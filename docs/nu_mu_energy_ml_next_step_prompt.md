# 当前交接：Stage115测量状态/强BDT残差两臂结束，下一问题转固定相对时序

先读AGENTS.md、路线§97、信息计划§77、[Stage115实测报告](../workbook/2026-11-05_stage115_measurement-state-residual.md)、[原Stage114设计](../workbook/2026-11-05_stage114_measurement-state-and-risk-research-reset.md)§5以及[主端点](../workbook/stage115_energy_ml/primary.tsv)/[门槛](../workbook/stage115_energy_ml/gates.tsv)。**Stage115已完成，不重复作业或继续其树/seed/状态子集网格。** 原Stage110固定差、Stage108三格/遮挡与旧门控/重权均结束。本次用户授权的下一阶段已兑现为实际能量结果，不需另做无实验研究阶段。

## 1. 最新实际结果

唯一Condor9668138首start/exit0。原71376 active（train/cal/test46575/11612/13189）、17657隔离、全部1016新增K和原incoming视图权重保持。origin/origin_row回接原62/11路status，incoming/run/event/group核验；全部状态可用、缺状态0，原62缺项21/6/5不删。原Stage87 direct_cal缓存含train，0新基线fit/forward，无ROOT/生产/换split/cut。

A原62+三flag+共同availability=66，B增11×4位=110。每臂8棵depth3/min_child_weight200、原eta.04/λ10/固定seed2026110515，52叶/rank45；固定字典signed残差和四次预定凸解已实际完成。主τ2.032000317154125、次修正平方.0023840304354885724，124/151迭代均success；主/次最大归一化违反1.073e−12/1.565e−11，近似KKT驻点1.441e−5/5.918e−6，无严格dual界或全局最佳宣称。主目标最低箱/all保护活跃，第二箱未活跃。

**B/f0主cal_post最坏两低能RMSE比1.024843205547326 [1.0058712848637628,1.0508710279789928]，失败；B/A1[1,1]，无受支持状态增量。** 最低箱cal .330275→.304464、test .282644→.270006有局部下降，但test传统.145661；第二箱test .246329→.252093，all .287491→.292520恶化。A/B目标及已报风险相同，不宣称独立核过逐行A/B完全相同，也未保存逐split特征使用表，不能把当前阴性归为所有状态冗余/信息界。状态非全常数，train Veto10/20/21 overflow19825/19174/18443（分母46575）。

两臂/θ锁后才新test前向与风险，完整原八层/状态/缺项/高端/三尾已交。B test两低能/传统上95=2.247412/1.092172、all/f0=1.021024失败；低pz真高E总/负尾差上95+3.391598/+2.583281pp、high-y负尾+2.360973pp等失败，A/B joint均False。不以train平方hinge保护冒称实际尾率或留出保护。40test配对独立区间max1.421085e−14，三主2.220446e−16，504旧参考标量差0，500draw主端点全有效。

## 2. 资源、产物与不变政策

4CPU申请8GB站点12GB，内线程1/0GPU，GNU73.72CPU/42.38wall秒/RSS515116KiB<1800/900；worker/两臂嵌套成本不重复相加。worker本地archive接口40315471byte，不是物理网络，整树峰/单核加速/全会话成本未测。21项输入原字节一致，运输副本核后删除；两小规则头和一个约1MB紧凑A/B点表保留于ml/artifacts/stage115，表/图/协议/资源于workbook/stage115_energy_ml，spool ~/condor/nu_muAnalysis/stage115/。完整[完成审计](../workbook/stage115_energy_ml/completion_audit.tsv)区分实验完成与项目未达。

一次方动量仅pz0，允许px/py/q/p/弯折，raw11/status/typed NaN/合法signed和Calo缺项、pz>50/原角色/全部K不变。负reduced已允许signed，不修cut/设通用NaN；不把fit坏与wave坏混同。unknown status是新增NaN/availability，不当正常零，弱/饱和/缺失事件不删。无新offset/主候选或阈值事后选择。Stage54原控制已在Stage85完成，保留旧资产/后缀，不据旧“未完成”措辞重跑。

## 3. 下一有界新观测问题

按Stage114§5，优先研究**VetoNu0/1相对一个事前固定Veto参考的时间族在给定电荷/状态/pz后是否增加连续能量风险信息**，区别于Stage80 peak/width。先另冻该科学合同/参考/两路差分/允许来源与预算，再同一任务内校准检查和一次匹配能量消融，不另拖成小QA/metadata阶段。不是再次扩Stage115字典或多状态头。

已知入口为ntuples/energy_ml_stage79/measurements.npz、Stage79生产证据与原PHYS精确producer，μ控制清单ml/configs/calonu_muon_files.tsv，及现行Stage87固定身份。Stage80 shape.npz只持久peak/width派生族，不能声称已有完整localtime。全池相对时序可用率/实际cost及匹配μ控制未测。只沿既知入口定位，不能扫全EOS/恢复旧REC/全部波形或新生产；如需已知PHYS定向读取，须在新合同列完整同split身份和资源，保留全样本missing路径。

必须证明两路共用可消的加性时基，并核通道常数/μ路径传播/time walk/fit fallback；trigger绝对时间无效不数学上否定共模差分，但不是校准证据。参考与窗口不得由test挑选；弱信号/overflow/无有效时间只新增NaN/availability，原能量仍预测，不用有效时间cut净化样本。若时基/μ控制可交付，再一个固定相对时间族与强基线匹配对照、头/输出先锁再cal_post/test全报告；验收为两个低能及困难/高端的配对能量风险、实际可用率/资源和原最终全部门槛。不以时间变异/可分类或truth时间oracle代替部署收益。若不可校准则交准确缺口并结束该实现，不硬造常数/1σ或称物理阴性。

父分母扩展/producer精确定义仍为解释支线，不因重新读取旧selected而称新训练支持，不改Stage113零charm/稀少draw端点，不以六稀有单元都能报CI作为能量学习前提。下个任务真实功效/效果/资源未测，本阶段不自动执行。

## 4. 最终要求

两低能RMSE/传统上95≤1.05、all/direct≤1.01、其他五层/direct≤1.03、八层总/正/负tail50差direct上95≤+2pp不改。真实response/interaction/FSI/材料/Calo/接受度/背景及新独立确认仍未交付，整体能量目标未完成。incoming条件CI不含source/parent/refit/研究选择/真实系统和新blind，不能以开发test重复改善冒称确认。每阶段先中文workbook，再本地Conventional Commit，不push；不自动新训练/生产或网格。

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
