#!/usr/bin/env python3
"""Report native transport coverage and same-plane bounded response, no fake pull."""
import argparse,csv,json,time,resource,gzip
from pathlib import Path
import numpy as np,yaml
from reference_bounds import momentum_bound
from train_bdt import write_table

def source_interval(values,groups):
 """A zero-event bootstrap cannot bound an unobserved population tail."""
 values=np.asarray(values)
 if groups<2 or np.ptp(values)<1e-14:
  return np.nan,np.nan,'degenerate_no_population_bound'
 lo,hi=np.quantile(values,[.025,.975])
 return lo,hi,'source_group_bootstrap'

def main():
 p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--compact',action='store_true');a=p.parse_args();repo=a.repo;tick=time.perf_counter();cpu=time.process_time()
 cfg=yaml.safe_load((repo/'ml/configs/reference_audit.yaml').read_text());out=repo/'workbook/stage32_energy_ml';root=repo/'ntuples/energy_ml_stage32'
 archive_path=root/'native_results.json.gz'
 archive=json.load(gzip.open(archive_path,'rt')) if archive_path.exists() else dict(cfg=cfg,requests={},truth={},cov={})
 assert archive['cfg']==cfg
 manifest=list(csv.DictReader((out/'manifest.tsv').open(),delimiter='\t'));requests={};truths={};covs={};jobs=[]
 for row in manifest:
  idx=row['index'];request=archive['requests'].get(idx)
  if request is None:
   request=json.loads((root/f'requests/{idx}.json').read_text());assert request.pop('cfg')==cfg;archive['requests'][idx]=request
  for old in request['events']:requests[(old['run'],old['eventID'])]=old
  for mode,target in [('truth',truths),('cov',covs)]:
   result=archive[mode].get(idx)
   if result is None:result=json.loads((root/f'{mode}/{idx}.json').read_text());archive[mode][idx]=result
   assert result['index']==int(idx)
   if mode=='truth':assert not result['smoke']
   for e in result['events']:
    key=(e['run'],e['eventID']);assert key not in target;target[key]=e
   jobs.append(dict(index=idx,mode=mode,events=len(result['events']),wall_s=result.get('wall_s',result.get('export_wall_s')),cpu_s=result.get('cpu_s',result.get('export_cpu_s')),peak_rss_MiB=result.get('peak_rss_MiB',result.get('export_peak_rss_MiB'))))
 assert set(truths)==set(requests) and set(covs)=={key for key,r in requests.items() if r['covariance_requested']}
 table=[];ref=[]
 for key,old in requests.items():
  e=truths[key];assert e['primary_matches']==1
  # Fixed z is only an input audit. Actual covariance cases use the native plane.
  bound=momentum_bound(e['chain'],old['reco_front'][:3],[0,0,1]) if not e['ambiguity'] else dict(valid=False,reason='ambiguous_chain')
  table.append(dict(run=key[0],eventID=key[1],group=old['group'],truth_E_GeV=old['truth_E_GeV'],primary_p_GeV=old['primary_p_GeV'],y_lepton=old['y_lepton'],vertex_z_mm=old['vertex_z_mm'],confirmed=old['lead_primary_parent_confirmed'],chain_states=len(e['chain']),ambiguous=e['ambiguity'],declared_momentum_unit=e['declared_momentum_unit'],enum_MEV=e['enum_MEV'],generated_muon_mass_raw=e['generated_muon_mass_raw'],nearest_saved_z_distance_mm=e['nearest_saved_z_distance_mm'],saved_state_within_z_tolerance=e['saved_state_within_z_tolerance'],z_bound_available=bound['valid'],bound_reason=bound['reason'],p_low_GeV=bound.get('p_low_GeV',np.nan),p_high_GeV=bound.get('p_high_GeV',np.nan)))
  if key not in covs:continue
  cov=covs[key];assert cov['original_front_reproduced'];mat=np.array(cov['covariance']).reshape(5,5)
  assert np.isfinite(mat).all() and np.allclose(mat,mat.T,atol=1e-16,rtol=1e-6) and (np.diag(mat)>0).all()
  correlation=mat/np.sqrt(np.outer(np.diag(mat),np.diag(mat)));eigen=np.linalg.eigvalsh(correlation)
  bound=momentum_bound(e['chain'],cov['surface_center_mm'],cov['surface_normal']) if not e['ambiguity'] else dict(valid=False,reason='ambiguous_chain')
  sigma=cov['sigma_kappa_GeVinv'];assert sigma>0;kappa=cov['kappa_GeVinv'];q=-np.sign(old['primary_pdg'])
  assert cov['primary_barcode_pdg_confirmed']==old['lead_primary_parent_confirmed']
  r=dict(run=key[0],eventID=key[1],group=old['group'],truth_E_GeV=old['truth_E_GeV'],primary_p_GeV=old['primary_p_GeV'],y_lepton=old['y_lepton'],vertex_z_mm=old['vertex_z_mm'],confirmed=old['lead_primary_parent_confirmed'],reco_p_GeV=old['reco_p_GeV'],q_true=q,q_reco=cov['charge'],sign_disagreement=cov['charge']!=q,kappa_reco_GeVinv=kappa,sigma_kappa_GeVinv=sigma,abs_kappa_over_sigma=abs(kappa)/sigma,production_standardized_residual=(kappa-q/old['primary_p_GeV'])/sigma,covariance_correlation_min_eigenvalue=eigen.min(),plane_normal_z=cov['surface_normal'][2],bound_available=bound['valid'],bound_reason=bound['reason'])
  vals=dict(p_low_GeV=np.nan,p_high_GeV=np.nan,propagation_fraction_loss_low=np.nan,propagation_fraction_loss_high=np.nan,kappa_truth_low_GeVinv=np.nan,kappa_truth_high_GeVinv=np.nan,standardized_residual_low=np.nan,standardized_residual_high=np.nan,kappa_interval_width_over_sigma=np.nan,guaranteed_abs_standardized_gt3=np.nan,possible_abs_standardized_gt3=np.nan)
  if bound['valid']:
   low,high=bound['p_low_GeV'],bound['p_high_GeV'];kl,kh=sorted([q/low,q/high]);rl,rh=(kappa-kh)/sigma,(kappa-kl)/sigma
   vals.update(p_low_GeV=low,p_high_GeV=high,propagation_fraction_loss_low=1-high/old['primary_p_GeV'],propagation_fraction_loss_high=1-low/old['primary_p_GeV'],kappa_truth_low_GeVinv=kl,kappa_truth_high_GeVinv=kh,standardized_residual_low=rl,standardized_residual_high=rh,kappa_interval_width_over_sigma=(kh-kl)/sigma,guaranteed_abs_standardized_gt3=bool(rl>3 or rh< -3),possible_abs_standardized_gt3=bool(rl< -3 or rh>3))
  r.update(vals)
  # Charge-aligned residual avoids cancellation between mu- and mu+.
  # These are endpoint summaries, never midpoint estimates or exact pulls.
  lo,hi=sorted([q*r['standardized_residual_low'],q*r['standardized_residual_high']])
  r.update(aligned_residual_low=lo,aligned_residual_high=hi,
           production_aligned_residual=q*r['production_standardized_residual'])
  ref.append(r)
 write_table(out/'transport_events.tsv',table);write_table(out/'reference_events.tsv',ref);write_table(out/'native_jobs.tsv',jobs)
 # Six source groups are the only resampling units, including repeated periods.
 groups=sorted({r['group'] for r in ref});ng=len(groups);gid=np.array([groups.index(r['group']) for r in ref]);rng=np.random.default_rng(cfg['seed']);draws=rng.multinomial(ng,np.full(ng,1/ng),size=cfg['bootstrap_replicates'])
 arrays={k:np.array([r[k] for r in ref]) for k in ref[0]};masks=[('all','all',np.ones(len(ref),bool)),('primary','confirmed',arrays['confirmed']),('primary','unconfirmed',~arrays['confirmed'])]
 for field,edges in [('primary_p_GeV',[0,400,1600,6400]),('truth_E_GeV',cfg['energy_edges_GeV']),('y_lepton',cfg['y_edges']),('vertex_z_mm',cfg['vertex_z_edges_mm']),('q_true',[-2,0,2])]:
  masks += [(field,f'{lo:g}_{hi:g}',(arrays[field]>=lo)&(arrays[field]<hi)) for lo,hi in zip(edges[:-1],edges[1:])]
 summaries=[]
 functions={'median_sigma_kappa_GeVinv':('sigma_kappa_GeVinv',np.median),'median_abs_kappa_over_sigma':('abs_kappa_over_sigma',np.median),'sign_disagreement_fraction':('sign_disagreement',np.mean),'production_standardized_RMS':('production_standardized_residual',lambda x:np.sqrt(np.mean(x*x))),'bound_fraction':('bound_available',np.mean),'median_interval_width_over_sigma':('kappa_interval_width_over_sigma',np.median),'mean_propagation_loss_low':('propagation_fraction_loss_low',np.mean),'mean_propagation_loss_high':('propagation_fraction_loss_high',np.mean),'guaranteed_gt3_fraction':('guaranteed_abs_standardized_gt3',np.mean),'possible_gt3_fraction':('possible_abs_standardized_gt3',np.mean),'mean_aligned_residual_low':('aligned_residual_low',np.mean),'mean_aligned_residual_high':('aligned_residual_high',np.mean)}
 for label,value,mask in masks:
  if not mask.any():continue
  for metric,(field,func) in functions.items():
   selected=mask&np.isfinite(arrays[field].astype(float));v=arrays[field][selected].astype(float);gg=gid[selected]
   if not len(v):continue
   bs=[]
   for draw in draws:
    repeated=np.repeat(v,draw[gg])
    if len(repeated):bs.append(func(repeated))
   lo,hi,status=source_interval(bs,len(set(gg)));summaries.append(dict(stratum=label,value=value,N=len(v),groups=len(set(gg)),metric=metric,point=func(v),CI025=lo,CI975=hi,bootstrap_valid=len(bs),interval_status=status))
 write_table(out/'reference_summary.tsv',summaries)
 # Exploratory endpoint summaries after the frozen extraction; no new selection.
 # Order statistics are monotone; R68 itself is bounded using opposite endpoints.
 interval_summaries=[]
 def endpoint_metrics(low,high):
  minabs=np.where((low<=0)&(high>=0),0,np.minimum(abs(low),abs(high)))
  maxabs=np.maximum(abs(low),abs(high))
  return dict(mean_low=np.mean(low),mean_high=np.mean(high),
              RMS_low=np.sqrt(np.mean(minabs**2)),RMS_high=np.sqrt(np.mean(maxabs**2)),
              R68_low=max(0,(np.quantile(low,.84)-np.quantile(high,.16))/2),
              R68_high=(np.quantile(high,.84)-np.quantile(low,.16))/2)
 for label,value,mask in masks:
  selected=mask&arrays['bound_available'];gg=gid[selected]
  if not selected.any():continue
  low=arrays['aligned_residual_low'][selected];high=arrays['aligned_residual_high'][selected]
  point=endpoint_metrics(low,high);bs={k:[] for k in point}
  for draw in draws:
   ll=np.repeat(low,draw[gg]);hh=np.repeat(high,draw[gg])
   if not len(ll):continue
   for k,v in endpoint_metrics(ll,hh).items():bs[k].append(v)
  for metric,v in point.items():
   lo,hi,status=source_interval(bs[metric],len(set(gg)))
   interval_summaries.append(dict(stratum=label,value=value,N=len(low),groups=len(set(gg)),metric=metric,point=v,CI025=lo,CI975=hi,bootstrap_valid=len(bs[metric]),interval_status=status))
 write_table(out/'bounded_aligned_summary.tsv',interval_summaries)
 coverage=[]
 ta={k:np.array([r[k] for r in table]) for k in table[0]};tg=np.array([groups.index(r['group']) for r in table])
 tm=[('all','all',np.ones(len(table),bool)),('primary','confirmed',ta['confirmed']),('primary','unconfirmed',~ta['confirmed'])]
 for field,edges in [('truth_E_GeV',cfg['energy_edges_GeV']),('y_lepton',cfg['y_edges']),('vertex_z_mm',cfg['vertex_z_edges_mm'])]:
  tm += [(field,f'{lo:g}_{hi:g}',(ta[field]>=lo)&(ta[field]<hi)) for lo,hi in zip(edges[:-1],edges[1:])]
 for label,value,mask in tm:
  if not mask.any():continue
  v=ta['z_bound_available'][mask];gg=tg[mask];bs=[]
  for draw in draws:
   vv=np.repeat(v,draw[gg])
   if len(vv):bs.append(np.mean(vv))
  lo,hi,status=source_interval(bs,len(set(gg)))
  coverage.append(dict(stratum=label,value=value,N=len(v),groups=len(set(gg)),bounded=int(sum(v)),fraction=np.mean(v),CI025=lo,CI975=hi,bootstrap_valid=len(bs),interval_status=status))
 write_table(out/'transport_coverage.tsv',coverage)
 bounded=[r for r in ref if r['bound_available']]
 highp=[r for r in bounded if r['primary_p_GeV']>=1600]
 below=[r for r in highp if r['reco_p_GeV']<r['p_low_GeV']]
 highp_sign=[r for r in ref if r['confirmed'] and r['primary_p_GeV']>=1600 and r['sign_disagreement']]
 physics=dict(
  bounded_confirmed_events=sum(r['confirmed'] for r in bounded),
  same_support_production_standardized_RMS=np.sqrt(np.mean([r['production_standardized_residual']**2 for r in bounded])),
  maximum_interval_width_over_sigma=max(r['kappa_interval_width_over_sigma'] for r in bounded),
  max_possible_abs_standardized_residual=max(max(abs(r['standardized_residual_low']),abs(r['standardized_residual_high'])) for r in bounded),
  highp_bounded_events=len(highp),highp_reco_below_bound=len(below),
  highp_propagation_loss_min=min(r['propagation_fraction_loss_low'] for r in highp),
  highp_propagation_loss_max=max(r['propagation_fraction_loss_high'] for r in highp),
  highp_below_bound_reco_deficit_min=min(1-r['reco_p_GeV']/r['primary_p_GeV'] for r in below),
  highp_below_bound_reco_deficit_max=max(1-r['reco_p_GeV']/r['primary_p_GeV'] for r in below),
  highp_confirmed_sign_disagreements=[dict(run=r['run'],eventID=r['eventID'],primary_p_GeV=r['primary_p_GeV'],abs_kappa_over_sigma=r['abs_kappa_over_sigma'],bound_available=r['bound_available']) for r in highp_sign],
  covariance_track_fitters=sorted({r['track_fitter'] for c in archive['cov'].values() for r in c['events']}),
  nearest_saved_z_distance_mm_quantiles=np.quantile([r['nearest_saved_z_distance_mm'] for r in table],[0,.5,1]).tolist(),
  exploratory_endpoint_summaries=True)
 (out/'physics_summary.json').write_text(json.dumps(physics,indent=2)+'\n')
 # Keep measured copy/reconstruction/export costs after raw shards are compacted.
 import re
 subjobs=[]
 for idx,c in archive['cov'].items():
  for stage,timing in sorted(c['stage_timings'].items()):
   m=re.search(r'wall_s=([\d.]+) max_rss_KiB=(\d+) user_s=([\d.]+) system_s=([\d.]+)',timing)
   wall,rss,user,system=map(float,m.groups())
   subjobs.append(dict(index=idx,stage=stage.removesuffix('.time'),wall_s=wall,peak_rss_KiB=int(rss),user_s=user,system_s=system))
 write_table(out/'cov_subprocess_resources.tsv',subjobs)
 summary=dict(transport_events=len(table),covariance_events=len(ref),groups=ng,primary_matches=sum(r['primary_matches']==1 for r in truths.values()),truth_branch_ambiguous=sum(r['ambiguous'] for r in table),near_z_saved_state_events=sum(r['saved_state_within_z_tolerance'] for r in table),z_bounded_events=sum(r['z_bound_available'] for r in table),reference_bounded_events=sum(r['bound_available'] for r in ref),all_original_front_reproduced=True,all_covariances_finite_symmetric_positive_diagonal=True,correlation_min_eigenvalue=min(r['covariance_correlation_min_eigenvalue'] for r in ref),reader_units_enum_disagreements=sum(r['declared_momentum_unit']!=r['enum_MEV'] for r in table),generated_muon_mass_raw_min=min(r['generated_muon_mass_raw'] for r in table),generated_muon_mass_raw_max=max(r['generated_muon_mass_raw'] for r in table),wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,calibration_test_challenge_evaluated=False)
 if a.compact:
  with gzip.open(archive_path,'wt',compresslevel=6) as f:json.dump(archive,f,separators=(',',':'))
  with gzip.open(archive_path,'rt') as f:assert json.load(f)==archive
  for row in manifest:
   for mode in ['requests','truth','cov']:
    path=root/f"{mode}/{row['index']}.json"
    if path.exists():path.unlink()
  summary.update(native_archive_bytes=archive_path.stat().st_size,native_archive_readback_verified=True)
 (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
