"""Second actual prefix read and scalar calibration residual reconstruction."""
import math
from stage174_common import *
if __name__=='__main__':
    calibrations=json.loads((OUT/'calibrations.json').read_text());checks=[]
    for i in range(3):
        report=read(i,4,'audit')
        if not report['supported']:continue
        with np.load(CACHE/f'audit_{i}.npz') as a,np.load(CACHE/f'full_{i}.npz') as b:
            for k in a.files:np.testing.assert_array_equal(a[k],b[k][:4])
        checks.append(dict(source=i,actual_prefix=4,all_arrays_exact=True))
    errors=[]
    for c in calibrations:
        if 'coefficient' not in c:continue
        i=next(j for j,s in enumerate(plan()['sources']) if s['label']==c['label']);L,R=c['pair'];kind=c['kind']
        with np.load(CACHE/f'full_{i}.npz') as z:
            residual=[];entries=[];qs=z['rawQ_pC'];times=z['localtime_ns']
            for k in range(len(z['entry'])):
                if not z['control'][k] or z['entry'][k]%2!=1:continue
                if not z['strict'][k,L] or not z['strict'][k,R]:continue
                if not (math.isfinite(qs[k,L]) and math.isfinite(qs[k,R]) and qs[k,L]>0 and qs[k,R]>0):continue
                if kind=='difference':
                    target=float(times[k,L])-float(times[k,R]);D=[1,float(z['x_mm'][k])/100,1/math.sqrt(qs[k,L]),1/math.sqrt(qs[k,R])]
                else:
                    if not z['strict'][k,4] or not math.isfinite(qs[k,4]) or qs[k,4]<=0:continue
                    source=plan()['sources'][i]
                    factor=math.sqrt(1+math.tan(z['theta_x'][k])**2+math.tan(z['theta_y'][k])**2)-(1 if source['kind']=='MC' else 0)
                    target=(float(times[k,L])+float(times[k,R]))/2-float(times[k,4])-1598.9*factor/299.792458
                    D=[1,1/math.sqrt(qs[k,L]),1/math.sqrt(qs[k,R]),1/math.sqrt(qs[k,4])]
                residual.append(target-sum(float(a)*b for a,b in zip(c['coefficient'],D)));entries.append(k)
            assert len(residual)==c['validation_N']
            rms=math.sqrt(sum(e*e for e in residual)/len(residual));p95=float(np.quantile(np.abs(residual),.95))
            delta=max(abs(rms-c['validation_RMSE_ns']),abs(p95-c['validation_abs95_ns']));assert delta<1e-10
            errors.append(delta)
    write('independent_validation.json',dict(passed=True,actual_prefix_checks=checks,
        calibration_rows_scalar_checked=len(errors),max_metric_difference_ns=max(errors,default=0),
        no_nonzero_status_times_used=True,no_energy_fits=True,overall_complete=False))
