# 阶段 20：89 个 backward-only 事件的逐轨迹 MC truth 准确度

## 阶段目标与直接结论

回答：在 backward 完整选择通过、merge 完整选择失败的 89 个事件中，merge 选中的 forward 候选，还是 backward leading track，更接近 MC truth？

**没有统一的动量胜者。** 84 个存在 merge long track 的事件中，只有 63 对同时匹配到主 μ 子；这 63 对相对主 μ 子产生 pz 的比较为 **backward 更近 32、forward 更近 31**，双侧配对 sign test **p=1.0**。绝对相对误差中位数为 **17.8622% / 16.7338%（B/F）**，不能据此声称 backward 整体重建更准。

**失败类别有相反趋势。** 同样要求双方匹配主 μ 子，pz cut 失败组是 **B 17 / F 3**，而 IFT 半径 cut 失败组是 **B 6 / F 20**。通过分析 cut 与更接近 truth 是两个不同的观测。另有一些 backward 通过轨迹实际匹配到强子，不能将所有通过者称为“正确 μ 轨迹”。

上述动量 truth 是**粒子产生动量**，不是输运到 tracker 的真实动量；本阶段比较的是相对这个明确参考的准确度，尚不能测量纯 tracker 动量拟合分辨率。

## 输入、配置与工作内容

- 沿用[阶段 17](2026-10-30_stage17_backward-only-events.md)的固定 89 IDs，选择为 `backward_bits == 16383 && merge_bits != 16383`，来自 81 个 RDO；没有新增事件剔除或截断高动量离群值。
- 基线为 342 个共同 RDO、383,670 个共同 truth-fiducial 事件、103,985 个 backward 最终通过事件；本阶段只重建目标 89 个，不重跑全体样本。run 为 200080、200082、200083、200089、200093、200094、200100；计数未加权，200080 为 SIBYLL 替代样本，另给出排除它的结果。
- 官方 Calypso `d32b0ff3cc4a2dad4abfb1474a82422c3c25b305`、Athena 24.0.41、TI12MC04/FASERNU-04/OFLCOND-FASER-06、without-IFT、无 CaloNu；使用现成构建，没有修改物理重建算法。
- 原始诊断：`ntuples/tracking_loss_stage17/diagnostics.json.gz`；逐事件 RDO、已发布 merge、cut bits 和输出路径见 `AnalysisZipFramework/submission/tracking_truth_manifest.tsv`。cuts/definitions/helper 保持阶段 17 配置。
- 新增 `TrackingTruthDiagnostic.h` 和 `inspect_tracking_truth.py`，读取全部原始 forward/backward/merge TrackCollection 的 hit truth contribution、匹配粒子产生动量、barcode、PDG 和母粒子。计数规则逐行对照固定版本官方 `TrackTruthMatchingTool`，HepMC3 编译宏与现成运行时一致。
- `extract_tracking_truth.py` 对新旧事件 ID、17 项非 track 输入、全部 14 个累计重建 cut bits、可对应的全部原始 `Track_*`/`truth_*` 列、原始候选数、首 state、χ²、nDoF、measurement 数逐项验收，只保留新增 truth 信息。
- `report_tracking_truth.py` 以完整 states、χ² 和 nDoF 精确对应 merge 实际选中的 forward 候选，和原 backward leader 比较。84 个 merge long leaders 中，**83 个也是独立 forward 模式的 leader**；例外为 **200083/691713**，本阶段使用实际 merge 候选，没有误用另一个 forward leader。
- 五个没有 merge long track 的事件，比较对象是阶段 17 确认的 raw forward 阻挡候选，单列为补充样本；没有将它们伪装成 merge long leaders。

主 μ 定义：在保存的前十个 truth particles 中寻找符号正确、产生点与入射 ν 衰变点一致的唯一 μ，三坐标容差 `1e-4 mm`；89 个事件均唯一。随后用 hit contribution 匹配的 barcode/PDG 验证身份，再检查母粒子 barcode/PDG 为该入射 ν，未固定使用粒子数组下标 4。两个候选匹配主 μ 时，产生三动量必须与这条主 μ 相符。

## Truth 匹配与全样本覆盖

| 样本 | 两者均主 μ | 仅 B 为主 μ | 仅 F 为主 μ | 两者均非主 μ | 合计 |
|:---|---:|---:|---:|---:|---:|
| 有 merge long track | 63 | 11 | 6 | 4 | 84 |
| 无 merge long track，raw 阻挡候选 | 4 | 0 | 0 | 1 | 5 |
| 全部 | **67** | **11** | **6** | **5** | **89** |

其中全部 89 对有 **69 对匹配同一个 truth 粒子**：67 对主 μ，另 2 对同一 π⁺。另外 **19 对的匹配粒子不同，1 对双方未匹配到保存的 truth 粒子**。表中的“两者均非主 μ”包括这对未匹配者，不等于全部都是确认的强子。不同粒子的候选不能作为同一条 μ 的配对拟合分辨率样本。

主比较 63 对中，**61 对双方 hit contribution fraction ≥0.8**。这里 fraction 为匹配粒子贡献的 measurement 数 / 全 measurement 数，不是假定互斥的概率纯度；一个 measurement 可以含多个粒子贡献。官方 `t_truthHitRatio` 的分母为 `nDoF+5`，另按其精确定义交叉验证，没有直接混用两个分母。

67 对主 μ 匹配均确认了入射 ν 母粒子。所有 **384 条持久化 long 候选**的诊断匹配 PDG、barcode、母粒子、产生三动量及官方 `t_truthHitRatio` 均与 maker 的官方 `t_*` 一致；总共诊断 **394 条 raw 候选**，差的 10 条来自 5 个事件的 forward/merge nonlong 候选。

## 动量定义、详细数据和统计

使用首个拟合 state 的重建动量。定义 `e_pz = |pz_reco / pz_truth,production − 1|`，`e_p` 同理。曲率指标为 `e_q/p = p_truth × |q_reco/p_reco − q_truth/p_truth|`，无量纲，纳入电荷符号。表内“更近”为逐事件比较误差大小；没有 ties。中位数差与逐事件胜出次数衡量不同性质，不能混为同一项检验。

| 比较范围 | N | B 更近 | F 更近 | B 的 e_pz 中位数 | F 的 e_pz 中位数 | 双侧 sign p |
|:---|---:|---:|---:|---:|---:|---:|
| 84 个 long，全部相对主 μ（含换粒子） | 84 | 45 | 39 | 22.1230% | 25.2602% | 0.58565 |
| **双方均主 μ，long 主比较** | **63** | **32** | **31** | **17.8622%** | **16.7338%** | **1.0** |
| 双方均主 μ，fraction ≥0.8 | 61 | 30 | 31 | 21.0418% | 16.6384% | 1.0 |
| 双方均主 μ，去掉 SIBYLL 200080 | 53 | 24 | 29 | 23.2042% | 16.6384% | 0.58313 |
| 同一个 truth 粒子，含 1 对 π，使用各自匹配 truth | 64 | 33 | 31 | 17.6834% | 16.8181% | 0.90065 |
| nonlong 中双方均主 μ，补充样本 | 4 | 4 | 0 | 8.2287% | 77.4472% | 0.125 |

63 对主比较中，B 胜出比例 **50.79%**，Clopper–Pearson 95% 区间 **[37.89%, 63.62%]**。B 中位数减 F 中位数为 **+1.1284 个百分点**；10,000 次按事件配对 bootstrap、固定种子 20261030，95% percentile 区间为 **[−11.2100, +20.1194] 个百分点**，跨零。有限样本不能证明两种方法等价，也不支持指定其中一种整体更优。

同一 63 对的 `e_p` 中位数为 **17.8622% / 16.7339%**，胜出仍是 **32/31**。`e_q/p` 中位数为 **0.21220 / 0.19960**，胜出同为 **32/31**。相对主 μ 的电荷误判为 **B 8/63、F 4/63**；高 contribution 子集为 **8/61、2/61**。这些计数没有推广为全样本电荷误判率。

长尾仍然存在：63 对的 `e_pz` 均值为 **34.4334% / 44.8694%**，90% 分位为 **81.8348% / 92.4504%**。因此“F 的误差中位数略小”也不表示 F 的整个误差分布更好。完整均值、分位数、配对中位差和区间见 [accuracy_summary.tsv](stage20_tracking_truth/accuracy_summary.tsv)。

### 按 merge 首次失败 cut 分组

仍只比较双方匹配主 μ 的 long tracks；“原始 N”保留全 89 事件首次失败分类，防止把去除非主 μ 后的分母误当成原类别总数。

| 首次失败 cut | 原始 N | 配对主 μ N | B 更近 | F 更近 | e_pz 中位数 B / F |
|:---|---:|---:|---:|---:|:---|
| 至少一条 long track | 5 | 0 | — | — | raw 结果单列 |
| pz >100 GeV | 21 | 20 | **17** | **3** | **8.7420% / 49.8257%** |
| nDoF ≥9 | 10 | 1 | 1 | 0 | 17.8622% / 528.2770% |
| χ²/nDoF <15 | 3 | 3 | 2 | 1 | 29.9599% / 80.9533% |
| 最大半径 <95 mm | 23 | 12 | 5 | 7 | 10.8787% / 10.3672% |
| IFT 外推半径 <95 mm | 26 | 26 | **6** | **20** | **54.9053% / 12.6912%** |
| θ <25 mrad | 1 | 1 | 1 | 0 | 0.5339% / 3.9578% |

pz 和 rIFT 两组未校正双侧 sign p 分别为 **0.0025768、0.0093553**；它们属于按失败类别的探索性比较，不能忽略小样本、选择条件和多重比较。其余类别数据尤其有限，未据 1–3 个事件声称普适规律。

20 个 pz 失败主 μ 事件中，**2 个的产生 truth pz 本就低于 100 GeV**。这两例 backward 通过阈值不能当作恢复了正确的产生动量接受度。另 1 个非主 μ 配对为 200082/255115：B/F 均匹配 π⁺，其产生 pz **128.8237 GeV**，重建为 **128.1112 / 82.8030 GeV**，相对这条 π 的误差 **0.5530% / 35.7238%**；其主 μ pz **24.3261 GeV**，不能把 π 的重建当作主 μ 分辨率。

原 backward leader 被移除且双方为主 μ 的 long 样本有 62 对，pz 胜出 **31/31**；“保留但不再 leading”中双方均主 μ 的只有 1 对，另 15 例涉及换粒子或未匹配。主比较中 F 的 χ²/nDoF 更小的 **43 对**，实际 **F pz 更近 28 对、B 更近 15 对**：较低 χ² 与准确度有联系，但不能保证产生动量更准；measurement 数优先和最高 pz 换 leader 也不能概括成“forward 的各项参数都更好”。

### 具体事件：通过 cut 不等于更接近 truth

下列三例双方均确认匹配同一主 μ，动量单位 GeV：

| run/event | 产生 truth pz | B pz | merge 所选 F pz | e_pz B / F | 说明 |
|:---|---:|---:|---:|:---|:---|
| 200080/33925 | 514.7943 | 149.2721 | 75.4494 | 71.00% / 85.34% | B 更近；F χ²/nDoF 6.2957 小于 B 7.0354，仍输在动量 |
| 200094/223588 | 761.3156 | 408.1987 | 542.5496 | 46.38% / 28.74% | **F 动量更近**，但 rIFT=95.3148 mm 失败；B rIFT=94.9153 mm 通过 |
| 200093/469001 | 96.7330 | 101.3916 | 97.6347 | 4.816% / 0.932% | **F 动量更近**但未过 100 GeV，B 高估后通过 |

前两例的轨迹可在[阶段 17 离线事件浏览页](stage17_tracking_loss/event_viewer.html)按 ID 查看。本阶段总体 truth 对照见 [PNG](stage20_tracking_truth/truth_accuracy_comparison.png) / [SVG](stage20_tracking_truth/truth_accuracy_comparison.svg)，上排散点的对角线上方表示 B 更近，下方表示 F 更近。

五个 nonlong 阻挡候选中，四个主 μ 配对的 pz 均为 B 更近；另一例 200094/270113 的双方匹配同一 π⁺，其 truth pz **182.6979 GeV**，B/F 为 **196.3182 / 152.5756 GeV**，各自误差 **7.4551% / 16.4875%**，也是 B 更近。即**以各自正确匹配粒子为参考，这五对全部 B 更近**；这个非常小且 station 覆盖不同的补充样本，仍不能推广为所有 forward 拟合较差。

## 位置、径向位置与方向

使用主 μ 在各 station 的模拟 SiHit 平均全局坐标和平均方向。将拟合 states 在真值平均 z 处作 station 内线性插值，仅允许相邻 z 间距 ≤150 mm，不跨磁铁、不外推；没有两端 states 时记未测量。空间残差为横向二维距离，径向残差为两者半径之差绝对值，方向残差为 `(px/pz,py/pz)` 斜率差模长，单位 mrad。SiHit 均值、散射和线性插值带来参考近似，没有将其包装为逐测量面的严格 pull。

| 位置/方向量 | 有效配对 N | B 更近 / F 更近 | 中位数 B / F |
|:---|---:|:---|:---|
| station 1 横向位置残差 | 62 | 22 / 40 | 0.5868 / 0.4767 mm |
| station 1 径向残差 | 62 | 24 / 38 | 0.3593 / 0.3047 mm |
| station 1 方向残差 | 62 | 22 / 40 | 0.4997 / 0.4139 mrad |
| station 2 横向位置残差 | 60 | 28 / 32 | 0.3141 / 0.2762 mm |
| station 2 径向残差 | 60 | 25 / 35 | 0.1636 / 0.1485 mm |
| station 2 方向残差 | 60 | 24 / 36 | 0.5241 / 0.3560 mrad |
| station 3 横向位置残差 | 61 | 34 / 27 | 0.4237 / 0.5067 mm |
| station 3 径向残差 | 61 | 34 / 27 | 0.3233 / 0.3196 mm |
| station 3 方向残差 | 61 | 27 / 34 | 0.4518 / 0.3951 mrad |

station 1 位置/方向胜出次数偏向 F，未校正 sign p 均为 **0.03002**，但两个中位数差的配对 bootstrap 区间仍跨零，多指标也有相关性。高 contribution 子集对应两项均为 **B20/F40，N=60**。不能把这个迹象扩展为每个 station、每个变量都由 F 胜出。

**IFT 真值半径未测量。** 官方 `rIFT` 是 VetoStation2、**z=−1609.65 mm** 的外推半径；现有 truth station 0 的 SiHits 在约 −1850 mm，不能直接代作该平面位置。本阶段没有跨磁场/材料直线外推 truth 来裁决哪个候选的 IFT 半径更准确。

## 物理含义、程序检查与适用范围

官方 `FiducialParticleTool::getMomentum` 用 `hit.particleLink()->momentum().rho()` 取得产生动量模长，再以 SiHit 端点构造方向；`truth_stN_pz` **不是真实输运动量 pz**，不能换这个分支就消除能损影响。产生点到 tracker 的材料效应和拟合误差混在当前动量残差中；tracker 入口动量、材料能损、严格逐层 pulls 和这些差异的系统误差均**未测量**。

程序方面，merge 按 measurement 数、再 χ²/nDoF 排序去重，**不按 truth pz 或 pz 准确度排序，也不重新拟合**。阶段 17 已确认 73 例移除、16 例改 leader，以及 5 例 station 2/3 候选阻挡三站好轨迹后又被 ntuple long-track 要求过滤。本阶段逐项新旧核验排除了重新运行意外改变 cuts 或拟合值作为当前比较的原因。

这是经“B pass、merge fail”筛出的样本，自带阈值迁移和候选选择条件。不能由 89 个损失事件推断全体 forward/backward 分辨率排序，也不能据 F 在某些变量更准就宣布这些分析 cut 不合理。尚未对共同通过、merge-only 或完整背景样本测量本阶段指标。

实现语义直接引用固定官方源码：[TrackTruthMatchingTool.cxx](https://gitlab.cern.ch/faser/calypso/-/blob/d32b0ff3cc4a2dad4abfb1474a82422c3c25b305/Tracking/Acts/FaserActsKalmanFilter/src/TrackTruthMatchingTool.cxx)、[FiducialParticleTool.cxx](https://gitlab.cern.ch/faser/calypso/-/blob/d32b0ff3cc4a2dad4abfb1474a82422c3c25b305/Tracking/Acts/FaserActsKalmanFilter/src/FiducialParticleTool.cxx)、[NtupleDumperAlg.cxx](https://gitlab.cern.ch/faser/calypso/-/blob/d32b0ff3cc4a2dad4abfb1474a82422c3c25b305/PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.cxx)。当前结论为固定样本的直接测量，未引入需要新文献支持的新算法或机制假设。

## 验证、性能与存储

先完整测试事件 200080/33925，再提交 HTCondor **1543666**，89 个作业均正常 **exit 0**；proc 0 读取已验收 pilot 后跳过，表格由 **1 个 pilot + 88 个批量实际计算**组成，不混入失败的接口调试尝试。每作业 1 CPU、3000 MB memory、2000 MB disk，线程上限均为 1。没有批量交互重建或重新编译 Calypso。

| 步骤 | 墙钟 min / median / max（s） | 合计墙钟（s） | 最大 RSS（KiB） |
|:---|:---|---:|---:|
| ID 定位 | 2.80 / 7.93 / 17.56 | 661.97 | 63,284 |
| RDO staging | 0.61 / 4.46 / 11.55 | 421.85 | 2,304 |
| reco | 10.48 / 18.42 / 51.52 | 1658.76 | 1,017,652 |
| forward | 6.93 / 11.74 / 16.25 | 1012.21 | 919,228 |
| backward | 6.95 / 11.75 / 31.97 | 1023.91 | 913,216 |
| merge + truth 诊断 | 62.37 / 120.32 / 443.04 | 11612.97 | 2,177,136 |
| extract / 验收 | 15.96 / 27.58 / 40.14 | 2358.26 | 739,616 |

合计分步骤墙钟 **18,749.93 s**，CPU user+system **13,055.55 s**；不包含 setup、队列等待和汇总，墙钟求和不是并行任务用户等待时间。Pilot 七步为 **7.93、2.21、16.83、13.11、13.94、97.74、30.01 s**，诊断峰值 **2,015,096 KiB**。首次用本地紧凑归档汇总绘图实测 **9.452 s、539.832 MiB 峰值 RSS**；最终从 EOS 归档重现全部表图实测 **97.462 s、539.832 MiB**，后者写入 `summary.json`。两次统计完全一致；包含 I/O、库加载和绘图，未测量内部步骤独立开销，不能将墙钟差解释为算法速度变化。

最后一个 proc 14 正常完成，merge+truth **443.04 s**，其中 user+system **67.72 s**；在线 stdout 和进程检查确认其继续进入 extract，未将耗时视为物理异常。具体等待原因未测量。部分 EOS 文件发生目录可见但本地 open 不可见的情况，proc 75/81/83/84 的 JSON 及最后完成的 proc 14 通过 XRootD 读取到临时汇总目录；proc 14 stdout 另存 `logs/tracking_truth_stage20_job14_recovered.log`。没有因 I/O 可见性问题漏事件。

89 个 compact JSON 合计 **565,142 bytes**，合并为唯一 `ntuples/tracking_truth_stage20/truth.json.gz`，**81,393 bytes**。合并前后 JSON 精确读回一致，远端上传后再经 XRootD 读回核验 89 IDs 和完整内容，随后删除 89 份重复 shards；XRootD 列目录确认只剩压缩结果及 `.gitignore`。RDO/xAOD/ntuple 中间件只在 worker scratch，随退出清理；原始数据及归档不入 Git。

验收包括：Python 编译、shell 语法、全 89 ID/14-bit cut 逐项重现、384 条官方 truth 匹配交叉核验、全 394 raw 候选核验、PNG 人工检查；另完全使用官方 ntuple `t_pz/t_barcode/t_pdg` 和旧 `Track_pz0` 独立重算 63 对，精确复现 **32/31、17.8622%/16.7338%**，见 [validation_summary.json](stage20_tracking_truth/validation_summary.json)。未运行浏览器自动化或新的实验背景验证。

## 产物、重现命令与下一步

核心产物：[逐事件数据](stage20_tracking_truth/truth_by_event.tsv)、[匹配统计](stage20_tracking_truth/matching_summary.tsv)、[全部准确度统计](stage20_tracking_truth/accuracy_summary.tsv)、[汇总图](stage20_tracking_truth/truth_accuracy_comparison.png)、`resources_by_event.tsv`、`resources_summary.tsv`、`summary.json`、`validation_summary.json`、`storage_summary.json`。原始 matching 仅保留 EOS 压缩归档，冻结运行软件包为 `software/tracking-truth-stage20.tar.gz`，包含阶段 17 reference 和当前检查器/配置。

```bash
# 提交前已完成单事件 pilot 及 dry-run；重新提交会重建 89 个目标事件
source /usr/share/Modules/init/bash
module load lxbatch/eossubmit
condor_submit -dry-run /tmp/nu_mu_stage20.dryrun AnalysisZipFramework/submission/tracking_truth.sub
condor_submit AnalysisZipFramework/submission/tracking_truth.sub

# 只用紧凑缓存重新产生全部 truth 对比表和图
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python3 AnalysisZipFramework/scripts/report_tracking_truth.py \
  --combined ntuples/tracking_truth_stage20/truth.json.gz

python3 AnalysisZipFramework/scripts/collect_tracking_loss_resources.py \
  --cluster 1543666 --pilot logs/tracking_truth_stage20_pilot.log \
  --manifest AnalysisZipFramework/submission/tracking_truth_manifest.tsv \
  --output workbook/stage20_tracking_truth --log-prefix tracking_truth \
  --override 14=logs/tracking_truth_stage20_job14_recovered.log
```

1. **取得 tracker 入口的输运动量。** 输入：同几何 RDO 的可用 G4 truth/track record 检查结果；若无保存，需为代表性样本增加参考面动量记录并通过 Condor 生产。验收：明确参考 z 与单位、主 μ/后继链关联，分别报告产生→入口能损和同平面 F/B 动量残差，不能再用 `truth_stN` 模长替代输运动量。
2. **测量条件选择之外的分辨率。** 输入：共同通过、merge-only 1,034 例及 truth μ pz/r/z 分层对照，与本阶段相同官方匹配和 cuts。验收：使用同一真实粒子配对，报告完整效率、迁移矩阵、分辨率、charge flip、物理权重与统计/系统误差，避免只在损失事件上优化排序。
3. **分开测试 station 覆盖与 leading 规则。** 输入：阶段 17 raw measurements、本阶段粒子匹配、完整候选及背景。验收：先恢复 5 个 station 覆盖冲突，再对 16 个换 leader 事件区分真 μ/强子；对全样本测量质量预选或 any-good-track 的信号与背景变化，不能把“通过更多”自动解释为“更准确”。
