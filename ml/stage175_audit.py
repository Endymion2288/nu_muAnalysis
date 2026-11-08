"""Actual independent selected-entry re-read and scalar mean/support verification."""
import csv,math
from stage175_common import *
if __name__=='__main__':
    checks=[];errors=[]
    with np.load(CACHE/'cohort.npz') as z:d={k:z[k] for k in z.files}
    for i in plan()['pilot_indices']:
        read((i,'audit'))
        with np.load(CACHE/f'audit_{i}.npz') as z:
            pos=z['row']
            for k in z.files:np.testing.assert_array_equal(z[k],d[k][pos])
        checks.append(dict(source=i,actual_selected_entries=1,all_fields_exact=True))
    f,v=means(d);np.testing.assert_array_equal(f,d['flags']);np.testing.assert_array_equal(v,d['relative_mean_ns'])
    records=json.loads((ROOT/'workbook/stage174_energy_ml/calibrations.json').read_text())
    for col,(i,j) in enumerate([(0,1),(2,3)]):
        c=next(r for r in records if r['label']=='MC100012' and r['pair']==[i,j] and r['kind']=='relative_mean')
        for k in np.flatnonzero(np.isfinite(v[:,col])):
            assert all(d['status'][k,e]==0 and math.isfinite(d['localtime_ns'][k,e]) and d['localtime_ns'][k,e]>0 for e in [i,j,4])
            q=d['rawQ_pC'][k];t=d['localtime_ns'][k];track=d['track'][k]
            path=1598.9*(math.sqrt(1+math.tan(track[3])**2+math.tan(track[4])**2)-1)/299.792458
            value=(t[i]+t[j])/2-t[4]-path-sum(a*b for a,b in zip(c['coefficient'],[1,1/math.sqrt(q[i]),1/math.sqrt(q[j]),1/math.sqrt(q[4])]))
            error=abs(value-v[k,col]);assert error<1e-10;errors.append(error)
    rows=list(csv.DictReader((OUT/'timing_support.tsv').open(),delimiter='\t'))
    for r in [r for r in rows if r['stratum']=='all']:
        ix=np.ones(len(v),bool) if r['role']=='-1' else d['role']==int(r['role'])
        assert int(r['N'])==int(ix.sum())
        assert int(r['pair01_calibrated'])==int(np.isfinite(v[ix,0]).sum()) and int(r['pair23_calibrated'])==int(np.isfinite(v[ix,1]).sum())
    write('independent_validation.json',dict(passed=True,actual_source_checks=checks,scalar_calibrated_values_N=len(errors),max_scalar_difference_ns=max(errors,default=0),
        full_derived_and_missingness_exact=True,all_role_counts_independent=True,no_nonzero_status_times=True,energy_fits=0,overall_complete=False))
