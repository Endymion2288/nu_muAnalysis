# Stage111：重新研究低能瓶颈，冻结已有 PHYS 的选择与响应实验

日期：2026-11-05；起始 commit `1bb5c51`。用户明确回复“没有新输入，请重新研究并制定下一实验”，因此本阶段重新提出一个有界科学问题，覆盖 Stage110 的“没有默认下一阶段”交接安排。**本轮交研究及实验设计，不执行 Stage112。**

## 1. 阶段目标与判断

下一项优先实验是：**保持其余名义切选，在已有完整 PHYS 中测量加入 reco `pz0>50 GeV` 前后，两个低能箱的传统估计器误差、真实能量转移和纵向缪子响应如何改变。** 同时记录完整切选分母以及无轨迹、占位值、未知真值关联的去向。

这回答了此前没有共同分母的问题。Stage73 的误差分解已表明，已选中、普通且确认的低能事件也存在模型过修正；它同时明确没有测量选择前效率。不能把本实验包装成第一次误差分解，也不能预先宣布选择就是唯一原因。Stage110 的局部收益与共同检验失败都保留，不马上再扩大模型。

没有新样本不妨碍这项测量：已有的六个 PHYS 父文件包含未通过当前分析切选的记录。不过它们是**已保存的重建 PHYS 分母**，不是生成级、输运级或完整 incoming 的接受度分母；PHYS 上游已经丢掉的事件仍不可测。本研究不能认证 50 GeV 分析的背景或全探测效率。

## 2. 已有数据证据与替代方案

全部下列性能数值引用既有汇总，不是本轮重算。自然 log 能量误差和 RMSE 无量纲，能量和动量为 GeV。逐字段原值见 [55项证据](stage111_energy_ml/evidence.tsv)。

|Stage110，原开发 test|传统|强 direct_cal|固定关系差 transfer|
|---|---:|---:|---:|
|真 50–100 GeV|0.1456613861|0.2826443432|0.2749913538|
|真 100–200 GeV|0.2479369853|0.2463287668|0.2435570705|
|全体|见原表|0.2874912364|0.2880392409|
|50<pz0<100 且真 E≥200 GeV|见原表|0.6581773341|0.6626600327|

唯一系数 α=1。主 cal_post 两低能最坏 transfer/direct RMSE 比 **1.0012495421 [0.9887913304, 1.0271199078]**，没有支持共同改善。test 最低能比 **0.9729236065 [0.9482766174, 0.9956754337]** 有局部改善；第二低能 **0.9887479794 [0.9729721857, 1.0045604313]** 区间含 1。cal_post 全体比 **1.007421105 [1.003665651, 1.011620807]** 有条件退步。

最终两低能相对传统的比上95为 **2.2620717134 / 1.0593452131**；high-y 总/负 tail50 差相对 direct 上95为 **+2.9750302963 / +3.0137680644 pp**。负尾中央差 +1.287247 pp 的区间含0，不能说证明增加超过2 pp。原 joint=False、不晋升、固定方向结束。

当前 active 71376，train/cal/test=46575/11612/13189，最低能 select/post/test=85/97/183；这些量不是六个父文件的产额。原17657隔离、全部1016新增K及困难尾保留。本次不重分这些角色。

|可选方向|本轮取舍与依据|
|---|---|
|再训 BDT+可训练 GNN 残差|固定差阴性不否定它；但 Stage108 完整三格、Stage110 保留强基线的已有差都未共同恢复，先不投入新的 fit/seed 网格。|
|非线性专家门控或 group-risk/能量重权|Stage59、68、73、78、104 已做相关实验，均有局部收益与风险迁移；重新命名不构成新问题。|
|换 mode、flow 或新的表格架构|外部文献说明可选统计量与先验依赖，未证明本任务 RMSE 会改善。当前缺少区分这些建议的项目证据。|
|新增低能/双侧模拟或真实响应变体|仍是长期优先，但用户确认没有新输入；本轮不能把尚不存在的路径和系统幅度写成可执行输入。|
|已有 PHYS 的选择/响应共同分母|以前只对已选样本做机制分析；现有精确父文件可支持有界测量，能够检验传统低能优势的样本条件，并审查占位值通过切选的可能性。选此项。|

## 3. 论文研究及可行性边界

本次会话用标准库 urllib 访问原论文摘要/HTML及 JMLR 页面，并经 INSPIRE 核对 FASER 文章标题与 DOI。完整引文、用途、限制在 [literature.tsv](stage111_energy_ml/literature.tsv)，没有下载训练样本或模型。

1. [Gambhir、Nachman、Thaler，Bias and Priors in Machine Learning Calibrations for HEP](https://arxiv.org/abs/2205.05084)：普通 ML 标定也可能有先验依赖，支持检查训练谱与所报分层风险；不证明这里的唯一原因，也不保证 mode 最优。
2. [FASER，First Measurement of the Muon Neutrino Interaction Cross Section and Flux as a Function of Energy at the LHC](https://arxiv.org/html/2412.03186)，DOI `10.1103/PhysRevLett.134.211801`：论文明确高动量 μ 选择、响应矩阵及效率处理。其 >100 GeV 分析不能认证当前 >50 GeV 扩展，提示应明确选择分母。
3. [Sugiyama、Krauledat、Müller，Covariate Shift Adaptation by Importance Weighted Cross Validation](https://jmlr.org/papers/v8/sugiyama07a.html)：重权保证要求条件分布不变及支持。不能用权重恢复零接受度区域，也不能把响应改变自动当普通协变量漂移。
4. [Boost then Convolve](https://arxiv.org/abs/2101.08543) 与 [GrowNet](https://arxiv.org/abs/2002.07971)：保留强表格核心及训练当前残差有方法依据，但前者是节点图任务，后者需要重新训练残差并纠正；Stage110 固定 A→B 差不是它们的完整实现，论文也不是立即重训的项目证据。
5. [Parametrizing Detector Response with Neural Networks](https://arxiv.org/abs/1910.03773) 与 [Unifying Simulation and Inference with Normalizing Flows](https://arxiv.org/abs/2404.18992)：可研究响应统计量/条件生成及反演，但依赖目标与响应定义，不能从外部例子推出当前低能 RMSE 收益。

一个关键概率限制：若选择 S 是完整观测 X 的确定函数，在选中支持内有 `p(t|X,S=1)=p(t|X)`。选择前后边缘真值组成不同，**不证明固定完整 X 后的 Bayes 条件改变或增加观测信息**。当前模型的62列与完整切选变量并不完全相同，因此还须明确所说的 X；本实验不宣称信息下界或唯一因果归因。

## 4. 冻结 Stage112：输入、总体和主要比较

可执行合同见 [experiment_contract.json](stage111_energy_ml/experiment_contract.json)，确切路径见 [source_manifest.json](stage111_energy_ml/source_manifest.json)。它们在任何新 ROOT 内容读取、产额测量或效应估计前冻结。

### 4.1 六个精确来源

选择规则：只在 Stage105 固定 QA 来源 metadata 中，按 π/K/charm × 原 train/cal，取数值 `(origin,source_index)` 最小者。**不按可读性、能量、产额、误差或符号挑选，不替换失败来源。** 这是诊断便利样本，旧 QA 来源本身并非随机代表全池。

|成分|历史角色|source|group|本轮 stat 逻辑大小 / byte|
|---|---|---|---|---:|
|π|train|55:4|pi:00040-00049|28456305|
|π|cal|55:164|pi:00420-00429|29633994|
|K|train|55:84|k:00440-00449|47597205|
|K|cal|55:67|k:00220-00229|47550580|
|charm|train|55:116|charm:00030-00039|60966291|
|charm|cal|55:118|charm:00050-00059|61459327|

六文件均存在，合计 **275663702 byte**。这只是 metadata 逻辑大小，不是实际读取量。schema、完整父事件数、低能产额、选择效率、效应大小、功效、吞吐量、CPU/GPU/内存和物理网络 I/O 均**未测量**。没有因为 K 产额未知而删掉 K。

### 4.2 分母、角色和权重

先在完整 PHYS 报逐项 native MC cutflow、每个切选独立失败和未知计数，明确 `requires` 与 aux/reduced/fallback 分支；DATA/ASIMOV-only 切选不套给 MC。

- `G0`：所有实际名义 MC 切选，仅去掉 reconstructed `LeadTrack_pz0>50`。保留真值 CC/νμ/位置/半径和 **truth_pz_nu>50 GeV**，以及 fitted-charge、质量、几何等切选。因此 G0 不是“没有选择”的总体，也没有覆盖真 νpz≤50 GeV。
- `G+`：G0 中 pz0 有限且 >0、Eν 有限且 >0 的可定义传统误差总体。无效/非正动量不补0，在 G0 和完整 PHYS 的分母表中保留。
- `S50=G0 & pz0>50 GeV`；`S100=G0 & pz0>100 GeV` 只作历史阈值对照。没有阈值扫描，不据结果改变名义50 GeV选择。报告原生 S50 和可定义误差子集的关系。

父文件中的旧角色不代表每条 incoming 都有该角色。batch 只读取 Stage87 split 的身份白名单字段 `incoming,role,initial_role,origin,source,group,run,eventID`，不读预测/特征/损失。incoming 沿用原生 `(pdg,px,py,pz)` 的精确 MeV 键，不称其为独立生成历史。保持 test>cal>train；已知 test-key 在完整父 cutflow 中计数，在主要开发对比中隔离，不读取 test-only 父文件或 test 风险。无历史记录的父事件只标“diagnostic-only”，不自动成为训练数据。known-role 冲突/未知身份分别报告，不用 source 角色覆盖已有隔离。

每来源内，一个 eligible incoming 的全部父视图总权重1，权重在应用 G+/S50 前固定，**不在幸存者中重新分摊**。主要源标准化为六来源等权；它是事前定义的诊断总体，不是自然物理 flux。另报原始条数和 record-weighted 结果，不把便利来源的比例推广到完整样本。

### 4.3 主要端点和机制分解

选择本身已有一个无需模拟的运动学约束：S50 内 `e>ln[50/(0.8 Eν)]`。在响应 r 给定时，它还要求 `Eμ_vertex/Eν>50 exp(−r)/Eν`，所以真低能中 transfer 与响应会被共同条件化。这个界只提示为何应检查富集与交叉项，不给出实际分布、误差改善幅度或模型应该学到的修正；这些仍须实测。

固定传统估计器 `Ehat=pz0/0.8`，不拟合0.8或 offset。对真 Eν `[50,100)` 和 `[100,200)` GeV 分别计算：

`Δ_E = (1/6) Σ_source [mean_w(e² | S50∩G+,E) − mean_w(e² | G+,E)]`，`e=ln(pz0/(0.8 Eν))`。

这是两个并列、完整报告的主要描述端点，单位 log误差平方；**不择优挑一箱，也不以负值作为阶段成功条件**。每来源同时报两边 RMSE/bias/R68/正负与总 tail50、incoming/视图数、权重和、ESS。任何来源某一边无支持时该箱的六源主端点写“不可估计”，不丢该来源后重归一化；其余已定义的来源结果仍交付。

在唯一主 μ 有效且 Eμ_vertex>0 的同一子集上令 `r=ln(pz0/Eμ_vertex)`、`u=ln(Eμ_vertex/Eν)`、`c=ln(0.8)`，验证 `e=r+u−c`，逐一报 `〈r²〉+〈u²〉+c²+2〈ru〉−2c〈r〉−2c〈u〉` 及两选择间变化。signed 交叉项不能删。r 包含角度、材料损失、参考面差异及错误 leading，不称纯 tracker 分辨率；confirmed/unconfirmed 分开解释，未确认者仍在传统主风险。

辅助报 `y_lepton=1−Eμ_vertex/Eν` 的分布、`y<0.2` 份额、主μ可识别率/leading确认率，顶点 z/半径、pz、响应与失败原因。固定真E箱为50–100/100–200/200–400/400–800/800–1600/1600–3200/≥3200 GeV，reco正pz箱为(0,50]/(50,100]/(100,200]/>200 GeV，并保留原八层的严格边界定义、high-y≥0.8、低pz真高E和未知状态表。不得把未知当物理0或只报容易层。

使用固定 seed `2026110512` 的500次 incoming-cluster Poisson(1) multiplier bootstrap；同键跨源视图共用乘数，G+/S50 成对，六源权重及原视图权重固定。percentile 2.5/97.5%，至少475个完整有效 draw 才报区间，同时报有效数，不反复抽到成功。它仅为**这六源条件**事件区间；两个来源/成分不足以认证 source 泛化，不涵盖重训、研究选择、校准估计、系统或新 blind。没有新模型比较或显著性驱动选择。

## 5. 变量与程序审查：下一实验必须同时核验

静态核查发现需要区分“模型输入已清洗”与“分析切选仍使用什么”。原62列已用 raw11/status/typed NaN；但 `ml_low_energy_cuts.yaml` 中 Veto20/21、Timing、Preshower 仍用 fitted charge。它们可能影响父分母，**不能未经标定就把同一个40/20/2.5 pC阈值套到 raw_charge**。本实验记录 fitted/raw/status 分布及切选去向，不修改这些切选。

`SafeAt` 无轨迹时返回 NaN，能避免负占位值通过 upper cut；但已有实际 branch 内的负半径、负χ²/NDF、count溢出等仍需逐类型检查。“<95”本身不会排除 −1。保留原生切选结果，另报 invalid-but-native-pass 的影子审计，不暗中加清洗切选或删尾。

`fallbackVetoNu*Charge=-1234` 是源码有意定义的“无需fallback”，不能算损坏电荷；AuxLookupSuccess 与 reduced>=0 决定 fallback。raw 的合法 signed 负值、charge sign=-1、module_eta=-1 均不能一刀切。模型 typed规则以 `ml/configs/audited_features.json` 为准；实际 branch 的新占位约定若无依据则标未知，不能因为罕见就擅自 NaN。Calo 缺失不得 nansum 为小沉积。

原 `truth_diagnostics` 的 argmax/flatten 路径面向已有轨迹的 selected 数据。Stage112 必须先适配空轨迹/空真值/多候选和向量错长，保持一父entry一记录及未知状态；不能直接复制后使数组悄然压短。leading 仍为最高 pz0，禁止为了改善响应换成 truth-matched μ。

一次方动量模型政策保持只用 pz0，允许 px/py、q/p、弯折。机制中的真 μ 能量只用于诊断，不是新增模型输入。低于50 GeV没有既有完整模型预测支持，因此**不对该区域做 BDT 外推或宣称 preselection ML-vs-traditional 改善**。

## 6. Stage112 执行、预算和验收

后续调用时，在同一阶段完成小QA和六文件测量，不拆成连续的 metadata/接线报告。优先复用匹配当前配置的 `build/analysis`；源码变动才重编。显式传入 definitions、cuts、output、file config，保存有效 `requires`、辅助文件与校准配置及实际命令，避免 build/config 旧副本。六个单线程 source worker，统一 `~/condor/nu_muAnalysis/stage112/`。

1. batch 读六文件头/schema，要求每文件≤20000、合计≤120000父entry；超出则停止完整比较，不截有利前缀或另换文件。固定最多40真实QA：每源最前4条共24条，加这六源的原Stage105记录按row排序补最多16条，重复身份去重不补；另做空轨迹/多主μ/−999/−1/NaN/unsigned wrap/合法负值合成例。QA不是产额估计。
2. 核原生 run/event/source/entry、leading identity、MeV→GeV、mm/mrad/pC、向量对齐、native S50/cache包含关系和逐事件 `requires`，新旧相同记录的 pz差应0 GeV、truth能量相对差≤1e−12。完整 S50 与独立原生名义选择须成员完全一致；旧缓存是交集校验，不能要求父文件所有selected都已有兼容缓存。原生cut/定义与独立掩码不一致则停止主结论并报告具体差异。
3. 一次6CPU/12000MB任务，最多6worker、BLAS/ROOT内线程1、0GPU；累计CPU≤3600秒、任务wall≤900秒、接口请求≤2GiB、临时≤128MiB、最终≤20MB。GPU不适合本轮主要I/O与掩码归约，故不申请。先用QA实测/文件entry与basket metadata作factor3保守投影，保留CPU300秒/wall120秒/接口128MiB余量；使用完整basket/branch估计，不以40事件线性比例冒充EOS物理流量。预算不能认证则交缺项，不再循环调预算。
4. 只读所需 scalar、truth 和 leading 关联向量，避免SP/波形/xAOD。逐源复用basket、短生命周期紧凑标量暂存、汇总并去重JSON；结束删除临时ROOT/事件明细/运输包，仅保留汇总、QA、冻结输入和图。记录GNU外层CPU/wall/RSS、worker耗时与请求字节，嵌套计时不相加；物理网络不可得则注明未测量。
5. 验收是分母守恒、身份/切选闭合、每个来源和困难状态完整报告、两端点或精确不可估原因、误差分解逐例误差≤1e−12、汇总闭合≤1e−10、固定500抽样/有效数及实际成本。**效应为零、反向或支持不足都可完成本机制检验**，不要求新的性能收益。

若有明确选择富集，结论仅限于它对这六源传统风险的实际影响，为后续独立双侧支持与接受度研究定量；若未见富集，降低该解释优先级，不能继续用它替代模型失败原因。若原生切选存在invalid-through-cut，先交精确受影响数量及类型，另冻修正合同；不能在本轮“修好再报更优风险”。任何结果都不自动训练、改cut、扩源、生产或晋升。

## 7. 本阶段实际操作、验证和交付

实际操作：读取 Stage59/68/73/78/98/103/109/110 及相关三格记录、原分析/清洗/提取源码；`rg`/`sed` 和标准库 JSON/CSV 读取；urllib 检索上述论文；按固定规则选择来源并 `Path.stat()` 六次；复制原汇总55字段；写本报告、合同、来源表、文献表及路线/交接。没有 ROOT/NPZ事件载荷、模型/forward/fit、CERN环境恢复、作业提交、SHA 或数据生产。

可复核命令：

```bash
python3 workbook/stage111_energy_ml/validate.py
git diff --check
git diff --stat
```

验证结果记录于 [validation.json](stage111_energy_ml/validation.json)：证据字段与原JSON/TSV逐值一致、六源选择规则与stat一致、历史路线/信息计划前缀和Stage54后缀逐字节保持、文档本地链接存在。没有新增事件性能或计时可报告；本轮文献/文本操作的全会话资源也未测量，不把Stage110的15.39 CPU秒当本轮成本。

起始五项未跟踪Stage54资产原样保留；没有本轮提交目录需要清理，不动其他项目队列/目录。阶段报告及相关紧凑文件一起本地 Conventional Commit，无push。**Stage111研究设计完成；Stage112未执行，项目最终物理目标仍未完成。** 两低能/传统上95≤1.05、all/direct≤1.01、其他五层/direct≤1.03及八层三向tail差direct上95≤+2pp保持；当前长期开发cal/test不能替代新独立确认、source/refit/真实系统。
