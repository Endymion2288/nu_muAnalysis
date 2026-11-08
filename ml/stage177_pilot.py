from stage177_common import *
if __name__=='__main__':
    d,x,names=inputs();r=energy.fit(('slab','X',x['X'],names['X'],d))
    p=load(ART/'slab_X_prediction.npz');old=load(ROOT/'ml/artifacts/stage87/predictions.npz');ref=np.full(89033,np.nan);ref[old['row']]=old['direct_cal'];active=d['role']>0
    delta=float(np.max(abs(p['cal'][active]-ref[active])));assert delta<=1e-7
    assert np.isnan(p['cal'][~active]).all()
    write('pilot_summary.json',dict(passed=True,fit=r,baseline_max_abs_logdiff=delta,original_roles_exact=True,quarantine_predictions=0,reserved_predictions=0,overall_complete=False))
