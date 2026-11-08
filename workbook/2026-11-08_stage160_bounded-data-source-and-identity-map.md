# Stage160：有限实际data源定位与原生身份索引

## 阶段目标与冻结范围

执行[Stage159下一合同](stage159_energy_ml/next_execution_contract.json)，[protocol](stage160_energy_ml/protocol.json)保留原文。Stage159原REC前64身份不在PHYS范围，本阶段另定义指定PHYS原前64行的控制父集；不替换或改写Stage159的0/64，不按电荷/动量/质量选父。

固定候选为run15838、r0022 REC00005/00006/00007/00008四个精确路径，另REC00000原前4作独立reference；完整路径见protocol。文件号邻域仅由已测PHYS最小event787406与已知REC00000条目124391的近6.3启发，不是范围认证，不广扫目录、不在失败后补路径。先实际metadata/schema和各候选首尾EventInfo；只有唯一候选覆盖全部64目标event/Unix timestamp才前1024成本pilot，准入才全源EventInfo扫描。不存在/不支持/歧义/未匹配保留，不假设entry=event−1。

## 执行前成本口径修订

[事前成本修订](stage160_energy_ml/execution_cost_amendment.json)在任何新候选数据读取之前冻结。只用observer execute CPU会漏掉相邻事件间的POOL conversion/框架工作；因此记录每次execute入口process CPU，舍弃含首execute/lazy初始化的第一边界间隔，用后续完整事件边界间隔的均值/总和作steady项；execute-only仍单列。

准入：`3*(GNU pilot CPU − steady完整事件间隔CPU总和 + 实际源N×steady完整事件间隔CPU均值)`，加实际已用scheduler CPU和200 audit预留，须≤2000 CPU秒。预算/阈值/候选/父集不变；这修正的是执行前成本定义，不是看到新源结果后改门。所有ROOT/元数据/数组/匹配/成本统计在HTCondor，客户端仅文本/运输/调度。提交目录`~/condor/nu_muAnalysis/stage160/`，2核/8GB、最多1job，无应用wall超时、无GPU/G4/重建/ν forward/能量fit。

## 实测结果与验证

实际首尾读取与原reference4通过。固定四候选全部存在，实际范围如下（同run15838；Unix timestamp单位s）：

| REC后缀 | 实际条目N | event首–尾 | timestamp首–尾 |
|---|---:|---|---|
|00005|118556|610162–728717|1720449517–1720449598|
|00006|118505|728718–847222|1720449598–1720449674|
|00007|118497|847223–965719|1720449674–1720449750|
|00008|118504|965720–1084223|1720449750–1720449826|

唯一locator为00006，实际TagInfo为Athena24.0.41/FASERNU04/OFLCOND05。端点只用于定位，不认证全源单调或被排除文件无相同身份。

前1024顺序pilot实际event728718–729741，首身份与header完全相同。observer首execute59.289264CPU秒，steady完整事件间隔1022个、合1.318803353CPU秒，均值0.001290414240CPU秒；native内部80.168636CPU秒/159.832480wall秒，ROOT11860596B，RSS1534532KiB。GNU总CPU84.71秒，含startup/首末及未被steady项覆盖的base83.391197秒。全118505三倍预测708.935208CPU秒，加当时已用181和200audit=1089.935208<2000，准入通过；这是预测，不是全源实测。

首次header科学读取已成功，但JSON决策误把reference字段中括号说明并入路径，作业9675360.0 exit1。修复为精确Stage159缓存路径后，9675369.0仅重做JSON决策，不重读ROOT。失败/原版本/成本全部保留。pilot9675375.0和admission9675386.0均exit0；全源9675390.0 exit0：118505原生条目完整读完、event728718–847222；原1024prefix逐值复现。目标64父全取得唯一source内native匹配和唯一完整PHYS索引，64/64timestamp相同，无父替换。实际映射见[manifest](stage160_energy_ml/matched_manifest.json)。全源native内部269.285714CPU秒/322.563426wall秒，GNU275.11CPU秒/332.32wall秒，ROOT24620068B、RSS1544940KiB；完整间隔118503个、均值0.001574673645CPU秒。未把native execute-only的67.537768秒冒充全源CPU。原三倍成本预测仍覆盖实际，未以实际结果重调门。

独立actual-entry身份复核9675408.0 exit0，真实重读全部64映射entry，run/event/native timestamp全同。不是只对缓存作同算法重复，也不推断全球所有REC身份独立。GNU65.23CPU秒/169.81wall秒，ROOT11782732B，RSS1581044KiB。

全阶段6job/6starts，含已修复header决策失败的529 scheduler CPU秒/877聚合execute wall秒；0live，无GPU/G4/重建/新ν/能量fit。提交2CPU/8000MB，CERN实际Request3CPU/9000MB包含传输资源，不能称科学算法用满3核。资源分项见[审计](stage160_energy_ml/resource_audit.json)，嵌套GNU/native CPU不再加到scheduler。最大已报告native/GNU RSS1581044KiB；不把未求值ClassAd MemoryUsage当实测峰值。

事件文本按原文合并并回读相同，胶囊`ntuples/energy_ml_stage160/event_records.json.gz`13773B；代码各版本/完整GNU/作业日志精确归档`software/stage160/`后删除276603B重复包/文本/日志，见[清理记录](stage160_energy_ml/storage_cleanup.json)。原四份完整native审计精确合并`software/stage160/native_audits.tar.gz`，保留紧凑时序/资源JSON与原文archive定位，消除重复schema/metadata；manifest仍保留actual TagInfo。无持久ROOT或波形样本复制。

```bash
python3 ml/stage160_ops.py submit --phase headers
python3 ml/stage160_ops.py collect --phase headers
# 只在唯一locator成立后：pilot -> admission -> 被准入full -> 独立audit
python3 ml/stage160_ops.py finalize
```

新代码为`ml/stage160_targets.py`、`stage160_native.py`、`stage160_decide.py`、`stage160_ops.py`及stage160 worker。输入只复制极小Stage159身份reference；不复制REC/PHYS/xAOD。逐阶段immutable包、实际失败及scheduler成本均保留；全量首1024需逐值复现pilot，实际匹配native entry另作独立原生读取复核。

## 阶段结论及下一步

实际唯一locator/成本准入/全118505身份扫描/1024prefix复现/64父逐entry独立复核全部通过。现在已取得同源真实身份到entry map；Stage159原64无配对结论保持，不认证native状态/PRD/raw producer等价或data纯度/FPR。WaveformHit容器存在不证明完整ADC samples；CaloHi/Lo物理通道和增益映射需后续另冻。原Stage87/所有原门/全部K/原角色/隔离/typed/raw/status/pz0规则保持，整体goal active。[下一Stage161合同](stage160_energy_ml/next_execution_contract.json)已在payload执行前冻结：同PHYS原4→成本及raw支持通过才64→独立原4；安全直读actual v1 aux绕开空time-vector转换器风险，逐event actual cable map/LoHi命名/id32/raw峰值/RMS/status及两份stored tracks/fullcov/PRD；2000累计CPU秒、600pilot/200audit，不merge/refit/GhostBusters。wave/time只存结构长度，非0status不提供timing，不推断ADC code或纯度。验收为身份保持、raw按float32精确、前4复现和实际资源/缺失审计；失败不换父/调门。Stage136/140有限MC工作模型结果已完成，下一不重复toy；真实相关系统/曝光GRL/背景/全生成接受度/乳胶/独立确认仍缺。

本阶段先完成中文report及文本/资产验证，再代码/小表/路线本地Conventional Commit，不push。
