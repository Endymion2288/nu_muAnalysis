# Stage161：实际data原生读出／轨迹一致性

## 阶段目标与冻结条件

承接[Stage160合同](stage160_energy_ml/next_execution_contract.json)，仅同PHYS原前64控制父：原前4pilot，实际raw/物理ID及成本全通过才64，随后独立原4。没有按电荷、轨迹质量或pz换父。本阶段因ID门失败停于原4，**未执行64或repeat**；不是能量模型实验，也不认证真实data纯度或FPR。

精确输入及真实entry见[manifest](stage161_energy_ml/matched_manifest.json)：

- REC：`/eos/experiment/faser/data0/rec/2024/r0022/015838/Faser-Physics-015838-00006-r0022-xAOD.root`。
- PHYS：`/eos/experiment/faser/data0/phys/2024_back/r0022/015838/Faser-Physics-015838-00000-00049-r0022-PHYS.root`。
- 实际TagInfo为Athena24.0.41/FASERNU-04/OFLCOND-FASER-05；复用Calypso d32b0ff3现成构建，CONDBR3，仅读已有forward/backward WithoutIFT两轨迹集合、first state/full5×5 covariance和真实PRD，不merge/GhostBusters/fit/reco。

旧v1→current转换器直接调用`time_vector()[0]`，故本阶段用TTreeReader直读actual `WaveformHitAuxContainer_v1`和旧interface，绕开转换器。保存raw_integral/50 pC、raw_peak/baseline/RMS mV、channel/id32/status/secondary与wave/time向量长度；**未读取采样内容或time-vector值**，非0status无localtime。非空向量只证明保存的mV/ns窗口结构存在，不认证原始ADC codes或全采集窗。

## 实测结果与物理含义

[完整结果](stage161_energy_ml/summary.json)、[逐路支持](stage161_energy_ml/pilot_raw_support.tsv)、[独立ID诊断](stage161_energy_ml/identity_diagnostic_summary.json)给出：

| 量 | 原4父实测 |
|---|---:|
| 身份精确 | 4/4 |
| 每父映射读出 | 24路（12Calo、12scint，含额外Veto11） |
| primary缺失／歧义 | 0／0 |
| raw charge、raw peak、baseline RMS、status逐字段float32精确 | 384/384 |
| 独立struct.pack标量float32复核 | 384/384 |
| 波形／时间向量非空且长度相同 | 96/96 |
| 空wave／空time向量 | 0／0 |
| 非0status视图／该类提供timing数 | 45／0 |
| 合法负raw | 0（策略保留负值，不据本例推广） |
| physical id32相同 | 52/96 |
| 后向long轨迹计数／pz0向量／全state向量精确 | 各4/4 |
| 前向计数／pz0向量／全state向量精确 | 2/4、0/4、0/4 |
| 最大leading pz0差，后向／前向 | 0／196.44459375 GeV |
| 两集合共long轨迹／真实measurement链接 | 6／104/104 |
| full5×5 covariance有限、对称、正定 | 各6/6 |
| PHYS轨迹控制选择／其中pz0[50,100)GeV | 2/4／0 |

后向一致是本次实测，不按结果选择集合或认证历史writer配置；前向不同不等于tracking bias。PRD链接和正定性不认证关联后验、pull或覆盖。控制选择不是μ纯度认证。

### 闪烁体ID差异：固定编码证据，而非丢hit

[逐ID表](stage161_energy_ml/identity_diagnostic.tsv)显示12路Calo各4/4相同，Veto10亦4/4；其余11路scint各0/4。例：channel4/VetoNu的stored `0x70000000`而当前map `0x58000000`；channel15/Veto11为`0x44000000`对`0x40800000`。所有raw数值依然精确，不能将差异解释为原波形缺失。

[生产日志摘录](stage161_energy_ml/producer_dictionary_excerpt.json)确认原producer读取`ScintIdDictFiles/IdDictScintillator.xml`。[源码证据](stage161_energy_ml/dictionary_source_evidence.json)显示同名默认文件于2025-06及2025-08扩展（Muon、VetoGm等）；pinned[2024候选](stage161_energy_ml/IdDictScintillator_2024.xml)与a443e427扩展前默认XML逐字节相同，而[当前默认](stage161_energy_ml/IdDictScintillator.xml)不同。**固定的ID位模式差异与字典演变相容，尚未实际用旧字典解码，故未将其写成已经认证的唯一原因。** 原生产字典payload字节亦未取得。不能仅因geometry/tag字符串相同就认证历史identifier解释。

原ID门保持False。下一工作是检验一个源码指定的历史字典，不能在本阶段忽略ID继续64或扫多个layout。相比未知物理响应，这已有具体程序／格式机制可检验。

## 技术修复、条件与验证

所有失败均留原源码包和日志，预算不重置：

| 作业 | 结果及修复 | scheduler CPU／wall（秒） |
|---|---|---:|
| 9675424.0 | Cling ElementProxy推导失败，改官方显式旧hit指针 | 31／43 |
| 9675433.0 | standalone缺Athena/Gaudi符号，显式加载现成库 | 18／34 |
| 9675443.0 | 首raw返回后manifest误用entry，改PHYS_entry | 18／39 |
| 9675450.0 | 已写raw4，cppyy string摘要JSON失败，显式str | 21／181 |
| 9675458.0 | raw成功、native前SQLite副本被veto | 30／135 |
| 9675478.0 | 只读条件探测、复用已计费raw4、native及比较成功 | 130／165 |
| 9675517.0 | 仅已有JSON/TSV独立标量诊断，成功 | 0（scheduler取整）／5 |

详见[修复记录](stage161_energy_ml/implementation_repair.json)。最后诊断GNU为0.04CPU秒/0.05wall秒，不将scheduler整数0当无实际成本；还独立证明早期已保存raw4与成功raw4完全相同，没有新增父。

原REC生产日志确认SCT/TDAQ/DIGITIZER/LHC/TRIGGER/GLOBAL用CONDBR3，DCS单独OFLP200，见[连接证据](stage161_energy_ml/producer_conditions_evidence.json)。失败来自Athena data默认`DBReplicaSvc.COOLSQLiteVetoPattern=/DBRelease/`拒绝FASER只读SQLite。实际[副本探测](stage161_energy_ml/conditions_replica_probe.json)确认ALLP200_261030.db内CONDBR3的Tracker/Align tag05解析TRACKER-ALIGN-05；CABP200_261028.db内CONDBR3的CableMapping为SINGLE_VERSION。仅关闭副本veto，不切MC库/geometry/tag；2026快照不冒充历史payload逐字节相同。

## 资源、命令与产物

原预算2000累计CPU秒、pilot600、audit200，2核8GB、最多1job、无app wall timeout。原三倍64投影raw51.11292958CPU秒/native331.898370726CPU秒，预算充分但**physical ID门False**，没有放宽。完整资源见[resource_audit](stage161_energy_ml/resource_audit.json)：7job/7start、5失败全部计入，248 scheduler CPU秒、602聚合execute wall秒、0live；CERN实际Request3核/9000MB含传输资源，不能当3科学核已用。0GPU/G4/新ν/自然ν或隔离forward/能量fit。小规模顺序读取无需GPU。

成功raw进程GNU16.16CPU秒/110.43wall秒、RSS775692KiB；native110.10CPU秒/125.79wall秒、RSS1897956KiB。内部计时分别12.427639021/104.835912677CPU秒，ROOT读2440448/7326384B；PHYS读2324395B。首native execute60.226780043CPU秒；两个steady完整间隔合计0.013758494秒、最大0.008539824秒，不能把lazy启动当steady成本或声称受控加速。

```bash
python3 ml/stage161_ops.py submit --phase pilot
# 原4内的技术修复phase见不可变submission.json；每次monitor后才提交
python3 ml/stage161_ops.py submit --phase identity_diagnostic
python3 ml/stage161_ops.py collect --phase identity_diagnostic
python3 ml/stage161_ops.py finalize
```

所有ROOT/事件数组/统计在`~/condor/nu_muAnalysis/stage161/`执行。本地仅源码/文本、调度和精确归档。事件原文胶囊`ntuples/energy_ml_stage161/event_records.json.gz`为14767B；source_snapshots、worker_logs、execution_audits、comparison_tables在`software/stage161/`，逐member/原文回读相同后删543682B重复。见[清理审计](stage161_energy_ml/storage_cleanup.json)。无持久ROOT/采样数组；Stage54用户资产size/mtime核对保持，home根无旧nu_mu_stage目录。静态Python AST/bash、冻结合同逐字节核对、Git diff检查和资源终态核对通过，见completion_checks。

## 阶段结论与下一步

本阶段建立4实际data父的raw数值、后向状态及非空stored-window支持，但ID解释未过原门，有限结束此默认字典实现，不能称64已认证。低能ν改善、纯度/FPR、covariance覆盖、gain/time校准、完整producer迁移**未测量**。Stage87保持；没有新的可部署模型通过原联合门。

[Stage162冻结合同](stage161_energy_ml/next_execution_contract.json)用唯一源码指定2024字典做兼容性检验，并读取实际stored mV窗口内容，验证signed样本积分/peak与原raw闭合。原4→成本及ID/内容通过才原64→独立原4，2000CPU秒、同geometry04/tag05/CONDBR3和cable payload，禁止改hit ID或放松门。内容如只含原重建窗，不宣称全采集窗/迟到能流；失败不换父/布局网格。需先由源码冻结数值累计误差界与实际字典解析证明。

随后回到Stage132的真实联合响应及新可测能量问题，而非将小工程步骤当最终目的；实际Calo raw/window相对X62的新内容须排查既有工作后另冻能量比较。Stage136/140有限MC工作模型及3000toy点覆盖已完成，不重复；真实相关外部约束、乳胶、GRL曝光、背景／全生成接受度和独立确认仍缺。pz0-only、允许px/py/q/p/弯折、raw11、typed占位、合法signed负值、Calo缺失、status0 timing、全部K、原角色/reserved、原所有门及Stage137双低箱5%门保持。整体目标未完成。
