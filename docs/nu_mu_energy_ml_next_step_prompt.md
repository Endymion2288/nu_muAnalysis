# 下一轮执行 Prompt：stage95 可部署轨迹候选与关联信息的可用性测量

先读AGENTS.md、[stage94报告](../workbook/2026-11-04_stage94_architecture-comparison.md)、修订路线§76、信息计划§56、stage93 §4.4/6.4和stage19既有全SP集合试验。**stage94五格九fit及完整评价已完成；本轮转新增关系信息，先做小QA和紧凑可用性测量，不追加能量训练或自动开始后续阶段。** 原stage54后缀仅为历史支线，stage85已交条件活动控制，不因此重做。

## 1. 已有证据与本轮问题

现有摘要上B/A、D/C、E/C有本次总体增量，C/B区间尚含1；E三seed最低能/第二低能/全体/低pz真高E/high-y log-RMSE .276027/.251510/.289843/.671125/.616675，最低能传统.145661、全体direct.287491。11候选均未过联合目标。E相对stage92改善主体/困难而损失其低能优势，概率输出总体68/90coverage62.602337%/86.253883%。当前不能宣称学习最优或观测到信息极限，也不能无限延长同62列的架构、gate或reweight。

本轮回答：**当前真实载荷中，leading之外是否有可靠、可部署、与现有全局摘要不同的轨迹候选与hit/外推关联？它们能支持何种最小关系表示，以及哪些歧义仍不可核？** 配置存在列名不等于所有source都存有有效关联；不能把全SP无关联集合包装为新信息。

## 2. 固定输入与小QA

复用已有已知PHYS source清单、stage87 split/incoming联结及stage94协议。保持89033兼容池/46575train/11612cal/13189test/17657隔离、incoming权重和1016新增K；不重新划分、不生成新MC、不要求新的独立样本作为开发前置。主体条件pz0>50 GeV，保留低pz、低能、高-y/未确认、缺失、高端和全部尾。

动量一次方只用各候选pz0，允许原px/py、q/p、弯折；不引入p0/p1/pz1、动量比。11路scintillator普通charge仍raw；typed NaN、合法负raw、Calo缺项与status合同保持。truth只用于核得关联后的诊断，不成为可部署输入或选择gate。

先从固定train/cal身份抽≤40个不同incoming，覆盖已知π/K/charm来源、pz50–100与更高动量、有效/缺失或失败状态；不打开test事件或按模型误差挑“可救”案例。只对已知源读取必要branches/有限entry，核：

- 全轨迹数组长度/单位、轨迹状态端点/方向、station/layer/module和hitSet身份的语义；计数/占位/合法负值，空集合不能当成缺失。
- hitSet是否有跨轨迹可比的同一身份；共享hit分母、重复候选和多次重建视图不能冒充独立粒子。
- veto/Timing/Calo外推坐标是否对应同一轨迹和探测平面；没有可靠协方差/传播就不构造伪显著性或硬匹配真μ。
- 原incoming/source/entry联结，原raw/status与全选择闭合；可在data定义的列与仅MC列清楚标注。

保存实际QA身份、源/entry清单、分支schema与有效率、读取字节/请求范围/耗时和实际内存；未测项写未测量，不用metadata替代载荷。优先现有CVMFS/已匹配构建，无源码变化不重建Calypso，不递归扫全EOS。

## 3. QA后冻结一次紧凑批量测量

只在确认schema/联结可用后冻结一种候选与关联定义，记录排序/截断/去重及缺失语义。默认研究固定2048个train/cal incoming的来源覆盖小批量，身份选择只用source和观测pz/状态，预先给出π/K/charm与低pz支持；若可用源不足，不静默替换有利源。每incoming的多视图关系和用途保留，不能把重复视图当2048个独立粒子。不得修改原模型风险样本或丢困难者。

大批量按source/文件分片走HTCondor，有足够独立分片时申请8CPU，否则4CPU；每进程BLAS/ROOT线程1，避免多进程重复打开同一大文件，复用basket/branch读取。QA后按实测吞吐、内存和I/O冻结资源，默认单作业8GB起/总CPU≤6h/紧凑≤20MB，不将默认当可执行性能保证。没有GPU优势的提取不占GPU；后续有拟合时再按实测选择本地GPU、Condor GPU或用户已配置Kubeflow。

只保存紧凑候选几何、允许动量、质量/状态及候选间共享hit/外推距离/计数摘要，尽量用稀疏边；不存逐hit点云、xAOD/ROOT副本，不新增G4/reconstruction。可核真值对应时另存最小诊断标签，禁止把其混入模型features。

## 4. 实测交付与判据

分别给全体和cal预定义X组的候选数分布、可用率/缺失/空集合分母、共享hit与重复率、轨迹状态/探测层一致性、leading与可区分备选的比例；按来源及低pz列支持和统计不确定度。诊断可另外按真E/y展开，但不据其选择部署候选。若真值到轨迹关联确实可核，给leading误选率、候选覆盖真μ率与oracle改善上限及明确定义；否则这些项未测量，不猜真μ身份。

本轮成功是**确认一族新的可部署关系载荷、测量其有效支持/歧义与程序闭合，并冻结后续一次匹配输入消融**。不要求提前证明GNN能量收益，不能因几个离群例停止分支。若关联无法核实，给实际缺失字段/来源和仍可测的几何关系，不能以未知原因宣称已无信息。

后续拟合方案应比较当前审计摘要与“同摘要＋新关系”且保持相同split、后处理和风险层；先最小集合/关系模型，再考虑GNN或attention。具体fit数、模型和资源等本轮测量后冻结，不自动恢复大模型竞赛。stage94中B/A、C/B、D/C、E/C的控制不再重训，stage92 moment可选且不阻塞本轮。旧stage85 tracker活动、旧数值认证链、纯noise反求不重做。

## 5. 阶段交付

先写中文stage95报告，包含目标、实际身份/源/配置/命令、有效率/分母/图表、数值/单位/不确定度、程序与物理解释、I/O/CPU/内存、失败/未测量和下一具体任务；配套紧凑manifest/schema/表图和代码本地Conventional Commit，不push、不自动进入stage96。历史路线只追加，保留下方stage54后缀逐字内容及原五项工作树；真实response、interaction/FSI/材料/Calo/接受度/背景和最终未开发确认仍待完成。

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
