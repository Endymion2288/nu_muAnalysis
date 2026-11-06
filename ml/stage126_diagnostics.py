"""Check the recommended plateau threshold in protected strata and added events."""
import csv
import gzip
import json
import time
import numpy as np
from stage126_report import (CACHE, OUT, arrays, metrics, paired_curve, save, table,
                             working_points)

def main():
    start=time.perf_counter()
    rows=list(csv.DictReader((OUT/'scan.tsv').open(),delimiter='\t'))
    numeric=[{k:float(v) if v not in ['', 'NA'] and k not in ['selection','role'] else v for k,v in r.items()} for r in rows]
    recommendations=working_points(numeric)
    save('working_points.json',recommendations)
    (OUT/'report.log').write_text(json.dumps(recommendations,indent=2)+'\n')
    d=arrays(CACHE/'predictions.npz');test=d['evaluation_role']=='test';n=len(test)
    strata={'all':np.ones(n,bool),'E50_100':d['truth_E_GeV']<100,
            'E100_200':(d['truth_E_GeV']>=100)&(d['truth_E_GeV']<200),'E200_inf':d['truth_E_GeV']>=200,
            'pz50_100':d['reco_pz_GeV']<100,'pz100_250':(d['reco_pz_GeV']>=100)&(d['reco_pz_GeV']<250),
            'pz250_1000':(d['reco_pz_GeV']>=250)&(d['reco_pz_GeV']<1000),'pz1000_inf':d['reco_pz_GeV']>=1000,
            'high_y':d['y_lepton']>.5,'unconfirmed':~d['confirmed'],
            **{c:d['component']==c for c in ['pi','k','charm']},
            'nu_box':d['vertex_z_mm']<-1900,'lead_block':d['vertex_z_mm']>-1800}
    pairs=[];added=[]
    for selection,pzcut in [('pz50',np.ones(n,bool)),('pz100',(d['reco_pz_GeV']>100)&(d['incoming'][:,3]>100000))]:
        for name,mask in strata.items():
            cohort=test&pzcut&mask
            before=metrics(d,cohort&(d['radius_mm']<100));after=metrics(d,cohort&(d['radius_mm']<125))
            if before is None:continue
            ci=paired_curve(d,cohort,[100,125],20261106126)[1]
            pairs.append(dict(selection=selection,stratum=name,baseline_N=before['N'],expanded_N=after['N'],
                log_RMSE_ratio=after['log_RMSE']/before['log_RMSE'],**{k:v for k,v in ci.items() if k!='radius_mm'}))
        for label,lo,hi in [('baseline',0,100),('added100_125',100,125),('outer105_125',105,125)]:
            m=metrics(d,test&pzcut&(d['radius_mm']>=lo)&(d['radius_mm']<hi))
            added.append(dict(selection=selection,region=label,**m))
    table('stratum_paired125.tsv',pairs);table('added_response.tsv',added)
    protocol=json.loads((OUT/'protocol.json').read_text())
    source_ids={s['index'] for s in protocol['sources']}
    with gzip.open(OUT.parents[1]/'ntuples/energy_ml_stage55/extraction_metadata.json.gz','rt') as f:
        original=[r for r in json.load(f) if r['index'] in source_ids]
    expanded=json.loads((OUT/'extraction_metadata.json').read_text())
    names=expanded['cutflow_names']
    assert len(original)==254 and all(r['cutflow_names']==names for r in original)
    table('cutflow_comparison.tsv',[dict(cut_name=name,
        original100_N=sum(r['cutflow_passed'][j] for r in original),
        no_radius_N=sum(r['cutflow_passed'][j] for r in expanded['sources']),
        extra_no_radius_N=sum(r['cutflow_passed'][j] for r in expanded['sources'])-sum(r['cutflow_passed'][j] for r in original))
        for j,name in enumerate(names)])
    save('diagnostics_resources.json',dict(wall_s=time.perf_counter()-start,CPU_s=time.process_time(),
        uncertainty='conditional incoming draws; sparse strata do not establish source/systematic closure'))
    print(json.dumps(recommendations,indent=2))

if __name__=='__main__':main()
