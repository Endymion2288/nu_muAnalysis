# Stage159：实际data前缀不在指定PHYS覆盖中，原生读出容器存在

## 1. 阶段目标与冻结输入

执行[Stage158下一合同](stage158_energy_ml/next_execution_contract.json)，[protocol](stage159_energy_ml/protocol.json)逐字节复制。Stage158固定空间摘要未修复最低能，本阶段推进Stage132真实data缺口：用已知run15838实际REC与合并PHYS验证逐事件身份及源元数据，避免长期把具体输入问题写成笼统“manifest未知”。

精确REC为`/eos/experiment/faser/data0/rec/2024/r0022/015838/Faser-Physics-015838-00000-r0022-xAOD.root`，PHYS为`/eos/experiment/faser/data0/phys/2024_back/r0022/015838/Faser-Physics-015838-00000-00049-r0022-PHYS.root`。路径来自未修改的Stage54 schema证据，PHYS也在tracked `ml/configs/calonu_muon_files.tsv`。本次实际条目数REC **124391**、PHYS **780874**，与历史参考一致，但条目数相同不认证逐例关联。

仅REC原0–63父，不按质量/电荷/动量筛选，独立重复0–3。先实际metadata/TagInfo及完整CollectionTree branch/class inventory，再EventInfo-only原生读取；与整个指定PHYS run/event索引唯一配对。不按entry混合，未匹配/歧义/不支持保留分母。固定PHYS匹配父才读取pz0/px/py、质量/计数和15路raw支持；不读p0/p1/pz1、不用fitted charge或hit timing。无ν forward/fit/G4/重建或新独立ν。

## 2. 实际身份与独立诊断

| 项目 | 实测 |
|---|---:|
| 原生请求父 | 64 |
| 独立原生前4身份重复 | 4/4完全一致 |
| 唯一REC/PHYS配对 | 0/64 |
| 未匹配 | 64/64 |
| 歧义匹配 | 0 |
| 匹配后raw/控制质量/低pz支持 | 未测量，因匹配父N=0 |

[逐父配对表](stage159_energy_ml/pairing.tsv)保留全部64父，原run/event/lumi/timestamp通过原生EventInfo读取。0配对不是“data无μ”“没有raw信号”或“前64为坏事例”的结论；没有matched输入时，`control_eligible_N=0`及raw支持分母0只表示未取得可测支持。

为区分程序与输入原因，在本来600 CPU秒预算内冻结一次[身份索引诊断](stage159_energy_ml/identity_diagnostic_contract.json)。只重读相同PHYS的run/eventID/eventTime索引及同64已保存native身份，不增加native父、来源、匹配容差或raw/能量拟合。独立Counter实现精确重现0配对；同event号跨其他run也没有匹配。

| 范围 | run | event号范围 | Unix timestamp范围（s） |
|---|---:|---:|---:|
| REC原前64 | 15838 | 1–64 | 1720443680–1720443682 |
| 指定PHYS全780874 | 15838 | 787406–5939966 | 1720449636–1720452640 |

PHYS首8 event=787406、787410、787411、787414、787417、787419、787420、787422，均timestamp1720449636 s。**原前缀的全部事件号和时间戳都在PHYS最小值之前**；这解释本次严格配对为什么无支持，不是程序漏配或run不一致。PHYS开始比该REC前缀末晚5954 s。详见[独立诊断](stage159_energy_ml/identity_diagnostic.json)。

未测量：整份REC00000的event号/时间范围和全量交集、PHYS上游实际选择/合并生产历史。因此不能由前64的范围排除推出整份REC无交集，更不能把“原生entry=event号−1”用于后续定位。没有换一个看起来匹配的父来改写本次0/64结果。

## 3. 真实metadata与读出schema

[原生metadata](stage159_energy_ml/native_metadata.json)的实际`/TagInfo`为：

| 字段 | 实际源值 |
|---|---|
| AtlasRelease | Athena-24.0.41 |
| GeoFaser | FASERNU-04 |
| IOVDbGlobalTag | OFLCOND-FASER-05 |
| file_size | 712170622 B |

本次不实例化detector geometry/conditions，也不把runtime默认值当源证据。该metadata没有认证Calypso源码commit、alignment/pull校准或跨生产raw等价；data条件05也不能与既有μ重放条件06混作同一个已认证响应。

实际完整CollectionTree inventory包含`CKFTrackCollectionWithoutIFT`及backward、SCT cluster/SP/RDO和`VetoWaveformHits`、`VetoNuWaveformHits`、`TriggerWaveformHits`、`PreshowerWaveformHits`、`CaloWaveformHits`、`Calo2WaveformHits`、`CaloNuWaveformHits`等。WaveformHit容器实际类为`DataVector<xAOD::WaveformHit_v1>`，配套aux为`xAOD::WaveformHitAuxContainer_v1`。**这认证存储了WaveformHit容器，不等于已读出实际payload，更不证明完整原始ADC samples持久化。** 历史Stage54只是过滤branch列表，其未列waveform不能当缺失证据。

[实际PHYS schema](stage159_energy_ml/PHYS_schema.json)中请求的11路scintillator raw字段存在，但旧`Calo0–3`的raw_charge/raw_peak/baseline_rms/status共16字段不存在。实际有`CaloHi0–3`、`CaloLo0–3`和`CaloNu0–3`等`*_raw_charge`命名。未自动重命名、未用`*_charge`补位、未认证CaloHi/Lo对应的物理通道或增益关系。原缺失Calo保持unknown；`raw_support.tsv`的0分母不作饱和/响应结论。下一步应从真实source与channel/gain mapping检验，不能复制旧MC15通道假设。

## 4. 执行、资源及存储

所有ROOT/元数据/事件数组和支持统计在HTCondor `~/condor/nu_muAnalysis/stage159/`，本地只作文本、提交/运输/精确审计。预算600累计CPU秒、100audit预留；2核/8000 MB、最多1作业、无应用wall超时。原生64/4分别独立进程，随后独立LCG109环境配对。实际2作业/2starts，ID9675294.0与9675311.0，均exit0、0live、无失败；唯一scheduler **177 CPU秒/248聚合execute wall秒**。CERN实际RequestCpus=3、RequestMemory=9000 MB；没有把额外资源预留当已用科学核心。

| 进程 | 内部CPU（s） | 内部wall（s） | GNU CPU（s） | GNU wall（s） | ROOT/索引读取（B） | 最大RSS（KiB） |
|---|---:|---:|---:|---:|---:|---:|
| native64 | 80.057091 | 115.890673 | 85.07 | 125.98 | 10027694 | 1539268 |
| native4 | 77.581633 | 90.169708 | 82.22 | 95.54 | 9985724 | 1568588 |
| PHYS配对 | 1.363545 | 2.352815 | 2.76 | 5.15 | 1734156 | 89044 |
| 独立身份诊断 | 1.170785 | 2.129655 | 2.14 | 4.50 | 1764696 | 311420 |

ROOT字节含metadata/Pool读取，不是整个712 MB源被复制；PHYS只读身份索引，没有matched rows因而raw payload未读取。进程内部/GNU均嵌在scheduler中，不重复相加；无GPU或加速比声明。[完整资源审计](stage159_energy_ml/resource_audit.json)保存四进程及两作业成本，诊断并非新预算或另选模型。

```bash
python3 ml/stage159_ops.py submit
python3 ml/stage159_ops.py monitor
python3 ml/stage159_ops.py collect
python3 ml/stage159_ops.py submit --phase identity_diagnostic
python3 ml/stage159_ops.py collect --phase identity_diagnostic
python3 ml/stage159_ops.py finalize
```

所有作业终态后，原64父及repeat4精确身份记录存`ntuples/energy_ml_stage159/paired_records.json.gz`，594 B<8 MiB；保留完整源metadata/schema和紧凑表。实际源码/worker、原生JSON及GNU文本、日志分别存`software/stage159/source_snapshots.tar.gz` 26078 B、`native_audits.tar.gz` 2480 B、`worker_logs.tar.gz` 3210 B，逐字节回读一致后删75093 B重复运输/审计/日志副本。无REC/PHYS/xAOD/ROOT/完整波形复制、无SHA，Stage54及其他阶段不动。[存储审计](stage159_energy_ml/storage_cleanup.json)有全部明细。

## 5. 阶段结论与下一步验收

本阶段完成的是实际data源及具体覆盖缺口的测量，**尚未取得joint native data配对控制或校准**。源geometry/tag和WaveformHit存在性已不再未知；固定原前缀不在指定PHYS范围，物理通道/gain mapping、payload可读性、控制纯度、data FPR、covariance/关联覆盖仍未测。源身份数据不能替代这些校准。

[Stage160下一合同](stage159_energy_ml/next_execution_contract.json)把目标改为明确的新data-control父集：指定PHYS原前64行，不依赖电荷/动量/质量。根据PHYS最小event及REC00000条目数得到近6.3的**启发式候选**，只查同run REC00005/00006/00007/00008四个冻结路径与reference00000的实际metadata及首尾EventInfo，不目录扫、不在失败后加候选，不把entry数当event范围。只有唯一源首尾能覆盖全部目标身份/时间才继续；否则有限locator结束。

对唯一候选先前1024 EventInfo成本pilot，再以实测startup/post-first三倍仿射估计，连同已用CPU和200audit预留须在2000 CPU秒内才全源EventInfo扫描。输出原PHYS64父的实际native entry/唯一身份map，未知/歧义保留；不假定entry=event−1，full前1024须精确复现pilot。2核/8GB、最多1作业，无detector/raw payload、G4、ν forward或fit。全源地图如成功，之后另冻实际metadata条件下的同父state/PRD/raw一致性，特别是CaloHi/Lo物理通道；不提前认证等价或data FPR。

Stage159原REC64父的0/64不被新父集替换。Stage132整体目标仍未完成；真实联合校准、宽能区来源/乳胶、GRL/曝光/背景/接受度/有限响应统计/相关nuisance与独立确认仍需测量。Stage87、所有原风险门/Stage137扩大门、全部K/原角色/隔离/pz0/raw/status/typed规则保持。中文报告先写，再连代码/小表/路线本地Conventional Commit，不push；整体goal active。
