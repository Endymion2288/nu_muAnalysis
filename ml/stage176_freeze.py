"""Small original natural-parent S0 instrumentation, not another full replay."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage176_energy_ml';OUT.mkdir(parents=True,exist_ok=True);(ROOT/'ntuples/energy_ml_stage176').mkdir(parents=True,exist_ok=True)
assert not (OUT/'protocol.json').exists()
old=json.loads((ROOT/'workbook/stage135_energy_ml/pilot_protocol.json').read_text())
p=dict(stage=176,parent_stage=174,question='Actual native pz0 reference surface, material convention, primary-muon crossing brackets and first-generation muon-secondary production labels on fixed natural parents.',
 sources=['ntuples/energy_ml_stage131/production_cases.json.gz','ntuples/energy_ml_stage131/parent_evidence.json.gz','ntuples/energy_ml_stage131/matched_input.npz','ntuples/energy_ml_stage135/parent_50_qa_hits.json.gz'],
 preflight_index=old['preflight_index'],remaining_indices=old['remaining_indices'],pilot_total_parents=12,
 selection='Exact old Stage131/135 first2train per6strata in fixed hash order; retain migrated/unknown parent. No tail/clip/source/error selection. Not representative exposure or new nu.',
 runtime='Pinned d32+TI12MC04+FTFP_BERT+tag06; same EVNT/entry/G4seed/HITSfilename, digitizer private seeds and original filenames. Only new read-only observer rebuilt; no Calypso rebuild.',
 instrumentation='Preserve all legacy fields and ordered 14-field DAQ hits. Add every primary-muon pre/post segment, primary initial state, direct-primary-muon secondary birth group/position/time/process/KE/total, inherited through descendants, parallel ordered DAQ group IDs. No new Geant steps,RNG,track info or transport changes.',
 S0='Actual first TrackParameters of matched leading ntuple pz0, native surface name/type/center/normal/covariance. Match all xyz/pxpy/pz at float32 interface. Snapshot actual merged-withoutIFT native collection after merge; no duplicate momentum model inputs. Preserve primary-association unknown.',
 analysis='Orient actual plane normal along primary muon momentum. Record every forward/back segment bracket at actual plane, pre/post energy interval without interpolated exact crossing. Classify first muon-child birth position before/after plane, inherited source at each actual sensitive hit. Direct primary muon and other/unknown roots separate. No radiation energy correction or E_nu closure claim.',
 acceptance=['old observer fields exact','ordered HITS count/ID/barcode and compressed-energy closure','preflight observer on/off sensitive HITS exact','same parent original pz0/selected raw11/status exactly preserved where old reference exists','actual S0 surface matched or explicit unknown','new group IDs form full per-hit partition; no unlabelled hit silently discarded'],
 limits='Small conditional mechanism/support pilot only. Birth KE sum not equal radiative loss. Fitted pz0 material energy-loss/scattering enabled in pinned source, detailed historical corrections not recoverable; no double count/add-back. Same-window analog source response and energy error contrast require separate support/contract after this pilot.',
 CPU_budget_s=10000,phase_CPU_allowance_s=dict(preflight=1500,pilot=7000,audit=1500),request_CPUs=4,request_memory_MB=12000,worker_processes=3,max_jobs=1,MaxRuntime_s=86400,short_application_timeout=False,
 admission='After successful exact1parent preflight, complete GNU CPU threefold times11 + used schedulerCPU +1500 audit <=10000 and projected<=7000; else no remaining11. Original4032 replay not authorized.',
 preserve='Stage87/all gates;pz0-only firstpower/raw11/typedNaN/signed/status0-only timing/Calo missing;pz>50GeV/K/roles/reserved/quarantine/Stage54',
 no=['energy fit/forward','readout repair','new independent nu','extra parents','truth input deployment','G4 step forcing','interpolated exact crossing energy','automatic production'],overall_complete=False,promotion=False)
(OUT/'protocol.json').write_text(json.dumps(p,indent=2)+'\n')
