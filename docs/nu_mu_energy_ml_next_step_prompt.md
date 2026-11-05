# 当前交接 Prompt：Stage108三格能量比较已完成，固定方案失败及真实终点缺口

先读AGENTS.md、路线§90、信息计划§70、[Stage108实际报告](../workbook/2026-11-05_stage108_full-point-relation-comparison.md)、[decision](../workbook/stage108_energy_ml/decision.json)、[完成审计](../workbook/stage108_energy_ml/completion_audit.tsv)，以及Stage103 §5–7。完整三格和风险本轮已完成，不能再按Stage106/107缺口重训；整体能量/物理终点仍未达。

## 1. 最新实测与结束范围

Stage108在本次持续目标下、任何全提取/optimizer前明确重设内部GPU预算2h→3h、CPU仍6h；科学合同和物理门槛不变，Stage106/107拒绝原样。全active71376角色原样提取，70332几何可用/1044缺源、15317515原点，0invalid、pz差0GeV/float32损失0mm；全部K与困难者不删。全train/cal122821859边、max10618点/116238边；完整准入及40例训练循环无更新适配/checkpoint回读通过。

唯一train-only预训练46230身份、固定20epoch/3620step；A/B/C监督55/55/50epoch、best25/25/20。三checkpoint与原cal_post单offset全部冻结后test一次提取/推断，全六raw/cal评价，无额外seed/校准/策略选择。

**主C_cal/A_cal两低能最坏比cal_post1.085532136 [1.053995639,1.151241510]，未支持增量。** cal最低能单组CI含1、第二低能排除1，不能说两cal单组都显著恶化；C/B两cal低能均有损失条件证据。B/A test两低能.941363 [.912611,.965639]/.972888 [.957446,.988274]有局部改善，但cal_post两组仍含1，低pz真高E test1.012767 [1.002106,1.022744]恶化、总体含1。最低能A/B/C cal .290846/.273792/.310558对传统.145661，全体.297337/.297717/.301478对强direct.287491。六策略最终联合全False，不晋升。

840旧标量max0、主区间独立差2.220446e−16、192gate区间max4.440892e−15。CPU实际2774.638062秒，包含提交宏错误导致一次重复train提取1029.268536秒，`-append`核Args修正后正确test，未重训；最终descriptor默认required。正确test结果FUSE滞后用XRootD回收无重跑。GPUfit outer680.536285wall秒，终态PodGC未保留CPU/内存和精确容器wall，按Job693秒保守计；infer容器22秒。连106/107已计CPU2810.686772秒、GPU计/预留734秒。wholefit绝对GPU峰、平台/全会话/物理网络/GPUbusy未测。

**结束本固定点关系＋遮挡方案。** 不自动Stage109、续seed/深宽/正则/隐藏任务/新loss或再次提取三格；预训练loss下降不是能量收益，不据此否定全部预训练/关系信息或认定数据充分。原动作/T/collection族仍结束，不恢复旧REC/EOS无新线索扫描。没有新样本并非所有开发不可能，但这份具体合同已兑现有限结论；新工作须有明确可失败科学问题和交付，不制造无限计划链。

## 2. 持续目标仍缺的实际交付与验收

1. **独立低能/过渡支持和确认**：新source/incoming谱系、提议密度/权重、原选择/接受度、pilot实际选中产额；真50–100/100–200GeV、同低pz真≥200/high-y反例和高端控制。验收无旧池重复、困难者不删、真正未开发locked来源。旧1016K已全使用，不能重分/多seed叫新blind；数量/功效未测不猜。
2. **真实response**：实际IOV/逐事件DAQ有效mask/coverage、无偏quiet/random或等效校准及PHYS身份联结。Stage85已做2048data+2048MC条件活动，110592是名义分母；缺输入时不反推纯noise/1σ或重做同控制。100–1000GeV单μ不认证低能ν shower。
3. **系统与选择**：可与原incoming联结、尺度有依据的interaction/FSI/材料/输运/Calo/读出变体，以及原选择分母/接受度/背景；固定模型上完整风险/尾与迁移。旧模板/prior重权不是认证。
4. **完整确认范围**：未开发locked来源与谱系及source/refit/offset估计/研究选择/真实系统依据。500incoming条件区间固定本模型/offset/来源，开发test反复研究、cal_post又拟offset，不当新blind或全流程覆盖。

原政策：pz0>50GeV、一次方动量仅pz0、允许原px/py/q/p/弯折；raw11/status/typed NaN和合法signed负值/Calo缺项；保留46575/11612/13189、17657隔离、全部1016K、missing21/6/5和全部缺源view。几何边不是ID/ghost；原两低能/传统RMSE上95≤1.05、all/direct≤1.01、其余五层/direct≤1.03，八层总/正/负tail50差相对direct上95≤+2pp不变。

先按完成审计核实际新输入/明确新规划，能推进才另冻一次完整比较/资源/停止，不能把重复状态或改写计划当进展。整体目标未达，不能标complete。所有事件/数值在batch，GPU适用则实测；独立CPU任务合理多核、内线程1，spool统一~/condor/nu_muAnalysis/。`condor_submit -append 'stage108_mode = ...'`并核Args/TransferInput，勿普通宏被默认覆盖。计实际/保守预留资源，不加嵌套时间；紧凑去重，先中文报告再本地Conventional Commit，无push。历史仅追加，以下Stage54后缀逐字保留、五资产不动，实际状态以Stage85为准，不自动重做noise支线。

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
