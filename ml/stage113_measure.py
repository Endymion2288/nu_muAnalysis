"""Complete the unchanged six-source question under the original actual caps."""
import json
import multiprocessing as mp
import resource
import time
from pathlib import Path

import numpy as np

import stage112_audit as audit
import stage112_statistics as statistics

REPO = Path(__file__).resolve().parents[1]
OUT = REPO/'workbook/stage113_energy_ml'
ORIGINAL_NATIVE = audit.snapshot_native
RESERVES = {}


def reserved_native(a, source, phase):
    # Reserve a generous local-native read envelope before the subprocess.
    # Requests from other workers see this reservation in their pre-read cap.
    reserve = RESERVES[source['source']]
    with audit.REQUESTED.get_lock():
        if audit.REQUESTED.value+reserve > audit.MAX_BYTES:
            raise RuntimeError('Native input reservation cannot fit original aggregate cap')
        audit.REQUESTED.value += reserve
    try:
        flags, selected, flow, cost = ORIGINAL_NATIVE(a, source, phase)
        assert cost['requested_bytes'] <= reserve, 'Native read envelope exceeded'
        cost['pre_reserved_input_bytes'] = reserve
        return flags, selected, flow, cost
    finally:
        with audit.REQUESTED.get_lock():
            audit.REQUESTED.value -= reserve


def invalid_examples(data, sources):
    rows, counts = [], []
    for d, source in zip(data, sources):
        tests = []
        for j in range(2):
            key = f'VetoNu{j}_reduced_charge'
            value = d[key]
            tests.append((key, ~np.isfinite(value) | (value < 0), value < 30,
                          value, d[f'VetoNu{j}_status'], 'pC'))
        for key, threshold, upper in [('nLayers', 7, False), ('nDoF', 9, False),
                                      ('chi2ndf', 15, True), ('r_atMaxRadius', 95, True),
                                      ('rIFT', 95, True), ('rVetoNu', 120, True), ('theta', 25, True)]:
            tests.append((key, d['invalid_'+key], d[key] < threshold if upper else d[key] >= threshold,
                          d[key], np.full(len(d['E']), np.nan), 'mm' if key.startswith('r') else 'mrad' if key == 'theta' else 'dimensionless'))
        for name, invalid, passed, value, status, unit in tests:
            use = invalid & passed
            counts.append(dict(source=source['source'], column=name, full_parent_N=len(use),
                               invalid_native_cut_pass=int(use.sum()),
                               also_final_S50=int((use & d['S50']).sum()),
                               also_eligible_S50=int((use & d['S50'] & d['eligible']).sum())))
            for i in np.flatnonzero(use):
                if len(rows) >= 40:
                    break
                rows.append(dict(source=source['source'], input_entry=int(d['input_entry'][i]),
                                 run=int(d['run'][i]), eventID=int(d['eventID'][i]), column=name,
                                 value=value[i], units=unit, status=status[i], S50=bool(d['S50'][i]),
                                 eligible=bool(d['eligible'][i]), known_priority=int(d['known_priority'][i]),
                                 reason='original typed domain invalid; native upper/lower comparison passes; no selection repair'))
    statistics.table('invalid_native_pass_counts.tsv', counts)
    statistics.table('invalid_native_pass_examples.tsv', rows)


def main():
    global RESERVES
    OUT.mkdir(parents=True, exist_ok=True)
    audit.OUT = statistics.OUT = OUT
    wall, cpu = time.perf_counter(), time.process_time()
    protocol = json.loads((OUT/'protocol.json').read_text())
    qa = json.loads((REPO/'workbook/stage112_energy_ml/QA.json').read_text())
    manifest = json.loads((REPO/'workbook/stage111_energy_ml/source_manifest.json').read_text())
    sources = manifest['files']
    assert qa['passed'] and qa['real_entries'] == 36
    assert [q['source'] for q in qa['sources']] == [s['source'] for s in sources]
    for s in sources:
        assert Path(s['input']).stat().st_size == s['logical_bytes_at_design']
    RESERVES = {q['source']: 16*q['selected_compressed_bytes']+16*1024**2 for q in qa['sources']}
    audit.snapshot_native = reserved_native
    ctx = mp.get_context('fork')
    prior = protocol['execution_contract']['limits_including_stage112']['already_requested_bytes_upper_bound']
    audit.REQUESTED = ctx.Value('q', prior)
    with ctx.Pool(6) as pool:
        results = pool.map(audit.work, [(s, 'full113', None) for s in sources])
    data, costs = [d for d, q in results], [q for d, q in results]
    assert sum(len(d['E']) for d in data) == 60000
    audit.save('source_audit.json', costs)
    identities = audit.identities(data, sources)
    audit.save('identity_audit.json', dict(passed=True, sources=identities, read_fields=audit.allowed_fields(),
                                         no_test_only_sources_features_predictions_or_risks=True))
    invalid_examples(data, sources)
    result = statistics.report(data, sources, costs)
    resources = dict(self_CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-wall,
                     child_native_and_worker_CPU_s=sum(q['worker_self_CPU_s']+q['native']['native_CPU_s'] for q in costs),
                     interface_requested_bytes_including_prior_bound=audit.REQUESTED.value,
                     prior_interface_upper_bound_bytes=prior,
                     new_interface_requested_bytes=audit.REQUESTED.value-prior,
                     source_requested_bytes=sum(q['requested_source_bytes'] for q in costs),
                     source_underlying_read_bytes=sum(q['underlying_source_read_bytes'] for q in costs),
                     native_local_requested_bytes=sum(q['native']['requested_bytes'] for q in costs),
                     native_local_returned_bytes=sum(q['native']['returned_bytes'] for q in costs),
                     parent_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                     note='GNU supervisor external total authoritative; internal nested costs are diagnostics, do not add twice',
                     physical_network_bytes='unmeasured', entire_process_tree_peak_memory='unmeasured',
                     single_core_speedup='unmeasured', GPU=0)
    audit.save('resources.json', resources)
    audit.save('complete.json', dict(status='measurement_complete', source_count=6, parent_entries=60000,
                                    original_QA_repeated=False, new_fits=0, new_forwards=0,
                                    original_science_selection_roles_and_weights_preserved=True,
                                    outcome=result, promotion=False))
    print(json.dumps(audit.plain(dict(outcome=result, resources=resources)), indent=2), flush=True)


if __name__ == '__main__':
    import traceback
    try:
        main()
    except Exception as error:
        OUT.mkdir(parents=True, exist_ok=True)
        audit.OUT = OUT
        audit.save('failure.json', dict(error=repr(error), traceback=traceback.format_exc(),
                                       requested_byte_counter=audit.REQUESTED.value if audit.REQUESTED else None,
                                       new_fits=0, physics_conclusions='not certified'))
        raise
