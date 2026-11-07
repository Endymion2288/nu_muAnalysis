"""Immutable multi-source CPU jobs; pinned runtime unpacked once per batch."""
import argparse
import json
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage130_energy_ml'
SPOOL = Path('/afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage130')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('phase', choices=['pilot', 'support', 'production'])
    p.add_argument('--indices', type=int, nargs='+')
    p.add_argument('--cpus', type=int, default=4)
    a = p.parse_args()
    protocol = json.loads((OUT / 'source_protocol.json').read_text())
    indices = a.indices
    if a.phase in ['pilot', 'support']:
        name = 'pilot_contract.json' if a.phase == 'pilot' else 'support_pilot_contract.json'
        frozen = json.loads((OUT / name).read_text())['indices']
        if indices is None:
            indices = frozen
        assert set(indices) <= set(frozen), 'Source indices differ from frozen contract'
    else:
        frozen = json.loads((OUT / 'production_contract.json').read_text())['indices']
        if indices is None:
            indices = frozen
        assert set(indices) <= set(frozen), 'Production indices differ from frozen contract'
    for index in indices:
        assert protocol['sources'][index]['eligible'] and not protocol['sources'][index]['old_locked']
    (ROOT / 'ntuples/energy_ml_stage130').mkdir(parents=True, exist_ok=True)
    stamp = time.time_ns()
    relative = f'software/stage130/{stamp}/energy-ml-stage130.tar.gz'
    target = ROOT / relative
    target.parent.mkdir(parents=True)
    files = [str(x.relative_to(ROOT)) for x in sorted((ROOT / 'ml').glob('*.py'))]
    files += ['ml/configs', 'AnalysisZipFramework/config', 'AnalysisZipFramework/include',
              'build/analysis', 'setup_env.sh', 'workbook/stage130_energy_ml/source_protocol.json',
              'AnalysisZipFramework/submission/run_ml_stage130_source.sh',
              'workbook/stage130_energy_ml/payload_snapshot.json']
    with tarfile.open(target, 'w:gz') as t:
        for name in files:
            t.add(ROOT / name, arcname=name)
    SPOOL.mkdir(parents=True, exist_ok=True)
    (SPOOL / 'logs').mkdir(exist_ok=True)
    worker = SPOOL / f'worker_{stamp}.sh'
    worker.write_bytes((ROOT / 'AnalysisZipFramework/submission/run_ml_stage130.sh').read_bytes())
    batches = [indices[i:i+a.cpus] for i in range(0, len(indices), a.cpus)]
    queue = '\n'.join(','.join(map(str, batch)) for batch in batches)
    descriptor = f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker} {a.phase} $(source_indices)
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = {a.cpus}
request_memory = {3000*a.cpus}MB
request_disk = {8000*a.cpus}MB
max_retries = 0
+MaxRuntime = 14400
+NuMuStage = "energy-ml-stage130"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue source_indices from (
{queue}
)
'''
    if a.phase == 'production':
        descriptor = descriptor.replace('+MaxRuntime = 14400', '+MaxRuntime = 86400')
        descriptor = descriptor.replace('queue source_indices from (',
            'max_materialize = 12\nmax_idle = 12\nqueue source_indices from (')
    sub = SPOOL / f'{a.phase}_{stamp}.sub'
    sub.write_text(descriptor)
    result = subprocess.check_output(['condor_submit', '-terse', str(sub)], text=True)
    record = dict(phase=a.phase, result=result, indices=indices, batches=batches,
                  cpus=a.cpus, descriptor=descriptor, package=dict(path=relative,
                  bytes=target.stat().st_size, files=files))
    (OUT / f'{a.phase}_submission_{stamp}.json').write_text(json.dumps(record, indent=2)+'\n')
    (OUT / f'{a.phase}_submission.json').write_text(json.dumps(record, indent=2)+'\n')
    print(result)


if __name__ == '__main__':
    main()
