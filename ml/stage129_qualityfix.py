"""Repair only controlled pulse-quality stress column mapping; no raw reread/refit."""
import csv
import json

import numpy as np

from stage129_energy import ROOT,OUT,CACHE,ART,load,evaluate,table
from stage129_energystress import forward

assert not (OUT/'quality_channel_mapping_validation.json').exists(), 'Legacy migration already applied'
d=load(ROOT/'ntuples/energy_ml_stage119/old_input.npz');f=load(CACHE/'timing_features.npz')
q=load(CACHE/'wave_peak_noise.npz')['peak_over_noise'][:,[0,1,4,2,3]]
np.savez_compressed(CACHE/'wave_peak_noise.npz',peak_over_noise=q)
rows=list(csv.DictReader((OUT/'timingstress_paired.tsv').open(),delimiter='\t'))
table('timingstress_quality_before_mapping.tsv',[r for r in rows if r['candidate'] in ['quality4sigma','quality6sigma']])
for threshold in [4,6]:
    valid=f['valid'].copy();value=f['features'].copy()
    for k,(i,j) in enumerate([(0,1),(3,4),(0,3),(1,3)]):
        keep=(q[:,i]>=threshold)&(q[:,j]>=threshold)
        valid[~keep,3*k+2]=0;value[~keep,k]=np.nan
    forward('timing',f'quality{threshold}sigma','T',np.column_stack([d['x'],valid,value]),d)
p=load(ART/'timingstress_predictions.npz');arms=[a for a in p if a not in ['direct_cal','traditional']]
evaluate('timingstress',d,arms,extra_references=['T'])
(OUT/'quality_channel_mapping_validation.json').write_text(json.dumps(dict(original_source_channels=[4,5,6,7,14],target_channels=[4,5,14,6,7],source_count=280,models_refitted=0,corrected_quality_forwards=2,raw_ADC_rereads=0,main_experiments_unchanged=True),indent=2)+'\n')
