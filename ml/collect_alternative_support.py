#!/usr/bin/env python3
"""Measure stage70 selected and genuinely additional keys; never fit or infer ML."""
import csv
import json
import resource
import time
from pathlib import Path

import numpy as np

from audited_features import REPO, SCINTILLATORS, WAVE_INVALID, FIT_INVALID, configuration
from alternative_calibration import reference_matrix

OUT = REPO/'workbook/stage70_energy_ml'
CACHE = REPO/'ntuples/energy_ml_stage70'


def write_table(path, records):
    with path.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]), delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(records)


def masks(d):
    e, p, y = d['truth_E_GeV'], d['reco_pz_GeV'], d['y_lepton']
    valid = d['confirmed'] & np.isfinite(y) & (y >= 0) & (y <= 1)
    m = dict(all=np.ones(len(e), bool), E50_100=(e>=50)&(e<100), E100_200=(e>=100)&(e<200),
             E200_inf=e>=200, pz50_100=(p>=50)&(p<100), high_y=y>=.8,
             unconfirmed=~d['confirmed'], input_missing=np.isnan(d['x']).any(axis=1))
    for k in ['E50_100', 'E100_200']:
        m[k+'_confirmed_low_transfer'] = m[k] & valid & (y < .2)
    m['pz50_100_trueE200_inf'] = m['pz50_100'] & m['E200_inf']
    m['pz50_100_high_y'] = m['pz50_100'] & m['high_y']
    m['pz50_100_unconfirmed'] = m['pz50_100'] & m['unconfirmed']
    for lo,hi in zip([50,75,100,150,200,400,800,1600,3200], [75,100,150,200,400,800,1600,3200,6400]):
        m[f'E{lo}_{hi}'] = (e>=lo)&(e<hi)
    m['E6400_inf'] = e>=6400
    return m


def main():
    tick, cpu = time.perf_counter(), time.process_time()
    protocol = json.loads((OUT/'protocol.json').read_text())
    resources = json.loads((OUT/'condor_resources.json').read_text())
    delivered = [r['proc'] for r in resources['jobs'] if r['success']]
    assert delivered, 'no complete source delivered; selected support is unmeasured'
    measured_components={protocol['source_contract']['sources'][i]['component'] for i in delivered}|{'all'}
    cfg = configuration()
    with np.load(REPO/'ntuples/energy_ml_stage55/dataset.npz') as z:
        old = {k:z[k] for k in ['incoming','run','eventID','source','partition','group','nominal','train_eligible','cal_eligible','truth_E_GeV','y_lepton','confirmed','reco_pz_GeV']}
    # Includes all stage55 developed selected events, not only train-eligible
    # nominal events, and does not open any locked-test event arrays.
    known = set(map(tuple, old['incoming']))
    parts, metadata, cutflows = [], [], []
    for index,source in enumerate(protocol['source_contract']['sources']):
        if index not in delivered:
            continue  # A failed full source is unmeasured, never a zero-yield source.
        result = CACHE/str(index)
        assert (result/'exitcode.txt').read_text().strip() == '0'
        with np.load(result/'selected.npz') as z:
            md = json.loads(str(z['metadata_json']))
            d = {k:z[k] for k in z.files if k != 'metadata_json'}
        n = len(d['run'])
        assert md['raw_N'] == protocol['input_events_by_source'][index]
        assert md['features'] == cfg['features'] and d['x'].shape == (n,62)
        assert np.all(d['run'] == source['run']) and len(set(d['eventID'])) == n
        assert np.all(d['reco_pz_GeV'] > 50) and np.isfinite(d['incoming']).all()
        assert np.all(d['incoming'][:,3] > 50000)
        np.testing.assert_array_equal(d['x'][:,0], d['reco_pz_GeV'].astype('float32'))
        assert np.isfinite(d['truth_E_GeV']).all() and (d['truth_E_GeV'] > 50).all()
        np.testing.assert_allclose(d['truth_E_GeV'], np.linalg.norm(d['incoming'][:,1:],axis=1)/1000, rtol=1e-10)
        valid = d['confirmed'] & np.isfinite(d['y_lepton']) & (d['y_lepton']>=0) & (d['y_lepton']<=1)
        assert np.all(~d['confirmed'] | (d['primary_valid'] & (d['primary_candidates']==1)))
        assert int((d['confirmed'] & ~valid).sum()) == 0
        for j,detector in enumerate(SCINTILLATORS):
            v = d['raw_charge'][:,j].astype('float32')
            v[(d['status'][:,j].astype(int)&WAVE_INVALID)!=0] = np.nan
            v[~np.isfinite(v)] = np.nan
            np.testing.assert_array_equal(d['x'][:,cfg['features'].index(detector+'_raw_charge')],v)
        calo = np.column_stack([d['x'][:,cfg['features'].index(f'ML_calo{j}_E_EM_GeV')] for j in range(4)])
        assert np.isnan(calo[(d['calo_status'].astype(int)&FIT_INVALID)!=0]).all()
        np.testing.assert_array_equal(d['x'][:,cfg['features'].index('ML_calo_total_E_EM_GeV')],np.sum(calo.astype(float),axis=1).astype('float32'))
        for j,name in enumerate(cfg['features']):
            rule = cfg['rules'][name];values = d['x'][:,j];finite=values[np.isfinite(values)]
            if rule['domain'] in ['positive','nonnegative','count']:
                assert (finite>=0).all()
            assert not np.isin(finite,rule.get('sentinels',[])).any()
        d.update(source_index=np.full(n,index,int),component=np.full(n,source['component']),group=np.full(n,source['group']))
        parts.append(d)
        metadata.append(md)
        for name,passed in zip(md['cutflow_names'],md['cutflow_passed']):
            cutflows.append(dict(component=source['component'],group=source['group'],cut=name,passed=passed))
        # Retain compact per-job production diagnostics without duplicate ROOT.
        (OUT/f"production_{source['component']}.txt").write_text((result/'production_validation.txt').read_text())
        (OUT/f"extraction_{source['component']}.json").write_text(json.dumps(md,indent=2)+'\n')
    d = {k:np.concatenate([p[k] for p in parts]) for k in parts[0]}
    keys = list(map(tuple,d['incoming']))
    reused = np.array([k in known for k in keys])
    seen = set()
    internal = np.zeros(len(keys),bool)
    for i,key in enumerate(keys):
        internal[i] = key in seen
        seen.add(key)
    # A stable source-index/input-entry order defines ownership for new keys.
    keep = ~reused & ~internal
    assert not set(k for k,m in zip(keys,keep) if m)&known
    assert int(keep.sum()) == len(set(keys)-known)
    # Independent numpy structured-row intersection verifies the exact key mask.
    _, inverse = np.unique(np.vstack([old['incoming'],d['incoming']]),axis=0,return_inverse=True)
    np.testing.assert_array_equal(reused,np.isin(inverse[len(old['incoming']):],inverse[:len(old['incoming'])]))
    np.testing.assert_array_equal(np.flatnonzero(~internal),np.sort(np.unique(d['incoming'],axis=0,return_index=True)[1]))
    # Typed columns do not establish common calibration. Re-expression from the
    # measured native payloads is released only after the independent full pi
    # closure, preserving the produced values as well as the reference values.
    conversion=json.loads((OUT/'calo_conversion_qa.json').read_text())
    reference=next(r['E_EM_over_charge_MeV_per_pC'] for r in conversion if r['sample']=='F7_nominal' and r['module']==0)
    produced=next(r['E_EM_over_charge_MeV_per_pC'] for r in conversion if r['sample']=='new_pi' and r['module']==0)
    assert not np.isclose(reference,produced,rtol=1e-4)
    closure=json.loads((OUT/'calibration_closure.json').read_text());assert closure['passed']
    d['x_produced']=d['x'].copy()
    for run in np.unique(d['run']):
        take=d['run']==run;d['x'][take]=reference_matrix(d['x_produced'][take],int(run))
    d.update(known_stage55_reuse=reused,pilot_internal_repeat=internal,new_training_support=keep)
    rows, features, charges, identities = [], [], [], []
    mm=masks(d)
    for component in ['pi','k','all']:
        component_mask = np.ones(len(keys),bool) if component=='all' else d['component']==component
        for state,selection in [('selected',np.ones(len(keys),bool)),('known_reuse',reused),('internal_repeat',internal),('new_support',keep)]:
            for stratum,mask in mm.items():
                take = component_mask & selection & mask
                y=d['y_lepton'];valid=d['confirmed']&np.isfinite(y)&(y>=0)&(y<=1)
                rows.append(dict(component=component,state=state,stratum=stratum,N=int(take.sum()),
                                 source_measured=component in measured_components,
                                 sources=len(set(d['source_index'][take])),groups=len(set(d['group'][take])),
                                 primary_unique_N=int((take&d['primary_valid']).sum()),confirmed_N=int((take&d['confirmed']).sum()),
                                 valid_y_N=int((take&valid).sum()),
                                 low_transfer_N=int((take&valid&(y<.2)).sum()),
                                 medium_transfer_N=int((take&valid&(y>=.2)&(y<.8)).sum()),
                                 high_transfer_N=int((take&valid&(y>=.8)).sum()),
                                 interpretation=('full source not delivered; yield未测量' if component not in measured_components
                                                 else 'empty measured support; performance未测量' if not take.any() else 'delivered development support with native Calo reference conversion; no independence/power claim')))
        for state,selection in [('selected',np.ones(len(keys),bool)),('new_support',keep)]:
            take=component_mask&selection
            for j,name in enumerate(cfg['features']):
                v=d['x'][take,j];vfinite=v[np.isfinite(v)]
                features.append(dict(component=component,state=state,source_measured=component in measured_components,feature=name,domain=cfg['rules'][name]['domain'],N=len(v),
                                     missing_N=int(np.isnan(v).sum()),negative_N=int((v<0).sum()),minus1_N=int((v==-1).sum()),
                                     minus999_N=int((v==-999).sum()),min=float(vfinite.min()) if len(vfinite) else '未测量',
                                     median=float(np.median(vfinite)) if len(vfinite) else '未测量',max=float(vfinite.max()) if len(vfinite) else '未测量'))
            for j,detector in enumerate(SCINTILLATORS):
                v=d['raw_charge'][take,j];st=d['status'][take,j].astype(int)
                charges.append(dict(component=component,state=state,source_measured=component in measured_components,detector=detector,N=len(v),raw_negative_N=int((v<0).sum()),
                                    raw_nonfinite_N=int((~np.isfinite(v)).sum()),wave_invalid_N=int(((st&WAVE_INVALID)!=0).sum()),
                                    fit_failure_N=int(((st&48)!=0).sum()),
                                    finite_raw_with_fit_failure_N=int((np.isfinite(v)&((st&48)!=0)&((st&WAVE_INVALID)==0)).sum()),
                                    status_counts=json.dumps({str(int(k)):int(v) for k,v in zip(*np.unique(st,return_counts=True))})))
        take=component_mask
        identities.append(dict(component=component,selected_N=int(take.sum()),known_stage55_reuse_N=int((take&reused).sum()),
                               source_measured=component in measured_components,
                               pilot_internal_repeat_N=int((take&internal).sum()),new_support_N=int((take&keep).sum()),
                               internal_repeat_not_known_N=int((take&internal&~reused).sum()),
                               unique_selected_keys=len(set(k for k,m in zip(keys,take) if m)),
                               unique_new_keys=len(set(k for k,m in zip(keys,take&keep) if m))))
    old_support=[]
    for component in ['pi','k']:
        source=next(s for s in protocol['source_contract']['sources'] if s['component']==component)
        group=(old['group']==source['group'])
        for role in ['train','calibration','validation']:
            take=group&(old['partition']==role)
            old_support.append(dict(component=component,group=source['group'],stage55_role=role,N=int(take.sum()),
                                    sources=len(set(old['source'][take])),eligible_train_N=int((take&old['train_eligible']).sum())))
    # Context is the existing F7 nominal training cohort, not the larger mixture
    # cache that is used conservatively for the known-key veto.
    old_train=old['nominal']&old['train_eligible']
    assert int(old_train.sum())==41447
    oe,op,oy=old['truth_E_GeV'],old['reco_pz_GeV'],old['y_lepton']
    context_masks=dict(all=np.ones(len(oe),bool),E50_100=(oe>=50)&(oe<100),E100_200=(oe>=100)&(oe<200),
                       pz50_100_trueE200_inf=(op>=50)&(op<100)&(oe>=200),
                       pz50_100_high_y=(op>=50)&(op<100)&(oy>=.8),
                       pz50_100_unconfirmed=(op>=50)&(op<100)&~old['confirmed'],
                       high_y=oy>=.8,unconfirmed=~old['confirmed'],E3200_6400=(oe>=3200)&(oe<6400))
    context=[]
    for stratum,mask in context_masks.items():
        take=old_train&mask
        increment=int((keep&mm[stratum]).sum())
        context.append(dict(stratum=stratum,F7_train_N=int(take.sum()),F7_train_sources=len(set(old['source'][take])),
                            F7_train_groups=len(set(old['group'][take])),new_support_N=increment,
                            increment_over_F7_train_pct=100*increment/int(take.sum()) if take.any() else '未测量'))
    write_table(OUT/'training_context.tsv',context)
    for name,records in [('support',rows),('feature_validity',features),('raw_validity',charges),('identities',identities),('cutflow',cutflows),('existing_group_support',old_support)]:
        write_table(OUT/(name+'.tsv'),records)
    summary=dict(selected_N=len(keys),new_support_N=int(keep.sum()),new_support_sources=len(set(d['source_index'][keep])),
                 known_stage55_reuse_N=int(reused.sum()),internal_repeat_N=int(internal.sum()),
                 internal_repeat_not_known_N=int((internal&~reused).sum()),
                 old_cache_N=len(old['incoming']),old_cache_unique_keys=len(known),
                 input_events=sum(md['raw_N'] for md in metadata),
                 planned_input_events=sum(protocol['input_events_by_source']),
                 complete_sources=delivered, unmeasured_sources=[i for i in range(2) if i not in delivered],
                 two_source_pilot_complete=len(delivered)==2,
                 selected_event_visits_per_source=[md['selected_N'] for md in metadata],
                 requested_uproot_bytes=sum(md['requested_uproot_bytes'] for md in metadata),
                 new_lowE_N={k:int((keep&mm[k]).sum()) for k in ['E50_100','E100_200']},
                 new_difficult_N={k:int((keep&mm[k]).sum()) for k in ['pz50_100_trueE200_inf','pz50_100_high_y','pz50_100_unconfirmed','high_y','unconfirmed','input_missing','E3200_6400','E6400_inf']},
                 known_key_and_internal_masks_independently_verified=True,all62_typed_policy_validated=True,
                 common_Calo_reference_conversion_validated=True,training_ready_N=int(keep.sum()),
                 complete_response_systematics_certified=False,calibration_closure='calibration_closure.json',
                 F7_reference_Calo0_MeV_per_pC=reference,new_Calo0_MeV_per_pC=produced,
                 old_train_cal_eval_modified=False,energy_model_fits=0,F7_inference=0,locked_test_read=False,
                 physical_flux_normalization='未测量; unit MC, source inclusion probability not a physical flux weight',
                 generation_independence='unproven; inherited train/challenge development ranges',
                 wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
                 peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    assert not (CACHE/'support.npz').exists()
    amendment=json.loads((OUT/'calibration_amendment.json').read_text())
    np.savez_compressed(CACHE/'support.npz',**d,metadata_json=np.array(json.dumps(dict(features=cfg['features'],feature_version=cfg['version'],
        calibration_reference='WAVE-Calibration-01-LG',protocol=protocol,calibration_amendment=amendment,calibration_closure=closure,summary=summary))))
    with np.load(CACHE/'support.npz') as z:
        for key,value in d.items():np.testing.assert_array_equal(z[key],value)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,3.7))
    strata=['E50_100','E100_200','pz50_100_trueE200_inf','pz50_100_high_y','unconfirmed','E3200_6400']
    for ax,component in zip(axes,['pi','k']):
        if component not in measured_components:
            ax.text(.5,.5,'Full source not delivered\nYield unmeasured',ha='center',va='center',transform=ax.transAxes)
            ax.set_title(component);ax.set_xticks([]);continue
        x=np.arange(len(strata))
        for state,shift in [('selected',-.18),('new_support',.18)]:
            values=[next(r['N'] for r in rows if r['component']==component and r['state']==state and r['stratum']==k) for k in strata]
            bars=ax.bar(x+shift,values,.34,label=state)
            ax.bar_label(bars,padding=2,fontsize=7)
        ax.set_xticks(x,strata,rotation=50,ha='right');ax.set_ylabel('Selected events');ax.set_title(component);ax.legend(fontsize=8)
    fig.suptitle('Stage70: native Calo reference conversion validated; overlapping strata')
    fig.tight_layout();fig.savefig(OUT/'support.png',dpi=150);plt.close(fig)
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
