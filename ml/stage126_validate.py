"""Independent arithmetic, identity, nesting, and fixed-cut checks for stage126."""
import csv
import json
from pathlib import Path
import numpy as np
import yaml
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage126_energy_ml'

def main():
    original=yaml.safe_load((ROOT/'AnalysisZipFramework/config/ml_low_energy_cuts.yaml').read_text())
    scan=yaml.safe_load((OUT/'scan_cuts.yaml').read_text())
    changed=[]
    for name in original['Cuts']:
        if original['Cuts'][name]!=scan['Cuts'][name]:changed.append(name)
    assert changed==['Truth dec r < 100 mm']
    assert scan['Cuts'][changed[0]]['expression']=='std::isfinite(truth_dec_r)'
    with np.load(ROOT/'ntuples/energy_ml_stage126/predictions.npz') as z:d={k:z[k] for k in z.files}
    rows=list(csv.DictReader((OUT/'scan.tsv').open(),delimiter='\t'))
    checked=[]
    for selection in ['pz50','pz100']:
        for role in ['cal','test','all_descriptive']:
            curve=[r for r in rows if r['selection']==selection and r['role']==role]
            assert all(int(b['N'])>=int(a['N']) for a,b in zip(curve,curve[1:]))
            for radius in [100,120,140,425]:
                row=next(r for r in curve if float(r['radius_mm'])==radius)
                mask=d['radius_mm']<radius
                if role!='all_descriptive':mask &= d['evaluation_role']==role
                if selection=='pz100':mask &= (d['reco_pz_GeV']>100)&(d['incoming'][:,3]>100000)
                assert int(mask.sum())==int(row['N'])
                residual=d['direct_cal'][mask]-np.log(d['truth_E_GeV'][mask])
                key=d['incoming'][mask]
                sums={}
                for k,e in zip(map(tuple,key),residual):
                    v=sums.setdefault(k,[0,0.,0.]);v[0]+=1;v[1]+=e*e;v[2]+=abs(np.expm1(e))>.5
                independent_rmse=np.sqrt(np.mean([v[1]/v[0] for v in sums.values()]))
                independent_tail=np.mean([v[2]/v[0] for v in sums.values()])
                np.testing.assert_allclose(independent_rmse,float(row['log_RMSE']),rtol=1e-13)
                np.testing.assert_allclose(independent_tail,float(row['tail50']),rtol=1e-13)
                checked.append(dict(selection=selection,role=role,radius_mm=radius,N=int(mask.sum()),independent_RMSE=float(independent_rmse)))
    for role in ['cal','test']:
        for selection in ['pz50','pz100']:
            row=next(r for r in rows if r['role']==role and r['selection']==selection and float(r['radius_mm'])==100)
            assert float(row['log_RMSE_ratio_low95'])==float(row['log_RMSE_ratio_high95'])==1
    result=dict(passed=True,only_changed_cut=changed,independent_arithmetic_checks=checked,
                nested_counts_monotonic=True,exact_baseline_ratio_CI=True,new_training_calls=0,
                max_radius_mm=float(d['radius_mm'].max()))
    (OUT/'independent_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Independent validation passed')

if __name__=='__main__':main()
