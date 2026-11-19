# Stage 216（Stage T5）总结报告：Run 3 全时期 `reduced_charge` 修正统一与盲化下工作点冻结及系统误差闭合

> 日期：2026-11-20  
> 阶段范围：Stage 216 / Timing Roadmap `T5`（含 2022–2026 `reduced_charge` 专项修正、2025–2026 RAW 直读重建、工作点冻结、`S3` 上界对照、30-bin 2D 协方差、6D 接受度与 `F7` 能量回归耦合闭环）  
> 盲化状态：**严格保持碰撞数据 `SR-ZoneB`（`REG_KIN_SR` 内 `!Timing_ZoneA` 且 `dt > 1.5 ns` 或下游/校准时间无效）100% 盲化**（`Timing_Allow_SR_ZoneB = false` for `DATA`）

---

## 1. 阶段目标

1. **彻底修正并统一 Run 3（2022–2026，717 个官方 GRL run，$335.92\ \mathrm{fb}^{-1}$）的 `VetoNu` `reduced_charge` 处理**：
   - 核实并移植 [El9CalypsoForWaveForm](file:///eos/home-x/xcheng/FASER/El9CalypsoForWaveForm) 的多数字化仪状态位处理（`(status & ~512) == 0`、`+16.0 ns` 偏移、`Veto2` 通道 `{6, 7, 22, 23}`）至隔离 Calypso `master` 补丁，同时实测 2022–2026 全部 7 个时期的单 $\mu$ 站间时间差分布并解决 2025–2026 PMT 升级后的时间窗跳变与 `2025/p0013` Preshower 拟合故障；
   - 针对尚未产出波形 reduced-charge Aux 文件的 2025–2026 全部 281 个 run，开发多线程原生 C++ 重建工具直接读取 RAW 与 PHYS NTuple 生成完整的 Aux `reduced_charge` 文件集，并将 `AnalysisZipFramework` 与 [t5_scanner.cxx](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/t5_scanner.cxx) 统一至同一套 Aux 查表、状态清洗与 `TimingOK` 判据。
2. **完成 Stage T5 工作点优化冻结与完整系统误差/能量 ML 闭环**：
   - 在碰撞数据 `SR-ZoneB` 绝对盲化、仅开放正交控制区（`CR-Prompt`、`CR-Geom`、`CR-EdgeVN`、`CR-NonColl`）及 GENIE / FLUKA MC 的条件下，扫描 `S0`、`S1`（时间窗）与 `S2`（Pull + $\Delta\chi^2_{\mathrm{back}}$）网格，冻结主工作点 `WP_Primary`、严格备选 `WP_Strict` 与似然对照 `WP_S2`，并与 10 变量浅层 `S3_GBDT` 信息上界对比；
   - 产出全 Run 3 30-bin 2D 展开矩阵与 14 源 7 组完整协方差/系统误差分解、6D 微分接受度与 5 套 Geant4 强子物理列表对比，以及 `F7_pz0_raw_v1` 62 特征 vs 58 无 VetoNu 消融特征在 Zone-B 恢复事例上的能量重建与偏置抑制验证；
   - 冻结框架 TIMING YAML 配置并通过全部 4 项工程与盲化验证门禁。

---

## 2. 工作内容

### 2.1 全 Run 3 站间时间差实测与 Calypso `master` 移植补丁
- 编写并运行 [measure_reduced_charge_timediffs.py](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/scripts/measure_reduced_charge_timediffs.py)，在 2022–2026 单穿透 $\mu$ 样本与 GENIE MC 上实测 `Veto2 - VetoNu`、`Timing - VetoNu`、`PS0/1 - VetoNu` 及 `PS0..3 - VetoNu` 高斯核心峰值（见 [reduced_charge_station_timediffs.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage216_timing_t5/reduced_charge_station_timediffs.tsv) 与 [fig0_reduced_charge_timediffs.png](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage216_timing_t5/fig0_reduced_charge_timediffs.png)）：
  - **关键硬件异常定位**：2025 年 Preshower PMT 更换导致 `Preshower0/1 - VetoNu` 由 `2024_postCaloNu` 的 `53.6005 ns` 突变 `-40.3 ns` 至 `13.2865 ns`（`2025/p0014`）与 `13.3018 ns`（`2026/p0015`）；而 `2025/p0013` 的 81 个 run（`19413..20142`，不含已为 `p0014` 的 `19878, 20012`）因 `TimingOffset` 常数过期导致约 $94\%$ 的 Preshower 波形拟合失败、残余峰值漂移至 $17.28\text{–}35.40\ \mathrm{ns}$。若在 2025–2026 直接沿用 Calypso 硬编码 `53.625 ns`，当 `Veto2` 饱和回退至 Preshower 时积分窗将提前 $40.3\ \mathrm{ns}$ 积入纯基线噪声（误判为 `~0 pC`）。
- 在不修改用户 `/eos/home-x/xcheng/FASER/calypso`（`Tracking-4ST-Clean` 分支）工作树的前提下，生成隔离补丁与说明：
  - [calypso_master_reduced_charge.patch](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/calypso_port/calypso_master_reduced_charge.patch)、[NtupleDumperAlg.h](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/calypso_port/NtupleDumperAlg.h)、[NtupleDumperAlg.cxx](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/calypso_port/NtupleDumperAlg.cxx)、[MyWaveformTimeRangeConfig_run3.py](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/calypso_port/MyWaveformTimeRangeConfig_run3.py)、[README.md](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/calypso_port/README.md)。
  - 修复 5 项核心缺陷：`hit_status & ~512` 与 `+16.0 ns` 偏移、`Veto2` 通道 `{6, 7, 22, 23}`、`vetoNuContainer` 按通道号映射并跳过二次脉冲、按 run 自动分期站间时间差、以及新增 `TriggerWaveformHits {8,9,10,11}` 作为 `2025/p0013` 失效 Preshower 的回退源（并将无效哨兵值统一设为 `-1.0f`）。

### 2.2 2025–2026 `raw_reduced_charge_dumper` 多线程重建与 `event_counter` 修复
- 开发原生 C++17 多线程工具 [raw_reduced_charge_dumper.cxx](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/raw_reduced_charge_dumper.cxx) 及 Condor 提交器 [submit_reduced_charge_2526_condor.py](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/submission/submit_reduced_charge_2526_condor.py)（并在 [CMakeLists.txt](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/CMakeLists.txt) 注册编译）：
  - 直接按 `PHYS` 时间戳关联 `/eos/experiment/faser/raw/<yr>/<run6>/Faser-Physics-*.raw` 的 Waveforms fragment，从 `Timing0..3`、`Veto2`、`Preshower0/1`（按 `broken_ps_p0013` 自动跳过 `2025/p0013`）提取上游预期到达时刻并积分 $[-10, +35]\ \mathrm{ns}$ `myVetoNu{0,1}_rawCharge35`。
  - **关键 BUG 修复**：审计发现 FASER RAW 二进制头中 `RawEventHeader.event_id`（字节偏移 16）会按 $2^{24} = 16,777,216$ 回绕并在 run 中途 ECR 时清零复位，而 Calypso `PHYS` NTuple 的 `eventID` 对应单调递增的 `RawEventHeader.event_counter`（字节偏移 24，`FaserEventSelectorByteStream.cxx:706`）。将 `raw_reduced_charge_dumper.cxx` 中的索引键值切换为 `hdr.event_counter` 后，在跨回绕分片 `019269_part0001`（`eventID` 范围 `[16884379, 17932255]`）上达到 `118368 / 118368`（`missing = 0`，`-j 28` 耗时 `22.41 s`）。
  - 核查磁盘发现 5 个 run 在 EOS RAW 目录确实缺少少数原始段文件（`19414 [199]`、`20282 [481]`、`20430 [466,481,482]`、`20480 [206]`、`20675 [496]`），对此显式放宽 `--max-missing-frac 0.025`，其余 276 个 run 保持 `0.001`。
  - 通过 HTCondor（含 ECR 重置受影响的 21 个旧分片经 Cluster `17081476` 全部重跑刷新）与本地并发验证完成 **281/281 run、866/866 分片**全量生产。

### 2.3 Run 3 清单统一、`AnalysisZipFramework` 兼容层与全量 T5 扫描
- 更新 [run3_timing_manifest.json](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/timing_calib/run3_timing_manifest.json)，为全部 717 个 Data run（覆盖 `2022, 2023, 2024_preCaloNu, 2024_CaloNu, 2024_postCaloNu, 2025, 2026` 七个时期）补齐 `waveform_glob`（436/436 2022–2024 路径及 281/281 2025–2026 自产 Aux 路径）与 81 个 `2025/p0013` `broken_ps_p0013` 标志。
- 升级 [make_fileconfig.py](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/scripts/make_fileconfig.py)（新增 `--run3` 与 XRootD URL 自动映射 `eoshome-x` / `eosuser` / `eospublic`）并生成 [file_config_run3.yaml](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/file_config_run3.yaml)（786 个 run = 717 Data + 69 GENIE MC）。
- 同步升级 [Analysis.h](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/include/Analysis.h)、[Analyis.cxx](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/source/Analyis.cxx) 与 [t5_scanner.cxx](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/t5_scanner.cxx)：
  - `Analysis::defineReducedChargeFromAux()` 与 `t5_scanner` 统一扩展至 `Veto2 + Preshower + Timing0..3`、`TimingOK` 按 `run < 18500` 及 `(!hasNativeRedQ) && (19413..20142)` 分期判断、2024 零电荷 bug 检查、以及 `Aux` 值强制覆盖 `2025/p0014` 与 `2026/p0015` 原生受损分支。
  - 利用 [submit_timing_t5_condor.py](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/submission/submit_timing_t5_condor.py)（`--cpus 4`、`--memory-mb 6500`）完成 **1,311/1,311 分片**扫描（Data 1,138 + GENIE 107 + FLUKA 66；Data 经 ECR 修复后局部重扫 23 个受影响分片 `23/23 rc=0` 并全量通过盲化/残差/missing-aux 审计）。

### 2.4 Stage T5 优化脚本修正、工作点冻结与 YAML 落地
- 在 [optimize_freeze_t5.py](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/scripts/optimize_freeze_t5.py) 中实施关键算法与性能优化（`ThreadPoolExecutor(28)` 并行评估 875 个候选点、`split.npz`/`input.npz` 一次预加载至内存）：
  1. **解决主/严格工作点倒置**：发现 `CR-Geom` 中存在约 `58.23` 例 GENIE 真实中微子信号，原代理指标将 `B_err` 统计涨落及 5 套 G4 RMS 微弱统计波动计入总不确定度，导致极严格点（`t2=5.0, t1=4.0`）被选为 `WP_Primary`，而按最大信号选出的 `WP_Strict`（`t2=4.0, t1=3.0`）反而更宽松。遂改用基于物理信背比目标与严格参数偏序的非倒置冻结准绳。
  2. **修复 `S3_GBDT` 训练与系统误差评估**：将 `m_d_geom_zb` 内的全部 `is_prompt_sub == 1` 穿透 $\mu$ 本底保留进训练集（训练权重 `20.0`，评估保持精确反抽样权重 `2000.0`），使用严格 OOF 预测计算 Data CR-Geom 响应，显式强制 `S3` 在 Zone-B 满足延迟盲区边界 `max(dt0, dt1) > 1.5 ns` 及下游参考质量切选 `chi2_ndof_down < 10.0 && |t0_down| < 2.5 ns`，同时将 `s3_score_mc` 扩展计算至全体 MC Zone-B 本底与侧带事例并计入 `CR-EdgeVN` 擦边 $\mu$ 项（`B4`）。
- 冻结配置至 [definitions_timing.yaml](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/definitions_timing.yaml)、[cuts_timing.yaml](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/cuts_timing.yaml)、[cuts_timing_s1.yaml](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/cuts_timing_s1.yaml)、[cuts_timing_strict.yaml](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/cuts_timing_strict.yaml) 与 [cuts_timing_s2.yaml](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/cuts_timing_s2.yaml)，完成 CMake 全量编译及 4 项验证门禁，清理全部临时 EOS 与 Condor 冗余目录。

---

## 3. 详细数据（全部为本阶段实测数值）

### 3.1 2022–2026 单穿透 $\mu$ 站间时间差实测峰值（单位：$\mathrm{ns}$）

| 时期 | $\mu$ 样本数 | `Veto2 - VetoNu` 峰 ($\sigma$) | `Timing - VetoNu` 峰 ($\sigma$) | `PS01 - VetoNu` 峰 ($\sigma$) | `PS0123 - VetoNu` 峰 ($\sigma$) | 数据来源 |
|---|---:|---:|---:|---:|---:|---|
| `2022` | 176,691 | $33.0279\ (0.5247)$ | $34.7299\ (0.7076)$ | $53.4639\ (0.5405)$ | `nan` | [reduced_charge_station_timediffs.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage216_timing_t5/reduced_charge_station_timediffs.tsv) |
| `2023` | 170,718 | $33.0433\ (0.5230)$ | $34.7424\ (0.7256)$ | $53.4830\ (0.5442)$ | `nan` | 同上 |
| `2024_preCaloNu` | 270,334 | $33.1265\ (0.5314)$ | $34.8843\ (0.7183)$ | $53.5845\ (0.5194)$ | `nan` | 同上 |
| `2024_CaloNu` | 298,430 | $35.8353\ (0.5266)$ | $34.8716\ (0.7144)$ | $53.5760\ (0.5147)$ | `nan` | 同上 |
| `2024_postCaloNu` | 273,973 | $33.1371\ (0.5242)$ | $34.8994\ (0.7185)$ | $53.6005\ (0.5171)$ | `nan` | 同上 |
| `2025_p0013`（故障） | 843,365 | $33.1652\ (0.5259)$ | $34.9777\ (0.6815)$ | $35.4049\ (2.8966)$ | $17.2797\ (1.5823)$ | 同上 |
| `2025_p0014` | 1,825,893 | $33.1641\ (0.5285)$ | $34.8868\ (0.7326)$ | $13.2865\ (1.0616)$ | $14.7108\ (1.2072)$ | 同上 |
| `2026`（`p0015`） | 359,302 | $33.1794\ (0.5273)$ | $35.0126\ (0.6783)$ | $13.3018\ (1.0683)$ | $14.4406\ (1.1894)$ | 同上 |

### 3.2 `rc2526` 重建、T5 扫描与优化执行性能及存储审计

- **2025–2026 `raw_reduced_charge_dumper` 生产（持久保留产物）**：
  - 覆盖范围：`281 / 281` run（2025 年 `199/199` run + 2026 年 `82/82` run），共 `866 / 866` ROOT 分片；
  - 事件匹配度：`1,254,668,335 / 1,254,758,833`（**`99.9928%`**），仅 5 个存在已知 EOS RAW 缺段的 run 采用 `--max-missing-frac 0.025`；
  - 最终磁盘占用：`12,443,226,689` bytes payload（目录占用 `12G` / 约 `11.590 GiB` < `20 GB` 上限），位于 `/eos/user/x/xcheng/FASER/nu_muAnalysis/reduced_charge_2025_2026`（[audit_summary.json](file:///afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage216_reduced_charge_2526/audit_summary.json)）。
- **T5 扫描生产（HTCondor `bigbird15.cern.ch` Cluster `17079988` + ECR 重建刷新，已清理临时 EOS 分片）**：
  - 总计 `1,311 / 1,311` 分片（Data `1,138`、GENIE `107`、FLUKA `66`），全部 `Exit status: 0`，`max_missing_aux = 0`；
  - Data 扫描活跃运行单元 `1,345` 个分片Run记录、总事例 `19,643,479,827` 条，入口盲化守卫严格跳过 `44,770,555` 条 `SR-ZoneB` 事例，保存 Data 正交控制区 `969,334` 条、FLUKA `4,816` 条、GENIE `1,937,092` 条；
  - 单作业最大内存 RSS `4,674,588 KB`（`4.46 GiB`），最大墙钟耗时 `331.32 s`（[audit_summary.json](file:///afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage216_timing_t5/audit_summary.json)）。
- **28 线程全量优化脚本运行实测**：
  - 执行命令：`python3 AnalysisZipFramework/scripts/optimize_freeze_t5.py --workers 28`
  - 加载 1,311 分片耗时：`28.151 s`；Task 5.2 `S3` 5-fold 训练/预测（28 核）：`127.605 s`；总墙钟时间：**`958.783 s`**（`/usr/bin/time -v` 测得 `16:05.39`），CPU 利用率 **`1975%`**，峰值常驻内存 Max RSS **`7,159,328 KB`**（`6.83 GiB`），`0` 次换页交换。
- **清理后资源核算**：
  - 临时 `ntuples/timing_stage216/`（原 `836M`）及测试产物已彻底删除；
  - Condor 目录：`stage216_reduced_charge_2526` 为 `7 KB`，`stage216_timing_t5` 为 `18 KB`（合计 `25 KB` < `100 KB`）；
  - [timing_calib](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/timing_calib) 目录大小为 `1.4 MB`（< `2 MB`）；[t5_summary.json](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage216_timing_t5/t5_summary.json) 与图 [fig1](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage216_timing_t5/fig1_wp_optimization_plane.png)–[fig6](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage216_timing_t5/fig6_energy_ml_f7_vetonu_ablation.png) 全部就绪。

### 3.3 冻结工作点全性能与 30-bin 2D 展开总表（$335.92\ \mathrm{fb}^{-1}$）

来自 [frozen_working_points.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage216_timing_t5/frozen_working_points.tsv) 与 [t5_summary.json](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage216_timing_t5/t5_summary.json)：

| 标签 | 配置名与核心切选 | $S_{\mathrm{tot}}$ | $S_{\mathrm{rec}}$（相对 S0） | $B_{\mathrm{tot}}$ (`B1`..`B5`) | $B/S_{\mathrm{rec}}$ | G4 5 模型包络 | $\bar{\epsilon}_{30}$ | $\bar{M}_{ii}$ | 总产额不确定度 (统计) | 截面总不确定度 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `S0` | `S0_baseline`（纯静默 Zone A） | 1301.73 | 0.00 (基准) | 0.000 (`0,0,0,0,0`) | 0.000% | 2.338% | 26.88% | 70.89% | 5.644% (3.189%) | 6.196% |
| **`WP_Primary`** | `S1_t2_4.0_t1_3.0_Q180_w16_tm18` | **1374.61** | **+72.88 (+5.60%)** | **0.027** (`0.027,0,0,0,0`) | **0.037%** | **2.300%** | **28.22%** | 70.74% | 5.678% (**3.133%**) | 6.227% |
| `WP_Strict` | `S1_t2_4.5_t1_3.5_Q150_w12_tm16` | 1362.20 | +60.47 (+4.65%) | 0.001 (`0.001,0,0,0,0`) | 0.002% | 2.375% | 28.00% | 70.77% | 5.681% (3.141%) | 6.229% |
| `WP_S2` | `S2_dc25_z2_6.0_z1_4.5_Q180_w12` | 1366.34 | +64.61 (+4.96%) | 0.029 (`0.0233,0,0,0.0057,0`) | 0.045% | 2.357% | 28.08% | 70.77% | 5.688% (3.138%) | 6.236% |
| `S3_GBDT` | `S3_GBDT_thr_0.9993`（仅对照） | 1426.30 | +124.56 (+9.57%) | 0.000 (`0,0,0,0,0`) | 0.000% | 1.658% | 29.12% | 70.57% | 5.481% (3.097%) | 6.048% |

> **说明**：全网格扫描共 875 个点（[s0_s1_s2_grid_scan.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage216_timing_t5/s0_s1_s2_grid_scan.tsv)）。在 `S3_GBDT` 中，`5-fold GroupKFold` 实测 $\mathrm{AUC}_{\mathrm{GBDT}} = 0.99994$、$\mathrm{AUC}_{\mathrm{LogReg}} = 0.99495$（[s3_cv_benchmark.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage216_timing_t5/s3_cv_benchmark.tsv)，特征增益前三位为 `dt0=0.49031`、`dt1=0.37605`、`r_vn=0.05752`），选定阈值 `0.999293` 时 `CR-Geom` `is_prompt_sub` 泄漏 `n_prompt_leak = 0`（[s3_roc_scan.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage216_timing_t5/s3_roc_scan.tsv)、[fig2](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage216_timing_t5/fig2_s3_roc_and_feature_audit.png)）。此外，规范视线符号审计测得 $y_\mu$ 对角纯度为 `-12.3 mm: 0.9447` vs `+12.3 mm: 0.9467`，自动锁定 `+12.3 mm`（[unfolding_30bin_comparison.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage216_timing_t5/unfolding_30bin_comparison.tsv)、[fig3](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage216_timing_t5/fig3_30bin_2d_unfolding_precision.png)）。

### 3.4 14 源 7 组边际系统不确定度分解（总产额相对不确定度，单位：`%`）

来自 [systematics_breakdown.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage216_timing_t5/systematics_breakdown.tsv) 与 [fig4](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage216_timing_t5/fig4_systematic_breakdown_and_corr.png)：

| 系统误差组 | `S0` | `WP_Primary` | `WP_Strict` | `WP_S2` | `S3_GBDT` |
|---|---:|---:|---:|---:|---:|
| `Detector_Selection` | 4.3581% | 4.3710% | 4.3702% | 4.3729% | 4.2017% |
| `Forward_Flux` | 1.2771% | 1.3238% | 1.3276% | 1.3392% | 1.3074% |
| `Geant4_Albedo` | 0.9329% | 0.9115% | 0.9560% | 0.9479% | 0.6171% |
| `MC_Stat` | 0.3966% | 0.3897% | 0.3907% | 0.3904% | 0.3850% |
| `Misalignment` | 0.1732% | 0.1832% | 0.1836% | 0.1790% | 0.2040% |
| `Timing_Calib` | 0.0000% | **0.0260%** | 0.0273% | 0.0419% | 0.1502% |
| `ZoneB_Bkg` | 0.0000% | 0.7430% | 0.6657% | 0.7118% | 0.7043% |

- `Timing_Calib`（包含时间标尺 $\pm \delta t_{\mathrm{scale}}$、$\pm 15\%$ 涂抹宽度与圆盘 `cone75` 查表变体）仅贡献 **`0.0260%`**。
- `ZoneB_Bkg`（`0.7430%`）源于 `B3` 数据驱动传播中包含实测 `CR-Geom` `N_CR_obs = 52.0` 的保守泊松统计项 $\sqrt{\max(N_{\mathrm{CR}}, 1.84)} \cdot T_{\mathrm{SR/CR}}$（尽管其中被 GENIE 中微子信号 `58.23` 解释后净超额 `N_CR_excess = 0.0`），若未来在 T6 加入紧致角度/径向纯背景侧带进一步压低 `T_SR/CR`，该保守统计项仍有下降空间。

### 3.5 6D 微分相空间接受度与 `F7_pz0_raw_v1` 能量 ML 耦合验证

- **6D 微分接受度**（[phase_space_6d_gains.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage216_timing_t5/phase_space_6d_gains.tsv)、[fig5](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage216_timing_t5/fig5_6d_efficiency_and_g4_closure.png)）：
  - 最上游钨靶段 `z_vtx in [-3000.0, -2950.0] mm`：信号产额由 `S0 = 11.097`（$\epsilon = 5.151\%$，5 套 G4 包络 $33.631\%$）跃升至 `WP_Primary = 25.001`（$\epsilon = 11.605\%$，G4 包络降为 $29.853\%$）；
  - $\nu_\mu$（`q_mu = -1`）接受度由 $24.309\%$ 升至 $25.714\%$（`G4_spread` $2.681\% \to 2.580\%$）；$\bar{\nu}_\mu$（`q_mu = +1`）接受度由 $34.315\%$ 升至 $36.083\%$（`G4_spread` $2.463\% \to 2.274\%$）。
- **`F7_pz0_raw_v1` 62 vs 58 无 VetoNu 特征消融对比**（[energy_ml_f7_ablation.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage216_timing_t5/energy_ml_f7_ablation.tsv)、[fig6](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage216_timing_t5/fig6_energy_ml_f7_vetonu_ablation.png)）：

| 测试层（Stratum） | 模型 | $N_{\mathrm{test}}$ | $\log\mathrm{RMSE}$ | 平均偏差 [%] | 中位偏差 [%] | $R_{68}$ [%] | $|\delta| > 50\%$ 拖尾率 [%] |
|---|---|---:|---:|---:|---:|---:|---:|
| `Test_ZoneA_S0` | `M0_pz0_over_0p8` | 50,459 | 0.5183 | +14.79 | -2.29 | 28.92 | 14.24 |
| `Test_ZoneA_S0` | `M1_F7_62_trainS0` | 50,459 | 0.2744 | +3.85 | +3.81 | 21.86 | 6.00 |
| `Test_ZoneA_S0` | `M4_F7_62_trainS1` | 50,459 | 0.2743 | +3.83 | +3.78 | 21.83 | 6.01 |
| **`Test_ZoneB_Rescued`** | `M0_pz0_over_0p8` | 3,005 | 0.5861 | -3.36 | -14.29 | 31.60 | 19.55 |
| **`Test_ZoneB_Rescued`** | `M1_F7_62_trainS0`（未含 ZoneB 训练外推） | 3,005 | 0.3251 | +11.97 | +9.77 | 31.33 | 13.41 |
| **`Test_ZoneB_Rescued`** | `M3_F7_58_noVN_trainS1`（去 VetoNu 特征） | 3,005 | 0.4195 | -13.66 | -12.42 | 26.21 | 9.94 |
| **`Test_ZoneB_Rescued`** | **`M4_F7_62_trainS1`（S1 全分布重训）** | 3,005 | **0.3132** | **+5.20** | **+4.00** | **28.15** | **9.16** |
| `Test_WP_Primary_All` | `M4_F7_62_trainS1` vs `M0` | 53,464 | **0.2766** vs 0.5223 | +3.91 vs +13.77 | +3.78 vs -2.95 | **22.17** vs 29.20 | **6.18** vs 14.54 |
| `Test_WP_Primary_G4Alt` | `M4_F7_62_trainS1` vs `M0` | 202,281 | **0.2917** vs 0.5720 | +5.55 vs +18.65 | +5.40 vs -5.20 | **23.74** vs 31.38 | **7.57** vs 16.88 |

  - 结论：在 `Test_WP_Primary`（`pz0/0.8 -> F7_58_noVN`）下 30-bin 迁移矩阵对角平均纯度分别为 `70.49%` vs `70.27%`；若直接把仅在 S0 训练的 `M1_F7_62_trainS0` 外推至 Zone-B 恢复事例，因训练支持域截断会产生 `+9.77%` 正向中位偏差与 `13.41%` 大偏差拖尾；一旦纳入 S1 全样本重新训练（`M4_F7_62_trainS1`），不仅零损失 Zone-A 分辨率（$21.83\%$ vs $21.86\%$），还将在 Zone-B 的中位偏差压低至 **`+4.00%`**、大误差拖尾降至 **`9.16%`**。

### 3.6 四项工程与盲化验证门禁实测结果

| 门禁 | 执行命令 / 配置 | 实测观测结果 | 结论 |
|---|---|---|---|
| **Gate 1**：盲化单元测试 | `python3 AnalysisZipFramework/scripts/test_timing_blinding_guard.py` | 18 项 C++/Python 一致性用例（含 `1.49 vs 1.5001 ns`、`2025/p0013` 无 reduced charge、NaN 下游参考、边带区及旁路拒绝异常）全部 `PASS` | **通过** |
| **Gate 2**：真实数据盲化集成检查 | `./analysis -j 8 -r {16023,19415}` + `file_config_run3.yaml` + `grl_config_run3_full.yaml` + `timing_calib` + `definitions_timing.yaml` + `cuts_timing.yaml`（`XrdSecPROTOCOL=krb5,unix`） | 两 run 均声明 `Reduced charge source: aux (waveform) NTuples.`；`16023` `AuxLookupSuccess = 4,133,966 / 4,133,966 (100%)`、`nt = 3`、`not_Timing_ZoneA = 0`、`Timing_Allow_SR_ZoneB = 0`；`19415` `AuxLookupSuccess = 209,104 / 209,104 (100%)`、`nt = 0`；两者 fallback 均为 `0` | **通过** |
| **Gate 3**：MC 多线程位一致与嵌套关系 | `./analysis -j {1,8,16} -r 200164 --isMC` + `timing_calib` + `definitions_timing.yaml` + `cuts_timing.yaml` | `-j 1 / 8 / 16` 三次结果**逐 bit 完全一致**：`nt = 25,370`、`passed_S0 = 23,839`、`passed_S1 = 25,370`（$+1,531$ 事例）、`passed_S1_strict = 25,143`、`passed_S2 = 25,186`，`sum(nt.eventID) = sum(eventID_pass 累积通过 eventID) = 9,361,432,518`（`ep_total = 738,614`） | **通过** |
| **Gate 4**：无 `--timing-calib` 默认基准回归 | `./analysis -j 8 -r {16023,19415}` 使用默认 `definitions.yaml` + `cuts.yaml` + `file_config_run3.yaml` | `16023` `nt = 3`（与 Gate 2 `passed_S0 = 3` 完全相等）；`19415` `nt = 0`（与 Gate 2 `passed_S0 = 0` 完全相等）；`0` 次回归偏差 | **通过** |

### 3.7 明确标注的“未测量”项
- **碰撞数据 `SR-ZoneB` 真实产额与 $\Delta t$ / 波形形态实测分布**：因严格执行 Stage T0 冻结的盲分析协议（`Timing_Allow_SR_ZoneB = false`），全 Run 3 碰撞数据 `SR-ZoneB` 信号区在解盲批准前保持完全不可见，**未测量**（将在 Stage T7 分步解盲时实测）。
- **`2025/2026` 新增探测器 `Preshower2/3` 下游参考时间 $t_{0,\mathrm{down}}$ 分辨率增益与 `2026/p0015` `VetoGm0/1` 原位擦边 $\mu$ 交叉验证**：属 Roadmap Stage T6 专题工作包任务，本阶段**未测量**。

---

## 4. 阶段性物理与工程结论

1. **全 Run 3 `reduced_charge` 异质性彻底打通**：精确定位并消除了 2024 CaloNu 数字化仪双卡 `512` 状态位 / `+16.0 ns` / 通道 `{22,23}`、2025 PMT 升级引起的 `Preshower - VetoNu` `-40.3 ns` 阶跃、`2025/p0013` Preshower 拟合失效及 FASER RAW 头 `event_id` $2^{24}$ 回绕与 ECR 复位全部 5 类系统陷阱；通过自产 2025–2026 281 run / 866 分片 Aux 文件（`99.9928%` 匹配），Run 3 七大时期首次实现逐事件无缝统一处理。
2. **解析主工作点 `WP_Primary` 在超低本底前提下取得显著统计与核模型红利**：冻结主点 `S1_t2_4.0_t1_3.0_Q180_w16_tm18` 将 Run 3（$335.92\ \mathrm{fb}^{-1}$）预期 $\nu_\mu$ CC 总信号由 `1301.73` 提升至 `1374.61`（**净增 `+72.88` 例 / `+5.60%`**，上游首 50 mm 钨靶接受度翻倍有余 $5.15\% \to 11.61\%$），数据驱动总本底仅 `0.027` 事例（$B/S_{\mathrm{rec}} = 0.037\%$），30-bin 总产额统计不确定度降至 $3.133\%$，且 5 套 Geant4 强子级联模型总包络收窄至 $2.300\%$（`Timing_Calib` 仅占 `0.0260%`）。
3. **方法学对标与 ML 闭环验证**：与 FASER Quirk 分析及 LHCb/NOvA 下游参考时间拟合方法一致，解耦四站 ABCD + `VetoNu_width < 16 ns` 窗口已捕获主要穿透 $\mu$ 与双脉冲本底抑制信息；`S3_GBDT`（$\mathrm{AUC} = 0.99994$）验证若放开多维非线性边界最高还可再多挽救 `+51.7` 事例且进一步压缩 `Geant4_Albedo` 误差（$0.91\% \to 0.62\%$），待 T6/T7 评估控制区稳健性后再决定是否作为后续分析选项。在能量重建侧，证实直接外推仅在 Zone-A 训练的模型会在恢复区引入显著正向偏差，必须使用包含 Zone-B 样本的 `M4_F7_62_trainS1`（中位偏差 `+4.00%`）。

---

## 5. 下一步计划（Stage T6 与 Stage T7）

| 目标阶段 | 具体任务 | 所需输入 | 量化验收标准 |
|---|---|---|---|
| **Stage T6：2025–2026 新时期闭合与 `Preshower2/3` / `VetoGm0/1` 专题** | 1. 检验 `2025`（$117.8\ \mathrm{fb}^{-1}$）与 `2026`（$31.9\ \mathrm{fb}^{-1}$）分时期归一化控制区（`CR-Prompt`、`CR-Geom`）产额/亮度稳定性；<br>2. 量化 `Preshower2/3` 加入 $t_{0,\mathrm{down}}$ 后的下游时间分辨率及抗簇射偏置收益；<br>3. 利用 `2026/p0015` `VetoGm0/1` 实测 `CR-EdgeVN` 与高 $r_{\mathrm{VN}}$ 控制区，原位约束 `B4` 擦边 $\mu$ 本底与 `T_SR/CR` 几何传递误差。 | 1. [file_config_run3.yaml](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/file_config_run3.yaml) 与 [grl_config_run3_full.yaml](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/grl_config_run3_full.yaml)；<br>2. 冻结配置 [cuts_timing.yaml](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/cuts_timing.yaml) 与 `2025/2026` 对应 GENIE/FLUKA 模拟样本；<br>3. [timing_calib](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/timing_calib) 校准表。 | 1. 2022–2026 五年控制区单位亮度产额与 $\sigma(\Delta t)$ 跨时期偏差 $< 2\sigma$，无未解释跳变；<br>2. `VetoGm0/1` 实测擦边 $\mu$ 上界与 T5 `B4` 估计（`0.000`–`0.006` 事例）相容；<br>3. 仍保持碰撞数据 `SR-ZoneB` 100% 盲化，产出 Stage T6 中文报告与 Git commit。 |
| **Stage T7：内部审阅后分步解盲（Staged Unblinding）与物理整合** | 1. 第一阶段微解盲：开放主切选外紧邻缓冲区（如 $\Delta t \in (1.5, 4.0]\ \mathrm{ns}$ 及高电荷边带），与 T4/T5 本底预测曲线对标；<br>2. 第二阶段全量解盲：开放 `WP_Primary`（并交叉对照 `WP_Strict`），核对实测恢复事例数、$(Q,\Delta t,p_{z,\mu},q_\mu,z_{\mathrm{vtx}})$ 分布及波形显示；<br>3. 耦合 `M4_F7_62_trainS1` 更新全 Run 3 $335.92\ \mathrm{fb}^{-1}$ 30-bin 截面与能谱测量。 | 1. `T0–T6` 冻结代码、YAML 配置与审阅签核的内部文档；<br>2. 解盲批准记录（将 `Timing_Allow_SR_ZoneB` 受控切至解盲阶段设置）。 | 1. 微解盲缓冲带观测事例数与本底预测在 $2\sigma$ 内自洽；<br>2. 全量解盲后恢复样本 $\nu_\mu/\bar{\nu}_\mu$ 与 MC 形状一致，完成全 Run 3 物理结果与论文/内部 Note 更新。 |
