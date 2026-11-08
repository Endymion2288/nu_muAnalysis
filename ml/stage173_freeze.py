"""One bounded detector-regime decision before new physical measurements."""
import io,json,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage173_energy_ml'
old=['ml/stage172_common.py','ml/stage172_full.py','ml/stage172_pilot.py','ml/stage172_raw.cxx',
     'workbook/stage172_energy_ml/protocol.json','workbook/stage172_energy_ml/header_sources.json']
# These are our own unsubmitted draft files, not the user's committed Stage172 research.
with tarfile.open(ROOT/'software/stage173/deferred_stage172_draft.tar.gz','w:gz') as t:
    for name in old:
        data=(ROOT/name).read_bytes();info=tarfile.TarInfo(name);info.size=len(data);t.addfile(info,io.BytesIO(data))
with tarfile.open(ROOT/'software/stage173/deferred_stage172_draft.tar.gz') as t:
    assert all(t.extractfile(n).read()==(ROOT/n).read_bytes() for n in old)
for name in old:(ROOT/name).unlink()
protocol=dict(stage=173,parent_commit='e973721',
 references=['workbook/2026-11-08_stage172_readout-regimes-and-observability-research.md','workbook/2026-11-08_stage172_retraining-and-detector-readout-supplement.md'],
 question='One bounded actual inclusive/CaloNu GRL and channel-condition applicability decision, not calibration or endless historical reconstruction.',
 run=15838,GRL_paths=[f'/cvmfs/faser.cern.ch/repo/sw/runlist/v10/faser_goodrunlist_2024_{s}.json' for s in ['physics','physics_calonu']],
 pages=['https://twiki.cern.ch/twiki/bin/view/FASER/FaserLuminosity','https://twiki.cern.ch/twiki/bin/view/FASER/BadFASERRuns'],
 database_base='/cvmfs/faser.cern.ch/repo/sw/database/DBRelease/current/sqlite200',
 folders=['/WAVE/DAQ/CableMapping','/WAVE/DAQ/Range','/WAVE/DAQ/Timing','/WAVE/DAQ/TimingOffset','/WAVE/Calibration/MIP_ref','/WAVE/Calibration/HV'],
 database_files=['CABP200.db','ALLP200.db'],
 data_instance='CONDBR3',MC_instance='OFLP200',MC_tag='OFLCOND-FASER-05',MC_runs=[100012,100049],
 requested_channels=list(range(24))+[31],max_channel=63,max_folder_rows=4096,
 data_time_keys_unix_s=[1720449636,1720473060,1720473064,1720503223],
 data_time_interval_inclusive_s=[1720449636,1720503223],
 endpoint='Stage171 RAW00400 finite prefix. Whole-run HV IOV browse bounded4096 records, no event payload.',
 pilot='Two explicit GRLs, two official pages, CableMapping25 channels at run15838 and HV at RAW400 first second; record absent/error without fallback.',
 full='Remaining explicit data folders/run and bounded HV interval plus same explicit folders for MC100012/100049. Only after pilot terminal and complete-GNU threefold projection within budget.',
 audit='Independent GRL record/membership and selected conditions re-query from actual DB. No data-quality inference from numeric equality.',
 CPU_budget_s=900,phase_CPU_allowance_s=dict(pilot=200,full=450,audit=250),request_CPUs=2,request_memory_MB=6000,max_jobs=1,MaxRuntime_s=86400,
 official_runtime_pin='d32b0ff3cc4a2dad4abfb1474a82422c3c25b305',short_application_timeout=False,
 HTTP_per_page_limit_bytes=1048576,HTTP_timeout_s=30,
 preserve='Stage87/all original gates, pz0-only first-power momenta, raw11/typedNaN/signed/status0 timing/Calo missing, pz>50GeV, allK, roles/reserved/quarantine, Stage54',
 no=['RAW/ROOT/event arrays','calibration fit','energy fit/forward','new production','unbounded folder/directory discovery','new prior','GRL luminosity extrapolation'],
 missing_policy='Record exact absent source, error or unsupported IOV. Finish one applicability judgement; no alternate tag/instance fallback or infinite historical searches.',
 deferred_draft=dict(archive='software/stage173/deferred_stage172_draft.tar.gz',files=old,exact_bytes_verified=True,unsubmitted=True),
 overall_complete=False,promotion=False)
(OUT/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
