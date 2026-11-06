"""Independent checks of identity, grid optimum, geometry and measured summaries."""
import csv
import gzip
import json
import numpy as np
import yaml
from stage127_scan import (ROOT,OUT,CACHE,load,rectangle,bounds,geometry,parent_count,table,save)


def main():
    d,coords=load();decision=json.loads((OUT/'decisions.json').read_text());c=decision['recommended']['geometry']
    m=rectangle(d,c);r100=d['radius_mm']<100;r125=d['radius_mm']<125
    xor=int(np.count_nonzero(m^r125));assert xor==0
    assert not (r100&~m).any()
    expected=json.loads((OUT/'coordinate_validation.json').read_text())
    assert expected['N']==len(m)==83300 and expected['old_coordinates_exact_N']==81313
    assert coords['hist50'].sum()==618779 and coords['hist100'].sum()==581501
    evaluation=list(csv.DictReader((OUT/'evaluation.tsv').open(),delimiter='\t'))
    checks=[]
    for selection in ['pz100','pz50']:
        cohort=d['evaluation_role']=='test'
        if selection=='pz100':cohort &= (d['reco_pz_GeV']>100)&(d['incoming'][:,3]>100000)
        for policy,mask in [('circle100',r100),('circle125',r125),(f"rectangle_{c['candidate_id']}",m)]:
            use=cohort&mask;e=d['direct_cal'][use]-np.log(d['truth_E_GeV'][use]);acc={}
            for k,v in zip(map(tuple,d['incoming'][use]),e):
                a=acc.setdefault(k,[0,0.,0.]);a[0]+=1;a[1]+=v*v;a[2]+=abs(np.expm1(v))>.5
            rmse=float(np.sqrt(np.mean([a[1]/a[0] for a in acc.values()])))
            tail=float(np.mean([a[2]/a[0] for a in acc.values()]))
            row=next(r for r in evaluation if r['selection']==selection and r['role']=='test' and r['policy']==policy)
            assert int(row['N'])==int(use.sum())
            np.testing.assert_allclose(rmse,float(row['log_RMSE']),rtol=1e-13)
            np.testing.assert_allclose(tail,float(row['tail50']),rtol=1e-13)
            checks.append(dict(selection=selection,policy=policy,N=int(use.sum()),independent_log_RMSE=rmse))
    with gzip.open(OUT/'cal_grid.tsv.gz','rt') as f:rows=list(csv.DictReader(f,delimiter='\t'))
    assert len(rows)==50750
    plateau={}
    representatives=[]
    windows=[(0,0,90,90),(0,0,100,100),(0,0,110,90),(0,0,90,110),
             (0,0,110,100),(0,0,100,110),(0,0,110,110),(0,0,120,115),
             (0,0,120,120),(0,0,130,130),(10,-21,120,115),(10,-21,120,140)]
    for selection in ['pz100','pz50']:
        rr=[r for r in rows if r['selection']==selection];max_n=max(int(r['N']) for r in rr)
        full=[r for r in rr if int(r['N'])==max_n]
        chosen=next(r for r in full if int(r['candidate_id'])==c['candidate_id'])
        area=min(int(r['area_mm2']) for r in full);assert int(chosen['area_mm2'])==area
        centers=min(int(r['cx'])**2+int(r['cy'])**2 for r in full if int(r['area_mm2'])==area)
        assert c['cx']**2+c['cy']**2==centers
        plateau[selection]=dict(max_cal_N=max_n,full_yield_candidates=len(full),minimum_area_mm2=area,
            width_range_mm=[min(int(r['width_mm']) for r in full),max(int(r['width_mm']) for r in full)],
            height_range_mm=[min(int(r['height_mm']) for r in full),max(int(r['height_mm']) for r in full)])
        for cx,cy,hx,hy in windows:
            r=next(r for r in rr if tuple(int(r[k]) for k in ['cx','cy','hx','hy'])==(cx,cy,hx,hy))
            q=dict(r);cc={k:int(r[k]) for k in ['candidate_id','cx','cy','hx','hy']}
            all_mask=rectangle(d,cc)
            if selection=='pz100':all_mask &= (d['reco_pz_GeV']>100)&(d['incoming'][:,3]>100000)
            parent=parent_count(coords,cc,selection)
            q.update(all_records_N=int(all_mask.sum()),parent_inside_N=parent,efficiency_within_geometry=float(all_mask.sum()/parent))
            representatives.append(q)
    table('representative_windows.tsv',representatives)
    original=yaml.safe_load((ROOT/'AnalysisZipFramework/config/ml_low_energy_cuts.yaml').read_text())
    config=yaml.safe_load((OUT/'recommended_cuts_pz50.yaml').read_text())
    assert config['Cuts']['In Faser Nu Box or Lead Block']==original['Cuts']['In Faser Nu Box or Lead Block']
    original['Cuts'].pop('Truth dec r < 100 mm');config['Cuts'].pop('Truth vertex in cuboid');assert original==config
    for original_name,new_name in [('cuts.yaml','cuts_cuboid.yaml'),('ml_low_energy_cuts.yaml','ml_cuboid_cuts.yaml')]:
        original=yaml.safe_load((ROOT/'AnalysisZipFramework/config'/original_name).read_text())
        delivered=yaml.safe_load((ROOT/'AnalysisZipFramework/config'/new_name).read_text())
        old=original['Cuts'].pop('Truth dec r < 100 mm')
        new=delivered['Cuts'].pop('Truth vertex in cuboid')
        assert new.pop('expression')==yaml.safe_load((OUT/'recommended_cuts_pz100.yaml').read_text())['Cuts']['Truth vertex in cuboid']['expression']
        old.pop('expression');assert old==new and original==delivered
    save('independent_validation.json',dict(passed=True,rectangle_vs_circle125_xor_records=xor,
      baseline_circle100_events_removed=0,independent_arithmetic=checks,plateau=plateau,
      geometry_replacement_only=True,delivered_config_histograms_preserved=True,new_fits=0,new_model_forwards=0))
    print(json.dumps(dict(passed=True,xor=xor,plateau=plateau),indent=2))


if __name__=='__main__':main()
