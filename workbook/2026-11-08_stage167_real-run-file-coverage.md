# Stage167：真实run15838文件目录与处理完整性的证据边界

## 阶段目标与冻结范围

承接Stage132§6的实际输入路线和[Stage166冻结合同](stage166_energy_ml/next_execution_contract.json)，在Stage166提交`6a6ac6f`之后执行。只核两个已有路径：`/eos/experiment/faser/data0/phys/2024_back/r0022/015838`和`/eos/experiment/faser/raw/2024/015838`。不寻找其他版本/run，不读RAW payload/REC或nt探测器分支，不重建Calypso，不训练/推理/新G4。原pz0-only一次方动量、允许px/py/q/p/弯折、raw11、typed NaN、合法负数、status0-only timing、Calo缺失、pz>50GeV、全部K、原角色/reserved、Stage87和全部原门保持。

[本阶段协议](stage167_energy_ml/protocol.json)为原合同逐字节副本。两个目录在pilot各一次非递归listing，匹配PHYS上限64、RAW4096；独立audit另各一次核对。严格文件名范围仅作为producer命名的声明，不等价于实际读过RAW、事件独立或DAQ完整性。先按编号固定前3份PHYS，读取nt的run/eventID/eventTime类型、首末真实行、N和top-level key/class。reference另核Stage166原前64/N/时间端点；不使用entry=event−1。

允许的producer metadata仅实际名为meta/MetaData的非nt TTree schema/N及最多4条数值scalar行，或名称明确metadata/config/input provenance的TNamed/TObjString，64KiB上限。其他key只记名字和class，不扫描直方图或nt detector branches。缺来源证明保持未知。

## 执行与实际pilot

所有目录与ROOT/数组/统计均在HTCondor，提交目录`~/condor/nu_muAnalysis/stage167/`；每次4个科学CPU/12GB，最多1job，1500累计CPU秒，pilot300/full900/audit300，MaxRuntime86400s，无应用短timeout。full四文件进程，各1解压/解释线程。GPU加速对此header/I/O任务未测量，不为使用GPU改变方法。

初次descriptor生成把内存误写15GB，作业9676426.0尚idle、NumJobStarts=0时已经`condor_qedit 9676426.0 RequestMemory 12000`，后续源码改回12GB。[修正记录](stage167_energy_ml/submission_repair.json)保留原提交descriptor和队列实际值，未改科学合同或CPU门。该pilot的CERN传输资源使实际RequestCpus=5，不把额外1核称为科学并行。

[目录清单](stage167_energy_ml/inventory.json)、[编号核查](stage167_energy_ml/range_coverage.json)实际取得16份PHYS、778份RAW；声明编号0–777，恰778个，内部缺口0、重叠0、RAW无PHYS声明0、声明无实际RAW0。这个明确结论仅关于实际名字集合，仍不证明处理成功或曝光。

[pilot](stage167_energy_ml/pilot_summary.json)固定00000–00049、00050–00099、00100–00149三份，N分别780874、914588、914240；三列均int32_t。原reference64及N780874和端点精确。三份都只有nt和24个hRandomCharge直方图，允许的producer metadata为空。逐文件读取请求426828/444301/447173B，CPU .516386826/.524176087/.506397410s；内部总1.560509270CPU秒、2.452932031wall秒。GNU总CPU2.24s已含于scheduler2s计量口径，不重复累加。

[成本准入](stage167_energy_ml/admission.json)按三倍完整pilot GNU CPU×16/3，预测full35.84CPU秒≤900，加入已用2秒和300audit reserve≤1500，通过。启动成本已包含；预测不是实测保证。

```bash
python3 ml/stage167_ops.py submit --phase pilot
python3 ml/stage167_ops.py collect --phase pilot
python3 ml/stage167_admit.py
python3 ml/stage167_ops.py submit --phase full
# 完成和验收后才提交audit
```

## 全目录header结果与物理解释

[全部header](stage167_energy_ml/full_summary.json)和[逐文件表](stage167_energy_ml/file_headers.tsv)完成16/16，前三份physical records/schema/有限metadata与pilot精确。全部三列int32_t，全部首尾run15838；每份top-level只有nt与24个hRandomCharge TH1F，没有实际meta/MetaData或允许的TNamed/TObjString。因此“无来源metadata”是已测得的文件内容边界，不是任意猜测producer布局。

16份的N相加为14237355条，未完整读取interior identities，不称为去重独立事件数，更不称为ν候选产额或完整选择效率。首份first为event787406/time1720449636s，末份last为event92068284/time1720503216s；这些是实际首末行，而非已认证全文件time min/max、事件单调性或连续处理。官方stable末端为1720503223s，文件名0–777全覆盖和首尾相接均不能补出DAQ活时间或解释末端无事件的原因。

完整header步骤16文件CPU合计8.049256009s、driver CPU .022926070s、driver wall2.925122678s、实际ROOT请求7241770B。GNU全步骤9.00CPU秒/5.26wall秒，峰单进程RSS66408KiB；并发进程的wall有重叠，不用其比值声称受控加速，亦未测量同时总RSS峰值。不读全ROOT payload，只读3身份列的端点basket及reference64。未将任何轨迹/电荷/时序或占位数加入本阶段模型。

## 独立验证、终态资源与存储

[独立审计](stage167_energy_ml/independent_validation.json)重新列两个原目录，使用另写regex及Counter重建编号集合，名字/重叠/缺口和RAW声明全同；从原ROOT逐分支独立读取前三份实际首末和类型，reference64精确，16行文件表及N总和精确。未复读完整interior，不认证事件独立、全文件单调或选择完整。

[曝光证据表](stage167_energy_ml/exposure_evidence.json)给全部端点包络53580秒、允许producer metadata文件数0、匹配曝光仍null。RAW非匹配名字完整保留，其中实际有`Faser-Incomplete-015838-00000.raw`、`Faser-Monitoring-015838-00000.raw`、`Faser-TLBMonitoring-015838-00000.raw`及histogram JSON。没有读这些内容，不能把Incomplete的名字当已证实丢失多少事件或DAQ故障原因；也不能把778个Physics RAW的名字全覆盖称为所有DAQ记录全覆盖。PHYS目录没有非匹配名字。本阶段没有给整run850.979pb⁻¹乘任何时间/事件比例。

[终态资源](stage167_energy_ml/resource_audit.json)三次提交/三次启动均exit0，pilot9676426、full9676432、audit9676440，0live；总14scheduler CPU秒/28聚合execute wall秒，未重复累加内部/GNU时间。实际RequestMemory全部12000MB，RequestCpus为4或5。scheduler最大RSS采样3000KiB不足代表完整峰值，MemoryUsage是未求值表达式；逐进程GNU见[表](stage167_energy_ml/process_resources.tsv)：

| 阶段 | CPU秒 | wall秒 | 峰RSS KiB |
|---|---:|---:|---:|
| pilot | 2.24 | 3.90 | 68336 |
| full | 9.00 | 5.26 | 66408 |
| audit | 2.66 | 5.01 | 65024 |

[精确归档清理](stage167_energy_ml/storage_cleanup.json)在全终态/当前Iwd无引用后保留实际phase源码/配置/worker/descriptor、完整GNU与日志，源和运输回传逐字节验证后删94366B重复；spool只留execution_index。7份最终目录/身份header/证据元数据合183226B<4MiB，不保存ROOT/xAOD、全事件数组或模型；源码archive58477B、GNU680B、日志1390B、spool2443B。无SHA，Stage54十二文件size/mtime保持。当前AST/bash/冻结合同/链接和历史全文保持等见[文档验证](stage167_energy_ml/document_validation.json)。

```bash
python3 ml/stage167_ops.py collect --phase full
python3 ml/stage167_ops.py submit --phase audit
python3 ml/stage167_ops.py collect --phase audit
python3 ml/stage167_finalize.py
```

## 后续实际输入与验收

本次有限data目录核查到此结束，不循环找其他版本。要认证run15838匹配曝光，仍需实际RAW→PHYS成功/失败/有意过滤的逐输入处理账目及其producer配置，和同选择的DAQ接受/活时间、官方逐时间亮度对应及其误差；只有文件名、首末行或run查表值不通过验收。背景、真实相关辅助校准、乳胶匹配与独立确认也仍未取得。所有未知保留，Stage87不晋升，低能超过传统和完整物理精度尚未完成。

下一[Stage168有限合同](stage167_energy_ml/next_execution_contract.json)转另一个可实际取得的输入——全生成分母：Stage130已经确知的22个EVNT，而非继续追data历史metadata。先按原manifest固定alternative-π/nominal-π/K/charm各首个路径及全22字面路径，仅读实际CollectionTree N/schema和有界producer/归一化metadata；pilot成本通过才4进程全22，独立原pilot和已保存实际log范围复核。1500CPU秒/4核12GB，无CollectionTree事件payload/模型/G4。交付真实生成记录数及有证据的生产范围、缺失weight/归一化/逐生成事件选择账目；N不是独立ν数，selected/N不能直接叫接受度。未知权重若只存在opaque对象则本实现有限结束，不自动大规模native扫描或拟合。这个工作包不替代data曝光证明，也不重复Stage136/140已经完成的有限MC/toys。
