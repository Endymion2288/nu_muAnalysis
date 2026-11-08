# Stage154：真实全局状态到硅片坐标的几何与表示精度 pilot

## 目标、输入与冻结政策

承接 [Stage153 独立几何合同](stage153_energy_ml/next_execution_contract.json)，[protocol](stage154_energy_ml/protocol.json)逐字节相同。Stage153保存的 curvilinear局部状态不能与硅片局部 cluster直接相减，本阶段改用真实 fitted **GLOBAL position** 映入 wafer frame，只研究未归一化的 dx；不借用、旋转或修补旧 covariance，不计算 pull/关联概率。

仍是 Stage124 request0/origin55/source_index0、π/run200082 原 role1 按 REC entry排序；先前4个父 entry19/52/59/62，身份/物理支持和成本通过后最多同原前40，不更换父、来源或风险筛选，不读 cal/test/reserved/role4/隔离或真能量。REC：`/eos/experiment/fasernu-data0/faser/sim/mc24/genie/200082/rec/s0014/FaserMC-MC24_Genie_epos_pi-200082-00000-00009-s0014-xAOD.root`；PHYS：`/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/merge_mc24_master_d32b0ff3/200082/FaserMC-MC24_Genie_epos_pi-200082-00000-00009-s0014-merge-PHYS.root`。配置为 pinned d32/FASERNU04/tag06、PoolRead+MergeTrack；无 digi/reco refit、G4、完整NtupleDumper或能量fit。

冻结条件是：实际PRD链接/identifier、唯一measurement wafer、measurement与detector surface完全一致、measurement非outlier、包含locX（本方案明确允许二维COT），fitted全局位置逆变换后的离面距离≤1e−6 mm，state rigid-transform与PRD local/global往返≤1e−8 mm。只对支持的wafer排除真实leading-owned PRD，读取其他cluster局部位置，计算dx并以全局差向量沿wafer局部X轴点积独立复核。不按近邻猜归属，不保存全cloud。预定每站candidate_N、mean/min/max abs dx、RMS dx，附可用性和覆盖；空/未知不填分数。

## 实际数据与支持结果

[审计汇总](stage154_energy_ml/summary.json)、[四站表](stage154_energy_ml/station_support.tsv)：

| 检查 | 实测 |
|---|---:|
| 原父数／原身份、pz0和cluster4/SP/longTracks匹配 | 4／4 |
| 第一父同进程native重复 | 精确 |
| 真实leading anchors | 70 |
| 真实PRD链接／identifier／measurement | 各70 |
| measurement与detector面变换相同 | 70 |
| 二维、parameterKey=3 | 70 |
| 通过冻结几何条件 | 16 |
| 超出1e−6 mm离面条件 | 54 |
| eligible非leading候选 | 0 |

每父最大绝对离面距离为2.9296875257071547e−5至7.812500007227749e−5 mm。state坐标变换往返每父最大差7.944109290391274e−15至1.464821375527116e−14 mm；PRD local/global往返差四父均0 mm。由此可区别“变换算错／PRD坐标不能闭合”与“保存的全局点并不满足事先过严的精确离面条件”。没有把小离面偏差当作物理tracking bias或真实位移。

| station | clusters | leading-owned | nonleading | 同leading测量wafer候选 | 通过的wafer | 有可用wafer的父 |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 34 | 0 | 34 | 0 | 0 | 0 |
| 1 | 30 | 24 | 6 | 1 | 15 | 4 |
| 2 | 27 | 24 | 3 | 0 | 0 | 0 |
| 3 | 26 | 22 | 4 | 1 | 1 | 1 |

站1、3各一个同wafer候选都落在不支持的anchor上，因此没有达到候选RDO/local/roundtrip后续检查，不能用这些未触发计数的0认证候选属性。支持wafer子集的candidate_N=0是有条件的实测零，不能外推成整事件无非leading活动；两个未评分候选仍未知。站0没有withoutIFT leading测量面，保留缺失。

**没有可用dx候选，独立dx点积复算、candidate roundtrip、非零dx动态范围与分辨能力均未测量。** 第一父native重复通过，但full40未执行，pilot/full前4复现未测量。不产生能量风险、FPR、σ覆盖或低能优于传统的结论。

## 数值表示诊断与原因边界

本阶段读取 Athena24.0.41 的实际 [TrackParametersCnv_p2源码](https://gitlab.cern.ch/atlas/athena/-/raw/release/24.0.41/Tracking/TrkEventCnv/TrkEventTPCnv/src/TrkParameters/TrackParametersCnv_p2.cxx)及CVMFS `TrackParameters_p2.h`。后者的m_parameters为`vector<float>`；转换器将全局position3/momentum3/charge写入7项，并在读取7项时构造CurvilinearParameters。对应源码已压缩保留于 `software/stage154/persistence_source_reference.tar.gz`；[精度记录](stage154_energy_ml/persistence_precision_notes.json)与[文献记录](stage154_energy_ml/research_sources.json)说明了访问范围。

对本来已保留的4父、各最多4anchor的小QA，在Condor独立计算：先核每个全局坐标是否恰可由float32表示，再取该float的前／后相邻可表示数的中点形成round-to-nearest区间，将三维box投影到wafer法向。汇总JSON逐项列出的QA坐标都为float32精确值，其离面距离区间均包含0。例如entry19的一项实测normal=−1.8310545928297113e−6 mm，区间[−3.7384032256422117e−6,+7.629403998278913e−8] mm，与保存前严格在面上相容，但在本阶段1e−6 mm条件下仍不通过。

这解释了**为什么不能仅凭这个过严精度门声称几何信息缺失**。同时，当前尚未直接认证旧REC实际使用的persistent parameter schema，也未对全部70anchor的rounding区间作认证；不能把“QA与float32相容”改写成“全部54偏差已证实只由舍入造成”，更不能声称alignment/covariance已校准。诊断没有修改本次容差、可用性、candidate定义或full准入。

## 成本准入、执行与存储

实际命令：

```bash
python3 ml/stage154_submit.py pilot
python3 ml/stage143_monitor.py --stage 154
tar -xzf ntuples/energy_ml_stage154/pilot_result.tar.gz
python3 ml/stage154_submit.py admission
python3 ml/stage143_monitor.py --stage 154
tar -xzf ntuples/energy_ml_stage154/admission_result.tar.gz
python3 ml/stage154_finalize.py
```

提交于 `~/condor/nu_muAnalysis/stage154/`，worker/package transfer到scratch后以basename执行；请求4CPU/12000MB、MaxRuntime86400秒、累计1200CPU秒、pilot400秒和audit100秒预留。所有ROOT/Cling/数组/精度统计在HTCondor执行；本地仅文本源码、调度、运输精确合并和文档检查。此有状态单事件native试验未测多线程/GPU加速，0GPU不代表GPU一般无用。

| 资源 | pilot | admission/audit |
|---|---:|---:|
| job ID | 9674900.0 | 9674912.0 |
| starts／exit code | 1／0 | 1／0 |
| GNU CPU秒 | 112.29 | 1.10 |
| GNU wall秒 | 181.18 | 1.49 |
| GNU peak RSS KiB | 1989116 | 96132 |
| 脚本内部CPU秒 | 105.748384470 | 0.768320357 |
| 脚本内部wall秒 | 169.598674800 | 0.774968561 |

[唯一scheduler账目](stage154_energy_ml/scheduler_accounting.json)：2作业/2starts全部exit0，119CPU秒、200聚合执行wall秒，0live、0新G4/独立ν/能量fit/reserved forward，ROOT实读2433493B。嵌套计时不能相加。

[full准入](stage154_energy_ml/full_admission.json)为False：物理条件无eligible候选；另外保留原冻结平均execute成本模型，GNU112.29CPU秒、4次execute和69.626746378秒，3倍affine40预测2216.792152206秒+100预留>剩1083秒。第一execute实测69.606419541秒，后3次仅.008784125/.004476545/.007066167秒，显示lazy PyROOT/Cling初始化在首execute中占主导。**2216.79是这个保守模型的预测，不是full40实测成本，也不证明40父实际需要这么久。** 本阶段未事后修改模型或为此抬预算/重提full；后续合同可事前将首执行与steady事件成本分开。

[存储清理](stage154_energy_ml/storage_cleanup.json)把pilot原JSON文本精确合并为 `ntuples/energy_ml_stage154/event_records.json.gz`，2936B，原key `ntuples/energy_ml_stage154/pilot.json.gz`；保留source_snapshots.tar.gz 32233B及六份实际日志胶囊6843B、参考converter源码胶囊，删除7225660B重复运输，无持久ROOT/REC。旧证据与Stage54资产未动。

## 结论与下一步

本阶段固定精确几何方案按门停止，未运行40父或energy fit。已证实实际PRD几何与刚体坐标变换闭合；无评分候选，不能就空间信息对能量的价值作阴性物理判断。float32表示是具体且在小QA上相容的程序原因，尚未全量认证。Stage153同基底covariance缺口也没有被本阶段补齐。

[Stage155合同](stage154_energy_ml/next_execution_contract.json)先核同一旧REC的真实persistent schema，再以明确的float32舍入box及投影区间表示数值精度，不任意放大几何半径。仍原前4→最多同40、1200CPU秒/先物理和成本准入、无新G4/refit/energy fit；成本模型事前保留first-event初始化，后3次估steady执行。验收为真实schema、全部实际anchor表示支持、plane兼容性/数值区间宽度、真实非leading新位置内容与独立点积、首父重复及成本；schema或候选支持失败即结束固定实现，不换父/扫容差。Stage155尚未提交。

即使该几何测量成功，仍需独立μ辐射/data控制、真实covariance基底/transport/校准、全原队列能量风险与尾部。乳胶、GRL/背景/接受度、真实相关nuisance和独立确认缺口继续开放。Stage87、原cuts/K/角色、pz0-only一次方动量/raw11/typedNaN/合法signed/status0 timing/Calo缺失、全部原风险门和Stage137双低箱5%扩大门保持；整体目标未完成，不晋升模型。
