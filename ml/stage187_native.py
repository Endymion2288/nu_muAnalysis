"""Batch-only measured primary endpoints and fixed same-window source ledger."""
import csv,gzip,json,math,resource,sys,time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
ROOT=Path.cwd();OUT=ROOT/'workbook/stage187_energy_ml';P=json.loads((OUT/'protocol.json').read_text())
def read_gz(path):
 with gzip.open(path,'rt') as f:return json.load(f)
def write(name,value):(OUT/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def table(name,rows):
 with (OUT/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)),delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(rows)
def parent(index):
 cpu=time.process_time();tick=time.perf_counter();path=ROOT/f'ntuples/energy_ml_stage{176 if index==50 else 178}/parent_{index}_lineage.json.gz';raw=read_gz(path)
 side=json.loads((ROOT/f'workbook/stage178_energy_ml/parent_{index}_intervals.json').read_text());boxes=json.loads((ROOT/'workbook/stage178_energy_ml/state_boxes.json').read_text());box=next(b for b in boxes if b['index']==index)
 cases=read_gz(ROOT/'ntuples/energy_ml_stage131/production_cases.json.gz');case=next(c for c in cases if c['frame_index']==index)
 assert len(raw['muon_primaries'])==1;primary=raw['muon_primaries'][0];root=int(primary[0]);steps=[(i,s) for i,s in enumerate(raw['muon_segments']) if int(s[0])==root];assert steps and all(len(s)==19 for _,s in steps)
 assert all(s[12]>=s[11] for _,s in steps);initial=primary[8];last=steps[-1][1]
 gaps=[b[7]-a[8] for (_,a),(_,b) in zip(steps,steps[1:])];drops=[s[7]-s[8] for _,s in steps]
 r=dict(index=index,stratum=case['stratum'],component=case['component'],truth_E_GeV=case['truth_E_GeV'],primary_root=root,primary_segments_N=len(steps),initial_E_GeV=initial/1000,first_pre_E_GeV=steps[0][1][7]/1000,first_minus_initial_MeV=steps[0][1][7]-initial,final_E_GeV=last[8]/1000,final_x_mm=last[4],final_y_mm=last[5],final_z_mm=last[6],final_time_ns=last[12],sum_step_drops_GeV=math.fsum(drops)/1000,sum_adjacent_gaps_GeV=math.fsum(gaps)/1000,max_abs_adjacent_gap_MeV=max(map(abs,gaps),default=0.),initial_minus_final_GeV=(initial-last[8])/1000,transport_energy_increase_steps_N=sum(d<0 for d in drops),plane_supported=side['state_supported'],forward_crossings_N=sum(c['forward'] for c in side['robust_crossings']),cross_ordinal=None,cross_pre_E_GeV=None,cross_post_E_GeV=None,loss_to_cross_pre_GeV=None,loss_to_cross_post_GeV=None,confirmed_primary_association=False,cached_fit_E_GeV=None,fit_minus_cross_pre_GeV=None,fit_minus_cross_post_GeV=None)
 cross=next((c for c in side['robust_crossings'] if c['forward']),None)
 if cross:
  ordinal=cross['ordinal'];s=raw['muon_segments'][ordinal];assert int(s[0])==root and s[7:9]==cross['pre_post_total_energy_MeV']
  r.update(cross_ordinal=ordinal,cross_pre_E_GeV=s[7]/1000,cross_post_E_GeV=s[8]/1000,loss_to_cross_pre_GeV=(initial-s[7])/1000,loss_to_cross_post_GeV=(initial-s[8])/1000)
 with np.load(ROOT/'ntuples/energy_ml_stage131/matched_input.npz') as z:
  ix=np.flatnonzero(z['frame_index']==index);assert len(ix)<=1
  if len(ix):
   j=int(ix[0]);assert z['role'][j]==1;r['confirmed_primary_association']=bool(z['confirmed'][j] and z['primary_valid'][j]);r['cached_pz0_GeV']=float(z['pz'][j])
   if box['supported'] and r['confirmed_primary_association']:
    components=box['cached_values'][3:];fit=math.sqrt(math.fsum(float(v*1000)**2 for v in components)+P['muon_mass_MeV']**2)/1000;r['cached_fit_E_GeV']=fit
    if cross:r.update(fit_minus_cross_pre_GeV=fit-r['cross_pre_E_GeV'],fit_minus_cross_post_GeV=fit-r['cross_post_E_GeV'])
 charges=[q for q in csv.DictReader((ROOT/'workbook/stage179_energy_ml/charge_interventions.tsv').open(),delimiter='\t') if int(q['index'])==index];assert charges
 sourcecols=['primary_muon_direct_pC','before_S0_pC','after_S0_pC','other_root_pC','unknown_root_pC','unknown_S0_pC'];qrows=[]
 for detector in sorted(set(q['detector'] for q in charges)):
  selected=[q for q in charges if q['detector']==detector];qrows.append(dict(index=index,detector=detector,channels_N=len(selected),**{k:math.fsum(float(q[k]) for q in selected) for k in sourcecols},total_ideal_pC=math.fsum(float(q['ideal_no_noise_no_clip_no_quantization_pC']) for q in selected)))
 old=next(q for q in csv.DictReader((ROOT/'workbook/stage179_energy_ml/parent_diagnostics.tsv').open(),delimiter='\t') if int(q['index'])==index)
 r.update(old_train_direct_relative_error=float(old['direct_cal_relative_error']) if old['direct_cal_relative_error'] else None,old_train_traditional_relative_error=float(old['traditional_relative_error']) if old['traditional_relative_error'] else None,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,compressed_lineage_B=path.stat().st_size,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
 if index==50:
  native=json.loads((ROOT/'workbook/stage176_energy_ml/parent_50_S0.json').read_text());assert native['first_forward_crossing']['pre_post_total_energy_MeV']==cross['pre_post_total_energy_MeV'];r['original_native_cross_endpoints_exact']=True
 return r,qrows
if __name__=='__main__':
 phase=sys.argv[1]
 if phase=='pilot':
  r,q=parent(50);write('pilot_result.json',dict(parents=[r],sources=q));print(r,flush=True)
 else:
  old=json.loads((OUT/'pilot_result.json').read_text())
  with ProcessPoolExecutor(max_workers=2) as pool:results=list(pool.map(parent,[i for i in P['parents'] if i!=50]))
  parents=old['parents']+[r for r,q in results];sources=old['sources']+[row for r,q in results for row in q];parents.sort(key=lambda r:P['parents'].index(r['index']))
  write('ledger.json',dict(parents=parents,sources=sources));table('parent_ledger.tsv',parents);table('source_ledger.tsv',sources)
  import matplotlib;matplotlib.use('Agg')
  import matplotlib.pyplot as plt
  fig,axes=plt.subplots(1,2,figsize=(10,4))
  for ax,side in zip(axes,['before_S0_pC','after_S0_pC']):
   for r in parents:
    if r['cross_pre_E_GeV'] is None:continue
    q=next(q for q in sources if q['index']==r['index'] and q['detector']=='Calo');ax.scatter(r['loss_to_cross_pre_GeV'],q[side]);ax.annotate(str(r['index']),(r['loss_to_cross_pre_GeV'],q[side]))
   ax.set_xlabel('Initial primary E minus crossing pre-step E [GeV]');ax.set_ylabel('Ordinary Ecal same-window '+side+' [pC]');ax.grid(alpha=.2)
  fig.suptitle('Fixed12 train controls; 9 S0 planes, missing3 retained; no regression');fig.tight_layout();fig.savefig(OUT/'energy_source_ledger.png',dpi=180);fig.savefig(OUT/'energy_source_ledger.pdf');plt.close(fig)
  write('analysis_summary.json',dict(passed=True,parents_N=len(parents),plane_N=sum(r['plane_supported'] for r in parents),confirmed_association_N=sum(r['confirmed_primary_association'] for r in parents),new_G4=0,new_fits=0,new_forward=0,overall_complete=False,promotion=False))
