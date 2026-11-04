"""Stage88 saved-posterior numerical audit, bounded train/cal only, zero fits."""
import argparse
import json
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

import numpy as np

from posterior_numerics import Reference, FixedGH, EDGES, PROBS
from support_augmentation import arrays, begin, resources, save, table

REPO = Path(__file__).resolve().parents[1]
OUT = REPO/'workbook/stage88_energy_ml'
CACHE = REPO/'ntuples/energy_ml_stage88'
SPOOL = Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage88')
CODE = ['ml/audit_posterior_integration.py', 'ml/posterior_numerics.py', 'ml/support_augmentation.py']


def load_selected(which):
    head = arrays(REPO/'ml/artifacts/stage87/posterior_parameters.npz')
    pred = arrays(REPO/'ml/artifacts/stage87/predictions.npz')
    split = arrays(REPO/'ntuples/energy_ml_stage87/split.npz')
    np.testing.assert_array_equal(head['row'], pred['row'])
    cal = np.flatnonzero(pred['role'] == 2); train = np.flatnonzero(pred['role'] == 1)
    if which == 'qa':
        use = cal[:40]
        expected = json.loads((REPO/'workbook/stage87_energy_ml/quadrature_QA.json').read_text())['identities']
        np.testing.assert_array_equal(head['row'][use], expected)
    else:
        p = json.loads((OUT/'protocol.json').read_text())
        use = np.r_[train[np.linspace(0, len(train)-1, p['train_N'], dtype=int)],
                    cal[np.linspace(0, len(cal)-1, p['cal_N'], dtype=int)]]
    assert not (pred['role'][use] == 3).any()
    d = {k:v[use] for k, v in pred.items()}
    d['head'] = head['head'][use];d['b'] = head['b'];d['T'] = head['T']
    for k in ['group', 'component', 'origin', 'origin_row', 'key_id', 'run', 'eventID']:
        d[k] = split[k][d['row']]
    np.testing.assert_array_equal(d['role'], split['role'][d['row']])
    np.testing.assert_array_equal(d['weight'], split['weight'][d['row']])
    # Rejoin actual observed status without fitted-charge substitution or ROOT.
    for k in ['wave_invalid', 'fit_failure', 'calo_invalid', 'negative_valid_raw']:
        d[k] = np.zeros(len(use), bool)
    for origin in np.unique(d['origin']):
        m = d['origin'] == origin;rr = d['origin_row'][m]
        filename = 'ntuples/energy_ml_stage56/readout.npz' if origin == 55 else f'ntuples/energy_ml_stage{origin}/support.npz'
        with np.load(REPO/filename) as z:
            if origin == 55:
                row = z['row'];idx = np.searchsorted(row, rr);np.testing.assert_array_equal(row[idx], rr)
            else:idx = rr
            status = z['status'][idx];calo = z['calo_status'][idx];raw = z['raw_charge'][idx]
        wave = 8|128|256;fit = wave|16|32|4
        d['wave_invalid'][m] = ((status&wave) != 0).any(1)
        d['fit_failure'][m] = ((status&(16|32)) != 0).any(1)
        d['calo_invalid'][m] = ((calo&fit) != 0).any(1)
        d['negative_valid_raw'][m] = ((raw < 0)&((status&wave) == 0)).any(1)
    return d


def ratios():
    return {k:np.array(v) for k,v in json.loads((REPO/'workbook/stage87_energy_ml/prior.json').read_text())['ratios'].items()}


def calculate(d, out, orders, label):
    start = begin();n = len(d['row']);ratio = ratios()['nominal'];b, T = float(d['b']), float(d['T'])
    method = {};timings = [];detail = [];refrows = [];cross = []
    allratios = ratios()
    for order in orders:
        tick = begin();gh = FixedGH(d['head'], d['pz'], b, T, order)
        method[order] = gh.summary(d['truth_E_GeV'], {'nominal':ratio})['nominal']
        timings.append(dict(method=f'cached_GH{order}_nominal',N=n,CDF_calls=gh.calls,**resources(tick)))
    refs = [];checks = []
    for i in range(n):
        tick = time.process_time()
        r = Reference(d['head'][i], d['pz'][i], b, T, 's')
        v = r.summary(d['truth_E_GeV'][i], ratio, method[32]['quantiles'][i]);refs.append(v)
        primary_CPU = time.process_time()-tick;tick = time.process_time()
        reverse = Reference(d['head'][i], d['pz'][i], b, T, 'r', eps=2e-11)
        queries = np.r_[np.log(EDGES[1:-1]), np.log(d['truth_E_GeV'][i]), v['quantiles']]
        ca = [];da = [];errs = [];low_density = 0
        for j,z in enumerate(queries):
            f, density, err = r.evaluate(z);g, other, err2 = reverse.evaluate(z,density=j>=8)
            ca.append(abs(f-g))
            if j>=8 and min(density, other) > 1e-7:
                da.append(abs(np.log(density)-np.log(other)))
            elif j>=8:
                low_density += 1
            errs.append(err+err2)
        # Independent reverse CDF verifies each main nominal quantile residual.
        F = np.r_[0., [reverse.evaluate(np.log(e),density=False)[0] for e in EDGES[1:-1]], 1.]
        mass = np.diff(F)*ratio;norm = mass.sum();prefix = np.r_[0.,mass.cumsum()]
        qcheck = []
        for z, q in zip(v['quantiles'], PROBS):
            k = np.clip(np.searchsorted(EDGES, np.exp(z), side='right')-1, 0, 8)
            qcheck.append(abs((prefix[k]+ratio[k]*(reverse.evaluate(z,density=False)[0]-F[k]))/norm-q))
        record = dict(row=int(d['row'][i]),role=int(d['role'][i]),group=str(d['group'][i]),
            max_abs_CDF_s_r=max(ca),max_abs_logdensity_s_r=max(da,default=0.),low_density_queries=low_density,max_combined_quad_error=max(errs),
            max_tail_bound=max(r.max_tail, reverse.max_tail),root_residual=v['root_residual'],
            reverse_quantile_probability_residual=max(qcheck),s_calls=r.calls,r_calls=reverse.calls,
            reference_precision_flags=r.precision_flags+reverse.precision_flags,
            reverse_density_step_difference=reverse.derivative_step_error,
            primary_summary_CPU_s=primary_CPU,reverse_crosscheck_CPU_s=time.process_time()-tick,
            global_CDF_lower=r.evaluate(np.log(.1056583755)+1e-12)[0],
            global_CDF_upper=r.evaluate(np.log(d['pz'][i])+40)[0],
            minimum_CDF_grid_increment=float(np.diff([r.evaluate(z)[0] for z in np.sort(queries)]).min()),
            integrand_evaluations=r.neval+reverse.neval)
        checks.append(record)
        refrows.append(dict(row=int(d['row'][i]),role=int(d['role'][i]),PIT=v['PIT'],log_density=v['log_density'],norm=v['norm'],
                            **{name:float(z) for name,z in zip(['q05','q16','median','q84','q95'],v['quantiles'])}))
        for order in orders:
            m = method[order]
            detail.append(dict(row=int(d['row'][i]),role=int(d['role'][i]),group=str(d['group'][i]),component=str(d['component'][i]),
                method=f'GH{order}',weight=float(d['weight'][i]),truth_E_GeV=float(d['truth_E_GeV'][i]),pz_GeV=float(d['pz'][i]),
                confirmed=bool(d['confirmed'][i]),input_missing=bool(d['input_missing'][i]),wave_invalid=bool(d['wave_invalid'][i]),
                fit_failure=bool(d['fit_failure'][i]),calo_invalid=bool(d['calo_invalid'][i]),negative_valid_raw=bool(d['negative_valid_raw'][i]),
                max_abs_edge_CDF=float(np.max(abs(m['F'][i]-v['F']))),abs_PIT=float(abs(m['PIT'][i]-v['PIT'])),
                abs_log_density=float(abs(m['log_density'][i]-v['log_density'])),
                max_abs_quantile_logE=float(np.max(abs(m['quantiles'][i]-v['quantiles']))),
                median_shift_logE=float(m['quantiles'][i,2]-v['quantiles'][2]),
                GH_logerror=float(m['quantiles'][i,2]-np.log(d['truth_E_GeV'][i])),reference_logerror=float(v['quantiles'][2]-np.log(d['truth_E_GeV'][i]))))
        if (i+1)%40 == 0:print(label, i+1, '/',n, 'CPU',resources(start)['CPU_s'],flush=True)
        assert resources(start)['CPU_s'] < 1500, 'bounded audit budget; no selecting shortened output'
    table(out/f'{label}_errors.tsv',detail);table(out/f'{label}_reference.tsv',refrows);table(out/f'{label}_crosscheck.tsv',checks)
    table(out/f'{label}_timings.tsv',timings)
    saved=dict(row=d['row'],reference_F=np.array([r['F'] for r in refs]),
               reference_quantiles=np.array([r['quantiles'] for r in refs]),
               reference_PIT=np.array([r['PIT'] for r in refs]),reference_log_density=np.array([r['log_density'] for r in refs]))
    for order,m in method.items():
        for key in ['F','quantiles','PIT','log_density']:saved[f'GH{order}_{key}']=m[key]
    np.savez_compressed(out/f'{label}_numerical_values.npz',**saved)
    refsummary = dict(N=n,max_CDF_s_r=max(v['max_abs_CDF_s_r'] for v in checks),
        max_logdensity_s_r=max(v['max_abs_logdensity_s_r'] for v in checks),max_quad_error=max(v['max_combined_quad_error'] for v in checks),
        max_tail_bound=max(v['max_tail_bound'] for v in checks),max_reverse_quantile_residual=max(v['reverse_quantile_probability_residual'] for v in checks),
        total_integrand_evaluations=sum(v['integrand_evaluations'] for v in checks),**resources(start))
    refsummary.update(primary_summary_CPU_s=sum(v['primary_summary_CPU_s'] for v in checks),
        reverse_crosscheck_CPU_s=sum(v['reverse_crosscheck_CPU_s'] for v in checks),
        max_density_step_difference=max(v['reverse_density_step_difference'] for v in checks),
        reference_precision_flags=sum(v['reference_precision_flags'] for v in checks),
        uncertainty='quad error estimates plus analytic omitted-normal-tail bounds and two-step finite-difference check; not physics/statistical intervals')
    save(out/f'{label}_reference_QA.json',refsummary)
    return method, refs, refsummary


def qa():
    start = begin();OUT.mkdir(parents=True, exist_ok=True)
    d = load_selected('qa');method, refs, check = calculate(d,OUT,[32,64,128,256],'qa')
    # Existing production implementation is an independent check on cached GH.
    from transfer_posterior import posterior_summary
    tick = begin();old = posterior_summary(d['head'], d['pz'], d['truth_E_GeV'], EDGES, ratios(),float(d['b']),float(d['T']))
    original_resources = resources(tick)
    tick = begin();cache = FixedGH(d['head'],d['pz'],float(d['b']),float(d['T']),32)
    new = cache.summary(d['truth_E_GeV'],ratios());new_resources = resources(tick)
    differences = []
    for name in ratios():
        for j,key in enumerate(['q05','q16','median','q84','q95']):
            differences.append(float(np.max(abs(old[name+'_'+key]-new[name]['quantiles'][:,j]))))
        differences.append(float(np.max(abs(old[name+'_pit']-new[name]['PIT']))))
        differences.append(float(np.max(abs(old[name+'_logscore']-new[name]['log_density']))))
    maxdiff = max(differences);assert maxdiff < 1e-8,maxdiff
    np.testing.assert_allclose(method[32]['PIT'],d['posterior_nominal_pit'],atol=1e-10,rtol=0)
    for j,key in enumerate(['q05','q16','median','q84','q95']):
        np.testing.assert_allclose(method[32]['quantiles'][:,j],d['posterior_nominal_'+key],atol=1e-8,rtol=0)
    assert check['max_CDF_s_r'] < 1e-7 and check['max_logdensity_s_r'] < 1e-6,check
    save(OUT/'startup_QA.json',dict(passed=True,identities=d['row'].tolist(),new_fits=0,new_ROOT_reads=0,
        cached_vs_original_max_difference=maxdiff,original_four_prior=original_resources,cached_four_prior=new_resources,
        cached_CDF_calls=cache.calls,reference=check,**resources(start)))
    print('40 identity reference and cached-production equivalence QA passed',flush=True)


def run():
    start = begin();d = arrays(CACHE/'input.npz');p = json.loads((OUT/'protocol.json').read_text())
    assert len(d['row']) == p['cal_N']+p['train_N'] and not (d['role'] == 3).any()
    method, refs, check = calculate(d,OUT,p['orders'],'audit')
    # Fixed b/T cross, no optimization. Both integration directions at all truth E.
    calibration = [];calibration_values = {}
    for db,dT in [(0.,0.),(-.01,0.),(.01,0.),(0.,-.05),(0.,.05)]:
        take = d['role'] == 2;ids = np.flatnonzero(take);w = d['weight'][take];logref = [];logGH = []
        b = float(d['b'])+db;T = float(d['T'])+dT
        gh = FixedGH(d['head'][take],d['pz'][take],b,T,32)
        _,den = gh.evaluate(np.log(d['truth_E_GeV'][take]),density=True)
        logGH = np.log(den[:,0])
        for i in ids:
            ref = Reference(d['head'][i],d['pz'][i],b,T,'s')
            logref.append(np.log(ref.evaluate(np.log(d['truth_E_GeV'][i]))[1]))
        calibration.append(dict(delta_b=db,delta_T=dT,N=len(ids),fixed_subset_weighted_NLL_GH32=float(-np.average(logGH,weights=w)),
            fixed_subset_weighted_NLL_reference=float(-np.average(logref,weights=w)),
            objective_difference=float(np.average(np.array(logref)-logGH,weights=w)),refitted=False))
        calibration_values[f'point{len(calibration)-1}_GH32']=np.array(logGH)
        calibration_values[f'point{len(calibration)-1}_reference']=np.array(logref)
    table(OUT/'fixed_calibration_objectives.tsv',calibration)
    np.savez_compressed(OUT/'calibration_numerical_values.npz',**calibration_values)
    summarize(d,method,refs,check)
    validate()
    save(OUT/'resources.json',dict(new_fits=0,new_ROOT_reads=0,test_evaluations=0,**resources(start)))


def summarize(d,methods,refs,check):
    rows=list(__import__('csv').DictReader((OUT/'audit_errors.tsv').open(),delimiter='\t'))
    groups = dict(all=np.ones(len(d['row']),bool),train=d['role']==1,cal=d['role']==2,
        E50_100=(d['truth_E_GeV']>=50)&(d['truth_E_GeV']<100),E100_200=(d['truth_E_GeV']>=100)&(d['truth_E_GeV']<200),
        lowpz_truehighE=(d['pz']<100)&(d['truth_E_GeV']>=200),high_y=d['y_lepton']>=.8,unconfirmed=~d['confirmed'],
        input_missing=d['input_missing'],wave_invalid=d['wave_invalid'],fit_failure=d['fit_failure'],calo_invalid=d['calo_invalid'],
        negative_valid_raw=d['negative_valid_raw'])
    for c in ['pi','k','charm']:groups['component_'+c]=d['component']==c
    result=[]
    for name,m in groups.items():
        for order in methods:
            r=[v for v,keep in zip(rows[ list(methods).index(order)::len(methods)],m) if keep]
            item=dict(stratum=name,method=f'GH{order}',N=len(r),unique_incoming=len(np.unique(d['key_id'][m])),groups=len(np.unique(d['group'][m])))
            for key,limit in [('max_abs_edge_CDF',1e-4),('abs_PIT',1e-4),('max_abs_quantile_logE',1e-3),('abs_log_density',1e-3)]:
                x=np.array([float(v[key]) for v in r]);item.update({key+'_max':float(x.max()) if len(x) else '未测量',key+'_median':float(np.median(x)) if len(x) else '未测量',key+'_failure_N':int((x>limit).sum())})
            result.append(item)
    table(OUT/'summary.tsv',result)
    save(OUT/'decisions.json',dict(reference_agreement=bool(check['max_CDF_s_r']<1e-7 and check['max_logdensity_s_r']<1e-6),
        numerical_convergence_limits=dict(CDF_abs=1e-4,quantile_abs_logE=1e-3,log_density_abs=1e-3),
        deployment='retain existing deployment; no fitting or test-risk/model/prior selection',
        scope='deterministic train/cal subset; numerical checks, not source statistics or physical uncertainty',
        training32_bias_repaired=False))


def validate():
    """Recompute stored per-event errors and fixed objectives with numpy."""
    import csv
    start=begin();d=arrays(CACHE/'input.npz');v=arrays(OUT/'audit_numerical_values.npz')
    np.testing.assert_array_equal(v['row'],d['row'])
    rows=list(csv.DictReader((OUT/'audit_errors.tsv').open(),delimiter='\t'))
    lookup={int(row):i for i,row in enumerate(v['row'])};maximum=0.;count=0
    for r in rows:
        i=lookup[int(r['row'])];name=r['method']
        values=dict(max_abs_edge_CDF=np.max(np.abs(v[name+'_F'][i]-v['reference_F'][i])),
                    abs_PIT=abs(v[name+'_PIT'][i]-v['reference_PIT'][i]),
                    abs_log_density=abs(v[name+'_log_density'][i]-v['reference_log_density'][i]),
                    max_abs_quantile_logE=np.max(np.abs(v[name+'_quantiles'][i]-v['reference_quantiles'][i])),
                    median_shift_logE=v[name+'_quantiles'][i,2]-v['reference_quantiles'][i,2])
        for key,x in values.items():
            diff=abs(float(r[key])-x);assert diff<1e-12;maximum=max(maximum,float(diff));count+=1
    # GH32 is the cached stage87 production calculation; selected rows exactly join.
    np.testing.assert_allclose(v['GH32_PIT'],d['posterior_nominal_pit'],atol=1e-10,rtol=0)
    for j,key in enumerate(['q05','q16','median','q84','q95']):
        np.testing.assert_allclose(v['GH32_quantiles'][:,j],d['posterior_nominal_'+key],atol=1e-8,rtol=0)
    cal=list(csv.DictReader((OUT/'fixed_calibration_objectives.tsv').open(),delimiter='\t'))
    cv=arrays(OUT/'calibration_numerical_values.npz');w=d['weight'][d['role']==2]
    for j,r in enumerate(cal):
        a=-np.dot(w,cv[f'point{j}_GH32'])/w.sum();b=-np.dot(w,cv[f'point{j}_reference'])/w.sum()
        for key,val in [('fixed_subset_weighted_NLL_GH32',a),('fixed_subset_weighted_NLL_reference',b),('objective_difference',a-b)]:
            diff=abs(float(r[key])-val);assert diff<1e-12;maximum=max(maximum,float(diff));count+=1
    source=json.loads((OUT/'protocol.json').read_text());assert len(d['row'])==source['cal_N']+source['train_N']
    assert not (d['role']==3).any()
    check=list(csv.DictReader((OUT/'audit_crosscheck.tsv').open(),delimiter='\t'))
    assert len(check)==len(d['row'])
    for r in check:
        assert abs(float(r['global_CDF_lower']))<1e-8
        assert abs(float(r['global_CDF_upper'])-1)<1e-8
        assert float(r['minimum_CDF_grid_increment'])>=-1e-10
    save(OUT/'independent_validation.json',dict(passed=True,checked_values=count,max_absolute_difference=maximum,
        identities=len(d['row']),new_fits=0,test_evaluations=0,GH32_matches_saved_stage87=True,
        endpoint_and_CDF_monotonicity=True,scope='stored-value arithmetic and production equivalence; adaptive reference separately crosschecked by reverse CDF',**resources(start)))


def submit():
    assert not (OUT/'submission.json').exists()
    d = load_selected('audit');CACHE.mkdir(exist_ok=True,parents=True);np.savez_compressed(CACHE/'input.npz',**d)
    # Freeze the exact actual input identities and small transfer payload before submitting.
    save(OUT/'input_manifest.json',dict(rows=d['row'].tolist(),roles=d['role'].tolist(),N=len(d['row']),test_N=0,input_bytes=(CACHE/'input.npz').stat().st_size))
    paths=CODE+['ntuples/energy_ml_stage88/input.npz','workbook/stage88_energy_ml/protocol.json','workbook/stage87_energy_ml/prior.json']
    archive=REPO/'software/energy-ml-numerics-stage88.tar.gz'
    with tarfile.open(archive,'w:gz',compresslevel=1) as tar:
        for name in paths:tar.add(REPO/name,arcname=name)
    with tempfile.TemporaryDirectory(prefix='stage88_package_') as tmp:
        with tarfile.open(archive) as tar:tar.extractall(tmp,filter='data')
        result=subprocess.check_output([sys.executable,'ml/audit_posterior_integration.py','package-qa'],cwd=tmp,text=True)
    save(OUT/'package_QA.json',dict(passed=True,actual_payload=result,archive_bytes=archive.stat().st_size,new_fits=0))
    (SPOOL/'logs').mkdir(parents=True,exist_ok=True)
    (SPOOL/'worker_v1.sh').write_bytes((REPO/'AnalysisZipFramework/submission/run_ml_posterior_numerics.sh').read_bytes())
    result=subprocess.check_output(['condor_submit','-terse',str(REPO/'AnalysisZipFramework/submission/ml_posterior_numerics.sub')],text=True)
    cluster=int(result.split('.')[0]);save(OUT/'submission.json',dict(cluster=cluster,result=result,paths=paths))
    print(result,flush=True)


def package_qa():
    d=arrays(CACHE/'input.npz');assert not (d['role']==3).any()
    r=Reference(d['head'][0],d['pz'][0],float(d['b']),float(d['T']))
    s=Reference(d['head'][0],d['pz'][0],float(d['b']),float(d['T']),'r')
    a=r.evaluate(np.log(d['truth_E_GeV'][0]));b=s.evaluate(np.log(d['truth_E_GeV'][0]))
    assert abs(a[0]-b[0])<1e-7 and abs(np.log(a[1]/b[1]))<1e-6
    print('actual payload: identity/role and independent CDF/density passed, zero fit')


def collect(result, recover_report=False):
    cluster=json.loads((OUT/'submission.json').read_text())['cluster'];log=SPOOL/'logs'/f'{cluster}.log'
    h=json.loads(subprocess.check_output(['condor_history','-userlog',str(log),'-json'],text=True,timeout=30))
    assert len(h)==1 and h[0]['NumJobStarts']==1,h
    if h[0]['ExitCode'] != 0:
        err=(SPOOL/'logs'/f'{cluster}.0.err').read_text()
        assert recover_report and h[0]['ExitCode']==1 and 'in summarize' in err and 'is not JSON serializable' in err,err
        (OUT/'worker_error.txt').write_text(err)
        (OUT/'worker_stdout.txt').write_text((SPOOL/'logs'/f'{cluster}.0.out').read_text())
    save(OUT/'history.json',h);(OUT/'condor.txt').write_text('\n'.join(s.rstrip() for s in log.read_text().splitlines())+'\n')
    with tarfile.open(result) as tar:
        for item in tar.getmembers():
            if item.isdir():continue
            assert item.isfile() and item.name.startswith('workbook/stage88_energy_ml/') and '..' not in item.name
            path=REPO/item.name;value=tar.extractfile(item).read()
            if path.exists():assert path.read_bytes()==value,path
            else:path.write_bytes(value)
    print('stage88 result collected; formal exit code',h[0]['ExitCode'])


def recover_report():
    """Finish only reporting/validation after the known JSON scalar failure."""
    start=begin();h=json.loads((OUT/'history.json').read_text());assert h[0]['ExitCode']==1
    d=arrays(CACHE/'input.npz');v=arrays(OUT/'audit_numerical_values.npz')
    assert len(v['row'])==len(d['row'])==552
    methods={order:{key:v[f'GH{order}_{key}'] for key in ['F','quantiles','PIT','log_density']} for order in [32,64,128,256]}
    check=json.loads((OUT/'audit_reference_QA.json').read_text())
    summarize(d,methods,[],check)
    validate()
    save(OUT/'report_recovery.json',dict(completed=True,formal_job_exitcode=1,formal_jobs=1,Condor_retries=0,
        reason='numpy bool JSON serialization in summarize after all552 numerical cases and5cal points finished',
        change='cast metadata decision to Python bool; numerical integration/model/calibration unchanged',
        additional_integration_evaluations=0,new_fits=0,new_ROOT_reads=0,**resources(start)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['qa','run','submit','package-qa','collect','recover-report']);p.add_argument('--result');p.add_argument('--recover-report',action='store_true')
    a=p.parse_args()
    if a.action=='collect':collect(a.result,a.recover_report)
    elif a.action=='recover-report':recover_report()
    elif a.action=='package-qa':package_qa()
    else:globals()[a.action]()
