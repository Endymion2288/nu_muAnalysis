"""Stage92 accounting and manifest; run only after full evaluation/closeout."""
import ast,json,re,subprocess
from pathlib import Path
root=Path.cwd();out=root/'workbook/stage92_energy_ml'
assert json.loads((out/'complete_validation.json').read_text())['passed']
def timer(path):
    text=path.read_text()
    fields={key:float(re.search(pattern,text)[1]) for key,pattern in {
      'user_CPU_s':r'User time \(seconds\): ([\d.]+)',
      'system_CPU_s':r'System time \(seconds\): ([\d.]+)',
      'peak_RSS_KiB':r'Maximum resident set size \(kbytes\): ([\d.]+)'}.items()}
    fields['CPU_s']=fields['user_CPU_s']+fields['system_CPU_s']
    fields['timer']=str(path)
    return fields
local=[dict(phase=p.stem,**timer(p)) for p in sorted(Path('/tmp').glob('stage92*.time'))]
remote=[]
for role in ['cal','test']:
    history=json.loads((out/f'history_{role}.json').read_text());assert len(history)==1
    h=history[0];assert h['ExitCode']==0 and h['NumJobStarts']==1
    remote.append(dict(role=role,**timer(out/role/'job.time'),Condor_user_CPU_s=h.get('RemoteUserCpu'),Condor_system_CPU_s=h.get('RemoteSysCpu'),worker=json.loads((out/role/'total_resources.json').read_text())))
fit=json.loads((out/'fit_outer_resources.json').read_text())
total=sum(a['CPU_s'] for a in local+remote)+fit['CPU_s']
assert total<32400
resources=dict(measured_outer_CPU_s=total,limit_CPU_s=32400,local_outer_timers=local,Kubeflow_fit_outer=fit,CPU_workers=remote,not_double_counted='worker internal CPU, training/calibration/trajectory/QA subtimers, Condor rounded CPU not summed again',unmeasured='platform admission/preflight/OAuth/container startup CPU and some early development/metadata/docs/monitoring/static checks; physical EOS IO; GPU allocated/physical peak memory',GPU='NVIDIA H100 NVL MIG3g.47gb',GPU_allocation=dict(CPUs=22,memory='63G',torch_CPU_threads=1),logical_bytes_not_physical_IO=True)
(out/'resources.json').write_text(json.dumps(resources,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
removed=[]
for name in ['software/energy-ml-retrain-stage92-fit.tar.gz','software/energy-ml-retrain-stage92-cal.tar.gz','software/energy-ml-retrain-stage92-test.tar.gz','ntuples/energy_ml_stage92/result_fit_kubeflow.tar.gz','ntuples/energy_ml_stage92/result_cal.tar.gz','ntuples/energy_ml_stage92/result_test.tar.gz']:
    p=root/name
    if p.exists():removed.append(dict(path=name,bytes=p.stat().st_size));p.unlink()
if removed or not (out/'transfer_cleanup.json').exists():
    (out/'transfer_cleanup.json').write_text(json.dumps(dict(removed=removed,only_own_collected_duplicates=True,actual_payload_sources_verified='precloseout_source_validation.json',full_results_preserved=True),indent=2)+'\n')
# Full document accounting, including inventory itself. Keep precise logical byte count.
paths=[Path('.gitignore')]+[p for p in Path('ml').glob('*retrained_posterior.py')]+[Path('ml/retrain_accurate_posterior.py'),Path('ml/time_stage92_worker.py')]
paths += [p for p in Path('AnalysisZipFramework/submission').glob('*retrain*') if p.is_file()]
paths += [Path('docs')/n for n in ['nu_mu_energy_ml_revised_roadmap.md','nu_mu_energy_ml_information_budget_plan.md','nu_mu_energy_ml_next_step_prompt.md']]
paths += [Path('workbook/2026-11-04_stage92_accurate-loss-retraining.md')]
paths += [p for folder in ['workbook/stage92_energy_ml','ntuples/energy_ml_stage92','ml/artifacts/stage92'] for p in Path(folder).rglob('*') if p.is_file()]
paths=sorted(set(paths+[out.relative_to(root)/'storage.json']))
inventory=out/'storage.json'
for _ in range(8):
    rows=[dict(path=str(p),bytes=p.stat().st_size if p.exists() else 0) for p in paths]
    size=sum(r['bytes'] for r in rows)
    inventory.write_text(json.dumps(dict(files=rows,total_bytes=size,limit_bytes=20000000,includes_inventory_and_changed_full_documents=True,logical_bytes_not_physical_IO=True,NPZ_in_Git=False),indent=2)+'\n')
    if inventory.stat().st_size==next(r['bytes'] for r in rows if r['path']==str(inventory.relative_to(root))):break
else:raise AssertionError('inventory byte count did not converge')
assert size<=20000000
print(json.dumps(dict(measured_outer_CPU_s=total,retained_bytes=size,removed_bytes=sum(r['bytes'] for r in removed)),indent=2))
