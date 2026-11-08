"""Actual ntuple/native-S0 match and plane brackets; no learned model or correction."""
import gzip,json,sys
from pathlib import Path
import awkward as ak
import numpy as np
import uproot
root=Path(sys.argv[1]);work=Path(sys.argv[2]);index=int(sys.argv[3]);out=root/'workbook/stage176_energy_ml';cache=root/'ntuples/energy_ml_stage176'
with gzip.open(cache/f'parent_{index}_lineage.json.gz','rt') as f:lineage=json.load(f)
states=json.loads((work/'native_S0_states.json').read_text());names=['Track_x0','Track_y0','Track_z0','Track_px0','Track_py0','Track_pz0']
scint=['VetoNu0','VetoNu1','Veto10','Veto20','Veto21','Timing0','Timing1','Timing2','Timing3','Preshower0','Preshower1']
with uproot.open(work/'ntuple.root') as f:
    t=f['nt'];keys=['run','eventID','longTracks']+names+[s+'_'+v for s in scint for v in ['raw_charge','status']]
    extra=[b for b in ['t_pdg','t_barcode','t_pdg_parent','t_barcode_parent','t_truthHitRatio'] if b in t]
    a=t.arrays(keys+extra);assert len(a)==1
    pz=ak.to_numpy(a.Track_pz0[0]);lead=int(np.argmax(pz)) if len(pz) else None
    observed=None
    if lead is not None:
        observed=[float(a[k][0][lead]) for k in names]
        matched=[s for s in states if np.array_equal(np.asarray(s['xyz_mm']+s['px_py_pz_MeV'],dtype='float32'),np.asarray(observed,dtype='float32'))]
    else:matched=[]
    raw=np.array([float(a[s+'_raw_charge'][0]) for s in scint]);status=np.array([int(a[s+'_status'][0]) for s in scint])
    recorded_truth={b:float(a[b][0][lead]) if lead is not None and len(a[b][0])==len(pz) else None for b in extra}
    summary=dict(index=index,N_native_states=len(states),N_ntuple_tracks=len(pz),leading_native_matches=len(matched),native_S0_supported=False,
        leading_state_xyz_pxpy_pz=observed,recorded_leading_truth=recorded_truth,
        ROOT_read_bytes=int(f.file.source.num_requested_bytes),energy_fits=0,energy_correction_added=False)
    with np.load(root/'ntuples/energy_ml_stage131/matched_input.npz') as old:
        row=np.flatnonzero(old['frame_index']==index);assert len(row)<=1
        if len(row):
            np.testing.assert_array_equal(raw.astype('float32'),old['raw_charge'][row[0]].astype('float32'));np.testing.assert_array_equal(status,old['status'][row[0]])
            np.testing.assert_array_equal(np.float32(pz[lead]/1000),np.float32(old['pz'][row[0]]))
            summary['original_selected_raw11_status_pz0_exact']=True
        else:summary['original_selected_raw11_status_pz0_exact']=None
    np.savez_compressed(cache/f'parent_{index}_readout.npz',raw_charge=raw,status=status,leading_state=np.asarray(observed) if observed is not None else np.full(6,np.nan))
if len(matched)==1 and len(lineage['muon_primaries'])==1:
    state=matched[0];normal=np.asarray(state['normal']);center=np.asarray(state['center_mm']);primary=lineage['muon_primaries'][0];rootID=int(primary[0]);momentum=np.array(primary[5:8])
    if np.dot(normal,momentum)<0:normal=-normal
    plane=bool('PlaneSurface' in state['surface_name'] and np.isfinite(normal).all() and abs(np.linalg.norm(normal)-1)<1e-8)
    summary.update(surface=state,plane_supported=plane,primary_muon_root=rootID)
    if plane:
        crossings=[]
        for ordinal,s in enumerate(lineage['muon_segments']):
            if int(s[0])!=rootID:continue
            pre=np.dot(np.array(s[1:4])-center,normal);post=np.dot(np.array(s[4:7])-center,normal)
            if pre<=0 and post>0 or pre>0 and post<=0:
                crossings.append(dict(ordinal=ordinal,forward=bool(pre<=0 and post>0),pre_post_signed_distance_mm=[float(pre),float(post)],pre_post_total_energy_MeV=s[7:9],pre_post_time_ns=s[11:13]))
        first=next((c for c in crossings if c['forward']),None)
        births=[];groups={0:'primary_muon_direct',-1:'other_root',-2:'unknown_root'}
        for b in lineage['muon_births']:
            distance=float(np.dot(np.asarray(b['xyz_mm'])-center,normal));tag='before_S0' if distance<0 else 'after_S0' if distance>0 else 'on_S0'
            groups[b['group']]=tag;births.append(dict(**b,signed_distance_mm=distance,S0_side=tag))
        partitions={}
        for name,hits in lineage['daq_hits'].items():
            ids=lineage['daq_birth_groups'][name];assert len(ids)==len(hits)
            counts={};energy={}
            for group,hit in zip(ids,hits):
                assert group in groups;tag=groups[group];counts[tag]=counts.get(tag,0)+1;energy[tag]=energy.get(tag,0.)+hit[5]
            assert sum(counts.values())==len(hits)
            partitions[name]=dict(hit_counts=counts,corrected_SD_response_MeV=energy,all_hits=len(hits),all_time_not_DAQ_charge=True)
        summary.update(native_S0_supported=first is not None,crossings=crossings,first_forward_crossing=first,
            fitted_E_mu_S0_GeV=float(np.sqrt(np.sum(np.asarray(observed[3:])**2)+105.6583755**2)/1000),
            actual_primary_initial_E_GeV=primary[8]/1000,muon_births=births,hit_source_partition=partitions,
            unmeasured='Exact within-step crossing energy, per-track applied material-loss correction, source analog charge, and unbiased population or energy improvement.')
(out/f'parent_{index}_S0.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
print(summary,flush=True)
