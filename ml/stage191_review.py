"""Batch-only original identity, scalar residual and measured-cost admission."""
import gzip
import json
import math
from fractions import Fraction
from pathlib import Path

import numpy as np
from audited_features import configuration, clean
from stage158_finalize import gnu
from stage191_summary import summarize

ROOT=Path.cwd();OUT=ROOT/'workbook/stage191_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage191'


def read(label):
    with gzip.open(CACHE/f'{label}.json.gz','rt') as f:return json.load(f)


def validate(data,d):
    checks=0
    for r in data['records']:
        c=r['case'];i=c['row']
        assert int(d['role'][i])==c['role']>0
        assert (int(d['run'][i]),int(d['eventID'][i]))==(c['run'],c['event'])
        assert d['pz'][i]==c['pz'] and c['reference']['pz0_GeV']==c['pz']
        np.testing.assert_array_equal(d['incoming'][i],np.asarray(c['incoming'],dtype='float32'))
        a=r['summary']['availability'];v=r['summary']['sigma'];content=r['summary']['content']
        assert len(a)==4 and len(v)==3 and len(content)==12
        for k in range(3):
            assert (v[k] is None)==(a[k+1]==0)
            assert all((x is None)==(a[k+1]==0) for x in content[4*k:4*k+4])
    byrow={r['case']['row']:r for r in data['records']}
    closures=[]
    for r in data['audit_records']:
        m=r['measurement'];assert not m['SDO_present']
        assert summarize(m,r['original_leading_match'])==byrow[r['case']['row']]['summary']
        if not m['start_supported']:continue
        lead=m['leading'];source=m['source']
        assert 0 not in lead['fitted_stations']
        cov=np.asarray(lead['stored_covariance']);sc=np.diag([1.,1.,1.,1.,1000.])
        np.testing.assert_allclose(np.asarray(source['ACTS_covariance'])[:5,:5],sc@cov@sc,rtol=3e-16,atol=0)
        tr=np.asarray(source['ACTS_transform'])
        np.testing.assert_allclose(tr,np.asarray(source['Trk_measurement_transform']),rtol=0,atol=1e-8)
        error=float(np.linalg.norm((tr@np.r_[source['local_mm'],0.,1.])[:3]-lead['position_mm']))
        assert error<=1e-6;closures.append(error)
        for w in m['wafers']:
            for c in w['candidates']:
                if c.get('pull') is None:continue
                assert float(Fraction(c['u_mm'])-Fraction(w['parameters'][0][0]))==c['residual_mm']
                assert float(Fraction(c['variance_mm2'])+Fraction(w['covariance'][0][0]))==c['innovation_variance_mm2']
                assert c['pull']==c['residual_mm']/math.sqrt(c['innovation_variance_mm2'])
                checks+=1
    return dict(passed=True,parents_N=len(byrow),raw_audit_N=len(data['audit_records']),scalar_checks_N=checks,max_position_closure_mm=max(closures,default=None))


if __name__=='__main__':
    p=json.loads((OUT/'protocol.json').read_text());data=read('pilot_0')
    with np.load(ROOT/'ntuples/energy_ml_stage119/old_input.npz') as z:d={k:z[k] for k in z.files if k!='metadata_json'}
    proof=validate(data,d)
    names=configuration()
    for j,name in enumerate(names['features']):
        active=d['role']>0
        np.testing.assert_array_equal(clean(d['x'][active,j],names['rules'][name]).astype('float32'),d['x'][active,j])
    records=data['records'];useful=[r for r in records if not r['first_source_event']]
    mean=sum(r['execute_CPU_s'] for r in useful)/len(useful);means={}
    for i in p['pilot']['source_indices']:
        q=[r['execute_CPU_s'] for r in useful if r['case']['source_index']==i]
        means[i]=max(mean,sum(q)/len(q)) if q else mean
    requests=json.loads((ROOT/p['input_manifest']).read_text())['requests']
    per_event=sum(sum(c['role']>0 for c in s['cases'])*means.get(s['index'],max(means.values())) for s in requests)
    cost=gnu(OUT/'pilot_time.txt');compile=gnu(OUT/'pilot_compile_time.txt')
    transition=max(r['execute_CPU_s'] for r in records if r['first_source_event'])
    projection=3*(35*(cost['CPU_s']+compile['CPU_s'])+per_event+35*transition)
    used=json.loads((OUT/'scheduler_accounting.json').read_text())['total_CPU_s']
    memory=8*1.25*cost['RSS_KiB']/1024
    support={str(i):sum(r['summary']['availability'][0]>0 and any(r['summary']['availability'][1:]) for r in records if r['case']['source_index']==i) for i in p['pilot']['source_indices']}
    admitted=all(support[str(i)]>0 for i in [0,48,113]) and projection<=48000 and used+1000+projection+8000<=60000 and memory<=24000
    proof.update(typed_X62_exact=True,original_roles_preserved=True,pilot_support=support)
    (OUT/'pilot_validation.json').write_text(json.dumps(proof,indent=2)+'\n')
    admission=dict(admitted=bool(admitted),projection_CPU_s=projection,production_cap_CPU_s=48000,used_CPU_s=used,
        per_event_projection_CPU_s=per_event,subsequent_mean_CPU_s=mean,source_mean_CPU_s=means,
        max_first_source_CPU_s=transition,pilot_GNU=cost,compile_GNU=compile,
        eight_reader_RSS_projection_MB=memory,peak_RSS_MB=cost['RSS_KiB']/1024,
        pz50_100_N=sum(50<=r['case']['pz']<100 for r in records),
        trueE50_100_N=int(sum(50<=d['truth_E_GeV'][r['case']['row']]<100 for r in records)),
        trueE100_200_N=int(sum(100<=d['truth_E_GeV'][r['case']['row']]<200 for r in records)),
        pilot_ROOT_read_bytes=json.loads((OUT/'pilot_0_summary.json').read_text())['ROOT_read_bytes'],
        limit='Conservative projection from measured source pilot; no controlled CPU/GPU speedup, calibrated coverage or energy success.',overall_complete=False)
    (OUT/'admission.json').write_text(json.dumps(admission,indent=2)+'\n')
    print('ADMISSION',admission,flush=True)
