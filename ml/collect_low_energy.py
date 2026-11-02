#!/usr/bin/env python3
"""Join complete stage55 sources and audit the original threshold/feature subset."""
import csv,json,resource,time
from pathlib import Path
import numpy as np
from train_bdt import write_table

repo=Path(__file__).resolve().parents[1]; cache=repo/'ntuples/energy_ml_stage55'; out=repo/'workbook/stage55_energy_ml'
tick,cpu=time.perf_counter(),time.process_time()
rows=list(csv.DictReader((repo/'ml/configs/low_energy_files.tsv').open(),delimiter='\t'))
excluded=json.loads((repo/'ml/configs/low_energy.json').read_text()).get('excluded_source_indices',[])
rows=[r for r in rows if int(r['index']) not in excluded]
old_rows={int(r['index']):r for r in csv.DictReader((repo/'ml/configs/files.tsv').open(),delimiter='\t')}
parts=[]; reports=[]; cutflows=[]; features=None
for row in rows:
 with np.load(cache/f"shards/{row['index']}.npz") as z:
  md=json.loads(str(z['metadata_json']));d={k:z[k] for k in z.files if k!='metadata_json'}
 expected_raw=int(old_rows[int(row['old_index'])]['expected_events']) if int(row['old_index'])>=0 else 10000
 assert md['index']==int(row['index']) and md['raw_N']==expected_raw
 assert np.all(d['run']==int(row['run']))
 if features is None:features=md['features']
 assert md['features']==features and d['x'].shape==(md['selected_N'],65)
 for k in ['component','family','group','partition']:
  d[k]=np.full(len(d['run']),row[k])
 d['nominal']=np.full(len(d['run']),row['family']=='nominal')
 parts.append(d)
 for name,passed in zip(md['cutflow_names'],md['cutflow_passed']):
  cutflows.append(dict(index=int(row['index']),cut=name,passed=passed))
 reports.append({k:md[k] for k in ['index','raw_N','selected_N','new_selection_N','reco_p50_100_N','truth_E50_100_N','wall_s','cpu_s','peak_parent_rss_MiB','peak_analysis_rss_MiB','uproot_requested_bytes']})
d={k:np.concatenate([p[k] for p in parts]) for k in parts[0]}
assert len(set(zip(d['run'],d['eventID'])))==len(d['run'])
assert np.isfinite(d['truth_E_GeV']).all() and (d['truth_E_GeV']>0).all()
assert np.isfinite(d['reco_p_GeV']).all() and (d['reco_p_GeV']>50).all()
# Exact incoming-neutrino overlap audit; no expensive file checksum or lineage claim.
keys=[tuple(v) for v in d['incoming']]
protected={keys[i] for i in np.flatnonzero(d['partition']!='train')}
overlap=np.array([k in protected for k in keys])&(d['partition']=='train')
d['train_eligible']=(d['partition']=='train')&~overlap
evaluation_keys={keys[i] for i in np.flatnonzero(d['partition']=='validation')}
cal_overlap=np.array([k in evaluation_keys for k in keys])&(d['partition']=='calibration')
d['cal_eligible']=(d['partition']=='calibration')&~cal_overlap
# Verify existing nominal >100 GeV identities and all 46 unchanged F5 inputs.
checks=[]
for part in ['train','validation','calibration']:
 mask=d['nominal']&(d['partition']==part)&(d['truth_pz_GeV']>100)&(d['reco_pz_GeV']>100)
 with np.load(repo/f'ntuples/energy_ml_stage12/dataset/{part}.npz') as z:
  lookup={tuple(k):i for i,k in enumerate(zip(z['run'],z['eventID']))}
  assert set(zip(d['run'][mask],d['eventID'][mask]))==set(lookup)
  order=np.array([lookup[k] for k in zip(d['run'][mask],d['eventID'][mask])])
  old=np.column_stack([z[k][order] for k in features[:46]]).astype('float32');old[~np.isfinite(old)]=np.nan
  np.testing.assert_array_equal(d['x'][mask,:46],old)
 checks.append(dict(partition=part,N=int(mask.sum()),identities_and_F5_exact=True))
# Existing F6 extra columns independently reproduced on old validation cache.
with np.load(repo/'ntuples/energy_ml_stage31/validation_tracks.npz') as z:
 lookup={tuple(k):i for i,k in enumerate(zip(z['run'],z['eventID']))}
 mask=d['nominal']&(d['partition']=='validation')&(d['truth_pz_GeV']>100)&(d['reco_pz_GeV']>100)
 order=np.array([lookup[k] for k in zip(d['run'][mask],d['eventID'][mask])])
 for j,k in enumerate(features[46:],46):
  old=z[k][order].astype('float32');old[~np.isfinite(old)]=np.nan
  np.testing.assert_array_equal(d['x'][mask,j],old)
summary=dict(N=len(d['run']),files=len(rows),raw_N=sum(r['raw_N'] for r in reports),features=features,
             checks=checks,validation_F6_extra_exact=True,train_exact_incoming_overlap_removed=int(overlap.sum()),
             calibration_exact_incoming_overlap_removed=int(cal_overlap.sum()),
             source_group_overlap=len(set(d['group'][d['partition']=='train'])&set(d['group'][d['partition']!='train'])),
             extraction_wall_sum_s=sum(r['wall_s'] for r in reports),uproot_requested_bytes=sum(r['uproot_requested_bytes'] for r in reports),
             analysis_requested_bytes='not instrumented; separate RDataFrame read',
             max_parent_rss_MiB=max(r['peak_parent_rss_MiB'] for r in reports),max_analysis_rss_MiB=max(r['peak_analysis_rss_MiB'] for r in reports),
             wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
assert summary['source_group_overlap']==0
np.savez_compressed(cache/'dataset.npz',**d,metadata_json=np.array(json.dumps(summary)))
write_table(out/'extraction_files.tsv',reports)
write_table(out/'extraction_cutflows.tsv',cutflows)
(out/'dataset_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
counts=[]
for nominal in [True,False]:
 for part in ['train','validation','calibration']:
  m=(d['nominal']==nominal)&(d['partition']==part)
  counts.append(dict(sample='nominal' if nominal else 'alternative',partition=part,N=int(m.sum()),sources=len(set(d['source'][m])),groups=len(set(d['group'][m])),eligible_train_N=int((m&d['train_eligible']).sum()),reco_p50_100_N=int((m&(d['reco_p_GeV']<100)).sum()),truth_E50_100_N=int((m&(d['truth_E_GeV']<100)).sum())))
write_table(out/'support.tsv',counts)
eligible=[]
for candidate in ['nominal100','nominal50','mixture50']:
 m=d['train_eligible'].copy()
 if candidate.startswith('nominal'):m &= d['nominal']
 if candidate=='nominal100':m &= (d['truth_pz_GeV']>100)&(d['reco_pz_GeV']>100)
 for lo,hi in [(50,100),(100,200),(200,float('inf'))]:
  s=m&(d['truth_E_GeV']>=lo)&(d['truth_E_GeV']<hi)
  eligible.append(dict(candidate=candidate,energy_low_GeV=lo,energy_high_GeV=hi,N=int(s.sum()),sources=len(set(d['source'][s])),groups=len(set(d['group'][s]))))
write_table(out/'eligible_training_support.tsv',eligible)
print(json.dumps(summary),flush=True)
