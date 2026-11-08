"""Small data validation and one original baseline ensemble for measured cost."""
from stage189_common import *

if __name__=='__main__':
    ART.mkdir(parents=True,exist_ok=True)
    d,x,names=inputs(save=True)
    assert len(d['role'])==89033
    fit=energy.fit(('composition','X',x['X'],names['X'],d))
    old=load(ROOT/'ml/artifacts/stage87/predictions.npz')
    ref=np.full(len(d['role']),np.nan);ref[old['row']]=old['direct_cal']
    saved=load(ART/'composition_X_prediction.npz');active=d['role']>0
    delta=float(np.max(abs(ref[active]-saved['cal'][active])))
    assert delta<=1e-7 and np.isnan(saved['cal'][~active]).all()
    write('pilot_summary.json',dict(passed=True,fit=fit,baseline_max_abs_logdiff=delta,
        original_roles_N={str(r):int((d['role']==r).sum()) for r in [0,1,2,3]},
        quarantine_predictions=0,reserved_predictions=0,overall_complete=False))
