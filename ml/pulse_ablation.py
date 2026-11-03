"""Stage80 fixed scalar pulse-family ablation and unchanged source roles."""
import csv
import json
from datetime import datetime, timezone
import numpy as np
from audited_features import REPO, SCINTILLATORS, configuration, load
from pulse_information_audit import strong_shape_validity
from support_augmentation import arrays, begin, resources, save, table, metrics, indicator, boot_weights, LOW, COST, TAILS, masks

OUT=REPO/'workbook/stage80_energy_ml'
CACHE=REPO/'ntuples/energy_ml_stage80'
ART=REPO/'ml/artifacts/stage80'
JOBS=['fold0','fold1','fold2','final']
ARMS=['U','P']
SHAPE=[s+'_'+k for s in SCINTILLATORS for k in ['raw_peak','width']]


def stamp():return datetime.now(timezone.utc).isoformat()


def training_split(d,p,job):
    from group_risk import training_split as split
    return split(d,p,job)


def matrix(d,arm):return d['x'] if arm=='U' else np.column_stack([d['x'],d['shape']])


def data():
    if (CACHE/'input.npz').exists():return arrays(CACHE/'input.npz')
    from group_risk import inputs
    d=inputs();shape=arrays(CACHE/'shape.npz');np.testing.assert_array_equal(d['row'],shape['row'])
    d.update(shape=shape['shape'],shape_valid=shape['valid'])
    original,s,_=load();ix={int(r):i for i,r in enumerate(s['row'])};loc=np.array([ix[int(r)] for r in d['row']])
    st=s['status'][loc].astype(int)
    d.update(overflow=((st&4)!=0).any(1),weak=((st&1)!=0).any(1),shape_missing=(~shape['valid']).any(1),
             shape_all_valid=shape['valid'].all(1))
    return d


def diagnostic_masks(d):
    mm=masks(d)
    mm.update(pz50_100_E200_inf=mm['pz50_100']&mm['E200_inf'],shape_any_missing=d['shape_missing'],
        shape_all_valid=d['shape_all_valid'],scint_overflow=d['overflow'],scint_weak=d['weak'])
    return mm


def support(d,m):
    return dict(N=int(m.sum()),groups=len(np.unique(d['group'][m])),sources=len(np.unique(d['source'][m])),
        unique_incoming=len(np.unique(d['incoming'][m],axis=0)))


def finite(v):
    if isinstance(v,dict):return {k:finite(t) for k,t in v.items()}
    if isinstance(v,list):return [finite(t) for t in v]
    if isinstance(v,(float,np.floating)) and not np.isfinite(v):return '未测量'
    return v


def prepare():
    from group_risk import inputs
    start=begin()
    OUT.mkdir(exist_ok=True);CACHE.mkdir(exist_ok=True);ART.mkdir(exist_ok=True,parents=True)
    assert not (OUT/'proposal.json').exists()
    q=inputs();d,s,x=load();loc={int(r):i for i,r in enumerate(s['row'])};idx=np.array([loc[int(r)] for r in q['row']])
    np.testing.assert_array_equal(q['x'],x[idx])
    np.savez_compressed(CACHE/'identity.npz',row=q['row'],run=d['run'][q['row']],eventID=d['eventID'][q['row']],source=q['source'],
        raw_charge=s['raw_charge'][idx],status=s['status'][idx],baseline_rms=s['baseline_rms'][idx])
    manifest=list(csv.DictReader((REPO/'ml/configs/low_energy_files.tsv').open(),delimiter='\t'))
    sources=[r for r in manifest if int(r['index']) in set(q['source'])]
    assert len(sources)==254 and all(r['family']=='nominal' for r in sources)
    old=json.loads((REPO/'workbook/stage68_energy_ml/protocol.json').read_text())
    plan=dict(stage=80,prepared_utc=stamp(),features=configuration()['features'],shape_features=SHAPE,
        features_by_arm=dict(U=configuration()['features'],P=configuration()['features']+SHAPE),
        seed=2026110380,bootstrap_seed=2026111380,rounds=400,xgboost=old['xgboost'],xgboost_version='2.1.3',
        fold_by_group=old['fold_by_group'],fold_counts=old['fold_counts'],sources=sources,
        role_counts={r:int((q['role']==r).sum()) for r in ['train','cal','eval']},
        qa_rows=json.loads((REPO/'workbook/stage79_energy_ml/qa_plan.json').read_text())['qa_rows'],
        main_candidate='P_cal',max_formal_fits=8,CPUs_each=1,memory_MB_each=3000,wall_each_s=1800,
        CPU_total_s=7200,input_limit_bytes=10000000000,retained_limit_bytes=20000000,
        new_features='11 interleaved raw_peak,width; original62 unchanged; stage79 joint mask; no timing/RMS inputs',
        no_new_identities=True,no_F7_inference=True,training_policy='unit direct logE, same actual split mean(logE), boost_from_average=0, no scans',
        bootstrap='500 component-stratified original conservative source groups; eval seed, OOF+1, cal+2; fixed predictions/offset',
        uncertainty='excludes retraining/calibration/full genealogy/response/research selection; cal/eval development',
        status='proposal: freeze formal resources only after source audit and QA')
    save(OUT/'proposal.json',plan);print(json.dumps(dict(N=len(q['row']),sources=len(sources),role_counts=plan['role_counts'],**resources(start))))


if __name__=='__main__':prepare()
