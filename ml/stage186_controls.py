"""Batch-only old X62 reproduction and actual selected PHYS/RDO controls."""
import json,time,sys
from pathlib import Path
import numpy as np
import ROOT as R
from audited_features import configuration,SCINTILLATORS,WAVE_INVALID,FIT_INVALID
from stage119_curve_common import old_inputs,load
from stage122_saved import SavedWaveforms
OUT=Path('workbook/stage186_energy_ml');CACHE=Path('ntuples/energy_ml_stage186')
if __name__=='__main__':
 diagnostic='--diagnostic' in sys.argv;calodifferences=[]
 from alternative_calibration import reference_matrix
 start=time.process_time();d=load('ntuples/energy_ml_stage119/old_input.npz');rebuilt=old_inputs()
 for k in d:
  if k in rebuilt:np.testing.assert_array_equal(d[k],rebuilt[k])
 p=json.loads((OUT/'protocol.json').read_text());requests=json.loads(Path('workbook/stage129_energy_ml/extraction_contract.json').read_text())['requests'];channels=p['channels'];names=configuration()['features']
 assert R.gSystem.Load('libWaveRawEvent.so')>=0
 support70=load('ntuples/energy_ml_stage70/support.npz');original70=reference_matrix(support70['x_produced'],200080);np.testing.assert_array_equal(original70,support70['x'])
 closure70=json.loads(Path('workbook/stage70_energy_ml/calibration_closure.json').read_text());calo70_N=0
 summary=[];failures=[];rawexact=0;caloexact=0;pzexact=0;legacyexact=0;legacyN=0
 for i in p['pilot']['source_indices']:
  s=requests[i];cases=[c for c in s['cases'] if c['role']==1][:p['pilot']['actual_train_N'][str(i)]]
  if not cases or not s['phys']:
   summary.append(dict(index=i,N=len(cases),PHYS_present=bool(s['phys']),reason='No original train or PHYS; no replacement'));continue
  f=R.TFile.Open(s['phys']);assert f and not f.IsZombie();t=f.Get('nt');t.SetBranchStatus('*',0)
  fields=['run','eventID','Track_pz0']+[n+'_'+v for n in SCINTILLATORS+[f'Calo{j}' for j in range(4)] for v in ['raw_charge','status','baseline']]+[f'Calo{j}_E_EM' for j in range(4)]
  for b in fields:assert t.GetBranch(b),b;t.SetBranchStatus(b,1)
  saved=SavedWaveforms(R,s['rdo'],['Calo','VetoNu','Veto','Trigger','Preshower']);checks=0;pzunknown=0;neg=0
  detector_channels=list(zip(SCINTILLATORS,channels[4:]));detector_channels += [(f'Calo{j}',j) for j in range(4)]
  for c in cases:
   assert t.GetEntry(c['entry'])>0;assert (int(t.run),int(t.eventID))==(c['run'],c['event']);row=c['row'];assert d['role'][row]==1
   pz=list(t.Track_pz0);leading=max(pz)/1000 if pz else np.nan
   if np.isclose(leading,c['pz'],rtol=3e-7,atol=3e-5):
    np.testing.assert_array_equal(np.float32(leading),d['x'][row,names.index('ML_mu_pz0_GeV')]);pzexact+=1
   else:pzunknown+=1
   waves=saved.read(c['entry'],c['run'],c['event']);wm={w['channel']:w for v in waves.values() for w in v}
   for n,ch in detector_channels:
    status=int(getattr(t,n+'_status'));q=float(getattr(t,n+'_raw_charge'));neg+=q<0
    if ch>=4:
     expected=np.nan if status&WAVE_INVALID else np.float32(q);actual=d['x'][row,names.index(n+'_raw_charge')]
     np.testing.assert_array_equal(actual,expected);rawexact+=1
    else:
     expected=np.nan if status&FIT_INVALID else np.float32(float(getattr(t,n+'_E_EM'))/1000);actual=d['x'][row,names.index(f'ML_calo{ch}_E_EM_GeV')]

     if np.array_equal(actual,expected,equal_nan=True):caloexact+=1
     else:
      if len(calodifferences)<32:calodifferences.append(dict(index=i,row=row,channel=ch,PHYS_E_EM_MeV=float(getattr(t,n+'_E_EM')),old_X_GeV=float(actual),double_divide_GeV=float(expected),float_divide_GeV=float(np.float32(getattr(t,n+'_E_EM'))/np.float32(1000))))
      if s['origin']==70:
       originrow=d['origin_row'][row];np.testing.assert_array_equal(actual,original70[originrow,names.index(f'ML_calo{ch}_E_EM_GeV')]);np.testing.assert_allclose(actual,expected,rtol=closure70['comparison_rtol'],atol=closure70['comparison_atol_GeV'],equal_nan=True);calo70_N+=1
      elif not diagnostic:np.testing.assert_array_equal(actual,expected)
    if ch in wm and not(status&WAVE_INVALID):
     w=wm[ch];baseline=np.float32(getattr(t,n+'_baseline'));lo,hi=(390,465) if ch<4 else (390,490)
     values=(baseline-np.array(w['adc'][lo:hi+1],dtype='float32')*np.float32(2000/16384)).astype('float32')
     predicted=np.float32(np.float32(2*sum(float(v) for v in values))/np.float32(50))
     legacyN+=1
     if np.float32(q)==predicted:legacyexact+=1
     elif len(failures)<32:failures.append(dict(index=i,row=row,channel=ch,PHYS_pC=q,computed_legacy_pC=float(predicted),baseline_mV=float(baseline)))
    checks+=1
  f.Close();saved.file.Close();summary.append(dict(index=i,N=len(cases),PHYS_present=True,leading_unknown_N=pzunknown,negative_old_raw_N=neg,scalar_checks_N=checks))
 result=dict(passed=not failures and all(r['index']==254 for r in calodifferences),Calo_differences=calodifferences,origin70_original_rescale_exact=True,origin70_old_PHYS_original_precision_pass_N=calo70_N,raw_control_definition='Actual d32 PHYS signed fullwindow, not6d6 RDOproducer reconstruction',X62_reproduced_all89033_exact=True,original_roles_exact=True,actual_scint11_feature_controls_exact_N=rawexact,actual_Calo_feature_controls_exact_N=caloexact,actual_pz0_controls_exact_N=pzexact,legacy_raw_checked_N=legacyN,legacy_raw_exact_N=legacyexact,legacy_raw_failures=failures,sources=summary,CPU_s=time.process_time()-start,new_features_for_cal_test=0,energy_fits=0,overall_complete=False)
 (OUT/('diagnostic_input_controls.json' if diagnostic else 'input_controls.json')).write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True);assert diagnostic or result['passed']
