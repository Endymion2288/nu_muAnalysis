# 下一轮执行 Prompt：stage83 剩余兼容 π 完整支持交付，保留已用 K

先读AGENTS.md、[stage82报告](../workbook/2026-11-03_stage82_k-support-learning-curve.md)、路线§63/信息预算§43、[实际输入合同](../workbook/stage82_energy_ml/followup_input_request.json)。本轮只做20个已知兼容π PHYS的实际支持交付，0能量fit/新F7推理/重建/GENIE/G4/谱toy，不自动执行stage84。

## 1. 已测结果与当前授权

用户要求解除旧K生产限制已执行：3源完整30000 RDO→1094 selected→1016新唯一K，Condor9663277一次exit0、wall4038–4537秒均超过旧3600秒，现workday/MaxRuntime28800、workerCPU unlimited。名义d32b0ff3 merge withoutIFT、实际四模块Calo03→01转换通过，K已经加入半892/全1786支持、6正式fit，不是只提交作业。历史不生产/不重试K的禁令和旧支持时限已被用户覆盖，不能恢复为审批阻碍。

主full_cal eval两低E .311861/.263216，对传统95上限2.464666/1.237750未恢复；all/F7 .997438 [.996118,.998709]小幅改善，低pz .999717 [.992558,1.006390]未证增量。原7层RMSE/总正负tail50保护均通过，额外同低pz真≥200总/负tail上限+2.233589/+2.162810pp仍保留。继续F7，不将局部all收益当低能成功、不按半/全/raw/cal挑赢家。

K此次真50–100新0、100–200新14，原π770＋K1016总新1786/6源，但最低能仅新23/原767（约3%）。不能据失败否证缺数据，也不能唯一归flux/接受度/过拟合，完整raw真谱和接受度因果尚未测。先完成已有兼容π支持入口，保留已交付K。

## 2. 冻结来源与实际小 QA

只用stage81 source_plan里22个已知合法train compatible merge π候选，排除已完整交付00100–00109/00250–00259及已完整交付范围，**全取剩余20文件**，精确路径/历史角色见输入合同；不随机挑有利来源、不按E/y/残差或prefix产额换源。已测逻辑PHYS合计611988745bytes，每完整10000输入，实际新N/功效未测量，不能用目录数冒充支持。

先≤40个固定身份核实际schema、11raw/status、VetoNu reduced、Calo reference01-LG与单位、原选择/62列、run/event/leading/incoming联结、成本和实际包启动；沿stage81兼容提取，不安装/编译、不新增重建。已有PHYS为01-LG，不再03→01缩放；若实际条件不同，先核准确切差异，不能猜测或混入backward-only。

原pz>50 GeV/原quality/geometry/truth fiducial、原62一次方动量仅pz0、px/py/q/p/弯折允许、11signed raw/VetoNu reduced、typed domain/status/dependency NaN、Calo缺模块totalNaN和所有困难尾保持。原41447/8440/14057、91/16/22组、缺失21/3/7＋11保护不动；新读仅合法train来源，不打开test/locked。

## 3. 完整交付与判据

QA通过后最多4Condor、每1CPU3000MB、wall每1800秒上限、CPU累计1800秒、完整≤200000输入/10GB、紧凑最终10MB，按实际QA冻结分片和有效ClassAds；CERN flavor改写须记实际值并验证预算内。stage81两πremote25CPU/48wall秒仅预算依据，不冒充20源新实测。完整文件不截有利prefix。

incoming精确nativeMeV(pdg,px,py,pz) key对stage55全部95748曝光/66843unique、stage70实际新28、stage81新742、stage82新1016和来源内部/之间稳定排重；保留复用与重复交叠，不简单相减。所有selected与新唯一key按来源/真50–100和100–200/confirmed低transfer、reco pz50–100及同pz真≥200/high-y/未确认、高端/缺失报告，完整cutflow、概率、raw有效性/占位域、资源和I/O并报。source概率不当物理flux权重。

验收20来源完整可追溯、原选择/62/raw/reference表示闭合、角色和全曝光去重干净、真实新增支持层/成本测得、紧凑合并缓存可回读；不可交付的来源写具体路径/条件原因，不能写selected0或换源。新增量多少都不自动证明足量；完整上游parent/subfile/seed未知，仅development enrichment，不称独立确认。

## 4. 交付与下一步

先中文stage83 workbook实测报告，再代码/协议/表图本地Conventional Commit，不push、不外发、不动stage54已有五项工作。仅保留合并支持/必要QA和紧凑表图，删重复ROOT/包/分片；逻辑请求字节与物理EOS网络I/O分开，未测明确未测。

本轮0fit，不按少量增补继续轮换模型或更多规模/来源/seed/权重曲线。交付后按实际低E及另一侧支持、来源与代价，为后续一次训练或具体缺失输入写新合同；尚未测量的N、收益与所需功效不造数。共同raw/stage54、完整Calo/脉冲条件、interaction/FSI/材料/接受度/背景和真正随机未开发确认继续；既有K支持一直保留，不让旧时限/禁令恢复。

以下stage54原后缀逐字保留，仅进入该支线时适用。

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
