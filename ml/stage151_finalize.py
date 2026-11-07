"""Lossless compact event/source audit, only after terminal jobs and verification."""
import gzip
import io
import json
import re
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage151_energy_ml'
CACHE = ROOT/'ntuples/energy_ml_stage151'


def main():
    accounting = json.loads((OUT/'scheduler_accounting.json').read_text())
    summary = json.loads((OUT/'summary.json').read_text())
    assert accounting['live_N'] == 0
    assert summary['passed'] and all(r['ExitCode'] == 0 for r in accounting['jobs'])
    if summary['phase'] == 'full':
        assert summary['prefix_reproducibility']['passed']
    paths = list(CACHE.glob('*/native.json.gz'))+list(CACHE.glob('*/paired.json.gz'))
    paths += list(CACHE.glob('*/legacy.json.gz'))
    paths += list(OUT.glob('*/seeds.json'))
    payload = {}
    for path in paths:
        if path.suffix == '.gz':
            with gzip.open(path, 'rt') as stream:
                text = stream.read()
        else:
            text = path.read_text()
        payload[str(path.relative_to(ROOT))] = text
    target = CACHE/'event_records.json.gz'
    with gzip.open(target, 'wt') as stream:
        json.dump(payload, stream, separators=(',', ':'))
    with gzip.open(target, 'rt') as stream:
        assert json.load(stream) == payload
    assert target.stat().st_size <= 8388608
    capsule = ROOT/'software/stage151/source_snapshots.tar.gz'
    capsule.parent.mkdir(parents=True, exist_ok=True)
    transports = []
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
            worker = Path.home()/'condor/nu_muAnalysis/stage151'/('worker_'+package.parent.name+'.sh')
            destination.add(worker, arcname=record['phase']+'/submission/worker.sh')
            transports.append(package)
            transports.append(CACHE/(record['phase']+'_result.tar.gz'))
    deleted = []
    for path in paths+transports:
        if path.exists():
            deleted.append(dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size))
            path.unlink()
    for path in transports:
        if path.parent != CACHE and path.parent.exists() and not any(path.parent.iterdir()):
            path.parent.rmdir()
    report = dict(all_jobs_terminal=True, event_text_equality=True,
        merged=dict(path=str(target.relative_to(ROOT)), bytes=target.stat().st_size),
        source_capsule=dict(path=str(capsule.relative_to(ROOT)), bytes=capsule.stat().st_size),
        deleted=deleted, deleted_bytes=sum(row['bytes'] for row in deleted),
        source_HITS_PHYS_and_other_stages_untouched=True)
    metadata_paths = list(OUT.glob('*/input_metadata.json'))
    if metadata_paths:
        original_text = metadata_paths[0].read_text()
        assert all(path.read_text() == original_text for path in metadata_paths)
        (OUT/'input_metadata.json').write_text(original_text)
        report['identical_input_metadata_copies_merged'] = len(metadata_paths)
        for path in metadata_paths:
            path.unlink()
    logs = list(OUT.glob('*/*.log'))
    log_archive = capsule.with_name('worker_logs.tar.gz')
    with tarfile.open(log_archive, 'w:gz') as archive:
        for path in logs:
            archive.add(path, arcname=str(path.relative_to(ROOT)))
    with tarfile.open(log_archive, 'r:gz') as archive:
        assert all(archive.extractfile(str(path.relative_to(ROOT))).read() == path.read_bytes() for path in logs)
    for path in logs:
        path.unlink()
    report['logs_compacted'] = dict(N=len(logs), path=str(log_archive.relative_to(ROOT)), bytes=log_archive.stat().st_size)
    (OUT/'storage_cleanup.json').write_text(json.dumps(report, indent=2)+'\n')
    resources = []
    for path in sorted(OUT.glob('*/pipeline.json')):
        pipeline = json.loads(path.read_text())
        for step in pipeline['steps']:
            timing = (path.parent/(step['name']+'_time.txt')).read_text()
            def metric(key):
                match = re.search(r'(?m)^\s*'+re.escape(key)+r': (\S+)', timing)
                return float(match.group(1)) if match else None
            resources.append(dict(phase=path.parent.name, step=step['name'], wall_s=step['wall_s'],
                GNU_CPU_s=metric('User time (seconds)')+metric('System time (seconds)'),
                RSS_KiB=metric('Maximum resident set size (kbytes)')))
    (OUT/'resource_audit.json').write_text(json.dumps(dict(steps=resources,
        accounting='Step GNU CPU is included in scheduler accounting; never add twice',
        GPU=0, scientific_payload_statistics_computed_locally=False), indent=2)+'\n')
    print(report)


if __name__ == '__main__':
    main()
