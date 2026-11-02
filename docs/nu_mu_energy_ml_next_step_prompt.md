# 下一轮执行 Prompt：stage64 宽组件内部谱与条件响应迁移分解

先读AGENTS.md、[stage63实测](../workbook/2026-11-02_stage63_joint-muon-ML-response.md)、路线§44和信息预算§24；stage61/62为方法背景。stage63两个Condor任务已经结束，v1数值故障已披露、v2完整结果通过独立数值验证；不重跑prepare/QA/正式profile、不覆盖历史协议。保留F7，停止当前二维布局扩展。

## 已知结果与唯一问题

选中N=1000，一个true50–200相对≥200强度参数：有限MC σ_r/r M/S/J=14.8224%/12.2557%/15.2184%，J/S=1.241734 [1.230569,1.252341]；J nominal/压力最坏2.042975/2.071419σ，四项验收失败。S的eval偏移也为−1.031638σ，不是已验证响应。J低能4328/4331集中第一M层四格，不能用连续J包含S的代数事实保证该离散布局胜出，亦不再扫格数/布局。

高组件eval/train mean(log true E)为6.642640/6.498560，差+.144080，M/S响应TV=.078489/.083202；低组件仅.016837/.021189。各role实际低比例已用于闭合，因而不能再把train f0与role f不同当作唯一原因。宽≥200组件的内部谱/生产混合变化、条件响应和train内F7模板乐观性尚未分离。

本次只回答：**固定原M/S表示和选择，宽组件的内部E谱/生产混合变化能解释多少响应迁移及既有低成分偏移，剩余条件响应差有多少可靠支持？** 不做新的低能点估计器或物理参数推广。残余条件响应包括格内谱、几何、interaction及有限支持，不自动等于detector失配或过拟合。

## 1. 输入与执行前冻结

1. 只读`ml/artifacts/stage63/observables.npz`、`workbook/stage63_energy_ml/{protocol_v2,templates,fits,support}.json`及必要历史说明。统计量仅固定M_mu/S_scalar，沿用stage63各16常规格和专用无效格；不增加格、改变边界或重推理/重训F7，不重开J推广、六自由箱或新谱profile/toy。
2. 保持train41447/91来源、cal8440/16、eval14057/22，低/高组件及全部缺失、未确认、high-y、负修正、离群/溢出和保护不变；不读ROOT/RDO/locked test、不生产、不恢复旧大文件或补raw。F7的62列、pz0-only线性动量、11raw/VetoNu reduced、合法signed及typed NaN策略继续有效。
3. 事前冻结不可覆盖stage64协议：粗trueE箱边界固定50/100/200/400/800/1600/3200/6400 GeV，隐含外侧保留分支；再与pi/k/charm生产组件交叉为k。truth只作研究分层，不成为部署统计量。不能按结果细化箱或匹配tracker/charge探针值。
4. 来源定义沿用已有保守group。用小合成计数验证分解、零支持、概率/权重和线性投影，再按实测冻结计算资源；不先看新分解结果挑参考顺序或混合网格。原结果/协议不覆盖。

## 2. 精确分解，保留非共同支持

分别对低/高truth组件、M/S及cal/eval相对train做：令w_T(k),R_T(z|k)为train层比例/条件响应，w_R,R_R为role对应量，原始总响应差ΔR=Σw_R R_R−Σw_T R_T。参考顺序固定为train。

在两侧均有事件的k上，逐z格分为：

- 混合项 `Σ_shared (w_R−w_T) R_T`；
- 条件项 `Σ_shared w_R (R_R−R_T)`；
- 非共同支持项为其余k上原始role响应减train响应（只使用各自实际有定义的一侧）。

三项必须逐格精确相加为原ΔR；报告有符号向量、每项TV/L1和未匹配概率质量、事件/来源数。不丢空层、不补造条件响应、不只展示共同支持的有利子集。由参照顺序定义的分解不是唯一因果分解；条件项仍含粗格内混合和有限来源噪声。

报告组件/trueE/生产层的实际N、来源、空格、权重/ESS；若另外展示标准化分布，权重定义必须来自冻结参考，保留原始全支持结果，不把重加权计数当新的独立multinomial MC或独立物理事件。不要为此新增有限MC profile似然。

## 3. 与既有物理偏移相联系

1. 在各role实际名义f_true处，固定stage63 train的a/b，v=a−b、q=f_true*a+(1−f_true)*b，以stage63有限MC协方差V和N=1000定义一次线性算子 `L(δq)=vᵀ V⁺ δq/(vᵀ V⁺v)`。该方向/截断沿用stage63信息公式，不按新结果换score。
2. 组合低/高组件的三项为δq=f_true*δR_low+(1−f_true)*δR_high；分别投影混合/条件/未匹配项，总和须等于总δq的线性投影。并列既有stage63 `f_hat−f_true`，保留线性化与精确profile偏移的差，不把一阶近似叫新fit或精确无偏修正。
3. 500次pi/k/charm分层保守来源重抽样，train与各role独立抽来源、M/S配对；名义f_true及中央线性算子固定，仅重算分解。每次重新保留零支持/未匹配项。区间条件于已训练F7、分箱和中央算子，不含重训、完整谱系或detector/interaction系统，不能当正式参数覆盖率。
4. 不要求混合项一定解释偏移，完整给出符号、大小、区间及相消；比例不稳定或分母接近零时不报漂亮百分比。若有方向稳定的条件差，再列最小共同raw/响应验证输入；若支持薄/混合未分清，列定向独立true低E及同pz高E/high-y/低可见/未确认样本所缺层、来源和预算依据。重抽样不是新事件。

## 4. 资源、验收和停止

0能量训练、0新F7推理、0ROOT/RDO/生产、0新谱profile或coverage toy。拟议≤1个Condor任务/1CPU/2GB、累计CPU≤10分钟、紧凑最终≤5MB，先pilot实测冻结；批量来源重抽样走Condor，不静默追加预算。资源计wall/CPU/RSS和实际可计I/O，文件大小不当EOS网络字节；无SHA、无全能量网格或输入副本。

验收：所有原始角色和支持计数精确保持，概率和非共同支持透明，逐格分解及线性投影守恒（冻结容差建议1e−12），区间/来源和程序校验完整。物理结论可以是混合主导、条件差存在或当前未定，不强行要求一个成功改善；残余不是detector因果证书。没有结果依据就不启动nuisance拟合、新生产、重新训练或更多二维布局。

写stage64中文workbook，包含实际输入/配置/命令、数值/单位/来源、原始与分解表图、偏移线性化局限、资源及具体下一单项的输入/验收；更新路线/信息预算/Prompt后本地Conventional Commit，不推送、不自动继续下一阶段。保留stage54工具/缓存，不混入提交。

共同signed/rectified raw、stage54占据、ν interaction/FSI/材料、接受度/背景和真正未开发生产确认继续交付。该诊断没有把选中条件成分参数变成未选中flux，也不改变stage62概率有价值但低能点推广失败的结论。


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
