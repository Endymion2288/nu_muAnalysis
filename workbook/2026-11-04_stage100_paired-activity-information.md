# Stage100：补齐 A 后，当前 collection 摘要未提供可支持的配对增量

## 1. 阶段目标与结论

按路线图§81、信息预算§61和原下一轮 Prompt，仅补齐 stage99 因保存接口失败而丢失的 A classifier：**本阶段恰一次 A fit，0 B 重训、0能量 fit、0新 T、0 ROOT/native 读取、0 test 评价**。起点 commit 为 `3d10d1e`。全部事件 QA、训练、推断、统计、独立验证和画图均在 HTCondor；本地只编辑、打包、回收、资源/文件元数据记账与提交，没有恢复 CERN 软件栈。

结果：A/B 的 cal 分数和条件区间完全一致，主指标 logscore 的 B−A 为 **0 [0,0]**，未达到事前规定的上95%<0。额外零训练审计发现：B 的42个新值全部已填充且在原 train/cal 诊断域中有变化，但 **B 的51次分裂没有一次使用新增值或新增 mask**；两格100棵树的执行 dump 完全相同，原2048 train/cal身份上的预测逐位相等。按既定停止规则，结束这一族 PHYS collection 几何摘要的工程扩展，不启动完整池提取、能量消融或 GNN。

这是固定小队列、固定正则与模型配置下的结果；没有证明真实关联活动无用、总体没有新增信息或已经达到 Bayes/物理上限。低能量模型的联合风险问题依然存在，既有部署不变。

## 2. 输入、选择与唯一训练合同

复用原 `ntuples/energy_ml_stage95/cohort.json` 的2048个不同 incoming、一incoming一视图、24个 source，只有原 train/cal。与 `ntuples/energy_ml_stage87/split.npz` 的 row/key/role/origin/origin_row/run/eventID/group/component 逐项核对，train/cal 的 incoming 和 source 不相交。

|原队列角色|完整身份数|PHYS collection可用|历史缺源|
|---|---:|---:|---:|
|train|1513|1388|125|
|cal|535|535|0|
|合计|2048|1923|125|

125缺源身份照旧保留，沿用stage99缺源π28/K97及全部K支持，不重建补源或恢复旧K生产时限。不是新增样本或重新划分角色。100–200 GeV中间能量仍保留完整队列分母。

classifier观测域严格为 **50<pz0<100 GeV**；诊断标签L=真50≤E<100 GeV，H=真E≥200 GeV。truth仅作标签，不作部署输入。

|诊断角色|L incoming/记录|L source|H incoming/记录|H source|
|---|---:|---:|---:|---:|
|train|65|9|82|17|
|cal|20|4|46|6|

train147例中139个PHYS可用、8缺源；cal66例全部可用。来源在类别间可能共享，不将各类别source数相加当独立source数。

A的127维严格匹配旧B共同分支：62 audited值＋62 missing mask＋status_other＋PHYS availability＋恒0的exact-native availability。B211维再加原42个collection值和42个mask。本轮没有改变B、原输入或旧输出：

- 原62值来自stage55 `dataset.npz`、stage56 `readout.npz`和stage70/81/82/83 `support.npz`，规则来自 `ml/configs/audited_features.json`。
- B复用 `ntuples/energy_ml_stage99/{B_collection_features,B_identities,B_classifier_predictions}.tsv`、`ml/artifacts/stage99/B_classifier_B.json` 和原B统计表。
- 第一幂动量只用pz0，不用p0/p1/pz1或其对数比；原px/py、q/p、弯折仍允许。保留raw11/status、typed NaN、合法负raw/charge及module_eta=-1，不把所有负数一刀切成缺失。原Calo缺项、pz>50 GeV和困难侧政策不变。
- 62值逐列重走typed cleaning并核一致；pz缓存是float32，按cohort pz转换为float32后核值，不拿未舍入float64做伪不一致判断。

唯一A配置：XGBoost2.1.3，`hist/binary:logistic/logloss`，100树、depth2、eta0.05、min_child_weight10、lambda10、seed2026110499、n_jobs1，无earlystop或seed/超参网格。与保存B相同。fit前落盘唯一attempt ledger；fit后先原子写出并回读train/cal预测，再用 `get_booster().save_model` 保存原生Booster，绕开旧sklearn保存接口的 `_estimator_type` 问题。模型重新加载后的预测逐位一致。**后续report/validate/audit均0fit，没有第二次A尝试。**

事前主证据规则为cal paired logscore B−A的上95%<0，Brier/低误判工作点作佐证。该条在QA打包后、读取QA结果和新A结果前补入protocol，原QA版本逐字归档为 `protocol_QA.json`，差异在admission说明；模型、支持、seed与统计合同均未因此改变。

## 3. 配对测量与工作点

以下数值无量纲；两格均为同66 cal例，区间来自500次component内incoming重抽样，seed2026110499，与stage99 B一致。预测和train阈值固定，区间不含来源抽样、重新训练、阈值估计、响应/系统或研究选择不确定度。

|cal指标|A|B|每格条件95%|B−A及其95%|
|---|---:|---:|---|---|
|logscore|0.346455633|0.346455633|[0.252028743,0.462819455]|0 [0,0]|
|Brier|0.101254665|0.101254665|[0.061707997,0.150646988]|0 [0,0]|
|ROC AUC|0.929891304|0.929891304|[0.863225141,0.979777553]|0 [0,0]|
|pAUC：FPR≤0.1面积/0.1|0.847826087|0.847826087|[0.730373476,0.950277778]|0 [0,0]|

阈值各自在本模型train L65上取：严格score>t，选满足经验FPR≤名义值的最低观测L分数，不拆ties，不看cal调阈值。A/B的阈值及所有工作点恰相等：

|名义FPR|train阈值t|train误判|cal L误判及实际FPR|L条件95%|cal H识别及TPR|H条件95%|
|---|---:|---|---|---|---|---|
|2%|0.591321885586|1/65=1.538462%|0/20=0%|[0,0]%|38/46=82.608696%|[71.111111,92.944352]%|
|5%|0.380478262901|3/65=4.615385%|1/20=5%|[0,17.181373]%|38/46=82.608696%|[71.111111,92.944352]%|
|10%|0.310286164284|5/65=7.692308%|2/20=10%|[0,25]%|40/46=86.956522%|[76.382979,95.700740]%|

两种错误类型的B−A差和500重抽样区间全部0 pp。0/20的经验bootstrap退化为[0,0]不表示总体无误判，不能认证2%人口错误率/NP保证；只有4个低能来源，cal又已反复用于研究。没有另开test评价，也没有以此替代能量RMSE/尾风险联合验收。

精确统计表为本目录 `stage100_energy_ml/{metrics,paired,thresholds,working_points,paired_working_points,ROC}.tsv`；图为 [paired_pilot.svg](stage100_energy_ml/paired_pilot.svg)，PDF在同目录忽略产物中。

## 4. 为什么结果完全相同：程序与物理边界

额外audit只加载保存模型和原缓存，0fit，目的是排除“新增列没接上”或“比较时误读同一模型”这样的程序解释：

|审计量|实测结果|
|---|---|
|模型实际输入维数|A127、B211|
|共同127列|含NaN位置完全相等|
|新增42值有限支持/非恒定|train42/42、cal42/42|
|新增42 mask非恒定|train42/42、cal13/42|
|树数|各100|
|非叶分裂数|各51|
|B使用新增84列的分裂|0|
|实际被使用的列|SpacePoints26次，Veto10_raw_charge19次，Veto20_raw_charge6次；A/B相同|
|执行tree dump、base score|A/B完全一致|
|原2048 train/cal预测|全部逐位相等，最大绝对差0|

原生JSON的100个tree_param对象不同，两个模型的输入维数也不同；因此不声称模型文件逐字相同。执行树dump相同核的是节点/阈值/叶值/缺失路由，足以解释相同分数。新增特征按既定211维传入且数值有变化，排除了整个新增分支被置常数或接线遗漏；没有证明这些量的真实条件信息量为零。

目前精确机制是**固定B没有选择新增变量**。样本规模、正则、既有SpacePoints/raw读出与新增摘要的关联，可能限制这个pilot，但本轮没有用新fit区分各因素的因果贡献，不将某个猜测当主因。按预注册停止规则结束当前摘要族的扩展，不靠放松正则、加树/seed或扩大提取来追逐结果。

真实measurement/cluster ID、SP constituent关联、与原leading轨迹闭合的TSOS、actual covariance和有效读出分母仍未测。stage99已经核实原d32b0ff3 scratch REC只发布PHYS后清理；同名6d6ab70b REC未与原track闭合。PHYS端点弦线是几何替代，不是拟合轨迹传播，collection entries不是唯一粒子/cluster，更不把未归属活动认作noise或强子能量。本轮不重新扫描或重建。

## 5. QA、独立验证、命令与资源

QA使用原cohort中顺序固定的40个qa身份/24source，37可用/3缺源，0optimizer。A127/B211，A有4个NaN，62值中614个合法负值保留；原B加载—预测—保存—回读逐位相同，原B文件字节未变，重合的2个旧cal预测闭合。软件版本XGBoost2.1.3、sklearn1.8.0。

fit/报告复现旧B **44项**指标/工作点；独立validate重新加载不同路径的两个Booster，核train/cal预测和旧B。独立sklearn log_loss/Brier/AUC、标准化pAUC反变换、显式重复incoming展开500样本及独立阈值选择共 **90项**通过，最大差 **1.1102230246251565×10⁻¹⁶**。不是只将同一报告函数再调用一次。原队列/角色/source/incoming闭合通过。

执行合同：

```bash
python3 ml/package_stage100.py package qa
condor_submit AnalysisZipFramework/submission/ml_stage100.sub -append stage100_mode=qa
python3 ml/package_stage100.py collect qa
# QA通过后，仅执行一次fit：
python3 ml/package_stage100.py package fit
condor_submit AnalysisZipFramework/submission/ml_stage100.sub -append stage100_mode=fit
python3 ml/package_stage100.py collect fit
# 依次零训练验证和结构审计：
python3 ml/package_stage100.py package validate
condor_submit AnalysisZipFramework/submission/ml_stage100.sub -append stage100_mode=validate
python3 ml/package_stage100.py package audit
condor_submit AnalysisZipFramework/submission/ml_stage100.sub -append stage100_mode=audit
```

每步待前一步完成并回收后进行，最多1并发。worker在已有LCG109环境运行，申请/实际均2CPU/6000MB，无GPU，线程全部1；`timeout180s/MaxRuntime240s`，无自动重试。147例浅树没有本阶段GPU收益测量，未为此占GPU；这不是GPU比CPU慢的测量结论。

|任务|Condor ID|exit/启动次数|外层CPU秒|外层wall秒|峰RSS KiB|
|---|---|---|---:|---:|---:|
|40身份QA|9667687.0|0/1|3.95|6.72|287664|
|唯一A fit＋报告|9667694.0|0/1|4.56|6.99|299524|
|独立验证＋图|9667695.0|0/1|11.11|14.14|308932|
|结构/输入审计|9667697.0|0/1|4.18|6.01|308788|

独立外层 `/usr/bin/time` 合计 **23.80 CPU秒<300秒**，Condor整数粒度合计25 CPU秒；不把二者相加。单次fit核心0.048707033 CPU秒/0.052819224 wall秒，含重建/报告的worker1.499268581 CPU秒/1.526410827 wall秒，已经包含在外层4.56CPU秒中。QA worker1.008878546CPU秒、独立验证8.979604510CPU秒和audit1.076967971CPU秒也不再叠加。环境setup/打包/本地metadata与全会话CPU未完整测量；数据不支持多核或GPU加速倍数声明。

四任务都首次exit0，没有本阶段fit失败或任务重试。validate返回包在XRootD端存在但EOS挂载listing滞后；通过明确XRootD路径下载临时包并以 `collect validate --archive /tmp/nu_mu_stage100_result_validate.tar.gz` 回收，audit同样使用此路径。没有因挂载问题重跑统计/训练。collector拒绝覆写不一致产物，并逐字核原cohort/旧B输入与各输入包一致；QA的旧protocol单独存档。

ROOT/native接口请求及native event payload均0；缓存解压/数组读取不等于物理EOS网络字节，后者**未测量**。重复输入包约36.8MB/个包含共用旧缓存，只在传输中使用，回收核验后删除，不保留新原生副本。最终新增唯一文件字节及清理清单见 `stage100_energy_ml/{storage,cleanup}.json`，上限20,000,000 bytes；旧共享缓存/B模型/Stage54只读保留。资源证据见 `resources.json`、`history.json` 和四个time文本。

产物：A模型在忽略目录 `ml/artifacts/stage100/A_classifier.json`；66cal/147train预测在 `ntuples/energy_ml_stage100/{predictions,train_predictions}.tsv`，均不入Git。协议、QA、配对统计、独立核验、结构/输入聚合表、图和报告入Git。stage54原五项未提交内容及Prompt保留后缀不改。

## 6. 阶段判断、未测量与下一最小任务

已交付原支持闭合、唯一A可靠持久化、旧B逐位不变、完整配对统计和同分原因。主证据不支持新增摘要收益，按计划停止这一collection族工程扩展；不自动执行Stage101，不晋升模型，不修改原最终两低E/传统上95≤1.05、all/direct≤1.01、≥200和困难/direct≤1.03及八层三向tail差上端≤2pp门槛。

本轮未测量：能量RMSE/尾风险新收益、NLL最佳checkpoint重训、真实关联/有效读出、源级95%区间、重训方差、严格总体低误判保证、真实response及interaction/FSI/材料/Calo/接受度/背景系统学、未开发独立确认。既有开发test/cal的研究选择效应未因配对bootstrap消失。

下一最小任务为**有界研究复盘**，只用stage94/98/99/100已提交曲线/汇总表和原论文，不读事件/模型载荷、不fit、不补积分、不重新找REC。输入包括原MDN point-best/NLL记录、stage99概率与连续点风险表、本轮结构证据和已确认原生产品缺口。具体交付：区分“概率checkpoint/目标未对齐”和“需要真实新增载荷”两条假设，列出现有证据及不能判断之处；核查point保持的概率变换不能降低point风险；用文献方法边界提出至多一个可验收后续合同或明确停止条件。任何新训练/提取均要在该阶段另冻输入、预算、主要比较和验收标准，不能从本轮阴性结果自动推出宽泛模型搜索。报告与路线记录完成即验收，不要求产生有利新分数。
