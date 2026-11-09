"""Admit complete-source production only after actual pilot QA/timing."""
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage199_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage199'
p=json.loads((OUT/'protocol.json').read_text());rows=[]
for index in p['pilot_indices']:
    path=CACHE/f'pilot_{index}'
    assert (path/'exitcode.txt').read_text().strip()=='0',(index,path)
    md=json.loads((path/'summary.json').read_text());assert md['passed'] and md['selected_N']>0
    times={}
    for f in path.glob('*.time'):
        text=f.read_text()
        values=[]
        for label in ['User time (seconds)','System time (seconds)']:
            values.append(float(re.search(re.escape(label)+r':\s*([0-9.]+)',text)[1]))
        times[f.stem]=sum(values)
    source=p['sources'][index]
    rows.append(dict(index=index,mode=source['mode'],component=source['component'],selected_N=md['selected_N'],
        raw_N=md['raw_N'],parent_N=md.get('original_parent_N',md['raw_N']),times_CPU_s=times,total_nested_CPU_s=sum(times.values())))
estimates={r['component']:r['total_nested_CPU_s']*10 for r in rows if r['mode']=='reco'}
projection=sum(estimates[s['component']] for s in p['sources'] if s['mode']=='reco')
result=dict(passed=True,pilot=rows,reco164_projection_CPU_s=projection,
    projection_scope='10x first1000 parent pilot per component; planning estimate, not measured full cost or statistical upper bound',
    resources='8CPU/24GB batches, up to20 concurrent, two-day job class; no former K one-hour limit',
    fits_so_far=0,sample_coverage_reduced=False)
(OUT/'pilot_admission.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
