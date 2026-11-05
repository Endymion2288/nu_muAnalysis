"""Quantify actual HITS ancestry coverage and GENIE W/FSI composition."""
import csv
import json
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage119_energy_ml'


def table(name,rows):
    with (OUT/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t');w.writeheader();w.writerows(rows)


def quantiles(values):
    values=np.asarray(values);values=values[np.isfinite(values)]
    return dict(N=len(values),q00=float(values.min()) if len(values) else None,
                q25=float(np.quantile(values,.25)) if len(values) else None,
                q50=float(np.median(values)) if len(values) else None,
                q75=float(np.quantile(values,.75)) if len(values) else None,
                q100=float(values.max()) if len(values) else None)


def hits():
    summaries=[];datasets={}
    for run in [200184,200110,200113,200300,200303]:
        p=json.loads((OUT/f'hits_{run}_hits.json').read_text());rows=p['events'];datasets[run]=rows
        for detector in ['VetoNuHits','VetoHits','TriggerHits','PreshowerHits']:
            for selection in ['all_parent','fiducial_numu']:
                use=rows if selection=='all_parent' else [r for r in rows if fiducial(r)]
                d=[r['detectors'][detector] for r in use];e=np.array([r['E_MeV'] for r in d])
                unknown=np.array([r['unknown_family_MeV'] for r in d]);known=np.array([r['known_nonmu_MeV'] for r in d]);mu=np.array([r['mu_family_MeV'] for r in d]);neutron=np.array([r['neutron_ancestor_MeV'] for r in d])
                assert np.allclose(unknown+known+mu,e,rtol=1e-8)
                nz=e>0;fully_known=nz & (unknown==0)
                means=np.array([r['time_E_ns_MeV']/r['E_MeV']-v.get('vertex_time_ns',np.nan) if r['E_MeV']>0 else np.nan for v,r in zip(use,d)])
                summaries.append(dict(run=run,detector=detector,selection=selection,parent_N=len(use),
                    nonzero_N=int(nz.sum()),zero_N=int((~nz).sum()),hits=sum(v['hits'] for v in d),
                    linked_hits=sum(v['linked_hits'] for v in d),E_MeV=float(e.sum()),
                    known_nonmu_MeV=float(known.sum()),mu_family_MeV=float(mu.sum()),unknown_family_MeV=float(unknown.sum()),
                    neutron_ancestor_MeV=float(neutron.sum()),neutron_unknown_MeV=sum(v['neutron_unknown_MeV'] for v in d),
                    fully_known_nonzero_N=int(fully_known.sum()),
                    nonmu_fraction_known_q50=float(np.median(known[fully_known]/e[fully_known])) if fully_known.any() else None,
                    nonmu_fraction_lower_q50=float(np.median(known[nz]/e[nz])) if nz.any() else None,
                    nonmu_fraction_upper_q50=float(np.median((known[nz]+unknown[nz])/e[nz])) if nz.any() else None,
                    deposition_Eweighted_delay_ns_q50=quantiles(means)['q50']))
    table('hits_coverage.tsv',summaries)
    # A transport pair requires the documented same EVNT and entry plus actual
    # input checks. This does not establish identical G4 stochastic seeds.
    left,right=datasets[200110],datasets[200113];pairs=[]
    by={r['eventID']:r for r in right}
    for l in left:
        r=by.get(l['eventID'])
        if r is None or 'incoming' not in l or 'incoming' not in r:continue
        if l['incoming']!=r['incoming'] or l.get('vertex_mm')!=r.get('vertex_mm') or l.get('y')!=r.get('y'):continue
        pairs.append((l,r))
    paired=[];rng=np.random.default_rng(2026110519)
    for selection in ['all_parent','fiducial_numu']:
        use=pairs if selection=='all_parent' else [(l,r) for l,r in pairs if fiducial(l) and fiducial(r)]
        for detector in ['VetoNuHits','VetoHits','TriggerHits','PreshowerHits']:
            a=np.array([l['detectors'][detector]['E_MeV'] for l,r in use]);b=np.array([r['detectors'][detector]['E_MeV'] for l,r in use]);delta=b-a
            draws=np.array([delta[rng.integers(0,len(delta),len(delta))].mean() for _ in range(500)]) if len(delta) else np.array([])
            paired.append(dict(selection=selection,detector=detector,matched_parent_N=len(use),JEFF_mean_MeV=float(a.mean()) if len(a) else None,
                ENDF_mean_MeV=float(b.mean()) if len(b) else None,ENDF_minus_JEFF_mean_MeV=float(delta.mean()) if len(delta) else None,
                delta_lower95_MeV=float(np.quantile(draws,.025)) if len(draws) else None,
                delta_upper95_MeV=float(np.quantile(draws,.975)) if len(draws) else None,
                nonzero_migration_JEFF_only=int(((a>0)&(b==0)).sum()),nonzero_migration_ENDF_only=int(((a==0)&(b>0)).sum())))
    table('hits_transport.tsv',paired)
    return dict(matched_transport_parents=len(pairs),matching='same documented EVNT, skip0, eventID, exact incoming, vertex, primary y; full GENIE record hash/transport seed not certified',
                interval_scope='fixed first-source 1000 parents; row bootstrap, not flux/population/systematic uncertainty; reused incoming not independent new families',
                fraction='[known_nonmu/E,(known_nonmu+unknown)/E]; no classification of absent ancestry',
                physical_claim='sensitive deposition comparison only; no charge/time readout or energy-model conclusion')


def fiducial(r):
    if abs(r.get('incoming',[0])[0])!=14 or 'vertex_mm' not in r:return False
    x,y,z=r['vertex_mm'];box=(-115<x<135 and -171<y<129 and -3000<z<-1950);lead=(-300<x<300 and -300<y<300 and -1769.65<z<-1619.65)
    return (box or lead) and np.hypot(x,y)<100 and r['incoming'][3]>50000


def genie():
    tables=[];schemas=json.loads((OUT/'genie_schema.json').read_text());cost=[]
    for source in schemas:
        if 'gFaser' not in source['trees']:continue
        path=source['input'];tune='Standard' if 'Pythia6_Standard' in path else 'NUX'
        with uproot.open(path,array_cache=None) as f:
            a=f['gFaser'].arrays(library='ak');cost.append(dict(input=path,requested_bytes=int(f.file.source.num_requested_bytes)))
        result=[]
        for row in ak.to_list(a):
            n=int(row['n']);pdg=np.asarray(row['pdgc'][:n]);status=np.asarray(row['status'][:n]);mother=np.asarray(row['firstMother'][:n]);energy=np.asarray(row['E'][:n]);mom=np.column_stack([row[k][:n] for k in ['px','py','pz']])
            nu=np.flatnonzero((np.abs(pdg)==14)&(status==0))
            if len(nu)!=1:continue
            ni=nu[0];mu=np.flatnonzero((pdg==pdg[ni]*13/14)&(mother==ni))
            if len(mu)!=1:continue
            mi=mu[0];target=np.flatnonzero((status==11)&np.isin(np.abs(pdg),[2112,2212]))
            qE=energy[ni]-energy[mi];qP=mom[ni]-mom[mi];Q2=float(qP@qP-qE*qE)
            W=np.nan
            if len(target)==1:
                ti=target[0];hadP=mom[ti]+qP;W2=(energy[ti]+qE)**2-hadP@hadP
                if W2>=0:W=float(np.sqrt(W2))
            nucleus=pdg[(status==0)&(pdg>1000000000)]
            d=dict(E=float(energy[ni]),y=float(qE/energy[ni]),W=W,Q2=Q2,z_mm=float(row['vz'])*1000,nucleus=int(nucleus[0]) if len(nucleus)==1 else 0)
            for stage,code in [('preFSI',14),('postFSI',1)]:
                mask=status==code;mask[mi]=False
                d[stage+'_neutron_N']=int((mask&(pdg==2112)).sum())
                d[stage+'_pi0_N']=int((mask&(pdg==111)).sum())
                d[stage+'_charged_hadron_N']=int((mask&np.isin(np.abs(pdg),[211,321,2212])).sum())
            result.append(d)
        for low,high in [(50,100),(100,200),(200,float('inf'))]:
            use=[r for r in result if low<=r['E']<high];w=np.array([r['W'] for r in use]);finite=np.isfinite(w)
            tables.append(dict(tune=tune,E_low_GeV=low,E_high_GeV=high,N=len(use),W_known_N=int(finite.sum()),
                W_lt2p3_N=int((w<2.3).sum()),W_2p3_3_N=int(((w>=2.3)&(w<3)).sum()),W_ge3_N=int((w>=3).sum()),
                W_median_GeV=float(np.median(w[finite])) if finite.any() else None,
                Q2_median_GeV2=float(np.median([r['Q2'] for r in use])) if use else None,
                y_median=float(np.median([r['y'] for r in use])) if use else None,
                preFSI_neutron_mean=float(np.mean([r['preFSI_neutron_N'] for r in use])) if use else None,
                postFSI_neutron_mean=float(np.mean([r['postFSI_neutron_N'] for r in use])) if use else None,
                preFSI_pi0_mean=float(np.mean([r['preFSI_pi0_N'] for r in use])) if use else None,
                postFSI_pi0_mean=float(np.mean([r['postFSI_pi0_N'] for r in use])) if use else None,
                nuclei=','.join(map(str,sorted({r['nucleus'] for r in use})))))
    table('genie_W_FSI.tsv',tables)
    return dict(cost=cost,scope='one unfiltered generator subjob per tune, not selected PHYS; no claim matching old model failures',
                W='(struck nucleon status11 + neutrino - primary charged muon)^2; primary mother is neutrino; GeV/c2',
                Q2='-(neutrino-primary charged muon)^2; GeV2',
                channel='not certified in gFaser; requires actual GHEP interaction summary',
                FSI='GENIE status14 versus status1 composition, no invented per-particle correspondence')


def main():
    result=dict(hits=hits(),genie=genie(),new_fits=0,new_forwards=0)
    (OUT/'mechanism.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)


if __name__=='__main__':main()
