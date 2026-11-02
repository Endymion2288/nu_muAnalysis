# 下一轮执行 Prompt：stage66 权重训练外模板的局部响应检验

先读AGENTS.md、[stage65实测](../workbook/2026-11-02_stage65_spectrum-hardness-identifiability.md)、路线§46和信息预算§26；stage61为物理目标，stage63/64为模板/分解约定。stage65一个正式任务完成，不覆盖协议/结果、不重跑正式来源抽样；继续F7，不恢复J布局、六自由箱或能量模型搜索。

## 已知结果与唯一问题

stage65单个高组件硬度α=0方向自由后，参考有限MC误差比M/S为1.026859/1.014748，12中央/6000来源Fisher均满秩；eval总δf虽降至M−.005299/S−.060672pp，S混合+.301805与条件−.362477 [−.623026,−.072791]pp相消，低组件条件仍−.197460 [−.368548,−.016856]pp。不能称响应闭合或硬度修正成功，局部δα约.32的非线性有效范围未测量。

本轮只回答：**将响应模板改为未参与F7权重训练的cal，eval条件偏移证据如何改变，小模板的有限MC/来源/缺层代价是否还允许判断？** 只有cal→eval一个新增方向，与stage65既存train→eval并列；不反向择优、合并模板或重校准。cal也参与既有global offset、谱/生产/几何不同，因此是权重训练外的开发响应检验，不是纯过拟合隔离或新独立确认。

## 1. 输入、角色和冻结

1. 只用stage63 `ml/artifacts/stage63/observables.npz`及原`protocol_v2/templates/support`，stage64支持/分解，stage65协议/模型/Fisher/投影/残差/来源汇总。原train→eval只读既有stage65，不重跑其500次；没有新F7推理/能量fit/ROOT/RDO/locked-test、原始raw补读、新生产或SHA。
2. 固定M_mu/S_scalar各16常规格+专用无效格。pz>50 GeV、原train41447/cal8440/eval14057与91/16/22保守来源，62输入、pz0-only线性动量/11raw/VetoNu reduced/signed/typed NaN、全部保护/缺失/未确认/high-y/负修正/困难尾/溢出不变。
3. 唯一新增模板cal8440=低841+高7599，来源16；目标eval14057=低1114+高12943，来源22。二者没有参与F7权重训练但都已经开发，cal参与旧global offset，原train冻结格来自训练内响应。不重训/重校准、不假称新独立角色。
4. 任何新Fisher/投影前冻结不可覆盖stage66协议：cal参考分解顺序、单α=0方向、名义eval f_true/N1000、协方差/秩/边界/区间/未匹配规则、比较量、预算和停止。先小合成QA，不看结果后挑模板/层/分箱/先验。

## 2. 同一个局部模型，更换响应模板

cal低/高模板a/b由原M/S格计数，高组件C_z=Σ_cal,high,z[log(E/400GeV)−ubar_cal]/MH_cal。D_f=a−b、D_α=(1−f_eval)C；固定f_eval=1114/14057、N_selected1000、α=0。truth仅构造响应，不进入部署统计量。没有α扫描、非线性谱fit/修正或新参数。

协方差沿用stage65数据+两MC条件multinomial，模板计数改为实际cal低841/高7599，不能沿用41447计数或把重抽样当新事件。给已知/有限MC的固定/自由硬度σ_f、σ_r/r、σ_α、相关、标准化秩/条件数；与stage65既有train→eval并列。归一化导数/对称小步差分、Schur/二维逆、正交/共线/零方向和边界QA沿用，容差先冻结。奇异/未定义保留null/NaN及次数，不用ridge/伪计数/先验救有限精度。

在相同固定trueE边界50/100/200/400/800/1600/3200/6400GeV×pi/k/charm下，**cal是唯一参考顺序**，对eval−cal低/高组件响应差作共同支持混合/条件/非共同支持守恒分解。每项实际乘f/(1−f)，固定/自由硬度投影δf/δα，保留全部signed残差、half-L1及加权范数；不能只给总偏移。旧train→eval分解作为不同参照的开发比较，不把两种条件项之差直接叫训练乐观性。

## 3. 有限支持、来源区间和结论边界

1. 500次pi/k/charm分层cal/eval独立来源抽样，M/S配对；每次重估cal a/b/C/V/算子及eval经验响应/共同支持，固定名义f_true。先冻结新seed，保留无效重复/边界/物理域外线性外推，区间与有效/无效数并列。原train重复仅读stage65汇总，不新增train抽样或三方向扫描。
2. 显式记录cal true50–100 charm0、eval1/1来源，以及100–200 charm cal6/2、eval17/3；未匹配质量不删、不补造cal响应，不按薄层删除事件。列实际事件/来源、来源ESS或权重集中度和缺层重复频率，重抽样不能制造支持。
3. 验收是守恒/导数/矩阵复核通过，原角色/保护不变，且能说明条件偏移证据改变多少、精度代价与哪些缺层限制解释。区间含零不等于响应相同，区间更宽不等于修正成功。M不依赖能量ML权重，是共同来源/混合影响的控制，不能据S差异单独证明过拟合。
4. cal/eval混合不同、粗箱内E/y/几何/interaction未固定、cal参与offset、两role已开发、有限来源/谱系未认证，都进入限制。区间不含重训/完整谱系/校准/detector系统；不是coverage toy、data验证或未选中flux。不能据较小局部总δf部署F7修正，也不把α约.32的旧投影当有限位移闭合证据。

## 4. 预算、交付与停止

0能量训练/F7推理、0ROOT/RDO/新生产、0非线性谱profile/coverage toy；不增加J布局、六箱、方向、先验或新网络。先pilot实测再冻结，拟议≤1Condor/1CPU/**3000MB**、CPU及wall≤600s、紧凑最终≤5MB；正式500次来源抽样经Condor，提交前dry-run并核最终ClassAd，不静默追加任务。实际资源/收益未测量。

复用小缓存、group直方图/来源矩阵，避免重复ROOT/I/O或持久逐事件副本；文件大小、进程计数、Condor传输和actual EOS物理/网络字节分开，未测量明确写出。独立逐事件计数/降维协方差与预定3重复复核即可，不重跑完整正式来源实验。失败/缺层/不确定如实交付，不循环模型或靠更多toy制造覆盖。

先写stage66中文workbook：样本/选择/输入/单位、cal/train模板并列的精度/条件偏移及支持/残差表图、实测命令/资源/验证、物理和程序原因/限制、最小下一单项输入与验收；再更新路线/信息预算/Prompt并本地Conventional Commit，不推送、不自动启动后续。若来源或低能支持不足则结论未定，列需要的真正独立低E及同pz高E/high-y/低可见/未确认输入，不自动开生产或参数网格。

继续F7，stage62概率增量但低能点失败、stage63固定J阴性保留。共同signed/rectified raw/积分窗/状态/mask与stage54有效占据、ν interaction/FSI/材料、接受度/背景及真正未开发来源仍必须交付。沿用stage61连续正向谱/有限MC文献入口。stage54已有工具/缓存和以下后缀保持，不混入提交。


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
