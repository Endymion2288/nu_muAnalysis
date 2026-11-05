# 当前执行入口：Stage118库存与物理机制路线，研究完成、计算未启动

先读[Stage118完整报告](../workbook/2026-11-05_stage118_mc-inventory-and-physics-strategy.md)、路线§100、信息预算§80。用户本轮要求研究思路与可用MC评估，不恢复环境、不运行训练/事件分析。本次只审阅已有结果和57页PDF，所有新增性能/产额/资源均未测量。以下Stage117及更早入口为历史，当前优先级由本段覆盖。

Stage117四臂已经结束；最低箱direct .282644→.246473，仍差于传统.145661，联合风险/尾门槛未达。Stage116物理B仅有输入缺口，没有oracle/代理实验，不能称已失败。旧Stage82/84低能扩样仅约3%/24%，不证明数量充分，也不证明更多MC一定成功。不要继续同缓存树/种子/温度/惩罚、旧门控或无新语义图网络。

下一有环境任务应一次交付“独立支持学习曲线＋最小响应机制对照”，具体分工/判定见Stage118§4–6：

1. 定向核查MC24下游200131–136和200184–189（均z>−2.2 m）的现成PHY/HITS/日志。PDF数量不是独立selected数；认证实际parent/种子/旧全部曝光、producer/geometry/calibration和纳入概率，pilot测两低能、同低pz真高E、高端的支持及成本。缺上游支持不能靠重权解决；不递归扫全EOS。
2. 新生成/输运/数字化家族先固定train/development/confirmation角色。共同支持内固定组成、特征、损失和一个强基线政策，pilot可行后冻结N/2N/4N嵌套规模；数量参考不是充分性承诺。原全目标继续评价，不按truth z部署分流。新确认先锁，旧test不再称blind。
3. 对固定传统/direct做一个事前选定强子化或G4/中子库环境对照，优先200300–311或相应年份G4族，留一环境用于迁移。家族未核不按行号配对；父分母/选择迁移与共同selected风险都报告，不把变体数充独立N或包络充1σ。先看W/模型分支，不把低E等同低W。
4. 修正Stage117非μ比例oracle：上游VetoNu主要响应退激中子，非μ比例可能退化，尚未测定。先定位发生器组成→中子祖先/敏感沉积时间结构→实际读出哪层保留条件能量信息，探索上游迟到活动与下游泄漏联合约束。有可交付读出时同阶段做oracle→部署代理→连续能量风险；HITS/乳胶ntp不默认含完整电子祖先，缺项只定向小重放，不伪造标签/时间窗。仅同旧X代理不增加信息，真H/E或真边界能流收益不当部署证明。

这是一项科学工作包，输入QA之后应给可做部分的物理结果，不无限拆metadata阶段；若某部分不可交付，交准确缺口并推进另一可做部分。批量仍走HTCondor，~/condor/nu_muAnalysis/<stage>/，预算/读字节/CPU/event由小样本实测先冻，只保留紧凑摘要。原pz0/raw/status/signed/typed NaN/缺失、全部1016 K与原角色政策保持。两低能1.05、all1.01、其余五层1.03和八层三尾+2pp不变，1.05只是非劣效，突破需预定改善证据。真实系统、背景/接受度和独立确认不可省略。

本轮没有自动执行上述后续计算。完成阶段先中文workbook再本地Conventional Commit、不push。Stage54原控制已在Stage85完成，历史资产/后缀保留，不据旧措辞重跑。

## Stage117历史入口（原文保留）

# 当前执行入口：Stage117四臂已完成，固定方法预算结束

先读[Stage117报告](../workbook/2026-11-05_stage117_oof-risk-direction.md)、路线§99和信息计划§79。Stage116缓存工作包A已经实际交付：训练内/真实OOF×普通/分层方向四臂，同110维、来源/incoming清除、训练内部4/8树选择（均选4）、最终全train强BDT锚定，以及匹配μ-only对照。15次真实折baseline fit+3次μ-only fit、24次凸解，全部完成；不重新跑该四臂或追加树/seed/温度/惩罚网格。下面Stage116/115入口均为历史，当前状态由本段及Stage117报告覆盖。

预定OOF分层臂test最低箱direct .282644→.246473、传统.145661；第二箱 .246329→.252963、all .287491→.290225。cal_post最坏两低能/direct=1.022398 [.999284,1.047816]、对OOF普通=1.016797 [.992371,1.046633]；共同主比较失败。两低能/传统上95=2.029808/1.096984，all/direct上95=1.012629，低pz真高E总尾差上95+4.320406pp等失败，四臂joint均False。局部改善不抵销困难尾或原最终标准，继续保留强direct。OOF确实生成，但source purging/训练量/offset使其误差分布不同，最终完整管道已测，不能称OOF自动消除迁移。

当前优先是Stage116物理工作包B的可交付输入：[准确缺口与候选中间量](../workbook/stage117_energy_ml/observability_input_gap.json)。七个明确缓存没有谱系敏感沉积/边界能流或新独立生成家族；不扫描旧源或用truth H/E、SP离轴代替新观测。需要预定双侧独立pilot，真实generator/输运/重放family身份、选择分母/纳入概率、实际VetoNu volume map与μ/非μ/unknown谱系沉积、匹配raw/reduced/status。候选是非μ敏感沉积组成量，实际schema未认证、覆盖/收益未测，零/unknown保留、不除H称效率。一次工作包完成原读出→中间量oracle→部署代理→同容量能量消融，代理源留出、全队列风险/尾/资源，成立才扩大编码器；新生产另冻合同并先测小pilot，不自动启动。

有已知共同控制和时基可直接交付时，相对时间可作有限独立分支；无真实波形/响应就不伪造删失幅度或prompt/late。物理工作包B尚未执行，不能称其阴性或完成。原pz0/raw/signed/NaN/缺失、全部K/角色、1.05/1.01/1.03和8层三尾+2pp保持；1.05只表示恢复/非劣效。真实系统、接受度/背景、新blind与完整能量目标仍未完成。每阶段先中文报告再本地Conventional Commit、不push，HTCondor提交目录仍为~/condor/nu_muAnalysis/<stage>/；Stage54原控制已在Stage85完成，保留下方历史资产/后缀，不按旧措辞重跑。

## Stage116历史研究入口（原文保留）

# 当前研究入口：Stage116双线研究路线，有限方向学习与非μ可见度

用户于2026-11-05重新要求文献研究和路线评估，本次仅完成研究设计，未执行训练/生产。优先阅读[Stage116完整评估](../workbook/2026-11-05_stage116_research-strategy-and-observability.md)及路线§98、信息预算§78。**下面保留的Stage115交接是历史记录；其中“下一唯一相对时序”和“不需另做研究阶段”的安排已被本次请求及Stage116路线更新覆盖。** Stage115、110、108的固定实验仍已结束，不重复执行。

下一次现有缓存方法研究：有限比较训练内/OOF残差×普通/分层风险方向学习，四臂同读出、同复杂度与最终保护。它检查Stage115先用总体残差选字典、后加风险约束的具体缺口，不是追加状态子集或树数网格；OOF需实际训练内分折，不把现成train预测冒充训练外。完整管道的OOF→全train基线变化、来源相关、最终风险和实际尾率必须评价，不能由训练可行性宣称泛化保证。具体实施合同与资源需在有环境时按输入冻结，本报告未执行。

主要物理投入转向独立双侧样本及非μ活动的粒子来源/可见度：同一阶段交一个物理中间量的oracle、可部署代理和能量增量，输入及判定见Stage116§5/§8/§9。先明确新样本、关联和响应是否可交付，不无限扫描旧源；新生产是后续工作包，本次不提交。相对时间保留为有共同控制时可先完成的有限消融，不再是唯一主线；联合prompt/late脉冲模型还需真实波形及弱信号/饱和响应，不能用status伪造。

最终目标、原特征/角色/全部K/困难缺失保留、八层风险和尾部保护不变。1.05仅是低能恢复/非劣效；宣称超过传统须另有比值区间上端<1的证据。真正未开发确认和物理系统仍缺。本次阶段报告与路线已形成，后续按明确科学工作包执行，不反复把同一复盘当新实验。

## Stage115历史交接（以下原文保留）

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
