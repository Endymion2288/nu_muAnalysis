"""Read-only bounded condition/GRL access; invoked on HTCondor workers only."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage173_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage173'


def plan():return json.loads((OUT/'protocol.json').read_text())


def write(name,obj):
    (OUT/name).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')


def read_conditions(folder_name,instance,run=None,seconds=None,interval=None,tag=''):
    from PyCool import cool
    p=plan();base=Path(p['database_base']);filename='CABP200.db' if 'CableMapping' in folder_name else 'ALLP200.db'
    source=(base/filename).resolve();result=dict(path=str(source),folder=folder_name,instance=instance,run=run,seconds=seconds,interval=interval,global_tag=tag,rows=[],supported=False)
    database=None
    try:
        database=cool.DatabaseSvcFactory.databaseService().openDatabase(f'sqlite://;schema={source};dbname={instance}',True)
        folder=database.getFolder(folder_name);single=folder.versioningMode()==cool.FolderVersioning.SINGLE_VERSION
        resolved=folder.resolveTag(tag) if tag and not single else ''
        time_folder=folder_name.endswith('/HV')
        start=(interval[0]*10**9 if interval else seconds*10**9) if time_folder else run<<32
        stop=((interval[1]+1)*10**9-1 if interval else start) if time_folder else start
        result.update(description=str(folder.description()),single_version=single,resolved_tag=str(resolved),
            columns=[str(v.name()) for v in folder.payloadSpecification()],key_start=start,key_stop=stop)
        objects=folder.browseObjects(start,stop,cool.ChannelSelection(0,p['max_channel']),resolved)
        N=0
        for obj in objects:
            N+=1
            if N>p['max_folder_rows']:
                result['truncated']=True;break
            payload=obj.payload();record=dict(channel=int(obj.channelId()),since=int(obj.since()),until=int(obj.until()),
                payload={str(k):payload[k] for k in payload.keys()})
            result['rows'].append(record)
        result.update(supported=True,returned_N=len(result['rows']),requested_channels=p['requested_channels'])
    except Exception as e:result['error']=str(e)
    finally:
        if database is not None:database.closeDatabase()
    return result


def acquire_grl(path):
    source=Path(path);data=source.read_bytes();content=json.loads(data)
    record=content.get('15838');ranges={}
    if record:
        for key in ['stable_list','excluded_list']:
            ranges[key]=[[int(r['start_utime']),int(r['stop_utime'])] for r in record.get(key,[])]
    def accepts(t):
        return bool(record) and any(a<=t<=b for a,b in ranges.get('stable_list',[])) and not any(a<=t<=b for a,b in ranges.get('excluded_list',[]))
    return dict(path=path,bytes=len(data),run_present=record is not None,record=record,ranges=ranges,
        fixed_time_membership={str(t):accepts(t) for t in plan()['data_time_keys_unix_s']}),data
