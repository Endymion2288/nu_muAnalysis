"""Unique native REC/merged PHYS identity pairing and fixed raw-support audit."""
import csv
import gzip
import json
import math
import resource
import time
from collections import Counter
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

OUT = Path('workbook/stage159_energy_ml')
CACHE = Path('ntuples/energy_ml_stage159')
SCINT = ['VetoNu0','VetoNu1','Veto10','Veto20','Veto21','Timing0','Timing1','Timing2','Timing3','Preshower0','Preshower1']
CHANNELS = SCINT + [f'Calo{i}' for i in range(4)]
TRACK = ['Track_pz0','Track_px0','Track_py0','Track_Chi2','Track_nDoF','Track_nLayers',
         'Track_X_atVetoStation1','Track_Y_atVetoStation1']
COUNTS = ['longTracks','SpacePoints'] + [f'nClusters{i}' for i in range(4)]
SENTINELS = [-999., -9999., -99999.]


def finite(value):
    return value is not None and math.isfinite(float(value))


def number(value, positive=False, nonnegative=False):
    if value is None:
        return None
    value = float(value)
    if not math.isfinite(value) or value in SENTINELS:
        return None
    if positive and value <= 0 or nonnegative and value < 0:
        return None
    return value


def main():
    cpu, tick = time.process_time(), time.perf_counter()
    plan = json.loads((OUT/'protocol.json').read_text())
    native = json.loads((OUT/'native_64.json').read_text())
    repeat = json.loads((OUT/'native_4.json').read_text())
    assert native['records'][:4] == repeat['records']
    assert native['source'] == repeat['source'] == plan['sources']['REC']
    assert len(native['records']) == 64 and len(repeat['records']) == 4
    native_counts = Counter((r['run'],r['event']) for r in native['records'])
    (OUT/'native_metadata.json').write_text(json.dumps({k:native[k] for k in ['source','native_entries','metadata','schema']},indent=2)+'\n')
    with uproot.open(plan['sources']['PHYS'], array_cache=None) as source:
        tree = source['nt']
        schema = tree.typenames()
        assert all(k in schema for k in ['run','eventID'])
        index = tree.arrays(['run','eventID'], library='np')
        lookup = {key:[] for key in native_counts}
        for entry, (run,event) in enumerate(zip(index['run'],index['eventID'])):
            key = (int(run),int(event))
            if key in lookup:
                lookup[key].append(entry)
        records, paired_entries = [], []
        for parent in native['records']:
            key = (parent['run'],parent['event'])
            matches = lookup[key]
            unique = len(matches)==1 and native_counts[key]==1
            records.append(dict(parent, PHYS_matches=len(matches), native_key_multiplicity=native_counts[key],
                PHYS_entry=matches[0] if unique else None, unique_pair=unique, track=None, counts=None, readouts=None))
            if unique:
                paired_entries.append(matches[0])
        wanted = TRACK + COUNTS + [f'{c}_{f}' for c in CHANNELS for f in ['raw_charge','raw_peak','baseline_rms','status']]
        missing = sorted(set(wanted)-set(schema))
        branches = [b for b in wanted if b in schema]
        payload = {}
        blocks = []
        for entry in sorted(set(paired_entries)):
            if not blocks or entry-blocks[-1][-1]>256 or entry-blocks[-1][0]>=4096:
                blocks.append([entry])
            else:
                blocks[-1].append(entry)
        for entries in blocks:
            start, stop = entries[0],entries[-1]+1
            arrays = tree.arrays(branches,entry_start=start,entry_stop=stop)
            for entry in entries:
                payload[entry] = arrays[entry-start]
        for record in records:
            if not record['unique_pair']:
                continue
            values = payload[record['PHYS_entry']]
            leading = None
            if 'Track_pz0' in branches:
                momenta = [number(v) for v in ak.to_list(values['Track_pz0'])]
                candidates = [j for j,v in enumerate(momenta) if v is not None]
                if candidates:
                    leading = max(candidates,key=lambda j:momenta[j])
            track = {}
            for branch in TRACK:
                values_list = ak.to_list(values[branch]) if branch in branches else []
                value = values_list[leading] if leading is not None and leading<len(values_list) else None
                value = number(value,positive=branch=='Track_nDoF',nonnegative=branch in ['Track_Chi2','Track_nLayers'])
                track[branch] = value/1000 if value is not None and branch in TRACK[:3] else value
            counts = {b:number(values[b],nonnegative=True) if b in branches else None for b in COUNTS}
            q = {}
            for channel in CHANNELS:
                fields = {}
                for field in ['raw_charge','raw_peak','baseline_rms','status']:
                    branch = channel+'_'+field
                    fields[field] = number(values[branch],positive=field in ['raw_peak','baseline_rms'],nonnegative=field=='status') if branch in branches else None
                status = fields['status']
                present = (status is not None and fields['baseline_rms'] is not None and (int(status)&(8|128|256))==0)
                fields['present'] = bool(present)
                fields['measured_raw_charge_pC'] = fields['raw_charge'] if present else None
                q[channel] = fields
            pz, ndof, chi = track['Track_pz0'],track['Track_nDoF'],track['Track_Chi2']
            selected = (counts['longTracks']==1 and finite(pz) and 50<pz<2000 and finite(ndof) and finite(chi)
                        and chi/ndof<10 and finite(track['Track_nLayers']) and track['Track_nLayers']>=7)
            record.update(track=track,counts=counts,readouts=q,control_eligible=bool(selected),
                pz50_100=bool(finite(pz) and 50<pz<100),
                complete_raw15=all(v['measured_raw_charge_pC'] is not None for v in q.values()))
        io_bytes = int(source.file.source.num_requested_bytes)
        phys_entries = int(tree.num_entries)
    CACHE.mkdir(parents=True,exist_ok=True)
    with gzip.open(CACHE/'paired_records.json.gz','wt') as stream:
        json.dump(dict(records=records,repeat4=repeat['records']),stream,separators=(',',':'),allow_nan=False)
    with (OUT/'pairing.tsv').open('w') as stream:
        fields = ['entry','run','event','PHYS_entry','PHYS_matches','native_key_multiplicity','unique_pair','control_eligible','pz50_100','complete_raw15']
        writer = csv.DictWriter(stream,fieldnames=fields,delimiter='\t',lineterminator='\n',extrasaction='ignore')
        writer.writeheader();writer.writerows(records)
    raw_rows = []
    for channel in CHANNELS:
        pairs = [r for r in records if r['readouts'] is not None]
        values = [r['readouts'][channel] for r in pairs]
        raw_rows.append(dict(channel=channel,paired_parent_N=len(pairs),present_N=sum(v['present'] for v in values),
            raw_known_N=sum(v['measured_raw_charge_pC'] is not None for v in values),
            signed_negative_raw_N=sum(v['measured_raw_charge_pC'] is not None and v['measured_raw_charge_pC']<0 for v in values),
            legal_raw_minus1_N=sum(v['measured_raw_charge_pC']==-1 for v in values),
            overflow_N=sum(v['status'] is not None and (int(v['status'])&4)!=0 for v in values),
            nonzero_status_N=sum(v['status'] is not None and v['status']!=0 for v in values)))
    with (OUT/'raw_support.tsv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(raw_rows[0]),delimiter='\t',lineterminator='\n')
        writer.writeheader();writer.writerows(raw_rows)
    (OUT/'PHYS_schema.json').write_text(json.dumps(dict(source=plan['sources']['PHYS'],entries=phys_entries,
        branches=schema,missing_requested_branches=missing),indent=2)+'\n')
    # The complete actual native inventory is retained, including unfiltered waveform names.
    waveform = [r for r in native['schema'] if any(t in (r['name']+' '+r['class_name']).lower() for t in ['wave','calo','veto','trigger','preshower'])]
    summary = dict(passed=True,native_parent_N=64,native_entries=native['native_entries'],PHYS_entries=phys_entries,
        unique_pair_N=sum(r['unique_pair'] for r in records),missing_pair_N=sum(r['PHYS_matches']==0 for r in records),
        ambiguous_pair_N=sum(not r['unique_pair'] and r['PHYS_matches']>0 for r in records),
        different_entry_N=sum(r['unique_pair'] and r['entry']!=r['PHYS_entry'] for r in records),
        control_eligible_N=sum(r.get('control_eligible',False) for r in records),
        control_eligible_pz50_100_N=sum(r.get('control_eligible',False) and r.get('pz50_100',False) for r in records),
        complete_raw15_N=sum(r.get('complete_raw15',False) for r in records),
        prefix4_independent_identity_exact=True,missing_requested_PHYS_branches=missing,
        actual_native_waveform_branch_inventory=waveform,PHYS_read_bytes=io_bytes,matched_read_blocks=len(blocks),
        CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        new_G4=0,energy_fits=0,natural_nu_forward=0,reserved_forward=0,promotion=False,overall_complete=False,
        limitations=['Exact event identity does not certify equal native/PHYS reconstruction or raw producer',
                    'No native detector payload read, no calibrated track covariance or association',
                    'No certified data muon purity, FPR, background, exposure or spectrum measurement'])
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(summary,flush=True)


if __name__=='__main__':
    main()
