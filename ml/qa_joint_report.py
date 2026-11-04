"""Stage97 fixed40 report numerical QA with synthetic points, zero fits."""
import json,sys,time
import multiprocessing as mp
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path.cwd()/'ml'))
import report_joint_candidates as r
from report_resplit_energy import incoming_draws
from prepare_candidate_ablation import arrays
out=Path('workbook/stage97_energy_ml');c=arrays(Path('ntuples/energy_ml_stage96/QA_candidates.npz'))
slim=arrays(Path('ntuples/energy_ml_stage94/evaluation_input.npz'));ix=np.searchsorted(slim['row'],c['row'])
np.testing.assert_array_equal(slim['row'][ix],c['row']);d={k:v[ix] for k,v in slim.items()}
assert len(d['row'])==len(np.unique(d['key_id']))==40 and np.isin(d['role'],[1,2]).all()
d['candidate_available']=c['available'];d['candidate_count']=np.diff(c['offsets'])
full=arrays(Path('ntuples/energy_ml_stage96/candidates.npz'));fi=np.searchsorted(full['row'],d['row']);np.testing.assert_array_equal(full['row'][fi],d['row']);d['source']=full['source'][fi]
# Numerical report QA, not candidate performance: deterministic synthetic point vectors.
y=np.log(d['truth_E_GeV']);base=np.linspace(5,7,len(y));names=['A_raw','A_cal','B_raw','B_cal','traditional','direct_cal','direct_raw_post','posterior92','stage94_C','stage94_Eensemble','stage96_A','stage96_B']
policies={k:base+.01*j for j,k in enumerate(names)}
keys,gid,draw=incoming_draws(d,2026110389);r.G=(d,policies,{2:(np.arange(len(y)),keys,gid,draw)})
tasks=[(2,k) for k in ['all','E50_100','E100_200','pz50_100_trueE200','X_candidates_available','X_candidates_unavailable','X_candidates_multiple','input_missing']]
tick=time.perf_counter();serial=[r.one(t) for t in tasks];single=time.perf_counter()-tick
tick=time.perf_counter()
with mp.get_context('fork').Pool(8) as p:parallel=p.map(r.one,tasks)
wall=time.perf_counter()-tick
assert serial==parallel
allpairs=serial[0][1];a=policies['B_cal']-y;b=policies['A_cal']-y;w=d['weight'];valid=np.ones(500,bool)
# Direct event-space draw calculation, independent of grouped squared-error code.
weights=draw[:,gid]*w[None,:];ratio=np.sqrt((weights@(a*a))/(weights@(b*b)));ci=np.quantile(ratio,[.025,.975]);saved=next(q for q in allpairs if q['candidate']=='B_cal' and q['reference']=='A_cal')
maximum=max(abs(ci[0]-saved['conditional_low95']),abs(ci[1]-saved['conditional_high95']))
assert maximum<1e-12
result=dict(passed=True,unique_incoming=40,mixed_original_train_cal=True,new_test_payload=0,new_fits=0,synthetic_points_only=True,processes=8,tasks=len(tasks),serial_parallel_identical=True,event_space_interval_max_difference=float(maximum),serial_wall_s=single,parallel_wall_s=wall)
(out/'report_QA.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
