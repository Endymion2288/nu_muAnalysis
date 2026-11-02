#!/usr/bin/env python3
"""Bounded diagnostic of native SCT HITS versus the copy embedded in RDO."""
import argparse
import json
from pathlib import Path
import resource
import tarfile
import time

import numpy as np
import ROOT
from analyze_tracker_noise import read_result

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
start,cpu=time.perf_counter(),time.process_time()
ROOT.gSystem.Load('libTrackerSimEventTPCnv.so')
assert ROOT.gInterpreter.Declare('''
#define HEPMC3 1
#include "TrackerSimEventTPCnv/TrackerHits/FaserSiHitCollectionCnv_p3a.h"
#include "AthenaKernel/ExtendedEventContext.h"
#include "GaudiKernel/ThreadLocalContext.h"
std::vector<double> Stage53DecodedHits(const FaserSiHitCollection_p3a* p) {
    EventContext context;
    Atlas::setExtendedEventContext(context,Atlas::ExtendedEventContext(nullptr,0));
    Gaudi::Hive::setCurrentContext(context);
    MsgStream log(nullptr,"Stage53DecodedHits");
    FaserSiHitCollectionCnv_p3a converter;
    auto transient=converter.createTransient(p,log);
    std::vector<double> values;
    for (const auto& hit : *transient) {
        auto a=hit.localStartPosition(),b=hit.localEndPosition();
        values.insert(values.end(),{double(hit.identify()),hit.energyLoss(),hit.meanTime(),
            a.x(),a.y(),a.z(),b.x(),b.y(),b.z()});
    }
    delete transient;
    return values;
}
''')
repo=Path(__file__).resolve().parents[1]
sample=read_result(repo/'ntuples/energy_ml_stage53','sample.json')
row=sample['sources'][0]
with tarfile.open(repo/'ntuples/energy_ml_stage53/pre_correction_nominal.tar.gz') as archive:
    nominal=json.load(archive.extractfile('nominal_0.json'))
# Result-selected diagnostics explain program behavior only, never population rates.
diagnostics=([r for r in nominal['records'] if not r['rdo_p4_exact_equal']][:2]
             +[r for r in nominal['records'] if r['rdo_p4_exact_equal']][:2])
opened={}
branch='FaserSiHitCollection_p3a_SCT_Hits'
fields=['m_hit1_meanTime','m_hit1_x0','m_hit1_y0','m_hit1_z0','m_hit1_theta','m_hit1_phi',
        'm_nHits','m_hitEne_2b','m_hitLength_2b','m_dTheta','m_dPhi','m_hitEne_4b',
        'm_hitLength_4b','m_barcode','m_mcEvtIndex','m_evtColl','m_nBC','m_id','m_nId']


def read(path,entry):
    if path not in opened:
        file=ROOT.TFile.Open(path);assert file and not file.IsZombie()
        tree=file.Get('CollectionTree');tree.SetBranchStatus('*',0);tree.SetBranchStatus(branch,1)
        opened[path]=(file,tree)
    file,tree=opened[path]
    assert tree.GetEntry(entry)>0
    persistent=getattr(tree,branch)
    encoded={name:list(getattr(persistent,name)) for name in fields}
    decoded=np.asarray(list(ROOT.Stage53DecodedHits(persistent))).reshape(-1,9)
    return encoded,decoded


results=[]
for record in diagnostics:
    entry=record['entry'];stem=Path(row['input_rdo']).name.split('-00000-00004-')[0]
    hits=str(Path(row['input_rdo']).parent.parent.parent/'sim/s0015'/f'{stem}-{entry//10000:05}-HITS.root')
    left,x=read(hits,entry%10000);right,y=read(row['input_rdo'],entry)
    equal={name:left[name]==right[name] for name in fields}
    aligned=x.shape==y.shape and np.array_equal(x[:,0],y[:,0])
    results.append(dict(source=0,entry=entry,rdo_replay_exact=record['rdo_p4_exact_equal'],input_hits=hits,
        encoded_fields_equal=equal,decoded_hits_HITS=len(x),decoded_hits_RDO=len(y),decoded_id_order_equal=bool(aligned),
        decoded_exact_equal=bool(np.array_equal(x,y)),
        max_abs_delta_columns=np.max(abs(y-x),axis=0).tolist() if aligned else None))
args.output.write_text(json.dumps(dict(diagnostic_only=True,records=results,
    columns=['identifier','energy_MeV','time_ns','start_x_mm','start_y_mm','start_z_mm','end_x_mm','end_y_mm','end_z_mm'],
    wall_s=time.perf_counter()-start,cpu_s=time.process_time()-cpu,
    peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
    ROOT_all_files_bytes_read=int(ROOT.TFile.GetFileBytesRead())),indent=2)+'\n')
for file,tree in opened.values():file.Close()
