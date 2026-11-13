# 阶段 201：几何旋转与隔离 smoothing 后的 merge/duplicate 复查

## 阶段目标与当前状态

使用 `/eos/home-x/xcheng/FASER/geoRotation_calypso` 的现成构建，重做阶段
09/10/17/20 的 forward、backward、merge 同源对照，新增 duplicate tracks
的独立定义及测量。首先完成小样本验证，再通过 HTCondor 处理全部输入。

本次准备阶段已经完成：343-event 全链验证、原生 C++ cutflow 对照、坐标约定
核对、重复径迹指标和固定旧版闪烁体输入的对照均已实现。全量 HTCondor
cluster **9717383** 已提交；全量效率、重复率、旧 89 例复查及全量性能均
**未测量完成**，下文不将试跑结果外推为全样本结论。

## 软件、输入和物理约定

- Calypso HEAD：`88c457c1e4bf4154e67b96114ee8e7020d9b1a97`，现成安装的
  CKF library mtime 为 2026-11-13 14:51。工作树含本地修复，**不能仅凭 HEAD
  重现本次软件**。完整状态和编译库字节/时间记录见
  `stage201_tracking/software_provenance.json`；跟踪文件 diff 见
  `stage201_tracking/calypso_local_changes.patch`。修改及未跟踪源码另存于
  `software/stage201_tracking/local_sources.tar.gz`。
- 固定 Athena 24.0.41、GCC 13、TI12MC04/FASERNU-04、OFLCOND-FASER-06，
  without-IFT、无 CaloNu。四套默认 CKF 均显式设置
  `IsolateCandidateSmoothing=True`；energy loss/scattering 均开启，bypass
  refit/fixed truth hits/electron hypothesis/seed override 均关闭。没有重新编译
  或修改外部 Calypso 工作树。
- 运行库冻结为 `software/stage201_tracking/calypso_reco_runtime.tar.gz`。
  移除重建不调用的 `libFaserGeant4.so`、`libFaserGeant4Lib.so`，保留 tracking、
  波形、ntuple 和字典的现成二进制。原始归档为 397,898,610 bytes，最终归档和
  解包字节数详见 provenance；不做 SHA 或全数据散列。
- 输入沿用 `AnalysisZipFramework/submission/merge_manifest.tsv` 全部 **343 RDO**，
  七个 run 为 200080、200082、200083、200089、200093、200094、200100。
  恢复旧流程缺失的原 index 291（200094/00400–00409，10,000 events），预计总计
  **3,384,987 events**；与旧版直接比较限定原来的 342 个共同文件。全部 RDO
  实测合计 **290,908,426,402 bytes**，最大文件 **1,700,260,410 bytes**。
- 不加 flux/luminosity 权重。200080 为 SIBYLL 替代样本；同时报告排除该 run
  的 nominal 分组和逐 run 统计。不以混合样本的未加权效率代替标称物理产额。

## 坐标与额外版本差异

源码实际使用的内部变换为 `(x',y',z')=(z,y,-x)`，束流方向在内部 x 轴，
不同于按口头轴名称理解几何。ntuple 的 Track 首点动量保留内部坐标，
中微子 `truth_*` 输入仍是原坐标。读取比较时在 RDataFrame 中作
`px=-pz'、py=py'、pz=px'`，然后使用原 YAML 的最高 pz leading track 和原
角度定义。`Track_r_atMaxRadius` 已在 dumper 内使用 `hypot(y',z')`；外推
半径保持原定义，Timing 的 y 也不改变。没有把新内部 pz 当作束流动量施加 cut。

另外发现新旧版本间 **波形重建源码不同**，包括
`WaveformReconstructionTool.cxx`，所以新旧完整选择差异不能全部归因于
旋转或 smoothing。343-event 样本的 truth/ID 共 7 个输入逐值相同；但
VetoNu0/1 reduced charge 分别有 **32/33 events** 不同，有限最大绝对差为
**183.9868/126.8893 pC**。Veto20/21 charge 分别有 **182/177 events** 不同；
Preshower 的比较存在非有限值。逐列记录见
`stage201_tracking/pilot343_old_nontrack_comparison.json`。

为此保留每个 truth-fiducial 事件三种模式的 **14 个独立 cut 决策**和新
leading track 在 Timing 的 y。全量报告额外使用旧 merge 的同事件闪烁体
输入重算 scintillator cuts，其余 tracking 决策保持新结果：既报告新版原生
流程，也报告固定旧闪烁体的 tracking 对照。Timing 上/下部仍按各自新 leader
的 y 选择。该对照不宣称隔离旋转和 smoothing 两者各自的因果贡献。

## Duplicate 定义与检查内容

1. **Hit overlap**：统计同 collection 内所有候选对的精确 cluster ID 重叠；
   另精确实现官方 merge 的 station/layer/side/strip key，记录共享数 `>6`
   及共享比例 `>=1/2`。官方 key 不含所有 module 信息，因此同时保留两种计数。
2. **Truth duplicate**：同 `(run,event,barcode)` 下至少两条通过匹配纯度要求的
   径迹；纯度为该 truth 粒子贡献的 measurement 数 / track measurement 数。
   主阈值 0.7，另给 0.5/0.9。匹配计数使用官方
   `TrackTruthMatchingTool` 规则，并逐轨迹对照 maker 的 barcode、PDG 和
   `t_truthHitRatio`。后者的分母为 `nDoF+5`，另行核对，不能误当成前述纯度。
3. 额外重复条数为每个 truth 组 `n-1` 的总和；分母为匹配径迹数。另报告
   duplicate events / 有轨迹事件，给 68% Wilson 区间；径迹比例用事件聚类
   的统计 SE，避免把同事件径迹当独立观测。
4. 分别报告 raw、long、truth-fiducial long、满足 layers≥7、nDoF≥9、
   χ²/nDoF<15 的 truth-fiducial long，以及各模式最终选择事件内的 long。
   最后一项仍统计该事件内所有 long，不能误解为每条径迹均通过 leading-track cuts。
5. 保存所有最终 backward/merge 获得和损失事件的候选来源、被保留/移除及阻挡
   候选，检查非 long 候选阻挡、换 leader 和共享 hit 去重。另报告主 μ 子匹配
   及产生 pz 的相对误差；产生动量并非测量站局部动量，不将能损忽略为拟合误差。

## 343-event 小样本实测

输入为 200100/00170–00179 的全部 **343 events**，共同 truth-fiducial 分母
**16 events**。所有模式使用同一次重建产生的 xAOD。

| 项目 | Forward | Backward | Merge |
|:---|---:|---:|---:|
| raw tracks | 128 | 109 | 204 |
| long tracks（条） | 19 | 38 | 41 |
| truth 分母内至少一条 long（事件） | 7 | 10 | 11 |
| 最终完整选择（事件） | 3 | 4 | 4 |
| 原始 track χ² 非有限（条） | 0 | 0 | 0 |
| 与官方输出核对 truth 匹配（条） | 19 | 31 | 34 |
| nMeasurements 向量长度与 long 数不同（事件） | 109 | 70 | 103 |

最后一行是已有 dumper 在筛除 nonlong 前先写 measurement 数的接口语义；本次
直接读取 raw TrackCollection 获得逐轨迹 measurement 数，没有将该向量的下标
误配到 long 候选。三种模式全部 17 个非轨迹输入逐值相同，ID 唯一，所有 merge
候选均对应到实际 forward/backward 原候选，long 来源标志核对通过。

将试跑 ntuple 的动量转回原坐标后，以现有 `build/analysis --isMC` 独立执行：
**三套各 20 行、共 60 个 cut 计数与配对提取逐项完全相同**，并检查每行分母。
证据见 `stage201_tracking/pilot343_native_validation.json`。

旧版试跑最终为 **4/5/5 events**。固定旧闪烁体后的新结果仍为 **3/4/4**；
这个特定样本的最终差异保留，但统计极小，不能外推总体效率下降。

purity≥0.7 时，merge raw 有 **75 条匹配径迹、61 个 distinct truth、14 个
重复 truth 组、14 条额外径迹、14 个 duplicate events**；额外条数占匹配径迹
**18.6667%**，事件聚类 SE **3.6306 个百分点**。它们的官方 key 共享数均
**≤6**，所以不是官方 `>6` 判据遗漏已达阈值的 pair。raw merge 所有 77 个
候选对中，`>6` 的精确/官方 key pair 均 **0**，共享比例≥1/2 的 pair 为 **46**。
同一试跑的三种 long collection 均未发现 purity≥0.7 的 truth duplicate。
这说明 raw 和持久化 long 的 duplicate 指标需要分开；不据此断言全量 long
重复率为零，也不将所有 nonlong 同 truth 候选直接判为错误物理重建。

| 步骤 | 墙钟 s | 峰值 RSS KiB |
|:---|---:|---:|
| reco 343 events | 91.20 | 1,086,512 |
| forward maker | 24.28 | 902,720 |
| backward maker | 23.35 | 901,776 |
| merge maker + raw/truth/hit 诊断 | 89.01 | 1,949,612 |
| 原生分析 forward | 11.90 | 894,716 |
| 原生分析 backward | 10.98 | 895,864 |
| 原生分析 merge | 11.18 | 896,224 |

reco 试跑吞吐 **3.761 events/s**。merge 诊断含第一次 C++ JIT，不能与无诊断
maker 的时间直接解释为重建算法速度比。紧凑摘要最初 **23,236 bytes**；增加
独立 cut bits/Timing y 后为 **23,908 bytes**。紧凑摘要报告生成实测 **7.334 s**。
没有测量线程加速比。每 job 请求 1 CPU、3000 MB memory、6000 MB disk，
OMP/OpenBLAS/MKL 固定 1，以文件间 HTCondor 并行提高吞吐。

## 执行命令、提交记录和存储

```bash
# 现成软件的明确运行；外部目录不重新构建
export NU_MU_SKIP_LCG=1 FASER_CALYPSO_RUN=/path/to/frozen/runtime
source setup_env.sh
nu_mu_calypso_setup
export ROOT_INCLUDE_PATH="$FASER_CALYPSO_RUN/include:${ROOT_INCLUDE_PATH:-}"
python AnalysisZipFramework/scripts/run_tracking_georotation.py reco input-RDO.root
faser_ntuple_maker.py --isMC --geom TI12MC04 --cond OFLCOND-FASER-06 \
  --CKFTrackType forward --outfile forward.root input-xAOD.root
# backward 同理；merge 额外附加 raw/truth/hit 诊断
python AnalysisZipFramework/scripts/run_tracking_georotation.py merge input-xAOD.root
python AnalysisZipFramework/scripts/extract_tracking_georotation.py \
  --repo /path/to/frozen/code --index 342 --output result.npz

python3 AnalysisZipFramework/submission/prepare_tracking_georotation.py --name productionv2
condor_submit ~/condor/nu_muAnalysis/stage201_tracking/productionv2/jobs.sub
```

提交目录统一位于 `~/condor/nu_muAnalysis/stage201_tracking/`。最终 cluster
**9717383**，343 jobs、workday，完整 manifest 和代码 payload 位于
`productionv2/`；独立 1,000-event 批处理验证为 **9717381**（espresso）。
初始 idle pilot 9717379 在执行前撤回以缩小软件归档。初始 production 9717382
在尚无发布摘要时撤回，以增加上述非轨迹控制所需的独立 cut bits；替代生产
不重复计数。确切审计见 `stage201_tracking/submission_audit.json`。

worker 每文件只重建一次，三种 maker 使用同一临时 xAOD。读入本地 scratch，
仅发布 `ntuples/tracking_georotation_stage201/productionv2/<index>.npz`，
其中包含测量时间、host、有效 CKF 设置和源码 provenance。RDO/xAOD/三套 ntuple
及逐事件 JSON 均随退出清理。最终将合并摘要并删除经读回验证的重复 shards。

小样本 ROOT 临时产物位于 `/tmp/xcheng_stage201_pilot/`，不提交 Git，不作为
长期重现输入。长期可重现性依靠原 RDO、源码/二进制冻结包、参数和紧凑测量记录。

## 阶段性结论与下一步

准备阶段已用数据证明：坐标转换与原生分析一致；raw merge 的同 truth 重复
不等价于 `>6` shared-hit pair；新旧波形输入差异需要独立控制。全量物理排序、
效率增益、fake/duplicate 率和有限 χ² 的恢复程度均尚未得出结论。

1. 验收全部 343 份摘要，输入为冻结 manifest/软件/配置，要求事件总数精确等于
   3,384,987，三个模式共同 ID/truth/scintillator 逐事件一致，不能因离群值删事件。
   特别核对旧失败 index 291 完整 10,000 events 的数值诊断。
2. 生成完整 cutflow、pν,z/r 效率、同事件增益/损失、按 run 与 nominal 分组的
   duplicate/primary-muon 指标，分别给 raw 与 long 的分母、阈值及统计误差。
3. 在共同 342 文件上对照旧版，使用独立 cut bits 和旧闪烁体输入检查 tracking
   与波形引起的迁移，复查原 89 个 backward-only 事件。验收：迁移分类求和等于
   实际获得/损失数，每个 merge 候选可追到源 collection，未知类别明确保留。
4. 汇总实际资源和事件吞吐、压缩合并缓存、读回比对后清除重复 shards；补齐
   全量中文报告、图表及阶段 Git commit。没有测量的系统误差继续明确标注。
