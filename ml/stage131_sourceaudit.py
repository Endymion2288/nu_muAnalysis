"""Bounded exact-commit interface inspection, without event or metadata scanning."""
import json
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage131_energy_ml'
COMMIT='d32b0ff3cc4a2dad4abfb1474a82422c3c25b305'
paths={
 'Scintillator/ScintSimEvent/ScintSimEvent/ScintHit.h':['particleLink','m_partLink','m_energyLoss'],
 'Calorimeter/FaserCaloSimEvent/FaserCaloSimEvent/CaloHit.h':['particleLink','m_partLink'],
 'Tracker/TrackerSimEvent/TrackerSimEvent/FaserSiHit.h':['particleLink','m_partLink'],
 'Scintillator/ScintG4/VetoG4_SD/src/VetoSensorSD.cxx':['GetTotalEnergyDeposit','FaserTrackHelper','GetParticleLink'],
 'Calorimeter/CaloG4/EcalG4_SD/src/EcalSensorSD.cxx':['GetTotalEnergyDeposit','birkCorrection','localNonUniformity','ecorrected','Emplace'],
 'Calorimeter/CaloEventCnv/FaserCaloSimEventTPCnv/src/CaloHits/CaloHitCollectionCnv_p1a.cxx':['m_persEneUnit','transSumE','persSumE'],
 'Scintillator/ScintEventCnv/ScintSimEventTPCnv/src/ScintHits/ScintHitCollectionCnv_p1a.cxx':['m_persEneUnit','transSumE','persSumE'],
 'Tracker/TrackerEventCnv/TrackerSimEventTPCnv/src/TrackerHits/FaserSiHitCollectionCnv_p3a.cxx':['m_persEneUnit','transSumE','persSumE'],
 'Simulation/G4Sim/FaserMCTruth/src/FaserTrackHelper.cxx':['GetBarcode','m_trackInfo==0','GetParticleLink'],
 'Simulation/G4Utilities/G4FaserUserActions/src/CalypsoTrackingAction.cxx':['IsRegisteredSecondary','m_secondarySavingLevel','SetTrajectory'],
 'Simulation/G4Sim/FaserMCTruthBase/src/FaserTrajectory.cxx':['IsSecondary','CreateTruthIncident'],
 'Simulation/G4Utilities/G4FaserUserActions/src/CalypsoStackingAction.cxx':['killAllNeutrinos','safeCut','GetParentID','fKill'],
 'Simulation/G4Faser/G4FaserServices/src/FaserUserActionSvc.cxx':['trackingActions','steppingActions','eventActions','addActionTool'],
 'Neutrino/NeutrinoDetDescr/EmulsionGeoModel/src/EmulsionDetectorFactory.cxx':['EmulsionStationA']}
records=[]
for path,terms in paths.items():
    source=subprocess.check_output(['git','-C',str(ROOT.parent/'calypso'),'show',COMMIT+':'+path],text=True)
    records.append(dict(path=path,source_bytes=len(source.encode()),lines=[dict(line=i+1,text=line) for i,line in enumerate(source.splitlines()) if any(t in line for t in terms)]))
OUT.mkdir(exist_ok=True)
(OUT/'source_interface_audit.json').write_text(json.dumps(dict(commit=COMMIT,files=records,conclusion='persistent particleLink is truth-strategy-dependent, not complete root ancestry; add read-only tracking/stepping observer via existing UserActionTools; verify persistent closure and actual envelope in pilot; original GENIE FSI history stays unknown'),indent=2)+'\n')
print('Inspected exact pinned source files:',len(records))
