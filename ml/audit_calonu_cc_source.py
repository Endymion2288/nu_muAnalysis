#!/usr/bin/env python3
"""Record production evidence and the source mechanism for absent CaloNu waveforms."""
import json
import resource
import subprocess
import time
from pathlib import Path

from report_calonu_native import table


def main():
    tick,cpu=time.perf_counter(),time.process_time()
    repo=Path(__file__).resolve().parents[1];out=repo/'workbook/stage39_energy_ml'
    cfg=json.loads((repo/'ml/configs/calonu_cc_waveform.json').read_text())
    rows=[]
    for index in cfg['indices']:
        req=json.loads((out/f'request_{index}.json').read_text())
        rdo=Path(req['input_rdo']);log=rdo.parents[2]/'log/s0015'/rdo.name.replace('-RDO.root','-RDO.rec.log')
        text=log.read_text()
        lines=[s.strip() for s in text.splitlines() if 'using release [' in s or ('faser_reco.py ' in s and '--geom' in s)]
        assert any('CaloNuMC/1ec47efe' in s for s in lines)
        assert any('TI12MCCaloNu' in s for s in lines)
        rows.append(dict(index=index,log=str(log),release_1ec47efe=True,geometry_TI12MCCaloNu=True,evidence=' | '.join(lines)))
    table(out/'production_reference.tsv',rows)
    def source(path):
        return subprocess.check_output(['git','-C',str(repo.parent/'calypso'),'show','1ec47efe:'+path],text=True)
    path='Calorimeter/CaloDigiAlgs/src/CaloWaveformDigiAlg.cxx'
    s=source(path);lo=s.index('  // Find the output waveform container');hi=s.index('  // Create structure to store pulse',lo)
    snippet=s[lo:hi]
    assert 'caloHitHandle->size() == 0' in snippet and 'return StatusCode::SUCCESS;' in snippet
    ntuple=source('PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.cxx')
    start=ntuple.index('      m_wave_localtime[ii]=0;')
    end=ntuple.index('\n  m_calonu_total_E_EM=0;',start)+len('\n  m_calonu_total_E_EM=0;')
    zero_excerpt=ntuple[start:end]
    assert 'm_wave_raw_charge[ii]=0;' in zero_excerpt and 'm_calonu_total_E_EM=0;' in zero_excerpt
    assert 'm_wave_status[ii]=1;' in zero_excerpt
    conditions=json.loads((repo/'workbook/stage37_energy_ml/conditions_audit.json').read_text())
    digi=next(r for r in conditions['records'] if r['label']=='MC100049' and r['folder']=='/WAVE/Digitization')
    for row in digi['rows']:
        for run in [200139,200140,200146]:assert row['since']<=run<<32<row['until']
    record=dict(source_commit='1ec47efe',source_path=path,empty_hit_collection_records_empty_RDO_and_returns_before_noise=True,
                digitization_payload_IOV_covers_CC_runs=True,
                ntuple_absent_channel_default_status=1,
                caveat='Cached historical payload, source and native mapping support nominal replay; original embedded complete conditions/random seed not reconstructed',
                source_excerpt=snippet,ntuple_default_zero_excerpt=zero_excerpt,
                wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
                peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (out/'source_audit.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({k:v for k,v in record.items() if k not in ['source_excerpt','ntuple_default_zero_excerpt']}))


if __name__=='__main__':main()
