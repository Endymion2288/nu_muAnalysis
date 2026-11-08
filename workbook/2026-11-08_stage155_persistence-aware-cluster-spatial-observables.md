# Stage155：认证旧 REC 数值表示并取得真实 cluster 空间量

## 阶段目标、合同与输入

执行 [Stage154 下一合同](stage154_energy_ml/next_execution_contract.json)，[protocol](stage155_energy_ml/protocol.json)逐字节相同。Stage153 的 curvilinear local state 与硅片 local measurement 不同基底，Stage154 的固定1e−6 mm离面条件又比持久化位置精度更严格。本阶段先认证**实际文件**表示，再用明确的舍入区间核验全局位置与硅片的相容性；不任意调大几何半径，不修 covariance，不用旧局部状态直接相减。

固定 Stage124 request0/origin55/source_index0、π/run200082，原 role1 按 REC entry 排序前4→最多同前40，无能量/风险/活动选择、替换父、来源扫描或cal/test/reserved/role4/隔离forward。REC：`/eos/experiment/fasernu-data0/faser/sim/mc24/genie/200082/rec/s0014/FaserMC-MC24_Genie_epos_pi-200082-00000-00009-s0014-xAOD.root`。PHYS：`/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/merge_mc24_master_d32b0ff3/200082/FaserMC-MC24_Genie_epos_pi-200082-00000-00009-s0014-merge-PHYS.root`。

Pinned d32/FASERNU04/tag06，只有PoolRead+MergeTrack；没有digi/reco refit、G4或完整NtupleDumper。原PHYS仅激活run/eventID/longTracks/SpacePoints/Track_pz0/nClusters0–3；pz0容差rel3e−7/abs3e−5 GeV保持。原 cuts/K/角色、pz0-only一次方动量、raw11/typedNaN/合法signed/status0 timing/Calo缺失政策均未改变；这个π来源方法pilot不构成全样本去掉K。

## 实际持久化证据与测量定义

[实际pilot schema](stage155_energy_ml/pilot_schema.json)与[full schema](stage155_energy_ml/full_schema.json)逐字段相同。实际CollectionTree的两个MergeTrack输入 `CKFTrackCollectionWithoutIFT`、`CKFTrackCollectionBackwardWithoutIFT`，class均为 `Trk::TrackCollection_tlp6`；**文件内streamer**的 `m_parameters` 为 `vector<Trk::TrackParameters_p2>`，后者的参数值成员为 `vector<float>`。这不是仅看当前C++头文件猜历史文件格式。

[源码核对](stage155_energy_ml/persistence_source_notes.json)保留pinned d32的MergeTracksAlg、TrackCollectionCnv和tlp6存储/转换链。实际raw POOL GUID token未单独读取；GUID→tlp6→TrackParametersCnv_p2是pinned转换代码证据。Stage154已实际读取并保存的p2转换器将curvilinear全局position3/momentum3/charge写成7个float；上游Atlas含p7/tlp5的代码只作上下文，没有拿来替代FASER实际映射。

对真实状态全局点g，先要求每坐标恰能由float32表示；以该float32前后邻数的中点定义round-to-nearest区间。把三维box沿实际wafer法向投影，要求0处于其可能离面区间内，单独记录 `64*eps64*max(1,sumabs(n*g)+sumabs(n*origin))` 的float64算术余量。局部X中心由真实wafer逆变换取得，沿X的box投影给保守数值区间；没有把位置改写为某个猜测的保存前点。

对唯一、真实链接的leading measurement wafer，保持measurement-detector相同基底及PRD/刚体往返≤1e−8 mm，按真实PRD对象排除leading-owned。对其他轨迹拥有或未归属的cluster，要求实际同wafer/同面、有效非空rdoList/strip、合法局部位置和cluster往返，计算 `dx_mm=cluster_native_locX−wafer_inverse(actual_state_global_position).x`。独立以全局差向量沿wafer局部X轴点积复核，并保留dx表示区间。不使用curvilinear locX或任何拟合方差归一化。

这是一个明确的**round-to-nearest表示模型**，不恢复实际保存前坐标，也不认证历史writer舍入模式、alignment、detector分辨率或fitted covariance。区间不是统计置信区间、pull或关联后验。

## 40父实际结果与新空间内容

[完整审计](stage155_energy_ml/summary.json)、[四站支持表](stage155_energy_ml/station_support.tsv)：

| 检查 | 实测结果 |
|---|---:|
| 原父身份/pz0及cluster4/SP/longTracks一致 | 40／40 |
| actual leading anchors | 697 |
| PRD链接／identifier／measurement-detector同面 | 各697 |
| 二维key3／全局坐标float32精确／plane-box相容 | 各697 |
| 有效唯一wafer anchors | 697 |
| 仍超过Stage154旧1e−6 mm条件 | 467 |
| eligible非leading cluster | 148 |
| 至少一个eligible candidate的父 | 22／40 |
| 第一父同进程重复 | 精确 |
| 独立full作业前4记录／小QA／schema复现 | 全部精确 |

467个小离面偏差在当前明确的表示区间中全部相容；这解决了本批数据按该表示模型计算空间量的程序支持问题，没有追认Stage154原门通过，也没有证明这些差是物理tracking bias。

| station | clusters | leading-owned | nonleading | leading测量wafer上／eligible | 其他wafer上 | 有候选父数 | 每父candidate_N范围 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | 3910 | 0 | 3910 | 0／0 | 3910 | 0 | 未定义 |
| 1 | 581 | 230 | 351 | 63／63 | 288 | 11 | 0–29 |
| 2 | 616 | 229 | 387 | 29／29 | 358 | 9 | 0–13 |
| 3 | 520 | 238 | 282 | 56／56 | 226 | 11 | 0–18 |

站1–3均有40父可用wafer，但非空父跨站重叠，不能把11+9+11当31独立父；union为22。当前仅测到了站1–3的148/1020个非leading cluster，其他872个在未被leading测量的wafer上，不能当作没有空间活动。站0由withoutIFT定义没有leading测量面，保持未知。支持wafer中确实无候选时candidate_N=0、空score统计仍为null/NaN；可用性与零不混淆。

| station | 非空父mean abs dx范围（mm） | min abs dx最小值（mm） | max abs dx最大值（mm） | 非空父RMS dx范围（mm） |
|---|---:|---:|---:|---:|
| 1 | 0.274922004–27.402826847 | 0.274922004 | 57.396242060 | 0.274922004–28.413486011 |
| 2 | 0.436139603–32.152983105 | 0.436139603 | 45.357948076 | 0.436139603–32.152983105 |
| 3 | 0.833489883–50.884252785 | 0.256825119 | 55.796139944 | 0.852704811–50.884252785 |

这是实际cluster局部测量与实际拟合全局位置形成的变化，原计数摘要未保存这些逐cluster位置。它不是仅给旧计数换聚合函数；但其相对旧X/Z/点关系的可用条件增量仍需同原队列比较，尚未测量。这里只读一个来源的训练父，不宣称低能区、来源/材料变化或全部K的性能。

## 独立数值验证与边界

全部实际anchor的表示区间由Python独立复算，候选全局点积、区间包含关系和账目闭合通过。以下值为full实测：

| 数值检查 | 结果 |
|---|---:|
| 每父最大abs normal范围 | 9.765625003866717e−6–7.812500007276948e−5 mm |
| state刚体往返最大差 | 1.5888218580782548e−14 mm |
| PRD／candidate local-global往返最大差 | 0／0 mm |
| C++独立全局点积dx最大差 | 1.4210854715202004e−14 mm |
| Python独立点积dx | 全部通过1e−8 mm界，精确最大差未单独记录 |
| 每父最大normal box宽度 | 均2.44140625e−4 mm |
| 每父最大float64 normal算术余量 | 6.972939572968962e−11–7.006804095266439e−11 mm |
| 所有state局部X区间最大宽度 | 7.70415756079501e−6 mm |
| 候选dx表示区间最大宽度 | 7.70415756079501e−6 mm |

实际距离变化远大于这个表示区间宽度；这仅排除“本批dx变化只是float32量化幅度”的解释，不能替代探测器/track误差校准。148个候选的RDO、local、surface、element或roundtrip失败计数均0；这次这些检查实际到达并执行了，与Stage153/154未触发的0计数不同。没有拟合covariance缩放、关联posterior、μ/其他根分类器、FPR、能量风险或真50–100 GeV性能测量。

Stage153指出的旧Stage124直接local residual物理解释限制仍保持；不改写历史模型结果，不把本阶段成功称为旧covariance已正确变换。Stage87 direct62未变。

## 事前准入、性能与存储

原前4实际有2个eligible候选。按[冻结准入](stage155_energy_ml/full_admission.json)：GNU62.49CPU秒，后3execute为.006882228/.004026424/.005928316秒；base62.473163032秒保留first-event/lazyJIT，steady均值.005612322667秒，`3*(base+39*steady)=188.076130848` CPU秒，加100audit预留低于剩1134CPU秒，故准入同前40，没有改预算或替换父。这是成本预测，不是全队列吞吐认证。Full实际GNU80.84CPU秒。

实际命令：

```bash
python3 ml/stage155_submit.py pilot
python3 ml/stage143_monitor.py --stage 155
tar -xzf ntuples/energy_ml_stage155/pilot_result.tar.gz
python3 ml/stage155_submit.py admission
python3 ml/stage143_monitor.py --stage 155
tar -xzf ntuples/energy_ml_stage155/admission_result.tar.gz
python3 ml/stage155_submit.py full
python3 ml/stage143_monitor.py --stage 155
tar -xzf ntuples/energy_ml_stage155/full_result.tar.gz
python3 ml/stage155_submit.py audit
python3 ml/stage143_monitor.py --stage 155
tar -xzf ntuples/energy_ml_stage155/audit_result.tar.gz
python3 ml/stage155_finalize.py
```

科学数组、ROOT、Cling、区间统计全部走 `~/condor/nu_muAnalysis/stage155/` 的HTCondor scratch；worker/package transfer后以basename执行。本地仅文本/调度/逐文本合并/文档。请求4CPU/12000MB、MaxRuntime86400秒、累计预算1200CPU秒、pilot400秒，无应用wall超时。此小native状态机按事件序列执行，未测多线程/GPU加速，不把请求4CPU当4倍加速。

| phase | job | GNU CPU秒 | GNU elapsed秒 | GNU peak RSS KiB |
|---|---|---:|---:|---:|
| pilot4 | 9674932.0 | 62.49 | 78.62 | 2033420 |
| admission/audit | 9674939.0 | 0.97 | 1.26 | 97776 |
| full40 | 9674944.0 | 80.84 | 109.74 | 1953544 |
| final audit | 9674951.0 | 1.29 | 1.65 | 99236 |

[唯一scheduler账](stage155_energy_ml/scheduler_accounting.json)为4job/4starts全部exit0、155CPU秒/222聚合执行wall秒、0live。不能加上这些嵌套计时。Native内部pilot/full分别57.676977544/74.755433132CPU秒、71.369715003/99.553481285wall秒，ROOT读取2804174/3986324B；44次原entry执行只有40个不同父，重复4不算独立支持。0GPU、0G4、0新独立ν、0fit/reserved forward。

[清理记录](stage155_energy_ml/storage_cleanup.json)：pilot/full原JSON文本精确合并为 `ntuples/energy_ml_stage155/event_records.json.gz`，13230B，原keys为 `ntuples/energy_ml_stage155/pilot.json.gz` 与 `ntuples/energy_ml_stage155/full.json.gz`。Source胶囊76663B，12份实际worker日志胶囊13639B，persistence参考源码胶囊6406B均回读核对。删除14508839B重复运输，无持久ROOT/REC。原输入/其他阶段/Stage54资产未动。

## 结论与下一步验收

本阶段取得可用且可复现的原生位置测量，纠正了对保存精度的支持判断；没有取得低能能量改善、μ辐射区分或校准误差证据。原全部风险门、Stage137双箱5%扩大门、Stage87及整体未完成状态保持；1.05仍为非劣效。

[Stage156冻结合同](stage155_energy_ml/next_execution_contract.json)在已知MC100012原HITS前4→最多64做**相同位置测量的μ控制**：复用Stage149的pinned官方digi/reco/RNG，新增原先没有保存的非leading位置，核同current06状态/raw/PRD/RNG及prefix，显式保留3无leading等选择失败，不把无候选当pilot失败。只在实测物理/表示/身份及按各子进程GNU与post-first-event时序的成本通过后扩大，3000CPU秒/800pilot/150audit预留，无G4/独立ν/energyfit。固定报告all/current-leading/pz0[50,100)GeV/硬件status&4 overflow的支持和空间分布，不因μ辐射尾删事件，也不将非leading本身称为其他根或误报。Stage156尚未提交。

之后才可另冻更充分μ/data联合响应和留出判别/FPR合同，以及受原门约束的全原ν队列能量比较；64方法控制本身不认证总体FPR。真实covariance基底/transport/校准、宽能区/data迁移、乳胶、GRL/背景/接受度、真实相关nuisance与独立确认仍开放，不以本次原生访问成功代替这些任务。
