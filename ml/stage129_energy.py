"""Fixed matched-support Stage129 arms; one fit/calibration policy, paired risk."""
import csv
import json
import multiprocessing as mp
import resource
import sys
import time
from pathlib import Path

import numpy as np
import xgboost as xgb

from audited_features import configuration
from stage119_curve_common import LAYERS, masks, weights
from stage119_reportcurve import ci, metrics

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage129_energy_ml'
CACHE = ROOT/'ntuples/energy_ml_stage129'
ART = ROOT/'ml/artifacts/stage129'


def load(path):
    with np.load(path) as z:
        return {k:z[k] for k in z.files if k!='metadata_json'}


def table(name, rows):
    if not rows:
        return
    with (OUT/name).open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(k for r in rows for k in r)), delimiter='\t', lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


def fit(task):
    experiment, arm, x, names, d = task
    tick, cpu = time.perf_counter(), time.process_time()
    train, cal, active = [d['role']==r for r in [1,2,-1]]
    active = d['role']>0
    y = np.log(d['truth_E_GeV'])
    w = weights(d['incoming'][train])
    protocol = json.loads((ROOT/'workbook/stage87_energy_ml/protocol.json').read_text())['baseline']
    target = xgb.DMatrix(x[train], label=y[train], weight=w, feature_names=names, nthread=1)
    evaluation = xgb.DMatrix(x[active], feature_names=names, nthread=1)
    predictions = []
    for seed in protocol['seeds']:
        params = dict(protocol['xgboost'], seed=seed, base_score=float(np.average(y[train], weights=w)), boost_from_average=0)
        model = xgb.train(params, target, num_boost_round=protocol['rounds'])
        path = ART/f'{experiment}_{arm}_{seed}.ubj'
        model.save_model(path)
        check = xgb.Booster(params={'nthread':1}); check.load_model(path)
        pred = model.predict(evaluation).astype(float)
        np.testing.assert_array_equal(pred, check.predict(evaluation))
        predictions.append(pred)
    raw = np.full(len(y), np.nan)
    raw[active] = np.mean(predictions, axis=0)
    offset = float(np.average(y[cal]-raw[cal], weights=weights(d['incoming'][cal])))
    np.savez_compressed(ART/f'{experiment}_{arm}_prediction.npz', raw=raw, cal=raw+offset)
    return dict(arm=arm, features=names, dimensions=x.shape[1], train_N=int(train.sum()), cal_N=int(cal.sum()),
                offset=offset, reload_exact=True, CPU_s=time.process_time()-cpu,
                wall_s=time.perf_counter()-tick, RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def evaluate(experiment, d, arms, extra_references=()):
    policies = {a:load(ART/f'{experiment}_{a}_prediction.npz')['cal'] for a in arms}
    old = load(ROOT/'ml/artifacts/stage87/predictions.npz')
    baseline = np.full(89033, np.nan); baseline[old['row']] = old['direct_cal']
    rows = d.get('row', np.arange(len(d['role'])))
    policies['direct_cal'] = baseline[rows]
    policies['traditional'] = np.where(d['role']>0, np.log(d['pz']/.8), np.nan)
    points, pairs, support, gates = [], [], [], []
    contrasts = [(a,arms[0]) for a in arms[1:]]
    contrasts += [(arms[i],arms[i-1]) for i in range(2,len(arms))]
    contrasts += [(a,b) for a in arms for b in ['direct_cal','traditional']]
    contrasts += [(a,b) for a in arms for b in extra_references if a != b]
    contrasts = list(dict.fromkeys(contrasts))
    for role in [1,2,3]:
        ix = np.flatnonzero(d['role']==role)
        sd = {k:v[ix] for k,v in d.items() if isinstance(v,np.ndarray) and len(v)==len(d['role'])}
        _, first, gid = np.unique(sd['incoming'], axis=0, return_index=True, return_inverse=True)
        rng = np.random.default_rng(20261107129+role)
        draw = np.zeros((500,len(first)), np.int16)
        for component in sorted(set(sd['component'][first])):
            u = np.flatnonzero(sd['component'][first]==component)
            draw[:,u] = rng.multinomial(len(u),np.full(len(u),1/len(u)),size=500)
        weight = weights(sd['incoming'])
        names = list(policies)
        strata = masks(sd)
        strata.update(E1600_3200=(sd['truth_E_GeV']>=1600)&(sd['truth_E_GeV']<3200),
                      E3200_6400=(sd['truth_E_GeV']>=3200)&(sd['truth_E_GeV']<6400))
        for layer, mask in strata.items():
            selected, w, group = ix[mask], weight[mask], gid[mask]
            if not len(selected):
                continue
            base = dict(role=role, stratum=layer, N=len(selected), incoming=len(np.unique(group)), ESS=float(w.sum()**2/(w@w)))
            support.append(base)
            err = np.column_stack([policies[a][selected]-np.log(d['truth_E_GeV'][selected]) for a in names])
            assert np.isfinite(err).all()
            agg = np.zeros((len(first),len(names)))
            np.add.at(agg,group,w[:,None]*err**2)
            squared = draw@agg
            den = draw@np.bincount(group,weights=w,minlength=len(first))
            good = den>0
            for j,a in enumerate(names):
                lo,hi = ci(np.sqrt(squared[good,j]/den[good]))
                points.append(dict(**base,model=a,**metrics(err[:,j],w),RMSE_low95=lo,RMSE_high95=hi))
            rel = np.expm1(err)
            tails = {}
            for sign,flag in [('total',abs(rel)>.5),('positive',rel>.5),('negative',rel<-.5)]:
                a = np.zeros_like(agg); np.add.at(a,group,w[:,None]*flag)
                tails[sign] = (a.sum(0)/w.sum(),draw@a)
            for candidate,reference in contrasts:
                j,k = names.index(candidate),names.index(reference)
                ok = good&(squared[:,k]>0)
                lo,hi = ci(np.sqrt(squared[ok,j]/squared[ok,k]))
                row = dict(**base,candidate=candidate,reference=reference,RMSE_ratio=float(np.sqrt(agg[:,j].sum()/agg[:,k].sum())),low95=lo,high95=hi)
                for sign,(central,t) in tails.items():
                    lo,hi = ci(100*(t[ok,j]-t[ok,k])/den[ok])
                    row.update({sign+'_tail_delta_pp':float(100*(central[j]-central[k])),sign+'_tail_low95_pp':lo,sign+'_tail_high95_pp':hi})
                pairs.append(row)
        for arm in arms:
            for layer in LAYERS:
                reference = 'traditional' if layer in LAYERS[:2] else 'direct_cal'
                limit = 1.05 if reference=='traditional' else 1.01 if layer=='all' else 1.03
                row = next((r for r in pairs if r['role']==role and r['stratum']==layer and r['candidate']==arm and r['reference']==reference),None)
                tail = next((r for r in pairs if r['role']==role and r['stratum']==layer and r['candidate']==arm and r['reference']=='direct_cal'),None)
                gates.append(dict(role=role,arm=arm,stratum=layer,RMSE_upper95=row['high95'] if row else None,limit=limit,
                                  RMSE_pass=bool(row and row['high95'] is not None and row['high95']<=limit),
                                  tail_pass=bool(tail and all(tail[s+'_tail_high95_pp'] is not None and tail[s+'_tail_high95_pp']<=2 for s in ['total','positive','negative']))))
    for name, data in [('metrics',points),('paired',pairs),('support',support),('gates',gates)]:
        table(experiment+'_'+name+'.tsv',data)
    np.savez_compressed(ART/f'{experiment}_predictions.npz',**policies)
    result = dict(experiment=experiment,N=len(d['role']),roles=[int((d['role']==r).sum()) for r in range(4)],
                  baseline_max_abs_log_difference=float(np.nanmax(abs(policies[arms[0]]-policies['direct_cal']))),
                  joint={f'{r}_{a}':all(g['RMSE_pass'] and g['tail_pass'] for g in gates if g['role']==r and g['arm']==a) for r in [2,3] for a in arms},
                  quarantine_predictions=0,reserved_predictions=0,
                  limits='developed pool; conditional incoming bootstrap, not full GENIE/source/refit/system or independent confirmation')
    (OUT/f'{experiment}_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result,flush=True)


def main():
    experiment = 'depth' if sys.argv[1]=='0' else sys.argv[1]
    assert experiment=='depth'
    assert not (OUT/'depth_fits.json').exists()
    d = load(ROOT/'ntuples/energy_ml_stage119/old_input.npz')
    assert len(d['role'])==89033
    assert np.isfinite(d['vertex_z_mm']).all()
    names = configuration()['features']
    xz = np.column_stack([d['x'],d['vertex_z_mm']]).astype('float32')
    tasks = [('depth','X',d['x'],names,d),('depth','Z',xz,names+['oracle_interaction_z_mm'],d)]
    ART.mkdir(parents=True,exist_ok=True)
    with mp.get_context('fork').Pool(2) as pool:
        fitted = pool.map(fit,tasks)
    (OUT/'depth_fits.json').write_text(json.dumps(fitted,indent=2)+'\n')
    evaluate('depth',d,['X','Z'])


if __name__=='__main__':
    main()
