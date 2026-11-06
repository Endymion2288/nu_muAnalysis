"""Nested radius tradeoff with paired incoming-cluster uncertainty; no model fit."""
import csv
import json
import tarfile
import time
from pathlib import Path

import numpy as np

from audited_features import REPO

OUT = REPO/'workbook/stage126_energy_ml'
CACHE = REPO/'ntuples/energy_ml_stage126'


def save(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def table(name, rows):
    with (OUT/name).open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows({k:('NA' if v == '' else v) for k,v in row.items()} for row in rows)


def arrays(path):
    with np.load(path) as z:
        return {k:z[k] for k in z.files if k != 'metadata_json'}


def weighted_quantile(v, w, qs):
    order = np.argsort(v)
    v, w = v[order], w[order]
    return np.interp(qs, (np.cumsum(w)-.5*w)/w.sum(), v)


def metrics(d, mask, policy='direct_cal', unit=False):
    if not mask.any():
        return None
    _, key, counts = np.unique(d['incoming'][mask], axis=0, return_inverse=True, return_counts=True)
    w = np.ones(len(key)) if unit else 1/counts[key]
    err = d[policy][mask]-np.log(d['truth_E_GeV'][mask])
    frac = np.expm1(err)
    logq = weighted_quantile(err, w, [.16,.5,.84])
    q = weighted_quantile(frac, w, [.16,.5,.84])
    mean = lambda v: float(np.average(v, weights=w))
    return dict(N=int(mask.sum()), unique_incoming=len(counts),
                log_RMSE=float(np.sqrt(mean(err**2))), log_bias=mean(err), log_R68=float((logq[2]-logq[0])/2),
                fractional_RMSE=float(np.sqrt(mean(frac**2))), fractional_bias=mean(frac),
                fractional_median=float(q[1]), fractional_R68=float((q[2]-q[0])/2),
                tail50=mean(abs(frac)>.5), tail50_positive=mean(frac>.5), tail50_negative=mean(frac<-.5),
                mean_E_GeV=mean(d['truth_E_GeV'][mask]), mean_pz_GeV=mean(d['reco_pz_GeV'][mask]),
                unconfirmed_fraction=mean(~d['confirmed'][mask]), high_y_fraction=mean(d['y_lepton'][mask]>.5),
                lead_block_fraction=mean(d['vertex_z_mm'][mask]>-1800))


def paired_curve(d, cohort, radii, seed):
    """Same incoming-key Poisson multipliers for all nested selections."""
    _, key = np.unique(d['incoming'][cohort], axis=0, return_inverse=True)
    nk = int(key.max())+1
    rng = np.random.default_rng(seed)
    draws = rng.poisson(1, (500, nk)).astype(float)
    r = d['radius_mm'][cohort]
    err = d['direct_cal'][cohort]-np.log(d['truth_E_GeV'][cohort])
    tail = abs(np.expm1(err))>.5
    output = []
    base_rmse = base_tail = base_yield = None
    for radius in radii:
        m = r < radius
        count = np.bincount(key[m], minlength=nk)
        active = count > 0
        mean2 = np.divide(np.bincount(key[m], weights=err[m]**2, minlength=nk), count,
                          out=np.zeros(nk), where=active)
        mt = np.divide(np.bincount(key[m], weights=tail[m], minlength=nk), count,
                       out=np.zeros(nk), where=active)
        nb = draws@active.astype(float)
        rmse = np.sqrt((draws@mean2)/nb)
        tails = (draws@mt)/nb
        if radius == 100:
            base_rmse, base_tail, base_yield = rmse, tails, nb
        lo, hi = np.quantile(rmse/base_rmse, [.025,.975])
        tl, th = np.quantile((tails-base_tail)*100, [.025,.975])
        yl, yh = np.quantile(nb/base_yield, [.025,.975])
        output.append(dict(radius_mm=radius, log_RMSE_ratio_low95=float(lo), log_RMSE_ratio_high95=float(hi),
                           tail50_change_pp_low95=float(tl), tail50_change_pp_high95=float(th),
                           incoming_yield_ratio_low95=float(yl), incoming_yield_ratio_high95=float(yh)))
    return output


def energy_standardized_rmse(d, mask, reference):
    """Hold baseline true-energy bin fractions fixed to expose spectrum mixing."""
    edges = np.array([50,100,200,400,800,1600,np.inf])
    means, masses = [], []
    for m in [mask, reference]:
        _, key, count = np.unique(d['incoming'][m], axis=0, return_inverse=True, return_counts=True)
        w = 1/count[key]
        bins = np.searchsorted(edges, d['truth_E_GeV'][m], side='right')-1
        mass = np.bincount(bins, weights=w, minlength=6)
        e2 = (d['direct_cal'][m]-np.log(d['truth_E_GeV'][m]))**2
        mse = np.divide(np.bincount(bins, weights=w*e2, minlength=6), mass,
                        out=np.zeros(6), where=mass>0)
        means.append(mse); masses.append(mass/mass.sum())
    return float(np.sqrt(means[0]@masses[1]))


def working_points(rows):
    recommendations=[]
    for selection in ['pz50','pz100']:
        for budget in [1.01,1.03,1.05]:
            valid=[r for r in rows if r['selection']==selection and r['role']=='cal' and r['log_RMSE_ratio_high95']<=budget and r['tail50_change_pp_high95']<=2]
            best=max(valid,key=lambda r:(r['N'],-r['radius_mm']))
            confirm=next(r for r in rows if r['selection']==selection and r['role']=='test' and r['radius_mm']==best['radius_mm'])
            recommendations.append(dict(selection=selection,allowed_log_RMSE_increase_pct=(budget-1)*100,cal_selected_radius_mm=best['radius_mm'],
                cal_record_gain_pct=best['record_gain_pct'],test_record_gain_pct=confirm['record_gain_pct'],
                test_log_RMSE_ratio=confirm['log_RMSE_ratio'],test_log_RMSE_ratio_high95=confirm['log_RMSE_ratio_high95'],
                test_tail50_change_pp_high95=confirm['tail50_change_pp_high95'],
                test_meets_same_budget=bool(confirm['log_RMSE_ratio_high95']<=budget and confirm['tail50_change_pp_high95']<=2)))
    return recommendations


def main():
    start=time.perf_counter()
    p=json.loads((OUT/'protocol.json').read_text())
    if all((CACHE/f'batch_{b}.tar.gz').exists() for b in range(p['batches'])):
        for batch in range(p['batches']):
            with tarfile.open(CACHE/f'batch_{batch}.tar.gz') as archive:
                for member in archive.getmembers():
                    assert member.isfile() and member.name.startswith(('ntuples/energy_ml_stage126/source_', 'workbook/stage126_energy_ml/batch_'))
                archive.extractall(REPO, filter='data')
        parts=[]; metadata=[]
        for s in p['sources']:
            path=CACHE/f"source_{s['index']}.npz"
            parts.append(arrays(path))
            with np.load(path) as z:metadata.append(json.loads(str(z['metadata_json'])))
        d={k:np.concatenate([a[k] for a in parts]) for k in parts[0]}
    else:
        d=arrays(CACHE/'predictions.npz')
        merged=json.loads((OUT/'extraction_metadata.json').read_text())
        metadata=[dict(m, features=merged['feature_names'], unit_contract=merged['unit_contract'],
                       cutflow_names=merged['cutflow_names']) for m in merged['sources']]
    assert len(set(zip(d['source'],d['eventID']))) == len(d['source'])
    assert np.isfinite(d['direct_cal']).all() and (d['truth_E_GeV']>50).all()
    split=arrays(REPO/'ntuples/energy_ml_stage87/split.npz')
    pred=arrays(REPO/'ml/artifacts/stage87/predictions.npz')
    lookup={(int(s),int(e)):j for j,(s,e) in enumerate(zip(d['source'],d['eventID']))}
    oldrow=pred['row']; old55=split['origin'][oldrow]==55
    ix=oldrow[old55]
    order=np.array([lookup[(int(s),int(e))] for s,e in zip(split['source'][ix],split['eventID'][ix])])
    np.testing.assert_array_equal(d['direct_raw'][order],pred['direct_raw'][old55])
    np.testing.assert_array_equal(d['direct_cal'][order],pred['direct_cal'][old55])
    sources={s['index']:s for s in p['sources']}
    initial=np.array([sources[int(s)]['initial_role'] for s in d['source']])
    d['component']=np.array([sources[int(s)]['component'] for s in d['source']])
    d['group']=np.array([sources[int(s)]['group'] for s in d['source']])
    keys=[tuple(v) for v in d['incoming']]
    forbidden_test={tuple(v) for v in split['incoming'][np.isin(split['role'],[1,2])]}
    forbidden_cal={tuple(v) for v in split['incoming'][np.isin(split['role'],[1,3])]}
    forbidden_cal.update(k for k,m in zip(keys,initial=='test') if m)
    test=(initial=='test') & np.array([k not in forbidden_test for k in keys])
    cal=(initial=='cal') & np.array([k not in forbidden_cal for k in keys])
    d['evaluation_role']=np.where(test,'test',np.where(cal,'cal','descriptive_only'))
    d['traditional']=np.log(d['reco_pz_GeV']/.8)
    save('validation.json',dict(passed=True,sources=len(metadata),baseline62_exact_N=sum(m['baseline62_exact_N'] for m in metadata),
         stage87_active_prediction_exact_N=len(order),new_fits=0,
         initial_test_rows=int((initial=='test').sum()),test_rows=int(test.sum()),
         test_excluded_frozen_train_cal_incoming_rows=int(((initial=='test')&~test).sum()),
         initial_cal_rows=int((initial=='cal').sum()),cal_rows=int(cal.sum()),
         cal_excluded_rows=int(((initial=='cal')&~cal).sum()),
         test_groups=len(np.unique(d['group'][test])),cal_groups=len(np.unique(d['group'][cal])),
         bootstrap='500 paired incoming Poisson draws, conditional on source mix; not source or systematic CI'))
    np.savez_compressed(CACHE/'predictions.npz',**d)
    save('extraction_metadata.json', dict(cutflow_names=metadata[0]['cutflow_names'],
         feature_names=metadata[0]['features'], unit_contract=metadata[0]['unit_contract'],
         sources=[{k:m[k] for k in ['source','raw_N','selected_N','cutflow_passed',
                  'requested_uproot_bytes','wall_s','cpu_s','child_user_s','child_system_s',
                  'peak_parent_rss_MiB','peak_analysis_rss_MiB','baseline_identity_exact',
                  'baseline62_exact_N','wall_total_s','new_fits','actual_command']} for m in metadata]))
    raw=sum(m['raw_N'] for m in metadata)
    truth_parent=sum(m['cutflow_passed'][m['cutflow_names'].index('Truth pz > 50 GeV')] for m in metadata)
    table('sources.tsv',[dict(source=s['index'],run=s['run'],component=s['component'],group=s['group'],initial_role=s['initial_role'],
          raw_N=m['raw_N'],selected_no_radius_N=m['selected_N'],selected100_N=int(((d['source']==s['index'])&(d['radius_mm']<100)).sum()),
          baseline62_exact_N=m['baseline62_exact_N'],wall_s=m['wall_total_s'],uproot_requested_bytes=m['requested_uproot_bytes']) for s,m in zip(p['sources'],metadata)])
    radii=p['thresholds_mm'];rows=[];rings=[];slices=[];comparisons=[]
    n=len(d['source'])
    strata={'all':np.ones(n,bool),'E50_100':d['truth_E_GeV']<100,
            'E100_200':(d['truth_E_GeV']>=100)&(d['truth_E_GeV']<200),'E200_inf':d['truth_E_GeV']>=200,
            'pz50_100':d['reco_pz_GeV']<100,'pz100_250':(d['reco_pz_GeV']>=100)&(d['reco_pz_GeV']<250),
            'pz250_1000':(d['reco_pz_GeV']>=250)&(d['reco_pz_GeV']<1000),'pz1000_inf':d['reco_pz_GeV']>=1000,
            'high_y':d['y_lepton']>.5,'unconfirmed':~d['confirmed'],
            **{c:d['component']==c for c in ['pi','k','charm']},
            'nu_box':d['vertex_z_mm']<-1900,'lead_block':d['vertex_z_mm']>-1800}
    for selection,pzcut in [('pz50',np.ones(n,bool)),('pz100',(d['reco_pz_GeV']>100)&(d['incoming'][:,3]/1000>100))]:
        for role,role_mask in [('all_descriptive',np.ones(n,bool)),('cal',cal),('test',test)]:
            cohort=role_mask & pzcut
            baseline=metrics(d,cohort&(d['radius_mm']<100))
            base_count=baseline['N']; base_keys=baseline['unique_incoming']
            ci=paired_curve(d,cohort,radii,20261106126) if role!='all_descriptive' else None
            for j,radius in enumerate(radii):
                mask=cohort&(d['radius_mm']<radius)
                m=metrics(d,mask); unit=metrics(d,mask,unit=True)
                row=dict(selection=selection,role=role,radius_mm=radius,**m,
                         energy_standardized_log_RMSE=energy_standardized_rmse(d,mask,cohort&(d['radius_mm']<100)),
                         record_gain_pct=(m['N']/base_count-1)*100,incoming_gain_pct=(m['unique_incoming']/base_keys-1)*100,
                         log_RMSE_ratio=m['log_RMSE']/baseline['log_RMSE'],record_log_RMSE=unit['log_RMSE'],
                         tail50_change_pp=(m['tail50']-baseline['tail50'])*100,
                         fraction_of_no_radius_yield=m['N']/int(cohort.sum()),
                         raw_input_efficiency=m['N']/raw if role=='all_descriptive' else '',
                         common_truth_parent_efficiency=m['N']/truth_parent if role=='all_descriptive' else '')
                if ci:row.update({k:v for k,v in ci[j].items() if k!='radius_mm'})
                else:row.update({k:'' for k in ['log_RMSE_ratio_low95','log_RMSE_ratio_high95','tail50_change_pp_low95','tail50_change_pp_high95','incoming_yield_ratio_low95','incoming_yield_ratio_high95']})
                rows.append(row)
                traditional=metrics(d,mask,'traditional')
                comparisons.append(dict(selection=selection,role=role,radius_mm=radius,direct_log_RMSE=m['log_RMSE'],
                   traditional_log_RMSE=traditional['log_RMSE'],direct_fractional_R68=m['fractional_R68'],traditional_fractional_R68=traditional['fractional_R68']))
                for stratum,sm in strata.items():
                    mm=metrics(d,mask&sm)
                    if mm:slices.append(dict(selection=selection,role=role,radius_mm=radius,stratum=stratum,**mm))
            for lo,hi in zip([0]+radii[:-1],radii):
                mm=metrics(d,cohort&(d['radius_mm']>=lo)&(d['radius_mm']<hi))
                if mm:rings.append(dict(selection=selection,role=role,lower_mm=lo,upper_mm=hi,**mm))
    table('scan.tsv',rows);table('annuli.tsv',rings);table('strata.tsv',slices);table('traditional.tsv',comparisons)
    recommendations=working_points(rows)
    save('working_points.json',recommendations)
    save('summary.json',dict(N=n,raw_input_N=raw,common_truth_parent_N=truth_parent,baseline_N=int((d['radius_mm']<100).sum()),
          no_radius_N=n,max_selected_radius_mm=float(d['radius_mm'].max()),wall_report_s=time.perf_counter()-start,
          source_worker_wall_sum_s=sum(m['wall_total_s'] for m in metadata),
          uproot_requested_bytes=sum(m['requested_uproot_bytes'] for m in metadata),ROOT_requested_bytes='未测量',physical_flux_normalized=False))
    print(json.dumps(recommendations,indent=2),flush=True)


if __name__=='__main__':main()
