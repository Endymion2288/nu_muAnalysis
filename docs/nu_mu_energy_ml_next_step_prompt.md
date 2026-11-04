# 下一轮执行 Prompt：stage98 原生重建中的真实轨迹关联及协方差信息测量

先读AGENTS.md、[stage97报告](../workbook/2026-11-04_stage97_joint-candidate-ablation.md)、修订路线§79、信息计划§59、stage95 source_semantics/representation与stage93复盘。**stage97恰2fit及完整评价已完成，不得重跑；本轮0能量fit、0新MC/重建、0test载荷/风险，购买一次真正关联/误差信息证据。不自动执行stage99。** stage54历史支线保留，stage85已完成条件活动控制，不默认重做。

## 1. 已测依据及唯一问题

stage96加入候选边际几何未确证总体或最低能改善，stage97再检验同输入的逐候选—leading边联合消息：A常数新增消息、B正确配对，均31553参数，原完整角色和K支持，恰2fit。test all .296267/.296744，B/A1.001610 [.999258,1.004056]；最低能.300780/.297487，传统.145661；低pz真高E .684707/.681645，direct.658177。多轨迹850条/834incoming的B/A1.009286 [.992612,1.025452]，cal含1。两格原8个RMSE门槛全失败、困难负tail未恢复，不晋升，不续几何消息深度/宽度/seed网格。单seed负结果不证明关系方法家族无用、缺数据是唯一原因或信息极限。

stage95生产d32b0ff3已核：Track_hitSet是24bit station/layer/side覆盖，不是cluster身份，且实际52/1923事件与保存轨迹长度不对齐。现有共同面外推用了单位协方差而非逐轨迹拟合误差；geometry不等于真实关联或显著性。stage96/97用的22节点/5边未交付track→cluster/SP引用/实测协方差。**本轮回答：在现有精确可追溯的原生重建载荷中，能否交付可靠的轨迹—cluster/spacepoint关联与误差摘要，其有效率、歧义和额外活动支持如何？** 先测真正新可部署输入，不先开另一轮能量fit。

## 2. 冻结入口、身份与边界

从stage95已经冻结的2048个不同train/cal incoming、一粒子一视图/24source开始：`ntuples/energy_ml_stage95/cohort.json`、workbook/stage95_energy_ml下的identities/sources表和已知production链；stage96 sources.json提供完整known-source映射，但不因此扩为全池native重读。原队列π/K/charm716/682/650，原PHYS可读1923、125因临时PHYS删除不可读；这是来源/X覆盖队列，不是自然flux概率样本，不重选有利者。

只沿精确PHYS→原始REC/ESD的生产配置/日志/已知目录核对应，先读旧source_semantics和生产Git对象，优先匹配现成Calypso构建。不能猜merge序号/输入entry比例、用run/event重复号跨源合并、按hitSet位交或zip等长强配。核source/run/eventID/native incoming和实际Track筛选/保存index对应；匹配truth若仅MC可用，只在独立诊断中核身份，不进入可部署关联规则。没有协方差/ID就如实标缺，不补单位矩阵。

仅查询冻结source的已知production目录/metadata/log，不递归扫EOS、不恢复整套历史生产。stage70/82临时PHYS已删的身份和缺源状态保留，native不可定位时也保留分母及具体原因；不重放/重建补齐，不恢复旧K生产时限，不删除原所有1016新增K摘要/训练支持。无新样本是前提事实，不阻止现有可测载荷；不能拿纯metadata清单代替已可做的测量。

原stage87角色/权重、46575train/11612cal/13189test/17657隔离、stage94cal协议与既有模型只读。本轮仅固定队列train/cal；不打开test native载荷/风险或借test挑输入。主体pz0>50GeV，一次方动量只pz0，允许px/py/q/p/弯折；raw11/status、合法signed负数/typed NaN/Calo缺项保持，不加p0/p1/pz1及动量比。geometry中的−999/±999999按实际源码/状态核定，正域−1非物理值转missing，但charge=−1/module_eta=−1/合法负raw保留。

## 3. 原生QA与唯一最小关联摘要

看新物理分布前，冻结≤40不同train/cal incoming（从原2048队列按来源/X/状态固定，不按truth/能量误差/关联成功选择）。核native schema/单位、collection键、TSOS/measurement实际链接、cluster Identifier、spacepoint组成cluster引用、逐轨迹实际covariance及可传播条件。源文件/原track筛选和index要逐项闭合；无法闭合的轨迹/事件显式不可用，不能静默重排或截断。

可靠ID引用可用时，冻结一种最小紧凑摘要：每轨迹关联cluster/SP计数、真实ID可核时的共享cluster比例、事件未归属cluster/SP活动及其完整有效分母；按station/面报告共有/缺失collection。保留所有候选和缺失mask、原index/leading映射，不能把重复重建视图当新incoming。真实共享ID与物理重复轨迹仍非同义，不据共享比例自动删候选。

协方差可核时，记录来源/参数化/单位、有限性/对称性/正定性与传播几何面，并给紧凑误差尺度；传播只有真正适用条件才做，不以单位covariance或伪pull当实测误差，不无限扩展传播模型。不可用则列具体缺失collection/参数和可交付替代。Track集合、cluster/SP集合或过滤定义不共有时分开报告，不能混合同名数组。

不构造truth输入、硬分配Calo电荷、noise标签或新的候选选择。未归属活动可能含真实次级/背景/漏重建；“未关联”“无SDO”“leading未确认”不能等于纯noise/无物理μ。已有stage85条件活动结果不替代本轮ID关联，也不重做噪声扫描。

## 4. 有界测量、并行资源与验收

≤40实际读取QA先测CPU/wall/RSS、单事件/固定源成本、实际读字节与单文件复用，记录native读取器必要的前缀扫描成本；用已有匹配构建，只有新导出源码确需变化才编译。QA通过后冻结全2048完整身份队列和资源，按实际可用native来源提取，任何缺源/失败保留原分母，不替换/删困难者。

批量必须HTCondor，独立source足够时8CPU且每process内线程1，最多2并发；建议累计CPU≤14400秒、实际读取输入≤10GB、紧凑最终≤20MB，QA后准入，不自动扩预算。没有GPU优势的原生稀疏I/O不占GPU。按源只打开一次/复用basket或native流，避免多进程重复全文件扫描。不能保存REC/RDO/xAOD副本或逐hit点云；只保留必要数值/ID关联摘要及可复核分母/配置，批量JSON/传输包去重。

交真实native可定位/联结成功/collection有效率，按原来源/component/观测pz/状态/单多候选分层；给关联cluster/SP计数、共享比例、未归属活动和可交付协方差尺度分布及分母。以固定source/X支持的500incoming条件区间说明队列性质，来源/系统/研究选择不覆盖；没有有效分母不制造精度。既有truth只能另表描述，不据真E/y/模型误差挑样本/门槛。

成功是实际可部署输入合同及有数据分母的紧凑测量，或做完所有可行测量后给精确缺失源/collection/身份映射和最小后续输入，不要求强行得到能量收益；0能量fit本轮不认证关联对Eν的增量。无法读取某native格式不能无限恢复环境或重建补齐，保留可做部分并说明未测量项。若输入可用，后续匹配输入消融另冻协议；若不可用，列明确可辨识物理目标和产品缺口，不自动续无信息的GNN/seed网格。

## 5. 交付

先写中文stage98 workbook：阶段目标、精确样本/生产链/身份/选择/单位、源码和运行配置、实际命令、关联/协方差/可用率分母及表图、物理与程序解释边界、CPU/wall/I/O/实际核占用/保留字节、失败/未测量、下一具体任务/输入/验收。与相关代码/配置/紧凑证据一起本地Conventional Commit，不push、不自动执行stage99。路线和信息计划历史只追加，下方stage54原后缀逐字、五路径工作树保持；真实response/interaction/FSI/材料/Calo/接受度/背景和最终未开发确认仍需证据。

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
