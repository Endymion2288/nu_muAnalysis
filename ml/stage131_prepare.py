"""Matched reselected support with exact natural-parent labels and HT weights."""
import gzip
import json
import time
import numpy as np
from audited_features import configuration
from latent_transfer_diagnostics import check_x
from stage131_common import ROOT,OUT,CACHE,load,table,protocol

def labels(lineage,detectors):
    totals=[];fractions=[];available=[]
    clean=lineage['unknown_tracks']==0 and lineage['primary_muons']==1
    for window in ['all_MeV','prompt_MeV']:
        for match in detectors:
            keys=[k for k in lineage['deposits'] if match in k.lower() and not(match=='veto' and 'vetonu' in k.lower())]
            e=np.sum([lineage['deposits'][k][window] for k in keys],axis=0) if keys else np.zeros(3)
            assert e.shape==(3,) and np.isfinite(e).all() and (e>=0).all()
            total=float(e.sum());valid=clean and total>0 and e[2]==0
            totals.append(np.log1p(total/1000));fractions.append(float(e[0]/total) if valid else np.nan);available.append(int(valid))
    envelope=any(n in ['EmulsionStationA','Emulsion::EmulsionStationA'] for n in lineage['envelopes'])
    # Lead-block/outside-envelope interactions remain in the energy cohort with
    # a missing boundary oracle; a backscatter visiting the target is not an exit.
    flowvalid=envelope and lineage['outside_primaries']==0 and lineage['unknown_tracks']==0 and lineage['flow_KE_MeV'][3]==0
    available += [int(clean),int(flowvalid)]
    flow=np.log1p(lineage['flow_KE_MeV'][1]/1000) if flowvalid else np.nan
    return np.array(totals),np.array(fractions),np.array(available),flow

def main():
    tick=time.perf_counter();p=protocol()
    with gzip.open(CACHE/'production_cases.json.gz','rt') as f:cases=json.load(f)
    parts=[];migration=[];mechanism=[];closure=[];track_N=step_N=unknown_N=0
    for c in cases:
        i=c['frame_index'];s=json.loads((OUT/f'parent_{i}_summary.json').read_text());assert s['successful']
        chk=json.loads((OUT/f'parent_{i}_hitscheck.json').read_text());assert chk['passed'];closure.extend(dict(index=i,**r) for r in chk['rows'])
        track_N+=s['lineage']['tracks'];step_N+=s['lineage']['steps'];unknown_N+=s['lineage']['unknown_tracks']
        selection=json.loads((OUT/f'parent_{i}_selection.json').read_text());assert selection['identity_incoming_exact']
        d=load(CACHE/f'parent_{i}_selected.npz');n=len(d['x']);assert n==selection['selected_N']
        u,l,a,flow=labels(s['lineage'],p['detectors'])
        migration.append(dict(index=i,role=c['role'],stratum=c['stratum'],component=c['component'],selected=n,inclusion_probability=c['inclusion_probability'],weight=1/c['inclusion_probability'],unknown_tracks=s['lineage']['unknown_tracks'],primary_muons=s['lineage']['primary_muons'],crossings=s['lineage']['crossings'],nonmu_exit_KE_GeV=s['lineage']['flow_KE_MeV'][1]/1000))
        if not n:continue
        np.testing.assert_array_equal(d['incoming'][0].astype('float32'),np.array(c['incoming'],dtype='float32'))
        fields=['x','truth_E_GeV','y_lepton','primary_p_GeV','primary_valid','confirmed','vertex_z_mm','incoming','raw_charge','status','calo_status']
        part={k:d[k] for k in fields};part.update(pz=d['reco_pz_GeV'],role=np.array([c['role']]),source=np.array([c['source']]),component=np.array([c['component']]),sampling_stratum=np.array([c['stratum']]),weight=np.array([1/c['inclusion_probability']]),frame_index=np.array([i]),total=u[None,:],lineage=l[None,:],availability=a[None,:],flow=np.array([[flow]]))
        parts.append(part)
    data={k:np.concatenate([s[k] for s in parts]) for k in parts[0]};check_x(data['x'])
    assert len(np.unique(data['incoming'].astype('float32'),axis=0))==len(data['x'])
    assert set(data['role'])<=set([1,2,3]);assert np.all(data['pz']>50)
    for a in [1,2,3]:
        for b in [1,2,3]:
            if a<b:assert not set(map(tuple,data['incoming'][data['role']==a]))&set(map(tuple,data['incoming'][data['role']==b]))
    np.savez_compressed(CACHE/'matched_input.npz',**data)
    counts=[];coverage=[]
    for role in [1,2,3]:
        for layer in sorted(set(data['sampling_stratum'])):
            m=[r for r in migration if r['role']==role and r['stratum']==layer];active=[r for r in m if r['selected']]
            counts.append(dict(role=role,sampling_stratum=layer,simulated_N=len(m),reselected_N=len(active),conditional_reselection_fraction=len(active)/len(m),target_reselected_HT_count=sum(r['weight'] for r in active)))
        use=data['role']==role
        for j in range(10):
            v=data['lineage'][use,j];finite=np.isfinite(v);w=data['weight'][use]
            mechanism.append(dict(role=role,label=j,window='all' if j<5 else 'prompt0_1000ns',detector=p['detectors'][j%5],N=int(use.sum()),available_N=int(finite.sum()),all_mu_N=int((v==1).sum()),no_mu_N=int((v==0).sum()),weighted_mean_mu_fraction=float(np.average(v[finite],weights=w[finite])) if finite.any() else None))
            t=np.expm1(data['total'][use,j])
            coverage.append(dict(role=role,window='all' if j<5 else 'prompt0_1000ns',detector=p['detectors'][j%5],N=int(use.sum()),zero_deposit_N=int((t==0).sum()),positive_deposit_N=int((t>0).sum()),fraction_label_available_N=int(finite.sum()),weighted_mean_deposit_GeV=float(np.average(t,weights=w)),scope='fixed G4 globaltime window,not calibrated DAQ time; zero deposit is measured,undefined fractions remain NaN'))
    table('migration_summary.tsv',counts);table('lineage_summary.tsv',mechanism)
    table('deposit_coverage.tsv',coverage)
    # Per-parent payloads are retained only in ignored compressed evidence.
    with gzip.open(CACHE/'migration_evidence.json.gz','wt') as f:json.dump(migration,f,separators=(',',':'))
    with gzip.open(CACHE/'hits_closure_evidence.json.gz','wt') as f:json.dump(closure,f,separators=(',',':'))
    summary=dict(parents_N=len(cases),selected_N=len(data['x']),incoming_proxy_N=len(data['x']),new_independent_neutrino_interactions_N=0,measured_G4_tracks=track_N,measured_G4_steps=step_N,unknown_root_tracks=unknown_N,selected_boundary_oracle_available_N=int(data['availability'][:,-1].sum()),selected_unique_mu_root_available_N=int(data['availability'][:,-2].sum()),reserve_forward_N=0,closure_pairs=len(closure),max_abs_closure_MeV=max(r['abs_delta_MeV'] for r in closure),all_closure_passed=True,roles_disjoint=True,wall_s=time.perf_counter()-tick)
    (OUT/'matched_support.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary)

if __name__=='__main__':main()
