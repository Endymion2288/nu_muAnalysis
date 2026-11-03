# 下一轮执行 Prompt：stage68 完整读出的群体风险受约束回归

先读AGENTS.md、[stage67研究复盘](../workbook/2026-11-03_stage67_research-reassessment.md)、[stage62](../workbook/2026-11-02_stage62_smooth-continuous-response.md)、[stage66](../workbook/2026-11-03_stage66_trainingout-response.md)、路线§48/信息预算§28。stage67是研究报告，无新实验；原拟stage67身份审计尚未执行，改为独立补样准备，不冒充已完成，也不作为已有缓存方法实验的无限前置。下一实验使用stage68。

继续保留F7，结束现有模板轮换/α=0投影链。本轮在有CERN环境的节点完成一个直接推动单事例目标的训练实验，不重跑stage62–66，不在本终端配置环境。

## 1. 唯一科学问题

**完整62读出＋完整train，直接优化低真实E与困难组风险，是否比同容量的普通回归获得更好的泛化取舍？**

stage62已有完整读出概率增量，但A低E50–100/100–200 log-RMSE=.277739/.259126，传统=.145487/.226876，全体仍差于F7；其最低能25/208尾贡献67.8241%平方log损失。stage58–60风险约束只在四输入、cal小样本及三专家凸包中学习，不能替代本实验。不要把本轮改成flat、普通残差、门控续调、NRE结构/先验或点估计器搜索。

物理解释沿用stage55/58：pz>50选择下true50–100偏向低y，但相近低pz/低活动仍包含高E/high-y低可见者。不能把传统在真低E的优势推广为“全部低pz应降低预测”，也不能将选择近似当部署真值边界。

## 2. 输入与训练角色

- 只读stage55 `dataset.npz`、stage56 `readout.npz`和必要身份/来源metadata、既有F7/传统/stage60/stage62固定参考。train41447/91来源，cal8440/16，eval14057/22；原pz>50选择、最高pz leading、truth fiducial和保护不变。cal/eval已开发，不叫blind。
- X经`audited_features.load/build`得到同62列，线性模长/纵向动量仅pz0；px/py、q/p和弯折允许。不加p0/p1/pz1、次轨迹线性动量或truth/y/来源输入。11scintillator raw、VetoNu reduced、合法signed/typed NaN/状态/依赖规则沿用。
- 不删缺失、巨大动量、高-y、未确认、负修正和大尾。原42缺失者eligible21/3/7、另11既有保护保持；不fit补raw、不nansum补零。原部分fitted-charge cuts不改，本轮不测接受度变化。
- 不读locked-test或大型ROOT/RDO、不新生产/重建、不恢复已删PHYS、不拟造alternative raw、不做SHA或谱toy。

## 3. 两个模型、最多八fit

1. C：同F7级depth5/400轮的普通平方log损失BDT；R：相同输入、容量、正则、单seed的受约束群体风险BDT。两者都直接预测t=log(Eν/GeV)，使用相同初始化/参数化。固定一个seed2026110368，不扫seed/结构/初值。C为匹配控制，原F7仍是推广参照；不能以C更弱降低成功标准。
2. train内按既有保守来源分三折，遵守已有generation-range/精确入射ν保护，同一已知身份不得跨fold。每折C/R各一次，再各一次全train最终fit，合计8fit。折内所有归一化、参照风险及模型/对偶更新只用其余train，留出折不早停、不调对偶、不挑checkpoint。不拿已见train标签的原F7预测冒充独立OOF基线。完整谱系未认证的限制如实保留，不称新独立确认。
3. 令`R_g=mean_g[(f−t)^2]`。低能目标为`min max(R_50–100/Rμ_50–100, R_100–200/Rμ_100–200)`；μ为同支持log(pz0/.8)。保护全体`R_all≤1.01² R_all(C)`，保护true≥200、reco pz50–100、high-y≥.8、未确认各`R_g≤1.03² R_g(C)`。真值仅定义训练/评价组，部署只使用X；重叠组须用各自N正确归一。
4. 用非负对偶权重/functional-gradient boosting实现有限的风险训练；每轮仅加一棵树，对当前各组平方误差构成的加权梯度/Hessian作更新。训练前冻结低能minimax和保护组的更新规则、尺度、dual上界/数值处理、固定400轮终点/唯一checkpoint政策，做小型算术/梯度QA。不因cal/eval结果改规则或多轮重训，不将对偶更新包装成额外候选搜索。
5. C的折内训练风险是R的训练参照，可能乐观；必须并列报训练与来源留出风险，不能把满足训练约束当泛化保证。没有全局最优/自动可行性定理；预算内找不到解则记录本实现未找到，不声称所有完整读出都不可行，不连开优化器认证阶段。
6. 不在首轮再叠加Huber/CVaR/各类尾损失或辅助分类头。尾部用真实指标验收，不能裁剪或弱化大误差让分数变好。

## 4. 评价与决定

- OOF比较C/R原始预测，仅在各自未参加训练/对偶选择的train来源上计算；最终两模型raw及各一个全cal global log-offset均报告。全cal offset不是OOF，点校准不等于概率校准。不得从eval选择raw/cal或C/R“最佳版本”替代预定主候选R。
- 同一最终eval对传统/F7/stage60/stage62固定参考，报告两个true低E层、所有能量箱、全体、true≥200、reco pz50–100/100–250、high-y、未确认和缺失组。给N/来源、log-RMSE、mean/median bias、R68、双向tail50/100、尾部平方log损失份额；3.2–6.4TeV单列，≥6400无支持标未测量。不要仅报告macro或中心宽度。
- 原推广标准不改：两低E/传统RMSE比来源95%上限≤1.05是恢复；改善下限>0才叫优于传统。全体/F7上限≤1.01、困难组≤1.03、关键tail50增加≤2pp。训练中相对新C的限制不替换最终对F7的限制。这些是研究取舍，非已测detector容忍度；相对C有改善但未过原门槛应分别报告。
- 500次component分层保守来源配对bootstrap只重抽固定预测，不重训；注明不含完整重训、校准、谱系、响应/interaction或研究选择误差，不作多重比较修正。train/cal/eval区分，不以负配对/重抽样当新独立支持。
- R在OOF与eval有稳定收益并过原门槛：冻结候选，安排新来源/共同raw确认，不自动部署。train改善而OOF/eval不转移：停止同数据调权，转定向独立混合边界支持。OOF有收益但未过原F7标准：保留研究结论，不放宽门槛。训练/OOF均无实用改善：结束本次目标实验，下一项在stage67§5的物理transfer/可见度分量或新支持中选一项，不续扫对偶/seed。

## 5. 资源、报告与保留任务

- 正式fit前冻结stage68协议，先少量样本验证组归一/梯度/Hessian、有限/NaN、推理不读truth及来源折；仅做资源/算术pilot，不增加正式候选。复用CVMFS与紧凑缓存，不重建无变化C++。
- 拟议最多4个Condor任务（各sourcefold两模型及一个最终两模型任务），每个≤2CPU/3000MB、累计CPU≤3h、紧凑最终≤20MB；先以pilot实测调整并冻结资源，预算不是实测成本。批量走Condor，记录actual wall/CPU/RSS及进程/I/O口径。只保存模型、必要OOF/cal/eval点输出和聚合轨迹，不存批量输入副本/重复JSON。
- 写stage68中文workbook：目标/输入/选择/单位、完整数据与区间、训练/OOF/eval对比、程序与物理解释、实际命令/验证/资源/I/O/产物及唯一下一项验收。所有未测项写明，更新路线/Prompt后本地Conventional Commit，不推送，不自动运行后续阶段。
- 独立补样准备沿用[stage66§9](../workbook/2026-11-03_stage66_trainingout-response.md)：原200080–200101已知22目录一层清单、≤24文件/≤40头事件的限量身份核实，不递归EOS。旧替代31训练/16评价来源与+139低能已开发，不能称新确认。其任务是找到可交付新源/缺失生成身份，不作为本轮唯一科研产物，也不自动启动生产。新支持重点为低E核心＋同pz高E/high-y/低可见成分；quiet缺共同读出定义时明确未测量。
- stage54共同signed/rectified raw、状态/积分窗/mask与有效占据、ν interaction/FSI/材料、接受度/背景和真正未开发确认继续交付。stage63的4×4阴性不重跑；后续联合量若做须嵌套保留S原格，α≈.32需有限范围非线性检验，本次不连开谱研究。

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
