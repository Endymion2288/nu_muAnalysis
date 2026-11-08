"""Complete fixed-cohort root/partition/geometry support and response audit; batch only."""
import csv
import gzip
import json
import math
import resource
import re
import time
from pathlib import Path
import numpy as np

OUT=Path('workbook/stage157_energy_ml');CACHE=Path('ntuples/energy_ml_stage157')


def load(path):
    with gzip.open(path,'rt') as stream:return json.load(stream)


def table(path,rows):
    with path.open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n')
        writer.writeheader();writer.writerows(rows)


def numbers(values):
    x=np.asarray([v for v in values if v is not None and np.isfinite(v)],dtype=float)
    return dict(N=len(x),min=float(x.min()),median=float(np.median(x)),max=float(x.max()),mean=float(x.mean())) if len(x) else dict(N=0)


def run():
    tick,cpu=time.perf_counter(),time.process_time();native=[];pairs=[];checks=[];seed_boundary_N=0
    seed_read_bytes=0;extract_read_bytes=0;native_read_bytes=0;pipeline_wall_s=0.;peak_ROOT_bytes=0
    for chunk in range(64):
        label=f'chunk_{chunk:02d}'
        n=load(CACHE/f'chains/{label}/native.json.gz');p=load(CACHE/f'chains/{label}/paired.json.gz')
        schema=json.loads((OUT/f'chains/{label}/schema.json').read_text())
        seed=json.loads((OUT/f'chains/{label}/seeds.json').read_text())
        proof=json.loads((OUT/f'chains/{label}/transport_proof.json').read_text())
        pipeline=json.loads((OUT/f'chains/{label}/pipeline.json').read_text())
        extraction=json.loads((OUT/f'chains/{label}/summary.json').read_text())
        seed_read_bytes+=seed['ROOT_read_bytes'];native_read_bytes+=n['ROOT_read_bytes']
        extract_read_bytes+=extraction['ROOT_read_bytes'];pipeline_wall_s+=pipeline['wall_s']
        peak_ROOT_bytes=max(peak_ROOT_bytes,pipeline['peak_ROOT_bytes'])
        assert pipeline['successful'] and not pipeline['intermediate_ROOT_retained']
        assert schema['verified'] and n['configured_conditions']==dict(conditions='OFLCOND-FASER-06',geometry='FASERNU-04')
        assert len(n['records'])==len(p)==len(seed['records'])==64
        for i,(r,v,s) in enumerate(zip(n['records'],p,seed['records'])):
            entry=64*chunk+i
            assert r['entry']==v['entry']==s['entry']==entry
            assert (r['run'],r['event'])==(v['run'],v['event'])==(s['run'],s['event'])
            assert all(v[k] for k in ['run_event_exact','old_run_event_exact','old_roots_float32_exact','all_tracks_float32_exact','raw15_exact'])
            assert v['leading_identity_exact']==(v['leading_index'] is not None)
            g=r['geometry'];assert g['anchor_counts']['valid']<=g['anchor_counts']['total']
            assert g['leading_identity_known']==(v['leading_index'] is not None)
            assert all(g[k] is None or g[k]<=1e-8 for k in ['max_state_roundtrip_mm','max_PRD_roundtrip_mm','independent_dx_max_delta_mm','max_candidate_roundtrip_mm'])
            assert all(w['status']==0 or w['localtime'] is None for w in r['waves'])
            if s['full_private_state_retained']:
                assert 'before' in s and 'after' in s;seed_boundary_N+=1
            else:assert 'before' not in s and 'after' not in s
            for station in g['stations']:
                assert station['clusters']==station['leadingOwned']+station['nonleading']
                assert station['nonleading']==station['offMeasuredWafer']+station['onMeasuredWafer']
                if not station['available']:assert station['candidate_N'] is None
            native.append(r);pairs.append(v)
        assert proof['passed']
        if chunk<2:
            assert len(proof['prefix_comparisons'])==64
            assert all(all(v for k,v in row.items() if k!='entry') for row in proof['prefix_comparisons'])
        checks.append(dict(chunk=chunk,begin=64*chunk,N=64,schema_verified=True,root_current_identity=True,
            all_anchor_valid=all(r['geometry']['anchor_counts']['total']==r['geometry']['anchor_counts']['valid'] for r in n['records']),temporary_ROOT_retained=False,pilot_prefix_exact_N=len(proof['prefix_comparisons'])))
    assert len(native)==4096 and [r['entry'] for r in native]==list(range(4096))
    table(OUT/'chunk_checks.tsv',checks)
    resources=[]
    for chunk in range(64):
        label=f'chunk_{chunk:02d}';row=dict(label=label,begin=64*chunk,N=64)
        for step in ['digi','reco','native','extract']:
            text=(OUT/f'chains/{label}/{step}_time.txt').read_text()
            row[step+'_GNU_CPU_s']=sum(float(re.search(r'(?m)^\s*'+re.escape(k)+r': (\S+)',text).group(1)) for k in ['User time (seconds)','System time (seconds)'])
            row[step+'_peak_RSS_KiB']=int(re.search(r'Maximum resident set size \(kbytes\): (\d+)',text).group(1))
        row['total_children_GNU_CPU_s']=sum(row[step+'_GNU_CPU_s'] for step in ['digi','reco','native','extract'])
        resources.append(row)
    table(OUT/'chain_resources.tsv',resources)
    drivers=[json.loads((OUT/f'batch_{i:02d}_driver.json').read_text()) for i in range(16)]
    aggregate_driver_wall=sum(d['wall_s'] for d in drivers)
    child_CPU=sum(r['total_children_GNU_CPU_s'] for r in resources)
    resource_summary=dict(full_chain_N=64,full_parent_executions=4096,
        total_children_GNU_CPU_s=child_CPU,aggregate_driver_wall_s=aggregate_driver_wall,
        aggregate_individual_chain_wall_s=pipeline_wall_s,
        observed_chain_wall_overlap_factor=pipeline_wall_s/aggregate_driver_wall,
        child_CPU_per_allocated_4core_driver_wall=child_CPU/(4*aggregate_driver_wall),
        parents_per_aggregate_driver_wall_s=4096/aggregate_driver_wall,
        child_CPU_per_parent_s=child_CPU/4096,
        largest_single_child_RSS_KiB=max(r[step+'_peak_RSS_KiB'] for r in resources for step in ['digi','reco','native','extract']),
        largest_single_chain_temporary_ROOT_bytes=peak_ROOT_bytes,
        conservative_4chain_temporary_ROOT_bytes=4*peak_ROOT_bytes,
        ROOT_requested_bytes=dict(digi=seed_read_bytes,native=native_read_bytes,extract=extract_read_bytes),
        scope='Measured complete fixed4096 processing, includes startup/lazyJIT; overlap is not a controlled serial-vs-parallel speedup. ROOT bytes exclude uninstrumented reco/metadata and are not physical network IO. Child RSS is not simultaneous job RSS.',
        GPU=0)
    (OUT/'resource_summary.json').write_text(json.dumps(resource_summary,indent=2)+'\n')
    keys=['clusters','leadingOwned','nonleading','offMeasuredWafer','onMeasuredWafer','measuredWafers','eligibleWafers',
        'eligibleCandidates','candidateSurfaceMismatch','unusableAnchorCandidates','candidateMissingElement','candidateInvalidRDO',
        'candidateInvalidLocal','candidateRoundtripFailure']
    strata=dict(all=list(range(4096)),current_leading=[i for i,p in enumerate(pairs) if p['leading_index'] is not None],
        pz0_50_100=[i for i,p in enumerate(pairs) if p['leading_index'] is not None and 50<=native[i]['tracks'][p['leading_index']]['state'][5]/1000<100],
        overflow=[i for i,p in enumerate(pairs) if any(v['name'] in __import__('stage157_response').CHANNELS and v['status']&4 for v in p['readout'])])
    station_rows=[];support={}
    for label,indices in strata.items():
        rows=[native[i]['geometry'] for i in indices];stations=[]
        for station in range(4):
            sr=[r['stations'][station] for r in rows]
            counts=dict(stratum=label,N=len(rows),station=station,available_parent_N=sum(s['available'] for s in sr),
                nonempty_parent_N=sum(s['eligibleCandidates']>0 for s in sr),**{k:sum(s[k] for s in sr) for k in keys})
            station_rows.append(counts)
            stations.append(dict(**counts,distributions={k:numbers([s[k] for s in sr]) for k in ['candidate_N','mean_abs_dx_mm','min_abs_dx_mm','max_abs_dx_mm','RMS_dx_mm']}))
        support[label]=dict(N=len(rows),nonempty_parent_N=sum(any(s['eligibleCandidates'] for s in r['stations']) for r in rows),stations=stations)
    table(OUT/'station_support.tsv',station_rows)
    from stage157_response import run as response
    result=response(native,pairs)
    from stage157_verify import run as verify
    verify(native,pairs)
    from stage157_plot import run as plot
    plot()
    report=dict(phase='full',passed=True,independent_parent_N=4096,physical_parent_executions=4416,duplicate_parent_executions=320,
        root_identity_exact_N=4096,current_native_ntuple_exact_N=4096,current_selected_N=sum(p['new_selected'] for p in pairs),
        no_leading_N=sum(p['leading_index'] is None for p in pairs),
        anchors={k:sum(r['geometry']['anchor_counts'][k] for r in native) for k in native[0]['geometry']['anchor_counts']},
        strata=support,diagnostics={k:numbers([r['geometry'][k] for r in native]) for k in ['max_abs_normal_mm','max_state_roundtrip_mm',
            'max_PRD_roundtrip_mm','independent_dx_max_delta_mm','max_candidate_roundtrip_mm','max_candidate_dx_interval_width_mm']},
        prefix128_current_and_RNG_exact=True,full_RNG_state_retained_parent_executions=seed_boundary_N,
        remaining_RNG_scope='Per-event actual seeds and observed changed flags; exact full-state pairing only pilot/prefix and fixed chunk boundary snapshots, not all4096independentreplays',
        response=result,new_G4=0,energy_fits=0,reserved_forward=0,population_FPR_certified=False,
        data_native_calibration='input_missing',overall_complete=False,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
        typed_QA=dict(nonzero_status_with_timing_N=sum(w['status']!=0 and w['localtime'] is not None for r in native for w in r['waves']),
            cleaned_raw_finite_sentinel_N=sum(v['raw_charge_pC'] in [-999.,-9999.,-99999.] for p in pairs for v in p['readout'] if v['raw_charge_pC'] is not None),
            undefined_surface_with_numeric_candidate_N=sum(not s['available'] and s['candidate_N'] is not None for r in native for s in r['geometry']['stations']),
            valid_empty_set_with_numeric_distance_N=sum(s['available'] and s['candidate_N']==0 and any(s[k] is not None for k in ['mean_abs_dx_mm','min_abs_dx_mm','max_abs_dx_mm','RMS_dx_mm']) for r in native for s in r['geometry']['stations'])),
        RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('FULL_SUMMARY',report,flush=True)
