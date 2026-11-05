"""Independent source-wide identity/support and traditional-response check."""
import csv
import json
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage119_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage119'


def table(name,rows):
    with (OUT/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t');w.writeheader();w.writerows(rows)


def main():
    p=json.loads((OUT/'protocol.json').read_text());data=[]
    for s in p['sources']:
        with np.load(CACHE/f'pilot_{s["index"]}.npz') as z:
            data.append({k:z[k] for k in ['incoming','run','eventID','E','pz','y','vertex_z','S50','G0','input_entry']})
    d={k:np.concatenate([r[k] for r in data]) for k in data[0]};old=set()
    for name in json.loads((OUT/'exposure_inputs.json').read_text()):
        with np.load(ROOT/name) as z:old.update(map(tuple,z['incoming']))
    oldmask=np.array([tuple(k) in old for k in d['incoming']]);rows=[];risks=[]
    for run in dict.fromkeys(s['run'] for s in p['sources']):
        use=d['run']==run;idx=np.flatnonzero(use);keys=d['incoming'][idx]
        _,inv,count=np.unique(keys,axis=0,return_inverse=True,return_counts=True);weight=1/count[inv]
        E,pz,y,z=[d[k][idx] for k in ['E','pz','y','vertex_z']];S50=d['S50'][idx];G0=d['G0'][idx]
        layers=dict(all=np.ones(len(idx),bool),low50_100=(E>=50)&(E<100),low100_200=(E>=100)&(E<200),
                    lowpz_highE=(pz>=50)&(pz<100)&(E>=200),high_y=y>=.8,highE=E>=1000,upstream=z<-2200)
        for selection,take0 in [('parent',np.ones(len(idx),bool)),('S50',S50)]:
            for layer,mask in layers.items():
                take=take0&mask;w=weight[take]
                rows.append(dict(run=run,selection=selection,stratum=layer,N=int(take.sum()),
                    incoming=len(np.unique(keys[take],axis=0)),old_overlap_N=int((take&oldmask[idx]).sum()),
                    unknown_proxy_N=int((take&~oldmask[idx]).sum()),ESS=float(w.sum()**2/(w@w)) if len(w) else 0))
        for selection,take0 in [('G_positive',G0&(pz>0)&(E>0)),('S50',S50),('S100',S50&(pz>100))]:
            for layer,mask in layers.items():
                take=take0&mask;w=weight[take];error=np.log(pz[take]/(.8*E[take]));rel=pz[take]/(.8*E[take])-1
                avg=lambda a:float(np.average(a,weights=w)) if len(w) else None
                risks.append(dict(run=run,selection=selection,stratum=layer,N=len(w),bias_log=avg(error),
                    log_RMSE=float(np.sqrt(avg(error**2))) if len(w) else None,
                    tail50=avg(np.abs(rel)>.5),tail_positive50=avg(rel>.5),tail_negative50=avg(rel<-.5)))
    table('source_support.tsv',rows);table('traditional_response.tsv',risks)
    ghep=[];closure=[]
    for source in json.loads((OUT/'genie_schema.json').read_text()):
        path=source['input']
        if 'gtree' in source['trees']:
            try:
                with uproot.open(path) as f:
                    value=f['gtree']['gmcrec'].array(entry_stop=1,library='np')[0]
                    ghep.append(dict(input=path,read=True,class_name=value.classname,members=list(value.all_members)))
            except Exception as error:
                ghep.append(dict(input=path,read=False,error=repr(error)[:2000]))
        if 'gFaser' not in source['trees']:continue
        with uproot.open(path) as f:a=f['gFaser'].arrays(['n','pdgc','status','firstMother','px','py','pz','E'])
        differences=[]
        for r in ak.to_list(a):
            n=r['n'];pid=np.asarray(r['pdgc'][:n]);s=np.asarray(r['status'][:n]);m=np.asarray(r['firstMother'][:n]);energy=np.asarray(r['E'][:n]);mom=np.column_stack([r[k][:n] for k in ['px','py','pz']])
            nu=np.flatnonzero((abs(pid)==14)&(s==0));target=np.flatnonzero((s==11)&np.isin(abs(pid),[2112,2212]));system=np.flatnonzero(s==12)
            if len(nu)!=1 or len(target)!=1 or len(system)!=1:continue
            mu=np.flatnonzero((pid==pid[nu[0]]*13/14)&(m==nu[0]))
            if len(mu)!=1:continue
            qe=energy[nu[0]]-energy[mu[0]];qp=mom[nu[0]]-mom[mu[0]]
            lhs=(energy[target[0]]+qe)**2-np.sum((mom[target[0]]+qp)**2)
            rhs=energy[system[0]]**2-np.sum(mom[system[0]]**2)
            differences.append(lhs-rhs)
        closure.append(dict(input=path,DIS_status12_N=len(differences),W2_max_abs_difference_GeV2=float(np.max(abs(np.asarray(differences)))) if differences else None,
            W2_median_abs_difference_GeV2=float(np.median(abs(np.asarray(differences)))) if differences else None,
            note='comparison with GENIE status12 prefragmentation four-vector; not GHEP internal Kine.W certification'))
    (OUT/'validation.json').write_text(json.dumps(dict(source_wide_weights_before_selection=True,
        native_QA=json.loads((OUT/'extractqa.json').read_text())['passed'],ghep=ghep,W_closure=closure,
        old_exposure_scope='all persisted Stage55/70/81/82/87 incoming, including quarantine; not all historical preselection/gen parents',
        new_fits=0,new_forwards=0),indent=2)+'\n');print('Validation complete',flush=True)


if __name__=='__main__':main()
