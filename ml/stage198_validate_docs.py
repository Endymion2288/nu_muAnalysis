"""Check a research synthesis against existing scalar products; no event I/O."""
import csv
import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'workbook/2026-11-09_stage198_electronic-observables-results-synthesis.md'
OUT = ROOT / 'workbook/stage198_energy_ml/document_validation.json'
BASE = '7e80d7e'


def read_json(name):
    return json.loads((ROOT / name).read_text())


def main():
    wall, cpu = time.perf_counter(), time.process_time()
    text = REPORT.read_text()
    citations = []
    for stage, table, candidate, reference in [
        (186, 'energy_paired.tsv', 'I', 'R'),
        (189, 'composition_paired.tsv', 'C', 'X'),
        (191, 'ift_paired.tsv', 'C', 'X'),
    ]:
        source = f'workbook/stage{stage}_energy_ml/{table}'
        with (ROOT / source).open() as stream:
            rows = list(csv.DictReader(stream, delimiter='\t'))
        for stratum in ['E50_100', 'E100_200']:
            selected = [r for r in rows if r['role'] == '3'
                        and r['stratum'] == stratum
                        and r['candidate'] == candidate and r['reference'] == reference]
            assert len(selected) == 1, (source, stratum)
            r = selected[0]
            quote = '{:.9f} [{:.9f}, {:.9f}]'.format(
                *[float(r[k]) for k in ['RMSE_ratio', 'low95', 'high95']])
            assert quote in text, quote
            assert r['N'] == ('183' if stratum == 'E50_100' else '856')
            citations.append(dict(source=source, role=3, stratum=stratum,
                                  candidate=candidate, reference=reference, quote=quote))
    for stage in [189, 191]:
        decision = read_json(f'workbook/stage{stage}_energy_ml/content_decision.json')
        assert decision['fixed_package_ended'] and not decision['promotion']
        assert not decision['expand'] and not decision['overall_complete']
    shape = read_json('workbook/stage196_energy_ml/full_summary.json')
    assert shape['real_parent_N'] == 64 and shape['raw_support']['all_records'] == 1536
    assert shape['raw_support']['supported'] == 727 and shape['template_channel_N'] == 16
    assert shape['MC_ideal_closure']['ideal_samples_N'] == 55200
    assert shape['MC_ideal_closure']['max_abs_difference_ADC'] == 0
    assert not shape['physical_source_identified'] and shape['energy_fits'] == 0
    for group in ['Trigger', 'Veto', 'VetoNu']:
        row, = [g for g in shape['groups']
                if (g['kind'], g['group'], g['subset']) == ('data', group, 'last32')]
        assert f"{row['standardized_RMS_median']:.9f}" in text
    pilot = read_json('workbook/stage197_energy_ml/independent_validation.json')
    assert pilot['actual_processed_records_N'] == 8192
    assert pilot['unknown_final_selection_N'] == 2647
    assert pilot['pre_veto_pz50_100_N'] == 351
    assert not pilot['final_candidate_yield_measured'] and pilot['MC_read_N'] == 0
    assert not read_json('workbook/stage197_energy_ml/admission.json')['admitted']
    user = read_json('workbook/stage197_energy_ml/input_status.json')
    assert user['status'] == 'deferred_by_user_pending_future_input'
    assert not user['whole_goal_paused'] and not user['overall_complete']
    with (ROOT / 'workbook/stage140_energy_ml/coverage_summary.tsv').open() as stream:
        nominal = [r for r in csv.DictReader(stream, delimiter='\t')
                   if r['scenario'] == 'nominal_empirical']
    assert len(nominal) == 3
    for r in nominal:
        assert f"{float(r['Asimov_width95_pp']):.6f}" in text
        assert r['covered'] in text
    links = 0
    for target in re.findall(r'\]\(([^)]+)\)', text):
        if target.startswith(('https:', 'http:', '#')):
            continue
        p = REPORT.parent / target.split('#')[0]
        assert p == OUT or p.exists(), target
        links += 1
    assert text.count('```') % 2 == 0
    for name in ['docs/nu_mu_energy_ml_revised_roadmap.md',
                 'docs/nu_mu_energy_ml_next_step_prompt.md']:
        historical = subprocess.check_output(['git', 'show', f'{BASE}:{name}'], cwd=ROOT)
        current = (ROOT / name).read_bytes()
        assert current.endswith(historical)
        assert current.startswith('# 当前研究综合：Stage198'.encode())
    snapshot = read_json('workbook/stage158_energy_ml/preexisting_asset_snapshot.json')
    for name, expected in snapshot.items():
        actual = (ROOT / name).stat()
        assert actual.st_size == expected['bytes'] and actual.st_mtime_ns == expected['mtime_ns']
    subprocess.run(['git', 'diff', '--check'], cwd=ROOT, check=True)
    subprocess.run(['git', 'diff', '--cached', '--check'], cwd=ROOT, check=True)
    result = dict(passed=True, scope='Existing scalar/text citation validation only; no new experiment',
                  starting_commit=BASE, energy_table_citations=citations,
                  historical_suffix_preserved=True, local_links_N=links,
                  Stage54_size_mtime_preserved_N=len(snapshot),
                  physical_source_and_final_yield_unmeasured=True,
                  user_deferral_preserved=True, new_scientific_CPU_s=0,
                  new_jobs_N=0, new_energy_fits_N=0, overall_complete=False,
                  document_validation_process_CPU_s=time.process_time() - cpu,
                  document_validation_wall_s=time.perf_counter() - wall)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'energy_table_citations'},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
