"""Stage92 full originalcal/test accurateReference inference, no additional fits."""
import argparse
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import numpy as np

import accurate_posterior as original
from posterior_numerics import Reference, M
from support_augmentation import arrays,save,table,begin,resources

REPO=Path(__file__).resolve().parents[1]
OUT=REPO/'workbook/stage92_energy_ml'
CACHE=REPO/'ntuples/energy_ml_stage92'
SPOOL=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage92')
ROLES={'cal':2,'test':3}
CODE=['ml/evaluate_retrained_posterior.py','ml/report_retrained_posterior.py','ml/accurate_posterior.py',
      'ml/posterior_numerics.py','ml/support_augmentation.py','ml/report_resplit_energy.py','ml/resplit_energy.py',
      'ml/latent_transfer_diagnostics.py','ml/audited_features.py']


def load(role,limit=None):
    d=arrays(REPO/f'ntuples/energy_ml_stage89/input_{role}.npz')
    old=arrays(REPO/f'ntuples/energy_ml_stage89/predictions_{role}.npz')
    new=arrays(REPO/'ml/artifacts/stage92/posterior_parameters.npz')
    base=arrays(REPO/'ml/artifacts/stage87/predictions.npz')
    np.testing.assert_array_equal(d['row'],old['row'])
    ids=np.searchsorted(new['row'],d['row']);np.testing.assert_array_equal(new['row'][ids],d['row'])
    ib=np.searchsorted(base['row'],d['row']);np.testing.assert_array_equal(base['row'][ib],d['row'])
    for key in ['role','weight','truth_E_GeV','pz','input_missing']:np.testing.assert_array_equal(d[key],base[key][ib])
    d['bounded_cal']=base['bounded_cal'][ib];d['head']=new['head'][ids];d['b']=new['b'];d['T']=new['T']
    for k in ['quantiles','PIT','logscore','training_logscore','ESS_fraction']:d['old_'+k]=old['accurate_'+k]
    # Old accurate quantiles are starting guesses only; Reference maintains brackets and tests residuals.
    for j,k in enumerate(['q05','q16','median','q84','q95']):d['posterior_nominal_'+k]=old['accurate_quantiles'][:,j]
    if limit is not None:d={k:(v[:limit] if v.ndim and len(v)==len(ids) else v) for k,v in d.items()}
    expected=({'cal':11612,'test':13189}[role] if limit is None else limit)
    assert len(d['row'])==expected
    return d


def qa():
    start=begin();d=load('cal',40);v,rows,cost=original.infer(d)
    assert v['numerical_certified'].all()
    r=Reference(d['head'][0],d['pz'][0],float(d['b']),float(d['T']),'r')
    reverse,density,_=r.evaluate(float(np.log(d['truth_E_GeV'][0])))
    s=Reference(d['head'][0],d['pz'][0],float(d['b']),float(d['T']))
    forward,den,_=s.evaluate(float(np.log(d['truth_E_GeV'][0])))
    assert abs(reverse-forward)<=1e-7 and abs(np.log(density/den))<=1e-6
    projected=cost['CPU_s']/40*13189
    passed=bool(projected*1.2+120<10800)
    save(OUT/'inference_startup_QA.json',dict(passed=passed,identities=40,certified_N=int(v['numerical_certified'].sum()),
        reverse_CDF_difference=abs(reverse-forward),reverse_log_density_difference=abs(np.log(density/den)),
        primary_inference=cost,projected_test_CPU_s=projected,admission='projected40cal mean*testN*1.2+120reportsec <=10800; projection not guarantee',**resources(start)))
    table(OUT/'inference_startup_checks.tsv',[dict(error=r.pop('error'),**r) for r in rows])
    np.savez_compressed(CACHE/'inference_QA.npz',row=d['row'],**v)
    print((OUT/'inference_startup_QA.json').read_text(),flush=True)


def package_qa(role):
    d=arrays(CACHE/f'input_{role}.npz');q=arrays(CACHE/'inference_QA.npz')
    assert len(d['row'])=={'cal':11612,'test':13189}[role]
    if role=='cal':
        use={k:(v[:1] if v.ndim and len(v)==len(d['row']) else v) for k,v in d.items()}
        val,_,_=original.infer(use);assert val['numerical_certified'].all()
        np.testing.assert_allclose(val['accurate_quantiles'][0],q['accurate_quantiles'][0],atol=1e-8,rtol=0)
    print(role,'actualpayload identities and cal savedreference control passed',flush=True)


def submit():
    start=begin();assert not (OUT/'submission_inference.json').exists();assert json.loads((OUT/'inference_startup_QA.json').read_text())['passed']
    from datetime import datetime,timezone
    save(OUT/'inference_protocol.json',dict(stage=92,frozen_utc=datetime.now(timezone.utc).isoformat(),
        algorithm='unchangedstage88/89 adaptiveReference CDF/quantiles, originalnominalprior/median, newbT; oldaccuratequantiles onlyNewton guesses',
        roles={'cal':11612,'test':13189},new_fits=0,new_calibration=0,checkpoint_records=500,
        reference_QA=json.loads((OUT/'inference_startup_QA.json').read_text()),
        limits='two1CPU3000MB10800s Condorjobs, concurrency2, overallstage32400CPU/final20MB',
        outputs='allidentities retained; unknowns/failedflags explicit, no valid-only risks; finite and allcertified needed for numeric completion',
        evaluation='cachedsame-splittraditional/direct/bounded/stage89oldaccurateposterior, fixednominalmedian, originalgates and500componentincoming draws; no testselection/source95/newblind'))
    manifests=[]
    for role in ROLES:
        d=load(role);np.savez_compressed(CACHE/f'input_{role}.npz',**d)
        manifests.append(dict(role=role,N=len(d['row']),missing=int(d['input_missing'].sum()),incoming_keys=len(np.unique(d['key_id'])),weight_sum=float(d['weight'].sum())))
        paths=CODE+[f'ntuples/energy_ml_stage92/input_{role}.npz','ntuples/energy_ml_stage92/inference_QA.npz',
            'workbook/stage92_energy_ml/protocol.json','workbook/stage92_energy_ml/inference_protocol.json','workbook/stage92_energy_ml/posterior_calibration.json','workbook/stage87_energy_ml/prior.json',
            'workbook/stage87_energy_ml/metrics.tsv',f'workbook/stage89_energy_ml/{role}/metrics.tsv']
        archive=REPO/f'software/energy-ml-retrain-stage92-{role}.tar.gz'
        with tarfile.open(archive,'w:gz',compresslevel=1) as t:
            for name in paths:t.add(REPO/name,arcname=name)
        with tempfile.TemporaryDirectory(prefix='stage92_infer_package_') as tmp:
            with tarfile.open(archive) as t:t.extractall(tmp,filter='data')
            output=subprocess.check_output([sys.executable,'ml/evaluate_retrained_posterior.py','package-qa','--role',role],cwd=tmp,text=True)
        save(OUT/f'package_QA_{role}.json',dict(passed=True,output=output,archive_bytes=archive.stat().st_size))
    table(OUT/'inference_inputs.tsv',manifests)
    (SPOOL/'infer_v1.sh').write_bytes((REPO/'AnalysisZipFramework/submission/run_ml_retrained_evaluation.sh').read_bytes())
    output=subprocess.check_output(['condor_submit','-terse',str(REPO/'AnalysisZipFramework/submission/ml_retrained_evaluation.sub')],text=True)
    cluster=int(output.split('.')[0]);ads=json.loads(subprocess.check_output(['condor_q',str(cluster),'-json','-attributes','ClusterId,ProcId,RequestCpus,RequestMemory,MaxRuntime'],text=True))
    assert len(ads)==2 and all(a['RequestCpus']==1 and a['RequestMemory']==3000 and a['MaxRuntime']==10800 for a in ads)
    save(OUT/'submission_inference.json',dict(cluster=cluster,result=output,actual_ads=ads,**resources(start)));print(output,flush=True)


def worker(role):
    start=begin();out=OUT/role;out.mkdir(parents=True,exist_ok=True);d=arrays(CACHE/f'input_{role}.npz');package_qa(role)
    numerical_start=begin();n=len(d['row']);all_rows=[];combined={}
    # Local-scratch compact checkpoints retain every identity, including unknown/unprocessed values.
    # Reference is unchanged and event-local, so chunking does not change its numerics.
    for begin_index in range(0,n,500):
        end_index=min(n,begin_index+500)
        chunk={k:(a[begin_index:end_index] if a.ndim and len(a)==n else a) for k,a in d.items()}
        v,rows,_=original.infer(chunk)
        for key,a in v.items():
            if key not in combined:
                fill=False if a.dtype.kind=='b' else np.nan
                combined[key]=np.full((n,)+a.shape[1:],fill,dtype=a.dtype)
            combined[key][begin_index:end_index]=a
        all_rows.extend([dict(error=r.pop('error'),**r) for r in rows])
        np.savez_compressed(CACHE/f'predictions_{role}.npz',row=d['row'],completed_N=end_index,**combined)
        table(out/'numerical_checks.tsv',all_rows)
        save(out/'inference_resources.json',dict(completed_N=end_index,requested_N=n,checkpoint_records=500,
             includes='Reference calls plus local compact checkpoints; no network or calibration',**resources(numerical_start)))
        print('inferred',end_index,'/',n,'CPU',resources(numerical_start)['CPU_s'],flush=True)
    from report_retrained_posterior import report
    report(role,d,combined)
    save(out/'total_resources.json',resources(start))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['qa','package-qa','submit','worker']);p.add_argument('--role',choices=list(ROLES));a=p.parse_args()
    if a.action in ['package-qa','worker']:globals()[a.action.replace('-','_')](a.role)
    else:globals()[a.action]()
