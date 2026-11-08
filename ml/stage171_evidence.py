"""HTCondor-only independent scalar support evidence, no amplitude selection."""
import collections
import gzip
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage171_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage171'


def main():
    with gzip.open(CACHE/'pilot_rows.jsonl.gz','rt') as f:rows=[json.loads(line) for line in f]
    versions=collections.Counter();input_bits=collections.Counter();strict=[]
    for r in rows:
        for t in r['tlb']:
            versions[(str(t['header']),str(t.get('version')),str(t.get('valid')))]+=1
        if len(r['tlb'])==1 and r['tlb'][0].get('valid') and r['tlb'][0]['TAP']==16 and r['tlb'][0]['TBP']==16:
            strict.append(r);t=r['tlb'][0];input_bits[f"{t['input_bits']}/{t['input_bits_next']}"]+=1
    summary=json.loads((OUT/'pilot_summary.json').read_text())
    assert len(strict)==summary['strict_N']
    result=dict(physics_N=len(rows),strict_N=len(strict),TLB_header_version_valid_counts=[dict(header=a,version=b,valid=c,N=n) for (a,b,c),n in versions.items()],
        strict_input_bits_current_next=dict(input_bits),strict_status_counts=dict(collections.Counter(str(r['status']) for r in strict)),
        timestamp_span_s=(rows[-1]['timestamp_us']-rows[0]['timestamp_us'])/1e6,
        empirical_strict_event_fraction=len(strict)/len(rows),
        fraction_is_not_live_time_or_acceptance=True,pilot_feasible=summary['controls']['feasible'],
        passed=True,pure_noise_certified=False,calibrated_covariance=False,overall_complete=False)
    (OUT/'control_evidence.json').write_text(json.dumps(result,indent=2)+'\n');print(result)


if __name__=='__main__':main()
