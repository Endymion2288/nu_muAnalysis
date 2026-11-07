"""Exact-identity RDO ADC/PHYS pilot and source-wise extraction; no energy fits."""
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np
import ROOT

from stage122_saved import SavedWaveforms

OUT = Path('workbook/stage129_energy_ml')
CACHE = Path('ntuples/energy_ml_stage129')
SCINT = ['VetoNu0', 'VetoNu1', 'Veto10', 'Veto20', 'Veto21']
SUFFIXES = ['status', 'raw_charge', 'charge', 'localtime', 'baseline', 'baseline_rms', 'raw_peak', 'width']
TRACK_FIELDS = ['Track_pz0'] + ['Track_'+axis+'_at'+plane for plane in ['VetoNu','VetoStation1','VetoStation2'] for axis in ['X','Y','ThetaX','ThetaY']]


def extract(phase, index):
    tick, cpu = time.perf_counter(), time.process_time()
    initial_read_bytes = int(ROOT.TFile.GetFileBytesRead())
    plan = json.loads((OUT/'extraction_contract.json').read_text())
    source = plan['requests'][index]
    cases = source['cases']
    if phase.startswith('pilot'):
        cases = [c for c in cases if c['role'] == 1][:plan['pilot_per_source']]
    assert cases
    assert ROOT.gSystem.Load('libWaveRawEvent.so') >= 0
    saved = SavedWaveforms(ROOT, source['rdo'], ['VetoNu', 'Veto'])
    phys = ROOT.TFile.Open(source['phys']) if source['phys'] else None
    if source['phys']:
        assert phys and not phys.IsZombie(), source['phys']
    tree = phys.Get('nt') if phys else None
    schema = [b.GetName() for b in tree.GetListOfBranches()] if tree else []
    branches = ['run', 'eventID'] + [s+'_'+k for s in SCINT for k in SUFFIXES] + TRACK_FIELDS
    if tree:
        tree.SetBranchStatus('*', 0)
        for name in branches:
            assert tree.GetBranch(name), (source['phys'], name)
            tree.SetBranchStatus(name, 1)
    rows, adc, channels, ids, scalar, track, track_match = [], [], [], [], [], [], []
    for case in cases:
        if tree:
            assert tree.GetEntry(case['entry']) > 0
            assert (int(tree.run), int(tree.eventID)) == (case['run'], case['event'])
        waves = saved.read(case['entry'], case['run'], case['event'])
        selected = waves['VetoNu'] + waves['Veto']
        # Persist actual channel IDs, never infer the layout from list order.
        assert len(set(w['channel'] for w in selected)) == len(selected)
        rows.append(case['row'])
        channels.append([w['channel'] for w in selected])
        ids.append([w['id32'] for w in selected])
        adc.append([w['adc'] for w in selected])
        scalar.append([[float(getattr(tree, s+'_'+k)) if tree else np.nan for k in SUFFIXES] for s in SCINT])
        if tree:
            pz=list(tree.Track_pz0);lead=int(np.argmax(pz)) if pz else None
            matched=bool(lead is not None and np.isclose(pz[lead]/1000,case['pz'],rtol=3e-7,atol=3e-5))
            track_match.append(matched)
            track.append([float(getattr(tree,k)[lead]) if matched else np.nan for k in TRACK_FIELDS])
            if not matched:
                print('LEADING_INTERFACE_UNKNOWN',index,case['row'],case['pz'],pz[lead]/1000 if lead is not None else 'no_track',flush=True)
        else:
            track.append([np.nan]*len(TRACK_FIELDS))
            track_match.append(False)
    # Empty physical channels are a legitimate absence, not a failed event.
    # Keep the parent and explicit availability; 65535 is storage-only padding.
    channel_union = sorted(set(c for event in channels for c in event))
    presence = np.zeros((len(rows),len(channel_union)), dtype=bool)
    padded_adc = np.full((len(rows),len(channel_union),600),65535,dtype=np.uint16)
    padded_ids = np.zeros(presence.shape,dtype=np.uint32)
    for i, event in enumerate(channels):
        for j, channel in enumerate(event):
            k = channel_union.index(channel)
            padded_adc[i,k] = adc[i][j]
            padded_ids[i,k] = ids[i][j]
            presence[i,k] = True
    channels = np.broadcast_to(np.asarray(channel_union,dtype=np.int16),presence.shape)
    path = CACHE/f'{phase}_{index}.npz'
    np.savez_compressed(path, row=np.asarray(rows), adc=padded_adc, present=presence,
                        channel=channels, id32=padded_ids,
                        range_default_V=np.full(channels.shape, 2.0),
                        scalar=np.asarray(scalar), track=np.asarray(track), track_match=np.asarray(track_match), track_names=np.asarray(TRACK_FIELDS),
                        names=np.asarray(SCINT), suffixes=np.asarray(SUFFIXES))
    raw = padded_adc
    scalars = np.asarray(scalar)
    summary = dict(phase=phase, index=index, N=len(rows), source=source['phys'],
                   channels=channel_union, adc_shape=list(raw.shape), absent_channel_views=int((~presence).sum()),
                   rail_zero_samples=int((raw == 0).sum()), rail_zero_waveforms=int((raw == 0).any(2).sum()),
                   strict_good_counts=(scalars[:, :, 0] == 0).sum(0).tolist(),
                   scintillators=SCINT, suffixes=SUFFIXES, range_default_V=2.0, range_provenance='p0 does not persist range or trigger_offset; official transient defaults, not measured event values',
                   strict_pairs={f'{i}-{j}':int(((scalars[:,i,0]==0)&(scalars[:,j,0]==0)&np.isfinite(scalars[:,i,3])&np.isfinite(scalars[:,j,3])&(scalars[:,i,3]>=0)&(scalars[:,j,3]>=0)).sum())
                                 for i,j in [(0,1),(2,3),(3,4),(0,3),(1,3)]},
                   schemas=saved.schemas, phys_branch_names=schema if phase.startswith('pilot') else [],
                   output_bytes=path.stat().st_size, CPU_s=time.process_time()-cpu,
                   wall_s=time.perf_counter()-tick, ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead())-initial_read_bytes,
                   RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                   phys_scalar_available=bool(tree),leading_match_N=sum(track_match),leading_interface_unknown_N=len(track_match)-sum(track_match),new_fit=0, new_forward=0)
    (OUT/f'{phase}_{index}.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['phys_branch_names','schemas']}), flush=True)
    saved.file.Close()
    if phys:
        phys.Close()


if __name__ == '__main__':
    phase, index = sys.argv[1], int(sys.argv[2])
    plan = json.loads((OUT/'extraction_contract.json').read_text())
    indices = plan['batches'][index] if phase=='extract' else [index]
    for source_index in indices:
        extract(phase, source_index)
