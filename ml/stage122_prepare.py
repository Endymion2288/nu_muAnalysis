"""Freeze the full existing response cohort before reading new response features."""
import io
import json
import tarfile
import zlib
from pathlib import Path

import numpy as np


def main():
    root=Path(__file__).resolve().parents[1];out=root/'workbook/stage122_energy_ml';cache=root/'ntuples/energy_ml_stage122'
    p=json.loads((root/'workbook/stage119_energy_ml/production_contract_summary.json').read_text())
    with np.load(root/'ntuples/energy_ml_stage119/old_input.npz') as z:old={k:z[k] for k in ['incoming','role','run','eventID']}
    roles={};isolated=set()
    for incoming,role,run,event in zip(old['incoming'],old['role'],old['run'],old['eventID']):
        key=tuple(incoming)
        if role:roles[key]=max(roles.get(key,0),int(role))
        else:isolated.add((int(run),int(event)))
    sources=[];arrays=[];support=[]
    for req in p['requests']:
        s=req['source'];i=s['index']
        if s['kind']=='expansion':continue
        with tarfile.open(root/f'ntuples/energy_ml_stage119/production_{i}.tar.gz') as t:
            assert t.extractfile('result/exitcode.txt').read().strip()==b'0'
            with np.load(io.BytesIO(t.extractfile('result/selected.npz').read())) as z:a={k:z[k] for k in z.files if k!='metadata_json'}
        a['role']=np.array([0 if (int(run),int(event)) in isolated else roles.get(tuple(inc),1+(zlib.crc32(np.asarray(inc,dtype='<f8').tobytes()+b'stage122')%100>=70)+(zlib.crc32(np.asarray(inc,dtype='<f8').tobytes()+b'stage122')%100>=85)) for inc,run,event in zip(a['incoming'],a['run'],a['eventID'])],dtype='int8')
        a['source_index']=np.full(len(a['role']),i);a['probability']=np.full(len(a['role']),s['file_inclusion_probability'])
        a['environment']=np.full(len(a['role']),'nominal' if s['kind']=='nominal' else 'JEFF' if s['run']<=200112 else 'ENDF')
        a['component']=np.full(len(a['role']),s['component']);arrays.append(a)
        path=Path(req['rdo']);first,last=map(int,s['segment'].split('-'))
        stem=path.name.split(f'-{s["run"]}-')[0]+f'-{s["run"]}-'
        hits=[str(path.parents[2]/'sim'/s['tag']/f'{stem}{j:05}-{s["tag"]}-HITS.root') for j in range(first,last+1)]
        # A final merged RDO may contain only one partially filled last HITS.
        # Actual per-file entry totals are verified by the native reader.
        hits=[h for h in hits if Path(h).is_file()]
        cases=[dict(entry=int(e),event=int(ev),incoming=inc.tolist()) for e,ev,inc in zip(a['input_entry'],a['eventID'],a['incoming'])]
        assert cases and [c['entry'] for c in cases]==sorted(set(c['entry'] for c in cases))
        sources.append(dict(run=s['run'],source_index=i,environment=str(a['environment'][0]),component=s['component'],rdo=str(path),hits=hits,cases=cases,parent_N=req['parent_N'],file_probability=s['file_inclusion_probability']))
        for role in [0,1,2,3]:
            for low,high in [(50,100),(100,200),(200,float('inf'))]:
                m=(a['role']==role)&(a['truth_E_GeV']>=low)&(a['truth_E_GeV']<high)
                support.append(dict(index=i,environment=str(a['environment'][0]),component=s['component'],role=role,low_GeV=low,high_GeV=high,N=int(m.sum()),incoming=len(np.unique(a['incoming'][m],axis=0))))
    shared=set.intersection(*(set(a) for a in arrays));d={k:np.concatenate([a[k] for a in arrays]) for k in shared}
    np.savez_compressed(cache/'cohort_input.npz',**d)
    contract=json.loads((out/'protocol.json').read_text());contract.update(database_instance='OFLP200',global_tag='OFLCOND-FASER-06',sources=sources,pilot_replicas=[],scope='all 27 already frozen nominal/JEFF/ENDF sources from Stage119; all selected parents retained incl quarantine; preselection denominator reused from Stage119, no independent-N or blind claim',
        resources=dict(jobs=27,cpus_each=2,memory_MB=6000,wall_s_each=1800,aggregate_CPU_s=18000,final_bytes=60000000),
        sampling='Stage119 uniform 3 sources/run with recorded probability; within chosen source all selected parents. No effect-dependent additions; original failed-parent counts retained.',
        roles='Original quarantined run/event stays excluded; all known original incoming retain highest original active role. Previously developed response-only incoming assigned crc32 <70/<85/rest before new waveform. Shared incoming across environments never crosses roles; no Stage119 expansion/reserved used.',
        learning=dict(arms=['A','B','C','D'],target='continuous log E_GeV',policy='Stage87 fixed3 seeds/400round/depth5/eta.04/minchild20/lambda10/hist CPU; same capacity; train only, one cal incoming-weighted offset; no tuning or winner',
                      A='original typed62',B='A +3channels:6signed ADC integral bins, baseline mean/rms, saturation fraction, availability; fixed first20baseline. 0-40/40-80/80-160/160-320/320-640/640-1200ns; no weak/saturation veto',
                      C='B +actual sensitive deposit energy histogram [-20,0,40,80,160,320,640,1200)ns perchannel, log1p(MeV), in-window log1p(total MeV) and in-window zero bit',
                      D='C +sensitive deposits time<-20 and [1200,1e4),[1e4,1e6),>=1e6ns; log1p(MeV), actual persisted history only; producer termination not yet certified'),
        inference='Mechanism comparison only; 500 paired incoming draws within component, full eight layers and actual tails. Source/refit/research/system uncertainty excluded. Report insufficient support rather than promotion.',
        environment_2x2_gate='At least100 train incoming and50 evaluation incoming in EACH low bin per environment; otherwise no2x2 fits',
        conditional_likelihood='Only after B/A paired upper95<1 for both low bins on heldout response roles and actual tails not deteriorated; otherwise unresolved/unsupported, no automatic grid')
    (out/'cohort_contract.json').write_text(json.dumps(contract,indent=2)+'\n');(out/'prepared_support.json').write_text(json.dumps(support,indent=2)+'\n')
    summary=dict(sources=len(sources),selected=len(d['role']),roles={str(k):int((d['role']==k).sum()) for k in [0,1,2,3]},low_support={str(k):[int(((d['role']==k)&(d['truth_E_GeV']>=lo)&(d['truth_E_GeV']<hi)).sum()) for lo,hi in [(50,100),(100,200)]] for k in [0,1,2,3]})
    (out/'prepared_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary,flush=True)


if __name__=='__main__':main()
