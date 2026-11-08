"""Exact static source excerpts for next physical pilot; no event analysis."""
import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage173_energy_ml';CALYPSO=ROOT/'../calypso'
paths={
 'ntuple':'PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.cxx',
 'waveform':'Waveform/WaveRecTools/src/WaveformReconstructionTool.cxx',
 'digitization':'Waveform/WaveDigiTools/src/WaveformDigitisationTool.cxx',
 'fitter':'Tracking/Acts/FaserActsKalmanFilter/src/KalmanFitterTool.cxx',
 'ckf':'Tracking/Acts/FaserActsKalmanFilter/src/CKF2.cxx'}
lines={};rev='d32b0ff3cc4a2dad4abfb1474a82422c3c25b305'
needles={'ntuple':['"Track_pz0"','upstreamParameters =','m_pzup.push_back','targetSurface_Trig =','m_wave_bcidtime[ch] =','m_wave_triggertime[ch] ='],
 'waveform':['hit->set_trigger_time(','hit->set_bcid_time(','digi_offset = -16.'],
 'digitization':['trigger_time_slope(ctx)','hit.meanTime()-dtime-tof','hit.meanTime()+dtime-tof'],
 'fitter':['m_fit = makeTrackFitterFunction'], 'ckf':['m_fitter = makeTrackFitterFunction','true, true, reverseFilteringMomThreshold']}
for name,path in paths.items():
 text=subprocess.check_output(['git','-C',str(CALYPSO),'show',rev+':'+path],text=True)
 source=text.splitlines();lines[name]=dict(path=path,matches=[dict(line=i+1,text=line,context=source[max(0,i-1):i+3]) for i,line in enumerate(source) if any(n in line for n in needles[name])])
assert all(v['matches'] for v in lines.values())
result=dict(source_pin=rev,source=lines,
 timing='Local acquisition time; trigger_time removes nominal/offset/digitizer shift; bcid_time already uses clock. No additional phase subtraction authorized.',
 S0='Track_pz0 comes from first stored TrackParameters, labelled most-upstream measurement; actual event state/surface and original producer must still be measured.',
 material='Pinned fitter/CKF call enable scattering and energy-loss; this alone does not identify historical producer corrections at S0 or permit adding radiated energy.',
 new_measurements=False,no_energy_features_added=True,overall_complete=False)
(OUT/'static_next_physics_evidence.json').write_text(json.dumps(result,indent=2)+'\n')
