"""Read only missing truth x/y coordinates; reuse every frozen stage126 prediction."""
import argparse
import json
import multiprocessing as mp
import resource
import time
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage127_energy_ml'
CACHE=ROOT/'ntuples/energy_ml_stage127'
DATA=None
ANCHOR=None
EDGES=None
BRANCHES=['run','eventID','truth_dec_x','truth_dec_y','truth_dec_z','truth_pdg','truth_pz']


def histogram_edges(protocol):
    grid=protocol['grid']
    edges=[]
    for centers,halves in [(grid['center_x_mm'],grid['half_width_mm']),
                           (grid['center_y_mm'],grid['half_height_mm'])]:
        bounds={-301.,301.}
        for c in centers:
            for half in halves:
                bounds.update([float(c-half),float(c+half),np.nextafter(float(c-half),np.inf)])
        edges.append(np.array(sorted(bounds)))
    return edges


def initialize():
    global DATA,ANCHOR,EDGES
    with np.load(ROOT/'ntuples/energy_ml_stage126/predictions.npz') as z:
        DATA={k:z[k] for k in ['source','run','eventID','input_entry','radius_mm']}
    with np.load(CACHE/'anchor.npz') as z:
        ANCHOR={k:z[k] for k in z.files}
    EDGES=histogram_edges(json.loads((OUT/'protocol.json').read_text()))


def work(source):
    start=time.perf_counter();cpu=time.process_time();index=source['index']
    take=np.flatnonzero(DATA['source']==index)
    with uproot.open(source['input']) as f:
        tree=f['nt'];entries=DATA['input_entry'][take]
        a=tree.arrays(BRANCHES)
        requested=int(f.file.source.num_requested_bytes);raw_N=tree.num_entries
    np.testing.assert_array_equal(ak.to_numpy(a.eventID)[entries],DATA['eventID'][take])
    np.testing.assert_array_equal(ak.to_numpy(a.run)[entries],DATA['run'][take])
    first=lambda v:ak.to_numpy(ak.fill_none(ak.firsts(v),np.nan)).astype(float)
    xx,yy,zz=[first(a['truth_dec_'+axis]) for axis in 'xyz']
    x,y=xx[entries],yy[entries]
    np.testing.assert_array_equal(np.hypot(x,y),DATA['radius_mm'][take])
    old=np.flatnonzero(ANCHOR['source']==index)
    lookup={int(e):i for i,e in enumerate(DATA['eventID'][take])}
    order=np.array([lookup[int(e)] for e in ANCHOR['eventID'][old]])
    np.testing.assert_array_equal(x[order],ANCHOR['vertex_x_mm'][old])
    np.testing.assert_array_equal(y[order],ANCHOR['vertex_y_mm'][old])
    xf,yf,zf=[v.astype('float32') for v in [xx,yy,zz]]
    box=(xf>-115)&(xf<135)&(yf>-171)&(yf<129)&(zf>-3000)&(zf<-1950)
    block=(xf>-300)&(xf<300)&(yf>-300)&(yf<300)&(zf>np.float32(-1769.65))&(zf<np.float32(-1619.65))
    cc=ak.to_numpy(ak.any((abs(a.truth_pdg)==11)|(abs(a.truth_pdg)==13)|(abs(a.truth_pdg)==15),axis=1))
    parent=cc&(abs(first(a.truth_pdg))==14)&(box|block)
    pz=first(a.truth_pz)/1000
    parent50=parent&(pz>50);parent100=parent&(pz>100)
    assert int(parent50.sum())==source['parent50_N']
    hist50=np.histogram2d(xx[parent50],yy[parent50],bins=EDGES)[0].astype('int64')
    hist100=np.histogram2d(xx[parent100],yy[parent100],bins=EDGES)[0].astype('int64')
    assert hist50.sum()==parent50.sum() and hist100.sum()==parent100.sum()
    meta=dict(source=index,raw_N=raw_N,N=len(take),old_coordinates_exact_N=len(old),
              requested_uproot_bytes=requested,wall_s=time.perf_counter()-start,
              CPU_s=time.process_time()-cpu,peak_worker_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              parent50_N=int(parent50.sum()),parent100_N=int(parent100.sum()))
    return dict(row=take,x=x,y=y,hist50=hist50,hist100=hist100),meta


def main():
    p=argparse.ArgumentParser();p.add_argument('--batch',type=int);p.add_argument('--pilot',type=int)
    a=p.parse_args();protocol=json.loads((OUT/'protocol.json').read_text());start=time.perf_counter()
    sources=[s for s in protocol['sources'] if s['index']==a.pilot] if a.pilot is not None else protocol['sources'][a.batch::protocol['coordinate_batches']]
    if a.pilot is not None:
        initialize();results=[work(s) for s in sources]
    else:
        with mp.get_context('spawn').Pool(4,initializer=initialize) as pool:results=pool.map(work,sources)
    data={k:np.concatenate([d[k] for d,_ in results]) for k in ['row','x','y']}
    data.update({k:np.sum([d[k] for d,_ in results],axis=0) for k in ['hist50','hist100']})
    label=f'pilot_{a.pilot}' if a.pilot is not None else f'coordinates_{a.batch}'
    CACHE.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(CACHE/f'{label}.npz',**data)
    report=dict(files=[m for _,m in results],wall_s=time.perf_counter()-start,new_fits=0,new_model_forwards=0,branches=BRANCHES)
    (OUT/f'{label}.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
