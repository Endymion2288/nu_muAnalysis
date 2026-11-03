# 下一轮执行Prompt：stage82 固定0＋两档π增补支持学习曲线

先读AGENTS.md、[stage81报告](../workbook/2026-11-03_stage81_phys-support-delivery.md)、路线§62/信息预算§42、[下一合同](../workbook/stage81_energy_ml/followup_input_request.json)、stage70参考Calo闭合和stage71三seed增补实现。继续F7，原固定脉冲族/分类器/组合预算已结束。本轮只执行一次0＋半/全真实π支持曲线，0新ROOT/PHYS/RDO/HITS/重建/生成/谱toy，不自动执行stage83。

## 1. 问题、实际支持和边界

stage81完整两π文件20,000→797 selected→742新唯一incoming，true50–100/100–200为19/89、同低pz true≥200为12，两侧实际交付；但只有两个π来源、高端0。K虽然存在，actual backward-only collection非原merge，完整selected/new未测，不混入/补0或重试生产。所有新行仅开发增补，完整谱系/独立确认/共同响应仍未认证。

将stage70实际28与stage81实际742合并为770唯一πkey/3来源，用原41447 nominal train作基底，检验一次固定增补量的趋势与原风险。不是充分N或纯样本量因果实验，效应混合π flux/支持/重训；770只约原train1.86%，缺增益不能否证缺数据假说。收益与功效未测，禁止按结果挑规模、来源、seed或另换方法。

## 2. 输入、冻结规模与零fit预检

- 仅`ntuples/energy_ml_stage70/support.npz`的new_training_support28、`ntuples/energy_ml_stage81/support.npz`的new_training_support742，均用已经reference01-LG的x，**不再运行03→01缩放**。对stage55全部95748已曝光incoming和pooled源内/源间精确key重核，不能仅检查原eligible；只读旧缓存和F7旧预测。
- 原62/pz0-only一次方动量/px-py-q/p-弯折、11signed raw/VetoNu reduced/typed-domain-status-dependency NaN、Calo缺一totalNaN不改，旧41447/8440/14057与91/16/22组、原缺失21/3/7＋11保护及全部困难/尾保持。
- 事前seed2026110382，按canonical group顺序每source无放回均匀取floor(N/2)：π00100–00109取194/388，π00250–00259取177/354，π00440–00449取14/28，half385；full770。文件内所有新增候选的身份/源概率保留；不按E、y、p、残差或模型排序。两档train41832/42217，cal/eval不增补；half subset full，不调样本数。
- 原F7实际版本/参数/初始化语义、label/features/incoming/源角色与NaN、缺失与signed值、支持层/概率、实际软件包两档无fit启动先通过；0pilot fit，完整成本仍未测，先QA/资源后冻结ClassAd/worker硬上限。沿LCG109/XGBoost2.1.3/现有构建，不安装/编译。

## 3. 唯一6fit与固定评价

size0复用stage56 F7已存cal/eval预测和原offset，0新基线fit/推理。half/full各原3seed **2026110255/2026110256/2026110257**、原depth5/400轮/原参数/unit direct logE，共最多6正式fit；初始化沿原F7实际语义，不自动换成另一初始化政策、早停、重权或挑轮。每档3seed平均raw log预测，再原8440 cal一个unit global log-offset，raw/cal均报。**主full_cal预定；half为曲线诊断，不从半/全/raw/cal中选赢家。** 不把每seed当独立生产重复。

报告两真低E（含confirmed低transfer）、reco pz50–100、同pz真≥200/high-y/未确认、全体/≥200/全部能箱/高端/缺失和总正负tail50/100、bias/R68、来源方向、支持实际增幅与训练内风险。500component分层保守来源配对固定预测bootstrap，eval seed2026111382；每档对F7、主full对传统，full/half曲线也并报，不能只报总体或有利中位数。区间不含重训/增补抽样/offset估计/完整谱系/响应/研究选择，cal/eval仍开发，非联合覆盖或独立确认。逐模型回读、原角色/缺失、校准与bootstrap独立核验。

原推广门槛不降：两低E相对传统RMSE来源95%上限≤1.05、all/F7≤1.01、≥200/低pz/high-y/未确认≤1.03、原关键层总/正/负tail50增量95%上限≤2pp；缺少证据不能改门槛。raw/half改善不能代替主full_cal同时通过。成功仅冻结研究候选与独立确认合同，失败继续F7并结束这次有限增补；不扫规模/源/权重/seed/架构或用同几例轮换方法。

## 4. 预算和交付

拟议≤2Condor任务（每档3fit）、每1CPU/3000MB、累计CPU≤1800s、每job wall≤1800s、紧凑最终≤20MB；是上限，实际拟合成本/收益未测，先实际无fit QA后冻结。批量Condor，一次尝试不自动重试/延长，记录脚本及remote CPU/wall/RSS、只读缓存输入与存储，删除重复大输入/传输包，保留6模型/预测和紧凑表图；无新ROOT I/O，EOS物理网络I/O未测要明示。

先中文stage82 workbook实测报告，再与代码/协议/紧凑成果本地Conventional Commit，不push、不外发，不动stage54五项已有工作。K0090/0160两个固定来源缺名义d32 merge/without-IFT PHYS与actual条件/联结/62 QA或完整逐例等价证据；不自动RDO生产/失败K重试。真实π/K parent/subfile/seed和随机未开发确认、共同raw/stage54、完整Calo/脉冲/interaction/FSI/材料/接受度/背景请求继续，不以770例替代。

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
