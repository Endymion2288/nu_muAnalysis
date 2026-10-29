# 阶段 09：相同来源 forward / backward / merge 的 νμ cutflow 对照

## 阶段目标

按本仓库 νμ 分析现有 cut 顺序，比较三种 tracking 模式；输入 RDO、重建版本、
几何、conditions、事件集合均相同，只有 maker 的 `--CKFTrackType` 改变。
没有 merge 输出的输入先跳过。提供逐行 Pass、Eff、CumEff 表和效率图，保留
配对统计，而不保存三套重复 ntuple 或 xAOD。

## 输入与配置

沿用阶段 06 的普通几何 RDO：TI12MC04 / FASERNU-04 / OFLCOND-FASER-06，
sim tag s0014。官方 master 固定于 `d32b0ff3cc4a2dad4abfb1474a82422c3c25b305`，
faser-common `1770d15df9311f6535c09909edf9ad64a5779e32`，Athena 24.0.41、
GCC 13.1、ROOT 6.28/12、Acts 32.0.2，物理源码无修改。不含 CaloNu，maker
使用默认 without-IFT。没有使用原 `../calypso` 的修改版，也没有使用 EOS 上
旧软件/旧 conditions 的 forward/backward 产品。

| run | 生成器/来源 | 本次文件数 |
|---:|:---|---:|
| 200080 | SIBYLL π，替代生成器 | 45 |
| 200082 | EPOS π | 56 |
| 200083 | EPOS K | 76 |
| 200089 | POWHEG/PYTHIA charm central | 19 |
| 200093 | 2024 crossing angle，EPOS π，wo_caloNu | 55 |
| 200094 | 2024 crossing angle，EPOS K，wo_caloNu | 73 |
| 200100 | 2024 crossing angle，POWHEG/PYTHIA charm central，wo_caloNu | 18 |
| 合计 | 七个 run | 342 |

输入根路径 `/eos/experiment/fasernu-data0/faser/sim/mc24/genie/`；已有 merge
位于 `/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/merge_mc24_master_d32b0ff3/`。
精确的一对一映射见 `AnalysisZipFramework/submission/tracking_comparison_manifest.tsv`，
字段为原 index、run、geometry、RDO、已有 merge、临时统计路径，无表头。
原 manifest index **291**（200094，00400–00409，10,000 events）没有已发布
merge，因此从三种模式共同排除。阶段 08 已定位该文件的 forward χ² NaN 传播；
这里没有删除单个离群事件或修改官方拟合/merge 代码。

全部 343 RDO 共 3,384,987 events，本次期望共同覆盖 **3,374,987 events**。
各 run 不做 luminosity/flux 权重；全样本混合含替代 SIBYLL，不能当作标称物理
产额预测。另给排除 200080 的六个 run 汇总和每个 run 的独立结果。

## 方法与效率定义

新增 `compare_tracking.py`，直接读取 `config/cuts.yaml`、`definitions.yaml`，
通过 PyROOT RDataFrame 执行仓库 `include/RDFDefines.h` 的 C++ 表达式。
采用正常 `--isMC` 语义和原生 `VetoNu{0,1}_reduced_charge < 30 pC`，共 20 个
有效 cut；DATA、aux-only 和 raw-charge fallback 条件不启用。

保留原分析的最高 pz leading-track 选择；没有改成“任一好轨迹”。真值分母为
前六个 cut：普通几何 PMT 清理、CC、|PDG|=14、FASERν box 或 lead block、
truth r<100 mm、truth pz>100 GeV；|PDG|=14 同时包含 νμ 和反 νμ。`Track R at IFT` 沿用现有定义中的
VetoStation2 外推坐标，不替换定义或阈值。

- Pass：按 YAML 顺序累计通过的未加权事件数。
- Eff：本行 Pass / 上一行 Pass；NoCuts 为 100%。
- CumEff：本行 Pass / NoCuts。
- 真值归一效率：重建选择阶段 Pass / 三种模式共同的 truth-fiducial 事件数。

这些量衡量事件重建/选择效率；未做 muon truth matching，不能称为单 muon
径迹重建效率。Through-theta 阶段还包含此前 scintillator cuts；最终阶段增加
两层 VetoNu veto。能量图横轴为 truth **pz**（GeV），不是精确中微子能量。

逐事件按 `(run,eventID)` 排序配对，检查 ID 唯一和三模式 17 个非轨迹原始输入
完全相同；检查新旧 merge 的分析标量及每一项 cut 决策完全相同。每对模式每行
保留 neither / first-only / second-only / both 计数。共同真值分母 N 下，
Δε=(second-only−first-only)/N，统计 SE 为
`sqrt(((first-only+second-only)/N − Δε²)/N)`，保留同事件协方差。
各能量/半径 bin 单模式误差采用 68% Wilson 区间；未测量系统误差。

## 执行命令、性能与验证

先验证 200082 的 100-event 三模式输入，再完整试跑 200100 最后一个 RDO
（00170–00179，343 events）。两者分别与仓库原 C++ `build/analysis --isMC`
对照，**全部 20 个 cut 的计数逐项一致**，覆盖早期和 2024 MC。
原分析只将输出列缩减到 run/eventID，没有改变 cut、definitions 或输入事件。

100-event RDataFrame 1/2 线程比较的全部 11 项摘要数组一致。首文件墙钟
11.36/10.42 s，后续 backward 0.81/0.80 s，merge 0.82/0.89 s；包括首次 JIT、
缓存与节点波动，没有证据据此宣称两线程有稳定加速。因此每 job 请求 1 CPU，
利用文件之间的 HTCondor 并行；OMP/OpenBLAS/MKL 固定 1，避免超配。
没有将 OMP 环境变量解释为 Athena 事件并发。

343-event 试跑实际计时：

| 步骤 | 墙钟 s | 峰值 RSS KiB |
|:---|---:|---:|
| RDO → scratch | 0.45 | 2,240 |
| reco | 93.97 | 1,119,864 |
| maker forward | 25.14 | 917,756 |
| maker backward | 24.61 | 951,516 |
| maker merge | 25.45 | 943,992 |
| 配对统计及重读已有 merge | 21.72 | 756,764 |

试跑三模式 NoCuts 均为 343，truth 分母均为 16；long-track 分别 8/10/11，
最终分别 4/5/5。这是流水线验证的小样本，不用它推断全量优劣。
修复了 PyROOT bool object 数组不能使用 NumPy equal_nan 的比较接口问题。
另将写回 XRootD 路径从本地 home-x alias 改为服务器接受的 `/eos/user/x/`；
2,461-byte 摘要已实际上传、服务器 stat 验证并删除。未做 SHA 或整文件散列。

批量 worker 每文件仅重建一次，在同一临时 xAOD 上依次制作三种模式；只读取
cut 所需分支并一次提取标量/判定。小型 NPZ 写回使用 xrdcp → 服务器长度核对 →
rename，scratch 随退出清理，不在 EOS 留存新增 ntuple、RDO 或 xAOD 副本。

```bash
# fresh shell；小样本提取
source setup_env.sh --official
python AnalysisZipFramework/scripts/compare_tracking.py --repo "$PWD" \
  --forward /tmp/nu_mu_stage06_validation/forward/ntuple.root \
  --backward /tmp/nu_mu_stage06_validation/backward/ntuple.root \
  --merge /tmp/nu_mu_stage06_validation/merge/ntuple.root \
  --existing-merge /tmp/nu_mu_stage06_validation/merge/ntuple.root \
  --output /tmp/nu_mu_stage09/test100_threads1.npz --threads 1

# 冻结本次 worker 配置后提交
tar -czf software/tracking-comparison-stage09.tar.gz setup_env.sh \
  AnalysisZipFramework/scripts/compare_tracking.py \
  AnalysisZipFramework/config/{cuts,definitions}.yaml \
  AnalysisZipFramework/include/RDFDefines.h
source /usr/share/Modules/init/bash
module load lxbatch/eossubmit
condor_submit AnalysisZipFramework/submission/tracking_comparison.sub
```

HTCondor cluster **1536139**，342 jobs，每 job 请求 1 CPU、3000 MB memory、
6000 MB disk、workday（8 h 执行时间）；2026-10-29 10:14:38 CET 提交。
初投 1536137 的 342 项尚未运行即撤回：EosSubmit 将 home-x alias 转为无法读取的
XRootD executable URL。改用显式 `/eos/user/x/` initialdir/executable/log 路径，
实际读取验证通过后重投。服务器接受的资源为 1 CPU / 3000 MB；原 3500 MB
请求会被站点上调为 2 CPU / 6000 MB，已避免该超配。

worker 的物理命令为：

```bash
faser_reco.py --isMC --geom TI12MC04 --nevents -1 <local-RDO.root>
for mode in forward backward merge; do
  faser_ntuple_maker.py --isMC --geom TI12MC04 --CKFTrackType "$mode" \
    --nevents -1 --outfile "$mode.root" <same-local-xAOD.root>
done
```

### 最后一个输入的节点 I/O 长尾与替代作业

原 index 125（200083，00240–00249）在 b9p02p8722 节点的输入复制耗时
1172.63 s；重建心跳后期停在 9501/10000。只读 worker 进程诊断记录
`State=D (disk sleep)`、`folio_wait_bit`、VmSwap=0，说明观察时正等待 I/O；
没有证据据此归因于物理算法或某个离群事件。经多次检查未及时恢复，补投同一
输入到其他节点，cluster **1537836.0**，排除原节点；使用完全相同 payload、
软件和配置，仅临时摘要路径改为 `125.retry.npz` 以避免并发写同一目标。
替代节点复制耗时 **8.30 s**，完整重建耗时 **2419.01 s**，峰值 RSS
**1,144,968 KiB**；使用相同输入成功推进到全部 10,000 events。原作业在
9501-event 心跳长期等待 I/O 后已撤回，最终采用替代作业通过配对验证的结果。
这确认节点 I/O 与该次长尾有关；没有测量底层设备/服务故障的精确根因。

## 全量详细数据、产物与阶段性结论

已验收 **342/342** 个相同 RDO，共 **3,374,987 个配对事件**，与输入审计逐文件精确一致。
三模式共同真值分母 **383,670**；全部 17 个非轨迹输入、事件 ID 及新旧 merge 分析变量/cut 判定检查通过。
341 项来自主 cluster 正常退出，index 125 来自替代 1537836.0；原慢节点实例撤回，不计作丢失样本。

| 阶段 | Forward Pass | Forward / truth (%) | Backward Pass | Backward / truth (%) | Merge Pass | Merge / truth (%) |
|:---|---:|---:|---:|---:|---:|---:|
| 至少一条 long track | 182,133 | 47.4713 | 211,222 | 55.0530 | 214,310 | 55.8579 |
| 累计通过 theta（含此前 scintillator） | 105,104 | 27.3944 | 116,694 | 30.4152 | 117,752 | 30.6910 |
| 最终完整选择 | 92,937 | 24.2232 | 103,985 | 27.1027 | 104,930 | 27.3490 |

完整 21 行（三种模式各 Pass/Eff/CumEff）见 [主对照表](stage09_tracking_comparison/comparison.md)。
其余分组见 `cutflow_nominal.md`、`cutflow_<run>.md`；机器可读结果见 `cutflow.tsv`。

| 最终选择差值 | 前者独有（损失） | 后者独有（获得） | 共同通过 | Δ效率 ± 配对 SE（百分点） |
|:---|---:|---:|---:|---:|
| backward-forward | 1,132 | 12,180 | 91,805 | +2.8796 ± 0.0297 |
| merge-forward | 101 | 12,094 | 92,836 | +3.1259 ± 0.0283 |
| merge-backward | 89 | 1,034 | 103,896 | +0.2463 ± 0.0087 |

各 run 的最终选择效率均使用该 run 自己的共同真值分母：

| run | 真值分母 | Forward (%) | Backward (%) | Merge (%) | Merge−backward（百分点 ± SE） |
|---:|---:|---:|---:|---:|---:|
| 200080 | 60,034 | 22.8371 | 25.0192 | 25.2257 | +0.2065 ± 0.0202 |
| 200082 | 71,902 | 22.3874 | 24.2997 | 24.5167 | +0.2170 ± 0.0185 |
| 200083 | 82,088 | 26.2767 | 30.0641 | 30.3418 | +0.2778 ± 0.0198 |
| 200089 | 10,512 | 26.6362 | 30.9932 | 31.3356 | +0.3425 ± 0.0630 |
| 200093 | 68,755 | 22.3082 | 24.1902 | 24.4302 | +0.2400 ± 0.0203 |
| 200094 | 80,542 | 25.7394 | 29.6082 | 29.8689 | +0.2607 ± 0.0200 |
| 200100 | 9,837 | 27.3559 | 31.2799 | 31.5442 | +0.2643 ± 0.0592 |

### 图表与数值产物

![累计及逐步效率](stage09_tracking_comparison/cutflow_efficiency.png)
![按真值 pz 的效率](stage09_tracking_comparison/efficiency_vs_energy.png)
![按真值半径的效率](stage09_tracking_comparison/efficiency_vs_radius.png)
![同事件配对差值](stage09_tracking_comparison/paired_efficiency_differences.png)

每图同时提供 SVG。`energy_bins.tsv` 保留 pz≥10000 GeV 的溢出档；`radius_bins.tsv` 记录 mm 分箱。
`paired_differences.tsv` 保留所有 cut 的同事件获得/损失和统计 SE，`files.tsv` 记录逐文件来源，
`cut_definitions.tsv` 保存实际表达式，`paired_results.npz` 为可再生成报告的唯一合并统计文件。

### 全量执行资源

| 步骤 | 墙钟 min / median / max（s） | 墙钟合计（s） | 峰值 RSS 最大值（KiB） |
|:---|---:|---:|---:|
| input | 0.38 / 4.39 / 30.16 | 1649.33 | 2,304 |
| reco | 90.30 / 1677.76 / 4506.33 | 635819.16 | 1,347,684 |
| forward | 27.50 / 336.62 / 688.96 | 124314.11 | 1,108,012 |
| backward | 26.00 / 349.55 / 723.95 | 125905.98 | 1,107,300 |
| merge | 27.91 / 345.41 / 723.81 | 126484.70 | 1,093,424 |
| comparison | 19.38 / 31.44 / 62.17 | 10787.07 | 804,452 |

资源统计只包括最终采用的 342 个成功实例；撤回的长尾实例和交互验证开销未混入。
不同文件、节点、初始化和 I/O 条件不同，不能把 min/max 的差异解释为线程加速比。
三模式全事件范围内，有 leading track 但 χ²/nDoF 非有限的事件数为 [556, 1963, 2362]（forward/backward/merge）；
此统计也包含 nDoF=0 等欠约束候选，不等价于非有限原始 χ²。原分析 nDoF cut 先于 χ²/nDoF cut，未添加新 cut。

## 阶段性结论

- 在固定输入、版本、几何和 cuts 下，最终 backward-forward 的效率差为 **+2.8796 ± 0.0297 个百分点**（仅配对统计 SE）。
- 在固定输入、版本、几何和 cuts 下，最终 merge-backward 的效率差为 **+0.2463 ± 0.0087 个百分点**（仅配对统计 SE）。
- 在固定输入、版本、几何和 cuts 下，最终 merge-forward 的效率差为 **+3.1259 ± 0.0283 个百分点**（仅配对统计 SE）。
- Merge 相对 backward 在 long-track 阶段净增加 3,088 个事件，最终净增加 945 个事件；重建收益经后续选择后只有部分保留。
- 最终 merge 获得 1,034 个 backward 不通过的事件，同时损失 89 个 backward 通过的事件。merge 不是后者通过事件集合的简单超集。官方去重和最高-pz leading-track 选择共同决定这一比较；本阶段未逐事件分解所有损失的具体机制。
- Merge/backward 的净通过数差在 χ²/nDoF 后为 2,351，在 max-radius<95 mm 后为 1,170；最大半径接受度是收益收缩的主要步骤之一。这是固定 cut 顺序下的计数证据，不能据此单独推断拟合偏差或因果机制。
- 七个 run 的 merge−backward 最终差值均为正（+0.2065 至 +0.3425 个百分点）；本次增益不是仅由单个 run 的总计主导。各样本的物理谱、几何年代和权重差异仍需在标称预测中分别处理。
- 原始 scintillator 输入逐事件相同，但 Timing cut 使用 leading track 的 y 选择上下部，所以三模式该 cut 的判定仍可不同，符合原分析定义。
- 所有结论限于这 342 个普通几何文件、固定官方 master 和现有事件 cuts；没有模拟权重、系统误差或 muon truth matching。缺失 merge 的 10,000 events 已共同排除，没有用三模式不同来源文件补齐。

## 重现命令与存储

```bash
source setup_env.sh --official
python AnalysisZipFramework/scripts/report_tracking_comparison.py --repo "$PWD" \
  --manifest AnalysisZipFramework/submission/tracking_comparison_manifest.tsv \
  --combined workbook/stage09_tracking_comparison/paired_results.npz \
  --output workbook/stage09_tracking_comparison
# 初次从 shards 汇总时省略 --combined，实际使用的性能日志选项为：
# --cluster 1536139 --retry 125=1537836.0
```

已对合并 NPZ 与 342 份 shard 逐数组读回比对并删除重复 shards；没有保留新增完整 ntuple 或 xAOD。
验收实测：合并 NPZ **177,452 bytes**；结果目录 27 个文件合计 **1,494,957 bytes**。
删除 342 份重复 shard，合计 **1,010,615 bytes**。合并文件逐数组相等，重建后的七类 Markdown/TSV 内容完全一致；未计算 SHA。

## 下一步计划

1. **定位 merge/backward 的获得与损失机制**：输入为本次 files.tsv、固定 RDO/runtime 和配对选中事件；在 HTCondor 中仅保留小型迁移分类摘要，按 leading-track 改选、去重和外推半径阈值分类。验收：所有迁移事件分类计数之和等于本报告获得/损失数，并用代表事件的匹配测量点、动量和外推值支持各分类。
2. **测量 muon 真值匹配效率与假径迹率**：输入为相同 RDO、各模式的 track truth association 与 CC muon truth；先定义匹配纯度/完整度和接受度。验收：共同可重建真值分母一致，报告 efficiency、fake/duplicate rate 及按 pz/r 分箱的配对统计，不能仅用 longTracks>0 代替 truth matching。
3. **恢复缺失的 200094 文件覆盖**：输入为 index 291 的已定位 forward χ² NaN 证据及上游明确修复版本。验收：同版本三模式完整 10,000 events、数值诊断与全量配对检查通过后，再增加该文件并重做比较；当前无需因此停止普通几何研究。
