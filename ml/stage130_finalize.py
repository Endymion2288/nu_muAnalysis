"""Stdlib completion audit: measured computation and outstanding physics inputs."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage130_energy_ml'


def read(name):
    return json.loads((OUT / name).read_text())


def main():
    assert (OUT / 'analysis_complete.json').exists()
    progress, resources = read('production_progress.json'), read('resource_summary.json')
    assert progress['complete'] and not progress['failed']
    assert resources['unique_submitted'] == resources['observed'] == resources['terminal']
    protocol, fits, validation = read('curve_protocol.json'), read('fits.json'), read('independent_validation.json')
    joint = read('energy_summary.json')['joint']
    assert len(fits['results']) == 9 and validation['max_abs_difference'] < 1e-10
    rows = [dict(task='complete_frozen_source_denominator', status='measured',
                 actual=progress['completed_source_N'], evidence='production_progress.json'),
            dict(task='selected_EVNT_entry_incoming_links', status='measured',
                 actual=progress['selected_exact_parent_links_N'], evidence='source_evidence.json.gz / ignored parentmaps.json.gz'),
            dict(task='original_scale_controlled_curve',
                 status='measured' if protocol['original_scale_reached'] else 'support_limited',
                 actual=json.dumps(protocol['scale_support'], separators=(',', ':')), evidence='curve_protocol.json'),
            dict(task='fixed_formal_model_fits', status='measured', actual=len(fits['results']), evidence='fits.json'),
            dict(task='independent_scalar_validation_max_abs_difference', status='measured',
                 actual=validation['max_abs_difference'], evidence='independent_validation.json'),
            dict(task='all_scheduler_attempts_terminal', status='measured',
                 actual=resources['terminal'], evidence='resource_jobs.tsv'),
            dict(task='original_GENIE_seed_complete_history', status='uncertified',
                 actual='not certified by simulation seed offsets or unique incoming alone', evidence='source_protocol.json'),
            dict(task='new_blind_independent_confirmation', status='not_measured',
                 actual='reserved remains zero prediction', evidence='independent_validation.json'),
            dict(task='full_data_background_acceptance_nuisance_precision', status='not_measured',
                 actual='requires matched real data/background/response and correlated external inputs', evidence='next_execution_contract.json')]
    for key, value in joint.items():
        rows.append(dict(task='original_joint_gate_'+key, status='passed' if value else 'failed',
                         actual=value, evidence='old_gates.tsv / new_gates.tsv'))
    with (OUT / 'completion_audit.tsv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=['task', 'status', 'actual', 'evidence'],
                                delimiter='\t', lineterminator='\n', quoting=csv.QUOTE_NONNUMERIC)
        writer.writeheader()
        writer.writerows(rows)
    report = dict(completed_stage=130, goal_complete=False,
        original_scale_proxy_support_reached=protocol['original_scale_reached'], joint=joint,
        scheduler_CPU_s=resources['scheduler_CPU_s'], reserve_predictions=0,
        retained_baseline='Stage87 direct62 pending full joint gate and independent confirmation',
        interpretation='quantity effect conditional on one frozen pooled composition and nested membership; augmentation also changes flux mixture; neither proves an information bound or universal sample saturation')
    (OUT / 'completion_summary.json').write_text(json.dumps(report, indent=2)+'\n')
    print(report)


if __name__ == '__main__':
    main()
