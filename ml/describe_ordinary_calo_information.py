#!/usr/bin/env python3
"""Saved sensitive deposit versus existing reconstructed EM readout; no new fits."""
import json
import numpy as np
from scipy.stats import spearmanr
from coarse_depth import REPO,load_inputs
from report_calonu_information import strata
from train_bdt import write_table

rows,d,x=load_inputs();out=REPO/'workbook/stage47_energy_ml'
with np.load(REPO/'ntuples/energy_ml_stage47/sensitive.npz') as z:
    np.testing.assert_array_equal(z['cache_row'],rows);energy=z['hit_energy_MeV']/1000;count=z['hit_count']
names=json.loads((REPO/'workbook/stage42_energy_ml/preparation.json').read_text())['feature_names']
reco=d['x'][:,names.index('ML_calo_total_E_EM_GeV')].astype(float);total=energy.sum(axis=1)
transfer=d['truth_E_GeV']*d['y_lepton']  # E_nu - primary E_mu proxy; not total visible hadronic energy.
records=[]
for label,mask in strata(d).items():
    if not mask.any():continue
    valid=mask&np.isfinite(reco);ratio=valid&(total>0)
    transfer_valid=valid&np.isfinite(transfer)
    records.append(dict(stratum=label,N=int(mask.sum()),sources=len(set(d['group'][mask])),
                        zero_hit_events=int((mask&(count.sum(axis=1)==0)).sum()),zero_energy_events=int((mask&(total==0)).sum()),
                        energy_total_quantiles_GeV=np.quantile(total[mask],[0,.1,.5,.9,.99,1]).tolist(),
                        module_median_energy_GeV=np.median(energy[mask],axis=0).tolist(),
                        module_zero_N=(energy[mask]==0).sum(axis=0).tolist(),finite_reco_N=int(valid.sum()),
                        nonpositive_reco_N=int((valid&(reco<=0)).sum()),
                        sensitive_vs_recoEM_spearman=float(spearmanr(total[valid],reco[valid]).statistic) if valid.sum()>2 else None,
                        transfer_proxy_valid_N=int(transfer_valid.sum()),
                        sensitive_vs_transfer_proxy_spearman=float(spearmanr(total[transfer_valid],transfer[transfer_valid]).statistic) if transfer_valid.sum()>2 else None,
                        recoEM_vs_transfer_proxy_spearman=float(spearmanr(reco[transfer_valid],transfer[transfer_valid]).statistic) if transfer_valid.sum()>2 else None,
                        recoEM_over_sensitive_quantiles=np.quantile(reco[ratio]/total[ratio],[.05,.5,.95]).tolist() if ratio.any() else []))
(out/'signal_summary.json').write_text(json.dumps(records,indent=2)+'\n')
write_table(out/'signal_summary.tsv',records)
print(json.dumps([r for r in records if r['stratum'] in ['all','focus']]))
