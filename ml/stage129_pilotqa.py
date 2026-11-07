"""ADC/scalar closure, strict pair coverage and measured extraction cost; no fit."""
import json
from pathlib import Path
import resource
import time

import numpy as np

OUT=Path('workbook/stage129_energy_ml')
CACHE=Path('ntuples/energy_ml_stage129')


def main():
    tick,cpu=time.perf_counter(),time.process_time()
    plan=json.loads((OUT/'extraction_contract.json').read_text())
    channel_names={4:'VetoNu0',5:'VetoNu1',14:'Veto10',6:'Veto20',7:'Veto21'}
    records=[];pairs=[];edge=[]
    for index in plan['pilot_indices']:
        with np.load(CACHE/f'pilot2_{index}.npz') as z:
            d={k:z[k] for k in z.files}
        names=d['names'].tolist();suffix=d['suffixes'].tolist()
        scalar=d['scalar'];actual_presence=np.zeros((len(d['row']),5),bool)
        for j,ch in enumerate(d['channel'][0]):
            name=channel_names[int(ch)];k=names.index(name);present=d['present'][:,j];actual_presence[:,k]=present
            wave=d['adc'][present,j].astype(float)
            baseline=scalar[present,k,suffix.index('baseline')]
            charge=.04*(600*baseline-wave.sum(1)*2/16.384)
            official=scalar[present,k,suffix.index('raw_charge')]
            diff=charge-official
            # Scalar integral is float32; the stored baseline also underwent
            # float32 arithmetic. Report absolute/relative closure, no refit.
            records.append(dict(source=index,channel=int(ch),name=name,present_N=int(present.sum()),
                                max_abs_raw_difference_pC=float(abs(diff).max()),
                                median_abs_raw_difference_pC=float(np.median(abs(diff))),
                                raw_range_pC=[float(official.min()),float(official.max())]))
            for w in wave:
                rail=w==0
                if rail.any():
                    first,last=np.flatnonzero(rail)[[0,-1]]
                    edge.append(dict(source=index,channel=int(ch),rail_samples=int(rail.sum()),
                                     first_rail_sample=int(first),last_rail_sample=int(last),
                                     leading_available=bool(first>=4),trailing_available=bool(last<596)))
        status=scalar[:,:,suffix.index('status')];times=scalar[:,:,suffix.index('localtime')]
        good=actual_presence&(status==0)&np.isfinite(times)&(times>=0)
        for i,j in [(0,1),(2,3),(3,4),(0,3),(1,3)]:
            valid=good[:,i]&good[:,j]
            delta=times[valid,i]-times[valid,j]
            pairs.append(dict(source=index,pair=names[i]+'-'+names[j],N=len(valid),valid_N=int(valid.sum()),
                              median_uncalibrated_ns=float(np.median(delta)) if len(delta) else None,
                              q16_q84_uncalibrated_ns=np.quantile(delta,[.16,.84]).tolist() if len(delta) else None))
    summary=dict(N=sum(json.loads((OUT/f'pilot2_{i}.json').read_text())['N'] for i in plan['pilot_indices']),
                 raw_closure=records,strict_pair_coverage=pairs,rail_edges=edge,
                 interpretation='raw arithmetic check only; no claimed response/timing calibration, artificial clipping or energy fit',
                 CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
                 RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (OUT/'pilot_qa.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('RAW_CLOSURE_MAX',max(r['max_abs_raw_difference_pC'] for r in records),flush=True)


if __name__=='__main__':main()
