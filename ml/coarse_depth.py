"""Stage45 reco-only inputs, fixed physical depth labels and source OOF roles."""
import json
from pathlib import Path
import numpy as np

REPO=Path(__file__).resolve().parents[1]
REGIONS=[[-3000,-2928],[-2812,-2600],[-2600,-2300],[-2300,-1950],[-1769.65,-1619.65]]


def load_inputs():
    with np.load(REPO/'ntuples/energy_ml_stage42/development.npz') as z:
        rows=np.flatnonzero(z['selected']); d={k:z[k][rows] for k in z.files}
    with np.load(REPO/'ntuples/energy_ml_stage44/features.npz') as z:
        np.testing.assert_array_equal(z['cache_row'],rows)
        for k in ['run','eventID']:np.testing.assert_array_equal(z[k],d[k])
        x=np.column_stack([d['x'],z['local']]).astype('float32')
    assert x.shape==(3703,87)
    x[~np.isfinite(x)]=np.nan
    return rows,d,x


def region_labels(z,regions=REGIONS):
    mask=np.column_stack([(z>=lo)&(z<hi) for lo,hi in regions])
    # The original selected support is entirely covered. Fail rather than silently remove an event.
    assert (mask.sum(axis=1)==1).all()
    return mask.argmax(axis=1)


def inner_roles(groups,train):
    mapping={str(g):i%2 for i,g in enumerate(np.sort(np.unique(groups[train])))}
    return np.array([mapping.get(str(g),-1) for g in groups]),mapping


def smoothed_prior(labels,nclasses,alpha):
    return (np.bincount(labels,minlength=nclasses)+alpha)/(len(labels)+nclasses*alpha)


def audit():
    from train_bdt import write_table
    rows,d,x=load_inputs();lab=region_labels(d['vertex_z_mm']);records=[];mapping={}
    for f in range(3):
        tr=d['fold']==(f+1)%3;inner,mp=inner_roles(d['group'],tr);mapping[str(f)]=mp
        for role,select in [('train',tr),('cal',d['fold']==(f+2)%3),('eval',d['fold']==f)]:
            subsets=[('all',select)]+([(f'inner{k}',select&(inner==k)) for k in range(2)] if role=='train' else [])
            for sub,m in subsets:
                records.append(dict(outer_fold=f,role=role,subset=sub,N=int(m.sum()),sources=len(np.unique(d['group'][m])),region_N=np.bincount(lab[m],minlength=5).tolist(),component_N={c:int((m&(d['component']==c)).sum()) for c in ['pi','k','charm']}))
    out=REPO/'workbook/stage45_energy_ml';out.mkdir(exist_ok=True)
    write_table(out/'region_support.tsv',records)
    summary=dict(events=len(rows),sources=len(np.unique(d['group'])),feature_columns=x.shape[1],focus_events=int(((d['reco_p_GeV']>=100)&(d['reco_p_GeV']<1000)).sum()),
                 regions_mm=REGIONS,region_N=np.bincount(lab,minlength=5).tolist(),unknown_z_N=int((~np.isfinite(d['vertex_z_mm'])).sum()),outside_defined_regions_N=0,
                 component_sources={c:len(np.unique(d['group'][d['component']==c])) for c in ['pi','k','charm']},inner_group_mapping=mapping,nu_fits_run=False)
    (out/'input_audit.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary));print(json.dumps(records))


if __name__=='__main__':audit()
