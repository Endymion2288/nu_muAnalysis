# 下一轮执行 Prompt：stage85 共同 data/MC tracker 响应与占据控制

先读 `AGENTS.md`、[stage84报告](../workbook/2026-11-03_stage84_full-support-fit.md)、[stage85研究复盘](../workbook/2026-11-03_stage85_research-reassessment.md)、路线§66、信息预算§46及[输入合同](../workbook/stage84_energy_ml/followup_input_request.json)。本轮只执行共同 data/MC tracker 读出与 occupancy control；**0 能量 fit、F7 新推理、ν replay、GENIE/G4、谱 toy、data 反调 BDT，也不自动执行 stage86。**

## 1. 本轮定位：响应/域偏移证据，不是低能修复实验

stage84 已用原 41447＋全 7720 新支持（π6704/K1016、26 来源）完整训练 49167。主 eval 50–100/100–200/all/低 pz log-RMSE 为 0.313532/0.265800/0.295944/0.502276；相对传统低能 95% 上限为 2.498753/1.242889，仍未恢复。低能新增支持约 24%，训练内最低能 median bias 仍约 +15.6%，所以关闭无条件随机扩样、架构和 seed 扫描；但这不证明数据量无关、响应已认证或信息达到极限。

stage78 的专家组合显示错误互补，stage79–80 显示真实 hit-time convolution 和有限 pulse variation，stage53 显示 on/off 噪声不能解释全部 data/MC 差异。本轮的唯一新问题是：在共同定义、共同分母和实际 collection 下，data/MC 的活动与响应差异能否被量化。100–1000 GeV 单 μ 控制不能直接替代 50–100 GeV ν shower 或强子响应校准。

## 2. 完整验收与 stage85 后分流

按下方保留的 stage54 §1–5 执行，先 ≤40 个身份 QA，再冻结 data2048 和单一关联排除定义。必须交付真实 active-channel/event、孤立 strip/cluster、timebin/大小、站间相关、run/来源/p/位置分层、两臂支持差异和来源重抽样区间；不能用 metadata 清单、DB 参数、无 SDO 或未配对活动冒充纯 noise。

stage85 结束后只允许三种分流：

- **A：可识别 response variant。** 共同 collection、active-channel 分母和条件差异均有实际证据。下一阶段另立一次固定 physics-constrained transfer posterior 合同：bounded residual/shrinkage 与 hurdle/zero-inflated transfer mixture 只做预定比较；不继续随机扩样或架构网格。
- **B：只有条件活动/含背景上限。** 继续报告 PHYS 条件活动及上限，把它作为 response nuisance envelope 的边界；不能把它当纯电子噪声，也不能先做“噪声修正”训练。
- **C：当前定义不可识别。** 明确缺少的 quiet/random trigger、共同 collection、coverage 或 active-channel 条件，并停止 noise 支线；转入带未识别 response nuisance 的 transfer posterior 研究，不追加 occupancy 参数扫描。

无论 A/B/C，stage85 都不自动启动 stage86，不改变历史 F7、四期 support、传统估计和困难事件保护。

## 3. 研究方向的固定原则

后续 transfer posterior 的目标是学习可见缪子能量与转移能的条件分布，而不是继续把全区均值回归当作唯一目标。模型可预测低 transfer/大 transfer 状态的软概率、非负转移或有界转移比例，并输出点估计、68/90% 区间与 tail 概率。能量先验修正与 data/MC domain reweight 必须分开：前者用预先固定的 `pi_target/pi_train` 做 prior stress test，后者只有在共同 control 变量可比时才用 classifier density ratio，并报告 clipping、ESS、closure 和来源留出。

当前 62 维标量 ntuple 先以 BDT/小型 MLP/MDN 为候选；Transformer/GNN 只有在逐 hit/时间/几何输入和 response 语义真实可用后再评估。低 pz 必须同时保留真低能和真高能/high-y 两侧，不能按 pz 硬切换传统估计。所有新收益、功效、资源、systematic 和 coverage 在实际测量前写“未测量”。

以下保留的 stage54 原后缀逐字不改，仅进入该支线时适用。

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
