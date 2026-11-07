"""Bounded real/MC prompt-muon timing control, with exact status-zero masks."""
import json
import resource
import sys
import time
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

OUT=Path('workbook/stage129_energy_ml');CACHE=Path('ntuples/energy_ml_stage129')
SCINT=['VetoNu0','VetoNu1','Veto10','Veto20','Veto21']


def main():
    tick,cpu=time.perf_counter(),time.process_time()
    index=int(sys.argv[1]);plan=json.loads((OUT/'mucontrol_protocol.json').read_text());source=plan['sources'][index]
    with uproot.open(source['input'],array_cache=None) as f:
        tree=f['nt'];schema=tree.typenames()
        branches=['run','eventID','longTracks','Track_pz0','Track_px0','Track_py0','Track_Chi2','Track_nDoF','Track_nLayers']
        branches += [s+'_'+k for s in SCINT for k in ['status','localtime','raw_charge']]
        branches += ['Track_'+axis+'_at'+p for p in ['VetoNu','VetoStation1','VetoStation2'] for axis in ['X','Y','ThetaX','ThetaY']]
        missing=[b for b in branches if b not in schema]
        report=dict(source=source,schema=schema,missing=missing)
        if not missing:
            a=tree.arrays(branches,entry_stop=plan['entry_stop'])
            lead=ak.argmax(a.Track_pz0,axis=1,keepdims=True,mask_identity=True)
            def get(name):
                return ak.to_numpy(ak.fill_none(ak.firsts(a[name][lead]),np.nan))
            pz=get('Track_pz0')/1000
            ndof=get('Track_nDoF');chi=get('Track_Chi2')
            good=(ak.to_numpy(a.longTracks)==1)&np.isfinite(pz)&(pz>50)&(pz<2000)&(ndof>0)&(chi/np.maximum(ndof,1)<10)&(get('Track_nLayers')>=7)
            stat=np.column_stack([ak.to_numpy(a[s+'_status']) for s in SCINT])
            times=np.column_stack([ak.to_numpy(a[s+'_localtime']) for s in SCINT])
            charge=np.column_stack([ak.to_numpy(a[s+'_raw_charge']) for s in SCINT])
            # Acquisition time0 is an uncalibrated/default interface, not a
            # prompt pulse at the expected beam trigger position.
            valid=(stat==0)&np.isfinite(times)&(times>0)&np.isfinite(charge)&(charge>0)
            x=np.column_stack([get('Track_X_at'+p) for p in ['VetoNu','VetoNu','VetoStation1','VetoStation2','VetoStation2']])
            y=np.column_stack([get('Track_Y_at'+p) for p in ['VetoNu','VetoNu','VetoStation1','VetoStation2','VetoStation2']])
            theta_x=get('Track_px0')/get('Track_pz0');theta_y=get('Track_py0')/get('Track_pz0')
            rows=[]
            for i,j in plan['pairs']:
                use=good&valid[:,i]&valid[:,j]&np.isfinite(x[:,i])&np.isfinite(y[:,i])&np.isfinite(x[:,j])&np.isfinite(y[:,j])
                rows.append(dict(pair=SCINT[i]+'-'+SCINT[j],muon_N=int(good.sum()),strict_pair_N=int(use.sum()),
                                 median_uncalibrated_ns=float(np.median(times[use,i]-times[use,j])) if use.any() else None))
            take=np.flatnonzero(good)
            np.savez_compressed(CACHE/f'mucontrol_{index}.npz',run=ak.to_numpy(a.run)[take],event=ak.to_numpy(a.eventID)[take],
                                status=stat[take],time=times[take],charge=charge[take],valid=valid[take],x=x[take],y=y[take],
                                theta_x=theta_x[take],theta_y=theta_y[take])
            report.update(input_N=len(a),muon_N=len(take),pairs=rows)
        report.update(read_bytes=int(f.file.source.num_requested_bytes),CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
                      RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (OUT/f'mucontrol_{index}.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='schema'}),flush=True)


if __name__=='__main__':main()
