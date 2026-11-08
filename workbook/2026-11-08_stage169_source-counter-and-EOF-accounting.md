# Stage169：保留来源计数、EOF与全生成分母边界

## 阶段目标与冻结输入

承接Stage132§6全生成接受度路线和[Stage168合同](stage168_energy_ml/next_execution_contract.json)，在Stage168提交`6b85473`之后执行。Stage168已经测得22份EVNT合11229101条，source508的请求90000+10000超实际EOF94877；原native实际scanned4877。现在用已有source-evidence和16原native摘要核实际parent/truth-superset/selected账目，不重复事件生成、读ROOT或重建。

[协议](stage169_energy_ml/protocol.json)为原合同精确副本，[冻结列表](stage169_energy_ml/inputs.json)给原666完成来源、原16pilot及字面输入路径。pilot使用原16，不为EOF、低产额或易读性换源；full最多原666账目和1134历史source声明。只解压一次`workbook/stage130_energy_ml/source_evidence.json.gz`，读取request_summary/source_qa/parentmap的标量摘要及原16份`workbook/stage130_energy_ml/parentlink_<index>.json`；不打开pilot_complete_parents、parentmaps事件记录、NPZ/模型数组或RAW/RDO/REC/EVNT载荷。

filename段按原1000-event块约定产生明确标为claim的候选区间，用实际EVNT N截到EOF。只有16 source的实际保存命令核边界；其余source的名字/计数相等仍不作全部未选事件身份/处理成功证明。原角色、nominal/alternative、eligible/old_locked分开，不将研究支持限制当物理拒绝效率。

## 执行与验收

所有科学JSON/gzip解析、计数和区间运算均走HTCondor `~/condor/nu_muAnalysis/stage169/`。提交2CPU/4000MB、max1job，300累计CPU秒分pilot60/full120/audit120，MaxRuntime86400s，无应用短timeout。元数据小，一次读取而非每source重复解压；此任务GPU加速与更多线程的收益未测量。先完整16pilot GNU CPU三倍投影至666，加实际已用/120audit reserve准入；物理计数矛盾作为结果保留，不以此删source或改预算。

full核逐source、run/component/role分组、原666行selected表与保存总数，另算1134历史与666完成source声明区间并集。独立audit从原缓存另取scalar、另用扫描线区间算法和表格验证，核source508实际4877；计数相等不认证全部未选事件身份。无接受度比值、物理weight/prior、模型fit/forward、G4/数字化/重建/新独立ν，不重建pinned Calypso。

Stage87、原全部门/Stage137双箱5%门、pz0-only一次方动量和允许px/py/q/p/弯折、raw11、typedNaN/合法signed/status0-only timing/Calo缺失、pz>50GeV、全部K、原角色/reserved/quarantine保持。

```bash
python3 ml/stage169_freeze.py
python3 ml/stage169_ops.py submit --phase pilot
# 成功和成本门后才full
```

```bash
python3 ml/stage169_ops.py collect --phase pilot
python3 ml/stage169_admit.py
python3 ml/stage169_ops.py submit --phase full
python3 ml/stage169_ops.py collect --phase full
python3 ml/stage169_ops.py submit --phase audit
python3 ml/stage169_ops.py collect --phase audit
python3 ml/stage169_finalize.py
```

上述命令逐项执行，所有科学运算在worker完成。最终归档只执行一次，不重复清理。

## 实测账目与物理边界

[全量摘要](stage169_energy_ml/full_summary.json)、[666行逐来源表](stage169_energy_ml/source_accounting.tsv)、[分组表](stage169_energy_ml/grouped_counters.json)及[证据边界](stage169_energy_ml/accounting_evidence.json)给出：

| 项目 | 实测记录数 | 含义 |
|---|---:|---|
| parent / full-parent | 6606398 / 6606398 | 两份实际处理账目相等 |
| truth-superset | 1048904 | 原truth选择口径 |
| selected | 222515 | 原selected表及链接计数闭合 |
| 文件名声明请求 | 6660000 | claim，不能作成功处理量 |
| 声明截到实际EVNT EOF后 | 6606400 | 比实际parent多2条 |
| 原16 native实扫 | 154877 | 16/16等于各自实际可用范围 |

666/666来源满足计数非负、parent≥truth-superset≥selected、QA/full-parent相等、selected表及链接数相等。664/666的parent等于按文件名声明并截EOF后的长度。两处差异均在实际EOF以内，原因**未测量**：

| source index | run / 成分 / 原角色 | 声明区间（左闭右开） | 声明可用 / 实际parent | truth-superset / selected |
|---|---|---|---:|---:|
| 652 | 200092 / K / train | [340000,350000) | 10000 / 9999 | 1453 / 364 |
| 1046 | 200098 / K / cal | [480000,490000) | 10000 / 9999 | 1476 / 376 |

不删这两个父来源、不改原总数，不将各少1条解释为已知G4失败、物理损失或EOF。12个完成source的声明被EOF截断，原请求合120000条，实际parent合66400条。source508仍为原scanned4877、truth-superset363、selected91，和Stage168测得的EVNT N94877及原skip90000一致。

| 原角色 | 来源数 | parent | truth-superset | selected |
|---|---:|---:|---:|---:|
| train | 470 | 4649763 | 738662 | 156318 |
| test（已开发使用） | 95 | 948046 | 150064 | 32147 |
| cal | 101 | 1008589 | 160178 | 34050 |

[历史范围声明](stage169_energy_ml/range_claims.json)覆盖1134来源，声明并集11229101条，恰好覆盖22个EVNT条目区间；这只是filename claim覆盖，不能认证实际逐事件处理。完成666来源的声明并集6606400条，未被其声明覆盖的生成记录4622701条。历史来源分nominal298、eligible alternative666、ineligible alternative170；nominal及old_locked/原角色等支持限制不能当物理拒绝。全未选事件身份、逐生成成功/失败/过滤账目、物理权重及曝光仍未认证。本阶段**没有计算selected/N接受度**，也没有取得完整全生成接受度。

## 验证、资源与存储

[独立审计](stage169_energy_ml/independent_validation.json)重新从原标量输入核666行、16native/log边界、22run扫描线区间并集、分组表及source508，全部通过；零ROOT/事件数组读取。16pilot与full逐值一致。冻结协议/phase输入及文档历史的精确字节验证见[文档验证](stage169_energy_ml/document_validation.json)。

[调度账目](stage169_energy_ml/scheduler_accounting.json)记录pilot9676486.0、full9676497.0、audit9676503.0，3提交/3start/均exit0/0live。schedd粗粒度CPU为0秒、聚合execute wall14秒；这不是零成本。完整GNU计时如下（不与schedd累加）：

| phase | CPU秒 | wall秒 | 峰值RSS KiB |
|---|---:|---:|---:|
| pilot | 0.37 | 0.38 | 40096 |
| full | 0.46 | 0.51 | 40364 |
| audit | 0.37 | 0.38 | 40612 |

pilot GNU CPU三倍投影至666为46.20375秒，满足预算及audit预留后才准入full。提交描述为2核/4000MB；实际schedd RequestCpus=2、RequestMemory=6000MB，未qedit，具体调整策略未测量。此次小元数据任务没有受控多线程/GPU加速比测量；新G4、独立ν、fit、forward均0。

[存储清理](stage169_energy_ml/storage_cleanup.json)最终12份账目元数据239411B，小于4MiB限额；删除1414162B运输、日志和spool重复。源119逻辑版本按内容唯一存50份，`software/stage169/source_snapshots.tar.gz`为479620B，经`source_versions.json`索引可逐字节恢复；GNU/archive660B、terminal spool2319B、worker logs1325B。清理前核全终态及无队列Iwd引用，提交目录仅留execution_index。无新ROOT/xAOD/事件数组/模型，无SHA；Stage54原12文件size/mtime保持。

## 阶段结论与下一步

本阶段把“请求10000”与“实际成功账目”分开，确认原666总数和selected计数闭合，明确12个EOF尾段及两处未知的1条差异。不能由总数相等补足全生成接受度、权重或曝光。Stage87、原完整验收门、原角色/K/reserved/quarantine保持，低能可部署优越性和整体物理精度目标仍未完成。

下一实验转向Stage132§5.5/§6真实联合读出约束，避免继续无限metadata核查：先冻结run15838已知RAW00400严格TLB随机触发的有限pilot。输入为Stage43已读RAW字面路径、原56普通PhysicsTag ADC reference、官方EventFormats/TLB decoder和已取得GRL；核实际触发帧/CRC、身份、四CaloNu ADC逐值回放、全部实际硬件通道支持、时间GRL、随机控制数量及实测成本。验收前不扩文件/全run、不做能量模型或噪声注入。严格随机不自动等于纯电子噪声；若联合控制足够，再另冻有限联合统计合同。该新pilot及联合协方差、gain/time/信号污染与data迁移均**未测量**，Stage170尚未执行。
