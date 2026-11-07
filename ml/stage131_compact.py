"""Exact array-level compaction proof before redundant event files are removed."""
import gzip
import json
import time
import numpy as np
from stage131_common import OUT,CACHE,load,protocol

def main():
    start=time.perf_counter();p=protocol();d=load(CACHE/'matched_input.npz');cursor=0;extras={};evidence=[];schemas=None;arrays=0;source_bytes=0
    mapping={'reco_pz_GeV':'pz'}
    for i in p['indices']:
        path=CACHE/f'parent_{i}_selected.npz';source_bytes+=path.stat().st_size
        with np.load(path) as z:
            n=len(z['x']);fields=[k for k in z.files if k!='metadata_json']
            schema={k:dict(dtype=str(z[k].dtype),shape_tail=list(z[k].shape[1:])) for k in fields}
            if schemas is None:schemas=schema
            else:assert schemas==schema
            assert np.array_equal(d['frame_index'][cursor:cursor+n],np.full(n,i))
            for k in fields:
                target=mapping.get(k,k)
                if target in d:np.testing.assert_array_equal(z[k],d[target][cursor:cursor+n])
                else:extras.setdefault(k,[]).append(z[k])
                arrays+=1
            meta=str(z['metadata_json'])
        reports={kind:json.loads((OUT/f'parent_{i}_{kind}.json').read_text()) for kind in ['summary','hitscheck','selection','rng']}
        evidence.append(dict(index=i,selected_N=n,extraction_metadata_json=meta,reports=reports))
        cursor+=n
    assert cursor==len(d['role'])
    extra={k:np.concatenate(v) for k,v in extras.items()};extra['frame_index']=d['frame_index']
    np.savez_compressed(CACHE/'selected_extra.npz',**extra)
    reloaded=load(CACHE/'selected_extra.npz')
    for k,v in extra.items():np.testing.assert_array_equal(v,reloaded[k])
    encoded=json.dumps(evidence,separators=(',',':'))
    with gzip.open(CACHE/'parent_evidence.json.gz','wt') as f:f.write(encoded)
    with gzip.open(CACHE/'parent_evidence.json.gz','rt') as f:assert f.read()==encoded
    summary=dict(passed=True,parents=len(evidence),selected_rows=cursor,source_arrays_verified=arrays,array_schemas=schemas,source_to_matched_mapping=mapping,source_selected_npz_B=source_bytes,extra_npz_B=(CACHE/'selected_extra.npz').stat().st_size,evidence_gzip_B=(CACHE/'parent_evidence.json.gz').stat().st_size,fields_not_duplicated=list(k for k in schemas if mapping.get(k,k) in d),wall_s=time.perf_counter()-start,scope='all original arrays reconstruct exactly from matched+extra in matchedframeorder; perparent original JSON string and reports preserved losslessly; NPZ ZIP container bytes not claimed identical')
    (OUT/'compact_verification.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary)

if __name__=='__main__':main()
