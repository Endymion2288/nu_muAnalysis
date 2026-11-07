"""Retire only verified Stage131 duplicates after all exact attempts terminate."""
import gzip
import json
import re
import shutil
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage131_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage131'


def archive_exact(path,files,base):
    files=sorted(set(files))
    with tarfile.open(path,'w:gz') as archive:
        for item in files:archive.add(item,arcname=str(item.relative_to(base)),recursive=False)
    with tarfile.open(path) as archive:
        members=archive.getmembers();assert len(members)==len(files)
        for member in members:
            assert archive.extractfile(member).read()==(base/member.name).read_bytes()
    return files


def main():
    assert json.loads((OUT/'analysis_complete.json').read_text())['successful']
    assert json.loads((OUT/'independent_validation.json').read_text())['passed']
    resources=json.loads((OUT/'resource_summary.json').read_text())
    assert resources['unique_submitted']==resources['observed']==resources['terminal']
    proof=json.loads((OUT/'compact_verification.json').read_text())
    assert proof['passed'] and proof['parents']==4032
    assert json.loads((OUT/'full_parent_audit.json').read_text())['all_fixed_parents_complete']
    with gzip.open(CACHE/'parent_evidence.json.gz','rt') as stream:evidence=json.load(stream)
    assert len(evidence)==proof['parents'] and len({r['index'] for r in evidence})==proof['parents']
    assert (CACHE/'matched_input.npz').is_file() and (CACHE/'selected_extra.npz').is_file()
    assert (CACHE/'execution_times.json.gz').is_file()
    retired=[];removed_B=0
    def retire(path):
        nonlocal removed_B
        if path.is_file():
            removed_B+=path.stat().st_size;retired.append(str(path.relative_to(ROOT)));path.unlink()
    # Preserve the failed engineering attempts without thousands of loose files.
    failure_files=[f for d in OUT.glob('pilot_attempt_*') for f in d.rglob('*') if f.is_file()]
    if failure_files:
        for f in archive_exact(CACHE/'engineering_failures.tar.gz',failure_files,ROOT):retire(f)
        for d in OUT.glob('pilot_attempt_*'):shutil.rmtree(d)
    # Preserve complete transfer member inventories compactly, then drop copies.
    transfer_files=sorted(OUT.glob('*_transfer.json'))
    transfers={f.name:json.loads(f.read_text()) for f in transfer_files}
    encoded=json.dumps(transfers,separators=(',',':'))
    with gzip.open(CACHE/'transport_audits.json.gz','wt') as stream:stream.write(encoded)
    with gzip.open(CACHE/'transport_audits.json.gz','rt') as stream:assert stream.read()==encoded
    for f in transfer_files:retire(f)
    # Original selected arrays and four reports were independently read back on
    # worker scratch before compaction. Both merged arrays and original metadata
    # survive in the compact proof/evidence; successful verbose logs are retired.
    for f in OUT.glob('parent_*'):
        if re.match(r'^parent_\d+_',f.name):retire(f)
    for f in CACHE.glob('parent_*_selected.npz'):retire(f)
    for f in OUT.glob('production_results_*.json'):retire(f)
    for f in OUT.glob('production_[0-9]*_exitcode.txt'):retire(f)
    for f in OUT.glob('production_[0-9]*_time.txt'):retire(f)
    for f in CACHE.glob('*_result.tar.gz'):retire(f)
    retire(CACHE/'frame.json.gz')
    for f in OUT.glob('*_submission_[0-9]*.json'):
        record=json.loads(f.read_text());retire(ROOT/record['package']['path'])
    # Only this stage's terminal scheduler logs; other projects are untouched.
    spool=Path('/afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage131')
    logs=[f for f in (spool/'logs').glob('*') if f.is_file()]
    if logs:
        for f in archive_exact(CACHE/'scheduler_logs.tar.gz',logs,spool):
            removed_B+=f.stat().st_size;f.unlink()
    retained={str(directory.relative_to(ROOT)):sum(f.stat().st_size for f in directory.rglob('*') if f.is_file()) for directory in [CACHE,ROOT/'ml/artifacts/stage131']}
    report=dict(all_attempts_terminal=True,parents_verified=proof['parents'],removed_logical_duplicate_B=removed_B,retired_files=len(retired)+len(logs),retained_B=retained,retained_observer_runtime_B=(ROOT/'software/stage131/observer-runtime.tar.gz').stat().st_size,scope='logical deleted bytes,not measured physical EOS release; compact matched+extra arrays,original parent JSON/metadata,full GNU times,failed-attempt and scheduler/transport archives retained; no ROOT retained; array roundtrip measured in HTCondor analysis before removal',reconstruction='matched_input in frozen case order plus selected_extra per schema/mapping in compact_verification.json reconstruct all original selected NPZ arrays; parent_evidence retains per-parent counts,metadata JSON string and four reports; restore original frame from Stage130 new_input and frozen stage131_frame.py without redoing G4')
    (OUT/'cleanup.json').write_text(json.dumps(report,indent=2)+'\n');print(report)


if __name__=='__main__':main()
