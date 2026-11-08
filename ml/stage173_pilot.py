"""Small actual GRL and conditions pilot; no event arrays."""
import io,json,re,resource,tarfile,time,urllib.request
from html import unescape
from stage173_common import *
if __name__=='__main__':
    start=time.perf_counter();cpu=time.process_time();p=plan();payload={};grls=[];pages=[]
    for name in p['GRL_paths']:
        try:
            row,data=acquire_grl(name);grls.append(row);payload['grl/'+Path(name).name]=data
        except Exception as e:grls.append(dict(path=name,error=str(e),supported=False))
    for i,url in enumerate(p['pages']):
        row=dict(url=url)
        try:
            with urllib.request.urlopen(url,timeout=30) as response:
                data=response.read(1048577);assert len(data)<=1048576
                charset=response.headers.get_content_charset() or 'latin1'
            payload[f'pages/{i}.html']=data;text=unescape(re.sub('<[^>]+>',' ',data.decode(charset)));text=re.sub(r'\s+',' ',text)
            row.update(bytes=len(data),excerpts=[text[max(0,m.start()-120):m.start()+300] for m in re.finditer('15838',text)])
        except Exception as e:row['error']=str(e)
        pages.append(row)
    conditions=[read_conditions('/WAVE/DAQ/CableMapping','CONDBR3',run=15838),
        read_conditions('/WAVE/Calibration/HV','CONDBR3',seconds=1720473060)]
    CACHE.mkdir(exist_ok=True,parents=True)
    with tarfile.open(CACHE/'official_sources.tar.gz','w:gz') as t:
        for name,data in payload.items():
            info=tarfile.TarInfo(name);info.size=len(data);t.addfile(info,io.BytesIO(data))
    write('pilot_summary.json',dict(passed=True,grls=grls,pages=pages,conditions=conditions,
        CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-start,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        missing_fields_are_not_fatal=True,energy_fits=0,new_G4=0,overall_complete=False))
