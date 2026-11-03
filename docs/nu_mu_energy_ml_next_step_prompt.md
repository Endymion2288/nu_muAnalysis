# 下一轮执行Prompt：stage73 低能重建取证与固定能量重权

先读AGENTS.md、[stage72研究复盘](../workbook/2026-11-03_stage72_reconstruction-reweight-reassessment.md)、[stage68](../workbook/2026-11-03_stage68_group-risk-regression.md)、[stage69](../workbook/2026-11-03_stage69_transfer-supervision.md)、[stage71](../workbook/2026-11-03_stage71_fixed-support-augmentation.md)、路线§53/信息预算§33。stage72只有研究设计，最新实测仍是stage71；本Prompt供有CERN环境的节点执行，不要求在研究终端安装环境。本次用户明确提出重建排查和能量reweight，更新stage71后“所有新方法须先交新生成”的过强前置；真正独立确认仍需新输入。

继续保留原F7。唯一科学问题是：当前低能失效与具体重建/读出状态怎样关联，固定边际能量权重能否纠正部分过修正，付出什么全区/困难组代价？不要重复28例π增补、对偶/辅助系数调参、架构/先验/校准扫描或EOS身份清单循环。

## 1. 输入、选择和不可改变的契约

- 只用stage55 dataset、stage56 readout、已有F7/传统固定预测与必要stage68 C来源OOF、stage71固定参考及身份metadata。nominal train/cal/eval41447/8440/14057，91/16/22来源；不追加stage70 π28例、不读取K QA作为训练，以隔离本次权重因素。已有cal/eval均开发，不能叫新blind。
- X必须通过audited_features.load/build使用同62列。线性模长/纵向动量只有pz0，px/py、q/p、弯折允许；p0/p1/pz1及其log比、次轨迹线性动量不作新增输入。11signed scintillator raw、VetoNu reduced、typed sentinel/domain/status/dependency→NaN保留；任一Calo module缺失使总和NaN，不nansum补零、不fit补raw、不裁合法负数。
- 原truth νpz与reco highest-pz leading>50GeV、fiducial/质量/其余fitted-charge cuts不变。42缺失21/3/7 eligible与11保护保留，巨大动量/高y/未确认/负修正和全部尾保留；truth只作训练标签/权重/诊断，不进入部署。
- 不读locked/未开发确认、原生大ROOT/RDO，不做新重建/生产、谱toy或SHA；不自动K重试/扩run。stage70参考化x不得重复缩放。新生成输入请求继续保留，但不阻断这次现有缓存开发。

## 2. A模块：零新能量fit/推理的逐例误差路径

完整检查cal/eval的true50–100与100–200，含全部尾和非尾，另保留相似reco pz/活动的高E/high-y/未确认对照。只使用已存预测；不要再用一个总体RMSE表作为全部交付。

对confirmed且primary/y有效的事例，由缓存E_mu,prod=(1−y)E_nu定义：

- a=log(pz_reco/E_mu,prod)；
- b=log(Ehat/pz_reco)−log(E_nu/E_mu,prod)；
- 检查逐例e=log(Ehat/E_nu)=a+b，组均方mean(e²)=mean(a²)+mean(b²)+2mean(ab)，保留有符号交叉项，不能解释成唯一因果百分比。

a是方向/传播/拟合的复合差，不叫纯tracker误差；b是附加修正与实际所需修正的差。未确认或非法标签单列且保留主评价，不能强填a/b或标错轨。train可用既有stage68 C的来源OOF作辅助，F7训练内预测不可冒充OOF。

交付两个低E全体/尾/非尾及来源层的a/b、F7修正、χ²/层数、几何、62列有效性与raw/Calo状态的联合证据，注明N/来源/缺失；与高E同读出者比较。可据已知尾作开发故障定位，未来确认不按旧坏例挑选。所有关联不自动等于因果。

沿用已有证据：stage55最低能206/208确认、μ核心R68=2.172%仅限选中支持；stage70 geometry/FPE日志和measurement长度不齐尚未证明进入旧nominal ML尾。stage55已说明measurement记录顺序问题，相关向量未入当前模型；先核计数/collection语义，不能自动宣布行错位。stage70 Calo03/01差已参考化，不作为同旧缓存失败的现成解释。

有可复现的输入/单位/对齐错误直接影响当前X时，暂停B，交付具体字段/事件/影响与一个配对修复合同，不删事件绕过；仅有全局日志/相关性不能无限卡住B。A不重跑框架、不盲改几何。重建前效率缺未选中母样本，本模块明确未测量；后续有需要再对少量已知nominal PHYS做独立cut-flow/配对修复设计，不在本阶段自动读新文件。

## 3. B模块：三种固定权重、最多12个正式fit

只在当前输入可用于既定比较时实施。三臂均为当前F7级直接预测t=log(E_nu/GeV)的BDT，depth5/400轮、eta.04/subsample.8/colsample1/min_child_weight20/lambda10/hist/单线程，单seed2026110373；相同未加权训练mean(t)初始化（明确base_score、boost_from_average=0）、相同参数/正则，唯一变化为训练样本权重。不使用动态dual、早停/最佳checkpoint或辅助头。

固定等倍程箱50/100/200/400/800/1600/3200/6400GeV；箱外不新增删除规则，真实空箱性能标未测量。对每次实际训练端计数n_b：

- U：alpha=0，w_i=1，匹配控制；
- S：alpha=1/2，w_i∝n_b^(−1/2)，唯一主研究候选；
- F：alpha=1，w_i=N/(B n_b)，非空箱总权重一致的敏感性控制。

N为本次实际训练端事件总数，B为非空箱数；空箱不赋伪权重。三者均使完整训练事件权重均值1；S箱总权重∝sqrt(n_b)，不是精确展平，F箱内谱也保持原样。权重直接进入DMatrix，不做加权抽样后再乘同样权重。report raw N/来源/唯一incoming数量、每箱总权重、权重范围及Kish ESS；ESS不叫独立物理N。完整train当前箱计数767/3564/9232/13805/10141/3656/282，F的既有全train ESS8621.671252只用于语义对照，折内要重新计算，不用held计数。

沿用stage68 v2三个保守来源折及训练端exact incoming purge，held不删、全部41447一次OOF。每折三臂＋每臂全train一次，最多12fit。折内权重/任何尺度只用实际训练端，不用held早停、调alpha/箱界/参数。不恢复stage68的乘法对偶，不增加LDS/BalancedMSE/Huber/flow/seed或新特征版本。

12fit是研究预算，单seed不包含重训不确定性。主候选S_cal固定，F不是事后备用赢家；所有臂都报告，不能因某臂更好改主候选。最终各模型raw及原8440cal的一个unit global mean-log offset并报，OOF仅raw；global unit offset与加权训练目标不同，应解释影响，不能另做truth分段校准。推理仅X，不按真实能量选模型。

## 4. 验收与结果分流

- 对OOF报告S/U与F/U；最终同一eval对U/传统/F7/stage68/stage69/stage71固定参考。给两个true低E层、全能量箱、≥200、reco pz50–100/100–250、高y、未确认及缺失的N/来源、log-RMSE、mean/median bias、R68、上下tail50/100和尾部损失。3.2–6.4TeV单列，≥6400空层不补0性能。
- macro明确定义为固定非空能量箱MSE等权平均再开方；unit总体、macro及两低E的收益/代价并列。不要用加权总分、主体宽度或尾外条件分数替代全样本表现。
- 延续500次component分层保守来源配对固定预测bootstrap，所有方向/空抽样透明；区间不含重训、offset重估、完整谱系、响应/interaction或研究选择误差，非独立确认。
- 原推广门槛不降：两低E/传统RMSE比来源95%上限≤1.05为恢复，改善下限>0才叫超越；all/F7≤1.01，≥200/低pz/high-y/未确认≤1.03，整体及双向tail50增量上限≤2pp。它们是研究标准，不是测得detector容忍度。不能因新U更弱降低F7基线。
- A发现可干预错误：先配对验证修复，B未运行照写。S在来源OOF/eval均稳定改善且原保护通过：冻结研究候选，安排共同响应/新来源确认，单seed不自动部署。F端点改善而其他区受损：报告三固定政策取舍，停止alpha扫描。train好而OOF/eval差：转真正新增的歧义两侧支持。a小、b大且三臂无收益：记录本次边际重权不足，下一项在条件能量假设判别、响应状态或实际新支持中依据A选择一个；不把结果叫全部方法不可行。

## 5. 资源和交付

先冻结stage73输入/公式/seed/分折/候选与结果分流，作小型加权均值/归一、解析梯度、NaN/推理仅X和资源pilot；不把pilot变额外科学候选。复用已有CVMFS与紧凑缓存，源码未变不重建C++。拟议≤4个Condor任务，每任务1CPU/3000MB、累计CPU≤1h、每任务wall≤1800s、最终≤20MB；预算/收益未测量，pilot后根据实测冻结，核最终ClassAd并保留worker上限。A/B复用一次缓存，scratch训练，不存新的全量输入副本/大量重复JSON。

写中文stage73 workbook，至少包括a/b恒等式及交叉项、低E尾与非尾/困难对照、实际权重/ESS/训练和OOF风险、全部eval门槛/双向尾、物理与程序解释、实际命令/CPU/wall/RSS/I/O/产物，以及唯一下一任务的输入与验收。新方法未测不写结果。更新路线/信息预算/Prompt，本地Conventional Commit、不push，不自动启动后续生产或模型。

共同raw/stage54、实际Calo条件、ν interaction/FSI/材料、接受度/背景、真正新π/K生成及未开发确认仍须交付。原stage71输入请求保留为数据分流，不能用metadata数量、重复digitization或28例小增补替代足量支持。下面stage54协议逐字保留，只有进入该支线才适用。

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
