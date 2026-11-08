"""Original evaluator, frozen Stage186 bootstrap seed; no policy changes."""
from stage186_common import *
from stage119_curve_common import LAYERS,masks,weights
from stage119_reportcurve import ci,metrics

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
        rng = np.random.default_rng(20261108186+role)
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
            base = dict(role=role, stratum=layer, N=len(selected), incoming=len(np.unique(group)), weight_sum=float(w.sum()), ESS=float(w.sum()**2/(w@w)))
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
