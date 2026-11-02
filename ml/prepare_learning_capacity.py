#!/usr/bin/env python3
"""Freeze the full-support capacity experiment before examining new paired residuals."""
import csv
import json
import subprocess
from datetime import datetime,timezone
import numpy as np
from learning_capacity import REPO,CACHE,OUT,load_inputs
from train_bdt import write_table

CACHE.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
path=REPO/'ml/configs/learning_capacity.json';assert not path.exists(),'Do not redefine a frozen experiment'
old=json.loads((REPO/'ml/configs/calonu_information.json').read_text());d,x=load_inputs()
folds=list(csv.DictReader((REPO/'workbook/stage42_energy_ml/source_folds.tsv').open(),delimiter='\t'))
for r in folds:
    m=d['group']==r['group'];assert m.sum()==int(r['N']) and (d['fold'][m]==int(r['fold'])).all()
assert len(folds)==81
for part,name in [('A','A0'),('B','I0')]:
    for f in range(3):
        p=REPO/f'ml/artifacts/stage42/{part}/{f}';assert (p/(name+'.ubj')).is_file() and (p/'predictions.npz').is_file()
    assert (REPO/f'ntuples/energy_ml_stage42/{part}_predictions.npz').is_file()
cfg=dict(stage=50,starting_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),frozen_utc=datetime.now(timezone.utc).isoformat(),
         input_cache='ntuples/energy_ml_stage42/development.npz',events=14309,sources=81,selection='all existing stage42 A events; no subsampling',
         support_level='source-disjoint development comparison; all sources previously exposed; not independent test',
         seed=old['seed'],rounds=old['rounds'],xgboost=old['xgboost'],train_role=old['train_role'],calibration_role=old['calibration_role'],
         candidates=['L3_F6z','L5_F6','L5_F6z'],baseline='L3_F6: cached stage42 A0',max_formal_fits=9,max_smoke_fits=1,
         fit_wall_limit_s=120,bootstrap_replicates=500,energy_edges_GeV=old['energy_edges_GeV'],
         common_B_calibration='current A0 evaluation-fold model predicts exact B-cal subset; mean log offset; I0 original B-cal offset',
         original_probability_mapping_reconstructions=0,gate=dict(focus='100<=reco_p_GeV<1000',minimum_relative_log_RMSE_gain=.02,paired_source_CI025_above=0),
         truth_inputs='continuous vertex_z_mm in oracle columns only',ROOT_HITS_reads=0)
path.write_text(json.dumps(cfg,indent=2)+'\n')
records=[]
for f in range(3):
    for support,m in [('A',np.ones(len(x),bool)),('B',d['selected'])]:
        for role,k in [('train',(f+1)%3),('calibration',(f+2)%3),('evaluation',f)]:
            take=m&(d['fold']==k);groups=sorted(set(d['group'][take]))
            records.append(dict(evaluation_fold=f,support=support,role=role,N=int(take.sum()),sources=len(groups),groups=groups,
                                component_N={c:int((take&(d['component']==c)).sum()) for c in ['pi','k','charm']},
                                energy_bin_N=np.histogram(d['truth_E_GeV'][take],old['energy_edges_GeV'])[0].tolist()))
write_table(OUT/'source_roles.tsv',records)
summary=dict(events=len(x),sources=len(folds),focus_events=int(((d['reco_p_GeV']>=100)&(d['reco_p_GeV']<1000)).sum()),
             B_events=int(d['selected'].sum()),remainder_events=int((~d['selected']).sum()),feature_columns=x.shape[1],fold_N=np.bincount(d['fold']).tolist(),
             component_sources={c:len(set(d['group'][d['component']==c])) for c in ['pi','k','charm']},
             cached_A0_I0_models_available=True,new_residuals_examined=False,old_test_opened=False)
(OUT/'input_audit.json').write_text(json.dumps(summary,indent=2)+'\n')
(OUT/'protocol.md').write_text('''# stage50 结果前冻结协议

依stage49复盘、修订路线§31/信息计划§16，只做一次学习能力对照。
使用stage42全部A=14309例/81来源，不作4000例或21来源抽样；原F6全部65项，不加stage44的22项。
原fold、eval=f/train=(f+1)%3/cal=(f+2)%3、最高pz leading/含lead truth fiducial/PMT veto/unit MC不变。
重点100–1000 GeV，100–250/250–1000及>=1TeV参考；Eν不封顶，全部y/proxy失败/缺失/尾部/最高箱保留。
先A0与I0在B同3703例比较原offset；再由当前eval-fold A0对真正B-cal预测拟合共同B-cal offset。
不能用cal的另一fold OOF预测代替；不看B-eval标签调offset。校准/训练人数与组成详source_roles.tsv。
完整A2x2：L3_F6复用A0；L3_F6z、L5_F6、L5_F6z各3折，固定400轮，只改变depth3->5，种子等全同。
9新正式能量fit+1小smoke，正式每fit<=120s，smoke仅L5_F6 20轮/200train/200cal/100eval。
不早停、不扫seed/深度/轮数，不重建概率映射/六箱谱、分类器或新ROOT-HITS/生产。
所有A候选用同A-cal mean-log offset，正式train/cal/eval来源无交叉。
报告完整A、B及全10606剩余事件，避免只靠特殊抽样作重要判断；这些仍是开发支持，不叫blind。
重点及原p/Eν/y/z/component/proxy逐层MSE/RMSE、mean/median bias、R68、两尾、来源配对区间。
500次component分层来源bootstrap，同支持全部模型共draw，条件于固定模型/offset，未含重训/校准不确定性/系统/选择。
报告L5_F6对L3_F6、各学习器z增量及G_L3-G_L5，G=MSE(F6)-MSE(F6z)；非互信息或唯一因果份额。
实用候选重点改善>=2%且95%下限>0；阴性不称信息不存在，不能事后换指标/加网格。
连续z仅oracle，不混truth p/方向/PDG/matching，不用truth_st1估材料能损；代理非barcode-confirmed。
结果后结束容量问题；按证据冻结reco候选或进入全81来源短段角度/会聚新信息实验，不机械继承HITS4000预算。
中文报告先写再Conventional Commit，记录真实资源/单位/命令/输入产物/限制，更新路线与Prompt，不推送。
''')
print(json.dumps(summary))
