"""Actual data readout/track comparisons and frozen complete-boundary cost gate."""
import csv
import gzip
import json
import math
import sys
from collections import Counter,defaultdict
from pathlib import Path
import awkward as ak
import numpy as np
import uproot
from stage158_finalize import gnu

OUT=Path('workbook/stage162_energy_ml');CACHE=Path('ntuples/energy_ml_stage162')
phase=sys.argv[1];assert phase in ['pilot','full','repeat']
def read(name):return json.loads((OUT/name).read_text())
def write(name,data):(OUT/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
def payload(kind,which=phase):
    with gzip.open(CACHE/f'{which}_{kind}.json.gz','rt') as stream:return json.load(stream)
def table(name,rows):
    with (OUT/name).open('w') as stream:
        columns=list(dict.fromkeys(k for row in rows for k in row))
        writer=csv.DictWriter(stream,fieldnames=columns,delimiter='\t',lineterminator='\n',quoting=csv.QUOTE_NONNUMERIC)
        writer.writeheader();writer.writerows(rows)
def number(value,positive=False):
    if value is None:return None
    v=float(value)
    return v if math.isfinite(v) and v not in [-999.,-9999.,-99999.] and (not positive or v>0) else None

native=payload('native');raw=payload('raw');N=64 if phase=='full' else 4
assert len(native)==len(raw)==N
if phase in ['full','repeat']:
    assert native[:4]==payload('native','pilot') and raw[:4]==payload('raw','pilot')
with gzip.open(Path('ntuples/energy_ml_stage161/event_records.json.gz'),'rt') as stream:prior_capsule=json.load(stream)
prior_raw=json.loads(prior_capsule['ntuples/energy_ml_stage161/pilot_raw.json.gz'])
prior_native=json.loads(prior_capsule['ntuples/energy_ml_stage161/pilot_native.json.gz'])
for old,new in zip(prior_raw,raw[:4]):
    assert all(new[k]==v for k,v in old.items() if k!='waves')
    assert len(old['waves'])==len(new['waves'])
    assert all(all(nw[k]==v for k,v in ow.items()) for ow,nw in zip(old['waves'],new['waves']))
for old,new in zip(prior_native,native[:4]):
    assert all(new[k]==v for k,v in old.items() if k!='cable_mapping')
    assert [row[:2] for row in old['cable_mapping']]==[row[:2] for row in new['cable_mapping']]
manifest=read('matched_manifest.json');plan=read('protocol.json')
labels={'calo':'CaloLo','calo2':'CaloHi','calonu':'CaloNu','veto1':'Veto1','veto2':'Veto2',
        'vetonu':'VetoNu','trigger':'Timing','preshower':'Preshower'}
fields={'raw_charge':'raw_charge_pC','raw_peak':'raw_peak_mV','baseline_rms':'baseline_rms_mV','status':'status'}
track_fields=['Track_x0','Track_y0','Track_z0','Track_px0','Track_py0','Track_pz0','Track_charge','Track_Chi2','Track_nDoF','Track_nLayers']
with uproot.open(manifest['PHYS'],array_cache=None) as file:
    tree=file['nt'];schema=set(tree.keys())
    branches=track_fields+['longTracks']+[label+str(i)+'_'+f for label in labels.values() for i in range(4) for f in fields]
    branches=list(dict.fromkeys(b for b in branches if b in schema))
    phys=tree.arrays(branches+['run','eventID'],entry_start=0,entry_stop=N)
    phys_bytes=int(file.file.source.num_requested_bytes)
rows=[];stats=defaultdict(Counter);trackstats=defaultdict(Counter);covstats=Counter();maxpz=defaultdict(float)
for j,(n,r) in enumerate(zip(native,raw)):
    assert n['PHYS_entry']==r['PHYS_entry']==j
    assert n['native_entry']==r['native_entry']==manifest['records'][j]['native_entry']
    assert n['run']==r['run']==int(phys['run'][j]) and n['event']==r['event']==int(phys['eventID'][j])
    grouped=defaultdict(list)
    for channel,kind,compact,id32 in n['cable_mapping']:
        if kind in labels:grouped[kind].append((int(channel),int(id32)))
    primary=defaultdict(list)
    for wave in r['waves']:
        assert wave['status']==0 or wave['localtime_ns'] is None
        if not wave['secondary']:primary[wave['channel']].append(wave)
    for kind,channels in grouped.items():
        for k,(channel,id32) in enumerate(sorted(channels)):
            label=labels[kind]+str(k);s=stats[label];s['parent_N']+=1
            hits=primary[channel];w=hits[0] if len(hits)==1 else None
            s['unique_primary_N']+=w is not None;s['missing_N']+=len(hits)==0;s['ambiguous_N']+=len(hits)>1
            if w is not None:
                s['identifier_equal_N']+=w['id32']==id32
                s['nonzero_status_N']+=w['status']!=0;s['overflow_N']+=(w['status']&4)!=0
                s['empty_wave_N']+=w['wave_sample_N']==0;s['empty_time_N']+=w['time_sample_N']==0
                s['nonempty_wave_N']+=w['wave_sample_N']>0;s['sample_lengths_equal_N']+=w['wave_sample_N']==w['time_sample_N']
                q=number(w['raw_charge_pC']);present=(w['status']&(8|128|256))==0 and number(w['baseline_rms_mV'],True) is not None
                s['measured_raw_N']+=present and q is not None
                s['legal_negative_raw_N']+=present and q is not None and q<0
                s['legal_raw_minus1_N']+=present and q==-1
            for field,stored in fields.items():
                branch=label+'_'+field;exists=branch in branches
                target=float(phys[branch][j]) if exists else None
                value=w[stored] if w else None
                exact=bool(exists and value is not None and float(np.float32(value))==target)
                s[field+'_compared_N']+=exists and value is not None;s[field+'_exact_N']+=exact
                rows.append(dict(PHYS_entry=j,native_entry=n['native_entry'],event=n['event'],label=label,
                    channel=channel,id32=id32,field=field,native=value,PHYS=target,exact_float32=exact,
                    source_field_present=exists,unique_primary=w is not None))
    target=[ak.to_list(phys[b][j]) if b in branches else [] for b in track_fields]
    for collection,tracks in n['collections'].items():
        s=trackstats[collection];s['parent_N']+=1;s['collection_present_N']+=tracks is not None
        if tracks is None:continue
        s['native_long_track_N']+=len(tracks)
        pz=[t['state'][5] for t in tracks]
        s['PHYS_long_count_equal_N']+=len(tracks)==int(phys['longTracks'][j])
        s['pz0_vector_exact_N']+=pz==target[5]
        s['all_state_vectors_exact_N']+=all([t['state'][v] for t in tracks]==target[v] for v in range(9)) and [t['layers'] for t in tracks]==target[9]
        if pz and target[5]:maxpz[collection]=max(maxpz[collection],abs(max(pz)-max(target[5]))/1000)
        for t in tracks:
            covstats['long_track_N']+=1
            measurements=t['measurements'];covstats['measurement_N']+=len(measurements)
            covstats['linked_measurement_N']+=sum(m[3]==1 for m in measurements)
            covstats['unlinked_measurement_N']+=sum(m[3]!=1 for m in measurements)
            cv=t['covariance']
            complete=len(cv)==25 and all(v is not None for v in cv)
            covstats['complete_finite_covariance_N']+=complete
            if complete:
                matrix=np.asarray(cv).reshape(5,5)
                covstats['exact_symmetric_covariance_N']+=bool(np.array_equal(matrix,matrix.T))
                covstats['positive_definite_covariance_N']+=bool(np.linalg.eigvalsh(matrix).min()>0)
    pz=target[5];valid=[v for v in pz if number(v) is not None]
    leading=max(range(len(pz)),key=lambda k:pz[k]) if valid and len(valid)==len(pz) else None
    c=covstats;c['PHYS_parent_N']+=1
    if leading is not None:
        p=number(pz[leading]);chi=number(target[7][leading]);ndof=number(target[8][leading],True)
        selected=(int(phys['longTracks'][j])==1 and 50000<p<2000000 and chi is not None and chi>=0 and ndof is not None
                  and chi/ndof<10 and target[9][leading]>=7)
        c['PHYS_track_control_eligible_N']+=selected
        c['PHYS_track_control_pz50_100_N']+=selected and 50000<p<100000

table(f'{phase}_raw_comparison.tsv',rows)
table(f'{phase}_raw_support.tsv',[dict(label=k,**dict(v)) for k,v in sorted(stats.items())])
required=set(['VetoNu0','VetoNu1','Veto10','Veto20','Veto21','Timing0','Timing1','Timing2','Timing3','Preshower0','Preshower1']+
             [f'Calo{gain}{i}' for gain in ['Lo','Hi'] for i in range(4)])
raw_complete=required<=set(stats) and all(s['unique_primary_N']==N and s['identifier_equal_N']==N and all(s[f+'_compared_N']==N and s[f+'_exact_N']==N for f in fields) for s in stats.values())
# Source-defined content and parser proof are additional gates, never relax physical IDs.
content=[]
for n,r in zip(native,raw):
    assert n['dictionary'][2]=='4',n['dictionary']
    for w in r['waves']:
        if w['secondary']:continue
        size=w['wave_sample_N'];summed=w['sample_sum_mV'];absolute=w['sample_abs_sum_mV']
        integral=w['raw_charge_pC']*50 if w['raw_charge_pC'] is not None else None
        finite=size>0 and w['finite_sample_N']==size and summed is not None and absolute is not None and integral is not None
        if finite:
            f=np.float32(integral)
            ulp=max(abs(float(np.nextafter(f,np.float32(np.inf)))-float(f)),abs(float(f)-float(np.nextafter(f,np.float32(-np.inf)))))
            gamma=(size+2)*2**-53/(1-(size+2)*2**-53)
            bound=ulp/100+gamma*absolute*2/50
            delta=abs(summed*2/50-w['raw_charge_pC'])
            closed=delta<=bound and w['sample_max_mV']==w['raw_peak_mV']
        else:bound=delta=None;closed=False
        assert w['status']==0 or (w['time_start_ns'] is None and w['time_end_ns'] is None and w['time_spacing_2ns'] is None)
        content.append(dict(PHYS_entry=r['PHYS_entry'],channel=w['channel'],detector=w['detector'],status=w['status'],
            samples=size,finite=finite,delta_pC=delta,bound_pC=bound,closed=closed,
            status0_start_ns=w['time_start_ns'],status0_end_ns=w['time_end_ns'],status0_spacing2=w['time_spacing_2ns']))
table(f'{phase}_window_content.tsv',content)
content_pass=all(w['closed'] for w in content)
raw_complete=raw_complete and content_pass
summary=dict(passed=True,phase=phase,N=N,identity_exact=True,mapped_readout_N=len(stats),
    all_mapped_raw_float32_exact=raw_complete,missing_required_labels=sorted(required-set(stats)),stored_wave_sample_nonempty_N=sum(s['nonempty_wave_N'] for s in stats.values()),
    stored_wave_sample_empty_N=sum(s['empty_wave_N'] for s in stats.values()),
    empty_time_vector_N=sum(s['empty_time_N'] for s in stats.values()),legal_negative_raw_N=sum(s['legal_negative_raw_N'] for s in stats.values()),
    nonzero_status_N=sum(s['nonzero_status_N'] for s in stats.values()),
    track_comparison={k:dict(v,max_leading_pz0_difference_GeV=maxpz[k]) for k,v in trackstats.items()},
    covariance_and_control=dict(covstats),PHYS_read_bytes=phys_bytes,
    window_content=dict(N=len(content),closed_N=sum(w['closed'] for w in content),
        max_delta_pC=max(w['delta_pC'] for w in content if w['delta_pC'] is not None),
        sample_counts=sorted({w['samples'] for w in content}),status0_spacing2_N=sum(w['status0_spacing2'] is True for w in content)),
    dictionary_regions=4,source_conditions=manifest['metadata'].get('/TagInfo'),prefix4_exact=phase!='pilot',Stage161_raw_and_track_controls_exact=True,
    muon_purity='unmeasured',covariance_coverage='unmeasured',FPR='unmeasured',energy_fits=0,new_G4=0,promotion=False,overall_complete=False)
if phase=='pilot':
    rawcost=gnu(OUT/'pilot_raw_time.txt');natcost=gnu(OUT/'pilot_native_time.txt')
    rs,ns=read('pilot_raw_summary.json'),read('pilot_native_summary.json')
    projected_raw=3*(rawcost['CPU_s']-rs['post_first_read_CPU_s']+64*rs['post_first_read_mean_CPU_s'])
    projected_native=3*(natcost['CPU_s']-ns['steady_complete_interval_CPU_s']+64*ns['steady_complete_interval_max_CPU_s'])
    raw_already_charged=(OUT/'reuse_raw.json').exists()
    used=read('scheduler_accounting.json')['total_CPU_s']+(0 if raw_already_charged else rawcost['CPU_s'])+natcost['CPU_s']
    admitted=bool(raw_complete and used+projected_raw+projected_native+200<=2000)
    write('admission.json',dict(admitted=admitted,raw_support_exact=raw_complete,already_used_plus_pilot_GNU_CPU_s=used,
        projected_full_raw_3x_CPU_s=projected_raw,projected_full_native_3x_CPU_s=projected_native,
        audit_reserve_CPU_s=200,CPU_budget_s=2000,raw_already_in_prior_scheduler=raw_already_charged,
        scope='Before pilot job exits: newly executed GNU plus prior scheduler; cached raw not charged twice; compare/probe CPU charged at next submission gate'))
    summary.update(admitted=admitted,terminal_experiment=not admitted)
elif phase=='full':summary.update(terminal_experiment=False)
else:summary.update(terminal_experiment=True,independent_prefix4_exact=True)
write(f'{phase}_comparison_summary.json',summary);write('summary.json',summary);print(summary,flush=True)
