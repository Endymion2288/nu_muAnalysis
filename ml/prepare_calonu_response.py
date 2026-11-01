#!/usr/bin/env python3
"""Freeze source-isolated CC timing confirmation; source controls remain distinct synthetic tests."""
import csv
import json
import resource
import time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from calonu_inputs import manifest

repo = Path(__file__).resolve().parents[1]
out = repo/'workbook/stage40_energy_ml'
path = repo/'ml/configs/calonu_response.json'
assert not path.exists(), 'Already frozen'
tick, cpu = time.perf_counter(), time.process_time()
assert json.loads((out/'development/summary.json').read_text())['selected_method']=='bounded_time'
rows = manifest(repo)
extracted = {int(r['index']):r for r in csv.DictReader((repo/'workbook/stage35_energy_ml/extraction_files.tsv').open(),delimiter='\t')}
old = json.loads((repo/'ml/configs/calonu_cc_waveform.json').read_text())
indices = []
for component in ['pi','k','charm']:
    eligible = [int(r['index']) for r in rows if r['component']==component and r['partition']=='fit'
                and extracted[int(r['index'])]['input_events']=='10000']
    indices.extend([eligible[2], eligible[-2]])
assert set(indices).isdisjoint(old['indices'])
cfg = dict(stage=40, starting_commit='7485e05', frozen_utc=datetime.now(timezone.utc).isoformat(),
           indices=indices, source_commit='1ec47efe', max_events=192, max_condor_jobs=10,
           new_ML_fits=0, new_G4_events=0, primary_readout='bounded_time', reference_readout='template_plus_constant',
           bound_ns=4., step_ns=.25, center_controls_ns=[-2.,0.,2.], high_signal_threshold_pC=1.,
           bootstrap_replicates=1000, bootstrap_seed=20261107, template_parameters=old['template_parameters'],
           source_noise_events=2048, source_zero_hist_pairs=256, source_noise_seed=20261107,
           gates=dict(high_signal_model_max_abs_error=.05, high_signal_model_max_abs_center_change=.05,
                      offpulse_RMS_ratio_to_fixed_max=1.25, offpulse_RMS_below_signed=True,
                      regular_RMSE_gain_vs_signed_lower95_min=0., constant_baseline_max_delta_pC=1e-10,
                      source_noise_ADC_mean_tolerance=.02, source_noise_ADC_RMS_relative_tolerance=.02,
                      source_zero_hist_bitwise_equal=True),
           partition='New native waveform groups from existing stage35 fit; not a new neutrino-energy test',
           source_test_scope='Exact pinned noise/convolution methods with explicit historical ID/conditions substitutes; no complete Athena/GeoModel replay')
with np.load(repo/'ntuples/energy_ml_stage35/fit.npz') as saved:
    d = {k:saved[k] for k in saved.files if k!='metadata_json'}
status = np.column_stack([d[f'CaloNu{i}_status'] for i in range(4)]).astype(np.uint32)
charge = np.column_stack([d[f'CaloNu{i}_charge'] for i in range(4)])
raw = np.column_stack([d[f'CaloNu{i}_raw_charge'] for i in range(4)])
conditions = [('nonfinite', (~np.isfinite(charge)).any(1)), ('saturated',(status&4!=0).any(1)),
              ('high_raw', raw.max(1)>10), ('negative',(charge<0).any(1)), ('fit_failed',(status&48!=0).any(1)),
              ('zero_readout',d['CaloNu_total_E_EM']==0), ('high_y',d['y_lepton']>=.8)]
counts = []
for index in indices:
    row = rows[index]; pool = np.flatnonzero(d['manifest_index']==index); p = d['reco_p_GeV']
    chosen = []
    for lo, hi in [(100,250),(250,1000)]:
        ids = pool[(p[pool]>=lo)&(p[pool]<hi)]; assert len(ids)>0
        ids = ids[np.argsort(d['eventID'][ids],kind='stable')]
        chosen.extend((int(i),'regular') for i in ids[np.linspace(0,len(ids)-1,min(12,len(ids))).astype(int)])
    diag = []
    for label, mask in conditions:
        ids = [int(i) for i in pool[mask[pool]] if i not in {r[0] for r in chosen+diag}]
        diag.extend((i,label) for i in ids[:min(2,8-len(diag))])
    for i in pool:
        if len(diag)==8: break
        if int(i) not in {r[0] for r in chosen+diag}: diag.append((int(i),'diagnostic_fill'))
    cases = []
    for i, role in chosen+diag:
        fp = dict(eventID=int(d['eventID'][i]), Track_p0=float(np.float32(p[i]*1000)),
                  Track_X_atVetoNu=float(d['ML_mu_X_atVetoNu_mm'][i]), Track_Y_atVetoNu=float(d['ML_mu_Y_atVetoNu_mm'][i]),
                  CaloNu0_raw_charge=float(d['CaloNu0_raw_charge'][i]))
        cases.append(dict(role=role, cache_row=i, fingerprint=fp, reco_p_GeV=float(p[i]), truth_E_GeV=float(d['truth_E_GeV'][i]),
                          y_lepton=float(d['y_lepton'][i]), vertex_z_mm=float(d['vertex_z_mm'][i]),
                          primary_kinematic_parent_proxy=bool(d['primary_kinematic_parent_proxy'][i])))
    phys = Path(row['input']); base = phys.parents[2]; first = int(row['group'].split(':')[1].split('-')[0])
    stem = phys.name.split(f'-{row["run"]}-')[0]+f'-{row["run"]}-'
    req = dict(index=index, run=int(row['run']), group=row['group'].replace(':','_'), component=row['component'],
               expected_phys_entries=10000, hits_events_per_file=1000, first_subfile=first,
               hits_name_template=stem+'{subfile:05}-s0015-HITS.root', allow_missing_channels=True, verify_phys_truth=True,
               input_phys=str(phys), input_rdo=str(base/'rdo/s0015'/phys.name.replace('-PHYS.root','-RDO.root')),
               input_rec=str(base/'rec/s0015'/phys.name.replace('-PHYS.root','-xAOD.root')), sim_directory=str(base/'sim/s0015'),cases=cases)
    for key in ['input_phys','input_rdo','input_rec']: assert Path(req[key]).exists()
    (out/f'request_{index}.json').write_text(json.dumps(req,indent=2)+'\n')
    counts.append(dict(index=index, regular=len(chosen), diagnostic=len(diag)))
assert sum(r['regular']+r['diagnostic'] for r in counts)<=cfg['max_events']
path.write_text(json.dumps(cfg,indent=2)+'\n')
record = dict(groups=counts, events=sum(r['regular']+r['diagnostic'] for r in counts),
              wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
              peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
(out/'preparation.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(cfg)); print(json.dumps(record))
