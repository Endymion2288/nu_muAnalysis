"""Collect complete returned archives and report the frozen source denominator."""
import json
import fcntl

from stage130_collect import CACHE, OUT, collect


def main():
    if (OUT / 'cleanup.json').exists():
        print(json.loads((OUT / 'production_progress.json').read_text()), flush=True)
        print('Verified sources have been compacted; no transport is repeated.', flush=True)
        return
    contract = json.loads((OUT / 'production_contract.json').read_text())
    plan = json.loads((OUT / 'source_protocol.json').read_text())
    available = {int(p.name.split('_')[1].split('.')[0])
                 for p in CACHE.glob('production_*.tar.gz')}
    errors = []
    for index in sorted(available & set(contract['indices'])):
        if (CACHE / f'production_{index}/exitcode.txt').exists():
            continue
        try:
            collect('production', index, verbose=False)
        except Exception as error:
            # An archive being uploaded is deliberately not published as a
            # completed source by the transactional collector. Retry next poll.
            errors.append(dict(index=index, transport_error=str(error)))
    completed, failed, parents, selected, linked = [], [], 0, 0, 0
    for index in contract['all_source_indices']:
        phase = 'support' if index in contract['pilot_reused'] else 'production'
        directory = CACHE / f'{phase}_{index}'
        marker = directory / 'exitcode.txt'
        if not marker.exists():
            continue
        code = int(marker.read_text())
        if code:
            failed.append(dict(index=index, exit_code=code))
            continue
        qa = json.loads((directory / 'source_qa.json').read_text())
        if phase == 'production':
            identity = json.loads((directory / 'parentmap.json').read_text())
            assert identity['selected_N'] == identity['eventID_entry_incoming_exact_N'] == qa['selected_N'], index
            linked += identity['selected_N']
        else:
            linked += qa['selected_N']
        assert qa['schema_and_typed_domains_passed'] and qa['model_fits'] == qa['predictions'] == 0
        completed.append(index)
        parents += qa['parent_N']
        selected += qa['selected_N']
    result = dict(frozen_source_N=contract['source_N'], completed_source_N=len(completed),
        pending_source_N=contract['source_N']-len(completed)-len(failed), failed=failed,
        PHYS_parent_N=parents, selected_records_N=selected, selected_exact_parent_links_N=linked,
        transport_pending=errors, complete=len(completed) == contract['source_N'],
        scope='live partial support, not final new-training yield; known-exposure purge and role/hash split occur after all sources return')
    result['component_sources'] = {component: dict(
        frozen=sum(plan['sources'][i]['component'] == component for i in contract['all_source_indices']),
        completed=sum(plan['sources'][i]['component'] == component for i in completed))
        for component in ['pi', 'k', 'charm']}
    (OUT / 'production_progress.json').write_text(json.dumps(result, indent=2)+'\n')
    print(result, flush=True)


if __name__ == '__main__':
    with (CACHE / '.collector.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        main()
