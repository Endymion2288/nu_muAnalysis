"""Freeze existing-source engineering pilot; no event arrays or ROOT access."""
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage184_energy_ml'

def hit_paths(source):
    path=Path(source['rdo']);pieces=path.name.split('-');tag=pieces[-2]
    first,last=map(int,pieces[-4:-2])
    stem=path.name.split(f'-{source["run"]}-')[0]+f'-{source["run"]}-'
    return [str(path.parents[2]/'sim'/tag/f'{stem}{j:05}-{tag}-HITS.root') for j in range(first,last+1)]

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    (ROOT/'ntuples/energy_ml_stage184').mkdir(parents=True,exist_ok=True)
    assert not (OUT/'protocol.json').exists()
    requests=json.loads((ROOT/'workbook/stage129_energy_ml/extraction_contract.json').read_text())['requests']
    sources=[];inventory=[]
    for s in requests:
        hits=hit_paths(s)
        inventory.append(dict(index=s['index'],component=s['component'],run=s['run'],
            parent_N=s['parent_N'],cases_N=len(s['cases']),active_N=sum(c['role']>0 for c in s['cases']),
            hits_paths_N=len(hits),hits_existing_N=sum(Path(h).is_file() for h in hits),
            rdo_exists=Path(s['rdo']).is_file()))
    for component in ['pi','k','charm']:
        s=next(s for s in requests if s['component']==component)
        cases=[c for c in s['cases'] if c['role']==1][:32]
        assert len(cases)==32
        sources.append(dict(index=s['index'],component=component,run=s['run'],rdo=s['rdo'],
            parent_N=s['parent_N'],hits=hit_paths(s),cases=cases))
    p=dict(stage=184,question='Can existing original-cohort official HITS deliver identity-matched same-window ideal Q15 at affordable cost without new transport?',
        inputs='Original Stage129 280 requests / original89033 identities; no role0 or reserved read. Stage17912 validated cached responses for numerical certification only.',
        sources=sources,reference_indices=json.loads((ROOT/'workbook/stage179_energy_ml/protocol.json').read_text())['indices'],
        selection='First existing request by component pi/k/charm, first32 original role1 by entry. Frozen before new extraction, no truth-E/error selection or replacement.',
        geometry='FASERNU-04',global_tag='OFLCOND-FASER-06',runtime_commit='d32b0ff3',
        channels=[0,1,2,3,4,5,14,6,7,8,9,10,11,12,13],
        scint_window_ns=[780,980],ecal_window_ns=[780,930],
        method='Pinned actual per-hit TOF/propagation, original float TH1D bins and strict last-bin omission; precomputed positive kernel window weights. Only per-bin float product rounding and sum order omitted. Not declared bit exact.',
        tolerance='abs(fastQ-referenceQ)<=32*float32eps*max(1pC,abs(referenceQ)); no tolerance changes after results. Original kernels, periods and inclusive windows fixed.',
        validation=['All12 retained Stage179 channel ideal charges within frozen tolerance',
            'Official HITS total event counts equal parent_N; actual run/event and float32 incoming exact against frozen original cases',
            'Actual persisted RDO run/event exact; hardware join only to current physical PMT, no old-ID decoding',
            'All15 declared hardware channels structurally mapped; empty container is missing ADC, not measured zero',
            'Official reconstruction of saved ADC reports original fixed windows; original negative raw retained',
            'Independent literal Stage141 convolution on first2 train parents per source within tolerance; full sparse selector emits exact frozen entries'],
        phases=dict(preflight='Stage17912 fast/reference + first4 pi HITS/RDO; first2 literal convolution',
            full='Remaining28 pi +32 K +32 charm; first2 per new source literal convolution',
            audit='Independent first4 pi HITS/RDO reread plus independent scalar reference/selector/source-count and full-table audit'),
        CPU_budget_s=4000,phase_CPU_allowance_s=dict(preflight=800,full=2200,audit=1000),
        admission='Scientific preflight allpass; 3*measured complete GNU CPU for4*pi*(92/4)<=2200 and used+projection+1000audit<=4000. No enlarged pilot or alternate sources if failed.',
        request_CPUs=4,request_memory_MB=12000,worker_processes=3,MaxRuntime_s=86400,
        storage_cap_B=16000000,scientific_scope='Pilot only, no energy fit/forward or claim of energy improvement; conditional detector response truth, not real-data calibration.',
        next='If engineering certified, separately freeze meaningful original-cohort status/content/ideal energy contrast and total resource admission before cal/test feature extraction or fits.',
        invariant='Stage87/allgates/8strata/3tails/K/roles/reserved/quarantine/pz>50GeV/pz0-only firstpower/raw11/typedNaN/legal signed/status0timing preserved.',
        new_G4=0,new_independent_nu=0,energy_fits=0,overall_complete=False,promotion=False)
    (OUT/'protocol.json').write_text(json.dumps(p,indent=2)+'\n')
    summary=dict(requests_N=len(inventory),components=dict(Counter(r['component'] for r in inventory)),
        all_hits_paths_present=all(r['hits_paths_N']==r['hits_existing_N'] for r in inventory),sources=inventory)
    (OUT/'existing_hits_inventory.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('FROZEN',[(s['index'],s['component'],len(s['cases'])) for s in sources], 'HITS complete',summary['all_hits_paths_present'])
