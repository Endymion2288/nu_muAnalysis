# 下一轮执行 Prompt：stage84 完整 π＋K 支持的一次固定训练

先读AGENTS.md、[stage83报告](../workbook/2026-11-03_stage83_pi-support-delivery.md)、路线§64/信息预算§44和[实际输入合同](../workbook/stage83_energy_ml/followup_input_request.json)。本轮只对已交付的完整累计支持训练一个原F7政策三seed ensemble，**恰3能量fit、0pilot、无半量或其他规模臂**；不自动执行stage85。

## 1. 已测支持与未测结论

stage83全取事前冻结剩余20个合法train兼容π PHYS，200000完整输入→7354 selected→5934新唯一native-MeV incoming key，已对stage55全部95748曝光/66843unique＋stage70新28＋stage81新742＋stage82新1016及内部排重。新π两低E159/740、confirmed低transfer140/509、低pz真≥200为161、high-y167/未确认215，20源均覆盖两低E和歧义另一侧；≥3200新0，不能用总数掩盖高端。4Condor9663291一次exit0、remoteCPU227秒/wall合计308秒，非训练。

累计新支持7720唯一key/26来源=π6704＋K1016；两低E182/845，相对原767/3564各增23.728814%/23.709315%；低pz真≥200新增190/原1005。拟train49167=41447＋7720，cal8440/eval14057及原91/16/22组不变。低E足量功效、新能量表现尚未测量；π分布/来源与N、重训共同改变，不称纯N因果效应。完整谱系/未开发随机确认仍未交付。

stage82已经解除K旧3600秒时限并完整重建3源，1016 K已实际加入6fit；旧不生产/不重试K禁令由用户覆盖，不能恢复为审批阻碍。本轮保留全部K，不需要新重建。stage82 full主两低E/传统95上限2.464666/1.237750未恢复，all/F7 .997438 [.996118,.998709]小收益，原七层保护通过但低pz真高E尾代价仍保留；当前继续F7。

## 2. 输入 QA 与唯一训练

仅从stage70/81/82/83各support.npz的new_training_support合并，保持历史稳定归属，不从all selected再排不同新名单；7720互异且与stage55全部曝光无交集。全池62/readout/reference/typed NaN逐值回读，角色不扩至cal/eval/test，原缺失21/3/7＋11保护不变，新增缺失2保留。stage83小QA40身份selected0，没有非空逐值证据；旧非空实际包核查在提交后，正式7354非空/四模块formula已核验，不能追写为全部QA先齐。

原62 F7_pz0_raw_v1：一次方动量仅pz0，px/py、q/p和弯折允许；11signed raw_charge/VetoNu reduced，按typed域/status/dependency清理占位与无效值，合法signed负值保留；Calo缺模块totalNaN，不nansum。四期支持都已经参考WAVE-Calibration-01-LG，**不再做03→01缩放**。原pz>50 GeV/quality/geometry/truth fiducial及全部困难尾保持。0新ROOT/RDO/GENIE/G4/toy/响应/形状补充。

复用LCG109/XGBoost2.1.3。所有7720完整新支持＋原41447一起，以原max_depth5、eta.04、subsample.8、colsample1、min_child_weight20、reg_lambda10、hist、nthread1、400轮、seed2026110255/256/257，unit direct ln(E_true/GeV)训练，原xgb.train默认初始化，不覆盖base_score/boost_from_average。恰3fit、0pilot，不做新来源OOF，不称整管道留出。三seed log预测取均值后，仅在原cal拟一个unit global mean-log offset；预定主pooled_cal，raw并报，不挑seed/raw/cal/轮数。

主对照μ=pz0/.8及原F7缓存预测/offset，0F7新fit/推理。stage82 full既存缓存作为次机制对照，先核同一cal/eval行；报告pooled/stage82full的配对变化但不从中选赢家。保留训练内误差与留出误差的区别。

实际转移包先做cache-only零fit启动、参数/角色/key/缺失/reference与资源核查，不安装/编译；再冻结≤1Condor、每1CPU3000MB、wall≤1800秒、CPU累计≤1800秒、紧凑最终≤20MB。stage82六fit remote43CPU/wall51秒仅预算依据，本轮实际成本尚未测量。核实际ClassAds，flavor改写在预算内照实记；资源/程序失败不写成物理否证，不无限重试。

## 3. 原恢复/风险判据与诊断

原eval两低E相对传统log-RMSE比95%上限≤1.05；all/F7≤1.01，≥200/低pz/high-y/未确认≤1.03；两低E＋五保护层各总/正/负tail50增量95%上限≤2pp，保持原七层门槛。500次component分层保守来源paired固定预测区间（seed2026111384，cal+1），非重训/offset估计/新增抽样/谱系/响应/研究选择区间，非联合覆盖；cal/eval均已开发，不称独立确认。

raw/cal均报两低E、confirmed低transfer、低pz及同pz真≥200/high-y/未确认、全体/high-y/未确认/缺失、高端及原细能箱，logRMSE/bias/R68/双向tail50/100与损失贡献，来源和seed诊断，统计少或空层明确未测量。额外低pz真高E不能被总低pz通过掩盖。新增支持与原队列各层N/来源/唯一key/概率保留，不将source概率当flux权重。

模型逐位回读和所有主配对区间独立核验；完整报告成功/失败哪些门槛，失败继续F7并关闭本次固定完整支持实验，不续扫规模/来源/权重/seed/架构，不以失败证明缺数据无关或信息上限。若全部原门槛通过也仅为开发候选，另需未开发确认。

## 4. 交付

先中文stage84 workbook实际报告，再代码/协议/紧凑表图本地Conventional Commit，不push/外发，不动stage54已有五项工作。共享输入包和三seed模型只保留必要一份，删传输/重复预测/大特征缓存，原四期support保持；计实际CPU/wall/RSS/请求与物理EOS I/O，未测明确未测。本轮只有一个训练候选，不自动下阶段。

共同raw/stage54、完整Calo/脉冲条件、interaction/FSI/材料/接受度/背景和真正随机未开发确认义务保留；独立支持协议原文和stage54后缀保持。

以下stage54原后缀逐字保留，仅进入该支线时适用。

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
