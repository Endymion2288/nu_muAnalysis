#!/usr/bin/env python3
"""Check retained CC measurements, archive, source evidence and review artifacts."""
import ast
import csv
import json
import re
import resource
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np


def main():
    tick, cpu = time.perf_counter(), time.process_time()
    repo = Path(__file__).resolve().parents[1]
    out = repo / 'workbook/stage39_energy_ml'
    cfg = json.loads((repo / 'ml/configs/calonu_cc_waveform.json').read_text())
    cache = repo / 'ntuples/energy_ml_stage39/cc_waveform.npz'
    with np.load(cache) as saved:
        d = {k: saved[k] for k in saved.files}
    cases = json.loads(str(d['cases_json']))
    common = d['common_waveform']
    regular = np.array([c['role'] == 'regular' for c in cases])
    assert len(cases) == 190 and regular.sum() == 142
    assert common.sum() == 147 and (regular & common).sum() == 112
    np.testing.assert_array_equal(common, d['channel_present'].all(axis=1))
    np.testing.assert_array_equal(~common, d['hit_count'].sum(axis=1) == 0)
    assert all(c['vertex_z_mm'] >= -2605.68 for c, missing in zip(cases, regular & ~common) if missing)
    for index in cfg['indices']:
        wanted = json.loads((out / f'request_{index}.json').read_text())['cases']
        actual = [c for c in cases if c['index'] == index]
        assert len(wanted) == len(actual)
        assert all(all(c[k] == value for k, value in w.items()) for w, c in zip(wanted, actual))
    assert all(c['hits_RDO_beam_momentum_equal'] and c['beam_barcode_generated_mass_equal'] for c in cases)
    assert max(c['beam_mass_shell_max_bound_ratio'] for c in cases) < 1
    samples = (d['saved_time'][common] / 2).astype(int)
    wave = (d['baseline_mean'][common, :, None]
            - np.take_along_axis(d['adc'][common], samples, axis=2) * (2/16.384)).astype(np.float32)
    np.testing.assert_array_equal(wave, d['saved_wave'][common])
    np.testing.assert_allclose(np.maximum(wave, 0).sum(axis=2, dtype=float)*2/50,
                               d['raw_integral'][common]/50, rtol=0, atol=3e-5)
    for key, value in d.items():
        if key.startswith('readout_') or key == 'nominal_window_charge_pC':
            assert np.isnan(value[~common]).all() and np.isfinite(value[common]).all()
    rows = {}
    for path in sorted(out.glob('*.tsv')):
        with path.open() as handle:
            contents = list(csv.reader(handle, delimiter='\t'))
        assert contents and all(len(r) == len(contents[0]) for r in contents[1:]), path
        rows[path.name] = len(contents)-1
    assert rows['events.tsv'] == 190 and rows['condor_resources.tsv'] == cfg['max_condor_jobs'] == 8
    assert rows['lineage_inventory.tsv'] == 124 and rows['production_reference.tsv'] == 6
    with (out / 'high_signal_timing.tsv').open() as handle:
        early = next(r for r in csv.DictReader(handle, delimiter='\t')
                     if r['subset'] == 'regular' and r['method'] == 'template_time_-2ns')
    assert int(early['N']) == 17
    assert round(float(early['fraction_abs_error_gt5pct'])*17) == 14
    assert round(float(early['fraction_abs_change_gt5pct'])*17) == 12
    source = json.loads((out / 'source_audit.json').read_text())
    assert source['empty_hit_collection_records_empty_RDO_and_returns_before_noise']
    assert source['ntuple_absent_channel_default_status'] == 1
    assert source['digitization_payload_IOV_covers_CC_runs']
    archive = json.loads((out / 'archive.json').read_text())
    assert archive['final_bytes'] == cache.stat().st_size == 1244048
    assert archive['native_all_fields_rejoined_equal'] and archive['metadata_and_schema_preserved']
    assert all(not (repo / r['path']).exists() for r in archive['removed'])
    scripts = sorted(repo.glob('ml/*calonu_cc*.py')) + [repo / 'ml/locate_calonu_native.py',
              repo / 'ml/read_calonu_native.py', repo / 'ml/probe_calonu_beam_mass.py']
    for path in scripts:
        ast.parse(path.read_text(), filename=str(path))
    subprocess.run(['bash', '-n', str(repo / 'AnalysisZipFramework/submission/run_ml_calonu_cc_waveform.sh')], check=True)
    json_paths = sorted(out.glob('*.json')) + [repo / 'ml/configs/calonu_cc_waveform.json']
    for path in json_paths:
        json.loads(path.read_text())
    documents = [repo / 'docs/nu_mu_energy_ml_revised_roadmap.md',
                 repo / 'docs/nu_mu_energy_ml_next_step_prompt.md',
                 repo / 'workbook/2026-11-01_stage39_calonu-cc-waveform.md', out / 'preregistered_protocol.md']
    links = 0
    for path in documents:
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text()):
            if '://' not in target and not target.startswith('#'):
                assert (path.parent / target.split('#')[0]).exists(), (path, target)
                links += 1
    ET.parse(out / 'cc_waveform.svg')
    subprocess.run(['git', 'check-ignore', '-q', str(cache.relative_to(repo))], cwd=repo, check=True)
    result = dict(events=190, regular=142, diagnostic=48, common_waveform=147, regular_common=112,
                  frozen_support_and_identity_passed=True, empty_HITS_and_missing_masks_equal=True,
                  missing_readouts_remain_NaN=True, ADC_waveform_exact=True, raw_integral_checked=True,
                  high_signal_time_error_exceeds_gate=True, source_mechanism_checked=True,
                  archive_checked=True, Python_AST_files=len(scripts), bash_syntax_passed=True,
                  JSON_files=len(json_paths), TSV_rows=rows, checked_local_links=links,
                  SVG_XML_valid=True, final_cache_ignored=True,
                  neutrino_energy_gain='not measured', data_MC_physics_closure='not measured',
                  wall_s=time.perf_counter()-tick, cpu_s=time.process_time()-cpu,
                  peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (out / 'final_validation.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
