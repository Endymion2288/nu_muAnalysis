"""One low-dimensional nuisance projection, joint real/random/MC; Condor only."""
import resource
import sys
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_CPU,(180,180) if sys.argv[1]=='pilot' else (1200,1200))
import collections
import csv
import gzip
import json
import math
import time
from pathlib import Path

import numpy as np
import ROOT

OUT=Path('workbook/stage196_energy_ml');CACHE=Path('ntuples/energy_ml_stage196')
P=json.loads((OUT/'protocol.json').read_text());LAGS=np.arange(-8,33)


def write(name,obj):
    (OUT/name).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')


def table(name,rows):
    if not rows:return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=keys,delimiter='\t',lineterminator='\n',quoting=csv.QUOTE_NONNUMERIC)
        w.writeheader();w.writerows(rows)


def read_gz(path):
    with gzip.open(path,'rt') as f:return json.load(f)


def key(w):return w['detector']+':'+str(w['channel'])


def patch(w):
    if w['status']!=0 or w['secondary'] or w['detector']=='CaloNu':return None,'ineligible_original_status_or_role'
    if w['samples_mV'] is None or w['times_ns'] is None:return None,'missing_vectors'
    if len(w['samples_mV'])!=len(w['times_ns']) or any(x is None for x in w['samples_mV']+w['times_ns']):return None,'missing_or_nonfinite'
    a=np.asarray(w['samples_mV']);t=np.asarray(w['times_ns'])
    if len(a)<41 or not np.all(np.diff(t)==2):return None,'unsupported_sampling'
    peak=int(np.argmax(a));indices=peak+LAGS
    if indices[0]<0 or indices[-1]>=len(a):return None,'stored_window_edge'
    amplitude=float(a[peak])
    if amplitude<=0:return None,'nonpositive_peak'
    return dict(values=a[indices],peak_mV=amplitude,indices=indices,time_ns=t[indices]),'supported'


def basis(template):
    return np.column_stack([np.ones(len(template)),template,np.gradient(template,2.)])


def project(y,b):
    coef,_,rank,singular=np.linalg.lstsq(b,y,rcond=None)
    if rank!=3:return None
    residual=y-b@coef
    return dict(residual=residual,coefficients=coef,rank=int(rank),RMS=float(np.sqrt(np.mean(residual**2))),singular=singular)


def original_check(records):
    capsule=read_gz(P['original4_reference'])
    original=json.loads(capsule['ntuples/energy_ml_stage161/pilot_raw.json.gz'])
    checks=0
    for actual,old in zip(records[:4],original):
        assert all(actual[k]==old[k] for k in ['PHYS_entry','native_entry','run','event'])
        assert len(actual['waves'])==len(old['waves'])
        for a,b in zip(actual['waves'],old['waves']):
            for k in ['detector','channel','id32','status','secondary']:assert a[k]==b[k]
            for k in ['raw_charge_pC','raw_peak_mV','baseline_mV','baseline_rms_mV']:
                assert a[k] is None and b[k] is None or np.float32(a[k])==np.float32(b[k]);checks+=1
    return checks


def real(records,phase):
    support=collections.Counter();raw=[];training=collections.defaultdict(list);template_rows=[]
    for parent in records:
        for w in parent['waves']:
            support['all_records']+=1;support[f"original_status_{w['status']}"]+=1
            if w['status']!=0 or w['secondary'] or w['detector']=='CaloNu':
                assert w['samples_mV'] is None and w['times_ns'] is None and w['localtime_ns'] is None
            a,reason=patch(w);support[reason]+=1
            if a is not None:
                raw.append((parent,w,a))
                if parent['PHYS_entry']<32:training[key(w)].append(a['values']/a['peak_mV'])
    templates={}
    if phase!='pilot':
        for k,arrays in training.items():
            if len(arrays)>=4:
                t=np.median(np.stack(arrays),axis=0)
                if np.linalg.matrix_rank(basis(t))==3:templates[k]=t
            template_rows.append(dict(channel=k,train_N=len(arrays),template_available=k in templates))
    rows=[];vectors=[]
    for parent,w,a in raw:
        if phase=='pilot':continue
        row=dict(PHYS_entry=parent['PHYS_entry'],event=parent['event'],detector=w['detector'],channel=w['channel'],
            subset='first32' if parent['PHYS_entry']<32 else 'last32',peak_mV=a['peak_mV'],baseline_RMS_mV=w['baseline_rms_mV'],template_available=key(w) in templates)
        if key(w) in templates:
            b=basis(templates[key(w)]);pr=project(a['values'],b);assert pr is not None
            rms=pr['RMS'];noise=w['baseline_rms_mV']
            row.update(residual_RMS_mV=rms,residual_over_peak=rms/a['peak_mV'],
                residual_over_baseline_RMS=rms/noise if noise is not None and noise>0 else None,
                fitted_amplitude_mV=float(pr['coefficients'][1]),rank=pr['rank'],
                basis_condition_number=float(pr['singular'][0]/pr['singular'][-1]))
            vectors.append(dict(kind='data',identity=[parent['PHYS_entry'],w['detector'],w['channel']],
                values=a['values'].tolist(),basis=b.tolist(),coefficients=pr['coefficients'].tolist(),residual=pr['residual'].tolist()))
        rows.append(row)
    return dict(support=dict(support),templates=templates,template_rows=template_rows,rows=rows,vectors=vectors)


def random_controls(templates):
    rows=[];vectors=[];n=0
    for file in range(400,432):
        phase='pilot' if file<402 else 'full'
        with gzip.open(f'ntuples/energy_ml_stage183/{phase}_{file}_controls.jsonl.gz','rt') as f:events=[json.loads(line) for line in f]
        for event in events:
            n+=1;adc={}
            for board in event['boards']:
                assert board['decoded'] and board['valid'] and not board['board_fail']
                for channel in board['channels']:adc[16*board['board']+channel['channel']]=channel['adc']
            for label,t in templates.items():
                hardware=int(label.split(':')[1]);assert 0<=hardware<=19
                assert hardware in adc and len(adc[hardware])==280
                a=np.asarray(adc[hardware],float);mv=2/16.384
                y=(a[:40].mean()-a[60:101])*mv;b=basis(t);pr=project(y,b);assert pr is not None
                noise=float(a[:40].std(ddof=1)*mv)
                rows.append(dict(file=file,eventID=event['eventID'],channel=label,residual_RMS_mV=pr['RMS'],
                    residual_over_baseline_RMS=pr['RMS']/noise if noise>0 else None,first16=file<416))
                vectors.append(dict(kind='random_fixed_samples',identity=[file,event['eventID'],label],
                    values=y.tolist(),template_key=label,coefficients=None,residual=pr['residual'].tolist()))
    assert n==116
    return rows,vectors


def MC(indices):
    assert ROOT.gInterpreter.Declare(Path('ml/stage141_analog.hxx').read_text())
    rows=[];parents=[];vectors=[];closure_N=0;closure_max=0.
    for index in indices:
        cached=read_gz(f'ntuples/energy_ml_stage179/parent_{index}_response.json.gz')
        count=0
        for detector,record in cached['records'].items():
            good=[w for w in record['waves'] if int(w['result'][0])==0]
            # Never inspect a bad-status PMT's arrival/source timing for this analysis.
            ids={int(w['id32']) for w in good}
            if not ids:continue
            hits=[r for r in record['source_timing'] if int(r[0]) in ids]
            n=len(good[0]['adc']);condition=record['conditions']
            flat=[v for r in hits for v in [r[0],r[3],r[1]]]
            exact=np.asarray([list(r) for r in ROOT.Stage141Analog(flat,condition,sorted(ids),1,n)])
            old=np.asarray(cached['analog'][detector]['total'])
            collapsed=[];moments={}
            for identifier in sorted(ids):
                h=[r for r in hits if int(r[0])==identifier and r[1]>0]
                energy=math.fsum(r[1] for r in h)
                if energy>0:
                    mean=math.fsum(r[1]*r[3] for r in h)/energy
                    collapsed.extend([identifier,mean,energy])
                    moments[identifier]=dict(positive_hit_N=len(h),input_energy=energy,input_energy_float_rounding=float(np.float32(energy))-energy,
                        corrected_hit_mean_ns=mean,corrected_hit_RMS_ns=math.sqrt(math.fsum(r[1]*(r[3]-mean)**2 for r in h)/energy),
                        source_positive_hit_counts=dict(collections.Counter(r[-1] for r in h)))
                else:moments[identifier]=None
            collapse=np.asarray([list(r) for r in ROOT.Stage141Analog(collapsed,condition,sorted(ids),1,n)])
            for wave in good:
                count+=1;identifier=int(wave['id32']);mask=old[:,0]==identifier
                original=old[mask,2];restored=exact[exact[:,0]==identifier,2]
                delta=np.abs(original-restored);tolerance=32*np.finfo('float32').eps*np.maximum(1,np.abs(original))
                assert np.all(delta<=tolerance),(index,detector,identifier,float(delta.max()))
                closure_N+=len(delta);closure_max=max(closure_max,float(delta.max()))
                result=wave['result'];lo,hi=result[6:8]
                samples=np.flatnonzero((2*old[mask,1]>=lo)&(2*old[mask,1]<=hi))
                # Align using the original status0 stored signal measurement, not the truth time centroid.
                observed=(result[3]-(2000/16384)*np.asarray(wave['adc'],float))
                peak=int(samples[np.argmax(observed[samples])]);use=peak+LAGS
                row=dict(index=index,detector=detector,channel=int(wave['channel']),id32=identifier,
                    original_status=0,window_supported=bool(len(samples)>0 and use[0]>=samples[0] and use[-1]<=samples[-1]),
                    positive_input_supported=moments[identifier] is not None)
                if row['window_supported'] and moments[identifier] is not None:
                    pulse=collapse[collapse[:,0]==identifier,2][use];b=basis(pulse);pr=project(original[use],b)
                    row['projection_supported']=pr is not None
                    row['basis_rank']=int(np.linalg.matrix_rank(b))
                    if pr is not None:
                        peak_signal=float(np.max(np.abs(original[use])));noise=condition[1]
                        row.update(residual_RMS_ADC=pr['RMS'],residual_over_peak=pr['RMS']/peak_signal if peak_signal>0 else None,
                            residual_over_MC_noise_RMS=pr['RMS']/noise if noise>0 else None,
                            basis_condition_number=float(pr['singular'][0]/pr['singular'][-1]),**moments[identifier])
                        vectors.append(dict(kind='MC',identity=[index,detector,int(wave['channel'])],values=original[use].tolist(),
                            basis=b.tolist(),coefficients=pr['coefficients'].tolist(),residual=pr['residual'].tolist()))
                rows.append(row)
        parents.append(dict(index=index,original_status0_N=count,all_original_waves_N=sum(len(r['waves']) for r in cached['records'].values()),
            diagnostic=cached['summary']['diagnostic']))
    return rows,parents,vectors,dict(ideal_samples_N=closure_N,max_abs_difference_ADC=closure_max,passed=True)


def aggregate(rows,kind):
    groups=collections.defaultdict(list)
    for r in rows:
        label=(r['detector'],r.get('subset','all')) if kind!='random' else (r['channel'],'first16' if r['first16'] else 'last16')
        groups[label].append(r)
    out=[]
    measure='residual_over_MC_noise_RMS' if kind=='MC' else 'residual_over_baseline_RMS'
    for (label,subset),items in groups.items():
        values=[r[measure] for r in items if r.get(measure) is not None]
        frac=[r['residual_over_peak'] for r in items if r.get('residual_over_peak') is not None]
        out.append(dict(kind=kind,group=label,subset=subset,N=len(items),residual_supported_N=len(values),
            standardized_RMS_median=float(np.median(values)) if values else None,
            standardized_RMS_abs95=float(np.quantile(values,.95)) if values else None,
            residual_over_peak_median=float(np.median(frac)) if frac else None))
    return out


def main(phase):
    tick=time.perf_counter();cpu=time.process_time();records=read_gz(CACHE/f'{phase}_raw.json.gz')
    original=original_check(records)
    if phase=='full':assert records[:4]==read_gz(CACHE/'pilot_raw.json.gz')
    data=real(records,phase);noise,nv=random_controls(data['templates'])
    mc,parents,mv,closure=MC(P['MC_pilot'] if phase=='pilot' else P['MC_full'])
    table(f'{phase}_data.tsv',data['rows']);table(f'{phase}_templates.tsv',data['template_rows'])
    table(f'{phase}_random.tsv',noise)
    # Nested source-count maps stay JSON; flat diagnostic table retains all eligible PMTs.
    table(f'{phase}_MC.tsv',[{k:v for k,v in r.items() if k!='source_positive_hit_counts'} for r in mc])
    summaries=aggregate(data['rows'],'data')+aggregate(noise,'random')+aggregate(mc,'MC')
    table(f'{phase}_groups.tsv',summaries)
    science=dict(data_rows=data['rows'],templates={k:v.tolist() for k,v in data['templates'].items()},random_rows=noise,
        MC_rows=mc,MC_parents=parents,vectors=data['vectors']+nv+mv)
    with gzip.open(CACHE/f'{phase}_science.json.gz','wt',compresslevel=1) as f:json.dump(science,f,separators=(',',':'),allow_nan=False)
    summary=dict(passed=True,phase=phase,real_parent_N=len(records),original4_scalar_checks_N=original,
        raw_support=data['support'],template_channel_N=len(data['templates']),random_controls_N=116,
        MC_parent_N=len(parents),MC_ideal_closure=closure,groups=summaries,CPU_s=time.process_time()-cpu,
        wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        physical_source_identified=False,real_error_coverage_certified=False,energy_fits=0,overall_complete=False,promotion=False)
    write(f'{phase}_summary.json',summary)
    if phase=='full':
        import runpy
        runpy.run_path('ml/stage196_plot.py')
    print(summary,flush=True)


if __name__=='__main__':
    assert sys.argv[1] in ['pilot','full'];main(sys.argv[1])
