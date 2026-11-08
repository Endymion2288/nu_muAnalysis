"""Batch sparse original HITS -> matched-window Q15; original saved ADC control."""
import csv
import json
import os
import resource
import sys
import time
from pathlib import Path
import numpy as np
import ROOT

OUT=Path('workbook/stage184_energy_ml')
source_index=int(sys.argv[1]);phase=sys.argv[2]
plan=json.loads((OUT/'protocol.json').read_text())
source=next(s for s in plan['sources'] if s['index']==source_index)
cases=source['cases'][:4] if phase in ['preflight','audit'] else source['cases'][4:] if source_index==0 else source['cases']
entries=[c['entry'] for c in cases];prefix=f'{phase}_source_{source_index}'
assert cases and all(c['role']==1 for c in cases)
tick=time.perf_counter();cpu=time.process_time()
assert ROOT.gInterpreter.Declare('#define HEPMC3 1\n')
counts=[]
for path in source['hits']:
    file=ROOT.TFile.Open(path);assert file and not file.IsZombie(),path
    tree=file.Get('CollectionTree');counts.append(dict(path=path,N=int(tree.GetEntries()) if tree else 0));file.Close()
assert sum(r['N'] for r in counts)==source['parent_N']

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
rows=[];identities=[];configuration={};exact_records=[];mapping_diagnostics=[]

class Readout(PyAthena.Alg):
    def initialize(self):
        import StoreGateBindings.Bindings
        for library in ['libIdentifier.so','libScintIdentifier.so','libScintReadoutGeometry.so',
            'libFaserCaloSimEvent.so','libCaloReadoutGeometry.so','libWaveRawEvent.so','libScintSimEvent.so','libxAODFaserWaveform.so']:
            assert ROOT.gSystem.Load(library)>=0,library
        for header in ['stage138_response.hxx','stage144_ecal.hxx','stage129_official.hxx','stage141_analog.hxx','stage184_window.hxx']:
            assert ROOT.gInterpreter.Declare(Path('ml',header).read_text()),header
        assert ROOT.gInterpreter.Declare('''
            std::vector<std::vector<unsigned int>> Stage184CaloMap() {
                ToolHandle<IWaveformCableMappingTool> tool("WaveformCableMappingTool/Stage122Cable");
                if(tool.retrieve().isFailure())throw std::runtime_error("No cable tool");
                std::vector<std::vector<unsigned int>> out;
                for(const auto& x:tool->getCableMapping())if(x.second.first=="calo")
                    out.push_back({unsigned(x.first),x.second.second.get_identifier32().get_compact()});
                return out;
            }
        ''')
        from stage122_saved import SavedWaveforms
        self.saved=SavedWaveforms(ROOT,source['rdo'],detectors);self.integrators={};self.key=None
        return PyAthena.StatusCode.Success

    def execute(self):
        n=len(identities);case=cases[n];store=PyAthena.py_svc('StoreGateSvc')
        info=store.retrieve('xAOD::EventInfo','EventInfo');run,event=int(info.runNumber()),int(info.eventNumber())
        assert (run,event)==(case['run'],case['event']),(source_index,case,run,event)
        truth=store.retrieve('McEventCollection','TruthEvent');assert truth.size()==1
        nu=[q for q in truth[0].particles() if abs(int(q.pid())) in [12,14,16] and int(q.status())==4]
        assert len(nu)==1
        momentum=nu[0].momentum();incoming=[int(nu[0].pid())]+[float(getattr(momentum,k)()) for k in ['px','py','pz']]
        np.testing.assert_array_equal(np.asarray(incoming,dtype='float32'),np.asarray(case['incoming'],dtype='float32'))
        saved=self.saved.read(case['entry'],run,event)
        identities.append(dict(row=case['row'],entry=case['entry'],run=run,event=event,role=case['role'],incoming=incoming))
        total_integrate=0.;total_literal=0.;hist_nonempty=0
        for detector in detectors:
            cable=[list(r) for r in (ROOT.Stage184CaloMap() if detector=='Calo' else ROOT.Stage122CableMap(detector))]
            mapping={int(r[0]):int(r[1]) for r in cable};channels=[ch for ch in plan['channels'] if ch in mapping]
            expected={'Calo':[0,1,2,3],'VetoNu':[4,5],'Veto':[14,6,7],'Trigger':[8,9,10,11],'Preshower':[12,13]}[detector]
            assert sorted(channels)==sorted(expected),(detector,cable)
            cond=list(ROOT.Stage122Conditions(detector));window=(390,465) if detector=='Calo' else (390,490)
            key=(detector,tuple(cond),window)
            if key not in self.integrators:self.integrators[key]=ROOT.Stage184Window(cond,*window)
            contributions=[list(r) for r in (ROOT.Stage144EcalTiming() if detector=='Calo' else ROOT.Stage138Timing(detector))]
            flat=[v for r in contributions for v in [r[0],r[3],r[1]]]
            t=time.process_time();ideal={int(r[0]):[float(r[1]),int(r[2])] for r in self.integrators[key].integrate(flat,[mapping[ch] for ch in channels])};total_integrate+=time.process_time()-t
            wave_map={w['channel']:w for w in saved[detector]}
            assert len(wave_map)==len(saved[detector]) and set(wave_map)<=set(mapping)
            do_literal=case['row'] in [c['row'] for c in source['cases'][:2]]
            exact={}
            if do_literal:
                t=time.process_time()
                analog=np.asarray([list(r) for r in ROOT.Stage141Analog(flat,cond,[mapping[ch] for ch in channels],184000+source_index,600)])
                for channel in channels:
                    use=(analog[:,0]==mapping[channel])&(analog[:,1]>=window[0])&(analog[:,1]<=window[1])
                    exact[channel]=float(analog[use,2].sum()*(2*2000/16384/50))
                total_literal+=time.process_time()-t
            if detector not in configuration:configuration[detector]=dict(conditions=cond,cable_map=cable,window_samples=list(window))
            assert configuration[detector]['conditions']==cond,'Within-source IOV change; report, no silent change'
            if phase=='audit':
                # Descriptive identification of the observed channel14 mismatch.
                # All four actual cable-map Veto PMTs, not a fitted ID/window grid.
                all_veto={int(r[0]):float(r[1]) for r in self.integrators[key].integrate(flat,list(mapping.values()))} if detector=='Veto' else {}
                for channel,wave in wave_map.items():
                    mapping_diagnostics.append(dict(row=case['row'],detector=detector,channel=channel,
                        stored_id32=wave['id32'],current_cable_id32=mapping[channel],
                        all_Veto_current_physical_Q_pC={str(ch):all_veto[mapping[ch]] for ch in mapping} if detector=='Veto' else {}))
            for channel in channels:
                q,nonempty=ideal[mapping[channel]];hist_nonempty+=nonempty
                wave=wave_map.get(channel);result=list(ROOT.Stage129Official(detector,channel,wave['id32'],wave['adc'])) if wave else None
                if result:assert result[6:8]==[window[0]*2.,window[1]*2.],(detector,channel,result)
                literal=exact.get(channel);tolerance=32*np.finfo('float32').eps*max(1,abs(literal)) if literal is not None else None
                if literal is not None:
                    assert abs(q-literal)<=tolerance,(source_index,case['row'],channel,q,literal,tolerance)
                    exact_records.append(dict(row=case['row'],channel=channel,fast_pC=q,literal_pC=literal,abs_delta_pC=abs(q-literal),tolerance_pC=float(tolerance)))
                rows.append(dict(source_index=source_index,row=case['row'],run=run,event=event,entry=case['entry'],detector=detector,
                    channel=channel,ADC_present=wave is not None,status=int(result[0]) if result else '',
                    raw_pC=result[1] if result else '',ideal_pC=q,nonempty_hist_bins=nonempty,
                    rail_samples=sum(v==0 for v in wave['adc']) if wave else '',window_start_ns=window[0]*2,window_end_ns=window[1]*2))
        print('STAGE184_PARENT',dict(row=case['row'],integrate_CPU_s=total_integrate,literal_CPU_s=total_literal,nonempty_bins=hist_nonempty),flush=True)
        return PyAthena.StatusCode.Success

reader=Readout('Stage184Readout');acc.addEventAlgo(reader)
ranges=[f'{left+2}-{right}' for left,right in zip(entries,entries[1:]) if right>left+1]
if ranges:acc.getService('EventSelector').SkipEventRanges=','.join(ranges)
assert acc.run().isSuccess();assert len(identities)==len(cases)
assert len(rows)==15*len(cases)
with (OUT/f'{prefix}_charges.tsv').open('w') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(rows)
summary=dict(passed=True,source_index=source_index,phase=phase,parents_N=len(cases),channel_records_N=len(rows),identities=identities,
    HITS_counts=counts,configuration=configuration,RDO_schema=reader.saved.schemas,literal_checks=exact_records,mapping_diagnostics=mapping_diagnostics,
    signed_negative_raw_N=sum(r['ADC_present'] and r['raw_pC']<0 for r in rows),ADC_missing_N=sum(not r['ADC_present'] for r in rows),
    CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()),G4_N=0,energy_fits=0,new_forward=0,overall_complete=False)
(OUT/f'{prefix}_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print({k:v for k,v in summary.items() if k not in ['identities','HITS_counts','configuration','RDO_schema','literal_checks']},flush=True)
sys.stdout.flush();sys.stderr.flush();os._exit(0)
