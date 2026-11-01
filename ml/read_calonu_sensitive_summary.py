#!/usr/bin/env python3
"""HITS-only native conversion and four-channel aggregation; no waveforms or reconstruction."""
import argparse
import ctypes
import json
import resource
import time
from pathlib import Path
import numpy as np


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--request',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    p.add_argument('--include',required=True); p.add_argument('--limit',type=int)
    a=p.parse_args(); request=json.loads(a.request.read_text()); tick,cpu=time.perf_counter(),time.process_time()
    import ROOT
    ROOT.gSystem.Load('libFaserCaloSimEventTPCnv.so'); ROOT.gSystem.Load('libFaserCaloSimEvent.so')
    ROOT.gInterpreter.AddIncludePath(a.include)
    assert ROOT.gInterpreter.Declare('''
#define HEPMC3 1
#include "FaserCaloSimEventTPCnv/CaloHits/CaloHitCollectionCnv_p1a.h"
#include "GaudiKernel/MsgStream.h"
#include "AthenaKernel/ExtendedEventContext.h"
#include "GaudiKernel/ThreadLocalContext.h"
#include <vector>
std::vector<double> SummarizeCaloNuHits(const CaloHitCollection_p1a* p, const std::vector<int>& ids) {
    EventContext ctx;
    Atlas::setExtendedEventContext(ctx, Atlas::ExtendedEventContext(nullptr,0));
    Gaudi::Hive::setCurrentContext(ctx);
    MsgStream log(nullptr,"CaloNuSummary");
    CaloHitCollectionCnv_p1a cnv;
    auto transient=cnv.createTransient(p,log);
    std::vector<double> out(9,0.);
    for (const auto& h:*transient) {
        int k=0;
        while (k<4 && h.identify()!=ids[k]) ++k;
        if (k==4) { out[8]+=1.; continue; }
        out[k]+=h.energyLoss(); out[k+4]+=1.;
    }
    delete transient;
    return out;
}
''')
    repo=Path(__file__).resolve().parents[1]
    conditions=json.loads((repo/'workbook/stage37_energy_ml/conditions_audit.json').read_text())
    cable=next(r['rows'] for r in conditions['records'] if r['label']=='MC100049_archived')
    ids=[1+(r['payload']['row']<<1)+(r['payload']['module']<<3) for r in sorted(cable,key=lambda r:r['channel'])]
    assert sorted(ids)==[1,3,9,11]
    def member(obj,name,typ):
        cls=ROOT.TClass.GetClass(type(obj).__cpp_name__); offset=cls.GetDataMember(name).GetOffset(); assert offset>=0
        address=ROOT.addressof(obj)+offset
        types={'unsigned int':ctypes.c_uint,'unsigned long long':ctypes.c_ulonglong,'int':ctypes.c_int,'float':ctypes.c_float}
        return types[typ].from_address(address).value if typ in types else ROOT.bind_object(address,typ)
    schemas=[]; opened={}
    def tree(path):
        if path not in opened:
            f=ROOT.TFile.Open(path); assert f and not f.IsZombie(),path
            t=f.Get('CollectionTree'); t.SetBranchStatus('*',0)
            for branch in ['CaloHitCollection_p1a_CaloNuHits','xAOD::EventAuxInfo_v3_EventInfoAux.','McEventCollection_p6_BeamTruthEvent']:
                assert t.GetBranch(branch),(path,branch)
                t.SetBranchStatus(branch,1); name=t.GetBranch(branch).GetClassName(); cls=ROOT.TClass.GetClass(name)
                saved=[int(s.GetCheckSum()) for s in f.GetStreamerInfoList() if s.GetName()==name]
                assert int(cls.GetCheckSum()) in saved,(path,name,'layout checksum differs')
                schemas.append(dict(file=path,branch=branch,loaded=int(cls.GetCheckSum()),saved=saved))
            assert t.GetEntries()==request['hits_events_per_file']
            opened[path]=(f,t)
        return opened[path][1]
    cases=request['cases'][:a.limit]; energy=[]; count=[]
    for case in cases:
        t=tree(case['hits_file']); assert t.GetEntry(case['hits_entry'])>0
        info=getattr(t,'xAOD::EventAuxInfo_v3_EventInfoAux.')
        assert (member(info,'runNumber','unsigned int'),member(info,'eventNumber','unsigned long long'))==(request['run'],case['fingerprint']['eventID'])
        event=getattr(t,'McEventCollection_p6_BeamTruthEvent')
        particles=member(event,'m_genParticles','std::vector<GenParticle_p6>')
        pdg,px,py,pz=case['phys_neutrino_signature']
        assert any(member(q,'m_pdgId','int')==pdg and np.allclose([member(q,'m_'+k,'float') for k in ['px','py','pz']],[px,py,pz],rtol=2e-6,atol=.001) for q in particles),case
        v=np.asarray(list(ROOT.SummarizeCaloNuHits(t.CaloHitCollection_p1a_CaloNuHits,ids)))
        assert v[8]==0 and np.isfinite(v).all() and (v>=0).all()
        energy.append(v[:4]); count.append(v[4:8])
    for f,t in opened.values(): f.Close()
    metadata=dict(index=request['index'],events=len(cases),files=len(opened),channel_hit_ids=ids,
                  locate_wall_s=request.get('locate_wall_s'),wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
                  peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                  identity_checked='PHYS fingerprint + HITS run/event + independent neutrino pdg/three-momentum',schemas=schemas)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(a.output,cache_row=np.array([c['cache_row'] for c in cases]),
                        eventID=np.array([c['fingerprint']['eventID'] for c in cases]),
                        hit_energy_MeV=np.array(energy),hit_count=np.array(count,dtype=np.int32),
                        cases_json=np.array(json.dumps(cases)),metadata_json=np.array(json.dumps(metadata)))
    print(json.dumps({k:v for k,v in metadata.items() if k!='schemas'}),flush=True)

if __name__=='__main__': main()
