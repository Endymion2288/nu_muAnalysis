# Stage166：实际GRL输入和同源PHYS曝光边界

## 阶段目标与新输入依据

承接Stage132§6实际物理精度路线。Stage165的来源诊断已终态，不触发同类H/G4/模型扩大；但“未取得完整曝光”不应误写成官方GRL无法取得。当前`AnalysisZipFramework/config/grl_config.yaml`明确给出v10的2022/2023/2024六份JSON/CSV。本阶段有界取得这些实际输入，并与Stage160已经严格配对的run15838 PHYS同源核对，回答这份局部文件是否足以赋予整run或局部曝光量。

冻结[协议](stage166_energy_ml/protocol.json)仅同`/eos/experiment/faser/data0/phys/2024_back/r0022/015838/Faser-Physics-015838-00000-00049-r0022-PHYS.root`，原前1024条pilot/原前64身份闭合后成本准入，再一次全文件header扫描。只读run/eventID/eventTime和实际存在的inputBits/distanceToCollidingBCID，无track/电荷/波形/ν选择/模型，原MC角色、全部K和reserved不动。Stage87与所有原门保持。

## 时间、亮度与选择口径

按仓库真实`GRLUtils::TimeRanges`，stable和excluded均含端点；JSON转long long的Unix秒，与data eventTime同口径。Data quality次序为colliding==0、触发任一0x8/0x10/0x20/0x40、GoodTimes、非ExcludedTimes。缺少可选分支则该部分未测，不替代；这是已生产PHYS内部的描述，不是触发/选择效率或ν产额。

CSV实际第4列lumi_rec及整run原值单独记录，单位pb⁻¹依据仓库配置声明，不认证独立亮度标定或其不确定度。文件eventTime包络、被事件占据的秒数以及与GRL区间的重叠，不是曝光/活时间。没有完整处理/DAQ活时间与逐时间亮度依据，不按事件数/时间比例缩放整run亮度，也不把整run亮度附到该局部文件。

## 执行、预算与验收

所有ROOT/GRL/CSV解析、数组和计数通过`~/condor/nu_muAnalysis/stage166/`，4CPU/12GB、最多1job、1200累计CPU秒分pilot300/full600/audit300，MaxRuntime86400秒，无应用短timeout。pilot两块512完整读取测startup/首块与次块CPU，3倍仿射全源预测加实际已用/300审计reserve决定准入；预测不是实测保证，不放宽失败门。full用4个解压/解释线程、65536行分块，只留紧凑按秒计数及原1024prefix；不保存ROOT/xAOD。

独立验证用仓库实际C++ TimeRanges覆盖所有实际占据秒、真实区间端点±1及无run情形；另从原ROOT逐分支重读1024做身份和标量DQ核查，区间长度另用中点扫描，官方源文件原字节归档回读精确。零fit/模型forward/G4/digi/reco/新独立ν，不为GPU改算法，不重建pinned Calypso。最终源/事件输入上限2MiB，Stage54保持，先中文报告后ConventionalCommit。

```bash
python3 ml/stage166_ops.py submit --phase pilot
python3 ml/stage166_ops.py collect --phase pilot
python3 ml/stage166_admit.py
# admitted才full，随后独立audit
```

## 官方输入与pilot实测

[实际输入](stage166_energy_ml/grl_input.json)给六份CVMFS v10源文件共509086B，按原字节归档为`ntuples/energy_ml_stage166/official_grl_inputs.tar.gz`。run15838只在2024 JSON/CSV各出现一次，LHC fill9877，无excluded_list。原JSON run起止为1720443677.720435–1720503358.048976 Unix秒；实际stable为[1720449636,1720503223] Unix秒（含端点），连续区间长度53587秒。

CSV实际header为Run/Fill/LumiDel/LumiRec/TimeDel/TimeRec，第4列LumiRec原值850.979，按仓库既定单位为**850.979 pb⁻¹的整run记录亮度**。原行完整保存，不给它补未测量的误差/协方差；本阶段没有独立重做亮度标定。CSV其他列原字符串亦保存，不把TimeRec或LumiDel任意当这份文件的亮度/活时间。

首次pilot9676366.0因读取脚本要求snake_case `lumi_rec`而拒绝实际`LumiRec`，尚未读ROOT；2CPU秒全部计入预算。仅规范化大小写/下划线列名检查，原第4列、全部路径和科学政策不变，pilot_retry沿用剩298秒，9676377.0退出0；详见[修复记录](stage166_energy_ml/parser_repair.json)。没有更换源、扩大目录或修改GRL范围。

[成功pilot](stage166_energy_ml/pilot_summary.json)取得原1024条，两块512；run/eventID/eventTime/inputBits/distanceToCollidingBCID均为int32_t，无缺少可选分支。原前64的run/event/time与Stage160逐条精确。stable/合格时间1024、excluded0、colliding1015、trigger1016、依序四项DQ通过1015。这些是原PHYS内部计数，不是完整采集效率。

pilot内部首512+source打开CPU .525675661秒，次512 CPU .012630731秒、wall .013949969秒；实际ROOT请求303296B、总内部CPU .650746125秒、wall1.390291174秒、峰RSS52224KiB。[成本准入](stage166_energy_ml/admission.json)给三倍全源预测59.362621308CPU秒，已用scheduler4秒+300秒审计reserve≤1200且预测≤600，因此准入；pilot GNU1.73秒已包含于scheduler，不重复相加。该预测不是完成保证或实测全源成本。

## 全文件数据质量与曝光边界

[全源结果](stage166_energy_ml/full_summary.json)为原780874条，全部run15838、原1024prefix精确；[按秒支持](stage166_energy_ml/time_support.tsv)保留完整紧凑计数。输入time包络1720449636–1720452640 Unix秒与Stage159已记录源范围一致；本阶段新增的是官方GRL/亮度取得、同源逐事件DQ与独立C++验证，并非把旧时间范围包装成首次发现。

| 同源逐事件项目 | 实测N |
|---|---:|
| 原PHYS记录 | 780874 |
| GoodTimes | 780874 |
| ExcludedTimes | 0 |
| GoodTimes且非ExcludedTimes | 780874 |
| colliding | 774232 |
| 原trigger任一位 | 774823 |
| colliding后trigger | 774232 |
| 再经GoodTimes和非ExcludedTimes | 774232 |

文件包络连续长度3004秒，与合格GRL相交长度亦3004秒；有事件的整数秒桶3004个，而含两端点的整数秒候选数3005，有1秒无事件。这些是不同口径，不能混为活时间；单秒无事件也不能直接解释为DAQ deadtime。

**该文件所有事件通过时间GRL，不证明该文件覆盖了整run处理/曝光。** 整run合格时间53587秒，源文件实际事件支持只到1720452640秒。当前没有完整RAW→PHYS处理manifest、逐时间亮度与DAQ活时间对应，`dataset_luminosity_pb_inv=null`、`dataset_exposure_certified=False`保持。不以事件数/时间比例缩放850.979pb⁻¹，也不把该run亮度直接附给本文件。

源码`Analysis::Run`中`meta.lumi`是按requested run从GRL查表的整run向量，并不是通过文件完整性证明计算出的局部曝光；`n_events_input`同样不足以补出这一证明。本阶段不改变原输出/C++选择，只明确它们的物理解释。后续完整物理似然不能仅用这两个metadata字段声称已取得同选择曝光。

## 独立验证、资源与紧凑存储

[独立审计](stage166_energy_ml/independent_validation.json)在LCG109中实际加载仓库`GRLUtils.h`的C++ TimeRanges，核对全部3004个实际占据秒的stable/excluded/合格计数、6个真实区间端点±1和无run情形；[边界表](stage166_energy_ml/boundary_validation.tsv)通过。原run无excluded区间，不能将此写成验证了真实excluded样本覆盖。另从原ROOT逐分支重读1024，身份/原prefix及独立标量DQ全同，ROOT请求280480B。全780874条的逐秒聚合总数精确；连续区间长度用独立中点扫描再核，与full的区间切分一致。六份源文件各字节和CVMFS实际文件精确。

全源科学步骤内部CPU .873399424秒、wall2.668176874秒、请求2425625B、峰RSS60352KiB，只读五列/65536行分块，4个解压与解释线程；不是读全PHYS payload。线程配置考虑了I/O/并发，未做受控串行加速对照。独立审计并未重放整个analysis可执行程序，也未执行完整ν选择或认证μ纯度/背景/接受度。

[终态资源](stage166_energy_ml/resource_audit.json)：4job/4starts，首pilot执行失败已计，后3均exit0；0live，总11 scheduler CPU秒/43聚合execute wall秒，低于1200秒。实际Request4CPU/12000MB；scheduler RSS采样0是未取得有效峰值，不当作零内存。[GNU逐进程](stage166_energy_ml/process_resources.tsv)：

| 步骤 | CPU秒 | wall秒 | 峰RSS KiB |
|---|---:|---:|---:|
| 首失败pilot | 1.15 | 2.42 | 45056 |
| 成功pilot_retry | 1.73 | 5.01 | 52224 |
| full | 1.88 | 4.56 | 60352 |
| audit | 4.12 | 7.67 | 645976 |

GNU/内部CPU均嵌套在scheduler内，不重复相加；其余时间包含启动/传输/环境。无模型训练、推理、GPU、G4、digi/reco或新独立ν。固定小输入读取与时间规则验证没有改用GPU的必要。

[精确清理](stage166_energy_ml/storage_cleanup.json)核所有作业终态及当前Iwd无引用后，归档实际源码/配置/worker/descriptor/GNU和所有成功失败日志，逐字节核对原输入和回传包再删除6292436B重复；本stage spool只留execution_index。官方六源精确archive62686B、原1024prefix gzip4108B，最终新增输入共66794B<2MiB，无ROOT/xAOD或全事件数组持久化，Stage54十二文件size/mtime保持。

[源码去重](stage166_energy_ml/source_compaction.json)再把3857个逻辑phase/path版本按精确内容存为975份，`source_versions.json`索引可重建全部原字节；先临时归档/读回逐项重建，再替换原archive，从5753927B降至1489384B，再减4264543B。没有SHA，不读取事件数组或丢失失败版本。当前源码和实际执行版本分别可审阅。验证AST/bash、合同冻结字节、链接、历史原文/Stage54及diff见[文档验证](stage166_energy_ml/document_validation.json)。

```bash
python3 ml/stage166_ops.py submit --phase pilot_retry
python3 ml/stage166_ops.py collect --phase pilot_retry
python3 ml/stage166_admit.py
python3 ml/stage166_ops.py submit --phase full
python3 ml/stage166_ops.py collect --phase full
python3 ml/stage166_ops.py submit --phase audit
python3 ml/stage166_ops.py collect --phase audit
python3 ml/stage166_finalize.py
python3 ml/stage166_compact_sources.py
```

## 阶段结论与下一步

[实际曝光输入清单](stage166_energy_ml/exposure_input_manifest.json)区分run查表值与未认证的文件曝光。本阶段取得并验证了实际v10 run15838 GRL及整run记录亮度；不能继续把这一具体输入写成完全未知。与此同时，**所用单份PHYS的匹配曝光仍未认证**，完整ν物理精度并未完成；背景、全生成接受度、真实相关响应/flux/GENIE辅助约束、乳胶匹配和独立确认仍缺。Stage87及全部原门、pz0-only/raw11/typedNaN/合法signed/status0timing/Calo缺失/全部K/角色/reserved保持。

下一[Stage167冻结合同](stage166_energy_ml/next_execution_contract.json)是这项新实际输入的有限覆盖核查：只在已知run15838的同官方PHYS目录和Stage43已实读RAW目录各作一次非递归listing，PHYS≤64/RAW≤4096个固定匹配文件；先原前3文件真实header/首尾身份及Stage166 reference64，成本通过才4进程读全部PHYS首尾和实际有限metadata，再独立核目录/文件范围/原3。1500CPU秒、4核12GB，不读RAW payload/轨迹/电荷、不重建或新G4，不做ν风险/模型，不借名义或其他run补缺。验收为具体文件manifest、实际来源/计数/metadata和缺口可复现，区间文件名、时间端点或缺事件都不得单独升级为DAQ处理完整性或曝光认证；缺少证明则如实保留未知，不能无限试目录。这样继续取得真正匹配的物理输入，而不是再次扫旧能量候选。
