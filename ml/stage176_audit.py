"""Independent scalar plane/source partitions on retained actual segment records."""
import gzip,json,math
from pathlib import Path
ROOT=Path.cwd();OUT=ROOT/'workbook/stage176_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage176'
p=json.loads((OUT/'protocol.json').read_text());checks=[]
indices=[p['preflight_index']]+(p['remaining_indices'] if json.loads((OUT/'admission.json').read_text())['admitted'] else [])
for index in indices:
    with gzip.open(CACHE/f'parent_{index}_lineage.json.gz','rt') as f:raw=json.load(f)
    with gzip.open(CACHE/f'parent_{index}_qa_hits.json.gz','rt') as f:saved=json.load(f)
    report=json.loads((OUT/f'parent_{index}_S0.json').read_text())
    for name,hits in raw['daq_hits'].items():
        assert len(hits)==len(raw['daq_birth_groups'][name])==len(saved[name])
        for a,b in zip(hits,saved[name]):assert a[4]==b[0] and a[7]==b[3]
    if not report.get('plane_supported'):
        checks.append(dict(index=index,plane_supported=False,ordered_hits_exact=True));continue
    state=report['surface'];normal=state['normal'];center=state['center_mm'];primary=raw['muon_primaries'][0]
    if sum(a*b for a,b in zip(normal,primary[5:8]))<0:normal=[-v for v in normal]
    def distance(x):return sum((a-b)*c for a,b,c in zip(x,center,normal))
    groups={0:'primary_muon_direct',-1:'other_root',-2:'unknown_root'}
    for a,b in zip(raw['muon_births'],report['muon_births']):
        z=distance(a['xyz_mm']);assert abs(z-b['signed_distance_mm'])<1e-9
        side='before_S0' if z<0 else 'after_S0' if z>0 else 'on_S0';assert side==b['S0_side'];groups[a['group']]=side
    crossings=[]
    for ordinal,row in enumerate(raw['muon_segments']):
        if int(row[0])!=int(primary[0]):continue
        a,b=distance(row[1:4]),distance(row[4:7])
        if a<=0 and b>0 or a>0 and b<=0:crossings.append(ordinal)
    assert crossings==[c['ordinal'] for c in report['crossings']]
    for name,hits in raw['daq_hits'].items():
        counts={};energy={}
        for group,h in zip(raw['daq_birth_groups'][name],hits):
            tag=groups[group];counts[tag]=counts.get(tag,0)+1;energy[tag]=energy.get(tag,0.)+h[5]
        r=report['hit_source_partition'][name];assert counts==r['hit_counts']
        assert all(abs(energy[k]-r['corrected_SD_response_MeV'][k])<=1e-10*max(1,abs(v)) for k,v in energy.items())
    checks.append(dict(index=index,plane_supported=True,ordered_hits_exact=True,births_scalar_checked=len(raw['muon_births']),segments_scalar_checked=len(raw['muon_segments']),source_partition_exact=True))
(OUT/'independent_validation.json').write_text(json.dumps(dict(passed=True,parents=checks,energy_fits=0,source_charge_not_inferred=True,overall_complete=False),indent=2)+'\n')

if len(indices)==1:
    report=json.loads((OUT/f'parent_{indices[0]}_S0.json').read_text());counts={}
    for b in report.get('muon_births',[]):
        key=b['S0_side']+':'+b['process']+':'+str(b['pdg']);counts[key]=counts.get(key,0)+1
    summary=dict(index=indices[0],native_S0_supported=report['native_S0_supported'],surface=report.get('surface'),
        fitted_E_mu_S0_GeV=report.get('fitted_E_mu_S0_GeV'),actual_primary_initial_E_GeV=report.get('actual_primary_initial_E_GeV'),
        crossings=report.get('crossings'),birth_process_side_counts=counts,hit_source_partition=report.get('hit_source_partition'),
        original_selected_raw11_status_pz0_exact=report['original_selected_raw11_status_pz0_exact'],
        scope='One fixed natural train parent;all-time SD response,not same-window analog charge;no energy closure or population claim.',remaining11_not_admitted=True)
    (OUT/'physical_pilot_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
