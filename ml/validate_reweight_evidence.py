#!/usr/bin/env python3
"""Independent A bookkeeping, moments and fixed-bin bootstrap spot checks; zero fits."""
import csv
import json
import numpy as np
from energy_reweight import *


def main():
    start=begin();d=arrays(CACHE/'input.npz');a=arrays(ART/'reconstruction_events.npz')
    p=json.loads((OUT/'protocol.json').read_text())
    evidence=list(csv.DictReader((OUT/'reconstruction_evidence.tsv').open(),delimiter='\t'))
    errors=[];moments=[]
    valid=a['confirmed']&a['primary_valid']&np.isfinite(a['y_lepton'])&(a['y_lepton']>=0)&(a['y_lepton']<1)
    assert np.all(np.isnan(a['a'][~valid])) and np.all(np.isnan(a['b'][~valid]))
    for role in ['cal','eval']:
        for lo,hi in [(50,100),(100,200)]:
            base=(a['role']==role)&(a['truth_E_GeV']>=lo)&(a['truth_E_GeV']<hi)
            assert base.sum()==((d['role']==role)&(d['truth_E_GeV']>=lo)&(d['truth_E_GeV']<hi)).sum()
            e=a['F7']-np.log(a['truth_E_GeV']);tail=indicator(e,'tail50')
            for label,sel in [('all',np.ones(len(e),bool)),('tail50',tail),('non_tail50',~tail)]:
                m=base&sel;v=m&valid
                row=next(r for r in evidence if r['role']==role and r['stratum']==f'E{lo}_{hi}:{label}')
                assert int(row['N'])==m.sum() and int(row['decomposable_N'])==v.sum()
                lhs=float(np.mean(e[v]**2));rhs=float(np.mean(a['a'][v]**2)+np.mean(a['b'][v]**2)+2*np.mean(a['a'][v]*a['b'][v]))
                errors.append(abs(lhs-rhs));moments.append(dict(role=role,stratum=row['stratum'],N=int(m.sum()),valid_N=int(v.sum()),moment_identity_abs_diff=abs(lhs-rhs)))
                src=[r for r in evidence if r['role']==role and r['stratum'].startswith(f'E{lo}_{hi}:{label}:group=')]
                assert sum(int(r['N']) for r in src)==m.sum()
    f=arrays(ART/'final/predictions.npz');offset=json.loads((OUT/'calibration.json').read_text())['offset_log']
    boot_diffs=[]
    for role in ['train','cal','eval']:
        dd={k:v[d['role']==role] for k,v in d.items()};mm=masks(dd);y=np.log(dd['truth_E_GeV'])
        if role=='train':pred=arrays(ART/'oof_predictions.npz');logs={n:pred[n+'_raw_log'] for n in ['U','S']}
        else:logs={n:f[role+'_'+n+'_raw_log']+offset[n] for n in ['U','S']}
        groups,gid,w=boot_weights(dd,p['bootstrap_seed']+{'train':2,'cal':1,'eval':0}[role],500)
        for draw in [0,173,499]:
            direct=[];grouped=[]
            for k in ENERGY:
                m=mm[k];rep=np.repeat(np.flatnonzero(m),w[draw,gid[m]])
                if not len(rep):break
                direct.append([np.mean((logs[n][rep]-y[rep])**2) for n in ['U','S']])
                den=w[draw]@np.bincount(gid[m],minlength=len(groups))
                grouped.append([float(w[draw]@np.bincount(gid[m],weights=(logs[n][m]-y[m])**2,minlength=len(groups))/den) for n in ['U','S']])
            if len(direct)==7:
                boot_diffs.append(float(np.max(abs(np.asarray(direct)-grouped))))
                ratio=np.sqrt(np.mean(direct,axis=0)[1]/np.mean(direct,axis=0)[0]);assert np.isfinite(ratio)
    assert max(errors)<1e-12 and max(boot_diffs)<1e-12
    boundary=weights(np.array([49.,50.,99.,100.,6399.,6400.,10000.]),1.)
    np.testing.assert_array_equal(boundary[1],[0,1,1,2,7,8,8])
    save(OUT/'evidence_validation.json',dict(passed=True,moments=moments,A_moment_identity_max_abs=max(errors),
        macro_bootstrap_event_replication_draws=[0,173,499],macro_MSE_max_abs_diff=max(boot_diffs),
        under_over_boundary_QA=True,all_lowE_sources_partition_exact=True,invalid_labels_NaN=True,new_fits=0,**resources(start)))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for ax,lo,hi in zip(axes,[50,100],[100,200]):
        m=(a['role']=='eval')&(a['truth_E_GeV']>=lo)&(a['truth_E_GeV']<hi)&valid
        ax.scatter(a['a'][m],a['b'][m],s=12,alpha=.55,c=indicator((a['F7']-np.log(a['truth_E_GeV']))[m],'tail50'),cmap='coolwarm')
        ax.axhline(0,color='gray',lw=.7);ax.axvline(0,color='gray',lw=.7)
        ax.set_xlabel('a = log(pz / E_mu,prod)');ax.set_ylabel('b = correction error');ax.set_title(f'eval true E {lo}-{hi} GeV (confirmed)')
    fig.tight_layout();fig.savefig(OUT/'reconstruction_paths.png',dpi=150);plt.close(fig)
    print((OUT/'evidence_validation.json').read_text())


if __name__=='__main__':main()
