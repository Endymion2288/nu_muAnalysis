"""Local stdlib-only transfer/byte verification for scoped Stage129 results."""
import argparse,json,subprocess,tarfile,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];CACHE=ROOT/'ntuples/energy_ml_stage129';OUT=ROOT/'workbook/stage129_energy_ml'
def collect(phase,index,names):
 remote=f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage129/{phase}_{index}_result.tar.gz';transport=Path(f'/tmp/nu_mu_stage129_{phase}_{index}_return.tar.gz')
 subprocess.run(['xrdcp','--silent','--force',remote,str(transport)],check=True)
 records=[]
 with tarfile.open(transport) as t:
  for m in t.getmembers():
   if not m.isfile():continue
   if names and Path(m.name).name not in names:continue
   pp=Path(m.name)
   if pp.is_absolute() or '..' in pp.parts:raise ValueError(m.name)
   if not any(m.name.startswith(v) for v in ['workbook/stage129_energy_ml/','ntuples/energy_ml_stage129/','ml/artifacts/stage129/']):continue
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
   log=Path(f'/afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage129/logs/{cluster}.{proc}.log')
   completed=OUT/f'{a.phase}_{index}_exitcode.txt'
   if log.exists() and '005 (' in log.read_text() and not (completed.exists() and completed.read_text().strip()=='0'):indices.append(index)
 for i in indices:collect(a.phase,i,a.names)
