"""Stage80 scalar-only, per-source reads; retain only frozen original identities."""
import argparse
import json
import resource
import numpy as np
import uproot
from pulse_ablation import *

SUFFIXES=['width','raw_peak','localtime','status','raw_charge','baseline_rms']


def extract(job,qa=False,check=False):
    start=begin();p=json.loads((OUT/('proposal.json' if qa else 'protocol.json')).read_text());identity=arrays(CACHE/'identity.npz')
    take=np.isin(identity['row'],p['qa_rows']) if qa else np.ones(len(identity['row']),bool)
    sources=[r for r in p['sources'] if int(r['index']) in identity['source'][take]]
    if not qa:sources=sources[job::4];resource.setrlimit(resource.RLIMIT_CPU,(850,875))
    if check:
        print(json.dumps(dict(job=job,sources=len(sources),N=int(np.isin(identity['source'],[int(r['index']) for r in sources]).sum()),
            no_ROOT=True,energy_fits=0,**resources(start))));return
    branches=['run','eventID']+[s+'_'+k for s in SCINTILLATORS for k in SUFFIXES]
    parts=[];records=[]
    for source in sources:
        tick=begin();idx=np.flatnonzero(take&(identity['source']==int(source['index'])))
        with uproot.open(source['input'],array_cache=None) as f:
            t=f['nt'];a=t.arrays(branches,library='np');requested=int(f.file.source.num_requested_bytes)
            assert len(np.unique(a['eventID']))==len(a['eventID'])
            lookup={int(e):i for i,e in enumerate(a['eventID'])};entry=np.array([lookup[int(e)] for e in identity['eventID'][idx]])
            np.testing.assert_array_equal(a['run'][entry],identity['run'][idx])
            a={k:v[entry] for k,v in a.items()}
        values={k:np.column_stack([a[s+'_'+k] for s in SCINTILLATORS]) for k in SUFFIXES}
        for key in ['status','raw_charge','baseline_rms']:np.testing.assert_array_equal(values[key],identity[key][idx])
        valid=strong_shape_validity(values)
        shape=np.stack([values['raw_peak'],values['width']],axis=2).reshape(len(idx),22).astype('float32')
        shape[np.repeat(~valid,2,axis=1)]=np.nan
        part=dict(row=identity['row'][idx],shape=shape,valid=valid)
        if qa:
            old=arrays(REPO/'ntuples/energy_ml_stage79/qa.npz');ix={int(r):i for i,r in enumerate(old['row'])};order=np.array([ix[int(r)] for r in part['row']])
            for key in SUFFIXES:np.testing.assert_array_equal(values[key],old[key][order])
        parts.append(part)
        records.append(dict(source=int(source['index']),N=len(idx),input_N=t.num_entries,requested_bytes=requested,
            scalar_array_calls=1,raw_status_RMS_exact=True,**resources(tick)))
        assert sum(r['requested_bytes'] for r in records)<2_300_000_000
    result={k:np.concatenate([r[k] for r in parts]) for k in parts[0]};order=np.argsort(result['row']);result={k:v[order] for k,v in result.items()}
    name='qa' if qa else f'extract{job}';destination=CACHE/(name+'.npz');assert not destination.exists()
    np.savez_compressed(destination,**result)
    stats=dict(N=len(result['row']),sources=len(records),records=records,raw_status_RMS_exact=True,
        stage79_QA_exact=qa,strong_valid_N=int(result['valid'].sum()),requested_bytes=sum(r['requested_bytes'] for r in records),
        output_bytes=destination.stat().st_size,no_energy_fit=True,**resources(start))
    save(OUT/(name+'.json'),stats);print(json.dumps({k:v for k,v in stats.items() if k!='records'}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',type=int,default=0,choices=range(4));p.add_argument('--qa',action='store_true');p.add_argument('--check-only',action='store_true');a=p.parse_args();extract(a.job,a.qa,a.check_only)
