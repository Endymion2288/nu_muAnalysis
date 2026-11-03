"""Bounded production-log and pinned-source evidence for stage79 selected sources."""
import json
import re
import subprocess
import time
from pathlib import Path

from pulse_information_audit import OUT, save


def main():
    start=time.perf_counter();plan=json.loads((OUT/'qa_plan.json').read_text());records=[]
    for source in plan['selected_sources']:
        name=Path(source['input']).name
        prefix=name.split('-'+source['run']+'-')[0]+'-'+source['run']
        segment=source['group'].split(':')[1];index=int(segment.split('-')[0])//10
        path=Path('/eos/experiment/fasernu-data0/faser/sim/mc24/genie')/source['run']/'log/s0014'/f'{prefix}-RDO-merge-{index}.rdo.log'
        rec=dict(source=int(source['index']),path=str(path),segment=segment)
        try:
            text=path.read_text(errors='replace');lines=text.splitlines()
            rec['bytes']=path.stat().st_size
            rec['exact_output_name_present']=f'{prefix}-{segment}-s0014-RDO.root' in text
            needles=['using release','Global tag:','resolved to WAVE-Digitization','Using improved digitization','Using simple digitization','initialize waveform digitization kernel',' INFO  Norm:',' INFO  Mean:',' INFO  Sigma:',' INFO  Alpha:',' INFO  N:']
            rec['evidence']=[dict(line=i+1,text=line) for i,line in enumerate(lines) if any(n in line for n in needles)]
            rec['scint_advanced_algorithms']=[line.split()[0] for line in lines if 'Using improved digitization timing' in line and not line.startswith('Calo')]
            rec['release_commits']=sorted(set(re.findall(r'Fast-forward/([0-9a-f]+)',text)))
            current=None;parameters={}
            for evidence in rec['evidence']:
                line=evidence['text']
                if 'initialize waveform digitization kernel' in line:
                    current=line.split()[0];parameters[current]={}
                elif current and any(f' INFO  {key}:' in line for key in ['Norm','Mean','Sigma','Alpha','N']):
                    key,value=line.split(' INFO  ')[1].split(':');parameters[current][key.strip()]=float(value)
            rec['kernel_parameters']=parameters
        except OSError as exc:
            rec['error']=str(exc)
        records.append(rec)
    calypso=Path('/eos/home-x/xcheng/FASER/calypso')
    paths=['Waveform/WaveDigiTools/src/WaveformDigitisationTool.cxx','Waveform/WaveDigiTools/src/WaveformDigitisationTool.h','Scintillator/ScintDigiAlgs/src/ScintWaveformDigiAlg.cxx','Scintillator/ScintDigiAlgs/src/ScintWaveformDigiAlg.h']
    comparisons=[]
    for commit in sorted({c for r in records for c in r.get('release_commits',[])}):
        for path in paths:
            run=subprocess.run(['git','-C',str(calypso),'diff','--numstat',commit,'d32b0ff3','--',path],capture_output=True,text=True,check=True)
            comparisons.append(dict(production_commit=commit,writer_commit='d32b0ff3',path=path,diff_numstat=run.stdout.strip(),identical=not run.stdout.strip()))
    save(OUT/'source_evidence.json',dict(stage=79,records=records,pinned_digitization_comparisons=comparisons,
        all_twelve_logged_kernel_parameters_identical=all(r.get('kernel_parameters')==records[0].get('kernel_parameters') for r in records),
        wall_s=time.perf_counter()-start,total_log_bytes=sum(r.get('bytes',0) for r in records),
        input_scope='only 12 chosen source production logs, exact RDO output-name checks; no event access or recursive scan',
        remaining='actual full payload (baseline/noise/slopes), clock/offset and reliable channel-specific mu path not certified'))
    print(json.dumps(dict(logs=len(records),exact_outputs=sum(r.get('exact_output_name_present',False) for r in records),
        errors=sum('error' in r for r in records),commits=sorted({c for r in records for c in r.get('release_commits',[])}))))


if __name__=='__main__':main()
