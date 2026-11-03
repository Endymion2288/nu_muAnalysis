# 下一轮执行Prompt：stage79 实际脉冲形状与相对时序的信息审计

先读AGENTS.md、[stage78报告](../workbook/2026-11-03_stage78_nested-risk-complementarity.md)、[stage77研究复盘§5.1](../workbook/2026-11-03_stage77_research-reassessment.md)、路线§59/信息预算§39及[请求](../workbook/stage78_energy_ml/followup_input_request.json)。最新实测stage78，Q_local低E改善但未联合过传统/困难尾，继续F7。结束固定组合与stage74分类器续调，0专家/深度/seed/q/温度扫描。

## 1. 唯一问题与边界

本轮0能量训练，实际回答：当前nominal ν PHYS在积分/pz/位置/状态之外，是否生成并记录了可审计、跨来源可复现的脉冲形状或相对时间变化？这不是能量风险收益已测，也不是另一个电荷总和/旧CaloNu波形/点云池化试验。必须交实际同事件测量与生成机制证据，或具体字段/条件缺口，不能用一份分支目录结束。

只沿stage55已知nominal来源manifest、既有canonical train身份/source/inputentry/incoming和实际writer/模拟/读出源码入口，优先已有匹配build。不得递归扫全EOS、不取test/cal/eval/locked新身份、不访问新PHYS增补或K RDO，不做重建/生成/F7推理/谱toy/SHA。stage78原62/角色/全部尾/缺失及用户变量合同不改。

## 2. 先有界核实真实语义与成本

旧stage11 schema出现width/baseline_rms/raw_peak/localtime只是线索；当前nominal可用性、单位、生成机制、有效率与成本未测。总≤40个事前身份QA，核run/event/inputentry/leading及原incoming联结、分支单位、typed sentinel/domain/status/dependency、合法负值、波形积分与宽/峰/时的关系。不能把另一个重建的同名列当共同定义。

定位实际使用的脉冲生成、模板/叠加/噪声/截断和fit算法及其版本/条件；确认这些新列是否随真实活动改变，还是固定模板/电子学设置/低信号拟合产物。不以当前DB默认、旧schema或data观察替代本nominal证据。若字段/条件缺失，保留失败来源与未测标志，列最小需要的实际输入，不静默换族或夸称可用。

相对时间需共同clock、可验证固定通道offset与可靠μ路径/飞行项；没有依据则先保留原时间并说明不可解释，不能按truth E/y反调offset。弱/无效信号时间保持缺失，不fit补raw；signed负积分可合法，不随意作小/负分母比。baseline逐点RMS不能直接作积分电荷误差，后者需要窗口/相关性；额外活动含次级/背景/噪声，不全称hadron。不可用超相对论μ飞行时间直接测50GeV以上能量。

同时实测代表性wall/CPU/RSS/读取请求字节与basket复用。先验证实际语义/小成本，再冻结正式提取，不能仅按前缀线性速率保证尾成本。

## 3. 一次冻结的同事件有界测量

QA通过后，在合法且可联结的已知train输入内，seed2026110379冻结≤2048个既有train身份、≤12个明确来源；按reco pz50–100/100–250/≥250、component/source事前分层，记录非零包含概率和可用池。不得按新形状/时间、truth E/y、坏残差或拟合结果选/换身份；保留原抽样中的弱信号、missing和尾。支持不足如实报告，不取有利prefix/凑产额。

只读取所需波形摘要及联结/原62/状态/路径字段，按source/basket聚合请求，不保留全波形或ROOT/PHYS副本。逐事件匹配原raw/Calo表示，原62逐值/NaN一致；一次方纵向/模长仅pz0，11signed raw/VetoNu reduced，typed/status/dependency NaN、合法负数、缺一Calo总和NaN原合同保持，不二次缩放Calo。

冻结一族形状/相对时序测量定义，先解释各量物理含义/单位和有效性；不多组参数/特征扫描。测给定积分、pz、位置/状态下的形状/时间条件变异、跨来源/组件稳定性、missing/饱和/弱信号及模板退化。可引用原incoming E/y作事后分层描述，但不得用其拟合响应、定义尺度/offset/选择或称训练收益。少量同来源不能冒充新独立运动学。

## 4. 预算、验收和下一分流

拟议≤4Condor、每≤2CPU/3000MB、CPU累计≤7200s、wall/job≤3600s、实际输入≤10GB、紧凑最终≤10MB。仅上限，成本/可完成性尚未测；QA后按实测冻结worker硬上限及最终ClassAd，批量走Condor。一次冻结测量，不自动重试失败源/改变政策或扩大输入。若无法在预算下交付，写具体输入/资源缺口，不能将未读取者记物理0。

验收至少包括实际事件联结/原62闭合、真实单位/生成语义与状态、同积分条件变化或模板退化证据、来源/抽样概率/有效N、缺失与成本/产物。描述性变异本身不证明增量能量信息，必须明确局限。若有可审计物理变化，下一阶段才冻结一次匹配训练政策/容量的基线vs＋这一族信息消融及原门槛，不能现在暗加能量fit。若无可用变化或缺条件，如实给具体结论/最小实际输入，不自动换任意特征/架构。

中文stage79 workbook先记录实测/单位、输入/语义/条件/命令、物理与程序解释、资源/I/O、样本及局限和唯一下一合同，再和代码/紧凑表图本地Conventional Commit，不push、不外发，不连开后续生产。

实际π/K开发支持继续按[独立协议](nu_mu_energy_ml_support_delivery_prompt.md)准备，但本轮不自动执行；真正未开发确认仍需实际parent/subfile/seed/角色/曝光，共同raw/stage54、Calo、interaction/FSI/材料、接受度/背景不因新信息审计取消。

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
