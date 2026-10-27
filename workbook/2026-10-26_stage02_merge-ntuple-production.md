# 阶段 02：merge 轨迹全量 νμ MC NTUP 生产

> 2026-10-27 验收更正：cluster 1512404 的 467 个 job 全部以退出码 1
> 结束，目标 ROOT 文件为 0 个。下面的交互式测试和成功提交记录不构成
> 批量生产成功；错误原因、修复与验收记录见
> [阶段 03](2026-10-27_stage03_condor-output-audit.md)。

## 阶段目标

使用本地编译的 Calypso 22.0.49，通过 `faser_ntuple_maker.py` 的
`--CKFTrackType merge`（三站、无 IFT）为论文相关的 νμ MC 生成精简 PHYS
NTUP，并用 HTCondor 覆盖全部输入 segment。

## 工作内容

### 环境与兼容性

实际环境为 `lxplus908.cern.ch`，GPU 为 Tesla T4（15360 MiB）；批量任务不占用
交互 GPU。Calypso 路径为 `../calypso/run`，版本为 `22.0.49`，平台为
`x86_64-el9-gcc13-opt`。可复现的环境命令为：

```bash
export NU_MU_SKIP_LCG=1
source setup_env.sh
nu_mu_calypso_setup
nu_mu_calypso_report
```

必须同时使用 Athena 24.0.41、GCC 13、
`ATLAS_POOLCOND_PATH=/cvmfs/faser.cern.ch/repo/sw/database/DBRelease/current`，
以及 `DATAPATH` 中的
`/cvmfs/faser.cern.ch/repo/sw/software/22.0/faser/offline/ReleaseData/v20`。
否则分别会出现 `GLIBCXX_3.4.31`、条件数据库 catalog 或磁场图找不到的错误。

MC xAOD 为 `WaveformHitAuxContainer_v1`，实际缺少新转换器直接读取的
`trigger_time` 和 `hit_status` aux 字段。已在 Calypso 工作区对
`xAODWaveformHitAuxContainerCnv_v1` 做最小可用性判断修复，并只重建、安装
`libxAODFaserWaveformAthenaPoolPoolCnv.so`；没有修改或复制输入 xAOD。
该外部源码修复已在 Calypso 仓库提交为 `35c48423`，本仓库只记录其版本和运行配置。

### 输入、配置与验证

输入根目录为 `/eos/experiment/fasernu-data0/faser/sim/mc24/genie`。manifest
为 [`merge_manifest.tsv`](../AnalysisZipFramework/submission/merge_manifest.tsv)，
每行对应一个已有十段 xAOD 文件，作业使用 `--files 1 --merge 10`；这里的
`--merge 10` 只负责 segment 文件匹配，轨迹模式由 `--CKFTrackType merge`
指定。输入数量如下：

| run | sim tag | geometry | xAOD 文件数 |
|---:|:---:|:---|---:|
| 200080 | s0014 | TI12MC04 | 45 |
| 200082 | s0014 | TI12MC04 | 56 |
| 200083 | s0014 | TI12MC04 | 76 |
| 200089 | s0014 | TI12MC04 | 19 |
| 200093 | s0014 | TI12MC04 | 55 |
| 200094 | s0014 | TI12MC04 | 74 |
| 200100 | s0014 | TI12MC04 | 18 |
| 200139 | s0015 | TI12MCCaloNu | 46 |
| 200140 | s0015 | TI12MCCaloNu | 63 |
| 200146 | s0015 | TI12MCCaloNu | 15 |
| **总计** |  |  | **467** |

交互式验证命令（100 events）为：

```bash
NTUPLE_NEVENTS=100 AnalysisZipFramework/submission/run_ntuple_merge.sh \
  /eos/experiment/fasernu-data0/faser/sim/mc24/genie/200080/rec/s0014 \
  0 TI12MC04 /tmp/nu_mu_merge_test.root
```

退出码为 `0`，耗时 `19.30 s`，产物为 `/tmp/nu_mu_merge_test.root`、
`348767 bytes`、`nt` 树 `100 entries`、`527 branches`。日志确认算法序列含
`MergeTracksAlg/MergeTrackAlg`，输入轨迹集合为
`CKFTrackCollectionMergeWithoutIFT`；这是模式配置验证，不是全量物理产量。

## HTCondor 提交

作业脚本为 [`run_ntuple_merge.sh`](../AnalysisZipFramework/submission/run_ntuple_merge.sh)，
提交描述为 [`ntuple_merge.sub`](../AnalysisZipFramework/submission/ntuple_merge.sub)。
dry-run 实际展开 `467 job(s)`；通过 `module load lxbatch/eossubmit` 提交，
首次 cluster **1509181** 使用 `workday`，在 5 分钟内保持 `467 idle` 且未启动，
因此已移除并改用短作业队列重新提交。每 job 请求 `2 CPU、6000 MB、2500 MB disk`，以
文件级并行覆盖吞吐；不写 JSON、不复制 xAOD，唯一持久产物为
`/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/merge_mc24/<run>/*-merge-PHYS.root`。
作业把 Athena 的 `PoolFileCatalog.xml` 和 event-loop 临时文件写入
`_CONDOR_SCRATCH_DIR`，避免并发 job 在共享 EOS checkout 中互相覆盖。

重新提交后的 cluster ID 为 **1512404**；截至本报告更新时需继续用
`condor_q 1512404` 查询实时状态；
全量输出文件数、总字节数、ROOT entry/branch 验证和失败 job 数**尚未测量**，
不能用交互样本推代。作业完成后必须运行 ROOT 汇总检查，并将实际数值补入本报告。

## 阶段性结论

merge 轨迹重建链路已在真实 MC xAOD 上成功启动并完成 100-event 验证；输入兼容
问题由旧 waveform aux schema 与新转换器的物理数据模型不一致造成，已通过兼容转换
修复解决。全量生产已进入 HTCondor 队列，尚无全量物理产量结论。

## 下一步计划与验收标准

1. 监控 cluster 1512404，重试退出码非零的 job；验收：467 行中每行有且仅有一个
   非空 PHYS ROOT 输出，失败数为 0。
2. 用 ROOT 读取全部输出的 `nt` 树、entry 数、关键 track/truth branch，按 run
   汇总字节数和事件数；验收：输出路径、字节、entry、branch 和缺失文件表均有实测值。
3. 与 forward/backward 样本比较 track multiplicity、long-track、`pμ` 和选择
   cutflow；验收：给出带单位和统计定义的中文阶段报告及明确物理结论。
