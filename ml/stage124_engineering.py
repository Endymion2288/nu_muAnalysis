"""Bounded secondary-safe channel semantics; no model forward or cut change."""
import csv,gzip,json,math,struct,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage124_energy_ml';OLD=ROOT/'ntuples/energy_ml_stage122'
def f32(x):return struct.unpack('f',struct.pack('f',x))[0]
def read(name):
 with gzip.open(OLD/name,'rt') as f:return json.load(f)
def reduced(rec,channels,by_channel):
 def mean(det,chs):
  v=[h[5] for h in rec[det] if int(h[2])==0 and int(h[1]) in chs];t=f32(0)
  for x in v:t=f32(t+f32(x))
  return f32(t/len(v)) if v else float('nan')
 vt=mean('Veto',channels);pt=mean('Preshower',[int(h[1]) for h in rec['Preshower'] if not int(h[2])&2]);limit=float(f32(vt-27.21 if math.isfinite(vt) else pt-51.41))+35
 result=[f32(0),f32(0)];primary={};ambiguous=[]
 for h in rec['VetoNu']:
  if int(h[2])&2:continue
  ch=int(h[1])
  if ch in primary:ambiguous.append(ch)
  primary[ch]=h
 if not math.isfinite(vt) and not math.isfinite(pt):return [f32(primary[ch][3]) if ch in primary else f32(0) for ch in [4,5]],ambiguous
 for j,h in enumerate(rec['VetoNu']):
  if by_channel:
   if int(h[2])&2 or int(h[1]) not in [4,5]:continue
   j=[4,5].index(int(h[1]))
  elif j>=2:continue
  n=int(h[6]);total=f32(0)
  for t,v in zip(h[7:7+n],h[7+n:]):
   if t>=limit:break
   total=f32(total+f32(v))
  result[j]=f32(total*f32(2/50))
 return result,ambiguous

def main():
 tick=time.perf_counter();cases=[(5,4386),(6,7875),(7,8429)];rows=[]
 for index,entry in cases:
  source=read(f'replicas_{index}.json.gz');mapping=read(f'referencemap_{index}.json.gz');chs=[v[0] for v in mapping['events'][0]['veto_cable_map'] if v[2]==1]
  event=next(r for r in source['events'] if r['entry']==entry)
  containers=[('original',event['original_reconstructed'])]
  for det in ['VetoNu','Preshower']:
   rr=event['detectors'][det]['replicas'];assert rr[0]==rr[1]
  for rep in range(16):
   rec={'Veto':event['original_reconstructed']['Veto']}
   for det in ['VetoNu','Preshower']:
    rec[det]=next(v for v in event['detectors'][det]['replicas'] if v['replica']==rep)['reconstructed']
   containers.append((f'replica{rep}',rec))
  for name,rec in containers:
   old,_=reduced(rec,chs,False);new,ambiguous=reduced(rec,chs,True)
   assert not ambiguous,(index,entry,ambiguous)
   extra=sum(bool(int(h[2])&2) for h in rec['VetoNu'])
   rows.append(dict(index=index,entry=entry,view=name,secondary_hits=extra,old_safe0_pC=old[0],old_safe1_pC=old[1],channel_primary0_pC=new[0],channel_primary1_pC=new[1],max_abs_difference_pC=max(abs(a-b) for a,b in zip(old,new)),full_container_N=len(rec['VetoNu']),native_UB_not_emulated=True))
 with (OUT/'secondary_safe_closure.tsv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(rows)
 summary=dict(fixed_parents=3,views=len(rows),secondary_views=sum(r['secondary_hits']>0 for r in rows),max_abs_difference_pC=max(r['max_abs_difference_pC'] for r in rows),all_primary_channel_semantics_equal_first_two_safe_semantics=all(r['max_abs_difference_pC']==0 for r in rows),preserve_all_hits_and_views=True,official_producer_UB_certified=False,production_cut_changed=False,model_fits=0,model_forwards=0,wall_s=time.perf_counter()-tick,scope='safe channel-keyed primary integration closes to defined first-two-primary diagnostic; does not reconstruct undefined native out-of-bounds behavior')
 (OUT/'engineering_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary,flush=True)
if __name__=='__main__':main()
