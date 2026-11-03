"""Check exact known production logs before stage80 formal submissions."""
import json
import re
import subprocess
from pathlib import Path
from pulse_ablation import *


def main():
    start=begin();p=json.loads((OUT/'proposal.json').read_text());old=json.loads((REPO/'workbook/stage79_energy_ml/source_evidence.json').read_text())
    known={r['source']:r for r in old['records']};expected=old['records'][0]['kernel_parameters'];records=[]
    for source in p['sources']:
        sid=int(source['index'])
        if sid in known:
            r=known[sid];records.append(dict(source=sid,path=r['path'],exact_output=True,improved_algorithms=4,commit='6d6ab70b',
                conditions='WAVE-Digitization-02-LG',kernel_identical=True,reused_stage79=True,read_bytes=0));continue
        prefix=Path(source['input']).name.split('-'+source['run']+'-')[0]+'-'+source['run'];segment=source['group'].split(':')[1]
        path=Path('/eos/experiment/fasernu-data0/faser/sim/mc24/genie')/source['run']/'log/s0014'/f'{prefix}-RDO-merge-{int(segment.split("-")[0])//10}.rdo.log'
        text=path.read_text(errors='replace');lines=text.splitlines()
        exact=f'{prefix}-{segment}-s0014-RDO.root' in text
        advanced=sum('Using improved digitization timing' in line and not line.startswith('Calo') for line in lines)
        commits={c for line in lines if 'using release' in line for c in re.findall(r'/([0-9a-f]{8,40})\]',line)};parameters={};current=None
        for line in lines:
            if 'initialize waveform digitization kernel' in line:
                current=line.split()[0];parameters[current]={}
            elif current and any(f' INFO  {key}:' in line for key in ['Norm','Mean','Sigma','Alpha','N']):
                key,value=line.split(' INFO  ')[1].split(':');parameters[current][key.strip()]=float(value)
        tag='WAVE-Digitization-02-LG' in text
        assert exact and advanced==4 and len(commits)==1 and tag and parameters==expected,str(path)
        records.append(dict(source=sid,path=str(path),exact_output=exact,improved_algorithms=advanced,commit=next(iter(commits)),
            conditions='WAVE-Digitization-02-LG',kernel_identical=True,reused_stage79=False,read_bytes=path.stat().st_size))
    comparisons=[]
    paths=['Waveform/WaveDigiTools/src/WaveformDigitisationTool.cxx','Waveform/WaveDigiTools/src/WaveformDigitisationTool.h',
           'Scintillator/ScintDigiAlgs/src/ScintWaveformDigiAlg.cxx','Scintillator/ScintDigiAlgs/src/ScintWaveformDigiAlg.h']
    for commit in sorted({r['commit'] for r in records}):
        for path in paths:
            diff=subprocess.check_output(['git','-C','/eos/home-x/xcheng/FASER/calypso','diff','--numstat',commit,'d32b0ff3','--',path],text=True)
            assert not diff,(commit,path,diff)
            comparisons.append(dict(commit=commit,path=path,identical_to_d32b0ff3=True))
    save(OUT/'source_audit.json',dict(passed=True,N=len(records),records=records,expected_kernel=expected,
        digitization_source_comparison_reused='workbook/stage79_energy_ml/source_evidence.json',
        comparisons=comparisons,
        read_bytes=sum(r['read_bytes'] for r in records),new_event_access=False,**resources(start)))
    print(json.dumps(dict(passed=True,sources=len(records),read_bytes=sum(r['read_bytes'] for r in records),**resources(start))))


if __name__=='__main__':main()
