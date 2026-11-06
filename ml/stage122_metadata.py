"""One bounded file-metadata supplement; missing lineage does not block response."""
import json
import resource
import time
from pathlib import Path


def main():
    from PyUtils.MetaReader import read_metadata
    root=Path(__file__).resolve().parents[1];out=root/'workbook/stage122_energy_ml'
    p=json.loads((root/'workbook/stage119_energy_ml/production_contract_summary.json').read_text())
    rows=[];tick=time.perf_counter();cpu=time.process_time()
    for run in list(range(200131,200137))+list(range(200184,200190)):
        request=next(r for r in p['requests'] if r['source']['run']==run)
        path=request['rdo'];metadata=read_metadata(path,mode='full')[path]
        # Preserve exactly what was exposed, without event/branch array reads.
        def serial(v):
            if isinstance(v,dict):return {str(k):serial(x) for k,x in v.items()}
            if isinstance(v,(list,tuple,set)):return [serial(x) for x in v]
            if v is None or isinstance(v,(str,int,float,bool)):return v
            return str(v)
        rows.append(dict(run=run,input=path,metadata=serial(metadata)))
    (out/'metadata_supplement.json').write_text(json.dumps(dict(files=rows,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        scope='12 precise existing RDO metadata only; no event payload, no rescan, no external requests',
        gate='Full entry/seed/old exposure and full final-state identities still require explicit evidence; file GUID or common EVNT does not certify independence'),indent=2)+'\n')


if __name__=='__main__':main()
