# Stage99：低 pz 能量歧义、保持点输出的概率校准与可见活动测量

日期：2026-11-04。起点 `817a1c0`；执行修订路线§80、信息计划§60和 stage98 研究复盘。A 的保存输出诊断与单参数概率产品完成；B 的完整固定队列 collection 测量完成，真实原生关联未交付。两格 classifier 各实际拟合一次，但 A 在保存接口报错后丢失预测，**配对信息增量未测量**。本报告保留这一程序失败，不把 B 单格成绩当作新增信息收益。

## 1. 本阶段回答了什么

1. **既有读出已经提供较强的低 pz H/L 排序；误判工作点的稳定性仍不足。** 在观测 50<pz0<100 GeV、共同 pz 支持标准化后，开发 test 的 direct/E94/stage92 AUC 为 0.975092/0.976727/0.973852，pz-only 为 0.519382。E94 使用 cal_select 冻结的名义 2% 低能误判阈值时，test 高能识别 91.7257%，实际低能误判 4.7543% [1.1219,10.1588]%。良好排序不等于严格低误判认证，更不等于连续能量重建通过。
2. **最低能的过大修正已被精确量化。** E94 在真 E=50–100 GeV 的修正平方项 0.050087735，交叉项 +0.004886017，合计增加平方 log 风险 0.054973752；在同低 pz 真 E≥200 GeV 中，相应为 2.644748833−5.758088969=−3.113340137。它描述同一修正在两类事件中的风险权衡，不是因果归因或 Bayes 信息界。
3. **一个保持点输出的尺度参数改善了概率产品。** 原 cal_post 一次有界优化得到 T=1.08691603355，旧 b=0.0211537082794 固定；test NLL −0.107503598→−0.120703623，配对条件差区间 [−0.015639933,−0.010692396]。68/90% coverage 62.602337%/86.253883%→67.110928%/89.394777%。仍有 X 条件失配，点能量和原最终门槛完全没有改善。
4. **可测的 collection 活动已经交付，真实引用仍有生产链缺口。** 原 2048 incoming/24 source 全保留，1923 可读、125 缺源；没有强配 hitSet/数组、把几何弦线当拟合轨迹或把未归属认作 noise。B classifier 单格可测，但由于 A 输出丢失，不能决定是否值得扩完整角色或做新增活动的能量消融。

## 2. 输入、固定选择和预注册

完整兼容池及外层角色沿 stage87：89033 条兼容记录，train/cal/test=46575/11612/13189、唯一 incoming=37556/10811/12125，17657 隔离不变。同 incoming 的全部重建视图总权重为1；全部 1016 新增 K、missing 21/6/5、困难侧和高端保留。cal_select/post=5443/5746，423 退出 select 仍参与完整 cal 报告。

一次方动量仍仅 pz0，允许原 px/py、q/p 和弯折；pz0>50 GeV 主选择、raw11/status、typed NaN、合法负 raw、charge/module_eta 的合法 −1 和 Calo 缺项不改。没有增加 p0/p1/pz1、旧禁用动量比、拟合 scintillator charge 回退或 truth 输入。

A 输入：

- `ntuples/energy_ml_stage94/{evaluation_input,cal_partition}.npz`；`ml/artifacts/stage94/{point_predictions,MDN_heads}.npz`；原 `workbook/stage94_energy_ml/offsets.tsv`。
- `ml/artifacts/stage87/predictions.npz` 中同 split direct/bounded/traditional 控制。
- `ntuples/energy_ml_stage92/predictions_{cal,test}.npz` 中真正保存的 `accurate_F`、准确 quantile 和数值认证标志；原 `workbook/stage87_energy_ml/prior.json`。

B 输入：原 `ntuples/energy_ml_stage95/cohort.json`、events/candidates 表、24 个明确 PHYS 来源和原 62 列缓存。固定队列一 incoming 一视图、仅 train/cal；不是自然 flux，也没有 test native 载荷。source/X/status 配额选择沿原队列，不按真 E/y/误差或新活动成败重选。

[冻结协议](stage99_energy_ml/protocol.json)、[collection 定义](stage99_energy_ml/activity_contract.json)在新结果前写入。所有计算、事件读取、数值 QA 和画图均在 HTCondor 节点完成；当前终端只做源码、文档、metadata、打包及结果小表读取，没有恢复 CERN 栈或本地复现事件。无新能量网络、网络 forward、后验数值积分、生成或重建；不使用 GPU 做稀疏 I/O。

## 3. A：共同 pz 支持的决策诊断

### 3.1 分数与标准化

固定 L=真 50≤E<100 GeV、H=真 E≥200 GeV；中间 100–200 GeV 单列，完整连续风险不删除。观测域严格 50<pz0<100 GeV。pz-only 用 pz0 排序；direct 用原保存的校准点 logE 排序；两个概率分数用 q=P(H)/(P(L)+P(H))，分母为0时未定义。

Stage92 `accurate_F` 的10列对应 `[0,50,100,200,400,800,1600,3200,6400,∞] GeV` 上的 raw CDF。直接取相邻差，再乘原固定 nominal prior ratio，与其原 `Reference.summary()` 同口径；L 为第1质量箱、H 为第3箱及以上之和。**不是重新积分，也没有把 raw training-prior CDF 误当 nominal posterior。** 两角色所有 numerical_certified 通过。

pz 格在 QA 前固定为 [50,60,70,80,90,100] GeV，参考质量只由 train/cal 的 X 与 incoming 权重得到：

|pz 格 GeV|固定参考质量|
|---|---:|
|50–60|0.180270199|
|60–70|0.188244602|
|70–80|0.203734180|
|80–90|0.213539948|
|90–100|0.214211070|

只在 cal_select 和被评价角色都同时有 L/H 的格报告共同支持，空格不补；本次五格均共有，保留参考质量为1。每类在各格内按原权重、格间按同一固定 X 质量标准化。test 域共659记录：L183、H297、中间179；H 权重和282.583333，不能混成297个全权重。逐格支持见 [pz_support.tsv](stage99_energy_ml/pz_support.tsv)，逐格 ROC/区间见 `ROC_within_pz_CI.tsv`。

500 次 component 内 incoming 重抽样，角色全体共同视图一起移动；固定模型、T、阈值和参考格，不重拟合或从 test 选阈值。此条件区间不覆盖 source、parent、重训、校准参数估计、响应及研究选择。cal 已用于选模和 offset，test 是反复研究的开发池；source95、独立确认和总体 NP 保证均未测量。

### 3.2 排序结果与实际工作点

下表 pAUC 是 FPR∈[0,0.1] 的面积除以0.1，并非全 ROC AUC。

|test 固定分数|共同支持 AUC [条件95%]|归一 pAUC [条件95%]|
|---|---:|---:|
|pz-only|0.519382 [0.509224,0.529927]|0.126835 [0.096172,0.169848]|
|direct 保存点|0.975092 [0.961382,0.987456]|0.900020 [0.860358,0.939149]|
|E94 H/L|0.976727 [0.963628,0.987887]|0.899069 [0.855216,0.941189]|
|stage92 保存质量|0.973852 [0.959901,0.985586]|0.874767 [0.808484,0.931942]|

每个分数的 2/5/10% 阈值只由 cal_select 定义一次：严格 score>t，选择满足标准化经验 L-FPR≤α 的最低已观测 L 分数，不拆 ties。cal_select 低能支持仅85；cal_post 97，不能 bootstrap 成149/299独立校准事例。

|分数|名义 L-FPR|test 实际 L-FPR %|test H 识别 %|
|---|---:|---:|---:|
|pz-only|2%|0.000000|2.904557|
|pz-only|5%|0.000000|5.990649|
|pz-only|10%|2.856148|13.252041|
|direct|2%|3.150588 [0.936154,5.717392]|91.302361 [87.957076,94.311516]|
|direct|5%|9.273959 [4.452414,14.461648]|94.764046 [91.859892,97.419468]|
|direct|10%|15.584594 [9.607795,22.155379]|96.154148 [93.515095,98.349118]|
|E94|2%|4.754309 [1.121885,10.158808]|91.725663 [88.527104,95.006203]|
|E94|5%|9.451037 [5.042598,15.922870]|93.838109 [90.821442,96.500540]|
|E94|10%|19.030327 [12.478623,26.827675]|96.148289 [93.631777,98.311295]|
|stage92|2%|3.862623 [0.887417,8.250711]|89.928997 [86.151098,93.323953]|
|stage92|5%|8.323219 [3.619747,13.582860]|92.305314 [89.031048,95.155793]|
|stage92|10%|9.809240 [4.996604,15.549810]|94.758186 [91.996678,97.374002]|

E94 名义2%阈值 q=0.608844825；test 原始计数为6/183个 L 误判、273/297个 H 识别，标准化率与原始比例不同。完整冻结阈值、原始计数和区间见 [working_points.tsv](stage99_energy_ml/working_points.tsv)。pz-only 零误判的条件 bootstrap 区间退化为[0,0]，**不能当总体零误判保证**。两格 BDT 的比较区间重叠，不能据此选“赢家”。

各阈值上下区域仍只评价原点输出，不部署新 gate；完整中间能量支持、实际连续风险及区间见 `working_point_energy_risks.tsv`。原全部层的 log-RMSE/正负总尾在 [point_risks.tsv](stage99_energy_ml/point_risks.tsv)。这些分类工作点不等于原 RMSE 或 tail≤+2pp 门槛。

### 3.3 精确点损失分解

m=ln(pz0/0.8)，c=保存点 logE−m，e0=m−ln(Etrue)，逐事件核 `(预测−真值)²−e0²=c²+2e0c`。无量纲平方 log 风险：

|test 层/模型|E[c²]|2E[e0c]|风险增量|
|---|---:|---:|---:|
|E50–100/direct|0.054455331|+0.004215254|+0.058670585|
|E50–100/E94|0.050087735|+0.004886017|+0.054973752|
|E50–100/stage92|0.025589856|−0.019373642|+0.006216214|
|低 pz 真高 E/E94|2.644748833|−5.758088969|−3.113340137|
|全体/direct|0.218034479|−0.445843931|−0.227809452|
|全体/E94|0.225013156|−0.451465074|−0.226451918|

E94 最低能风险增量条件95% [0.034975649,0.082281951]；stage92 [−0.004304841,0.021241365]。全部原层及其他控制见 [loss_decomposition.tsv](stage99_energy_ml/loss_decomposition.tsv)。逐例最大恒等式残差1.421085472e−14；交叉项带符号，不把 c² 当唯一物理原因，也不从此分解推导信息下界。

## 4. A：唯一尺度校准的概率产品

仅变换 stage94 E 的三 seed、九个 Normal 分量：

`μ′k=mE+b+T(μk−mE)`，`σ′k=Tσk`，混合权重不变。

T∈[0.5,3]、从1单次 L-BFGS-B；原 cal_post 5746条、权重5539，weighted NLL。4 iter/12 eval 成功，非边界，cal_post NLL −0.173945459→−0.183550272；没有重启、扫描、局部温度或新 offset。点输出继续返回原保存的 float32 解码点加旧 b 的完全相同数组。float64 重新解码均值与保存点最大差1.380003567e−6，不能为消除此舍入差改点；解析均值变换残差3.056582765e−15。

|角色/概率量|之前|之后|
|---|---:|---:|
|全 cal NLL|−0.155169210|−0.165976198|
|全 cal 68% coverage %|62.377054|66.995807|
|全 cal 90% coverage %|87.078747|90.434897|
|全 cal mean PIT|0.477608202|0.485487375|
|test NLL|−0.107503598|−0.120703623|
|test 68% coverage %|62.602337|67.110928 [66.214213,67.814753]|
|test 90% coverage %|86.253883|89.394777 [88.835928,89.861151]|
|test mean PIT|0.491100702|0.497919730 [0.492919214,0.503147610]|
|test 68%平均 logE 宽度|0.433694182|0.471389160|
|test 90%平均 logE 宽度|0.754108721|0.819652860|

解析 CDF/密度/quantile，不做旧后验积分；最大 quantile CDF 残差≤5.884182031e−15。十箱 PIT 及 stage94 原 X_pz/status/calo/activity 分组完整报告于 [probability.tsv](stage99_energy_ml/probability.tsv)、[PIT.tsv](stage99_energy_ml/PIT.tsv)。总体改善不等于所有条件校准通过：test X_pz100–200 的 mean PIT=0.483144030 [0.469218582,0.497510976]，X_activity0=0.483519906 [0.474395867,0.493038546]仍排除0.5；完整 cal mean PIT 区间仍排除0.5。仅均值含0.5也不证明 PIT 均匀。真 E/y 选组只描述，不强求后验在这些组内 PIT 均匀。

最低能/全体/低 pz 真高 E 的点 log-RMSE 仍为0.276027/0.289843/0.671125；传统最低能0.145661、direct全体0.287491。原8层点风险与三向尾门槛不变，不晋升能量模型。本产品可复用 `ml/energy_probability_scale.py` 与 `calibration.json`。stage94 point-best epochs65/90/65、记录的 NLL-best50/25/35只引用曲线；未保存早期权重的 test 性能未测量，本轮没有重训。

## 5. B：原生生产链与实际 collection 测量

### 5.1 没有把“同名官方 REC”当作原生联结

逐一匹配22个现存 PHYS 到 `merge_manifest.tsv`、对应22份实际 worker 日志及22份官方 reco 日志。原输出 worker 是 d32b0ff3、Athena24.0.41：RDO→scratch REC→ntuple，**只发布 PHYS，退出清理 scratch**。`faser_ntuple_maker.py@d32b0ff3`在 ntuple 阶段运行 MergeTrackCfg，临时构造 CKFTrackCollectionMergeWithoutIFT；所以“REC 没有 merge branch”本身不能单独证明 track 不对应。

已知官方同 basename REC 存在，实际日志是6d6ab70b/Calypso22.0.49，schema 有 forward/backwardWithoutIFT、clusters/SP/RDO 等；没有同一原重建/筛选/index/TSOS闭合。不能把不同生产的轨迹按 run/event、猜 merge entry 比例或数组位置接到原 PHYS。没有重建补源、递归 EOS 扫描、读取其 native event payload 或重新运行 merge/拟合。详细路径和实际日志片段在 [native_provenance.json](stage99_energy_ml/native_provenance.json)，schema 在 `native_entry_QA.json`。

本阶段真实 track→measurement ID、SP constituent cluster 引用、关联唯一 cluster/SP、按真实ID排除后的活动、actual covariance/单位、active-strip/readout 分母均为**未测量**；不是0活动。stage95 hitSet非ID、52例不等长及单位传播 covariance 的结论保持。

### 5.2 QA 与冻结的可行替代

原 flagged 40 QA 身份覆盖24source，仅按来源/X/status；37 PHYS可读、3来自已删除源。检查了原精确 input_entry 内 run/event、leading index=最大pz0、原保存 pz 与候选数、SP scalar/vector长度，全部可读者通过。QA只计算这40个身份的摘要；为复用 basket，源内读取其 min/max entry span，额外跨度条目不作测量/选样，实际请求137508965bytes明确计入成本。没有以“40”假称只传输了40个事件的字节。

冻结一族42维 **collection 几何摘要**：每站 SP entries；站1–3的9面 entries、距原 leading 端点弦线>10mm/>50mm计数及RMS半径；可见部分的站间计数差和首个有>10mm活动的面。station中心 [−1860.15,47.4,1237.4,2427.4]mm、layer偏移[−31.5,0,31.5]mm、z支持10mm沿已有几何配置；不按新结果选尺度。

reference 是原保存 x0/y0/z0→x1/y1/z1 的几何弦线，只在端点跨度内及10mm支持使用。**不是弯曲拟合轨迹、pull或“被缪子关联/未关联”的定义。** 端面覆盖不足时各面值/掩码保留；纵向差和first-plane只描述被弦线支持的可见部分，不能解释为全站淋浴增长或真实粒子起点。SP entries 不等于唯一cluster/粒子；坐标重复也没有当成共享ID。几何支持不等于有效通道响应，缺真实读出分母无法报告每active-channel占据。

完整2048队列结果：1923ok，125 source_unavailable，0实际 join失败、0可读空SP集合；单轨迹1770、多轨迹153。原 missing源分别是70:0的28个π和82:2的97个K；全部保留原62摘要和 availability。按来源/component/原角色/状态/pz的分母在 [B_availability_strata.tsv](stage99_energy_ml/B_availability_strata.tsv)。

|分层|原队列 N|collection可读|
|---|---:|---:|
|train|1513|1388|
|cal|535|535|
|π|716|688|
|K|682|585|
|charm|650|650|
|pz50–100 GeV|284|276|
|其他状态|395|359|

|已测 collection 量|有限支持 N|均值|中位数|p95|
|---|---:|---:|---:|---:|
|站0 SP entries|1923|275.511700|20|1500.3|
|站1 SP entries|1923|14.520021|4|45|
|站2 SP entries|1923|6.017161|3|16|
|站3 SP entries|1923|6.934997|3|11|
|站1面0，弦线外10mm entries|1882|3.690755|0|12.95|
|站1面0，RMS半径 mm|1825|32.765751|1.270315|110.404490|

p95为经验分位插值，可为非整数。站0高活动与 downstream 不同；这不是 noise 分解、强子标签、能量计量或同真实data的响应闭合。完整紧凑值/掩码及单位在 `ntuples/energy_ml_stage99/B_collection_features.tsv`、[B_activity_summary.tsv](stage99_energy_ml/B_activity_summary.tsv)。没有保存逐hit点云、原生文件或xAOD副本。

### 5.3 两次 classifier fit 与程序失败的边界

预注册 depth2、100树、eta0.05、min_child_weight10、lambda10、hist、seed2026110499、单线程，无cal调参/earlystop/补seed。A=原62值/缺失mask＋共同status/availability；B=同A＋42维collection族及mask。角色固定、每incoming一视图；只有观测50<pz0<100且真L/H进入诊断训练/评价。全队列仍在可用性和活动报告。

类别支持满足事前每角色每类≥20条件：train L/H=65/82，cal=20/46。A在9667677完成一次fit和predict，但 XGBoost sklearn `save_model()` 因 `_estimator_type undefined` 报错；进程退出时尚未落盘预测，不能补造数值。错误和发生位置在 [B_failure.json](stage99_energy_ml/B_failure.json)。

修复使用 `get_booster().save_model()`，且先持久化预测，再做模型/报告保存。没有重复A、没有重新抽样或读取ROOT；9667683只执行剩余B一次fit，因此本阶段总共仍为两次classifier fit。B的66个cal预测（`ntuples/energy_ml_stage99/B_classifier_predictions.tsv`）与booster（`ml/artifacts/stage99/B_classifier_B.json`）保留，单格结果：log-score=0.346455633 [0.252028743,0.462819455]，Brier=0.101254665 [0.061707997,0.150646988]，AUC=0.929891304，归一pAUC=0.847826087。

B按train冻结的名义2%阈值，在cal识别H38/46=82.608696% [71.111111,92.944352]%，L误判0/20。0/20和[0,0]条件bootstrap不能认证2%总体误判；5%/10%工作点完整报告在 `B_classifier_ROC_working.tsv`。队列为配额pilot、cal仅4个L来源，不外推自然flux。**A数值、B−A配对差及信息增量均未测量**，这不是活动无效的物理负结果；不据B单格启动完整提取、强BDT能量消融或GNN。

## 6. 执行命令、验证、资源和产物

典型命令（所有数值运行均由worker在batch设置LCG109环境）：

```bash
condor_submit AnalysisZipFramework/submission/ml_stage99.sub
condor_submit AnalysisZipFramework/submission/ml_stage99.sub -append stage99_mode=nativeqa
condor_submit AnalysisZipFramework/submission/ml_stage99.sub -append stage99_mode=report -append '+MaxRuntime = 900'
condor_submit AnalysisZipFramework/submission/ml_stage99.sub -append stage99_mode=bqa
condor_submit AnalysisZipFramework/submission/ml_stage99.sub -append stage99_mode=breport
condor_submit AnalysisZipFramework/submission/ml_stage99.sub -append stage99_mode=bfinish
condor_submit AnalysisZipFramework/submission/ml_stage99.sub -append stage99_mode=validate -append '+MaxRuntime = 900'
```

打包/收集通过仓库Stage99脚本；worker命令为 `python -u ml/stage99_<mode>.py`，外层`/usr/bin/time -v`，XRootD只回传小表/模型/图。请求8CPU/8000MB，站点修改为8CPU/24000MB；内层线程1。B按源8进程，A解析分布4进程，最多2并发。GPU未用，本轮主要是保存输出统计和I/O，未声称GPU加速性能。

实际cluster9667673/74/75/76/77、9667683与9667684分别对应QA、native metadata QA、A、B QA、B提取+A失败、仅B收尾、独立复核。9667677 exit1，其余完成情况/CPU/wall/RSS见最终 [resources.json](stage99_energy_ml/resources.json)、每任务time文件及精简history；没有自动重试。一次事后hold命令到达时9667676已完成，返回not found，没有hold/remove/重跑任何任务。

已返回的实测外层：A 18.80CPU秒/16.63wall秒、peak425468KiB；B批量（含A失败）65.70CPU秒/22.74wall秒、peak450484KiB，平均2.889CPU而不是8核满载；仅B收尾3.95CPU秒/5.34wall秒。全单核对照加速**未测量**。B main Uproot请求627934214bytes，QA137508965bytes，另计schema请求；不是EOS物理网络流量。真实native事件payload为0，不把未测ROOT物理读取字段写成0。七任务外层已计CPU共136.27秒（A含QA/复核32.50、B103.77），ROOT接口请求共775439164bytes；本地metadata/打包未完全计时，嵌套timing不重复相加。总预算A900/B13500CPU秒、native实际读取10GB/紧凑20MB保持；最终已计账范围和不足见resources。

独立验证不调用优化器/训练：与旧stage94点风险/NLL闭合；逐例/汇总分解闭合；独立Normal密度检查；温度处解析NLL梯度、均值/方差T²缩放和保存点逐位不变；从B保存预测独立复核score/条件区间。独立600项旧输出/恒等式核对最大差1.776356839e−15，B单格6项score/区间闭合；温度处解析NLL梯度−7.806230954e−9，独立40例密度最大差4.718447855e−16，方差T²缩放残差3.885780586e−16。数值细节见 [validation.json](stage99_energy_ml/validation.json) 和 `independent_checks.tsv`，图见 [diagnostics.svg](stage99_energy_ml/diagnostics.svg)（另有PDF/PNG）。真实response、interaction/FSI/材料/Calo/接受度/背景、准确CRPS、source95及独立未开发确认仍未测量。

最终只保留紧凑表、冻结配置、一个B classifier、校准参数、图和审计；重复传输包/返回归档清理，不修改历史共享缓存或原Stage54五项及Prompt后缀。最终唯一保留字节按 [storage.json](stage99_energy_ml/storage.json) 实测，生成数据不入Git。事件小表迁移和数值验证后的产物路由变更不改变算法，七个返回包全部逐字收集核对后才删除，见source_validation/cleanup.json。

## 7. 结论和下一最小任务

继续既有能量部署，不宣称最低能恢复或最终联合通过。已有分数的强排序与阈值外移、尺度校准的概率改善共同支持：当前已有信息并非完全不可辨，概率尺度/严格低误判支持/连续修正风险需要分别处理。一个T已经测完，不续温度网格，不自动新能量网络或NLL checkpoint重训。

**下一Stage100仅补齐本次丢失的A classifier产物**：复用同一2048身份、原62缓存、冻结A定义/seed/100树配置和已保留B预测，只允许A一次fit；0B重训/ROOT/native读取/新T/能量fit/test风险。先≤40原身份QA、0optimizer核baseline定义与Booster保存接口，再在batch完成一个A和完整cal配对log-score/Brier/既定低误判诊断、500incoming条件区间。建议CPU≤300秒、≤1个2CPU/6GB任务、最终紧凑≤20MB；这是下一轮上限，尚未执行。

验收首先是预测/模型可靠持久化和配对算术闭合，不能再因保存接口丢结果；是否存在增量由实际配对证据判断，不预设方向。没有支持增量就停止这族collection工程扩展；若有支持，也须先说明它仅是几何collection摘要与有限cal证据，不能跳过真实原生产品/读出响应或直接承诺能量收益。真实引用的最小缺失产品为原生产的轨迹状态、merge原候选索引与measurement/SP组成引用和有效读出支持；同名官方REC不能替代。该输入与最终未开发确认仍需后续独立任务。
