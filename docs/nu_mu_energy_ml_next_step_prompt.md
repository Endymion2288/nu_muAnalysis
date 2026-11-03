# 下一轮执行Prompt：stage77 兼容既存PHYS的真实新增开发支持交付

先读AGENTS.md、[stage76报告](../workbook/2026-11-03_stage76_exact-conditional-energy-decision.md)、路线§57/信息预算§37、[新增支持合同](../workbook/stage76_energy_ml/followup_input_request.json)、stage70完整π/失败K与Calo闭合证据、stage55/65/70历史manifest和角色保护。继续F7。stage76精确积分与独立核验通过，但主X_cal低E/全体/困难风险失败；这次固定决策预算关闭，不追加temperature/q/估计器/架构或能量fit。

## 1. 唯一问题、实际入口与边界

本阶段只问：在原pz>50 GeV、原62/raw与共同Calo表示下，可访问的既存π/K PHYS能交付多少相对开发缓存新增的、歧义两侧的训练支持，实际代价是多少？0能量训练/概率映射/谱toy。新增N/足量功效/学习曲线未测，不按目录数或旧28例复评当扩样成功。

优先使用已知manifest明确指向的、历史canonical train角色下现成PHYS及其已知production日志/实际条件入口，不默认重建RDO。stage70旧π完整784例曾通过原选择/62列提取与参考Calo闭合，证明这条直接提取路径值得先核；**不等于新K PHYS或所有源schema已证实可用**。先仅检查这些具体候选路径，禁止递归扫全EOS或再列22run目录当物理成果。

兼容PHYS/raw/status/Calo条件无法交付时，明确列出最小缺失实际路径/字段/条件；不假造0产额、静默换源、制造空metadata阶段或自动恢复失败K RDO作业。只有实际输入到位才进入正式提取；新RDO重建/生成另需实际成本合同，不在本轮默认动作中。

## 2. 身份、来源与事前选样

沿用跨flux/几何的全部历史canonical角色/曝光/保护规则，不把文件名train当唯一角色；不读test/cal/eval/locked候选事件，不把已暴露challenge当独立确认。排除已完整提取交付的来源（例如stage70完整π）；只有partial缓存的合法train源可读完整文件，但必须对所有旧incoming去重。

在有明确可访问PHYS的合法π/K池中，先冻结候选池与输入可用性/角色判据，seed2026110377各均匀选至多2个来源，总≤4个完整文件，记录每源选择概率和文件内条件概率1。不得按低E数量、坏残差、模型输出或新key产额挑/换来源；不足源按实际缺口报告，不把缺K当0。

先总≤40个事前身份schema/单位/联结/状态/条件/成本QA（四源时各≤10，少源也不突破总数），不扫描能量/噪声/拟合参数。继承原incoming=(pdg,px,py,pz)原生MeV精确key语义，不能只用run/eventID。新行对stage55全部已开发缓存（含所有曝光分区/几何/flux，不只eligible）和stage70实际28新增key排复用；源内/源间稳定去重后只保留一次，原事件和来源包含概率保留，unit MC不冒充flux权重。

已知角色＋精确key保护的新行只称development enrichment。完整GENIE parent/subfile/entry/seed未知时标未知，不能声称真正独立；真新随机未开发确认仍要求实际上游谱系/曝光/角色。未知谱系不应再次成为所有有界开发提取的无限前置，但不放宽已知保护/确认条件。

## 3. 原选择、62变量和共同响应QA

使用与stage55/56一致的名义geometry/build/分析定义，现有build源码未变不重编译。原truth νpz/reco highest-pz leading>50 GeV、质量/几何/fitted-charge cuts和truth fiducial保持，不设真E上限或删尾。一次方纵向/模长动量仅pz0，允许px/py、q/p、弯折；11signed raw、VetoNu reduced、typed/domain/status/dependency NaN及合法负值、缺一Calo使totalNaN严格保持。不得用fit charge代替缺raw、nansum或填补。

从实际PHYS核全部所需分支、run/event/inputentry/leading与incoming联结、原62派生代数和raw/status。核四Calo实际E/charge单位/payload与F7 reference01-LG表示；只有已核实payload和逐例闭合支持的表述转换可沿用，不能按truth/坏残差拟合尺度，也不得二次缩放stage70参考化x。历史完整snapshot未证就保留限制，不以同名分支/当前DB默认当共同响应认证。

优先复用 `extract_alternative_support.py` 的原选择/build链，移除仅适用于stage70两固定源的索引耦合时保留原物理合同；先真实小样本验证，不把新输入硬套旧run/条件。任何不兼容/缺失字段都交具体缺口，不将失败源删除后夸称完整π/K交付。

## 4. 实测成本后冻结有界完整提取

拟议新上限：总≤4完整源/40000输入事件/10GB，≤4Condor、每任务≤2CPU/3000MB，累计CPU≤7200s、wall/job≤3600s、紧凑最终≤10MB。上限不是已证明能完成；先代表性QA实测提取wall/CPU/RSS/ROOT或Uproot请求字节、basket复用/吞吐，再分配总CPU与worker硬上限，最终ClassAd核实后才提交。禁止用prefix线性速率冒充尾成本保证或自动延长预算。

批量必须Condor，固定源一次尝试，无部分/成功重跑。完整文件或组合无法在预算内交付时停在实际资源/输入缺口，不静默取有利前缀、换源或扩大run。无RDO/xAOD/PHYS复制长期留存，分块读所需分支，保留一个合并去重NPZ与必要小表/图，删除每源重复传输包/ROOT中间文件；EOS物理I/O未测明确写未测。

## 5. 必交付测量、验收与下一分流

逐来源/组件报告raw N、完整cutflow、selected N、旧key/内部复用/跨源复用与新增唯一incoming，原62缺失/raw/status/Calo状态，所有困难/巨大动量/负修正/尾保留。分层至少：true50–100/100–200核心、同reco pz50–100的两低E和true≥200、high-y/未确认、3.2–6.4TeV/≥6400、缺失；报新增N/来源/唯一key和原train41447支持的实际增幅，不只总N。

输入/身份/物理定义/参考响应/选择与预算QA必须通过才释放新增开发支持；未测/未交付源用显式标志，不能填成物理0。源少/新N很小或未覆盖歧义两侧时如实交付局限，0模型训练，不自动用同几例轮换方法；是否值得一次固定增补比较只在实际数据后给下一合同，不造最低充分N或独立性。真正新生成/共同响应请求继续并行，不以当前四源替代独立确认、data/raw/stage54、interaction/FSI/材料和接受度/背景。

中文stage77报告记录实测数值/单位、输入/角色/选择概率/条件/命令、程序与物理解释、资源/I/O和实际产物及最小下一任务；先报告后与代码/配置/紧凑表图本地Conventional Commit，不push，不外发消息，不自动执行下一阶段。实际输入不可交付时先报告具体缺失输入，禁止为重复metadata清单制造新空阶段commit。

下面stage54协议逐字保留，只有进入该支线时适用。

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
