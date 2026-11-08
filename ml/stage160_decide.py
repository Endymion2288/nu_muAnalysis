"""Frozen locator, complete-event cost admission and independent entry audit."""
import gzip
import json
import sys
from pathlib import Path
from stage158_finalize import gnu

OUT=Path('workbook/stage160_energy_ml');CACHE=Path('ntuples/energy_ml_stage160')
KEYS=['entry','run','event','timestamp','lumi_block']


def read(name):return json.loads((OUT/name).read_text())
def write(name,data):(OUT/name).write_text(json.dumps(data,indent=2)+'\n')
def payload(phase):
    with gzip.open(CACHE/f'{phase}.json.gz','rt') as stream:return json.load(stream)
def same(a,b):return all(a[k]==b[k] for k in KEYS)


def main():
    phase=sys.argv[1];targets=read('targets.json')['records']
    assert len(targets)==64
    if phase=='headers':
        headers=read('headers_summary.json');records=payload('headers')['records']
        with gzip.open('ntuples/energy_ml_stage159/paired_records.json.gz','rt') as stream:reference=json.load(stream)['records'][:4]
        actual=[r for r in records if r['source_index']==0]
        assert len(actual)==4 and all(same(a,b) for a,b in zip(actual,reference))
        candidates=[]
        for source in headers['metadata']:
            if source['source_index']==0 or not source['supported']:continue
            ends=[r for r in records if r['source_index']==source['source_index']]
            assert len(ends)==2
            first,last=ends
            qualified=all(first['run']==r['run']==last['run'] and first['event']<=r['event']<=last['event']
                          and first['timestamp']<=r['timestamp']<=last['timestamp'] for r in targets)
            candidates.append(dict(source=source,first=first,last=last,qualified=qualified))
        qualified=[r for r in candidates if r['qualified']]
        locator=dict(passed=True,reference4_exact=True,qualified_N=len(qualified),continue_to_pilot=len(qualified)==1,
            source=qualified[0]['source'] if len(qualified)==1 else None,candidates=candidates,
            endpoint_scope='A bounded locator, not a certificate of interior monotonicity or excluded-source absence')
        write('locator.json',locator)
        write('summary.json',dict(passed=True,phase='headers',terminal_experiment=len(qualified)!=1,
            reference4_exact=True,qualified_N=len(qualified),promotion=False,overall_complete=False))
    elif phase=='admission':
        pilot=read('pilot_summary.json');source=read('locator.json')['source'];prefix=payload('pilot')['prefix']
        first=next(r['first'] for r in read('locator.json')['candidates'] if r['source']['REC']==source['REC'])
        assert same(prefix[0],first) and pilot['N']==min(1024,source['N'])
        measured=gnu(OUT/'pilot_time.txt');steady=pilot['steady_complete_interval_mean_CPU_s']
        assert steady is not None and steady>=0
        base=measured['CPU_s']-pilot['steady_complete_interval_CPU_s'];assert base>=0
        projected=3*(base+source['N']*steady)
        used=read('scheduler_accounting.json')['total_CPU_s']
        admitted=bool(used+200+projected<=2000)
        admission=dict(passed=True,admitted=admitted,measured_complete_event_interval_CPU_s=steady,
            startup_first_last_and_unscaled_CPU_s=base,actual_source_N=source['N'],projected_full_3x_CPU_s=projected,
            already_used_scheduler_CPU_s=used,audit_reserve_CPU_s=200,CPU_budget_s=2000,
            first_identity_exact=True,cost_amendment='execution_cost_amendment.json')
        write('admission.json',admission)
        write('summary.json',dict(passed=True,phase='pilot',terminal_experiment=not admitted,admitted=admitted,
            promotion=False,overall_complete=False))
    elif phase=='full':
        full=read('full_summary.json');pilot=payload('pilot')['prefix'];current=payload('full')
        assert current['prefix']==pilot
        assert full['N']==read('locator.json')['source']['N']
        by_key={(r['run'],r['event']):r['native_matches'] for r in current['target_matches']}
        records=[]
        for target in targets:
            matches=by_key[(target['run'],target['event'])]
            unique=len(matches)==1 and target['PHYS_key_multiplicity']==1
            record=dict(target,native_matches_N=len(matches),unique_pair=unique,
                native_entry=matches[0]['entry'] if unique else None,
                native_timestamp=matches[0]['timestamp'] if unique else None,
                timestamp_equal=bool(unique and matches[0]['timestamp']==target['timestamp']))
            records.append(record)
        manifest=dict(REC=read('locator.json')['source']['REC'],PHYS=read('protocol.json')['PHYS'],
            native_N=full['N'],metadata=full['metadata'][0]['metadata'],records=records,
            parent_scope='Exactly original first64 named PHYS entries; no quality/charge selection',
            limitation='Unique within the scanned native source and full named PHYS index; no globally independent-source certificate')
        write('matched_manifest.json',manifest)
        write('summary.json',dict(passed=True,phase='full',terminal_experiment=False,full_prefix_exact=True,
            target_N=64,unique_pair_N=sum(r['unique_pair'] for r in records),native_N=full['N'],
            timestamp_equal_N=sum(r['timestamp_equal'] for r in records),promotion=False,overall_complete=False))
    elif phase=='need_audit':
        raise SystemExit(0 if any(r['unique_pair'] for r in read('matched_manifest.json')['records']) else 1)
    elif phase=='audit':
        manifest=read('matched_manifest.json');unique=[r for r in manifest['records'] if r['unique_pair']]
        expected={r['native_entry']:r for r in unique}
        actual=payload('audit')['records'] if unique else []
        assert len(actual)==len(expected)
        for record in actual:
            target=expected[record['entry']]
            assert all(record[k]==target[k] for k in ['run','event'])
            assert record['timestamp']==target['native_timestamp']
        summary=read('summary.json');summary.update(phase='audited_full',terminal_experiment=True,
            independent_native_entry_read_N=len(actual),independent_entry_identity_exact=True,
            data_muon_purity='unmeasured',native_state_raw_equivalence='unmeasured',new_G4=0,energy_fits=0,
            natural_nu_forward=0,reserved_forward=0)
        write('summary.json',summary)
        write('independent_validation.json',dict(passed=True,reloaded_native_entry_N=len(actual),
            exact_run_event_timestamp=True,pilot_full_prefix_N=len(payload('pilot')['prefix']),
            no_parent_substitution=True,source_scope=manifest['REC']))
    else:raise ValueError(phase)
    print(phase,read('summary.json'),flush=True)


if __name__=='__main__':main()
