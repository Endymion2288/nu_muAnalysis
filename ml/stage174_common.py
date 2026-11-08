"""Truth-free same-slab control extraction and fixed calibration, worker only."""
import json,resource,time
from pathlib import Path
import awkward as ak
import numpy as np
import uproot
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage174_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage174'
NAMES=['Timing0','Timing1','Timing2','Timing3','Veto21']


def plan():return json.loads((OUT/'protocol.json').read_text())


def write(name,obj):
    (OUT/name).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')


def read(index,limit,phase):
    start=time.perf_counter();cpu=time.process_time();p=plan();source=p['sources'][index]
    keys=['run','eventID','clockPhase','longTracks','Track_pz0','Track_nDoF','Track_Chi2','Track_nLayers',
        'Track_X_atTrig','Track_Y_atTrig','Track_ThetaX_atTrig','Track_ThetaY_atTrig']
    keys+=[s+'_'+v for s in NAMES for v in ['status','raw_charge','localtime','bcidtime','triggertime']]
    with uproot.open(source['path'],array_cache=None) as f:
        tree=f['nt'];schema=tree.typenames();missing=sorted(set(keys)-set(schema))
        report=dict(index=index,label=source['label'],source=source,N_total=int(tree.num_entries),missing=missing,supported=not missing)
        if missing:
            report.update(CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-start);write(f'{phase}_{index}_summary.json',report);return report
        a=tree.arrays(keys,entry_stop=limit);n=len(a);lead=ak.argmax(a.Track_pz0,axis=1,keepdims=True,mask_identity=True)
        def leading(name):return ak.to_numpy(ak.fill_none(ak.firsts(a[name][lead]),np.nan))
        pz=leading('Track_pz0')/1000;ndof=leading('Track_nDoF');chi=leading('Track_Chi2');layers=leading('Track_nLayers')
        x=leading('Track_X_atTrig');y=leading('Track_Y_atTrig');tx=leading('Track_ThetaX_atTrig');ty=leading('Track_ThetaY_atTrig')
        track=(ak.to_numpy(a.longTracks)==1)&np.isfinite(pz)&(pz>50)&(pz<2000)&(ndof>0)&np.isfinite(chi)&(chi>=0)&(chi/np.maximum(ndof,1)<10)&(layers>=7)
        projection=np.isfinite(x)&np.isfinite(y)&(abs(x)<1000)&(abs(y)<1000)&(x!=-999)&(y!=-999)&np.isfinite(tx)&np.isfinite(ty)&(abs(tx)<1)&(abs(ty)<1)
        control=track&projection;status=np.column_stack([ak.to_numpy(a[s+'_status']) for s in NAMES])
        q=np.column_stack([ak.to_numpy(a[s+'_raw_charge']) for s in NAMES]).astype(float)
        local=np.column_stack([ak.to_numpy(a[s+'_localtime']) for s in NAMES]).astype(float)
        strict=(status==0)&np.isfinite(local)&(local>0)
        hist={}
        for key in f.keys(cycle=False):
            if key.startswith('hRandomCharge'):
                obj=f[key];hist[key]=str(obj.title)
        arrays=dict(run=ak.to_numpy(a.run),event=ak.to_numpy(a.eventID),entry=np.arange(n),control=control,track=track,projection=projection,
            pz0_GeV=pz,x_mm=x,y_mm=y,theta_x=tx,theta_y=ty,status=status,rawQ_pC=q,localtime_ns=local,strict=strict,
            bcidtime_ns=np.column_stack([ak.to_numpy(a[s+'_bcidtime']) for s in NAMES]),
            triggertime_ns=np.column_stack([ak.to_numpy(a[s+'_triggertime']) for s in NAMES]),clockPhase=ak.to_numpy(a.clockPhase))
        assert np.all(arrays['run']==source['run'])
        if phase=='full':
            with np.load(CACHE/f'pilot_{index}.npz') as old:
                for name in old.files:np.testing.assert_array_equal(arrays[name][:len(old[name])],old[name])
            report['pilot_prefix_exact']=True
        if index in [0,1]:
            old_index=1 if index==0 else 2
            with np.load(ROOT/f'ntuples/energy_ml_stage129/mucontrol_{old_index}.npz') as old:
                ref={int(e):k for k,e in enumerate(old['event'])}
                for entry in np.flatnonzero(control):
                    key=int(arrays['event'][entry]);assert key in ref
                    other=ref[key];assert int(old['run'][other])==source['run']
                    np.testing.assert_array_equal(local[entry,4],old['time'][other,4])
                    np.testing.assert_array_equal(q[entry,4],old['charge'][other,4])
            report['original_Stage129_control_identity_Veto21_exact']=True
        CACHE.mkdir(exist_ok=True,parents=True);path=CACHE/f'{phase}_{index}.npz';np.savez_compressed(path,**arrays)
        report.update(N=n,track_muon_N=int(track.sum()),projection_valid_N=int((track&projection).sum()),control_N=int(control.sum()),
            strict_end_N=[int((control&strict[:,j]).sum()) for j in range(5)],signed_negative_rawQ_N=int((q<0).sum()),
            placeholder_minus999_N=int((q==-999).sum()),histogram_titles=hist,
            raw_time_values_are_diagnostics=True,energy_fits=0,read_bytes=int(f.file.source.num_requested_bytes),
            CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-start,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,bytes=path.stat().st_size)
    write(f'{phase}_{index}_summary.json',report);return report


def pair_mapping(index,pair):
    source=plan()['sources'][index];record=next(r for r in json.loads((OUT/'cable_mapping.json').read_text()) if r['label']==source['label'])
    channels=record['channels']
    if len(channels)!=4:return False,channels
    a,b=[channels[j]['payload'] for j in pair]
    good=all(a[k]==b[k] for k in ['type','station','plate']) and a['pmt']!=b['pmt']
    summary=json.loads((OUT/f'full_{index}_summary.json').read_text())
    titles=summary['histogram_titles']
    for end in pair:
        channel=channels[end]['hardware'];title=titles.get(f'hRandomCharge{channel}','')
        good=good and title.startswith(f'Timing{end} Ch{channel} ')

    return good,channels


def calibrate(index):
    p=plan();gate=p['gates'];source=p['sources'][index];rows=[]
    with np.load(CACHE/f'full_{index}.npz') as z:d={k:z[k] for k in z.files}
    for i,j in p['pairs']:
        mapping,channels=pair_mapping(index,[i,j]);base=d['control']&d['strict'][:,i]&d['strict'][:,j]
        base &= np.isfinite(d['rawQ_pC'][:,[i,j]]).all(1)&(d['rawQ_pC'][:,[i,j]]>0).all(1)
        for kind in ['difference','relative_mean']:
            good=base.copy()
            if kind=='relative_mean':good &= d['strict'][:,4]&np.isfinite(d['rawQ_pC'][:,4])&(d['rawQ_pC'][:,4]>0)
            train=good&(d['entry']%2==0);valid=good&(d['entry']%2==1)
            row=dict(label=source['label'],pair=[i,j],kind=kind,input_N=len(good),control_N=int(d['control'].sum()),
                strict_pair_N=int((d['control']&d['strict'][:,i]&d['strict'][:,j]).sum()),
                positive_charge_supported_N=int(good.sum()),train_N=int(train.sum()),validation_N=int(valid.sum()),
                physical_same_slab_mapping=mapping,mapping=channels,usable=False,units='ns; x in mm; rawQ in pC')
            if mapping and train.sum()>=gate['train_N_min'] and valid.sum()>=gate['validation_N_min']:
                qi=d['rawQ_pC'][:,i];qj=d['rawQ_pC'][:,j];qr=d['rawQ_pC'][:,4]
                with np.errstate(divide='ignore',invalid='ignore'):
                    D=np.column_stack([np.ones(len(good)),d['x_mm']/100,1/np.sqrt(qi),1/np.sqrt(qj)]) if kind=='difference' else np.column_stack([np.ones(len(good)),1/np.sqrt(qi),1/np.sqrt(qj),1/np.sqrt(qr)])
                if kind=='difference':target=d['localtime_ns'][:,i]-d['localtime_ns'][:,j]
                else:
                    factor=np.sqrt(1+np.tan(d['theta_x'])**2+np.tan(d['theta_y'])**2)-(1 if source['kind']=='MC' else 0)
                    target=(d['localtime_ns'][:,i]+d['localtime_ns'][:,j])/2-d['localtime_ns'][:,4]-1598.9*factor/299.792458
                coef=np.linalg.lstsq(D[train],target[train],rcond=None)[0];error=target[valid]-D[valid]@coef
                rank=int(np.linalg.matrix_rank(D[train]));condition=float(np.linalg.cond(D[train]));xSD=float(d['x_mm'][train].std(ddof=1))
                abs95=float(np.quantile(abs(error),.95));rms=float(np.sqrt(np.mean(error**2)))
                basic=rank==4 and condition<gate['condition_max'] and xSD>=gate['train_x_SD_min_mm']
                row.update(coefficient=coef.tolist(),rank=rank,condition=condition,train_x_SD_mm=xSD,validation_RMSE_ns=rms,
                    validation_median_ns=float(np.median(error)),validation_abs95_ns=abs95,
                    training_ranges={k:[float(np.min(v[train])),float(np.max(v[train]))] for k,v in [('qL_pC',qi),('qR_pC',qj),*(( [('qRef_pC',qr)] ) if kind=='relative_mean' else []),('x_mm',d['x_mm']),('y_mm',d['y_mm'])]},
                    raw_validation_RMSE_ns=float(np.sqrt(np.mean((target[valid]-np.mean(target[train]))**2))))
                if kind=='difference':
                    slope=coef[1]/100
                    xerr=error/slope if abs(slope)>1e-12 else np.full(len(error),np.nan)
                    x95=float(np.quantile(abs(xerr),.95)) if np.isfinite(xerr).all() else None
                    row.update(slope_ns_per_mm=float(slope),effective_speed_magnitude_mm_per_ns=float(abs(2/slope)) if abs(slope)>1e-12 else None,
                        validation_position_abs95_mm=x95,
                        usable=bool(basic and abs95<=gate['delta_validation_abs95_max_ns'] and x95 is not None and x95<=gate['position_validation_abs95_max_mm']))
                else:row['usable']=bool(basic and abs95<=gate['relative_mean_validation_abs95_max_ns'])
            rows.append(row)
    return rows
