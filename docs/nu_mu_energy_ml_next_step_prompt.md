# 下一轮执行Prompt：stage76 固定条件分数密度的分段积分修复与唯一能量决策

先读AGENTS.md、[stage75报告](../workbook/2026-11-03_stage75_conditional-decision-numerical-qa.md)、路线§56/信息预算§36、[修复合同](../workbook/stage75_energy_ml/integration_repair_contract.json)、stage74模型/q与stage73原点风险标准。继续F7。stage74判别信息为正；stage75均匀257/513积分不收敛，0正式点风险结论。此次只修复同一科学映射的数值实现，不追加模型/估计器候选。

## 1. 输入与不可改变项

只用原stage55/56 audited_features同62、stage74八固定M/X模型及每实际train原q、stage75事前256数值身份、既有stage73/68/69/71/F7/传统固定参考。0classifier训练，不改q/seed/模型/温度/先验/决策或挑误差小的来源。原stage68 v2来源折＋train端exact incoming purge、41447/8440/14057与91/16/22保守来源、42缺失21/3/7＋11保护、12零q、所有困难/高y/未确认/巨大动量/负修正/双向尾保持。

一次方纵向/模长动量仅pz0，px/py、q/p和弯折保留；11signed raw/VetoNu reduced、typed/domain/status/dependency NaN、合法负值及缺一Calo使totalNaN不改。pz>50与其他cuts不变。不读新ROOT/RDO/π28/locked确认、不生产/K重试/扩run/谱toy/SHA/重缩放stage70参考化x/新F7推理。stage54五项工作树和下方支线保持。

## 2. 同一科学映射的确定性求积修复

仍是t∈[ln50,ln6400]、`r(t|X)∝q(t|Bpz)exp(s(t,X))`、唯一 `logEhat=∫t rdt`，不硬施Ehat≥pz。r只称归一分数密度，不称已校准真后验。q零区保持0，真值q0的density logscore未定义/−∞，点预测仍全评价，不能删例/floor或按真E回退。

读取已存模型序列化的query数值split（M feature1，X feature62），并计实际推理输入float32舍入。对条件float32(t)<cut，有效连续跳点是cut与其float32前驱的中点，tie为零测度；与原q边界合并，在每个非零长度区间选可核实的内点，score固定。每区间精确质量 `q exp(s) Δt`、一阶矩为该质量×区间中心；稳定logsumexp归一并求均值。不得在跳点之间假设线性树输出。结构库存给251–261段/模型，实际query成本/精度仍未测。

无更密均匀网格、q平滑/混合/伪计数、温度、mean/MLE/median/quantile/拼接/gate/分段校准选择；不根据RMSE挑积分定义。声明实际float32边界与序列化模型语义，不能只按JSON小数字符串当双精度真阈值。

## 3. 数值、部署与资源QA先于正式点风险

先冻结合同与预算。合成piecewise score/q、单/零支持箱、已知均值、极大logit/常数平移、split/tie/边界/NaN分支通过；独立序列化树遍历与XGBoost输出逐例核实，包含float32前驱/cut/后继代表。固定reco时若段内并非常数，交具体最小程序问题，不继续正式点风险。

使用stage75同256身份（每held64，final cal/eval各32），独立float64 logsumexp与显式分段积分log均值差≤1e−6、归一误差≤1e−12；另每held取这64排序等距8个，final cal/eval各4个，总≤32身份，核各段quarter/mid/three-quarter及独立树遍历。所有身份先定、不看真E残差。不要把257/513当精确参考或用密网格扫描替代结构验证。QA失败保留事实并交具体积分问题，0正式点结论。

query仅reco＋候选t，不读事件真标签选密度/模型。分块复用输入与模型，每chunk约化为均值/归一/首尾箱质量等小摘要，不留全量grid；实测wall/CPU/RSS、query吞吐/I/O。小资源pilot后冻结实际预算，实际4split包 --check-only（含worker预建目录、两输入维数与0fit）通过才提交，无部分/成功正式任务重跑。

## 4. 正式点风险与完整验收（仅QA通过）

原≤4Condor（每fold＋final）、1CPU/3000MB、CPU总≤3600s、wall/job≤1800s、worker1750s、紧凑最终≤20MB；核最终ClassAd和硬上限。0新训练。3OOF raw、41447各一次；final M/X完整train/cal/eval，各在原8440cal一个unit mean(logEtrue−logEhat) offset。预定主X_cal、raw及M并列，不挑赢家。

原两true低E对传统RMSE比来源95%上限≤1.05恢复、gain下限>0才超越；all/F7≤1.01，≥200/pz50–100/high-y/未确认/F7≤1.03；关键层总体及正负tail50增量上限≤2pp。不用弱M替代传统/F7门槛。OOF X/M、最终X/M、传统/F7与stage73/68/69/71固定参考全报，train内/OOF/cal/eval开发分开。

所有七真E非空箱、3.2–6.4TeV、≥6400空箱、≥200、pz50–100/100–250、high-y/未确认/缺失和12零q给N/来源/唯一incoming、logRMSE、mean/median bias、R68、tail50/100双向和尾损失。unit与固定七箱等权MSE开根macro并列。500次component分层保守来源配对固定预测bootstrap，seed2026111375（cal+1/OOF+2），记录有效/无效；模型/q/offset固定，排除重训、q/配对RNG、完整谱系、响应/研究选择误差。cal/eval已开发，非新盲测。

## 5. 分流与交付

QA通过且主X_cal原全门槛/OOF稳定才冻结研究候选，再安排共同响应/真正新来源随机确认；不得称完整校准后验。若信息正但点风险未恢复，结束这次固定决策预算，记录支持/边界/校准/双向代价，转真实新增歧义两侧支持，不自动temperature/q/架构轮换。数值仍失败只交具体程序问题。

先中文stage76 workbook，实测数值/单位、输入/身份/数值QA、完整点风险（未测标未测）、程序与物理解释、命令/资源/产物和唯一下一项；更新路线/信息预算/Prompt，报告＋代码/小表图本地Conventional Commit，不push，不自动执行下一阶段。原[真实π/K/共同响应请求](../workbook/stage74_energy_ml/followup_input_request.json)、raw/stage54、Calo、interaction/FSI/材料、接受度/背景与未开发确认继续并行，不外发消息、不把metadata当新N/功效，也不将新生成作为有限积分修复的无限前置。

下面stage54协议逐字保留，只有进入该支线时适用。

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
