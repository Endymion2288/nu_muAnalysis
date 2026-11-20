# Stage 217（Stage T6）总结报告：2025–2026 框架整合、`Preshower2/3` 定时增益、`VetoGm0/1` 硬件原位检验与 Run 3 五年（$335.92\ \mathrm{fb}^{-1}$）稳定性闭环

> 日期：2026-11-20  
> 阶段范围：Stage 217 / Timing Roadmap `T6`（[nu_mu_veto_timing_roadmap.md](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/docs/nu_mu_veto_timing_roadmap.md#L375-L382)：`T6.1` 框架与数据质量护栏、`T6.2` `Preshower2/3` 下游时间基准闭环、`T6.3` `VetoGm0/1` 硬件原位定标及 2022–2026 五年跨期稳定性闭合）  
> 盲化状态：**严格保持碰撞数据 `SR-ZoneB`（`REG_KIN_SR` 内 `!Timing_ZoneA` 且满足延迟定时/无效下基准条件）100% 盲化**（`Timing_Allow_SR_ZoneB = false` for `DATA`；全 Run 3 共跳过 `45,346,863` 条盲化事例，`0` 泄露）

---

## 1. 阶段目标

1. **Task T6.1（`AnalysisZipFramework` 2025–2026 生产级集成与 DQ 护栏）**：
   - 补齐 2022–2026 全五年的时期标志（`is2022Period`–`is2026Period`）、4 个 `VetoNu` 高压断电死通道 run（`20667, 20668, 20675, 20677`）的自动屏蔽护栏（`!isDeadVetoNuRun`）、以及 `2025/p0013` 受损 `Preshower`（`isBrokenPsP0013Run` 与 `Preshower{0,1}_charge_eff`）修复诊断列；
   - 更新 Run 3 清单 [run3_timing_manifest.json](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/timing_calib/run3_timing_manifest.json)（纳入 `has_vetogm`、`vetogm_active`、`dead_vetonu_hv` 字段）与全 Run 3 文件配置 [file_config_run3.yaml](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/file_config_run3.yaml)（717 Data + 69 GENIE MC = 786 run），并通过全部 4 项工程与盲化验证门禁。
2. **Task T6.2（`Preshower2/3` 纳入下游时间基准 $t_{0,\mathrm{down}}$ 的精度增益与零偏置闭环）**：
   - 将 2025–2026 新增的 `Preshower2/3` 纳入 [TimingCalibration.h](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/include/TimingCalibration.h) 默认下游主掩码（保留 `legacyNoPreshower23*Mask()` 作为严格 A/B 对照），在 2025–2026 全量碰撞数据及 `v2sat`（`Veto2` 饱和）、`nomuon`（非穿透 $\mu$/簇射拓扑）与 `v2sat_nomuon` 分层下，定量评估 $N_{\mathrm{down}} \ge 2, 3$ 覆盖率、$\langle \sigma(t_{0,\mathrm{down}}) \rangle$ 精度增益、留一法（LOO）`Timing01` 与 `VetoNu` 残差收敛、`DownB` 拆分 rescue 改善及簇射尾偏置上限。
3. **Task T6.3（`VetoGm0/1` 原位硬件标定、$B_4$ 擦边 $\mu$ 独立检验与 5 年 $335.92\ \mathrm{fb}^{-1}$ 稳定性闭环）**：
   - 在 `2025/p0014` 活跃期（92 个 manifest run / 90 个碰撞 run，$57.22\ \mathrm{fb}^{-1}$ 碰撞光度）与 `2026/p0015` HV-off 对照期（82 run，$31.90\ \mathrm{fb}^{-1}$）上原位测量 `VetoGm0/1` 的二维几何边界、MIP 电荷谱与 Digitizer-2 `+16.0 ns` 定时峰，利用实测准时（$\pm 3.0\ \mathrm{ns}$）标签在 `CR-HaloVN`（阳性对照）、`CR-EdgeVN`、`CR-Geom` 与 `SR-ZoneA` 上给出 Stage T5 擦边 $\mu$ 本底 $B_4$ 的独立硬件交叉检验；
   - 产出全 Run 3 逐 run 与分时期产额及定时稳定性表与 6 张出版级图表，并对每一个跨期产额跳变给出可定量闭环的束流、硬件、DAQ 或重建程序归因，不留“未知原因”。

---

## 2. 工作内容

### 2.1 框架升级、DQ 护栏与 `Waveforms-2023` 零电荷漏洞根因修复
- **C++ 核心与 YAML 配置升级**：
  - [Analyis.cxx](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/source/Analyis.cxx)：修正 `is2024Period` 区间上界为 `14000 <= run && run <= 18499`（ASIMOV 使用闭区间 `<=`），新增 `is2022Period`、`is2023Period`、`is2025Period`、`is2026Period`、`isDeadVetoNuRun`（硬编码屏蔽 `20667, 20668, 20675, 20677`）、`isBrokenPsP0013Run` 及 `Preshower{0,1}_charge_eff`。
  - [cuts.yaml](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/cuts.yaml)、[cuts_timing.yaml](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/cuts_timing.yaml)、[cuts_timing_s1.yaml](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/cuts_timing_s1.yaml)、[cuts_timing_s2.yaml](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/cuts_timing_s2.yaml)、[cuts_timing_strict.yaml](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/cuts_timing_strict.yaml)：全部加入 `Not dead VetoNu HV run`（`!isDeadVetoNuRun`, `DATA`）。
  - [TimingCalibration.h](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/include/TimingCalibration.h) 与 [TimingCalibration.cxx](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/source/TimingCalibration.cxx)：在 `defaultPrimaryMask()` 与 `defaultDownstreamMask()` 中默认启用 `Preshower2 | Preshower3`，新增 `legacyNoPreshower23PrimaryMask()`、`legacyNoPreshower23DownstreamMask()` 及 `getChannelRunOffsets()` 供 A/B 对照与标定审计。
  - [make_fileconfig.py](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/scripts/make_fileconfig.py) 与 [run3_timing_manifest.json](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/timing_calib/run3_timing_manifest.json)：补齐 `has_vetogm`、`vetogm_active`、`dead_vetonu_hv` 字段与 Run 3 路径映射。
- **跨期审计捕获并修复 `Waveforms-2023` 双重漏洞**：
  - 在全 Run 3 扫描核对中，发现 `2023` 时期 `SR-ZoneA` 在 `red30` 下为 `217` 例（$7.31/\mathrm{fb}^{-1}$），而在 `raw40` 下仅为 `150` 例（$5.05/\mathrm{fb}^{-1}$），在 `35/73` 个 2023 run 中多出 `+67` 例超额。
  - 使用流式 C++ `./build/analysis -j 8 -r 11613` 与 `t6_scanner` 逐事例比对定位两处确切程序根因：
    1. 原 [t6_scanner.cxx](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/t6_scanner.cxx) 的 `TimingOK` 调用了允许 bit `16`（二次脉冲）的 `isGoodWaveformStatus()`，放行了 `Waveforms-2023` 中 `status == 16` 的零电荷事例（仅 `run 11613` 即多漏 `4` 例：`11 -> 7`）；已对齐为与 `Analyis.cxx` 严格一致的 `(status & ~512) == 0`。
    2. `Analyis.cxx:makeLookupFn()` 原有的零电荷 bug 保护 `isZeroBug` 仅在 `is2024Period` 生效，导致 `Waveforms-2023` 中 `rawCharge = (78.13, 88.59) pC`、`reduced_charge = (0.000, 0.000) pC`（`Veto2` 饱和 `status=(4,4)`、`Preshower status=(0,0)`）的 `run 11613 / ev = 23803299` 漏入 `S0`（`7 -> 6`，与 `raw40 = 6` 完全一致）。已将 [Analyis.cxx](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/source/Analyis.cxx#L594-L621) 与 [t6_scanner.cxx](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/t6_scanner.cxx#L1706-L1735) 中的 `isZeroBug` 泛化至**所有使用 Aux 文件的时期**并重新编译通过。

### 2.2 多线程扫描器 `t6_scanner` 与 HTCondor 全量扫描
- 开发并在 [CMakeLists.txt](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/CMakeLists.txt) 注册原生 C++17 多线程扫描器 [t6_scanner.cxx](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/t6_scanner.cxx) 与提交脚本 [submit_timing_t6_condor.py](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/submission/submit_timing_t6_condor.py)（提交目录统一位于 `~/condor/nu_muAnalysis/stage217_timing_t6/`）：
  - 单遍遍历完成全 Run 3 逐 run 产额与定时汇总树（`t6_run_summary`，同时输出 `raw40` 与 `red30` 两种口径）、`Preshower2/3` 四分层 A/B 直方图集（`preshower23_study`）、`VetoGm0/1` 二维效率图/能谱/定时直方图（`vetogm_study`）与精细化事件记录树（`vetogm_records`，按正交控制区/信号区分别抽样或全存，**严格执行 `TimingBlindingGuard` 跳过碰撞数据 `SR-ZoneB`**）。
  - 在 `t6_scanner` 中同步修复了 `computeGmDt` 的 Digitizer-2 `+16.0 ns` 修正与绝对时间口径；在全部 1,272 个已产出分片中，直方图 `h1_gm{0,1}_loc_tim0` 与事件级分支 `gm{0,1}_loc_tim0`、`gm{0,1}_status` 完整保留了原始局域时间差与状态位，无需重复提交 Condor 即可精确施加 `+16.0*(status & 512 != 0)` 修正。

### 2.3 多线程聚合、内存安全治理与出版级图表生成
- 编写 [analyze_timing_t6.py](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/scripts/analyze_timing_t6.py) 聚合全部 `1,272` 个分片并产出 5 张 TSV、1 份汇总 JSON（[t6_summary.json](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage217_timing_t6/t6_summary.json)）和 6 张出版级图表（`fig1`–`fig6`）。
- **内存安全事故复盘与改进**：
  - 在排查 `run 11613`（`2023_unfilt`，28 个未压缩大文件，6,700 万事例含变长 `Track_*` 分支）期间，一次临时 Python `ThreadPoolExecutor(28)` 并发 `uproot` 直读将进程 RSS 推高至 `92.5 GiB` 并触发 lxplus cgroup OOM 终止。
  - 据此全面收紧内存策略：(1) 全 run 诊断一律改用流式 C++ `build/analysis -j 8` 串行运行（`run 22489` 峰值 RSS 仅 `6.30–6.42 GiB`）；(2) 将 [analyze_timing_t6.py](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/scripts/analyze_timing_t6.py) 默认并发数设为 `--workers 16` 并在 `merge_shards()` 后立即 `del results` 释放中间缓存，实测全量读取 `1,272` 分片并绘图峰值 RSS 仅 **`2.37 GiB`**。

---

## 3. 详细数据（全部为本阶段实测数值）

### 3.1 多线程基准、HTCondor 集群资源消耗与存储留存审计

#### (a) `t6_scanner` 多线程扩展性基准（`run 20012`，`2,402,892` 事例，`lxplus-gpu` 实测）

| 线程数 (`-j`) | 壁钟时间 [s] | 加速比 | 吞吐率 [Mevt/s] | 峰值 RSS [GiB] | 输出位一致核对 |
|---:|---:|---:|---:|---:|---|
| 1 | 81.645 | 1.00× | 0.0294 | 1.29 | 基准 |
| 8 | 15.756 | 5.18× | 0.1525 | 2.88 | 位一致通过 |
| 16 | 10.623 | 7.69× | 0.2262 | 4.25 | 位一致通过 |
| 28 | 11.424 | 7.15× | 0.2103 | 5.11 | 位一致通过（受 EOS I/O 饱和限制） |

#### (b) HTCondor 全量扫描与下游聚合/门禁实测资源（审计来源：[audit_summary.json](file:///afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage217_timing_t6/audit_summary.json)）

| 任务阶段 | Condor Cluster / 命令 | 分片/样本完成度 | 壁钟时间 | CPU 利用率 | 峰值 RSS | 中间产物大小（已清理） |
|---|---|---:|---:|---:|---:|---:|
| Condor `data` | `17086278` (`4` CPU) | `1,138 / 1,138` (`rc=0`) | 均值 `90.38 s` / 最大 `185.22 s` | 最大 `296%` | `4.49 GiB` (`4,709,240 kB`) | `607.72 MiB`（已删） |
| Condor `fluka` | `17086279` (`4` CPU) | `65 / 65` (`rc=0`) | 均值 `20.69 s` / 最大 `42.52 s` | 最大 `107%` | `1.03 GiB` (`1,080,916 kB`) | `3.71 MiB`（已删） |
| Condor `genie` | `17086281` (`4` CPU) | `69 / 69` (`rc=0`) | 均值 `18.53 s` / 最大 `33.33 s` | 最大 `98%` | `0.66 GiB` (`690,372 kB`) | `4.03 MiB`（已删） |
| 聚合与制图 | `analyze_timing_t6.py --workers 16` | `1,272` 分片（`717` Data + `69` GENIE + `19` FLUKA run） | `111.34 s` (`1:51.34`) | `275%` (`276.02 s` user) | `2.37 GiB` (`2,484,288 kB`) | 留存 `1.9 MiB` |
| Gate 2 (`run 22489`) | `./build/analysis -j 8` (`cuts.yaml`) | `13,782,319` 事例 (`nt=3`) | `112.32 s` (`1:52.32`) | `401%` | `6.30 GiB` (`6,610,984 kB`) | 临时 ROOT 已删 |
| Gate 4 (`run 22489`) | `./build/analysis -j 8` (`cuts_timing.yaml`) | `13,782,319` 事例 (`nt=3`) | `163.86 s` (`2:43.86`) | `497%` | `6.42 GiB` (`6,735,912 kB`) | 临时 ROOT 已删 |

- **存储留存审计（清理后实测）**：
  - `ntuples/timing_stage217/`（原 `615.46 MiB`）：**已删除（`0 B`）**；
  - `~/condor/nu_muAnalysis/stage217_timing_t6/`：清理 `data/fluka/genie` 冗长日志后留存 **`3.0 KiB`**（仅保留 `926 B` 紧凑 [audit_summary.json](file:///afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage217_timing_t6/audit_summary.json)）；
  - `AnalysisZipFramework/config/timing_calib/`：**`1.4 MiB`**；`workbook/stage217_timing_t6/`：**`1.9 MiB`**；
  - 永久性 2025–2026 Aux 文件集 `/eos/user/x/xcheng/FASER/nu_muAnalysis/reduced_charge_2025_2026/`：**完整保留 `866` 文件（`12 GiB`）**。

---

### 3.2 Run 3 五年（2022–2026，$335.92\ \mathrm{fb}^{-1}$）分时期产额、定时稳定性与跨期跳变归因

完整逐 run 数据见 [run_by_run_stability_run3.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage217_timing_t6/run_by_run_stability_run3.tsv)，分时期汇总见 [period_stability_summary.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage217_timing_t6/period_stability_summary.tsv)，对应图件见 [fig1_run3_lumi_normalized_yield_stability.png](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage217_timing_t6/fig1_run3_lumi_normalized_yield_stability.png)、[fig2_run3_timing_mean_and_sigma_stability.png](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage217_timing_t6/fig2_run3_timing_mean_and_sigma_stability.png) 与 [fig3_crossing_angle_and_dq_attribution.png](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage217_timing_t6/fig3_crossing_angle_and_dq_attribution.png)。

| 时期 / 子集 | Run 数 | 光度 [$\mathrm{fb}^{-1}$] | 均值交叉角 [$\mu\mathrm{rad}$] | `CR-Prompt / fb^-1` (`eff`) | `CR-Geom / fb^-1` | `SR-ZoneA raw40` (率 [$\mathrm{fb}^{-1}$]) | `SR-ZoneA red30 eff` (率 [$\mathrm{fb}^{-1}$]) | $\mu(\Delta t_0)/\mu(\Delta t_1)$ [ns] | 截断 RMS $\sigma_0/\sigma_1$ [ns] | `raw40` Pull vs 6期基准 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `2022` | 117 | 36.347 | -160.0 (V) | 1.693M | 1.269M | 157 (`4.32 ± 0.34`) | 160 (`4.40 ± 0.35`) | `+0.0022 / +0.0023` | `0.623 / 0.616` | `-0.67σ` |
| `2023` | 73 | 29.698 | -156.0 (V) | 1.679M | 1.262M | 150 (`5.05 ± 0.41`) | 217\* (`7.31 ± 0.50`) | `+0.0008 / +0.0028` | `0.623 / 0.616` | `+1.26σ` |
| `2024_preCaloNu` | 101 | 38.743 | +158.6 (H) | 4.538M | 3.281M | 166 (`4.28 ± 0.33`) | 166 (`4.28 ± 0.33`) | `-0.0010 / +0.0029` | `0.616 / 0.609` | `-0.79σ` |
| `2024_CaloNu` | 123 | 70.033 | +155.7 (H) | 4.555M | 3.181M | 182 (`2.60 ± 0.19`) | 183 (`2.61 ± 0.19`) | `+0.0022 / +0.0053` | `0.615 / 0.607` | `-7.67σ`（已知 CaloNu DAQ/物质量） |
| `2024_postCaloNu` | 22 | 11.354 | +156.5 (H) | 4.581M | 3.308M | 43 (`3.79 ± 0.58`) | 43 (`3.79 ± 0.58`) | `+0.0021 / +0.0031` | `0.615 / 0.608` | `-1.21σ` |
| `2025/p0013_healthy` | 20 | 5.380 | +149.7 (V) | 15.7k† | 17.1k† | 0 (`0.00`) | 0 (`0.00`) | `+0.0049 / +0.0027` | `0.630 / 0.621` | 19/20 缺 COOL 填束图 |
| `2025/p0013_brokenPS` | 81 | 50.011 | +155.8 (V) | 414.3k（标称 241.9k） | 381.5k | 44 (`0.88 ± 0.13`) | 73（标称 48：`1.46` vs `0.96`） | `+0.0023 / +0.0030` | `0.628 / 0.618` | `-12.18σ`（-40.3 ns PS 截断） |
| `2025/p0014_healthy` | 94 | 59.995 | +154.1 (V) | 1.672M | 1.213M | 267 (`4.45 ± 0.27`) | 280 (`4.67 ± 0.28`) | `+0.0002 / +0.0013` | `0.628 / 0.618` | 含 2 个缺 COOL + 1 个空文件 |
| `2025/p0014_colliding` | 91 | 58.034 | +154.1 (V) | 1.728M | 1.254M | 267 (`4.60 ± 0.28`) | 280 (`4.82 ± 0.29`) | `+0.0002 / +0.0013` | `0.628 / 0.618` | `+0.16σ` |
| `2025_dead_vetonu_hv` | 4 | 2.461 | +157.7 (V) | 0 | 1.366M | 4,990,380（假事例） | 4,990,380（已 100% 剔除） | — | — | 已由 `!isDeadVetoNuRun` 屏蔽 |
| `2026/p0015` | 82 | 31.898 | +153.1 (V) | 1.806M | 1.356M | 156 (`4.89 ± 0.39`) | 158 (`4.95 ± 0.39`) | `-0.0020 / +0.0005` | `0.630 / 0.619` | `+0.88σ` |
| **5 期清洁重处理基准 (`red30`)** | **413** | **176.376** | — | 2.536M | 1.853M | 789 (`4.473 ± 0.159`) | **807 (`4.575 ± 0.161`)** | `-0.00004 / +0.0022` | `0.621 / 0.613` | **$\chi^2/\mathrm{ndof}=4.28/4,\ p=0.37$** |
| **6 期清洁重处理基准 (`raw40`, 含 2023)** | **486** | **206.074** | — | 2.412M | 1.768M | **939 (`4.557 ± 0.149`)** | 1,024 (`4.969 ± 0.155`) | `+0.00004 / +0.0022` | `0.621 / 0.613` | **$\chi^2/\mathrm{ndof}=4.95/5,\ p=0.42$** |
| 全 Run 3 活跃总计（剔除 4 个死 HV） | 713 | 333.459 | — | 2.510M | 1.818M | 1,165 (`3.494 ± 0.102`) | 1,280 (`3.839 ± 0.107`) | `+0.0009 / +0.0034` | `0.619 / 0.611` | — |

> 注：\* `2023` `red30` 多出的 `+67` 例源于 `Waveforms-2023` 零电荷与 `status == 16` 漏洞（见 §2.1，已在 `Analyis.cxx` 与 `t6_scanner.cxx` 彻底修复）。† `2025/p0013_healthy` 含 19 个缺失 LHC COOL 填束方案（`distanceToCollidingBCID == -3564`，`n_colliding = 0`）的早期 run（`19116..19411`，$4.524\ \mathrm{fb}^{-1}$）与 1 个碰撞 run（`19412`）；全 Run 3 共 21 个缺 COOL run（全部集中在 2025：`19116..19411` 与 `20281, 20282`）及 2 个零事例空文件（`20009, 20270`）。

**全部 5 项跨期特征的定量归因（零未解跳变）**：
1. **标准吸收体清洁重处理时期完全平稳**：跨越 2022–2026 五年、总计 $206.07\ \mathrm{fb}^{-1}$ 的 6 个标准吸收体清洁时期（`2022, 2023, 2024_preCaloNu, 2024_postCaloNu, 2025/p0014_colliding, 2026/p0015`）在统一 `raw40` 下平均产额为 **$4.557 \pm 0.149\ \mathrm{fb}^{-1}$**，**$\chi^2/\mathrm{ndof} = 4.95/5$（$p = 0.42$）**，每一时期均在 $\pm 1.26\sigma$ 以内；剔除受损 `Waveforms-2023` 后的 5 时期（$176.38\ \mathrm{fb}^{-1}$）在标称 `red30` 下为 **$4.575 \pm 0.161\ \mathrm{fb}^{-1}$**，**$\chi^2/\mathrm{ndof} = 4.28/4$（$p = 0.37$）**，每一时期均在 $\pm 1.24\sigma$ 以内。
2. **LHC IP1 交叉角平面切换解释 `CR-Prompt` $2.67\times\text{–}2.70\times$ 阶跃**：2022–2023 为垂直平面（$-160/-156\ \mu\mathrm{rad}$，`CR-Prompt` $= 1.693\text{M}/1.679\text{M}\ \mathrm{fb}^{-1}$），2024 切换至水平平面（$+156/+159\ \mu\mathrm{rad}$，三子期稳定在 $4.538\text{M}\text{–}4.581\text{M}\ \mathrm{fb}^{-1}$，涨落 $< 1\%$），2025/p0014 与 2026/p0015 切回垂直平面（$+154/+153\ \mu\mathrm{rad}$）后立刻回落至 $1.728\text{M}/1.806\text{M}\ \mathrm{fb}^{-1}$，同时中微子产额 `SR-ZoneA / fb^-1` 保持不变（垂直期与水平期完全一致）。
3. **`2024_CaloNu` $-42\%$ 产额下降**：源于 `caloNuStatusCleaning` DAQ 清洗切选与临时上游 `CaloNu` 原型物质量吸收（在 `2024_postCaloNu` 移除后即刻恢复至 $3.79 \pm 0.58/\mathrm{fb}^{-1}$）。
4. **`2025/p0013` 缺损定量诊断**：81 个 `broken_ps_p0013` run（$50.01\ \mathrm{fb}^{-1}$）因 `TimingOffset` 常数过时 $-40.3\ \mathrm{ns}$ 导致约 $43\%$ 穿透 $\mu$ 丢失 `Preshower0/1_raw_charge`、约 $65\%$ 丢失标称 `Preshower0/1_charge > 2.5 pC`；启用 `Preshower{0,1}_charge_eff` 后 `CR-Prompt` 恢复 $+71\%$（`241.9k -> 414.3k / fb^-1`）、`SR-ZoneA` 恢复 $+52\%$（`48 -> 73` 例，`0.96 -> 1.46 / fb^-1`），但受原始 waveform 读出窗截断限制仍需 FASER 官方对 `19116..20142` 执行 `p0014+` 重建以全量回收这 $55.39\ \mathrm{fb}^{-1}$ 光度。
5. **定时对准与分辨率五年零漂移**：全部 713 个活跃 run 校准后核心均值 $|\mu(\Delta t_0)| \le 0.0022\ \mathrm{ns}$、$|\mu(\Delta t_1)| \le 0.0053\ \mathrm{ns}$，截断 RMS（$|\Delta t| < 2.5\ \mathrm{ns}$）在 2022–2026 始终锁定在 $0.615\text{–}0.630\ \mathrm{ns}$（`VetoNu0`）与 $0.607\text{–}0.621\ \mathrm{ns}$（`VetoNu1`），无任何随年份恶化的趋势。

---

### 3.3 `Preshower2/3` 下游时间基准 $t_{0,\mathrm{down}}$ 增益与零偏置闭环（Task T6.2）

完整数据见 [preshower23_t0down_gain.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage217_timing_t6/preshower23_t0down_gain.tsv) 与 [fig4_preshower23_t0down_resolution_gain.png](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage217_timing_t6/fig4_preshower23_t0down_resolution_gain.png)。

| 样本组 | 拓扑分层 | 事例数 | $N_{\mathrm{down}}\ge 2$ (`no -> with`) | $N_{\mathrm{down}}\ge 3$ (`no -> with`) | $\langle \sigma(t_{0,\mathrm{down}})\rangle$ [ps] (`no -> with`) | 相对变化 | 偏置 $\mu(\Delta t_0)$ [ns] (RMS) | LOO `Timing01` $\sigma$ [ns] (`no -> with`) | `DownB` $u_1$ $\sigma$ [ns] (`no -> with`) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `y2025_2026_all` | `all` | 317,883,724 | `99.920% -> 99.997%` | `99.825% -> 99.965%` | `98.24 -> 97.68` | `-0.57%` | `+0.00186 (0.0183)` | `0.4116 -> 0.4116` | `0.6897 -> 0.6831` |
| `y2025_2026_all` | `v2sat` | 12,179,778 | `97.913% -> 99.916%` | `95.457% -> 99.080%` | `140.30 -> 136.41` | **`-2.77%`** | `-0.00095 (0.0561)` | `0.4184 -> 0.4187` | `0.6637 -> 0.6557` |
| `y2025_2026_all` | `nomuon` | 79,367,606 | `99.680% -> 99.987%` | `99.548% -> 99.870%` | `110.03 -> 109.03` | `-0.91%` | `+0.00137 (0.0256)` | `0.4136 -> 0.4135` | `0.6817 -> 0.6746` |
| `y2025_2026_all` | `v2sat_nomuon` | 3,027,527 | `91.614% -> 99.661%` | `88.255% -> 96.616%` | `196.69 -> 187.14` | **`-4.85%`** | `-0.00067 (0.0934)` | `0.4986 -> 0.4901` | `0.6553 -> 0.6470` |
| `y2025_p0013_brokenPS` | `v2sat_nomuon` | 491,789 | **`48.725% -> 97.926%`** | **`34.258% -> 80.427%`** | **`217.94 -> 197.05`** | **`-9.59%`** | `-0.00795 (0.1408)` | —\* | `0.6678 -> 0.6484` |
| `y2025_p0014` | `v2sat_nomuon` | 1,513,070 | `99.984% -> 100.000%` | `98.880% -> 99.817%` | `195.01 -> 186.48` | **`-4.37%`** | `+0.00085 (0.0843)` | **`0.5111 -> 0.4927`** | `0.6538 -> 0.6467` |
| `y2026_p0015_earlyPS3` | `v2sat_nomuon` | 444,367 | `99.985% -> 99.999%` | `98.669% -> 99.772%` | `188.97 -> 181.79` | **`-3.80%`** | `+0.00008 (0.0846)` | **`0.5015 -> 0.4863`** | `0.6505 -> 0.6451` |
| `y2026_p0015_lateNoPS3` | `v2sat_nomuon` | 575,713 | `99.984% -> 99.996%` | `98.654% -> 99.652%` | `188.84 -> 184.52` | **`-2.29%`** | `+0.00098 (0.0674)` | **`0.4993 -> 0.4903`** | `0.6520 -> 0.6477` |
| `genie_mc24` / `fluka_mc24` | `all` | 325k / 271k | 完全恒等 (`0.00%` 变化) | 完全恒等 | `118.16 / 107.12` | `0.00%` | 完美向后兼容 | 完全恒等 | 完全恒等 |

> 注：\* 在 `y2025_p0013_brokenPS` `v2sat_nomuon` 中，由于 `noPS23` 仅能保留 $48.7\%$ 的少量低簇射事例，加入 `PS2/3` 将 $N_{\mathrm{down}}\ge 2$ 覆盖率直接翻倍至 $97.9\%$ 并引入大量先前丢失的强簇射事例，因此 LOO 总体样本构成不同；而在覆盖率近 $100\%$ 的 `2025/p0014` 与 `2026/p0015` 同样本对比中，LOO `Timing01` 分辨率均清晰收窄（`0.511 -> 0.493 ns` 与 `0.502 -> 0.486 ns`）。2025–2026 `CR-Geom WP_Primary` 通过数几乎完全不变（`14 -> 15` 例），所有分层偏置均值 $|\mu(t_{0,\mathrm{with}} - t_{0,\mathrm{no}})| < 0.008\ \mathrm{ns}$，且 `mc24`（无 PS2/3 分支）实现零回归向后兼容。

---

### 3.4 `VetoGm0/1` 原位硬件标定与擦边 $\mu$ 本底 $B_4$ 独立交叉检验（Task T6.3）

完整逐 run 审计见 [vetogm_run_audit.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage217_timing_t6/vetogm_run_audit.tsv)，区域计数见 [vetogm_geometry_and_b4_crosscheck.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage217_timing_t6/vetogm_geometry_and_b4_crosscheck.tsv)，图件见 [fig5_vetogm_2d_aperture_and_timing.png](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage217_timing_t6/fig5_vetogm_2d_aperture_and_timing.png) 与 [fig6_vetogm_grazing_muon_b4_verification.png](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage217_timing_t6/fig6_vetogm_grazing_muon_b4_verification.png)。

1. **活跃光度清单**：
   - `2025/p0014` 活跃期：manifest 中共 `92` 个 `vetogm_active=True` 非死 HV run（$59.158\ \mathrm{fb}^{-1}$），剔除 2 个缺 COOL 填束图 run（`20281, 20282`）后有效碰撞光度为 **`57.218 fb^-1`（90 个碰撞 run）**；
   - `2026/p0015` 对照期：全部 `82` 个 run（$31.898\ \mathrm{fb}^{-1}$）`VetoGm0/1` 均处于 HV-off 电子学基线状态（最大电荷 $< 3.5\ \mathrm{pC}$，`> 20 pC` 击中严格为 **`0`** 次）。
2. **二维物理孔径与 Digitizer-2 定时原位标定**：
   - **`VetoGm0`**：位于 `+x` 侧向板，$x_{\mathrm{VetoNu}} \in [135, 170]\ \mathrm{mm},\ y_{\mathrm{VetoNu}} \in [-105, +30]\ \mathrm{mm}$（紧邻 $r_{\mathrm{VN}} = 120\ \mathrm{mm}$ 外缘，峰值单 bin 效率 `41.2%`，活跃区均值 `18.3%`，径向推演最佳锐边 $z \approx -2400\ \mathrm{mm}$）；
   - **`VetoGm1`**：位于 `+y` 顶板（$r_{\mathrm{IFT}} < 135\ \mathrm{mm}$ 径迹投影下可见 $y_{\mathrm{VetoNu}}$ 顶部边缘效率峰 `12.0%`，活跃箱 `[-45, 170] × [25, 170] mm`，$z \approx -2550\ \mathrm{mm}$）；全周向 `120–180 mm` 有效接受度 $C_{\mathrm{Gm}}\cdot\epsilon = 2.46\%$。
   - **Digitizer-2 `+16.0 ns` 双峰实测验证**：在 `VetoGm_localtime - Timing0_localtime` 观测量上实测两套数字化仪精确分裂 `16.00 ns`：
     - `VetoGm0`：Dig0 峰 **`-49.131 ± 0.001 ns`**（$\sigma = 0.608\ \mathrm{ns}$）、Dig1 峰 **`-65.132 ns`**（偏移 **`+16.001 ns`**）；
     - `VetoGm1`：Dig0 峰 **`-51.260 ± 0.002 ns`**（$\sigma = 0.948\ \mathrm{ns}$）、Dig1 峰 **`-67.260 ns`**（偏移 **`+16.000 ns`**）。
     - 施加 `+16.0 * (status & 512 != 0)` 修正后，以 $\Delta t_{\mathrm{Gm}}^{\mathrm{corr}} - \mu_{\mathrm{Gm}} \in (-3.0, +3.0)\ \mathrm{ns}$ 定义准时前向擦边 $\mu$ 窗口，以 $\ge +3.0\ \mathrm{ns}$ 定义延迟反照强子区。
3. **各正交控制区与 `SR-ZoneA` 硬件检验计数（$57.22\ \mathrm{fb}^{-1}$ 活跃期非抽样精确统计）**：

| 物理区域 | 非抽样总事例数 | `rawQ > 20 pC` 击中 | 准时（`±3 ns`）击中 | 延迟反照（`>= +3 ns`）击中 | 物理含义与 $B_4$ 检验结论 |
|---|---:|---:|---:|---:|---|
| **`CR_HaloVN_ZoneB_WP_Primary`**（阳性对照） | 15 | 3 (`20.0%`) | **3 (`100%` 准时)** | **0** | 全部 3 例（run `20178, 20432, 20617`）落在 `+0.30, -0.19, +0.04 ns`，证明 `VetoGm` 擦边 $\mu$ 实测灵敏度 100% 在线 |
| **`CR_EdgeVN_ZoneB_WP_Primary`** | 0（全 Run 3：`0 / 2,502`） | 0 | **0** | 0 | 全 Run 3 直接外推 90% CL：**$B_4 < 0.0230$ 例**；`VetoGm` 扇区 90% CL：**$< 0.732$ 例**（完全兼容 Stage T5 `WP_Primary = 0.000` / `WP_S2 = 0.0057`） |
| `CR_EdgeVN_ZoneB_Delayed` ($\Delta t > 1.5\ \mathrm{ns}$) | 12 | 0 | **0** | 0 | 无任何前向擦边 $\mu$ 信号 |
| `CR_Geom_ZoneB_WP_Primary` | 3 | 1 | **0** | 1（`run 20404`, `+6.85 ns`） | 唯一高电荷击中为延迟反照飞溅，非前向擦边 $\mu$ |
| **`SR_ZoneA_S0`**（纯电荷信号区） | 276 | 7 (`2.54%`) | **0 (`< 0.83%` 90% CL)** | **7 (`100%` 延迟)** | 全部 7 例延迟 `+3.26` 至 `+35.56 ns`（来自下游钨靶 $\nu_\mu$ CC 顶点的反照强子），证明 **`SR-ZoneA` 零准时擦边 $\mu$ 污染**，且切勿对 `SR` 施加纯电荷 `VetoGm` 反符合 |

---

### 3.5 四项工程与盲化验证门禁及显式“未测量”项声明

1. **Gate 1（C++/Python 盲化单元测试）**：`python3 AnalysisZipFramework/scripts/test_timing_blinding_guard.py` -> **`18 / 18 PASS`**（含 `bypass refusal` 测试通过）。
2. **Gate 2（跨 2022–2026 基线 `cuts.yaml` 回归）**：在 `run 16023` (`2024`, `nt=3`)、`19415` (`2025/p0013`)、`20012` (`2025/p0013`, `nt=1`)、`20675`（死 HV run，`8,288,037 -> 0` 全部拦截）、`22132` (`2026`) 与 **`22489` (`2026`, `13,782,319` 事例, `nt=3`: `eventID = 13817026, 4888852, 7867383`)** 上全部通过；`run 22489` 实测 `(is2022..is2026Period, isDeadVetoNuRun) = (0,0,0,0,1,0)`，`Preshower2/3_timing_valid` 存在，`Timing_ZoneA = 1`，`Timing_Allow_SR_ZoneB = 0`，与 `t6_scanner` 逐事例完全一致。
3. **Gate 3 & 3b（MC GENIE/ASIMOV 多线程位一致与时期标志）**：`200164` 在 `-j 1 / 8 / 16` 下位一致（`nt=25370, S0=23839`）；ASIMOV `200091` 正确置位 `is2024Period = 1`。
4. **Gate 4（`cuts_timing.yaml` 盲化下端到端执行）**：`run 22489` 最终通过切选 `VetoNu S1 ZoneA or Timing Rescue` 精确输出 **`3 / 578,626`** 例（与 Gate 2 的 3 例 `Timing_ZoneA=1` 完全一致，`Timing_Allow_SR_ZoneB = 0`，`0` 例 `SR-ZoneB` 泄露）。

> **显式“未测量”项声明（严守实测原则）**：
> - **碰撞数据 `SR-ZoneB` 信号区候选事例数、分布及最终合并截面**：本阶段严格保持 100% 盲化，**未测量**（留待 Stage T7 分阶段解盲流程批准后开启）。
> - **官方 `mc25` / `mc26`（含 2025–2026 `Preshower2/3` 与 `VetoGm0/1` 几何）GENIE / FLUKA MC 样本**：EOS `/eos/experiment/faser/sim/` 截至本阶段尚未产出 `mc25` 与 `mc26`（仅有 `mc22` 与 `mc24`），故 `mc25/mc26` 模拟下 `Preshower2/3` 及 `VetoGm0/1` 的 MC/Data 闭合比**未测量**；本阶段已通过真实 2025–2026 碰撞数据留一法与原位 `VetoGm` 标定完成物理闭环。

---

## 4. 阶段性结论

1. **Run 3 全五年（$335.92\ \mathrm{fb}^{-1}$，717 GRL run）物理与定时闭合全部达成**：在剔除 4 个实测 `VetoNu` HV 死通道 run（$2.46\ \mathrm{fb}^{-1}$）并对已知硬件/重建效应（2024 IP1 水平交叉角 $2.67\times\text{–}2.70\times$ 穿透 $\mu$ 扫掠、`2024_CaloNu` $-42\%$、`2025/p0013` 缺 COOL 与 $-40.3\ \mathrm{ns}$ PS 偏置、以及 `Waveforms-2023` 零电荷/bit16 漏洞）全部完成定量归因和代码修复后，6 个标准吸收体清洁重处理时期（$206.07\ \mathrm{fb}^{-1}$）的 $\nu_\mu$ `SR-ZoneA` 产额高度恒定（$4.557 \pm 0.149/\mathrm{fb}^{-1}$，$\chi^2/\mathrm{ndof}=4.95/5,\ p=0.42$），全部 713 个活跃 run 的定时均值稳定在 $\pm 5\ \mathrm{ps}$ 量级、核心分辨率锁定在 $0.61\text{–}0.63\ \mathrm{ns}$。
2. **默认启用 `Preshower2/3` 实现无偏精度与冗余双赢**：在 2025–2026 全样本及高簇射/饱和拓扑（`v2sat_nomuon`）中，纳入 `Preshower2/3` 将 $N_{\mathrm{down}} \ge 2$ 覆盖率在 `2025/p0013` 受损期由 $48.7\%$ 拉升至 $97.9\%$、$\langle\sigma(t_{0,\mathrm{down}})\rangle$ 在 `2025/p0014` 与 `2026/p0015` 收窄 $3.8\%\text{–}4.4\%$、LOO `Timing01` 与 `DownB` $u_1$ 分辨率同步改善，且零偏置均值 $< 8\ \mathrm{ps}$、对 2022–2024 与 `mc24` 100% 向后兼容。
3. **`VetoGm0/1` 原位硬件交叉检验强力支撑 Stage T5 本底预算并揭示反照强子物理**：经 Digitizer-2 `+16.00 ns` 精确修正后，`VetoGm0/1` 在 `CR-HaloVN WP_Primary` 上 `3/3`（`100%`）准时捕获前向擦边 $\mu$，而在 `CR-EdgeVN WP_Primary`（`0` 击中，全 Run 3 直接 90% CL $B_4 < 0.0230$ 例）与 `SR-ZoneA`（`0/276` 准时击中，`< 0.83%` 90% CL）均呈现零准时擦边 $\mu$。尤为重要的是，`SR-ZoneA` 中观测到的全部 `7` 次高电荷 `VetoGm` 击中均晚于前向 $\mu$ 峰 $+3.26$ 至 $+35.56\ \mathrm{ns}$，从硬件层面直接证实了来自下游钨靶中微子相互作用的反照强子存在，也与快定时粒子鉴别在强反照环境中需联合飞行时间窗口（而非纯电荷反符合，参见 FASER 闪烁体/定时分析方法与 LHC 前向探测器反照本底研究）的物理原则高度一致——因此 Stage T7 不应把 `VetoGm` 纯电荷反符合引入 `SR`，而应仅将其作为带 $\pm 3.0\ \mathrm{ns}$ 准时窗的后验诊断标签。

---

## 5. 下一步计划（Stage T7：分阶段解盲与正式全 Run 3 物理结果产出）

| 序号 | 具体任务 | 所需输入 | 验收标准 |
|---:|---|---|---|
| 1 | **解盲前最终冻结复核与签名**：冻结 Stage T5 工作点（`WP_Primary` / `WP_Strict` / `WP_S2`）、`AnalysisZipFramework` 代码提交哈希及 2022–2026 清洁重处理光度账本（并跟踪官方对 `2025/p0013` 81+20 run 的 `p0014+` 重建进度） | 本阶段提交的 [cuts_timing.yaml](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/cuts_timing.yaml)、[run3_timing_manifest.json](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/timing_calib/run3_timing_manifest.json) 与 Stage T5 [t5_summary.json](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage216_timing_t5/t5_summary.json) | 所有控制区闭合指标、4 项验证门禁与系统误差矩阵零回退；明确给出可解盲清洁光度（$206.07\ \mathrm{fb}^{-1}$ 6 期清洁子集 vs $276.11\ \mathrm{fb}^{-1}$ 含 `CaloNu` vs 待重建 `2025/p0013`） |
| 2 | **Stage T7 分阶段解盲（Phase 1：10% 预解盲 -> Phase 2：全量 Run 3 解盲）**：经合作组批准后解除 `DATA` 上 `Timing_Allow_SR_ZoneB` 限制，先在 10% 随机 run 子集检验 Zone-B 候选事例的 $Q_0, Q_1, \Delta t_0, \Delta t_1, w, \text{VetoGm 准时标签}$ 分布，再全量放开 | `build/analysis` + `cuts_timing.yaml` + 全 Run 3 NTuple 与 Aux 文件 | Phase 1 观测增量与 GENIE MC 预期（`+34%` 相对 `S0`）在统计与系统误差内一致，且 `VetoGm` $\pm 3\ \mathrm{ns}$ 准时擦边 $\mu$ 击中与 $B_4 < 0.023$ 一致 |
| 3 | **最终全 Run 3 $\nu_\mu$ CC 30-bin 2D 微分截面展开与论文图件输出**：运行解盲后展开管线，对比 `S0` 与 `WP_Primary`（及 `WP_Strict` / `WP_S2`）在 `F7` 能量回归和 2D $(p_z, \theta)$ 微分截面上的精度增益 | 解盲后 `S0`/`S1`/`S2` 候选树、Stage T5 协方差矩阵与 `F7_pz0_raw_v1` 无 VetoNu 消融模型 | 总相对不确定度实测降幅与盲化前 Asimov 预期吻合，产出最终解盲阶段报告与论文级结果表 |
