"""One full file-metadata read of each exact retained EVNT; no event forward."""
import json,time,resource
from pathlib import Path
from PyUtils.MetaReader import read_metadata
OUT=Path('workbook/stage129_energy_ml');paths=json.loads((OUT/'parent_probe_protocol.json').read_text())['EVNT'];rows=[];tick=time.perf_counter()
def serial(v):
 if isinstance(v,dict):return {str(k):serial(x) for k,x in v.items()}
 if isinstance(v,(list,tuple,set)):return [serial(x) for x in v]
 return v if v is None or isinstance(v,(str,int,float,bool)) else str(v)
for path in paths:rows.append(dict(path=path,metadata=serial(read_metadata(path,mode='full')[path])))
(OUT/'generator_file_metadata.json').write_text(json.dumps(dict(files=rows,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,scope='five exact EVNT full metadata, not an event independence assertion'),indent=2)+'\n')
