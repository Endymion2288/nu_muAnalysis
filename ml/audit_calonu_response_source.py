#!/usr/bin/env python3
"""Verify six confirmation production references and pinned conditions coverage."""
import json
import resource
import time
from pathlib import Path
from report_calonu_native import table
repo=Path(__file__).resolve().parents[1];out=repo/'workbook/stage40_energy_ml';tick,cpu=time.perf_counter(),time.process_time()
cfg=json.loads((repo/'ml/configs/calonu_response.json').read_text());rows=[]
conditions=json.loads((repo/'workbook/stage37_energy_ml/conditions_audit.json').read_text())
digi=next(r for r in conditions['records'] if r['label']=='MC100049' and r['folder']=='/WAVE/Digitization')
for index in cfg['indices']:
    req=json.loads((out/f'request_{index}.json').read_text());rdo=Path(req['input_rdo'])
    log=rdo.parents[2]/'log/s0015'/rdo.name.replace('-RDO.root','-RDO.rec.log')
    lines=[s.strip() for s in log.read_text().splitlines() if 'using release [' in s or ('faser_reco.py ' in s and '--geom' in s)]
    assert any('CaloNuMC/1ec47efe' in s for s in lines)
    assert any('TI12MCCaloNu' in s for s in lines)
    assert all(r['since']<=req['run']<<32<r['until'] for r in digi['rows'])
    rows.append(dict(index=index,group=req['group'],log=str(log),release_1ec47efe=True,geometry_TI12MCCaloNu=True,
                     digitization_IOV_covers_run=True,evidence=' | '.join(lines)))
table(out/'production_reference.tsv',rows)
(out/'production_audit.json').write_text(json.dumps(dict(sources=len(rows),all_references_passed=True,
    base_mean_ADC=digi['rows'][0]['payload']['base_mean'],base_rms_ADC=digi['rows'][0]['payload']['base_rms'],
    exact_bck_maker_for_K_charm='not measured',original_embedded_complete_conditions='not reconstructed',
    wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024),indent=2)+'\n')
print('Six production references and historical digitization IOV passed')
