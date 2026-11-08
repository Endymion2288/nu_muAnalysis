"""Audit the two erroneously mapped historical bck candidates; never replace producer."""
import json
import time

import awkward as ak
import numpy as np
import uproot

from stage163_extract import OUT, SCINTILLATORS, configuration, load, write


def main():
    tick,cpu=time.perf_counter(),time.process_time()
    frozen=json.loads((OUT/'source_manifest_original.json').read_text())
    d=load();names=configuration()['features'];checks=[]
    for index in [258,259]:
        source=frozen['records'][index]
        assert source['origin']==82 and '/bck/' in source['path']
        cases=source['cases'];rows=np.asarray([c['row'] for c in cases]);entries=np.asarray([c['entry'] for c in cases])
        start,stop=int(entries.min()),int(entries.max())+1;take=entries-start
        fields=['run','eventID','Track_pz0']+[s+'_raw_charge' for s in SCINTILLATORS]
        with uproot.open(source['path'],array_cache=None) as file:
            v=file['nt'].arrays(fields,entry_start=start,entry_stop=stop,library='ak')
            identity=bool(np.array_equal(ak.to_numpy(v['run'])[take],d['run'][rows]) and np.array_equal(ak.to_numpy(v['eventID'])[take],d['eventID'][rows]))
            tracks=[ak.to_list(v['Track_pz0'][int(k)]) for k in take]
            pz=np.asarray([max(t)/1000 if t else np.nan for t in tracks],dtype='float32')
            modules=[]
            for detector in SCINTILLATORS:
                actual=ak.to_numpy(v[detector+'_raw_charge'])[take].astype('float32')
                old=d['x'][rows,names.index(detector+'_raw_charge')];finite=np.isfinite(old)
                mismatch=finite&(actual!=old)
                modules.append(dict(detector=detector,finite_reference_N=int(finite.sum()),mismatch_N=int(mismatch.sum()),
                    actual_negative_N=int((actual[finite]<0).sum()),reference_negative_N=int((old[finite]<0).sum()),
                    max_abs_pC=float(np.max(abs(actual[mismatch]-old[mismatch]))) if mismatch.any() else 0.))
            checks.append(dict(request_index=index,origin=82,source_index=source['source_index'],N=len(rows),
                candidate=source['path'],identity_exact=identity,pz0_exact=bool(np.array_equal(pz,d['pz'][rows].astype('float32'))),
                ROOT_read_bytes=int(file.file.source.num_requested_bytes),raw11=modules))
        assert identity and any(m['mismatch_N'] for m in modules)
    # Original Stage82 report/worker prove ALL three source datasets came from newly
    # produced scratch ntuple.root. Historical source['input'] was the rejected bck
    # candidate, not that produced PHYS. No conversion/reconstruction/substitution.
    for source in frozen['records']:
        if source['origin']==82:
            source.update(rejected_historical_candidate=source['path'],path=None,exists=False,file_bytes=None,
                producer='original Stage82 scratch merge PHYS not retained; historical bck is not the producer',
                waveform_integral_definition='missing original produced PHYS; no cross-producer replacement')
    write('source_manifest.json',frozen)
    from stage163_extract import table
    table('source_inventory.tsv',[{k:v for k,v in r.items() if k!='cases'} for r in frozen['records']])
    write('source_repair_audit.json',dict(passed=True,checks=checks,changed_original_source_requests=[257,258,259],
        cause='Manifest input field denotes rejected historical bck candidate; Stage82 production used separate scratch merge ntuple.root',
        evidence=['workbook/2026-11-03_stage82_k-support-learning-curve.md',
                  'AnalysisZipFramework/submission/run_ml_k_support.sh','ml/extract_k_support.py'],
        correction='All original Stage82 PHYS unavailable; appended fields unknown, X/parents/K/roles unchanged; no tolerance relaxation',
        known_missing_original_active_N=sum(r['active_N'] for r in frozen['records'] if not r['exists']),
        energy_fits_executed=0,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick))


if __name__=='__main__':main()
