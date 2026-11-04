# Stage101：区分概率选模缺口与真实活动缺口，下一步只做一次双 checkpoint 实验

## 1. 阶段目标与判断

依照路线§82、信息预算§62和当前Prompt，复盘stage94/98–100已提交曲线、统计、源码与原论文。起点为 `9c9991b`。本轮**0训练、0网络/分类推断、0概率优化、0事件或模型载荷读取、0积分、0原生定位、0HTCondor/Kubeflow任务**，没有恢复CERN环境。以下实验数值全部引用历史阶段，新的性能、功效和训练成本均未测量。

结论是：**当前既有输入的概率选模仍有一个具体未完成的对照，真实新增关联活动则仍缺可交付载荷；两者不能互相替代。** 下一stage102只购买一条原seed/原输入/原MDN训练轨迹，同时可靠保存point-MSE-best与NLL-best两个checkpoint。它回答“概率checkpoint选择的效果”，不预设解除最低能和同低pz真高能的点风险竞争。当前PHYS collection摘要族保持停止，不追加分类器正则/树数/seed，也不扩大几何/GNN工程。

这不是重做stage94五格九fit，或继续等待一串零训练资格阶段。本轮直接交付唯一下一实验的输入、选择规则、主比较、预算和退出标准；**本轮没有执行stage102，也不自动晋升模型**。

## 2. 已有证据：哪些已测，哪些尚不能判断

### 2.1 同一概率训练轨迹，保存准则与训练目标不同

只读[原训练源码](../ml/compare_energy_architectures.py)确认：E是以 `log(pz0/0.8)` 为anchor的三Normal residual MDN，2×64 SiLU、9维head、12937个参数；训练目标为incoming加权marginal NLL，点输出为混合的mean logE。每5epochs验证，以cal_select **point MSE**严格下降选唯一权重，并按该准则patience30停止。NLL虽记录，但没有独立保存NLL-best权重。

以下直接取原三条曲线，未读取模型或事件。NLL和MSE均针对自然对数 `ln(E/GeV)`，无量纲；不是test结果。

|seed|point-best epoch|该点MSE|该点NLL|已记录NLL-best epoch|该点MSE|最低记录NLL|实际停止epoch|
|---|---:|---:|---:|---:|---:|---:|---:|
|2026110494|65|0.083493121|−0.135048985|50|0.083763599|−0.143989831|95|
|2026110495|90|0.082972117|−0.120730676|25|0.084431343|−0.137924746|120|
|2026110496|65|0.082424387|−0.134592965|35|0.084025793|−0.143561393|95|

精确原值/来源见[checkpoint_evidence.tsv](stage101_energy_ml/checkpoint_evidence.tsv)。这些是已记录验证点中的最小值，不是连续epoch或全训练域的最优。NLL较早变差而point MSE继续改善，支持“概率与点准则没有对齐”的判断；**不支持**“早期checkpoint test更好”“加epochs必然恢复低能”或“训练已达全局最优”。同一cal_select用于挑最小值，不能把表内差当留出概率增益或重训显著性。原源码只保存point-best，故需要一次受限轨迹才能得到缺失权重。

### 2.2 Stage99确实改善了概率产品，但没有改善点预测

下面来自[stage99概率表](stage99_energy_ml/probability.tsv)、[标量校准记录](stage99_energy_ml/calibration.json)和[配对变化](stage99_energy_ml/test_probability_change.json)。它们是三seed E集成，不能与下一次单seed两checkpoint冒充同容量对照。

|原开发test，全体13189记录/12125 incoming|旧点offset后的分布|唯一mean-preserving T之后|
|---|---:|---:|
|logE NLL|−0.107503598|−0.120703623|
|68% coverage|62.602337%|67.110928%|
|90% coverage|86.253883%|89.394777%|
|68%平均logE宽度|0.433694182|0.471389160|
|90%平均logE宽度|0.754108721|0.819652860|
|mean PIT|0.491100702|0.497919730|

唯一 `T=1.0869160335498813`、旧 `b=0.0211537082794257` 固定；cal_post5746记录、incoming权重和5539，优化4iter/12eval成功。test配对NLL变化95%为[−0.015639933,−0.010692396]，是已有的条件概率收益。区间变宽与coverage改善同时发生，不能只挑coverage而略去sharpness。

但test的X_pz100–200组meanPIT仍为0.483144030 [0.469218582,0.497510976]，X_activity0为0.483519906 [0.474395867,0.493038546]；均为X定义的组，局部失配仍有证据。总体meanPIT区间包含0.5并不能认证全分布或任意X条件校准。真E/y选组的PIT则不要求均匀，不能混作相同检验。

变换严格为 `Z′=m(X)+b+T[Z−m(X)]`，因此 `E[Z′|X]=m(X)+b`。本项目点能量为 `exp(mean logE)`，不是 `E[E|X]`；均值在这里专指logE均值。stage99已经逐位核旧点输出不变，故每个固定组的点RMSE、正/负/总tail也不变。未来一般CDF局部变换并不自动保持这个均值，不能把Cal-PIT当作相同的免费尺度修正。

### 2.3 强排序与低能风险付出可以同时存在

引用[stage99报告](2026-11-04_stage99_energy-ambiguity-and-activity.md)：观测50<pz0<100 GeV、train/cal X格冻结标准化后，开发test direct/E94/stage92 AUC为0.975092/0.976727/0.973852，pz-only为0.519382。已有读出及模型输出有强排序能力，不能把问题表述成完全无辨别力。

但E94名义2%cal_select阈值在开发test的低能误判为4.754309 [1.121885,10.158808]%，H识别91.725663 [88.527104,95.006203]%。排序、分数概率和受控工作点是不同性质；阈值不是由test选择，仍未取得2%总体NP保证。

原自然对数点风险满足 `R(m+c)−R(m)=E[c²]+2E[e0c]`，m为传统、e0=m−真logE。stage99已测最低真能50–100 GeV的E94修正平方为0.050087735，交叉项为+0.004886017，风险增量+0.054973752 [0.034975649,0.082281951]；同低pz真≥200 GeV风险增量为−3.113340137。这是同一修正在两个真值层的不同代价，不能从二类AUC推出连续点风险联合通过，也不能用signed交叉项给出唯一物理因果分账。

同split test最低能传统/direct/E94 log-RMSE分别0.145661/0.282644/0.276027，全体direct/E94为0.287491/0.289843（stage98/99已有记录）。NLL选模可能改善分布形状或中心，但本轮没有测到它对这些数值的效果。

### 2.4 新摘要没有进入固定树，不等于真实活动没信息

[stage100结构审计](stage100_energy_ml/structural_audit.json)使用原2048 train/cal incoming/24source；train L/H65/82、cal20/46。42新值在两角色诊断域均有有限支持且非恒定，B实际211维，排除了整个新增分支漏接/置常数。可是51次分裂全部使用旧SpacePoints26次、Veto10_raw_charge19次、Veto20_raw_charge6次，新增84列使用0次；两格100树执行相同，2048预测逐位相等。

故该固定pilot的A/B logscore均0.346455633、Brier均0.101254665，配对差和500条件区间均0[0,0]，事前主证据未达。cal L0/20、H38/46的名义2%工作点不构成总体零风险。小样本/正则/旧新量关联各自的因果份额未测；本轮不会靠重调模型把阴性结果变成有利结果。

|假设|支持的现有证据|仍缺的判别证据|当前行动|
|---|---|---|---|
|概率选模影响了分布质量|三条NLL/point最佳轮次不同；单T概率收益已经实测|保存NLL-best在out-of-selection支持上的概率/点配对结果|唯一下一轨迹同时保存两准则，分开验收|
|需要更真实的相对μ活动载荷|既有几何扩展无主体确证收益；真实关联/读出分母缺失|与原track闭合的ID/TSOS/SP组成/实际误差/有效读出及其预测增量|保留精确产品缺口，停止当前collection族扩展|
|已经达到物理信息上限|没有支持该断言的证据|全观测最优风险、响应/interaction系统和独立支持|不下信息极限结论|

## 3. 原论文核阅及本项目可行性

本轮使用网络读取原文，原PDF/HTML仅临时保存在 `/tmp/nu_mu_stage101_research/`，不入Git或EOS最终产物；引用/版本/阅读位置见[literature.json](stage101_energy_ml/literature.json)。没有借外部性能预测本项目收益。

|原文|核阅要点|本项目判断|
|---|---|---|
|[Gneiting & Raftery, JASA2007](https://doi.org/10.1198/016214506000001437)，§1/4.1/9|严格proper logscore针对分布，评价需兼顾calibration与sharpness；与点目标不同|以NLL选择概率checkpoint有方法依据，但proper不保证有限样本真E分层RMSE都改善|
|[Dey等，LADaR/Cal-PIT，v8](https://arxiv.org/abs/2205.14568v8)，§2/3/3.1|总体校准不推出局部校准；用覆盖X支持的iid calibration学条件PIT映射|有助解释stage99残余X失配；它额外训练一个映射且可改变点均值，不作为下一实验叠加自由度|
|[Tong/Feng/Li，Science Advances2018](https://pmc.ncbi.nlm.nih.gov/articles/PMC5804623/)，umbrella/NP-ROC/Discussion|用left-out class0次序统计量控制type-I，依赖独立同分布和足够class0支持|现有train阈值/复用cal/相关source不满足直接套用条件；AUC、0/20和bootstrap不补齐该保证|
|[Kopp等，中微子能量重建，2405.15867v3](https://arxiv.org/abs/2405.15867v3)，观测定义/neutron场景/错interaction模型比较|可见末态关联可部分推断不可见能量；interaction模型变化仍能带来偏差|支持真实可见活动与系统核验的研究价值；LArTPC输入/能区/包含度不同，外部改善倍数不迁移|
|[Kakati等，HGPflow，2410.23236v3](https://arxiv.org/abs/2410.23236v3)，§2.1/targets|输入是tracks与calorimeter对象，incidence描述粒子归属，cluster目标涉及真实能量贡献|PHYS SP计数/端点弦线不能替代这些载荷；没有产品支撑时换图网络名称不能补信息|

原文核查还表明：Cal-PIT在§3明确假定calibration数据来自覆盖目标X空间的分布；NP论文Discussion明确限制为各类内部iid。现有来源相关、研究选择和低能支持不足不能通过引用这些方法而消失。数学上平方log损失的总体Bayes动作是条件mean logE，NLL则拟合整个条件密度；即使密度拟合准确，也不保证在每个按真实能量挑出的组同时优于传统。这解释任务的区别，不证明当前模型已接近那个最优动作。

## 4. 唯一下一实验：原MDN一轨迹，两种保存准则

机器可读合同为[stage102_contract.json](stage101_energy_ml/stage102_contract.json)。以下全部是**拟议执行，未测量收益与新成本**。

**输入与角色固定。** 原89033兼容记录、46575/11612/13189 train/cal/test、17657隔离；37556/10811/12125 incoming，全部1016新增K、缺失21/6/5和困难/尾支持不变。复用stage94原cal_select5443/5272incoming、cal_post5746/5539incoming；423条purged_select仍参与完整cal评价。不能重分cal或改变incoming总权重。子角色用原subrole重归一权重，完整角色用原stage87权重。

输入为stage94 E原62 typed值＋62 mask＋wave_invalid/fit_failure/calo_invalid，共127维；虽维数与stage100 A相同，后者status/availability定义不同，不能混用。直接复用原train-only变换状态，核对 `preprocessing.json` 的E状态，不用新cal/test统计拟合尺度。pz0-only第一幂动量、允许px/py/q/p/弯折、raw11/status、typed NaN、合法负raw/charge/module_eta=-1、Calo缺项及pz>50 GeV全部保持。

**训练只一条。** seed2026110494，选择原第一个seed而非按结果挑最好seed；原E12937参数/三Normal residual MDN，sigma=0.05+softplus，float32、无AMP/TF32、Adam lr0.001原defaults/no decay、clip10、batch1024、原numpy permutation及incoming加权NLL。最多300epochs，每5轮验证，仍按原point-MSE patience30停止；NLL保存准则不改变梯度、停止时间或样本。NLL-best仅覆盖该轨迹已记录轮次，不是完整300epochs的概率最优。

同一轨迹保存P=cal_select raw point-MSE严格最小，N=cal_select raw NLL严格最小；ties均保留更早轮次。不是把旧50/65轮强行当新最佳，也不是两个fit。fit前唯一attempt ledger，训练中原子保存两state/epoch/score，结束回读后先持久化预测，再做统计；任何失败均不得自动第二次训练。两模型选择和协议冻结后才载入/forward test，不能用test择checkpoint、校准或gate。

**不追加任何新b/T优化。** 主要比较两者raw分布/mean logE，即b=0/T=1。另报告一项事前固定的旧seed494平移 `b=0.02017839294662559`，对两格点和所有分量均值相同施加；这是stage94 `offsets.tsv` 的旧值，带旧参数估计/研究复用限制。不套用三seed ensemble的b/T，不在raw/shifted中择test赢家。stage99单T集成仅作历史参照，不做匹配优越性归因。

**主要证据只有一个。** 原cal_post上，raw NLL(N)−raw NLL(P)的500component内incoming配对条件95%上端<0，才支持这条轨迹的概率checkpoint增量。采用原 `incoming_draws`，cal/cal_post seed2026110389、test2026110390；cal_post只用其子角色权重。cal_post历次研究复用，不能称新blind或独立确认。无论主结果正负，均一次性交完整cal11612/cal_post5746/开发test13189的两格预定统计，不按结果追加或隐去组。

概率报告raw和旧固定b两版本的NLL、68/90 coverage/宽度、meanPIT/十箱可靠性、原X组/真值诊断层；解析Normal-mixture CDF/确定逆CDF，不能重开stage92后验积分。点输出mean logE后取exp，报两格配对风险、传统/direct原八层RMSE门槛和三向tail50（总/正/负）差上端。保留全部中间能量、缺失和困难例，不做gate、拒绝预测或删尾。概率主结果、点风险保护和最终联合通过分别记录；任何一项概率改善都不自动晋升。

**QA与资源有界。** 原 `qa_rows()`固定40 train/cal身份，含全部21train/6cal missing，0optimizer，先核身份/角色/权重/subrole/变换/signed值、CPU/GPU forward/VJP、独立density/CDF与加载回读；记录实际batch1024成本后准入。float64 head中心差分最大差<1e−7、独立log-density差<1e−12，float32 CPU/GPU点logE差≤1e−5、同设备state回读预测逐位一致、逆CDF残差<1e−10；不得事后放宽。

旧seed494已存模型/head可作只读QA控制，mean解码对旧预测沿原3e−6门槛。新P不要求跨GPU/platform逐位重放旧P；如有差异量化，不把“新P−旧P”归于checkpoint选择。主要N−P来自同一新轨迹，隔离此歧义。

所有数值只在batch：至多1GPU/2CPU6000MB、内线程1、GPU任务含QA wall≤600秒；报告任务申请8CPU8000MB，最多8进程/内线程1，已加载数组共享、相同draw复用，最多1并发。阶段CPU≤1800秒、最终≤20,000,000bytes；实际站点可能改memory，申请与实际分开记录。GPU可用性/token状态和新成本**未测量**，不得假定旧10小时令牌仍有效。参考stage94原seed494 fit为7.984613wall/7.109082CPU秒、allocated peak94.310547MiB；九fit等外层worker112.157179wall/82.837277CPU秒，原4进程报告child151.100112CPU/39.138680wall秒，均非本轮实测成本或速度保证。无需GPU处理稀疏I/O，也不把8进程等同8倍加速。

若QA、预算或平台不准入，保留精确失败/已保存state，0第二轨迹；不靠删除事件、降容差或无界延长解决。无增量/有害则结束该checkpoint实验，不续seed/loss/局部校准网格；有概率增量也要如实保留低能点风险与响应缺口，不自动扩工程。

## 5. 原生最小产品、阶段交付与验证

真实新增活动分支若未来重开，最小产品不是再给一个REC文件名，而是：原stage95身份/production/原leading-track筛选闭合的持久轨迹引用；measurement/cluster唯一ID与TSOS；SP constituent引用；实际covariance及坐标/单位/有效性；各plane/module的collection和有效读出分母。可用紧凑提取表交付，不要求保留REC/xAOD副本。未归属活动不等于noise/强子，SP entries也不等于唯一cluster/粒子。其能量增量仍需单独测量。

stage99已核原d32b0ff3 scratch REC只发布PHYS后清理，官方同名6d6ab70b REC没有与原track闭合；本轮没有新定位或读取。不默认重建补源或新样本：若不能从原生产的持久产品证明上述联结，就明确缺失；新重建会改变响应合同，需要另行研究，不能冒充同一旧track信息恢复。这一缺口不阻塞已有输入的一次checkpoint对照。

交付为本中文报告、六行旧曲线证据、一份文献核阅索引、一份未执行stage102合同；追加路线§83/信息预算§63，下一Prompt改为唯一stage102实验。旧历史正文只追加，Stage54后缀逐字保留，五项原未提交工具/缓存不改。本地Conventional Commit，不push，不自动后续实验。

复核命令包括 `git status --short`、`cat/tail/rg`读取上述已提交文本；用Python标准库csv选原曲线最小已记录值，校对合同JSON；`urllib.request`并发读取上述五篇原文，PDF以 `pdftotext -layout`转临时文本。Cal-PIT无版本HTML返回404后用成功取得的abs/PDF，不据失败页面推断内容；Crossref宽标题查询先返回报告DOI，最终按JASA精确DOI核实作者/期卷页。路径误写的 `ml/report_architecture_comparison.py`查询未找到，已定位真实 `ml/report_energy_architectures.py`，未运行其事件代码。

文档/链接/表格/JSON、历史前缀与Stage54后缀验证和实际保留字节见 [validation.json](stage101_energy_ml/validation.json)。本轮event/ROOT/NPZ/model读取0，作业/fit/optimizer0；全文阅读/编辑全会话CPU、wall、峰内存及物理EOS网络字节**未测量**，不把旧stage94/99/100资源算成本轮消耗，也不为文档研究占用GPU/批处理资源。没有保存新事件数据或重复论文PDF。

继续保留最终两低能/传统上95≤1.05、all/direct≤1.01、≥200与困难/direct≤1.03、八层三向tail差上端≤2pp。source95、重训/阈值/参数估计/研究选择、真实response/interaction/FSI/材料/Calo/接受度/背景和未开发确认仍未认证；本轮没有新增物理性能测量。
