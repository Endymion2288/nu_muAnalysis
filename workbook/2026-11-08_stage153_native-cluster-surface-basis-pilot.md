# Stage153：真实 cluster 空间关联的同面／基底支持 pilot

## 阶段目标与冻结范围

执行 [Stage152 冻结合同](stage152_energy_ml/next_execution_contract.json)，原字节保存为 [protocol](stage153_energy_ml/protocol.json)。本阶段只回答：在旧 REC 保存的 leading 测量面上，能否直接用真实非 leading cluster 的局部位置和 fitted-state 方差，形成新的 covariance-scaled separation？不训练能量模型，不扩自然 ν 或重跑输运，不把访问到 covariance 当作误差已校准。

输入固定为 Stage124 `native_contract.json` 的 request0、origin55/source_index0、π/run200082；只取原 REC entry 排序前40个 role1，未使用 cal/test/reserved/role4/隔离、真能量或风险选择，未更换父或扫描库存。REC 为 `/eos/experiment/fasernu-data0/faser/sim/mc24/genie/200082/rec/s0014/FaserMC-MC24_Genie_epos_pi-200082-00000-00009-s0014-xAOD.root`。PHYS 为 `/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/merge_mc24_master_d32b0ff3/200082/FaserMC-MC24_Genie_epos_pi-200082-00000-00009-s0014-merge-PHYS.root`。

读取 pinned d32 tracker-only PoolRead/MergeTrack，geometry FASERNU-04、conditions OFLCOND-FASER-06；没有 digi/reco refit、G4 或完整 NtupleDumper。PHYS 只读 run、eventID、longTracks、SpacePoints、Track_pz0、nClusters0–3。pz0 原容差 rel3e−7/abs3e−5 GeV 未放宽。一次方动量仍只用 pz0；本阶段没有引入 p0/p1。raw11、typed NaN、合法 signed、status0 timing、Calo 缺失及所有原 cuts/K/角色政策保持。

## 工作内容与实测结果

新增 `ml/stage153_native.hxx/.py`，读取实际 PRD 对象、leading TSOS、COT localParameters、真实 measurement/state surface RTTI 和完整4×4变换、5参数与25项 covariance。leading-owned PRD 按真实对象排除，不按坐标近邻猜归属。只有唯一 wafer anchor、真实链接/identifier、measurement 非 outlier、一维 locX、完全相同的面与基底、有限正相关方差才允许计算 `r2=(cluster loc1−state loc1)^2/(cluster variance+state variance)`。它原本也只是 scaled separation，而非 pull、χ²覆盖或关联后验。无效量保留为 JSON null/NaN 语义，不修 covariance 或删除父。

[完整审计](stage153_energy_ml/summary.json)及[站支持表](stage153_energy_ml/station_support.tsv)实测：

| 检查 | 实际结果 |
|---|---:|
| 原父数／原身份、pz0 及旧四站 cluster/SP/longTracks 一致 | 40／40 |
| 第一父同进程 native 重复 | 精确一致 |
| leading 测量 anchors | 697 |
| 真实 PRD 链接／identifier 一致／Measurement | 697／697／697 |
| Outlier／缺失链接 | 0／0 |
| 有限完整 covariance、正 loc1 state variance | 697 |
| 满足冻结的一维 locX 条件 | 0 |
| measurement/state 面变换完全相同 | 0 |
| 可用 wafer anchor／eligible candidate | 0／0 |
| 保留小型 QA 父 | 4 |

维数失败与面不一致是重叠原因，不能相加为1394个独立测量。measurement/state RTTI 均为 `Trk::PlaneSurface`，但参数类型为 `Trk::CurvilinearParametersT<5,Charged,PlaneSurface>`；同为 PlaneSurface 不等于同一个面／坐标基底。每父最大的变换逐元素差范围12.31012237548828–63.36991822719574，40个父均不同。该诊断混合无量纲旋转元素和以 mm 表示的平移元素，不能称为物理距离。

| station | clusters | leading-owned | nonleading | 在 leading 测量 wafer 上 | 在其他 wafer 上 | 支持的 anchors |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 3910 | 0 | 3910 | 0 | 3910 | 0 |
| 1 | 581 | 230 | 351 | 63 | 288 | 0 |
| 2 | 616 | 229 | 387 | 29 | 358 | 0 |
| 3 | 520 | 238 | 282 | 56 | 226 | 0 |

所以不能说样本没有非 leading 活动。站1–3在同 wafer 上的63/29/56个候选因 anchor 不支持而无法计算冻结量。站0由 withoutIFT leading 没有测量面，单独报告，不填0分数。全部站的 candidate_N 特征和三个 score 统计均保持未知；计数诊断中的 eligibleCandidates=0不等于“已知没有空间活动”。后续 candidate surface/variance/RDO 检查未被执行，其0计数也不认证这些属性。

**本阶段 r2 数值验证、state/candidate 同面 roundtrip、score 动态范围均未测量。** 输出里的 independent max-delta=0只是空候选累加器初值，不能写成独立算术已验证零差；[审计语义](stage153_energy_ml/audit_semantics.json)对此作出明确说明。没有 FPR、能量风险、关联概率、pull覆盖率或低能优于传统方法的测量。

## 程序原因与物理解释边界

[静态源码记录](stage153_energy_ml/basis_source_notes.json)核对 pinned d32 `CreateTrkTrackTool.cxx`：构建含 loc1/loc2 的 COT；转换函数建立 CurvilinearParameters，并复制 bound covariance 的左上块和 q/p 单位换算，函数内未见显式空间基底 Jacobian。该代码不是本阶段重新执行的重建器，也没有认证为历史 REC 的实际生产版本，因此只是表示风险的源码依据。真正的本批证据是原 REC 实测的参数类型及697次面变换不一致，不能由源码推断所有旧 covariance 都错。

Stage124 旧 `s[22:24]` 直接将 COT locX 与 state locX 相减，未证明共同坐标面。现在不能再把这些旧工程摘要当作物理 residual/pull 证据；保留其历史能量结果原文，不修改旧模型或用本例重写其统计结论。Stage87 direct62 不依赖原生 Z57 扩展，仍为基线。本阶段也没有证明空间信息无用；当前失败的是“直接使用保存的 local state/covariance”这个固定实现。

[ACTS 论文](https://arxiv.org/abs/2106.13593)本阶段实际读取摘要，支持使用 geometry-aware tracking 接口，但未借其摘要声称本项目已认证 covariance 变换。CMS PF 和 Deep Sets 引用沿用 Stage132/152，不导入 CMS 性能、不新建网络。访问 ACTS 在线 track-fitting 文档得到 HTTP403，未读内容不作为证据；详见[文献记录](stage153_energy_ml/research_sources.json)。

## 执行、性能和存储

实际命令：

```bash
python3 ml/stage153_submit.py native
python3 ml/stage143_monitor.py --stage 153
tar -xzf ntuples/energy_ml_stage153/native_result.tar.gz
python3 ml/stage153_submit.py audit
python3 ml/stage143_monitor.py --stage 153
tar -xzf ntuples/energy_ml_stage153/audit_result.tar.gz
python3 ml/stage153_finalize.py
```

科学 ROOT/Cling/数组及统计全部在 HTCondor scratch 执行，AFS 仅调度和日志；本地只做代码文本、运输解包／逐文本精确合并和文档检查。提交目录 `~/condor/nu_muAnalysis/stage153/`，transfer worker/package 后以 basename 执行。请求4CPU/12000MB、MaxRuntime86400s、累计预算1200CPU秒、预留100秒审计，无应用墙钟限时。该 native StoreGate pilot 为单事件序列，未测多线程或 GPU 加速，不把4CPU请求当作4倍吞吐。

| 资源 | native | audit |
|---|---:|---:|
| job ID | 9674875.0 | 9674884.0 |
| starts／exit code | 1／0 | 1／0 |
| GNU CPU秒 | 110.06 | 0.80 |
| GNU elapsed秒 | 137.60 | 1.06 |
| GNU peak RSS KiB | 1781128 | 82040 |
| 脚本内部 CPU秒 | 103.824619764 | 0.689410984 |
| 脚本内部 wall秒 | 128.923181692 | 0.701338038 |

[调度记账](stage153_energy_ml/scheduler_accounting.json)两作业合计116CPU秒、156聚合执行wall秒、2starts、全部终态exit0；这些与嵌套计时不同，不能相加。ROOT实际读取3615643B，无持久 REC/ROOT；0GPU、0G4、0新独立ν、0能量fit、0reserved forward。冻结支持失败后没有 full pool 或能量 fit。

[存储清理](stage153_energy_ml/storage_cleanup.json)：原 native JSON文本精确合并为 `ntuples/energy_ml_stage153/event_records.json.gz`，10812B，原key `ntuples/energy_ml_stage153/native.json.gz`。保留 `software/stage153/source_snapshots.tar.gz`（29249B）与实际worker日志胶囊（6164B，6份逐字节一致），另保留很小的 pinned参考源码胶囊。删除7245092B重复 package/result/native transport，无持久ROOT。其他阶段证据与历史Stage54未动。

## 阶段结论与下一步

Stage153 固定同面 covariance-scaled 实现因保存格式／坐标基底支持缺口而结束，程序读取、父身份与计数审计通过。有限正 covariance 不能解决这项基底问题，也未证明低能目标失败或成功。原两低箱／传统上95≤1.05、all/f0≤1.01、其他五层≤1.03及八层三向尾差上95≤+2pp、Stage137双低箱5%扩大门、Stage87和整体未完成状态保持。1.05仍只是非劣效。

[Stage154 独立冻结合同](stage153_energy_ml/next_execution_contract.json)改问“真实全局 fitted position 是否落在实际硅片上，以及可否由此定义**不归一化**的局部 dx”：同原request0 role1前4作物理／成本pilot，严格几何 roundtrip、plane距离及原身份通过后，按3倍成本＋100秒预留准入同原前40，累计1200CPU秒。它不是放宽 Stage153 面匹配或把旧 covariance 随意旋转；只从实际全局位置变换到真实 wafer frame，明确允许含locX的二维COT，既不使用 curvilinear locX 相减，也不计算 sigma-normalized 量。

验收为实际全局／局部几何闭合、非 leading新位置内容、独立点积复算与实测成本；无支持即结束这个新几何实现，不调整容差或换父。通过后仍须另冻 μ辐射／data控制及全原队列能量比较，不能自动 full/fit。Stage154本阶段尚未提交。总体 μ响应、covariance校准、关联后验、宽能区/data迁移、乳胶、GRL/背景/接受度、真实相关系统与独立确认仍是开放任务，不用虚构输入填补。
