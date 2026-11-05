"""Freeze controlled family-count curves before any new model outcome."""
import hashlib
import json
import tarfile
from pathlib import Path

import numpy as np

from stage119_curve_common import ROOT,OUT,CACHE,old_inputs,load,weights,table


def main():
    contract=json.loads((OUT/'production_contract.json').read_text());old=old_inputs();parts=[];audits=[]
    for i,request in enumerate(contract['requests']):
        with tarfile.open(CACHE/f'production_{i}.tar.gz') as t:
            assert t.extractfile('result/exitcode.txt').read().strip()==b'0',i
            with np.load(t.extractfile('result/selected.npz')) as z:
                zdata={k:z[k] for k in z.files if k!='metadata_json'};md=json.loads(str(z['metadata_json']))
        n=len(zdata['run']);s=request['source'];a={k:zdata[k] for k in ['x','incoming','run','eventID','input_entry','truth_E_GeV','y_lepton','primary_p_GeV','primary_valid','confirmed','vertex_z_mm']}
        a.update(pz=zdata['reco_pz_GeV'],source=np.full(n,i),kind=np.full(n,s['kind']),component=np.full(n,s['component']),year=np.full(n,24 if 200184<=s['run']<=200189 else 22))
        parts.append(a);audits.append(dict(index=i,run=s['run'],kind=s['kind'],component=s['component'],parents=request['parent_N'],reconstructed=len(request['entries']),selected=n,
            reference=md['reference'],identity=md['parent_identity']))
    d={k:np.concatenate([a[k] for a in parts]) for k in parts[0]};allold=set()
    for path in json.loads((OUT/'exposure_inputs.json').read_text()):
        allold.update(map(tuple,load(path)['incoming']))
    keys,first,gid=np.unique(d['incoming'],axis=0,return_index=True,return_inverse=True);d['key_id']=gid
    isold=np.array([tuple(k) in allold for k in keys]);role=[]
    for key in keys:
        digest=hashlib.blake2b(np.asarray(key,dtype='<f8').tobytes(),digest_size=8,person=b'nuMu119').digest()
        u=int.from_bytes(digest,'little')%100
        role.append(1 if u<70 else 2 if u<85 else 3)
    # Retain every generated response view in the same proxy-family role.
    d['role']=np.where(isold[gid],0,np.asarray(role)[gid]);d['is_old_exposure']=isold[gid]
    expansion=d['kind']=='expansion';train=expansion&(d['role']==1);development=expansion&(d['role']==2);reserved=expansion&(d['role']==3)
    # Canonical-family composition: year/component/E/y/depth, independent of
    # fitted response and all model errors. Unsupported cells are listed.
    cells=[]
    for j in first:
        e=d['truth_E_GeV'][j];y=d['y_lepton'][j];z=d['vertex_z_mm'][j]
        cell=f'{d["year"][j]}:{d["component"][j]}:E{np.searchsorted([100,200,1000],e,side="right")}:y{np.searchsorted([.8],y,side="right") if np.isfinite(y) and 0<=y<1 else 2}:z{int(z>=-1950)}'
        cells.append(cell)
    d['cell']=np.asarray(cells)[gid];rng=np.random.default_rng(2026110519);subsets=[[],[],[]];composition=[]
    for cell in sorted(set(d['cell'][train])):
        families=np.unique(gid[train&(d['cell']==cell)]);families=rng.permutation(families);base=len(families)//4
        for j in range(3):subsets[j].extend(families[:base*2**j].tolist())
        composition.append(dict(cell=cell,available_train_families=len(families),N=base,N2=2*base,N4=4*base,excluded_families=len(families)-4*base))
    scales=[len(s) for s in subsets];assert scales[0]>0 and scales==[scales[0],2*scales[0],4*scales[0]]
    d['curve_scale']=np.zeros(len(gid),int)
    for j in range(2,-1,-1):d['curve_scale'][train&np.isin(gid,subsets[j])]=j+1
    for j in range(3):
        use=train&np.isin(gid,subsets[j]);d[f'train_{2**j}N']=use
        assert not set(gid[use])&set(gid[development|reserved])
    np.savez_compressed(CACHE/'curve_input.npz',**d)
    np.savez_compressed(CACHE/'old_input.npz',**old)
    table('curve_composition.tsv',composition)
    counts=[]
    for name,mask in [('new_train',train),('new_development',development),('new_reserved',reserved),('old_exposure_response',expansion&(d['role']==0))]:
        for low,high in [(50,100),(100,200),(200,np.inf)]:
            use=mask&(d['truth_E_GeV']>=low)&(d['truth_E_GeV']<high)
            counts.append(dict(role=name,E_low_GeV=low,E_high_GeV=high,N=int(use.sum()),proxy_families=len(np.unique(gid[use]))))
    table('new_role_support.tsv',counts)
    baseline=json.loads((OUT.parent/'stage87_energy_ml/protocol.json').read_text())['baseline']
    protocol=dict(stage=119,scales=scales,counts_unit='new independent-incoming proxies within fixed common composition; GENIE parent certification incomplete',
        nesting='within each canonical-family year/component/E/y/depth cell, same random order and exact1:2:4 counts; all views in same role/subset',
        baseline=baseline,curve='three new-only training sizes; one original fixed strong BDT policy, original full-cal offset; evaluate same new development and old full target',
        augmented='one prespecified original full train + all new train deployment candidate, same policy, original cal offset; not called a fixed-composition quantity point',
        same_N_control='one old-train control matched at max-curve N to component/E/y/depth common cells where supported; year/flux mismatch must remain explicit',
        source_gap='only downstream support in expansion. No truth-z deployment gate. Unsupported strata kept for whole-target risk.',
        main_candidate='augmented_cal; all curve raw/cal points mandatory, no candidate/size/seed selection by development risk',
        confirmation='reserved proxy-family data extracted only; zero prediction/risk/fit; no new-blind claim without parent/old-all-exposure certification',
        gates='original two-low/1.05 traditional; all1.01/direct; five other1.03/direct; eight total/positive/negative tail50 upper95 <=+2pp',
        bootstrap='500 common incoming-cluster draws; conditional on available sources, refits/research-selection and real systems excluded',
        budgets=dict(cpus=8,memory_MB=24000,CPU_s=21600,wall_s=7200,GPU=0),model_outcomes_before_freeze=0)
    (OUT/'curve_protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    (OUT/'production_audit.json').write_text(json.dumps(audits,indent=2)+'\n')
    print('Frozen scales',scales,'role counts',counts,flush=True)


if __name__=='__main__':main()
