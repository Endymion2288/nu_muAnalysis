"""Fixed full heldout tails without removal, refit or threshold/window scan."""
from stage175_common import *
def diagnostics():
    rows=[];cal=json.loads((ROOT/'workbook/stage174_energy_ml/calibrations.json').read_text())
    for index,label in enumerate(['data8006','MC100012','data15838']):
        with np.load(ROOT/f'ntuples/energy_ml_stage174/full_{index}.npz') as z:d={k:z[k] for k in z.files}
        q=d['rawQ_pC'];t=d['localtime_ns'];x=d['x_mm']
        for c in [r for r in cal if r['label']==label and 'coefficient' in r]:
            i,j=c['pair'];good=d['control']&d['strict'][:,i]&d['strict'][:,j]&(d['entry']%2==1)&np.isfinite(q[:,[i,j]]).all(1)&(q[:,[i,j]]>0).all(1)
            if c['kind']=='relative_mean':good &= d['strict'][:,4]&np.isfinite(q[:,4])&(q[:,4]>0)
            u=np.flatnonzero(good)
            if c['kind']=='difference':
                D=np.column_stack([np.ones(len(u)),x[u]/100,1/np.sqrt(q[u,i]),1/np.sqrt(q[u,j])]);target=t[u,i]-t[u,j]
            else:
                D=np.column_stack([np.ones(len(u)),1/np.sqrt(q[u,i]),1/np.sqrt(q[u,j]),1/np.sqrt(q[u,4])])
                factor=np.sqrt(1+np.tan(d['theta_x'][u])**2+np.tan(d['theta_y'][u])**2)-(1 if index==1 else 0)
                target=(t[u,i]+t[u,j])/2-t[u,4]-1598.9*factor/299.792458
            residual=target-D@np.asarray(c['coefficient']);assert len(u)==c['validation_N']
            tail=abs(residual)>2;support=np.ones(len(u),bool)
            for key,v in [('qL_pC',q[u,i]),('qR_pC',q[u,j]),('x_mm',x[u]),('y_mm',d['y_mm'][u])]+([('qRef_pC',q[u,4])] if c['kind']=='relative_mean' else []):
                lo,hi=c['training_ranges'][key];support &= (v>=lo)&(v<=hi)
            groups=[]
            for tag,ix in [('all',np.ones(len(u),bool)),('abs_gt_2ns',tail),('abs_le_2ns',~tail)]:
                idx=u[ix];tt=t[idx]
                groups.append(dict(group=tag,N=len(idx),inside_training_ranges_N=int((support&ix).sum()),
                    localtime_three_bins_per_end=[[int((tt[:,end]<100).sum()),int(((tt[:,end]>=100)&(tt[:,end]<300)).sum()),int((tt[:,end]>=300).sum())] for end in [i,j,4]],
                    phase_nonfinite_N=int((~np.isfinite(d['clockPhase'][idx])).sum()),
                    localtime_minmax_ns=[[float(tt[:,end].min()),float(tt[:,end].max())] if len(idx) else None for end in [i,j,4]],
                    max_abs_residual_ns=float(abs(residual[ix]).max()) if ix.any() else None))
            examples=[]
            for pos in np.flatnonzero(tail)[:8]:
                k=u[pos];examples.append(dict(entry=int(d['entry'][k]),run=int(d['run'][k]),event=int(d['event'][k]),residual_ns=float(residual[pos]),
                    localtime_ns=t[k,[i,j,4]].tolist(),rawQ_pC=q[k,[i,j,4]].tolist(),x_mm=float(x[k]),y_mm=float(d['y_mm'][k]),
                    phase=float(d['clockPhase'][k]) if np.isfinite(d['clockPhase'][k]) else None,
                    bcidtime_ns=d['bcidtime_ns'][k,[i,j,4]].tolist(),triggertime_ns=d['triggertime_ns'][k,[i,j,4]].tolist()))
            rows.append(dict(label=label,pair=[i,j],kind=c['kind'],groups=groups,first8_deterministic_examples=examples))
    write('muon_tail_diagnostics.json',dict(rows=rows,no_tail_removal=True,no_refit=True,threshold_ns=2,causes='Unresolved: status0 does not establish one prompt MIP. These time/range associations are descriptive, not causal attribution or a quality veto.',overall_complete=False))
