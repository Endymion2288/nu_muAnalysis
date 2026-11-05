# 当前交接：Stage114研究修正，下一步做测量状态消融与强BDT锚定残差

先读AGENTS.md、路线§96、信息计划§76及[Stage114报告](../workbook/2026-11-05_stage114_measurement-state-and-risk-research-reset.md)，尤其§3–4；再读Stage113/110、Stage78/68及Stage79/80。**本Prompt供具备环境的后续执行端使用；Stage114只做文献/已有结果复盘，没有运行实验。** 下一阶段应交付能量结果，不再写一轮无实验的综述或单独QA阶段。

## 1. 现状与科学问题

Stage113已完成六源60000父行20cut/native闭合；50–100 GeV两个charm来源零支持，100–200 GeVΔMSE=−.09447554689537985但309/500完整draw，按原规则无CI。它不是模型改善或统一失败原因。Stage110固定差转移、Stage108固定三格和Stage104固定密度动作均结束，不重做或延长网格。Stage113正文§5误排表，channel计数引用其原TSV；小负reduced不是坏事件证据，现行配置已允许signed，不据此修cut。

**下一Stage115只回答：逐通道测量状态是否比原读数/mask和汇总状态提供额外信息，使强BDT上的小残差同时改善两个低能组并保住困难侧？** 不是继续平谱重权、再组合三个专家或重学整个GNN。

## 2. 固定样本、基线和两个臂

复用Stage87 split/input/身份、Stage94原cal_select/post和同split强direct_cal；用原Stage55/56 readout与70/81/82/83 support缓存按(origin,origin_row)回接11路status。不要只按run/event联结，不开ROOT/EOS扫源；缓存联结/availability QA并入本任务。未知状态保留NaN，不当0；所有缺失、全部1016新K、隔离和困难/高端完整保留。

train/cal/test=46575/11612/13189，每incoming视图权重和1；pz0>50 GeV，一次方动量仅pz0，允许原px/py/q/p/弯折，raw11/status/typed NaN/合法signed和Calo缺项政策保持。无新split、物理生产、切选、重建或fitted-charge回退。科研参照为同split Stage87 direct，不用可能接触过新test的旧F7预测混比较。

固定f0=原direct_cal log能量。必要的train f0预测只在batch补一次，不重训基线。两臂同容量、同seed、原incoming权重：

- A：原62＋wave_invalid/fit_failure/calo_invalid＋共同status_available，共66维。
- B唯一主候选：同A再加11通道×4布尔量，共110维。四族为overflow bit4、threshold_failed bit1、fit_failure 16|32、wave_invalid 8|128|256，依据已审计producer语义。非互斥，不把status整数当连续值。

逐通道状态是新受测表示，不是已经证明的信息；旧62的NaN清洗完全不改。缺缓存不自动补EOS，显式记录并保留A/B missing路径。

## 3. 一次有限学习与求解

按Stage114§4预先冻结完整实现：每臂在train目标t−f0上建立8棵depth3/min_child_weight200的规则字典，最多64叶基，其他树学习率/正则沿已有配置并固定一个seed，不扫参数。结构冻结后f=f0+Φθ，θ允许正负；零θ精确返回旧点。

每臂一次主求解：min τ，两低能train MSE分别≤τ×传统MSE；all相对f0≤1.01²，原其余五层≤1.03²。原八层的正、负平方hinge尾损失各不得超过f0，阈值为ln1.5与ln0.5。第二次预定求解在τ≤τ*+1e−8下最小化train平均修正平方。固定字典问题凸；报告实际可行性、适用的KKT/界与数值缺口，不仅报success。不得把soft-tail当实际tail率保证；无新offset、局部gate、按真E推理或旧α方向扩展。

原始train拟合残差不是OOF，不冒称来源外泛化。所有truth标签只定义train目标/组或评价，不进入部署输入。采用现成环境，不为此安装求解器或制造长数值认证链；在同任务完成正常小样本/零修正/NaN/状态接线QA后进入完整任务，有实际错误则如实交付。

## 4. 验收和终点

主cal_post两低能最坏B/f0 RMSE比及B/A同端点，原500incoming条件区间；前者上95<1才称共同低能改进，后者也有支持才称状态族增量。状态收益、残差策略收益与最终达标三件事分开。锁定两臂/求解结果后，一次报告完整开发test的八层、状态可用性/缺失、高端、bias/R68、实际正负总tail50和配对区间。

最终标准仍为两低能/传统上95≤1.05、all/direct≤1.01、其余五层/direct≤1.03、八层三向tail差direct上95≤+2 pp。cal/test均已开发，区间不含source/parent/refit/研究选择/真实系统，不是新blind或joint全流程95%保证。不从A/B、raw/offset或不同seed事后换主候选。

拟议唯一CPU批任务4CPU/8GB、内线程1/0GPU，CPU≤1800s/wall≤900s/最终紧凑≤20MB；QA和实际计时并入。它们是未测的上限，不是运行时间承诺。提交目录~/condor/nu_muAnalysis/stage115/；不保存新ROOT/xAOD或整套事件副本。无环境的当前终端不加载事件/模型或复现物理，不做SHA。无法提交时交可执行包和具体阻碍，不能冒写完成结果。

无共同增量则结束这两个固定方案，不续树数/seed/位子集网格，不宣称信息极限。更具物理潜力的下一分支按Stage114§5研究少量VetoNu相对时间；需要同一时间基准与offset/传播/time-walk/fit控制，弱信号和缺失保留，不能直接投入未校准时间。扩已有父分母和精确producer定义仍可作解释任务，但不把六个稀有单元都有CI当这次缓存能量学习的前提，不改写Stage113端点或自动扩训练集。

先中文workbook记录实际结果、输入/命令/资源/局限及一个具体下一任务，再本地Conventional Commit，不push，不自动开启再下一实验。Stage54历史控制已在Stage85完成，下面后缀按原文保留，不按其“未完成”旧措辞重跑。

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
