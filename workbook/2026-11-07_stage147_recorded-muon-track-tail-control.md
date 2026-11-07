# Stage147：μ根尾部的记录轨迹匹配控制

## 阶段目标、输入与冻结方案

沿 Stage132 §5.5 和 [Stage146 后续合同](stage146_energy_ml/next_execution_contract.json)，区分两个问题：事件的初始根是否为 μ，以及选中的重建轨迹是否记录为匹配 μ。前者已在 Stage146 对4096父认证保留图，本阶段检查后者。不得因尾部大活动就先认定选中了 e/γ，或直接标为强子活动。

使用同一个 MC100012 nominal100 GeV PG PHYS：`/eos/experiment/faser/sim/mc24/particle_gun/100012/phy/s0012-r0023/FaserMC-MC24_PG_muon_fasernu_100GeV-100012-00000-00004-s0012-r0023-PHYS.root`。原 Stage146 缓存 `ntuples/energy_ml_stage146/event_records.json.gz` 提供全部身份、选中entry、根匹配、分组及固定评分。没有新读取 raw15 或重新计算评分，不使用训练函数。

[本阶段协议](stage147_energy_ml/protocol.json)固定先64条schema／向量对齐，再同一作业前4096条。读取 `t_pdg/t_barcode/t_pdg_parent/t_barcode_parent/t_truthHitRatio/t_pz`，按最高 `Track_pz0` 索引取与原选择相同的轨迹；与 Track_pz0 向量长度不同、无匹配PDG0、非正barcode均显式保留unknown。只将记录的barcode与已由p3/顶点精确匹配的根barcode比较，绝不按barcode数值推父链。

−999等沿用typed NaN，signed PDG／动量／坐标的合法负值不统一删除；记录的hit fraction需在[0,1]，否则只将该质量量置unknown，不改变响应原分母。0.8只作事前固定质量诊断，不作新cut或模型输入。正式ν的pz0-only／raw／status及原选择保持。

`t_pz`是所匹配truth粒子生产点的pz，`Track_pz0`是重建首状态的pz；输出比值差 `pz0/t_pz−1`。两者未认证同一测量面，**不能将其差直接称为tracking bias、resolution或已测辐射损失**。这些truth字段仅供MC诊断，不进入部署模型。

## 实测schema、身份与匹配

64条小测试所需字段齐全，六个t字段的向量错位均0；读取211066 B，0.343852 CPU秒／0.772299 wall秒。完整4096条同样无缺字段、无错位，读取346857 B，0.396106 CPU秒／0.481251 wall秒；ROOT basket使小测试读取量并不按条数比例缩小。

[实际汇总](stage147_energy_ml/summary.json)确认原4096身份、原3612选中entry以及两评分四分组的原留出／可评分／报警计数全部精确。3612 selected **全部记录为 μ truth 匹配**，非μ匹配、无匹配和根未知均0；invalid hit ratio及非正barcode计数均0。全体可评分留出878条的barcode均直接等于已核初始μ根barcode，记录的hit fraction均不低于0.8、中位1.0。

这沿用了ntuple已有truth-matching语义。本阶段未重建匹配器、检查逐PRD真实性或测量关联概率；记录的hit ratio为1也不能自动认证真实covariance、同面动量或空间关联不确定度。

## 固定响应尾部结果

完整[40行表](stage147_energy_ml/heldout_track.tsv)保留 all／记录μ／记录非μ／关联未知／根未知，包括全部0分母行。计数及Wilson95与Stage146精确保持；下表括号为百分数区间：

| 分组 | 原留出／可评分 | 记录μ且直接根匹配 | Q15报警 | Qshape30报警 | hit fraction中位／低于0.8 |
|---|---:|---:|---:|---:|---:|
| all | 897／878 | 878／878 | 26/878 [2.02874,4.30363]% | 25/878 [1.93599,4.16959]% | 1.0／0 |
| overflow | 17／16 | 16／16 | 10/16 [38.6410,81.5188]% | 11/16 [44.4044,85.8354]% | 1.0／0 |
| high activity | 6／6 | 6／6 | 6/6 [60.9666,100]% | 6/6 [60.9666,100]% | 1.0／0 |
| 重建pz50–100 GeV | 766／759 | 759／759 | 22/759 [1.92183,4.34965]% | 21/759 [1.81667,4.19264]% | 1.0／0 |

比例点值、Wilson、原未评分分母均在表中，不把可评分878冒称原留出897的全事件效率。此四分组不互斥，不能相加。

另一个实测诊断为相对生产pz差，中位无量纲：

| 分组 | 全部可评分 | Q15报警子集 | Qshape30报警子集 |
|---|---:|---:|---:|
| all | −0.048462933 | −0.063266830 | −0.079890656 |
| overflow | −0.090226739 | −0.090226739 | −0.084879331 |
| high activity | −0.141473811 | −0.141473811 | −0.141473811 |
| pz50–100 GeV | −0.054633913 | −0.076652406 | −0.084879331 |

全体和报警各组的hit fraction中位均1，低于0.8数均0。高活动组存在较大的负相对生产pz差，但未计算同面truth、逐材料能损／辐射过程或协方差pull；这些项目明确为**未测量**，不对表中差作因果解释或显著性宣称。

## 阶段结论

**在这个固定PG源及已有ntuple匹配记录下，尾部报警并非由“把非μ轨迹选作leading轨迹”解释。** 连同Stage146，它们属于已核μ初始根、且leading轨迹记录为匹配初始μ的控制。当前Q15／Qshape30大残差不能单独用作其他根活动判据。

这个结论只排查了一个具体程序／身份解释。波形截断、随机μ能损、point均值／协方差模型及真实轨迹状态误差仍未分离；overflow和high-activity本身也由同一响应定义，不能将其条件报警率与全体5%目标等同。Wilson为本源有限计数参考，不含源／研究选择／相关系统。没有证明某种新实际观测无用，也不因6例就关闭所有联合响应研究；同样不继续改本固定评分的阈值、树或网络来隐藏尾部。

## 执行、资源、存储与验证

```bash
python3 ml/stage147_submit.py
python3 ml/stage143_monitor.py --stage 147
# 从XRootD运输结果到/tmp后解包；终态核对后
python3 ml/stage147_finalize.py
```

单job9674493、1start、exit0，**4 scheduler CPU秒／11 execute wall秒／0GPU**，低于60 CPU秒预算。请求1 CPU／4 GB，站点实际RequestCpus2／内存6 GB，BLAS各1线程。主逻辑2.588954 CPU秒／3.125305 wall秒，GNU进程3.76 CPU秒／6.25 wall秒，峰RSS98044 KiB；不与scheduler重复相加。无新G4、ν预测、能量fit、响应fit或reserved访问。原模型、阈值、split未修改。

目录为 `~/condor/nu_muAnalysis/stage147/`。核任务终态后，将尾部见证JSON原文本精确gzip为 `ntuples/energy_ml_stage147/tail_witnesses.json.gz`，1196 B；不提交事件载荷。记录了原overflow／high-activity留出者的身份、匹配和既有评分，未另存raw数组或xAOD。源码胶囊 `software/stage147/source_snapshots.tar.gz` 6185 B；删除426446 B重复运输／分散见证文本，Stage146合并记录和原输入保持。见[存储审计](stage147_energy_ml/storage_cleanup.json)。Python语法、文档链接和diff空白检查通过。

## 下一工作与未完成项

Stage132 §5.5中，actual covariance／逐PRD关联不确定度、宽动量且匹配生产的μ控制、随机响应及ν／data适用性仍未测量。这些不能由ntuple的truth匹配字段或当前100 GeV单源补齐。当前固定point表示不晋升其他根判别或能量模型，不再扫描相同评分。

独立推进§5.4一个明确未覆盖的方法控制：[Stage148合同](stage147_energy_ml/next_execution_contract.json)只在既有4032证据内审计role1、按原frame顺序固定至多一个同时含μ／其他根Ecal响应的父，沿实际SD标签和官方8-PMT噪声流验证混合来源的ADC／同窗模拟加和。没有支持就记录0，不换库存；all-time混合未必是同channel有限窗混合，须如实报告。原seed／旧字段／HITS闭合和选中参考缺失保留，无新独立ν／fit／阈值改变，1000累计CPU秒、不增加父数或预算；本阶段尚未执行Stage148。

本阶段没有解决低能可部署优势。真实乳胶匹配、曝光GRL、背景、全生成接受度、相关系统辅助约束和独立生成确认仍缺；§5.4总体及Ecal混合控制尚不完整。Stage87 direct62、原1.05/1.01/1.03与八层三尾+2 pp、Stage137双低箱5%扩大门保持；全部K／角色、pz0-only、raw11、typed NaN／合法signed、非0 status无timing、Calo缺失及reserved关闭保持。整体goal仍未完成。
