"""Bounded identity diagnostics before accepting any GENIE label association."""
import json
import re

import awkward as ak
import numpy as np
import uproot

from stage119_curve_common import OUT,table


def main():
    p=json.loads((OUT/'pythia_contract.json').read_text());rows=[]
    for i in [0,3,6,9,12,15]:
        s=p['sources'][i];r=json.loads((OUT/f'pythia_parent_{i}.json').read_text())['parents'][0]
        comp={'pi':'EPOSLHC_pi','k':'EPOSLHC_k','charm':'Powheg_pythia_charm_central'}[s['component']]
        path=f'/eos/experiment/fasernu-data0/MC/Genie_files/genie_output_Pythia6tunes/Pythia6_{s["environment"]}/{comp}/faser_filtered.gfaser.root'
        segment=int(re.search(r'-(\d{5})-master_dev-HITS.root',s['input']).group(1))
        with uproot.open(path,array_cache=None) as f:
            for proposal in sorted(set([r['eventID'],segment*1000])):
                a=ak.to_list(f['gFaser'].arrays(['vx','vy','vz','pdgc','status','firstMother','px','py','pz','E'],entry_start=proposal,entry_stop=proposal+1))[0]
                pid=np.asarray(a['pdgc']);status=np.asarray(a['status']);mother=np.asarray(a['firstMother']);nu=np.flatnonzero((abs(pid)==14)&(status==0))
                info=dict(index=i,run=s['run'],HITS_eventID=r['eventID'],segment=segment,proposed_entry=proposal,generator_input=path,nu_N=len(nu))
                if len(nu)==1:
                    ni=nu[0];incoming=np.array([pid[ni]]+[a[k][ni]*1000 for k in ['px','py','pz']]);vertex=np.array([a[k]*1000 for k in ['vx','vy','vz']])
                    mu=np.flatnonzero((pid==pid[ni]*13/14)&(mother==ni))
                    info.update(incoming_max_abs_MeV=float(np.max(abs(incoming-r['incoming']))),vertex_max_abs_mm=float(np.max(abs(vertex-r['vertex_mm']))),
                        HITS_incoming=r['incoming'],GENIE_incoming=incoming.tolist(),HITS_vertex_mm=r['vertex_mm'],GENIE_vertex_mm=vertex.tolist(),mu_N=len(mu),
                        y_delta=1-a['E'][mu[0]]/a['E'][ni]-r['y'] if len(mu)==1 and 'y' in r else None)
                rows.append(info)
            rows[-1]['source_requested_bytes']=int(f.file.source.num_requested_bytes)
    (OUT/'genie_identity_probe.json').write_text(json.dumps(rows,indent=2)+'\n');print(rows,flush=True)


if __name__=='__main__':main()
