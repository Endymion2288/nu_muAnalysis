"""Complete native selection and direct62 extraction; sparse reco keeps a truth-only superset."""
import argparse
import json
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

ROOT = Path(__file__).resolve().parents[1]


def source(index):
    return json.loads((ROOT/'workbook/stage199_energy_ml/protocol.json').read_text())['sources'][index]


def request(index, pilot):
    s = source(index)
    with uproot.open(s['input'], array_cache=None) as f:
        t = f['nt']; n = min(1000, t.num_entries) if pilot else t.num_entries
        a = t.arrays(['eventID','run']+['truth_'+k for k in ['pdg','px','py','pz','dec_x','dec_y','dec_z']], entry_stop=n)
        first = lambda k: ak.to_numpy(ak.fill_none(ak.firsts(a['truth_'+k]), np.nan))
        x,y,z = [first('dec_'+k) for k in 'xyz']
        incoming = np.column_stack([first(k) for k in ['pdg','px','py','pz']])
        keep = (abs(incoming[:,0])==14)&(incoming[:,3]>50000)&(x*x+y*y<10000)
        keep &= ((z>-3000)&(z<-1950))|((z>np.float32(-1769.65))&(z<np.float32(-1619.65)))
        d = dict(source=s,parent_N=n,full_parent_N=t.num_entries,entries=np.flatnonzero(keep).tolist(),
                 eventID=ak.to_numpy(a.eventID)[keep].tolist(),incoming=incoming[keep].tolist(),
                 rdo='input-RDO.root',requested_bytes=int(f.file.source.num_requested_bytes))
    assert d['entries'], 'Empty truth pilot; record explicitly, do not replace by yield'
    Path('request.json').write_text(json.dumps(d)+'\n')


def extract(index, path, output):
    from extract_alternative_support import extract as native_extract
    from audited_features import configuration
    from latent_transfer_diagnostics import check_x
    s = source(index); output=Path(output);output.mkdir(parents=True,exist_ok=True)
    native_extract(index,Path(path),output/'native.npz',source=s)
    with np.load(output/'native.npz') as z:
        d = {k:z[k] for k in z.files if k!='metadata_json'}
        md = json.loads(str(z['metadata_json']))
    payload=json.loads((ROOT/'workbook/stage130_energy_ml/payload_snapshot.json').read_text())
    refs={tag:np.array([next(v['charge_ref'] for v in rows if v['channel']==j) for j in range(4)])
          for tag,rows in payload['payloads'].items()}
    with uproot.open(path) as f:
        a=f['nt'].arrays([f'Calo{j}_{k}' for j in range(4) for k in ['charge','E_EM','status']],library='np')
    qa=[];scales=[]
    for j in range(4):
        q,e,st=[a[f'Calo{j}_{k}'] for k in ['charge','E_EM','status']]
        use=(st==0)&np.isfinite(q+e)&(abs(q)>1e-6)
        assert use.any(),('No native calibration formula support',index,j)
        fits=[tag for tag,ref in refs.items() if np.allclose(e[use]/q[use],330/ref[j],rtol=2e-6)]
        assert len(fits)==1,(index,j,fits)
        tag=fits[0];scales.append(refs[tag][j]/refs['WAVE-Calibration-01-LG'][j])
        qa.append(dict(module=j,valid_N=int(use.sum()),native_tag=tag))
    names=configuration()['features'];cols=[names.index(f'ML_calo{j}_E_EM_GeV') for j in range(4)]
    d['x'][:,cols]=(d['x'][:,cols].astype(float)*np.array(scales)).astype('float32')
    d['x'][:,names.index('ML_calo_total_E_EM_GeV')]=np.sum(d['x'][:,cols].astype(float),axis=1).astype('float32')
    if s['mode']=='reco':
        r=json.loads(Path('request.json').read_text())
        with uproot.open(path) as f:
            a=f['nt'].arrays(['run','eventID','truth_pdg','truth_px','truth_py','truth_pz'])
            assert len(a)==len(r['entries'])
            np.testing.assert_array_equal(ak.to_numpy(a.eventID),r['eventID'])
            inc=np.column_stack([ak.to_numpy(ak.firsts(a['truth_'+k])) for k in ['pdg','px','py','pz']])
            np.testing.assert_array_equal(inc,r['incoming'])
        d['input_entry']=np.asarray(r['entries'])[d['input_entry']]
        md.update(original_parent_N=r['parent_N'],truth_superset_N=len(r['entries']),sparse_identity_exact=True)
    check_x(d['x'])
    start,end=map(int,s['segment'].split('-'))
    assert ((d['eventID']>=start*1000)&(d['eventID']<(end+1)*1000)).all()
    assert len(set(d['eventID']))==len(d['eventID'])
    md.update(source=s,reference='WAVE-Calibration-01-LG',formula_QA=qa,scales=scales,passed=True)
    np.savez_compressed(output/'selected.npz',**d)
    (output/'summary.json').write_text(json.dumps(md,indent=2)+'\n')
    (output/'native.npz').unlink()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['request','extract']);p.add_argument('index',type=int)
    p.add_argument('--pilot',action='store_true');p.add_argument('--input');p.add_argument('--output');a=p.parse_args()
    if a.action=='request':request(a.index,a.pilot)
    else:extract(a.index,a.input,a.output)
