# 当前交接：Stage113复用已通过QA，一次完成六源选择/响应测量

先读AGENTS.md、路线§94、信息计划§74、[Stage112实际报告](../workbook/2026-11-05_stage112_selection-response-audit.md)、[原Stage111科学合同](../workbook/stage111_energy_ml/experiment_contract.json)、[Stage113执行合同](../workbook/stage112_energy_ml/next_execution_contract.json)、[六源manifest](../workbook/stage111_energy_ml/source_manifest.json)、[QA](../workbook/stage112_energy_ml/QA.json)和[实际资源](../workbook/stage112_energy_ml/resources.json)。**Stage112按冻结准入stop结束，科学端点仍未测；Stage113本轮未执行。** 当前用户授权的持续推进任务按此明确新合同继续同一项实际测量，不再询问新输入或重复研究/metadata阶段。

## 1. 已交付与新执行条件

原定六源各10000父entry/67branch。≤40真实QA去重实际36（5/5/5/5/8/8），20有效native MC cuts与独立掩码/累积cutflow/最终成员相同、pz差0GeV/leading一致、truthE相对1e−12，empty/unknown/sentinel/合法负值通过。不是60000条全量闭合；不把QA selected比例当效率。

首次9668058在uproot mktree把数组当类型处失败；显式schema+extend修正已实际通过补跑9668059。两任务GNU共69.33CPU/24.80wall秒；首次实际IO未保留，确定性QA前缀重放上界计入，累计接口上界53388186bytes。12GB descriptor被站点改写/分配18GB，6CPU/0GPU/六worker内线程1。两次失败/修订/原字节运输/去重证据保留，不隐藏提交数。

原小批decode0.179–0.265CPU秒按N/n1250–2000倍放大，factor3+reserve投影14665.550938CPU/3371.318452wall秒被原3600/900拒绝。小Awkward固定调用开销无全批比例依据，不能称全量实测耗时。本阶段原拒绝不改；Stage113只替换这一工程准入，保持下列科学问题及总预算。复用36例QA，不再单设计时/接线/metadata轮。

## 2. 固定科学比较

仅六源manifest，π/K/charm×历史train/cal；不能换缺源、按产额补源或读test-only源。PHYS分母不是生成/输运/full incoming接受度，也不是自然flux；固定完整X内确定选择不增加p(t|X)信息。完整60000父entry全部计数，无轨迹/invalid/unknown保留；每源缺支持就主端点不可估，不丢源重归一。

G0=所有有效名义MC cuts仅去reco LeadTrack_pz0>50；保留truth νpz>50、原fitted-charge/质量/几何/实际requires。G+=有限正pz/Eν的G0；S50=G0且pz>50，S100仅历史对照。模型变量政策仍一次方动量仅pz0、允许px/py/q/p/弯折、raw11/status/typed NaN/Calo缺失、合法signed负值；0新模型/forward/offset/温度/阈值选择/生产。pz≤50区域不做BDT外推。

主端点固定传统pz0/0.8，真[50,100)/[100,200)GeV各报六源平均 MSE(S50∩G+)−MSE(G+)。每源eligible incoming全部父视图总权重1，在选择前固定；不是在幸存者重新分摊。两箱都报，零/反向也完成。唯一主μ有效子集r=ln(pz/Eμ_vertex)、u=ln(Eμ_vertex/Eν)、c=ln0.8，e=r+u−c，六项平方分解保留signed交叉项；r不是纯tracker resolution，主风险仍留unconfirmed/未知μ。

batch只读split身份白名单incoming/role/initial_role/origin/source/group/run/eventID；test>cal>train，原隔离和低优先来源视图保持，已知test-key仅完整cutflow计数，主要开发对比隔离；新父entry仅diagnostic-only不加入训练。input source+entry核run/event，incoming精确原生MeV四元组为代理、非真实独立谱系。完整角色联结本轮尚未验证，须实际执行。

交完整cutflow/独立fail和unknown、原八层/高端/困难、两侧RMSE/bias/R68/总正负tail50、incoming/权重/ESS、transfer/y<.2、μ有效/确认率、vertex/pz/response分布及r/u分解。固定seed2026110512的500共同incoming Poisson乘数、同键跨源共用/成对/固定源视图权重，≥475有效draw才报percentile95，无重抽到成功；独立record-space与key聚合核验。只条件于六源，不覆盖source/refit/研究选择/系统/newblind。

## 3. 必须核完的程序与异常

复用Stage112选择/空轨迹/原生snapshot接口，保持原definitions依赖闭包及mktree显式类型；复用现成build不重编。对60000条逐个核native独立掩码/成员、已知cached交集（缓存不等于完整父selected）。pz差0GeV、truthE相对1e−12、逐例/汇总分解1e−12/1e−10。Stage112统计源码全量路径没有运行过，不能直接标通过；实现新stage输出目录，不覆盖Stage112 QA/准入/历史结果。

QA有4个(source,cut)非负域invalid reduced<30pC单项pass：55:164 VetoNu0/1各1、55:67 VetoNu1一、55:116 VetoNu0一。不是四个独立incoming或最终S50，具体值/status/去向与全池发生率未测。完整影子审计应输出紧凑source/entry/变量/值/status/是否S50例表（首40例、完整计数保留），不以它们删除事件/修cut/换阈值。SafeAt NaN、非负/count−1/−999/uintwrap、合法signed raw/charge sign/module_eta、fallback−1234控制值分清；原native reduced/fitted charge切选保持，不直接把同阈值套raw。非物理truth ratio不clip。

## 4. 一次执行与实际预算监督

单新HTCondor6CPU/12000MB、最多6worker、ROOT/BLAS内线程1、0GPU，spool ~/condor/nu_muAnalysis/stage113/。不跑另一个小批成本benchmark。112+113共享原3600累计CPU秒/900累计GNU任务wall秒/2GiB接口请求，先扣69.33CPU/24.80wall秒和53388186bytes上界，剩3530.67CPU/875.20wall秒/2094095462bytes；临时128MiB/最终20MB保持，不扩cap。

监督器启动独立进程组，计所有活后代自身CPU与已reap子CPU（避免嵌套重复），native/strace都包含；剩CPU留60秒清理余量、wall825秒停止阈值，组TERM/KILL并收集，GNU外层累计权威。共享pre-read计数以原接口上界初始化，在请求前拒绝越界。只读67必要列、复用basket，native本地I/O和源I/O分开记录、不称物理网络。新科学计算只在batch。

达到实际cap/源缺失/身份或native不闭合，报告精确缺项与未完成端点；不能截有利前缀、只平均已完成来源、改权重、追加job/预算或再做工程计时循环。一次完成完整测量，或按这些实际stop结束。QA需复核的只限真正改动的watchdog/输出路由，不重做36事件/原始模型接线。

## 5. 交付与后续

先写中文Stage113实际workbook，交两个完整端点或精确零支持原因、全分母/原八层/invalid表、signed分解/500区间、独立校验及实际累计CPU/wall/RSS/接口I/O，再本地Conventional Commit，无push。重复JSON/运输/临时ROOT去重；Stage54资产和后缀保持，其他项目不动。

Stage112不是物理阴性；Stage113也不要求有利效应才能完成。原Stage110固定差、Stage108三格/遮挡及既有门控/重权均结束，不自动训练/改cut/扩源/新生产/晋升。两低能/传统上95≤1.05、all/direct≤1.01、其他五层/direct≤1.03及八层三尾差direct上95≤+2pp不改；真实response/interaction/FSI/材料/Calo/接受度/背景和新独立确认仍未交付，整体目标未完成。

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
