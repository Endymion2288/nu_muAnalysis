# Stage108：完成全点关系与遮挡预训练三格比较，关系存在局部取舍，预训练主比较失败

日期：2026-11-05；起点 `9fdc973`。执行Stage103 §5/§7的局部点关系＋遮挡预训练探索，保留Stage104动作族停止以及Stage106/107原资源拒绝历史。

## 1. 阶段目标和实际结论

本阶段终于完成**一次固定的三格能量比较**：A=原audited62＋全点逐面mean；B=同输入＋同站邻层真实局部消息；C=同B，几何encoder先接受唯一train-only遮挡面计数预训练。不是再以零优化器QA代替能量实验。

**主比较不成立，而且有共同低能最坏风险恶化的条件证据。** 原cal_post上两个低能区的最大RMSE比 C_cal/A_cal 为 **1.085532136 [1.053995639, 1.151241510]**，事前要求上95<1，未通过。cal_post最低能单组比1.073787 [0.990711,1.150610]包含1，第二低能1.085532 [1.033779,1.130589]排除1；不能把联合最坏统计说成两个cal单组均显著恶化。

B的关系分支有局部迹象：开发test两低能B_cal/A_cal为 **0.941363 [0.912611,0.965639]** 和 **0.972888 [0.957446,0.988274]**；但低pz真≥200GeV困难层 **1.012767 [1.002106,1.022744]** 有恶化。cal_post两个低能B/A各自上95为1.005352/1.002360，均仍包含1。C_cal/B_cal在cal_post两低能分别 **1.116202 [1.045065,1.198967] / 1.102140 [1.049213,1.152368]**，本固定预训练未补足局部消息模型。

全部A/B/C raw/cal六种输出均未通过原最终联合门槛，不晋升，继续既有部署策略。B_cal最低能log-RMSE **0.273792** 对传统 **0.145661**，低能差距仍明显。结果限制的是本固定方案，不是全部关系模型/预训练的信息界，也不证明训练数据充分或不足的唯一原因。

## 2. 为什么执行Stage108，以及事前改变了什么

Stage107最终GPU保守投影7435.695189s超过7200s，在任何optimizer前结束。该7200s是前期内部工程合同，并非用户规定的硬限制。本次用户持续要求完成Stage103/路线图，并明确可改进或替换已有工作，因此在任何完整提取/优化器之前，另冻 [protocol.json](stage108_energy_ml/protocol.json)：

- **仅执行资源改变**：GPU累计任务wall封顶由2h改3h（10800s），CPU仍6h（21600s），GPU并发1，独立源提取/统计8CPU、内线程1，坐标缓存≤512MB、最终≤20MB。
- 原科学Stage106合同整体逐项嵌入，与Stage107的scientific_contract相同；原样本、架构、seed2026110506、点/边定义、全部epoch上限、optimizer、隐藏面/目标、校准和原最终门槛不变。新资源上限另行覆盖旧资源字段，**不声称Stage106/107通过了旧cap**。
- 复用真实Stage107测速与等价性，不再做实现/计时网格。先完整train/cal提取及真实规模/最大事件显存/训练适配准入，再恰1预训练＋3能量fit；三checkpoint及三offset全部冻结后才提取test。

这不是用户明确指定了3小时，而是本次持续完成目标下的执行预算决定；历史“不可自动续网格”与原阴性/拒绝证据保持。所有新能量结果在合同冻结后才得到。准入和完整实耗见下文。

## 3. 输入、角色和全量几何实测

使用Stage87原89033兼容池身份，17657隔离保持，active=train46575/cal11612/test13189，共71376；不重分、不补重复view。原incoming总权重1、全部1016新增K、标量missing21/6/5和全部困难/高端/尾支持保持。cal_select5443、cal_post5746，另423不参与select但保留完整cal。

原62由既有标量缓存重建，Stage94 C固定train-only127维变换不重拟合。pz0>50GeV、一次方动量只用pz0，原px/py、q/p、弯折允许；raw11/status/typed NaN、合法signed负读数和Calo缺项政策保持。没有p0/p1/pz1或ln(p0/p1)、没有fitted scintillator charge回流。坐标中的合法−1不普遍当缺失；非有限/−999整点/不支持名义层按原几何规则保留事件并fallback。本轮完整active几何实际没有无效点。

提取只读已知精确PHYS路径的run/event/SpacePoints/XYZ/Track_pz0七列；完整模式由原split身份＋既有pz元数据定位entry，原生ROOT不读truth。标量与truth标签来自已冻结缓存，仅按角色进入指定用途；不恢复已删Stage96 manifest，不扫EOS或旧scratch REC。

|实际测量|train/cal|test|
|---|---:|---:|
|原记录|58187|13189|
|来源|239|41|
|可用几何 / 已知缺源|57499 / 688|12833 / 356|
|原点数|12146928|3170587|
|单事件最大点数|10618|9138|
|无效原点|0|0|
|native pz0最大差|0GeV|0GeV|
|float32坐标损失|0mm|0mm|
|接口请求|3399056255bytes|762039400bytes|
|底层read|1399741924bytes|297414476bytes|
|压缩坐标临时缓存|66061470bytes|17160143bytes|

因此本轮实际认证active池 **70332可用/1044缺源、15317515个原点**，不再只引用Stage96覆盖元数据。train/cal图有 **122821859条有向边**，最大事件 **116238条边**；原train节点/边平均相对固定40QA倍率为 **1.432624457 / 1.455488767**。全点和重复点全部保留，同站邻层双向XY k8、E≤16N，不跨磁铁；无真实粒子ID、ghost或纯noise标签。

缺源分别原train345/cal343/test356，全部仍以原标量＋显式geometry_missing保留，不用错误bck替代K源。test缺几何356例也单独报告：A/B/C cal的log-RMSE **0.308771 / 0.311850 / 0.313391**，强direct62为 **0.280814**。缺源不是有利删样本入口，也不能由此推断完整几何样本的因果增益。

数据与逐源成本/schema见 [train_cal_extraction.json](stage108_energy_ml/train_cal_extraction.json)、[test_extraction.json](stage108_energy_ml/test_extraction.json)及相应TSV。

## 4. 完整规模准入、训练和可靠保存

### 4.1 全量准入

GPU沿用Stage107驻留准备和原Stage106模型，未增加架构或筛点。在所有optimizer前，以全train点/边倍率的较大值且至少1，缩放原“最慢256批×182×620×3+600”规则；另计3倍完整冷构建、旧提取/reserve8118.720840CPU秒、此前实际QA和本轮首次提取成本。

完整标量重建/建图/驻留/20epoch隐藏schedule/目标冷构建 **84.120805CPU s / 84.411882wall s**。驻留＋最大事件前后向allocated峰 **5096.236816MiB**，低于75%设备内存准入线。投影为 **9495.337188GPU任务wall s / 17734.079217CPU s**，分别低于10800/21600，故通过。详见 [full_input_admission.json](stage108_energy_ml/full_input_admission.json)。这仍是固定保守投影，不是完整训练实耗。

同原40身份执行实际训练循环适配、原incoming/logE、完整批分母与clip10，用不更新权重的optimizer stub与原参考F/B比较；clip后梯度max差 **5.960464477539063e−8**，checkpoint/预测回读精确，optimizer step=0。它承接Stage107的强制小微批监督及train-only Poisson梯度检查，不宣称逐全池独立梯度复算。见 [adapter_QA.json](stage108_energy_ml/adapter_QA.json)。

### 4.2 唯一预训练和三fit

预训练仅46230个几何可用train（46575减已知345），cal/test不参与任务或目标。隐藏面从原九个名义下游面按固定key/epoch RNG选择，先去隐藏节点/边再forward，visible-only元数据；原62标量/原全局counts/隐藏矩不入输入，目标独立交给loss。空目标允许，不按隐藏活动选面；名义面不等于认证active读出。

原Poisson257格任务固定20epochs，共3620 optimizer steps。训练loss（省略常数）从 **0.097468033** 到 **0.024420224**；这说明任务被优化，不能代替下游能量收益。仅point/message/update权重迁移给C，其余监督模块与A/B同seed重新初始化，三格同shuffle和目标。

监督为incomingweighted平方logE、Adam lr.001/默认betas/无decay、clip10、有效256，16384nodes/262144edges微批及完整批权重分母，超大单事件不截断。每5epoch原cal_select log-MSE选最早严格最小，patience30/max200。

|格|完成epoch|best epoch|监督optimizer steps|cal_post offset（logE）|该格记录GPU峰MiB|
|---|---:|---:|---:|---:|---:|
|A|55|25|10010|+0.012895421744292|4926.711426|
|B|55|25|10010|+0.007630535336039|5204.972656|
|C|50|20|9100|−0.023060013940051|5204.972656|

各声明参数90242，A常量message与B/C真实关系不是相同有效容量，C还有额外预训练计算。best cal_select log-MSE A/B/C分别 **0.087003247 / 0.086412663 / 0.087848613**。末epoch训练log-MSE **0.059632032 / 0.056165653 / 0.049424852**，末cal_select **0.091216817 / 0.092296827 / 0.100747390**；训练误差继续下降而验证恶化，符合已记录的开发过拟合迹象，但不据此事后改正则/早停策略或断言完整因果机制。

三checkpoint保存后逐state tensor回读一致，三offset各只用原cal_post权重一次；预测NPZ临时文件回读逐位核后原子更名。最终 [before_test.json](stage108_energy_ml/before_test.json)在test提取前写出三选择全部冻结；之后不换checkpoint、offset或策略。test一次推断，全active71376条六点输出均有限，原预测回读不变。模型与最终点表在忽略的 `ml/artifacts/stage108/`，无模型/事件数组入Git。

## 5. 原完整风险、主比较和最终门槛

所有能量/动量单位GeV；log-RMSE为自然log(E/GeV)误差、无量纲。下表使用**预定offset输出**，raw始终完整保留在points/paired/gates中，不据test选raw或offset。

|开发test策略|真50–100|真100–200|全体|50<pz0<100且真≥200|high-y|unconfirmed|
|---|---:|---:|---:|---:|---:|---:|
|传统pz0/.8|0.145661|0.247937|0.557190|1.887790|1.618799|1.638613|
|同split强direct62|0.282644|0.246329|0.287491|0.658177|0.609395|0.551305|
|A cal|0.290846|0.249292|0.297337|0.702500|0.644300|0.582378|
|B cal|0.273792|0.242533|0.297717|0.711469|0.646134|0.588583|
|C cal|0.310558|0.261919|0.301478|0.703016|0.637660|0.585907|

最低能cal_post只有97个incoming，test183；第二低能cal_post482记录/481incoming，test856/851；低pz真高能test297incoming、high-y385记录/384incoming。incoming条件精度不代表独立source/完整尾风险认证。

C/A主统计cal_post最坏两低能比 **1.085532 [1.053996,1.151242]** 未达上95<1。test两低能C/A为 **1.067774 [1.013658,1.115976] / 1.050652 [1.017926,1.088117]**；C/B为 **1.134285 [1.084605,1.181623] / 1.079932 [1.049594,1.118411]**。总体test C/A **1.013925 [1.007872,1.020361]**，C/B **1.012631 [1.006727,1.018797]**。high-y C/A **0.989695 [0.969928,1.008945]**包含1，不能说预训练恢复了困难侧。

B/A test两低能改进与困难侧损失见§1；总体 **1.001278 [0.998701,1.003680]** 包含1。B虽在两个低能区比本实验A好，仍不能用它替代强direct62或传统最低能基线。最低能正尾：传统0/183的经验率、direct **13.114754%**、A/B/C **12.021858/11.475410/12.021858%**；零经验率不认证总体零尾。

原八层最终门槛及三向tail50严格保持，六策略全部False。几个offset输出的关键95上端：

|最终门槛|A cal|B cal|C cal|原上限|
|---|---:|---:|---:|---:|
|最低能RMSE/传统|2.297860|2.192268|2.504250|1.05|
|第二低能RMSE/传统|1.092860|1.056850|1.140370|1.05|
|all RMSE/direct|1.042044|1.043363|1.056550|1.01|
|低pz真高能RMSE/direct|1.094131|1.110038|1.098471|1.03|
|high-y RMSE/direct|1.083720|1.089814|1.078330|1.03|
|低pz真高能负尾差/direct，pp|+8.202357|+7.994065|+8.207480|+2|
|high-y负尾差/direct，pp|+10.649272|+10.519514|+9.108718|+2|

这些困难层有额外负尾，不能以正尾下降或预训练loss下降掩盖。B_cal低pz真高能总/正/负尾 **37.481569/7.962253/29.519316%**，direct为 **35.830139/11.501032/24.329106%**。全部八层、总/正/负三向、raw/cal完整数据见 [points.tsv](stage108_energy_ml/points.tsv)、[paired.tsv](stage108_energy_ml/paired.tsv)、[gates.tsv](stage108_energy_ml/gates.tsv)；图见 [point_relation.svg](stage108_energy_ml/point_relation.svg)。

### 程序和物理解释的边界

完整身份/native pz/坐标、真实加权小微批、模型接线、checkpoint和点回读、独立risk及旧对照均通过，当前证据不支持把失败归为已发现的漏接或少读K。它们也不排除任何潜在建模/程序问题，尤其未做全池逐梯度独立复算。物理上，PHYS邻近点关系仍混合shower、次级和组合，计数遮挡优化不要求得到与能量风险一致的表示；本次loss下降、C的低能/总体劣化和末验证曲线恶化是实测事实。目标未对齐、小样本/泛化、几何混合或读出差异各自的因果份额**未测量**，不猜一个原因当结论。

不宣称小QA/三fit证明Bayes界、数据量足够或模型已最优。本次固定C任务没有支持增量，B有条件局部取舍；按合同结束，不自动追加depth/seed/遮挡任务/正则/新loss。

## 6. 统计验证、CPU/GPU和执行错误

8进程报告共92个非空role×stratum任务，共享数组/原component内incoming500次配对draw，cal/cal_post seed2026110389，test2026110390；不保存draw数组。完整cal11612/10811incoming、post5746/5539、test13189/12125；角色内incoming权重各总1。原X层、高端、缺标量/缺几何和困难者均报告。

840项旧传统/direct标量逐项差 **0**；主区间独立record-space展开差 **2.220446049250313e−16**；六输出×八层×RMSE/三尾共192项独立区间max差 **4.440892098500626e−15**。原点表逐位保留，0报告fit/校准。见 [report_validation.json](stage108_energy_ml/report_validation.json)。

区间固定当前模型、来源、offset和研究选择；cal_post又用于单offset拟合，不是全流程独立校准留出。开发test反复用于研究，**不是新blind**。source/refit/offset估计/研究选择及真实response/interaction/FSI/材料/Calo/接受度/背景不被500incoming条件区间覆盖。

|独立任务外层计时|CPU s|wall s|备注|
|---|---:|---:|---|
|9667814 首次train/cal提取|745.148787|129.859496|8CPU，申请8GB、站点24GB|
|Kubeflow唯一fit|674.266279|680.536285|含导入/冷构建/QA/预训练/三fit/保存|
|9667832 误重复train/cal提取|1029.268536|179.700640|必须计入，未重训/读test|
|9667833 正确test提取|282.540730|54.868506|8CPU，申请8GB、站点24GB|
|Kubeflow固定infer|19.562547|20.372337|0fit|
|9667835 报告|23.851183|9.203728|8CPU/8process/内线程1|

独立CPU合计 **2774.638062s**，含Stage106/107为 **2810.686772s < 21600s**。报告pool wall2.439562s/childCPU18.279539s是嵌套窗口，不再次相加；没有单核对照，不称8倍加速。

GPU使用指定H100节点/MIG3g.47gb，一次fit和一次infer均首次成功、无optimizer重跑。fit Pod在终态资源JSON保存前被平台GC，**actual CPU/内存和精确容器wall未保留、未测量**，不从infer推断22CPU/63G。fit完整Job区间 **693s** 作为GPU任务保守预留，包含调度/init/sidecar，不等于680.536285s数值外层wall；infer实际容器 **22s**、平台资源22CPU/63G/1MIG。共计/预留 **715s**，加前两阶段19s为 **734s < 10800s**。supervised阶段分别reset allocator，已记录峰max **5204.972656MiB**；预训练及整个fit绝对GPU峰**未测量**。Torch/OMP/BLAS线程1，GPUbusy/物理EOS流量/全会话与打包CPU未测。详见 [resources.json](stage108_energy_ml/resources.json)。

有一次可以避免的提交错误：普通CLI宏 `stage108_mode=test_extract` 被submit文件内默认赋值覆盖，9667832实际重复train/cal。检查out/Args后用 **`-append 'stage108_mode = test_extract'`** 修正，核实际Args/TransferInput才继续；原首次提取/三fit/冻结结果不改。重复输出的元数据单独保存，CPU和I/O完整计入；不掩盖错误、不重复optimizer。最终descriptor默认改为`required`，避免未显式设mode时隐式再做train。

正确test返回包一度在本地EOS FUSE不可见；XRootD stat证实既有17128964bytes结果后回收至/tmp，标准库collector仅改CACHE入口，550输入文件核验通过；**没有因观察缺失重跑正确test作业**。

## 7. 实际命令、产物与清理

```bash
python3 ml/package_stage108.py package train_extract
condor_submit AnalysisZipFramework/submission/ml_stage108.sub  # 当时默认train_extract
python3 ml/package_stage108.py collect train_extract
python3 ml/package_stage108.py package fit
kubectl create -f AnalysisZipFramework/submission/ml_stage108_fit_kubeflow.json
python3 ml/package_stage108.py collect fit
python3 ml/package_stage108.py package test_extract
condor_submit AnalysisZipFramework/submission/ml_stage108.sub stage108_mode=test_extract  # 错误：实际重复train
condor_submit -append 'stage108_mode = test_extract' AnalysisZipFramework/submission/ml_stage108.sub
# 本地FUSE缺失时，xrdcp既有结果到/tmp/nu_mu_stage108_collect后collector.CACHE覆盖收集
python3 ml/package_stage108.py package infer
kubectl create -f AnalysisZipFramework/submission/ml_stage108_infer_kubeflow.json
python3 ml/package_stage108.py collect infer
python3 ml/package_stage108.py package report
condor_submit -append 'stage108_mode = report' AnalysisZipFramework/submission/ml_stage108.sub
python3 ml/package_stage108.py collect report
```

后续使用descriptor必须显式 `-append 'stage108_mode = ...'`；本轮已终止，无待继续作业。五个输入包字节数 **4578298 / 103105658 / 4589682 / 56784854 / 52912192**，各收集534/546/550/571/583个原文件逐字节一致，不做SHA。报告代码在早期收集后才补齐、key_id对齐修正为原split元数据；训练/准备科学实现未在fit运行中变动。所有数值/事件/模型/统计在batch，本地仅标准库静态/传输/元数据/已测TSV整理。

spool统一 `~/condor/nu_muAnalysis/stage108/`。重复与正常原生提取合计接口 **7560151910bytes**、底层read **3096898324bytes**；不等于物理EOS流量。核验后删除所有传输包/临时坐标（两角色83221613bytes）及被最终全active点表覆盖的train_cal预测副本；保留三checkpoint、一个最终紧凑点表、曲线/风险/验证/图和代码。实际删除明细和最终≤20MB见 [storage.json](stage108_energy_ml/storage.json)。无ROOT/xAOD/逐边落盘，无push；Stage54五资产和Prompt原后缀保持。

## 8. 完成审计与下一步

[completion_audit.tsv](stage108_energy_ml/completion_audit.tsv)逐项区分实验完成与物理终点：Stage104有限动作、全量几何、Stage108恰三fit＋一预训练/完整风险均完成；**C/A主增量不支持、原最终联合未达、整体目标仍未完成**。不能再把“没有完整三格结果”列为当前缺口，也不能把完成实验写成达到能量恢复。

本固定点关系＋遮挡任务结束，不自动再开Stage109或调整seed/正则/目标来追赢家。下一任务需真实可交付输入或明确另冻的新科学问题：

1. **独立支持/确认**：输入为新source/incoming谱系、提议密度/权重、原接受度/选择和低能/过渡/同低pz真高能及高端控制的pilot选中产额。验收为与原池不重叠、困难者不删、真正未开发locked来源；旧1016K已完整使用，不能以重分/新seed冒充独立样本。
2. **真实读出/response**：输入为实际IOV/逐事件DAQ有效mask/coverage及无偏quiet/random或等效校准，能与PHYS联结。验收为共同有效分母、可识别的条件/噪声成分和物理尺度明确的变体；Stage85条件活动与110592名义分母不能反推纯noise或1σ。
3. **系统和选择**：输入为可与原incoming联结的interaction/FSI、材料/输运、Calo/读出等有依据变体及原选择分母/接受度/背景。验收为固定策略下完整风险/尾和迁移，独立source/refit/研究选择依据，不以prior重权/旧模板或开发bootstrap替代。

这些输入本轮未交付；没有时不恢复旧REC/EOS搜索、同一T/动作/collection族或再造无限计划链。原两低能1.05、all1.01、其他五层1.03，以及八层相对direct三向tail上95≤+2pp继续保持。先本中文报告，再代码/配置/紧凑证据本地Conventional Commit；路线追加§90、信息计划§70，Stage54历史后缀逐字保留。
