"""Batch-only linked HITS timing and controlled official waveform digitization."""
import argparse
import gzip
import json
import resource
import time
import zlib
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=int,required=True)
    p.add_argument('--events',type=int)
    p.add_argument('--contract',default='workbook/stage122_energy_ml/protocol.json')
    p.add_argument('--output',required=True)
    a=p.parse_args();plan=json.loads(Path(a.contract).read_text());source=plan['sources'][a.source]
    cases=source.get('cases');entries=[c['entry'] for c in cases] if cases else None
    import ROOT
    # Commit the build macro before ROOT rootmap/autoparse starts a separate
    # transaction for an interface included by the helper below.
    assert ROOT.gInterpreter.Declare('#define HEPMC3 1\n')
    if cases:
        counts=[];valid=[]
        for path in source['hits']:
            f=ROOT.TFile.Open(path);assert f and not f.IsZombie(),path
            tree=f.Get('CollectionTree');n=int(tree.GetEntries()) if tree else 0
            counts.append(dict(input=path,events=n));f.Close()
            if n:valid.append(path)
        assert sum(c['events'] for c in counts)==source['parent_N'],(counts,source['parent_N'])
        source=dict(source,hits=valid,hits_metadata_counts=counts)
    from CalypsoConfiguration.AllConfigFlags import initConfigFlags
    from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
    from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
    from AthenaConfiguration.ComponentFactory import CompFactory
    from FaserGeoModel.ScintGMConfig import ScintGeometryCfg
    from WaveformConditionsTools.WaveformDigitizationConfig import WaveformDigitizationCfg
    from AthenaPython import PyAthena
    flags=initConfigFlags();flags.Input.Files=source['hits'] if isinstance(source['hits'],list) else [source['hits']];flags.Input.isMC=True
    flags.IOVDb.DatabaseInstance='OFLP200'
    flags.Input.ProjectName='data20'
    flags.GeoModel.FaserVersion=plan['geometry'];flags.IOVDb.GlobalTag=plan['global_tag']
    for detector in ['VetoNu','Veto','Trigger','Preshower']:setattr(flags.Detector,'Geometry'+detector,True)
    flags.Concurrency.NumThreads=0;flags.Exec.OutputLevel=4
    flags.Exec.MaxEvents=a.events or (len(entries) if cases else source['events'])
    flags.Exec.SkipEvents=entries[0] if cases else source.get('entry_start',0);flags.lock()
    acc=MainServicesCfg(flags);acc.merge(PoolReadCfg(flags));acc.merge(ScintGeometryCfg(flags))
    acc.merge(WaveformDigitizationCfg(flags))
    from WaveformConditionsTools.WaveformCableMappingConfig import WaveformCableMappingCfg
    acc.merge(WaveformCableMappingCfg(flags))
    acc.addPublicTool(CompFactory.WaveformCableMappingTool('Stage122Cable'))
    for detector in ['VetoNu','Preshower']:
        acc.addPublicTool(CompFactory.WaveformDigitisationTool('Stage122'+detector))
        acc.addPublicTool(CompFactory.WaveformDigiConditionsTool('Stage122Cond'+detector,Detector=detector))
    if plan.get('reconstruct'):
        from WaveformConditionsTools.WaveformTimingConfig import WaveformTimingCfg
        acc.merge(WaveformTimingCfg(flags))
        for detector in ['VetoNu','Preshower','Veto']:
            acc.addPublicTool(CompFactory.WaveformReconstructionTool('Stage122Rec'+detector,FitWindowWidth=100,
                BaselineSampleHi=60 if detector!='Veto' else 75))
    rows=[];tick=time.perf_counter();cpu=time.process_time()
    class Snapshot(PyAthena.Alg):
        def initialize(self):
            import StoreGateBindings.Bindings
            for library in ['libWaveRawEvent.so','libScintSimEvent.so']:
                assert ROOT.gSystem.Load(library)>=0,library
            assert ROOT.gInterpreter.Declare(Path('ml/stage122_response.hxx').read_text())
            if plan.get('reconstruct'):
                assert ROOT.gSystem.Load('libxAODFaserWaveform.so')>=0
                assert ROOT.gInterpreter.Declare(Path('ml/stage122_reconstruct.hxx').read_text())
            self.root=ROOT;self.centers={};self.conditions={}
            if cases:
                from stage122_saved import SavedWaveforms
                self.saved=SavedWaveforms(ROOT,source['rdo'],['VetoNu','Preshower','Veto'] if plan.get('reconstruct') else None)
            return PyAthena.StatusCode.Success
        def execute(self):
            s=PyAthena.py_svc('StoreGateSvc');info=s.retrieve('xAOD::EventInfo','EventInfo')
            run,event=int(info.runNumber()),int(info.eventNumber())
            row=dict(entry=entries[len(rows)] if cases else len(rows)+source.get('entry_start',0),run=run,event=event,detectors={})
            if cases:
                case=cases[len(rows)];assert (run,event)==(source['run'],case['event'])
                saved=self.saved.read(row['entry'],run,event)
                if plan.get('reconstruct'):
                    row['original_reconstructed']={k:self.reconstruct(k,w) for k,w in saved.items()}
                    row['veto_cable_map']=[[int(x) for x in rr] for rr in self.root.Stage122CableMap('Veto')]
            truth=s.retrieve('McEventCollection','TruthEvent');assert truth.size()==1
            nu=[q for q in truth[0].particles() if abs(int(q.pid())) in [12,14,16] and int(q.status())==4]
            if len(nu)==1:
                q=nu[0];v=q.end_vertex();m=q.momentum()
                row.update(E_GeV=float(m.e())/1000,incoming=[int(q.pid())]+[float(getattr(m,k)()) for k in ['px','py','pz']])
                if cases:
                    import numpy as np
                    np.testing.assert_array_equal(np.asarray(row['incoming'],dtype='float32'),np.asarray(case['incoming'],dtype='float32'))
                if v:
                    row['vertex_mm']=[float(getattr(v.position(),k)()) for k in ['x','y','z']]
                    mu=[x for x in v.particles_out() if int(x.pid())==int(q.pid())*13/14]
                    if len(mu)==1:row['y']=1-float(mu[0].momentum().e())/float(m.e())
            for detector in ['VetoNu','Preshower']:
                cable=[[int(x) for x in rr] for rr in self.root.Stage122CableMap(detector)]
                channels={r[0]:r for r in cable};generated_channels={r[1]:r[0] for r in cable}
                hits=s.retrieve('ScintHitCollection',detector+'Hits');cond=list(self.root.Stage122Conditions(detector))
                self.conditions[detector]=cond;records=[]
                for h in hits:
                    station,plate=int(h.getStation()),int(h.getPlate());key=f'{detector}:{station}:{plate}'
                    if key not in self.centers:self.centers[key]=float(self.root.Stage122Z(detector,station,plate))
                    t=float(h.meanTime())-self.centers[key]/299.792458
                    if detector=='Preshower':t-=cond[2]*(float(h.localStartPosition().y())+float(h.localEndPosition().y()))/2
                    records.append([station,plate,int(h.getIdentifier().get_compact()),t,float(h.energyLoss())])
                replicas=[]
                for replica in plan['pilot_replicas']:
                    # Stable transport key, not Python hash(), no assumption of original producer seeds.
                    seed=zlib.crc32(f'stage122:{run}:{event}:{detector}:{replica}'.encode()) or 1
                    if replicas and replica==replicas[0]['replica']:
                        self.root.Stage122Restore(detector,replicas[0]['before'])
                    else:self.root.Stage122Seed(detector,seed)
                    before=str(self.root.Stage122State(detector))
                    waves=[[int(x) for x in w] for w in self.root.Stage122Digitize(detector,hits)]
                    replicas.append(dict(replica=replica,seed=seed,before=before,after=str(self.root.Stage122State(detector)),waves=waves))
                    if plan.get('reconstruct'):
                        # The digitizer also generates unconnected PMTs. The
                        # production algorithm rejects these after consuming
                        # their noise stream. Retain the exact persisted native
                        # readout identifiers, without merging different PMTs.
                        mapping={w['channel']:w for w in saved[detector]}
                        assert len(mapping)==len(saved[detector])
                        assert set(mapping)<=set(channels)
                        ww=[]
                        for w in waves:
                            channel=generated_channels.get(w[0]>>32)
                            # Current cabling also includes newer PMTs (24/25)
                            # absent from this historical readout. The frozen
                            # experiment varies its original channel bank only.
                            if channel not in mapping:continue
                            actual=mapping[channel]
                            ww.append(dict(id32=actual['id32'],channel=actual['channel'],adc=w[1:]))
                        assert {w['channel'] for w in ww}==set(mapping),(run,event,detector,
                            list(mapping),cable,[w[0]>>32 for w in waves],len(records),'readout coverage')
                        replicas[-1]['reconstructed']=self.reconstruct(detector,ww)
                if len(replicas)>1:assert replicas[0]==replicas[1],(run,event,detector,'replay mismatch')
                row['detectors'][detector]=dict(hits=records,replicas=replicas)
                if cases:
                    import numpy as np
                    timing=[];edges=[-np.inf,-20,0,40,80,160,320,640,1200,1e4,1e6,np.inf]
                    for plate in [0,1]:
                        rr=[h for h in records if h[0]==0 and h[1]==plate]
                        timing.append(dict(station=0,plate=plate,hits=len(rr),
                            energy_MeV=np.histogram([h[3] for h in rr],bins=edges,weights=[h[4] for h in rr])[0].tolist(),
                            min_time_ns=min((h[3] for h in rr),default=None),max_time_ns=max((h[3] for h in rr),default=None)))
                    assert sum(t['hits'] for t in timing)==len(records),(detector,'unmapped hit plate')
                    row['detectors'][detector].pop('hits');row['detectors'][detector]['timing']=timing
                    # Historical persisted IDs use an older field packing.
                    # Native hardware channel is the stable join to the actual
                    # current MC cable-map element; never decode old IDs with
                    # the newly loaded expanded dictionary.
                    for wave in saved[detector]:wave['station_plate']=channels[wave['channel']][2:]
                    row['detectors'][detector]['cable_map']=cable
                    row['detectors'][detector]['saved']=saved[detector]
            rows.append(row)
            if len(rows)%20==0:print('STAGE122_PROGRESS',len(rows),flush=True)
            return PyAthena.StatusCode.Success
        def reconstruct(self,detector,waves):
            return [[float(x) for x in rr] for rr in self.root.Stage122Reconstruct(detector,
                [w['channel'] for w in waves],[w['id32'] for w in waves],[x for w in waves for x in w['adc']])]
    reader=Snapshot('Stage122Snapshot');acc.addEventAlgo(reader)
    if cases:
        # Athena POOL selector ranges are 1-based inclusive, already validated in Stage119.
        ranges=[f'{left+2}-{right}' for left,right in zip(entries,entries[1:]) if right>left+1]
        if ranges:acc.getService('EventSelector').SkipEventRanges=','.join(ranges)
    assert acc.run().isSuccess()
    assert len(rows)==flags.Exec.MaxEvents,(len(rows),flags.Exec.MaxEvents)
    output=Path(a.output);output.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(output,'wt',compresslevel=1) as f:
        json.dump(dict(source={k:v for k,v in source.items() if k!='cases'},events=rows,centers_z_mm=reader.centers,conditions=reader.conditions,
                       configuration=dict(database_instance=str(flags.IOVDb.DatabaseInstance),geometry=str(flags.GeoModel.FaserVersion),global_tag=str(flags.IOVDb.GlobalTag),runtime_commit='d32b0ff3'),
                       readout_schema=reader.saved.schemas if cases else [],
                       conditions_order=['baseline_mean','baseline_rms','preshower_time_slope','cb_alpha','cb_n','cb_sigma','cb_mean','cb_norm'],
                       CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
                       RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                       read_bytes=int(reader.root.TFile.GetFileBytesRead())),f,separators=(',',':'))


if __name__=='__main__':main()
