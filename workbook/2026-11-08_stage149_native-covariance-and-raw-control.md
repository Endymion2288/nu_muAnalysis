# Stage149：真实 μ 状态完整协方差、PRD 归属与 raw 配对控制

## 阶段目标与冻结范围

执行 [Stage148 的下一阶段合同](stage148_energy_ml/next_execution_contract.json)，推进 [Stage132 §5.5](2026-11-07_stage132_boundary-observability-research.md)。问题是取得真实重建状态的不确定度及测量链接，避免把点状态当精确；不是重开 Stage124 的 Z57 模型、Stage145 评分网格或新的能量回归。

原 HITS 前 4 条物理 pilot 通过后，按实测成本准入固定前 64 条。唯一控制输入为 MC100012、原 entries0–63，未根据尾部、风险、能量或选择结果换例。64 个不同原 entry，共执行 72 次物理 entry：首次失败输出的4次、成功 pilot4次、正式64次；重叠8次不计新独立样本。本阶段新 G4、新独立 ν、能量／响应 fit、旧评分 refit、reserved forward 均为0。

## 输入、实际条件与执行

[协议](stage149_energy_ml/protocol.json)逐字段保留原合同。

- HITS：`/eos/experiment/faser/sim/mc24/particle_gun/100012/sim/s0012/FaserMC-MC24_PG_muon_fasernu_100GeV-100012-00000-s0012-HITS.root`。
- 旧 PHYS：`/eos/experiment/faser/sim/mc24/particle_gun/100012/phy/s0012-r0023/FaserMC-MC24_PG_muon_fasernu_100GeV-100012-00000-00004-s0012-r0023-PHYS.root`。
- 原身份依据：`ntuples/energy_ml_stage146/event_records.json.gz` 中4096条原图根及身份记录，只使用前64对应项。
- 复用 pinned Calypso `d32b0ff3cc4a2dad4abfb1474a82422c3c25b305` 官方现成构建；只在 worker 中按需 Cling 加载 observer helper，没有重建完整软件，也没有 G4。
- 当前 digi/reco/ntuple 使用 `TI12MC04`、`FASERNU-04`、`OFLCOND-FASER-06`，native observer 插入官方 `--CKFTrackType merge` ntuple 作业，读取同一次 `CKFTrackCollectionMergeWithoutIFT`。
- [实际 HITS 元数据](stage149_energy_ml/input_metadata.json)：10000 entries、1205670747 B、`GeoFaser=FASERNU-04`、`IOVDbGlobalTag=OFLCOND-FASER-04`、`AtlasRelease=Athena-22.0.49`。几何匹配，conditions／release 不同；输入 G4 physics list 等未记录项目仍为未测量／未知。不能用当前 flags 认证旧输运已匹配当前 ν 或 data。
- waveform 私有流逐事件实际设为 `720000000+10000*original_event+1000*detector_index`，顺序 Calo/VetoNu/Veto/Trigger/Preshower；硅 digitizer 的 `Random.SeedOffset=2026110749`。保存真实 private RNG 初末状态，未把“只设全局 seed”当作完整随机性控制。

控制选择沿 Stage145：单条长轨迹、`50<pz0<2000 GeV`、至少7层、非负 χ²、`χ²/ndof<10` 且 ndof>0。它是 μ 控制选择，不改正式 ν cuts、原训练／测试角色或全部 K 覆盖。

主要执行命令如下；科学数组、ROOT、Cling、数字化及重建都在 HTCondor worker 中运行：

```bash
python3 ml/stage149_submit.py pilot
python3 ml/stage149_submit.py pilot_retry
python3 ml/stage149_submit.py admission
python3 ml/stage149_submit.py full
python3 ml/stage149_submit.py full_retry
python3 ml/stage149_submit.py audit
python3 ml/stage143_monitor.py --stage 149
python3 ml/stage149_finalize.py
```

底层官方参数为 `faser_digi.py --geom TI12MC04 --nevts N HITS`、`faser_reco.py --isMC --geom TI12MC04 --nevents N RDO`、`faser_ntuple_maker.py --isMC --geom TI12MC04 --CKFTrackType merge --nevents N --outfile ntuple.root REC`；seed／计时／原生快照由本阶段 wrapper 注入。精确 worker argv 在各 [pipeline 记录](stage149_energy_ml/full/pipeline.json)中。Calypso 与 LCG 提取进程用干净子环境隔离；BLAS 固定1线程，事件序列保持私有 RNG 顺序。

## 实测身份、协方差与选择

[完整审计](stage149_energy_ml/summary.json)、[逐轨迹协方差表](stage149_energy_ml/full/covariance.tsv)及[局部传播表](stage149_energy_ml/tangent_covariance.tsv)提供测得数值。

| 项目 | 实测 |
|---|---:|
| 原父／新 ntuple 事件 | 64 |
| 同 run/event、根 p4／生产顶点 float32 身份 | 64/64 |
| 原／新控制选中数 | 61/61 |
| old0/new0；old0/new1；old1/new0；old1/new1 | 3；0；0；61 |
| 真实新 leading 与同一新 ntuple 精确匹配 | 61/61 |
| 有限、对称、正定 full5×5 covariance | 61/61 |
| 原父中无 leading／无 covariance | 3/64，保留原父 |
| 选中且 `50<pz0<100 GeV` | 57 |
| 非零非对角项总数 | 1220，即每条20项 |
| 每条最大绝对非对角相关系数，最小／中位／最大 | 0.560425／0.941346／0.985139 |
| 实际 leading reference global z 范围 | 9.5–44.9700012 mm |

新拟合 pz **不要求等于旧 PHYS pz**。核对的是同一新 REC 所选的所有长轨迹状态、highest-pz0 leading 及同一新 ntuple，按 ntuple 实际 float32 精度精确比较，没有放宽成“近似身份”。

实际类型为 `Trk::CurvilinearParametersT<5,Charged,PlaneSurface>`（审计保存 RTTI 原字符串）及 `Trk::PlaneSurface`；每条保留真实 surface transform、完整25项 covariance、5个参数和实际 global 状态。以下局部坐标误差是该 fitted basis 下的量，不是已校准的探测器空间分辨率。

| 拟合标准差 | 最小 | 中位 | 最大 | 单位 |
|---|---:|---:|---:|---|
| σ(loc1) | 0.0101361 | 0.0131310 | 0.0178276 | mm |
| σ(loc2) | 0.374254 | 0.431406 | 0.517768 | mm |
| σ(φ) | 0.00380365 | 0.0401230 | 1.02406 | rad |
| σ(θ) | 2.49651e−5 | 2.04714e−4 | 7.12400e−4 | rad |
| σ(q/p) | 1.43734e−7 | 2.45623e−7 | 4.15321e−6 | MeV⁻¹ |

保留全部 offdiagonal，并作一次固定的一阶参数函数传播：`tx=cosφ tanθ`、`ty=sinφ tanθ`、`log(pz0)` 的导数为 θ方向 `−tanθ`、q/p方向 `−1/(q/p)`。得到61条的 σ(tx) 中位2.76336e−4、σ(ty) 中位3.93057e−5；σ(log pz0) 最小0.0133675、中位0.0237178、最大0.394096，均无量纲。这是 fitted covariance 的局部传播；尤其大误差和近束轴坐标情况下，不能由此许诺高斯区间覆盖。

**同面 truth residual、covariance pull、tracking bias、covariance 覆盖率仍未测量。** 没有以生成点 pz 差、假直线传播或任意 covariance repair 代替这些量。正定性及明显非零相关性证明完整不确定度可以读取，不能证明它已校准。

## 真实测量链接及 raw／状态

总2174个 cluster、1097个 TSOS cluster 测量；PRD 指针链接缺失0、cluster到raw-strip链接缺失0、invalid strip0。以下统计来自真实对象链接，未将 Identifier 相同就当作指针归属；shared 是子集，不能与其他列当互斥类别相加。

| station | leading-owned | other-owned、非leading | 多track共享 | unassigned |
|---|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | 706 |
| 1 | 357 | 11 | 5 | 168 |
| 2 | 353 | 12 | 0 | 126 |
| 3 | 353 | 6 | 0 | 82 |

IFT/station0未被 withoutIFT leading 使用，以及 μ 根控制中存在其他／未分配 cluster，都不自动等于其他初始根的强子活动。**这些归属计数不是关联后验概率，也不是“无关联不确定度”的证明。**

真实 conditions cable map 给出18个通道，包含合同的11 scint+4 Calo全部15通道；额外为 Veto11、Preshower2/3，同步保留审计。没有为了满足“15”而忽略真实映射。原代码的 `raw15_exact` 字段在本阶段实际核了整个18通道超集；准入另外逐名核对原15通道。[逐通道表](stage149_energy_ml/full/charge.tsv)包括 raw_charge、status 与 baselineRMS 的实际结果，完整配对事件另存紧凑缓存。

- 64/64事件逐字段 raw_charge/raw_peak/status/baseline/baselineRMS 与同一新 ntuple 精确闭合；1152个映射通道视图，1136个实际测量可用、16个实际无原生hit。后者保留为缺失，不把默认0当读出。
- status0为642视图、status1为505、status4为5；其中3个status0的 Calo1，其余 Calo 全status1；Calo status4为0。五个溢出视图为 Veto10×1、Veto11×1、Veto20×2、Veto21×1，不等于五个不同父事件。
- signed负raw视图245，全部按合法电荷处理；恰为−1的signed raw0例，−999/−9999/−99999 raw占位值0例，baselineRMS=−1为0例，leading χ²负值0例。正值量仍要求合法正值，不能推广成“所有−1都删掉”。
- 非0 status导出有限 localtime 的数量0；没有使用 fitted charge，也没有把内部pulse或弱信号峰当测得到达时间。
- 成功 pilot 与 full 的 entries0–3：native记录、配对字段、真实 waveform RNG before/after 全部精确复现。首次输出失败的4例不冒充额外验证分母。

## 程序失败、资源与存储

首次 pilot 的 native 过程实际读取4例，但最终 cable-map 的 C++ string 代理不能 JSON 编码，官方进程没有将 finalize 错误传播为非0退出；下游 JSON 验证正确阻止通过。修复为显式 `str` 并先完整序列化再写压缩输出。同一前4例重跑成功。[失败审计](stage149_energy_ml/failure_audit.json)保留原因及成本，未换有利例。

首次 full 在 AFS 读取启动脚本时超时，exit126，科学entry执行0、CPU0；改为 transfer worker 脚本并用 basename 从 scratch 启动。[基础设施审计](stage149_energy_ml/infrastructure_failure.json)保留记录。

| 作业 | 用途／结局 | scheduler CPU s | execute wall s |
|---|---|---:|---:|
| 9674618 | 首次pilot，JSON失败 | 156 | 194 |
| 9674632 | 修复同前4例，通过 | 156 | 235 |
| 9674651 | 准入审计，通过 | 0 | 5 |
| 9674657 | AFS启动失败，未执行科学事件 | 0 | 4 |
| 9674663 | 固定前64例，通过 | 185 | 256 |
| 9674677 | 复现／最终审计，通过 | 0 | 5 |

[调度汇总](stage149_energy_ml/scheduler_accounting.json)：6次start全部终态，497 scheduler CPU秒、699聚合execute wall秒、GPU0，低于3000秒；两个轻审计的scheduler CPU记录为0是计数精度，不能解释成无需CPU。两次pilot累计312秒低于800 allowance。无应用短timeout，MaxRuntime86400秒，request4CPU/12GB。串行私有随机流与官方事件链本阶段不使用GPU。

[原准入](stage149_energy_ml/full_admission.json)使用3个post-first间隔实测：digi0.368059273、reco0.690983047、native0.067544198 CPU秒；含初始化的三倍affine64预测523.05519108秒，另留100秒审计。原准入时剩2688秒，满足合同，未事后改预算。

[资源计数](stage149_energy_ml/resource_audit.json)：full digi GNU CPU78.29秒、reco21.88秒、native77.46秒、extract3.38秒；它们包含在scheduler中，不能再次相加。full pipeline wall246.232850秒，按64父的全链吞吐约0.260父/秒，仅限此已计初始化的小控制。GNU最大RSS2065356 KiB；ROOT全进程读计数digi35364792 B、native17459284 B，包含conditions／初始化读，不声称全是hit payload；提取另读247243 B。reco独立ROOT读计数、失败尝试全体累计ROOT读字节未测量。

full临时RDO/REC/ntuple合2240586 B，验证提取后全部删除；成功pilot合319067 B也删除。没有持久化ROOT/xAOD。[清理审计](stage149_energy_ml/storage_cleanup.json)记录：事件原文本精确合并为 `ntuples/energy_ml_stage149/event_records.json.gz`，2245381 B，低于8MiB；格式为原相对路径→原JSON文本字符串，恢复 `.gz` 时重新gzip该文本。源码快照 `software/stage149/source_snapshots.tar.gz` 100558 B；重复运输／散事件删除11669571 B，3份相同输入metadata合一，12份worker日志压缩为99603 B。原HITS/PHYS、共享runtime、Stage54和其他阶段产物未动。提交目录为 `~/condor/nu_muAnalysis/stage149/`。

## 阶段结论与下一步

本阶段证实：该已知 μ 根控制可在当前官方链中取得并精确配对 **真实raw、完整state covariance、surface以及真实PRD/TSOS链接**，而不再只记录一个点状态。61条完整 covariance 普遍有强相关，不能将新增数据解释为已校准的不确定度；3个失败父、16个无hit视图保留。原两低箱能量收益、本阶段新ν性能和总体FPR均未测量。

下一按[Stage150冻结合同](stage149_energy_ml/next_execution_contract.json)补§5.4尚缺的真实Ecal clipping方法控制：先仅审计既有4032父的role1和实际保留calo_status支持；若非空，只重放原frame顺序首个overflow父，最多1个同父G4、1000CPU秒，以实际780–930ns窗核总ADC/来源与非线性删失。若无支持，交付明确的有限队列支持缺口，不人工裁切替代、扩库存或换例。先支持／成本、后执行，保留K与所有原角色，不启动自然ν大生产或旧模型网格。

Stage132其余真实协方差校准、关联不确定度、宽能区与data迁移、乳胶匹配、真实曝光GRL／背景／全生成接受度、相关nuisance辅助输入及独立确认仍缺。Stage87 direct62、原1.05/1.01/1.03与八层三尾上95≤+2pp、Stage137双低箱5%扩大门保持；1.05仍仅非劣效。pz0-only一次方动量、允许px/py/q/p/弯折、raw11、typedNaN／合法signed、非0status无timing、Calo缺失、全部K／角色及reserved关闭不变。整体研究目标尚未完成。
