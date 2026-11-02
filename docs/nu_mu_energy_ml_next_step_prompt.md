# 下一轮执行 Prompt：stage62 平滑连续响应与额外读出的条件价值

先读 AGENTS.md、[stage61研究复盘](../workbook/2026-11-02_stage61_research-reassessment.md)、[stage60实测](../workbook/2026-11-02_stage60_profiled-expert-gate.md)、修订路线§42和信息预算§22。stage61只做研究设计，没有新实验；下一次实验编号为stage62。stage58–60已完成，不重跑prepare/fit、不覆盖历史协议。本次在有CERN环境的节点执行以下有限研究，当前继续F7。

## 研究问题与预定决定

**相对只看pz0，完整62个读出是否能更可靠地预测同一pz下的能量分布；该增量能否同时改善低true E与全区点预测？**

stage60 true50–100/100–200 log-RMSE=.186690/.260643，传统=.145487/.226876；全体/低p/high-y等代价仍失败。原gate只用四个汇总量，训练标签来自cal，其中最低能仅150例；不能据此否定完整X。3.2–6.4TeV的F7中位bias仍约−43%。本次用完整train和连续能量假设，不续调gate。

相同X与先验下，理想posterior mean(logE)与log-MSE回归有同一Bayes目标；似然不会自动增加信息，也不保证MLE无偏。主要点候选事前固定为unit完整模型的posterior mean(logE)。概率增量和点预测推广标准分别回答，不能用其中一个替另一个报成功。

## 1. 输入和样本

1. 复用stage55 `dataset.npz`、stage56 `readout.npz`、F7预测及stage60固定对照。train41447/91组、cal8440/16组、eval14057/22组，沿用来源保护与原pz>50选择；不读locked test、ROOT/RDO、不新生产、不补造alternative raw、不恢复已删PHYS、不做谱toy。cal/eval已开发，不能叫blind。原选择仍含部分fitted-charge cut，本次不测接受度变化。
2. X只取`ml/audited_features.load/build`的F7 62列：线性模长/纵向动量仅pz0；px/py、q/p、弯折允许；不用p0/p1/pz1/log(p1/p0)。11闪烁体用raw，VetoNu reduced保留。合法signed负值/−1按逐变量域保留，失败status/父项依赖转NaN；不删缺失、不nansum补零、不fit补raw。
3. 原42缺失者角色、所有high-y/大尾/未确认保留；unconfirmed不能全当错primary。除扫描假设t=log(E假设/GeV)外，不把truth/y/来源/身份用作部署输入。
4. 全部train标签用于训练，cal仅作预定校准/诊断；不再仅靠150个cal低E例学gate。cal最低能150/14组、无charm，eval208/19组；这些支持限制仍须报告。去重保护不等于已认证完整谱系独立。

## 2. 只做三个固定平滑分类fit

在任何正式fit及新评价前写stage62协议，冻结版本、输入、变换、先验、负配对、seed、模型和资源；不覆盖既有协议。

1. 三个模型：A=完整X＋unit；B=完整X＋train logE-bin-flat；C=pz0-only＋unit。A是唯一主候选，B检验抽样先验敏感性，C是μ-only概率对照。不是选三个模型中eval最好的。模型均为两层64单元SiLU MLP＋单一logit，固定seed2026110262；AdamW lr=1e−3、weight_decay=1e−4、batch1024、120epoch，无cal/eval早停，不扫seed/层数/损失/负例数。不采用树网格并列最低能MLE。
2. 对每一配对先生成(X,t)，再构造`u=t−log(pz0/GeV)`作为能量假设坐标。不能独立抽u后仍声称joint/product代数不变。μ-only模型使用logpz和u；完整模型使用同62列的变换、缺失mask和u。坐标变换不增加物理信息，不等于重做residual50回归。若有无效pz，先在协议中明确可推理的缺失分支，事件保留，不能取非法对数后删例。
3. 正值动量用log、非负计数用log1p、signed量用asinh；尺度和median/IQR均只由train确定，零尺度回退须有固定规则。缺失用train-only插补并保留mask。无需为此重新读取ROOT或历史波形。
4. B的flat权重按train固定logE箱等总权重，默认50/100/200/400/800/1600/3200/6400GeV边界。先只查train支持，越界时在fit前按固定倍增边界覆盖；空箱无事件不能靠合成填充，不丢越界事件、不看eval改箱。记录N/来源、权重和/范围及Neff；不称纯样本量干预。
5. 各模型正例为train真实(X,t)，带对应unit/flat权重并归一到总权重N。负例从同一加权train的X边际与t边际独立有放回抽2N；每负例权重1/2，使类别总权重相等。A/C复用同一unit负配对以便比较。一次冻结负配对seed，偶然真实配对不删；负例/重复使用不增加独立MC。
6. 平衡binary logit的目标为`log p(X|t,S)−log p_ref(X|S)`；是选中S内响应比，不含接受度/背景。B的不同reference改变X相关常数，比较时必须归一到共同先验，不能直接比较原始logit高度。

## 3. 推断、概率增量与点预测

1. 固定129点logE网格，默认50–6400GeV。若train支持要求扩展，在任何fit前按上面的固定倍增规则冻结统一范围；不能看eval后改。分块推断，不让全量(X,t)展开常驻。t/u在推理时只来自假设和reco，不读该事件真值。
2. 共同先验π_unit只由unit train的选中谱冻结：默认每能量倍程两个等logE箱的分段常数密度，每箱加入1/2伪计数后归一；边界覆盖扫描支持并写入协议。该正则是数值/先验选择，不是新增MC。三模型均用同一π_unit和同一logE积分/密度插值约定，得到`qπ∝exp(logit)π`。共同logE均匀π_flat只作0新fit敏感性对照。
3. 主点输出为A的exp(E_q[t])；A/B/C在共同π_unit下均报raw及各一次global cal log-offset点输出。此offset不是OOF，也不能把点校准说成完整分布已校准。概率评分只对原始归一化q；π_flat敏感性只报raw，不据eval选先验/估计器。
4. 概率主比较：A相对C的held-out log-density score、logE-CRPS与低E概率可靠性，按来源报告全体、true低E、同reco低p/high-y等。C是动量条件分布，不能把传统pz0/.8当零宽概率分布直接比NLL。B相对A比较共同先验下的形状/评分稳定性。单个真能量组上的评分是诊断，整体proper score增量也不等于精确互信息。无增量不能证明额外X无信息。
5. 报告积分误差、扫描边界率、非唯一/多峰及低/高能曲线。MLE仅作诊断：宽平台/多峰报告其范围，不能并列取最低能后据此报低E改善。范围外真值事件保留点评价，明确概率支持失效；不偷偷只报覆盖内结果。少量train/cal曲线事前固定选例规则，不按eval挑漂亮曲线。
6. 传统pz0/.8、F7、stage60固定参考与A完整比较：true50–100/100–200、全部能量箱、全体、≥200、reco pz50–100/100–250、high-y、未确认及缺失组。报N/来源、log-RMSE、mean/median bias、R68、双向tail50/100；B/C并列控制，不用其最佳分数替换A。
7. 点预测沿用旧标准：两低E/传统RMSE比来源95%上限≤1.05是恢复；真正优于传统须改善下限>0。全体/F7≤1.01、困难组≤1.03、关键tail50增加≤2pp。1%/3%/5%等是既定研究取舍，不是实测物理容忍度；不后改门槛宣布通过。概率有用而点未过应如实分别说明。
8. 500次component分层来源配对bootstrap仅重抽固定预测，不增加fit；明确不含重训/校准/有限分类器/响应/研究选择误差，不作多重比较修正。按实际来源支持解释，不能把负配对数当独立统计量。

## 4. 预算、QA与停止条件

- 正式fit固定3次，单一结构和seed；global offsets为既定校准，不是额外模型搜索。先少量pair验证加权joint/product代数、signed/NaN、u依赖、logE密度单位、归一化/积分和分块一致性；资源pilot只作数值/吞吐验证，不额外训练候选或读取新物理结果。
- 小型MLP的实际成本未测量。拟议最多3个Condor任务，每个≤2CPU/3GB、累计CPU≤3h、最终新增≤20MB，包含fit和完整推断；先按pilot实测冻结可交付资源。GPU若可用需记录actual资源，不能用GPU速度掩盖I/O；不重建无变化C++。预算是上限建议，不是测得耗时。
- 保存模型、变换/先验、必要逐例点/评分摘要和少量曲线；不保存全train×能量网格、不复制ROOT/NPZ、不留批量重复JSON。记录实际wall/CPU/RSS/I/O，不能把文件大小当网络I/O。
- A概率稳定且点过门槛：冻结候选，安排共同raw和新独立来源确认，不自动部署。概率有增量而点失败：保留分布价值，下一研究做联合μ/ML物理响应，不续扫点估计器。无稳定增量：结束本次模型预算，给出定向独立低E及同p困难样本需求，或物理transfer/可见度分量的单一后续。技术失败与物理阴性分开，不能用3次fit否定全部似然方法。
- 不因本次成功或失败自动训练flow/TabM/Transformer/GNN、重启gate、改选择或开新生产。不要把原有概率六箱/flat/residual方案重新包装成新解。

## 5. 报告与下一项物理交付

写stage62中文workbook，包含目标、实际样本与选择、输入/配置/命令、全部数值与单位/区间、资源、产物、方法与物理解释、正负结果和明确下一项验收；未测量项写明。更新路线/Prompt后本地Conventional Commit，不推送，不自动启动下一研究。stage54工具/缓存按实际状态保留，不混入无关修改。

下一物理研究已明确：复用F7，以`z=(logpz0, logE_F7−logpz0)`联合响应，对比μ-only与已有灵活scalar，检验选中50–200相对≥200成分参数的不确定性；包含有限MC、来源留出及低能箱内/高E-high-y混合压力。不是重开六自由箱谱或大批coverage toy；stage62成功不是其前置条件，详见stage61§5，本次不连开。

共同raw积分/饱和/时间窗定义、stage54 data占据、ν interaction/FSI/材料、定向独立低E及困难样本、接受度/背景和最终flux收益仍需交付；选中事件似然不能替代它们。

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
