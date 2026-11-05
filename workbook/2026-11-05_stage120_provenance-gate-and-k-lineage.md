# Stage120：扩样 producer 认证门与 K 样本谱系核查

日期：2026-11-05。依据路线图 §101 和 Stage119 报告 §7，先解决“新增低能样本是否可以作为独立支持”的身份问题，再决定是否购买下一批训练规模。本阶段只做已冻结输入的目录元数据与保留 producer 日志审计；没有读取 ROOT 事件数组，没有训练、推理、拟合、重建、数字化或新 GENIE/G4 生成。所有批处理通过 HTCondor，阶段提交目录为 `~/condor/nu_muAnalysis/stage120/`。

## 阶段目标

1. 认证扩样 run 200131–200136 是否保留足以证明 producer、EVNT、release、seed 和 parent 身份的证据。
2. 核对 200187 和 200188 的 K 输入是否为独立 EVNT 家族；不能按 run 编号或 c1/c2 文件名自动认定独立。
3. 在身份门未通过时，停止把这些记录当新的训练或确认样本，并给出下一阶段所需的最小输入。

## 工作内容与输入

批任务 `9668991.0` 读取以下已归档输入和 EOS 目录元数据：Stage119 的 `production_evidence.json`，以及 `/eos/experiment/fasernu-data0/faser/sim/mc24/genie/{200131..200136,200184..200189}` 下 `bck/phy/rdo/rec/sim/log` 的目录和文件名。审计程序为 [stage120_provenance.py](../ml/stage120_provenance.py)，提交描述和 worker 为 [ml_stage120_provenance.sub](../AnalysisZipFramework/submission/ml_stage120_provenance.sub) 与 [run_stage120_provenance.sh](../AnalysisZipFramework/submission/run_stage120_provenance.sh)。首次提交 `9668988.0` 因提交目录未放置 worker 而以 exit 127 结束，未运行分析；修正后任务首次启动即 exit 0。两次记录都保留在本阶段日志目录。

## 实测数据

### 1. 扩样目录存在，但 producer 身份仍不能认证

12 个目标 run 的 `s0014` 目录均存在。200131–136 的实际文件计数如下；计数包括目录内的 `missing_files.txt`（200131 的 `phy` 因此为198，而有效 PHYS ROOT 文件为197）：

| run | 成分 | bck | phy | rdo | rec | sim | log |
|---:|---|---:|---:|---:|---:|---:|---:|
|200131|π c0|197|198|197|197|0|0|
|200132|π c1|196|196|196|196|0|0|
|200133|K c0|176|176|176|177|0|0|
|200134|K c1|178|178|178|178|0|0|
|200135|K c2|178|178|178|178|0|0|
|200136|charm central|133|133|133|133|0|0|

六个扩样 run 的 `log/s0014` 均没有保留日志。因此文件名确认了下游产品的 run、成分、crossing tag 和 `s0014`，但不能从现有证据确认 producer release、EVNT entry/skip、随机种子、完整 parent 链或与旧曝光的生成家族关系。认证结果为 **0/6 producer runs**，不是“六个 run 都独立”。完整结果见 [provenance_audit.json](stage120_energy_ml/provenance_audit.json)。

作为对照，200184–189 的下游目录均有 `bck/phy/rdo/rec/sim/log`。其 log 文件数分别为 2535、2535、2314、2288、2275、1651；这些日志包含 `Calypso-22.0.49`、`OFLCOND-FASER-04` 和 `TI12MC04` 等记录。这个对照说明审计程序能够看到保留日志，但不能替代 200131–136 缺失的 producer 证据。

### 2. 200187/188 不是已认证的两个独立 K 家族

保留的 generator 日志都报告 `Nevts: 1000`、`Remaining: --geom TI12MC04`、release `/afs/cern.ch/work/f/fasermc/mc24/s0014`。关键的 `Input File` 为：

| run | 文件输入 |
|---:|---|
|200187|`.../fasernu_100_iab_downstream_samples/epos-k-1-24-xing-100iab.EVNT.pool.root`|
|200188|`.../fasernu_100_iab_downstream_samples/epos-k-1-24-xing-100iab.EVNT.pool.root`|

两个输入集合逐字相同。因而本阶段的 K 独立性门为 **false**：200188 虽然输出文件名含 `c2`，不能据此称为独立 c2 家族；最保守的解释是两个 run 都来自同一 `epos-k-1` EVNT 输入，仍需 entry/seed/job 分块证据才能判断是否是独立响应重放。Stage119 的 200187/188 记录因此继续排除在“新增独立训练 N”和确认样本之外。

## 阶段结论

本阶段确认了一个程序事实和一个物理统计事实：目标目录确实有下游产品，但扩样的独立性证据不完整；200187/188 的保留日志反而直接显示相同 K EVNT 输入。故不能因为目录文件数量大或 run 名称不同就扩大训练集、开放 reserved 或宣称新 blind。Stage119 已测的学习曲线和 JEFF/名义条件环境比仍然有效，但其 source/parent 混合不能在本阶段被重新解释为因果响应效应。

本阶段没有测量新的能量风险、oracle→代理增量、系统不确定度或独立确认功效；这些项目明确标记为“未测量”。

## 资源、验证与产物

成功任务 `9668991.0` 使用 2 CPU、4 GB 请求，远程 user+sys CPU **0 s**（粒度取整），远程 wall **4 s**，exit 0；初次 worker 路径错误 `9668988.0` 使用远程 wall **1 s**、exit 127，没有执行分析。返回包 `ntuples/energy_ml_stage120/provenance_result.tar.gz` 为 **2,807 B**，收集后与成员字节逐项核对；审计 JSON 的运输记录见 [provenance_transport.json](stage120_energy_ml/provenance_transport.json)。

验证通过：Python AST 解析、worker `bash -n`、stage120 JSON 解析和 12 run 目录快照均通过；没有保存 ROOT、HITS、RDO、xAOD 或事件数组。Stage119 的原始特征政策（一次方动量只用 pz0、raw11、typed NaN、合法 signed 负值、Calo 缺失传播）和原角色/K/最终门槛没有修改。

## 下一阶段计划

1. 向 producer/样本维护方取得 200131–136 的原始生成子作业、EVNT 输入、entry/skip、seed、release、geometry/calibration 和 parent/incoming 映射；验收是六 run 中至少能对每个被纳入的文件建立可核 parent 身份和旧曝光交集，而不是只有文件名计数。
2. 对 200187/188 取得同一 EVNT 输入的 job 分块与 seed/entry 范围；若不能证明独立重放，则保留为单一 K 家族的响应诊断，不进入新增训练 N。
3. 在上述身份门通过后，再对 JEFF 最低能共同支持做同 parent、材料/深度、完整末态和数字化条件的成对核查；在输入门未通过前不重训、不增加树/seed、不开放 reserved，也不启动全量新 G4/GENIE。
