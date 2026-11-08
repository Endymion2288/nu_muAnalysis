"""Read-only metadata probe of the exact FASER condition replicas, Condor only."""
import json
import sqlite3
from pathlib import Path
from PyCool import cool

OUT=Path('workbook/stage161_energy_ml')
base=Path('/cvmfs/faser.cern.ch/repo/sw/database/DBRelease/current/sqlite200')
rows=[]
for filename,foldername in [('ALLP200.db','/Tracker/Align'),('CABP200.db','/WAVE/DAQ/CableMapping')]:
    path=(base/filename).resolve()
    with sqlite3.connect(f'file:{path}?mode=ro',uri=True) as database:
        names=[r[0] for r in database.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    row=dict(path=str(path),database_instances=sorted({name[:-6] for name in names if name.endswith('_NODES')}),
        requested_instance='CONDBR3',folder=foldername,supported=False)
    try:
        database=cool.DatabaseSvcFactory.databaseService().openDatabase(f'sqlite://;schema={path};dbname=CONDBR3',True)
        folder=database.getFolder(foldername)
        single=folder.versioningMode()==cool.FolderVersioning.SINGLE_VERSION
        tag=None if single else str(folder.resolveTag('OFLCOND-FASER-05'))
        row.update(supported=True,resolved_tag=tag,single_version=single,
            payload_columns=[str(v.name()) for v in folder.payloadSpecification()])
        database.closeDatabase()
    except Exception as error:row['error']=str(error)
    rows.append(row)
report=dict(passed=all(r['supported'] for r in rows),replicas=rows,
    change='Disable Athena data DBReplicaSvc COOLSQLiteVetoPattern=/DBRelease/ only; retain actual CONDBR3/tag05/run/geometry',
    no_fallback=True,no_conditions_payload_modification=True)
(OUT/'conditions_replica_probe.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)
assert report['passed'],'Actual data condition instance/tag support missing; no MC or nominal-alignment substitute'
