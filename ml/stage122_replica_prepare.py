"""Freeze truth/selection-stratified parents for a finite same-HITS experiment."""
import json
import zlib
from pathlib import Path

import numpy as np


def main():
    root=Path(__file__).resolve().parents[1];out=root/'workbook/stage122_energy_ml';cache=root/'ntuples/energy_ml_stage122'
    p=json.loads((out/'cohort_contract.json').read_text());selected=[];support=[]
    # First already frozen file for each environment x component, independent of new outcomes.
    for original_index in [36,39,42,45,48,51,54,57,60]:
        source=next(s for s in p['sources'] if s['source_index']==original_index)
        with np.load(root/f'ntuples/energy_ml_stage119/pilot_{original_index}.npz') as z:d={k:z[k] for k in z.files}
        e,y=d['E'],d['y'];eligible=(np.abs(d['incoming'][:,0])==14)&(d['incoming'][:,3]>50000)
        # Disjoint truth categories; high transfer gets priority above 200GeV.
        cat=np.where(e<100,0,np.where(e<200,1,np.where((y>=.8)&(y<1),2,np.where(e<400,3,4))))
        cases=[]
        for category,name in enumerate(['E50_100','E100_200','high_y_trueE200','transition200_400','natural_high_control']):
            for passed in [False,True]:
                ix=np.flatnonzero(eligible&(e>=50)&(cat==category)&(d['S50']==passed))
                order=sorted(ix,key=lambda j:(zlib.crc32(f'stage122rep:{source["run"]}:{int(d["eventID"][j])}'.encode()),int(j)))
                chosen=order[:3];probability=len(chosen)/len(ix) if len(ix) else 0
                support.append(dict(source_index=original_index,category=name,pilot_selected=passed,population_N=len(ix),sample_N=len(chosen),inclusion_probability=probability))
                for j in chosen:cases.append(dict(entry=int(j),event=int(d['eventID'][j]),incoming=d['incoming'][j].tolist(),category=name,pilot_selected=bool(passed),inclusion_probability=probability))
        s=dict(source,cases=sorted(cases,key=lambda c:c['entry']));selected.append(s)
    p.update(sources=selected,pilot_replicas=[0,0]+list(range(1,16)),reconstruct=True,
        scope='Nine predeclared existing response sources, three hashed parents per nonempty truth category x old pilot selected/fail. All sampled parent paths retained. Sixteen distinct digitization streams per same HITS, replica0 restored exactly once; no new independent parent N.',
        role_policy='Original incoming roles and quarantined identities retained; all views inherit parent, no repeat crosses fit/evaluation. No replica enters fitting.',
        reconstruction='Original full RDO tracking/calo frozen per parent; only VetoNu/Preshower waveform-dependent summaries re-evaluated with official primary+secondary tools and original reduced-charge formula. Original waveform round-trip must match native reference first.',
        outputs='Per-parent fixed Stage87 energy output variance/mean/MSE/bias/actual signed tails, no averaging as deployable point. Full parent selection pass/fail probability and preselection denominators; non-scint failures cannot migrate.',
        resources=dict(native_jobs=9,candidate_reconstruction_jobs=9,cpus_each=2,memory_MB=6000,wall_s_each=3600,aggregate_CPU_s=25000,retained_bytes=80000000),
        limitation='Conditional waveform fluctuation only, SCT/calo/other scintillator responses fixed. Not total detector variance or Bayes error; full GENIE/G4 replicas conditional and separately need certified final-state replay input.')
    (out/'replica_contract.json').write_text(json.dumps(p,indent=2)+'\n');(out/'replica_sampling_support.json').write_text(json.dumps(support,indent=2)+'\n')
    print('Frozen parents',sum(len(s['cases']) for s in selected),flush=True)


if __name__=='__main__':main()
