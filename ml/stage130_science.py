"""Stdlib-only packaging/collection for source-independent Stage130 calculations."""
import argparse
import json
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage130_energy_ml'
SPOOL = Path('/afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage130')


def submit(phase, files, cpus=8, memory=24000):
    stamp = time.time_ns()
    relative = f'software/stage130/{stamp}/energy-ml-stage130-{phase}.tar.gz'
    target = ROOT / relative
    target.parent.mkdir(parents=True)
    with tarfile.open(target, 'w:gz') as t:
        for name in dict.fromkeys(files):
            t.add(ROOT / name, arcname=name)
    worker = SPOOL / f'worker_science_{stamp}.sh'
    worker.write_bytes((ROOT / 'AnalysisZipFramework/submission/run_ml_stage130_science.sh').read_bytes())
    descriptor = f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker} {phase}
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = {cpus}
request_memory = {memory}MB
request_disk = 8000MB
max_retries = 0
+MaxRuntime = 14400
+NuMuStage = "energy-ml-stage130"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
    sub = SPOOL / f'{phase}_{stamp}.sub'
    sub.write_text(descriptor)
    result = subprocess.check_output(['condor_submit', '-terse', str(sub)], text=True)
    record = dict(phase=phase, result=result, descriptor=descriptor,
                  package=dict(path=relative, bytes=target.stat().st_size, files=files))
    (OUT / f'{phase}_submission_{stamp}.json').write_text(json.dumps(record, indent=2)+'\n')
    (OUT / f'{phase}_submission.json').write_text(json.dumps(record, indent=2)+'\n')
    print(result)


def collect(phase):
    remote = f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage130/{phase}_result.tar.gz'
    transport = Path(f'/tmp/nu_mu_stage130_{phase}_return.tar.gz')
    subprocess.run(['xrdcp', '--silent', '--force', remote, str(transport)], check=True)
    members = []
    with tarfile.open(transport) as t:
        for member in t.getmembers():
            if not member.isfile():
                continue
            path = Path(member.name)
            assert not path.is_absolute() and '..' not in path.parts
            assert any(member.name.startswith(prefix) for prefix in
                       ['workbook/stage130_energy_ml/', 'ntuples/energy_ml_stage130/', 'ml/artifacts/stage130/'])
            payload = t.extractfile(member).read()
            target = ROOT / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            assert target.read_bytes() == payload
            members.append(dict(path=member.name, bytes=len(payload)))
    (OUT / f'{phase}_transfer.json').write_text(json.dumps(dict(phase=phase, members=members,
        transport_bytes=transport.stat().st_size, byte_roundtrip_verified=True), indent=2)+'\n')
    transport.unlink()
    print('collected', phase, len(members))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['submit', 'collect'])
    p.add_argument('phase')
    p.add_argument('--manifest')
    p.add_argument('--cpus', type=int, default=8)
    p.add_argument('--memory', type=int, default=24000)
    a = p.parse_args()
    if a.action == 'submit':
        submit(a.phase, json.loads(Path(a.manifest).read_text()), a.cpus, a.memory)
    else:
        collect(a.phase)
