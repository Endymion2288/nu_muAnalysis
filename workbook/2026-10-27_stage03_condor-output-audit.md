# 阶段 03：Condor 产物验收与启动故障定位

## 阶段目标

核对上一阶段 merge 轨迹 MC 生产是否完成，按 manifest 验收输出、确认失败原因，
修正 worker 启动路径，并区分交互验证与实际 batch 验证。

## 工作内容与执行命令

2026-10-27 在仓库根目录检查。普通 shell 的 `condor_q` 查询 `bigbird28`，
生产使用的是 EosSubmit schedd `bigbird24`；必须切换后查询：

```bash
module load lxbatch/eossubmit
condor_config_val SCHEDD_HOST
condor_q 1512404
condor_history 1512404 -limit 500 -af ProcId ExitCode RemoteWallClockTime
```

`bigbird24` 中原 cluster 已无在队作业。history 查询返回的记录出现重复且未及时
结束，因此终止查询，最终全量退出统计使用完整事件日志逐 ProcId 去重核验：
`logs/ntuple_merge_1512404.log`，并逐一读取 467 个 `.err` 文件。输入与目标路径
均取自 `AnalysisZipFramework/submission/merge_manifest.tsv`，没有复制 xAOD。

## 详细数据

### 原批量任务

| run | 预期文件数 | 实际目标 ROOT 文件数 | 目标文件合计大小（bytes） |
|---:|---:|---:|---:|
| 200080 | 45 | 0 | 0 |
| 200082 | 56 | 0 | 0 |
| 200083 | 76 | 0 | 0 |
| 200089 | 19 | 0 | 0 |
| 200093 | 55 | 0 | 0 |
| 200094 | 74 | 0 | 0 |
| 200100 | 18 | 0 | 0 |
| 200139 | 46 | 0 | 0 |
| 200140 | 63 | 0 | 0 |
| 200146 | 15 | 0 | 0 |
| **总计** | **467** | **0** | **0** |

目标根目录为 `/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/merge_mc24/`。
467 个唯一 ProcId 均有终止事件，退出码全部为 `1`，成功为 `0/467`；终止时间覆盖
2026-10-26 `21:04:42–21:05:23`（日志时间）。467 份 stderr 全部包含：

```text
/pool/condor/dir_920874/run_ntuple_merge.sh: line 12: /pool/setup_env.sh: No such file or directory
```

worker 临时目录编号不同，错误相同。程序尚未加载分析环境，更未进入事件循环。
事件日志的 `TimeExecute` 为每 job `0–3 s`，467 个 job 合计 `402 s`。
所以 ROOT tree、branch、物理分布及选择效率均**未测量**；不存在可据此比较
forward/backward/merge 效率的物理样本。没有 ROOT 产物是程序启动失败，不能解释为
νμ 事件为零或 merge 重建效率低。

### 路径修复和移位验证

EosSubmit 会下载 executable 到 worker scratch。原脚本通过 executable 的父目录
推导仓库位置，结果错误。修复是在 submit arguments 中显式传入仓库绝对路径作为
第 5 参数；第 6 参数可限制小样本事件数。源文件为
`AnalysisZipFramework/submission/run_ntuple_merge.sh` 和 `ntuple_merge.sub`。

模拟 executable 被传走的测试：

```bash
mkdir -p /tmp/nu_mu_stage03_relocation
cp AnalysisZipFramework/submission/run_ntuple_merge.sh /tmp/nu_mu_stage03_relocation/worker.sh
bash /tmp/nu_mu_stage03_relocation/worker.sh \
  /eos/experiment/fasernu-data0/faser/sim/mc24/genie/200080/rec/s0014 \
  0 TI12MC04 /tmp/nu_mu_stage03_relocation/probe.root "$PWD" 1
```

配置为 Calypso `22.0.49`、Athena `24.0.41`、GCC `13.1.0`、ROOT `6.28/12`，
`--files 1 --merge 10 --isMC --CKFTrackType merge`，无 IFT。退出码 `0`，Athena
耗时 `24.3401 s`；ROOT 产物 `94,326 bytes`，`IsZombie=False`，`nt` 树
`1 entry / 527 branches`。该结果只验证交互节点上的移位启动和输出可读性。

真实 worker 的 100-event 验证已通过 `logs/ntuple_merge_probe.sub` 提交，
cluster **1529530**，1 个 job；提交命令 `condor_submit logs/ntuple_merge_probe.sub`。
它采用与全量相同的资源：2 CPU、6000 MB RAM、2500 MB disk、`espresso`，
输入为上述 200080 slice 0，输出独立为
`/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/merge_probe_stage03/200080-100events.root`。
此小样本不会冒充全量产物。提交时 dry-run 展开 1 个 job，实际于 `08:58:09`
完成，退出码 `0`，worker 为 `b9p22p7769.cern.ch`。
Athena 耗时 `34.3497 s`，Condor `TimeExecute=42 s`，远端用户/系统 CPU 时间
为 `8 s / 5 s`。文件实际为 **349,026 bytes**、`nt` **100 entries / 527 branches**，
`IsZombie=False`、`kRecovered=False`；`run`、`eventID`、`longTracks`、`Track_pz0`、
`truth_pdg`、`VetoNu0_charge`、`VetoNu1_charge` 分支全部存在。
事件日志 MemoryUsage 只采样到 `15 MB`，不视为峰值内存；可信峰值**未测量**。
日志路径为 `logs/ntuple_merge_probe_1529530.{log,0.out,0.err}`，stderr 为 0 bytes。
这验证了实际 worker 上环境加载、EOS 输入输出与 100-event 执行；没有再次提交
467 个全量 job。

### 额外发现：CaloNu 配置不兼容

当前 `../calypso/run/bin/faser_ntuple_maker.py` 不接受 `TI12MCCaloNu`。
用上面的移位脚本替换输入为 `200139/rec/s0015`、geometry 为 `TI12MCCaloNu`，
限制 1 event，实际退出码 `1`，消息为 `Unknown: --geom TI12MCCaloNu!`。
此问题影响原 manifest 的 `200139/200140/200146`，合计 **124 个文件**；它是
修正启动路径后还会遇到的配置问题，并非这次 467 个失败 job 已执行到的错误。

原 MC 生产日志
`/eos/experiment/fasernu-data0/faser/sim/mc24/genie/200139/log/s0015/FaserMC-MC24_Genie_24_xing_angle_caloNu_epos_pi-200139-0000-PHYS.ntp.log`
记录 `CaloNuMC/1ec47efe`、`FASERNU-CALONU`、`OFLCOND-FASER-05`。本地当前普通
`TI12MC04` 使用 `FASERNU-04`、`OFLCOND-FASER-06`，不能用普通几何代替 CaloNu。
原 Calypso waveform 兼容修复把缺失字段设为默认值，对电荷、状态字、timing 的
物理等价性尚未验收；程序退出成功不能替代这些数值检查。

## 阶段性结论

原任务全部结束且全部失败，成功全量产物为零；失败原因确定为 executable 传输后
仓库路径推导错误。移位启动已修复，且实际 worker 的 100-event 验证已通过。
CaloNu 几何和旧 waveform schema 的物理兼容性必须在全量生产前验收。
本阶段没有可报告的新物理选择效率或 merge 性能结论。

## 下一步计划与验收标准

1. 以 probe cluster 1529530 和同输入现有 PHYS 为基础做完整 slice 验证；验收为
   输入输出事件 ID 对应、关键电荷与状态字一致，并记录墙钟时间、吞吐及峰值内存。
2. 以原 MC 配置和已有 Calypso 构建为输入，恢复兼容的 CaloNu runtime；验收为
   日志明确 `FASERNU-CALONU` 及匹配条件，完整处理一个 slice 并验证 ROOT。
3. 用原 xAOD/已有 PHYS 小样本检查 waveform 电荷、状态和 timing 的数值对应关系，
   然后按通过验收的配置重提缺失任务；验收为 467 个唯一有效完整输出及逐 run 事件
   数、大小、配置证据。此前保留原失败日志，不把少量事件测试当成全量。
