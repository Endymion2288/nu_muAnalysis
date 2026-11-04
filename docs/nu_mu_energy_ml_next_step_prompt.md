# 下一轮执行 Prompt：stage91 批量准确score loss与执行成本认证，0fit

先读`AGENTS.md`、路线§72、信息预算§52、[stage90报告](../workbook/2026-11-04_stage90_differentiable-likelihood-gradients.md)、[完整数值证据](../workbook/stage90_energy_ml/audit_summary.json)、[梯度汇总](../workbook/stage90_energy_ml/parameter_summary.tsv)、[实测速率](../workbook/stage90_energy_ml/benchmark.json)与[后续合同](../workbook/stage90_energy_ml/followup_input_request.json)。**唯一任务：同一准确score likelihood的批量CPU/GPU实现、数值保真与训练执行成本认证，0能量fit/校准优化/网络forward/新test评价/ROOT/生成。**

## 1. 已测证据和范围

stage90固定40train＋512cal的值/9384导数全部独立认证，最大值差1.776357e−15、梯度差7.962786e−11；GH32349事例/2414坐标失败，旧autograd自身与numpy差分闭合，近似积分梯度偏差是已确认程序因素。train上尾head监督差可与总loss导数同量级，但没量完整网络权重/150epochs轨迹或能量因果份额。cal512有限子集导数非0不证明全cal未达最优。

现有CPUfloat64 scalar score VJP每例约.016753099CPU秒，原46575×150仅密度外推117041.335秒（非实测训练）；不能直接复用旧预算启动fit。先做批量可执行loss，再另冻单次原模型fit。继续既有部署，不把数值认证当低能恢复/response闭合/新blind确认，无新样本前置。

## 2. 输入与单一实现

- `ntuples/energy_ml_stage90/{input,audit_values}.npz`和`workbook/stage90_energy_ml/audit_gradients.tsv/protocol.json`；原固定552身份、角色、head、权重、truth/pz、独立参考/参考不确定度均保留。train用b0/T1、cal用原b/T；raw training-prior marginal，loss−joint−.25marginal，不加nominal prior到优化目标。无需重复9384差分或打开test。
- 拟议**一种**分段Gauss–Legendre32张量score积分，原standardized-s响应split/尾界与物理模型保持；先小QA再冻结最终实现，不做GH阶数/节点/架构/先验网格。积分内解析score支持head15及b/T，不能只因autograd能跑就认证。移动分点是数值工具，一阶梯度处理需与保存独立参考闭合。
- 检查原float32网络head到float64积分、再传回float32 head梯度的桥接；本阶段仅叶张量/VJP，不运行网络/optimizer。支持非均匀上游权重、共享b/T及批量padding/mask，避免漏成分/错误归一化。CPU/GPU（实际可用才报告）值/导数均需验证，不伪称当前scalar接口支持CUDA/高阶梯度。

## 3. QA、预算、性能与验收

≤40固定cal实际包身份/单位/值/VJP与实测成本QA，随后冻结单一实现与容差：log-density绝对误差≤1e−6，梯度|差|＋stage90参考不确定度≤1e−4＋1e−3|参考|；全552保留，无容易子集/困难cut/事后降精度。若单一实现不能通过，交具体失败/最小改进，不自动扫阶或训练。

固定batch256/1024，测CPU与可用GPU的完整node构造/传输/同步/forward＋backward及peak内存，用确定重复计时，不挑物理赢家；包括float32/64桥接误差，输出真正可训练的资源预测与范围。QA后建议≤1Condor/≤2CPU6GB、可用时1GPU、MaxRuntime与阶段CPU1800秒、紧凑20MB；GPU真实准入/成本目前未测，按QA确认资源，不临时无限扩大。全数组与吞吐批任务通过Condor；不得保存逐节点大网格/重复head模型。

交付数值全通过且实测较scalar明显加速的可复用loss或明确缺口；随后提出**一次原posterior固定seed/150epochs＋原cal一次b/T优化**的独立合同/执行预算，同split direct/bounded旧预测复用，不重训基线、不换feature/prior/风险门槛。stage91本身0fit，不提前执行该合同或自动进入stage92。最终head点认证仍不保证所有训练中间head，后续训练需要明确数值失败策略和预算，不能静默降级GH32。

## 4. 阶段交付

中文stage91 workbook记录实际数值/全部失败、真实CPU/GPU/RSS/吞吐与计量范围、输入产物/下一单次fit验收；本地Conventional Commit，不push。原pz0-only一次方动量、允许px/py/q/p/弯折、raw11/typed NaN/合法负raw/Calo缺项、pz>50GeV/困难侧与已交付1016K保持，旧K生产时限不恢复。原stage54五项只读，以下后缀逐字保留。

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
