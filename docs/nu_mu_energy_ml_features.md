# 当前模型输入契约：F7_pz0_raw_v1

按用户意见修订，固定清单与逐列有效域见[配置](../ml/configs/audited_features.json)，实际65→62列映射见[审计表](../workbook/stage56_energy_ml/feature_inventory.tsv)。实测、对照与限制见[stage56报告](../workbook/2026-11-02_stage56_model-feature-validity.md)。

| 输入类别 | 当前约定 |
|---|---|
| 动量模长/纵向量 | 仅`ML_mu_pz0_GeV`，来自分析的`LeadTrack_pz0`；基线`pz0/0.8` |
| 允许的其他参数化 | 保留前/后`px/py`、`q/p`、方向弯折；位置、几何方向与拟合质量保留 |
| 删除列 | `ML_mu_p_GeV`被pz0替换；删除`ML_track_p1_GeV`、`ML_track_pz1_GeV`、`ML_track_log_p1_over_p0` |
| 闪烁体 | 11个`*_charge`改成对应`*_raw_charge`；`LeadTrack_charge`是粒子符号，不在此替换中 |
| VetoNu reduced | 原始波形时间窗积分，保留；不是拟合电荷 |
| 缺失 | 按物理域、文档哨兵、波形状态与派生依赖置NaN；不补0、不删整个事件 |
| 有符号变量 | 保留合法的负坐标、px/py、q/p、粒子符号、模块eta及基线扣除电荷/EM能量 |

`ml/audited_features.py`负责统一构造与清理；`build`先按状态清理，再处理几何/比值依赖，最后`matrix`按逐列规则转换float32。训练与回读评价使用同一实现。
新模型内嵌完整feature_names和policy/version；旧65列F6不能直接套新列，保留作历史参照。后续训练以F7契约为起点，不从旧baseline/track_response配置重新引入已删除列或拟合闪烁体电荷。

[新基础snapshot配置](../AnalysisZipFramework/config/ml_audited_output_columns.yaml)配合既有`ml_definitions.yaml`与显式50GeV cuts；所需raw/status同时保留于data/MC公共列。Python补充track特征。没有修改原历史snapshot/配置以免破坏已有结果的复现。
当前F7验证模型只训练nominal完整支持；替代flux新PHYS曾按stage55存储约定清理，缺raw/status补充，历史混训模型未冒充F7或用拟合电荷代替raw填补。
选择仍沿用stage55（其中部分cut基于原拟合电荷），本轮修改的是模型输入。接受度、背景、data与强子shower响应尚未重测。
