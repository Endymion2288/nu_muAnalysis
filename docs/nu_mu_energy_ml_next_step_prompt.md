# 下一轮执行Prompt：stage81 兼容既存PHYS的真实新增开发支持交付

先读AGENTS.md、[stage80报告](../workbook/2026-11-03_stage80_pulse-shape-ablation.md)、路线§61/信息预算§41、[新增支持请求](../workbook/stage80_energy_ml/followup_input_request.json)，然后执行[独立支持协议](nu_mu_energy_ml_support_delivery_prompt.md)原stage77合同。独立协议保持原文，其中阶段号stage77在本次执行记录为stage81；原seed2026110377、物理/角色/选择与资源合同不变，不复制重写协议或缩减保护。

## 当前证据与唯一任务

stage80原62 vs 加22 raw_peak/width的8fit已完成。总体和100–200有小幅增量，但主低pz OOF/eval风险比区间跨1，最低能仍差传统，两低E恢复和部分双向尾门槛失败。继续F7，结束固定脉冲族；不续扫通道/mask/时间/seed/权重/架构，也不重开条件classifier/积分/专家组合。

本轮唯一问题：可访问的兼容既存π/K PHYS能交付多少相对旧开发缓存**实际新增**的低E及同reco pz真高E/high-y/未确认支持，条件与实际代价是什么？0模型训练。新增N、足量功效、学习曲线均未测；四来源只是入口，不预判足量，不以旧28例再评/目录清单当扩样。

## 执行要点与验收

- 输入限已知manifest明确PHYS、历史canonical train合法池；先读stage55/65/70角色与全部曝光，排除已完整交付的来源。事前seed2026110377在π/K各均匀≤2来源、总≤4完整文件，记录池/源概率及文件内概率1；不按能量、残差或新key产额换源，不扫全EOS/test/cal/eval/locked。
- 先≤40事前身份QA实际schema/单位/62/raw/status/VetoNu reduced/联结及Calo reference01-LG实际payload与逐例闭合，复用现成build/LCG，仅源码变才重建。原pz>50、一次方模长/纵向动量仅pz0，px/py/q/p/弯折允许，typed/domain/status/dependency NaN与合法负raw、缺一Calo总和NaN保持，不二次缩放或以fit charge补raw。
- 原生MeV incoming精确key，对stage55**全部已曝光开发缓存**＋stage70实际28新增排复用，再源内/源间稳定去重；保留原事件/来源包含概率。没有完整parent/subfile/entry/seed时明确未知，新行仅development enrichment，不能称随机独立确认；未知谱系也不自动否定所有合法有界开发提取。
- 小样本测CPU/wall/RSS/请求字节与联结/资源，再冻结≤4Condor/每≤2CPU3000MB、CPU累计7200s/wall每3600s、总≤4完整源/40000输入/10GB、最终≤10MB。上限不是已证明可交付，不用有利prefix外推或自动扩大预算/重试失败K。批量走Condor，不长期留ROOT/PHYS/大输入和传输副本。
- 完整cutflow、来源/组件、旧key/内部/跨源复用、新增唯一incoming、原62缺失/raw/status/Calo状态，true50–100/100–200、同pz50–100两低E与true≥200、high-y/未确认、3200–6400/≥6400及缺失的新增N/来源/唯一key和原41447实际增幅，所有困难/尾保留。输入/角色/定义/参考响应与预算QA通过才释放新增开发缓存；未交付或未测明确标记，不能填物理0。

实际兼容PHYS/条件入口不可交付则交最小缺失路径/字段/条件，不以空metadata清单制造新阶段commit，不自动读取新RDO/HITS/重建/生成或K重试。少量支持只交局限；是否进行一次固定增补比较，在真实数据交付后给唯一下一合同，本轮不训练或自动开始stage82。

先中文stage81 workbook，记录实际输入、选择概率、数值/单位、完整QA/命令/成本、物理/程序限制及具体下一任务，再与代码和紧凑成果本地Conventional Commit。不push、不外发、不动stage54已有工具/缓存。共同raw/stage54、完整Calo/脉冲条件、interaction/FSI/材料、接受度/背景及真正随机未开发确认继续。

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
