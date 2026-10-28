# 阶段 05：官方 merge 实现与 RDO 重建流程确认

## 阶段目标

根据 Pawan 提供的两步命令和算法说明，核实官方 Calypso 的实现、输入要求及输出
语义。用户已明确先按官方 master 推进，Eric 所涉修复的最终答复尚未收到。
因此不再把“移植 merge 到 2025 年原生产版本”作为首选路线，而以固定的官方版本
建立统一的重建和 ntuple 基线。

## 工作内容与源码基线

2026-10-28 查询官方仓库 `https://gitlab.cern.ch/faser/calypso.git`：

```bash
git ls-remote https://gitlab.cern.ch/faser/calypso.git refs/heads/master
```

结果为 `d32b0ff3cc4a2dad4abfb1474a82422c3c25b305`。该提交日期为
2026-10-09，标题为 `Merge branch 'ci-opts' into 'master'`。本地 `pawan/master`
指向同一提交；本地 `master` 和 `origin/master` 仍为 `1eb885ae`。
这两个版本的差异仅在 CI 配置，不能把本地 master 名称误当作最新官方版本。

通过官方 GitLab 的固定提交 raw URL 读取 maker、reco、merge 算法及 dumper。
merge 功能引入提交为 `6b4bbb73971b01417cb2c4d0ec44069968e9f348`，作者
Lawson Michael Mccoy，提交日期 2025-11-07，标题
`Including merge tracking option in faser_ntuple_maker`；当前官方 merge 算法文件的
最近一次提交仍是它。官方源码地址示例：

<https://gitlab.cern.ch/faser/calypso/-/blob/d32b0ff3cc4a2dad4abfb1474a82422c3c25b305/Tracking/Acts/FaserActsKalmanFilter/src/MergeTracksAlg.cxx>

已建立独立 detached worktree：

```bash
git -C ../calypso worktree add --detach \
  /tmp/nu_mu_stage05_WmLTWo/calypso-official \
  d32b0ff3cc4a2dad4abfb1474a82422c3c25b305
```

它是源码基线，本阶段尚未在此目录完成独立的官方软件构建。没有切换或覆盖用户
原有 Calypso 分支及安装目录。`/tmp` 为本节点临时空间，后续生产不能直接依赖
worker 看不到的这个绝对路径。

## 详细数据：算法和接口逐项确认

| 项目 | 官方实现与核查结果 |
|:---|:---|
| 命令行 | `--CKFTrackType forward/backward/merge`，默认 `forward` |
| 默认 merge 输入 | `CKFTrackCollectionWithoutIFT`、`CKFTrackCollectionBackwardWithoutIFT` |
| merge 输出集合 | `CKFTrackCollectionMergeWithoutIFT` |
| 主排序 | measurements 数量降序 |
| 同数时排序 | χ²/nDoF 升序，χ²/nDoF 无量纲 |
| 去重阈值 | 与已选轨迹共享的 measurements **> 6**；恰好 6 个不会触发此删除规则 |
| 默认接受策略 | `acceptTrackSeenByOne=True`，允许只在一个方向找到的候选 |
| 拟合行为 | 复制已有拟合轨迹并选择、去重，不做新的联合拟合或参数平均 |
| 来源分支 | `Track_isForward`，C++ `std::vector<bool>`，true=forward，false=backward |

Pawan 的 “Remove any tracks with more than 6 measurements” 应理解为
**删除共享超过 6 个测量点的其他候选**，不是删除总测量点数超过 6 的轨迹。
程序统计匹配时使用 station、layer、side、strip 编号。这里记录实现细节；本阶段
未测量多轨迹事件的误合并率或遗漏率，不能据此宣称去重效率达到某个数值。

merge 中 backward 副本的 TrackInfo fitter 被设为 `Unknown`，dumper 将它标为
false；forward 使用 `KalmanFitter` 标为 true。这个标记记录**算法来源**，不等同于
粒子沿束流还是逆束流运动的物理判定。源码还存在非默认的“双向均找到才接受”
算法，本次沿用 Pawan 命令的默认策略。

## 从 RDO 到 ntuple 的完整流程

Pawan 的示例文件确实存在：

```text
/eos/experiment/fasernu-data0/faser/sim/mc24/genie/200082/rdo/s0014/FaserMC-MC24_Genie_epos_pi-200082-00000-00009-s0014-RDO.root
```

实测文件大小 **464,059,606 bytes**。生产流程为：

1. `faser_reco.py` 读取 RDO，重建 waveform/量能器、tracker clusters、space points、
   segment，并运行 CKF。默认同时生成 3-station 和 4-station 的 forward/backward
   集合；`--noForward`、`--noBackward` 均不能用于本次标准生产。
2. `faser_ntuple_maker.py --CKFTrackType merge` 读取新 xAOD，重算需要的
   GhostBusters 集合，再调用 `MergeTrackCfg`，将 merge 集合交给 NtupleDumper。
   merge 集合在该进程中生成，直接输出 PHYS ntuple。

所以不需要额外运行独立 MergeTracksConfig 脚本，也不需要永久保存带 merge 集合
的第二份 xAOD。独立脚本虽然具备复制输入并添加集合的能力，其独立运行示例硬编码
旧 `FASERNU-03`/条件标签，不能拿来替代 Pawan 给出的标准 maker 命令。

上一阶段确认旧 xAOD 含两套集合，说明它满足 merge 的结构性输入要求；这**不足以
证明旧重建、schema 和当前 runtime 在物理上完全兼容**。依照本次专家反馈，后续
生产采用 RDO → 当前官方重建 → 当前官方 ntuple，不再把“无需重建”作为已确定结论。
从 RDO 起步也不意味着重新生成 GENIE 或 Geant4 样本。

另外以现有 manifest 的输出名将 `-merge-PHYS.root` 替换为 `-RDO.root`，与
`MC/<run>/rdo/<tag>/` 的目录清单比对（4 线程，仅文件名，不读取全部 ROOT）：

| run | 预期文件数 | 找到的对应 RDO 数 | 缺失数 |
|---:|---:|---:|---:|
| 200080 | 45 | 45 | 0 |
| 200082 | 56 | 56 | 0 |
| 200083 | 76 | 76 | 0 |
| 200089 | 19 | 19 | 0 |
| 200093 | 55 | 55 | 0 |
| 200094 | 74 | 74 | 0 |
| 200100 | 18 | 18 | 0 |
| 200139 | 46 | 46 | 0 |
| 200140 | 63 | 63 | 0 |
| 200146 | 15 | 15 | 0 |
| **合计** | **467** | **467** | **0** |

其中 343 个普通几何输入、124 个 CaloNu 输入。此结果证明文件路径齐备，不替代
逐文件内容、事件数及完整性验收；未做 SHA 或复制 RDO。

## 版本、几何及性能边界

- 官方 master 的 `TI12MC04` 在 reco 和 maker 中均映射为 `FASERNU-04`、
  `OFLCOND-FASER-06`，并非旧生产的条件 05。以同一官方版本和配置生成
  forward/backward/merge 才能隔离轨迹模式差异；不能承诺与旧 ntuple 逐字段完全相同。
  `Track_isForward` 是 Pawan 明确说明的正常新增分支，不应视为 merge 接口异常。
- 当前官方 master 不支持 `TI12MCCaloNu`，Pawan 的 200082 普通几何示例不能自动
  外推至 200139/200140/200146。已检查本地远端跟踪分支
  `pawan/CaloNuMCRebase` 的 `d1c8a2b2`：同时有 CaloNu 和 merge 入口；但这不是
  本次确定使用的 master，也未做运行验收。其提交说明中的旧 HITS 数字化兼容问题
  不能直接等同于 Pawan 提到、尚未明确的 Eric 修复。
- 本地当前工作分支是 `Tracking-4ST-Clean/35c48423`，不是官方 master。
  maker、merge 算法 `.cxx/.h` 和安装的 reco 脚本与固定官方版本文本一致；dumper
  有 3 处外推方向差异，另有本地 waveform converter 补丁。因此当前安装的小测试
  不能冒充纯官方构建的最终验收。
  完整源码比较还显示该分支与官方有 59 个文件差异，包括 KalmanFitterTool 等；
  不能通过只覆盖 maker 或 dumper 就宣称整个 runtime 已是官方 master。
- merge 继承 `AthAlgorithm`，不是 `AthReentrantAlgorithm`；reco 中 NumThreads/
  NumConcurrentEvents 设置处于注释状态。设置 `OMP_NUM_THREADS=2` 或申请 2 CPU
  不能证明事件循环已并行。后续须实测 CPU、墙钟及吞吐，优先利用 HTCondor 的
  文件级并行，避免未经验证启用事件并发或占用无效 CPU。

## 20 事件运行验证、执行命令与产物

为了验证两步流程，复用现有已编译环境进行小测试。**这是当前本地库的运行验证，
不是独立官方构建的验收**；三种 ntuple 均使用同一个新重建 xAOD、同一编译库及
固定官方 maker 脚本。三个调用只改变模式及独立输出位置：

```bash
export NU_MU_SKIP_LCG=1
source setup_env.sh
nu_mu_calypso_setup
export OMP_NUM_THREADS=2
cd /tmp/nu_mu_stage05_WmLTWo
faser_reco.py --isMC --geom TI12MC04 --nevents 20 \
  /eos/experiment/fasernu-data0/faser/sim/mc24/genie/200082/rdo/s0014/FaserMC-MC24_Genie_epos_pi-200082-00000-00009-s0014-RDO.root
```

ntuple 命令为以下形式，在 `<mode>/` 子目录分别执行：

```bash
python /tmp/nu_mu_stage05_WmLTWo/calypso-official/PhysicsAnalysis/NtupleDumper/scripts/faser_ntuple_maker.py \
  --isMC --geom TI12MC04 --CKFTrackType <mode> \
  --outfile /tmp/nu_mu_stage05_WmLTWo/<mode>/ntuple.root \
  /tmp/nu_mu_stage05_WmLTWo/FaserMC-MC24_Genie_epos_pi-200082-00000-00009-s0014-xAOD.root
```

使用 `/usr/bin/time` 记录墙钟、峰值 RSS；ntuple 由
`ThreadPoolExecutor(max_workers=2)` 启动两个独立进程进行小规模对照，未启用
Athena 事件多线程。时间包含启动、条件加载及 I/O，不是稳定事件循环性能：

| 步骤 | 退出码 | 事件数 | 文件大小（bytes） | 墙钟（s） | 峰值 RSS（KiB，GNU time %M） |
|:---|---:|---:|---:|---:|---:|
| RDO → xAOD | 0 | 20 | 1,103,231 | 415.28 | 1,020,536 |
| forward ntuple | 0 | 20 | 152,608 | 11.69 | 900,388 |
| backward ntuple | 0 | 20 | 153,895 | 15.36 | 899,108 |
| merge ntuple | 0 | 20 | 153,764 | 11.68 | 900,936 |

三个 ntuple 的用户/系统 CPU 时间分别为 forward **5.30/2.13 s**、backward
**5.52/1.97 s**、merge **5.26/2.15 s**。没有测得启用 OMP=2 后的加速比，不能
把这些数字当作已实现事件多线程的证据。

重建启动明显受 EOS 软件目录 I/O 影响。对本次进程做 8 s 的定向 strace，看到：
Python 目录打开 **1.496228 s**；不存在的扩展模块路径查询 **0.806836 s**、
**0.666391 s**、**0.769416 s**。因此不能从 20/415.28 的整作业吞吐外推正式生产
效率，更不能把初始化延迟解释成 merge 算法慢。原始证据在 `reco.strace`。

PyROOT 验证结果：

- 新 xAOD 的 `CollectionTree` 有 20 entries，具备全部四个 CKF 集合。
- 三个 PHYS 均 `IsZombie=False`、`kRecovered=False`，各 **20 entries / 527
  branches**。逐分支比较名称、class 和 leaf 类型，三种 schema 完全相同。
- 三种模式的 `(run,eventID)` 逐行对齐，差异 **0/20**。
- `Track_isForward` 与 `Track_pz0` 的向量长度差异均为 **0/20**。

| 模式 | 输出轨迹总数 | true 数 | false 数 | 至少有一条输出轨迹的事件数 |
|:---|---:|---:|---:|---:|
| forward | 5 | 5 | 0 | 4 |
| backward | 6 | 0 | 6 | 5 |
| merge | 6 | 3 | 3 | 5 |

merge 保留轨迹的八元组 `(pz0, px0, py0, x0, y0, z0, Chi2, nDoF)`，在
来源标记所指的同事件 forward/backward ntuple 中均能找到相同值，找不到的为
**0/6**。因此本小样本实际验证了两种来源均可贡献，以及来源标记和已有拟合轨迹
副本的对应。逐 hit 重建共享点数及完整去重选择顺序本阶段**未测量**。

逐事件对照以下 14 个非轨迹字段，backward/merge 各自相对 forward 的差异事件数
均为 **0/20**：`VetoNu0_charge`、`VetoNu1_charge`、`Veto20_charge`、
`Veto21_charge`、`Timing0_charge`、`Preshower0_charge`、`Calo0_charge`（pC），
`VetoNu0_status`、`VetoNu1_status`、`Veto20_status`、`truth_pdg`（无量纲），
`VetoNu0_localtime`、`Veto20_localtime`、`truth_px`（保持原生分支单位，单位
本阶段未复核）。比较器将两侧均为 NaN 视作相同，不能以相同替代数值有效性检查。
其余非轨迹字段尚未逐一验证，不能把 14 个字段的结果外推成全部量均无差异。
另外检查上述 14 个字段及全部输出轨迹的六个动量/位置分量，没有发现非有限值；
所有输出轨迹的 χ² 有限、nDoF > 0。因此已检查字段的一致不是靠两侧 NaN 得到。

### 发现并定位 Track_nMeasurements 的填充时机问题

`Track_isForward` 对齐通过，并不代表所有 `Track_*` 向量都已对齐：

| 模式 | Track_nMeasurements 总元素数 | Track_pz0 总元素数 | 长度不相同的事件数 / 20 |
|:---|---:|---:|---:|
| forward | 10 | 5 | 5 |
| backward | 10 | 6 | 4 |
| merge | 13 | 6 | 4 |

forward 异常 eventID 为 **0、3、5、7、15**，每个事件 `Track_pz0` 长度 0、
`Track_nMeasurements` 长度 1。backward 为 **0、3、7、15**，同样是 0 对 1。
merge 为 **0、3、7、15**，对应长度分别是 **0 对 1、0 对 2、0 对 2、0 对 2**。

原因已在固定官方源码定位：`NtupleDumperAlg.cxx:1674` 先向 m_nMeasurements
push_back，随后才在 1676 行按三个 tracking station 的覆盖筛选轨迹，1681 行还
可能因上下游参数缺失 continue；其他运动学字段和来源标记在这些筛选之后填充。
因此被筛掉的候选仍会留下 measurement 计数。当前本地 dumper 该段与官方一致。
这不是本次 3/4-station 来源混用，也不是 Track_isForward 标记失效。

不能直接按索引把此分支和输出轨迹配对。merge 排序读取 Track 对象的 measurements，
不读取这个 ntuple 分支；本现象不等于 merge 选择算法失效。上述来源验证已改用
长度对齐的六个运动学分量及 χ²/nDoF 两个字段，6 条轨迹全部通过。正式对照前应
将 measurement 计数的填充移至同一轨迹筛选之后，或明确排除此分支；修复必须在
三种模式中一致应用并验证，不能静默把数组错位当作物理差异。本阶段只定位并记录，
没有修改固定官方源码。

日志仍有重建 warning：WaveformClock 读句柄缺失、HepMC signal vertex 无效、部分
space-point intersection failed；reco 的 FPE INVALID 计数为 **19**，OVERFLOW/
DIVBYZERO 均为 **0**。三种 ntuple 的三类 FPE 计数均为 **0**。本阶段尚未完成
warning 对物理量影响的逐事件归因；这是正式生产验收待办，退出码 0 不等于该项
通过。不能把这些现象直接归为尚未收到细节的 Eric 修复。

日志已将 19 次 INVALID 定位到执行组件：四个 CKF（CKF2、CKF_Back、CKF_woIFT、
CKF_Back_woIFT）各 **4 次**，TriggerWaveformRecAlg **1 次**，StreamxAOD 与
AthOutSeq 各 **1 次**；覆盖日志事件索引 **0、3、4、5、7、15**。这些是 auditor
记录次数，含输出序列记录，不能解释成 19 个独立坏事件。部分 CKF 告警附近明确
记录候选测量点不足、refit 未执行或失败；精确浮点操作及全部物理影响尚未定位。

所有测试产物位于 `/tmp/nu_mu_stage05_WmLTWo/`：`reco.log`、`reco.time`、
`reco.strace`、上述 xAOD 和三个模式目录中的 `ntuple.root`、`run.log`、`run.time`。
不复制到 EOS，不纳入 Git；可重现命令和实际汇总数据保存在本报告。临时 xAOD
不是最终留存结果，后续批量在 worker scratch 使用后清理。

## 阶段性结论

Pawan 的描述与官方 merge 实现一致，关键去重含义已明确；功能已在官方 master
中，无需回移到旧版本。现有安装的 RDO → 新 xAOD → 三种 ntuple 流程已在 20
事件跑通，merge 的 6 条轨迹确有 3 条来自每种来源。这个样本只支持接口和来源
对应结论，不能宣称 merge 的物理效率优于 backward，更不能因计数相同而放弃
merge。下一阶段固定纯官方构建，检查告警并扩大同版本对照后再判断物理性能。

## 下一步计划与验收标准

| 具体任务 | 所需输入 | 验收标准 |
|:---|:---|:---|
| 固定官方 runtime | d32b0ff3 官方 worktree、已有 CVMFS Athena/依赖 | 构建与源码可追溯，不混入现有分支的局部库或补丁 |
| RDO → xAOD → merge 小样本 | 上述 200082 RDO、TI12MC04、官方条件 06 | reco/maker 均成功，事件 ID 对齐，轨迹来源向量长度与轨迹数一致，逐轨迹检查来源与去重 |
| 物理量有效性及告警归因 | 同一小样本、reco 日志、逐事件 waveform/truth/space-point 数据 | 定位 19 个 FPE INVALID 及告警的算法来源和受影响事件，区分 MC 缺失元数据、正常候选失败与真实物理量异常，给出数量及影响证据 |
| 同版本三种模式对照 | 同一个新重建 xAOD、完全相同的其他参数 | schema 相同，非轨迹量一致；测量轨迹效率、重复率和方向贡献，记录不确定度 |
| 修正或隔离 measurement 分支错位 | 官方 dumper 的填充位置、上述 20 事件参考 | 在三种模式中验证 Track_nMeasurements 与运动学和来源向量长度、索引均对应；任何补丁单独记录，不冒称无修改的官方产物 |
| 批量包装和性能测试 | 通过验收的完整 slice、测得的 CPU/RAM/disk 需求 | HTCondor 单 job 串联 reco 与 maker，中间 xAOD 仅留 worker scratch，成功后仅转存最终 ntuple |
| 核实 Eric 修复及 CaloNu 路线 | Pawan 后续答复、准确提交/分支 | 确定修复内容与所影响样本；CaloNu 必须使用正确几何并单独验收，不能替换成 MC04 |

本阶段不提交 467 个全量作业，不产生新的物理效率结论；软件实现能确认合并策略，
实际效率提升、假轨迹率和完整 slice 性能须由后续同版本对照测量。
