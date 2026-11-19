# 阶段 215（Stage T4）：全 Run 3 盲化正交侧带本底测量与五类本底预算分析

- **日期**：2026-11-19
- **状态**：已完成（Stage T4 / 阶段 215，真实碰撞数据 `SR-ZoneB` 盲化锁严格激活）
- **前置阶段**：Stage T0–T3（阶段 211–214，最近一次提交 `cfc40f3`）

---

## 阶段目标

依据 [nu_mu_veto_timing_roadmap.md](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/docs/nu_mu_veto_timing_roadmap.md)（第 5.1、5.2、7 节与 8-T4 节），在严格保持碰撞数据 `SR-ZoneB` 完全不可见（**Blind Analysis**）的前提下，完成覆盖全部五个本底机制的独立、数据驱动定量测量并检验核心物理假说 **H4**：

1. **盲化守卫与全量并行扫描**：将 [TimingBlindingGuard.h](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/include/TimingBlindingGuard.h) 入口硬盲化锁嵌入高速多线程 C++ 扫描器 [t4_bkg_scanner.cxx](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/t4_bkg_scanner.cxx)，通过 HTCondor 覆盖全 Run 3 碰撞数据（`2022–2026`，`335.9197 fb^-1`，`1,031` 个作业 / `15,194` 个 PHYS 文件）、`2024_cos` 宇宙线数据、`19` 组 FLUKA μ 子背景 MC 与 `12` 个 GENIE 中微子 MC run；
2. **零协方差 `(u_0, u_1)` 验证与正交 ABCD 闭合**：构造互相完全独立的下游四站参考 `t0_A`（`kMaskDownA = {Veto10, Veto11, Veto20, Veto21}`）与 `t0_B`（`kMaskDownB = {Timing01, Timing23, Preshower0, Preshower1}`），验证跨层 Pearson 相关系数消弭并在 `CR-Geom`、`CR-Geom-HiTheta`、`Kinematic_SR_NegMirror` 与 1-hit 单层失效率侧带中闭合；
3. **五分量本底不重算分解（`B1–B5`）与假说 H4 裁决**：在 [estimate_timing_bkg_abcd.py](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/scripts/estimate_timing_bkg_abcd.py)（`--workers 28`）中扣除 GENIE 中微子侧带污染、完成跨年度 7 周期稳定性审计，精确分离：
   - **`B1`**：2-hit 随机正延迟尾部交叠（分 `(r_VN, Q_max)` 2D 网格 + 保守 `C_t0(t2)` 转换）；
   - **`B2`**：真穿行 μ 子单层失效率（Zone A 单层漏记 + 另一层延迟尾部）；
   - **`B3`**：不重算 `CR-Geom` 关联超额（高电荷 μ 子韧致辐射/电磁簇射与 `-25 ns` 错束团 Pileup）；
   - **`B4`**：`VetoNu` 径向边缘漏穿（`r_VN >= 120 mm` 或近边界散射 μ 子进入 SR）；
   - **`B5`**：非碰撞束团、Beam-Halo（`Beam1_InB1_0`）、宇宙线（`2024_cos`）、束团内偶然符合与下游饱和/失步分量。

---

## 工作内容

1. **盲化守卫与极端 NaN 边界修复（`18/18` 单元测试全通过）**：
   - 在 HTCondor 首批全量 Data 扫描（Cluster `9759520`）运行过程中，[t4_bkg_scanner.cxx](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/t4_bkg_scanner.cxx#L1550-L1557) 中的 `REG_KIN_SR` 二次防御性断言捕获到一个潜在接口不一致：当径迹高偏移击中单侧 Timing 闪烁体时，未被击中侧的 Timing 电荷分支在部分 PHYS 事例中为 `NaN`（实测 `007930` 文件 `00000-00024` 在 `59,352` 事例中存在 `7` 例），导致 [TimingBlindingGuard.h](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/include/TimingBlindingGuard.h) 漏判为非运动学 SR 而由防御性断言主动 `abort()` 中止（`464 / 921` 个作业在写出任何文件前触发 `TimingBlinding violation` 退出，实现零泄漏）。
   - 修复 [TimingBlindingGuard.h](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/include/TimingBlindingGuard.h#L47-L57)、[timing_blinding_guard.py](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/scripts/timing_blinding_guard.py#L27-L42) 与 [t4_bkg_scanner.cxx](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/t4_bkg_scanner.cxx#L1445-L1450) 仅对被径迹击中的 Timing 半平面检查 `isfinite`，并在 [test_timing_blinding_guard.py](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/scripts/test_timing_blinding_guard.py) 新增 `sr_zoneB_top_hit_nan_bottom` 与 `sr_zoneB_bot_hit_nan_top` 两个测试用例，`18/18` C++/Python 一致性单元测试与反绕过测试全数通过。重编并重投 Cluster `9759529` 后，`464/464` 补跑作业零异常完成。
2. **高速多线程 C++ 扫描器与紧凑 Sharding 存储设计**：
   - 取消 `t4_bkg_scanner` 中对海量 prompt 2-hit 大宗事例的盲目存树，改为以确定性哈希预抽样保存（`REG_KIN_SR` 抽样率 `0.002` -> 精确逆预标度权重 `ev_w = 500`；`CR-Geom` 抽样率 `0.01` -> `ev_w = 100`；所有 1-hit 与延迟尾部全量保留 `ev_w = 1`），将全 Run 3 Data 输出总体积从预计超过 `400 GB` 压缩至 **`10,793,191,469 bytes`（`10.05 GiB` / `10,293.19 MiB`）**；全量直方图与协方差累计器仍在 C++ `RDF` 无抽样下精确统计。
   - 更新 [CMakeLists.txt](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/CMakeLists.txt) 与 [submit_timing_t4_condor.py](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/submission/submit_timing_t4_condor.py)，通过 `--workers 28` 校验所有分片。
3. **28 核并行 ABCD 闭合与 I/O、计算双重加速优化**：
   - 将 [estimate_timing_bkg_abcd.py](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/scripts/estimate_timing_bkg_abcd.py) 升级为 `forkserver` 多进程规约架构，本地 EOS FUSE 读取结合内存 `io.BytesIO` 解压及失败时自动切换 `xrdcp -s root://eoshome-x.cern.ch/... -`（解决节点本地 EOS FUSE 缓存页面失效导致 `data_0624.root` 报错 `unrecognized compression algorithm: b'\x00\x00'`，而 XRootD 实测可无误读取全部 `94,544` 行）。
   - 在 worker 内预汇总非碰撞区域计数 `nc_counts` 并将 `data_small_ev` 由 `28.6M` 行收窄为仅保留 `REG_CR_EDGE_VN` 与几何 SR 内 `REG_NONCOLL_B1`（缩减 `~1000x`），同时改用在无盲化、`Q < 200 pC`、运动学 SR 同几何负延迟侧 `Kinematic_SR_NegMirror_MIP_Qlt200` 纯净 μ 子测得的平滑仪器分辨率转换系数 `C_t0(t2)`，消除原宽脉冲簇射对 `T_2hit = 3.0 ns` 处的污染，使总运行时间由 `7,551.14 s` 降至 **`254.27 s`**（`/usr/bin/time -v` 全程 `261.46 s` 报告打印 / `4:31.82`）。
4. **临时空间清理与目录审计**：
   - 确认 `condor_q` 零运行作业后删除全部 `1,031` 个 EOS 临时分片（`/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/timing_stage215` 已移除），清理 `/afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage215_timing_t4/` 下的冗余 tarball/logs/plans，仅保留 **`46 KB`** 紧凑审计文件（含 [audit_summary.json](file:///afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage215_timing_t4/audit_summary.json)、`.sub`、`run_*.sh`、`pending_jobs.args`）。

---

## 详细数据

### 1. 执行命令、多线程扩展性与 HTCondor 资源汇总

1. **本地 `./build/t4_bkg_scanner` 多线程加速与确定性检验**：
   - 7 个 2024 物理文件代表切片（`n_total = 20,703,503`，`n_blinded = 65,130`，`n_geom = 612,793`，`n_tail_recs = 1,487,282`）：
     * `--threads 1`：`wall_s = 442.437 s`（`0.04679 Mevt/s`，进程 `/usr/bin/time` 墙钟 `443.80 s`，Max RSS **`1,657,600 KB`** / `1.58 GiB`）；
     * `--threads 8`：`wall_s = 70.1038 s`（`0.2953 Mevt/s`，`443.80 -> 72.17 s`，Max RSS `3,989,228 KB`）；
     * `--threads 16`：`wall_s = 44.49 s`（`0.4654 Mevt/s`，`time` `46.27 s`，Max RSS `6,344,156 KB`）；
     * `--threads 28`：`wall_s = 34.1763 s`（`0.6058 Mevt/s`，`time` `35.87 s`，Max RSS `10,917,160 KB`），实现 **`12.95x`** 多核加速；
     * 与 `j=1` 输出一致性对比（`j = 8, 16, 28`）：所有整型计数与非协方差分支 `exact_non_cov_diffs = []`，浮点协方差累计器最大相对误差 `max_cov_rel_diff <= 1.140e-13`。
   - 2022 精简切片 `MT2022`（`n_total = 1,759,244`，`n_blinded = 1,864`，`n_tail_recs = 3,850`）：
     * `j=1: 34.4387 s (RSS 1,305,728 KB)`；`j=8: 6.92088 s (2,431,072 KB)`；`j=16: 6.69885 s (2,429,780 KB)`；`j=28: 8.2377 s (2,431,336 KB)`；`j=8/16/28` 与 `j=1` 间 `non_cov_diffs = []`，`max_cov_rel_diff <= 1.448e-13`。
   - 修复 opposite-Timing-paddle `NaN` 后的 `data_0000`（`43` 文件、`37,646,015` 事例，`--threads 28`）：`wall_s = 49.0928 s`（`0.766834 Mevt/s`，`n_blinded = 43,350`）。

2. **HTCondor 全量 `1,031` 作业吞吐与资源统计**（源自 [audit_summary.json](file:///afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage215_timing_t4/audit_summary.json)）：

| 数据流 | 有效作业数 / 计划数 | PHYS 文件数 | 扫描总事例数 | 分片体积 | Wall 中位 / p95 / 最大 (s) | Max RSS 中位 / 最大 (MB) | CPU 利用率中位 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `data`（Cluster `9759520` + `9759529`） | `921 / 921` | `10,618` | `19,666,814,300` | `10,293.19 MiB` | `143.02 / 239.27 / 381.67` | `2697.0 / 3777.8` | `312%` |
| `fluka`（Cluster `9759521`） | `66 / 66` | `1,813` | `345,798,810` | `16.55 MiB` | `45.39 / 53.52 / 57.72` | `660.6 / 1209.8` | `282.5%` |
| `genie`（Cluster `9759522`） | `32 / 32` | `546` | `5,414,860` | `18.08 MiB` | `6.60 / 8.51 / 14.96` | `580.7 / 600.3` | `112.0%` |
| `cosmic`（Cluster `9759523`） | `12 / 12` | `2,217` | `87,772` | `0.31 MiB` | `11.96 / 13.65 / 13.88` | `364.7 / 367.2` | `48.5%` |
| **合计** | **`1,031 / 1,031`** | **`15,194`** | **`20,018,115,742`** | **`10.8298 GB`** | 总 Wall `143,151.40 s` | 估算 CPU **`159.06 核时`** | — |

3. **下游 Python 并行归约与存储审计**：
   - 运行命令：`source AnalysisZipFramework/setup.sh && /usr/bin/time -v python3 AnalysisZipFramework/scripts/estimate_timing_bkg_abcd.py --workers 28`；
   - 优化前后耗时对比：初始版本并行加载耗时 `1271.49 s`、总耗时 `1:30:56`；第二版重构后加载 `178.39 s` 但单核扫 `28.6M` `Empty_BCID` 导致分析阶段 `7372.75 s`（总 `7551.14 s`）；最终版预聚合 `nc_counts` 并叠加 XRootD 自动回退后，**并行加载耗时 `225.91 s`、后处理与绘图仅 `35.55 s`（提速 `207x`）、脚本内部总计 `254.27 s`（`/usr/bin/time` 含退出 `4:31.82`）、主进程 Max RSS `1,509,976 KB`**。
   - 空间清理验证：`test_timing_blinding_guard.py` 复测 **`18/18 PASSED`**；EOS `timing_stage215` 已清除（保留 `energy_ml_stage54` 等无关目录）；`~/condor/nu_muAnalysis/stage215_timing_t4/` 仅余 **`46 KB`**；[timing_calib/](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/timing_calib/) 为 **`1.3 MB`**（`< 2 MB`）；[stage215_timing_t4/](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage215_timing_t4/) 全部产出共计 **`1.1 MB`**。

---

### 2. 两项关键 2025–2026 Run 3 数据质量（DQ）发现

1. **剔除 4 个 VetoNu 高压关闭的 2025 run**：
   - 在核查 `raw40` Zone A 异常峰时发现，Runlist 中的 **`20667, 20668, 20675, 20677`** 四个 2025 run 在 `t4_run_summary` 中呈现 **`prompt2h = 0`**，却在 `23,275,404` 碰撞事例中产生多达 **`4,990,381`** 个伪 SR Zone A（`4,990,381` `raw40` / `red30`）与 `3,362,179` 个 `CR-Geom` 事例。将其从活时间数据中剔除后，全 Run 3 **活跃 VetoNu 样本为 `711` 个 run**：共 `19,643,479,827` 碰撞总记录事例、严格盲化的 **`58,717,967` 个 `SR-ZoneB` 事例** 与 `599,855,530` 个 `CR-Geom` 事例（对应 `335.9197 fb^-1`）。其余 `193` 个正常 2025 run 仅产生 `311` 个 `raw40` SR Zone-A 事例。
2. **`2025/p0014` 与 `2026/p0015` 中 `VetoNu*_reduced_charge` 积分窗口未对齐**：
   - 全量汇总揭示 `2025` 与 `2026` 分别产生 `403,853` 与 `307,535` 个伪 `red30` SR 单层漏记事例（共 `711,388` 例），但同期 `raw40` 下 `2025` 与 `2026` 的 1-hit SR prompt 计数分别为 **`0` 与 `0`**（在 `data_0809.root` 抽检中，prompt 穿过 μ 子真实 `q0_raw` 为 `83.9–607.8 pC`，而 `q0_red` 却为 `-0.12` 至 `+0.60 pC`；`data_0843.root` 中亦呈 `q0_raw = 77.9–206.9 pC` vs `q0_red = -0.08` 至 `+1.34 pC`）。
   - 据此采用分时代一致的物理 Zone A 判据：**`2022–2024`（`run < 18500`）与 MC 使用 `reduced_charge < 30 pC`**，**`2025–2026`（`run >= 18500`）使用 `raw_charge < 40 pC`**。在此物理干净口径下，全 Run 3 **`686,197,609`** 例 SR prompt 穿过 μ 子（`|dt| < 1.0 ns`）中仅出现 **`7` 例**真实单层漏记（`0.0102 ppm` / 约 `1.02e-8`：2022 年 `1` 例、2023 年 `0` 例、2024 年 `6` 例、2025 年 `0` 例、2026 年 `0` 例），直接将单层失效率本底 **`B2`** 钉死在 **`0.001 +- 0.015`** 事例（见 [fig3_single_layer_miss_and_edge_vn.png](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage215_timing_t4/fig3_single_layer_miss_and_edge_vn.png)）。

---

### 3. 零协方差四站分离 `(u_0, u_1)` 独立性与正交侧带 ABCD 闭合

完整数据表见 [t4_u0_u1_independence.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage215_timing_t4/t4_u0_u1_independence.tsv)、[t4_genie_cr_contamination.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage215_timing_t4/t4_genie_cr_contamination.tsv) 与 [t4_abcd_closure_tests.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage215_timing_t4/t4_abcd_closure_tests.tsv)，可视化见 [fig1_u0_u1_independence_and_cov.png](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage215_timing_t4/fig1_u0_u1_independence_and_cov.png) 与 [fig2_abcd_closure_cr_geom_and_neg_sr.png](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage215_timing_t4/fig2_abcd_closure_cr_geom_and_neg_sr.png)：

1. **相关性消除验证（`Run3_All`）**：
   - 在 `CR_Prompt_1p0ns`（`N_u = 653,183,410` / `N_dt = 686,197,609`）：共同下游参考下的 `rho(dt0, dt1) = +0.025801 +- 0.000038`，而分离四站参考下 **`rho(u0, u1) = +0.001383 +- 0.000039`**（相关性降低 **`18.7x`**）；
   - 在 `CR_Prompt_1p5ns`（`N_u = 797,835,165`）：`rho(dt0, dt1) = +0.030101 +- 0.000035`，分离四站参考下 **`rho(u0, u1) = +0.000097 +- 0.000035`**（相关性降低 **`310x`**）。条件尾部概率 `P(u1 > T | u0, Q < 200 pC)` 在 `|u0| < 2.2 ns` 宽范围内保持完全平坦。
2. **GENIE 侧带中微子信号扣除（`335.92 fb^-1`）**：
   - `REG_CR_GEOM_ALL` 中预期存在 `1,168.275` 个总中微子事例，其中 `S1_zoneB = 116.238 +- 1.329`（`Q_2hit < 200 pC` 下 `70.941`）；`REG_CR_GEOM_HITHETA` 中总中微子 `157.365` 例、`S1_zoneB = 17.720 +- 0.522`；`REG_CR_EDGE_VN` 中总中微子 `10.453` 例、`S1_zoneB = 1.023 +- 0.127`。必须在正交 ABCD 与超额测量中先减去 GENIE 侧带预期，否则高阈值区纯信号会被误当本底。
3. **非盲控制区（`CR`）ABCD 闭合检验**：
   - **大角度软 μ 子区 `CR_Geom_HiTheta`（`25 <= theta < 55 mrad`）**：在扣除 GENIE 后与分离 ABCD 联合预测精准闭合：`cum_1p5_22` 观测 `124` vs 预测 `117.67`（`1.054`，`+0.55 sigma`）；`cum_1p8_22` 观测 `31` vs `27.02`（`+0.71 sigma`）；`cum_2p5_22` 观测 `7` vs `7.49`（`-0.18 sigma`）；`cum_3p0_22` 观测 `5` vs `6.81`（`-0.81 sigma`）。
   - **运动学 SR 负延迟镜像区 `Kinematic_SR_NegMirror_MIP_Qlt200`（`N_D = 448,956,298`）**：在 `|t0_down| < 2.5 ns` 与 `Q < 200 pC` 下的 `-u0/-u1` 在 `1.5–2.5 ns` 内 `obs/pred = 1.071–1.195`（如 `cum_1p5_22: 152,803 vs 142,352.66`、`cum_2p0_22: 5,392 vs 4,901.51`、`cum_2p2_22: 1,468 vs 1,327.41`）。由于四站 `dt` 比两站 `u` 具备略高时间精度（`std_dt ~ 0.464 ns` vs `std_u ~ 0.471 ns`），同域 `common_dt0_dt1_neg` 观测值反低于 `decoupled_u` 预测（`130,694 vs 142,352.66 = 0.918`、`1,112 vs 1,327.41 = 0.838`），因而 `c_t0_by_t2` 保守钉在 **`1.0`**，确保 `B1` 不低估且与 `B3` 边界清晰无缝。
   - **CR-Geom 1-Hit 延迟闭环（`B2` 校验）**：对 `CR-Geom` `254`（`VN0`）与 `473`（`VN1`）个 prompt 1-hit 事例用 2-hit 单臂尾部概率交叉预测并叠加 GENIE，观测与总预测在统计内一致（如 `T1 > 2.0 ns`: `VN0` `27 vs 24.87`，`VN1` `45 vs 39.19`；`T1 > 3.0 ns`: `VN0` `15 vs 23.44`，`VN1` `30 vs 36.10`），证实 `CR-Geom` 延迟 1-hit 事例主要由中微子构成而非未计本底。

---

### 4. `B3` 关联超额的物理根因与 `B1–B5` 五分量本底预算（回答假说 H4）

1. **`B3` 的物理来源（[t4_b3_b4_fluka_and_edge.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage215_timing_t4/t4_b3_b4_fluka_and_edge.tsv) 与 [fig4_width_and_backscatter_b3.png](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage215_timing_t4/fig4_width_and_backscatter_b3.png)）**：
   - 在 `10%` 抽样 Data 的 `CR_Geom_OuterR` 2-hit `dt > 3.0 ns` 延迟事件中，**`85.0%`（`463 / 545`）** 伴随高电荷 **`Q_max > 200 pC`（`3–12 MIP`）**，其中 `t0_down` 的 `5%` 分位到达 `-25.19 ns`、`25%` 分位达 `-3.29 ns`（前序 BCID `-25 ns` 锁定 Pileup），且 `46.6%`（`254/545`）伴随 `w > 10 ns` 展宽波形；
   - 独立在 `FLUKA` μ 子背景 MC（`3.458e8` 模拟穿行事例，未含任何真实中微子信号）中核对：`REG_KIN_SR` 共有 `13` 例通过未清洗 `S1(2.2, 3.0)`（等价 `335.92 fb^-1` 下高达 `69,772.9 +- 19,351.5` 事例），其中 **`12/13` 具有 `Q_max > 200 pC`**（`13/13` 全部 **`Q_max >= 183.9 pC`**，而 1-hit 通过 `0` 例）。这证实 **`B3` 的物理本质是高能穿行 μ 子在上游产生电磁簇射/韧致辐射以及 `-25 ns` 错束团 Pileup 同时延迟两层 `VetoNu`**。
   - **三维清洗抑制效果**：施加 **`|t0_down| < 2.5 ns` + `width < 12.0 ns` + `Q_2hit < 200 / 180 pC`** 后，FLUKA `REG_KIN_SR` 2-hit 本底记数从 **`13` 例（`69,772.9`）骤降至 `0` 例**；真实 Data `CR-Geom` `2-hit` 观测总数从 `14,672` 例（`allQ_not0`）依次降至 **`473`**（`Q<200, t2=2.5, w<12`）、**`33`**（`Q<180, t2=3.0, w<12`）与 **`23`**（`Q<150, t2=3.0, w<12`）。

2. **`B4`（[t4_b3_b4_fluka_and_edge.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage215_timing_t4/t4_b3_b4_fluka_and_edge.tsv)）与 `B5`（[t4_b5_accidental_noncoll.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage215_timing_t4/t4_b5_accidental_noncoll.tsv)）测量结果**：
   - **`CR-EdgeVN`（`120 <= r_VN < 180 mm`）**：剔除 4 个无高压 run 前全量观测 `2,520` 例；扣除 GENIE `Zone A` 预期（`8.576` 例）后剩余径向边缘穿行 μ 子基数 **`edge_vn_zoneA_mu = 10.4`**，而 Zone B（`S1`）仅观测 **`1` 例**（同期 GENIE 中微子预期 `0.46–1.02` 例），给出 SR 边缘漏穿 **`B4 = 0.0–1.45 +- 2.40`** 事例；另外在 2026 新增 `VetoGm` 触发检验中，`684` 例 `CR-EdgeVN` 仅 `5` 例 `vgm_max_q >= 40 pC`。
   - **非碰撞与偶然符合**：全量 `Beam1_InB1_0`（`442,826,675` 事例，几何 SR 下行径迹 `25,360` 例）、`Unpaired_BCID`（`3,724,671` 事例，SR `8,759` 例）与 `Empty_BCID_Other`（`334,280,502` 事例，SR `13,011,602` 例）给出非碰撞延迟偶然率 **`p_acc_vn0_delayed_2p2 = 0.00141452`**、**`p_acc_vn1_delayed_2p2 = 0.00142434`**；`2024_cos` 宇宙线（`87,772` 事例）在运动学 SR 长期径迹cut下通过 `0` 例。结合活跃 Data SR Zone A μ 子基数（扣除 GENIE 后）给出 **`B5 = 4.96–5.51 +- 0.004`** 事例（以束团内/邻窗偶然符合为主）。

3. **Run 3 全量五分量本底预算代表工作点对比（`335.9197 fb^-1`，源自 [t4_summary.json](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage215_timing_t4/t4_summary.json) 与 [t4_background_budget_scan.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage215_timing_t4/t4_background_budget_scan.tsv)，见 [fig5_five_component_bkg_vs_threshold.png](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage215_timing_t4/fig5_five_component_bkg_vs_threshold.png)）**：

| 策略与清洗口径 | 工作参数 (`w_max`, `Q_2hit`, `T_2hit`, `T_1hit`) | `B1` (2-hit 随机) | `B2` (1-hit 漏穿) | `B3` (簇射/超额) | `B4` (边缘) | `B5` (偶然/非碰撞) | **`B_tot +- B_err`** | **`S_rec` (`fid numu CC`)** | **`B_tot / S_rec`** | **`B_tot / sqrt(S)`** | 假说 **H4** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `S1` 未清洗（基线） | `w<19.5`, 无`Q`/无`t0`, `2.2 / 3.0 ns` | `6244.89` | `0.001` | `17603.60` | `0.00` | `5.23` | **`23853.71 +- 4408.84`** | `129.43` | `18430.3%` | `630.539` | **否决** |
| `S1` MIP-Clean | `w<12`, `<200 pC`, `|t0|<2.5`, `2.5 / 3.0 ns` | `767.23` | `0.001` | `193.56` | `1.21` | `5.23` | **`967.23 +- 80.27`** | `80.51` | `1201.4%` | `26.016` | 未过关 |
| `S1` MIP-Tight | `w<12`, `<180 pC`, `|t0|<2.5`, `3.0 / 3.0 ns` | `18.14` | `0.001` | `27.05` | `1.29` | `5.23` | **`51.71 +- 14.80`** | `78.25` | **`66.09%`** | `1.392` | **初步达标** |
| `S1` MIP-UltraTight-180 | `w<12`, `<180 pC`, `|t0|<2.5`, `3.5 / 3.5 ns` | `0.45` | `0.000` | `7.69` | `1.41` | `5.09` | **`14.63 +- 10.91`** | `76.09` | **`19.23%`** | `0.394` | **强烈通过** |
| `S1` MIP-UltraTight-150 | `w<12`, `<150 pC`, `|t0|<2.5`, `3.5 / 3.5 ns` | `0.32` | `0.000` | `4.72` | `1.45` | `5.09` | **`11.59 +- 10.38`** | `73.52` | **`15.76%`** | `0.312` | **强烈通过** |
| `S1` **纯 1-Hit Only** | `w<12`, 屏蔽 2-hit, `|t0|<2.5`, `- / 3.0 ns` | `0.00` | `0.001` | `0.00` (`+-9.58`) | `0.00` (`+-2.40`) | `5.23` | **`5.23 +- 9.87`** | **`68.65`** | **`7.62%`** | **`0.141`** | **最优通过** |
| `S1` `raw40_ext (2025/26口径)` | `w<12`, `<180 pC`, `>32ns`, `3.0 / 3.0 ns` | `18.14` | `0.000` | `1132.62` | `0.15` | `5.23` | `1156.15 +- 286.41` | `144.18` | `801.9%` | `31.568` | 需禁用双层`>32ns` |
| `S2` 原始 MIP (`dchi2>25`) | `w<19.5`, `<200 pC`, `z2>3.0 (~1.8ns)`, `z1>6` | `83628.74` | `0.353` | `0.00` | `1.16` | `5.09` | `83635.35 +- 724.78` | `85.95` | `97311.1%` | `2245.151` | 需提高 `z2` |

4. **7 个取数时期本底稳定性审计**（详见 [t4_period_stability.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage215_timing_t4/t4_period_stability.tsv) 与 [fig6_run3_period_bkg_stability.png](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage215_timing_t4/fig6_run3_period_bkg_stability.png)）：

| 周期 | 亮度 (`fb^-1`) | 活跃 Run | 总碰撞事例 | 盲化 `SR-ZoneB` 事例 | SR Prompt / `fb^-1` | Geom Prompt / `fb^-1` | 1-Hit 漏记 (`ppm`) | `rho(u0, u1)` (`\|u\|<1.0`) | 基准 `B_tot / fb^-1` (`Q<200,2.5/3.0`) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `2022` | `36.347` | `117` | `2,560,484,018` | `3,813,902` | `1,396,261.3` | `961,467.0` | `0.0197` | `+0.00079 +- 0.00014` | `1.2474` |
| `2023` | `29.6982` | `73` | `2,105,887,786` | `3,215,860` | `1,384,855.1` | `954,016.4` | `0.0` | `+0.00123 +- 0.00016` | `1.2132` |
| `2024_preCaloNu` | `38.7435` | `101` | `4,231,224,730` | `13,182,138` | `3,768,060.6` | `2,475,247.2` | `0.0137` | `+0.00175 +- 0.00008` | `3.1861` |
| `2024_CaloNu` | `70.0331` | `123` | `7,036,069,805` | `24,073,218` | `3,787,230.5` | `2,489,683.7` | `0.0151` | `+0.00203 +- 0.00006` | `3.1605` |
| `2024_postCaloNu` | `11.3535` | `22` | `1,214,839,959` | `3,918,137` | `3,805,996.4` | `2,496,421.5` | `0.0` | `+0.00143 +- 0.00015` | `3.1892` |
| `2025`（剔除4坏Run） | `117.8464` | `193` | `985,928,242` | `6,926,185` | `785,376.2` | `546,501.8` | `0.0` | `+0.00004 +- 0.00011` | `1.0743` |
| `2026` | `31.8981` | `82` | `1,509,045,287` | `3,588,527` | `1,483,964.9` | `1,020,425.8` | `0.0` | `-0.00003 +- 0.00015` | `2.1464` |

*(注：2024 vs 2022–23 / 2025–26 的单位亮度 SR Prompt 速率差异反映 LHC 交叉角 / 束流与触发预标度及运行工况变化；同年度三大 2024 子周期保持在 `3.16–3.19 / fb^-1` 的亚百分点稳定性。)*

---

### 5. 未测量项目声明

- **真实物理碰撞数据 `SR-ZoneB`（`dt > +1.5 ns` 且位于运动学 SR）的实际观测事例数、能谱与击中分布**：**未测量**（严格盲化锁 `Timing_Allow_SR_ZoneB = false` 激活中，严禁任何探测或画图）。
- **面向最终开盲的优化策略冻结与 `S1 / S2 / S3 (GBDT)` Asimov 发现显著度全局最大化、以及去除 `VetoNu` 电荷特征后的 ML 能量回归消融重训结果**：**未测量**（将在 Stage T5 完成并完成开盲前审计）。

---

## 阶段性结论

1. **盲化工程与数据契约闭环**：在 `20.02B` 总扫描事例中 `SR-ZoneB` 零泄漏（`18/18` 单元测试全过），并抓出两项足以改变本底数量级的 2025–2026 DQ 隐患（4 个无高压 2025 run 与 `reduced_charge` 积分窗口失效），将真实单层穿行失效率钉死在 **`1.02e-8`（`7 / 686,197,609`）**。
2. **四站分离 `(u_0, u_1)` 独立性成立**：在全 Run 3 `653M–798M` 高统计样本下，跨层相关度由 `+0.026..0.030` 降至 `+0.00138`（`1.0 ns`）/ `+0.00010`（`1.5 ns`），并在 `CR-Geom-HiTheta` 与 `Kinematic_SR_NegMirror` 闭合于 `1 sigma / ~7–20%` 量级，证明 `B1` 可被全数据驱动精准约束。
3. **假说 H4 获精确边界裁决与重大物理发现**：
   - 未施加电荷与宽度约束的 `S1(2.2, 3.0, w<19.5, allQ)` **无法通过 H4**（`B_tot = 23,853.71 +- 4,408.84` vs `S_rec = 129.43`），因为高达 **`85.0%`** 的延迟 2-hit 事例为高能穿行 μ 子激发的 **`Q_max > 200 pC` 电磁/韧致辐射簇射**及 `-25 ns` 错束团 Pileup（FLUKA MC 独立重现 `12/13` 为 `Q > 200 pC`、`13/13 >= 183.9 pC`）；
   - 通过引入 **波形清洗（`width < 12 ns`）+ `|t0_down| < 2.5 ns` + 2-hit 电荷上限（`Q_2hit < 180 pC` / `150 pC`）或纯 `1-Hit Only` 模式**，`S1` 本底急剧塌缩 **3 个以上数量级**：
     * **纯 `1-Hit Only`（`T_1hit > 3.0 ns, w < 12 ns, |t0_down| < 2.5 ns`）**：**`B_tot = 5.23 +- 9.87`** vs **`S_rec = +68.65`**（`B / S_rec = 7.62%`），零双层簇射且对后向中子信号维持极高纯度；
     * **`2-Hit + 1-Hit` 联合超紧工作点（`Q_2hit < 180 pC, w < 12 ns, T_2hit > 3.5 ns, T_1hit > 3.5 ns`）**：**`B_tot = 14.63 +- 10.91`** vs **`S_rec = +76.09`**（`B / S_rec = 19.23%`），在不暴露 `SR-ZoneB` 情况下将 Zone-B 增量物理信号完整保留在高信噪比区间，圆满回答 **H4**。

---

## 下一步计划（Stage T5：策略优化 `S1/S2/S3`、系统误差协方差与开盲前评审）

| 任务序号 | 具体任务 | 所需输入 | 验收标准 |
| --- | --- | --- | --- |
| T5-1 | 在 [t4_background_budget_scan.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage215_timing_t4/t4_background_budget_scan.tsv) 基础上执行二维与连续变量精细优化：重点把 `1-hit` 与紧缩 `MIP 2-hit`（如 `Q_2hit < 160–180 pC`, `T_2hit >= 3.2–3.5 ns`, `w < 12 ns`, `|t0_down| < 2.5 ns`, 优化 `S2 Z_2hit >= 5.5–6.0`）扩展并对比多特征 `S3 (GBDT)` 的纯非盲 sideband+MC Asimov 显著度 | Stage T3 GENIE 6D 产额 + Stage T4 数据驱动 `B1..B5` 参数化 + 非盲 `CR-Geom` / `FLUKA` 特征分布 | 冻结唯一主用与备选工作点（在全系统误差下 `B_tot / S_rec <= 10–20%` 且 Asimov 显著度增益严格为正），并写入 `cuts_timing_*.yaml` |
| T5-2 | 针对 `2025/2026` 将 Zone A `raw40_ext`（`>32 ns`）限流为仅开启 **1-hit** 模式或屏蔽 `Q > 180 pC` 双层脉冲重测其 `B_tot` 增益；构建完整 `S0+ZoneB` 统计/系统误差协方差矩阵（涵盖通量、G4 物理模型、`C_t0`、时间尺度/分辨率与 `B1..B5` 外推） | Stage T3 系统误差表 + Stage T4 2022–2026 `DQ` 合约 + 2025–2026 限流策略扫描 | 证实 `2025–2026` `raw40` 1-hit 模式无 `1,132` 例高能双层簇射污染，生成全 Run 3 Asimov 误差预算总表 |
| T5-3 | 开展不含 `VetoNu*_charge` 的 ML 能量回归模型 `F7_pz0_raw_v1` 消融重训与验证，消除 `8.91% / 15.47%` Zone B 特征域外推偏差 | [ml/audited_features.py](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/ml/audited_features.py) 与 S1/Stage T5 GENIE 样本 | 证明重训后能量偏置与分辨率在 `Zone A` 与 `Zone B`（包含高 `y_inel`）间一致性优于 `2%` |
| T5-4 | 召开 **Pre-Unblinding Freeze Review**，核查全套 Stage T0–T5 证据与 `TimingBlindingGuard` 校验清单 | Stage T0–T5 workbook 报告、Git 冻结配置 tag | 所有独立闭合、稳定性与系统误差门控全部书面签认后，方可讨论首次解盲 `Timing_Allow_SR_ZoneB` |
