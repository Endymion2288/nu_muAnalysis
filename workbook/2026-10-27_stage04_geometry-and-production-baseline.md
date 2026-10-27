# 阶段 04：几何依赖与“仅切换 merge”生产基线核查

## 阶段目标

以现有 forward/backward ntuple 为基准，只替换轨迹集合为 merge；保持输入、
几何、条件、波形转换、truth 定义和输出 schema。核实几何选项的实际依赖，整理
需要向原生产者确认的信息。本阶段只读检查日志、源码和已有 ROOT，不提交全量作业。

## 工作内容与输入配置

输入根目录为 `/eos/experiment/fasernu-data0/faser/sim/mc24/genie`（下称 `MC`）。
逐 run 检查 `MC/<run>/log/<tag>/*PHYS.ntp.log`，以 4 个线程读取，共 467 份日志。
候选基准输出为 `MC/<run>/bck/<tag>/*PHYS.root`；输入为相同 run 的
`rec/<tag>/*xAOD.root`。文件清单见 `AnalysisZipFramework/submission/merge_manifest.tsv`。

检查 `../calypso` 的当前源码、安装目录和历史提交，重点为：

- `PhysicsAnalysis/NtupleDumper/scripts/faser_ntuple_maker.py`
- `DetectorDescription/GeoModel/FaserGeoModel/python/FaserGeoModelConfig.py`
- `Calorimeter/CaloDetDescr/CaloNuGeoModel/`
- `Tracking/Acts/FaserActsKalmanFilter/{src/MergeTracksAlg.*,python/MergeTracksConfig.py}`

## 详细数据与验证结果

### 原生产记录

| run | tag | 日志数 | 无 backward 参数 | 有 backward 参数 | 记录的源码提交 | 几何选项 |
|---:|:---|---:|---:|---:|:---|:---|
| 200080 | s0014 | 45 | 26 | 19 | 6d6ab70b | TI12MC04 |
| 200082 | s0014 | 56 | 28 | 28 | 6d6ab70b | TI12MC04 |
| 200083 | s0014 | 76 | 31 | 45 | 6d6ab70b | TI12MC04 |
| 200089 | s0014 | 19 | 6 | 13 | 6d6ab70b | TI12MC04 |
| 200093 | s0014 | 55 | 17 | 38 | 4a0e366b | TI12MC04 |
| 200094 | s0014 | 74 | 29 | 45 | 4a0e366b | TI12MC04 |
| 200100 | s0014 | 18 | 3 | 15 | 4a0e366b | TI12MC04 |
| 200139 | s0015 | 46 | 24 | 22 | 1ec47efe | TI12MCCaloNu |
| 200140 | s0015 | 63 | 30 | 33 | 1ec47efe | TI12MCCaloNu |
| 200146 | s0015 | 15 | 10 | 5 | 1ec47efe | TI12MCCaloNu |
| **合计** | | **467** | **204** | **263** | | |

467 份日志均有 `Execution succeeded`，均记录 `OFLCOND-FASER-05`。
原命令使用 `--files 1 --merge 10 --isMC`、`Use IFT = False`。这里的
`--merge 10` 是输入 segment 分组，**不是**轨迹 merge 模式。

三套构建均标作 Calypso 22.0.49、el9/gcc13，实际构建来源不同：

| 源码记录 | 构建时间（原日志字符串） | 文件数 |
|:---|:---|---:|
| pull origin master: Fast-forward/6d6ab70b | 2025-08-05T1957 | 196 |
| master/4a0e366b | 2025-09-08T1233 | 147 |
| CaloNuMC/1ec47efe | 2025-09-17T1439 | 124 |

公共 `log/` 中两种模式混杂，不能据此把日志直接一一归属于 `bck/` 的生产。
这不证明 `bck/` 文件混用了模式；必须确认权威基准及其日志对应关系。

### 几何选项的含义与缺少的组件

| 原选项 | GeoModel 标签 | 原条件标签 | 特殊要求 |
|:---|:---|:---|:---|
| TI12MC04 | FASERNU-04 | OFLCOND-FASER-05 | 原普通几何配置 |
| TI12MCCaloNu | FASERNU-CALONU | OFLCOND-FASER-05 | CaloNuMC 分支的 CaloNuGeoModel、GDML 和对应几何数据库 |

历史 `FaserGeoModelConfig.py` 在 CALONU 时加载 `CaloNuGeometryCfg`，替代普通的
`EmulsionGeometryCfg`。`CaloNu00.gdml` 包含四个 calorimeter 模块、PMT 和前后钨块；
这改变探测器材料与几何描述，不能用普通几何或字符串别名替代。GDML 中的尺寸是
模型配置，不是本阶段测得的探测器尺寸。

当前安装不接受 `TI12MCCaloNu`，且缺少 `libCaloNuGeoModel*`、
`python/CaloNuGeoModel` 和 `XML/CaloNuGeoModel`。因此问题是 **Calypso 分支及构建
内容不匹配**，不是另需一个独立分析程序，也不能只看“22.0.49”版本号。
三个历史源码提交均可在本地 Git 读取。原日志的安装路径
`/afs/cern.ch/work/f/fasermc/mc24/{s0014,s0015}/run/setup.sh` 当前均不存在。
已有 CVMFS 基础软件可用；归档构建及特殊数据库覆盖是否仍可访问需原生产者确认。

### ROOT 与数值对照

代表输入为 200080、200093、200139 各自 `rec/<tag>/` 中
`*-00000-00009-<tag>-xAOD.root`。三个文件各有 **10,000 个事件**，均包含：

```text
CKFTrackCollection
CKFTrackCollectionBackward
CKFTrackCollectionWithoutIFT
CKFTrackCollectionBackwardWithoutIFT
```

因此这些代表输入已经具备 merge 所需的 forward/backward 轨迹，无需为切换模式
重新生成 GENIE、Geant4 或重建 xAOD。其余 464 个文件的集合内容本阶段未逐文件读取。

| 已检查文件 | nt 事件数 | 分支数 | 当前 probe 相比新增分支数 |
|:---|---:|---:|---:|
| 200080/bck/s0014 首文件 | 10,000 | 426 | 101 |
| 200093/bck/s0014 首文件 | 10,000 | 487 | 40 |
| 200139/bck/s0015 首文件 | 10,000 | 487 | 40 |
| stage03 的 200080 probe | 100 | 527 | — |

probe 路径为
`/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/merge_probe_stage03/200080-100events.root`，
大小 **349,026 bytes**。相对三个基准，未发现缺少的分支名，但增加了
`Track_isForward`、`Track_nMeasurements`、`*_tover`、部分 truth 字段等。
这只比较了分支名，没有证明类型、定义或数值全部一致。

进一步对齐 200080 基准首文件和 probe，**100/100** 个 `(run,eventID)` 相同。
逐事件检查以下 **14 个共有字段**，每个字段的差异事件数均为 **0/100**，
最大绝对差均为 **0**：

- 电荷：`VetoNu0/1_charge`、`Veto20/21_charge`、`Timing0_charge`、
  `Preshower0_charge`、`Calo0_charge`（源码单位 pC）。
- 状态：`VetoNu0/1_status`、`Veto20_status`（无量纲）。
- 时间：`VetoNu0_localtime`、`Veto20_localtime`（按分支原生单位比较，单位未复核）。
- truth：`truth_pdg`（无量纲）、`truth_px`（按分支原生单位比较，单位未复核）。

`truth_vx/vz` 未完成共有字段比较，不能列为通过。其他字段、CaloNu 数值、完整
slice 的等价性、重建效率与性能均**未测量**。14 个字段的一致不能外推为全量兼容。

### merge 的实际行为及版本差异

当前默认 `acceptTrackSeenByOne=True`：合并两个 WithoutIFT 候选集合，优先保留
measurement 数更多的轨迹，同数时按 χ²/nDoF 更小排序；选中一条后删除与它共享
**超过 6 个 hit** 的候选。源码判断是 `> 6`，不是部分注释写的“6 个及以上”。
这是已拟合轨迹的选择与去重，不是动量平均或重新拟合。输出为
`CKFTrackCollectionMergeWithoutIFT`。

历史三套基线 maker 只有默认 forward 和 `--backward`，没有 MergeTracksAlg。
为满足用户要求，应在确认的原基线上最小移植 merge 算法及入口，保持原 dumper。
当前分支默认条件已变为 `OFLCOND-FASER-06`，还改变了输出 schema 和部分 truth
实现；stage02 的 waveform 兼容补丁也不是原生产基线的一部分。仅把当前条件覆盖
回 05 不足以实现“只改模式”。先前 probe 只能视作运行验证，不能作为等价生产结果。

## 执行命令与证据位置

几何映射和分支依赖可复核：

```bash
git -C ../calypso show 1ec47efe:PhysicsAnalysis/NtupleDumper/scripts/faser_ntuple_maker.py
git -C ../calypso show 1ec47efe:DetectorDescription/GeoModel/FaserGeoModel/python/FaserGeoModelConfig.py
git -C ../calypso ls-tree -r --name-only 1ec47efe Calorimeter/CaloDetDescr/CaloNuGeoModel
git -C ../calypso show 6d6ab70b:PhysicsAnalysis/NtupleDumper/scripts/faser_ntuple_maker.py
git -C ../calypso show 4a0e366b:PhysicsAnalysis/NtupleDumper/scripts/faser_ntuple_maker.py
```

原始命令和 release 证据分别位于三个代表 run 的
`log/<tag>/*-<run>-0000-PHYS.ntp.log`。日志统计用 Python `Path.glob` 枚举上述
467 份文件、`ThreadPoolExecutor(max_workers=4)` 读取，提取含 maker 和 `--geom`
的命令，按有无 `--backward` 计数。ROOT 检查在以下环境中执行：

```bash
export NU_MU_SKIP_LCG=1
source setup_env.sh
nu_mu_calypso_setup
```

使用 PyROOT 的 `TFile.Open`、`Get('nt')`、`GetEntries()`、`GetListOfBranches()`
比较 schema，逐事件读取共有字段并计算不等次数和最大绝对差。读取 xAOD 的
`CollectionTree` 分支核实轨迹集合；未复制输入或生成新的 ROOT/JSON。
本阶段唯一新增持久产物是本报告；未测量本次只读扫描的吞吐和峰值内存。

## 阶段性结论

几何特殊性由原 MC 探测器配置决定，与选择 merge 正交；必须逐样本保持原几何。
当前构建不满足“只改轨迹模式”，原因已有版本、组件和 schema 证据，不是 MC
缺失或 merge 物理效率异常。已有输入支持直接合并轨迹；本阶段未产生新的物理
选择效率结论。后续应固定原生产基线，再做最小 merge 移植，避免把软件变化误判
为 forward/backward/merge 的物理差异。

## 需向原生产者统一确认

1. 请指定本分析应对齐的权威 forward/backward ntuple 路径、每类至少一个完整参考
   文件，以及它们对应的 ntuple maker 命令和生产日志。公共 log 混有两种模式，
   需要确认与 bck 文件的对应关系。
2. 日志中三套构建是否就是最终生产版本？是否包含未提交修改？请提供仍可访问的
   已编译安装及 setup 路径；若无归档安装，则确认准确源码及本地补丁、完整配置。
   特别请注明 CaloNu 使用的几何数据库、CaloNu00.gdml 是否有非仓库版本，条件
   数据库/校准是否有本地覆盖，以及是否有特殊 waveform converter。
3. 若已有与上述生产完全配套的 merge 实现，请给出分支/提交及调用方式；若没有，
   可以由本仓库在原基线上接入当前 MergeTracksAlg，不要求重新生产 MC。

## 下一步计划与验收标准

| 具体任务 | 所需输入 | 验收标准 |
|:---|:---|:---|
| 锁定每组生产基线 | 权威参考、对应日志、准确构建或补丁与几何/条件资源 | 三组源码、schema、几何、条件及模式可一一追溯 |
| 先重现原 forward/backward 小样本 | 同一 xAOD、上述 runtime | 事件 ID、分支名/类型、非轨迹字段及原模式轨迹字段与对应基准一致；差异须定位 |
| 最小接入 merge，分别测试两种几何 | 验收通过的基线、现有 merge 源码 | 只替换轨迹来源；schema 与基线一致，非轨迹物理量一致；逐轨迹验证排序、去重和外推，允许轨迹依赖量按模式变化 |
| 完整 slice 的 HTCondor 验证，再全量生产 | 两类几何的代表 slice、明确资源配置 | 完整事件数、ROOT 完整性、数值检查通过；记录墙钟秒数、events/s 和峰值 MB，验证实际多线程与 I/O 配置后提交 467 个 job |

全量仍使用 HTCondor；小样本验收前不扩大生产。只保存最终 ntuple 和必要的中文
报告/日志，不留 xAOD 副本或每 job 重复的 JSON。
