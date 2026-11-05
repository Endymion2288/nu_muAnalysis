"""Freeze sparse hadronization readout production from every sampled parent."""
import json

import numpy as np

from stage119_curve_common import OUT


def main():
    p=json.loads((OUT/'pythia_contract.json').read_text());requests=[];audit=[]
    for i,s in enumerate(p['sources']):
        a=json.loads((OUT/f'pythia_parent_{i}.json').read_text());rows=a['parents']
        assert a['source']==s and [r['entry'] for r in rows]==list(range(len(rows)))
        selected=[r for r in rows if r['eligible']]
        # PhysicsNtuple stores incoming four-vector components as Float_t.
        incoming=np.asarray([r['incoming'] for r in selected],dtype='float32').astype(float).tolist()
        requests.append(dict(source={**s, 'kind':'hadronization'},parent_N=len(rows),entries=[r['entry'] for r in selected],
            hits=s['input'],eventID=[r['eventID'] for r in selected],incoming=incoming,
            incoming_conversion='native HepMC double -> ntuple Float_t, exact after declared conversion',
            criterion='all parents, original truth numu/pz/r/z conservative superset only'))
        for lo,hi in [(50,100),(100,200),(200,float('inf'))]:
            keep=[r for r in selected if lo<=r.get('E_GeV',0)<hi]
            audit.append(dict(index=i,run=s['run'],environment=s['environment'],component=s['component'],parents=len(rows),
                truth_eligible=len(selected),E_low_GeV=lo,E_high_GeV=hi,eligible_in_bin=len(keep),CPU_s=a['CPU_s'],wall_s=a['wall_s']))
    from stage119_curve_common import table
    table('pythia_parent_support.tsv',audit)
    result=dict(stage=119,requests=requests,scope='18 uniformly frozen complete HITS parents, no source replacement',
        policies='official sparse digi/reco/merge with unchanged settings and actual payload-only01 representation',
        roles='fixed-model mechanism environment only; zero energy fitting; HERMES held from energy development',
        resources=dict(jobs=18,cpus_each=1,memory_MB_each=4000,disk_MB_each=8000,wall_s_each=28800,aggregate_CPU_s=108000),
        independence='no assumption of equal row/event across tunes, no contribution to learning-curve N')
    (OUT/'pythia_production_contract.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Pythia parents',sum(r['parent_N'] for r in requests),'eligible',sum(len(r['entries']) for r in requests),flush=True)


if __name__=='__main__':main()
