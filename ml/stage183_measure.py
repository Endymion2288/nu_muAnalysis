"""Finite ordinary-Ecal joint ADC controls; all payload/statistics on HTCondor."""
import collections,csv,gzip,json,math,multiprocessing as mp,resource,subprocess,sys,time
from pathlib import Path
import numpy as np
ROOT=Path.cwd();OUT=ROOT/'workbook/stage183_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage183'
p=json.loads((OUT/'protocol.json').read_text());CHANNELS=[0,1,2,3,16,17,18,19]
WINDOWS=['signal_diagnostic','offpulse']

def write(name,obj):(OUT/name).write_text(json.dumps(obj,indent=2)+'\n')
def table(name,rows):
    with (OUT/name).open('w') as stream:
        w=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n',quoting=csv.QUOTE_NONNUMERIC);w.writeheader();w.writerows(rows)
def read_controls(path):
    with gzip.open(path,'rt') as stream:return [json.loads(line) for line in stream]

def read_file(task):
    phase,index=task;path=p['paths'][index-400];tick=time.perf_counter();before=resource.getrusage(resource.RUSAGE_CHILDREN)
    with (OUT/f'{phase}_{index}_reader.log').open('w') as log:
        child=subprocess.Popen([str(ROOT/'reader'),path,str(p['limits']['physics_per_file'])],stdout=subprocess.PIPE,stderr=log,text=True)
        rows=[json.loads(line) for line in child.stdout];code=child.wait()
    assert code==0 and len(rows)==8192,(index,code,len(rows))
    if index==400:
        original=read_controls(ROOT/p['reference']);assert rows==original
    strict=[];trigger=collections.Counter();status=collections.Counter()
    for r in rows:
        t=r['tlb'];selected=len(t)==1 and t[0].get('supported')==1 and t[0].get('framed')==1 and t[0].get('valid')==1 and t[0].get('TAP')==16 and t[0].get('TBP')==16
        assert bool(r['strict'])==selected
        status[str(r['status'])]+=1
        if len(t)==1 and t[0].get('valid'):trigger[f"{t[0]['TAP']}/{t[0]['TBP']}"]+=1
        if selected:strict.append(r)
    retained=[r for r in strict if r['retained']];assert len(retained)==min(256,len(strict))
    with gzip.open(CACHE/f'{phase}_{index}_controls.jsonl.gz','wt',compresslevel=1) as stream:
        for r in retained:stream.write(json.dumps(r,separators=(',',':'))+'\n')
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    report=dict(file=index,path=path,physics_N=len(rows),strict_N=len(strict),retained_strict_N=len(retained),cap_exceeded=len(strict)>256,
        raw_frames_through=rows[-1]['raw_entry']+1,logical_RAW_bytes_through=rows[-1]['bytes_through'],trigger_counts=dict(trigger),status_counts=dict(status),
        timestamp_min_us=min(r['timestamp_us'] for r in rows),timestamp_max_us=max(r['timestamp_us'] for r in rows),
        first_eventID=rows[0]['eventID'],last_eventID=rows[-1]['eventID'],original400_all8192_exact=index==400,
        reader_CPU_s=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    write(f'{phase}_{index}_summary.json',report);return report

def channel_adc(r):
    boards=r['boards'];counts=collections.Counter(b['board'] for b in boards);result={}
    for b in boards:
        if counts[b['board']]!=1 or not (b.get('decoded') and b.get('valid') and not b.get('board_fail')):continue
        cs=collections.Counter(c['channel'] for c in b.get('channels',[]))
        for c in b.get('channels',[]):
            if cs[c['channel']]==1:result[16*b['board']+c['channel']]=c['adc']
    return result

def measurements(records):
    grl=json.loads((ROOT/p['GRL']).read_text());data={name:np.full((len(records),8),np.nan) for name in WINDOWS};details=[]
    for i,(file,r) in enumerate(records):
        adc=channel_adc(r);t=r['timestamp_us']//1000000
        good=any(a<=t<=b for a,b in grl['stable_inclusive_unix_seconds']) and not any(a<=t<=b for a,b in grl['excluded_inclusive_unix_seconds'])
        for channel in CHANNELS:
            a=adc.get(channel);valid=a is not None and len(a)>=max(max(p['windows'][name]) for name in p['windows'])
            row=dict(file=file,eventID=r['eventID'],raw_entry=r['raw_entry'],timestamp_us=r['timestamp_us'],channel=channel,valid=valid,
                GRL=good,status=r['status'],input_bits=r['tlb'][0]['input_bits'],input_bits_next=r['tlb'][0]['input_bits_next'],
                ADC_samples=len(a) if a is not None else None,zero_ADC_N=sum(v==0 for v in a) if a is not None else None,
                max_ADC_N=sum(v==16383 for v in a) if a is not None else None)
            baseline=float(np.mean(a[slice(*p['windows']['pedestal'])])) if valid else None
            row['pedestal_ADC']=baseline
            for name in WINDOWS:
                value=float(np.sum(baseline-np.asarray(a[slice(*p['windows'][name])],float))) if valid else None
                row[name+'_ADC_samples']=value
                if valid:data[name][i,CHANNELS.index(channel)]=value
            details.append(row)
    return data,details

def ratio(values):
    good=np.isfinite(values).all(1);a=values[good]
    if len(a)<2:return dict(N=len(a),ratio=None,sum_variances=None,sum_charge_variance=None)
    var=np.var(a,axis=0,ddof=1);den=float(var.sum());num=float(np.var(a.sum(1),ddof=1))
    return dict(N=len(a),ratio=num/den if den>0 else None,sum_variances=den,sum_charge_variance=num)

def statistics(records):
    data,details=measurements(records);blocks=np.asarray([f for f,r in records]);rng=np.random.default_rng(20261108183)
    draws=rng.choice(np.arange(400,432),size=(1000,32),replace=True);ratios=[];covariance=[];ranks=[]
    for name,a in data.items():
        for i,ch in enumerate(CHANNELS):
            for j,cj in enumerate(CHANNELS):
                use=np.isfinite(a[:,i])&np.isfinite(a[:,j]);n=int(use.sum())
                cv=float(np.cov(a[use,i],a[use,j],ddof=1)[0,1]) if n>=2 else None
                sd=np.std(a[use][:,[i,j]],axis=0,ddof=1) if n>=2 else None
                corr=cv/float(sd.prod()) if n>=2 and sd.prod()>0 else None
                covariance.append(dict(window=name,channel_i=ch,channel_j=cj,N=n,covariance_ADC_samples_squared=cv,correlation=corr))
        complete=a[np.isfinite(a).all(1)]
        ranks.append(dict(window=name,complete8_N=len(complete),rank=int(np.linalg.matrix_rank(np.cov(complete,rowvar=False))) if len(complete)>=2 else None,
            eigenvalues=np.linalg.eigvalsh(np.cov(complete,rowvar=False)).tolist() if len(complete)>=2 else None,no_inverse=True))
        for group,chs in p['active_groups'].items():
            values=a[:,[CHANNELS.index(c) for c in chs]];all_=ratio(values);rep=[]
            for draw in draws:
                selected=np.concatenate([np.flatnonzero(blocks==f) for f in draw]);v=ratio(values[selected])['ratio']
                if v is not None and math.isfinite(v):rep.append(v)
            low,high=np.quantile(rep,[.025,.975]).tolist() if rep else [None,None]
            ratios.append(dict(window=name,group=group,**all_,low95=low,high95=high,bootstrap_valid_N=len(rep),bootstrap_draw_N=1000,
                first16=ratio(values[blocks<416]),last16=ratio(values[blocks>=416])))
    return details,ratios,covariance,ranks

def scalar_audit(records,data,ratios,covariance):
    maximum=0.;checked=0
    for i,(file,r) in enumerate(records):
        adc=channel_adc(r)
        for j,ch in enumerate(CHANNELS):
            a=adc.get(ch)
            if a is None or len(a)<256:continue
            base=math.fsum(a[:40])/40
            for name in WINDOWS:
                lo,hi=p['windows'][name];value=math.fsum(base-v for v in a[lo:hi]);checked+=1
                maximum=max(maximum,abs(value-data[name][i,j]));assert abs(value-data[name][i,j])<1e-8
    def scalar_cov(x,y):
        n=len(x);mx=math.fsum(x)/n;my=math.fsum(y)/n
        return math.fsum((u-mx)*(v-my) for u,v in zip(x,y))/(n-1)
    for row in covariance:
        a=data[row['window']];i=CHANNELS.index(row['channel_i']);j=CHANNELS.index(row['channel_j'])
        pairs=[(float(r[i]),float(r[j])) for r in a if math.isfinite(r[i]) and math.isfinite(r[j])]
        assert len(pairs)==row['N']
        if len(pairs)>=2:
            x,y=zip(*pairs);value=scalar_cov(x,y)
            assert math.isclose(value,row['covariance_ADC_samples_squared'],rel_tol=1e-10,abs_tol=1e-8)
    for row in ratios:
        columns=[CHANNELS.index(c) for c in p['active_groups'][row['group']]];a=data[row['window']][:,columns];a=a[np.isfinite(a).all(1)]
        if len(a)<2:continue
        summed=[math.fsum(r) for r in a];den=math.fsum(scalar_cov(list(col),list(col)) for col in a.T);value=scalar_cov(summed,summed)/den
        assert math.isclose(value,row['ratio'],rel_tol=1e-10,abs_tol=1e-10)
    return dict(passed=True,scalar_integrals_N=checked,max_integral_abs_difference_ADC_samples=maximum,scalar_covariances_N=len(covariance),scalar_group_ratios_N=len(ratios))

if __name__=='__main__':
    tick,cpu=time.perf_counter(),time.process_time();phase=sys.argv[1]
    catalog=json.loads((ROOT/p['catalog']).read_text());allowed={r['path'] for r in catalog['RAW']['matched']}
    assert all(path in allowed for path in p['paths'])
    mappings=json.loads((ROOT/p['mapping']).read_text());mapping=next(r for r in mappings if r['instance']=='CONDBR3' and 'CableMapping' in r['folder'])
    assert {r['channel'] for r in mapping['rows'] if r['payload']['type']=='calo'}=={0,1,2,3}
    assert {r['channel'] for r in mapping['rows'] if r['payload']['type']=='calo2'}=={16,17,18,19}
    files=p['pilot_files'] if phase=='pilot' else p['full_files'] if phase=='full' else p['audit_RAW_files']
    with mp.get_context('spawn').Pool(min(p['worker_processes'],len(files))) as pool:summaries=pool.map(read_file,[(phase,f) for f in files])
    assert all(r['strict_N']>=1 for r in summaries) if phase=='pilot' else True
    result=dict(passed=True,phase=phase,files_N=len(files),physics_N=sum(r['physics_N'] for r in summaries),strict_N=sum(r['strict_N'] for r in summaries),
        files=summaries,parent_CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,overall_complete=False)
    if phase=='audit':
        for f in files:
            assert read_controls(CACHE/f'audit_{f}_controls.jsonl.gz')==read_controls(CACHE/f'pilot_{f}_controls.jsonl.gz')
        records=[]
        for f in range(400,432):
            prefix='pilot' if f in p['pilot_files'] else 'full';rows=read_controls(CACHE/f'{prefix}_{f}_controls.jsonl.gz')
            records.extend((f,r) for r in rows)
        assert len({(r['run'],r['eventID'],r['raw_entry'],f) for f,r in records})==len(records)
        details,ratios,covariance,ranks=statistics(records);data,_=measurements(records)
        proof=scalar_audit(records,data,ratios,covariance);proof.update(independent_RAW_files=files,original400_all8192_exact=True,strict_ADC_reread_exact=True,all32_catalog_paths=True)
        all_summaries=[]
        for f in range(400,432):
            prefix='pilot' if f in p['pilot_files'] else 'full'
            meta=json.loads((OUT/f'{prefix}_{f}_summary.json').read_text());assert meta['file']==f and meta['physics_N']==8192
            all_summaries.append(meta)
        assert sum(r['retained_strict_N'] for r in all_summaries)==len(records)
        hardware=collections.defaultdict(list)
        for file,r in records:
            for ch,adc in channel_adc(r).items():hardware[ch].append(adc)
        table('hardware_support.tsv',[dict(channel=ch,strict_denominator_N=len(records),valid_board_channel_N=len(values),
            sample_lengths=','.join(map(str,sorted({len(a) for a in values}))),zero_ADC_N=sum(v==0 for a in values for v in a),max_ADC_N=sum(v==16383 for a in values for v in a)) for ch,values in sorted(hardware.items())])
        control_meta=dict(files_N=32,physics_N=sum(r['physics_N'] for r in all_summaries),strict_N=sum(r['strict_N'] for r in all_summaries),
            cap_exceeded_files=[r['file'] for r in all_summaries if r['cap_exceeded']],
            logical_RAW_bytes_through=sum(r['logical_RAW_bytes_through'] for r in all_summaries),
            timestamp_min_us=min(r['timestamp_min_us'] for r in all_summaries),timestamp_max_us=max(r['timestamp_max_us'] for r in all_summaries),
            control_status_counts=dict(collections.Counter(str(r['status']) for f,r in records)),
            control_input_bits_counts=dict(collections.Counter(f"{r['tlb'][0]['input_bits']}/{r['tlb'][0]['input_bits_next']}" for f,r in records)),
            original_denominators_complete=not any(r['cap_exceeded'] for r in all_summaries),
            retained_controls_bytes=sum((CACHE/f"{'pilot' if f in p['pilot_files'] else 'full'}_{f}_controls.jsonl.gz").stat().st_size for f in range(400,432)))
        assert control_meta['retained_controls_bytes']<=p['limits']['final_event_bytes']
        write('independent_validation.json',proof);write('joint_summary.json',dict(passed=True,retained_strict_N=len(records),ratios=ratios,complete8=ranks,readout_counts=control_meta,
            unsupported_group_interpretation=['CaloNu20-23','clock31'],pure_noise_certified=False,charge_error_coverage_certified=False,MC_migration_certified=False,overall_complete=False))
        table('integrals.tsv',details);table('covariance.tsv',covariance)
        compact=[dict(window=r['window'],group=r['group'],**{k:v for k,v in r.items() if k not in ['window','group','first16','last16']},
            first16_N=r['first16']['N'],first16_ratio=r['first16']['ratio'],last16_N=r['last16']['N'],last16_ratio=r['last16']['ratio']) for r in ratios]
        table('variance_ratios.tsv',compact)
    write(f'{phase}_summary.json',result);print({k:v for k,v in result.items() if k!='files'},flush=True)
