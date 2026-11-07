"""Disjoint bounded complete-EVNT eligibility census, no simulation or prediction."""
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np
import ROOT
from AthenaPython import PyAthena
from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
from CalypsoConfiguration.AllConfigFlags import initConfigFlags
from CalypsoConfiguration.MainServicesConfig import MainServicesCfg

OUT=Path('workbook/stage129_energy_ml')
index=int(sys.argv[1]);plan=json.loads((OUT/'evntrange_protocol.json').read_text());task=plan['tasks'][index]
known=set()
for path in ['ntuples/energy_ml_stage119/old_input.npz','ntuples/energy_ml_stage119/curve_input.npz']:
    with np.load(path) as z:known.update(tuple(x) for x in z['incoming'].astype('float32'))
records=[];counts={};scanned=0;tick=time.perf_counter();cpu=time.process_time()


class Snapshot(PyAthena.Alg):
    def execute(self):
        global scanned
        entry=task['skip']+scanned;scanned+=1
        store=PyAthena.py_svc('StoreGateSvc');events=store.retrieve('McEventCollection','BeamTruthEvent');event=events[0]
        nu=[];mu=[]
        for p in event.particles():
            if abs(p.pid())==14 and p.status()==4:nu.append(p)
            if abs(p.pid())==13 and p.status()==1:mu.append(p)
        if len(nu)!=1 or len(mu)!=1:return PyAthena.StatusCode.Success
        p=nu[0].momentum();m=mu[0].momentum();pos=nu[0].end_vertex().position()
        E=p.e()/1000;pz=m.pz()/1000;y=1-m.e()/p.e();key=tuple(np.asarray([nu[0].pid(),p.px(),p.py(),p.pz()],dtype='float32'))
        if key in known:counts['old_overlap']=counts.get('old_overlap',0)+1;return PyAthena.StatusCode.Success
        fid=np.hypot(pos.x(),pos.y())<100 and ((-3000<pos.z()<-1950) or (-1769.65<pos.z()<-1619.65))
        if not fid or pz<=50:return PyAthena.StatusCode.Success
        layer='E50_100' if 50<=E<100 else 'E100_200' if 100<=E<200 else 'lowpz_highE' if 50<=pz<100 and E>=200 else 'high_y' if y>=.8 else 'transition' if 200<=E<800 else 'highE'
        counts[layer]=counts.get(layer,0)+1
        # All low/hard candidates retained; a fixed entry modulus thins large
        # natural controls, with explicit probabilities (not fitted by risk).
        modulus=1 if layer in ['E50_100','E100_200','lowpz_highE','high_y'] else 8
        if entry%modulus:return PyAthena.StatusCode.Success
        particles=[]
        for q in event.particles():
            qm=q.momentum();pv=q.production_vertex();ev=q.end_vertex()
            particles.append(dict(id=int(q.id()),pdg=int(q.pid()),status=int(q.status()),p=[qm.px(),qm.py(),qm.pz(),qm.e()],mass=q.generated_mass(),production_vertex=int(pv.id()) if pv else None,end_vertex=int(ev.id()) if ev else None))
        vertices=[]
        for v in event.vertices():
            vp=v.position();vertices.append(dict(id=int(v.id()),position=[vp.x(),vp.y(),vp.z(),vp.t()],incoming=[int(q.id()) for q in v.particles_in()],outgoing=[int(q.id()) for q in v.particles_out()]))
        records.append(dict(EVNT=task['EVNT'],entry=entry,incoming=list(key),source_index=task['source_index'],stratum=layer,inclusion_probability=1/modulus,truth_E_GeV=E,truth_mu_pz_GeV=pz,truth_mu_theta_rad=float(np.arctan2(np.hypot(m.px(),m.py()),m.pz())),full_generator_record=dict(event_number=event.event_number(),momentum_unit=str(event.momentum_unit()),length_unit=str(event.length_unit()),weights=list(event.weights()),particles=particles,vertices=vertices)))
        return PyAthena.StatusCode.Success


flags=initConfigFlags();flags.Input.Files=[task['EVNT']];flags.Input.isMC=True;flags.Input.ProjectName='data21';flags.IOVDb.DatabaseInstance='OFLP200';flags.GeoModel.FaserVersion='FASERNU-04';flags.IOVDb.GlobalTag='OFLCOND-FASER-06';flags.Concurrency.NumThreads=0;flags.Exec.SkipEvents=task['skip'];flags.Exec.MaxEvents=task['N'];flags.Exec.OutputLevel=4;flags.lock()
a=MainServicesCfg(flags);a.merge(PoolReadCfg(flags));a.addEventAlgo(Snapshot('Stage129EVNTCensus'));assert a.run(task['N']).isSuccess()
# Convert numpy float32 scalar keys before JSON, with exact float32 values.
for r in records:r['incoming']=[float(x) for x in r['incoming']]
(OUT/f'evntrange_{index}.json').write_text(json.dumps(dict(task=task,scanned=scanned,counts=counts,records=records,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()),independence='EVNTentry/full record/incoming proxy; original GENIE randomseed and unrecorded production history not certified'),separators=(',',':'))+'\n')
