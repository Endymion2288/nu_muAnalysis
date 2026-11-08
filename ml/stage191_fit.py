"""Exactly15 new fits with original seeds/capacity and no role0 inference."""
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
from stage191_common import *


if __name__=='__main__':
    assert not any(ART.glob('*')),'No refits after inspection'
    ART.mkdir(parents=True,exist_ok=True)
    d,x,names=inputs(save=True)
    with ProcessPoolExecutor(max_workers=5,mp_context=mp.get_context('fork')) as pool:
        fits=list(pool.map(energy.fit,[('ift',a,x[a],names[a],d) for a in ['X','A','V','C','S']]))
    write('fits.json',fits)
    old=load(ROOT/'ml/artifacts/stage87/predictions.npz');new=load(ART/'ift_X_prediction.npz')
    np.testing.assert_array_equal(new['cal'][old['row']],old['direct_cal'])
    energy.evaluate('ift',d,['X','A','V','C','S'],extra_references=['A','V','S'])
    from stage191_plot import main as plot
    plot()
    write('fit_summary.json',dict(passed=True,new_models_N=15,baseline_exact=True,
        roles_N={str(r):int((d['role']==r).sum()) for r in [0,1,2,3]},
        quarantine_predictions=0,reserved_predictions=0,promotion=False,overall_complete=False))
