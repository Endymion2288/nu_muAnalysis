"""Actual64 reread and independent scalar Gram-Schmidt; no repeated gzip decoding."""
import resource
resource.setrlimit(resource.RLIMIT_CPU,(240,240))
import collections
import math
import statistics
import time

from stage196_measure import CACHE,P,OUT,basis,read_gz,write


def scalar_projection(values,columns):
    dot=lambda x,y:math.fsum(a*b for a,b in zip(x,y))
    q=[]
    for column in columns:
        v=list(map(float,column))
        for _ in range(2):
            for u in q:
                c=dot(u,v);v=[x-c*y for x,y in zip(v,u)]
        norm=math.sqrt(dot(v,v));assert norm>0
        q.append([x/norm for x in v])
    r=list(map(float,values))
    for u in q:
        c=dot(u,values);r=[x-c*y for x,y in zip(r,u)]
    return r


if __name__=='__main__':
    started=time.perf_counter();cpu=time.process_time()
    raw=read_gz(CACHE/'full_raw.json.gz');reread=read_gz(CACHE/'audit_raw.json.gz')
    assert reread==raw and len(raw)==64
    assert raw[:4]==read_gz(CACHE/'pilot_raw.json.gz')
    full=read_gz(CACHE/'full_science.json.gz');pilot=read_gz(CACHE/'pilot_science.json.gz')
    prohibited=0;eligible=0;training=collections.defaultdict(list);data_patches={};data_noise={}
    for parent in raw:
        for w in parent['waves']:
            allowed=w['status']==0 and not w['secondary'] and w['detector']!='CaloNu'
            if not allowed:
                assert w['samples_mV'] is None and w['times_ns'] is None and w['localtime_ns'] is None
                prohibited+=1;continue
            eligible+=1
            a=w['samples_mV'];t=w['times_ns']
            if len(a)!=len(t) or len(a)<41 or any(x is None for x in a+t):continue
            if any(t[k]-t[k-1]!=2 for k in range(1,len(t))):continue
            peak=max(range(len(a)),key=lambda k:a[k]);amplitude=a[peak]
            if peak<8 or peak+32>=len(a) or amplitude<=0:continue
            label=w['detector']+':'+str(w['channel'])
            identity=(parent['PHYS_entry'],w['detector'],w['channel'])
            data_patches[identity]=a[peak-8:peak+33];data_noise[identity]=w['baseline_rms_mV']
            if parent['PHYS_entry']<32:training[label].append([v/amplitude for v in a[peak-8:peak+33]])
    template_checks=0
    for label,template in full['templates'].items():
        values=training[label];assert len(values)>=4
        expected=[statistics.median(row[j] for row in values) for j in range(41)]
        assert template==expected;template_checks+=41
    controls={}
    for index in range(400,432):
        phase='pilot' if index<402 else 'full'
        import gzip,json
        with gzip.open(f'ntuples/energy_ml_stage183/{phase}_{index}_controls.jsonl.gz','rt') as f:
            events=[json.loads(line) for line in f]
        for event in events:
            adc={16*b['board']+c['channel']:c['adc'] for b in event['boards'] for c in b['channels']}
            controls[index,event['eventID']]=adc
    assert len(controls)==116
    checked=collections.Counter();max_scaled=0.;noise_checks=0;row_checks=0
    data_rows={(r['PHYS_entry'],r['detector'],r['channel']):r for r in full['data_rows']}
    random_rows={(r['file'],r['eventID'],r['channel']):r for r in full['random_rows']}
    mc_rows={(r['index'],r['detector'],r['channel']):r for r in full['MC_rows']}
    mc_inputs={};mc_noise={}
    for index in P['MC_full']:
        source=read_gz(f'ntuples/energy_ml_stage179/parent_{index}_response.json.gz')
        for detector,record in source['records'].items():
            for wave in record['waves']:
                if int(wave['result'][0])!=0:continue
                original=[r[2] for r in source['analog'][detector]['total'] if int(r[0])==int(wave['id32'])]
                start,end=wave['result'][6:8]
                samples=[k for k in range(len(wave['adc'])) if start<=2*k<=end]
                observed=[wave['result'][3]-(2000/16384)*v for v in wave['adc']]
                peak=max(samples,key=lambda k:observed[k])
                if peak-8>=samples[0] and peak+32<=samples[-1]:
                    identity=(index,detector,int(wave['channel']))
                    mc_inputs[identity]=original[peak-8:peak+33];mc_noise[identity]=record['conditions'][1]
    for vector in full['vectors']:
        y=vector['values']
        b=vector.get('basis')
        if b is None:b=basis(full['templates'][vector['template_key']]).tolist()
        columns=list(zip(*b));reference=scalar_projection(y,columns)
        scale=max(1,max(abs(v) for v in y));delta=max(abs(a-c) for a,c in zip(reference,vector['residual']))
        assert delta<=1e-8*scale,(vector['identity'],delta,scale)
        max_scaled=max(max_scaled,delta/scale)
        norm_y=math.sqrt(math.fsum(v*v for v in y))
        for column in columns:
            value=math.fsum(a*c for a,c in zip(column,vector['residual']))
            limit=1e-8*math.sqrt(math.fsum(v*v for v in column))*norm_y+1e-12
            assert abs(value)<=limit
        if vector['kind']=='random_fixed_samples':
            file,event,label=vector['identity'];channel=int(label.split(':')[1]);a=controls[file,event][channel]
            mean=math.fsum(a[:40])/40
            expected=[(mean-v)*(2/16.384) for v in a[60:101]]
            assert y==expected
            assert vector['coefficients'] is None;noise_checks+=len(y)
            row=random_rows[tuple(vector['identity'])]
            noise=math.sqrt(math.fsum((v-mean)**2 for v in a[:40])/39)*(2/16.384)
            standardized_field='residual_over_baseline_RMS'
        elif vector['kind']=='data':
            assert y==data_patches[tuple(vector['identity'])]
            row=data_rows[tuple(vector['identity'])]
            noise=data_noise[tuple(vector['identity'])];standardized_field='residual_over_baseline_RMS'
        else:
            assert y==mc_inputs[tuple(vector['identity'])]
            row=mc_rows[tuple(vector['identity'])]
            noise=mc_noise[tuple(vector['identity'])];standardized_field='residual_over_MC_noise_RMS'
        rms=math.sqrt(math.fsum(v*v for v in reference)/len(reference))
        saved=row['residual_RMS_ADC'] if vector['kind']=='MC' else row['residual_RMS_mV']
        assert abs(rms-saved)<=1e-8*scale;row_checks+=1
        if noise is not None and noise>0:
            assert abs(saved/noise-row[standardized_field])<=1e-10*max(1,abs(saved/noise))
        else:assert row[standardized_field] is None
        checked[vector['kind']]+=1
    full_mc={tuple(r['identity']):r for r in full['vectors'] if r['kind']=='MC'}
    overlap=0
    for vector in pilot['vectors']:
        if vector['kind']!='MC':continue
        other=full_mc[tuple(vector['identity'])]
        for field in ['values','residual']:
            scale=max(1,max(abs(v) for v in vector[field]))
            assert max(abs(x-y) for x,y in zip(vector[field],other[field]))<=1e-8*scale
        overlap+=1
    assert [r['index'] for r in full['MC_parents']]==P['MC_full']
    summary=__import__('json').loads((OUT/'full_summary.json').read_text());group_checks=0
    for g in summary['groups']:
        if g['kind']=='data':items=[r for r in full['data_rows'] if r['detector']==g['group'] and r['subset']==g['subset']]
        elif g['kind']=='random':items=[r for r in full['random_rows'] if r['channel']==g['group'] and r['first16']==(g['subset']=='first16')]
        else:items=[r for r in full['MC_rows'] if r['detector']==g['group']]
        field='residual_over_MC_noise_RMS' if g['kind']=='MC' else 'residual_over_baseline_RMS'
        values=sorted(r[field] for r in items if r.get(field) is not None)
        assert len(items)==g['N'] and len(values)==g['residual_supported_N']
        if values:
            assert math.isclose(statistics.median(values),g['standardized_RMS_median'],rel_tol=1e-10,abs_tol=1e-10)
            position=(len(values)-1)*.95;k=int(position)
            q=values[k]+(values[min(k+1,len(values)-1)]-values[k])*(position-k)
            assert math.isclose(q,g['standardized_RMS_abs95'],rel_tol=1e-10,abs_tol=1e-10)
        group_checks+=1
    # Source and status support is checked by identity, not by selecting small residuals.
    write('independent_validation.json',dict(passed=True,actual_native_reread_N=64,raw_full_exact=True,pilot_prefix4_exact=True,
        prohibited_sample_time_records_verified_N=prohibited,original_eligible_records_N=eligible,
        template_scalar_medians_N=template_checks,scalar_projection_vectors=dict(checked),
        max_projection_scaled_difference=max_scaled,random_fixed_sample_scalar_checks_N=noise_checks,
        residual_rows_and_original_vector_checks_N=row_checks,
        independent_group_summary_checks_N=group_checks,
        MC_pilot_full_overlap_N=overlap,MC_all12_retained=True,
        physical_source_or_error_coverage_certified=False,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-started))
    print('Independent scalar projection and native64 reread passed',flush=True)
