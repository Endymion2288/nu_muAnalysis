"""Retained-label material audit and final package consistency checks."""
import csv
import json

import numpy as np

from stage119_curve_common import OUT,load,table


def main():
    a=load('ntuples/energy_ml_stage119/genie_labels.npz');d=load('ml/artifacts/stage119/response_predictions.npz')
    lookup={(int(s),int(e)):i for i,(s,e) in enumerate(zip(a['source_index'],a['input_entry']))};rows=[];targets=[]
    parents={}
    for i in range(18):
        for r in json.loads((OUT/f'pythia_parent_{i}.json').read_text())['parents']:parents[(i,r['entry'])]=r
    for env in ['Standard','NUX']:
        use=np.flatnonzero(d['environment']==env);li=np.array([lookup[(int(d['source_index'][j]),int(d['input_entry'][j]))] for j in use])
        native=[parents[(int(d['source_index'][j]),int(d['input_entry'][j]))] for j in use]
        np.testing.assert_array_equal(a['eventID'][li],[r['eventID'] for r in native]);assert a['linked'][li].all()
        np.testing.assert_array_equal(d['incoming'][use],np.asarray([r['incoming'] for r in native],dtype='float32').astype(float))
        E=d['truth_E_GeV'][use];error=np.expm1(d['direct_cal'][use]-np.log(E));sign=d['incoming'][use,0]
        for layer,z in dict(all=np.ones(len(use),bool),E50_100=(E>=50)&(E<100),E100_200=(E>=100)&(E<200),pz50_100_trueE200=(d['pz'][use]<100)&(E>=200)).items():
            for group,g in [('all',np.ones(len(use),bool)),('direct_tail50',abs(error)>.5)]:
                mask=z&g
                for target in np.unique(a['target'][li][mask]):
                    for nu in np.unique(sign[mask]):
                        keep=mask&(a['target'][li]==target)&(sign==nu)
                        if keep.any():targets.append(dict(environment=env,stratum=layer,error_group=group,target_nuclear_PDG=int(target),nu_PDG=int(nu),N=int(keep.sum()),
                            target0='no unique status0 nucleus; includes free-nucleon cases or unknown, not assigned tungsten'))
    table('genie_selected_material.tsv',targets)
    audit=json.loads((OUT/'support_audit.json').read_text());curve=json.loads((OUT/'curve_summary.json').read_text());scope=json.loads((OUT/'genie_failure_scope.json').read_text())
    correction=json.loads((OUT/'same_N_correction_lock.json').read_text());assert correction['old_unique_incoming']==correction['new_curve_families']==1320
    assert audit['passed'] and audit['original_1016K_rows']==1016 and audit['old_quarantine']==17657
    assert curve['passed_validation'] and curve['reserved_predictions']==0 and scope['linked_selected_N']==527
    assert not any(curve['augmented_joint'].values())
    ref=list(csv.DictReader((OUT/'curve_reference_validation.tsv').open(),delimiter='\t'))
    paired=list(csv.DictReader((OUT/'curve_validation.tsv').open(),delimiter='\t'))
    contrast=list(csv.DictReader((OUT/'response_contrast_validation.tsv').open(),delimiter='\t'))
    assert ref and paired and contrast
    result=dict(passed=True,original_reference_scalar_controls=len(ref),original_reference_max_abs=max(float(r['abs_error']) for r in ref),
        paired_interval_checks=len(paired),paired_interval_max_abs=max(float(r['interval_max_abs']) for r in paired),
        environment_row_cluster_checks=len(contrast),environment_row_cluster_loss_max_abs=max(float(r['row_cluster_loss_max_abs']) for r in contrast),
        same_N_exact1320=True,original_K1016=True,original_quarantine17657=True,new_reserved_forwards0=True,
        genotype_labels_selected=527,W_known_selected=523,energy_target_achieved=False,
        required_input_gaps=['complete old/exansion GENIE-parent provenance','persisted neutron ancestry for most sensitive deposition','deployment proxy/oracle continuous-energy experiment','certified independent confirmation'],
        finished_scope='Stage118 bounded joint package: actual curve + fixed physical-response measurements, explicit input gaps under its stated exception')
    (OUT/'final_validation.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)


if __name__=='__main__':main()
