# 下一轮执行 Prompt：Stage110 强BDT上的固定关系差检验

先读AGENTS.md、[Stage109研究复盘](../workbook/2026-11-05_stage109_research-after-relation-results.md)、路线§91、信息计划§71，以及Stage104/108报告。Stage104固定q动作、Stage108完整三格及计数遮挡已完成，不能因新研究请求重新训练它们。本轮只检验下述一个问题，不自动开展新模拟/response/GNN残差训练。

**在有实际环境的节点执行；当前本地终端不复现物理结果。** 0新网络/分类器/网络optimizer step/模型forward/checkpoint或head读取、0ROOT/SP/native/生成/重建/新offset/T/积分/GPU。不创建一串单独准入阶段：原缓存可用时，≤40cal算术QA后同一CPU任务直接交唯一α和完整预定风险。

## 1. 问题与输入

问题：保留原Stage87强BDT后，Stage108 A→B的已保存功能变化能否共同降低两低能风险，而不是要求一个完整GNN从头替代强BDT？差包含关系、标量重学习和优化，不能宣称纯几何信息或因果效应。它与专家组合有关；不同于Stage78旧U/F/μ的simplex，也不是重开Stage104固定q代价权重。

输入为：

- `ml/artifacts/stage108/predictions.npz`：按row保存全部71376 active行、`A_raw`、`B_raw`、`geometry_available`；读取schema参见`ml/stage108_train.py`的infer保存与`ml/stage108_report.py`联结。不得从C/各cal版本选更有利方向。
- `ml/artifacts/stage87/predictions.npz`：强`direct_cal`及身份；冻结原offset，沿Stage108 reporter读取，不直接运行要求rich旧格式的Stage87 report。
- `ntuples/energy_ml_stage94/{evaluation_input,cal_partition}.npz`、`ntuples/energy_ml_stage87/split.npz`及已有身份/权重/原风险层定义；只复用标量/身份，勿调用会重训的main。

当前终端未核真实事件缓存可读性。执行节点若缺某点表，交准确路径/列/角色缺口，不用汇总制造逐事件差，也不为补缓存重新forward/提取。不要重新扫描EOS/旧REC。

保持89033兼容、17657隔离、46575/11612/13189原角色；incoming37556/10811/12125、全部1016K及missing21/6/5、geometry缺源345/343/356不变。cal_select5443/post5746、另423退出select仍完整cal；两个子角色按原subrole权重重归一，完整cal用原权重。所有high-y/未确认/高端/正负尾不删。

原pz0>50GeV，一次方动量pz0-only、允许原px/py/q/p/弯折；raw11/status/typed NaN/合法signed负读数及Calo缺项政策保持。真E/y/确认标签只能定义训练风险与评价层，不能作部署gate或输入。

## 2. 先冻结方向，恰一个解析α

所有值均为自然log(E/GeV)。令f0为原`direct_cal`，d=geometry_available×(`B_raw`−`A_raw`)，fα=f0+αd，α∈[0,1]。缺几何或α0显式复制旧f0，逐位保留；不裁d、不截输出、不强制E≥pz、不按truth能量或低pz切换。差保留raw定义，不减均值/拟新offset；不把(1,α,−α)组合称为有限专家凸平均。

在原cal_select一次求解，对每层按原权重得到C=mean[(f0−t)^2]、D=mean[(f0−t)d]、A=mean[d²]，R(α)=C+2αD+α²A。最小化两低能各自R/C的最大值；all R≤1.01²C，其余≥200/低pz/低pz真≥200/high-y/未确认五层R≤1.03²C。原f0是匹配开发保护参考，原最终两低能对传统目标保持。

保护不等式与[0,1]交成可行区间，α0必可行。用稳定二次根和退化线性/常数分支求边界；只检查可行端点、两目标二次函数的区间内顶点/交点，选目标最小、并列取较小α。不使用SLSQP、网格、多起点或事后允许负α/放宽bounds；这是有限一维问题的全局求解，不是所有reco策略的界。冻结数值容差：风险/可行性absolute1e−10、目标并列1e−12；若数值QA不通过先修算术，不把它写成物理阴性。

先保存方向、定义、角色和验收，再只用cal_select目标求α；保存α/三系数/可行区间/候选点及活跃约束后，才计算或查看test差分诊断与风险。共享压缩列可以载入内存，不为阻止列解压而复制/改写缓存；冻结前不得做test α扫描或风险诊断。Stage108 A/B的checkpoint曾用cal_select，f0及offset有历史cal用途；本次不能称重新获得整管道独立性。

## 3. QA、主比较和完整结果

≤40个固定cal身份含全部6个标量缺失及若干geometry_missing、select/post；不按新误差挑例。核row/key/role/weight联结、差的log单位和raw定义、全部几何缺源仍在、α0/缺几何逐位回f0。独立解析小算例覆盖交叉/切触/空额外改进/二次退化；直接展开小样本平方误差对照三系数公式，误差≤1e−10。不做模型接线/梯度QA或扩大计时网格。

主开发证据为cal_post上两低能`max(RMSE_fα/RMSE_f0)`，500次共同component内incoming抽样，逐draw先取最大再给条件95%区间，上端<1才支持共同低能增量。cal/cal_post seed2026110389、test2026110390，复用原draw定义但不保存draw副本。α0时主统计应精确1。cal_post不拟α/offset。

固定α后一次报告完整cal/cal_post/开发test八层：all、E50–100、E100–200、≥200、pz50–100、低pz真≥200、high-y、未确认；保留原高端/missing/geometry_missing/confirmed低transfer和X诊断层。交log-RMSE、bias/R68、总/正/负tail50、相对传统与direct的配对区间。各层列C/D/A及实际风险变化，区分共同改善、单侧收益和困难代价；不只交一张α选择表。

原最终不改：两低能/传统RMSE比上95≤1.05，all/direct≤1.01，其余五层/direct≤1.03；八层总/正/负tail50相对direct差上95≤+2pp。两低能改善不是最终联合通过；tail非二次量，不能由MSE约束推导已通过。无论结果有利或α为0，都完整交付，不依据test选raw/cal/C或重拟方向。

所有区间固定旧模型/来源/offset/本α与研究选择，不涵盖完整source/parent、refit/参数估计/研究选择和真实系统；旧cal/test已开发，不叫新blind，不自动晋升。

## 4. 资源、停止与交付

QA后最多1个4CPU/6000MB的CPU batch，最多4process、内线程1，共享只读数组和相同draw；CPU和wall各≤900秒，最终≤20MB是拟议上限，新实耗/收益/功效未测。spool统一`~/condor/nu_muAnalysis/stage110/`。没有ROOT/native I/O、GPU或模型副本，不为了提高核占用重复计算。没有真实缓存则只交缺口，不重建一串环境/前置阶段。

无增量就结束此固定方向，不扩α符号/局部系数、加入C或更多专家；单组增量如实记录，不称零进展；共同增量也只支持另冻一次强BDT+可训练残差比较，本轮不自动执行。阴性不能否定所有残差模型或认证信息界。

Stage109的E/transfer/z双侧独立支持、同末态真实读出变体和匹配初态generator研究是另一个生产/物理设计，不由本Prompt自动授权作业。最小外部输入是合法新source/parent及已知提议密度/选择产额，或有物理尺度的实际响应变体；缺输入不无目标扫描EOS。

先写中文Stage110 workbook，记录输入/原角色、实际α及三系数/约束、完整风险/条件区间/尾、程序与物理解释、真实CPU/wall/RSS/产物和未测量项，再与代码/配置/紧凑证据本地Conventional Commit。不push，不自动Stage111。路线只追加，Stage54后缀及原资产保持，实际状态以Stage85为准，不重做noise支线。

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
