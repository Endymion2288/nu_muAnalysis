#!/usr/bin/env python3
"""Package frozen controls and pinned source; retain no duplicate source checkout."""
import io
import shutil
import subprocess
import tarfile
from pathlib import Path

repo=Path(__file__).resolve().parents[1]
paths=['setup_env.sh','ml/read_calonu_native.py','ml/locate_calonu_native.py','ml/report_calonu_native.py',
       'ml/repair_calonu_wavefit.py','ml/build_waveform_repair.py','ml/StableWaveformIntegral.h',
       'ml/configs/calonu_repair_control.json','workbook/stage37_energy_ml/conditions_audit.json',
       'workbook/stage36_energy_ml/geometry_audit.json']
paths += [f'workbook/stage38_energy_ml/request_{i}.json' for i in [1,4,7,10]]
target=repo/'software/energy-ml-calonu-repair-stage38.tar.gz'
with tarfile.open(target,'w:gz') as tar:
    for p in paths: tar.add(repo/p,arcname=p)
    for name in ['WaveformFitResult.h','WaveformFitResult.cxx','WaveformReconstructionTool.cxx']:
        content=subprocess.check_output(['git','-C',str(repo.parent/'calypso'),'show','1ec47efe:Waveform/WaveRecTools/src/'+name])
        info=tarfile.TarInfo('ml/pinned_waveform/'+name);info.size=len(content);tar.addfile(info,io.BytesIO(content))
spool=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage38')
(spool/'logs').mkdir(parents=True,exist_ok=True)
shutil.copy2(repo/'AnalysisZipFramework/submission/run_ml_calonu_repair.sh',spool)
(spool/'run_ml_calonu_repair.sh').chmod(0o755)
(repo/'ntuples/energy_ml_stage38/shards').mkdir(parents=True,exist_ok=True)
print(dict(payload=str(target),bytes=target.stat().st_size))
