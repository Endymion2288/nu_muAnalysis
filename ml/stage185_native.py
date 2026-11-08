"""One Athena process, fixed three original sources, historical physical-PMT join."""
import csv,json,os,resource,sys,time
from pathlib import Path
import numpy as np
import ROOT
OUT=Path('workbook/stage185_energy_ml');plan=json.loads((OUT/'protocol.json').read_text())
audit=len(sys.argv)>1 and sys.argv[1]=='audit';label='audit_native' if audit else 'batch'
cpu=time.process_time();tick=time.perf_counter()
sources=plan['sources'][:1] if audit else plan['sources'];cases=[];counts=[];offset=0
for source in sources:
    source_counts=[]
    for path in source['hits']:
        f=ROOT.TFile.Open(path);assert f and not f.IsZombie(),path
        tree=f.Get('CollectionTree');source_counts.append(dict(path=path,N=int(tree.GetEntries()) if tree else 0));f.Close()
    assert sum(r['N'] for r in source_counts)==source['parent_N']
    counts+=source_counts
    cases += [dict(c,source_index=source['index'],global_entry=offset+c['entry']) for c in source['cases']]
    offset+=source['parent_N']
entries=[c['global_entry'] for c in cases];assert entries==sorted(set(entries))
assert ROOT.gInterpreter.Declare('#define HEPMC3 1\n')
from CalypsoConfiguration.AllConfigFlags import initConfigFlags
from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
from AthenaConfiguration.ComponentFactory import CompFactory
from AthenaPython import PyAthena
from FaserGeoModel.ScintGMConfig import ScintGeometryCfg
from EcalGeoModel.EcalGeoModelConfig import EcalGeometryCfg
from WaveformConditionsTools.WaveformDigitizationConfig import WaveformDigitizationCfg
from WaveformConditionsTools.WaveformCableMappingConfig import WaveformCableMappingCfg
from WaveformConditionsTools.WaveformTimingConfig import WaveformTimingCfg
flags=initConfigFlags();flags.Input.Files=[r['path'] for r in counts if r['N']]
flags.Input.isMC=True;flags.Input.ProjectName='data20';flags.IOVDb.DatabaseInstance='OFLP200'
flags.GeoModel.FaserVersion=plan['geometry'];flags.IOVDb.GlobalTag=plan['global_tag']
for d in ['VetoNu','Veto','Trigger','Preshower','Ecal']:setattr(flags.Detector,'Geometry'+d,True)
flags.Concurrency.NumThreads=0;flags.Exec.MaxEvents=len(cases);flags.Exec.SkipEvents=entries[0];flags.Exec.OutputLevel=4;flags.lock()
acc=MainServicesCfg(flags);acc.merge(PoolReadCfg(flags));acc.merge(ScintGeometryCfg(flags));acc.merge(EcalGeometryCfg(flags))
acc.merge(WaveformDigitizationCfg(flags));acc.merge(WaveformCableMappingCfg(flags));acc.merge(WaveformTimingCfg(flags))
acc.addPublicTool(CompFactory.WaveformCableMappingTool('Stage122Cable'))
detectors=['Calo','VetoNu','Veto','Trigger','Preshower']
for d in detectors:
    acc.addPublicTool(CompFactory.WaveformDigiConditionsTool('Stage122Cond'+d,Detector=d))
    options={} if d=='Calo' else dict(FitWindowWidth=100,BaselineSampleHi=60 if d in ['VetoNu','Preshower'] else 75)
    acc.addPublicTool(CompFactory.WaveformReconstructionTool('Stage129Rec'+d,**options))
historical=json.loads((OUT/'identity_summary.json').read_text())['channels']
physical={(r['detector'],r['channel']):(r['station'],r['plate'],r['pmt']) for r in historical}
expected={'Calo':[0,1,2,3],'VetoNu':[4,5],'Veto':[14,6,7],'Trigger':[8,9,10,11],'Preshower':[12,13]}
rows=[];identities=[];literal=[];mapping_records=[];conditions_records=[];event_resources=[]

class Reader(PyAthena.Alg):
    def initialize(self):
        import StoreGateBindings.Bindings
        for lib in ['libIdentifier.so','libScintIdentifier.so','libScintReadoutGeometry.so','libFaserCaloSimEvent.so',
            'libCaloReadoutGeometry.so','libWaveRawEvent.so','libScintSimEvent.so','libxAODFaserWaveform.so','libIdDict.so','libIdDictParser.so']:
            assert ROOT.gSystem.Load(lib)>=0,lib
        for header in ['stage138_response.hxx','stage144_ecal.hxx','stage129_official.hxx','stage141_analog.hxx',
            'stage184_window.hxx','stage185_mapping.hxx','stage185_identity.hxx']:
            assert ROOT.gInterpreter.Declare(Path('ml',header).read_text()),header
        self.decoder=ROOT.Stage185Identity(str(OUT/'IdDict_6d6ab70b.xml'));self.readers={};self.integrators={}
        return PyAthena.StatusCode.Success

    def execute(self):
        begin=time.process_time();wall=time.perf_counter();case=cases[len(identities)];source=next(s for s in sources if s['index']==case['source_index'])
        if not identities:self.startup_CPU_s=begin-cpu;self.startup_wall_s=wall-tick
        store=PyAthena.py_svc('StoreGateSvc');info=store.retrieve('xAOD::EventInfo','EventInfo')
        run,event=int(info.runNumber()),int(info.eventNumber());assert (run,event)==(case['run'],case['event'])
        truth=store.retrieve('McEventCollection','TruthEvent');assert truth.size()==1
        nu=[q for q in truth[0].particles() if abs(int(q.pid())) in [12,14,16] and int(q.status())==4];assert len(nu)==1
        q=nu[0];m=q.momentum();incoming=[int(q.pid())]+[float(getattr(m,k)()) for k in ['px','py','pz']]
        np.testing.assert_array_equal(np.asarray(incoming,dtype='float32'),np.asarray(case['incoming'],dtype='float32'))
        if source['index'] not in self.readers:
            from stage122_saved import SavedWaveforms
            self.readers[source['index']]=SavedWaveforms(ROOT,source['rdo'],detectors)
        waves=self.readers[source['index']].read(case['entry'],run,event)
        identities.append(dict(row=case['row'],entry=case['entry'],global_entry=case['global_entry'],source_index=source['index'],run=run,event=event,incoming=incoming,role=case['role']))
        do_literal=case['row'] in [c['row'] for c in source['cases'][:2]]
        literal_CPU=0.
        for detector in detectors:
            mapping=[list(r) for r in (ROOT.Stage185CaloMap() if detector=='Calo' else ROOT.Stage185ScintMap(detector))]
            by_channel={int(r[0]):r for r in mapping};by_physical={tuple(map(int,r[2:])):r for r in mapping} if detector!='Calo' else {}
            chosen={ch:(by_channel[ch] if detector=='Calo' else by_physical[physical[detector,ch]]) for ch in expected[detector]}
            wave_map={w['channel']:w for w in waves[detector]};assert len(wave_map)==len(waves[detector])
            assert set(expected[detector])<=set(chosen)
            cond=list(ROOT.Stage122Conditions(detector));window=(390,465) if detector=='Calo' else (390,490)
            key=(detector,tuple(cond));
            if key not in self.integrators:self.integrators[key]=ROOT.Stage184Window(cond,*window)
            contributions=[list(r) for r in (ROOT.Stage144EcalTiming() if detector=='Calo' else ROOT.Stage138Timing(detector))]
            flat=[v for h in contributions for v in [h[0],h[3],h[1]]];ids=[int(r[1]) for r in chosen.values()]
            ideal={int(r[0]):float(r[1]) for r in self.integrators[key].integrate(flat,ids)}
            exact={}
            if do_literal:
                t=time.process_time();a=np.asarray([list(r) for r in ROOT.Stage141Analog(flat,cond,ids,185000+source['index'],600)])
                for ch,r in chosen.items():
                    use=(a[:,0]==r[1])&(a[:,1]>=window[0])&(a[:,1]<=window[1]);exact[ch]=float(a[use,2].sum()*(2*2000/16384/50))
                literal_CPU+=time.process_time()-t
            conditions_records.append(dict(row=case['row'],detector=detector,conditions=cond))
            for ch,r in chosen.items():
                wave=wave_map.get(ch);actual=None
                if wave:
                    if detector=='Calo':assert wave['id32']==r[1]
                    else:assert tuple(list(self.decoder.decode(wave['id32']))[2:])==physical[detector,ch]
                    actual=list(ROOT.Stage129Official(detector,ch,wave['id32'],wave['adc']))
                    assert actual[6:8]==[window[0]*2.,window[1]*2.]
                value=ideal[int(r[1])]
                if do_literal:
                    bound=32*np.finfo('float32').eps*max(1,abs(exact[ch]));assert abs(value-exact[ch])<=bound
                    literal.append(dict(row=case['row'],channel=ch,fast_pC=value,literal_pC=exact[ch],abs_delta_pC=abs(value-exact[ch]),tolerance_pC=float(bound)))
                rows.append(dict(source_index=source['index'],row=case['row'],run=run,event=event,entry=case['entry'],detector=detector,channel=ch,
                    ADC_present=wave is not None,status=int(actual[0]) if actual else '',raw_pC=actual[1] if actual else '',
                    ideal_pC=value,rail_samples=sum(v==0 for v in wave['adc']) if wave else '',window_start_ns=window[0]*2,window_end_ns=window[1]*2,
                    stored_id32=wave['id32'] if wave else '',current_physical_id32=int(r[1]),current_physical_cable_channel=int(r[0])))
                mapping_records.append(dict(row=case['row'],detector=detector,channel=ch,current_channel=int(r[0]),
                    physical=list(physical[detector,ch]) if detector!='Calo' else None,stored_id32=wave['id32'] if wave else None,current_id32=int(r[1])))
        event_resources.append(dict(row=case['row'],source_index=source['index'],CPU_s=time.process_time()-begin,wall_s=time.perf_counter()-wall,literal_CPU_s=literal_CPU))
        print('STAGE185_PARENT',event_resources[-1],flush=True)
        return PyAthena.StatusCode.Success

reader=Reader('Stage185SharedSourceReadout');acc.addEventAlgo(reader)
ranges=[f'{left+2}-{right}' for left,right in zip(entries,entries[1:]) if right>left+1]
if ranges:acc.getService('EventSelector').SkipEventRanges=','.join(ranges)
assert acc.run().isSuccess();assert len(identities)==len(cases) and len(rows)==15*len(cases)
filename='audit_charges.tsv' if audit else 'charges.tsv'
with (OUT/filename).open('w') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(rows)
summary=dict(passed=True,parents_N=len(cases),identities=identities,HITS_counts=counts,original_source_N=len(sources),literal_checks=literal,
    mappings=mapping_records,conditions=conditions_records,event_resources=event_resources,startup_CPU_s=reader.startup_CPU_s,startup_wall_s=reader.startup_wall_s,
    CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()),new_G4=0,energy_fits=0,overall_complete=False)
(OUT/f'{label}_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print({k:v for k,v in summary.items() if k not in ['identities','HITS_counts','literal_checks','mappings','conditions','event_resources']},flush=True)
sys.stdout.flush();sys.stderr.flush();os._exit(0)
