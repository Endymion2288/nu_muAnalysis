"""Local stdlib-only transfer/byte verification for scoped Stage124 results."""
import argparse,json,subprocess,tarfile,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];CACHE=ROOT/'ntuples/energy_ml_stage124';OUT=ROOT/'workbook/stage124_energy_ml'
def collect(phase,index,names):
 remote=f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage124/{phase}_{index}_result.tar.gz';transport=Path(f'/tmp/nu_mu_stage124_{phase}_{index}_return.tar.gz')
 subprocess.run(['xrdcp','--silent','--force',remote,str(transport)],check=True)
 records=[]
 with tarfile.open(transport) as t:
  for m in t.getmembers():
   if not m.isfile():continue
   if phase.startswith('pilot') or phase in ['native','repair','mismatch']:
    if not m.name.startswith('result/'):continue
    target=CACHE/f'{phase}_{index}'/Path(m.name).name
   else:
    if names and Path(m.name).name not in names:continue
    pp=Path(m.name)
    if pp.is_absolute() or '..' in pp.parts:raise ValueError(m.name)
    if not any(m.name.startswith(v) for v in ['workbook/stage124_energy_ml/','ntuples/energy_ml_stage124/','ml/artifacts/stage124/']):continue
    target=ROOT/pp
   payload=t.extractfile(m).read();target.parent.mkdir(parents=True,exist_ok=True)
   target.write_bytes(payload);assert target.read_bytes()==payload
   records.append(dict(path=str(target.relative_to(ROOT)),bytes=len(payload)))
 ledger=OUT/'transfers.json';saved=json.loads(ledger.read_text()) if ledger.exists() else []
 saved.append(dict(phase=phase,index=index,transport_bytes=transport.stat().st_size,files=records,byte_roundtrip_verified=True));ledger.write_text(json.dumps(saved,indent=2)+'\n')
 transport.unlink();print(json.dumps(dict(phase=phase,index=index,files=len(records),bytes=sum(v['bytes'] for v in records))))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase');p.add_argument('indices',nargs='*',type=int);p.add_argument('--ready',action='store_true');p.add_argument('--names',nargs='*');a=p.parse_args()
 indices=a.indices
 if a.ready:
  submission=json.loads((OUT/f'{a.phase}_submission.json').read_text());cluster=int(re.match(r'\d+',submission['result'])[0]);package=json.loads((OUT/f'{a.phase}_package.json').read_text())
  indices=[]
  for proc,index in enumerate(package['indices']):
   log=Path(f'/afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage124/logs/{cluster}.{proc}.log')
   if log.exists() and '005 (' in log.read_text() and not (CACHE/f'{a.phase}_{index}/exitcode.txt').exists():indices.append(index)
 for i in indices:collect(a.phase,i,a.names)
