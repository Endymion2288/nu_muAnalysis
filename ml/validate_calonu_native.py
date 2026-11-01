#!/usr/bin/env python3
"""Validate retained event identities, measured tables, syntax and report links."""
import ast
import csv
import json
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np


def main():
    tick = time.perf_counter()
    repo = Path(__file__).resolve().parents[1]
    out = repo/'workbook/stage37_energy_ml'
    with np.load(repo/'ntuples/energy_ml_stage37/native_response.npz') as z:
        d = {k: z[k] for k in z.files}
    cases = json.loads(str(d['cases_json']))
    lineage = json.loads(str(d['lineage_json']))
    assert len(cases) == len(lineage) == 128
    assert len({(r['group'], r['input_entry']) for r in cases}) == 128
    assert sum(r['role'] == 'regular' for r in cases) == 96
    assert d['adc'].shape == (128, 4, 600)
    assert d['saved_wave'].shape == (128, 4, 76)
    for r, link in zip(cases, lineage):
        assert r['input_entry'] == link['input_entry']
        assert link['hits_entry'] == link['input_entry'] % 10000
        assert link['hits_subfile_ordinal'] == link['input_entry']//10000
        # The first two successful jobs required the entire signature (including mass) to be equal.
        assert link.get('hits_RDO_beam_momentum_equal') or link.get('hits_RDO_beam_equal')
    for g in [0, 5, 6, 11]:
        r = [r for r in cases if r['group'] == g and r['role'] == 'regular']
        assert len(r) == 24 and sum(x['reco_p_GeV'] < 250 for x in r) == 12
    raw = np.maximum(d['saved_wave'], 0).sum(axis=2)*2/50
    np.testing.assert_allclose(raw, d['raw_integral']/50, rtol=0, atol=3e-5)
    waveform = np.take_along_axis(d['adc'], (d['saved_time']/2).astype(int), axis=2)
    waveform = (d['baseline_mean'][:, :, None]-waveform*(2/16.384)).astype(np.float32)
    np.testing.assert_array_equal(waveform, d['saved_wave'])
    expected_rows = {'native_case_response.tsv': 128, 'native_module_response.tsv': 512,
                     'native_metrics.tsv': 80, 'nonfinite_integral_diagnosis.tsv': 8,
                     'wavefit_replay.tsv': 8, 'paired_signal_residual.tsv': 3,
                     'calibration_constant_checks.tsv': 20, 'condor_resources.tsv': 6}
    tables = {}
    for name, n in expected_rows.items():
        rows = list(csv.DictReader((out/name).open(), delimiter='\t'))
        assert len(rows) == n, (name, len(rows), n)
        tables[name] = rows
    for j, row in enumerate(tables['native_case_response.tsv']):
        assert int(row['input_entry']) == cases[j]['input_entry']
        np.testing.assert_allclose(float(row['raw_total_pC']), (d['raw_integral'][j]/50).sum(), rtol=1e-13)
    replay = tables['wavefit_replay.tsv']
    assert sum(not np.isfinite(float(r['saved_integral_mVns'])) for r in replay) == 4
    assert all(r['saved_status'] == r['replay_status'] for r in replay)
    assert all(not np.isfinite(float(r['replay_integral_mVns'])) for r in replay[:4])
    assert all(r['CB_valid'] == '1' and r['CB_fit_status'] == '0' for r in replay[:4])
    assert all(float(r['stable_integral_pC']) > 0 and r['analytic_A_overflows'] == 'True'
               for r in tables['nonfinite_integral_diagnosis.tsv'])
    calib = tables['calibration_constant_checks.tsv']
    assert sum(int(r['N']) for r in calib) == 2040682
    assert sum(int(r['subnormal_float32_pairs']) for r in calib) == 10
    assert all(r['forward_relation_passed'] == 'True' for r in calib)
    scripts = sorted(repo.glob('ml/*calonu_native*.py'))+[repo/'ml/replay_calonu_wavefit.py']
    for path in scripts:
        ast.parse(path.read_text(), filename=str(path))
    subprocess.run(['bash', '-n', str(repo/'AnalysisZipFramework/submission/run_ml_calonu_native.sh')], check=True)
    documents = [repo/'docs/nu_mu_energy_ml_revised_roadmap.md', repo/'docs/nu_mu_energy_ml_next_step_prompt.md',
                 repo/'workbook/2026-11-01_stage37_calonu-native-response.md', out/'source_audit.md',
                 out/'preregistered_protocol.md', repo/'workbook/2026-11-01_stage36_calonu-muon-response.md',
                 repo/'workbook/stage36_energy_ml/source_audit.md', repo/'workbook/stage35_energy_ml/source_audit.md']
    links = 0
    for path in documents:
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text()):
            if '://' not in target and not target.startswith('#'):
                resolved = path.parent/target.split('#')[0]
                assert resolved.exists() or resolved.resolve() == (out/'final_validation.json').resolve(), (path, target)
                links += 1
    archive = json.loads((out/'archive.json').read_text())
    assert archive['retained_bytes'] == 649006 and archive['all_field_readback_equal']
    assert all(not (repo/r['path']).exists() for r in archive['removed'])
    ET.parse(out/'native_response.svg')
    result = dict(events=128, regular=96, diagnostic=32, all_retained_fields_loaded=True,
                  unique_actual_input_entries=True, source_identity_and_subfile_order=True,
                  ADC_waveform_exact=True, raw_integral_tolerance_passed=True,
                  actual_table_rows=expected_rows, four_nonfinite_source_replays_confirmed=True,
                  eight_saved_parameter_overflows_confirmed=True, calibration_forward_relation_confirmed=True,
                  Python_AST_files=len(scripts), bash_syntax_passed=True, checked_local_links=links,
                  SVG_XML_valid=True,
                  final_cache_bytes=649006, archive_checked=True, wall_s=time.perf_counter()-tick)
    (out/'final_validation.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
