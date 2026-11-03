# 下一轮执行Prompt：stage75 固定条件分数密度的唯一能量决策

先读AGENTS.md、[stage74报告](../workbook/2026-11-03_stage74_conditional-energy-hypotheses.md)、路线§55/信息预算§35、stage74协议/decisions及stage73点风险标准。继续F7。stage74信息主门槛和七重要组OOF/eval均正，完整支持合同因12个OOF零q例失败，X分类概率ECE也未闭合。保留两项事实，不把判别收益叫点风险恢复。

本任务明确修订旧stage74 Prompt“支持不足即停止条件方向”的过强分流：AGENTS要求“不能因少数离群事件就停止某条分析分支”，不能以12罕见例或校准未知代替实际点风险；也不能反写完整覆盖失败、加伪计数重训或挑分布。本阶段仅用已训练8模型，0新fit，问**固定分数密度的一种决策能否将信息增量变成全样本点风险收益？** 真新支持/共同响应仍并行交付，不作为本有限实验的无限前置。

## 1. 输入与保护

只用stage55/56原开发缓存、audited_features.load/build的同62、stage74八模型/各实际train q和既存stage73/F7/传统/stage68/69/71参考。train/cal/eval41447/8440/14057、91/16/22来源，stage68 v2 fold+train端incoming purge，OOF41447恰一次；不得重新fit分类器或改q/RNG/提议边界。stage74的12零q真实者、所有缺失/巨大动量/high-y/未确认/负修正/困难尾完整保留，不按未知真能量回退F7或M。

一次方模长/纵向动量仅pz0，px/py、q/p、弯折允许；11signed raw/VetoNu reduced、typed/domain/status/dependency NaN和缺一Calo使totalNaN保持。原pz>50及其他cuts、42缺失21/3/7＋11保护不变。query t只作部署候选，绝不读事件真E选择密度/估计器。无新ROOT/RDO/生产/π28/locked确认/K重试/扩run/谱toy/SHA，不重缩放stage70参考化x，不新F7推理。

## 2. 唯一映射与数学边界

对每个模型与它的实际train q（stage74精确7×7与log箱内均匀），定义
`r(t|X) = q(t|Bpz(X)) exp(s(t,X)) / Z(X)`，固定t∈[log50,log6400]。
称**归一分数密度**，不称已校准物理真后验。q=0处r=0，不伪填/merge/加floor或改条件层；真实标签q=0的密度logscore未定义/−∞，不得删它们或裁logscore凑有限均值。点决策仍对每个真实X存在，必须全评价；无实际箱外事件不等于未来支持已完整。

唯一决策 `logEhat=∫ t r(t|X)dt`，Ehat=exp(logEhat)，与平方log损失口径一致。M/X都用相同规则，无MLE/median/quantile/拼接/gate/混合或truth分段校准。不硬施Ehat≥pz。用稳定指数减每行supported节点最大logit，归一时常数抵消，禁止裁odds/沉积负值。

OOF仅raw、每fold各M/X query其完整held，最终M/X完整train/cal/eval；最终各在原8440cal上一个unit mean(logEtrue−logEhat) offset。预定主X_cal，X_raw、M_raw/cal并列，不因某版本更好改赢家。无温度/等距/能量分段校准，无新classifier、q混合/伪计数/seed或先验扫描。

## 3. 数值QA与小资源pilot先于正式点评价

先冻结输入/模型/来源/唯一映射/网格/验收/资源；0训练。主网格257等logE节点，积分分段显式包含原能量箱边界，不跨q跳点做错误平均。声明所用分数插值和求积定义；树阶梯输出不自动等于精确连续密度。

合成piecewise常数/指数、q跳点、单箱/零箱、稳定大logit/归一、已知均值、两模型相同输出/score加常数不变、独立参考积分和X-only必须通过。每job按row排序等距取≤64身份，final取cal/eval各≤32，共≤256个固定真实身份；不是按残差选。以513节点复核，要求最大|ΔlogEhat|≤.005、各有支持来源的中位|Δ|≤.001。数值标准是工程QA，非detector容忍度，不能根据能量RMSE选择网格。未通过先交实际误差/输入/最小积分修复合同，不直接报告成功或扫描更有利的决策。

用少量固定身份实测query吞吐、wall/CPU/RSS与chunk内存，0新训练、不保留全量逐例能量grid。每chunk及时约化为log均值/归一/边界质量等紧凑量，复用一次输入与已存模型；比对独立回读和提议计数。没有成功/部分正式任务重跑；先实际包4split无fit启动，避免目录冲突。

## 4. 点风险验收，完整保留分母

原sample支持/来源和原标准不降：两个true低E/传统RMSE比来源95%上限≤1.05恢复，gain下限>0才超越；all/F7≤1.01，≥200/reco pz50–100/high-y/未确认/F7≤1.03，整体及正/负tail50增量上限≤2pp（原各关键层都报）。不能以较弱M替代传统/F7门槛。

OOF X_raw/M_raw及最终X/M、传统/F7/stage68/69/71固定参考完整对照；train内、OOF、cal和eval开发分开。所有七真E箱、3.2–6.4TeV、≥200、pz50–100/100–250、high-y、未确认、缺失和12零q诊断层给N/来源/唯一incoming、logRMSE、mean/median bias、R68、上下tail50/100及尾损失；≥6400空层未测。unit总体、固定七非空箱等权MSE开根的macro和两低E并列，不用macro替换unit保护。

500次component分层保守来源配对固定点预测bootstrap，seed2026111375（cal+1/OOF+2），offset/q/模型固定，记录有效/无效；不含重训、q/负配对RNG、完整谱系、响应/选择误差，cal/eval仍开发。密度/归一和数值误差另报；分类ECE/判别信息与新点风险的关系只能据实讨论，不能自动叫后验闭合。

## 5. 资源、结果分流与交付

拟议≤4Condor，每fold一个＋final一个，M/X复用该job输入/分块查询，1CPU/3000MB、累计CPU≤3600s、wall/job≤1800s、最终≤20MB；pilot后按实测冻结，核最终ClassAd和worker硬上限，原预算不自动延长。源码未变不编译C++，用CVMFS；EOS实际物理I/O未测则明写，紧凑结果去重。仅257→513固定身份数值QA允许额外query，不能变种子/架构/先验/能量决策研究扫描。

主X_cal若OOF/eval稳定且原全门槛通过：只冻结研究候选，需共同响应/真新来源随机确认。若有信息而点风险未恢复：给实际信息→决策落差、边界/校准/支持和困难双向代价，不推成信息极限定理；结束这一固定决策预算，转真实新增歧义两侧支持，不自动temperature/q/架构轮换。数值QA失败则交具体积分问题，0正式点结论。未测均标未测，不把概率或macro改善代替能量恢复。

中文stage75报告包含实际输入/数值/单位/命令、数值与身份/来源QA、全部点风险/双向尾、CPU/wall/RSS/吞吐/产物、物理/程序解释及唯一下一任务。更新路线/信息预算/Prompt，先报告后本地Conventional Commit、不push，不自动执行新生产。实际[π/K/共同响应请求](../workbook/stage74_energy_ml/followup_input_request.json)、raw/stage54、Calo条件、interaction/FSI/材料、接受度/背景与未开发确认继续交付；不发外部消息或用metadata数量冒充功效。

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
