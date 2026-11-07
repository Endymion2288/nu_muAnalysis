"""Actual bounded EVNT -> G4 -> digitization -> reconstruction -> compact selection pilot."""
import json,os,re,shutil,subprocess,sys,time
from pathlib import Path
OUT=Path('workbook/stage129_energy_ml').resolve();CACHE=Path('ntuples/energy_ml_stage129').resolve();ROOT=Path.cwd();index=int(sys.argv[1]);plan=json.loads((OUT/'fullchain_protocol.json').read_text());case=plan['cases'][index];work=ROOT/f'chain_{index}';work.mkdir();tick=time.perf_counter();steps=[]
datasets=dict(G4LEDATA='G4EMLOW7.9.1',G4LEVELGAMMADATA='PhotonEvaporation5.5',G4RADIOACTIVEDATA='RadioactiveDecay5.4',G4PARTICLEXSDATA='G4PARTICLEXS2.1',G4NEUTRONHPDATA='G4NDL4.6',G4SAIDXSDATA='G4SAIDDATA2.0',G4ABLADATA='G4ABLA3.1',G4INCLDATA='G4INCL1.0',G4ENSDFSTATEDATA='G4ENSDFSTATE2.2',G4REALSURFACEDATA='RealSurface2.1.1')
for key,name in datasets.items():
 path=Path('/cvmfs/geant4.cern.ch/share/data')/name;assert path.is_dir();os.environ[key]=str(path)
(OUT/f'fullchain_{index}_datasets.json').write_text(json.dumps({k:os.environ[k] for k in datasets},indent=2)+'\n')

def run(name,command):
 print('FULLCHAIN_STEP_START',index,name,flush=True)
 log=OUT/f'fullchain_{index}_{name}.log';timing=OUT/f'fullchain_{index}_{name}_time.txt';start=time.perf_counter()
 with log.open('w') as stream:
  process=subprocess.Popen(['/usr/bin/time','-v','-o',str(timing)]+command,cwd=work,stdout=stream,stderr=subprocess.STDOUT)
  while True:
   try:
    process.wait(timeout=45);break
   except subprocess.TimeoutExpired:
    print('FULLCHAIN_STEP_RUNNING',index,name,round(time.perf_counter()-start,1),flush=True)
    with log.open('rb') as recent:
     recent.seek(max(0,log.stat().st_size-1400));print(recent.read().decode(errors='replace'),flush=True)
  r=process
 print('FULLCHAIN_STEP_END',index,name,r.returncode,time.perf_counter()-start,flush=True)
 steps.append(dict(name=name,returncode=r.returncode,wall_s=time.perf_counter()-start,command=command))
 (OUT/f'fullchain_{index}_summary.json').write_text(json.dumps(dict(case=case,steps=steps,wall_s=time.perf_counter()-tick,scope='engineering selected-candidate cost/yield, not unbiased efficiency, not independent learning N; no model prediction',successful=False),indent=2)+'\n')
 if r.returncode:raise SystemExit(r.returncode)

# The installed pinned simulation script is retained; only explicit conditions
# and reproducible RNG offset are inserted, with the exact substitutions audited.
script=Path(shutil.which('faser_simulate.py'));source=script.read_text();assert source.count('configFlags = initConfigFlags()')==1
source=source.replace('configFlags = initConfigFlags()',f'configFlags = initConfigFlags()\n    configFlags.Random.SeedOffset = {case["seed"]}')
assert source.count('sys.exit(int(sc.isFailure()))')==1
source=source.replace('sys.exit(int(sc.isFailure()))','import os\n    sys.stdout.flush(); sys.stderr.flush()\n    os._exit(int(sc.isFailure()))')
substitutions=source.count('OFLCOND-FASER-04');source=source.replace('OFLCOND-FASER-04','OFLCOND-FASER-06');(work/'simulate.py').write_text(source)
(OUT/f'fullchain_{index}_producer.json').write_text(json.dumps(dict(installed_script=str(script),official_commit=os.environ.get('FASER_OFFICIAL_COMMIT'),random_seed_offset=case['seed'],conditions_replacements=substitutions,geometry='FASERNU-04',conditions='OFLCOND-FASER-06',physics_list='FTFP_BERT',seed_scope='recorded G4 seed offset plus unique random stream filename; waveform RNG provenance checked separately'),indent=2)+'\n')
name=f'FaserMC-Stage129Nu-990129-{index:05d}-stage129';hits=name+'-HITS.root';rdo=name+'-RDO.root';rec=name+'-xAOD.root'
run('sim',[sys.executable,'simulate.py',case['EVNT'],hits,'--geom','TI12MC04','--G4_phys','FTFP_BERT','--skip',str(case['entry']),'-n','1'])
run('validate_hits',[sys.executable,'-c','import ROOT,sys; f=ROOT.TFile.Open(sys.argv[1]); assert f and not f.IsZombie(); assert f.Get("CollectionTree").GetEntries()==1; f.Close()',hits])
run('digi',[sys.executable,str(ROOT/'ml/stage129_digitize.py'),hits,str(case['seed']+1),str(OUT/f'fullchain_{index}_waveform_states.json')])
if index==0:
 adc_snapshot=str(CACHE/'fullchain_pilot_adc.json');adc_report=str(OUT/'fullchain_pilot_adc_repeat.json')
 run('adc_before',[sys.executable,str(ROOT/'ml/stage129_adcqa.py'),rdo,adc_snapshot,adc_report,'before'])
 run('digi_repeat',[sys.executable,str(ROOT/'ml/stage129_digitize.py'),hits,str(case['seed']+1),str(OUT/f'fullchain_{index}_waveform_states_repeat.json')])
 run('adc_after',[sys.executable,str(ROOT/'ml/stage129_adcqa.py'),rdo,adc_snapshot,adc_report,'after'])
 first=json.loads((OUT/f'fullchain_{index}_waveform_states.json').read_text());second=json.loads((OUT/f'fullchain_{index}_waveform_states_repeat.json').read_text());assert first==second
run('reco',['faser_reco.py','--isMC','--geom','TI12MC04','--nevents','1',rdo])
run('ntuple',['faser_ntuple_maker.py','--isMC','--geom','TI12MC04','--CKFTrackType','merge','--nevents','1','--outfile','ntuple.root',rec])
payload_tick=time.perf_counter();payload=json.loads((OUT/'fullchain_fixed_payload.json').read_text())
assert payload['resolved']=='WAVE-Calibration-03-LG'
assert all(r['since']==0 and r['until']==9223372036854775807 for rows in payload['payloads'].values() for r in rows)
(OUT/f'fullchain_{index}_payload.json').write_text(json.dumps(payload,indent=2)+'\n')
steps.append(dict(name='payload_frozen_reuse',returncode=0,wall_s=time.perf_counter()-payload_tick,command=None,method='read validated literal full-IOV COOL snapshot fullchain_fixed_payload.json'))
# An isolated LCG process uses the same typed62 and original native cuts.
run('extract',['env','-i','PATH=/usr/bin:/bin','HOME='+os.environ['HOME'],'USER='+os.environ.get('USER','xcheng'),'PYTHONNOUSERSITE=1','OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','bash','-c','source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh\npython "$1/ml/stage129_fullchainextract.py" "$1" "$2" "$3"','bash',str(ROOT),str(index),str(work/'ntuple.root')])
summary=json.loads((OUT/f'fullchain_{index}_summary.json').read_text());summary.update(successful=True,wall_s=time.perf_counter()-tick,intermediate_ROOT_retained=False);(OUT/f'fullchain_{index}_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print('FULLCHAIN',index,'success',time.perf_counter()-tick,flush=True)
