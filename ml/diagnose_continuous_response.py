#!/usr/bin/env python3
"""Zero-fit loss attribution and probability/source diagnostics for frozen models."""
import csv
import json
import numpy as np

from continuous_response import OUT, ART, MODELS, inputs, subset, begin, resources, save
from expert_combination import masks
from report_expert_combination import table


def main():
    start=begin();d=inputs();p=json.loads((OUT/'protocol.json').read_text())
    rows=[];global_reliability=[];source_stability=[]
    for role in ['cal','eval']:
        dd=subset(d,d['role']==role);y=np.log(dd['truth_E_GeV'])
        with np.load(ART/'A_full_unit/predictions.npz') as z:pred=z[role+'_point_cal_log']
        error=pred-y;tail=abs(np.expm1(error))>.5
        for key,m in masks(dd).items():
            total=float(np.sum(error[m]**2));use=m&tail
            rows.append(dict(role=role,stratum=key,N=int(m.sum()),tail50_N=int(use.sum()),positive_tail50_N=int((use&(error>0)).sum()),
                tail50_squared_log_loss_fraction=float(np.sum(error[use]**2)/total) if total else np.nan,
                non_tail_log_RMSE=float(np.sqrt(np.mean(error[m&~tail]**2))) if (m&~tail).any() else np.nan))
        for name in MODELS:
            with np.load(ART/name/'predictions.npz') as a:
                for e in [100,200]:
                    j=int(np.argmin(abs(np.array(p['prior_log_edges'])-np.log(e))))
                    global_reliability.append(dict(role=role,model=name,threshold_GeV=e,
                        predicted_probability=float(a[role+'_probabilities'][:,j].mean()),observed_fraction=float((dd['truth_E_GeV']<e).mean())))
    sources=list(csv.DictReader((OUT/'source_metrics.tsv').open(),delimiter='\t'))
    for sample in ['cal_development','evaluation']:
        for key in ['all','E50_100','E100_200','pz50_100','high_y']:
            aa=[r for r in sources if r['sample']==sample and r['stratum']==key and r['model']=='A_full_unit']
            gains=[];crps=[]
            for a in aa:
                c=next(r for r in sources if (r['sample'],r['stratum'],r['model'],r['group'])==(sample,key,'C_mu_unit',a['group']))
                gains.append(float(a['log_density'])-float(c['log_density']));crps.append(float(c['CRPS_logE'])-float(a['CRPS_logE']))
            source_stability.append(dict(sample=sample,stratum=key,groups=len(gains),positive_logscore_groups=sum(v>0 for v in gains),
                positive_CRPS_groups=sum(v>0 for v in crps),logscore_gain_min=min(gains),logscore_gain_max=max(gains)))
    table(OUT/'loss_attribution.tsv',rows)
    save(OUT/'diagnostic_resources.json',dict(**resources(start),additional_fits=0,global_reliability=global_reliability,
        source_stability=source_stability,note='post-fit diagnostics; all events retained; non-tail scores never used for acceptance'))


if __name__=='__main__':main()
