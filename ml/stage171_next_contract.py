"""Freeze bounded joint-control statistics after Stage171 exact replay succeeds."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage171_energy_ml'
assert json.loads((OUT/'audit_completion.json').read_text())['passed']
assert json.loads((OUT/'control_evidence.json').read_text())['pilot_feasible']
p=dict(stage=172,parent_stage=171,
    question='Measure same-event multi-hardware signed ADC integral covariance in strict random controls, with finite-file uncertainty and signal-contamination limits.',
    catalog='workbook/stage167_energy_ml/inventory.json',run=15838,
    paths=[f'/eos/experiment/faser/raw/2024/015838/Faser-Physics-015838-{i:05d}.raw' for i in range(400,432)],
    files='Fixed400..431, verify all32 literal paths in prior actual catalog on worker; no new listing or file replacement.',
    pilot_files=[400,401],full_files=list(range(402,432)),audit_RAW_files=[400,401],
    reference='ntuples/energy_ml_stage171/pilot_rows.jsonl.gz',
    GRL='workbook/stage166_energy_ml/exposure_input_manifest.json',
    official_headers='software/stage170/official_headers.tar.gz',
    strict_selection='Same unique supported framed valid TLB TAP==16 && TBP==16; preserve current/next bits, statuses and amplitudes.',
    limits=dict(physics_per_file=8192,max_RAW_frames_per_file=16384,bytes_before_next_frame=134217728,
                max_strict_per_file=256,final_event_bytes=12582912),
    ADC='All actual hardware channels; retain missing/bad/ambiguous boards as unknown; no guessed physical mapping or automatic channel31 removal.',
    raw_retention='All strict ADC up to256/file. If cap exceeded, record all trigger counts and mark support incomplete; no extrapolation/covariance certification. Original56 only for reference QA, no redundant persistent normal ADC.',
    windows=dict(pedestal=[0,40],signal_diagnostic=[60,140],offpulse=[180,256]),
    measurement='For each hardware channel: residual=mean(ADC[0:40])-ADC. Signed integrals are sums over fixed windows in ADC-code*samples; legitimate negatives retained. No fitted charge and no arrival-time input.',
    units='All hardware raw ADC-code units. Only Stage43 verified CaloNu20..23 may also quote factor2ns*0.1220703125mV/50ohm=0.0048828125pC per ADC-code*sample; not a real signal gain calibration.',
    statistics=['N/valid per channel and file/GRL/status/input bits/length/rail diagnostics',
        'Fixed hardware0..23,31 per-channel pedestal, signed-signal/offpulse mean,SD, min,max',
        'Pairwise event covariance/correlation with each pair N; joint25 complete support rank, no inverse/likelihood/shrinkage/prior',
        'CaloNu20..23 signed offpulse sum variance divided by sum channel variances; corresponding signal-window ratio',
        '1000 fixed-seed20261108 file-block bootstrap intervals for the two fixed ratios; no bootstrap-as-independent-events',
        'First16 vs last16 file blocks, same two ratios; no data-chosen window/cleaning/threshold/energy model'],
    confidence='95% percentile, conditional32file control/selection only; matrix descriptive with no per-cell discovery claim; no pure noise/gain/timewalk/DAQ exposure/physics nuisance certification.',
    pilot_admission='400 full8192 original metadata/ADC exact; 401 valid framing/at least one strict supported control; GNU full process CPU*3*32/2 + scheduler_used +600audit reserve <=2400.',
    independent_audit='Second RAW400/401 read exact, independent scalar fixed-window sums for every stored strict ADC and covariance/ratio recomputation; all32 counters and exact row identities unique.',
    CPU_budget_s=2400,phase_CPU_allowance_s=dict(pilot=400,full=1400,audit=600),
    request_CPUs=4,request_memory_MB=8000,max_jobs=1,worker_processes=4,MaxRuntime_s=86400,short_application_timeout=False,
    no=['new directory discovery','full files or full run','RAW/xAOD copy','G4/reconstruction','energy fit or forward','amplitude veto','fitted timing','inverse covariance prior','new neutrino independence claim'],
    preserve='Stage87/all original gates; pz0-only first-power momenta; px/py/q/p/bending allowed; raw11; typedNaN/signed/status0-only timing/Calo missing; pz>50GeV; allK/roles/reserved/quarantine/Stage54',
    overall_complete=False,promotion=False)
path=OUT/'next_execution_contract.json';assert not path.exists();path.write_text(json.dumps(p,indent=2)+'\n')
