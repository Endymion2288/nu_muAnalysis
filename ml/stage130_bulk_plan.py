"""Freeze all eligible alternative sources after measured pilot, before model risk."""
import json
import math
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage130_energy_ml'


def main():
    plan = json.loads((OUT / 'source_protocol.json').read_text())
    support = json.loads((OUT / 'pilot_support_summary.json').read_text())
    assert support['files'] == 16 and support['new_model_fits'] == support['predictions'] == 0
    link = json.loads((OUT / 'parentlink_508.json').read_text())
    assert link['unmatched_incoming_N'] == 0, 'Resolve actual generator linkage before bulk admission'
    pilot = json.loads((OUT / 'support_pilot_contract.json').read_text())
    sources = [s for s in plan['sources'] if s['eligible'] and not s['nominal']]
    indices = [s['index'] for s in sources if s['index'] not in pilot['indices']]
    # Cost is a pilot point estimate, not a systematics or confidence interval.
    # No source replacement or low-yield filtering is made after looking at risk.
    costs = {}
    for row in csv.DictReader((OUT / 'pilot_step_cost.tsv').open(), delimiter='\t'):
        index = int(row['index'])
        costs[index] = costs.get(index, 0) + float(row['CPU_s'])
    by_run = {plan['sources'][i]['run']: costs[i] for i in pilot['indices']}
    estimate = sum(by_run[s['run']] for s in sources)
    contract = dict(stage=130, indices=indices, pilot_reused=pilot['indices'],
        all_source_indices=[s['index'] for s in sources], source_N=len(sources),
        source_inclusion_probability=1.0, conditional_parent_probability=1.0,
        old_roles='unchanged; canonical source groups inherited from Stage87; historical locked-test excluded',
        old_exposure='purge exact native incoming and conservative float32 incoming across all Stage119 exposure inputs and expansion reserved metadata; no reserved predictions',
        new_roles='source train/cal/development-test inherited; among new-only train incoming families, fixed 15% hash reserve before fit; no blind claim without full lineage certification',
        reserve_hash='blake2b digest_size8 person=nuMu130, native float32 incoming little-endian bytes, modulo100<15;all views together',
        curve='pool old train plus new eligible train; fixed same-mixture nested1:2 family counts, aim at old two-low-bin incoming support926 and second-bin measuredN0; retain whole-target and all difficult sides; freeze exact counts before risk',
        candidate='one old-full-train plus all new-train candidate, fixed Stage87 policy; flux/mixture effect reported separately from controlled quantity curve',
        reference='frozen Stage87 direct62 and traditional; original cal one global offset per candidate',
        model_search='none: original3seeds400roundsdepth5; no hyperparameter/architecture/seed grid',
        confirmation='new reserve role4 zero fit/prediction; old Stage119 reserve unopened; existing test remains development',
        acceptance='original two-low/1.05 traditional;all1.01/direct;fiveother1.03/direct;eightlayers3tail upper95<=+2pp;1.05 is noninferiority and final low-energy win requiresupper95<1',
        CPU_budget_s=math.ceil(1.5*estimate), pilot_extrapolated_CPU_s=estimate,
        resources=dict(cpus_per_job=8, memory_MB_per_job=24000, max_materialized_jobs=12,
                       max_runtime_s=14400, retained='compact selectedNPZ only;no newROOT/xAOD/HITS/RDO copies'),
        model_outcomes_before_freeze=0,
        scope='Full-depth alternative flux support; unknown original GENIE seed/complete unpersisted history must remain explicit, not silently certified')
    assert not (OUT / 'production_contract.json').exists(), 'Do not silently overwrite frozen production contract'
    (OUT / 'production_contract.json').write_text(json.dumps(contract, indent=2)+'\n')
    print('Frozen', len(indices), 'additional sources; CPU budget', contract['CPU_budget_s'])


if __name__ == '__main__':
    main()
