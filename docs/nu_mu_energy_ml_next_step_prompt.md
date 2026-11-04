# 下一轮执行 Prompt：stage99 能量歧义、概率产品与真实关联活动

先读AGENTS.md、[stage98研究复盘](../workbook/2026-11-04_stage98_research-reassessment.md)、修订路线§80、信息计划§60和stage94–97报告。stage94九fit、stage96/97各两fit均已完成，不重跑。stage98现为研究报告，原native-only计划尚未执行；本轮执行编号stage99，做下面两个独立工作包，不让native入口阻塞已有输出的诊断。**在有环境的节点执行；当前本地终端不恢复CERN环境或复现事件。** 无新能量网络/生成/重建，无架构seed网格，不自动进入stage100。

## 1. 已测依据与固定边界

stage94 E集成最低能/all/低pz真高E=.276027/.289843/.671125，stage92=.165630/.326058/.826918；传统最低能.145661、direct总体.287491。stage96/97新增几何和联合消息全体B/A区间含1；stage95最低能81可读例全单轨迹，已有候选替换μ-pz oracle仅2例改善，不是ν能量信息上限。不把“尚未推广”等同于没有研究结论，也不继续几何深宽扩展。

原stage87兼容池、角色/隔离/同incoming总权重1保持：train/cal/test46575/11612/13189、唯一incoming37556/10811/12125；全部1016新增K和missing21/6/5/困难侧/高端/尾保留。cal_select5443、cal_post5746，423退出select仍全cal报告。test是已研究池留出，所有结论标开发，source95未测；不从test选择阈值/输入/checkpoint/prior。

一次方动量pz0-only，既有px/py/q/p/弯折、raw11/status、合法负raw、typed NaN和Calo缺项不改，不加p0/p1/pz1或旧禁用动量比。原stage54后缀逐字保留，但其实际完成状态以stage85条件活动报告为准，不默认重做noise控制。

## 2. 工作包A：只用保存输出，完成决策诊断和一个概率后处理

读取已保存cal/test的点输出、标签/角色/权重及stage94 E三seed MDN head/旧ensemble offset；stage92只复用确实保存的准确CDF边界质量。没有保存的质量明确缺口，不为此再积分/网络forward/ROOT，也不按test补模型。

先冻结四个分数：pz-only、原direct点输出、E的H/L质量比、stage92保存质量比。在观测50<pz0<100内定义诊断L=真E50–100、H=真E≥200，分数q=P(H|X)/[P(L|X)+P(H|X)]；100–200仍保留全部能量风险、在二类诊断中单列。部署输入无truth；分母0保留未定义。pz标准化格只由train/cal X预先确定，空格不补，无新谱选择。

交ROC/partial ROC及2%/5%/10%名义低能误判工作点的高能识别率、实际支持/条件区间、各分数的完整风险；阈值只由cal_select定义一次，不在test选赢家，不将其部署成新gate。当前cal已用于选模/offset且来源相关，不能声称NP总体保证。iid149/299低能校准支持是2%/1%错误率的数学示例，当前select/post最低能85/97不能bootstrap复制变大。工作点与原tail≤+2pp/RMSE门槛不是同一量。

同时对旧点输出做精确损失分解：m=log(pz0/.8)，c=预测logE−m，e0=m−logEtrue，分别给各低能/同低pz高能/总体的E[c²]、2E[e0c]及风险增量，逐例恒等式闭合；仅已有结果解释，不冒称因果或信息下界。其他全风险层原样保留。

概率工作固定stage94 E分布和旧点offset b，只拟合一个T>0：Z′=m_E(X)+b+T[Z−m_E(X)]，其中m_E是未校准MDN的mean logE。全部seed/分量按同一变换，权重不变。保持原点预测m_E+b完全不变，只在原cal_post上优化weighted NLL。事前固定T∈[0.5,3]、从1单次有界优化，不续温度/先验/局部网格；边界命中如实报告。校准前后都报完整cal/test NLL、宽度、十箱PIT、68/90coverage和stage94原X组，不能用真E组PIT均匀性当后验要求，不把区间改善冒称低能点恢复。

已有曲线表明E三seed的point-best65/90/65与NLL-best50/25/35不同；这里只引用曲线，不虚构未保存早期checkpoint预测，不重训。若后续确需NLL选模，另冻最多一条训练轨迹，本轮不自动执行。

## 3. 工作包B：原生引用服务于相对μ活动，交付可行时直接做两格信息pilot

使用stage95原2048不同train/cal incoming、一视图/24source及原身份表、已知production链。原PHYS1923可读/125临时删除不改；stage96全池1044候选缺源不混同本队列125。只沿精确PHYS→REC/ESD已知配置/日志定位，不猜merge序号或run/event跨源匹配，不扫全EOS、不重建补删源，不丢既有K摘要。

先≤40固定train/cal身份QA，覆盖原来源/观测pz/状态而不按真E/y/误差挑样。核原track筛选/index、TSOS/measurement真实ID、SP组成cluster引用、collection有效分母和实际covariance/单位。hitSet是层覆盖且已测不等长，不能代替真实ID；单位covariance不能造pull。优先已有匹配Calypso构建，仅新导出源码确需改时编译，不恢复整套历史栈。

冻结一族紧凑活动摘要：每station/面关联唯一cluster/SP与其余活动数；其余活动相对leading的横向分布/纵向增长和有效读出支持；可核误差尺度作质量解释。单轨迹事件同样提取。SP/cluster不重复计能量、共享ID不等于重复粒子，不据此删候选；未归属不是noise/强子标签，geometry不是通道响应，无truth输入或硬Calo电荷分配。没有可靠引用就给可做collection级测量和具体未测项，不强配数组。

对原完整2048身份队列保留native不可定位/联结失败/空集合/缺collection的不同状态，按原source/component/X/单多轨迹交真实分母。既有truth只另表诊断，不按标签重选队列。只保留紧凑活动摘要，不留逐hit点云或REC/RDO/xAOD副本。

若一族输入实际交付且原train/cal两类支持允许，在同阶段完成恰两个预注册信息classifier fit：A=原62摘要＋共同native可用状态，B=同A＋这一族活动及其值mask。两格同seed2026110499、固定低容量BDT（拟议depth2/100树、eta.05、min_child_weight10、lambda10；在读取新cal目标结果前冻结）、无cal调参/早停/补seed。使用原队列train训练、cal评价，同incoming一视图；truth L/H仅标签，pz50–100作为共同观测研究域，所有原队列身份在可用性/支持报告中保留。不能把共同缺源状态造成的差异当新活动收益，不能把此配额队列当自然flux。

报两格条件log-score/Brier、低误判率识别及支持/条件区间，原角色/来源/incoming不可交叉泄漏。无法支持某工作点写不可认证，不给零错误总体保证；类别不足或native失败时不强行fit，交已完成物理测量和确切缺口。没有test native载荷/新test风险。小pilot只判断是否值得扩完整输入，不称完整能量收益、物理信息极限或部署通过。

独立μ控制的条件秩/残差可列下一方案，但stage52/85主要100–1000GeV/tag/trigger条件不能无验证外推50–100GeV；同62的确定变换不新增观测。先交真实关联活动，不为μ控制再起无期限前置。

## 4. 资源、判断和最终交付

A无需等待B，B无需等待A。≤40实际包QA先核数学/身份/输出和CPU/wall/RSS/真实读取成本再冻结资源；不用SHA。拟议A≤900CPU秒，B含可行pilot/报告≤13500CPU秒，总≤14400CPU秒/native实际读取≤10GB/紧凑最终≤20MB。native批量走HTCondor按source分片，内线程1，独立源足够时用8CPU、最多2并发；不占GPU做I/O，不重复扫描/保留大中间文件，实际请求/read/物理网络口径分清。成本与新收益均未测，不据预算缩成有利样本或自动加资源。

决策必须具体：已有概率排序可用但尺度偏则交概率产品/决策缺口；排序只在高误判率下有效则支持购买新活动，但不是Bayes界；B有可支持信息增量才下一轮扩完整角色并在强BDT做匹配两格能量消融；B无可交付新载荷或该统计族无增量则停止本工程扩展，列最小缺失产品/实际风险前沿，不续GNN深宽/seed。概率产品和信息pilot不能替代最终点目标。

原最终门槛保留：两低E/传统上95≤1.05、all/direct≤1.01、≥200/困难≤1.03，原八层总/正/负tail差上端≤2pp；当前A的点输出恒定，不能因此声称新能量门槛改善。开发增量与最终联合通过分开记，source95/interaction/FSI/材料/Calo/接受度/背景/真实response及未开发确认仍待测。

先写中文stage99 workbook，说明实际样本/选择/单位/输入/命令、详细数值/区间、失败与资源、程序/物理解释、产物和下一最小任务；未测写“未测量”。再报告/代码/紧凑证据本地Conventional Commit，不push、不自动执行stage100。保持历史正文及以下stage54后缀逐字不变。

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
