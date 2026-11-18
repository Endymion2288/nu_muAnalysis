# 阶段 214（Stage T3）：后向强子回溅模拟验证、下游拟合冻结与五种 Geant4 物理模型评估

- **日期**：2026-11-18
- **状态**：已完成（Stage T3 / 阶段 214，盲化锁保持激活）
- **前置阶段**：Stage T0–T2（阶段 212–213，最近一次提交 `536104a`）

## 阶段目标

完成 [nu_mu_veto_timing_roadmap.md](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/docs/nu_mu_veto_timing_roadmap.md) 规划中的 **Stage T3**：
1. 规模化提取全 Run 3 周期共计 `69` 个 GENIE MC run（覆盖 `3` 种几何与 `5` 种 Geant4 物理模型：`FTFP_BERT`、`QGSP_BERT`、`QBBC`、`FTFP_BERT_ATL`、`FTFP_INCLXX`）的 PHYS 与对应 `-HITS.pool.root` 真值信息；
2. 对下游时间参考 `t0_down` 开展电磁簇射离群点审计，冻结抗偏置拟合模式与脉冲宽度上限；
3. 揭示 Zone B（`VetoNu` 高电荷却仍属于真 $\nu_\mu$ CC 信号）的后向强子真值成分，定量验证 S1 / S2 对 Zone B 的挽救效率及失效来源；
4. 量化无 `reduced_charge` 时的 `raw_charge < 40` 方案差异、排查 `2024_CaloNu` 内部 run 间效率偏移根因、检验假说 **H1 / H3 / H4 / H5 / H6**、评估 `335.92 fb^-1` 产额提升与 6D 接收度恢复、测量时间刻度/涂抹系统误差，以及审计现有 ML 能量回归特征 `F7_pz0_raw_v1` 的输入域偏移；
5. 将冻结后的 `Trimmed3Sigma` 逻辑、`Timing_Allow_SR_ZoneB` 盲化锁与 S1/S2 配置正式集成到 `AnalysisZipFramework`，并用多线程 determinism、单位盲化测试与未开盲 Data 验证闭环。

---

## 工作内容

1. **T3 GENIE PHYS + HITS 扫描与 HTCondor 批处理提交**：
   - 开发/更新 [t3_genie_hits_scanner.cxx](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/t3_genie_hits_scanner.cxx) 与 [submit_timing_t3_condor.py](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/submission/submit_timing_t3_condor.py)，打包最小 Scint/DetDescr 运行库及 Stage T2 `timing_calib`（`1.3 MB`），在 HTCondor 上提交 `191` 个作业覆盖全部 `69` 个 GENIE MC run（`3,297` 个 PHYS 文件，并在 EOS 上核查全部 run 编号连贯且无断点）。
2. **28 核并行 Stage T3 物理分析流水线**：
   - 编写并运行 [analyze_t3_backward_hadrons.py](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/scripts/analyze_t3_backward_hadrons.py)（`--workers 28`），系统性输出全部 TSV 数据表、`t3_summary.json` 及 6 幅物理诊断图至 [workbook/stage214_timing_t3/](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage214_timing_t3/)。
3. **框架集成、盲化锁固化与回归验证**：
   - 更新 [Analyis.cxx](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/source/Analyis.cxx)，将下游拟合从 `AllValid` 切换为 `TimingCalib::DownstreamMode::Trimmed3Sigma`，并在 C++ 中注册 `Timing_Allow_SR_ZoneB`（`DATA = false`，`ASIMOV = true`）与 `VetoNu{0,1}_zone_a`（严格按 `hasRedQ` 逻辑优先使用 `reduced_charge < 30`、无该分支时回退 `raw_charge < 40`）。
   - 新建时间定义与 S1/S2 选择配置文件：[definitions_timing.yaml](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/definitions_timing.yaml)、[cuts_timing_s1.yaml](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/cuts_timing_s1.yaml)、[cuts_timing_s2.yaml](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/cuts_timing_s2.yaml)。
   - 在与 Stage T2 完全相同的 2024 Data 与 FLUKA `mc24` 样本上对比 `mc_timing_scanner`（`AllValid`）与 `build/analysis`（`Trimmed3Sigma`），确认 `CR-Prompt` 闭合度维持在 `< 5%` 以内。
4. **临时空间清理**：
   - 验证 `condor_q` 无活动作业后，清理全部 `191` 个 EOS 临时分片及本地 `build_t3`、`/tmp/stage214_val`，在 `~/condor/nu_muAnalysis/stage214_timing_t3/audit_summary.json` 保留紧凑 Condor 审计记录。

---

## 详细数据

### 1. 执行命令、规模、耗时与资源消耗

| 执行步骤 | 实际命令 / 集群标识 | 输入规模 | 实测耗时 / 资源使用 |
| --- | --- | --- | --- |
| Condor 全量提取 | `python3 AnalysisZipFramework/submission/submit_timing_t3_condor.py`（Cluster `9759403`） | `69` runs、`3,297` PHYS 文件、`191` jobs | `191/191` `Exit status = 0`；RSS 中位 `522.12 MB`、`p95 665.30 MB`、最大 `697.95 MB`；单作业 Wall 中位 `571.30 s`、`p95 964.44 s`、最大 `1163.02 s`；总计 `30.647 CPU h` |
| 28 核并行物理分析 | `python3 AnalysisZipFramework/scripts/analyze_t3_backward_hadrons.py --workers 28` | `32,656,934` gen / `3,272,104` fid / `991,211` SR | 总耗时 `37.19 s`（并行加载 `69` runs 仅 `8.27 s`） |
| 校准包体积复查 | `du -sh AnalysisZipFramework/config/timing_calib/` | JSON 校准包 | `1.3M`（`< 2 MB`） |
| 盲化守卫单元测试 | `python3 AnalysisZipFramework/scripts/test_timing_blinding_guard.py` | `16` 个 C++/Python 用例 | `16/16 PASSED` |
| Data 16023 `p0015` 盲化锁 | `./build/analysis`（Run `16023` `2024_unfilt/p0015` 原生 `reduced_charge`） | `106,725` 事件 | `S0=1, S1=1, S2=1`（`Total event loop runs: 1`），`SR-ZoneB` 泄漏 = `0` |
| Data 16023 `r0022` 盲化锁 | `./build/analysis ... --no-reduced-charge`（Run `16023` `2024_back/r0022`） | `244,234` 事件 | `S0=0, S1=0, S2=0`，`SR-ZoneB` 泄漏 = `0` |
| GENIE `200164` 多线程一致性 | `./build/analysis`（`200164` `00000-00009`，`-j 1 / 8 / 16`） | `372` SR 候选（`S0=320, S1=357, S2=355, S1 raw=321`） | `-j 1/8/16` 下 `nt`（`568` 列）与 `eventID_pass`（`21` 列）`diffs = []` |

**HITS 数据完整性门控**：全样本 `991,211` 个运动学 SR 事件中，`hits_matched = 991,139 / 991,211 (99.9927%)`，`hits_vtx_match = 991,139 / 991,211 (99.9927%)`；仅 run `200092` 缺失 `68` 例、run `200098` 缺失 `4` 例，其余 `67` 个 run 为 `100%` 匹配。

---

### 2. Task 2：下游参考时间 `t0_down` 离群点审计、模式冻结与 Stage T2 闭合校验

1. **下游各层前冲簇射时间偏置（`AllValid` 模式）**：
   - 未饱和 `Veto10` 总体残差 `mean = +0.541 ns`、`p95 = +2.881 ns`（在量能器能量 `100–300 GeV` 区间 `p95 = +2.906 ns`）；`Veto20/21` 分别为 `+0.232 / +0.204 ns`；`Timing01/23` 的 `RMS` 高达 `5.82 / 4.70 ns`。
   - `Preshower0/1` 最稳定，良好比例为 `99.59% / 99.36%`，平均偏置仅 `+0.062 / +0.060 ns`（`p95 = +0.360 ns`）。详见 [t3_downstream_channel_bias.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage214_timing_t3/t3_downstream_channel_bias.tsv) 与 [fig3_downstream_shower_bias.png](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage214_timing_t3/fig3_downstream_shower_bias.png)。
2. **`AllValid` 与冻结模式 `Trimmed3Sigma` 对比**（详见 [t3_downstream_modes.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage214_timing_t3/t3_downstream_modes.tsv) 与 [t3_threshold_scan.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage214_timing_t3/t3_threshold_scan.tsv)）：
   - 下游覆盖 `cov >= 2`：`99.918%`；
   - `chi2_down / ndof < 3` 比例：`73.447%`（`AllValid`）提升至 **`90.732%`**（`Trimmed3Sigma`）；
   - `chi2_down / ndof < 5` 比例：`80.533%`（`AllValid`）提升至 **`97.887%`**（`Trimmed3Sigma`）；
   - 无条件 `t0_down` 标准差：由 `1.341 ns` 收敛至 **`0.345 ns`**；`|t0_down| > 1.0 ns` 尾部事件比例由 `7.295%` 降至 **`0.746%`**；
   - `VetoNu` 时间残差均值偏置：由 `-0.278 ns` 改善至 **`-0.063 ns`**。
3. **波形宽度上限与 $\chi^2$ 阈值冻结理由**：
   - FLUKA `210020` 中干净穿行 μ 子 `VetoNu0_width` 的中位数为 `p50 = 5.06 ns`、`p99.9 = 5.46 ns`；而 GENIE SR 中多条核反冲次级粒子叠加会把真实物理脉冲展宽至 `~15–18 ns`，波形拟合碰顶失败则钉死在 `20.0 ns`。
   - 综合扫描 `(chi2/ndof in {3.0, 5.0}) x (width_max in {12, 16, 19.5, 999} ns)` 后，冻结工程选择为 **`DownstreamMode::Trimmed3Sigma`** + **`chi2_down / ndof < 5.0`** + **`1.5 < width < 19.5 ns`**。
4. **`Trimmed3Sigma` 对 Stage T2 `CR-Prompt` 闭合度影响复核**（与 Stage 213 相同的 2024 Data `6` runs `15816, 15818, 15820, 17147, 17199, 17230`（共 `5,247,516` 事件）与 142 个 FLUKA `mc24` 文件 `210010..210025`（共 `27,366,194` 事件），采用完全一致的 `_fit_trunc_gauss_hist(-1.45, +1.45)`）：
   - `AllValid`（`./build/mc_timing_scanner --threads 28`：Data `9.94 s`，FLUKA `28.48 s`）：
     * `VetoNu0_dt`：Data `N=3,671,066`、`mu=-0.0021`、`sig=0.6060 +- 0.0003 ns` vs 未加权 FLUKA `N=28,373`、`mu=-0.0351`、`sig=0.6273 +- 0.0035 ns`（`+3.51%`）；按周期加权 FLUKA `0.5970 +- 0.0036 ns`（`-1.49%`）。
     * `VetoNu1_dt`：Data `N=3,680,219`、`mu=-0.0021`、`sig=0.5985 +- 0.0003 ns` vs 未加权 FLUKA `N=28,093`、`mu=-0.0365`、`sig=0.6160 +- 0.0034 ns`（`+2.92%`）；按周期加权 FLUKA `0.6078 +- 0.0039 ns`（`+1.54%`）。
   - `Trimmed3Sigma`（`./build/analysis`，Data `N=4,095,724`，FLUKA `N=30,574`）：
     * `VetoNu0_dt`：Data `N=4,080,298`、`mu=+0.0023`、`sig=0.6072 +- 0.0003 ns`（原始 std `0.5811 ns`）vs 未加权 FLUKA `N=30,462`、`mu=-0.0291`、`sig=0.6281 +- 0.0033 ns`（`+3.44%`，原始 std `0.5949 ns` / `+2.37%`）。
     * `VetoNu1_dt`：Data `N=4,080,866`、`mu=+0.0016`、`sig=0.6003 +- 0.0003 ns`（原始 std `0.5764 ns`）vs 未加权 FLUKA `N=30,464`、`mu=-0.0281`、`sig=0.6142 +- 0.0032 ns`（`+2.32%`，原始 std `0.5868 ns` / `+1.80%`）。
     * `chi2_down / ndof < 5.0` 保留率：Data `4,094,263 / 4,095,724 = 99.964%`，FLUKA `30,549 / 30,574 = 99.918%`，对应标度因子 `SF(chi2 < 5) = 1.00046`。
   - **结论**：由 `AllValid` 切换至 `Trimmed3Sigma` 对 `CR-Prompt` 核高斯宽度影响仅 `< 0.3%`，Data-vs-FLUKA 闭合偏差稳健保持在 `< 5%` 目标以内。

---

### 3. Task 1：Zone B 后向强子真值解剖与 S1 / S2 挽救闭环

1. **名义 `30 ab^-1`（`FTFP_BERT`）及全 `69` run 总览**：
   - 名义 `30 ab^-1` 共 `123,928` 个 SR 事件：`S0 (Zone A) = 108,933`，**`Zone B = 14,995 (12.100%)`**（拓扑分布：`both = 6,582`、`vn1_only = 4,849`、`vn0_only = 3,564`；顶点材料：`FASERnu_box = 14,979`、`Lead_block = 16`）。
   - 引入冻结后的 `Trimmed3Sigma` 与定时选择：**`S1 = 119,586`**（相对 `S0` 净增 `+10,653`，Zone B 挽救率 **`71.044%`**），**`S2 = 119,673`**（净增 `+10,740`，Zone B 挽救率 **`71.624%`**）。
   - 全 `69` 个 GENIE run 合计 `991,211` SR 事件中，`Zone B = 125,207`，`S1 = 954,361`（Zone B 挽救率 **`70.569%`**），`S2 = 955,240`（Zone B 挽救率 **`71.271%`**）。
2. **`VetoNuHits` Zone B 贡献物种分解（名义 `30 ab^-1`）**（详见 [t3_truth_species.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage214_timing_t3/t3_truth_species.tsv) 与 [fig1_species_topology.png](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage214_timing_t3/fig1_species_topology.png)）：
   - `n_recoil_nuc`：**`46.65%`**（低能中子非弹/弹性散射次级核反冲，最主要来源）
   - `unm_high_dEdx`：**`23.43%`**
   - `gamma_to_e`：**`11.73%`**
   - `proton`：**`7.17%`**
   - `unm_low_dEdx`：`5.30%`；`other`：`4.00%`；`pi+-`：`1.08%`；`e_cascade`：`0.61%`；`K+-`：`0.03%`。
3. **S1 失效互斥分类完整性核查**：
   - 名义 `30 ab^-1` 中未被 S1 挽救的 `4,342` 个 Zone B 事件可被 **100% 完全互斥拆解**：`downstream_lt2 = 8`、`chi2 >= 5 = 195`、`sat = 621`、`cbfail = 53`、`width >= 19.5 = 626`、`late (>= 22 ns) = 2,157`、`prompt (dt <= +1.5 ns) = 682`，**未解释失效 = `0` 例**（全部 `69` 个 run 同为 `0` 例）。

---

### 4. Task 3：`raw_charge < 40` 与 `reduced_charge < 30` 对比

当真实 Data 或无 `reduced_charge` 分支分流使用 `raw_charge < 40` 时（详见 [t3_raw40_vs_red30.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage214_timing_t3/t3_raw40_vs_red30.tsv) 与 [fig4_raw40_vs_red30.png](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage214_timing_t3/fig4_raw40_vs_red30.png)）：
- `S0 raw40` 相对 `S0 red30` 偏低 **`-8.18%`**（`2022–23` 与 `2024_noCaloNu`）。
- 仅使用 `+1.5 < dt < 22 ns` 窗口的 `S1 raw40 (<22 ns)` 仍偏低 **`-7.6%`**。
- 开启 S1 对无还原波形但电荷受限于饱和/溢出窗口的 `> 32 ns` 恢复分支 `S1 raw40_ext (+>32 ns)` 后，与 `red30` 的相对偏差大幅收窄至 **`-1.58%`**（`2022–23`）、**`-1.67%`**（`2024_noCaloNu`）与 **`-1.11%`**（`2024_CaloNu`），对应 `Run3_Combined` 条件 `VetoNu` 存活率达 `94.98%`（vs `red30` 的 `96.51%`）。

---

### 5. Task 4：`2024_CaloNu` 溯源、H5 五模型包络、Run 3 产额、6D 接收度与系统误差

1. **`2024_CaloNu` 内部 run 间效率偏移根因核实**：
   - 直接核查 EOS `-HITS.sim.log` 元数据确认：`200139..146`（tag `s0015`，如 `200139`）使用 `caloNu_v3/epos-pi.EVNT.pool.root` 且几何配置为 `EnableCaloNu = True, EnableEmulsion = False`（`n_fid = 87,910, eff_sr = 27.736%`）；而 `200172..183`（tag `master_dev`，如 `200172`）使用 `caloNu/epos-pi.EVNT.pool.root` 且配置为 `EnableEmulsion = True`（无 `CaloNu`，`n_fid = 97,236–97,238, eff_sr = 28.654%–28.990%`）。详见 [t3_run_inventory.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage214_timing_t3/t3_run_inventory.tsv)。
   - 因此评估 H5 Geant4 物理模型散度时，必须将 `2024_CaloNu` 区分同几何同重建链的 **`master_dev` 4 模型** 子集，防止几何/乳胶配置差异混入强子模型不确定度。
2. **H5 五种 Geant4 强子模型相对包络收敛**（详见 [t3_5models_acceptance.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage214_timing_t3/t3_5models_acceptance.tsv)、[t3_h5_model_spread.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage214_timing_t3/t3_h5_model_spread.tsv) 与 [fig5_g4_models_h5.png](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage214_timing_t3/fig5_g4_models_h5.png)）：

| 几何 / 组合样本 | `S0` 总接收度包络（条件 `VetoNu` 包络） | `S1` 总接收度包络（条件 `VetoNu` 包络） | `S2` 总接收度包络（条件 `VetoNu` 包络） |
| --- | --- | --- | --- |
| `2022_2023`（5 模型） | `2.539%` (`2.399%`) | **`1.153%`** (`1.032%`) | **`1.083%`** (`0.948%`) |
| `2024_noCaloNu`（5 模型） | `2.156%` (`2.363%`) | **`0.820%`** (`0.955%`) | **`0.742%`** (`0.879%`) |
| `2024_CaloNu_master_dev`（4 模型） | `1.540%` (`1.050%`) | **`0.414%`** (`0.754%`) | **`0.502%`** (`0.706%`) |
| `2024_CaloNu`（5 模型，仅条件 `VetoNu`） | `—` (`4.122%`) | `—` (`1.612%`) | `—` (`1.401%`) |
| `Run3_Combined_335.92fb` | `2.117%` (`2.114%`) | **`0.839%`** (`0.938%`) | **`0.816%`** (`0.870%`) |

3. **Run 3 全周期积分亮度加权预期信号产额（`335.92 fb^-1`，名义 `FTFP_BERT`）**（详见 [t3_run3_yields.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage214_timing_t3/t3_run3_yields.tsv)）：

| 周期 | 积分亮度 (`fb^-1`) | `S0` 预期产额 | `S1` 预期产额（净增） | `S2` 预期产额（净增） |
| --- | --- | --- | --- | --- |
| `2022_2023` | `66.045` | `292.94` | `322.35` (`+29.41`) | `322.59` (`+29.65`) |
| `2024_noCaloNu + 25 + 26` | `199.841` | `856.70` | `943.83` (`+87.13`) | `944.21` (`+87.51`) |
| *(其中 `2024_noCaloNu`)* | *(`50.097`)* | *(`214.76`)* | *(`236.60`)* | *(`236.70`)* |
| `2024_CaloNu` | `70.033` | `152.03` | `164.92` (`+12.89`) | `165.15` (`+13.11`) |
| **Run 3 合计** | **`335.92`** | **`1301.68`** | **`1431.11` (`+129.43`, `+9.94%`)** | **`1431.95` (`+130.27`, `+10.01%`)** |

4. **6D 微分接收度恢复（H1 / H6）**（详见 [t3_6d_acceptance.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage214_timing_t3/t3_6d_acceptance.tsv)、[t3_flux_variations.tsv](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage214_timing_t3/t3_flux_variations.tsv)、[fig2_kinematics_delay_vs_z.png](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage214_timing_t3/fig2_kinematics_delay_vs_z.png) 与 [fig6_6d_acceptance_recovery.png](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/workbook/stage214_timing_t3/fig6_6d_acceptance_recovery.png)）：
   - **上游靶区恢复（H1）**：最靠 `VetoNu` 的 `z_vtx in [-3008.6, -2967.1) mm` 区间接收度由 `4.38%` 跃升至 **`24.74%`（`+464.5%`）**；
   - **高能尾部恢复（H6）**：`E_nu in [3600, 4000) GeV` 接收度由 `26.46%` 提高至 **`33.42%`（`+26.3%`）**；
   - **正反中微子电荷态（`q = -1` / `+1`）**：`q = -1` 由 `24.09% -> 26.54% (+10.2%)`；`q = +1` 由 `34.24% -> 37.29% (+8.9%)`。
5. **时间刻度与分辨率系统误差（名义 `30 ab^-1`）**：
   - 总体时间刻度偏移 `+-0.15 ns`：`S1` 为 `+0.053% / -0.076%`，`S2` 为 `+0.035% / -0.044%`；
   - 总体时间涂抹不确定度 `+-15%`：`S1` 为 `-0.027% / +0.023%`，`S2` 为 `-0.019% / +0.010%`。
   - Timing-window 与 smear 系统误差均稳定低于 `0.08%`，远小于模型包络与中微子通量误差。
6. **ML 能量回归特征 `F7_pz0_raw_v1` 输入域偏移审计**：
   - 核查 [audited_features.json](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/ml/configs/audited_features.json) 与 [audited_features.py](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/ml/audited_features.py) 可知：`F7_pz0_raw_v1` 的 `62` 个输入特征中包含 `VetoNu0_raw_charge`、`VetoNu1_raw_charge`、`VetoNu0_reduced_charge`、`VetoNu1_reduced_charge`（索引 `#25–26` 与 `#36–37`）。
   - 在 `S1` 通过样本中，**`8.91%`（`10,653 / 119,586`）** 处于 `reduced_charge >= 30 pC` 的 Zone B 区域；在高非弹性区 `y_inel >= 0.5` 该比例升高至 **`15.47%`**。Zone B 被挽救事例呈现更高的非弹性与能量特征：**中位 `y_inel = 0.280`**（vs `S0` `0.171`）与 **中位 `E_nu = 1027 GeV`**（vs `S0` `706 GeV`）。由于训练时模型仅见过 `S0 (reduced_charge < 30)` 事件，直接将未重训的 `F7_pz0_raw_v1` 应用于 S1/S2 样本将面临特征外推风险。

### 6. 未测量项目声明

- **真实物理 Data 的 `SR-ZoneB` 通过事例数、物种构成及实测信号增长**：**未测量**（根据盲化政策，`Timing_Allow_SR_ZoneB` 对 `DATA` 严格锁定为 `false`）。
- **穿过 μ 子与大角度软本底进入 `SR-ZoneB` 的 ABCD 数据驱动本底产额**：**未测量**（将在 Stage T4 完成并建立开盲门控）。

---

## 阶段性结论

1. **假说 H1 / H3 / H6 全面证实**：`S0` 弃用事件的 `12.100%`（名义 `30 ab^-1`）主要由中子核反冲（`46.65%`）与高 `dE/dx` / $\gamma \to e$ / 质子后向回溅在 `VetoNu` 造成，其中近 `71.0%–71.6%`（`+10,653 / +10,740`）显著延迟到 `+1.5` 至 `22 ns` 之后。S1 / S2 带来 **`+464.5%`** 最上游靶区接收度与 **`+26.3%`** 多 TeV 高能区恢复，Run 3 合计（`335.92 fb^-1`）预期 CC 信号从 `1301.68` 增至 **`1431.11 (+9.94%, S1)`** 与 **`1431.95 (+10.01%, S2)`**。
2. **假说 H4 与 `t0_down` 冻结定案**：下游簇射偏置主要由饱和/离群道拉歪非迭代加权均值造成；冻结 `DownstreamMode::Trimmed3Sigma`（配合 `chi2_down/ndof < 5.0` 与 `1.5 < width < 19.5 ns`）将 `t0_down` 的 `|t0| > 1.0 ns` 尾部从 `7.295%` 压缩到 `0.746%`，把全部 `4,342` 例 S1 Zone B 未救出事件解释完毕（`0` 例未知），同时维持 Stage T2 `CR-Prompt` 宽度闭合优于 `5%`（`+3.44% / +2.32%` 未加权、`-1.49% / +1.54%` 周期加权；`Trimmed3Sigma` vs `AllValid` `< 0.3%`）。
3. **假说 H5 强有力验证**：恢复 Zone B 将 5 种 Geant4 物理模型间总接收度包络收窄约 `60%–73%`——`Run3_Combined` 从 `2.117%`（`S0`）降至 **`0.839%`（`S1`）** 与 **`0.816%`（`S2`）**；同几何同乳胶配置下的 `2024_CaloNu_master_dev` 4 模型甚至从 `1.540%` 降至 **`0.414%`（`S1`）**，证明后向核反冲强子模拟分歧（尤其是不同核内级联对反冲粒子到达角和能谱截断的模型差异）正是原先 `S0` 系统误差的主要物理根源之一。
4. **`2024_CaloNu` 异质性澄清与框架就绪**：明确了 `s0015 (200139..146)` 与 `master_dev (200172..183)` 的几何/乳胶配置差异；S1 与 S2 已作为正式分析配置落地 `AnalysisZipFramework` 且盲化锁完好；同时识别出 ML 模型 `F7_pz0_raw_v1` 对 `VetoNu` 电荷特征存在直接依赖，在应用于 Zone B 之前需开展消融重训或域适应评估。

---

## 下一步计划（Stage T4：本底验证、盲化内 Data 校验与开盲门控审计）

| 任务序号 | 具体任务 | 所需输入 | 验收标准 |
| --- | --- | --- | --- |
| T4-1 | 开展 2022–2024/25 全周期非盲侧带（`CR-Geom`、`CR-NonColl`、多径路大角度高电荷控制区与未开盲 FLUKA MC）本底扫描与 ABCD 独立性检验 | 全 Run 3 Data PHYS 与 FLUKA MC，配套 [cuts_timing_s1.yaml](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/cuts_timing_s1.yaml) 与 [cuts_timing_s2.yaml](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/AnalysisZipFramework/config/cuts_timing_s2.yaml) | 构建经独立性验证的 `SR-ZoneB` 非中微子本底估计及闭合精度（`< 20%` 或优于统计不确定度 1/3） |
| T4-2 | 评估穿行 μ 子脉冲尾部、偶然符合（pileup / off-BCID）及下游误触发进入 `+1.5 < dt < 22 ns` 窗口的泄漏上限 | Data `CR-Prompt` 与 `CR-NonColl` 高统计直方图 | `S1` 与 `S2` 候选工作点总本底占预期 `+129.43` 信号增量的比例小于预设安全阈值（目标 `< 5%`） |
| T4-3 | 评估并在必要时消融重训无 `VetoNu` 电荷特征的 ML 能量回归模型（避免 `8.91% / 15.47%` 特征域外推） | [audited_features.json](file:///eos/home-x/xcheng/FASER/nu_muAnalysis/ml/configs/audited_features.json) 与 S1 选定 GENIE 样本 | 对比含/不含 `VetoNu` 电荷特征的模型在 Zone A 与 Zone B 上的能量分辨率与偏置稳定性 |
| T4-4 | 汇总 Stage T0–T4 证据完成预开盲审查（Pre-unblinding Freeze Review），在物理批准后解锁 `Timing_Allow_SR_ZoneB` | Stage T0–T4 报告、完整系统误差表与独立审阅结论 | 所有先验 Freeze 条件逐条满足后方可单次提交开盲生产运行并产出物理结果 |
