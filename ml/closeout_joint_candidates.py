"""Stage97 compact resource/storage evidence, without event prediction or fitting."""
import ast
import json
import re
import subprocess
from pathlib import Path
from joint_candidate_common import REPO,OUT,save

CODE=['train_joint_candidates','report_joint_candidates','joint_candidate_common',
      'package_joint_candidates','qa_joint_report','time_joint_worker',
      'collect_joint_candidates','audit_joint_inputs','closeout_joint_candidates']
CONFIG=['AnalysisZipFramework/submission/ml_joint_candidates.sub',
        'AnalysisZipFramework/submission/ml_joint_candidates_kubeflow.json',
        'AnalysisZipFramework/submission/run_ml_joint_candidates.sh']
REPORT='workbook/2026-11-04_stage97_joint-candidate-ablation.md'
DOCS=['docs/nu_mu_energy_ml_revised_roadmap.md','docs/nu_mu_energy_ml_information_budget_plan.md',
      'docs/nu_mu_energy_ml_next_step_prompt.md']


def read(name):return json.loads((OUT/name).read_text())


def resources():
    outer={name:read(name+'_job.json') for name in ['fit','report']}
    qa={}
    for path in sorted(OUT.glob('*.time')):
        value={}
        for label,key in [('User time','user_CPU_s'),('System time','system_CPU_s')]:
            value[key]=float(re.search(re.escape(label)+r' \(seconds\): ([0-9.]+)',path.read_text())[1])
        value['CPU_s']=value['user_CPU_s']+value['system_CPU_s'];qa[path.name]=value
    total=sum(v['CPU_s'] for v in outer.values())+sum(v['CPU_s'] for v in qa.values())
    pod=read('GPU_execution.json');t=pod['container_state']['terminated']
    from datetime import datetime
    wall=(datetime.fromisoformat(t['finishedAt'].replace('Z','+00:00'))-
          datetime.fromisoformat(t['startedAt'].replace('Z','+00:00'))).total_seconds()
    report=read('report_completion.json')
    save('resources.json',dict(measured_disjoint_CPU_s=total,batch_outer_scopes=outer,
         separate_QA_outer_scopes=qa,CPU_cap_s=7200,GPU_concurrency=1,
         GPU_task_outer_wall_s=outer['fit']['wall_s'],GPU_task_container_wall_s=wall,GPU_task_wall_cap_s=3600,
         report_child_average_cores=report['child_CPU_s']/report['parallel_wall_s'],
         report_parallel_wall_scope='pool launch through aggregate checks and plot; not pure pool-only benchmark',
         unmetered='First fixed40 QA before CPU/GPU agreement was added, freeze/metadata/collection/some audits and plotting/housekeeping; not exact whole-session CPU.',
         nested_times_not_added=True,complete_training_CPU_GPU_speedup='未测量',
         physical_EOS_network_bytes='未测量',simultaneous_total_peak_RSS='未测量'))
    assert total<7200 and wall<3600


def validate():
    for name in CODE:ast.parse((REPO/'ml'/str(name+'.py')).read_text())
    subprocess.run(['bash','-n',str(REPO/CONFIG[2])],check=True)
    for path in OUT.glob('*.json'):json.loads(path.read_text())
    original=subprocess.check_output(['git','show','5499517:docs/nu_mu_energy_ml_next_step_prompt.md'],cwd=REPO)
    current=(REPO/DOCS[2]).read_bytes();marker='## 保留的stage54 data占据支线'.encode()
    assert original[original.index(marker):]==current[current.index(marker):]
    for name in DOCS[:2]:
        original=subprocess.check_output(['git','show','5499517:'+name],cwd=REPO)
        assert (REPO/name).read_bytes().startswith(original)
    links=[]
    for target in re.findall(r'\]\(([^)]+)\)',(REPO/REPORT).read_text()):
        if '://' in target:continue
        assert (REPO/REPORT).parent.joinpath(target.split('#')[0]).exists(),target
        links.append(target)
    assert read('validation.json')['passed'] and read('checkpoint_QA.json')['passed'] and read('input_audit.json')['passed']
    assert read('worker_completion.json')['new_fits']==2
    assert (OUT/'preprocessing.json').read_bytes()==(REPO/'workbook/stage96_energy_ml/preprocessing.json').read_bytes()
    save('final_validation.json',dict(passed=True,Python_AST_files=len(CODE),shell_syntax=True,
         JSON_parse=True,report_local_links=len(links),stage54_suffix_byte_exact=True,append_only_history=True,
         frozen_preprocessing_byte_equal=True,new_fits=2,optimizer_steps=sum(read('fit_'+cell+'.json')['optimizer_steps'] for cell in ['A','B']),
         actual_event_space_max_difference=read('validation.json')['actual_event_space_max_difference'],
         new_fits_or_predictions_during_closeout=0,stage98_executed=False))


def storage():
    files=[]
    for name in ['workbook/stage97_energy_ml','ntuples/energy_ml_stage97','ml/artifacts/stage97']:
        files.extend(p for p in (REPO/name).rglob('*') if p.is_file())
    files += [REPO/'ml'/str(name+'.py') for name in CODE]
    files += [REPO/name for name in CONFIG+[REPORT]+DOCS+['.gitignore']]
    target=OUT/'storage.json';files=sorted(set(files+[target]))
    for _ in range(8):
        rows=[dict(path=str(p.relative_to(REPO)),bytes=p.stat().st_size if p.exists() else 0) for p in files]
        total=sum(r['bytes'] for r in rows)
        save('storage.json',dict(total_logical_bytes=total,final_retention_cap_bytes=20000000,files=rows,
             scope='All new Stage97 caches/models/workbook/code/config/report; conservatively includes full shared docs/gitignore; previous-stage shared caches, site logs and Git object storage excluded',
             no_ROOT_or_xAOD=True,source_data_in_Git=False,cleanup='cleanup.json'))
        if sum(p.stat().st_size for p in files)==total:break
    assert total==sum(p.stat().st_size for p in files) and total<20000000
    print(json.dumps(dict(passed=True,retained_logical_bytes=total,measured_disjoint_CPU_s=read('resources.json')['measured_disjoint_CPU_s'])))


if __name__=='__main__':
    resources();storage();validate();storage()
