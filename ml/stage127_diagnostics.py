"""Protected strata and event migrations for the cal-chosen cuboid."""
import json
import time
import numpy as np
from stage127_scan import (ROOT,OUT,load,rectangle,Bootstrap,table,save,arrays)
from stage126_report import metrics


def main():
    start=time.perf_counter();d,coords=load();dec=json.loads((OUT/'decisions.json').read_text());c=dec['recommended']['geometry'];mask=rectangle(d,c)
    n=len(mask);r100=d['radius_mm']<100;r125=d['radius_mm']<125
    strata={'all':np.ones(n,bool),'E50_100':d['truth_E_GeV']<100,
      'E100_200':(d['truth_E_GeV']>=100)&(d['truth_E_GeV']<200),'E200_inf':d['truth_E_GeV']>=200,
      'pz50_100':d['reco_pz_GeV']<100,'pz100_250':(d['reco_pz_GeV']>=100)&(d['reco_pz_GeV']<250),
      'pz250_1000':(d['reco_pz_GeV']>=250)&(d['reco_pz_GeV']<1000),'pz1000_inf':d['reco_pz_GeV']>=1000,
      'high_y':d['y_lepton']>.5,'unconfirmed':~d['confirmed'],**{c:d['component']==c for c in ['pi','k','charm']},
      'nu_box':d['vertex_z_mm']<-1900,'lead_block':d['vertex_z_mm']>-1800}
    pairs=[];migration=[]
    for selection in ['pz100','pz50']:
        pzmask=np.ones(n,bool) if selection=='pz50' else (d['reco_pz_GeV']>100)&(d['incoming'][:,3]>100000)
        for role in ['all_descriptive','test']:
            cohort=pzmask & (np.ones(n,bool) if role=='all_descriptive' else d['evaluation_role']=='test')
            for ref,rmask in [('circle100',r100),('circle125',r125)]:
                for region,m in [('common',mask&rmask),('added',mask&~rmask),('removed',rmask&~mask)]:
                    q=metrics(d,cohort&m)
                    if q:migration.append(dict(selection=selection,role=role,reference=ref,region=region,**q))
            if role=='test':
                for name,sm in strata.items():
                    sub=cohort&sm
                    if not (sub&r100).any():continue
                    q=metrics(d,sub&mask);base=metrics(d,sub&r100);boot=Bootstrap(d,sub,20261106127)
                    pairs.append(dict(selection=selection,stratum=name,baseline_N=base['N'],cuboid_N=q['N'],
                        log_RMSE_ratio=q['log_RMSE']/base['log_RMSE'],**boot.compare(mask,r100)))
    table('stratum_paired_recommended.tsv',pairs);table('migration.tsv',migration)
    save('diagnostics_resources.json',dict(wall_s=time.perf_counter()-start,CPU_s=time.process_time(),new_model_forwards=0))
    print('Protected-stratum and migration diagnostics complete')


if __name__=='__main__':main()
