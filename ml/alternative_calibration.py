"""Known native MC Calo calibration representation, validated before release."""
import json
from pathlib import Path

import numpy as np

from audited_features import REPO, configuration

OUT=REPO/'workbook/stage70_energy_ml'


def payload_scales(run):
    audit=json.loads((OUT/'calo_conditions_qa.json').read_text())
    assert audit['resolved_tag']=='WAVE-Calibration-03-LG'
    def charges(tag):
        row=next(r for r in audit['measurements'] if r['tag']==tag and r['run']==run)
        return np.array([next(v['payload']['charge_ref'] for v in row['rows'] if v['channel']==j) for j in range(4)])
    current=charges('WAVE-Calibration-03-LG');reference=charges('WAVE-Calibration-01-LG')
    assert (current>0).all() and (reference>0).all()
    return current/reference


def reference_matrix(x,run):
    """Only re-express four module E_EM and their existing total; truth-free."""
    names=configuration()['features'];result=x.copy();columns=[names.index(f'ML_calo{j}_E_EM_GeV') for j in range(4)]
    result[:,columns]=(x[:,columns].astype(float)*payload_scales(run)).astype('float32')
    result[:,names.index('ML_calo_total_E_EM_GeV')]=np.sum(result[:,columns].astype(float),axis=1).astype('float32')
    return result


def main():
    with np.load(REPO/'ntuples/energy_ml_stage70/0/selected.npz') as z:
        current={k:z[k] for k in z.files if k!='metadata_json'};current_md=json.loads(str(z['metadata_json']))
    with np.load('/tmp/nu_mu_stage70_qa/pi/reference_full.npz') as z:
        reference={k:z[k] for k in z.files if k!='metadata_json'};reference_md=json.loads(str(z['metadata_json']))
    for k in ['run','eventID','input_entry','truth_E_GeV','incoming','raw_charge','status','calo_status']:
        np.testing.assert_array_equal(current[k],reference[k])
    assert current_md['cutflow_names']==reference_md['cutflow_names'] and current_md['cutflow_passed']==reference_md['cutflow_passed']
    names=configuration()['features'];columns=[names.index(f'ML_calo{j}_E_EM_GeV') for j in range(4)]+[names.index('ML_calo_total_E_EM_GeV')]
    other=[j for j in range(62) if j not in columns]
    np.testing.assert_array_equal(current['x'][:,other],reference['x'][:,other])
    converted=reference_matrix(current['x'],200080)
    np.testing.assert_allclose(converted,reference['x'],rtol=1e-6,atol=1e-6,equal_nan=True)
    scales=payload_scales(200080);np.testing.assert_array_equal(scales,payload_scales(200081))
    values=[]
    for j in columns:
        a=converted[:,j].astype(float);b=reference['x'][:,j].astype(float);finite=np.isfinite(a)&np.isfinite(b)
        values.append(dict(feature=names[j],finite_N=int(finite.sum()),max_abs_difference_GeV=float(abs(a[finite]-b[finite]).max()) if finite.any() else 0.,
                           max_relative_difference=float(np.max(abs(a[finite]-b[finite])/np.maximum(abs(b[finite]),1e-12))) if finite.any() else 0.))
    import uproot
    checks=[]
    for component in ['pi','k']:
        with uproot.open(f'/tmp/nu_mu_stage70_qa/{component}/ntuple.root') as f:
            data=f['nt'].arrays([f'Calo{i}_{k}' for i in range(4) for k in ['charge','status','E_EM']],entry_stop=16,library='np')
        for j in range(4):
            take=(data[f'Calo{j}_status']==0)&(data[f'Calo{j}_charge']!=0)
            if not take.any():continue
            ratio=data[f'Calo{j}_E_EM'][take].astype(float)/data[f'Calo{j}_charge'][take]
            np.testing.assert_allclose(ratio,330/.07569999992847443,rtol=2e-6)
            checks.append(dict(component=component,module=j,N=int(take.sum()),native_current_MeV_per_pC=float(np.median(ratio))))
    result=dict(passed=True,reference_tag='WAVE-Calibration-01-LG',produced_tag='WAVE-Calibration-03-LG',
                scales_by_module=scales.tolist(),source='actual COOL charge_ref and unmodified native MC E_EM formula; not residual fitted',
                full_pi_raw_N=784,selected_N=len(current['run']),unchanged_feature_columns_exact=57,
                identity_raw_status_truth_exact=True,full_cutflow_exact=True,calo_comparison=values,
                comparison_rtol=1e-6,comparison_atol_GeV=1e-6,K_prefix_checks=checks,
                limits='full paired reference only for pi; K uses same measured payloads and prefix formula, no full historical K counterpart; complete production response/systematics not certified',
                new_RDO_reconstruction_jobs=0,model_fits=0)
    assert not (OUT/'calibration_closure.json').exists()
    (OUT/'calibration_closure.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
