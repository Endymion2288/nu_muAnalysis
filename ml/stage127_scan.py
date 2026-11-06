"""Cal-only rectangle grid and fixed-finalist test evaluation, reusing direct62."""
import csv
import gzip
import json
import multiprocessing as mp
import resource
import time
from pathlib import Path
import numpy as np
import yaml
from stage126_report import metrics,energy_standardized_rmse
from stage127_native import cut_configuration

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage127_energy_ml'
CACHE=ROOT/'ntuples/energy_ml_stage127'
DATA=None
CAL=None
GRID=None


def arrays(path):
    with np.load(path) as z:return {k:z[k] for k in z.files}


def save(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')


def table(name,rows):
    opener=gzip.open if name.endswith('.gz') else open
    with opener(OUT/name,'wt') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n')
        writer.writeheader();writer.writerows(rows)


def candidates(p):
    rows=[];g=p['grid']
    for cx in g['center_x_mm']:
        for cy in g['center_y_mm']:
            for hx in g['half_width_mm']:
                for hy in g['half_height_mm']:
                    rows.append(dict(candidate_id=len(rows),cx=cx,cy=cy,hx=hx,hy=hy))
    return rows


def rectangle(d,c):
    return (d['x']>c['cx']-c['hx'])&(d['x']<c['cx']+c['hx'])&(d['y']>c['cy']-c['hy'])&(d['y']<c['cy']+c['hy'])


def bounds(c):return [c['cx']-c['hx'],c['cx']+c['hx'],c['cy']-c['hy'],c['cy']+c['hy']]


def geometry(c):
    return dict(**{k:c[k] for k in ['candidate_id','cx','cy','hx','hy']},width_mm=2*c['hx'],height_mm=2*c['hy'],aspect_width_over_height=c['hx']/c['hy'],
                area_mm2=4*c['hx']*c['hy'])


def load():
    d=arrays(ROOT/'ntuples/energy_ml_stage126/predictions.npz');coords=arrays(CACHE/'coordinates.npz')
    d.update(x=coords['x'],y=coords['y'])
    return d,coords


def initialize():
    global DATA,CAL,GRID
    DATA,_=load();p=json.loads((OUT/'protocol.json').read_text());GRID=candidates(p)
    CAL={}
    for selection in ['pz50','pz100']:
        cohort=DATA['evaluation_role']=='cal'
        if selection=='pz100':cohort &= (DATA['reco_pz_GeV']>100)&(DATA['incoming'][:,3]>100000)
        d={k:DATA[k][cohort] for k in ['incoming','direct_cal','truth_E_GeV','radius_mm','x','y']}
        _,d['key']=np.unique(d['incoming'],axis=0,return_inverse=True)
        d['e']=d['direct_cal']-np.log(d['truth_E_GeV']);d['frac']=np.expm1(d['e'])
        CAL[selection]=d


def basic(d,mask):
    k=d['key'][mask];count=np.bincount(k,minlength=int(d['key'].max())+1);nk=int((count>0).sum())
    w=1/count[k];e=d['e'][mask];frac=d['frac'][mask]
    return dict(N=int(mask.sum()),unique_incoming=nk,log_RMSE=float(np.sqrt(np.sum(w*e*e)/nk)),
                log_bias=float(np.sum(w*e)/nk),tail50=float(np.sum(w*(abs(frac)>.5))/nk))


def work(chunk):
    output=[]
    for selection,d in CAL.items():
        b100=basic(d,d['radius_mm']<100);b125=basic(d,d['radius_mm']<125)
        for i in chunk:
            c=GRID[i];m=rectangle(d,c);q=basic(d,m)
            q.update(selection=selection,**geometry(c),log_RMSE_ratio100=q['log_RMSE']/b100['log_RMSE'],
                     log_RMSE_ratio125=q['log_RMSE']/b125['log_RMSE'],record_gain100_pct=(q['N']/b100['N']-1)*100,
                     tail50_change100_pp=(q['tail50']-b100['tail50'])*100,
                     stat_proxy_ratio=(q['unique_incoming']/q['log_RMSE']**2)/(b100['unique_incoming']/b100['log_RMSE']**2))
            output.append(q)
    return output


def pareto(rows):
    result=[];best=np.inf
    for r in sorted(rows,key=lambda r:(-r['N'],r['log_RMSE'],r['area_mm2'],r['cx']**2+r['cy']**2)):
        if r['log_RMSE']<best-1e-14:
            result.append(r);best=r['log_RMSE']
    return result


class Bootstrap:
    def __init__(self,d,cohort,seed):
        self.cohort=cohort
        _,self.key=np.unique(d['incoming'][cohort],axis=0,return_inverse=True)
        self.nk=int(self.key.max())+1
        self.draws=np.random.default_rng(seed).poisson(1,(500,self.nk)).astype(float)
        self.e=d['direct_cal'][cohort]-np.log(d['truth_E_GeV'][cohort])
        self.tail=abs(np.expm1(self.e))>.5
        self.cache={}

    def values(self,mask):
        m=mask[self.cohort];packed=np.packbits(m).tobytes()
        if packed in self.cache:return self.cache[packed]
        k=self.key[m];count=np.bincount(k,minlength=self.nk);active=count>0
        s2=np.divide(np.bincount(k,weights=self.e[m]**2,minlength=self.nk),count,out=np.zeros(self.nk),where=active)
        st=np.divide(np.bincount(k,weights=self.tail[m],minlength=self.nk),count,out=np.zeros(self.nk),where=active)
        den=self.draws@active.astype(float)
        result=(np.sqrt((self.draws@s2)/den),(self.draws@st)/den,den)
        self.cache[packed]=result
        return result

    def compare(self,mask,reference):
        rmse,tail,count=self.values(mask);r0,t0,c0=self.values(reference)
        q=np.quantile(rmse/r0,[.025,.975]);t=np.quantile((tail-t0)*100,[.025,.975]);n=np.quantile(count/c0,[.025,.975])
        return dict(log_RMSE_ratio_low95=float(q[0]),log_RMSE_ratio_high95=float(q[1]),
                    tail50_change_pp_low95=float(t[0]),tail50_change_pp_high95=float(t[1]),
                    incoming_yield_ratio_low95=float(n[0]),incoming_yield_ratio_high95=float(n[1]))


def parent_count(coords,c,selection):
    hist=coords['hist100' if selection=='pz100' else 'hist50']
    prefix=np.pad(hist.cumsum(0).cumsum(1),((1,0),(1,0)))
    x0,x1,y0,y1=bounds(c)
    ix0=np.searchsorted(coords['edges_x'],np.nextafter(float(x0),np.inf));ix1=np.searchsorted(coords['edges_x'],x1)
    iy0=np.searchsorted(coords['edges_y'],np.nextafter(float(y0),np.inf));iy1=np.searchsorted(coords['edges_y'],y1)
    return int(prefix[ix1,iy1]-prefix[ix0,iy1]-prefix[ix1,iy0]+prefix[ix0,iy0])


def main():
    start=time.perf_counter();p=json.loads((OUT/'protocol.json').read_text());grid=candidates(p)
    with mp.get_context('spawn').Pool(8,initializer=initialize) as pool:
        chunks=pool.map(work,[list(range(j,len(grid),8)) for j in range(8)])
    rows=sorted([r for chunk in chunks for r in chunk],key=lambda r:(r['selection'],r['candidate_id']))
    table('cal_grid.tsv.gz',rows)
    d,coords=load();n=len(d['x']);radius100=d['radius_mm']<100;radius125=d['radius_mm']<125
    front=[];shortlist=[];finalists={};decisions=[];ci_rows=[]
    for selection in ['pz100','pz50']:
        rr=[r for r in rows if r['selection']==selection]
        pf=pareto(rr);front+=pf
        chosen={};all_short={}
        for budget in [1.01,1.03,1.05]:
            feasible=[r for r in pf if r['log_RMSE_ratio100']<=budget and r['tail50_change100_pp']<=2]
            # Include the smallest-area representative at each Pareto yield.
            feasible=sorted(feasible,key=lambda r:(-r['N'],r['area_mm2'],r['cx']**2+r['cy']**2))[:12]
            for r in feasible:all_short[r['candidate_id']]=r
        for r in [min(rr,key=lambda r:r['log_RMSE']),max(rr,key=lambda r:r['stat_proxy_ratio'])]:all_short[r['candidate_id']]=r
        cohort=(d['evaluation_role']=='cal')
        if selection=='pz100':cohort &= (d['reco_pz_GeV']>100)&(d['incoming'][:,3]>100000)
        boot=Bootstrap(d,cohort,p['bootstrap_seed'])
        for r in all_short.values():
            ci=boot.compare(rectangle(d,r),radius100)
            q=dict(r,**ci);shortlist.append(q);chosen[r['candidate_id']]=q
        for budget in [1.01,1.03,1.05]:
            valid=[r for r in chosen.values() if r['log_RMSE_ratio_high95']<=budget and r['tail50_change_pp_high95']<=2]
            best=max(valid,key=lambda r:(r['N'],-r['area_mm2'],-r['cx']**2-r['cy']**2))
            finalists[(selection,best['candidate_id'])]=best
            decisions.append(dict(selection=selection,budget_RMSE_ratio=budget,candidate_id=best['candidate_id'],bounds_mm=bounds(best),
                                  cal_N=best['N'],cal_log_RMSE=best['log_RMSE'],cal_RMSE_ratio_high95=best['log_RMSE_ratio_high95']))
        proxy=max(rr,key=lambda r:r['stat_proxy_ratio']);finalists[(selection,proxy['candidate_id'])]=proxy
    table('cal_pareto.tsv',front);table('cal_shortlist.tsv',shortlist)
    evaluations=[];slices=[];paired=[]
    strata={'all':np.ones(n,bool),'E50_100':d['truth_E_GeV']<100,'E100_200':(d['truth_E_GeV']>=100)&(d['truth_E_GeV']<200),
       'E200_inf':d['truth_E_GeV']>=200,'pz50_100':d['reco_pz_GeV']<100,
       'pz100_250':(d['reco_pz_GeV']>=100)&(d['reco_pz_GeV']<250),'pz250_1000':(d['reco_pz_GeV']>=250)&(d['reco_pz_GeV']<1000),
       'pz1000_inf':d['reco_pz_GeV']>=1000,'high_y':d['y_lepton']>.5,'unconfirmed':~d['confirmed'],
       **{c:d['component']==c for c in ['pi','k','charm']},'nu_box':d['vertex_z_mm']<-1900,'lead_block':d['vertex_z_mm']>-1800}
    for selection in ['pz100','pz50']:
        pzmask=np.ones(n,bool) if selection=='pz50' else (d['reco_pz_GeV']>100)&(d['incoming'][:,3]>100000)
        masks={'circle100':radius100,'circle125':radius125,'full_geometry':np.ones(n,bool)}
        selected={key[1]:r for key,r in finalists.items() if key[0]==selection}
        masks.update({f"rectangle_{i}":rectangle(d,r) for i,r in selected.items()})
        for role in ['all_descriptive','cal','test']:
            cohort=pzmask & (np.ones(n,bool) if role=='all_descriptive' else d['evaluation_role']==role)
            base=metrics(d,cohort&radius100)
            boot=Bootstrap(d,cohort,p['bootstrap_seed']) if role!='all_descriptive' else None
            for name,mask in masks.items():
                m=metrics(d,cohort&mask);q=dict(selection=selection,role=role,policy=name,**m,
                  record_gain100_pct=(m['N']/base['N']-1)*100,log_RMSE_ratio100=m['log_RMSE']/base['log_RMSE'],
                  energy_standardized_log_RMSE=energy_standardized_rmse(d,cohort&mask,cohort&radius100),
                  parent_inside_N='NA',efficiency_within_geometry='NA',efficiency_common_parent='NA')
                if role=='all_descriptive':
                    if name.startswith('rectangle_'):
                        count=parent_count(coords,selected[int(name.split('_')[1])],selection)
                        q['parent_inside_N']=count;q['efficiency_within_geometry']=m['N']/count
                    common=int(coords['hist100' if selection=='pz100' else 'hist50'].sum())
                    q['efficiency_common_parent']=m['N']/common
                evaluations.append(q)
                if boot:
                    for ref,refmask in [('circle100',radius100),('circle125',radius125)]:
                        paired.append(dict(selection=selection,role=role,policy=name,reference=ref,**boot.compare(mask,refmask)))
                if role=='test':
                    for sn,sm in strata.items():
                        mm=metrics(d,cohort&mask&sm)
                        if mm:slices.append(dict(selection=selection,policy=name,stratum=sn,**mm))
    table('evaluation.tsv',evaluations);table('paired.tsv',paired);table('strata.tsv',slices)
    recommended=next(q for q in decisions if q['selection']=='pz100' and q['budget_RMSE_ratio']==1.01)
    candidate=grid[recommended['candidate_id']]
    for selection in ['pz100','pz50']:
        (OUT/f'recommended_cuts_{selection}.yaml').write_text(yaml.safe_dump(cut_configuration(bounds(candidate),selection),sort_keys=False))
    save('decisions.json',dict(recommended=dict(**recommended,geometry=geometry(candidate)),budgets=decisions,
          finalists=[dict(selection=s,**geometry(r)) for (s,_),r in finalists.items()],
          scope='exploratory cal-only grid selection; fixed finalists evaluated on already exposed test source groups; no retraining',
          objective='maximum yield within conditional +1% RMSE upper budget, tie smallest area; other budgets and N/log-MSE proxy are alternatives'))
    save('scan_resources.json',dict(wall_s=time.perf_counter()-start,CPU_parent_s=time.process_time(),workers=8,
          max_parent_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,candidates_per_selection=len(grid),grid_metric_rows=len(rows),
          cal_pareto_rows=len(front),cal_shortlist_rows=len(shortlist),test_finalists=len(finalists),new_fits=0,new_model_forwards=0))
    print(json.dumps(recommended),flush=True)


if __name__=='__main__':main()
