# 下一轮执行 Prompt：stage89 全既有cal/test的准确后验推断与配对评价，0fit

先读`AGENTS.md`、路线§70、信息预算§50、[stage88实际报告](../workbook/2026-11-04_stage88_posterior-numerical-audit.md)、[实际数值QA](../workbook/stage88_energy_ml/audit_reference_QA.json)、[资源与失败恢复](../workbook/stage88_energy_ml/resources.json)及[下一输入/验收](../workbook/stage88_energy_ml/followup_input_request.json)。**唯一任务：现成stage87后验在完整cal11612＋test13189的一次准确推断与配对评价；0新能量fit/校准优化/ROOT/生成，无新样本前置。**

## 1. 已测证据与冻结边界

stage88固定552train/cal已经独立认证参考：CDF两向差6.616929e−14、log-density差7.666686e−10、tail界4.253165e−19。GH32 PIT/quantile/log-density超限132/231/159，GH256仍6/29/20；不再提高节点扫描。固定512cal NLL GH32/参考−.124483590/−.130228601，五点差分未优化。cal子集log-RMSE .312583173→.314381109、低pz真高E13条.850516317→.876315710，不能把准确积分预称能量改善或修复训练loss；低E9条不代表全体，missing/wave/Calo-invalid在该子集未覆盖。

stage88唯一Condor9667190全数值完成后JSON序列化exit1，原数组已零积分重算恢复、11055项验证通过；不是失败后重训/重提，数值核心与正式包相同。继续既有部署，旧stage87 GH32数字保持历史。原split/test对stage87拟合留出，但池已曝光，**不是新blind**；source/incoming连通块每角色3，source95不可估。

## 2. 真实输入、算法和QA

- 保存原`ml/artifacts/stage87/posterior_parameters.npz`的row/head/b/T，`predictions.npz`的同split direct/原后验/标签/pz/weight，`ntuples/energy_ml_stage87/split.npz`、原prior与calibration JSON；按pooled row联结，不把compact索引当全池索引。无需网络forward、读取ROOT或重建训练数据。
- **唯一主数值定义为`ml/posterior_numerics.py`的自适应s参考**：相同解析r逆变换/能量Jacobian、分点、eps与normal尾界、safeguarded quantile解。原b=.011721733230708156/T=1.2001641697078562、名义ratio及主median全部固定；不按test选算法/积分阶/先验，不依据stage88五点目标改b/T。
- 先≤40固定cal真实身份/单位/row和实际包计时QA，核CDF/quantile/log-density/边界；算法与容差在test计算前冻结。反向r-CDF/五点差分只作固定小QA，不逐事件重复；逐例主积分误差/尾界、CDF端点/归一化/单调性仍保存。不认证者保留标记及原因，不删事件。

## 3. 全量评价与统计

一次覆盖全部cal11612/test13189，缺失6/5、未确认、fit失败、低pz真低E及真高E、high-y、高端全部保留。恢复原每key全部视图/总权重1；不按低pz硬切传统，不只复核stage88容易子集。

保存名义median/q05/q16/q84/q95/PIT/log-density及同一固定参数下training-prior NLL；只比较GH32→准确推断、准确→同split新direct/传统。两低E相对传统1.05、all/direct1.01、困难1.03、原七层总/正/负tail50差+2pp及同低pz真≥200保护不降；报告bias/R68、68/90coverage/宽度/PIT十箱/NLL，稀少missing/高端单列。精确CRPS积分未认证，不用旧近似证明通过，不自动扩展昂贵二维积分。

复用500component内incoming条件重抽样，seed2026110387+rolecode，完整key多视图及原权重保留；不宣称来源、parent相关、重训/cal估计、响应或研究选择覆盖。真正来源稳健/独立确认未提供，开发通过也不晋升。cal用于数值/目标诊断，不优化任何参数；test只交该冻结模型的固定诊断，不选赢家。

## 4. 预算与交付

主参考512cal实际172.797432CPU秒=.337494984秒/例，24801线性外推8370.213102CPU秒仅规划依据；实际全量、未覆盖状态与统计成本未测。QA后冻结≤2Condor/并发≤2，各1CPU/3000MB/MaxRuntime5400s，累计CPU≤10800s、最终紧凑≤20,000,000bytes。输入/输出去重、共享head只传必要角色，不保存逐节点大网格；500draw暂存在worker、独立验证后只留seed/指标。测CPU/wall/RSS、被积函数/CDF调用、逻辑与传输字节，未测物理I/O不冒称。预算或精度不够时先交实测缺口，不静默削成有利子集或自动扩大模型网格。

写中文stage89 workbook实际报告，包含完整计数、风险/数值界/条件统计、失败尝试与资源、输出及下一具体任务，与代码/配置/紧凑证据本地Conventional Commit；不push、不自动执行stage90。原pz0-only一次方动量、允许px/py/q/p/弯折、raw11/typed NaN/Calo缺项、pz>50与困难侧保持；1016K继续使用，旧生产禁令/时限不恢复。原stage54五项只读，以下后缀逐字保留。

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
