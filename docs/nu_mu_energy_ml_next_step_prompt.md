# 下一轮执行 Prompt：stage69 可信transfer辅助监督的匹配点回归

先读AGENTS.md、[stage68报告](../workbook/2026-11-03_stage68_group-risk-regression.md)、[stage67研究复盘](../workbook/2026-11-03_stage67_research-reassessment.md)、路线§49/信息预算§29；必要时读stage55/56变量与stage62 MLP实现。stage68已完成8fit，不重训或继续同一对偶更新。继续F7，下一阶段编号69，不在本终端安装/配置环境。

## 1. 唯一科学问题

可信truth transfer标签辅助共享表示，能否帮助相同reco区分低E核心与高E/大transfer混合，改善两个低能层而保住全体及困难尾？这是stage67§5辅助监督的有限对照，尚不是完整μ产生响应＋H＋可见度的机制模型。不能将普通残差改名，也不能把标签视为新增观测信息。

stage68来源OOF true50–100 C/R=.267998/.223814、100–200=.244169/.286366，三折均同向；eval R_cal最低能.253745/传统.145487、100–200 .308859/传统.226876、全体.300964/F7 .296363。最低能20/208上尾占73.7434%损失；高端中位bias−44.144%。早期低能对偶积累偏向第一组，最终未达所有训练保护；不能以此宣称全部62列信息极限。原对偶预算结束，不续扫参数/seed/损失或做优化证书。

## 2. 输入和角色不变

- 仅复用stage55 dataset、stage56 readout及必要stage68来源协议，完整62列经audited_features，线性模长/纵向动量仅pz0；px/py、q/p、弯折允许。11raw/VetoNu reduced、合法signed、typed invalid/status/dependency→NaN均不变。不加p0/p1/pz1、ln比值或新次轨迹线性动量。
- 同train/cal/eval41447/8440/14057、91/16/22来源；原pz>50及其余选择/保护不变。原42缺失者21/3/7 eligible、另11保护，未确认、高-y、巨大动量、负修正和所有尾保留；不删例、不nansum补零、不fit补raw。原fitted-charge cuts不改，本轮不测接受度变化。
- stage68 protocol v2冻结三来源折，并在每折训练端剔除共享留出精确入射四元组者；held13820/13667/13960，train22795/22878/22543，最终train41447。复用此政策，不为新标签重分折；同已知generation-range/入射身份不得跨训练与留出。完整谱系未证，来源相关限制继续报告。
- 不读locked-test事件/大ROOT/RDO、不新生产/重建、不重训F7或重算stage62–66、不做SHA/谱profile/coverage toy。cal/eval均已开发，不能称blind。

## 3. 两个匹配模型、八个固定fit

1. C与P使用相同62输入＋NaN mask、train-only清理/尺度、共享两层64 SiLU、一个logE回归头和同样的三类辅助头。沿用stage62的小型MLP实现经验，不比赛BDT/ResNet/Transformer。两者参数化、初始化、优化器/批顺序与容量匹配。
2. C只优化主平方log误差；P额外添加固定系数.1的辅助transfer交叉熵。标签仅在可信confirmed且finite y∈[0,1]处有效：y<.2、.2≤y<.8、y≥.8；CE按实际有效事件N归一，主损失包括所有原事件。先核truth y定义、单位、边界和各role/来源覆盖；无法可信标注则明确缺失，不凭空补标签。未确认不等于错轨，也不强贴某一transfer类。
3. 辅助标签/真E/身份仅训练和评价用；部署回归及辅助软概率仅X。不要把辅助头解释为已识别可见度或专家物理组成；不硬施E≥测量pz，不把reco quiet等同小H。单回归头主目标明确，不自动添加完整混合似然/CVaR/新风险对偶或更多辅助损失。
4. 单seed2026110369、固定120epoch，不扫辅助系数/结构/seed；三来源折各C/P一次，再各全train一次，共8正式fit。其余实现如train-only尺度、batch/optimizer学习率在任何正式结果前经小型算术/资源pilot一次冻结；不以cal/eval选择或早停。唯一checkpoint为末端120epoch；pilot只作QA不增加科研候选。
5. source OOF均raw；最终C/P各一个全cal mean log-offset，raw并列，事前主候选P_cal。不从raw/cal或辅助头诊断中选有利版本。全cal offset不是OOF或概率校准。

## 4. 验收和解释

- 同一OOF比较C/P/传统，F7 train内输出不能冒充OOF。最终eval对传统/F7/stage68 C/R及必要stage60/stage62固定点参考，报告两个低能层、全能量细箱、3.2–6.4TeV及≥6400支持、全体/≥200/低pz/high-y/未确认/缺失组。
- 每组N/来源、log-RMSE、mean/median bias、R68、双向tail50/100及尾平方log损失份额；辅助分类用未参加训练的来源指标/支持判断监督是否可迁移，不能以分类分数替代能量推广。不删尾、不以中心更好冒充全样本恢复。
- 500次component分层保守来源配对bootstrap固定预测/offset，注明不含重训、校准重估、完整谱系/响应/interaction和研究选择误差。薄来源/空组明确无精确CI/未测量，不作多重比较修正或新独立确认。
- 原门槛：两个true低E/传统RMSE比95%上限≤1.05为恢复；gain下限>0才称优于传统；全体/F7上限≤1.01，≥200/低pz/high-y/未确认≤1.03，关键双向tail50增加上限≤2pp。新C即使较弱也不能降低门槛，raw/cal分别验收。
- 若P来源OOF及eval有稳健增量且过原门槛，冻结候选并转真正新来源/共同响应确认；只训练好或分类迁移而能量失败，不能当成功。若仍失败，结束此辅助监督分支，转新π/K生成身份输入合同，不接同eval结构/损失轮换。保留有限支持、容量/训练与响应原因，不把未知归成物理不可能。

## 5. 资源、补样合同与交付

- 先小pilot验证标签mask/N归一、尺度/NaN、梯度、仅reco推理和折身份保护，再冻结精确协议。拟议≤4 Condor任务、每任务≤2CPU/3000MB、总CPU≤3h、紧凑最终≤20MB；实际由pilot计量并执行前冻结。仅交互小验证，批量训练走Condor。保持scratch本地训练、少量紧凑返回，不保存重复输入或ROOT。
- 补样准备已有限完成：stage68 supplement_runs/candidates表的22目录1134文件名中161历史test范围保留保护，53无历史角色文件仅charm max；最终200090/200101候选共享charm:00190-00199，生成parent/seed未证，0新独立事件/0 ROOT头/事件读取。不要重复一轮全EOS清单或把不同flux/几何叫新独立支持。
- 最小新源合同需要π/K低E核心＋同pz高E/high-y/未确认边界，原generator parent/subfile/seed与精确入射联结、全历史角色保护、共同重建/raw定义；先分层随机小pilot量选择后支持、包含概率与I/O，再定新增规模。旧替代31训练/16评价来源和+139低E均已开发。现两个charm候选不能替代这一合同，本轮不自动生产。
- 完成中文stage69 workbook，包含目标/输入/选择/实测数值和单位、协议/训练与OOF/开发eval、物理与程序解释、验证/资源/I/O/产物及唯一后续任务；未测写未测。更新路线/信息预算/Prompt，本地Conventional Commit不推送，不自动执行stage70。
- 原stage54未跟踪工具/缓存及下方协议完整保留。共同signed/rectified raw、状态/积分窗/有效mask/占据、ν interaction/FSI/材料、接受度/背景和真正未开发确认继续交付；谱联合量若重访须嵌套保留S，有限α需非线性检验，本次不连开。

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
