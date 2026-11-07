"""Stdlib transport verification; numerical source QA runs inside Condor."""
import argparse
import json
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage130_energy_ml'
CACHE = ROOT / 'ntuples/energy_ml_stage130'


def collect(phase, index, verbose=True):
    destination = CACHE / f'{phase}_{index}'
    if (destination / 'exitcode.txt').exists() and (destination / 'exitcode.txt').read_text().strip() == '0':
        return None
    remote = f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage130/{phase}_{index}.tar.gz'
    transport = Path(f'/tmp/nu_mu_stage130_{phase}_{index}.tar.gz')
    subprocess.run(['xrdcp', '--silent', '--force', remote, str(transport)], check=True)
    members, payloads = [], []
    with tarfile.open(transport) as t:
        for member in t.getmembers():
            if not member.isfile():
                continue
            relative = Path(member.name)
            assert not relative.is_absolute() and '..' not in relative.parts and relative.parts[0] == 'result'
            payload = t.extractfile(member).read()
            payloads.append((Path(*relative.parts[1:]), payload))
            members.append(dict(name=member.name, bytes=len(payload)))
    assert any(str(name) == 'exitcode.txt' for name, _ in payloads)
    # A complete validated tar is required before publishing the completion
    # marker. Keep a failed prior attempt available for the final audit.
    if destination.exists():
        destination.rename(CACHE / f'{phase}_{index}_previous_{time.time_ns()}')
    destination.mkdir(parents=True, exist_ok=True)
    for name, payload in sorted(payloads, key=lambda item: str(item[0]) == 'exitcode.txt'):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        assert target.read_bytes() == payload
    report = dict(phase=phase, index=index, bytes=transport.stat().st_size,
                  members=members, byte_roundtrip_verified=True,
                  exitcode=int((destination / 'exitcode.txt').read_text()))
    for name in ['request_summary.json', 'source_qa.json', 'identity.json']:
        if (destination / name).exists():
            report[name] = json.loads((destination / name).read_text())
    (OUT / f'{phase}_{index}_audit.json').write_text(json.dumps(report, indent=2) + '\n')
    transport.unlink()
    if verbose:
        print(phase, index, report['exitcode'], report.get('source_qa.json', {}).get('counts'))
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('phase')
    p.add_argument('indices', type=int, nargs='+')
    args = p.parse_args()
    for index in args.indices:
        collect(args.phase, index)
