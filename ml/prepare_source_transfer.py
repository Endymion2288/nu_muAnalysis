#!/usr/bin/env python3
"""Freeze identity-only external-source development support before new predictions."""
import csv
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from calonu_inputs import manifest
from train_bdt import write_table

repo=Path(__file__).resolve().parents[1];out=repo/'workbook/stage48_energy_ml';cache=repo/'ntuples/energy_ml_stage48'
out.mkdir(parents=True,exist_ok=True);cache.mkdir(parents=True,exist_ok=True)
assert not (repo/'ml/configs/source_transfer.json').exists(), 'Do not redefine a frozen support'
with np.load(repo/'ntuples/energy_ml_stage42/development.npz') as z:d={k:z[k] for k in z.files}
files=manifest(repo);old_groups=set(d['group'][d['selected']]);groups=sorted(set(d['group'])-old_groups)
pools={g:sorted(np.flatnonzero(d['group']==g),key=lambda j:(int(d['run'][j]),int(d['eventID'][j]),int(j))) for g in groups}
chosen=[]
for k in range(max(map(len,pools.values()))):
    for g in groups:
        if k<len(pools[g]):chosen.append(pools[g][k])
        if len(chosen)==4000:break
    if len(chosen)==4000:break
rows=np.sort(chosen);assert len(rows)==4000 and len(groups)>=12
indices=sorted(set(map(int,d['manifest_index'][rows])));records=[]
for r in files:
    i=int(r['index']);g=r['group'];m=d['manifest_index']==i;take=rows[d['manifest_index'][rows]==i]
    old=g in old_groups
    exposure='stage35 fit; stage42 A training' if r['partition']=='fit' else 'stage35 '+r['partition']+' already exposed'
    records.append(dict(index=i,run=int(r['run']),group=g,partition=r['partition'],component=r['component'],
                        production='CaloNuMC/1ec47efe; FASERNU-CALONU; OFLCOND-FASER-05; s0015',
                        exposure=exposure,current_XZ_train_or_calibration=old,
                        eligible_source_external=r['partition']=='fit' and not old,available_N=int(m.sum()),
                        selected_N=len(take),assigned_fold=int(d['fold'][take[0]]) if len(take) else None,input=r['input']))
    if len(take):assert r['partition']=='fit' and not old
cfg=dict(stage=48,seed=20261101,starting_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
         frozen_utc=datetime.now(timezone.utc).isoformat(),support_level='source-external development replication; not blind or independent production',
         input_cache='ntuples/energy_ml_stage42/development.npz',selection='exclude selected source groups; group lexicographic; within source (run,eventID,cache_row); round robin to 4000; retain original assigned folds',
         max_events=4000,minimum_sources=12,indices=indices,source_groups=groups,energy_fits=0,target_calibration_fits=0,
         original_calibration_reconstructions=6,max_pilot_events=40,bootstrap_replicates=500,
         energy_edges_GeV=[100,200,400,800,1600,3200,6400],models=['local','oracle_z'],
         gate=dict(focus='100<=reco_p_GeV<1000',minimum_relative_log_RMSE_gain=.02,paired_source_CI025_above=0),
         new_truth_inputs=['vertex_z_mm (oracle_z only)'],new_HITS_reads=0)
(repo/'ml/configs/source_transfer.json').write_text(json.dumps(cfg,indent=2)+'\n')
names=json.loads((repo/'workbook/stage42_energy_ml/preparation.json').read_text())['feature_names']
fingerprints=dict(expected_p_GeV=d['reco_p_GeV'][rows],
                  expected_mu_xyz_mm=d['x'][rows][:,[names.index('ML_mu_'+a+'0_mm') for a in 'xyz']],
                  expected_SpacePoints=d['x'][rows,names.index('SpacePoints')],
                  expected_sp_shape_mm=d['x'][rows][:,[names.index('ML_sp_'+v+'_'+a+'_mm') for a in 'xy' for v in ['mean','rms']]])
np.savez_compressed(cache/'selection.npz',cache_row=rows,**fingerprints,**{k:d[k][rows] for k in ['run','eventID','manifest_index','group','component','fold']})
write_table(out/'source_exposure.tsv',records)
summary=dict(manifest_sources=len(files),manifest_partitions=dict(Counter(r['partition'] for r in files)),
             no_certified_unused_same_geometry_source=True,audit_scope='existing calonu_files.tsv + stage35/stage42 provenance; no EOS scan; nominal non-CaloNu geometry is not interchangeable',
             supporting_records=['workbook/2026-11-01_stage35_calonu-readout-information.md','workbook/stage35_energy_ml/source_audit.md','workbook/2026-11-01_stage42_calonu-information-budget.md'],
             support_level=cfg['support_level'],eligible_events=sum(len(v) for v in pools.values()),eligible_sources=len(groups),
             selected_events=len(rows),selected_sources=len(set(d['group'][rows])),
             component_sources={c:len(set(d['group'][rows][d['component'][rows]==c])) for c in ['pi','k','charm']},
             source_event_count_range=[min(len(rows[d['group'][rows]==g]) for g in groups),max(len(rows[d['group'][rows]==g]) for g in groups)],
             fold_N=np.bincount(d['fold'][rows],minlength=3).tolist(),new_predictions_read=False)
(out/'support_audit.json').write_text(json.dumps(summary,indent=2)+'\n')
(out/'protocol.md').write_text('''# stage48 预测前冻结协议

唯一问题：冻结X87与X87+连续真z的条件收益能否迁移到其训练/校准之外的来源？
依据stage47后的路线§29/信息计划§14/执行Prompt。无可认证新blind同几何来源；
现有manifest所有分区均参与过stage35，fit又参与stage42 A。只采用来源外开发复现，不能称独立生产或新blind。
来源/暴露详source_exposure.tsv，选择与UTC详ml/configs/source_transfer.json。
身份轮转取4000例，无标签/残差/p选择；同原最高pz、truth fiducial含lead、PMT veto/unit MC，不截Eν或丢难例。
先首pi/首K各20例特征pilot，复用stage44原22项函数/单位/半径，不增加新变量族。
完整提取CPU1 Condor，仅最小reco列、每文件一次打开；缺失branch/错身份不可填零或删例。
只加载stage44 local和stage45 oracle_z已存模型及原assigned fold。
6份原cal概率映射可确定性重建，必须对原3703预测精确回读；无新支持标签/先验适配，0能量fit/0目标校准。
真z只oracle；无truth方向/PDG/matching输入，不用truth_st1模长测能损。
重点100–1000 GeV Z对X相对log-RMSE改善≥2%且500次component分层来源配对95%下限>0。
同报all/p/Eν/y/z/component/运动学parent代理的N、来源、误差、bias/R68/尾、proper/Brier与六箱固定响应谱诊断。
barcode不可得不称primary-confirmed；≥1TeV参考。来源区间条件于固定模型/校准，不含重训/系统/开发选择。
不为有利结果增fit/重校准/重选来源。过门槛只建立此支持等级的迁移证据，不通过也不证明信息不存在。
先中文报告再Conventional Commit，更新两路线和Prompt，回读blob/clean，不推送。
''')
print(json.dumps(summary))
