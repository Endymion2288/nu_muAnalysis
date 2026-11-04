# 下一轮执行 Prompt：stage101 有界研究复盘，不自动延长collection或训练

先读AGENTS.md、路线§82、信息计划§62、[stage100报告](../workbook/2026-11-04_stage100_paired-activity-information.md)、stage98研究修订和stage99实际报告。本轮是研究判断阶段；不再补A，不重做B，不自动开始新能量实验。

## 1. 已确认事实

Stage100恰一次替补A，旧B不变；原2048 train/cal incoming/24source，train L/H65/82、cal20/46。A127维/B211维；42新增collection值在train/cal均已填充且有变化，B的51次分裂却全部用原SpacePoints/Veto10_raw_charge/Veto20_raw_charge。两格100树执行完全相同，2048预测逐位相同，cal logscore .346455633/Brier .101254665、配对差0[0,0]。名义2%train阈值cal L0/20、H38/46，不认证总体2%误判。

按事前规则停止当前PHYS collection摘要族扩展，不放松正则、加树/seed、扩提取或转GNN来追分；这不是新活动无信息或物理上限的证明。原生measurement/cluster ID、SP组成、原track/TSOS/actual covariance及有效读出仍缺；原scratch REC未持久化，同名官方REC未闭合。不要重扫EOS/重建/强配hitSet或造pull。

stage99已有强排序与概率产品：E94名义2%工作点开发test实际低能误判4.754309%、H识别91.725663%，最低能修正风险增量+.054973752；唯一T=1.08691603355改善NLL/coverage但点不变。stage94 E三seed point-best65/90/65与记录NLL最低50/25/35尚有目标差异，不证明继续训练或NLL checkpoint能解除point风险。stage96/97几何/联合消息主体条件区间含1；这些旧路线不重包装成新架构发现。

## 2. 本阶段唯一任务与输入

只读已提交Markdown、曲线/汇总TSV/JSON、源码和原论文，不读NPZ/ROOT或模型/逐事件载荷，不运行任何fit、网络forward、分类推断、概率优化、积分、native定位/提取或HTCondor/Kubeflow任务。无需恢复CERN环境。文献研究可检索网络，引用原文并解释当前小样本、条件误判、目标与响应边界，不移植他处性能。

具体输入：stage94学习曲线/point与概率选择记录；stage98研究报告；stage99已提交probability/PIT/point_risks/loss_decomposition/工作点汇总及原生来源缺口；stage100指标/结构审计、冻结协议和停止决定。保留既有source/X支持和研究选择限制，不重新估计分数或从test选gate。

必须交付：

1. 用现有证据区分概率checkpoint/训练目标未对齐与真正新增载荷缺失两条假设，明确已测和未测。固定均值的概率尺度变换不改变point风险；排序好不自动保证低误判工作点和联合能量风险。
2. 核阅相关原论文的可行方法和假设；不要求任意新模型名称或制造正结果，不从pilot阴性推导Bayes上限。
3. 至多提出一个下一阶段的具体可执行合同，或明确现有证据下的停止/所需产品条件。若拟议固定MDN轨迹同时保存NLL-best/point-best，须说明其购买的问题、输入/角色/训练次数/主比较/验收与资源上限，并承认point收益未证；本轮不执行。若需真实产品，列精确最小产品与关联证明，不以新样本或全环境重建作默认前置。

## 3. 物理与交付边界

原split/同incoming权重、全部1016新增K、缺源/困难/尾支持、pz>50GeV保持。第一幂动量只用pz0，允许原px/py/q/p/弯折；raw11/status/typed NaN、合法负raw/charge及module_eta=-1/Calo缺项保持。原两低能/传统上95≤1.05、all/direct≤1.01、≥200及困难/direct≤1.03和八层三向tail上差≤2pp不变。旧test已开发，source/refit/阈值估计/response/研究选择和未开发确认未因bootstrap闭合。

研究阶段验收为中文stage101报告：现有数值注明来自哪个阶段，不冒称新测量；证据/论文适用边界、具体下一合同或停止条件、未测量项目清楚。报告后追加路线/信息计划记录，本地Conventional Commit，不push，不自动执行后续实验。保留模型/事件缓存和原Stage54五项，历史正文只追加；以下Stage54后缀必须逐字保持。

## 保留的stage54 data占据支线

以下§1–5为尚未完成的原协议，仅进入该支线时适用；其中“本轮”均指stage54 data控制。保留其工具/缓存及当前实际工作树状态，历史“未提交”描述不能代替当前状态检查。当前低能优先级按上面的主任务，data可靠性交付仍需完成。

先读AGENTS.md、stage49审查§7、[stage53报告](../workbook/2026-11-02_stage53_tracker-noise-mechanism.md)、修订路线§35、信息计划§20，以及stage52/53的manifest、实际conditions和原生collection读取工具。本轮只做一次有界data占据/有效读出条件约束；不自动执行ν重放、能量训练或谱toy。

## 1. 已测结论与唯一问题

stage53使用12来源2048个100–1000 GeV μ，原HITS和原材料图补齐后，原RDO逐strip/timebin、六计数、选择及名义两次轨迹全通过。actual occupancy3.5e−5，threshold1fC，compression/readout1/1。只关NoiseOn、保留analog：每站平均少约1.3 cluster，station3>6从72.607%降18.750%，差−53.857 [−55.773,−52.036] pp；SP>12 −1.514 pp，segment>4与零相容。两动量层、两符号和12来源保持。53例退出选择，主要是重建动量越界，全部保留。

独立strip噪声确能产生MC额外cluster过量，却不能同时解释stage52 data的SP/segment较多。两轮混合不同，不能机械相减或从on/off反求occupancy。**本轮回答：真实data在可核实的共同读出定义下，对孤立strip/cluster活动及有效噪声占据能给出什么约束或上限？它是否足以定义一个有依据的响应变体？**

0新能量fit/概率映射、0ν重放、0新G4、0谱反演/toy/coverage。不得按data反调BDT，不将零噪声或on/off全差称为1σ，不恢复波形/架构/历史生产扫描。

## 2. 已知输入与有限metadata入口

- 既有`ml/configs/calonu_muon_files.tsv`中的6 data/12 MC来源；stage52完整18文件统计在`ntuples/energy_ml_stage52/source_histograms.tar.gz`。不要沿用manifest历史entry_stop前缀来挑data。
- stage53冻结2048个MC的sample与两臂紧凑摘要在`ntuples/energy_ml_stage53/replay_results.tar.gz`，用`ml/analyze_tracker_noise.py:read_result`回读；旧程序诊断在`pre_correction_nominal.tar.gz`。不重新生成名单、不重复做两臂重放。
- 原生工具`ml/replay_tracker_noise.py`及stage37/38读取器；已有源/entry/生成子文件联结不能只按重复run/eventID配对。data的实际REC/RDO对应关系需用原身份/指纹核实，不能猜一对多entry比例。
- 已知data日志在`/eos/experiment/faser/data0/rec/2024/r0022_log/{015838,016000,016923}/Faser-Physics-<run>-00000.rec.log`；stage36 production_audit记录了精确路径与release，stage52 source_semantics已核对应`d0b1b2dd`的branch代数。
- 只对这些已知production目录做有界metadata确认，找配套REC/RDO及collection schema。核actual几何/station/sensor、mask、active channels、timebin/cluster接受、trigger/filter。文件名noIFT、header默认和当前DB不能自动等同历史actual配置。不可用时列出最小缺失输入，不递归扫全EOS或恢复全部历史Athena环境。

## 3. 看data probe差异前冻结

1. ≤40个独立身份QA，仅核schema、单位、对齐/联结、collection、有效channel分母和I/O/计时；不扫描能量、半径或噪声参数。
2. 默认从6 data已知PHYS完整支持冻结2048个μ，100–250/250–1000 GeV均有来源覆盖；保留stage52独立四Veto tag、质量/几何和原动量定义，不按被测tracker活动取样。与stage53原2048 MC比较，明确来源/p/位置混合，必要标准化只用事前运动学，不按probe匹配。
3. 先明确真正共有的station/sensor与active-strip分母。IFT或collection不共有时独立报告，不能按同名branch强合并。有效mask/DAQ coverage改变必须进入分母，而非统一缩放cluster。
4. 只冻结一种有物理尺度依据的μ邻域/关联排除定义，测远离可靠轨迹的strip/cluster占据、timebin、孤立性及station间相关；无可靠传播/关联时保留未归属，不凭“无SDO”或“没配上leading”认定noise。
5. 未归属活动含真实次级、beam背景和漏重建粒子。缺quiet/随机触发或无偏时间窗时，只给**条件活动或可证明的上限**，不硬分解成纯电子噪声，也不把DB参数直接当data测量。空间sideband若不能分离污染，结论就是未识别，而非假定全是noise。

## 4. 指标、预算和验收

- 同一observable上报data/MC的每active-channel/event占据、timebin组成、孤立cluster大小/额外率、中央分位数/尾及来源/run、p、位置层；对μ条件及过滤边界明确限制，不测全tracker效率或ν shower闭合。
- 来源配对/分层重抽样500次，明确data仅6来源/3run的外推限制。不能以很多同来源事件冒充独立生产；稀少支持写明，重要判断不靠少数异常。
- 默认最多6并发Condor、每任务≤2CPU/6GB、累计CPU≤8h、实际输入≤10GB、紧凑最终≤20MB。QA后按实测冻结执行资源；完整读取/批量稀疏提取通过Condor。先试basket复用，计实际请求字节/ROOT读字节，不能把理论大小当I/O。不得保存RDO/REC/xAOD副本或逐hit点云。
- 目标样本/共同collection不可交付时，先说明覆盖与预算，交付可测的条件统计和具体缺失输入，不静默缩小成有利样本、不用metadata清单替代一切可做的物理测量。

**成功不要求得到一个非零noise最佳值。** 应能判断：data是否约束可信噪声范围；是否只有含背景的上限；或当前数据/定义无法识别电子噪声。只有有真实依据时才提出下一轮响应变体，不将on/off线性插值当标定或正式1σ。

## 5. 后续和交付

有可信范围后，下一阶段才对同事件ν做真实读出/重建变体，固定F6评价计数、动量、选择迁移、能量bias/R68/尾；不能给计数减常数或重训模型吸收失配。范围未识别则结束这轮有界控制，列出最小需要的quiet/calibration输入及仍可推进的预定可辨识谱目标，不延长成参数网格。

ν interaction/FSI、G4材料/输运、连续正向谱硬度及真正未开发生产确认仍是最终交付，单μ噪声结果不能替代。保留六箱自由谱未稳定的结论，不靠更多toy调覆盖。

先写中文stage54 workbook报告，包含实际样本/选择/单位/配置、数值/区间、物理与程序原因、命令/资源/I/O、产物和最小下一任务，再与代码/配置/紧凑表图本地Conventional Commit，不推送，不自动启动下一阶段。
