# 下一轮执行 Prompt：stage67 定向独立补样身份与可交付性审计

先读AGENTS.md、[stage66实测](../workbook/2026-11-03_stage66_trainingout-response.md)、路线§47与信息预算§27，再读stage55低能补样、stage56变量/保护、stage61物理目标。stage66一个任务完成，不覆盖协议/结果、不重跑正式Fisher/来源抽样；继续F7，结束本轮模板轮换，不加局部参数/布局/先验/toy。

## 已知证据与唯一问题

cal权重训练外模板的S自由条件δf−.346904 [−.733243,+.057334]pp，仍近旧train−.362477pp；低组件−.165032pp。区间跨零是证据变弱，不能称残差消失或唯一归因训练内模板。最低能charm cal0/eval1、31%重复eval也零支持，100–200 charm仅6/17例；同pz高E/high-y/低可见/未确认也需要独立支持，不能只补容易低E核心。

本轮只回答：**现有数据中哪些支持已被开发/重复/保护，用户指定200080–200101中还有什么可核身份的候选输入，可以形成怎样一个最小定向补样合同？** 不以metadata条数冒充新独立事件，不声称已测功效或纯样本量收益，不自动启动正式生产。

## 1. 固定输入、角色和身份

1. 既有`ml/configs/low_energy.json`、`low_energy_files.tsv`、`ntuples/energy_ml_stage55/dataset.npz`与`extraction_metadata.json.gz`，stage56 `audited_features`/raw审计及F7原角色/身份保护，stage64/66支持表。只读已经开发的缓存和必要身份metadata，不读locked-test事件/预测，不恢复历史大ROOT/RDO/xAOD或做SHA。
2. stage55替代flux已经开发过31训练来源、16评价来源，新增true50–100训练139例；完整生成谱系仍未认证，保守component×generation-range跨run角色一致，精确入射ν(pdg,px,py,pz)复用有原保护。这些来源不能再次叫未开发独立确认；F7未用某些替代样本作权重训练也不撤销早期研究曝光。
3. 不改变pz>50/原cuts/最高pz leading/真值fiducial/角色/保护，F7的62输入/pz0-only线性动量/11raw/VetoNu reduced/signed/typed NaN沿用，px/py、q/p、弯折仍允许。0F7训练/推理或重新校准、0谱fit/profile/toy、0重建/新生产。
4. 开始批量前冻结stage67不可覆盖协议：缓存schema/单位、身份主键/精确复用与谱系证据等级、角色保护、支持分层、候选选择顺序、metadata目录/文件/QA事件上限、I/O/资源/停止。小QA只核字段/身份/单位/读字节，不按模型残差/低E结果挑候选。

## 2. 现有缓存的可测支持

按原nominal/alternative、run/production/generation-range和角色，列实际N/保守来源及精确重复/保护计数：true50–100、100–200、reco pz50–100且true≥200、与high-y交集、未确认；所有困难尾/缺失/负修正保留，不重定义角色。沿用stage55/56明确的eligible/保护标记，不把原95,748原始选中者与41,447 F7训练者混称同一总体。

检查精确入射ν身份在不同flux/run/几何间的复用，保留原键/单位和合法signed值；不同四动量或run/eventID不同不能自动证明独立谱系。没有可信生成ID/种子/子文件联结则标谱系未证。输出需要支持的层和已有曝光来源，而非新性能或事件数功效。低可见若缺共同raw状态/积分窗/有效mask定义，明确未测量，不拿小ML修正或零charge定义quiet。

缓存统计经Condor，按source分组/分块复用，禁止保存逐事例副本或重新生成旧95K缓存。报告实际读取/CPU/wall/RSS；文件大小、系统计数和EOS实际网络/物理字节分开。

## 3. 替代runs的有界输入审计

只访问原manifest指向的200080–200101共22个run的`rdo/s0014`已知目录，一层文件清单/metadata；明确其中nominal六run和替代16run。不能递归扫全EOS或从不同几何/flux名称推独立。对照stage55实际成功301源与技术失败257、已用range/角色/保护，不能只对照原计划302。

在看到新候选事例前按run/production/来源范围确定最多24个文件、总≤40个native头/schema/身份QA事件，不能按低能残差选源或只取有利前缀当物理样本。优先用已有匹配构建/头读取工具；环境不匹配则交付可测的头信息和缺失字段，不重编译或恢复完整历史生产链。

候选分为已开发、受保护、精确重复/几何变体、未用但谱系未证、具可核谱系的新来源；分类依证据，不能为满足数量目标升级未知。metadata能证明文件/条目/身份可访问，不能证明通过选择后的低E数、同pz困难支持或功效；这些未测项目明确标注。不得把重复digitization/重抽样/替代flux同一入射ν叫新增独立运动学支持。

## 4. 交付、预算和停止

交付实测缓存支持/复用/保护表、候选来源证据表、最少缺失生成身份或quiet/raw输入，并给**一个**最小定向提取/生产输入合同：具体源与角色隔离/生成谱系要求、共同重建和变量定义、低E及同pz高E/high-y/未确认支持、去重与校准/最终未开发确认边界、pilot测得I/O/计时对应的预算和停止条件。无法证明独立输入时明确未定，不用metadata清单冒充新增物理样本，也不自动开生产或新模型。

拟议≤1Condor/1CPU/**3000MB**、CPU及wall≤600s、实际新增读取≤1GB、紧凑最终≤5MB；先小QA实测冻结，缓存批量统计经Condor，dry-run和最终ClassAd均核，不静默追加任务。0F7训练/推理、0重建/新生产/原始ROOT大提取、0谱fit/profile/toy/SHA。本轮新独立事件数/选中支持/功效和实际任务成本均未测量，不照抄旧3000–5000目标。

先写stage67中文workbook（输入/选择/身份与单位、实测支持/重复/未知和源表、命令/验证/资源/I/O、物理/程序限制、唯一最小下一任务及验收），再更新路线/信息预算/Prompt并本地Conventional Commit，不推送，不自动运行后续生产。若只有未证谱系或无新源，给具体缺失输入和仍可推进的共同raw/响应任务，不靠扩大目录扫描或更多模板/toy制造答案。

继续F7，stage62概率有用但低能点失败、stage63固定J布局阴性保留。stage54共同signed/rectified raw/状态/积分窗/mask与有效占据、ν interaction/FSI/材料、接受度/背景和真正未开发确认仍必须交付；沿用stage61连续正向谱/有限MC文献入口。stage54已有未提交工具/缓存与下方原协议后缀不改、不混入提交。


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
