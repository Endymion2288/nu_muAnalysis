# 下一轮执行 Prompt：有界连续能量似然比研究

先读AGENTS.md、[stage60报告](../workbook/2026-11-02_stage60_profiled-expert-gate.md)、路线§41、stage57研究报告及 `workbook/stage60_energy_ml/{protocol,models,optimizer_diagnostics,acceptance,validation}.json`。stage60的4次gate拟合已完成，不重跑prepare/fit、不覆盖历史协议或失败记录。当前继续F7，结束当前gate调参支线；本次只做以下连续能量似然比研究。

## 已测证据和唯一问题

stage60解析rho使所有训练callback及选中/末端均可行，但evaluation低E50–100/100–200 log-RMSE为.186690/.260643，传统为.145487/.226876。全体/低reco p/high-y/未确认代价仍失败；cal OOF最低能.203420也未恢复传统。3/4求解器成功仅为函数变化终止，末端梯度与方向探测不支持充分stationarity。不能宣称信息极限，也不再延长gate优化。

本次问题：**用连续E条件似然比保留完整能量依赖，能否改善低真实E与同reco低p高E/high-y混合下的风险取舍，并减少对训练能谱先验的敏感性？** 方法入口沿用stage57的[Hermans等2020](https://proceedings.mlr.press/v119/hermans20a.html)。收益、所需功效和实际资源尚未测量；旧六箱概率负结果仍约束投入，不重新包装旧q或flat回归。

## 执行前冻结的输入与训练协议

1. 复用stage55 `dataset.npz`、stage56 `readout.npz`和F7预测。train41447/cal8440/eval14057、来源保护、truth去重及原pz>50选择不变；cal/eval均已开发，不叫blind。只读紧凑缓存，不读locked test、ROOT/RDO，不新生产/重建、不恢复shards、不做谱toy。原选择仍含部分fit-charge cut，本次不测其接受度影响。
2. X仅为`audited_features.load/build`的同62个F7清理读出。线性模长/纵向动量仅pz0，px/py、q/p、弯折允许；11闪烁体raw及VetoNu reduced不回退。保留合法负数，非法占位/status/父项依赖转NaN；不删缺失者，不用fit charge补raw。完整42缺失者原角色、全部大尾/high-y/未确认保留。除扫描参数t=log(E假设/GeV)外，不加入truth/y/来源/身份；假设E不是部署事件的真实能量。
3. 在新fit和新评价结果前写不可覆盖stage61协议，记录输入/软件、精确负配对/权重/先验、候选、seed、输出和资源。只有两种训练先验：unit empirical；按train固定logE箱等总权重的bin-flat。默认50/100/200/400/800/1600/3200/6400GeV边界；先核全部train支持，越界/空箱必须记录并在冻结前明确处理，不丢事件或按eval改箱。flat权重仅取train计数，报告各箱N/来源、权重和/范围及Neff，不称纯样本量干预。
4. 每种先验的正例为train真实(X,t)，保留相应权重；负例从同一加权train的X边际与t边际**独立有放回**各抽2N，形成乘积分布。负例均匀权重，正负类别总权重相等。固定一次负配对seed，记录重复使用及偶然重复真实配对，不用删除真实配对改变乘积分布。负配对不增加独立MC事件/来源。平衡分类器logit近似log p(X|t,S)/p_ref(X|S)，仅是选中S内的响应比，不包含接受度/背景。
5. 只做两次固定XGBoost二分类fit：unit与bin-flat各一次，depth5/400轮、同F7级其余超参数、单一seed2026110261。冻结确切参数/版本，不以cal/eval早停，不重训F7或回归器，不扫seed/架构/网格/负例数，不续调gate。保存训练状态、损失、CPU/wall/RSS及支持统计。

## 预定输出、敏感性及验收

1. 每事件扫描固定129个log-spaced 50–6400GeV假设，分块计算log-ratio，避免全量(X,t)展开驻留内存；只留必要紧凑预测/模型和聚合曲线。事前固定两个输出：网格MLE（并列取最低E并报并列率）；加入**共同unit train-only冻结先验**、以固定logE积分权重归一化的posterior mean(logE)，再取exp。参考先验在logE的密度、端点权重和零支持处理必须在fit前写明；不能每个分类器使用其自身先验来混淆比较。raw及每输出一个global cal log-offset均报告，不做分箱校准，不用eval挑估计器。cal为校准开发指标，不能以全cal offset称OOF。
2. 两分类器在同一参考先验下比较稳定性；再使用共同bin-flat参考先验作0新fit的预定敏感性诊断，与unit输出并列报告。有限样本/容量会使训练先验仍影响响应。检查端点率、次峰/并列、网格积分及固定少量train/cal例的曲线；不按结果加密网格或改范围。扫描范围外真值事件保留并单列。不能承诺MLE无偏、最低RMSE、后验校准或覆盖。
3. 与传统pz0/.8、F7及stage60固定参考完整比较：true50–100/100–200、全部能量箱、全体、true≥200、reco pz50–100/100–250、high-y、未确认、缺失组。报告N/来源、log-RMSE、mean/median bias、R68、双方向tail50/100，不只报低能中心宽度。两低E/传统RMSE比来源95%上限须≤1.05；真正优于传统需改善下限>0。全体/F7≤1.01、困难组≤1.03、关键tail50增加≤2pp沿用，不改门槛报成功。
4. 500次component分层来源配对bootstrap只重抽固定预测，不增加fit；注明不含训练/校准/分类器有限模拟/响应/研究选择误差，不作多重比较修正。cal16组/两个charm、最低能150/14组且无charm，evaluation最低能208/19组，不用大量负配对掩盖独立支持不足。
5. 无论结果都完成一次有限研究，解释响应表示、训练/推断先验、偏差/尾、边界和支持/数值因素。未知原因不作结论。失败则停止本次扫描，给下一项定向独立低E及同reco困难样本的具体输入/功效验收；通过也只冻结候选并安排共同raw和新生产确认，不自动替换部署。

## 预算、QA和交付

- 先小样本核joint/product权重、比值代数、推理不读truth、假设单位、signed/NaN、端点积分及分块一致性。数值QA不增加分类fit预算；已知函数算术检验不叫物理toy。先测内存/推理时间，再冻结Condor分块配置，不把预算当实测成本。
- 固定2fit，批量通过HTCondor；拟议最多2任务、各≤2CPU/3GB、累计CPU≤1h、最终新增≤20MB，包含fit和整网格推理。若pilot表明不可达，先给实测瓶颈及具体缩减方案，不静默追加任务。不按结果重试/扩网格；技术失败如实记录，不当物理阴性。复用CVMFS，不重建无改动C++或读大型ROOT。
- 写stage61中文workbook，包含实际N/选择/输入/配置/命令、实测wall/CPU/RSS/I/O、fit数、产物、结论/限制及具体下一项验收；更新路线/Prompt，本地Conventional Commit，不推送、不自动启动下一研究。stage54既有工具/缓存保持原状且不混入提交。
- stage54/data占据、共同raw积分/饱和/时间窗定义、ν interaction/FSI/材料、独立低能及困难样本和最终正向谱收益仍必须交付；本次选中事件似然比不替代这些工作。

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
