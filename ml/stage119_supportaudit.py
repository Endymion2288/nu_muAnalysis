"""Independent role/support/feature audit for the actual compatible cohort."""
import json
import tarfile

import numpy as np

from audited_features import configuration
from stage119_curve_common import OUT,CACHE,LAYERS,load,masks,table,weights


def main():
    old=load('ntuples/energy_ml_stage119/old_input.npz');new=load('ntuples/energy_ml_stage119/curve_input.npz')
    checks={};exposure=set()
    for path in json.loads((OUT/'exposure_inputs.json').read_text()):exposure.update(map(tuple,load(path)['incoming']))
    roles={r:set(map(tuple,new['incoming'][new['role']==r])) for r in [0,1,2,3]}
    assert all(not roles[a]&roles[b] for a in roles for b in roles if a<b)
    assert not (roles[1]|roles[2]|roles[3])&exposure
    checks.update(new_role_incoming_disjoint=True,all_listed_old_exposure_excluded=True,old_exposure_unique=len(exposure),
        old_rows=len(old['role']),old_quarantine=int((old['role']==0).sum()),original_1016K_rows=int(((old['origin']==82)&(old['component']=='k')).sum()))
    assert checks['original_1016K_rows']==1016
    names=configuration()['features'];assert len(names)==62
    forbidden=['ML_mu_p_GeV','ML_track_p1_GeV','ML_track_pz1_GeV','ML_track_log_p1_over_p0']
    assert not set(names)&set(forbidden)
    assert len([n for n in names if n.endswith('_raw_charge')])==11
    checks.update(feature_names=names,forbidden_first_power_momenta_absent=True,raw11=True,
        actual_typed_nan_N=int(np.isnan(new['x']).sum()),finite_placeholder_minus999_N=int((new['x']==-999).sum()),
        signed_policy='original audited rule domains, not blanket negative-value deletion',
        original_cut='native fitted-charge selection unchanged; reco and truth pz>50 GeV; new feature inference raw11')
    rows=[]
    for name,d,use in [('old_train',old,old['role']==1),('old_cal',old,old['role']==2),('old_test_developed',old,old['role']==3),
            ('new_train_all',new,(new['role']==1)&(new['kind']=='expansion')),('new_development',new,(new['role']==2)&(new['kind']=='expansion')),
            ('new_reserved_support_only',new,(new['role']==3)&(new['kind']=='expansion'))]+[(f'curve_{f}N',new,new[f'train_{f}N']) for f in [1,2,4]]:
        ix=np.flatnonzero(use);sd={k:v[ix] for k,v in d.items()};w=weights(sd['incoming'])
        for layer,mask in masks(sd).items():
            rows.append(dict(cohort=name,stratum=layer,N=int(mask.sum()),incoming=len(np.unique(sd['incoming'][mask],axis=0)),
                weight_sum=float(w[mask].sum()),ESS=float(w[mask].sum()**2/(w[mask]@w[mask])) if mask.any() else 0))
    table('compatible_support.tsv',rows)
    byrun=[];cost=[];p=json.loads((OUT/'production_contract.json').read_text())
    for i,r in enumerate(p['requests']):
        use=new['source']==i;source=r['source']
        with tarfile.open(CACHE/f'production_{i}.tar.gz') as t:
            assert t.extractfile('result/exitcode.txt').read().strip()==b'0'
            for member in t.getnames():
                if not member.endswith('_time.txt'):continue
                values={}
                for line in t.extractfile(member).read().decode().splitlines():
                    if 'User time (seconds):' in line:values['user_s']=float(line.split(':')[-1])
                    if 'System time (seconds):' in line:values['system_s']=float(line.split(':')[-1])
                    if 'Maximum resident set size (kbytes):' in line:values['RSS_KiB']=int(line.split(':')[-1])
                    if 'Elapsed (wall clock)' in line:
                        a=list(map(float,line.split('): ')[-1].split(':')));values['wall_s']=sum(v*60**j for j,v in enumerate(a[::-1]))
                cost.append(dict(index=i,run=source['run'],step=member,**values))
        for layer,z in masks(new).items():
            take=use&z
            byrun.append(dict(index=i,run=source['run'],kind=source['kind'],component=source['component'],stratum=layer,
                parents=r['parent_N'],truth_reconstructed=len(r['entries']),selected_N=int(take.sum()),
                selected_incoming=len(np.unique(new['incoming'][take],axis=0)),old_exposure_N=int((take&(new['role']==0)).sum()),
                new_train_N=int((take&(new['role']==1)).sum()),new_development_N=int((take&(new['role']==2)).sum()),new_reserved_N=int((take&(new['role']==3)).sum()),
                file_probability=source['file_inclusion_probability']))
    table('compatible_source_support.tsv',byrun);table('compatible_production_cost.tsv',cost)
    checks['production_steps_CPU_s']=sum(r['user_s']+r['system_s'] for r in cost)
    checks['production_steps_wall_s_sum']=sum(r['wall_s'] for r in cost)
    checks['production_peak_step_RSS_KiB']=max(r['RSS_KiB'] for r in cost)
    checks['production_selected_N']=len(new['role']);checks['passed']=True
    (OUT/'support_audit.json').write_text(json.dumps(checks,indent=2)+'\n');print(checks,flush=True)


if __name__=='__main__':main()
