"""Independent original identities, link flags and exact pilot/full overlap."""
from stage192_review import *

if __name__=='__main__':
    phases=['pilot']+(['full'] if (CACHE/'full_native.json.gz').exists() else [])
    flags=0
    for phase in phases:
        data,result=summarize(phase)
        assert len(data['records'])==sum(min(P['pilot_per_source'],len(s['cases'])) if phase=='pilot' else len(s['cases']) for s in P['sources'])
        for r in data['records']:
            c=r['case'];s=next(s for s in P['sources'] if s['index']==c['source_index'])
            assert c['entry'] in {v['entry'] for v in s['cases']}
            for strip in r['links']['strips']:
                for d in strip['deposits']:
                    assert not d['pointer_in_selected_truth'] or d['pointer_valid']
                    if d['pointer_is_unique_primary']:
                        assert d['pointer_in_selected_truth'] and len(r['links']['primary_muons'])==1
                        assert d['linked_barcode']==r['links']['primary_muons'][0]['barcode']
                        assert abs(d['linked_pdg'])==13
                    flags+=1
    overlap=None
    if 'full' in phases:
        full={(r['case']['source_index'],r['case']['entry']):r for r in read(CACHE/'full_native.json.gz')['records']}
        pilot=read(CACHE/'pilot_native.json.gz')['records']
        for r in pilot:
            assert r['links']==full[(r['case']['source_index'],r['case']['entry'])]['links']
        overlap=len(pilot)
    write('independent_validation.json',dict(passed=True,phases=phases,actual_link_flag_checks_N=flags,
        pilot_full_exact_N=overlap,original_identities=True,all_original_cached_contributors_exact=True,
        limit='Structural independent scalar/overlap audit, not a second implementation of HepMC pointer resolution or a certified data truth label.',
        overall_complete=False,promotion=False))
