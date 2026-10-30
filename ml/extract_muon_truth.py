#!/usr/bin/env python3
"""Read selected event diagnostics only: primary muon candidates and truth matching."""
import argparse
import csv
import json
import resource
import time
from pathlib import Path

import awkward as ak
import numpy as np
import uproot
import yaml


def extract(row, selected, config):
    started = time.perf_counter()
    truth = ['truth_pdg','truth_barcode','truth_px','truth_py','truth_pz','truth_m']
    truth += [f'truth_{kind}_{axis}' for kind in ['prod','dec'] for axis in ['x','y','z']]
    truth += [f'truth_st1_{axis}' for axis in ['x','y','z','px','py','pz']]
    track = ['Track_pz0','Track_p0','t_pdg','t_barcode','t_pdg_parent','t_barcode_parent',
             't_truthHitRatio','t_px','t_py','t_pz']
    with uproot.open(row['input']) as source:
        tree = source['nt']
        ids = tree['eventID'].array(library='np')
        wanted = selected['eventID'][selected['manifest_index']==int(row['index'])]
        mask = np.isin(ids,wanted)
        if int(mask.sum()) != len(wanted):
            raise RuntimeError('Missing or duplicate selected IDs')
        # Branch-clipped reads; cache excludes all non-selected events.
        arrays = tree.arrays(['run','eventID']+truth+track)[mask]
    if len(wanted)!=int(row['expected_selected']):
        raise RuntimeError('Frozen selected count mismatch')
    n=len(wanted)
    truth_lengths = ak.num(arrays['truth_pdg'])
    for name in truth:
        if bool(ak.any(ak.num(arrays[name])!=truth_lengths)):
            raise RuntimeError(f'Truth alignment failure: {name}')
    track_lengths=ak.num(arrays['Track_pz0'])
    for name in track:
        if bool(ak.any(ak.num(arrays[name])!=track_lengths)):
            raise RuntimeError(f'Used matching vector alignment failure: {name}')
    if bool(ak.any(track_lengths==0)):
        raise RuntimeError('Selected event has no track')
    expected_pdg=ak.firsts(arrays['truth_pdg'])*13/14
    candidate=arrays['truth_pdg']==expected_pdg
    for axis in ['x','y','z']:
        candidate=candidate & (abs(arrays[f'truth_prod_{axis}']-ak.firsts(arrays[f'truth_dec_{axis}'])) <= config['vertex_tolerance_mm'])
    nc=ak.to_numpy(ak.sum(candidate,axis=1))
    valid=nc==1
    def first_candidate(name):
        value=ak.to_numpy(ak.fill_none(ak.firsts(arrays[name][candidate]),np.nan)).astype(float)
        value[~valid]=np.nan
        return value
    result=dict(run=ak.to_numpy(arrays['run']),eventID=ak.to_numpy(arrays['eventID']),
                manifest_index=np.full(n,int(row['index']),dtype=np.int32),primary_candidates=nc,
                primary_valid=valid,primary_index=ak.to_numpy(ak.fill_none(ak.firsts(ak.local_index(candidate)[candidate]),-1)))
    for field in ['pdg','barcode','px','py','pz','m']:
        result['primary_'+field]=first_candidate('truth_'+field)
    result['primary_p_GeV']=np.sqrt(sum(result['primary_'+axis]**2 for axis in ['px','py','pz']))/1000
    result['primary_E_GeV']=np.sqrt(sum(result['primary_'+axis]**2 for axis in ['px','py','pz','m']))/1000
    for axis in ['x','y','z','px','py','pz']:
        result['primary_st1_'+axis]=first_candidate('truth_st1_'+axis)
    for axis in ['x','y','z']:
        result['vertex_'+axis+'_mm']=ak.to_numpy(ak.firsts(arrays['truth_dec_'+axis]))
    enu=np.sqrt(sum(ak.to_numpy(ak.firsts(arrays['truth_'+c]))**2 for c in ['px','py','pz','m']))/1000
    result['truth_E_GeV']=enu
    result['y_lepton']=1-result['primary_E_GeV']/enu
    result['transfer_energy_GeV']=enu-result['primary_E_GeV']
    lead=ak.argmax(arrays['Track_pz0'],axis=1,keepdims=True)
    for name in track:
        result['lead_'+name]=ak.to_numpy(ak.flatten(arrays[name][lead]))
    primary_match=(valid & (result['lead_t_barcode']==result['primary_barcode']) &
                   (result['lead_t_pdg']==result['primary_pdg']))
    incoming_pdg=ak.to_numpy(ak.firsts(arrays['truth_pdg']))
    incoming_barcode=ak.to_numpy(ak.firsts(arrays['truth_barcode']))
    parent_ok=(result['lead_t_pdg_parent']==incoming_pdg)&(result['lead_t_barcode_parent']==incoming_barcode)
    result['lead_primary_barcode_match']=primary_match
    result['lead_primary_parent_confirmed']=primary_match & parent_ok
    # Independently confirm candidate ancestry wherever any matched track provides it.
    matches=(arrays['t_barcode']==ak.Array(result['primary_barcode'])) & (arrays['t_pdg']==ak.Array(result['primary_pdg']))
    matches=matches & (arrays['t_pdg_parent']==ak.firsts(arrays['truth_pdg'])) & (arrays['t_barcode_parent']==ak.firsts(arrays['truth_barcode']))
    result['any_primary_parent_confirmed']=ak.to_numpy(ak.any(matches,axis=1))&valid
    result['primary_st1_p_GeV']=np.sqrt(sum(result['primary_st1_'+axis]**2 for axis in ['px','py','pz']))/1000
    # Official FiducialParticleTool uses NaN for missing references. Its norm uses
    # production momentum and averaged hit directions, NOT transported momentum.
    result['primary_st1_valid']=valid & (result['primary_st1_p_GeV']>0) & np.isfinite(result['primary_st1_p_GeV'])
    result['reco_p_GeV']=result['lead_Track_p0']/1000
    order=np.lexsort((result['eventID'],result['run']))
    result={k:v[order] for k,v in result.items()}
    expected_order=np.argsort(selected['eventID'][selected['manifest_index']==int(row['index'])])
    expected_ids=selected['eventID'][selected['manifest_index']==int(row['index'])][expected_order]
    np.testing.assert_array_equal(result['eventID'],expected_ids)
    report=dict(index=int(row['index']),run=int(row['run']),input=row['input'],partition=row['partition'],
                input_events=len(ids),selected_events=n,primary_unique=int(valid.sum()),
                primary_missing=int((nc==0).sum()),primary_ambiguous=int((nc>1).sum()),
                lead_primary_barcode_matches=int(primary_match.sum()),
                lead_primary_parent_confirmed=int((primary_match&parent_ok).sum()),
                any_primary_parent_confirmed=int(result['any_primary_parent_confirmed'].sum()),
                primary_station1_valid=int(result['primary_st1_valid'].sum()),
                y_outside_0_1=int(((result['y_lepton']<0)|(result['y_lepton']>1)).sum()),
                truth_track_alignment_failures=0,wall_s=time.perf_counter()-started,
                peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    return result,report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--batch',type=int,required=True)
    p.add_argument('--batch-size',type=int,default=12)
    p.add_argument('--index',type=int)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    config=yaml.safe_load((args.repo/'ml/configs/physics_decomposition.yaml').read_text())
    rows=[r for r in csv.DictReader((args.repo/'ml/configs/files.tsv').open(),delimiter='\t') if r['partition'] in config['partitions']]
    if args.index is not None:
        rows=[r for r in rows if int(r['index'])==args.index]
    else:
        rows=rows[args.batch*args.batch_size:(args.batch+1)*args.batch_size]
    if not rows:raise ValueError('Empty extraction batch')
    base=Path(rows[0]['cache']).parents[1]/'dataset'
    selected={}
    for part in config['partitions']:
        with np.load(base/f'{part}.npz') as d:
            selected[part]={k:d[k] for k in ['eventID','manifest_index']}
    all_data=[];reports=[]
    for row in rows:
        data,report=extract(row,selected[row['partition']],config)
        all_data.append(data);reports.append(report)
        print(json.dumps(report),flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(args.output,**{k:np.concatenate([d[k] for d in all_data]) for k in all_data[0]},
                        reports_json=np.array(json.dumps(reports)),config_json=np.array(json.dumps(config)))


if __name__=='__main__':
    main()
