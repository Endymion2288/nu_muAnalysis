#!/usr/bin/env python3
"""Compact event, primary truth, candidate matching and local station response for one RDO."""
import argparse
import gzip
import json
from pathlib import Path
import time

import awkward as ak
import numpy as np
import uproot
from compare_tracking import extract, raw_nontrack_check, selection, MODES
from run_tracking_georotation import FIELDS

TRACK_FIELDS=['event_index','mode','raw_index','long_index','leader']+FIELDS
SCALARS=['LeadTrack_Idx','LeadTrack_pz0','LeadTrack_nLayers','LeadTrack_nDoF','LeadTrack_Chi2_NDF',
         'LeadTrack_r_atMaxRadius','LeadTrack_rIFT','LeadTrack_rVetoNu','LeadTrack_Theta','Lead_Track_Y_atTrig']


def station_point(states,z):
    a=np.asarray(states,dtype=float).reshape(-1,6)
    if not len(a) or not np.isfinite(z):return np.full(6,np.nan),np.nan,0
    a=a[np.isfinite(a).all(axis=1)];a=a[np.argsort(a[:,2],kind='stable')]
    if not len(a):return np.full(6,np.nan),np.nan,0
    a=a[np.r_[True,np.diff(a[:,2])>1e-6]]
    nearest=int(np.argmin(abs(a[:,2]-z)));distance=abs(a[nearest,2]-z)
    hi=np.searchsorted(a[:,2],z)
    if 0<hi<len(a) and a[hi,2]-a[hi-1,2]<=150:
        w=(z-a[hi-1,2])/(a[hi,2]-a[hi-1,2])
        return a[hi-1]*(1-w)+a[hi]*w,distance,1
    if distance<=5:return a[nearest],distance,2
    return np.full(6,np.nan),distance,0


def main():
    start=time.monotonic();p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,required=True);p.add_argument('--version',choices=['old','new'],required=True)
    p.add_argument('--index',type=int,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--reference',type=Path);p.add_argument('--full-reference',action='store_true')
    args=p.parse_args();rotated=args.version=='new'
    data,masks=zip(*(extract(Path(mode+'.root'),args.repo,rotated=rotated) for mode in MODES))
    assert raw_nontrack_check([m+'.root' for m in MODES])==17
    names=[n for n,_ in selection(args.repo)[0]];fi=names.index('Truth pz > 100 GeV')+1
    for d in data[1:]:
        for k in ['run','eventID','truth_pz_nu','truth_dec_x_nu','truth_dec_y_nu','truth_dec_z_nu']:
            assert np.array_equal(d[k],data[0][k],equal_nan=True),k
    baseline=masks[0][:,fi];n=int(baseline.sum());keys=list(zip(data[0]['run'][baseline],data[0]['eventID'][baseline]))
    lookup={tuple(map(int,k)):i for i,k in enumerate(keys)}
    result={k:data[0][k][baseline] for k in ['run','eventID','truth_pz_nu','truth_dec_x_nu','truth_dec_y_nu','truth_dec_z_nu']}
    result['all_run']=data[0]['run'];result['all_eventID']=data[0]['eventID']
    result['counts']=np.array([m.sum(axis=0) for m in masks]);result['event_cut_bits']=np.zeros((n,3),np.uint16)
    result['event_individual_bits']=np.zeros((n,3),np.uint16)
    for m in range(3):
        for j in range(14):
            result['event_cut_bits'][:,m]|=masks[m][baseline,fi+1+j].astype(np.uint16)<<j
            result['event_individual_bits'][:,m]|=data[m][f'comparison_cut_{fi+j}'][baseline].astype(np.uint16)<<j
    result['event_scalars']=np.stack([np.column_stack([d[k][baseline] for k in SCALARS]) for d in data],axis=1)
    result['scalar_fields']=np.array(SCALARS)
    # Retain common scintillator inputs so waveform changes can be controlled independently.
    scint=['Veto20_charge','Veto21_charge','Preshower0_charge','Preshower1_charge',
           'VetoNu0_reduced_charge','VetoNu1_reduced_charge']+[f'Timing{i}_charge' for i in range(4)]
    truthnames=['truth_barcode','truth_pdg','truth_px','truth_py','truth_pz','truth_prod_x','truth_prod_y','truth_prod_z',
                'truth_dec_x','truth_dec_y','truth_dec_z']
    truthnames += [f'truth_st{s}_{a}' for s in (1,2,3) for a in ['x','y','z','px','py','pz']]
    truthnames += [f'truth_nHits_st{s}_l{l}' for s in (1,2,3) for l in (0,1,2)]
    tracknames=['Track_px0','Track_py0','Track_pz0','Track_Chi2','Track_nDoF','Track_nLayers','t_barcode','t_pdg','t_truthHitRatio']
    nts=[]
    for mode in MODES:
        with uproot.open(mode+'.root') as f:a=f['nt'].arrays(['run','eventID']+truthnames+tracknames+scint,library='ak')
        nts.append({(int(r.run),int(r.eventID)):r for r in a if (int(r.run),int(r.eventID)) in lookup})
    primary=np.zeros((n,3));primary[:,2]=np.nan
    truth_st=np.full((n,3,6),np.nan);truth_prod=np.full((n,3),np.nan);truth_layers=np.zeros((n,9),np.int16);charges=np.full((n,len(scint)),np.nan)
    for key,i in lookup.items():
        row=nts[0][key];pdg=np.asarray(row.truth_pdg)
        selected=pdg==pdg[0]*13/14
        for a in 'xyz':selected&=abs(np.asarray(row['truth_prod_'+a])-float(row['truth_dec_'+a][0]))<=1e-4
        found=np.flatnonzero(selected);primary[i,2]=len(found)
        charges[i]=[float(row[k]) for k in scint]
        if len(found)==1:
            j=found.item();primary[i,:2]=[int(row.truth_barcode[j]),int(row.truth_pdg[j])]
            truth_layers[i]=[int(row[f'truth_nHits_st{s}_l{l}'][j]) for s in (1,2,3) for l in (0,1,2)]
            truth_prod[i]=[float(row['truth_'+a][j]) for a in ['px','py','pz']]
            truth_st[i]=[[float(row[f'truth_st{s}_{a}'][j]) for a in ['x','y','z','px','py','pz']] for s in (1,2,3)]
    tracks=[];reco=[];reco_primary=[];matched_truth=[];near=[];methods=[];raw_primary=np.zeros((n,3,3),np.int32)
    checked=0;seen=set()
    with gzip.open('station_states.jsonl.gz','rt') as f:
        for line in f:
            run,event,collections=json.loads(line);key=(run,event)
            assert key not in seen;seen.add(key)
            if key not in lookup:continue
            i=lookup[key]
            for m,collection in enumerate(collections):
                row=nts[m][key];long_idx=0
                for raw_idx,(v,states) in enumerate(collection):
                    match_primary=primary[i,2]==1 and v[13]==primary[i,0] and v[14]==primary[i,1]
                    if match_primary and v[15]>=.7*v[9]:
                        raw_primary[i,m,0]+=1;raw_primary[i,m,1]+=bool(v[12])
                        raw_primary[i,m,2]+=bool(v[12] and v[10]>=7 and v[8]>=9 and np.isfinite(v[7]) and v[7]<15*v[8])
                    if not v[12]:continue
                    assert long_idx<len(row.Track_px0),(key,m,'long mismatch')
                    q=[v[5],v[4],-v[3]] if rotated else v[3:6]
                    assert np.allclose([row.Track_px0[long_idx],row.Track_py0[long_idx],row.Track_pz0[long_idx]],q,rtol=2e-6,atol=.05,equal_nan=True)
                    assert np.allclose([row.Track_Chi2[long_idx],row.Track_nDoF[long_idx],row.Track_nLayers[long_idx]],
                                       [v[7],v[8],v[10]],rtol=2e-6,equal_nan=True)
                    if v[13]!=0:
                        assert row.t_barcode[long_idx]==v[13] and row.t_pdg[long_idx]==v[14]
                        assert np.isclose(row.t_truthHitRatio[long_idx],v[15]/(v[8]+5),rtol=2e-6)
                    checked+=1
                    islead=long_idx==int(result['event_scalars'][i,m,0])
                    tracks.append([i,m,raw_idx,long_idx,int(islead)]+v)
                    found=np.flatnonzero(np.asarray(row.truth_barcode)==v[13]) if v[13] else []
                    t=np.array([[float(row[f'truth_st{s}_{a}'][found[0]]) for a in ['x','y','z','px','py','pz']] for s in (1,2,3)]) if len(found)==1 else np.full((3,6),np.nan)
                    pred=[station_point(states,x[2]) for x in t]
                    reco_primary.append([station_point(states,x[2])[0] for x in truth_st[i]])
                    reco.append([x[0] for x in pred]);near.append([x[1] for x in pred]);methods.append([x[2] for x in pred]);matched_truth.append(t)
                    long_idx+=1
                assert long_idx==len(row.Track_px0),(key,m,'long count')
    assert len(seen)==int(result['counts'][0,0])
    result.update(primary=primary,primary_production_momentum_mev=truth_prod,primary_station=truth_st,primary_layer_hits=truth_layers,
        scintillator=charges,scintillator_fields=np.array(scint),raw_primary_counts=raw_primary,
        tracks=np.asarray(tracks).reshape(-1,len(TRACK_FIELDS)),track_fields=np.array(TRACK_FIELDS),
        reco_station=np.asarray(reco).reshape(-1,3,6),reco_at_primary_station=np.asarray(reco_primary).reshape(-1,3,6),matched_truth_station=np.asarray(matched_truth).reshape(-1,3,6),
        nearest_state_dz_mm=np.asarray(near).reshape(-1,3),station_method=np.asarray(methods,dtype=np.uint8).reshape(-1,3),
        version=args.version,manifest_index=args.index,official_long_matches_checked=checked)
    if args.reference:
        with np.load(args.reference) as ref:
            pos={(int(r),int(e)):j for j,(r,e) in enumerate(zip(ref['run'],ref['eventID']))}
            assert all(key in pos for key in lookup)
            indices=np.array([pos[key] for key in lookup])
            assert np.array_equal(result['event_cut_bits'],ref['event_cut_bits'][indices]),'prior cut bits'
            if args.full_reference:assert len(indices)==len(pos)
        result['prior_cut_bits_verified']=True
    result['extraction_wall_s']=time.monotonic()-start
    np.savez_compressed(args.output,**result)
    with np.load(args.output) as saved:
        for k,v in result.items():
            a=np.asarray(v);assert np.array_equal(a,saved[k],equal_nan=a.dtype.kind in 'fc'),k
    print(json.dumps(dict(events=int(result['counts'][0,0]),truth=n,long_tracks=len(tracks),
                          checked=checked,wall_s=result['extraction_wall_s'],bytes=args.output.stat().st_size)),flush=True)


if __name__=='__main__':main()
