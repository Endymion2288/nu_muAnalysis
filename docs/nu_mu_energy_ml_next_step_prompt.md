# 下一轮执行 Prompt：stage94 输入、表示、架构与能量目标的五格实验

先读 AGENTS.md、[stage93 研究报告](../workbook/2026-11-04_stage93_research-reassessment.md)、修订路线 §75、信息计划 §55、stage87/92 报告，以及当前 split/weights/审计特征实现。**本轮任务是在有运行环境的节点完成一轮有限、可归因的模型比较；当前没有运行环境的本地终端不训练、不推断事件。** stage93 已用于研究复盘；旧 stage92 JSON 中“三 prior stress 唯一先行、0fit”不再约束本轮优先级，历史产物不改。不要重复数值认证链或自动进入下一阶段。

## 1. 要回答的物理问题

当前后验不是已证最优：2×64、41 项观测/85 输入、单 seed、固定 150epochs，训练目标为 joint+.25marginal NLL，点输出为 median；BDT 用 62 项输入。stage92 最低能传统/direct/后验 log-RMSE 为 .145661/.282644/.165630，但 all/direct/后验 .287491/.326058，低 pz 真高能 .658177/.826918，high-y .609395/.781673。准确 loss 修复的新/旧主要区间含 1，不能再默认积分是主瓶颈。

本轮区分输入、表示、架构方案及能量输出路线的影响，争取同时改善低能与困难侧。没有新独立样本不阻塞开发；新 test 是已研究池对本次 fit 的留出，不叫 blind，不据 test 选择 checkpoint、模型、prior、变换或 seed。

## 2. 固定输入和校准/选择边界

复用 stage87 89033 兼容记录、原 split/隔离/每 incoming 总权重 1；outer train/cal/test 保持 46575/11612/13189，唯一 incoming37556/10811/12125。missing21/6/5、全部1016新增K、高端、未确认、高-y、低pz真高E和所有尾完整保留。旧14435缺raw/status者不以fitted charge填回，无ROOT/新生成/重建/随机扩样。

保持 raw11、typed NaN、合法负raw、Calo缺项和状态掩码；一次方动量仅pz0，允许既有px/py/q/p/弯折，不加p0/p1/pz1或历史禁用动量比。恢复62输入只用现有审计列，不偷偷引入truth或不部署变量。62对41的新增族逐项列出。

看新候选指标前，将原cal按source分成cal_select/post，incoming冲突按事前优先级purge，记录用途、支持、隔离与子集权重；不按能量风险选择source。新子集人数/低能功效未测，先交付实际支持。outer cal全体仍保留作报告；不能声称它是独立确认。若无法可靠分开，预注册固定epochs，用完整cal做一次后处理，取消earlystop和候选选择，不借test补位。

有有效cal_select时，事前冻结最大300epochs、每5轮验证、patience30epochs及含两个低能和困难侧保护的排序；相同MLP臂使用相同optimizer规则。MDN用marginal NLL训练，同时记录NLL和对齐点风险，checkpoint规则预先固定。超参数是有界比较配置，不声称已最优。各点模型只在cal_post拟合一次共同定义的全局log-offset；MDN密度与点输出一起平移，报告校准前后。缓存BDT可用已存cal预测计算同样offset，不重训；原样传统/direct和同后处理对照分列，原风险门槛仍按原样控制。

## 3. 五格主实验，最多九个新网络fit

|格|输入/预处理|模型和训练目标|回答|
|---|---|---|---|
|A|41，当前median/IQR±20与掩码|2×64 SiLU，weighted log-MSE|点回归控制|
|B|62，与A相同规则|同A主干/目标|补齐输入是否有效|
|C|62，train-only typed log/log1p/asinh与掩码|同A主干/目标|数值表示是否有效|
|D|与C相同|TabM、weighted log-MSE；首轮不额外加embedding|结构方案是否有效|
|E|与C相同|同C主干，3分量residual logE MDN、marginal NLL|直接能量概率路线是否有效|

C的变换按变量物理域定义；正量、计数、有符号量分别处理，尺度仅从train得，报告变换和饱和率，不把合法负raw变0，不删尾。首轮不叠加数值embedding，否则不能归因C/D差异。复用ml/train_tabular.py已有TabM实现，重接当前loader/权重/特征，禁止复活旧fitted-charge输入。报告参数量与计算差异，不冒称等容量。

E预测u=log(Eν/GeV)−log[(pz0/.8)/GeV]的3分量Normal混合，用analytic mean/CDF/density；点能量为exp(mean logE)，不是mean E。不要强迫Eν≥reco pz，不按低pz硬切传统，不加zero-transfer点质量。E/C同时改变输出族与loss，不单独归因其中一项。

最多5个预注册单seed主fit；如有可靠cal_select，在打开新test前至多选2格各加2seed，总≤9新网络fit，seed和集成规则事前固定。没有有效cal_select则停在固定五格，test只报告开发探索，不事后补幸运seed。此次不加FT-Transformer/GNN/大预训练/辅助权重或prior网格。

## 4. 固定后验读出诊断与概率解释

可同时用stage92保存head/newbT、同名义prior比较median与exp(E[logE|x])，0新网络fit。stage76的旧score密度mean-log结果不是当前posterior的结果。新增moment只核自身固定小cal误差、尾界和成本；已有CDF认证不自动认证moment，不重开stage88–91。若成本不合适，此诊断不阻塞五格；不以training prior的简化矩冒充nominal重权后的矩。

正确后验PIT要求在X及X定义组中均匀，不一般要求在真E/y分组均匀。保留旧真值分组表/物理风险；后续看明确目标谱/权重下的总体完整PIT及cal预定义pz、Calo、活动、质量/缺失等X组，不能用真值组PIT不含.5单独否决后验。固定真E频率coverage若需要另建response区间，不靠本轮后验自动保证。此修正不意味着旧模型通过。

原三prior的准确bin/PIT/NLL/ESS可代数复用为诊断，不需要先做三谱全量quantile重积分；不按test选新谱。stage85的tracker data/MC条件活动已交付，缺active-channel/quiet触发不能反求纯noise，不重做此默认支线；stage73固定重权有低能收益和困难侧代价，不续边际权重网格。

## 5. QA、验收、资源和交付

先≤40固定train/cal记录，覆盖已有missing/status，检查schema、单位、权重、梯度/输出和实际计时，再冻结批量实现/资源。只核新增数学与接线，复用旧认证核。大批量通过现成配置的batch服务，优先现有环境，不在本地恢复CERN栈。拟议≤1GPU并发、GPU任务wall累计≤2h、CPU累计≤6h、最终紧凑≤20MB；实际吞吐/显存/收益未测，QA后准入，不把stage92的训练时间当新模型保证。不静默缩样/删困难者或重复大I/O，不留事件/逐hit副本。

交付train/cal_select学习曲线、参数量、单seed及固定集成、全部cal/test配对。分层含50–100/100–200GeV、all、≥200、低pz、低pz真高E、high-y、未确认、高端、missing；点指标log-RMSE/median bias/R68/总正负tail50，概率指标NLL/宽度/总体及X组PIT与coverage，500incoming条件配对和seed波动，source95不可估及开发池限制明确。

保留原点风险门槛：两低E/传统条件上95≤1.05、all/direct≤1.01、≥200及困难/direct≤1.03，原七层加低pz真高E双向tail差上端≤2pp。不能用解释修正、核心变窄或一个好能箱替代联合目标；若只取得B−A/C−B/D−C/E−C的稳定增量，仍应写清研究结论，而不是只有“未通过”。所有新收益、功效、资源和真实系统效应无实测时写“未测量”。

先写中文stage94 workbook，给出实际样本、配置/命令、数值、成本/失败、图表/产物、程序和物理解释及下一最小任务，再本地Conventional Commit，不push、不自动执行下一阶段。历史stage54后缀逐字保留；其“尚未完成”是历史文字，当前完成状态以stage85 tracker报告为准，不因此重复执行。

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
