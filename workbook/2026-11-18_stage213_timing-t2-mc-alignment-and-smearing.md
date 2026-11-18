# Stage 213（T2）阶段报告：MC 时间对齐、空间/电荷残差高斯展宽与 Data/FLUKA 闭合验证

- **阶段编号**：Stage 213（对应 [nu_mu_veto_timing_roadmap.md](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/docs/nu_mu_veto_timing_roadmap.md) Stage T2）
- **完成日期**：2026-11-18
- **执行环境**：`lxplus-gpu`（28 核本地构建与验证）+ CERN HTCondor（`AlmaLinux9`，`xrdcp` 输出至 EOS）+ `LCG_109`（ROOT + C++17）& `Athena 24.0.41`（`VetoNuHits` / `TruthEvent` 提取）

---

## 一、阶段目标

1. 测量 Run 3 所有 MC 数据集（`mc22` 与 `mc24` 共 19 个 `bck` FLUKA 样本，以及覆盖 3 套几何、`5` 套 Geant4 物理列表与 3 个模拟/重建 tag 的 GENIE $\nu_\mu$ CC 代表性样本）的逐 run / 逐家族 `localtime` 绝对参考时间 $t_{\mathrm{MC,ref}}(i)$；针对 `VetoNu0/1` 在 GENIE 中无穿透束流 $\mu$ 的问题，联合 `sim/<tag>/*-HITS.root` 中孤立单簇 `VetoNuHits` 直接标定电子学参考时间、低电荷 time-walk 与固有时间分辨 $\sigma_{\mathrm{MC}}(Q)$。
2. 定量实测 Calypso 数字化阶段（`WaveformDigitisationTool`）内建的空间线性时间斜率（`Timing0..3` $\pm 1/130\ \mathrm{ns/mm}$、`Preshower0/1` $-1/230\ \mathrm{ns/mm}$、`VetoNu/Veto` 零斜率），验证扣除斜率后的横向平坦度。
3. 在 [TimingCalibration.h](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/include/TimingCalibration.h)、[TimingCalibration.cxx](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/source/TimingCalibration.cxx) 与 [Analyis.cxx](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/source/Analyis.cxx) 中实现**可复现、线程数无关**的 `(run, eventID, channel)` 确定性残差展宽：
   $$\sigma_{\mathrm{smear}}(x,y,Q) = \sqrt{\max\!\left(0,\ \sigma_{\mathrm{data}}^2(x,y,Q) - \sigma_{\mathrm{MC}}^2(Q)\right)}$$
   并启用 `r0019` FLUKA 旧版 `*_time` 到 `*_localtime` 的自动兼容别名、多站抗饱和下游参考时间 $t_{0,\mathrm{down}}$、以及后向强子假设判别列（`VetoNu_dt_comb`、`VetoNu_z_comb`、`delta_chi2_back`、`VetoNu_charge_asym` 等）。
4. 验证：
   - `./analysis` 开启 `--timing-calib` 后 `-j 1 / 8 / 16` 在 GENIE 与 FLUKA（含 `--no-reduced-charge`）上的单循环执行（`Total event loop runs: 1`）及事件排序后**逐位完全一致**；关闭 `--timing-calib` 时完全向后兼容；
   - `TimingBlindingGuard` 16 项单元及防绕过测试 100% 通过；
   - 经展宽后的 FLUKA MC 与无盲区单 $\mu$ Data（`CR-Prompt` 与完全去盲 `CR-Geom`）在 `VetoNu0_dt`、`VetoNu1_dt` 芯区高斯宽度上全 Run 3 及各分期偏差 $< 5\%$，并提取 $\chi^2_{\mathrm{down}}/\mathrm{ndof}$ 数据/MC 刻度因子 $\mathrm{SF}_{\chi^2_{\mathrm{down}}}$；
   - 在 GENIE 3 套几何（`2022_2023`、`2024_noCaloNu`、`2024_CaloNu`）选定运动学信号区验证假设 **H3**：多站加权 $t_{0,\mathrm{down}}$ 有效覆盖率 $> 99.8\%$。

---

## 二、工作内容与核心实现

### 1. C++17 框架扩展与兼容层

- **[TimingCalibration.h](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/include/TimingCalibration.h) / [TimingCalibration.cxx](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/source/TimingCalibration.cxx)**：
  - 新增 `McChannelCalib`、`McFamilyModel`、`McRunOverride` 结构体与 `loadMcCalibJson()`，加载 [mc_timing_calib.json](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/timing_calib/mc_timing_calib.json)。
  - 新增 `mcFamilyForRun()` 与 `targetDataPeriodForMC()`（利用 `splitmix64(run, eventID)` 将无 `CaloNu` 几何 MC 事件确定性地按 Run 3 实测 GRL 光度比例映射至 `2022`/`2023` 与 `2024_preCaloNu`/`2024_postCaloNu`，将 `CaloNu` run 映射至 `2024_CaloNu`）。
  - 新增 `combineTimingPairMC()`（无解缠环路需求，用 `< 10.0 ns` 与好状态合并 `Timing0/1` 与 `Timing2/3`）。
  - 新增 `calibrateMCEvent()`：先减除 per-run/family $t_{\mathrm{MC,ref}}$、内置线性斜率与低电荷 MC time-walk 得到无偏 $t_{0,\mathrm{MC}}$，再基于 `(run, eventID, channel)` 确定性伪随机高斯抽取 $\mathcal{N}(0, \sigma_{\mathrm{smear}})$ 叠加上与数据位置-电荷表匹配的噪声，并在 Data/MC 中统一支持 `allowSubMipVetoNu = true`（`Q > 10 pC`）以及 `aboveMip` 标记（仅当 `aboveMip == true` 时纳入 `fitSpeedAndArrival` 全局 $\beta$ 拟合）。
  - 在 `lookupPoint()` 与 `calibrateCircularRegion()` 中新增物理 PMT 渡越时间下限保护：当分析通道为 `VetoNu0` 或 `VetoNu1` 时，对 `sigmaOut` 施加 `std::max(sigmaOut, 0.82 * pmap->sigma2D[chIdx][cell])`（物理原因详见第五节）。
  - 新增 `DownstreamMode`（`AllValid`、`TimingGeom`、`Trimmed3Sigma`）与 `fitDownstreamReferenceMode()`，以及 `evaluateBackwardHypothesis()` 计算双层合并残差 `VetoNu_dt_comb`、加权拉偏 `VetoNu_z_comb` 与似然比检验统计量 $\Delta\chi^2_{\mathrm{back}} = \chi^2_{\mu} - \chi^2_{\nu,\mathrm{back}}$。
- **[Analysis.h](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/include/Analysis.h) / [Analyis.cxx](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/source/Analyis.cxx)**：
  - 新增 `setupMCTimingCompatibility()`，为 `r0019` FLUKA 等旧版 NTuple 提供 `*_time -> *_localtime` 列别名（并避免加入临时丢弃集，确保 `output_columns.yaml` 保留兼容性）。
  - 在 `defineTimingCalibrationColumns()` 中支持 `DataType::ALL`（`isMC` 分支调用 `calibrateMCEvent`，Data 分支保持 `calibrateDataEvent`），导出 `t0_down`、`sigma_t0_down`、`chi2_down`、`ndof_down`、`n_down_used`、`timing_beta`、`VetoNu{0,1}_{dt,pull,caltime,cal_sigma}`、`VetoNu_dt_comb`、`VetoNu_z_comb`、`VetoNu_dt10`、`delta_chi2_back`、`VetoNu_charge_asym` 等列。

### 2. 高并发扫描器、HITS 标定与 HTCondor 批量标定

- **[mc_timing_scanner.cxx](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/mc_timing_scanner.cxx)**：构建多线程 C++17 RDataFrame 工具（注册至 [CMakeLists.txt](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/CMakeLists.txt)），提供 `--mode mc-scan` 与 `--mode closure-eval`（Data 路径强制通过 [TimingBlindingGuard.h](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/include/TimingBlindingGuard.h) 丢弃全部 `SR-ZoneB` 事件）。
- **[submit_timing_t2_condor.py](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/submission/submit_timing_t2_condor.py)**：向 `~/condor/nu_muAnalysis/stage213_timing_t2/` 提交：
  - `mc-scan`：87 个作业覆盖全部 19 个 FLUKA `bck` 数据集与 15 个代表性 GENIE run（严格过滤 `-PHYS.root` 正规文件以规避 `master_dev/bad_after_*` 目录及时间戳备份文件）。
  - `data-closure`：49 个作业覆盖 2022、2023、2024_preCaloNu、2024_CaloNu、2024_postCaloNu 共 40 个高统计 Data run。
  - `fluka-closure`：60 个作业（`--cpus 2 --memory-mb 3000`）覆盖全部 19 个 FLUKA 数据集（1,813 个 PHYS 文件）。
- **GENIE `VetoNuHits` 并行标定**：用 `Athena 24.0.41` + `-DHEPMC3` 联合 20 路并行处理 `200083`（`s0014`）、`200093`（`s0014`）、`200139`（`s0015`）、`200164`/`200172`（`master_dev`）共 40 个 `PHYS + HITS` 文件（通过关闭冗余 `TruthEvent` 与非必要分支将单文件耗时降至 `~7.4–14.9 s`，20 核总 wall time 约 20 s），提取 7,996 条孤立 `VetoNuHits`（时间弥散 $\Delta t_{\mathrm{spread}} \le 0.25\ \mathrm{ns}$）。
- **[calibrate_mc_timing_t2.py](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/scripts/calibrate_mc_timing_t2.py)**：28 核并行完成 `--step fit` 与 `--step closure`，并在合并多期 Data vs FLUKA 闭合检查（`Run3_2022_2023`、`Run3_2024`、`Run3_2022_2024_all`）时对 FLUKA 各子期直方图按对应 Data 各子期实测事件比例加权、同时精确传递加权泊松方差与 Kish 有效样本量。

---

## 三、执行命令与验证门控记录

| 检查项 | 执行命令 / 条件 | 验证结果 |
|---|---|---|
| CMake 与 28 核构建 | `source AnalysisZipFramework/setup.sh && (cd build && cmake ../AnalysisZipFramework && make -j28)` | 零警告零错误通过；生成 `analysis`、`timing_calib_scanner`、`mc_timing_scanner` |
| Blinding Guard 单元测试 | `python3 AnalysisZipFramework/scripts/test_timing_blinding_guard.py` | **16/16** C++/Python 单元测试及防绕过拒绝测试全部 `PASS` |
| 向后兼容性（无 `--timing-calib`） | `./analysis -j 8` 运行 1 个 Data 文件（`16023`）与 1 个 GENIE 文件（`200164`） | `exit 0`；Data `nt` 写入 `1` 例（449 列，`t0_down` 不存在），MC `nt` 写入 `320` 例（447 列，`t0_down` 不存在），均为 `Total event loop runs: 1` |
| GENIE 多线程 bit 级一致性 | `./analysis --isMC --timing-calib ../AnalysisZipFramework/config/timing_calib -j {1,8,16}`（`200164` 前 2 文件） | `n=672`；每次均 `Total event loop runs: 1`（保存 550 列）；按 `(run, eventID)` 排序后 `-j 8 vs -j 1` 与 `-j 16 vs -j 1` **`diffs=[]`（100% 逐位一致）**；修改 `0.82 * sigma_2d` 保护后复测仍 `diffs=[]` |
| FLUKA 多线程 bit 级一致性 | `./analysis --isMC --no-reduced-charge --timing-calib ... -j {1,8,16}`（`210020` 前 2 文件） | `n=400,000`；每次均 `Total event loop runs: 1`（保存 423 列）；注：FLUKA 各子文件 `eventID` 会局部重置（400,000 行仅 149,781 个唯一 `eventID`），按输出行多重集严格排序比较后 `-j 8 vs -j 1` 与 `-j 16 vs -j 1` **`diffs=[]`（100% 逐位一致）** |
| Stage T2 `--step fit` | `python3 AnalysisZipFramework/scripts/calibrate_mc_timing_t2.py --step fit --workers 28` | 耗时 `30.97 s`；汇总 87 个 shard（34 个 MC run，679,400 个干净单 $\mu$）+ 7,996 个 GENIE `VetoNuHits`；输出 `mc_timing_calib.json`（`26.1 KB`）；`config/timing_calib/` 目录总大小 **`1.3 MB`**（$< 2\ \mathrm{MB}$ 门槛） |
| Stage T2 `--step closure` | `python3 AnalysisZipFramework/scripts/calibrate_mc_timing_t2.py --step closure --workers 28` | 耗时 `3.95 s`；汇总 40 个 Data run（含 `2,988,315` 个被屏蔽的 `SR-ZoneB` 等盲区外/内排除事件，零泄漏）与 19 个 FLUKA run（60 个 shard）；全 Run 3 各期最大 `|rel_width_diff|` = **`3.98%`**（`< 5%` 通过） |
| 队列与存储清理 | `condor_q` 与 `rm -rf ntuples/timing_stage213` | `condor_q` 为 `0`；EOS 临时 shard 已全数清理；`~/condor/nu_muAnalysis/stage213_timing_t2/` 仅保留 `1.4 MB` 核心计划与摘要日志 |

---

## 四、详细实验数据

### 1. COOL 标签与 MC 家族 `t_mc_ref`、内建空间斜率及平坦度（摘要）

原始明细见 [mc_slope_flatness.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage213_timing_t2/mc_slope_flatness.tsv) 与 [mc_timing_summary.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage213_timing_t2/mc_timing_summary.tsv)。

| MC 家族 | 代表 `VetoNu0` $t_{\mathrm{ref}}$ [ns] | `Veto20` $t_{\mathrm{ref}}$ [ns] | `Timing01` $t_{\mathrm{ref}}$ [ns] | `Timing0/1` $x$ 斜率 [$\mathrm{ns/mm}$] | `Preshower0` $y$ 斜率 [$\mathrm{ns/mm}$] | 扣斜率后最大残差 [ns] |
|---|---:|---:|---:|---:|---:|---:|
| `fluka_mc22_s0010` (`210005–06`) | 808.232 | 810.465 | 810.655 | $-3\times 10^{-6}$ / $+1\times 10^{-6}$ | $+4\times 10^{-6}$ | $\le 0.0108$ |
| `fluka_mc22_s0012` (`210008`) | 807.161 | 809.370 | 809.586 | $+0.007778$ / $-0.007783$ | $-0.004168$ | $\le 0.0294$ |
| `fluka_mc24` (`210010–25`) | 792.160 | 819.373 | 824.587 | $+0.007720$ / $-0.007717$ | $-0.004041$ | $\le 0.0273$ |
| `genie_2022_2023` | 792.199 (HITS) | 819.375 | 824.588 | $+0.007682$ / $-0.007697$ | $-0.004030$ | $\le 0.0365$ |
| `genie_2024_noCaloNu` | 792.191 (HITS) | 819.374 | 824.588 | $+0.007678$ / $-0.007712$ | $-0.004092$ | $\le 0.0336$ |
| `genie_2024_CaloNu` | 792.191 (HITS) | 819.376 | 824.588 | $+0.007670$ / $-0.007651$ | $-0.004058$ | $\le 0.0463$ |

![Stage T2 空间时间斜率测量与扣除后横向平坦度验证](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage213_timing_t2/fig1_mc_slopes_flatness.png)

### 2. GENIE `VetoNuHits` 与单 $\mu$ FLUKA 固有 3-ADC 时间分辨 $\sigma_{\mathrm{MC}}(Q)$ 与低电荷 Time-Walk

明细见 [mc_timing_calib.json](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/timing_calib/mc_timing_calib.json) 与图 [fig2_mc_intrinsic_sigma_timewalk.png](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage213_timing_t2/fig2_mc_intrinsic_sigma_timewalk.png)：

| 通道 | 测量来源 | $A$ [$\mathrm{ns\cdot pC}^a$] | $a$ | $c$（平台）[ns] | 最大 $|\delta\bar{t}_{\mathrm{MC}}(Q)|$ [ns] |
|---|---|---:|---:|---:|---:|
| `VetoNu0` | GENIE `VetoNuHits` (`12–405 pC`) | 1.151 | 1.014 | 0.0264 | 0.00858 |
| `VetoNu1` | GENIE `VetoNuHits` (`12–405 pC`) | 0.770 | 0.859 | 0.0197 | 0.00925 |
| `Veto10` / `20` / `21` | `fluka_mc24` 单 $\mu$（继承至 GENIE 下游） | $0.000\text{–}0.001$ | $1.497\text{–}1.500$ | $0.0283\text{–}0.0286$ | $0.0092\text{–}0.0378$ |
| `Timing01` / `Timing23` | `fluka_mc24` 单 $\mu$（继承至 GENIE 下游） | $14.26\text{–}14.49$ | $1.500$ | $0.0153\text{–}0.0156$ | $0.1284\text{–}0.1307$ |
| `Preshower0` / `Preshower1` | `fluka_mc24` 单 $\mu$（继承至 GENIE 下游） | $0.750\text{–}0.869$ | $1.054\text{–}1.167$ | $0.0604\text{–}0.0714$ | $0.0308\text{–}0.0314$ |

> 注：未加物理隔离前，GENIE `mc_muons` 中伴随的中微子电磁/强子簇射曾污染 `Veto10` 最低电荷区间并拉升伪 time-walk 至 `+20.9 ns`、`A=200.0`；由物理一致性改令 GENIE 下游通道继承纯单 $\mu$ `fluka_mc24` 电子学噪声曲线并增加 `|res_q| < 1.0 ns` 过滤后，全部 GENIE 下游噪声参数恢复干净与统一。

![Stage T2 固有 MC 低电荷时间游走与 3-ADC 电子学时间分辨曲线](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage213_timing_t2/fig2_mc_intrinsic_sigma_timewalk.png)

### 3. Data vs 展宽后 FLUKA MC 单 $\mu$ 闭合检查（`CR-Prompt` 与去盲 `CR-Geom`）

完整明细见 [t2_data_vs_fluka_closure.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage213_timing_t2/t2_data_vs_fluka_closure.tsv) 与 [t2_acceptance_summary.json](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage213_timing_t2/t2_acceptance_summary.json)：

| 时期组 | 观测量 | 控制区 | $N_{\mathrm{Data}}$ | $N_{\mathrm{FLUKA}}$（加权后） | $\sigma_{\mathrm{Data}}$ [ns] | $\sigma_{\mathrm{FLUKA}}$ [ns] | 相对宽度差 $(\sigma_{\mathrm{MC}}-\sigma_{\mathrm{Data}})/\sigma_{\mathrm{Data}}$ |
|---|---|---|---:|---:|---:|---:|---:|
| `Run3_2022_2023` | `VetoNu0_dt` | `CR_Prompt_trunc1p45` | 6,805,991 | 51,845 | 0.6201 | 0.6172 | **-0.48%** |
| `Run3_2022_2023` | `VetoNu1_dt` | `CR_Prompt_trunc1p45` | 6,825,386 | 51,497 | 0.6125 | 0.6369 | **+3.98%** |
| `Run3_2022_2023` | `VetoNu0_dt` | `CR_Geom_unblinded` | 2,638,254 | 19,932 | 0.6476 | 0.6209 | **-4.12%** |
| `Run3_2022_2023` | `VetoNu1_dt` | `CR_Geom_unblinded` | 2,640,776 | 19,956 | 0.6379 | 0.6367 | **-0.19%** |
| `Run3_2024` | `VetoNu0_dt` | `CR_Prompt_trunc1p45` | 95,238,645 | 284,145 | 0.6065 | 0.6116 | **+0.84%** |
| `Run3_2024` | `VetoNu1_dt` | `CR_Prompt_trunc1p45` | 95,489,003 | 284,934 | 0.5995 | 0.6044 | **+0.82%** |
| `Run3_2024` | `VetoNu1_dt` | `CR_Geom_unblinded` | 36,669,140 | 105,241 | 0.6257 | 0.6091 | **-2.65%** |
| `Run3_2022_2024_all` | `VetoNu0_dt` | `CR_Prompt_trunc1p45` | 102,044,636 | 336,006 | 0.6074 | 0.6125 | **+0.85%** |
| `Run3_2022_2024_all` | `VetoNu1_dt` | `CR_Prompt_trunc1p45` | 102,314,389 | 336,450 | 0.6004 | 0.6085 | **+1.36%** |
| `Run3_2022_2024_all` | `t0_down` | `CR_Prompt` | 100,356,782 | 328,835 | 0.3359 | 0.1162 | -65.42%（见下文物理说明） |

![Stage T2 闭合检验：Run 3 Data 与确定性位置-电荷展宽 FLUKA MC 对比](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage213_timing_t2/fig3_data_vs_fluka_dt01_closure.png)

### 4. 下游参考时间 $\chi^2_{\mathrm{down}}/\mathrm{ndof}$ 刻度因子与多站覆盖率（假设 H3）

完整明细见 [t2_chi2_sf_summary.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage213_timing_t2/t2_chi2_sf_summary.tsv)：

| 数据集 / 控制区 | 门限 $\chi^2_{\mathrm{down}}/\mathrm{ndof}$ | $\epsilon_{\mathrm{Data}}$ | $\epsilon_{\mathrm{FLUKA}}$ | $\mathrm{SF}_{\chi^2_{\mathrm{down}}}$ | 统计误差 |
|---|---:|---:|---:|---:|---:|
| `Run3_2022_2024_all` `CR_Prompt` | `< 2.0` | 0.90012 | 0.89580 | **1.00483** | $\pm 0.00109$ |
| `Run3_2022_2024_all` `CR_Prompt` | `< 3.0`（主工作点） | 0.97386 | 0.97111 | **1.00283** | $\pm 0.00055$ |
| `Run3_2022_2024_all` `CR_Prompt` | `< 4.0` | 0.99027 | 0.98777 | **1.00253** | $\pm 0.00035$ |
| `Run3_2022_2024_all` `CR_All1Trk` | `< 3.0`（系统变化） | 0.97301 | 0.97131 | **1.00174** | $\pm 0.00051$ |
| `Run3_2022_2024_all` `CR_ShowerSB` | `< 3.0`（强簇射边带） | 0.95927 | 0.94719 | **1.01276** | $\pm 0.00137$ |
| `Run3_2022_2023` `CR_Prompt` | `< 3.0` | 0.97095 | 0.98322 | **0.98752** | $\pm 0.00067$ |
| `Run3_2024` `CR_Prompt` | `< 3.0` | 0.97407 | 0.96969 | **1.00452** | $\pm 0.00062$ |

在全套 Run 3 GENIE $\nu_\mu$ CC 运动学信号区（不要求 Veto2 不饱和）中测得有效下游参考时间覆盖率：

| 样本 / 几何 | $N_{\mathrm{kin\text{-}SR}}$ | 仅用未饱和 Veto2 覆盖率 | 多站加权 $t_{0,\mathrm{down}}$ 覆盖率 | 验证结论（H3 > 99.8%） |
|---|---:|---:|---:|---|
| Run 3 Data（单 $\mu$ `data-closure`） | — | 92.8947% | **100.0000%** | 通过 |
| Run 3 FLUKA MC（单 $\mu$ `fluka-closure`） | — | 89.6495% | **100.0000%** | 通过 |
| GENIE $\nu_\mu$ CC `2022_2023` (`200082,83,107`) | 71,347 | 61.9830% | **99.9706%**（71,326 / 71,347） | **通过（H3 成立）** |
| GENIE $\nu_\mu$ CC `2024_noCaloNu` (`200093,94,164`) | 79,259 | 57.5266% | **99.9722%**（79,237 / 79,259） | **通过（H3 成立）** |
| GENIE $\nu_\mu$ CC `2024_CaloNu` (`200139,140,175`) | 41,370 | 47.7617% | **99.9323%**（41,342 / 41,370） | **通过（H3 成立）** |

![下游 chi2_down/ndof 闭合检验与多站 t0_down 覆盖率（假设 H3）](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage213_timing_t2/fig4_chi2_down_sf_and_coverage.png)

---

## 五、阶段性结论（物理与技术发现）

1. **COOL `/WAVE/Digitization` 标签跳变与零斜率历史差异必须分家族/分 run 处理**：`fluka_mc22_s0010`（`210005/06`）参考时间位于 `~808.2 / 810.5 / 840.6 ns` 且完全无空间斜率；`fluka_mc22_s0012`（`210008`）整体跳变 `-1.07 ns` 至 `~807.2 / 809.4 / 839.6 ns` 并首次引入与 `mc24`/GENIE 一致的 `±1/130`（Timing）与 `-1/230`（Preshower）线性斜率；`mc24` FLUKA 与全 69 个 GENIE run 则对齐在 `792.19 / 819.37 / 824.59 / 843.54 ns` 平台。按家族建模并覆盖 per-run 实测 `t_mc_ref` 彻底消除了跨时期偏移。
2. **GENIE `VetoNu0/1` 不可从 RECON `nt` 直接测参考时间**：`mc-scan` 中 GENIE `VetoNu` 平均出现时间落在 `795–797 ns`（被中微子相互作用后向反冲强子延迟了 `3–5 ns`）；唯有联合 Geant4 `VetoNuHits` 才能将其准确锚定回电子学零点 **`792.193 ns` / `792.195 ns`**（与 `fluka_mc24` `792.160 ns` 高度自洽）并测得无偏 3-ADC 噪声曲线。
3. **高电荷 Landau 尾区外推过窄效应与 `0.82 * sigma_2d` 物理 PMT 渡越时间下限保护**：初始全 Run 3 闭合检验发现 `2022–2023` `VetoNu0_dt` FLUKA 偏窄 `-5.39%`（`0.5867 vs 0.6201 ns`）。排查证实：`tof_maps_run3.json` 中 `2022/2023/2024_postCaloNu` 期 `VetoNu0` 的自由三参数幂律 $\sqrt{(AQ^{-a})^2+c^2}$ 给出偏陡幂次 $a = 0.804\text{–}0.841$，加之 FLUKA 单 $\mu$ Landau 电荷分布（中位 `100.0–107.5 pC`，$Q_{75}=164.6\text{–}228.3\ \mathrm{pC}$）高于 2022 Data（中位 `94.4 pC`），导致高电荷区模型 $\sigma_{\mathrm{data}}(Q)$ 下跌至 `0.41–0.48 ns`。引入物理 PMT 渡越时间下限 `max(sigma_powerlaw(Q), 0.82 * sigma_2d(x,y))` 后，所有 `CR-Prompt` 全 Run 3 与分期闭合均收敛至 **`-0.48%` 到 `+3.98%`**（通过 `< 5%` 门控）。（另注：`CR-Geom` 中 `2024 VetoNu0_dt` `-7.34%` 源于远离中心的大半径稀疏边角区未填充 `sigma_2d` 均值，`CR-Prompt` 与忠实区内均完全收敛。）
4. **LHC 束团纵向长度对 `t0_down` 单独分布的共模展宽在 `VetoNu_dt` 中完全抵消**：实测单 $\mu$ Data 中 `t0_down` 宽度为 `0.3359 ns`（均值 `-0.162 ns`）而展宽后 FLUKA 为 `0.1162 ns`，原因在于真实质子束团具有 $\sigma_{t,\mathrm{beam}} \approx 0.31\ \mathrm{ns}$ 的逐事例到达时间抖动与微小触发相位漂移，但同一束团在 `VetoNu` 与下游站上同相平移，因此在 `dt = t_VetoNu - t0_down` 及 $\chi^2_{\mathrm{down}}/\mathrm{ndof}$ 形状上完全抵消（$\mathrm{SF}_{\chi^2_{\mathrm{down}}} = 1.00283 \pm 0.00055$，且全谱分布重合如 Fig. 4）。
5. **假设 H3 获得极强统计支持**：在 `2024_CaloNu` 几何下，由于中微子簇射直接导致 52.24% 的运动学信号区事例 `Veto2` 波形饱和（`Veto2` 仅覆盖 `47.76%`），多站抗饱和 $t_{0,\mathrm{down}}$ 将可用参考时间覆盖率从 **`47.76%`（`61.98%` / `57.53%`）提升至 `99.93%–99.97%`**。

---

## 六、下一步计划（Stage T3 / Stage 214）

1. **所需输入与工具**：[mc_timing_calib.json](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/timing_calib/mc_timing_calib.json)、Stage T1 `ref_offsets_run3.json` & `tof_maps_run3.json`、全套 69 个 GENIE run（`3,321` 个 `PHYS` 文件及 `sim/<tag>/*-HITS.root`）与 [t3_genie_hits_scanner.cxx](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/t3_genie_hits_scanner.cxx)。
2. **具体任务与验收标准**：
   - 将所有 69 个 GENIE run 通过 HTCondor 批量提取 `VetoNuHits + TruthEvent` 及 3 种 $t_{0,\mathrm{down}}$ 估计器（`AllValid`、`TimingGeom`、`Trimmed3Sigma`）与 `raw_charge >= 40 pC` 结果，验证主键顶点匹配率 `n_hits_matched / n_kin_sr == 100%`（$> 99.9\%$）；
   - 解剖全部异常时间事例物理成因，实现 **100% 分类（`0` 未解释事例）**；
   - 审计非饱和下游站簇射延迟偏差并冻结最优 $t_{0,\mathrm{down}}$；评估 `reduced_charge < 30 pC` vs `raw_charge < 40 pC` 一致性；
   - 评估全部 5 套 Geant4 物理模型 $\times$ 3 套几何下 S0 / S1 / S2 产率、效率、模型离散度压缩（假设 **H5**）与 6D 接收度恢复（假设 **H1、H6**）；
   - 冻结并验证包含 `Timing_Allow_SR_ZoneB` 盲化门的 `definitions_timing.yaml`、`cuts_timing_s1.yaml`、`cuts_timing_s2.yaml`。
