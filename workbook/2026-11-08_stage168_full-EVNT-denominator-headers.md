# Stage168：完整EVNT生成记录数与归一化证据边界

## 阶段目标与冻结输入

承接Stage132§6完整生成接受度路线和[Stage167冻结合同](stage167_energy_ml/next_execution_contract.json)，在Stage167提交`d858c6f`之后执行。Stage130的666成功来源、6606398 PHYS和222515 selected是既有条件支持，不等于完整生成分母。本阶段取得原22个完整EVNT的实际记录数及有界metadata，区分“知道文件N”与“已知物理权重/接受度”。

[本协议](stage168_energy_ml/protocol.json)与前合同字节相同；[字面输入清单](stage168_energy_ml/inputs.json)直接来自Stage130的source_protocol.json，只做本地文本映射，不探测目录或事件文件。runs200080–200101的22条映射无重复路径；固定pilot按alternative-π、nominal-π、K、charm的原排序首个，分别run200080、200082、200081、200088。没有按产额、易读性或能量残差替换。

CollectionTree仅读header的N与stored branch/type schema，不读取任何事例载荷/weights/particles。其他实际TTree保留N/schema；只有名称明确metadata/config/input/provenance/normalization/params的tree才允许最多前4条primitive numeric scalar，非数值/对象/向量保持省略；POOL数据头不自动当作生成metadata。名称明确的TNamed/TObjString对象及文本上限64KiB，单tree metadata≤64KiB、每文件总metadata≤128KiB。未知物理权重/seed/独立性不由名字或计数补齐。

所有ROOT、源记录科学解析、数组与计数走HTCondor `~/condor/nu_muAnalysis/stage168/`。4科学CPU/12GB、max1job；1500累计CPU秒分pilot300/full900/audit300，MaxRuntime86400s，无应用短timeout。先pilot完整GNU成本三倍投影，加入实际已用和300audit reserve通过才4进程全22，每个1解压/解释线程。只读已有实际log证据，不再扫描日志/其他目录、RDO/REC/RAW，不重建Calypso/新G4/生成/数字化/重建/训练/模型forward。

pz0-only一次方动量、允许px/py/q/p/弯折、raw11、typedNaN/合法signed负数/status0-only timing/Calo缺失、pz>50GeV、全部K、原角色/reserved/quarantine、Stage87和全部原门保持。GPU加速本header读取任务未测量，不更换算法。失败pilot终止固定实现，不重试/扩预算或挑易读替代品。

```bash
python3 ml/stage168_freeze.py
python3 ml/stage168_ops.py submit --phase pilot
# 成功回传并成本准入后才全22
python3 ml/stage168_ops.py collect --phase pilot
python3 ml/stage168_admit.py
```

## Pilot成本与实际全文件记录数

[pilot摘要](stage168_energy_ml/pilot_summary.json)四文件通过，内部CPU .735295816s/wall1.345357827s；逐文件CPU .265500716/.176682475/.194294604/.094788860s，请求412851/509801/695247/113068B，原次序200080/200082/200081/200088保持。GNU1.47CPU秒/2.68wall秒、峰RSS54784KiB。首pilot9676456.0退出0，scheduler1CPU秒已含该步骤，不重复相加；短作业scheduler取整不等于GNU精度。

[准入记录](stage168_energy_ml/admission.json)按完整四文件GNU成本，三倍全22预测24.255CPU秒，≤900；加已用1秒和300审计预留≤1500，通过。预测含startup，并非实测保证。

[全源结果](stage168_energy_ml/full_summary.json)、[逐run表](stage168_energy_ml/EVNT_headers.tsv)完成22/22，四pilot实际N/schema/key/数值metadata完全重复。共11229101条CollectionTree记录；这是完整已命名EVNT的条目总和，未认证生成seed/跨flux独立性，不称新独立ν。此次未读CollectionTree event payload，也没有用selected/总N计算接受度。

| run | 组分 | 原manifest nominal | 生成记录N |
|---|---|---|---:|
| 200080 | π | False | 440784 |
| 200081 | K | False | 704816 |
| 200082 | π | True | 559607 |
| 200083 | K | True | 752808 |
| 200084 | π | False | 548243 |
| 200085 | K | False | 754423 |
| 200086 | π | False | 533501 |
| 200087 | K | False | 659758 |
| 200088 | charm | False | 94877 |
| 200089 | charm | True | 180947 |
| 200090 | charm | False | 463986 |
| 200091 | π | False | 428832 |
| 200092 | K | False | 703608 |
| 200093 | π | True | 541884 |
| 200094 | K | True | 738614 |
| 200095 | π | False | 528046 |
| 200096 | K | False | 744975 |
| 200097 | π | False | 512804 |
| 200098 | K | False | 642977 |
| 200099 | charm | False | 89976 |
| 200100 | charm | True | 170343 |
| 200101 | charm | False | 433292 |

full四进程科学文件CPU合计4.642307665s、driverCPU .058264102s、driver wall2.365057519s，ROOT请求10786718B。只读取header和允许的少量metadata scalar，字节计数不是全文件传输量；并发wall重叠，未做串行受控速度对照。

## 持久化metadata与生成范围的实际含义

实际CollectionTree有`McEventCollection_p6_BeamTruthEvent`及EventInfo/FaserEventInfo，metadata含持久化FileMetaData、EventStreamInfo、TagInfo和POOL头。可读的数值scalar是`index_ref`；它们是POOL引用标识，不是命名的GENIE权重或物理归一化。`char* db_string`和对象/向量未读取，不能说文件不存在权重，也不能以opaque对象名字认证其物理含义。源定义、named weights、生成曝光/积分与逐生成事例的处理账目仍未取得。

[实际保存的log范围核查](stage168_energy_ml/logged_ranges.json)只检查原16份边界命令证据，不根据其他source文件名补证明。index508/run200088请求skip90000/count10000，实际EVNT N94877，名义请求末端100000超出EOF；其他15个实际log窗口完全在各自N以内。`within_actual_N=False`是这个请求范围的描述，不是本阶段读取失败，也不意味着全部selected身份错误。

旧[Stage130 index508原生实测摘要](stage130_energy_ml/parentlink_508.json)已明确requested10000/scanned4877、91 selected全部有incoming匹配，1个incoming对应多个entry；原精确selected-entry检查为91/91。[Stage130原验证](stage130_energy_ml/parent_event_entry_validation.json)保持，不修改或撤销已测selected身份。新的header N使其EOF语义具体闭合；不能把“请求10000”改写为“成功生成/处理10000”，也不能假设全部source都是固定10000。边界命令仍不是整窗口G4/reco/选择成功的证明。

```bash
python3 ml/stage168_ops.py submit --phase full
python3 ml/stage168_ops.py collect --phase full
python3 ml/stage168_ops.py submit --phase audit
```

## 独立验证、资源与终态存储

[独立验证](stage168_energy_ml/independent_validation.json)用实际C++ ROOT TFile/GetEntries读四pilot，CollectionTree及实际metadata树N与uproot精确；再另写逐branch type/primitive scalar读取，schema/key/数值全同。全部22字面run/path映射、16原命令的独立shlex范围重建、22行表及全N总数精确。ROOT仅缺少xAOD/POOL对象字典的提示保留在完整日志；没有读取opaque对象，C++ header验证不认证这些对象的物理内容或原GENIE运行史。

[分母证据](stage168_energy_ml/denominator_evidence.json)给nominal条目2944203、alternative8284898；它们不按通量权重混合。历史source_manifest有1134来源，原Stage130完成的是666，其中16有本阶段检查的实际log窗口，650没有这套逐窗口log证明；全历史1134中1118没有这套证明。不得把1134、666和22文件混为同一分母，或把缺本项证明当已证实处理失败。index_ref是唯一实际读取的metadata scalar branch名，named weight归一化/生成曝光/完整处理接受度仍False。

[终态资源](stage168_energy_ml/resource_audit.json)pilot9676456/full9676460/audit9676465，三job/三start全部exit0，0live；总11scheduler CPU秒/30聚合execute wall秒，均实际4CPU/12000MB，无额外科学核声明。GNU嵌套于scheduler且精度不同，不重复累加。scheduler最大RSS采样150000KiB，不能替代独立审计GNU峰648004KiB；MemoryUsage是表达式，不解释为数值内存峰。[GNU表](stage168_energy_ml/process_resources.tsv)：

| 步骤 | CPU秒 | wall秒 | 峰RSS KiB |
|---|---:|---:|---:|
| pilot | 1.47 | 2.68 | 54784 |
| full | 5.49 | 3.77 | 50520 |
| audit | 5.30 | 10.75 | 648004 |

[精确归档清理](stage168_energy_ml/storage_cleanup.json)全终态且当前Iwd无引用，源码/配置/worker/descriptor、GNU/完整日志及pilot部分检查点按原字节归档回读；删200552B重复运输/日志/spool/partial，提交目录只留execution_index。7份最终生成header/范围/证据元数据177167B<4MiB；source archive160421B、GNU692B、worker日志1792B、spool2454B、partial1392B。未持久化ROOT/xAOD、事件数组或模型，未SHA，Stage54十二文件size/mtime保持。[文档验证](stage168_energy_ml/document_validation.json)另核AST/bash、执行阶段冻结字节、链接/围栏和历史文档完整保留。

```bash
python3 ml/stage168_ops.py collect --phase audit
python3 ml/stage168_finalize.py
```

## 阶段结论与下一步

本阶段取得实际完整EVNT记录数、明确persistent schema和原log窗口相对EOF的边界；这项真实输入已不再完全未知。物理归一化、跨flux/seed独立性和全生成接受度仍未认证，不能用条目数代替物理权重，不凭任意prior恢复不可识别量。Stage167两目录data覆盖核查和本阶段opaque metadata读取范围到此结束，不自动做大规模native EVNT扫描或继续其他目录；原Stage87、最低能目标尚未达成及全部原门保持。真实run逐输入处理/DAQ亮度、背景、相关校准/生成系统辅助约束、乳胶和独立确认仍缺。

下一[Stage169冻结合同](stage168_energy_ml/next_execution_contract.json)直接利用现存、已压缩的Stage130 source_evidence和16份原native summary，核666来源实际parent/truth-superset/selected计数、source508的4877 EOF处理，以及1134历史source声明对实际22EVNT N的范围覆盖；不读事件数组/ROOT或再生成。原16作为固定pilot，schema/成本通过才全部666，独立scalar/区间扫描复核。预算300CPU秒，pilot60/full120/audit120，2核4GB；微小元数据一次解压，避免多进程重复I/O。验收是具体“请求/可用/实际计数”账目、原角色/来源支持与缺证据区分；数量相等不认证未选事例身份或物理接受度，也不修改Stage130总数。这推进逐生成处理账目的现有证据部分，同时把真正缺失的weight/曝光/全事件处理输入留给实际producer证明，不重复有限MC/toys或新G4。
