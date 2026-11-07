"""Compact full-denominator, seed, hit-closure and measured execution evidence."""
import collections
import gzip
import json
import re
import sys
import tarfile
from pathlib import Path
from stage131_common import OUT,CACHE,protocol,table


def main():
    contract=protocol()
    with gzip.open(CACHE/'production_cases.json.gz','rt') as stream:
        cases=json.load(stream)
    with gzip.open(CACHE/'parent_evidence.json.gz','rt') as stream:
        reports={r['index']:r['reports'] for r in json.load(stream)}
    archived_times={}
    for archive in CACHE.glob('production_*_result.tar.gz'):
        with tarfile.open(archive) as bundle:
            for member in bundle:
                match=re.fullmatch(r'parent_(\d+)_(.+)_time.txt',Path(member.name).name)
                if match:archived_times[int(match[1]),match[2]]=bundle.extractfile(member).read().decode()
    assert sorted(c['frame_index'] for c in cases)==sorted(contract['indices'])
    assert len({(c['EVNT'],c['entry']) for c in cases})==len(cases)
    cells=collections.defaultdict(collections.Counter)
    cuts=collections.defaultdict(collections.Counter)
    timing=collections.defaultdict(list)
    closure=collections.defaultdict(list)
    g4_seeds=[];private_seeds=[];tracks=steps=unknown=missing=outside=scratch=read_bytes=0
    primary_mu=collections.Counter();raw_times=[];rng_counts=collections.defaultdict(collections.Counter)
    collections_by_tool=dict(Calo='EcalHits',VetoNu='VetoNuHits',Veto='VetoHits',Trigger='TriggerHits',Preshower='PreshowerHits')
    for case in cases:
        i=case['frame_index']
        summary=reports[i]['summary'];selection=reports[i]['selection']
        hits=reports[i]['hitscheck'];rng=reports[i]['rng']
        assert summary['successful'] and selection['identity_incoming_exact'] and hits['passed']
        assert summary['case']['entry']==case['entry'] and summary['case']['EVNT']==case['EVNT']
        assert summary['case']['seed']==case['seed']
        base=case['seed']+1 if i==50 else 650000000+10000*i
        assert {r['seed'] for r in rng.values()}=={base+1000*j for j in range(5)}
        assert all(step['returncode']==0 for step in summary['steps'])
        for detector,state in rng.items():
            n=next(row['hits_N'] for row in hits['rows'] if row['collection']==collections_by_tool[detector])
            # Both official waveform algorithms return SUCCESS before touching
            # their private generator when their entire HITS collection is empty.
            assert state['advanced']==bool(n),(i,detector,n,state['advanced'])
            rng_counts[detector]['parents_N']+=1
            rng_counts[detector]['positive_HITS_and_advanced_N']+=int(bool(n))
            rng_counts[detector]['zero_HITS_early_return_unchanged_N']+=int(not n)
        g4_seeds.append(case['seed']);private_seeds.extend(r['seed'] for r in rng.values())
        for stratum in [case['stratum'],'ALL']:
            key=case['role'],stratum,case['component']
            cells[key]['parents_N']+=1;cells[key]['reselected_N']+=selection['selected_N']
        for cut,passed in selection['cuts'].items():
            cuts[case['role'],cut]['parents_N']+=1
            cuts[case['role'],cut]['passed_N']+=passed
        lineage=summary['lineage'];tracks+=lineage['tracks'];steps+=lineage['steps']
        unknown+=lineage['unknown_tracks'];missing+=lineage['missing_birth']
        outside+=lineage['outside_primaries'];primary_mu[lineage['primary_muons']]+=1
        scratch+=summary['scratch_ROOT_logical_B'];read_bytes+=hits['read_bytes']
        for row in hits['rows']:closure[row['collection']].append(row)
        for step in summary['steps']:
            path=OUT/f'parent_{i}_{step["name"]}_time.txt'
            text=path.read_text() if path.is_file() else archived_times[i,step['name']]
            raw_times.append(dict(index=i,step=step['name'],GNU_time_text=text))
            cpu=sum(map(float,re.findall(r'(?:User time|System time) \(seconds\): ([\d.]+)',text)))
            rss=int(re.search(r'Maximum resident set size \(kbytes\): (\d+)',text).group(1))
            timing[step['name']].append(dict(CPU_s=cpu,wall_s=step['wall_s'],RSS_KiB=rss))
    assert len(g4_seeds)==len(set(g4_seeds)) and len(private_seeds)==len(set(private_seeds))
    assert all(0<s<2**31 for s in g4_seeds+private_seeds)
    table('parent_yield_by_component.tsv',[dict(role=k[0],stratum=k[1],component=k[2],**v) for k,v in sorted(cells.items())])
    table('individual_cut_counts.tsv',[dict(role=k[0],cut=k[1],**v) for k,v in sorted(cuts.items())])
    table('parent_execution_steps.tsv',[dict(step=k,calls=len(v),CPU_s=sum(r['CPU_s'] for r in v),aggregate_wall_s=sum(r['wall_s'] for r in v),max_RSS_KiB=max(r['RSS_KiB'] for r in v)) for k,v in sorted(timing.items())])
    table('hits_closure_summary.tsv',[dict(collection=k,pairs=len(v),hits_N=sum(r['hits_N'] for r in v),max_abs_delta_MeV=max(r['abs_delta_MeV'] for r in v),max_fraction_of_tolerance=max(r['abs_delta_MeV']/r['tolerance_MeV'] for r in v),all_passed=all(r['passed'] for r in v)) for k,v in sorted(closure.items())])
    table('private_rng_usage.tsv',[dict(detector=k,**v) for k,v in sorted(rng_counts.items())])
    with gzip.open(CACHE/'execution_times.json.gz','wt') as stream:json.dump(raw_times,stream,separators=(',',':'))
    with gzip.open(CACHE/'execution_times.json.gz','rt') as stream:assert json.load(stream)==raw_times
    report=dict(parents_N=len(cases),unique_exact_EVNT_file_entry_N=len(cases),all_fixed_parents_complete=True,reselected_N=sum(v['reselected_N'] for k,v in cells.items() if k[1]=='ALL'),tracks=tracks,steps=steps,unknown_root_tracks=unknown,missing_birth=missing,outside_primary_tracks=outside,primary_muon_multiplicity=dict(primary_mu),G4_seed_offsets_N=len(g4_seeds),private_TRandom3_seeds_N=len(private_seeds),within_domain_numeric_seed_collisions_N=0,cross_domain_equal_numeric_seed_values=sorted(set(g4_seeds)&set(private_seeds)),seed_scope='G4 framework SeedOffset plus unique output-filename stream; waveform private TRandom3 with explicit state audit. Equal numeric values across these namespaces are not equal engine states; no global numeric-uniqueness claim',HITS_check_ROOT_read_B=read_bytes,scratch_ROOT_logical_B=scratch,transported_ROOT_B=0,new_independent_neutrino_interactions_N=0,reserved_forward_N=0,scope='successful fixed-parent calls only; failed attempts remain in scheduler ledger and failure archives; GNU child CPU is nested,never added to scheduler CPU; ROOT read covers HITS checker only,not full-chain I/O; scratch byte total is cumulative logical output,not physical EOS consumption')
    (OUT/'full_parent_audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report)


if __name__=='__main__':
    main()
    if len(sys.argv)>1:
        assert len(json.loads((OUT/'fits.json').read_text())['results'])==18
        assert json.loads((OUT/'independent_validation.json').read_text())['passed']
        assert json.loads((OUT/'compact_verification.json').read_text())['passed']
        (OUT/'analysis_complete.json').write_text(json.dumps(dict(sequence=['prepare','fit','evaluate','mechanism','validate','plot','compact','audit'],successful=True,energy_fits=18,reserve_forward=0,resumed_only='audit after correcting zero-HITS private RNG early-return assertion; no refits or risk changes'),indent=2)+'\n')
