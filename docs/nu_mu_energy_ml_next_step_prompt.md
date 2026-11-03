# 后续执行入口：stage71已完成，先交付真正新生成与共同响应输入

先读AGENTS.md、[stage71报告](../workbook/2026-11-03_stage71_fixed-support-augmentation.md)、路线§52/信息预算§32，以及[具体输入请求](../workbook/stage71_energy_ml/followup_input_request.json)。本轮唯一增补候选3fit已完成并停止；不是继续训练的待执行stage71 Prompt。没有自动安排stage72模型/metadata实验。

## 1. 已测结论与停止规则

π仅28个新key（低E4/2、同低pz困难0）增加到原41447train，原F7参数/62输入/400轮/三seed/unit MC。主增补cal两低E/传统95%比值上限2.480478/1.237628失败，raw也失败；全体/困难及双向尾保护通过，不能替代低能成功。继续原F7，停止这组样本的架构/权重/unit-matched/residual/gate/seed/校准变体；不重算旧预测当新进展，不降低门槛。

K在stage70预算停止，完整支持未测，不能写0产额或把QA K行训练；不自动重试/分块/扩run。小π增补失败不能推论充分补样无效、物理不可能或缺数据唯一原因。真正独立确认及共同响应仍未交付。

## 2. 下一项实际需要的输入与验收

优先交付请求中的实际可访问新π及K GENIE parent/input/subfile/entry映射、真实seed/是否重用运动学说明、跨flux/geometry事前角色与随机未开发确认池/包含概率。不同run/文件名/几何/flux不等于独立parent；四个原生头random_states为空和HepMC event_number0不能认证谱系。

同时交付共同nominal构建/几何和实际Calo payload/单位、11 signed scintillator raw/status与VetoNu reduced及原生Calo能量；01-LG只为兼容F7，不是完整物理响应认证。保留true50–100/100–200与同reco pz50–100 true高E/high-y/未确认、高端和缺失，不按已知残差择源/删尾，不捏造生成N或3000–5000选择后目标。

收到明确新输入后，先在用户授权范围做有界schema/单位/身份与旧key交集/角色/成本分布QA。实际文件和生成身份、角色冻结、共同读出验证及资源成本可交付，才冻结下一单项物理实验与CPU/wall/事件/来源/storage上限及验收。尤其不要只凭16例平均吞吐预算整个K文件；须核最终ClassAd并保留worker硬上限（本轮dry-run900→schedd3600偏差已披露）。不得无合同自动全run/G4生产或新模型拟合。

输入未交付时，明确引用请求中的缺项并保留F7；不以反复metadata扫描/旧预测评价虚构下一阶段。无明确新实验不要虚设已执行stage72；不要未经授权发送邮件/消息要求他人交付。共同raw/stage54、interaction/FSI/材料、接受度/背景仍需完成，下方stage54协议只有进入该支线时适用。

## 3. 任何后续能量实验必须保留

- 模长/纵向线性输入只pz0；px/py、q/p、弯折允许；11raw/VetoNu reduced/typed sentinel/status/dependency→NaN，合法signed负值保留，任一Calo模块缺失总和NaN，无nansum补零、fit-charge替代或困难尾删样。stage70 x已参考化，不能再乘比例。
- 原train/cal/eval41447/8440/14057、42缺失21/3/7＋11保护不改；已有cal/eval均开发，不读locked/未开发确认事件择优。原两低E/传统≤1.05、all/F7≤1.01、困难≤1.03与整体/双向tail50增量≤2pp门槛不降，报告完整能量箱/缺失/空层。
- 按新合同先小QA再Condor，现成LCG子进程、局部scratch、一次缓存/紧凑产物；不重配终端、无无必要SHA，不扩预算或自动重试；实测CPU/wall/RSS/吞吐与逻辑I/O，EOS物理总I/O未测照写。
- 新阶段须中文workbook（实际输入/选择/单位/详细数据/误差与物理程序解释/命令/验证/资源/产物/下一具体输入与验收），更新路线/信息预算/入口并本地Conventional Commit、不push。旧路线§1–52、信息预算§1–32保留；原stage54五项未跟踪工具/缓存和下面6714bytes协议不动。

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
