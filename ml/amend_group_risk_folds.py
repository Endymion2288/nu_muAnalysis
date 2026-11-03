import sys,json,shutil
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
sys.path.insert(0,str(Path.cwd()/'ml'))
from group_risk import inputs,OUT,save
p=json.loads((OUT/'protocol.json').read_text());assert not (OUT/'protocol_v1.json').exists()
shutil.copyfile(OUT/'protocol.json',OUT/'protocol_v1.json')
d=inputs();tr=d['role']=='train';groups=np.unique(d['group'][tr]);fold={};loads=np.zeros((3,3),int);total=np.zeros(3,int)
for ci,c in enumerate(['pi','k','charm']):
 gs=[str(g) for g in groups if str(g).startswith(c+':')]
 for g in sorted(gs,key=lambda g:(-int((tr&(d['group']==g)).sum()),g)):
  f=min(range(3),key=lambda f:(loads[ci,f],total[f],f));fold[g]=f;n=int((tr&(d['group']==g)).sum());loads[ci,f]+=n;total[f]+=n
ff=np.full(len(tr),-1);ff[tr]=[fold[str(g)] for g in d['group'][tr]]
counts=[]
for f in range(3):
 held=tr&(ff==f);candidate=tr&(ff!=f);identities=set(map(tuple,d['incoming'][held]));purged=np.array([candidate[i] and tuple(v) in identities for i,v in enumerate(d['incoming'])]);use=candidate&~purged
 assert not set(d['group'][use])&set(d['group'][held]);assert not set(map(tuple,d['incoming'][use]))&identities
 counts.append(dict(fold=f,held_N=int(held.sum()),held_groups=len(set(d['group'][held])),candidate_train_N=int(candidate.sum()),purged_train_N=int(purged.sum()),train_N=int(use.sum()),train_groups=len(set(d['group'][use])),train_components={c:int((use&(d['component']==c)).sum()) for c in ['pi','k','charm']},held_components={c:int((held&(d['component']==c)).sum()) for c in ['pi','k','charm']}))
p.update(protocol_version=2,amended_utc=datetime.now(timezone.utc).isoformat(),prior_protocol='protocol_v1.json',
 amendment='Before any formal fit: exact valid incoming reuse connects all conservative groups within each production component. Replace union folds (which held out entire components) with component-balanced conservative-group folds and purge only each fold training events sharing exact incoming with its held fold. All held/train-final/cal/eval events retained; no labels or held residuals used to choose folds.',
 folds='within each pi/k/charm sort conservative groups by decreasing N then name, greedily assign to minimum component event load, total event load, fold index; exclude training events sharing exact incoming(pdg,px,py,pz) with held fold',
 fold_by_group=fold,fold_event_N=total.tolist(),fold_identity_purge=True,fold_counts=counts)
save(OUT/'protocol.json',p)
save(OUT/'identity_fold_audit.json',dict(train_N=41447,unique_incoming=32046,finite_incoming_N=41447,zero_incoming_N=0,crossgroup_incoming_keys=6625,crossgroup_incoming_events=15918,union_components=3,union_component_interpretation='pi/k/charm, not three interchangeable source folds',exact_incoming_is_conservative_reuse_proxy_not_complete_generator_identity=True,fold_counts=counts))
print(json.dumps(counts,indent=2))
