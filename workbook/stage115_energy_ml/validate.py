#!/usr/bin/env python3
"""Local stdlib audit of collected text, documents and unchanged transport."""
import ast
import csv
import json
import re
import subprocess
import tarfile
from pathlib import Path

R=Path(__file__).resolve().parents[2]
O=Path(__file__).resolve().parent
BASE='522f6db'
REPORT='workbook/2026-11-05_stage115_measurement-state-residual.md'


def load(n):return json.loads((O/n).read_text())
def rows(n):
    with (O/n).open() as f:return list(csv.DictReader(f,delimiter='\t'))


def main():
    complete=load('complete.json');v=load('measurement_validation.json');qa=load('QA.json');inputs=load('input_validation.json')
    assert complete['status']=='experiment_complete' and complete['active_records']==71376
    assert complete['formal_rule_dictionaries']==2 and complete['head_solves']==4
    assert complete['baseline_fits']==complete['baseline_forwards']==0
    assert complete['both_arms_frozen_before_test_forward_and_risk'] and not complete['new_split'] and not complete['new_ROOT']
    assert v['passed'] and v['independent_final_test_comparisons']==40 and v['independent_primary_comparisons']==3
    assert v['independent_interval_max_abs']<1e-10 and v['old_scalar_max_abs']<1e-10
    assert qa['passed'] and qa['real_train_identities']==40 and qa['all_constraint_gradient_max_abs']<1e-6
    assert inputs['passed'] and [inputs[k] for k in ['active_rows','quarantined','train','cal','test','all_new_K']]==[71376,17657,46575,11612,13189,1016]
    assert inputs['status_available']+inputs['status_missing']==71376
    frozen=load('fits_frozen.json');assert frozen['all_theta_locked'] and frozen['fits']==2 and frozen['convex_solver_calls']==4
    assert not frozen['test_forward_or_risk_before_both_locked']
    for arm in ['A','B']:
        fit=load(f'{arm}_fit.json');assert fit['trees']==8 and fit['leaf_indicators']<=64 and fit['rank']<=fit['leaf_indicators']
        for which in ['primary','secondary']:
            solve=load(f'{arm}_{which}_solve.json')
            assert solve['max_normalized_violation']<=1e-7
            assert solve['formal_dual_lower_bound'] is None
        assert len(rows(f'{arm}_train_tail_constraints.tsv'))==16
    assert len(rows('primary.tsv'))==3 and len(rows('gates.tsv'))==16
    gates=rows('gates.tsv');layers=['E50_100','E100_200','all','E200_inf','pz50_100','pz50_100_trueE200','high_y','unconfirmed']
    for arm in ['A','B']:
        assert [r['stratum'] for r in gates if r['candidate']==arm]==layers
    assert len(rows('state_coverage.tsv'))==3*11*4
    history=load('condor_history.json')[0]
    assert history['ClusterId']==9668138 and history['JobStatus']==4 and history['ExitCode']==0 and history['NumJobStarts']==1
    assert load('watchdog.json')['passed'] and load('watchdog.json')['stop'] is None
    accounting=load('accounting.json')
    assert accounting['total_CPU_s']<=1800 and accounting['total_task_wall_s']<=900
    assert load('transport_validation.json')['byte_exact_input_files']==21
    package=R/'software/energy-ml-stage115.tar.gz'
    if package.exists():
        with tarfile.open(package) as t:
            for name in load('package.json')['files']:
                assert t.extractfile(name).read()==(R/name).read_bytes(),name
    for name in ['docs/nu_mu_energy_ml_revised_roadmap.md','docs/nu_mu_energy_ml_information_budget_plan.md']:
        old=subprocess.check_output(['git','show',f'{BASE}:{name}'],cwd=R)
        assert (R/name).read_bytes().startswith(old)
    prompt='docs/nu_mu_energy_ml_next_step_prompt.md'
    old=subprocess.check_output(['git','show',f'{BASE}:{prompt}'],cwd=R);new=(R/prompt).read_bytes();marker='## 保留的stage54 data占据支线'.encode()
    assert old[old.index(marker):]==new[new.index(marker):]
    for name in ['AnalysisZipFramework/submission/ml_tracker_occupancy_prepare.sub',
        'AnalysisZipFramework/submission/run_ml_tracker_occupancy_prepare.sh','ml/prepare_tracker_occupancy.py',
        'ntuples/energy_ml_stage54','workbook/stage54_energy_ml']:
        assert (R/name).exists()
    checked=0
    for name in [REPORT,prompt]:
        for target in re.findall(r'\]\(([^)]+)\)',(R/name).read_text()):
            if target.startswith(('https://','http://','#')):continue
            path=(R/name).parent/target.split('#',1)[0]
            if path.parent==O and path.name in ['storage.json','document_validation.json']:continue
            assert path.exists(),(name,target)
            checked+=1
    for path in R.glob('ml/*stage115*.py'):ast.parse(path.read_text())
    subprocess.run(['bash','-n','AnalysisZipFramework/submission/run_ml_stage115.sh'],cwd=R,check=True)
    subprocess.run(['git','diff','--check'],cwd=R,check=True)
    result=dict(passed=True,completed_fixed_two_arm_experiment=True,all_original_roles_and_K_preserved=True,
        all8_final_RMSE_and_3_tail_gates_reported=True,independent_test_interval_pairs=40,
        independent_primary_pairs=3,no_baseline_refit_or_forward=True,no_offset_or_winner_selection=True,
        formal_optimality_not_claimed=True,source_refit_systematic_and_blind_confirmation=False,
        total_CPU_s=accounting['total_CPU_s'],total_task_wall_s=accounting['total_task_wall_s'],
        historical_doc_prefixes_and_stage54_suffix_preserved=True,local_links_checked=checked,
        local_event_or_model_computation=False)
    (O/'document_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
