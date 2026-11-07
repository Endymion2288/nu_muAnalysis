"""Compact the completed empty-support audit; never modify original inputs."""
import io
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage150_energy_ml'


def main():
    accounting = json.loads((OUT/'scheduler_accounting.json').read_text())
    support = json.loads((OUT/'support.json').read_text())
    assert accounting['live_N'] == 0 and accounting['completed_N'] == 1
    assert accounting['jobs'][0]['ExitCode'] == 0
    assert support['passed'] and support['eligible_overflow_parents'] == 0
    submission = json.loads((OUT/'support_submission.json').read_text())
    package = ROOT/submission['package']['path']
    capsule = ROOT/'software/stage150/source_snapshots.tar.gz'
    capsule.parent.mkdir(parents=True, exist_ok=True)
    stamp = package.parent.name
    worker = Path.home()/f'condor/nu_muAnalysis/stage150/worker_{stamp}.sh'
    with tarfile.open(capsule, 'w:gz') as destination:
        with tarfile.open(package, 'r:gz') as source:
            for member in source:
                if not member.isfile() or not member.name.endswith(('.py', 'protocol.json')):
                    continue
                data = source.extractfile(member).read()
                info = tarfile.TarInfo(member.name)
                info.size = len(data)
                destination.addfile(info, io.BytesIO(data))
        destination.add(worker, arcname='submission/worker.sh')
        destination.add(ROOT/'ml/stage150_submit.py', arcname='ml/stage150_submit.py')
    deleted = []
    for path in [package, ROOT/'ntuples/energy_ml_stage150/support_result.tar.gz']:
        deleted.append(dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size))
        path.unlink()
    if not any(package.parent.iterdir()):
        package.parent.rmdir()
    report = dict(all_jobs_terminal=True, no_new_transport_or_ROOT=True,
        source_capsule=dict(path=str(capsule.relative_to(ROOT)), bytes=capsule.stat().st_size),
        deleted=deleted, deleted_bytes=sum(row['bytes'] for row in deleted),
        retained='Compact support JSON/35-row TSV, scheduler/timing/source audit only',
        original_inputs_and_other_stages_untouched=True)
    (OUT/'storage_cleanup.json').write_text(json.dumps(report, indent=2)+'\n')
    print(report)


if __name__ == '__main__':
    main()
