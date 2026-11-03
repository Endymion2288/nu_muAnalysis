# 下一轮执行Prompt：stage74 同pz条件能量假设判别信息

先读AGENTS.md、[stage73报告](../workbook/2026-11-03_stage73_reconstruction-energy-reweight.md)、[stage72§6.1](../workbook/2026-11-03_stage72_reconstruction-reweight-reassessment.md)、路线§54/信息预算§34、stage68 v2协议。继续F7。stage73已完成固定U/S/F12fit，S在OOF/eval两个低E均改善但原恢复/困难标准失败；F100–200胜传统但全区/困难受损，停止alpha扫描。下一单项只问：**同reco pz内竞争不同能量解释时，全62输入相对pz0-only的判别信息，能否在来源留出及歧义两侧稳定转移？**

stage62旧full/pz-only在低pz proper-score已有增量；它不是新条件负配对方法的收益或点预测保证。不要把另一个y辅助头、旧gate、全局joint/product重新命名。本次先交信息实验，不自动新能量点映射/谱拟合或部署。

## 1. 输入与保护

仅stage55 dataset、stage56 readout和必要既存stage62/73聚合/固定参考，X通过audited_features.load/build，同62与角色train/cal/eval41447/8440/14057、91/16/22保守来源。stage68 v2来源折和train端exact incoming purge不改，held全部保留，41447恰一次OOF。q、权重、初始化及任何尺度只读每次**实际train**，不得用held频率。

一次方模长/纵向动量仅pz0，允许px/py、q/p、弯折；11signed raw/VetoNu reduced与typed/status/dependency NaN、缺一Calo使totalNaN保持。原pz>50及其他cuts、42缺失21/3/7＋11保护、巨大动量/未确认/high-y/负修正/全部尾不变；真E标签覆盖未确认，不贴错轨或无效y标签。

无新ROOT/RDO/重建/生产/locked确认/π28追加/K重试/扩run/谱toy/SHA；stage70参考化x不重缩放。已有cal/eval仍开发，真正独立确认及共同响应另需输入，不用metadata循环替代实验。

## 2. 先冻结条件负配对与概率语义

t=log(Eν/GeV)，Bpz固定reco边界[50,75,100,150,250,500,1000,+∞)GeV。能量固定stage73七箱[50,100,200,400,800,1600,3200,6400]GeV。对每个实际train的每个Bpz，q_b为其七能量箱unit频率；箱内在logE均匀，因此q(t|Bpz)=q_b/ΔlogE。没有伪计数或事后merge/clip；空Bpz/零q箱/箱外支持明确单列，不删事件或把未见叫物理不可能，遇实际箱外先冻结支持处理再fit，不盲裁边界。

每个真实训练X配一个真实t正例、一个由该实际train q(t|Bpz(X))独立抽出的负假设；两类1:1等权，U式unit事件，不再能量reweight。每job固定一次负配对，不扫负例数量/种子/带宽；同一配对同时给两对照。held/cal/eval的负例用该训练q独立固定RNG抽，不能用其真实谱估q，不能按坏例筛选。来源bootstrap按真实X的来源抽样，携带它的正/负假设对；合成负假设不是新增独立物理事件。

平衡BCE的理想logit=log p(t|X)−log q(t|Bpz)。候选t是待查询假设，部署从候选输入；禁止读取未知真t选择模型/校准。要解释后验必须乘回q并处理归一，不能把raw sigmoid/logit直接称p(E|X)或条件互信息精确值。零q支持上的后验恢复未定义，分类器可输出但只能作外推诊断，所有角色主样本保留并报告支持缺口；不能静默从成功分母去掉。

本阶段不作高密度能量grid/新点能量/均值-MLE选择/额外概率校准；真实能量后验归一和点风险留给下一份独立合同。proper-score在已定义的正/负实验分布下评价，不冒充自然物理类先验。

## 3. 两个固定判别器，最多8正式fit

- M：仅pz0与候选t，共2输入；
- X：原62reco列与候选t，共63输入，NaN原样。

同容量BDT depth5/400轮、eta.04/subsample.8/colsample1/min_child_weight20/lambda10/hist/nthread1，objective=binary:logistic，base_score=.5、boost_from_average=0，模型seed2026110374。两者同一正/负配对及train顺序；q/RNG每job固定seed2026110374＋job序号0/1/2/3，评价负例另固定+100，不选RNG赢家。仅三来源折各M/X＋全train M/X，共8fit；不earlystop/checkpoint、无其他seed/aux/结构/权重/负分布变体。树直接接收原值和NaN，不添加truth-derived reco列。原62和候选假设的部署字段分别明确审计。

## 4. 必须回答的评价与验收

主指标为每真实X的平均正/负BCE：−.5[log σ(s_pos)+log(1−σ(s_neg))]，用稳定softplus；X相对M的gain=loss_M−loss_X，正为好。并报Brier、正/负分项与固定10个等宽概率箱的可靠性，原始N/保守来源/唯一incoming/q支持、sampled negatives数量分开。不能只印总体accuracy/AUC，分类概率好不自动恢复逐E箱能量风险。

主层reco pz50–100；同时报告pz50–75/75–100、100–250、原trueE七箱、同低pz true低E50–100/100–200/≥200、高y、未确认、缺失，以及stage73固定Timing活动格（原train阈值只作诊断）；所有层全保留，低支持/空层写未测。训练内、来源OOF raw、cal/eval开发分开；原F7/传统的stage73点风险只读参考，不新推理。

500次component分层保守来源配对bootstrap，seed2026111374（cal+1/OOF+2），固定模型/q/负配对，不重训/重抽q/重新校准；记录有效/无效，不含完整谱系/响应/重训/研究选择，不是独立确认。主“可迁移条件判别增量”仅在OOF和eval主低pz层gain95%下限均>0、关键两侧支持已覆盖，且未发现任一关键低E/同pz高E/high-y/未确认层gain区间整体<0时成立；单层区间跨零明确未定，不叫全层成功。零q缺口不允许宣称该层完整后验恢复。即使通过也不推广能量模型。

## 5. QA、资源与交付

先冻结所有输入/来源/公式/负配对/主候选/验收；先做小合成条件独立（最优比值1）、已知条件密度比和q乘回/归一、零支持/边界、BCE解析梯度/类先验、NaN和假设查询不读truth、实际tar包四split `--check-only`（worker已预建目录）及资源pilot。stage73目录创建冲突须覆盖，不再只验证DMatrix。本轮不新增科学候选作pilot。

拟议≤4Condor，每任务M/X各1fit、1CPU/3000MB，累计CPU≤3600s、wall/job≤1800s、最终≤20MB；pilot后按实测冻结，核最终ClassAd与worker硬上限。成功/部分fit不重跑，不自动突破提交/运行预算；异常先保存实际状态并交具体修复合同。用CVMFS现成构建、scratch和一次紧凑输入，记录逻辑bytes与实际测到的资源，物理EOS I/O未测则如实写，不保留点云/ROOT/全能量grid。

写中文stage74报告：实际q/支持、两对照全部train/OOF/开发proper-score/校准/双侧来源证据、概率语义/程序物理解释、命令/CPU/wall/RSS/产物、独立回读/来源保护。更新路线/信息预算/Prompt，先报告再本地Conventional Commit、不push。通过则只冻结一个后续能量决策/共同响应独立确认合同；无转移/支持不足则停条件方向、交真正新增歧义两侧支持，禁止自动扫超参或把阴性当信息极限。共同raw/stage54、Calo实际状态/标度、interaction/FSI/材料、接受度/背景、新π/K parent/seed与随机未开发确认继续交付。本轮未执行stage74。

下面stage54原协议逐字保留，只有进入该支线时适用。

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
