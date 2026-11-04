# 下一轮执行 Prompt：Stage104 固定概率表示的连续点决策实验

先读AGENTS.md、[Stage103研究复盘](../workbook/2026-11-04_stage103_research-reset-and-decision-budget.md)、路线§85、信息计划§65和stage99/100/102。stage102双checkpoint、stage99温度、stage100配对与结构审计均已完成，不重做。用户新的研究请求覆盖旧Prompt“仅终态交接”的优先级；本轮只检验下面一个新假设，不自动开展关系预训练或后续阶段。

**在有实际环境的节点执行。当前本地终端不恢复CERN环境或复现事件。** 0新能量网络/分类器/ROOT/native/生成/重建、0网络forward/后验积分，0新offset/T/seed/架构或prior网格。读取保存head并做解析矩不等于模型forward。

## 1. 研究问题与输入

问题是：固定stage99已训练且做过一次尺度校准的q(logE|X)，改变连续点动作，能否降低两低能风险且保护总体/困难侧？这与温度点保持不同，也与旧stage68/73重训、stage78有限专家凸包不同；形式上仍与能量重权/先验倾斜有关，不声称新信息或无代价修复。

输入仅保存缓存：stage94的`evaluation_input.npz`、`cal_partition.npz`、`ml/artifacts/stage94/{MDN_heads,point_predictions}.npz`，stage99的`calibration.json`、既存概率尺度源码和汇总，stage87同split `predictions.npz`及原身份/权重。具体路径与head解码见`ml/stage99_report.py`，只复用读入/解析过程，**不得调用会重新拟合T的main**。stage92/102仅作已提交结果参照，不重新forward或积分。没有实际head缓存时交精确缺失输入，不从工作簿汇总虚构事件分布。

原89033兼容池、train/cal/test46575/11612/13189、唯一incoming37556/10811/12125、隔离17657不变。select5443/post5746，最低能85/97；423退出select仍保留完整cal。所有1016新增K、missing21/6/5、两低能/高端/困难与尾保留；不重分角色。原incoming总权重1，两个cal子角色用原subrole重归一权重。一次方动量pz0-only、允许原px/py/q/p/弯折、raw11/status/typed NaN/合法负raw和Calo缺项保持；不加p0/p1/pz1、truth输入或按真值部署gate。

## 2. 先冻结解析动作与唯一优化问题

q固定为stage99 E94三seed九Normal混合及原b/T，完整值直接读calibration.json，不用文档舍入值。以九分量共同的原mean logE为尺度中心，按stage99规则变换；不能各seed单独居中，也不套stage102单seed旧b。混合权重/密度不优化。

令t=ln(E/GeV)，I1=[ln50,ln100)、I2=[ln100,ln200)。对每例解析计算Pj=∫Ij q、Mj=∫Ij t q、m=∫t q。单Normal的P=Φ(β)−Φ(α)，M=μP+σ[φ(α)−φ(β)]，再按混合权重求和。输出解析aλ=(m+λ1M1+λ2M2)/(1+λ1P1+λ2P2)，实际点数组为**原保存点＋解析(aλ−a0)**，避免float64重解码改写旧float32点的末位。

λ=0必须逐位返回旧stage99点；全部X连续输出，允许负修正，不强制E≥重建pz、不截到truth能量范围、不拒绝困难事件。新的点是成本敏感动作，原q继续作为概率产品，两者分开命名；不把加权q宣布成新物理后验。high-y/未确认不由这两个能区矩完全描述，保留经验评价，不宣称解析满足其风险。

只在原cal_select拟合λ1/λ2与辅助τ，最小化τ：两低能新MSE≤τ×同支持传统MSE。λ∈[0,100]²；匹配开发保护为新all MSE≤1.01²×旧E94，新≥200/低pz/低pz真≥200/high-y/未确认各≤1.03²×旧E94。这里保护旧E94是为了有λ0可行控制，**不替代最终对原direct和传统的门槛**。所有损失保留完整尾、不换Huber/裁残差或按cal补变量。

恰一次SLSQP，解析导数，起点λ=(0,0)、τ为当前两低能风险比最大值，ftol1e−9/maxiter200。事前固定，不从test换起点/bounds/算法/目标、重启或扫描λ网格。记录status/边界/可行残差，数值不成功则报告未定和已完成QA，不用中间解选test赢家；有限参数非凸问题不称全局证明。0新offset/T或第三权重。冻结λ后才评价完整开发test。

## 3. QA后同阶段交完整点结果

从原cal固定≤40身份（含全部6个cal缺失及select/post）做0优化QA：身份/角色/head的原变换、Pj范围与区间可加性、截断矩的独立解析算例、λ0点逐位不变、λ导数有限差分和实际CPU/wall/RSS。核原q均值/概率与stage99保存汇总，不重新拟合概率参数或为此全量重复概率表。原float32与解析float64差沿已有3e−6控制并单列；不事后改容差。本轮只需保存的cal head做QA，不能为补QA身份重开网络forward；stage94保存active角色，勿与stage102仅cal/test的head合同混用。若QA有程序错误，修复算术后再执行唯一优化，不能把失败当物理阴性。

主开发证据：原cal_post上，两低能各新/旧E94 RMSE比的**最大值**，以500次共同component内incoming抽样给条件95%区间，上端<1才支持共同低能增量。两cal子角色权重保持原定义，cal_post不拟参数。全体/困难相对旧E94的保护、原传统/direct的最终验收分别交付，不拿平均AUC/NLL或单个低能改善替代。

无论是否有利，按冻结策略一次性交完整cal和开发test的原八层：all、E50–100、E100–200、≥200、pz50–100、低pz真≥200、high-y、未确认；另保留高端/缺失/confirmed低transfer等旧诊断层。log-RMSE、bias/R68、总/正/负tail50和配对区间齐全，给相对传统/direct/原E94三种基准的清楚命名。使用原incoming重抽样规则、相同draw复用，不把来源/refit/校准/研究选择或真实response当已覆盖。

原最终要求不改：两低能/传统RMSE比上95≤1.05，all/direct≤1.01，≥200及困难/direct≤1.03；八层三向tail50差上95≤+2pp。主开发增量不等于最终联合通过，cal/test已开发不能叫新blind。概率q不变，不宣称新coverage/NLL收益，点动作可以改变点风险。

## 4. 预算、停止与交付

拟议一次CPU批任务申请最多4CPU/6GB、进程内线程1；解析矩/两参数求解无需GPU，配对统计复用只读数组和同draw，最多4进程/1任务并发。阶段CPU≤900秒、任务wall≤900秒、紧凑最终≤20MB；≤40QA实测后准入，新成本/收益/功效未测。没有ROOT/native I/O或新事件副本；只保留两权重、配置、紧凑点输出及必要汇总，旧head/q/b/T只读复用，不生成大积分/500draw副本。

给出明确结论：有开发点增量则记录改善与最终差距；无可行改善则结束这个固定q两参数动作族，不追加权重/局部校准/专家或重训。失败只限制该表示与动作族，不认证信息极限或否定关系预训练。stage103提出的全点关系/遮挡预训练、独立低能支持和真实response分别是另冻研究设计，不能由本Prompt自动连开。

先写中文stage104 workbook，包含样本/选择/单位、输入与命令、实际λ/求解/风险区间/完整尾与程序及物理解释、资源/失败/未测量、产物和明确下一科学问题，再与代码/配置/紧凑证据本地Conventional Commit；不push、不自动stage105。历史路线只追加，stage54原后缀逐字保留，其实际完成状态以stage85为准，不重做历史noise支线。

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
