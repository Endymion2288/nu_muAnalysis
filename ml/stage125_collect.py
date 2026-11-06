"""Audit every scoped result without retaining ROOT or intermediate xAOD files."""
import argparse
import io
import json
import os
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage125_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage125'
INPUT=Path(os.environ.get('NU_MU_STAGE125_INPUT_ROOT',str(ROOT)))


def inspect(phase):
    plan=json.loads((OUT/'protocol.json').read_text());results=[]
    for path in sorted((INPUT/'ntuples/energy_ml_stage125').glob(f'{phase}_*.tar.gz')):
        index=int(path.name.split('_')[1].split('.')[0]);s=plan['sources'][index]
        with tarfile.open(path) as t:
            names=t.getnames()
            def read(n):return t.extractfile('result/'+n).read()
            exitcode=int(read('exitcode.txt'))
            summary=json.loads(read('request_summary.json')) if 'result/request_summary.json' in names else {}
            row=dict(index=index,run=s['run'],tune=s['tune'],component=s['component'],exitcode=exitcode,
                     parent_N=summary.get('parent_N'),empty='result/empty.txt' in names,
                     selected_present='result/selected.npz' in names,transport_bytes=path.stat().st_size)
            for n in ['parent_time.txt','digi_time.txt','reco_time.txt','ntuple_time.txt','extract_time.txt']:
                if 'result/'+n in names:
                    import re
                    text=read(n).decode();values={}
                    for key,label in [('user_s','User time (seconds)'),('system_s','System time (seconds)'),('RSS_KiB','Maximum resident set size (kbytes)')]:
                        m=re.search(re.escape(label)+r':\s*([0-9.]+)',text)
                        if m:values[key]=float(m[1])
                    m=re.search(r'Elapsed \(wall clock\) time \(h:mm:ss or m:ss\):\s*([0-9:.]+)',text)
                    if m:values['wall_s']=sum(float(v)*60**i for i,v in enumerate(reversed(m[1].split(':'))))
                    values['CPU_s']=values.get('user_s',0)+values.get('system_s',0);row[n.replace('_time.txt','')]=values
            if exitcode:
                row['errors']={n:read(n).decode(errors='replace')[-6000:] for n in ['extract_log.txt','parent_log.txt','digi_excerpt.txt','reco_excerpt.txt','ntuple_excerpt.txt'] if 'result/'+n in names}
            elif row['selected_present']:
                import numpy as np
                with np.load(io.BytesIO(read('selected.npz'))) as z:
                    md=json.loads(str(z['metadata_json']));row['selected_N']=len(z['x'])
                    assert z['x'].shape==(row['selected_N'],62)
                    assert np.all(np.isfinite(z['incoming'])) and np.all(z['reco_pz_GeV']>50)
                    row['identity']=md['parent_identity'];row['calibration']=md['calibration']
                    row['feature_version']=md['feature_version'];row['cutflow_names']=md['cutflow_names'];row['cutflow_passed']=md['cutflow_passed']
        results.append(row)
    record=dict(phase=phase,returned=len(results),failed=sum(r['exitcode']!=0 for r in results),results=results)
    (OUT/f'{phase}_audit.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({k:v for k,v in record.items() if k!='results'}))
    for r in results:
        if r['exitcode']:print(r['index'],r.get('errors'))
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase');a=p.parse_args();inspect(a.phase)
