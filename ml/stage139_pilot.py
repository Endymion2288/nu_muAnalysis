"""Measured nonlinear-profile cost and convergence before coverage-toy scale."""
import json
import resource
import time
from pathlib import Path
import numpy as np
from stage133_common import load
from stage136_analysis import TRUTH,RECO,PZ,precision
from stage119_curve_common import weights
from stage139_likelihood import lr,fit,loglike

OUT=Path('workbook/stage139_energy_ml');CACHE=Path('ntuples/energy_ml_stage139')

def main():
    tick=time.perf_counter();cpu=time.process_time()
    d=load('ntuples/energy_ml_stage119/old_input.npz')
    pred=load('ml/artifacts/stage129/depth_predictions.npz')
    cal=np.flatnonzero(d['role']==2);test=d['role']==3
    _,first=np.unique(d['incoming'][cal],axis=0,return_index=True)
    rows=cal[np.sort(first)]
    truebin=np.searchsorted(TRUTH,d['truth_E_GeV'],side='right')-1
    assert ((truebin[rows]>=0)&(truebin[rows]<7)).all()
    fraction=np.bincount(truebin[test],weights=weights(d['incoming'][test]),minlength=7)
    fraction/=fraction.sum()
    trad=np.searchsorted(RECO,np.exp(pred['traditional'][rows]),side='right')-1
    direct=np.searchsorted(RECO,np.exp(pred['direct_cal'][rows]),side='right')-1
    pz=np.searchsorted(PZ,d['pz'][rows],side='right')-1
    maps={'traditional':(trad,9),'direct62':(direct,9),'joint_direct62_pz0':(direct*4+pz,36)}
    results=[];saved=dict(fraction=fraction,selected_rows=rows)
    for name,(category,size) in maps.items():
        mc=np.zeros((7,size),int);np.add.at(mc,(truebin[rows],category),1)
        n=mc.sum(1);assert (n>1).all();q=mc/n[:,None]
        data=1000*(fraction@q)
        stat,free,fixed=lr(data,mc,fraction)
        exact=loglike(data,mc,fraction,q)
        assert abs(free['loglike']-exact)<1e-4 and stat<1e-4,(name,stat,free['loglike']-exact)
        covariance=np.array([(np.diag(r)-np.outer(r,r))/count for r,count in zip(q,n)])
        fisher=precision(q,fraction,covariance)[0]
        rng=np.random.default_rng(20261107139)
        toys=[]
        for toy in range(4):
            aux=np.array([rng.multinomial(int(count),r) for count,r in zip(n,q)])
            observed=rng.multinomial(1000,fraction@q)
            value,a,b=lr(observed,aux,fraction)
            toys.append(dict(toy=toy,LR_at_true_psi=value,free_iterations=a['iterations'],fixed_iterations=b['iterations']))
        saved[name+'_MC_counts']=mc
        results.append(dict(model=name,MC_families=len(rows),MC_counts_per_truebin=n.tolist(),
            zero_cells_per_truebin=(mc==0).sum(1).tolist(),Asimov_LR_at_truth=stat,
            Asimov_loglike_delta_vs_exact=free['loglike']-exact,
            Asimov_iterations=[free['iterations'],fixed['iterations']],pilot_toys=toys,
            local_one_view_fisher=fisher))
    np.savez_compressed(CACHE/'template_counts.npz',**saved)
    result=dict(results=results,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
        RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,no_regression_fit_or_forward=True,
        reserved_forward=0,scope='cost/convergence pilot only;4toys not coverage evidence;one deterministic view per incoming proxy,not full generator-family independence')
    (OUT/'pilot_results.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)

if __name__=='__main__':main()
