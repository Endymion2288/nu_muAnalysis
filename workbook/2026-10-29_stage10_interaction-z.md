# 阶段 10：tracking cut 效率随中微子相互作用 Z 的变化

## 阶段目标

在阶段 09 的相同输入、官方 master、几何和 νμ cuts 下，增加 forward/backward/
merge 效率随真值相互作用 Z 的图。保留每个 Z bin 的分子、分母、统计区间和
同事件模式差值，区分累计选择效率与单项 cut 的逐步效率。

## 输入、坐标与配置

输入清单 `AnalysisZipFramework/submission/tracking_z_manifest.tsv` 与阶段 09
逐行使用相同的 342 个 RDO 和已有 merge，仍共同跳过没有 merge 的原 index 291。
参考结果为 `workbook/stage09_tracking_comparison/paired_results.npz`：NoCuts
3,374,987 events、共同 truth fiducial 分母 383,670 events。这些是上一阶段
实测参考数，新增提取必须逐文件复现后才验收。

Calypso 固定官方 master `d32b0ff3cc4a2dad4abfb1474a82422c3c25b305`，
Athena 24.0.41/GCC 13.1，TI12MC04/FASERNU-04/OFLCOND-FASER-06；不含 CaloNu，
maker 使用 without-IFT 默认配置。全部 cuts 和 leading-track 最高 pz 定义不变，
使用原生 VetoNu reduced charge。

横轴使用仓库现有 `truth_dec_z_nu = SafeAt(truth_dec_z, 0)`，单位 **mm**，
表示入射中微子的真值相互作用点；对于本次 νμ/反νμ CC 选择，对应主相互作用
产生 μ 的顶点坐标。定义见 `config/definitions.yaml`；空间选择界限来自
`include/RDFDefines.h`：

| 区域 | 原分析 Z 选择（mm，严格不等式） | 分箱 |
|:---|:---|:---|
| FASERν box | −3000 < Z < −1950 | 100 mm，最后一档 50 mm |
| 选择空隙 | −1950 至 −1769.65 | 独立空 bin，不定义效率 |
| lead block | −1769.65 < Z < −1619.65 | 3 档，每档 50 mm |

每档累计效率为该模式通过相应阶段的事件数 / 该档三模式共同的真值事件数。
主图分别累计到 long-track、theta 和完整选择；theta 前包含原有 scintillator
cuts。附图给出全部 14 个重建 cut 的逐步效率，本行 / 同模式上一行；第一行
分母为共同真值。单模式使用 68% Wilson 区间，模式差值使用同事件配对 SE。
空分母记为 NaN 并留空，不补零、不跨空隙插值。没有引入 flux 权重或系统误差。

## 工作内容、性能与验证

阶段 09 的最终摘要没有保存事件 Z，无法从 pz/r 的边缘分布还原 Z 效率。
新增精简输出：只保留共同 truth fiducial 事件的 run/eventID、truth pz/x/y/z，
以及三模式各一个 uint16 位掩码，按原顺序编码 14 个累计重建 cut。
不保存全量事件树或未选中事件的宽分支，可供之后直接补充其他坐标图。
该精简事件文件仅在 EOS 留一份并加入 Git ignore；代码、分箱统计和图表纳入 Git。

每个 worker 临时重建一次 RDO，再只制作 forward/backward；merge 直接使用已
验收的阶段 09 输出，复制到 scratch 后读取，省去一次 maker 和重复远端读。
三模式逐事件核对 17 个非轨迹输入，并要求全 cutflow、配对统计、非有限
leading-quality 计数和全部 pz/r 分箱逐项复现该文件阶段 09 的结果。
输出仅含小型精简 NPZ，ROOT ntuple、RDO 和 xAOD 均随 scratch 清理。

100-event 基线试验：共同真值 15 events；1/2 RDataFrame 线程提取的 **14 个
精简输出数组全部一致**。首文件提取计时为 10.85/18.58 s，受首次 JIT/缓存影响，
不据此宣称多线程加速。正式每 job 请求 1 CPU、3000 MB memory、6000 MB disk，
OMP/OpenBLAS/MKL 固定 1；使用 HTCondor 在文件间并行。汇总器用 4 个线程
读取小型 NPZ，采用 NumPy 矢量计算，不扫描全部 ROOT 分支，不做 SHA。

完整试跑为 run 200100 的 00170–00179 RDO，343 events，公共真值 16 events。
全部阶段 09 参考统计精确匹配；最终通过数 forward/backward/merge=4/5/5。

| 步骤 | 墙钟 s | 峰值 RSS KiB |
|:---|---:|---:|
| RDO → scratch | 0.69 | 2,464 |
| reco | 102.97 | 1,117,128 |
| 已有 merge → scratch | 0.28 | 2,464 |
| maker forward | 26.22 | 919,700 |
| maker backward | 25.69 | 946,140 |
| 比较与精简输出 | 21.96 | 734,044 |

试跑输出 3,492 bytes，Z 分母分箱为 `[2,3,1,0,2,1,2,0,1,1,2,0,1,0,0]`，
和为 16；空隙 bin 为零。坐标、位掩码解码、累计计数、图形和空分母显示已验证。
试跑仅验证流程，不作为全量物理趋势依据。

冻结软件包 `software/tracking-z-stage10.tar.gz`，**187,834 bytes**，包含
setup_env、提取脚本、原 YAML/C++ helper 和阶段 09 参考 NPZ。官方 runtime
沿用既有归档，没有重新编译或改动 Calypso。342 项 dry-run 通过后提交
HTCondor **cluster 1537993**，workday；排除阶段 09 已实测出现 I/O 长尾的
`b9p02p8722.cern.ch`，不改变输入文件和物理配置。

执行中发生过 EOS/FUSE `Input/output error`。Condor proc 268/315 的分析退出码
均为 0，但自动回传 scratch 中 `xcheng.cc` 时发生 EOS versioning/communication
错误并进入 Held；这不是 cut/reference 验证失败。核对 job ad 后，显式将
`TransferOutput` 设为空并释放两项作业。提交描述符同步使用
`should_transfer_files = YES`、`transfer_output_files = ""`，342 项 dry-run 通过。
NPZ 仍由 worker 单独上传、核对远端大小并原子改名；stdout/stderr 继续回传到
指定日志。修复没有改变冻结的提取 payload、重建代码或物理配置。

```bash
source /usr/share/Modules/init/bash
module load lxbatch/eossubmit
condor_submit AnalysisZipFramework/submission/tracking_z.sub

# 首次汇总（分片清理前）
source setup_env.sh --official
python AnalysisZipFramework/scripts/report_tracking_z.py --repo "$PWD" \
  --manifest AnalysisZipFramework/submission/tracking_z_manifest.tsv \
  --reference workbook/stage09_tracking_comparison/paired_results.npz \
  --output workbook/stage10_tracking_z
```

## 全量结果与验证

HTCondor cluster **1537993** 的 342 项最终任务均正常退出，退出码全部为 0；
event log 记录 344 次启动、2 次 Held、2 次 release。最终 stdout 中 339 项包含
完整计算计时，3 项在确认精简结果有效后跳过：proc 268、315（回传重试）和
341（复用完整试跑）。物理输入、共同跳过的 index 291 与阶段 09 完全相同。

全量 3,374,987 events、共同真值 **383,670 events**。三模式最终通过数
**92,937 / 103,985 / 104,930**，全部 20 个 cut、逐文件配对计数和原有 pz/r
分箱与阶段 09 精确一致。共同真值事件的 `(run,eventID)` 唯一；逐文件分母、
14-bit 累计模式、每项 cut 解码计数及 Z 分箱积分全部验收通过。

Z 分母为 `[32091,34097,34261,34292,34369,34253,34200,34249,34238,34190,17165,0,6718,12796,6751]`，
和为 383,670；box **357,405**、lead **26,265**，选择空隙为 **0**。

### 图表与分箱数据

![三种模式随 Z 的累计效率](stage10_tracking_z/efficiency_vs_z.png)

![全部 cut 随 Z 的逐步效率](stage10_tracking_z/conditional_cut_efficiency_vs_z.png)

主图每个非空 bin 的误差为 68% Wilson 区间；热图保持原有 cut 顺序，不把
逐步效率误认为累计效率。所有数值为未加权事件选择效率，未做 primary-muon
truth matching，也未测量系统误差。

| Z 范围（mm） | 真值 N | long F / B / M（%） | 最终 F / B / M（%） | 最终 M−B（百分点，±SE） |
|:---|---:|:---|:---|:---|
| -3000 至 -2900 | 32,091 | 51.912 / 53.713 / 54.330 | 9.579 / 9.732 / 9.850 | +0.118 ± 0.020 |
| -2900 至 -2800 | 34,097 | 53.049 / 54.961 / 55.653 | 23.210 / 23.671 / 23.920 | +0.249 ± 0.028 |
| -2800 至 -2700 | 34,261 | 53.612 / 55.921 / 56.665 | 28.461 / 29.132 / 29.401 | +0.269 ± 0.030 |
| -2700 至 -2600 | 34,292 | 53.963 / 56.730 / 57.474 | 30.103 / 31.136 / 31.383 | +0.248 ± 0.029 |
| -2600 至 -2500 | 34,369 | 53.391 / 56.865 / 57.692 | 29.995 / 31.304 / 31.581 | +0.276 ± 0.030 |
| -2500 至 -2400 | 34,253 | 52.994 / 58.237 / 59.177 | 30.181 / 32.280 / 32.561 | +0.280 ± 0.031 |
| -2400 至 -2300 | 34,200 | 51.716 / 58.722 / 59.655 | 29.184 / 32.061 / 32.377 | +0.316 ± 0.032 |
| -2300 至 -2200 | 34,249 | 48.696 / 58.256 / 59.319 | 26.999 / 30.623 / 30.944 | +0.321 ± 0.034 |
| -2200 至 -2100 | 34,238 | 44.375 / 57.395 / 58.336 | 24.365 / 29.520 / 29.762 | +0.242 ± 0.030 |
| -2100 至 -2000 | 34,190 | 39.161 / 54.770 / 55.627 | 21.679 / 27.777 / 28.020 | +0.243 ± 0.031 |
| -2000 至 -1950 | 17,165 | 33.731 / 51.646 / 52.496 | 18.380 / 25.430 / 25.610 | +0.181 ± 0.041 |
| -1950 至 -1769.65 | 0 | — / — / — | — / — / — | 未定义 |
| -1769.65 至 -1719.65 | 6,718 | 24.665 / 43.495 / 43.971 | 14.290 / 21.435 / 21.584 | +0.149 ± 0.052 |
| -1719.65 至 -1669.65 | 12,796 | 18.349 / 35.308 / 35.605 | 11.097 / 17.654 / 17.779 | +0.125 ± 0.038 |
| -1669.65 至 -1619.65 | 6,751 | 18.797 / 35.891 / 36.246 | 10.532 / 17.716 / 17.908 | +0.193 ± 0.065 |

表中 F/B/M 为 forward/backward/merge；百分比按各 bin 的共同真值 N 归一。
每个 cut 的完整分子、分母、条件效率、Wilson 上下界见
[`z_bins.tsv`](stage10_tracking_z/z_bins.tsv)，同事件 gain/loss/both 与统计 SE 见
[`z_paired_differences.tsv`](stage10_tracking_z/z_paired_differences.tsv)。

### 按原几何区域积分

| 区域 | 阶段 | 真值 N | Forward Pass（%） | Backward Pass（%） | Merge Pass（%） |
|:---|:---|---:|---:|---:|---:|
| FASERnu_box | long-track | 357,405 | 176,859（49.484） | 201,359（56.339） | 204,353（57.177） |
| FASERnu_box | through theta | 357,405 | 102,011（28.542） | 111,796（31.280） | 112,815（31.565） |
| FASERnu_box | 完整选择 | 357,405 | 89,846（25.138） | 99,090（27.725） | 99,996（27.978） |
| lead_block | long-track | 26,265 | 5,274（20.080） | 9,863（37.552） | 9,957（37.910） |
| lead_block | through theta | 26,265 | 3,093（11.776） | 4,898（18.648） | 4,937（18.797） |
| lead_block | 完整选择 | 26,265 | 3,091（11.769） | 4,895（18.637） | 4,934（18.785） |

分区域原始统计另存 [`z_regions.tsv`](stage10_tracking_z/z_regions.tsv)。
各区域仍施加 truth r<100 mm 和 pz>100 GeV；不是对整个几何体积求效率。

### 性能与存储

下表覆盖 **340 个有完整计时的输入实例**：339 个最终计算日志加独立完整试跑。
两项回传重试的原计算 stdout 被新一次跳过日志覆盖，其原分步骤计时未保留，
未纳入合计；重试额外开销未测量。详细 p95 与 CPU 时间见
[`timing_summary.tsv`](stage10_tracking_z/timing_summary.tsv)，不将这些合计当作
全部集群资源消耗，也不将节点/输入差异解释为线程加速比。

| 步骤 | min / median / max 墙钟（s） | 墙钟合计（s） | 最大 RSS（KiB） |
|:---|---:|---:|---:|
| input | 0.68 / 4.35 / 102.65 | 1888.64 | 2,464 |
| reco | 102.02 / 1471.22 / 4457.27 | 514852.56 | 1,344,988 |
| existing_merge | 0.28 / 1.25 / 881.67 | 71560.20 | 2,464 |
| forward | 26.22 / 304.27 / 721.97 | 99136.10 | 1,118,232 |
| backward | 25.69 / 302.22 / 744.10 | 100503.10 | 1,116,152 |
| comparison | 14.49 / 22.18 / 134.47 | 8545.61 | 768,540 |

已有 merge 复制的中位数为 1.25 s，但 p95 达 **761.06 s**，最大 881.67 s；
该步骤记录的 CPU 合计仅 39.51 s，墙钟合计 71,560.20 s，表明此阶段主要等待
存储 I/O，与执行中实测 EOS 错误一致。没有把这部分长尾归因为物理事件复杂度。
reco 和 maker 的样本/节点差异仍保留在统计中，不删除慢事件。

342 份分片原占 **8,399,212 bytes**。合并事件文件仅 **6,827,773 bytes**，
只在 EOS 留一份、被 Git 忽略。已完成以下核验后删除全部 342 份重复分片：

- 所有分片的 7 个事件列逐项等于合并文件对应 slices；未做 SHA 扫描。
- 使用合并文件在 `/tmp/nu_mu_stage10/reloaded_final/` 重新生成：全部数组一致，
  3 张 TSV 和说明 Markdown 逐字节一致，两张 PNG 的像素数组完全一致。
- 原始/重建 ROOT 数据只在 worker scratch 使用；不新增长期 RDO、xAOD 或
  forward/backward ntuple 副本。额外自动回传的 scratch 临时文件已清理。

代码与产物：`compare_tracking.py` 新增精简位掩码输出及旧结果验收；
`report_tracking_z.py` 负责汇总/绘图；`tracking_z.sub` 和
`tracking_z_manifest.tsv` 固定生产配置/输入。图、分箱 TSV、说明与本日志纳入 Git，
合并事件数据和软件归档留在 EOS。图同时提供同目录 SVG 版本。

分片清理后，直接用合并文件重新出图，无需再提交 reco：

```bash
source setup_env.sh --official
python AnalysisZipFramework/scripts/report_tracking_z.py --repo "$PWD" \
  --manifest AnalysisZipFramework/submission/tracking_z_manifest.tsv \
  --reference workbook/stage09_tracking_comparison/paired_results.npz \
  --combined workbook/stage10_tracking_z/fiducial_events.npz \
  --output workbook/stage10_tracking_z
```

## 阶段性结论

1. **下游相互作用的方向策略差异更大。** box 第一档（−3000 至 −2900 mm）的
   long-track F/B/M 为 51.912/53.713/54.330%；box 最后一档（−2000 至
   −1950 mm）为 33.731/51.646/52.496%。Backward 相对 forward 的优势从
   1.801 增至 17.915 个百分点。Lead 区域积分为 20.080/37.552/37.910%；
   B−F 为 **17.472 ± 0.242 个百分点**，box 对应 **6.855 ± 0.048 个百分点**。
   因而仅看全样本平均会掩盖明显的 Z 依赖。
2. **最上游最终效率低谷主要出现在最后两项 VetoNu cuts。** 以 merge 的
   −3000 至 −2900 mm 为例，through-theta 为 10,125 events，VetoNu0 后
   4,700，VetoNu1 后 3,161；逐步效率为 **46.420% / 67.255%**，累计真值
   归一效率由 31.552% 降至 **9.850%**。相比之下，−2400 至 −2300 mm 的
   两项逐步效率均超过 99.3%。该低谷不能当作上游 long-track 效率突然下降，
   也不是只在一种 tracking 模式出现的现象。
3. **Merge 的最终增益贯穿所有 14 个非空 Z bins。** 相对 backward 的最终
   差值为 +0.118 至 +0.321 个百分点。Box 净增 906 events（gain 987、loss 81），
   **+0.25349 ± 0.00913 个百分点**；lead 净增 39（gain 47、loss 8），
   **+0.14849 ± 0.02822 个百分点**。合计净增 945，复现阶段 09。
4. 上述结论由同源事件、固定 cuts 的 Z 分箱和配对计数直接支持。当前图测量的是
   混合生成器/运动学下的事件选择效率；仅凭 Z 边缘分布不能分解材料传播、
   shower 占有率与 tracking 播种/拟合的各自贡献。未测量的因果分量不代以推断。
   已明确区分“存在 long track 的模式差异”与“后续 VetoNu 的 Z 依赖”两个效应，
   后续应分别检验。

## 下一步计划

- **检验方向优势的运动学依赖：** 输入为已保存的 `fiducial_events.npz`、原有
  pz/r 分箱和 run 清单；按 run、truth pz、truth r 分层比较 Z 效率及配对差值，
  单独给出排除 SIBYLL 的结果。验收标准：各分层分子/分母之和精确还原当前
  cutflow，每格报告 N 和统计区间，零分母留空，三模式使用相同分层/权重。
- **区分主要 μ 与其他 track 的贡献：** 输入为位掩码提取的模式 gain/loss 事件
  ID、对应原 RDO 和 merge ntuple；针对这些事件核查 leading track 的 primary
  muon truth matching、hits/layers 和拟合质量。如需批量重新提取则提交 HTCondor，
  仅留紧凑事件诊断。验收标准：保留原 cutflow，分别给出匹配/未匹配计数及
  Z 分布，明确量化有多少净增事件来自 primary muon。
- **降低后续存储等待：** 输入为同一批代表性 merge 文件；在小规模测试中对比
  FUSE `cp` 与直接 XRootD staging 的墙钟、CPU、失败率和必要分支一致性。
  验收标准：文件/分支结果一致，报告实测统计，只有数据支持时才更新生产脚本，
  不用单次缓存命中宣称加速。
