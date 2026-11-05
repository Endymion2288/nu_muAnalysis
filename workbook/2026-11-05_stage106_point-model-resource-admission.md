# Stage106：局部点模型接线通过，资源准入拒绝，在优化器前停止

日期：2026-11-05；起点 `da6f620`。按 Stage103 §5、路线§87、信息计划§67及 Stage105 已冻结三格合同执行。用户本次设定持续目标为完成现有规划，因此继续了 Stage106；没有把上一轮“不自动启动下一阶段”当作本次明确续作的障碍。

## 1. 结论与执行范围

**本次测得的几何、CPU/GPU前后向、可见输入隔离和梯度接线项目通过；事前固定的资源准入失败。依合同在任何 optimizer step 前停止。**

H100 NVL MIG 3g.47gb 上，有效256事件的 A/B/遮挡任务端到端前后向中位耗时分别 **8.839163 / 15.010071 / 43.922181 ms**。冻结规则使用最慢任务外推全部620个最坏epoch并乘3保守系数、加600s，得到 **15468.536715 s GPU-task wall**，超过7200s；对应总CPU投影 **22692.597896 s**，超过21600s。记录的GPU计时窗口allocated峰最大361.045898MiB，未触及该窗口的显存准入线。

这不是实测完整训练需要15469s，也不是几何/预训练无用的能量阴性结果。它是**当前实现、固定QA输入和既定保守准入公式不允许继续**；没有改用阶段加权投影、较少epoch/seed/数据、放宽预算或换有利子集来制造通过。三格风险、C/A主比较、真实训练收敛、完整输入规模、完整实际GPU成本均为**未测量**。

实际完成1个8CPU Condor提取QA和1个H100 MIG零优化器QA，均首次成功；累计独立外层 **22.281917 CPU s**。新监督fit=0、预训练运行/更新=0、optimizer step=0、test载荷/风险=0、完整样本提取=0、模型晋升=0。前后向探针不等于一次训练。

## 2. 事前合同与实际输入

[protocol.json](stage106_energy_ml/protocol.json) 在首次事件任务前冻结，保留 [Stage105原合同](stage105_energy_ml/experiment_contract.json) 的架构、seed2026110506、原角色、预算和stop条款，仅补充运行实施细节：native请求总保护上限10GB、坐标float32误差≤0.002mm、RAM中按需缓存边但不落盘、正常提取成本的固定外推公式。未改原物理门槛。

**身份仍是 Stage105 原40个 train/cal key、24个来源，不按当前点活动或能量重选。** 使用原精确PHYS路径和实际 input_entry；只读 `run,eventID,SpacePoints,SpacePoint_x/y/z,Track_pz0` 七列，不读ROOT truth。38MB量级的GPU输入传输包包含既有缓存供原typed62重建，QA仅选择原40身份，未对test特征/真值作模型计算或统计。

|本轮实际输入/联结|测量|
|---|---:|
|固定身份、唯一incoming|40、40|
|train/cal/test QA身份|31 / 9 / 0|
|来源|24|
|可读/已知缺源|37 / 3|
|原点数/最大事件点数|5718 / 1117|
|非有限或不支持名义层的原点|0|
|原身份及leading pz0对齐最大差|0 GeV|
|float32坐标损失|0 mm，仅此QA|
|接口请求/底层native read|3823241 / 3569873 bytes|
|临时QA坐标缓存|36876 bytes，最终删除|

3个缺源仍为 `70:0` 的row81325、`82:2` 的row82784/82790；两条K和一条pi保留，没有替代错误bck路径。与 Stage105 点数、可读分母、请求量一致。几何仍是四站×三名义层、同站邻层XY双向k8、E≤16N、不跨磁铁；完整点和重复点不截断不去重，缺源与观测空集合分开。

标量由 `reconstruct(原40 rows)` 及 Stage94 C冻结train-only变换生成，实际输入40×127，来自原audited62。原 pz0>50GeV、pz0-only一次方动量/允许px-py-q/p-弯折、raw11/status/typed NaN/合法signed负值/Calo政策保持；没有恢复Stage19历史p0或fitted charge。占位规则依变量物理域，不把坐标或signed raw中的−1普遍当缺失。真实异常占位率和全角色几何覆盖仍未测；合成异常只作程序probe。

原完整角色46575/11612/13189、17657隔离、incoming总权重1、全部1016新增K及标量missing21/6/5在本轮未变更。历史70332可读/1044缺PHYS与train/cal/test缺345/343/356仍仅为 Stage96 已有元数据；**本轮没有重新认证完整角色载荷**。

首次本地打包发现 Stage96 `manifest.npz` 已在历史清理中删除；打包失败时没有作业成功提交、没有事件运算。随后将QA包改为直接使用已冻结Stage105身份；条件完整提取路径改从原Stage87 split与既有pz元数据联结，不恢复旧临时manifest或扫描EOS。这些未准入完整路径没有执行。所有本地Python均为标准库静态/打包/字节/格式/元数据整理，没有本地ROOT、模型或风险复算。

## 3. 模型、遮挡和本次程序证据

[stage106_model.py](../ml/stage106_model.py) 实现合同的10→32→32点编码、68→32→32消息、64→32→32残差更新，两轮共享权重；12面mean384、meta26、原标量127，经537→64→64→1输出logE。A的消息MLP只读固定零68向量；B/C使用真实局部邻接，C仅预定由train-only任务迁移几何encoder。包含422→64→257预训练decoder时各声明 **90242参数**，不同有效容量/额外计算限制保持。

边仅在单个事件内组装成ragged disjoint union；微批上限16384nodes/262144edges，单事件不截断，输入/传输/前后向/回传均进入批计时。CPU/GPU取相同原40，扩展到有效256仅为成本重复，不增加独立物理事件。

[model_QA.json](stage106_energy_ml/model_QA.json) 的实测范围：

|接线核验|实际结果|
|---|---:|
|CPU/GPU max logE差|4.76837158203125×10⁻⁷，要求≤3×10⁻⁶|
|A/B 各CPU/GPU事件置换 max logE差|0|
|A/B 各CPU/GPU点重排及边索引重映射 max差|0|
|B/C 预训练前全部初始参数|逐项精确一致|
|所有边两端事件索引|精确相同，无跨事件边|
|隐藏面先去除再建图 vs 从原邻接过滤两端|40/40输入逐项精确相同|
|改变隐藏XY/增加隐藏点后可见输入|37个可读身份逐项精确相同|
|合成空事件/缺源/全XYZ=−999|输出及已参与梯度有限|
|合成XY=300mm隐藏点|进入第257格overflow，计数守恒|

隐藏面按 `default_rng(SeedSequence([2026110506,epoch_1_based,key_id])).integers(3,12)` 生成，选择独立于隐藏活动/能量。预训练decoder probe只取原train且geometry可用身份；不输入62标量、原总点数、隐藏计数/矩或truth。可见counts/metadata重算，hidden plane onehot允许。过滤边与重新构图相等是因为整名义面移除不会产生新的相邻层对，**并非允许隐藏面参与构图**；本轮实测逐项相等。

用非零诊断能量head和平方输出probe，将导数传入encoder，不按能量风险选策略。B GPU point/message/update首层weight梯度范数分别 **0.008391605690 / 0.001334711094 / 0.014887060039**，预训练decoder首层 **0.075564578176**，有限且非零。A固定零输入使message首层weight梯度为0，bias与后续层有梯度，这是常量对照的定义，不把它称为漏接。

**测试范围限制**：这些是40身份上的数值接线证据，不认证完整训练或最终物理性能。QA诊断平方输出与单位重复权重不是实际全池incomingweighted log-MSE训练；真实加权微批梯度等价、完整train/cal最大规模、checkpoint选择/offset以及所有学习轨迹没有执行。`stage106_train.py` 是受admission门控的条件实现草案，未运行或完成fit验证，不能据其存在称三fit已交付。当前admission=False，入口在任何optimizer前拒绝；也没有 `optimizer_started.json`、`before_test.json`、模型checkpoint或预测产物。

真实名义面≠经认证的active readout；几何邻近≠共同粒子ID，SP≠唯一粒子。没有ghost/强子/noise伪标签，也没有恢复ID/TSOS/covariance/历史conditions；这些机制和response缺口保持。

## 4. 正常提取与CPU/GPU实测成本

### 4.1 唯一CPU任务

Condor `9667791.0`，首start/exit0、无重试。请求8CPU/8000MB，站点实际8CPU/24000MB，线程1；仅24来源的固定QA，未扩到全池。

- source窗口CPU总和 **12.411866591s**，其中逐entry正常payload **1.173081020s**、包含在payload内的建边 **0.130220819s**；没有Stage105逐查询暴力近邻复核。
- main内层wall **3.922180869s**、selfCPU **0.102943630s**；外层含导入和全部子进程 **7.961973572wall / 14.710458CPU s**，峰单进程RSS **95664KiB**。嵌套时间不重复相加。
- 37身份平均payloadCPU×历史70332记录，加22个可读QA来源测得的非payload平均CPU×280来源，整体×3再加1000CPU reserve，投影 **8118.720840197s**。这是正常提取的保守估计，不是实际全量成本；请求bytes为接口量，不是物理EOS流量。

逐source七列schema与成本见 [QA_schema.tsv](stage106_energy_ml/QA_schema.tsv)、[QA_source_cost.tsv](stage106_energy_ml/QA_source_cost.tsv)，汇总见 [QA_extraction.json](stage106_energy_ml/QA_extraction.json)。没有单核提取对照，不能把8CPU申请当8倍加速证明。

### 4.2 唯一GPU任务

Kubeflow job `nu-mu-energy-stage106-qa`，pod `nu-mu-energy-stage106-qa-svltl`，NVIDIA H100 NVL MIG3g.47gb。实际mutated资源22CPU/63G内存/1MIG，Torch/OMP/BLAS内线程1；首Pod、restart0、exit0，container运行12s。Torch2.10.0/CUDA12.5、LCG_109_cuda/x86_64-el9-gcc13-opt。资源和终态证据见 [kubeflow_qa.json](stage106_energy_ml/kubeflow_qa.json)。没有同时排另一个GPU任务或扫设备。

以下每项是一次warmup后3次有效256前后向的中位数；含微批组装、CPU→设备、前后向及结果回传/同步，**不是纯CUDA kernel时间**。worker每次重复reset峰计数，表中allocated是各分支最后一次重复窗口的峰，不是整个容器全程峰；后者未测。

|任务/设备|wall中位ms|host CPU中位ms|GPU allocated峰MiB|
|---|---:|---:|---:|
|A / CPU单线程|82.522742|82.225017|不适用|
|A / H100 MIG|8.839163|8.788941|105.419434|
|B / CPU单线程|946.125649|943.615004|不适用|
|B / H100 MIG|15.010071|14.932492|359.426758|
|遮挡task / H100 MIG|43.922181|43.051746|361.045898|

实测GPU明显缩短同一小批的A/B前后向，已实际用GPU；不能推广成全阶段加速比。遮挡任务还含可见mask/target组装和decoder，hostCPU与wall接近提示有host开销，但**没有kernel/分项profile，不能定量归因或声称GPU利用率瓶颈已定位**。47,488MiB设备总显存下，已记录窗口峰远小于75%准入线；整个QA绝对峰及完整数据最大显存未测。

GPU main内层 **7.789756511wall / 5.711669736CPU s**；完整外层 **10.625067532wall / 7.571459CPU s**，峰单进程RSS **1828316KiB**。与12s容器窗口、CPU提取的Condor整数资源口径分开。独立外层CPU只加14.710458+7.571459=**22.281917s**；source/内层不再相加。实耗、投影、未测口径见 [resources.json](stage106_energy_ml/resources.json)。物理EOS网络、GPU busy time/利用率、平台准入及全会话/打包编辑CPU未测。

### 4.3 冻结准入的实际结果

|准入量|固定公式投影|上限|结果|
|---|---:|---:|---|
|GPU任务wall|15468.536714958s|7200s|拒绝|
|GPU任务hostCPU|14573.877055920s|作为总CPU分项|保留|
|完整提取+reserve CPU|8118.720840197s|作为总CPU分项|保留|
|总CPU|22692.597896117s|21600s|拒绝|
|已记录QA窗口allocated峰|361.045898MiB|设备47488MiB的75%|通过|

GPU公式为 `max(measured GPU batch F/B) × ceil(46575/256) × 620 × 3 + 600`；620=3×200监督epoch+20预训练epoch。GPU hostCPU用相应最慢批CPU外推；与正常提取+reserve相加。该固定规则把最慢任务代价用于全部epoch，较保守，**不代表实际三阶段和20epoch都必须用同样代价**。没有在看到结果后换更宽松公式；推测实际早停较快也不能替代准入。具体未舍入值见 [admission.json](stage106_energy_ml/admission.json)。

根据合同，未提交train_extract、fit、test_extract、infer或risk作业，没有完整坐标、学习曲线、offset或新点表可供评价。原1.05/1.01/1.03、八层三向tail相对direct上95≤2pp仍保持，当前未新增任何通过证据。

## 5. 实际命令、收集与存储

```bash
python3 ml/package_stage106.py package qa_extract
condor_submit AnalysisZipFramework/submission/ml_stage106.sub
python3 ml/package_stage106.py collect qa_extract
python3 ml/package_stage106.py package qa
kubectl create -f AnalysisZipFramework/submission/ml_stage106_qa_kubeflow.json
kubectl logs -n xcheng job/nu-mu-energy-stage106-qa --tail=35
python3 ml/package_stage106.py collect qa
```

实际batch入口为 `timeout ... python -u ml/time_stage106.py qa_extract` / `qa`，其子进程执行几何提取或CPU/GPU probe；本地只标准库打包。独立计时见 [time_qa_extract.json](stage106_energy_ml/time_qa_extract.json)、[time_qa.json](stage106_energy_ml/time_qa.json)。提交目录统一 `~/condor/nu_muAnalysis/stage106/`，未新建home根spool；其他项目未改动，原Stage54五项保持。

两个实际输入包分别 **1131077 / 37190609 bytes**，在scratch计算，收集时逐文件核原输入/源码字节一致，分别516/530文件；不用SHA。传输与验证记录合并去重为 [transport_validation.json](stage106_energy_ml/transport_validation.json)，减少共同Python依赖清单的重复。核验后删除两输入/结果传输包和36876bytes QA坐标，只保留代码、配置、紧凑schema/成本/QA/终态证据；不保留点云或逐边数组。最终体积及删除明细见 [storage.json](stage106_energy_ml/storage.json)，≤20MB。未推送。

## 6. 对持续目标的逐项完成审计

本轮继续检查了 Stage103 §2–7、路线当前条目、Stage104优化/全部gate、Stage105实际QA、Stage106实测与stop，以及 Stage85实际读出控制、Stage66旧训练外响应、Stage98/102研究/决定。完整逐要求证据和下一所需输入见 [completion_audit.tsv](stage106_energy_ml/completion_audit.tsv)。

|目标条目|当前证据|状态|
|---|---|---|
|固定q点动作与停止规则|Stage104唯一优化/原全风险；共同门槛失败|有限实验完成，未恢复最终目标|
|完整点坐标/局部图/遮挡输入可交付|Stage10537/40、原全点/边、泄漏QA|可行性完成|
|一次三格的程序/资源准入|本轮实测probe；资源拒绝，0optimizer|按stop完成有界尝试|
|C/A点收益、B解释、三fit/预训练|未准入，未测量|未完成能量比较，不称阴性|
|独立低能/过渡与同低pz真高E支持|现有原池已使用，未交付新的独立样本|未完成，需新谱系/提议密度及pilot实际支持|
|真实response/interaction/FSI/材料/Calo/接受度/背景|Stage85条件控制及旧开发压力不等于系统认证|未完成|
|真正未开发来源确认与完整source/refit/系统/研究选择|当前开发test及条件incoming区间不能证明|未完成|
|原最终联合能量/双向尾门槛|Stage102/104已有候选未过，本轮无新风险|未达成|

因此**不能把整个用户目标标记complete**，也不能将成本stop改写成“已完成低能重建”或“目标不可实现”。这次是实质进展：有真实GPU/CPU测量并按冻结规则结束当前合同；持续目标仍保留active，物理终点未交付。

## 7. 下一步边界和具体所需输入

当前没有默认新训练/metadata搜索任务，不重复Stage85条件活动或Stage104动作族；不把没有新样本泛化为一切开发都必须停止，停止的是本次具体资源合同。若后续有明确修订的可执行合同，仍须在任何optimizer前另冻准入，不能无声续本轮三fit。当前没有自动申请更多GPU时间、换seed/深宽/预训练任务或缩短训练来回避失败。

要完成物理终点，至少需逐项交付并核验：

1. **独立支持和确认**：新source/incoming生成谱系、与现有池不重叠的证明，真50–100/100–200GeV及相同pz真≥200/high-y反例、原物理接受度/高端控制；生成提议密度与权重、选中pilot产额/成本和真正未开发locked确认角色。数量/功效未测，不机械指定几千个或重新随机拆旧池充数。
2. **可标定的读出/response**：实际IOV和逐事件DAQ有效mask/coverage、无偏quiet/random触发或等效校准、可与PHYS身份联结的真实变体；Stage85已测2048data+2048MC只能给条件活动，110592是名义分母。不能由其raw比值或noise-on/off全差造1σ噪声变体，也不能用100–1000GeV单μ认证50–100GeV ν/shower。
3. **interaction和完整系统评价**：原incoming可联结的GENIE/FSI、材料/输运、Calo/读出等有依据变体及原选择分母、接受度/背景样本；不能把重权/模板替换等同真实变体。随后才在固定策略上交完整风险/尾/概率（若有定义）和选择迁移。

这些是未交付证据的最小具体类别，不是本轮已测结果或生产授权。没有输入时保留精确缺口，不延长旧REC定位链，不凭几例异常下物理结论。路线历史只追加§88、信息计划§68，下一Prompt转为证据交接及有新输入时的验收入口，Stage54原后缀逐字保留。先本中文报告，再相关代码/配置/紧凑证据一次本地Conventional Commit。
