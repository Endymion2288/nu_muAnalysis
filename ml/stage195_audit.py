"""Independent scalar audit on Condor, including actual full PHYS reread."""
import csv
import json
import math
import resource
import statistics
from pathlib import Path

import numpy as np

from stage195_measure import CACHE, OUT, OLD, P, controls, read_phys, write


def close(x, y):
    assert math.isclose(x, y, rel_tol=1e-10, abs_tol=1e-10), (x,y)


def quantile(values, q):
    a=sorted(values);pos=(len(a)-1)*q;k=int(pos)
    return a[k]+(a[min(k+1,len(a)-1)]-a[k])*(pos-k)


if __name__=='__main__':
    import time
    started=time.perf_counter();cpu=time.process_time()
    # Kernel enforcement avoids the scheduler's several-minute accounting delay.
    resource.setrlimit(resource.RLIMIT_CPU,(180,180))
    full=json.loads((OUT/'full_summary.json').read_text())
    data,perf=read_phys('audit')
    c=controls();checks=0;lipschitz=0
    for n,adc in enumerate(c['adc']):
        for k,channel in enumerate(adc):
            baseline=math.fsum(channel[:40])/40
            e=[baseline-x for x in channel]
            factor=float(c['factors'][k])
            close(math.fsum(e[60:140])*factor,c['signed'][n,k]);checks+=1
            close(math.fsum(max(x,0) for x in e[60:140])*factor,c['positive'][n,k]);checks+=1
            b=math.fsum(abs(x) for x in e)*factor
            close(b,c['l1'][n,k]);checks+=1
            # Algebra audit at fixed amplitudes from the same control; no fitted signal-template model.
            for s in [0,1,-1]:
                difference=math.fsum(max(s+x,0)-max(s,0) for x in e[60:140])*factor
                assert abs(difference)<=b+1e-10;lipschitz+=1
    scalar_modules=[]
    with (OUT/'full_bins.tsv').open() as f:bins=list(csv.DictReader(f,delimiter='\t'))
    with (OUT/'full_moments.tsv').open() as f:moments=list(csv.DictReader(f,delimiter='\t'))
    for j in range(4):
        with np.load(CACHE/f'full_module{j}.npz') as stored:
            a={key:stored[key] for key in stored.files}
        prefix=lambda gain,field:data[f'Calo{gain}{j}_{field}']
        selected=[];base=[];train_logs=[];pre_N=0;paired_N=0
        for i,values in enumerate(zip(*[prefix(g,f) for g,f in [('Lo','raw_charge'),('Hi','raw_charge'),
            ('Lo','raw_peak'),('Hi','raw_peak'),('Lo','baseline_rms'),('Hi','baseline_rms'),('Lo','status'),('Hi','status')]])):
            ql,qh,pl,ph,rl,rh,sl,sh=map(float,values)
            if sl==0 and sh==0:paired_N+=1
            pre=sl==0 and sh==0 and all(math.isfinite(x) for x in [ql,qh,pl,ph,rl,rh]) and min(ql,qh,rl,rh)>0
            if not pre:continue
            pre_N+=1;selected.append(i);isbase=pl>=10*rl and ph>=10*rh;base.append(isbase)
            if isbase and (i//8192)%2==0:train_logs.append(math.log(qh/ql))
        assert pre_N==full['support'][j]['preSNR_N'] and paired_N==full['support'][j]['paired_status0_N']
        assert sum(base)==OLD['support'][j]['positive_highSNR_overlap_N']
        assert selected==a['entry'].tolist() and base==a['base'].tolist()
        for key,gain,field in [('ql','Lo','raw_charge'),('qh','Hi','raw_charge'),('pl','Lo','raw_peak'),('ph','Hi','raw_peak'),('rl','Lo','baseline_rms'),('rh','Hi','baseline_rms')]:
            assert a[key].tolist()==prefix(gain,field)[selected].tolist()
        assert a['eventID'].tolist()==data['eventID'][selected].tolist()
        rho=math.exp(statistics.median(train_logs));close(rho,full['fits'][j]['rho'])
        b=float(c['bound'][j+4]+rho*c['bound'][j])
        module_checks=0
        for row in [r for r in bins if int(r['module'])==j]:
            values=[];ratios=[];exceed=0
            for k,i in enumerate(selected):
                if (i//8192)%2==0:continue
                group=row['group']
                if group!='preSNR' and not base[k]:continue
                dt=float(a['dt'][k])
                if group=='within2ns' and not (math.isfinite(dt) and abs(dt)<=2):continue
                if group=='outside2ns' and not (math.isfinite(dt) and abs(dt)>2):continue
                if not float(row['Lo_peak_lower_mV'])<=a['pl'][k]<float(row['Lo_peak_upper_mV']):continue
                r=float(a['qh'][k])-rho*float(a['ql'][k]);values.append(r)
                ratios.append(float(a['qh'][k])/(rho*float(a['ql'][k]))-1)
                exceed+=abs(r)>b
            assert len(values)==int(row['N']) and exceed==int(row['beyond_bound_N'])
            if values:
                close(statistics.median(values),float(row['median_difference_pC']))
                close(statistics.median(ratios),float(row['median_ratio_residual']))
                close(quantile([abs(x) for x in values],.95),float(row['abs95_difference_pC']))
                close(quantile([abs(x)/b for x in values],.95),float(row['required_bound_multiplier95']))
            module_checks+=1
        # Independent fixed pooled contrast, plus explicitly nonidentifiable latent construction.
        mid=[];high=[];identity_max=0
        for k,i in enumerate(selected):
            ql,qh=float(a['ql'][k]),float(a['qh'][k]);d=qh-rho*ql
            # A: a=QL, epsL=0, epsH=d. B: a=QH/rho, epsH=0, epsL=-d/rho.
            identity_max=max(identity_max,abs((rho*ql+d)-qh),abs((qh/rho-d/rho)-ql))
            if (i//8192)%2==1 and base[k] and abs(float(a['dt'][k]))<=2:
                if 100<=a['pl'][k]<250:mid.append(qh/(rho*ql)-1)
                if 500<=a['pl'][k]<2000:high.append(qh/(rho*ql)-1)
        co=full['contrasts'][j];assert len(mid)==co['mid_N'] and len(high)==co['high_N']
        close(statistics.median(high)-statistics.median(mid),co['contrast_ratio'])
        assert identity_max<1e-8
        expected=full['free_scale_constraints'][j]
        for expected_group in expected['groups']:
            intervals=[]
            for k,i in enumerate(selected):
                if (i//8192)%2==0 or not base[k] or not abs(float(a['dt'][k]))<=2:continue
                lo,hi=(100,250) if expected_group['group']=='mid' else (500,2000)
                if not lo<=a['pl'][k]<hi:continue
                ql,qh=float(a['ql'][k]),float(a['qh'][k]);bl,bh=float(c['bound'][j]),float(c['bound'][j+4])
                intervals.append((max(0,qh-bh)/(ql+bl),(qh+bh)/(ql-bl) if ql>bl else math.inf))
            n=len(intervals);need=math.ceil(.95*n)
            assert n==expected_group['N'] and need==expected_group['required_covered_N']
            close(sorted(x for x,y in intervals)[need-1],expected_group['necessary_rho_lower'])
            u=sorted(y for x,y in intervals)[n-need]
            if math.isfinite(u):close(u,expected_group['necessary_rho_upper'])
            else:assert expected_group['upper_unbounded']
        def scalar_cov(x,y):
            mx=math.fsum(x)/len(x);my=math.fsum(y)/len(y)
            return math.fsum((u-mx)*(v-my) for u,v in zip(x,y))/(len(x)-1)
        moment_checks=0
        for row in [r for r in moments if int(r['module'])==j]:
            coords=[];differences=[]
            for k,i in enumerate(selected):
                if (i//8192)%2==0 or not base[k]:continue
                if row['group']=='within2ns' and not abs(float(a['dt'][k]))<=2:continue
                ql,qh=float(a['ql'][k]),float(a['qh'][k])
                coords.append(ql if row['axis']=='Lo' else qh/rho);differences.append(qh-rho*ql)
            assert len(coords)==int(row['N'])
            cv=scalar_cov(differences,coords);var=scalar_cov(coords,coords)
            close(cv,float(row['difference_covariance_pC2']));close(cv/var,float(row['difference_slope']))
            for label,array in [('signed_window',c['signed']),('rectified_zero_signal',c['positive'])]:
                ns=[float(u[j+4])-rho*float(u[j]) for u in array]
                nx=[float(u[j]) if row['axis']=='Lo' else float(u[j+4])/rho for u in array]
                nv=scalar_cov(ns,nx)
                close(nv,float(row[label+'_covariance_pC2']));close(nv/var,float(row[label+'_conditional_slope']))
            moment_checks+=1
        scalar_modules.append(dict(module=j,preSNR_N=pre_N,fit_N=len(train_logs),scalar_bins_N=module_checks,
            scalar_moments_N=moment_checks,cache_identity_exact=True,independent_contrast_exact=True,
            latent_linear_constructions_max_roundoff_pC=identity_max))
    write('independent_validation.json',dict(passed=True,actual_full_PHYS_N=perf['N'],prefix8192_exact=True,
        scalar_random_integrals_N=checks,rectifier_Lipschitz_checks_N=lipschitz,scalar_modules=scalar_modules,
        controls_N=116,arbitrary_errors_allow_exact_linear_constructions=True,
        error_independence_or_distribution_certified=False,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-started))
    print('Independent scalar and full ROOT reread audit passed',flush=True)
