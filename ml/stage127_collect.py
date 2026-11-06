"""Merge exact event coordinates and truth-parent histograms into one small cache."""
import json
import tarfile
from pathlib import Path
import numpy as np
from stage127_coordinates import histogram_edges
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage127_energy_ml'
CACHE=ROOT/'ntuples/energy_ml_stage127'


def main():
    p=json.loads((OUT/'protocol.json').read_text());parts=[];metadata=[]
    for b in range(p['coordinate_batches']):
        with tarfile.open(CACHE/f'coordinates_{b}.tar.gz') as archive:
            for member in archive.getmembers():
                assert member.isfile() and member.name.startswith(('ntuples/energy_ml_stage127/coordinates_','workbook/stage127_energy_ml/coordinates_'))
            archive.extractall(ROOT,filter='data')
        with np.load(CACHE/f'coordinates_{b}.npz') as z:parts.append({k:z[k] for k in z.files})
        metadata.extend(json.loads((OUT/f'coordinates_{b}.json').read_text())['files'])
    with np.load(ROOT/'ntuples/energy_ml_stage126/predictions.npz') as z:
        r=z['radius_mm'];n=len(r)
    rows=np.concatenate([a['row'] for a in parts]);assert sorted(rows.tolist())==list(range(n))
    x=np.empty(n);y=np.empty(n)
    for a in parts:x[a['row']]=a['x'];y[a['row']]=a['y']
    np.testing.assert_array_equal(np.hypot(x,y),r)
    hist50=np.sum([a['hist50'] for a in parts],axis=0);hist100=np.sum([a['hist100'] for a in parts],axis=0)
    assert hist50.sum()==618779
    ex,ey=histogram_edges(p)
    np.savez_compressed(CACHE/'coordinates.npz',x=x,y=y,hist50=hist50,hist100=hist100,edges_x=ex,edges_y=ey)
    report=dict(passed=True,N=n,coordinate_identity_and_radius_exact=True,old_coordinates_exact_N=sum(m['old_coordinates_exact_N'] for m in metadata),
                parent50_N=int(hist50.sum()),parent100_N=int(hist100.sum()),raw_N=sum(m['raw_N'] for m in metadata),
                requested_uproot_bytes=sum(m['requested_uproot_bytes'] for m in metadata),worker_wall_sum_s=sum(m['wall_s'] for m in metadata),
                worker_CPU_sum_s=sum(m['CPU_s'] for m in metadata),files=metadata,new_fits=0,new_model_forwards=0,
                bounds_mm=dict(x=[float(x.min()),float(x.max())],y=[float(y.min()),float(y.max())]))
    (OUT/'coordinate_validation.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items() if k!='files'})


if __name__=='__main__':main()
