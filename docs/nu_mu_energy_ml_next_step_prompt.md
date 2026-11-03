# 下一轮执行 Prompt：stage88 现成后验积分收敛与推断成本，0fit

先读 `AGENTS.md`、路线§69、信息预算§49、[stage87实际报告](../workbook/2026-11-04_stage87_resplit-retraining.md)、[冻结训练协议](../workbook/stage87_energy_ml/protocol.json)、[数值QA](../workbook/stage87_energy_ml/quadrature_QA.json)与[下一输入/验收提议](../workbook/stage87_energy_ml/followup_input_request.json)。**唯一任务是已保存后验的数值精度和推断成本审计，0新能量fit、0ROOT、0生成；没有新样本不构成此前置。**

## 1. 已测结果与边界

用户授权重划现有样本，stage87已合池89033兼容记录并完成五模型，train/cal/test46575/11612/13189、唯一incoming37556/10811/12125，source/incoming跨角色隔离、每key权重1。14435无审计readout未混fitted charge；1016K新支持保留。新test仅留出本轮fit，已曝光开发池不是blind，旧F7缓存不能当新split独立对照。五fit已结束，不再重复训练。

新test传统/direct/bounded/名义posterior最低能log-RMSE .145661/.282644/.315593/.172273，第二.247937/.246329/.282926/.232803；posterior有低E收益但最低能仍差传统，低pz真高E/high-y/未确认退化，候选均未通过联合门槛，继续既有部署。总体68/90覆盖68.633677%/90.836976%不能抵消PIT偏移、高端欠覆盖和点值/尾失败；flat/pressure为诊断，不选赢家，不归结信息极限。

每角色只有3个source/incoming连通块（pi/k/charm各1），保守来源区间不可估；500incoming bootstrap仅条件于已有来源混合，排除来源/parent相关、重训/cal估计/响应/研究选择。真实响应/interaction/FSI/材料/Calo/接受度/背景及未来真正未开发确认仍未闭合。

## 2. 实际输入及零fit启动

- `ml/artifacts/stage87/posterior_parameters.npz`：全部活跃原始15维head、pooled row索引、b/T；保存的head尚未加b/T。
- `posterior.pt`、`normalization.json`、`posterior_calibration.json`、`prior.json`、`split.npz`及原stage55/56/70/81/82/83缓存用于身份/状态与输入复现。紧凑`predictions.npz`也是active-row索引，不能当rich全89033行直接运行report/validator；先按row联结还原，不重训。
- 已有首40cal固定身份：max|PIT32−64|=.039193110、|64−128|=.012998450。先只复用这≤40身份做独立积分/计时QA，不能无预算全cal×多节点扫描。

## 3. QA后冻结一次数值合同

提出一个独立确定性参考：对标准正态s的一维自适应积分、解析r逆变换/CDF或density、显式尾界；与GH32/64/128和至多一个事前较高参考比较。最大节点数本身不是truth，需独立交叉精度/尾残差/归一化证明。参考无法收敛时如实标未认证，不无限加节点。

默认验收提议为CDF/PIT绝对误差≤1e−4、quantile绝对logE误差≤1e−3、log-density误差≤1e−3，并验证CDF单调、[0,1]、分箱质量和归一化。先固定参考实际可达容差，容差更改须解释数值依据，不能按test能量风险调整。基于小QA成本固定≤512等间隔cal＋≤40 train，若全cal可行必须事前明确范围；保留稀少/极端数值情况，不删坏事件。

只在train/cal设计/验收，不按test挑节点、模型或先验。固定b/T和预定小邻域的cal目标变化可以诊断，不再优化校准。原主GH32数字保持历史；更精确推断的诊断须另名，不能宣称修复训练时32点loss偏差。禁止新增架构、seed、loss、early stop、谱或校准自由度。

## 4. 资源与交付

大批量通过≤1Condor、1CPU/3000MB、累计CPU≤1800s、wall≤1800s，紧凑留存≤20,000,000bytes。QA后按真实耗时冻结，执行前包检查；测CPU/wall/peakRSS、CDF次数、逻辑/传输字节和CDF/bin缓存复用成本，未测物理EOS I/O不冒称。无新样本前置，不重读ROOT、不生产支持，不保存重复包/逐事件大网格。

交CDF/PIT/median/q05/q16/q84/q95/log-density误差、固定校准目标敏感性、各来源/观测状态的数值稳定性、参考认证范围及性能；区分数值误差、条件统计、先验/训练loss与尚未识别物理响应。若以后评test，先冻结算法和预算，只交诊断，不据此选赢家或晋升模型。当前未来收敛/收益/成本均未测量。

先写中文stage88 workbook实际报告（单位、输入/命令、数值/误差界、失败、资源、产物和下一具体任务），与代码/配置/紧凑证据本地Conventional Commit，不push、不自动启动stage89。原62/pz0-only一次方动量、允许px/py/q/p/弯折、raw11/typed NaN/Calo缺项、pz>50和全部困难侧不变；1016K保留，旧K生产禁令/时限不恢复。下面原stage54后缀与五项未跟踪路径逐字/只读保留。

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
