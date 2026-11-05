# Stage107：GPU驻留点输入保持等价，遮挡批耗时降低，但原资源准入仍未通过

日期：2026-11-05；起点 `54e7f58`。本次按用户持续推进路线图的请求，完成一次保持科学定义的工程修复。Stage106的拒绝和停止记录不改写；本阶段合同在提交前冻结于 [protocol.json](stage107_energy_ml/protocol.json)，其中整个 `scientific_contract` 与Stage106协议逐项相同。本次授权解释为可修复已定位的工程开销，不解释为增加预算或更改物理验收。

## 1. 阶段目标与结论

将原来逐事件在CPU生成遮挡子图、再复制到GPU的准备方式，改为静态点/边一次驻留GPU，按批移除隐藏面。核验模型入口、实际incoming权重梯度及端到端成本；只有原准入通过才可进入完整提取与训练。

**程序等价性通过，资源准入仍失败，按合同停止本次单一工程尝试。** 有效256事例的遮挡前后向中位耗时由Stage106的43.922181ms降至本轮17.501300ms；这两个独立QA窗口的比值约2.51，不是完整训练的配对加速测量。计冷构建、上一阶段和本次独立成本后，GPU任务wall投影为 **7435.695189s > 7200s**；CPU投影 **14900.267009s < 21600s**。没有第二个实现/计时网格、调seed/epoch/公式或放宽门槛。

监督fit、预训练运行/更新、optimizer step、完整角色提取、test载荷/风险、模型晋升均为 **0**。因此本阶段没有新的能量物理收益或阴性结论，C/A及最终能量门槛仍为**未测量**。不能从预算拒绝推断信息上限或低能不可恢复。

## 2. 输入、改动和等价性证据

固定原Stage105的40个train/cal incoming、24来源，train/cal=31/9，不重选人。Condor只读既知精确PHYS的run/event/SpacePoints/XYZ/Track_pz0七列，复用Stage106提取器但重定向输出到Stage107；不覆盖历史证据。37可读、3已知缺源保持，原5718点、单事件最大1117点、0无效点。原生pz0最大差 **0GeV**，float32损失 **0mm**，仅针对这40例。缺源仍是70:0一例及82:2两例K，不替换、不删分母。

原62变量经Stage94 C固定train-only状态形成127维；pz0>50GeV、一次方动量仅pz0、允许px/py/q/p/弯折、raw11/status/typed NaN及合法signed负值/Calo缺项保持。没有新增p0/p1/pz1或ln(p0/p1)，没有换回fitted charge。保留原46575/11612/13189角色、incoming权重、cal_select/post及全部1016新增K；完整角色载荷本轮未读取。真实sentinel发生率与完整几何覆盖仍未测，不以合成或小QA代替。

[stage107_device_data.py](../ml/stage107_device_data.py) 一次存放原点特征、平面、局部边、边特征和元数据；保留所有点/重复点。组批仍按16384nodes/262144edges，跨事件边为零。隐藏节点和所有关联边在forward前移除，可见counts/meta重新生成，模型不接触原62标量、隐藏计数或目标；目标独立传给loss。train-only的九面257格目标预先计算；按原始坐标自身的plane索引取目标，避免合成扰动导致的非canonical输入与已排序plane错配。NumPy log1p查表保留原float32计数变换逐位结果。隐藏面随机规则、架构/初始化/seed2026110506、loss、effective256及所有物理验收均不变。

实测见 [model_QA.json](stage107_energy_ml/model_QA.json)：

|核验|实测结果|
|---|---:|
|正常输入原40 vs GPU驻留pack|x/edges/ef/pool/meta/summary逐位一致|
|epoch1/7/20遮挡，各28个可读train|可见输入、hidden onehot及目标逐位一致|
|微批边端点事件归属|相同，无跨事件边|
|一个固定train身份隐藏XY及点数扰动|所有可见模型输入逐位一致|
|实际incoming/logE，40例，强制600node/6000edge微批 vs原批|参与参数梯度最大差1.1920928955078125e−7|
|train-only Poisson，28例，同样强制拆批|梯度最大差2.7939677238464355e−9|
|监督/遮挡输出最大差|0 / 5.960464477539063e−8|

梯度要求rtol1e−5/atol3e−6，输出要求≤3e−6，均通过。拆批始终使用相同完整有效批的权重分母；这补齐原Stage106未验证的**小样本真实加权微批**证据。诊断head设非零以传播梯度，未创建optimizer。没有测完整规模、optimizer轨迹、模型checkpoint或offset；B探针也不等同完整A/B/C训练认证。原Stage106的CPU/GPU、置换、空/缺/−999/overflow测试属于历史范围，本轮未重复宣称全部重测。

## 3. 实测成本、资源和准入

唯一CPU任务 `9667807.0`：首次start、exit0、无重试；申请8CPU/8000MB，站点8CPU/24000MB；8进程、内线程1。接口请求 **3823241bytes**、底层read **3569873bytes**，与原QA相同；物理EOS网络流量未测。外层含导入/全部子进程 **10.533633CPU s / 7.961872wall s**，峰单进程RSS **88964KiB**。source CPU8.625824444s、payload0.835719538s、其中建边0.095075289s是嵌套计时，不再相加。此次提取公式值6063.208614CPU s仅作测量保留，准入仍用事前约定的旧8118.720840CPU s提取/reserve，未因更快结果替换。

唯一GPU任务 `nu-mu-energy-stage107-qa`，pod `nu-mu-energy-stage107-qa-xzkgn`：H100 NVL MIG3g.47gb，首次成功、restart0、exit0。模板只显式GPU限制，平台实际分配 **22CPU/63G/1MIG**，Torch/OMP/BLAS线程1；设备总显存47488MiB。最大allocated **358.577637MiB**，本次计数器自驻留构建前开始，覆盖整个数值QA，口径不同于Stage106最后重复窗口。完整外层 **3.233160CPU s / 5.124189wall s**，峰RSS1395680KiB；容器wall **7s**，不是纯GPU busy time。

每项一次warmup+三次测量，含组批、索引/传输、forward/backward、回传与同步，无optimizer：

|分支|有效256 wall中位ms|host CPU中位ms|
|---|---:|---:|
|A|7.976036|7.932768|
|B|13.832497|13.763596|
|遮挡|17.501300|17.417472|

冷驻留/原图/20epoch隐藏schedule/目标构建 **0.194621900CPU s / 0.204434004wall s**。未做kernel或数据准备分项profile，不能定量归因全部速度变化，也未测完整训练和单核/多核加速比。

本轮独立外层CPU为 **13.766793s**；连Stage106为 **36.048710s**。GPU容器7s，连Stage106为19s；不把source/主函数/批窗口再次相加。平台、编辑、打包及完整会话CPU未测。详情见 [resources.json](stage107_energy_ml/resources.json)、[condor_history.json](stage107_energy_ml/condor_history.json)、[kubeflow_qa.json](stage107_energy_ml/kubeflow_qa.json)。

准入仍用最慢GPU批×ceil(46575/256)×620×3+600；CPU同理加旧提取/reserve与已测历史成本。另加三次完整train/cal驻留冷成本投影：本次40例冷成本×58187/40×3，得到849.334837CPU s / 892.155104GPU任务wall s。它是保守外推，并非已测全池构建。

|准入|worker内投影（已含Stage106）|再加本轮独立实际成本|上限|
|---|---:|---:|---:|
|GPU任务wall|7428.695189s|7435.695189s|7200s，失败|
|CPU|14886.500216s|14900.267009s|21600s，通过|

[admission.json](stage107_energy_ml/admission.json) 保留worker原结果；[final_admission.json](stage107_energy_ml/final_admission.json)补计本轮完整成本。GPU超限235.695189s，未因接近门槛而忽略冷成本、重测选快窗口或改变最坏任务620epoch规则。投影不是完整训练实耗或必要成本下界。

## 4. 命令、验证与存储

```bash
python3 ml/package_stage107.py package qa_extract
condor_submit AnalysisZipFramework/submission/ml_stage107.sub
python3 ml/package_stage107.py collect qa_extract
python3 ml/package_stage107.py package qa
kubectl create -f AnalysisZipFramework/submission/ml_stage107_qa_kubeflow.json
kubectl logs -n xcheng job/nu-mu-energy-stage107-qa -c qa --tail=70
python3 ml/package_stage107.py collect qa
bash -n AnalysisZipFramework/submission/run_ml_stage107.sh
```

两包 **1142633 / 37199682bytes**；收集时分别523/536个原输入/源码逐文件字节一致，不做SHA，记录去重于 [transport_validation.json](stage107_energy_ml/transport_validation.json)。收集后只收紧打包器/计时器/提取入口/shell可用模式为qa与qa_extract，以防失败后误触全量路径；数值准备/QA源码未变。静态AST及bash语法通过，未为这个入口收紧重复数值QA。

所有事件/模型运算在batch；本地仅标准库打包/静态/字节/元数据/文字整理。spool `~/condor/nu_muAnalysis/stage107/`。核验后删除两输入/返回包及36876bytes QA点云，不留逐点/边数组、xAOD或模型权重；最终逻辑体积≤20MB，明细见 [storage.json](stage107_energy_ml/storage.json)。Stage54五项原资产、Prompt后缀、其他项目spool和历史Stage106不改。

## 5. 阶段结论和下一步

本轮排除了一个具体程序顾虑：小QA中GPU驻留遮挡未改变模型可见信息、目标或实际加权梯度，且实测批耗时下降。**这仍未回答低能能量恢复、C/A增量或任何真实系统问题。** 当前三格完整训练合同在原预算下仍未准入，本次单一工程尝试结束，不再追加计时/实现/架构/seed网格。

[completion_audit.tsv](stage107_energy_ml/completion_audit.tsv) 保留原阶段性完成与未完成条目，并追加本次实测。原最终两低能/传统上95≤1.05、all/direct≤1.01、其余五层/direct≤1.03，以及八层总/正/负tail50差相对direct上95≤+2pp不变。旧开发test和incoming条件区间不覆盖source/refit/参数估计/研究选择/真实response或独立确认；整体目标仍未完成。

后续具体任务与验收入口：

1. 如有明确修订的执行合同，须先指定实际实现/准入条件，保持科学比较和物理门槛，另冻结成本与停止规则；不默认为本次结果授权加预算或新的优化网格。当前无后续作业提交。
2. 独立低能/过渡及同低pz真高E支持：所需输入为新source/incoming谱系、提议密度/权重、接受度与pilot实际选中产额；验收为与现有池无重复、困难与高端控制保留、真正未开发locked确认。没有输入时不随机拆旧池冒充新blind。
3. 真实response/系统：所需输入为逐事件DAQ有效mask/IOV及无偏quiet控制，或可与原incoming联结的interaction/FSI/材料/Calo等有依据变体及选择分母；验收为定义可核验、尺度有物理依据、完整选择迁移和固定模型评价。Stage85条件活动不能反推纯noise或1σ变体，旧模板/prior压力不是认证。

本轮不新扫EOS/旧REC、不重做已结束的动作/T/collection族。路线只追加§89、信息计划§69，更新下一Prompt并逐字保留Stage54后缀；先本中文报告再本地Conventional Commit，不push。
