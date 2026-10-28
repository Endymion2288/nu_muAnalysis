# 阶段 07：EOS 并发写回修正与首批产物验收

## 阶段目标

跟踪阶段 06 的普通几何官方 master 生产，定位首批写回失败，避免修改物理重建代码，
修正作业输出路径并重投失败项。对实际完成的文件记录完整输入事件数、输出计数、
资源和验收结果，区分“已提交”“进程成功”和“最终文件已核实”。

## 工作内容与原因定位

软件、几何、条件和 343 项 manifest 沿用阶段 06：Calypso master d32b0ff3、
TI12MC04、官方默认重建、maker merge、nevents=-1；CaloNu 不参与。

主 cluster 1532700 的 proc 342 首先完成并成功写回；proc 44 的 reco/maker 和
validator 都成功，但随后挂载路径上的 `mkdir -p` 失败，stderr 为：

```text
mkdir: cannot create directory '/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/merge_mc24_master_d32b0ff3': File exists
```

这次故障发生在验收之后，失败点不在物理重建或 ROOT 内容。并发 worker 在 EOS
挂载层创建共同父目录出现 EEXIST；本阶段未测量挂载负缓存的精确生存时间，不能
声称已定位某个 FUSE 内部实现。直接使用 EOS namespace 操作可避免依赖挂载缓存。

已通过 `xrdfs root://eoshome-x.cern.ch mkdir -p <run-output-dir>` 顺序预建七个 run
目录，让在途旧 worker 使用现成目录。新 worker 写回使用：

```bash
xrdfs "$output_endpoint" mkdir -p "$(dirname "$outfile")"
xrdcp --force --silent "$workdir/ntuple.root" "$output_endpoint/$partial_out"
xrdfs "$output_endpoint" mv "$partial_out" "$outfile"
```

默认 endpoint 为 `root://eoshome-x.cern.ch`。只有完整上传临时名后才 rename 最终名；
失败时通过 xrdfs 清理自己的临时文件。物理程序、参数、validator 切选和线程配置
均未改变。scratch xAOD 仍在退出时删除。已运行 Bash 语法检查和小样本端到端测试。

## 详细数据

### 首个完整文件成功：1532700.342

输入：
`200100/rdo/s0014/FaserMC-MC24_Genie_24_xing_angle_wo_caloNu_powheg_pythia_charm_central-200100-00170-00179-s0014-RDO.root`。
输出：`ntuples/merge_mc24_master_d32b0ff3/200100/` 下同前缀的 `-merge-PHYS.root`。

| 项目 | 实测值 |
|:---|:---|
| nevents/输入和输出事件数 | -1 / 343 / 343 |
| 输出分支数/大小 | 527 / 2,306,123 bytes |
| 轨迹数/forward/backward | 31 / 4 / 27 |
| 至少一条输出轨迹的事件 | 28 |
| measurement 长度差异事件/非正 nDoF 轨迹 | 105 / 0 |
| RDO scratch 复制 | 0.42 s，峰值 RSS 1,536 KiB |
| reco 墙钟/峰值 RSS/用户和系统 CPU | 77.65 s / 1,106,548 KiB / 68.40、3.85 s |
| maker 墙钟/峰值 RSS/用户和系统 CPU | 20.12 s / 938,024 KiB / 14.79、2.57 s |
| 进程退出码 | 0 |

worker 已检查 RDO、新 xAOD、ntuple 事件数相同，ROOT 非 zombie/recovered，关键
轨迹向量及来源对齐、数值有限。343 是该 RDO 的完整事件数，不是人为限制为 343；
不能用文件名中覆盖 10 个 segment 推断每个 RDO 必定有 10,000 个事件。
reco 的 WARNING/ERROR=3156/26，FPE OVERFLOW/INVALID/DIVBYZERO=37/563/20；
maker 为 15/5、0/0/4。官方诊断仍按阶段 06 的范围记录，不等于物理系统误差已验收。

### 写回失败的完整输入：1532700.44

输入：`200080/rdo/s0014/FaserMC-MC24_Genie_sibyll_pi-200080-00440-00449-s0014-RDO.root`。
原 worker 在 b9p24p8267：nevents=-1，输入/重建/ntuple **784 events**，527 branches，
临时 ntuple **2,399,628 bytes**；143 条轨迹（31 forward、112 backward），136 个
有轨迹事件，measurement 长度差异 215 个事件，非正 nDoF 1 条。已被检查的关键
向量有限且对齐。RDO 复制 0.72 s；reco 96.08 s、999,244 KiB、用户/系统 CPU
84.20/3.96 s；maker 26.28 s、895,812 KiB、20.59/2.85 s。

mkdir 失败导致整个 job 退出 1，未发布最终文件，scratch 已清理；不能把临时
ntuple 的成功验收计为最终文件生产成功，也不保留 xAOD 以节约 EOS 空间。

### 新写回路径端到端测试

同一 200080 输入，在 lxplus908 截取前 20 个事件运行完整 worker（交互小测试）：

```bash
AnalysisZipFramework/submission/run_ntuple_merge.sh \
  /eos/experiment/fasernu-data0/faser/sim/mc24/genie/200080/rdo/s0014/FaserMC-MC24_Genie_sibyll_pi-200080-00440-00449-s0014-RDO.root \
  TI12MC04 \
  /eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/merge_probe_stage07/publication-20events.root \
  /eos/home-x/xcheng/FASER/nu_muAnalysis \
  /eos/user/x/xcheng/FASER/nu_muAnalysis/software/calypso-master-d32b0ff3-el9-gcc13.tar.gz 20
```

退出 0，输出 20 entries、527 branches、189,738 bytes，4 条轨迹（1 forward、3 backward），
4 个有轨迹事件，measurement 长度差异 6 个事件，非正 nDoF=0。RDO 复制 0.91 s；
reco 19.82 s、1,016,152 KiB、用户/系统 CPU 8.95/2.66 s；maker 12.38 s、902,508 KiB、
5.58/1.86 s。实际执行了 xrdfs mkdir → xrdcp → xrdfs mv；scratch 自动清理。
日志：`/tmp/nu_mu_stage06_validation/stage07-publication.log`。

### HTCondor 重投与进度

只取 manifest 第 45 行（原 proc 44），用修订后的 worker 提交新 cluster
**1532712**，1 job，nevents=-1，资源仍为 1 CPU/3000 MB RAM/5000 MB disk/workday。
单项 descriptor 为 `logs/ntuple_merge_stage07_retry.sub`，dry-run 通过。

```bash
source /usr/share/Modules/init/bash
module load lxbatch/eossubmit
condor_submit logs/ntuple_merge_stage07_retry.sub
condor_q 1532700 -af JobStatus
condor_q 1532712 -af ProcId JobStatus RemoteHost HoldReason
```

重投 **1532712.0 于 13:58:22 CET 退出 0**，在 b9p28p6942 执行并完成新写回
路径。最终 ROOT 为 **784 entries、527 branches、2,399,508 bytes**，143 条轨迹
（31 forward、112 backward），136 个有轨迹事件；measurement 长度差异 215 个
事件、非正 nDoF 1 条，与原失败项验收计数一致。字节数不同不作为物理变化证据。
RDO 复制 0.73 s；reco 94.43 s、1,002,280 KiB、用户/系统 CPU 79.31/4.27 s；
maker 26.99 s、904,836 KiB、19.72/3.00 s。官方 warning/error 和 FPE 计数与原运行一致。

用 xrdcp 将这个最终文件下载到 `/tmp/nu_mu_stage06_validation/stage07-retry.root`，
再次独立运行 validator（--nevents 默认 -1，和完整 RDO 比较），784 事件验收通过，
关键拟合量有限且对齐。stdout 为 `logs/ntuple_merge_1532712.0.out`，本机复核副本
`/tmp/nu_mu_stage06_validation/stage07-retry.out`。没有向 EOS 另存中间数据。

**2026-10-28 13:59:55 CET** 快照：主 cluster 有 339 个 Running；事件日志记录
proc 342/195/250 退出 0，proc 44 的唯一退出 1 已由上述重投恢复。合计 **4 个唯一
manifest 项成功、339 个运行中、0 个 Held**；全量 343 项仍未完成，不宣称全量验收
通过。完整目录的总事件数、总字节数和全体物理统计此时尚未测量。

诊断日志：`logs/ntuple_merge_1532700.{log,44.out,44.err,342.out}`；若挂载暂不可见，
用 XRootD 读取 EOS namespace。此次已实际这样读取并定位 errno，无需 SHA 校验。

## 阶段性结论

首个完整 RDO 的官方普通几何 merge 结果已通过 worker 验收并写回 EOS，证明全量
nevents=-1 路径可运行；与小样本结论一致，两种来源均可贡献。这个完整文件的
31 条输出轨迹不能单独用于宣称 merge 效率提升，尚缺同事件真值分母与质量切选对照。
首个失败项是验收之后的目录写回问题，有明确 stderr 证据；不应因此否定 merge
算法或改变几何/物理配置。XRootD 新写回路径已通过端到端测试。
784-event 完整输入的批量重投和最终 EOS 文件独立验收也已通过，写回故障已恢复。

## 下一步计划与验收标准

| 具体任务 | 所需输入 | 验收标准 |
|:---|:---|:---|
| 全量统一核查 | 343 项 manifest、主/重投事件日志、最终文件 | 每项都有成功完成记录，输出事件数匹配 RDO，汇总实际总事件数、大小、来源计数和已知异常；失败逐项定位，不将试验 ROOT 计入生产 |
| 后续物理对照 | 同一官方版本三模式、真值匹配/质量切选定义 | 用相同事件分母报告效率、不确定度及假轨迹/重复率，单独量化低约束候选和官方外推诊断影响 |
