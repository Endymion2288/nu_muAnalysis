"""Batch-only source-version ID decoding and exact source-run condition query."""
import csv,json
from pathlib import Path
import ROOT
from PyCool import cool
OUT=Path('workbook/stage185_energy_ml')

def conditions(tag,run):
    path=Path('/cvmfs/faser.cern.ch/repo/sw/database/DBRelease/current/sqlite200/CABP200.db').resolve()
    database=cool.DatabaseSvcFactory.databaseService().openDatabase(f'sqlite://;schema={path};dbname=OFLP200',True)
    try:
        folder=database.getFolder('/WAVE/DAQ/CableMapping');single=folder.versioningMode()==cool.FolderVersioning.SINGLE_VERSION
        resolved='' if single else folder.resolveTag(tag)
        objects=folder.browseObjects(run<<32,run<<32,cool.ChannelSelection(0,31),resolved)
        rows=[]
        for obj in objects:
            payload=obj.payload();rows.append(dict(channel=int(obj.channelId()),since=int(obj.since()),until=int(obj.until()),payload={str(k):payload[k] for k in payload.keys()}))
        return dict(path=str(path),run=run,tag=tag,single_version=single,resolved_tag=resolved,rows=rows,
            historical_bytes_certified=False,caveat='Current DB snapshot is queried exactly; this does not recover historical database bytes.')
    finally:database.closeDatabase()

if __name__=='__main__':
    for library in ['libIdentifier.so','libIdDict.so','libIdDictParser.so']:
        assert ROOT.gSystem.Load(library)>=0,library
    assert ROOT.gInterpreter.Declare(Path('ml/stage185_identity.hxx').read_text())
    decoder=ROOT.Stage185Identity(str(OUT/'IdDict_6d6ab70b.xml'))
    original=json.loads(Path('workbook/stage184_energy_ml/audit_source_0_summary.json').read_text())
    found={};rows=[];parts=dict(Veto=1,Trigger=2,Preshower=3,VetoNu=4)
    for record in original['mapping_diagnostics']:
        if record['detector']=='Calo':
            assert record['stored_id32']==record['current_cable_id32']
            continue
        values=list(decoder.decode(record['stored_id32']));assert values[:2]==[2,parts[record['detector']]]
        physical=values[2:];key=(record['detector'],record['channel'])
        if key in found:assert found[key]==physical
        else:
            found[key]=physical;rows.append(dict(detector=record['detector'],channel=record['channel'],stored_id32=record['stored_id32'],
                subdet=values[0],part=values[1],station=physical[0],plate=physical[1],pmt=physical[2],roundtrip_exact=True))
    assert len(rows)==11
    with (OUT/'historical_physical_channels.tsv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(rows)
    records=[conditions(tag,source['run']) for source in json.loads((OUT/'protocol.json').read_text())['sources'] for tag in ['OFLCOND-FASER-04','OFLCOND-FASER-06']]
    result=dict(passed=True,historical_scint_channel_N=len(rows),source_commit='6d6ab70b',actual_decoder='Standalone IdDictParser with exact source dictionaries, compact expanded compact roundtrip',
        physical_mapping_selected_by_charge=False,channels=rows,current_condition_records=records,
        original_historical_database_bytes='unavailable; physical stored identifier decoded directly',energy_fits=0,new_G4=0,overall_complete=False)
    (OUT/'identity_summary.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k not in ['channels','current_condition_records']},flush=True)
