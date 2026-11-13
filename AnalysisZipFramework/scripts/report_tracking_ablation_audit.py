#!/usr/bin/env python3
"""Check real ACTS material queries and seed/refit lineage in the paired audit pilot."""
import argparse
import json
from pathlib import Path

import numpy as np
from report_tracking_ablation import EVENT_KEYS, TRACK_KEYS, table

R = np.array([[0,0,1],[0,1,0],[-1,0,0]])


def query(entry, point, rotated):
    m = entry['value']['material']; utility = m['binUtility']
    tr = utility.get('transform', {})
    rotation = np.eye(3) if tr.get('rotation') is None else np.array(tr['rotation']).reshape(3,3,order='C')
    translation = np.array(tr.get('translation',[0,0,0]))
    if rotated:
        rotation = R @ rotation; translation = R @ translation
    local = rotation.T @ (point-translation)
    bins = []
    for axis in utility['binningdata']:
        assert axis['option'] == 'open' and axis['type'] == 'equidistant'
        value = {'binX':local[0], 'binY':local[1], 'binR':np.hypot(*local[:2]), 'binPhi':np.arctan2(local[1],local[0])}[axis['value']]
        lo = np.float32(axis['min']); hi = np.float32(axis['max'])
        step = np.float32((hi-lo)/axis['bins'])
        bins.append(int(np.clip(np.trunc(np.float32((np.float32(value)-lo)/step)),0,axis['bins']-1)))
    cell = m['data'][bins[1]][bins[0]]
    return cell['thickness']/cell['material'][0] if cell['material'] else 0.


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit', type=Path, required=True)
    p.add_argument('--pilot', type=Path, required=True)
    p.add_argument('--material-audit', type=Path)
    p.add_argument('--material-reference', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--map', type=Path, default=Path('/cvmfs/faser.cern.ch/repo/sw/database/DBRelease/current/acts/material-maps-alma9.json'))
    args = p.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    source = json.loads(args.map.read_text())
    entries = {(e.get('volume',0),e.get('layer',0),e.get('approach',0),e.get('sensitive',0)):e for e in source['Surfaces']['entries']}
    data = {}; validation = {}; rows = []; lineage = []
    for variant in ['native','material']:
        audit_path = args.material_audit if variant == 'material' and args.material_audit else args.audit/f'{variant}_053_00000.npz'
        reference_path = args.material_reference if variant == 'material' and args.material_reference else args.pilot/f'{variant}_053_00000.npz'
        assert audit_path.resolve() != reference_path.resolve()
        with np.load(audit_path) as f:
            a = {k:f[k] for k in f.files}
        with np.load(reference_path) as f:
            for k in EVENT_KEYS+TRACK_KEYS:
                assert np.array_equal(a[k],f[k],equal_nan=a[k].dtype.kind in 'fc'),(variant,k)
        # Retain only compact audit arrays; the pilot station cache is already consolidated separately.
        compact = {k:a[k] for k in a if k.startswith('audit_')}
        np.savez_compressed(args.output/f'audit_{variant}.npz',**compact)
        data[variant] = a
        validation[variant] = dict(observer_exact=True, summary=json.loads(str(a['audit_summary_json'])))
        t = a['primary_station']
        accepted = (a['primary'][:,2] == 1) & np.isfinite(t).all(axis=(1,2)) & (t[:,:,5]>100000).all(axis=1)
        accepted &= (np.linalg.norm(t[:,:,:2],axis=2)<95).all(axis=1)
        accepted &= (1000*np.arctan2(np.linalg.norm(t[:,:,3:5],axis=2),t[:,:,5])<25).all(axis=1)
        accepted &= (a['primary_layer_hits']>0).sum(axis=1)>=7
        primary = {(int(r),int(e)):int(b) for r,e,b,keep in zip(a['run'],a['eventID'],a['primary'][:,0],accepted) if keep}
        path = a['audit_paths']
        chosen = {tuple(row[:5].astype(int)) for row in path if row[5] == 1 and
            primary.get((int(row[0]),int(row[1])),0) == int(row[13]) and row[14] >= .7*row[15]}
        material = a['audit_materials']; sample = []
        for row in material:
            ident = int(row[6]); key = (ident>>56,(ident>>36)&0xfff,(ident>>28)&0xff,(ident>>8)&0xfffff)
            entry = entries[key]; point = row[10:13]
            current = query(entry,point,False); corrected = query(entry,point,True)
            actual = row[7]; expected = corrected if variant == 'material' else current
            np.testing.assert_allclose(actual,expected,rtol=2e-6,atol=1e-8)
            sample.append([row[2],row[5],key[0],key[1],actual,current,corrected,
                           int(tuple(row[:5].astype(int)) in chosen)])
        sample = np.array(sample)
        validation[variant]['real_queries_checked'] = len(sample)
        validation[variant]['max_relative_query_error'] = float(np.max(abs(sample[:,4] - (sample[:,6] if variant=='material' else sample[:,5]))/np.maximum(abs(sample[:,4]),1e-8)))
        for mode in [0,1]:
            for stage in [6,7]:
                for volume in sorted(set(sample[:,2])):
                    for scope in ['all_selected','accepted_primary']:
                        keep = (sample[:,0]==mode)&(sample[:,1]==stage)&(sample[:,2]==volume)
                        if scope == 'accepted_primary':keep &= sample[:,7] > 0
                        x = sample[keep]
                        if not len(x):continue
                        rows.append(dict(variant=variant,mode=['forward','backward'][mode],stage=['selected','refit'][stage-6],
                            volume=int(volume),scope=scope,states=len(x),actual_median_X0=float(np.median(x[:,4])),
                            unrotated_same_point_median_X0=float(np.median(x[:,5])),
                            rotated_same_point_median_X0=float(np.median(x[:,6])),
                            unrotated_gt1_X0=int((x[:,5]>1).sum()),rotated_gt1_X0=int((x[:,6]>1).sum())))
        for mode in [0,1]:
            for scope in ['all','accepted_primary']:
                for stage in [1,2,3,4,5]:
                    keep = (path[:,2] == mode)&(path[:,5] == stage)
                    if scope == 'accepted_primary':keep &= np.array([tuple(row[:5].astype(int)) in chosen for row in path])
                    x = path[keep]
                    lineage.append(dict(variant=variant,mode=['forward','backward'][mode],scope=scope,
                        stage=['seed','selected','converted','refit_input','refit','final'][stage],tracks=len(x),
                        fallback=int((x[:,12]==0).sum()) if stage==5 else -1,
                        median_p_gev=float(np.median(np.linalg.norm(x[:,6:9],axis=1))) if len(x) else np.nan))
    x = data['native']['audit_paths']; y = data['material']['audit_paths']
    x = x[x[:,5]==0]; y = y[y[:,5]==0]
    validation['seed_rows_native'] = len(x); validation['seed_rows_material'] = len(y)
    validation['seed_rows_exact'] = bool(np.array_equal(x,y,equal_nan=True))
    scales = []
    for mode in [0,1]:
        for scope in ['all','accepted_primary']:
            selected = x[:,2] == mode
            if scope == 'accepted_primary':
                selected &= np.array([primary.get((int(r[0]),int(r[1])),0)==int(r[13]) and r[15]>0 and r[14]>=.7*r[15] for r in x])
            momentum = x[selected,6:9]
            direction_a = momentum / np.linalg.norm(momentum,axis=1)[:,None]
            direction_f = direction_a @ R
            before = 1000*np.sqrt(.1089*np.maximum(0,1-direction_f[:,2]**2)+8.41e-6)
            after = 1000*np.sqrt(.1089*np.maximum(0,1-direction_a[:,2]**2)+8.41e-4)
            old_numbers = 1000*np.sqrt(.1089*np.maximum(0,1-direction_a[:,2]**2)+8.41e-6)
            scales.append(dict(mode=['forward','backward'][mode],scope=scope,seeds=len(momentum),
                old_direction_rms_median_mrad=float(np.median(before)),
                new_direction_rms_median_mrad=float(np.median(after)),
                new_with_old_diagonal_numbers_rms_median_mrad=float(np.median(old_numbers)),
                median_new_over_old_rms=float(np.median(after/before))))
    table(args.output/'seed_prior_physical_scales.tsv',scales)
    table(args.output/'actual_material_queries.tsv',rows)
    table(args.output/'audit_lineage.tsv',lineage)
    (args.output/'audit_validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    print(json.dumps({k:v for k,v in validation.items() if not isinstance(v,dict)}))


if __name__ == '__main__':main()
