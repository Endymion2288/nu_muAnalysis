# 下一轮执行 Prompt：stage92 一次原posterior准确loss重训、原cal校准与完整配对评价

先读`AGENTS.md`、路线§73、信息预算§53、[stage91报告](../workbook/2026-11-04_stage91_batched-likelihood-gpu.md)、[冻结数值实现](../ml/batched_posterior.py)、[完整552认证](../workbook/stage91_energy_ml/numerics.tsv)、[实际GPU吞吐](../workbook/stage91_energy_ml/throughput.tsv)、[下一合同](../workbook/stage91_energy_ml/followup_input_request.json)及stage87原protocol/normalization/prior/split、stage89完整准确评价代码与报告。**唯一任务：一次原posterior从头150epochs＋原完整cal单b/T准确优化，然后完整准确cal/test配对评价；不得重训direct/bounded/扫seed/架构/先验。** 无新样本/ROOT/生成/重建，无新blind或自动晋升。

## 1. 已测与未测

stage91 CPU/CUDA×batch256/1024各552/552事例、9384/9384坐标通过原1e−6值与1e−4＋1e−3梯度容差（含参考误差）；最大值2.835953694e−12、梯度7.324036932e−10。初始response-only20σ大区间失败后，冻结前按高斯单位尺度加整数分点，同GL32，原失败保留。H100 MIG2g.24gb真实batch1024密度/VJP167203.601325记录/秒，端到端较CPU2线程快28.795653倍；原6986250次仅密度外推41.782892秒，未含网络/joint/Adam/cal/CDF/排队，非完整训练或保证。

固定552最终head不能证明初始化/训练全轨迹或missing精度。GH32梯度偏差已识别，但对低能/困难侧的风险份额仍未测。保持既有部署，不因数值成功宣传物理收益。

## 2. 输入重建和唯一训练

读取原stage55+56、stage70/81/82/83现有支持缓存，在stage92自己的路径重建89033兼容池；不要直接调用会写stage87的prepare。与`ntuples/energy_ml_stage87/split.npz`逐项核对origin/row/group/key/role/weight，保留原46575train/11612cal/13189test与17657quarantine，missing21/6/5及K1016。不重新分割、不激活隔离样本、不修改旧模型或缓存。

同41特征、train-only median/IQR/NaN flags和wave/fit/Calo flags、85维输入，与原normalization逐项闭合；原合法负raw/typed NaN/缺项总NaN不变。原CPU float32 Network、原seed2026110387初始化/2×64SiLU、Adam lr.001默认/无weightdecay、clip10、batch1024/150epochs/原numpy permutation及incoming权重不变；从头初始化，不能warmstart旧posterior。原float32监督张量构造保持，再交float64积分。只将原marginal GH32替换成本轮冻结GL32 score，−joint−.25marginal、trainb0/T1与rawtrainingprior保持，不在优化中加nominal prior。

保留CPU1线程原网络/joint/optimizer，让GPU执行float64积分，自动传回float32 head梯度；先验证跨设备完整网络参数VJP，禁用AMP/TF32。无需让小MLP所有算子迁移GPU而另改初始化/optimizer路径；GPU积分已实测包括head输入/梯度返回开销。不声称新轨迹与旧训练逐bit相同。

## 3. 数值控制和原cal一次校准

QA固定40条＝全部21train missing＋6cal missing＋stage90固定train前13，去重后按原固定train顺序补足，不按风险挑样。初始化和每25epochs核同40保存head的值/15head导数与未改stage90自适应score，原1e−6及1e−4＋1e−3容差并报告参考误差；不是重复9384差分或认证所有中间head。所有batch必须密度/loss/梯度finite和tail准入；失败/预算耗尽保存row/head/日志并停，不删事件、不回退GH32、不挑中途checkpoint、不自动重训或加阶。

完整cal11612唯一L-BFGS-B，原初值(0,1)、b[-.2,.2]/T[.5,2]/maxiter100和其他原默认，incomingweighted准确raw NLL与解析b/T导数；记success/nit/nfev/终点梯度，禁止多起点/test校准。固定cal初始/终点独立数值QA，最终完整cal目标与Reference汇总一致到1e−6，否则不得声称校准完成。

## 4. 资源与完整评价

≤40实际包身份/单位/完整网络VJP/数值和成本QA，0optimizer后冻结：≤1GPU Condor，2CPU/6000MB/1兼容GPU（当前torch无sm70，禁V100）、wall5400秒/CPU7200秒；含重建/唯一训练/cal/head。训练后≤40固定cal准确Reference计时QA，再准入≤2CPU Condor（全cal/test各1，1CPU/3000MB/CPU与wall10800秒、并发≤2）。阶段QA/报告合计CPU≤32400秒/最终≤20000000bytes；是封顶不是实测保证，不无限延长。大批量必须Condor，交互只小QA。记录实际GPU/torch/CUDA、CPU/wall/RSS/torchallocated和计量边界；清理重复归档/重建feature大中间文件，保留紧凑head/必要失败与最终模型。

新模型完整cal11612/test13189主评价使用**未改stage88/89自适应Reference CDF/quantiles、newbT、原nominal prior/median**，不能用未修正GH32宣布收益。复用stage87同split direct/bounded/传统与stage89准确旧posterior，逐身份配对；原两低E/传统upper95≤1.05、all/direct≤1.01、≥200/低pz/低pz真高能/high-y/未确认≤1.03，七层及额外低pz真高能total/positive/negative tail50上差≤2pp全部保留。交log-RMSE/bias/R68/尾、68/90coverage/PIT十箱可靠性/NLL/宽度/ESS，含missing5/6及高端不省略；500component-incoming条件配对区间，source95不可估/3块角色/历史研究池test非新blind，不能自动晋升。

CRPS16×32旧近似只作命名诊断，准确CRPS未认证不冒称完成；预定prior stress如计算用相同准确CDF，不按test选prior。不自动追加模型或进入stage93。物理无收益也须交完整失败/可识别边界及明确下一任务。

## 5. 交付

中文stage92 workbook实际报告先行，再代码/配置/紧凑表图一起本地Conventional Commit，不push。原pz0-only一次方动量、允许px/py/q/p/弯折、raw11/typed NaN/合法负raw/Calo缺项、pz>50GeV/所有困难侧、1016K与解除旧K生产时限保持；原stage54五项只读，下面后缀逐字保留。

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
