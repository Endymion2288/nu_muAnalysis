"""Freeze text provenance and fixed original-cohort experiment; no event access."""
import json,re,subprocess
from pathlib import Path
from stage184_freeze import hit_paths
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage186_energy_ml'
if __name__=='__main__':
 OUT.mkdir(parents=True,exist_ok=True);(ROOT/'ntuples/energy_ml_stage186').mkdir(parents=True,exist_ok=True)
 assert not (OUT/'protocol.json').exists()
 p=json.loads((ROOT/'workbook/stage185_energy_ml/next_execution_contract.json').read_text());p.update(stage=186,starting_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip())
 requests=json.loads((ROOT/'workbook/stage129_energy_ml/extraction_contract.json').read_text())['requests'];evidence=[]
 for s in requests:
  rdo=Path(s['rdo']);first=int(rdo.name.split('-')[-4]);stem=rdo.name.split(f'-{s["run"]}-')[0]
  log=rdo.parents[2]/'log'/'s0014'/f'{stem}-{s["run"]}-RDO-merge-{first//10}.rdo.log'
  lines=log.read_text(errors='replace').splitlines() if log.exists() else []
  needles=['using release [','Global tag:','Reading Scintillator  IdDict','Reading Calorimeter   IdDict','Using improved digitization timing','Data output:',' INFO  Norm:',' INFO  Mean:',' INFO  Sigma:',' INFO  Alpha:',' INFO  N:']
  selected=[dict(line=i+1,text=l) for i,l in enumerate(lines) if any(n in l for n in needles)]
  release=[l for l in lines if 'using release [' in l];commit_match=re.search(r'/([0-9a-f]{8})\]',release[0]) if len(release)==1 else None;commit=commit_match.group(1) if commit_match else None
  params={}
  for det in ['Calo','VetoNu','Veto','Trigger','Preshower']:
   q={}
   for key in ['Norm','Mean','Sigma','Alpha','N']:
    values=[float(l.rsplit(':',1)[1]) for l in lines if l.startswith(det+'WaveformDigiAlg ') and re.search(r' INFO  '+key+r':\s',l)]
    if values and len(set(values))==1:q[key]=values[0]
   params[det]=q
  supported=commit in ['6d6ab70b','4a0e366b'] and any('Data output: '+rdo.name in l for l in lines) and sum('Using improved digitization timing' in l for l in lines)==5 and all(len(v)==5 for v in params.values())
  evidence.append(dict(index=s['index'],path=str(log),source_commit=commit,supported=supported,kernel_parameters=params,evidence=selected))
 p['producer_versions']=['6d6ab70b','4a0e366b'];p['dictionary_paths']={'6d6ab70b':'workbook/stage185_energy_ml/IdDict_6d6ab70b.xml','4a0e366b':'workbook/stage186_energy_ml/IdDict_4a0e366b.xml'}
 paths=json.loads((ROOT/'workbook/stage185_energy_ml/protocol.json').read_text())['dictionary_sources'];dictionaries=[]
 for source in paths:
  text=subprocess.check_output(['git','-C',str(ROOT.parent/'calypso'),'show','4a0e366b:'+source['path']]).decode();start=text.index('<IdDictionary');dictionaries.append(text[start:text.index('</IdDictionary>')+len('</IdDictionary>')])
 (OUT/'IdDict_4a0e366b.xml').write_text('<IdDict>\n'+'\n'.join(dictionaries)+'\n</IdDict>\n')
 p['producer_identity_addendum']={'source_index':129,'first_train_N':2,'purpose':'First exact4a0e366b producer; original first2train identity/old controls/literal checks added before any Stage186 scientific execution, within4000pilot. No replacement or risk-based choice. Exact4a digitization/reconstruction source diff against6d6 empty; dictionary addsVetoGm and requires separate actualID decoding.'}
 p['producer_evidence']='workbook/stage186_energy_ml/source_producers.json';p['geometry']='FASERNU-04';p['global_tag']='OFLCOND-FASER-06';p['channels']=[0,1,2,3,4,5,14,6,7,8,9,10,11,12,13]
 p['pilot']['actual_train_N']={str(i):min(40,sum(c['role']==1 for c in requests[i]['cases'])) for i in p['pilot']['source_indices']}
 p['pilot']['source_indices'] += [129];p['pilot']['actual_train_N']['129']=2
 p['pilot']['shortage_policy']='Use min(40,original train N); source254 has28, source257 has0. No substitute/role0 read; source257 remains original missing denominator.'
 p['concrete_missingness']=dict(WAVE_INVALID=8|128|256,FIT_INVALID=8|128|256|16|32|4,common='ADC present, finite current signedraw, no WAVE_INVALID, historical source+actualID/window/response certified',known_fit_invalid='current official reconstruction FIT_INVALID bitmask when ADC present; NaN for absent',censor='any actual ADC code0 or16383 in fixed inclusive window, or WAVE_OVERFLOW bit4; NaN for absent')
 p['old_producer_raw']='6d6 positive-part full-window integral (2*sum(max(wave_mV,0))/50), float32 product/output. Original X62/raw11 unchanged; new R uses d32 signed full-window integral. Explicitly different estimands.'
 p['production_groups']=[list(range(i,min(i+8,280))) for i in range(0,280,8)]
 p['production_jobs']=[list(range(i,min(i+8,35))) for i in range(0,35,8)]
 p['production_job_CPU_allowances_s']=[38400]*4+[14400]
 p['pilot_job_CPU_allowance_s']=3000;p['pilot_audit_CPU_reserve_s']=1000
 p['cost_formula']='3 * (35 * measured main complete GNU CPU + sum_source activeN * max(measured source mean subsequent nonliteral event CPU,global such mean)) + alreadyused schedulerCPU + 8000 <=180000 and projectedproduction<=168000. Complete GNU includes cold init,firstexecute,JIT,all metadata,30+HITS file opens andsource transitions; repeated in35groups, then full per-event cost added conservatively (intentional double counting pilot events). Unsupported producer active parents counted but additionalQ missing; no role0 read. ROOT byte projection 35*measuredbytes+active/pilot*eventreadbytes remains provisional.'
 (OUT/'protocol.json').write_text(json.dumps(p,indent=2)+'\n');(OUT/'source_producers.json').write_text(json.dumps(evidence,indent=2)+'\n')
 print('Frozen',sum(r['supported'] for r in evidence),'/',len(evidence),'sources; pilot',p['pilot']['actual_train_N'])
