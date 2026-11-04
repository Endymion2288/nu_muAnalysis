# 下一轮执行 Prompt：stage90 可微准确marginal likelihood与梯度认证，0fit

先读`AGENTS.md`、路线§71、信息预算§51、[stage89实际报告](../workbook/2026-11-04_stage89_full-accurate-posterior.md)、[全量数值表](../workbook/stage89_energy_ml/numerical_summary.tsv)、[全cal闭合](../workbook/stage89_energy_ml/closeout_validation.json)和[输入/验收](../workbook/stage89_energy_ml/followup_input_request.json)。**唯一任务：在保存的固定head上认证一个可微准确marginal log-likelihood及其梯度，0能量fit/校准优化/网络forward/新test评价/ROOT/生成，无新样本前置。**

## 1. 已测结论与边界

stage89原cal11612/test13189全部数值认证，缺失6/5和困难/K保留，0重试。GH32 PIT/quantile/log-density超限6075/10636/7403，最大.039168732/.218637202/3.732729847。准确test最低能/第二低能/all为.169296/.231281/.326783，同低pz真高能/high-y .828213/.807754；最低能仍差于传统.145661，总体/困难差于同split direct。第二低能/GH32条件收益小，all/high-y小幅变差，不晋升模型。总体coverage68.819244%/90.951065%不替代PIT偏移或高端22.343750%/59.947917%欠覆盖。

完整cal GH32 training-prior NLL−.063295544复现旧目标至1.387779e−17，准确−.086449009；这说明目标值确实变了，**不说明原b/T已重新最优，也没量出训练梯度偏差**。推断积分已修，不能未经认证就重复原GH32训练或归因数据无关/信息上限。原split/test是已研究池，不是新blind；source95仍不可估，不能靠更多incoming draw补齐。

## 2. 固定输入和实施范围

- `ml/artifacts/stage87/{posterior_parameters,predictions}.npz`与原`split.npz`，原stage88固定40train＋512cal等间隔row、role/weight/pz/truth；可直接复用`ntuples/energy_ml_stage88/input.npz`并逐项核对stage87。该552无missing/wave/Calo-invalid，不伪造覆盖。本任务不打开test作新的候选评价，不计算全量quantile或多个prior。
- 训练点固定b=0/T=1；校准点固定b=.011721733230708156/T=1.2001641697078562。模型head/角色/名义prior不变；训练原−joint−.25marginal定义不变；训练/校准均使用原training-prior的raw marginal密度，nominal prior不进入这个优化目标。truth只用于监督目标审计，不变成部署输入。
- 在truth能量处计算marginal log-density与对15个原head输出及b/T的梯度。建立**一种**可微准确实现，以未改动stage88自适应参考核值、独立双步长差分核导数及其不确定度；不得只因autograd能运行就认证。积分节点/截断边界的导数处理需要实际验证。
- 原GH32值与梯度是被审计项，不再扫64/128/256挑节点。记录值/梯度误差分布、方向/尺度及其对原−joint−.25marginal loss的贡献；最终head点的误差不是整个训练轨迹的已知偏差，也不能据512cal判完整cal最优。

## 3. 先QA、后冻结与资源

≤40固定cal先做实际包/身份/单位/原GH32复现与精确值/双步导数QA、CPU/wall/RSS计时；无optimizer step。QA后冻结单一实现、样本/参数点和参考导数精度规则，建议log-density绝对误差≤1e−6、梯度|差|≤1e−4＋1e−3|参考|；参考差分误差另报，不达标不能静默放宽或只保留容易行。

正式建议≤1Condor、1CPU3000MB、MaxRuntime1800s、累计CPU1800s（含QA）、最终≤20,000,000bytes。按实际QA确认准入，重计算通过Condor；资源/导数通过率目前未测。避免逐节点/逐参数大网格和重复head/ROOT，先保存紧凑分块检查点，报告失败不重算已完成积分。若预算/精度无法交付，准确记录具体缺口和最小后续输入/实现，不自动扩大网格或提前训练。

## 4. 验收与交接

完整固定552的值/梯度或明确未认证项、参考精度、原GH32闭合、原权重/角色、实际成本与紧凑产物交付；单一可微loss能复用或解释具体失败。只有数值认证后才提出一次同模型训练/校准的另冻合同，**stage90自身不fit、不优化b/T、不按test选先验/损失/模型、不自动进入stage91**。此阶段也不证明低能恢复、真实response认证或独立确认。

写中文stage90 workbook，实际数值/单位/命令/资源/失败/下一输入与验收，与代码配置证据本地Conventional Commit，不push。原pz0-only一次方动量、允许px/py/q/p/弯折、raw11/typed NaN/合法负raw/Calo缺项、pz>50GeV/困难侧与已交付1016K保持，旧K生产时限不恢复。原stage54五项只读，以下后缀逐字保留。

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
