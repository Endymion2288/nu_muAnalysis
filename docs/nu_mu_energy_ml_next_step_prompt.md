# 下一轮执行 Prompt：stage97 同输入的候选—边联合编码消融

先读AGENTS.md、[stage96报告](../workbook/2026-11-04_stage96_candidate-input-ablation.md)、修订路线§78、信息计划§58、stage93复盘和stage94 cal协议。**stage96恰两fit及完整评价已完成，不得重跑；本轮只做一次同输入的有限联合表示消融，恰两fit，不自动执行stage98。** stage54历史支线保留，stage85条件活动控制已完成，不默认重做。

## 1. 已测依据及唯一问题

stage96原71376条全保留，70332可读、1044缺候选源保留摘要；75220节点/4888 leading边。A新增分支常数、B实际候选/几何，test总体log-RMSE .295567/.295826，B/A1.000876 [.993406,1.007993]。最低真E50–100为.272854/.284603、传统.145661；两格无联合通过。多轨迹test850条/834incoming，.385150→.371944，比.965712 [.935322,.999559]，cal对应区间含1。单seed/预定义多组条件区间不能称总体或经多重比较控制的发现；不按test补seed。

当前节点与边分别编码、各自mean/max pool，没有逐备选保留候选状态和对应leading边的联合消息。这个结构限制已经确认，但并未证明是物理风险瓶颈；两轨迹时边际pool未必丢配对信息，仍可能比较非线性归纳偏好。**本轮回答：保留全部相同边际输入后，增加正确配对的联合消息能否改善原联合点风险？** 不是新探测器信息采购，不将任何增量全归因于primary替换或信息因果；有效容量因素仍需说明。

方法参照[Interaction Networks, arXiv:1612.00222](https://arxiv.org/abs/1612.00222)，stage96已在线核阅。论文是关系物理模拟，不是本探测器性能承诺；只取聚合前联合编码的思想，不做预训练、大型Transformer或深度/宽度网格。

## 2. 输入、来源与不可改变的合同

复用原stage87兼容89033池、46575train/11612cal/13189test/17657隔离和incoming总权重；原stage94 source/incoming不交的select5443、post5746，冲突423仍全cal报告。全部1016新增K、missing21/6/5、低pz/真高E/high-y/未确认/高端完整保留，无新样本前置。主体reco pz0>50GeV，一次方动量仅pz0，允许px/py/q/p/弯折；不加p0/p1/pz1或其比。raw11/status、合法signed负值、typed NaN和Calo缺项保持。

直接用`ntuples/energy_ml_stage96/candidates.npz`、`QA_candidates.npz`及stage94摘要预处理；原split/兼容缓存和cal分区按原row核身份。已有紧凑节点float32原生leading最大相对量化误差5.912586e−8，不误认错配。稀疏边与规范排序后nodes[1:]逐项对应，由保存cache几何复核过；无hitSet/truth/截断去重。

stage70 28条π、stage82全部1016新增K的临时PHYS已删除，候选不可用1044条（345/343/356）必须保留原摘要及缺源状态，不能替换来源/当空/丢K/恢复旧K生产时限。stage96计数命名更正已见bookkeeping_audit：13189为请求test输入，实际打开12833载荷；不重复提取。共有3966个多轨迹记录，分别2480/636/850，实际可读空集合0；仍要支持未来空集合。

本轮0ROOT读取/新MC/重建，无需重新打提取包。manifest是raw/status重复已清理，可从原缓存重建；本轮不需重建它。旧stage87/92/94/96预测与offset复用，不再训练旧控制。test是开发过的研究池，本轮fit留出不能称新blind。

## 3. 恰两fit，冻结一种联合表示

两格都保留stage96 B的真实62 typed摘要、22节点/5边各自编码/mean-max池化/leading embedding及4个metadata。节点44→32SiLU→32SiLU，边10→16SiLU→16SiLU；原train-only变换和summary127维状态直接复用，不按新cal/test重估归一化。全部边际输入对两格一致。

只新增一个消息模块：拼接leading节点32维、备选节点32维、该备选对应leading边16维，共80→32SiLU→32SiLU；对真实边masked mean/max共64维，再与原259维一起接2×64SiLU→1 logE head。无递归message passing/attention/深度扫描，不改点目标。A消息模块用固定一个全0输入/固定有效mask，因此输出恒定且不随真实边或配对变化；B用真实逐备选配对，无边或缺源时联合pool为0，原metadata仍保留状态。两格原节点/边pool和metadata都仍真实可变，区别仅新增联合分支。A不能通过新增分支的padding形状、分母等额外泄露联合内容；原边际信息本来就在两格中，不声称A无候选信息。

同声明结构、seed2026110497/初始化规则/优化器与预算，QA后在新cal风险前记录精确参数量。恒定对真实消息分支的有效容量不同，不称容量完全隔离或家族最优；B/A是有限联合编码方案增量。原stage96只作为旧控制，本轮两fit才能构成同轮对照。

incomingweighted log-MSE、Adam lr.001/default betas/no decay、clip10、batch1024，每epoch同seed一次NumPy permutation；max300epochs/每5轮原cal_select点MSE/strict min/patience30epoch。各自停止，不保证同更新次数。原cal_post各一次weighted mean(logtruth−point) offset，raw/offset分列。最多2fit，无额外seed/warmstart/预训练/模型扫描，test不得选checkpoint/gate/偏移。两个fit及偏移固定后才产生新test预测与诊断；冻结前不打开新的test风险。

## 4. 固定40 QA、GPU/CPU与完整验收

原stage96的40个不同train/cal incoming，不新增身份或按能量误差/候选多寡重选。0optimizer QA核既有row和边到备选对齐、共同置换不变、改变候选—边配对能使非退化B联合表示改变、A新增分支恒定、缺源/空/全mask前向反向finite和全body/关系模块梯度。若真实40无≥3候选，不为展示配对敏感性换名单；可仅从同40张量构造明确标记的有限合成配对例做代数检查，不把它作为物理样本/风险结果。head零初始化时使用QA非零head核VJP，正式训练仍原零weight初始化，不继承QA状态。

按全输入max10节点/9边padding同40测实际CPU/GPU F/B、导入/传输/同步/内存，实际包逐源文件和数值QA后冻结资源。仅建议阶段CPU≤7200秒、1GPU并发/GPU任务累计wall≤3600秒、最终紧凑≤20MB；收益/新成本未测，stage96的42秒容器时间只是参考。拟合优先已授权GPU batch平台，用仍有效令牌，不复制/记录凭证；大批评价必须HTCondor、78个独立任务用8CPU/每process BLAS1线程、fork只读共享draw，不把分配核数当实际占用。

完整原cal/test：两低E50–100/100–200、all、≥200、reco低pz、同低pz真高E、high-y、未确认、高端和missing；各source/component、候选可用/缺源、单/多候选及原X组分母和风险。原八层RMSE门槛：低E对传统上95≤1.05、all/direct≤1.01、≥200及困难/direct≤1.03；原各层总/正/负tail对direct差上95≤+2pp，不能仅交平均误差。500component内incoming配对重抽，同incoming多视图一起移动；记录source95未测/单seed/重训和offset/系统/研究选择不覆盖，缺源test只有一个source不可单独认证。点回归不编造density/PIT/coverage。

独立核配对聚合/实际表区间和旧控制、checkpoint/offset、完整行/权重/K与typed缺失闭合。记录真实wall/CPU/GPU allocated峰与适用范围、8核实际占用、未测量项，嵌套时间不加。成功标准是一次完整可复核的同输入表示比较，不要求强行晋升；仍无联合收益就交明确结论和真正关联读出/协方差输入缺口，不自动续消息深度/宽度/seed扫描。

## 5. 交付

先写中文stage97 workbook：目标、原输入/配置/命令、实际两fit曲线/参数、全分层及尾/区间/图、程序与物理解释边界、实际资源和保留字节、失败/未测项、下一具体任务及验收。模型/缓存只EOS留最小结果，去重传输归档/重复JSON，不复制旧共享缓存。再与代码/配置/紧凑证据本地Conventional Commit，不push、不自动进入stage98。路线/信息计划历史仅追加，下方stage54后缀逐字和五项工作树保持。

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
