"""Finite-window analog closure from retained actual timing and random seed."""
import csv
import gzip
import json
import resource
import time
from pathlib import Path
import ROOT

OUT=Path('workbook/stage141_energy_ml')

def main():
    tick=time.perf_counter();cpu=time.process_time()
    with gzip.open('ntuples/energy_ml_stage138/control_0.json.gz','rt') as f:control=json.load(f)
    with gzip.open('ntuples/energy_ml_stage131/pilot_private_rng_states.json.gz','rt') as f:rng=json.load(f)
    assert ROOT.gInterpreter.Declare(Path('ml/stage141_analog.hxx').read_text())
    details=[];checks=[];mismatch=0;samples=0
    for detector,record in control['records'].items():
        waves=sorted(record['waves'],key=lambda r:r['id32'])
        if not waves:
            checks.append(dict(detector=detector,ADC_present=False,ADC_samples=0,mismatch=0,meaning='no HITS/no ADC;raw0/status1 producer defaults'))
            continue
        counts={len(w['adc']) for w in waves};assert len(counts)==1;n=counts.pop()
        # Stage138 already computes original float time-of-flight/light delay.
        hits=[v for r in record['timing'] for v in [r[0],r[3],r[1]]]
        result=list(ROOT.Stage141Analog(hits,record['conditions'],[w['id32'] for w in waves],rng[detector]['seed'],n))
        byid={w['id32']:w for w in waves};bad=0
        for r in result:
            id32,i=int(r[0]),int(r[1]);wave=byid[id32];actual=wave['adc'][i]
            bad+=int(actual!=int(r[5]));samples+=1
        mismatch+=bad
        checks.append(dict(detector=detector,ADC_present=True,ADC_samples=len(result),mismatch=bad,meaning='float analog+original Gaussian stream thenround/clip vsactual ADC'))
        for wave in waves:
            rows=[r for r in result if int(r[0])==wave['id32']]
            selected=[r for r in rows if 390<=int(r[1])<=490]
            conversion=2*2/16384/50*1000
            analog=conversion*sum(r[2] for r in selected)
            mean=record['conditions'][0]
            noisy=conversion*sum(mean-r[4]+r[3] for r in selected)
            clipped=conversion*sum(mean-r[5] for r in selected)
            details.append(dict(detector=detector,channel=wave['channel'],samples=n,
                analog_fixedbaseline_window_pC=analog,
                noisy_before_round_clip_fixedbaseline_pC=noisy,
                rounded_clipped_fixedbaseline_pC=clipped,
                measured_raw_fittedbaseline_pC=wave['result'][1],
                status=int(wave['result'][0]),clipped_samples=sum(r[5]==0 for r in rows),
                scope='all downstream deposits mu-root for this one parent;no general muon/nonmu label or radiation-tail calibration'))
    result=dict(passed=mismatch==0,ADC_samples=samples,ADC_mismatch=mismatch,
        detectors=checks,window_ns=[780,980],inclusive_samples=101,
        source_frame_index=50,new_G4=0,new_model_fit=0,reserved_forward=0,
        CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
        RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        scope='analog-method closure only;finitewindow truth charge differs from reconstructed signed raw by baseline/noise/clip;no source-fraction ADC additivity claim')
    (OUT/'analog_control.json').write_text(json.dumps(result,indent=2)+'\n')
    if details:
        with (OUT/'analog_charge.tsv').open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(details[0]),delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(details)
    print(result,flush=True);assert result['passed']

if __name__=='__main__':main()
