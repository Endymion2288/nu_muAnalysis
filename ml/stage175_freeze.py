"""Freeze existing cohort support, tails and actual S0 inventory before event access."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage175_energy_ml'
OUT.mkdir(parents=True,exist_ok=True);(ROOT/'ntuples/energy_ml_stage175').mkdir(parents=True,exist_ok=True)
assert not (OUT/'protocol.json').exists()
p=json.loads((ROOT/'workbook/stage129_energy_ml/extraction_contract.json').read_text())
protocol=dict(stage=175,parent_commit='b83e2ee',question='Whole original-cohort support for newly calibrated same-slab prompt-relative means, fixed real-control tails, and native leading pz0 S0 inventory; no energy training yet.',
 source_contract='workbook/stage129_energy_ml/extraction_contract.json',source_N=len(p['requests']),original_N=sum(len(s['cases']) for s in p['requests']),
 pilot_indices=p['pilot_indices'],pilot_first_train_N=32,full='All original explicitly selected entries from all280 frozen sources,including absent PHYS and role0 as missing denominators; no substitute source or directory scan.',
 mapping='Explicit each actual MC run COOL OFLP200/tag05 CableMapping; compare sameplate/oppositePMT and hardware8..11 with control. Also actual source histogram titles. Unknown is missing, no silent transplant.',
 calibrations='workbook/stage174_energy_ml/calibrations.json',features='Only two relative means: each data8006 and MC100012 gate usable. MC coefficients only; no data offset transfer. Difference/position not supplied because all real difference gates failed.',
 support='Original status exactly0,localtime finite>0, positive rawQ for each end/reference, leading pz0 exact original match, finite physical Trig projections/angles, and every MC training qL/qR/qRef/x/y minmax. Preserve signed charges; invalid derived mean NaN.',
 split='Original unchanged roles/K/reserved/quarantine; report all89033 denominator and role1/2/3 separately; no prediction for role0.',
 native_S0='Optional original Track_x0/y0/z0 of identical leading pz0; never read p0/p1/pz1. Record absence/mismatch rather than invent plane. This is fitted state, not vertex muon energy or independent local momentum.',
 tails='All Stage174 heldout valid rows, fixed |residual|>2ns; counts and fixed localtime ranges [-infty,100),[100,300),[300,infty), phase finite/nonfinite, reference timing, charge/position range support. No drop/re-fit/window or threshold scan; event identities retained only compact fixed first8 tail examples per row.',
 audit='Actual independent first selected case in each3 pilot source; all extracted fields exact vs full, full original pilot selected rows exact; scalar derived mean/missingness checks and independent counts.',
 CPU_budget_s=4500,phase_CPU_allowance_s=dict(pilot=300,full=3600,audit=600),request_CPUs=8,worker_processes=8,request_memory_MB=12000,max_jobs=1,MaxRuntime_s=86400,short_application_timeout=False,
 admission='3*(sum worker file-read CPU * original_N/96 + max(0,pilot GNU CPU - worker read CPU)*8/3 process-startup scaling + mapping GNU CPU), <=3600 full phase and plus used schedulerCPU+600audit <=4500. Pre-submission decomposition keeps measured setup in the cost without scaling a one-time import per event.',
 preserve='Stage87/all original gates; pz0-only firstpower/raw11/typedNaN/signed/status0 timing/Calo missing;pz>50GeV/allK/roles/reserved/quarantine/Stage54',
 no=['energy fit/forward','new G4','new parents','source replacement','non0-status timing','weak-signal extrapolation','data offsets to MC','real position certification'],promotion=False,overall_complete=False)
(OUT/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
print('Frozen',protocol['original_N'],'rows',protocol['source_N'],'sources')
