# 下一轮执行Prompt：stage80 固定脉冲形状族的同容量消融

先读AGENTS.md、[stage79报告](../workbook/2026-11-03_stage79_pulse-information-audit.md)、路线§60/信息预算§40、[stage79测量](../workbook/stage79_energy_ml/measurement_summary.json)、[生成证据](../workbook/stage79_energy_ml/source_evidence.json)和[下一合同](../workbook/stage79_energy_ml/followup_input_request.json)。最新实测stage79为0能量训练，继续F7；不得重开stage74概率/积分或stage78专家/分区续调。

## 1. 唯一问题与未测项

原62＋一族11×(raw_peak,width)是否在匹配容量/训练政策下，改善低pz与低E风险并保持原困难/全体/尾保护？唯一对照U=原62、P=原62＋22；不扫通道、阈值、seed、权重、深度或架构。shape族包含状态依赖缺失模式，收益不能全归纯物理形状。

stage79实测12已知train来源/2048身份，原62/raw/status/RMS精确闭合；实际生产均hit-time convolution，观测到跨源摘要差。但214通道对仅240不同事件、低pz50–100只有1对、VetoNu零对；只固定本通道积分有限容差，噪声/fit和其他61输入未排除。新增能量信息、风险增量、完整提取/训练成本均未测量，不把变化图当收益。

localtime/trigger/bcid及baseline RMS不作新增能量输入。MC trigger/bcid全0有写出/clock条件原因，CLOCK_INVALID未置也不能认证clock。RMS仅用于有效性，不是积分电荷误差；不以高能μ飞行时间测能，不按truth E/y调响应。

## 2. 输入、清理与先行QA

仅stage55已知nominal manifest中**原41447/8440/14057 train/cal/eval身份**，原source/group/incoming角色及缺失/困难/尾全部保持；不得取新身份、test/challenge/locked或alternative支持。不读取新RDO/HITS、重建/生成、递归扫EOS或做SHA。真实π/K按独立支持协议另交付，本轮不自动执行。

复用stage79固定≤40 QA身份，先小样本验证新增scalar提取、实际writer/digitization语义和完整包无fit启动/资源。12源已知生成日志可直接复用；新涉及的既有nominal来源需有界核对应生产入口/差异，不能拿当前默认或另一版本代替。本轮须把所需语义/成本QA放在正式提交前，不复制stage79日志核准迟于提交的顺序偏差。沿已知构建/LCG，不安装、不重建C++。

只补22列及必需run/eventID/status/raw_charge/baseline_rms联结，原62直接使用冻结缓存；按源/basket批读后只保留合法固定身份，不将默认0当测量，不保存全波形/ROOT/PHYS副本。逐源标量联结和旧raw/status/RMS精确闭合；保持一次方模长/纵向动量仅pz0，px/py、q/p、弯折允许。11signed raw、VetoNu reduced、typed/dependency NaN、缺一Calo总和NaN不改，不二次缩放Calo。

新增两列按stage79 `strong_shape_validity`的同一保守联合mask：status & (444|1)==0、finite width>0、localtime>0、baseline_rms>0、raw_peak≥5×RMS。localtime只为既定有效性依赖，不进模型；5σ是审计约定，不称已认证生产阈值。不合格新列NaN，所有事件仍参加训练/评价；旧raw不应用fit-invalid mask，不以拟合charge补raw。−999/正域−1/默认0依赖需验证；合法signed负值保持。不能依新形状有效率/真E/坏残差换样或截prefix。

## 3. 一次冻结的8fit与评价

QA和实际资源通过后才冻结最终ClassAd/worker上限。沿stage68 v2三outer来源折、train端incoming purge，U/P每折各1fit＋final各1fit，共最多8fit；41447恰一次来源OOF。两臂同原depth5/400轮/unit direct logE，seed2026110380，同实际fold train mean(logE)初始化、boost_from_average=0，余参数原low_energy配置；不扫seed/超参，不早停挑轮/挑列，不加入其他目标或重权。禁止F7新推理，复用原预测作参考。

OOF只报raw；final各原cal一个unit global log-offset，raw/cal并报，P_cal预定主候选，U为匹配控制。主信息增量对照为reco pz50–100的P/U配对log-RMSE，OOF与eval的500次component分层来源固定预测区间（seed2026111380，OOF+1/cal+2）；两真低E、同低pz真高E、高y、未确认、全体、≥200、稀疏高端、缺失/饱和状态及正负尾并报，不能只看新列有效子样本或总体分数。来源区间不含重训/offset/谱系/响应/研究选择，cal/eval仍已开发，不称新确认。

原推广门槛不降：两低E相对传统RMSE来源95%上限≤1.05，all相对F7≤1.01，≥200/低pz/high-y/未确认≤1.03，以及原关键层总/正/负tail50增量95%上限≤2pp。匹配控制收益和原恢复/保护分别交付；不得以某个中位数、macro或只有有效者收益替代。逐模型独立回读、角色/来源/incoming隔离、原62/新增NaN、校准和bootstrap核验。

## 4. 预算、停止与交付

拟议最多4个scalar提取＋4个训练Condor作业，每1CPU/3000MB，累计CPU≤7200s、每job wall≤1800s、输入≤10GB、最终≤20MB；是上限，实际完整成本未测，先QA后冻结，批量走Condor。记录请求字节/真实wall/CPU/RSS和basket复用，软件/缓存/分片归并去重，不保留重复传输包；不得将历史或理想前缀速率当实际成本。一次冻结，不自动重试失败源或扩大预算。

有增量且过原门槛仅冻结研究候选与独立确认合同；无跨源增量或风险失败，保留F7、结束这一固定族，解释物理/统计/程序限制，不自动改通道、mask、时间、权重/架构。条件/资源不可用则记录具体实际缺口和已测结果，不将未读者置0，不以目录清单结束。不要因少量异常就删支线，也不把未识别原因写成信息极限。

先中文stage80 workbook，记录实测/输入/命令/资源/单位、原62与新增族有效性、全部风险/来源区间/失败及唯一下一合同，再和相关代码/紧凑结果本地Conventional Commit，不push、不外发、不连开stage81。真实π/K支持按[独立协议](nu_mu_energy_ml_support_delivery_prompt.md)，共同raw/stage54、Calo/完整脉冲条件、interaction/FSI/材料/接受度/背景及真正未开发随机确认继续。

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
