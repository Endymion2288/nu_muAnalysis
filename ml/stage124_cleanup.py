"""Local stdlib-only deletion of byte-verified duplicate Stage124 transports."""
import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage124_energy_ml'
def main():
 ledger=json.loads((OUT/'transfers.json').read_text());target=OUT/'cleanup.json';old=json.loads(target.read_text()) if target.exists() else [];done={r['path'] for r in old};result=list(old)
 for row in ledger:
  assert row['byte_roundtrip_verified']
  name=f'{row["phase"]}_{row["index"]}_result.tar.gz';path=f'/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage124/{name}'
  if path in done:continue
  # A previous completed cleanup may later deduplicate an input against its
  # retained original. Revalidate members only for transports still present.
  for f in row['files']:assert (ROOT/f['path']).stat().st_size==f['bytes'],f['path']
  p=subprocess.run(['xrdfs','root://eoshome-x.cern.ch','rm',path],capture_output=True,text=True)
  if p.returncode:raise RuntimeError(p.stderr)
  result.append(dict(path=path,bytes=row['transport_bytes'],reason='all compact extracted members previously byte-roundtrip verified and retained; duplicate transport only'));done.add(path)
  target.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(dict(duplicate_transports_removed=len(result),bytes_removed=sum(r['bytes'] for r in result))))
if __name__=='__main__':main()
