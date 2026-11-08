"""Compile the small bridge with the pinned runtime's gcc ABI, on the worker."""
import json
import os
import subprocess
from pathlib import Path

root = Path.cwd()
out = root / 'workbook/stage192_energy_ml'
spec = json.loads((out / 'build_spec.json').read_text())
runtime = Path(os.environ['FASER_CALYPSO_RUN'])
command = [spec['compiler'], *spec['flags'], '-I'+str(runtime/'include'), '-I'+str(root/'ml')]
command += ['-I/cvmfs/atlas.cern.ch/repo/sw/software/24.0/Athena/24.0.41/InstallArea/x86_64-el9-gcc13-opt/include']
command += ['-I'+p for p in spec['includes']]
command += ['ml/stage192_links.cxx', '-o', str(root/'stage192_links.so')]
(out/'bridge_compile_command.json').write_text(json.dumps(command, indent=2)+'\n')
subprocess.run(command, check=True)
