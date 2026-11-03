# 下一轮执行 Prompt：stage70 π/K替代flux的训练支持pilot

先读AGENTS.md、[stage69报告](../workbook/2026-11-03_stage69_transfer-supervision.md)、[stage68报告](../workbook/2026-11-03_stage68_group-risk-regression.md)、路线§50/信息预算§30与[已冻结来源合同](../ml/configs/alternative_support_pilot.json)。保持F7，不重训stage68/69或继续系数/seed/结构搜索。本阶段编号70，只完成一个有界数据支持pilot，不在本终端安装/配置环境，不自动连开stage71。

## 1. 唯一科学问题

在保持历史角色和已知入射身份保护后，尚未提取的两个π/K替代flux训练来源实际能增加多少true50–100/100–200核心，以及相同reco低pz的高E/high-y/未确认边界支持？重点是选择后、有效62共同读出的新支持与代价，不能把metadata/file条数换算成新独立物理事件。

stage69的transfer概率评分有来源迁移价值，但P_cal最低能.297088/传统.145487，100–200 .278826/传统.226876，全体.306012/F7 .296363，原推广失败。OOF最低能收益未稳健迁移，辅助高transfer仅360个train标签，未确认大多不监督；结束方法预算，按既定分流测训练增补，不把未知原因定为信息极限/纯样本不足。

## 2. 已经选定的两个输入，不能按结果替换

[alternative_support_pilot.json](../ml/configs/alternative_support_pilot.json)由stage69 prepare_transfer_followup在任何新事件读取前，用seed2026110370从固定run的合格canonical train来源中均匀抽取：

- π run200080，pi:00440-00449，`FaserMC-MC24_Genie_sibyll_pi-200080-00440-00449-s0014-RDO.root`，完整绝对路径见config；23个合格来源中1个，源包含概率1/23，stat42220266bytes，继承train＋已暴露challenge。
- K run200081，k:00630-00639，`FaserMC-MC24_Genie_sibyll_k-200081-00630-00639-s0014-RDO.root`；41个合格来源中1个，源概率1/41，stat1293229936bytes，继承train。

已排除任何历史test/cal/validation范围及stage55已提取的替代文件。源文件内计划完整提取，条件事件包含概率1；不是按低E/残差抽事件或只取头前缀。实际entries未测，文件大小不能估N。若缺失/不兼容，报告确切失败，不另选看起来更有利的源。两个文件没有证成parent/seed独立，只作开发训练支持；真正未开发确认需要新生成运动学/parent与随机来源池。

不要重复stage68的22目录/1134文件清单。53个无历史角色文件只在charm max，不妨碍历史训练范围内替代π/K增补，但不能将两者混称新确认。旧31训练/16评价替代源和+139低E均已开发，不重复计新增。原stage55全缓存/metadata和既有files.tsv角色为已知身份参照；不读取locked-test事件。

## 3. 先完成有界QA，再冻结资源与提取

1. 仅这2个指定文件，≤40总头事件核schema、原生成parent/subfile/seed可用性、事件身份/单位/collection。不能凭run/eventID或文件名证明独立；头中缺的字段写未测量。既有生成角色跨flux/几何继承；任何新发现的已知保护关系必须保留。
2. 核实际可复用共同名义重建：d32b0ff3/without-IFT、TI12MC04/FASERNU-04/OFLCOND-FASER-06，优先精确匹配现成Calypso构建/配置；仅源码确需变化才构建。不要恢复全历史生产环境/扫描release，不猜几何或raw代数。先小原生资源QA量时间、CPU/RSS/I/O，验证原生能量/动量MeV→GeV、raw/status及关联。
3. 原选择固定stage55 pz>50 GeV的truth/reco、最高pz leading、truth fiducial及其余cut，无E上限；原fitted-charge cut不变。每来源一次完整文件选择/62共同读出提取，最多2文件/20000输入事件。若实际entries/成本与cap不兼容，在正式完整提取前报告并明确最小缺项，不悄悄换前缀或扩大生产。
4. 62变量契约沿用audited_features：线性纵向/模长动量仅pz0，允许px/py、q/p、弯折；11raw/VetoNu reduced、typed sentinel/合法signed/状态/依赖→NaN。无p0/p1/pz1或ln比值输入，不fit补raw、不nansum补零、不删缺失/巨大动量/未确认/高-y/困难尾。新源全62有效性需实际核对，不能从旧65拟合charge伪造raw。
5. 大批量通过HTCondor，使用本地scratch，一次返回紧凑结果。最多2任务，各≤2CPU/3000MB，CPU总≤2h、单任务wall≤1h、最终≤5MB为拟议预算，QA后冻结精确资源。原PHYS若实际存在且配置匹配，优先复用；需要临时重建只处理2个指定RDO，保存紧凑所需结果后删除中间PHYS/ROOT/xAOD与重复归档，不做新G4或全run生产。预计CPU/I/O未测量，不能把预算记作实际成本。

## 4. 身份、支持与物理解释必须同时交付

- 与stage55已开发完整dataset的incoming(pdg,px,py,pz)精确key比较，并在pilot内部去重；记录全部选择后N、已知复用N、剩余key/事件/来源N。其余原角色保护不能由去重放松。新key不是完整生成谱系独立证明，parent/seed不明继续标未证。
- 角色只在新的训练支持池，现有train/cal/eval41447/8440/14057、原42缺失21/3/7＋11保护和所有旧输出不改。不能把新事件混进旧cal/eval或用旧evaluation挑新增坏例；不推理/重训F7，不用ML残差筛新源。
- 每组件/来源在去重前后报告true50–100/100–200低transfer核心、同reco pz50–100且true≥200/high-y、未确认与high-E3.2–6.4TeV（≥6400无支持写未测量）；N/保守来源、primary确认/y覆盖、raw11/状态/NaN、实际执行命令/单位/资源/吞吐/I/O/产物。没有共同可见度定义就不编quiet；继承unit MC，不把源抽样概率当已测物理flux归一。
- 用真实头schema、回读/选择cutflow、身份/特征对齐和极端/缺失小算例核程序；检查物理原因和程序原因。有限2来源只能测输入产出和支持组成，不能作总体泛化/模型饱和/正式功效结论；新增规模和功效根据pilot后再定，不照抄3000–5000事件目标。

## 5. 停止条件、交付与下一项

本阶段0能量模型fit/新F7推理、0谱profile/toy/SHA、0全run生产。完成2-source pilot即停止，无论剩余支持多少；别自动扩源、调模型或连开stage71。

若有可复用剩余支持，给实测62共同读出质量/组成/身份限制与最小后续训练合同，继续原传统/F7低E/全区/困难双向尾推广标准，不降低门槛。若全部复用、无低E/困难增量或共同配置不可交付，保留零/失败测量，写具体所缺的新π/K generator parent/subfile/seed/共同raw输入请求，结束本轮，不再循环metadata和同eval方法。

写中文stage70 workbook，至少目标/工作/完整实测数据与单位/输入命令/验证与资源/物理程序解释/下一任务及输入验收；未测项目明确未测。更新路线/信息预算/Prompt，Conventional Commit本地提交、不推送。原stage54五项未跟踪工具/缓存及下方协议逐字保留。

共同raw/stage54、interaction/FSI/材料、接受度/背景与真正未开发独立确认仍须交付，不能由本开发补样pilot替代；谱联合表示/有限α非线性研究本轮不启动。

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
