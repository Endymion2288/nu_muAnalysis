"""One bounded two-arm Stage115 measurement-state experiment; batch only."""
import json
import multiprocessing as mp
import resource
import time
import traceback

import numpy as np

from stage115_common import ART, IO, OUT, ROOT, cached_inputs, plain, save
from stage115_head import fit_arm, infer_arm, qa
from stage115_report import report


def main():
    wall=time.perf_counter();cpu=time.process_time()
    assert not (OUT/'fits_frozen.json').exists()
    p=json.loads((OUT/'protocol.json').read_text());assert p['stage']==115
    d,x,sub,pw=cached_inputs();qa(x,d)
    with mp.get_context('fork').Pool(2) as pool:
        fitted=pool.map(fit_arm,[(name,x[name],d,p) for name in ['A','B']])
    save('fits_frozen.json',dict(arms=[n for n,r in fitted],fits=2,convex_solver_calls=4,
        all_theta_locked=True,test_forward_or_risk_before_both_locked=False,
        source_baseline='frozen saved Stage87 direct_cal; no baseline forward/refit',
        new_offset=False,primary_candidate='B',fit_results=[r for n,r in fitted]))
    with mp.get_context('fork').Pool(2) as pool:
        predictions=pool.map(infer_arm,[(name,x[name],d) for name in ['A','B']])
    policies=dict(traditional=np.log(d['pz']/.8),direct_cal=d['base'],**dict(predictions))
    path=ART/'points.npz';np.savez_compressed(path,row=d['row'],A=policies['A'],B=policies['B'])
    with np.load(path) as z:
        for k in ['A','B']: assert z[k].tobytes()==policies[k].tobytes()
        np.testing.assert_array_equal(z['row'],d['row'])
    outcome=report(d,policies,sub,pw)
    save('io.json',dict(files=IO,local_read_requested_bytes=sum(r['local_read_requested_bytes'] for r in IO),
        local_read_returned_bytes=sum(r['local_read_returned_bytes'] for r in IO),physical_network_bytes='unmeasured',
        scope='local cached archive reader interfaces inside worker; package staging and OS cache excluded'))
    save('resources.json',dict(worker_self_CPU_s=time.process_time()-cpu,worker_wall_s=time.perf_counter()-wall,
        reaped_children_CPU_s=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime+resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,
        worker_max_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        note='nested diagnostics; GNU outer total authoritative; entire tree simultaneous peak unmeasured',GPU=0,
        fits=[dict(arm=n,CPU_s=r['CPU_s'],wall_s=r['wall_s']) for n,r in fitted]))
    save('complete.json',dict(status='experiment_complete',active_records=71376,formal_rule_dictionaries=2,
         head_solves=4,baseline_fits=0,baseline_forwards=0,new_split=False,new_ROOT=False,
         both_arms_frozen_before_test_forward_and_risk=True,decision=outcome))
    print(json.dumps(plain(outcome),indent=2),flush=True)


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        save('failure.json',dict(error=repr(error),traceback=traceback.format_exc(),
             completed=False,no_automatic_retry=True))
        raise
