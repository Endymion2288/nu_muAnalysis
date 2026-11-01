#!/usr/bin/env python3
"""Export genuine fitted covariance with the fixed official merge collection."""
import argparse,json,runpy,shutil,sys,time,resource,math
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--request',type=Path,required=True);p.add_argument('--event',type=int,required=True);p.add_argument('--xaod',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 request=json.loads(a.request.read_text());old=next(e for e in request['events'] if e['eventID']==a.event);tick=time.perf_counter();cpu=time.process_time();records=[]
 from AthenaPython import PyAthena
 from AthenaConfiguration.ComponentAccumulator import ComponentAccumulator
 class Inspect(PyAthena.Alg):
  def execute(self):
   import ROOT
   ROOT.gInterpreter.AddIncludePath(str(Path(__file__).resolve().parents[1]/'AnalysisZipFramework/include'))
   assert ROOT.gInterpreter.Declare('#include "ReferenceCovarianceAudit.h"\n#include "TrackingTruthDiagnostic.h"')
   store=PyAthena.py_svc('StoreGateSvc');det=PyAthena.py_svc('DetectorStore')
   helper=det.retrieve('FaserSCT_ID','FaserSCT_ID');tracks=store.retrieve('TrackCollection','CKFTrackCollectionMergeWithoutIFT')
   rows=[list(row) for row in ROOT.AuditReferenceCovariances(tracks,helper)];assert rows
   row=max(rows,key=lambda r:r[5]);front=row[:6];p0=math.sqrt(sum(v*v for v in front[3:]))/1000
   # Native state is double; PHYS state vector components can be float.
   assert math.isclose(p0,old['reco_p_GeV'],rel_tol=2e-7,abs_tol=1e-7),(a.event,p0,old['reco_p_GeV'])
   assert all(abs(front[i]-old['reco_front'][i])<.002 for i in range(3)),(a.event,front,old['reco_front'])
   assert all(math.isclose(front[i],old['reco_front'][i],rel_tol=2e-7,abs_tol=.01) for i in range(3,6))
   assert row[6]==old['reco_charge'];assert math.isclose(row[14],row[6]/(p0*1000),rel_tol=2e-7)
   # Match the selected long track to the raw collection by its exact front pz.
   track=next(t for t in tracks if t and float(t.trackParameters().front().momentum().z())==front[5])
   match=list(ROOT.DiagnosticTrackTruth(track,store.retrieve('TrackerSimDataCollection','SCT_SDO_Map'),store.retrieve('xAOD::TruthParticleContainer','TruthParticles')))
   confirmed=bool(match and int(match[0])==int(old['primary_barcode']) and int(match[1])==int(old['primary_pdg']))
   info=store.retrieve('xAOD::EventInfo','EventInfo');assert int(info.eventNumber())==old['eventID'] and int(info.runNumber())==old['run']
   cov=row[15:40];sigma=1000*math.sqrt(cov[24]) if cov[24]>0 else None
   records.append(dict(run=old['run'],eventID=old['eventID'],group=old['group'],front=front,charge=row[6],track_fitter=int(row[7]),chi2=row[8],ndof=row[9],parameters=row[10:15],covariance=cov,surface_center_mm=row[40:43],surface_normal=row[43:46],sigma_kappa_GeVinv=sigma,kappa_GeVinv=1000*row[14],truth_match=match,primary_barcode_pdg_confirmed=confirmed,original_front_reproduced=True))
   return PyAthena.StatusCode.Success
 original=ComponentAccumulator.run
 def run(acc,*args,**kwargs):acc.addEventAlgo(Inspect('AuditReferenceCovariance'));return original(acc,*args,**kwargs)
 ComponentAccumulator.run=run;maker=shutil.which('faser_ntuple_maker.py');sys.argv=[maker,'--isMC','--geom','TI12MC04','--CKFTrackType','merge','--nevents','1','--outfile','audit-ntuple.root',a.xaod]
 # The maker exits via sys.exit even on success.
 try:runpy.run_path(maker,run_name='__main__')
 except SystemExit as e:
  if e.code not in [None,0]:raise
 assert len(records)==1
 result=dict(events=records,wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
 a.output.write_text(json.dumps(result,separators=(',',':'))+'\n')

if __name__=='__main__':main()
