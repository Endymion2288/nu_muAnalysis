#!/usr/bin/env python3
"""Per-source auxiliary scores and fixed-prediction confusion figure for stage69."""
import csv,json
import numpy as np
from transfer_supervision import OUT,ART,inputs,labels,training_split,begin,resources,save
from report_expert_combination import table


def main():
    start=begin();p=json.loads((OUT/'protocol.json').read_text());d=inputs();tr=d['role']=='train';trrows=d['row'][tr]
    with np.load(ART/'oof_predictions.npz') as z:oof={k:z[k] for k in z.files}
    with np.load(ART/'final/predictions.npz') as z:final={k:z[k] for k in z.files}
    priors=np.zeros((len(trrows),3));full_prior=np.array(json.loads((OUT/'final/fit.json').read_text())['train_class_prior'])
    for job in ['fold0','fold1','fold2']:
        _,held,_=training_split(d,p,job);idx=np.searchsorted(trrows,d['row'][held]);priors[idx]=json.loads((OUT/job/'fit.json').read_text())['train_class_prior']
    records=[]
    for sample,role in [('source_OOF_raw','train'),('cal_development','cal'),('evaluation','eval')]:
        dd={k:v[d['role']==role] for k,v in d.items()};target,valid=labels(dd);prob=oof['P_prob'] if role=='train' else final[role+'_P_prob'];prior=priors if role=='train' else np.broadcast_to(full_prior,prob.shape)
        for g in np.unique(dd['group']):
            m=valid&(dd['group']==g);n=int(m.sum());ix=np.flatnonzero(m)
            ce=-np.log(np.maximum(prob[ix,target[m]],np.finfo(float).tiny));bc=-np.log(prior[ix,target[m]])
            records.append(dict(sample=sample,group=str(g),valid_N=n,NLL_P=float(ce.mean()),NLL_prior=float(bc.mean()),NLL_gain=float((bc-ce).mean()),class2_N=int((m&(target==2)).sum())))
    table(OUT/'auxiliary_sources.tsv',records)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    data=list(csv.DictReader((OUT/'auxiliary_confusion.tsv').open(),delimiter='\t'));fig,axes=plt.subplots(1,2,figsize=(8,3.7))
    for ax,sample in zip(axes,['source_OOF_raw','evaluation']):
        matrix=np.array([[int(next(v['N'] for v in data if v['sample']==sample and v['stratum']=='all' and int(v['truth_class'])==i and int(v['predicted_class'])==j)) for j in range(3)] for i in range(3)])
        norm=matrix/matrix.sum(1)[:,None];im=ax.imshow(norm,vmin=0,vmax=1,cmap='Blues')
        for i in range(3):
            for j in range(3):ax.text(j,i,f'{100*norm[i,j]:.1f}%\nN={matrix[i,j]}',ha='center',va='center',color='white' if norm[i,j]>.65 else 'black',fontsize=9)
        ax.set_xticks(range(3),['low','mid','high']);ax.set_yticks(range(3),['low','mid','high']);ax.set_xlabel('predicted transfer class');ax.set_ylabel('true class, confirmed subset');ax.set_title(sample)
    fig.suptitle('Stage69 P auxiliary head: row-normalized confusion, no threshold fitting')
    fig.tight_layout();fig.savefig(OUT/'auxiliary_confusion.png',dpi=150);plt.close(fig)
    save(OUT/'auxiliary_summary_resources.json',dict(**resources(start),new_fits=0,inference_calls=0,source_scores='fixed P probabilities versus own-training class prior; confirmed valid labels only'))
    print({sample:sum(v['NLL_gain']>0 for v in records if v['sample']==sample) for sample in ['source_OOF_raw','cal_development','evaluation']})


if __name__=='__main__':main()
