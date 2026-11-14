#!/usr/bin/env python3
"""Audit pilot material queries against frozen JSON and compare primary station response."""
import argparse
import gzip
import json
from pathlib import Path
import numpy as np
from report_tracking_ablation import table, load_cache, subset, event_key
from report_tracking_material import truth_masks
from report_tracking_station import derived
from report_tracking_ablation_audit import query
from compare_tracking import MODES


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--afs', type=Path, required=True)
    p.add_argument('--strict', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    data = {}; validation = {}; configs = {}; queries = []
    for label, path, mapname in [('afs', args.afs, 'material-afs.json.gz'), ('strict',args.strict,'material-manual-rowmajor.json.gz')]:
        with np.load(path) as f: a = {k: f[k] for k in f.files}
        assert int(a['counts'][0,0]) == 1000 and len(a['all_eventID']) == 1000
        mapdata = json.loads(gzip.decompress((args.repo/'software/stage205_material'/mapname).read_bytes()))
        entries = {tuple(e.get(k,0) for k in ['volume','layer','approach','sensitive']): e for e in mapdata['Surfaces']['entries']}
        errors = []
        for row in a['audit_materials']:
            ident = int(row[6]); key = (ident>>56,(ident>>36)&0xfff,(ident>>28)&0xff,(ident>>8)&0xfffff)
            expected = query(entries[key], row[10:13], False)
            np.testing.assert_allclose(row[7],expected,rtol=2e-6,atol=1e-8)
            errors.append(abs(row[7]-expected)/max(abs(row[7]),1e-8))
        configuration = json.loads(str(a['effective_ablation_json']))
        assert 'material-rotated.json' in configuration['geometry']['MaterialMapInputFile']
        for alg in configuration['algorithms'].values():
            assert alg['IsolateCandidateSmoothing'] == 'True' and alg['BypassRefit'] == 'False'
            assert float(alg['seed_effective']['covTheta']) == 8.41e-4
            assert float(alg['seed_effective']['covQOverP']) == 1e-3
        validation[label] = dict(events=1000, truth=len(a['run']), real_queries_checked=len(errors),
                                 max_relative_query_error=max(errors), checked_official_long=int(a['official_long_matches_checked']),
                                 final_FBM=a['counts'][:,-1].tolist(), performance=json.loads(str(a['performance_json'])),
                                 runtime_map=configuration['geometry']['MaterialMapInputFile'])
        compact = {k:v for k,v in a.items() if k.startswith('audit_')}
        np.savez_compressed(args.output/(label+'_audit.npz'),**compact)
        np.savez_compressed(args.output/(label+'.npz'),**{k:a[k] for k in a if not k.startswith('audit_')})
        data[label] = a; configs[label] = configuration
    for label,version in [('old','old'),('native','new')]:
        data[label] = subset(load_cache(args.repo/f'workbook/stage203_station_truth/{version}.npz'),event_key(data['afs']))
    for label,a in data.items():
        for k in ['run','eventID','primary','primary_station','primary_layer_hits']:
            np.testing.assert_equal(a[k],data['old'][k])
        if label != 'old': np.testing.assert_equal(a['scintillator'],data['native']['scintillator'])
    seeds = [data[v]['audit_paths'][data[v]['audit_paths'][:,5] == 0] for v in ['afs','strict']]
    assert np.array_equal(seeds[0],seeds[1],equal_nan=True)
    validation['identical_seeds_afs_strict'] = len(seeds[0])
    accepted = truth_masks(data['old'])['truth_station_acceptance']; rows=[]
    for label,a in data.items():
        d=derived(a)
        for m,mode in enumerate(MODES):
            leader=d['leaders'][:,m];li=np.maximum(leader,0)
            correct=(leader>=0)&d['primary'][li]&(d['purity'][li]>=.7)
            for st in range(3):
                r=a['reco_at_primary_station'][li,st,5];t=a['primary_station'][:,st,5]
                good=correct&np.isfinite(r)&np.isfinite(t)&(t>0)
                x=r[good]/t[good]-1
                rows.append(dict(version=label,mode=mode,station=st+1,pairs=int(good.sum()),
                    median_abs_pz_percent=100*float(np.median(abs(x))),truth_accepted=int(accepted.sum()),
                    truth_accepted_final=int((accepted&d['final'][:,m]).sum())))
    table(args.output/'pilot_station_response.tsv',rows)
    (args.output/'pilot_validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    (args.output/'pilot_effective_configurations.json').write_text(json.dumps(configs,indent=2)+'\n')
    print(json.dumps(validation))


if __name__ == '__main__': main()
