"""Compact completed controls and immutable workers; text transport only."""
import gzip
import io
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage154_energy_ml'
CACHE = ROOT/'ntuples/energy_ml_stage154'


def main():
    account = json.loads((OUT/'scheduler_accounting.json').read_text())
    summary = json.loads((OUT/'summary.json').read_text())
    assert account['live_N'] == 0 and all(r['ExitCode'] == 0 for r in account['jobs'])
    assert summary['passed']
    if summary['phase'] == 'full':
        assert summary['prefix_reproducibility']['records_exact']
    events = [path for path in [CACHE/'pilot.json.gz', CACHE/'full.json.gz'] if path.exists()]
    payload = {}
    for path in events:
        with gzip.open(path, 'rt') as stream:
            payload[str(path.relative_to(ROOT))] = stream.read()
    target = CACHE/'event_records.json.gz'
    with gzip.open(target, 'wt') as stream:
        json.dump(payload, stream, separators=(',', ':'))
    with gzip.open(target, 'rt') as stream:
        assert json.load(stream) == payload
    assert target.stat().st_size <= 8388608
    capsule = ROOT/'software/stage154/source_snapshots.tar.gz'
    capsule.parent.mkdir(parents=True, exist_ok=True)
    transport = []
    with tarfile.open(capsule, 'w:gz') as destination:
        for path in sorted(OUT.glob('*_submission.json')):
            record = json.loads(path.read_text())
            package = ROOT/record['package']['path']
            with tarfile.open(package, 'r:gz') as source:
                for member in source:
                    if not member.isfile() or not member.name.endswith(('.py', '.hxx', '.sh', 'protocol.json')):
                        continue
                    data = source.extractfile(member).read()
                    info = tarfile.TarInfo(record['phase']+'/'+member.name)
                    info.size = len(data)
                    destination.addfile(info, io.BytesIO(data))
            worker = Path.home()/'condor/nu_muAnalysis/stage154'/('worker_'+package.parent.name+'.sh')
            destination.add(worker, arcname=record['phase']+'/submission/worker.sh')
            transport += [package, CACHE/(record['phase']+'_result.tar.gz')]
    deleted = []
    for path in events+transport:
        if path.exists():
            deleted.append(dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size))
            path.unlink()
    for path in transport:
        if path.parent != CACHE and path.parent.exists() and not any(path.parent.iterdir()):
            path.parent.rmdir()
    report = dict(all_jobs_terminal=True, event_text_equality=True,
        merged=dict(path=str(target.relative_to(ROOT)), bytes=target.stat().st_size),
        source_capsule=dict(path=str(capsule.relative_to(ROOT)), bytes=capsule.stat().st_size),
        deleted=deleted, deleted_bytes=sum(r['bytes'] for r in deleted),
        no_persistent_ROOT=True, original_inputs_and_other_stages_untouched=True)
    logs = []
    for row in account['jobs']:
        for suffix in ['out', 'err', 'log']:
            logs.append(Path.home()/'condor/nu_muAnalysis/stage154/logs'/
                        f"{row['ClusterId']}.{row['ProcId']}.{suffix}")
    log_archive = capsule.with_name('worker_logs.tar.gz')
    with tarfile.open(log_archive, 'w:gz') as destination:
        for path in logs:
            destination.add(path, arcname=path.name)
    with tarfile.open(log_archive, 'r:gz') as source:
        assert all(source.extractfile(path.name).read() == path.read_bytes() for path in logs)
    report['actual_worker_logs'] = dict(N=len(logs), path=str(log_archive.relative_to(ROOT)),
                                      bytes=log_archive.stat().st_size, byte_equality=True)
    (OUT/'storage_cleanup.json').write_text(json.dumps(report, indent=2)+'\n')
    print(report)


if __name__ == '__main__':
    main()
