#!/usr/bin/env python3
"""Verify retained measurements and distinguish source-function tests from production repair."""
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

repo=Path(__file__).resolve().parents[1];out=repo/'workbook/stage40_energy_ml';tick,cpu=time.perf_counter(),time.process_time()
cfg=json.loads((repo/'ml/configs/calonu_response.json').read_text());summary=json.loads((out/'summary.json').read_text())
path=repo/'ntuples/energy_ml_stage40/response.npz'
with np.load(path) as saved:d={k:saved[k] for k in saved.files}
cases=json.loads(str(d['cases_json']));common=d['common_waveform'];regular=np.array([c['role']=='regular' for c in cases]);mask=common&regular
assert len(cases)==181 and regular.sum()==133
assert len({(c['index'],c['input_entry']) for c in cases})==181
assert set(cfg['indices']).isdisjoint(json.loads((repo/'ml/configs/calonu_cc_waveform.json').read_text())['indices'])
for index in cfg['indices']:
    expected=json.loads((out/f'request_{index}.json').read_text())['cases'];actual=[c for c in cases if c['index']==index]
    assert len(actual)==len(expected)
    assert all(all(c[k]==v for k,v in e.items()) for e,c in zip(expected,actual))
assert all(c['hits_RDO_beam_momentum_equal'] and c['beam_barcode_generated_mass_equal'] and c['beam_mass_shell_max_bound_ratio']<1 for c in cases)
np.testing.assert_array_equal(~common,d['hit_count'].sum(1)==0)
np.testing.assert_array_equal(common,d['channel_present'].all(1))
samples=(d['saved_time'][common]/2).astype(int)
wave=(d['baseline_mean'][common,:,None]-np.take_along_axis(d['adc'][common],samples,axis=2)*(2/16.384)).astype(np.float32)
np.testing.assert_array_equal(wave,d['saved_wave'][common])
np.testing.assert_allclose(np.maximum(wave,0).sum(axis=2,dtype=float)*2/50,d['raw_integral'][common]/50,rtol=0,atol=3e-5)
for name in ['bounded_time','fixed','signed']:
    err=d['readout_'+name][mask]-d['nominal_window_charge_pC'][mask]
    row=summary['regular_primary' if name=='bounded_time' else 'regular_'+name]
    np.testing.assert_allclose([np.sqrt(np.mean(err**2)),err.mean()],[row['rmse_pC'],row['bias_pC']],rtol=1e-12,atol=1e-14)
cache_rows=np.array([c['cache_row'] for c in cases])
fit_max_difference=0.
with np.load(repo/'ntuples/energy_ml_stage35/fit.npz') as old:
    for channel in range(4):
        present=d['channel_present'][:,channel]
        observed=d['integral'][present,channel]/50
        reference=old[f'CaloNu{channel}_charge'][cache_rows[present]]
        np.testing.assert_allclose(observed,reference,rtol=3e-6,atol=3e-5,equal_nan=True)
        fit_max_difference=max(fit_max_difference,float(abs(observed-reference).max()))
for key,value in d.items():
    if key.startswith(('readout_','model_readout_','offpulse_','time_shift_')) or key=='nominal_window_charge_pC':assert np.isnan(value[~common]).all()
noise=json.loads((out/'source_noise.json').read_text());assert noise['source_noise_gate'] and noise['zero_histogram_channel_mismatches']==0
assert noise['events']==2048 and noise['zero_histogram_pairs']==256
with np.load(repo/'ntuples/energy_ml_stage40/source_noise.npz') as saved:
    for key in saved.files:
        v=saved[key];np.testing.assert_allclose([v.mean(),np.sqrt(np.mean(v**2))],[noise['readouts'][key]['bias_pC'],noise['readouts'][key]['RMS_pC']],rtol=1e-12,atol=1e-14)
archive=json.loads((out/'archive.json').read_text());assert archive['native_all_fields_rejoined_equal'] and archive['metadata_and_schema_preserved']
assert archive['final_cache_bytes']==path.stat().st_size
assert all(not (repo/r['path']).exists() for r in archive['removed'])
resources=json.loads((out/'condor_summary.json').read_text());assert resources['jobs']==3<=cfg['max_condor_jobs'] and resources['failures']==0
scripts=sorted(set([*repo.glob('ml/*calonu_response*.py'),*repo.glob('ml/*calonu_noise*.py'),repo/'ml/build_calonu_empty_noise.py',repo/'ml/calonu_timed_readout.py']))
for p in scripts:ast.parse(p.read_text(),filename=str(p))
subprocess.run(['bash','-n',str(repo/'AnalysisZipFramework/submission/run_ml_calonu_response.sh')],check=True)
rows={}
for p in out.rglob('*.tsv'):
    with p.open() as handle:contents=list(csv.reader(handle,delimiter='\t'))
    assert contents and all(len(row)==len(contents[0]) for row in contents[1:]),p
    rows[str(p.relative_to(out))]=len(contents)-1
assert rows['events.tsv']==181 and rows['condor_resources.tsv']==3
json_paths=list(out.rglob('*.json'))+[repo/'ml/configs/calonu_response.json']
for p in json_paths:json.loads(p.read_text())
links=0
for p in [repo/'docs/nu_mu_energy_ml_revised_roadmap.md',repo/'docs/nu_mu_energy_ml_next_step_prompt.md',repo/'workbook/2026-11-01_stage40_calonu-full-response.md',out/'preregistered_protocol.md']:
    for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',p.read_text()):
        if '://' not in target and not target.startswith('#'):
            assert (p.parent/target.split('#')[0]).exists(),(p,target);links+=1
ET.parse(out/'response_controls.svg')
subprocess.run(['git','check-ignore','-q',str(path.relative_to(repo))],cwd=repo,check=True)
record=dict(events=181,regular=133,diagnostic=48,common=int(common.sum()),regular_common=int(mask.sum()),
            frozen_support_and_identity=True,ADC_waveform_and_raw_checked=True,summary_metrics_recomputed=True,
            present_fit_charge_cache_checked=True,fit_charge_max_difference_pC=fit_max_difference,
            source_noise_metrics_recomputed=True,archive_checked=True,Python_AST_files=len(scripts),bash_syntax=True,
            JSON_files=len(json_paths),TSV_rows=rows,local_links=links,SVG_XML=True,cache_ignored=True,
            source_function_fixture_only=True,full_Athena_production_repair='not measured',neutrino_energy_gain='not measured',
            wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
(out/'final_validation.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
