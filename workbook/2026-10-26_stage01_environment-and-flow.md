# Stage 01：运行环境、已有分析流程与 MC 样本盘点

## 阶段目标

配置可重复加载的运行环境；根据仓库代码和 `docs/` 中的论文，明确已有分析的研究目标、数据、选择方法、输出和当前结论；在 EOS 中定位可用于 forward/backward/merged track collection 研究的 νμ MC。

## 工作内容

### 1. 环境配置

当前终端实测为 `lxplus908.cern.ch`，GPU 为 `Tesla T4`，显存 `15360 MiB`，驱动 `610.57.04`。CVMFS 的 LCG_109 路径 `/cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt` 可读，`root-config` 报告 ROOT `6.38.00`；`cmake` 和 `condor_submit` 可执行。当前主机名不是字面上的 `lxplus-gpu`，但 GPU 实际可用。

新增根目录脚本 [`setup_env.sh`](../setup_env.sh)。使用：

```bash
source setup_env.sh
nu_mu_env_report
nu_mu_configure
nu_mu_build
nu_mu_run --input-dir /path/to/ntuples -o /path/to/result.root --isMC -j 4
```

脚本统一设置仓库、build、EOS 和 ROOT 快照变量，加载 LCG_109，提供 `nu_mu_configure`、`nu_mu_build` 和 `nu_mu_run` 函数。`nu_mu_run` 自动进入 `build/`，确保相对路径 `config/*.yaml` 可用；脚本不会自动重新构建 Calypso 或本分析程序。若以后需要某个兼容的预编译 Calypso，可在 source 前设置 `FASER_CALYPSO_SETUP`。

验证命令及结果：

```bash
bash -n setup_env.sh
source setup_env.sh
nu_mu_configure
nu_mu_build
```

结果为 CMake 配置成功、`[100%] Built target analysis`，build 目录生成 6 个 YAML 配置文件。第一次从仓库根目录直接运行二进制时，程序报 `Config file not found: config/definitions.yaml`；修正运行函数后，根目录调用也能正常找到配置。这是脚本固定工作目录的直接依据。

### 2. 程序完整流程

程序入口为 `AnalysisZipFramework/analysis.cxx`，核心实现在 `source/Analyis.cxx`：

1. 解析 `--run/-r` 或 `--input-dir`，以及 `--isMC`、`--isAsimov`、`--no-reduced-charge`、`-j [n]` 和各 YAML 配置路径。目录模式只读取目录第一层 `.root` 文件，并从 `nt` 树读取 run number。
2. 读取 `file_config.yaml`、`grl_config.yaml`、`output_columns.yaml`、`definitions.yaml` 和 `cuts.yaml`。当前配置统计为 624 个 run 条目、35 个 definition、30 个 cut、44 个附着 histogram；输出配置保留 442 个公共列、5 个 MC 列和 18 个 data 列，默认保存所有运行时定义列。
3. 建立 ROOT `TChain`/`RDataFrame`。输入兼容层把旧 `VetoStN_*` 映射为 `VetoN_*`，缺失的 `Veto11_*` 回退到 `Veto10_*`，2024 的 `CaloLo*` 在缺少单读出时回退为 `Calo*`。
4. reduced VetoNu charge 按 aux waveform、输入 NTUP 原生列、或 `--no-reduced-charge` 的 raw charge 顺序选择。aux 模式只读取 `run`、`event` 和两个 charge 分支，建立 `(run,eventID)` 查找表；data 还生成 GRL 的 `GoodTimes/ExcludedTimes`。
5. 依 `definitions.yaml` 文件顺序创建 truth、几何、timing、leading-track 和质量变量。MC truth 使用 `SafeAt(truth_*,0)`；leading track 取 `Track_pz0` 最大者。`data_type=MC` 的 truth cuts 在 Asimov 模式跳过，`ASIMOV` definitions/histograms 仍适用于 MC。
6. 依 `cuts.yaml` 顺序懒惰预订 histogram 并逐个 `Filter`。MC 的主要物理选择是：去除 CaloNu PMT truth 区域、CC、`|truth_pdg[0]|=14`、在 FASERν/lead target、truth `r<100 mm`、truth `pz>100 GeV`、至少一个 long track，然后施加下游 scintillator、track 质量和 VetoNu charge 选择。
7. 所有 action 在一次 ROOT event loop 中触发：`nt` snapshot、`eventID_pass`、cutflow、meta 和 histogram 同时写出。`eventID_pass` 先写临时 ROOT 文件，随后以 fast basket copy 合并，临时文件删除。`-j` 调用 `ROOT::EnableImplicitMT`。

当前程序的研究边界是“选择、cutflow、变量和响应输入生产器”。代码中没有论文所需的二维 binned likelihood、migration matrix unfolding、HEPData 协方差处理、flux 或 cross-section 最终解释；这些必须作为后续阶段实现或接入。

### 3. 论文对应的物理目标与方法

参考文件：[`docs/Electronic_2D_measurement_PRD-2.pdf`](../docs/Electronic_2D_measurement_PRD-2.pdf) 和 [`docs/Electronic_2D_measurement_internal_note-6.pdf`](../docs/Electronic_2D_measurement_internal_note-6.pdf)。论文目标是测量 FASER 电子探测器中 CC `νμ+ν̄μ` interaction yield，真值空间为 `(yν,-L/Eν)` 的 `5×6=30` 个 bin；重建空间使用 muon rapidity `yμ` 和 `qμ/p'μ`，其中 `p'μ=pμ/0.8`。二维 likelihood 同时处理效率、bin migration、背景和系统学，再将 unfolded yield 解释为 SM cross-section 假设下的 flux，或模拟 flux 假设下的 CC cross-section。

论文数据为 Run 3、`√s=13.6 TeV`、`186±4 fb⁻¹`，其中 2022/2023/2024 分别为 `37/29/120 fb⁻¹`。标称 flux 使用 EPOS-LHC（light hadron）和 POWHEG+PYTHIA（charm）；GENIE 3.04.0 使用 Bodek–Yang，Geant4 标称 FTFP_BERT+G4NDL，替代项包括 FTF_BIC、FTFP_INCLXX、FTFP_BERT_HP、JEFF-3.3 和 ENDF/B-VIII.0。每个生成器、几何和 π/K/charm 模式的模拟积分亮度为 `10 ab⁻¹`；FASERν 使用 `s0014`，CaloNu 使用 `s0015`。论文最终采用三站 backward tracking，内部笔记明确写为 `CKFTrackCollectionBackwardWithoutIFT`。

选择阈值与本仓库 `cuts.yaml` 一致：reduced VetoNu 每层 `<30 pC`，Veto20/21 各 `>40 pC`，Timing `>20 pC`，Preshower 每层 `>2.5 pC`，track hits `≥14`、layers `≥7`、`χ²/nDoF<15`、`pμ>100 GeV`、各 tracking station `r<95 mm`、Veto `r<95 mm`、VetoNu `r<120 mm`、`θ<25 mrad`。论文报告 tracking efficiency 为模拟 `98.3%`，data 2022–2023/2024 为 `97.2%/96.5%`，因此赋予 `1.8%` tracking uncertainty。

### 4. 端到端 MC 验证

输入为 `/eos/experiment/fasernu-data0/faser/sim/mc24/genie/200080/bck/s0014/` 下一个 PHYS ROOT 文件（`nt` 树 `10000` entries，文件名模式 `FaserMC-MC24_Genie_sibyll_pi-200080-00000-00009-s0014-PHYS.root`）。通过 `/tmp/nu_mu_stage1_input/sample.root` 软链接运行：

```bash
source setup_env.sh
nu_mu_run --input-dir /tmp/nu_mu_stage1_input \
  -o /tmp/nu_mu_stage1_output.root --isMC -j 2 -v
```

实际 cutflow 为：

| cut | all | passed | efficiency |
|---|---:|---:|---:|
| Remove CaloNu PMT region | 10000 | 10000 | 100.000% |
| CC events only | 10000 | 7560 | 75.600% |
| nu_mu only | 7560 | 7559 | 99.9868% |
| In FASER Nu Box or Lead Block | 7559 | 3208 | 42.4395% |
| Truth dec r < 100 mm | 3208 | 1499 | 46.7269% |
| Truth pz > 100 GeV | 1499 | 1319 | 87.9920% |
| At least one long track | 1319 | 723 | 54.8143% |
| Track/scintillator selections through θ<25 mrad | 723 | 381 | 52.6971% |
| VetoNu0 and VetoNu1 reduced charge | 381 | 347 | 91.0761% |

产物 `/tmp/nu_mu_stage1_output.root` 大小为 `1,401,470 bytes`，包含 `nt` `347` entries/`386` branches、`eventID_pass` `10000` entries/`22` branches、`cutflow` `20` rows、`meta` `1` row 和 `42` histograms。该结果证明环境、配置、MC truth 分支、reduced charge 原生列、多线程和输出链路均可运行；它不是完整物理测量结果，样本只有一个 10,000-event 文件。

## MC track collection 盘点

仓库 `file_config.yaml` 将 MC 指向 `root://eospublic.cern.ch//eos/experiment/fasernu-data0/faser/sim/mc24/genie/...`；本地挂载对应 `/eos/experiment/fasernu-data0/faser/sim/mc24/genie/`。论文内部笔记给出 nominal νμ 相关 run：FASERν 的 EPOS π/K/charm 为 `200082/200083/200089`（下降 crossing angle）和 `200093/200094/200100`（上升 crossing angle），CaloNu 为 `200139/200140/200146`；这些目录均有 PHYS ROOT 和 Calypso ntuple 日志。

track collection 的直接证据来自 ntuple 日志，而不是 PHYS ROOT branch 名：例如

- `/eos/experiment/fasernu-data0/faser/sim/mc24/genie/200080/log/s0014/*PHYS.ntp.log` 中同时出现 `Backward = False` 与 `faser_ntuple_maker.py ... --merge 10`，可作为 forward/default 重建的候选证据；
- 同一目录的部分 slice 日志出现 `--merge 10 --backward` 和 `Backward = True`，可作为 backward 候选证据；
- 论文和内部笔记把分析样本描述为 `CKFTrackCollectionBackwardWithoutIFT`，且只用三座 tracking stations。

目前已确认 `--merge 10` 是 ntuple 文件合并参数（输出文件也按 `00000-00009` 等十文件区间命名），但尚未在 ROOT 元数据中测得一个明确名为 “merged track collection” 的独立 collection；也没有证据证明同一输出目录下所有 slice 都是同一 collection。不能把 `--merge 10` 直接等同于 merged tracking collection。下一阶段应先把每个 ntuple 日志的 slice、输出文件和 collection 一一对应，再选取同一配置的 forward、backward、merged 三套样本；若 EOS 没有现成 homogeneous merged 样本，则用 CVMFS 中已编译的 Calypso/`faser_ntuple_maker.py` 只重新生成所需 NTUP，不保存 xAOD 或其他中间文件。

## 阶段性结论

1. 运行环境已固定为可 source 的 `setup_env.sh`，并已在 GPU 可用的 lxplus 节点完成 CMake 构建和 2 线程端到端 MC 验证。
2. 已有程序可靠地复现论文的 MC truth、track、scintillator 和 VetoNu candidate selection，并能以单 event loop 输出 cutflow、histograms、event IDs 和精简 NTUP。
3. 当前仓库尚未实现二维 unfolding 和最终 flux/cross-section 统计推断，因此目前唯一新的实测物理量是上述 10,000-event 样本的阶段性 cutflow；不能将其表述为论文测量结论。
4. EOS 中存在与论文一致的 FASERν/CaloNu GENIE PHYS MC，日志确认 forward/default 与 backward ntuple maker 选项都出现过；merged track collection 尚未被直接确认。

## 下一步计划与验收标准

1. 建立 MC 日志到 PHYS 文件的映射表，输入为各 run 的 `log/*PHYS.ntp.log`、`bck/*PHYS.root` 和 `nt` branch schema；验收标准是每个候选文件唯一标注 generator、geometry、sim tag、forward/backward/merged 状态。
2. 在同一 10k-event 或等价小样本上比较三种 collection 的 track multiplicity、longTracks、`pμ`、`θ`、径向变量和完整 cutflow；验收标准是给出带单位的表格、统计误差定义和可复现命令。
3. 优先用已有 PHYS/NTUP 做 response 输入，不复制 xAOD；只有 collection 缺失且确认物理必要时才提交 HTCondor 重建。验收标准是 EOS 仅保留精简 NTUP/汇总结果，并记录作业资源、吞吐和失败原因。
4. 设计 30 truth bins 与重建 bins 的 response/migration 文件，随后实现 binned likelihood/unfolding；验收标准是 closure test 在独立 MC 上恢复 truth yield，并报告 covariance 与系统变体。
