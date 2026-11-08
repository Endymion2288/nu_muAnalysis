"""Finish missing audit metadata using already-read exact replay, without another RAW read."""
import gzip
import json
from stage171_evidence import main as evidence
from stage171_run import OUT,CACHE,write

assert json.loads((OUT/'independent_validation.json').read_text())['passed']
evidence()
with gzip.open(CACHE/'pilot_rows.jsonl.gz','rt') as f:rows=[json.loads(line) for line in f]
with gzip.open(CACHE/'audit_rows.jsonl.gz','rt') as f:other=[json.loads(line) for line in f]
assert other==rows
rejoin={}
for phase in ['smoke','smoke_retry']:
    with gzip.open(CACHE/f'{phase}_rows.jsonl.gz','rt') as f:other=[json.loads(line) for line in f]
    assert other==rows[:56]
    rejoin[f'{phase}_rows.jsonl.gz']=dict(rows=56,exact_prefix=True)
rejoin['audit_rows.jsonl.gz']=dict(rows=len(rows),exact_full=True)
write('storage_rejoin.json',dict(passed=True,canonical='pilot_rows.jsonl.gz',rejoin=rejoin,all_hardware_ADC_and_metadata_equal=True))
write('audit_completion.json',dict(passed=True,earlier_worker_exit=1,
    issue='Missing pilot_summary.json in audit transfer, after successful exact second RAW replay.',
    correction='Finish scalar evidence and rejoin from frozen already-read pilot/audit rows. No additional RAW read.',
    independent_replay_passed=True,control_feasible=True,new_RAW_reads=0,overall_complete=False))
