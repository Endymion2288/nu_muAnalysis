# 下一轮执行 Prompt：stage65 高组件谱硬度自由后的局部可辨识性

先读AGENTS.md、[stage64实测](../workbook/2026-11-02_stage64_component-response-migration.md)、路线§45和信息预算§25；stage61为物理目标，stage63为模板/有限MC约定。stage64一个任务已完成，不重跑prepare/正式来源抽样、不覆盖原协议/结果；继续F7，不恢复J布局或能量模型搜索。

## 已知结果与唯一问题

stage63固定宽组件内部响应的低能比例闭合偏移并非全由模型/探测器引起。stage64固定trueE粗箱×pi/k/charm分解，eval M/S混合贡献−1.179538/−.651509pp，来源区间均负；S仍有条件贡献−.398815 [−.687241,−.116617]pp。条件差包含格内E谱、几何/y/interaction、train内F7模板乐观性，不能归为detector已测系统。

本次只回答：**允许高组件一个连续选中谱硬度方向后，低比例f还有多少局部可辨识性和误差代价，既有响应差还有多少未解释？** 偏移变小但自由度导致精度退化不能单独称成功；一个硬度方向也不保证代表全部E×π/K/charm混合或条件响应变化。

## 1. 输入、选择和冻结

1. 只用stage63 `ml/artifacts/stage63/observables.npz`、原`protocol_v2/templates/fits/support.json`和stage64 `protocol/operators/vectors/projection/summary`等紧凑产物。沿用M_mu/S_scalar各16常规格+专用无效格，0新F7推理、能量训练或新输入分箱；不重新开J、六自由箱、先验/网络/点估计器扫描。
2. 原train41447/cal8440/eval14057、91/16/22保守来源，pz>50、低/高truth定义、全部缺失/未确认/high-y/负修正/极端尾/溢出和保护不变。62输入、pz0-only线性动量、11raw/VetoNu reduced、signed/typed NaN政策沿用，不读locked-test/ROOT/RDO、不生产/补raw/恢复旧大文件/做SHA。
3. 在任何新Fisher/投影结果前冻结不可覆盖stage65协议：参数与唯一α=0研究点、导数、有限MC协方差、奇异/边界处理、来源重抽样、线性残差、资源及停止。先合成正交/共线和导数算例验证，不能按eval挑能量标度/硬度函数/先验或增加方向。

## 2. 一个高组件硬度方向与两个局部参数

低组件a保持原train条件响应。高组件对选中MC按 `(E/400 GeV)^α` 重权并在高组件内部归一：该参数描述selected-spectrum形状，不是部署事件truth输入，也不是未选中flux。只在α=0做局部研究，不扫描α范围或实际做非线性谱fit。

令u=log(E/400GeV)，高组件平均为ubar；在原统计格z上：

- `C_z = Σ_high,z (u−ubar)/MH`；
- `D_f=a−b`；`D_α=(1−f)*C`。

报告ΣC=0、与解析小步对称差分的数值对照，不把差分当新增物理形状扫描。中央分别用train f0参考和cal/eval名义f_true；f0/实际f标签不进入部署统计量。固定N_selected=1000。

V沿用stage63数据+低/高MC条件多项式切向协方差。给出已知响应与有限MC两种 `I=DᵀV⁺D`，比较固定α的一参数σ_f与自由α后的Schur补/二维逆矩阵σ_f，并转换σ_r/r；同时报告σ_α、相关系数、标准化Fisher的秩/条件性。原始矩阵条件数依赖参数尺度，不能代替标准化退化诊断。

零方向、共线/奇异或接近边界时明确无定义/失去精度，不能加小先验/岭或伪计数生成有限答案。分箱零MC时仍为切向局部近似，不宣称精确有限MC profile/coverage；α方向估计也有MC/来源误差，不能把中央导数当已知物理响应。

## 3. 来源稳定性与既有偏移

1. 对cal/eval的原始δq以及stage64混合/条件/未匹配分项，在各自f_true、α=0处，使用同一二维算子 `(DᵀV⁺D)⁺DᵀV⁺` 计算局部δf/δα和格残差。只有满秩时给常规二维误差解释；奇异方向的伪逆最小范数解不能冒充自由参数可辨识。
2. 并列固定α/自由α的δf与σ_f、相关性和未解释响应向量；保留一阶近似与stage63旧精确一参数profile的区别。既有低组件条件残差不能因总偏移被另一个参数抵消而消失。不截断超出物理域的线性外推，不把局部δθ叫新fit或无偏修正。
3. 冻结500次pi/k/charm分层来源抽样，train/cal/eval独立，M/S配对；同一train抽样用于两role。中央f0及各role f_true固定，每次重算train a/b、C/V/Fisher与经验响应。来源计数/零支持及退化重复完整保留，不只报有效重复的漂亮区间；未定义精度的次数/比例须与有限重复结果并列。区间条件于F7和分箱，不含重训、完整谱系/校准或detector/interaction系统，不是coverage toy。
4. 结果决定需要什么独立输入：硬度自由后若低比例退化，则给出所需独立谱硬度/响应信息，不用事后先验救结果；若局部精度尚可且偏移改善，也只支持下一笔诚实训练外模板/共同raw/响应确认，不自动部署或做正式flux。低能charm缺层、同pz高E/high-y/低可见/未确认与未开发来源仍需要覆盖，新事件数/功效未测量。

## 4. 预算、交付和停止

0能量训练/F7推理、0ROOT/RDO/新生产、0非线性谱profile或coverage toy。先pilot实测冻结，拟议≤1个Condor/1CPU/**3GB**、累计CPU≤10分钟、紧凑最终≤5MB；批量来源抽样经Condor，不静默追加预算。stage64提交2000MB但最终调度请求3000MB的偏差已记录，本轮需核最终ClassAd并按明确3GB预算执行，不反写旧协议。

验收是导数/归一/正交共线QA通过、全部角色/保护不变、矩阵/秩/误差代价/来源区间/线性残差透明；不预设必须获得更窄误差或成功推广。无法独立识别就如实报告所需物理约束，不加更多箱/参数、先验或toy调覆盖。记录wall/CPU/RSS/实际可计I/O；文件大小不等于EOS网络字节，不保存输入副本或逐事例能量网格。

先写stage65中文workbook，含实测数据/单位/输入/配置/命令、固定/自由硬度与来源/残差表图、局限、资源及下一单项输入/验收，再更新路线/信息预算/Prompt并本地Conventional Commit。不推送、不自动运行下一研究。保持F7，stage54既有工具/缓存和下方保留协议不变、不混入提交。

共同signed/rectified raw与stage54有效读出、诚实训练外响应、ν interaction/FSI/材料、接受度/背景和真正独立生产确认继续交付。stage62概率有用但低能点推广失败、stage63固定J布局阴性都保留；沿用stage61连续正向谱/有限MC方法文献入口。


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
