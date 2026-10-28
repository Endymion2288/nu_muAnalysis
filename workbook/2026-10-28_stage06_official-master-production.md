# 阶段 06：普通几何 MC 的官方 master ntuple 生产

## 阶段目标

按用户最新指示排除 CaloNu，以固定的官方 master 执行 RDO → reco → merge
ntuple。建立可在交互节点和 HTCondor worker 共用的环境，验证同版本三种轨迹模式，
再提交普通几何全量输入。保留官方物理代码原样。

## 输入、配置与版本

- Calypso：官方 master `d32b0ff3cc4a2dad4abfb1474a82422c3c25b305`；
  faser-common：`1770d15df9311f6535c09909edf9ad64a5779e32`。源码 tracked changes 为零。
- 独立源码、构建、安装目录：`/tmp/nu_mu_stage05_WmLTWo/` 下的
  `calypso-official/`、`official-build/`、`official-run/`。
  原 `../calypso` 的 Tracking-4ST-Clean 安装不参与生产。
- Athena 24.0.41，GCC 13.1.0，ROOT 6.28/12，Acts 32.0.2，EL9，Release 构建。
- reco/maker 均使用 `--isMC --geom TI12MC04`：`FASERNU-04`、
  `OFLCOND-FASER-06`。reco 保留默认两方向、3/4-station 重建；maker 默认不用 IFT，
  仅指定 `--CKFTrackType merge`。不额外覆盖权重、校准、筛选或 merge 策略。
  因官方版本和条件不同，不承诺与旧生产 ntuple 逐值相同。

| run | 输入 tag | RDO 文件数 |
|---:|:---|---:|
| 200080 | s0014 | 45 |
| 200082 | s0014 | 56 |
| 200083 | s0014 | 76 |
| 200089 | s0014 | 19 |
| 200093 | s0014 | 55 |
| 200094 | s0014 | 74 |
| 200100 | s0014 | 18 |
| **合计** | | **343** |

输入根目录：`/eos/experiment/fasernu-data0/faser/sim/mc24/genie/<run>/rdo/s0014/`。
清单：`AnalysisZipFramework/submission/merge_manifest.tsv`，Tab 分隔的
`run, sim_tag, geometry, rdo, outfile, first_segment, last_segment`。
343 个输入及输出路径分别唯一，全部为 TI12MC04；200139/200140/200146 不在清单中。
200093 文件名中的 `wo_caloNu` 表示不带 CaloNu，属于本次普通几何范围。

输出根目录：
`/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/merge_mc24_master_d32b0ff3/`。
该路径在当前节点对应 `/eos/home-x/xcheng/FASER/nu_muAnalysis/ntuples/` 下的同名目录。

## 工作内容与运行环境

### 构建、部署和存储

使用官方 `CI/package_filters_CI.txt` 排除 graphics，构建重建和 ntuple 组件：

```bash
cmake -S /tmp/nu_mu_stage05_WmLTWo/calypso-official \
  -B /tmp/nu_mu_stage05_WmLTWo/official-build \
  -DCMAKE_INSTALL_PREFIX=/tmp/nu_mu_stage05_WmLTWo/official-run \
  -DCMAKE_BUILD_TYPE=Release \
  -DATLAS_PACKAGE_FILTER_FILE=/tmp/nu_mu_stage05_WmLTWo/calypso-official/CI/package_filters_CI.txt
cmake --build /tmp/nu_mu_stage05_WmLTWo/official-build --parallel 16
cmake --install /tmp/nu_mu_stage05_WmLTWo/official-build
```

配置耗时 162.7 s，生成 9.6 s。最初 -j8 构建运行 1147.36 s 后主动切换 -j16；
第一次续编 303.55 s，因 Geant4 ENSDFSTATE 数据环境未设置失败。设置
`G4ENSDFSTATEDATA=/cvmfs/geant4.cern.ch/share/data/G4ENSDFSTATE2.2`
后再续编 448.14 s，构建和安装成功；没有修改物理源码。

187 个 ELF 库只剥离调试符号，合计由 988,734,176 bytes 降为 163,645,184 bytes。
安装目录补充内部头文件符号链接 `include/WaveEventAthenaPool`，指向安装包自身
`src/` 下的同名目录，并设置 ROOT_INCLUDE_PATH；这解决 ROOT 自动解析缺失头文件，
不改变库或算法。所有安装符号链接均指向包内部；`ldd libNtupleDumper.so` 没有
未解析依赖，也没有引用原修改版安装或构建目录。

软件归档：`software/calypso-master-d32b0ff3-el9-gcc13.tar.gz`，
**54,973,160 bytes**，gzip-1 压缩耗时 3.47 s；只在 EOS 留一份，不纳入 Git。
包内 `NU_MU_BUILD_INFO.txt` 记录版本。构建、安装、计时和链接检查证据位于
`/tmp/nu_mu_stage05_WmLTWo/official-*.log`、`official-*.time`、
`official-runtime-ldd.txt`。这些 `/tmp` 产物不保证跨节点或长期保存。

`eos root://eoshome-x.cern.ch quota` 实测当前用户目录逻辑用量 865.93 GB、
额度 1.00 TB、占用 86.59%；全量最终 ntuple 总大小尚未测量。

### 合一环境与 worker

在 fresh shell 中执行：

```bash
source setup_env.sh --official
nu_mu_calypso_report
```

该入口加载 Athena/GCC13，避免混入分析用 GCC15/LCG；软件包解压到本机临时目录。
worker 显式接收仓库和归档路径，不依赖 EosSubmit 传输后的 executable 位置。

每个 job 顺序复制一个 RDO 到 scratch，在本地重建、制作 ntuple、验证，再只将最终
ROOT 文件写回 EOS。xAOD、runtime 副本、诊断 ROOT、临时 JSON 均随 scratch 清理。
已有结果只有再次通过事件数和轨迹验收后才跳过。用与重建 catalog 一致的相对
xAOD 文件名调用 maker，避免同一文件以绝对/相对路径重复登记。

标准命令（全量 nevents=-1；试验使用 100 或 1000）：

```bash
faser_reco.py --isMC --geom TI12MC04 --nevents -1 <local-RDO.root>
faser_ntuple_maker.py --isMC --geom TI12MC04 --CKFTrackType merge \
  --nevents -1 --outfile ntuple.root <local-xAOD.root>
```

## 详细数据与验证

### 200082：100 事件官方基线和线程比较

输入：`200082/rdo/s0014/FaserMC-MC24_Genie_epos_pi-200082-00000-00009-s0014-RDO.root`，
464,059,606 bytes。测试目录 `/tmp/nu_mu_stage06_validation/`；两次重建分别在
`omp1/`、`omp2/`，ntuple 在 `forward/`、`backward/`、`merge/`、`merge_omp2/`。
每目录有程序日志和 GNU time 计时文件。
该输入和下述 200093 输入的原始 CollectionTree 均实测为 10,000 entries；
100/1000-event 测试均为截取输入开头，不是完整文件验收。

| 步骤/模式 | 事件数 | 轨迹数 | forward/backward 来源 | 有轨迹事件数 | 文件大小 bytes | 墙钟 s | 峰值 RSS KiB |
|:---|---:|---:|:---|---:|---:|---:|---:|
| reco OMP=1 | 100 | — | — | — | 未汇总 | 24.47 | 1,009,856 |
| reco OMP=2 | 100 | — | — | — | 未汇总 | 23.98 | 1,015,916 |
| forward | 100 | 19 | 19/0 | 18 | 345,397 | 14.65 | 903,100 |
| backward | 100 | 23 | 0/23 | 21 | 349,922 | 13.10 | 901,940 |
| merge OMP=1 | 100 | 23 | 4/19 | 21 | 349,973 | 14.31 | 902,188 |
| merge OMP=2 | 100 | 23 | 4/19 | 21 | 349,973 | 未单列 | 未单列 |

两次 reco 用户/系统 CPU 时间为 15.38/2.25 s 和 15.39/2.23 s；三个主模式 ntuple
分别为 6.75/2.08、6.79/2.02、6.78/1.85 s。时间包括初始化，不是稳态事件吞吐。
OMP=1/2 的 merge 全部 **527 个分支值相同**（成对 NaN 视为相同）。每配置只运行
一次，未测量统计误差；23.98/24.47 s 不足以证明线程加速。Athena 事件循环仍为
串行，因此正式作业每文件 1 CPU，OMP/OpenBLAS/MKL 均为 1，使用文件级并行。

三个模式及 OMP 对照均为 100 entries/527 branches，schema 名称/class/leaf 类型一致，
事件 ID 对齐 100/100。merge 的 23 条八元组
`(px0,py0,pz0,x0,y0,z0,Chi2,nDoF)` 全部在标记所指来源中找到，缺失 0/23。
六个动量/位置分量及 χ² 有限，nDoF>0。

14 个非轨迹字段在三模式完全一致且未见非有限值：VetoNu0/1、Veto20/21、Timing0、
Preshower0、Calo0 的 charge（pC），VetoNu0/1、Veto20 的 status，truth_pdg
（无量纲），VetoNu0/Veto20_localtime 和 truth_px（原生单位，本阶段未复核单位）。
其余非轨迹字段未逐一做跨模式比较；truth_pdg 是 truth 粒子列表，不作为中微子
味道的直接标签。

### 200093：1000 事件和异常候选归因

输入：`200093/rdo/s0014/FaserMC-MC24_Genie_24_xing_angle_wo_caloNu_epos_pi-200093-00000-00009-s0014-RDO.root`，
464,928,030 bytes。本地复核目录 `/tmp/nu_mu_stage06_validation/run200093/`。
三模式共享同一新 xAOD，仅改变轨迹模式和输出名。

本地 reco 耗时 113.26 s、峰值 RSS 1,044,568 KiB、用户/系统 CPU 93.52/4.95 s；
forward/backward/merge maker 分别耗时 30.21/31.21/29.37 s，峰值 RSS
917,608/917,544/920,384 KiB，用户/系统 CPU 分别为 22.33/2.12、22.86/2.28、
21.54/2.16 s。

| 模式 | 事件数 | 分支数 | 轨迹数 | forward/backward | 有轨迹事件 | bytes | nDoF<=0 轨迹 |
|:---|---:|---:|---:|:---|---:|---:|---:|
| forward | 1000 | 527 | 136 | 136/0 | 132 | 2,918,078 | 0 |
| backward | 1000 | 527 | 170 | 0/170 | 169 | 2,945,991 | 1 |
| merge | 1000 | 527 | 179 | 42/137 | 173 | 2,954,687 | 1 |

schema 相同，ID 对齐 1000/1000，merge 来源八元组缺失 **0/179**，被查关键参数
没有非有限值。比较脚本与文本结果：`compare_200093.py`、`compare_200093.txt`，
位于 `/tmp/nu_mu_stage06_validation/`；完整验证汇总在同目录 `validate_200093.txt`。

事件 `(run,eventID)=(200093,264)` 的 backward 与 merge 都有同一候选：
χ²=32.089717864990234（无量纲），nDoF=-2147483648，nLayers=3，
pz=4363.2275390625 MeV（4.3632275390625 GeV），位置=(-4.127150535583496,44.90804672241211,
13.470000267028809) mm。该事件 backward 仅一条候选，nMeasurements=4；merge
两项 measurement 计数均为 4。forward 无通过 station 覆盖筛选的输出轨迹。

源码 `CreateTrkTrackTool.cxx:95` 对无符号 `track.nMeasurements()` 执行减 5，再转
为 double；小于 5 时会下溢。Athena `FitQuality.h:63` 将 double 自由度取整到 int，
本机以 `size_t n=4` 和 `Trk::FitQuality(chi2, double(n-5))` 实测：
`n-5=18446744073709551615`，存储的 double 自由度约 1.84467e19，
`numberDoF()=-2147483648`，与该事件值一致。`CKF2.cxx` 可保留少测量点的首候选，refit 不执行/失败时
保留原轨迹；dumper 只要求三个 station 有覆盖，并未在序列化前要求正自由度。
因此此异常已存在于 backward 来源，不能归为 merge 生成的新参数或 EOS 损坏。
它不满足现有分析的 nLayers>=7、nDoF>=9；不应把这个低约束候选的 χ²/nDoF 当作
有效拟合质量。生产保持官方值，validator 计数并给出最多 5 个示例，不删事件/轨迹。
该候选也不满足当前分析 pz>100 GeV 的要求。

### 官方字段和日志限制

`Track_nMeasurements` 在 `NtupleDumperAlg.cxx:1674` 的 station/参数筛选前填充，
可能与运动学字段错位。100-event merge 有 20 个事件长度不一致；不能按此分支
索引配对轨迹。当前分析用 nDoF/Chi2，merge 算法直接读取 Track 对象，不读取这个
序列化分支。本阶段不修补官方源码。validator 检查关键拟合向量、isForward 对齐，
记录 measurement 长度差异和非正自由度，不将物理质量切选混入文件完整性验收。
源码中 `Track_hitSet` 也在同一筛选前填充，使用它时存在相同的索引风险；当前仓库
只将其写入输出列，不用于切选。本阶段未另行汇总该字段的错位事件数。

100-event reco 有 WARNING 1167 行、ERROR 9 行；FPE INVALID=127、OVERFLOW=9、
DIVBYZERO=0。INVALID 组件计数：CKF_woIFT/CKF_Back_woIFT 各 21，CKF2/CKF_Back
各 26，StreamxAOD/AthOutSeq 各 11，TriggerWaveformRecAlg 8，VetoWaveformRecAlg 3。
这些是 auditor 计数，不是独立坏事件数。

9 行 ERROR 中，5 行是初始化 Acts layer overlap，z=-1800.4、-1778.9、-1744.65、
-1630.4、-1608.9 mm；其余 4 行来自两次候选拟合失败（1000-step limit/
PropagatorError:3，以及 target/path limit/SurfaceError:1）。100-event merge maker
有 WARNING 11 行、ERROR 5 行，后者为同样的初始化 overlap，三类 FPE 均为 0。
这些诊断在官方普通几何中出现，不是使用了 CaloNu；不能声称退出 0 即证明物理
几何和所有外推无误，也不能把它们直接等同于 Eric 尚未明确的修复。
本阶段沿用用户指定的官方 master，完整几何系统效应、全部 FPE 的逐操作影响及
tracking efficiency/假轨迹率尚未测量。

1000-event 200093 本地 reco 有 WARNING 5642、ERROR 137 行，auditor 最终统计
OVERFLOW/INVALID/DIVBYZERO=77/1563/28；merge maker 为 WARNING 29、ERROR 5 行，
FPE=0/0/7。此样本比 100-event 测试暴露更多异常，因此不能外推“小测试全部 FPE=0”。
日志逐条消息可能限流，不能用打印的组件消息次数替代最终 auditor 计数。
该 merge 中 179 条轨迹的被查数值均有限，289 个事件 measurement 长度不一致，
1 条非正自由度候选；这些验收范围不包括所有 waveform/外推字段。

验证命令（在已加载官方环境的仓库根目录运行，输入路径见上文）：

```bash
python AnalysisZipFramework/submission/validate_merge_ntuple.py \
  --rdo <RDO.root> --xaod <new-xAOD.root> --ntuple <merge.root> \
  --nevents 1000 --logs reco.log merge.log
python /tmp/nu_mu_stage06_validation/compare_200093.py
bash -n setup_env.sh AnalysisZipFramework/submission/run_ntuple_merge.sh
git diff --check
```

## HTCondor 验证与全量生产状态

第一次 1000-event 试投 cluster **1532267**：200082 退出 0；200093 已完成 reco/maker，
但旧 validator 要求 nDoF>0，因上述来源候选退出 1，未转存该测试 ntuple。
完成本地三模式归因后，修订验收规则并复测 cluster **1532514**，两项均退出 0。
其中 200082 验证已有结果后跳过，证明重试路径有效；200093 从 RDO 完整重跑
1000 个事件。两个 EOS 测试文件又在交互节点独立运行 validator，通过验收。

| worker 试验 | stage RDO s | reco s / RSS KiB | maker s / RSS KiB | entries/branches | tracks F/B | 有轨迹事件 | bytes |
|:---|---:|:---|:---|:---|:---|---:|---:|
| 200082，1532267.0 | 2.24 | 129.66 / 1,055,100 | 34.37 / 912,292 | 1000/527 | 39/141 | 170 | 3,051,829 |
| 200093，1532514.1 | 3.86 | 94.86 / 1,040,440 | 26.50 / 898,720 | 1000/527 | 42/137 | 173 | 2,955,001 |

200082 worker 的 reco 用户/系统 CPU=118.41/3.33 s，maker=29.55/2.44 s；
200093 为 82.88/4.17 s 和 20.43/2.89 s。scratch 复制 RDO 系统 CPU 分别
0.68/0.90 s。200082 measurement 长度差异 280 个事件，非正 nDoF=0；
200093 为 289 个事件和 1 条轨迹。后者和本地数值、来源计数一致，文件字节数
略有不同不作为内容完全相同的证明。没有做文件 SHA 或二进制逐字节比较。

200082 首次 worker 日志有 WARNING/ERROR=5683/77（reco）、38/6（maker）；
maker 有一条重复 catalog 路径诊断。相对 xAOD 路径修订后的 200093 worker 为
5642/137 和 29/5；FPE 总计与上文本地 200093 完全相同，已无重复 catalog 路径
诊断。两样本不同，不能仅凭两组 WARNING 数量比较推断修订减少了其他告警。

试验日志：`logs/ntuple_merge_1532267.*`、`logs/ntuple_merge_1532514.*`。
试验 ROOT 位于 `ntuples/merge_probe_stage06/`，是 1000-event 小样本，不能计入
全量输出。worker scratch 已自动清理，没有留存 xAOD。

全量 dry-run 通过后，已提交 **343 个 job，cluster 1532700**，schedd 为
**bigbird24**。提交后首次快照为 Idle=343、Running=0、Held=0；这是排队状态，
不是全量成功证明。每 job：1 CPU、3000 MB memory、5000 MB disk、workday（8 h），
nevents=-1。普通几何清单中每个 RDO 一项，作业 ad 记录 run/tag/segments/Calypso commit。
全量完成数、总事件数、总大小及完整文件性能在此时均**未测量**。
2026-10-28 **13:48:59 CET（UTC+1）** 再查：**Running=343、Idle=0、Held=0**。

```bash
source /usr/share/Modules/init/bash
module load lxbatch/eossubmit
condor_submit -dry-run /tmp/nu_mu_stage06_validation/full.dryrun \
  AnalysisZipFramework/submission/ntuple_merge.sub
condor_submit AnalysisZipFramework/submission/ntuple_merge.sub
condor_q 1532700 -af JobStatus
condor_history 1532700 -af ClusterId ProcId ExitCode
```

必须从仓库根目录提交，以便 descriptor 中 `$ENV(PWD)` 指向本仓库。EOS 挂载可能
暂时缓存“文件不存在”；此次 1532514.1 的 stdout 已在 EOS namespace 中，但本机
挂载暂不可见，使用 `eos root://eoshome-x.cern.ch ls` 与 `xrdcp` 成功读取核实。

## 阶段性结论

官方独立软件可执行普通几何 RDO → reco → merge；两方向均贡献保留轨迹，merge
逐轨迹沿用对应来源的拟合参数。1000-event 200093 中 merge 有轨迹事件 173 个，
backward 169 个、forward 132 个；这只说明本样本的输出覆盖计数，不是带真值分母
和系统误差的中微子效率结论。低约束候选已定位到来源重建与自由度转换路径，不应
因该离群值停止 merge 方向，也不应不经质量选择把它作为物理好轨迹。

## 下一步计划与验收标准

| 具体任务 | 所需输入 | 验收标准 |
|:---|:---|:---|
| 全量完成后统一审计 | 343 项 manifest、Condor history、最终 ROOT | 343 个唯一输出，全部退出 0 或解释重试，逐文件事件数匹配 RDO，关键向量对齐且有限；汇总实际大小、轨迹和异常计数 |
| 同版本物理对照 | 同一批新重建、forward/backward/merge、真值匹配定义 | 同一事件分母，报告 nDoF/层数等质量切选前后计数、效率及不确定度、重复/假轨迹率，解释方向贡献 |
| 官方诊断影响审计 | 固定 master、逐事件日志和相关 waveform/轨迹/外推量 | 区分初始化 overlap、候选失败和输出异常；用数量、单位及参考对照界定物理影响，不以退出码替代 |
| 上游问题反馈材料 | 4-hit 自由度数值复现、measurement 填充行号、固定版本 | 准备最小复现并记录上游修复提交；若改版本，重新做三模式一致性验收 |

CaloNu 几何不在本阶段计划内；Eric 修复答复不是继续当前普通几何官方基线生产的前置条件。
