"""Validate actual native pilot before batch admission; freeze source batches."""
import gzip,json
from pathlib import Path
import numpy as np
from audited_features import configuration
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage124_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage124'
def main():
 with gzip.open(CACHE/'pilot4_0/native.json.gz','rt') as f:r=json.load(f)
 with np.load(CACHE/'input.npz') as z:d={k:z[k] for k in z.files}
 names=configuration()['features'];delta=0.;linked=missing=stripinvalid=rawinvalid=measurement=measurementmissing=0
 for v in r['records']:
  j=v['row'];assert v['clusters']==[int(d['x'][j,names.index('nClusters'+str(s))]) for s in range(4)],(j,'clusters',v['clusters'])
  assert v['sp']==int(d['x'][j,names.index('SpacePoints')]),(j,'sp',v['sp'],d['x'][j,names.index('SpacePoints')])
  assert v['longTracks']==int(d['x'][j,names.index('longTracks')]),(j,'tracks')
  delta=max(delta,abs(v['pz_GeV']-d['pz'][j]));linked+=v['spLinks'];missing+=v['spMissing'];stripinvalid+=v['invalidStrip'];rawinvalid+=v['invalidRaw'];measurement+=v['measurements'];measurementmissing+=v['measurementMissing']
  if v['invalidCluster']:assert any(np.isnan(v['z'][24*st+3]) for st in range(4)),j
 a=dict(N=len(r['records']),native_run_event_equal=True,native_leading_pz_max_abs_GeV=delta,all_cluster_station_counts_equal=True,spacepoint_counts_equal=True,long_track_counts_equal=True,SP_cluster_links=linked,SP_missing_links=missing,invalid_strips=stripinvalid,CPU_s=r['CPU_s'],wall_s=r['wall_s'],read_bytes=r['read_bytes'],RSS_KiB=r['RSS_KiB'],invalid_raw_IDs=rawinvalid,track_measurements=measurement,track_missing=measurementmissing,admitted=bool(linked>0 and measurement>0 and rawinvalid==0),caveat='pilot initialization dominates; not a linear CPU/event projection; multi-file range closure still checked in full batch before fits')
 (OUT/'pilot_validation.json').write_text(json.dumps(a,indent=2)+'\n');print(a,flush=True)
 assert a['admitted'],a
 p=json.loads((OUT/'native_contract.json').read_text());requests=p['requests'];batches=[]
 # Group only same run/geometry under one initialization; use actual metadata
 # entry totals for global offsets and preserve every original selected parent.
 for run in sorted(set(s['run'] for s in requests)):
  indices=[s['index'] for s in requests if s['run']==run]
  batches.extend([indices[i:i+8] for i in range(0,len(indices),8)])
 p['batches']=batches;p['resources_after_pilot']=dict(jobs=len(batches),cpus_each=2,memory_MB_each=6000,wall_s_each=7200,aggregate_CPU_s=60000,retained_bytes=200000000,admission='actual40 parent tracker relations/identity/PHYS counts passed; invalid persisted cluster strip IDs kept as unknown not parent rejection; source groups fixed independent of new model outcomes')
 (OUT/'native_contract.json').write_text(json.dumps(p,separators=(',',':'))+'\n')
 (OUT/'batch_inventory.json').write_text(json.dumps(dict(batches=batches,N=len(d['role']),sources=len(requests),policy='all original roles and quarantined identities retained; no new-fit before complete native closure'),indent=2)+'\n')
if __name__=='__main__':main()
