# 阶段 17：Backward 通过、merge 失败事件的空间特征与逐轨迹机制

## 阶段目标

延续阶段 09/10 的同源 forward/backward/merge 比较，研究 **backward 最终完整选择通过、merge 最终完整选择失败** 的事件。检验动量、径向位置、相互作用 z 和重建轨迹 z 的规律，并区分物理分布、拟合候选差异、merge 去重及最高 pz leading-track 选择的作用。

本阶段已完成全量 89 个目标事件的逐一复现和验收，生成统计图、逐事件诊断表、11 组静态事件图和包含全部 89 个事件的离线交互浏览页。

## 输入、选择与比较基线

- 阶段 10 缓存：`workbook/stage10_tracking_z/fiducial_events.npz`，342 个相同 RDO、383,670 个共同 truth-fiducial 事件；上游全样本为 3,374,987 events。
- run：200080、200082、200083、200089、200093、200094、200100；清单沿用 `tracking_comparison_manifest.tsv`。仍共同排除没有已发布 merge 的原 manifest index 291，没有新增剔除离群事件。
- 官方 Calypso `d32b0ff3cc4a2dad4abfb1474a82422c3c25b305`，Athena 24.0.41、TI12MC04/FASERNU-04/OFLCOND-FASER-06，without-IFT、无 CaloNu；使用已编译归档，没有改物理代码或重新编译。
- cuts/definitions/helper 沿用 `config/{cuts,definitions}.yaml` 和 `include/RDFDefines.h`，最高 pz 定义 leading track；原生 VetoNu reduced charge，20 个 MC 有效 cuts，14 个重建累计位。
- **目标集合**：`backward_bits == 16383 && merge_bits != 16383`，共 **89 events**，分布在 **81 个 RDO 文件**。对照集合是全部 **103,985 个 backward 最终通过事件**，包含这 89 个事件。不是用全真值样本或 merge-only 样本作为条件损失率的分母。
- 最终 merge 通过 **104,930**，merge-only **1,034**、backward-only **89**、共同通过 **103,896**；merge 相对 backward 仍净增加 **945 events**。

物理量含义：`truth_pz_nu` 为中微子真值 pz（GeV），**不是 μ 动量**；`truth_dec_r` 是真值相互作用顶点半径（mm），不是重建轨迹半径。`LeadTrack_r_atMaxRadius` 为拟合 track states 上最大半径，`rIFT` 沿用当前分析的 **VetoStation2 外推半径**。真值相互作用 z、轨迹首个 state 的 z 和最大半径处的 z 分开报告。

所有计数均未加权，含 SIBYLL 替代样本；另提供排除 200080 的结果。没有测量系统误差、flux 权重、primary-muon truth matching 或真实数据的对应损失率。

## 工作内容与验证方法

### 1. 条件损失率与空间分析

直接读取已有 6.6 MiB 缓存，计算每个动量、半径、z bin 的 `merge fail / backward pass`，保存分子、分母和 **95% Wilson 区间**；空分母记 NaN。z 选择空隙 −1950 至 −1769.65 mm 留空，未插值成零效率。

同时保留所有 14 个累计重建阶段的 backward-only/merge-only 计数，避免把最终损失误认为所有 tracking 阶段损失。例如 long-track 阶段 backward-only 是 **276**，pz cut 后是 **423**，最终才是 **89**。后续事件级 cuts 会共同剔除一部分早期损失。

新增未惩罚 logistic 关联模型，以 backward 最终通过事件为样本、是否最终损失为响应：

`logit P(loss) = intercept + (r−60)/20 + (z+2400)/500 + log2(pz/700) + lead_region + run_dummies`。

模型同时控制 r、z、中微子 pz、box/lead 区域和 run。报告观测信息矩阵的 Wald 95% 区间及梯度收敛；排除 200080 后独立拟合。它是探索性关联模型，89 个稀有响应、11 个参数，不能把系数当成材料/算法机制的因果测量。三个二分对照同时报告 Fisher 双侧 p 值及三项 Bonferroni 校正；二分阈值为探索性诊断，不作为预注册发现检验。

### 2. 单事件重建与程序机制

先在已发布 merge 中只读 run/eventID 定位 entry，再用原 RDO `--skip entry --nevents 1` 重建一次，同一 xAOD 分别制作 forward、backward、merge。只对 89 个目标事件重建，没有重新扫描/重建全部 3.37M events。

小样本为 run 200080 / event 33925，完整流程实测通过后提交 HTCondor **1543524，89 jobs**，每 job 1 CPU、3000 MB memory、2000 MB disk、longlunch；OMP/OpenBLAS/MKL 固定 1。proc 0 验证已有 pilot 后跳过，其余 88 项计算；event log 记录 **89/89 正常退出，退出码全部为 0**。

每个事件必须通过：

1. 三模式 run/eventID 与目标一致，17 个原始非轨迹列精确相同。
2. 三模式 14-bit 累计选择与阶段 10 的对应事件逐项一致。
3. 新 merge 和已发布 merge 的全部持久化 `Track_*`、space points、truth 原始列逐项精确相同，含 NaN 一致。
4. backward leading track 在 merge 中是否保留，使用位置、动量、charge、χ²、nDoF 精确指纹检查，并以原始 TrackCollection 的所有 states 和 fit quality 再确认。
5. 对被移除者，实际保留的 merge 候选必须与其共享 **>6 measurements**，并满足官方排序优先级：更多 measurements，或数目相同但 χ²/nDoF 更小。共享比较使用官方相同的 station/layer/side/strip 四元组。

`inspect_tracking_loss.py` 通过 Python 诊断算法读取原始 TrackCollection 的 measurements 和 states，未改变 track 拟合/排序。避免直接按 `Track_nMeasurements` 与输出轨迹索引配对：本样本有 **10 组模式数组长度不匹配**，对应 5 个无 merge long-track 事件的 forward/merge；该已知填充位置问题在阶段 05 已记录。

最终 89 个 JSON 原占 **9,341,418 bytes**，精确合并、解压读回核验后形成唯一 `ntuples/tracking_loss_stage17/diagnostics.json.gz`，**1,631,509 bytes**。RDO/xAOD/ntuple 只存在于临时 scratch 并随退出清理；合并核验后删除 89 份 JSON 及 1 份重复验证 JSON，XRootD 目录核验只保留该压缩文件，详见 `storage_summary.json`。

### 3. 可视化与验收

- [全部事件交互浏览页](stage17_tracking_loss/event_viewer.html)：不依赖外部网络，按首次失败 cut 筛选，切换 x–z/y–z、纵轴中心及放大倍数，显示 leading/其他 long tracks、非 long 候选、space points；右图比较 VetoStation2 外推点与 95 mm 圆。
- [总体分布与条件损失率](stage17_tracking_loss/population_and_loss_rates.png)：每 bin 同时展示样本比例及条件损失率，不能把上排的原始形状差异直接当作效率。
- [空间分布与失败步骤](stage17_tracking_loss/spatial_and_failures.png)：x–y 空间、r–z 联合分箱、首次失败 cut。
- [配对重建轨迹诊断](stage17_tracking_loss/paired_track_diagnostics.png)：B/M 动量、最大半径、外推半径、最大半径处 z 与机制分解。

轨迹图使用原始拟合 states；只连接测量面 states，不伪造磁场区的连续传播拟合。近似 tracker station z=0、1190、2380 mm 参照 `../EventDisplay_PHYS/src/DetectorRender.py`。该工具默认启用 pixel preshower 几何，与本样本不匹配，因此本阶段复用坐标思路制作专用对照图，未直接套用其整套 detector display。space points 在 SVG 中栅格化以压缩高占有率事件图，轨迹和坐标轴保留矢量。

验证：Python 编译、shell 语法、HTML 内嵌 JSON 的 89 个唯一事件、5 个无 merge long-track 事件均通过；Node JavaScript 语法通过；以 DOM 桩运行全部 89 个事件、两个投影、缩放、cut 筛选和前后翻页，SVG 数值属性有限且事件一致。未做真实浏览器渲染自动化测试；已人工检查代表性 PNG。

## 详细数据与阶段性结论

### 条件损失率：半径和 z 有关联，未看到明确的中微子动量依赖

| 对照区域 | 损失 / backward 最终通过 | 条件损失率（%，95% Wilson 区间） |
|:---|---:|:---|
| 全部 | 89 / 103,985 | 0.08559 [0.06956, 0.10530] |
| 排除 SIBYLL run 200080 | 77 / 88,965 | 0.08655 [0.06926, 0.10815] |
| 真值 r < 80 mm | 46 / 81,314 | 0.05657 [0.04242, 0.07544] |
| 真值 r ≥ 80 mm | 43 / 22,671 | 0.18967 [0.14085, 0.25537] |
| 真值 z < −2400 mm | 31 / 53,668 | 0.05776 [0.04070, 0.08198] |
| 真值 z ≥ −2400 mm | 58 / 50,317 | 0.11527 [0.08919, 0.14897] |
| 真值中微子 pz < 500 GeV | 30 / 36,151 | 0.08299 [0.05814, 0.11844] |
| 真值中微子 pz ≥ 500 GeV | 59 / 67,834 | 0.08698 [0.06744, 0.11217] |
| FASERν box | 81 / 99,090 | 0.08174 [0.06578, 0.10158] |
| Lead block | 8 / 4,895 | 0.16343 [0.08284, 0.32219] |

外侧/内侧条件损失率比 **3.3528**，Fisher p=3.81×10⁻⁸；z 下游/上游比 **1.9956**，p=0.00193；中微子 pz 高/低比 **1.0481**，p=0.9115。三项校正 p 分别 **1.14×10⁻⁷、0.00578、1.0**。

分布中位数：损失/全部 backward 的真值半径 **79.24 / 59.77 mm**，真值 z **−2234.44 / −2414.86 mm**，中微子 pz **762.98 / 685.17 GeV**。不能仅凭最后一个中位数差称为动量效应。

| 联合模型变量 | 全样本调整后 odds ratio [95% CI] | 排除 200080 后 |
|:---|:---|:---|
| 真值 r 每增加 20 mm | 1.850 [1.495, 2.290] | 1.911 [1.513, 2.413] |
| 真值 z 每向下游增加 500 mm | 2.300 [1.505, 3.513] | 2.387 [1.509, 3.774] |
| 真值中微子 pz 翻倍 | 1.074 [0.868, 1.330] | 1.083 [0.863, 1.360] |

全样本对应 Wald p 为 1.52×10⁻⁸、1.17×10⁻⁴、0.512。两个模型最大绝对梯度 **3.24×10⁻⁷ / 3.17×10⁻⁷**。在此模型假设下，r、z 关联不是仅由 run 混合或 pz 谱差异解释；没有证据断言不存在其他非线性或 μ 动量依赖。

### 失败 cut 与轨迹机制

| Merge 首次失败 cut | 事件数 | 原 backward leader 被移除 | 保留但不再 leading |
|:---|---:|---:|---:|
| 至少一条 long track | 5 | 5 | 0 |
| track pz > 100 GeV | 21 | 21 | 0 |
| nDoF ≥ 9 | 10 | 4 | 6 |
| χ²/nDoF < 15 | 3 | 3 | 0 |
| 最大轨迹半径 <95 mm | 23 | 13 | 10 |
| IFT 外推半径 <95 mm | 26 | 26 | 0 |
| θ <25 mrad | 1 | 1 | 0 |
| 合计 | **89** | **73** | **16** |

这是原 cut 顺序下首次失败分类，不排除同一个候选还会失败于其他 cuts。**49/89（55.06%）首先失败于两个 95 mm 半径 cuts**，21/89（23.60%）首先失败于动量阈值。

**73 个去重损失**中，31 个由更多 measurements 的候选胜出，42 个由相同 measurements 数、较小 χ²/nDoF 的候选胜出。官方 merge 在此处做候选排序及去重，没有对胜出的 track 重新拟合；所以损失的直接来源是保留哪个原始拟合结果，而非 merge 引入了新的拟合偏移。

**16 个改选 leading 的损失**中，原 backward 好轨迹仍精确保留，其 track cuts 仍通过；最高 pz 的另一个候选成为 leading。10 个首先失败于 rmax，6 个首先失败于 nDoF。若仅诊断这 89 个损失事件，允许保留的原 backward 候选参加选择就能恢复这 16 个；尚未在完整样本测量 any-good-track 规则的背景、产额或系统效应，不能直接把它当成可部署选择。

有 merge leading 的 **84/84** 个事件，其 leading 均标记为 forward；另 5 个没有 merge long track。这是该条件损失集合的观测，不说明全体 forward 轨迹质量更差。

### 动量：候选重建跨阈值是真实机制，但不等于中微子谱规律

21 个 pz 首次失败事件的 backward leading pz 最小/中位/最大为 **100.012 / 128.111 / 1936.897 GeV**；merge 为 **29.292 / 87.713 / 99.858 GeV**。既有阈值附近的小迁移，也有较大的候选拟合差异。

例如 [200080/33925](stage17_tracking_loss/event_200080_33925.png)：F/B 均有 18 measurements，**全部 18 个共享**；χ²/nDoF 为 **6.2957 / 7.0354**，merge 选择 forward。Backward pz **149.272 GeV** 通过，merge **75.449 GeV** 失败。两条轨迹的空间投影很接近，但曲率/动量估计不同；仅看全视野事件图容易忽略。

本阶段没有 primary-muon truth matching，因此不据此宣称哪一个候选动量更接近真实 μ。极高重建 pz 也没有被截掉：例如 200094/95906 的 merge pz 为 **20,802.814 GeV**，保留为诊断对象，不作为停止分支的理由。

### 半径：明显的边界迁移，兼有换轨迹造成的大变化

26 个 IFT 首次失败事件，backward rIFT 最小/中位/最大为 **83.175 / 94.154 / 94.987 mm**；merge 为 **95.030 / 95.312 / 98.239 mm**，显示大量 95 mm 接受度边缘事件跨阈值。

例如 [200094/223588](stage17_tracking_loss/event_200094_223588.png)：rIFT 从 **94.9153 mm** 变为 **95.3148 mm**，仅相差 **0.3995 mm**，但使事件从通过变为失败。交互页可缩小纵轴半宽查看亚毫米位置差。

23 个 rmax 首次失败事件中，backward rmax 中位 **93.650 mm**，merge 中位 **95.998 mm**；merge 最大达 **158.215 mm**。因此不能把所有损失都描述为亚毫米边缘迁移：10 个事件是保留好轨迹后改选 leading，可能伴随更大的径向变化。

### z：相互作用下游偏好与径迹半径位置是两个观测

真值顶点 z 的下游关联见条件损失率及联合模型。它不等于轨迹从更下游开始：89 个 backward leaders 的首 state z 最小/中位/最大为 **9.500 / 17.445 / 52.915 mm**，均在第一 spectrometer tracking station 附近。

按最接近 z≈0、1190、2380 mm 的 station 归类，最大半径处 z 的分布：backward **43 / 4 / 42 events**，merge **35 / 4 / 45 events**（另 5 个无 merge track）。仅看 23 个 rmax 首次失败者，backward **5 / 0 / 18**、merge **1 / 0 / 22**，因此其中 **22/23** 的 merge 最大半径出现在最后 station 附近。这与沿 spectrometer 传播后的径向接受度有关，但尚未分解磁场弯曲、散射、错误 hits 和候选混入的各自比例。

### 5 个 long-track 丢失：merge 与下游 station 要求之间存在不一致

| run/event | Backward measurements | 阻挡候选 measurements | 不同 strip 四元组 | 共享 measurements | 阻挡候选 stations |
|:---|---:|---:|---:|---:|:---|
| 200083/617054 | 15 | 16 | 13 | 10 | 2,3 |
| 200089/170435 | 14 | 16 | 16 | 11 | 2,3 |
| 200094/252438 | 14 | 16 | 13 | 8 | 2,3 |
| 200094/270113 | 14 | 14 | 11 | 9 | 2,3 |
| 200094/638706 | 18 | 18 | 15 | 13 | 2,3 |

所有阻挡候选都缺 station 1，而 backward 好轨迹覆盖 stations 1/2/3。前三个以更多 measurements 胜出，后两个以同数 measurements、较低 χ²/nDoF 胜出。随后 NtupleDumper 又要求同时覆盖 stations 1/2/3，阻挡候选被排除，merge 的 longTracks 变成 0。

其中 4/5 的阻挡候选各含 **3 个重复 strip 四元组**；另一个虽有 16 个不同 strips，也只覆盖 **12 个不同 station/layer/side 面**。因此 measurement 总数不能替代 station 覆盖或独立测量面数。这里只确认程序行为，尚未定位重复 measurements 是如何进入原始 CKF 候选的。

[200094/252438 事件图](stage17_tracking_loss/event_200094_252438.png) 显示：backward 轨迹覆盖三个 stations；merge 原始候选的虚线只覆盖 stations 2/3，虽然没有 merge long track，候选本身仍可见。该事件真值 r **21.610 mm**、backward rmax **22.862 mm**，也说明这类问题并非只发生在径向边缘。

## 性能、存储与执行记录

小样本 pipeline 实测墙钟：locate **7.25 s**、RDO staging **2.13 s**、reco **14.54 s**、forward **9.91 s**、backward **9.75 s**、merge+原始 measurements 诊断 **73.63 s**、extract **21.69 s**。最大 RSS 为诊断阶段 **1,888,768 KiB**。诊断计时包含 PyROOT 对新 C++ 类型/接口的解释及 measurements 读取开销，未测量严格的分项占比，不与正常 maker 性能直接比较。

下表为最终采用的 **89 个成功实例**，含 pilot 加 88 个 Condor 计算；不包含重复验证、setup、队列等待和汇总绘图。

| 步骤 | 墙钟 min / median / max（s） | 合计墙钟（s） | 最大 RSS（KiB） |
|:---|:---|---:|---:|
| ID 定位 | 3.51 / 11.93 / 45.49 | 1051.72 | 63,652 |
| RDO staging | 0.75 / 5.00 / 12.19 | 428.09 | 2,240 |
| reco | 10.86 / 18.42 / 57.09 | 1748.13 | 1,025,540 |
| forward | 7.49 / 11.72 / 20.02 | 1034.99 | 915,216 |
| backward | 7.39 / 11.52 / 17.57 | 1010.71 | 917,048 |
| merge + measurements | 64.66 / 145.69 / 337.76 | 12287.20 | 2,133,488 |
| extract / 验收 | 19.55 / 30.41 / 40.83 | 2612.79 | 743,664 |

合计分步骤墙钟 **20,173.63 s**、CPU user+system **13,136.95 s**；并行运行，不能把墙钟求和当成用户等待时间。线程未超配，没有据节点差异推断加速比。`resources_by_event.tsv` 保存逐事件计时，`resources_summary.tsv` 保存汇总。

最后返回的 proc 52（200093/386752）曾出现 EOS/FUSE 目录列出但 `open/stat` 不可见的情况：XRootD stat 确认目标 **32,008 bytes** 存在，使用 xrdcp 读取后完成验收。该 job 正常退出；其 recovered stdout 保存在 `logs/tracking_loss_stage17_job52_recovered.log`。没有将它归因为异常物理事件。为核对曾额外交互复现同一个事件：所得 JSON 与 Condor 结果 **逐字节一致**，额外七步墙钟合计 **137.22 s**，不混入上表；重复产物已去重。没有测量底层 FUSE 缓存故障根因。

总体事件统计和绘图实测 **5.952 s、273.402 MiB 峰值 RSS**；逐轨迹汇总和 11 组示例绘图实测 **24.028 s、206.898 MiB 峰值 RSS**，详见 `population_summary.json`、`details_summary.json`；这些属于小型缓存计算，无需重新提交全量重建。

## 产物与重现命令

核心表格：`loss_events.tsv`（89 IDs、真值变量、三模式位掩码、首次失败）、`event_mechanisms.tsv`、`mechanism_by_cut.tsv`、`nonlong_blockers.tsv`、`kinematic_bins.tsv`、`joint_z_radius.tsv`、`adjusted_logistic.tsv`、`exploratory_contrasts.tsv`、`groups.tsv`、`stage_losses.tsv`。PNG 和 SVG 同时保存，交互页只含绘图必需信息，原始诊断只在 EOS 留压缩单份，Git 不提交 ROOT/原始 JSON 数据。

```bash
# 利用既有事件缓存生成条件损失率；不需要 Calypso
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python3 AnalysisZipFramework/scripts/report_tracking_loss.py

# 利用已合并的 89 个诊断重新生成机制表、静态示例和离线 HTML
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python3 AnalysisZipFramework/scripts/report_tracking_loss_details.py \
  --combined ntuples/tracking_loss_stage17/diagnostics.json.gz \
  --example 200080/33925 --example 200094/223588

# 冻结的重建诊断软件包（已在 EOS 留存）
tar -czf software/tracking-loss-stage17.tar.gz setup_env.sh \
  AnalysisZipFramework/scripts/{inspect_tracking_loss,extract_tracking_loss,compare_tracking}.py \
  AnalysisZipFramework/config/{cuts,definitions}.yaml AnalysisZipFramework/include/RDFDefines.h

# 正式提交前已完整运行 1 个目标事件并通过新旧输出核验；89 项 dry-run 通过
source /usr/share/Modules/init/bash
module load lxbatch/eossubmit
condor_submit -dry-run /tmp/nu_mu_stage17.dryrun AnalysisZipFramework/submission/tracking_loss.sub
condor_submit AnalysisZipFramework/submission/tracking_loss.sub

python3 AnalysisZipFramework/scripts/collect_tracking_loss_resources.py \
  --cluster 1543524 --pilot logs/tracking_loss_stage17_pilot.log \
  --override 52=logs/tracking_loss_stage17_job52_recovered.log
```

本阶段机制解释直接依据固定版本官方源码：
[MergeTracksAlg.cxx](https://gitlab.cern.ch/faser/calypso/-/blob/d32b0ff3cc4a2dad4abfb1474a82422c3c25b305/Tracking/Acts/FaserActsKalmanFilter/src/MergeTracksAlg.cxx)；
[NtupleDumperAlg.cxx](https://gitlab.cern.ch/faser/calypso/-/blob/d32b0ff3cc4a2dad4abfb1474a82422c3c25b305/PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.cxx)。
本阶段没有引入新算法或需要论文支持的新物理假设；没有额外文献检索结果，避免用一般文献替代当前代码/数据证据。

## 下一步计划

1. **先检验 station-aware merge 去重。** 输入：同一官方源码、当前 89 个 loss、1034 个 gain 的 IDs、代表性共同通过事件及原 RDO。候选策略是在 measurement 排序前限制目标 station 覆盖，或将独立面数/重复 measurements 纳入排序；作为独立补丁，不混入当前基线。验收：先逐一复现 5 个 long-track loss 的恢复，记录是否改变其他 84 个 loss；再用同源共同真值分母测 gain/loss、背景、资源，不能仅报告恢复 5 个事件。
2. **量化 leading-track 策略。** 输入：完整样本三模式候选及原 cuts，至少包含所有 1034 个 merge-only 和 89 个 backward-only。比较最高 pz、先质量筛选再最高 pz、任一合格轨迹规则。验收：完整 cutflow、配对统计、primary-muon matching、背景与系统效应均报告；验证当前 16 个“保留但非 leading”的具体恢复，不用事后为单个事件换规则。
3. **区分真实 μ 与错误组合的动量差异。** 输入：目标事件原 ntuple 的 `t_barcode/t_pdg/t_truthHitRatio`、primary μ 的 barcode/parent、truth station momenta，以及共同通过匹配对照。验收：给出同一 primary μ 匹配 F/B 的 Δq/p、p 分辨率、charge-flip，按 truth μ momentum、r、z 分层；没有 matching 的候选单列。不能用中微子 pz 代替 μ p。
4. **检查重复 measurements 来源及半径边缘迁移。** 输入：5 个 nonlong blocker 的完整 strip/plane 列表、CKF states、磁场与几何面，另加 49 个半径首次失败事件。验收：定位重复是同 strip、同面不同 strip 还是状态装配问题；独立测量面数一致；分解 rIFT 亚毫米迁移与换轨迹的大变化，报告修复后的效率、分辨率、资源和系统误差。尚未测量这些后续量。
