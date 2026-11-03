# 下一轮执行 Prompt：stage71 固定F7补样增量对照

先读AGENTS.md、[stage70报告](../workbook/2026-11-03_stage70_alternative-support-pilot.md)、路线§51/信息预算§31、[增补合同](../ml/configs/alternative_support_augmentation.json)以及[标定闭合](../workbook/stage70_energy_ml/calibration_closure.json)。本阶段编号71，只一个固定增补候选，完成后停止；不自动连开stage72，不安装/重配本终端环境。

## 1. 唯一问题与已测支持

在相同F7特征/算法/超参数下，加入实际已交付π来源的28个新唯一key，能否改善原真实低E及完整能量风险？stage70预定π/K头测10784输入；仅π完整784输入、30选中，K触及3600s预算停止、完整支持未测。实际π去重后true50–100/100–200增量4/2，同低pz高E/high-y/未确认0/0/0。只有π增补，K完整支持未交付，不把QA K行加入；不自动重试K或扩源。不是新独立确认，也未测模型收益。保留F7作为现用参照。

## 2. 输入与校准必须先核实

- 新缓存`ntuples/energy_ml_stage70/support.npz`，只取`new_training_support=True`，与原audited_features.load的41447 nominal train_eligible行拼接，共41475。其余已知复用/内部重复保留证据但不训练，旧train/cal/eval41447/8440/14057及42缺失21/3/7＋11保护不改。
- 必须用缓存`x`（reference WAVE-Calibration-01-LG），不能用`x_produced`（原默认03-LG），也不能对已参考化x重复乘1.061711。读metadata的features/version、calibration_amendment与passed closure，独立验证四模块与总和/NaN传播及57列未变。标度差异源于实际payload，不按truth/残差再拟合；01相容性不等于真实响应认证。
- 同62输入：线性纵向/模长动量仅pz0，px/py、q/p、弯折允许，11raw/VetoNu reduced/typed invalid/status/dependency→NaN保留。p0/p1/pz1/ln比值不入模型，不fit补raw、不nansum补零、不删巨大动量/缺失/未确认/high-y/困难尾。MC原单位MeV/mm，部署读出GeV/既定单位；校准run/身份是预处理/审计信息，不作ML特征。
- 新身份必须与stage55全部已开发cache零精确incoming交集、内部唯一，保留canonical角色。π继承已暴露challenge，两个预定源parent/subfile/seed未证，实际训练支持只有π，源概率1/23、1/41不作物理flux权重；所有旧角色保护保持。不能称cal/eval为新确认。

## 3. 唯一训练及资源

严格复用ml/configs/audited_features.json的F7原XGBoost参数、400末轮、原三seed2026110255/56/57、直接平方logE回归，unit MC。一个增补候选共3正式fit，无额外C重训/seed或树数选择/early stop。存量F7原三seed平均＋原offset，以及传统pz0/.8预测为固定参照，不重新推理F7。收益包括样本组成/flux先验及重训，不能叫纯样本量效果；不追加matched-flux/residual/gate/MLP/权重变体。

模型保存后cal/eval推理；三seed raw log平均为ensemble，8440cal只拟合一个global mean log offset。预定增补_cal为主，raw并列，不在两者间选好值，无E分段校准或E≥pz硬边界。旧evaluation14057仅开发比较，不用其结果回改训练政策。

先做无fit的标签/身份/62列/缺失/Calo reference对齐和小内存/I/O QA，冻结具体实现后一次HTCondor；拟议≤1任务/1CPU/3000MB、累计CPU/wall≤900s、最终≤10MB，最多3fit。现成LCG/GCC15子进程，局部scratch、一次缓存、紧凑模型/预测/表图；不读新ROOT/RDO、不重建/生产、0谱profile/toy/SHA。新成本收益未测，QA后冻结，不自动扩预算。

## 4. 验收与物理解释

按原共同选择比较新增_cal/raw、固定F7和传统：两个trueE50–100/100–200、reco pz50–100/100–250、≥200、high-y/未确认/缺失、全E箱50/75/100/150/200/400/800/1600/3200/6400及更高空层。报告log-RMSE、bias/R68、上下tail50/100、损失归因，不删尾。缺支持或未测标未测量。

500次component分层保守来源配对固定预测bootstrap，原eval22组/14057例，记录valid/invalid重复；不含重训/offset重估/完整谱系/系统/研究选择误差，无独立确认/coverage认证。新增3seed平均不等同完整训练统计误差；训练内不是OOF，不给没有新fit的OOF。

门槛不变：两低E/传统log-RMSE的95%上限≤1.05，全体/F7≤1.01，≥200/低pz/high-y/未确认/F7≤1.03；原各组总体/双向tail50增量95%上限≤2pp。突破另外报告两低E/传统改善下限>0，不以一个箱/局部输出替代全部标准。继续检查程序原因与物理支持，不能将未知或少数离群当不可恢复证明。

模型回读预测逐位/行身份/所有缺失/校准协议/配对bootstrap独立复核；实际CPU、wall、RSS、吞吐和可计量I/O记录，不把逻辑file bytes当EOS总网络字节。合并删除重复transport/shards，不提交事件数组/ROOT。

## 5. 停止与交付

完成唯一3fit增补候选及报告即停止。失败保留F7，结束这组样本的方法变体，交已有generation_input_request中的具体新π/K parent/subfile/seed/共同raw所缺输入，不再改架构、权重或扩源。若全部门槛通过，仅冻结研究候选并给真正未开发随机来源/共同响应确认合同，不冒充已部署成功。

写中文stage71 workbook：目标、实际输入/选择/单位/详细结果/区间、程序与物理解释、执行命令/验证/资源/产物、下一任务的输入与验收。更新路线/信息预算/Prompt，本地Conventional Commit、不push。原stage54五项未跟踪工具/缓存和下方6714bytes协议逐字保留。

共同raw/stage54、interaction/FSI/材料、真实随机确认、接受度/背景仍须交付；本轮不启动谱联合表示/非线性谱研究或历史重建扫描。

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
