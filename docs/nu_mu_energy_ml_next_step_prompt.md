# 下一轮执行 Prompt：stage85 实际共同 data/MC tracker 读出与占据控制

先读AGENTS.md、[stage84报告](../workbook/2026-11-03_stage84_full-support-fit.md)、路线§65/信息预算§45及[输入合同](../workbook/stage84_energy_ml/followup_input_request.json)。本轮进入下方保留stage54 data控制协议，完成尚缺的实际共同响应测量；**0能量fit/F7新推理/ν重放/GENIE/G4/谱toy**，不自动执行stage86。

## 1. 当前结论与为什么转向共同响应

stage84已用原41447＋全7720新增（π6704/K1016，26来源）完整训练49167，恰原3seed/400轮/unit direct logE/原62，0pilot；原cal8440一个global log offset .007550640，主pooled_cal，0新F7推理/来源OOF。新增低E182/845各增约24%，而eval两低E .313532/.265800、相对传统95上限2.498753/1.242889仍未恢复。all/F7 .998587 [.996663,1.000424]未测出显著增量，所有原五RMSE保护和七层总正负tail50通过；不能写所有门槛失败。主最低能32/208正tail占73.8522%损失，额外confirmed低transfer最低能tail上限+2.430147pp仍保留。

相对stage82full，第二低E比1.009817 [1.000854,1.018749]变差，最低能/总体区间跨1。关闭本固定完整支持实验、继续F7；不续扫更多规模/来源/seed/权重/架构。失败没有证明缺数据无关、24%已足量、完整响应已认证或物理信息极限。

共同data/MC读出可靠性一直未交付。stage53 on/off同事件证明独立strip噪声可贡献MC额外cluster，但on/off全差不是1sigma，也未解释data的SP/segment过量。现在用真实data检验共同定义下活动与有效占据是否给出约束；**不是已知MC低E退化原因**，100–1000GeV单μ控制不能直接替代50–100GeV ν或强子响应/效率确认。已有K已重建且入模，其旧时限/禁令仍被用户覆盖，不恢复为阻碍。

## 2. 输入、隔离输出与完整验收

按下方原stage54§1–5原文执行。只用`ml/configs/calonu_muon_files.tsv`已知6data（index12–17、run15838/16000/16923）、原12MC和stage52统计/原stage53固定2048同事件摘要；不重做MC两臂。先≤40独立身份核native collection/联结/单位、实际geometry/station/sensor、timebin/trigger/mask及active-channel分母和成本，再冻结data2048、原100–250/250–1000GeV两层与一个muon邻域/关联排除定义。按全部已知PHYS支持取样，不用历史entry_stop前缀，不按probe或data残差挑样本/匹配。

阶段编号和新产物统一为stage85（workbook报告/证据/缓存），保留stage54原协议文字。原五项未跟踪工作仅只读参考，不能改动/stage/提交或清理其路径；复用前核实际内容与协议，不把历史partial JSON当已完成产物。需要实现/修正工具时写新的stage85文件，使用现有匹配构建，批量走Condor。

必须交actual共同读出定义与真实计量：每active-channel/event孤立strip/cluster活动、timebin/大小/站间相关、来源/run/p/位置、两臂支持差异及500来源区间。没有quiet/random触发时给条件活动或可证明的上限，不将未关联、无SDO或sideband全称noise，不凭同名noIFT分母强合并。不以metadata目录清单替代可测统计；真入口缺失明确路径/collection/coverage/条件和最小需要，能测PHYS条件活动则说明其不等于原生strip噪声。

原资源为上限：≤6并发/每≤2CPU6GB、累计CPU8h、实际输入10GB/紧凑20MB，均须实际小QA和actual包后冻结；不是新成本测量。0ν重放/参数扫描或data反调BDT。报告需回答是否足以定义可信响应变体、只能给含背景上限、或当前定义无法识别电子噪声，不能制造一个非零最佳值。后续真ν响应变体另立合同，本轮不执行。

先中文stage85报告，再新代码/配置/紧凑表图本地Conventional Commit，不push/外发。保留原四期support、stage84三模型/比较和所有困难事件保护；独立支持协议及以下原后缀逐字保持。interaction/FSI/材料/接受度/背景与真正随机未开发确认继续，data控制不替代它们。

以下stage54原后缀逐字保留，仅进入该支线时适用。

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
