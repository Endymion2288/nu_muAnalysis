"""Official digitizer with explicit reproducible stream offsets and waveform states."""
import json,re,shutil,sys
from pathlib import Path
seed=int(sys.argv[2]);output=Path(sys.argv[3]);input_path=sys.argv[1]
import ROOT
from AthenaPython import PyAthena
from AthenaConfiguration.ComponentAccumulator import ComponentAccumulator
from AthenaConfiguration.ComponentFactory import CompFactory
original=ComponentAccumulator.run
before={}
class Seed(PyAthena.Alg):
 def finalize(self):
  for detector in before:
   before[detector]['after']=str(ROOT.Stage129PrivateState(detector));assert len(before[detector]['after'])>1000
  output.write_text(json.dumps(before,indent=2)+'\n')
  assert any(v['after']!=v['state'] for v in before.values()),'No actual digitizer randomstream advanced'
  return PyAthena.StatusCode.Success
header=Path(__file__).with_name('stage129_rng.hxx')
# sys.argv becomes the production CLI; preserve the header path separately.
def initialize(self):
 print('RNG_INIT_BEGIN',flush=True)
 assert ROOT.gInterpreter.Declare('#define HEPMC3 1\n')
 for lib in ['libWaveRawEvent.so','libScintSimEvent.so','libxAODFaserWaveform.so']:assert ROOT.gSystem.Load(lib)>=0
 print('RNG_LIBRARIES_LOADED',flush=True)
 assert ROOT.gInterpreter.Declare(header.read_text())
 print('RNG_HEADER_DECLARED',flush=True)
 return PyAthena.StatusCode.Success

def execute(self):
 for j,detector in enumerate(['Calo','VetoNu','Veto','Trigger','Preshower']):
  print('RNG_SEED_START',detector,flush=True)
  value=seed+1000*j;ROOT.Stage129PrivateSeed(detector,value);before[detector]=dict(seed=value,state=str(ROOT.Stage129PrivateState(detector)));assert len(before[detector]['state'])>1000
  print('RNG_SEED_DONE',detector,flush=True)
 return PyAthena.StatusCode.Success
Seed.initialize=initialize
Seed.execute=execute

def run(acc,*args,**kwargs):
 for detector in ['Calo','VetoNu','Veto','Trigger','Preshower']:
  tool=CompFactory.WaveformDigitisationTool('Stage122'+detector);acc.getEventAlgo(detector+'WaveformDigiAlg').WaveformDigitisationTool=tool
 acc.addEventAlgo(Seed('Stage129SeededWaveforms'),sequenceName='AthBeginSeq')
 return original(acc,*args,**kwargs)
ComponentAccumulator.run=run
source=Path(shutil.which('faser_digi.py')).read_text();assert source.count('configFlags = initConfigFlags()')==1
source=re.sub(r'(?m)^([ \t]*)configFlags = initConfigFlags\(\)',lambda m:m.group(0)+'\n'+m.group(1)+f'configFlags.Random.SeedOffset = {seed}',source);source=source.replace('OFLCOND-FASER-04','OFLCOND-FASER-06')
sys.argv=['faser_digi.py','--geom','TI12MC04','--nevts','1',input_path];exec(compile(source,'pinned-seeded-faser_digi.py','exec'),{'__name__':'__main__'})
