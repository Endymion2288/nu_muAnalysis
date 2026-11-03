#!/usr/bin/env python3
"""Independent direct-probability scoring, pair accounting and calibration QA."""
import csv
import json
import numpy as np
from group_risk import inputs as original_inputs
from conditional_hypotheses import *


def main():
    start=begin();p=json.loads((OUT/'protocol.json').read_text())
    d=arrays(CACHE/'input.npz') if (CACHE/'input.npz').exists() else original_inputs()
    np.testing.assert_array_equal(np.searchsorted(PZ_EDGES,d['pz'],side='right'),
                                  np.searchsorted(PZ_EDGES,d['x'][:,0],side='right'))
    final=arrays(ART/'final/predictions.npz');oof=arrays(ART/'oof_predictions.npz')
    metrics=list(csv.DictReader((OUT/'metrics.tsv').open(),delimiter='\t'))
    reliable=list(csv.DictReader((OUT/'reliability.tsv').open(),delimiter='\t'))
    direct_diffs=[];calibration=[];per_source=[];q_audit=[]
    for sample,role in [('source_OOF','train'),('cal_development','cal'),('evaluation','eval')]:
        dd={k:v[d['role']==role] for k,v in d.items()};mm=strata(dd,p['Timing_quartiles_pC'])
        pred=oof if role=='train' else final
        prefix='' if role=='train' else role+'_'
        np.testing.assert_array_equal(pred[prefix+'row'],dd['row'])
        loss={}
        for arm in ARMS:
            logits=pred[prefix+arm+'_logits'];probability=1/(1+np.exp(-logits))
            direct=-.5*(np.log(probability[:,0])+np.log1p(-probability[:,1]))
            # Independent formula uses direct binary probabilities, no shared loss helper.
            loss[arm]=direct
            for k,m in mm.items():
                row=next(v for v in metrics if v['sample']==sample and v['stratum']==k and v['model']==arm)
                assert int(row['N'])==m.sum() and int(row['synthetic_negative_N'])==m.sum()
                if m.any():direct_diffs.append(abs(float(direct[m].mean())-float(row['BCE'])))
                bins_rows=[v for v in reliable if v['sample']==sample and v['stratum']==k and v['model']==arm]
                assert sum(int(v['pair_rows']) for v in bins_rows)==2*m.sum()
                if m.any() and k in ['all','pz50_100']+CRITICAL:
                    ece=sum(int(v['pair_rows'])*abs(float(v['predicted_probability'])-float(v['observed_positive_fraction'])) for v in bins_rows if int(v['pair_rows']))/(2*m.sum())
                    calibration.append(dict(sample=sample,stratum=k,arm=arm,real_X_N=int(m.sum()),pair_rows=2*int(m.sum()),
                        ECE10=float(ece),scope='balanced pair-experiment probability, not neutrino energy posterior'))
        for k in ['all','pz50_100']+CRITICAL:
            for g in np.unique(dd['group'][mm[k]]):
                m=mm[k]&(dd['group']==g)
                per_source.append(dict(sample=sample,stratum=k,group=str(g),N=int(m.sum()),
                    BCE_gain=float((loss['M'][m]-loss['X'][m]).mean())))
    for job in JOBS:
        a=arrays(ART/job/'predictions.npz');mass=a['proposal_mass'];count=a['proposal_counts']
        np.testing.assert_allclose(mass.sum(1),1,rtol=1e-14)
        assert int(count.sum())==json.loads((OUT/job/'fit.json').read_text())['records'][0]['train_N']
        # Every proposed negative must be in a nonzero cell, including held/eval pairs.
        for role in (['held'] if job!='final' else ['train','cal','eval']):
            row=a[role+'_row'];idx=np.searchsorted(d['row'],row);np.testing.assert_array_equal(d['row'][idx],row)
            pb=np.searchsorted(PZ_EDGES,d['pz'][idx],side='right')-1
            eb=np.searchsorted(LOG_EDGES,a[role+'_negative_log_E'],side='right')-1
            assert np.all(mass[pb,eb]>0)
            q_audit.append(dict(job=job,role=role,real_X_N=len(idx),negative_N=len(eb),
                forbidden_negative_N=0,real_zero_q_N=int((a[role+'_true_q_density']==0).sum())))
    assert max(direct_diffs)<1e-12
    table(OUT/'calibration_summary.tsv',calibration);table(OUT/'source_gain.tsv',per_source)
    save(OUT/'independent_validation.json',dict(passed=True,direct_probability_BCE_max_abs_diff=max(direct_diffs),
        float32_reco_pz_and_proposal_bin_exact=True,
        reliability_pair_rows_exact=True,proposal_draw_audit=q_audit,all_zero_q_real_events_retained=True,
        new_fits=0,new_point_or_grid_predictions=0,**resources(start)))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(9,4))
    for ax,sample in zip(axes,['source_OOF','evaluation']):
        for arm in ARMS:
            rr=[v for v in reliable if v['sample']==sample and v['stratum']=='pz50_100' and v['model']==arm and int(v['pair_rows'])]
            ax.plot([float(v['predicted_probability']) for v in rr],[float(v['observed_positive_fraction']) for v in rr],'o-',label=arm)
        ax.plot([0,1],[0,1],'k--',lw=.8);ax.set_xlabel('Pair-experiment predicted probability')
        ax.set_ylabel('Observed positive fraction');ax.set_title(sample+' pz50-100 GeV');ax.legend();ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(OUT/'pair_reliability.png',dpi=150);plt.close(fig)
    save(OUT/'independent_resources.json',dict(**resources(start),scope='complete independent QA and plot'))
    print((OUT/'independent_validation.json').read_text())


if __name__=='__main__':main()
