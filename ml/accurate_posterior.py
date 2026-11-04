"""Stage89: frozen accurate inference on complete existing cal/test; zero fitting."""
import argparse
import csv
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import numpy as np

from posterior_numerics import Reference, FixedGH, EDGES, M
from support_augmentation import arrays, save, table, begin, resources

REPO=Path(__file__).resolve().parents[1]
OUT=REPO/'workbook/stage89_energy_ml'
CACHE=REPO/'ntuples/energy_ml_stage89'
SPOOL=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage89')
ROLES={'cal':2,'test':3}
CODE=['ml/accurate_posterior.py','ml/report_accurate_posterior.py','ml/posterior_numerics.py','ml/support_augmentation.py',
      'ml/report_resplit_energy.py','ml/resplit_energy.py','ml/latent_transfer_diagnostics.py','ml/audited_features.py']


def prior():
    return np.array(json.loads((REPO/'workbook/stage87_energy_ml/prior.json').read_text())['ratios']['nominal'])


def load_role(role,limit=None):
    head=arrays(REPO/'ml/artifacts/stage87/posterior_parameters.npz')
    pred=arrays(REPO/'ml/artifacts/stage87/predictions.npz');split=arrays(REPO/'ntuples/energy_ml_stage87/split.npz')
    np.testing.assert_array_equal(head['row'],pred['row'])
    use=np.flatnonzero(pred['role']==ROLES[role])
    if limit is not None:use=use[:limit]
    keep=['row','role','weight','truth_E_GeV','y_lepton','confirmed','pz','input_missing','direct_cal',
          'posterior_nominal_median','posterior_nominal_q05','posterior_nominal_q16','posterior_nominal_q84','posterior_nominal_q95',
          'posterior_nominal_pit','posterior_nominal_logscore','posterior_nominal_ESS_fraction']
    d={k:pred[k][use] for k in keep};d.update(head=head['head'][use],b=head['b'],T=head['T'])
    for k in ['group','component','block','key_id','incoming','origin','origin_row','run','eventID']:
        d[k]=split[k][d['row']]
    np.testing.assert_array_equal(d['role'],split['role'][d['row']]);np.testing.assert_array_equal(d['weight'],split['weight'][d['row']])
    assert json.loads((REPO/'workbook/stage87_energy_ml/split_audit.json').read_text())['unknown_transfer_labels']==0
    d['label_physical']=np.ones(len(use),bool)
    for k in ['wave_invalid','fit_failure','calo_invalid','negative_valid_raw']:d[k]=np.zeros(len(use),bool)
    for origin in np.unique(d['origin']):
        m=d['origin']==origin;rr=d['origin_row'][m]
        name='ntuples/energy_ml_stage56/readout.npz' if origin==55 else f'ntuples/energy_ml_stage{origin}/support.npz'
        with np.load(REPO/name) as z:
            if origin==55:
                rows=z['row'];ix=np.searchsorted(rows,rr);np.testing.assert_array_equal(rows[ix],rr)
            else:ix=rr
            status=z['status'][ix];calo=z['calo_status'][ix];raw=z['raw_charge'][ix]
        wave=8|128|256;fit=wave|16|32|4
        d['wave_invalid'][m]=((status&wave)!=0).any(1);d['fit_failure'][m]=((status&(16|32))!=0).any(1)
        d['calo_invalid'][m]=((calo&fit)!=0).any(1);d['negative_valid_raw'][m]=((raw<0)&((status&wave)==0)).any(1)
    assert np.isfinite(d['head']).all() and (d['pz']>50).all()
    return d


def infer(d,progress=False):
    start=begin();n=len(d['row']);ratio=prior();b,T=float(d['b']),float(d['T'])
    values=dict(accurate_quantiles=np.full((n,5),np.nan),accurate_PIT=np.full(n,np.nan),
        accurate_logscore=np.full(n,np.nan),accurate_training_logscore=np.full(n,np.nan),accurate_F=np.full((n,10),np.nan),
        accurate_ESS_fraction=np.full(n,np.nan),numerical_certified=np.zeros(n,bool))
    diagnostics=[]
    for i in range(n):
        guesses=np.array([d['posterior_nominal_'+q][i] for q in ['q05','q16','median','q84','q95']])
        r=Reference(d['head'][i],d['pz'][i],b,T,'s')
        error='';lo=hi=inc=root=np.nan
        try:
            v=r.summary(d['truth_E_GeV'][i],ratio,guesses)
            lo=r.evaluate(np.log(M)+1e-12)[0];hi=r.evaluate(np.log(d['pz'][i])+40)[0]
            queries=np.sort(np.r_[np.log(EDGES[1:-1]),np.log(d['truth_E_GeV'][i]),v['quantiles']])
            inc=float(np.diff([r.evaluate(z)[0] for z in queries]).min());root=v['root_residual']
            values['accurate_quantiles'][i]=v['quantiles'];values['accurate_PIT'][i]=v['PIT']
            values['accurate_logscore'][i]=v['log_density'];values['accurate_F'][i]=v['F']
            k=np.searchsorted(EDGES,d['truth_E_GeV'][i],side='right')-1
            values['accurate_training_logscore'][i]=v['log_density']-np.log(ratio[k])+np.log(v['norm'])
            values['accurate_ESS_fraction'][i]=v['norm']**2/(np.diff(v['F'])*ratio**2).sum()
            values['numerical_certified'][i]=bool(abs(lo)<1e-8 and abs(hi-1)<1e-8 and inc>=-1e-9 and
                root<1e-7 and r.max_error<1e-9 and r.max_tail<1e-10 and np.isfinite(v['log_density']) and
                np.diff(v['quantiles']).min()>=0 and 0<=v['PIT']<=1)
        except (ArithmeticError,AssertionError,ValueError) as exc:
            # Preserve the row and explicit failure: no replacement or favorable-case selection.
            error=f'{type(exc).__name__}: {exc}'
        diagnostics.append(dict(row=int(d['row'][i]),certified=bool(values['numerical_certified'][i]),error=error,
            quad_error=r.max_error,tail_bound=r.max_tail,quad_precision_flags=r.precision_flags,root_residual=root,
            global_CDF_lower=lo,global_CDF_upper=hi,minimum_CDF_increment=inc,CDF_calls=r.calls,integrand_evaluations=r.neval))
        if progress and (i+1)%500==0:print('inferred',i+1,'/',n,'CPU',resources(start)['CPU_s'],flush=True)
    return values,diagnostics,resources(start)


def qa():
    start=begin();OUT.mkdir(parents=True,exist_ok=True);d=load_role('cal',40)
    expected=list(csv.DictReader((REPO/'workbook/stage88_energy_ml/qa_reference.tsv').open(),delimiter='\t'))
    np.testing.assert_array_equal(d['row'],[int(v['row']) for v in expected])
    v,diagnostics,cost=infer(d)
    assert v['numerical_certified'].all()
    difference=0.
    for i,r in enumerate(expected):
        for key,k in [('PIT','accurate_PIT'),('log_density','accurate_logscore')]:difference=max(difference,abs(float(r[key])-v[k][i]))
        for j,key in enumerate(['q05','q16','median','q84','q95']):difference=max(difference,abs(float(r[key])-v['accurate_quantiles'][i,j]))
    assert difference<1e-8,difference
    # Existing independently certified40 reference values plus one fresh reverse control.
    reverse=Reference(d['head'][0],d['pz'][0],float(d['b']),float(d['T']),'r',eps=2e-11)
    cp,den,_=reverse.evaluate(np.log(d['truth_E_GeV'][0]))
    primary=Reference(d['head'][0],d['pz'][0],float(d['b']),float(d['T']))
    f,density,_=primary.evaluate(np.log(d['truth_E_GeV'][0]))
    assert abs(cp-f)<1e-7 and abs(np.log(den/density))<1e-6
    table(OUT/'startup_numerical_checks.tsv',diagnostics)
    save(OUT/'startup_QA.json',dict(passed=True,rows=d['row'].tolist(),maximum_difference_from_stage88=difference,
        new_reverse_CDF_difference=abs(cp-f),new_reverse_logdensity_difference=float(abs(np.log(den/density))),
        inference_resources=cost,zero_fits=True,zero_test_evaluations=True,**resources(start)))
    CACHE.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(CACHE/'control.npz',head=d['head'][:1],pz=d['pz'][:1],truth_E_GeV=d['truth_E_GeV'][:1],
        guesses=d['posterior_nominal_median'][:1],b=d['b'],T=d['T'],expected_quantiles=v['accurate_quantiles'][:1],
        expected_PIT=v['accurate_PIT'][:1],expected_logscore=v['accurate_logscore'][:1])
    print('40 actual cal identities and exact stage88 reference equivalence passed; no test evaluation',flush=True)


def package_qa(role):
    d=arrays(CACHE/f'input_{role}.npz');assert len(d['row'])=={'cal':11612,'test':13189}[role]
    assert (d['role']==ROLES[role]).all()
    _,gid=np.unique(d['key_id'],return_inverse=True);np.testing.assert_allclose(np.bincount(gid,weights=d['weight']),1,atol=1e-12)
    c=arrays(CACHE/'control.npz');r=Reference(c['head'][0],c['pz'][0],float(c['b']),float(c['T']))
    result=r.summary(c['truth_E_GeV'][0],prior(),c['expected_quantiles'][0])
    np.testing.assert_allclose(result['quantiles'],c['expected_quantiles'][0],atol=1e-8,rtol=0)
    assert abs(result['PIT']-c['expected_PIT'][0])<1e-8
    # Exercise JSON serialization of real numerical metadata before job submission.
    json.dumps(dict(certified=bool(r.max_error<1e-9),resources=resources(begin())),allow_nan=False)
    print(role,'actual payload identity/weights and fixed cal reference control passed; zero fits/no test risk')


def submit():
    start=begin();assert not (OUT/'submission.json').exists()
    p=json.loads((OUT/'protocol.json').read_text());assert p['algorithm_frozen_before_test']
    roles={role:load_role(role) for role in ROLES}
    a,b=roles['cal'],roles['test']
    for key in ['key_id','group']:assert not set(a[key])&set(b[key])
    assert not set(map(tuple,a['incoming']))&set(map(tuple,b['incoming']))
    manifest=[]
    for role,d in roles.items():
        np.savez_compressed(CACHE/f'input_{role}.npz',**d)
        w=d['weight'];manifest.append(dict(role=role,N=len(w),unique_incoming=len(np.unique(d['key_id'])),groups=len(np.unique(d['group'])),blocks=len(np.unique(d['block'])),
            weight_sum=float(w.sum()),record_ESS=float(w.sum()**2/(w@w)),missing_N=int(d['input_missing'].sum()),fit_failure_N=int(d['fit_failure'].sum()),
            wave_invalid_N=int(d['wave_invalid'].sum()),calo_invalid_N=int(d['calo_invalid'].sum()),K_N=int((d['component']=='k').sum()),
            input_bytes=(CACHE/f'input_{role}.npz').stat().st_size))
        paths=CODE+[f'ntuples/energy_ml_stage89/input_{role}.npz','ntuples/energy_ml_stage89/control.npz',
            'workbook/stage89_energy_ml/protocol.json','workbook/stage87_energy_ml/prior.json',
            'workbook/stage87_energy_ml/metrics.tsv','workbook/stage87_energy_ml/posterior_coverage.tsv']
        archive=REPO/f'software/energy-ml-accurate-stage89-{role}.tar.gz'
        with tarfile.open(archive,'w:gz',compresslevel=1) as t:
            for name in paths:t.add(REPO/name,arcname=name)
        with tempfile.TemporaryDirectory(prefix='stage89_package_') as tmp:
            with tarfile.open(archive) as t:t.extractall(tmp,filter='data')
            result=subprocess.check_output([sys.executable,'ml/accurate_posterior.py','package-qa','--role',role],cwd=tmp,text=True)
        save(OUT/f'package_QA_{role}.json',dict(passed=True,actual_payload=result,archive_bytes=archive.stat().st_size,zero_fits=True))
    table(OUT/'input_counts.tsv',manifest)
    (SPOOL/'logs').mkdir(parents=True,exist_ok=True)
    (SPOOL/'worker_v1.sh').write_bytes((REPO/'AnalysisZipFramework/submission/run_ml_accurate_posterior.sh').read_bytes())
    result=subprocess.check_output(['condor_submit','-terse',str(REPO/'AnalysisZipFramework/submission/ml_accurate_posterior.sub')],text=True)
    cluster=int(result.split('.')[0]);ads=json.loads(subprocess.check_output(['condor_q',str(cluster),'-json','-attributes','ClusterId,ProcId,Args,RequestCpus,RequestMemory,MaxRuntime'],text=True))
    assert len(ads)==2 and all(a['RequestCpus']==1 and a['RequestMemory']==3000 and a['MaxRuntime']==5400 for a in ads)
    save(OUT/'submission.json',dict(cluster=cluster,result=result,actual_ads=ads,**resources(start)))
    print(result,flush=True)


def worker(role):
    start=begin();out=OUT/role;out.mkdir(parents=True,exist_ok=True)
    d=arrays(CACHE/f'input_{role}.npz');package_qa(role)
    v,diagnostics,cost=infer(d,True)
    np.savez_compressed(CACHE/f'predictions_{role}.npz',row=d['row'],**v)
    table(out/'numerical_checks.tsv',diagnostics);save(out/'inference_resources.json',cost)
    from report_accurate_posterior import report
    report(role,d,v)
    save(out/'total_resources.json',dict(role=role,new_fits=0,new_ROOT_reads=0,**resources(start)))


def collect(role,result):
    cluster=json.loads((OUT/'submission.json').read_text())['cluster'];proc={'cal':0,'test':1}[role]
    log=SPOOL/'logs'/f'{cluster}.{proc}.log'
    h=json.loads(subprocess.check_output(['condor_history','-userlog',str(log),'-json'],text=True,timeout=30))
    save(OUT/f'history_{role}.json',h)
    assert len(h)==1 and h[0]['ExitCode']==0 and h[0]['NumJobStarts']==1,h
    (OUT/f'condor_{role}.txt').write_text('\n'.join(line.rstrip() for line in log.read_text().splitlines())+'\n')
    with tarfile.open(result) as t:
        for item in t.getmembers():
            if item.isdir():continue
            assert item.isfile() and '..' not in item.name and (item.name.startswith(f'workbook/stage89_energy_ml/{role}/') or item.name==f'ntuples/energy_ml_stage89/predictions_{role}.npz')
            path=REPO/item.name;value=t.extractfile(item).read();path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists():assert path.read_bytes()==value
            else:path.write_bytes(value)
    print(role,'one job once exit0, collected')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['qa','package-qa','submit','worker','collect']);p.add_argument('--role',choices=list(ROLES));p.add_argument('--result')
    a=p.parse_args()
    if a.action=='worker':worker(a.role)
    elif a.action=='package-qa':package_qa(a.role)
    elif a.action=='collect':collect(a.role,a.result)
    else:globals()[a.action]()
