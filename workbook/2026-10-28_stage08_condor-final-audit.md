# 阶段 08：Condor 生产结束审计、截断文件修复与 NaN 事件定位

## 阶段目标

检查已结束的普通几何 merge ntuple 生产：核对 Condor 退出记录、最终 EOS 文件、
RDO 事件数、schema、事件 ID 和关键轨迹参数；定位异常，修复可明确归因的写回
故障，保留官方 master 物理代码不变。生成可供后续分析直接筛选的逐文件验收表。

## 输入、软件与审计方法

软件仍为官方 Calypso master `d32b0ff3cc4a2dad4abfb1474a82422c3c25b305`，
Athena 24.0.41/GCC 13.1/ROOT 6.28/12/Acts 32.0.2；TI12MC04、FASERNU-04、
OFLCOND-FASER-06。默认 reco 后 maker `--CKFTrackType merge`，不用 IFT，
nevents=-1。输入和输出完全沿用 `AnalysisZipFramework/submission/merge_manifest.tsv`。
343 项清单仅含阶段 06 确定的七个普通几何 run，不含 CaloNu。

输入根目录为 `/eos/experiment/fasernu-data0/faser/sim/mc24/genie/`，最终输出根目录为
`/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/merge_mc24_master_d32b0ff3/`。
交互节点实际 hostname 为 lxplus908.cern.ch。

新增 `audit_merge_production.py`：读取每个 RDO 的 CollectionTree 条目数，以 PyROOT
检查最终 ROOT 是否 zombie/recovered，以 uproot/awkward 分块读取关键 ntuple 分支；
采用 4 个独立进程并行文件 I/O，不启用 Athena 事件并发。只读需要的分支、每块
32 MB，避免重复扫描整文件或 SHA。只写一份合并 TSV，不生成每个 job 的重复 JSON。

检查范围：

- 最终事件数与对应 RDO 相同且非零；各文件 schema 名称/类型一致。
- `(run,eventID)` 的 run 正确、文件内 eventID 不重复、ID 落在输入 segment 区间。
  同 run 的 manifest segment 区间互不重叠，因此已验收文件间也没有 eventID 重叠。
- Track 的 px0/py0/pz0、x0/y0/z0、Chi2、nDoF、isForward、nLayers 长度对齐；
  前八个数值分支全部有限。Track_nMeasurements 的官方填充错位另行计数。
- 独立统计的轨迹数、两方向来源数、有轨迹事件数与 worker 的验收记录相同；
  worker 版本标记为上述官方 commit、tracked_source_changes=none，且有发布记录。

检查 ROOT 完整性不等于读过全部 527 个分支的每个值；本次没有宣称所有外推、
waveform、truth 分支或物理系统效应都已通过认证。

## 执行命令与资源

小样本先在交互节点检查 manifest 第一项：

```bash
source setup_env.sh --official
python AnalysisZipFramework/submission/audit_merge_production.py \
  --manifest AnalysisZipFramework/submission/merge_manifest.tsv \
  --output /tmp/nu_mu_stage08_sample.tsv --workers 1 --limit 1
```

该项有 10,000 个事件，单进程初测耗时 9.60 s；增加 worker 日志比对后再次检查
耗时 12.69 s，结果和原验证器一致。时间包括 ROOT 导入与 EOS I/O，不作为稳态
线程加速比。全量通过 HTCondor 提交，审计 cluster **1533833**，申请 4 CPU、
5000 MB memory、1000 MB disk、workday；实际分配 memory=12,000 MB。

```bash
source /usr/share/Modules/init/bash
module load lxbatch/eossubmit
condor_q 1532700 1532712 -af ClusterId ProcId JobStatus HoldReason
condor_submit logs/merge_audit_stage08.sub
```

审计 executable 为 `run_merge_audit.sh`，参数依次为仓库、官方 runtime 归档、manifest、
报告 TSV、进程数 4。全部计算在 worker 完成，软件解压到 scratch，结束后清理。
审计于 **2026-10-28 15:29:40 CET** 结束，返回 1 表示发现验收不通过项，
不是审计程序没有生成结果。Python 统计耗时 **145.27 s**；GNU time 墙钟
**146.95 s**，用户/系统 CPU **262.16/15.25 s**，峰值单进程 RSS **562,768 KiB**
（不能解释为四进程总内存）。Condor TimeExecute=153 s，平均 CPU Usage=2.13。

产物 `workbook/2026-10-28_stage08_merge-audit.tsv` 为 **343 行数据**的审计快照，
记录每项 status/error、输入/输出事件数、字节数、轨迹统计、日志计数和计时。
`index` 是原 manifest 的零基行号；334 个 `status=ok` 文件才是此快照中已验收的
分析输入。修复作业完成后应更新独立审计结果，不将待修项提前标为通过。
表中 `NA` 表示未测量/因前置失败未执行，不代表数值零。TSV 使用 LF 换行；
提交前统一检查新增表格的行尾和语法，保留原始计数与错误证据。

## 详细数据：作业退出与产物完整性

主 cluster **1532700** 的事件日志记录 343 个终止项：**341 个退出 0、2 个退出 1**。
原 proc 44 的目录写回失败已由 **1532712.0** 成功恢复；新发现的 proc **291** 因
非有限 χ² 被 validator 拦截，未发布最终文件。两 cluster 均已不在队列中。

最初目录有 342 个 ROOT，总实际大小 13,541,125,551 bytes；没有清单外文件。
逐文件审计发现其中 **8 个截断文件**，所以“文件存在”和“job 退出 0”均不能代替
最终验收。结果为 **334 项通过、8 项截断、1 项缺失**。

### 334 项通过的实际统计

| run | 通过/计划文件 | 已验收事件数 | 输出轨迹数 | forward / backward 来源 | 已验收文件 bytes |
|---:|:---|---:|---:|:---|---:|
| 200080 | 45/45 | 440,784 | 74,825 | 18,400 / 56,425 | 1,343,691,544 |
| 200082 | 55/56 | 550,000 | 88,828 | 22,029 / 66,799 | 1,570,688,531 |
| 200083 | 72/76 | 712,808 | 115,015 | 26,327 / 88,688 | 3,395,020,970 |
| 200089 | 18/19 | 170,947 | 18,856 | 4,130 / 14,726 | 1,049,400,044 |
| 200093 | 54/55 | 531,884 | 84,474 | 20,617 / 63,857 | 1,552,581,245 |
| 200094 | 72/74 | 718,614 | 116,119 | 26,623 / 89,496 | 3,462,847,167 |
| 200100 | 18/18 | 170,343 | 18,886 | 4,160 / 14,726 | 1,024,420,786 |
| **合计** | **334/343** | **3,295,380** | **517,003** | **122,286 / 394,717** | **13,398,650,287** |

所有通过项有 **527 个分支**，schema 相同，事件数匹配输入，关键轨迹字段有限、
长度对齐、事件 ID 检查通过；worker 来源计数和独立重读计数一致。
全部 343 个 RDO 的预期事件合计 **3,384,987**，尚有 **89,607** 个输入事件没有
最终通过的结果：截断八项 79,607，NaN 项 10,000。不能将现有 334 项冒充全量样本。

通过项共有 489,035 个含输出轨迹的事件。非正 nDoF 候选 **5,152 条**；
Track_nMeasurements 长度错位 **936,920 个事件**，与此前定位的官方填充顺序一致，
但未逐个证明每次错位都是同一种拒选原因。Track_hitSet 也有相同填充位置风险，
本阶段未另行量化，不能按它与轨迹坐标直接配对。

另统计一个明确受限的轨迹质量子集：nLayers>=7、nDoF>=9、有限 χ²、χ²/nDoF<15、
pz>100 GeV。得到 **348,681 条轨迹**（81,018 forward、267,663 backward），
**346,255 个事件**含至少一条这样的轨迹。这不是原分析的完整 cutflow：未要求
veto/时序/量能器、半径、真值匹配，也没有固定 leading-track 后再执行所有选择。
没有真值分母、统计/系统误差对照，不能称作中微子效率。

### 通过项的生产性能及官方诊断

| 步骤 | 单文件墙钟最小/中位/最大 s | 墙钟合计 s | 峰值 RSS 最大值 KiB |
|:---|:---|---:|---:|
| RDO → scratch | 0.42 / 4.67 / 13.93 | 1,622.61 | 2,240 |
| reco | 77.65 / 1573.15 / 3424.32 | 527,553.67 | 1,366,940 |
| maker merge | 20.12 / 323.295 / 821.89 | 106,123.53 | 1,122,852 |

统计限于 334 个通过项；每文件事件数不同，初始化/节点/I/O 条件不同，不能按最短
和最长时间推断算法加速比。单文件最大 reco/maker 远低于 8 h 配额和 3000 MB 请求，
本批没有证据要求增加线程数或内存。各阶段独立峰值不能相加为同一时刻使用量。

通过项 stdout 汇总中 reco WARNING/ERROR=2,853,735/283,007 行，FPE
OVERFLOW/INVALID/DIVBYZERO=328,263/5,083,350/102,112；maker 为
86,443/15,605 行和 0/121/34,609。这些是消息或 auditor 计数，**不是坏事件数**，
含同一事件多组件和初始化诊断。最终关键轨迹字段有限，并不证明所有 FPE 或
几何外推均无物理影响；该审计仍需同版本物理对照。

## 八个截断文件：证据与修复

原 worker 都通过本地 ntuple 验证并记录 completed，但 EOS 的实际长度小于 ROOT
头部 fEND/worker 原文件大小。ROOT 在本地挂载和自动回退的 XRootD 打开均报告
truncated、不能恢复 key，排除了“只是本机看不到文件”的解释。

| 原 proc/index | run | segments | EOS 截断长度 bytes | 原完整长度 bytes |
|---:|---:|:---|---:|---:|
| 100 | 200082 | 00550–00559 | 10,354,688 | 27,464,358 |
| 102 | 200083 | 00010–00019 | 23,461,888 | 47,794,381 |
| 137 | 200083 | 00360–00369 | 6,422,528 | 48,030,239 |
| 147 | 200083 | 00460–00469 | 10,616,832 | 46,806,523 |
| 168 | 200083 | 00670–00679 | 9,699,328 | 47,146,834 |
| 192 | 200089 | 00150–00159 | 30,146,560 | 61,420,004 |
| 243 | 200093 | 00470–00479 | 27,000,832 | 29,178,971 |
| 322 | 200094 | 00710–00719 | 24,772,608 | 48,067,992 |

已保留 TSV 中路径、长度和错误证据，并用 xrdfs 删除这八个已确认损坏的最终文件。
不保留无效 ROOT 副本，不删除 334 个通过项。损坏发生在原挂载 cp/mv 写回之后；
没有证据将其归因于物理重建、超时或 EOS quota，也未声称已定位底层服务故障。

新 worker 继续用 XRootD 上传临时名，在 rename 前增加服务器侧长度校验：

```bash
local_bytes=$(stat -c '%s' "$workdir/ntuple.root")
remote_bytes=$(xrdfs "$output_endpoint" stat "$partial_out" | awk '$1 == "Size:" {print $2}')
[[ "$local_bytes" == "$remote_bytes" ]] || exit 1
xrdfs "$output_endpoint" mv "$partial_out" "$outfile"
```

这是一次 metadata 查询，不做 SHA 或整文件二次读回。已实际测试 xrdcp → 服务器
stat → rename：本地/远端均 **189,738 bytes**，测试副本随后删除；Bash 语法检查通过。
原阶段 07 的完整 784-event XRootD 重投已独立验收，本次加强的是发布前长度确认。

只取上述八项，使用同一官方 runtime、原配置、1 CPU/3000 MB RAM/5000 MB disk/
workday、nevents=-1，通过 `logs/ntuple_merge_stage08_repair.sub` 补投，
**cluster 1533865，8 jobs**，dry-run 通过。提交后的首次检查八项均为 Running。
这八项的最终完成状态及重新验收结果尚未测量，不提前计入通过项。
2026-10-28 **15:39:25 CET** 再查仍为 8 个 Running、0 个 Held。重投 proc 0–7
依次对应原 manifest index **100、102、137、147、168、192、243、322**。
后续可用 `audit_merge_production.py --indices ... --retry 100=1533865.0 ...`
仅重验这八项，并保留原始行号和正确的 worker 日志映射。该索引/重投接口已在
原 index 44 的 784-event 完整文件验证通过，耗时 33.08 s。

### 首项修复后的独立补验

1533865.0（原 index 100、run 200082、00550–00559）现已完成。使用
`--indices 100 --retry 100=1533865.0` 从最终 EOS 文件独立重验，耗时 **26.72 s**，
验收通过：**9,607 events、527 branches、27,464,358 bytes、1,511 条轨迹**
（420 forward、1,091 backward），1,462 个有轨迹事件，measurement 长度差异
2,867 个事件，非正 nDoF 14 条，关键数值均有限。最终字节数与原完整长度一致，
本次是实际重读验收，不只是根据新 worker 退出码推定成功。
记录在 `2026-10-28_stage08_repair-audit.tsv`，与初审 TSV 分开保留原始损坏证据。

因此此时累计 **335/343 项通过、3,304,987 events、518,514 条轨迹**
（122,706 forward、395,808 backward），总大小 **13,426,114,645 bytes**。
尚余七项截断修复待验收（70,000 个输入事件）和一个 NaN 项（10,000 个输入事件）。

## NaN 项：200094、eventID 401649 的稳定复现

原 proc 291 输入：

```text
/eos/experiment/fasernu-data0/faser/sim/mc24/genie/200094/rdo/s0014/FaserMC-MC24_Genie_24_xing_angle_wo_caloNu_epos_k-200094-00400-00409-s0014-RDO.root
```

原 job：reco 1914.50 s/峰值 1,175,248 KiB，maker 395.55 s/1,015,668 KiB，
均执行成功；validator 在零基 entry 1649 的 Track_Chi2 发现非有限值，退出 1，
整个 10,000-event 文件未发布。不能把它计为“只有一个坏事件，所以其余已经生产”。

在 `/tmp/nu_mu_stage08_diag/` 用同一原始 RDO（1,081,624,620 bytes）复现单事件：

```bash
source /eos/home-x/xcheng/FASER/nu_muAnalysis/setup_env.sh --official
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
# 在本地临时目录复制上述 RDO 后：
faser_reco.py --isMC --geom TI12MC04 --skip 1649 --nevents 1 <local-RDO.root>
for mode in forward backward merge; do
  faser_ntuple_maker.py --isMC --geom TI12MC04 --CKFTrackType "$mode" \
    --outfile "$mode.root" <new-local-xAOD.root>
done
```

reco 单事件墙钟 **32.67 s**，RSS **1,018,176 KiB**；forward/backward/merge
分别 **12.76/12.93/13.73 s**，RSS **903,624/902,044/905,224 KiB**。三种模式各
1 event，run=200094、eventID=401649、各一条输出轨迹：

| 模式 | χ²（无量纲） | nDoF | nLayers | measurements | pz GeV | r_atMaxRadius mm |
|:---|:---|---:|---:|---:|---:|---:|
| forward | **NaN** | 10 | 9 | 15 | 882.582375 | 134.0872339 |
| backward | 16.9241218567 | 10 | 9 | 15 | 794.7965625 | 127.7461652 |
| merge | **NaN** | 10 | 9 | 15 | 882.582375 | 134.0872339 |

完整运动学实际值见 `2026-10-28_stage08_event401649-tracks.tsv`：动量 MeV、位置 mm。
merge 的 isForward=true，六个运动学值与 forward 相同；backward 的 χ²/nDoF
为约 1.6924。这里没有 Track_nMeasurements 错位，因为三种模式均恰有一条候选。
两条轨迹最大半径都超过当前分析的 95 mm 要求，本事件不能通过这一 fiducial 切选；
这不证明其他潜在 NaN 事件都在接受度外。

### 来源、传播路径与具体证据

官方 `MergeTracksAlg.cxx` 先放入 forward 再 backward；按 measurements 数排序，同数
直接以 χ²/nDoF 的 `<` 比较。NaN 与有限数的 `<` 比较都为 false，本例 forward
NaN 先保留，backward 未保留。对 NaN 没有优先选择有限 χ² 的处理；不应把这个
选择解释为 forward 物理拟合更好。

进一步从两套 Trk::Track 的 measurements 读取完整 cluster Identifier，实测两者
**15 个 Identifier 完全相同，共享 15 个测量点**（数值列表见
`2026-10-28_stage08_event401649-hits.tsv`）。这超过官方删除阈值 >6，明确解释了
为什么选中 forward NaN 后，有限 χ² 的 backward 被去重删除；不是 backward
没有重建成功，也不是因为其测量点数更少。

另外通过只读 PyAthena 诊断算法检查新 xAOD 的 Trk::Track（没有重拟合或修改官方库）：
forward 的原始 Track fitQuality χ² 已为 NaN，证明 NaN 不是 NtupleDumper 或 EOS
序列化产生。逐 state 检查在 **z=41.0 mm** 的 state χ² 已为 NaN；
**z=1199.5 mm** 的 state χ² 为 **-0.0965507254**。backward 相应 state χ² 分别
为 **0.5122314692、0.1805443913**，总 χ²=16.9241218567。
所有读取到的 state 值见 `2026-10-28_stage08_event401649-states.tsv`。

这已确定为 forward CKF/拟合质量数值异常沿 Track → merge → ntuple 传播，且
merge 的 NaN 比较行为会影响来源选择。到底是哪一步矩阵运算产生非有限值，
其协方差/残差及上游修复提交本阶段未测量，不用猜测替代结论。单事件 reco 的
FPE INVALID=2、DIVBYZERO=1、OVERFLOW=0，与数值异常相符，但不能用 auditor
计数直接证明某个矩阵的精确根因。

只读诊断使用 PyAthena Alg 在 maker 的 ComponentAccumulator 中附加读取操作：
`StoreGateSvc.retrieve('TrackCollection', key)`，分别取
`CKFTrackCollectionWithoutIFT` 和 `CKFTrackCollectionBackwardWithoutIFT`，
读取 `track.fitQuality()`、`track.trackStateOnSurfaces()` 的 fitQualityOnSurface，
以及 `measurement.identify().get_compact()`。脚本/日志在
`/tmp/nu_mu_stage08_diag/inspect_tracks.py`、`inspect.log`、`inspect_hits.log`，
没有替换或修改任何官方重建/maker 函数的物理实现；添加诊断算法后输出不用于生产。
相同的只读方法已整理为仓库中的 `AnalysisZipFramework/submission/inspect_merge_event.py`：
加载官方环境后运行 `python <script> <small-xAOD.root> --outfile inspect.root`。
可移植入口已检查 Python 语法和 `--help`；实际 state/Identifier 读取由上述单事件
运行验证。诊断结束后已删除 `/tmp` 中本次复制的 1.08 GB RDO 和临时 xAOD，
没有向 EOS 保存中间过程文件；原始输入仍在实验 EOS 上。

保持官方 master 和严格非有限值验收，本阶段没有过滤事件、删轨迹、替换 backward、
修改 merge 比较器或将 NaN 默认为有效值，也没有对这个稳定复现问题盲目重投全文件。

### 可转交 Pawan 的具体问题（草稿，未发送）

> With official Calypso master d32b0ff3, TI12MC04, I can reproduce a non-finite
> forward-track chi2 in run 200094, event 401649 (RDO entry 1649), using the RDO
> path above and `faser_reco.py --isMC --geom TI12MC04 --skip 1649 --nevents 1`.
> From the same new xAOD, forward has 15 measurements, 9 layers, nDoF=10,
> chi2=NaN; backward has 15 measurements, 9 layers, nDoF=10, chi2=16.9241218567.
> The forward Track in xAOD already has NaN fitQuality; its state at z=41 mm
> also has NaN chi2. Merge retains the forward NaN candidate. Is Eric's pending
> fix related to this forward fit-quality problem or NaN handling in the merge
> comparator? Which official commit should be used? Please confirm the intended
> treatment of a finite backward candidate when the equal-hit forward has NaN chi2.

## 阶段性结论与下一步验收

初审 334 项、随后补验 1 项，共 335 项在生产结束后独立重读通过，证明它们具备一致接口、事件保存和可用的关键
拟合向量；两种来源确实均贡献轨迹。八项已确认的最终文件截断中一项完成修复，其余正在定向重建；
一项是稳定复现的官方 forward χ² 数值异常和 merge 选择问题，不是低统计离群值
就足以否定整个研究方向。当前全量验收**尚未完成**，效率、假轨迹率和几何系统误差
仍需后续有真值和同版本对照的数据研究。

| 下一步具体任务 | 所需输入 | 验收标准 |
|:---|:---|:---|
| 完成八项写回修复 | 1533865、八项原 RDO、原 manifest 索引与新 worker 映射 | 八个最终文件服务器长度正确、ROOT 不截断/恢复，逐事件验收通过，补齐 79,607 事件，更新合并审计表 |
| 确定 NaN 项官方处理 | 上述单事件复现、Trk::Track state 数据、Pawan/Eric 的准确修复 commit | 定位数值修复/比较策略，保持版本可追溯并验证三模式；不得静默删事件来凑齐 343 项 |
| 全量统一验收与冻结 | 修复后的 343 项、生产/重投日志、输出 | 每项成功且最终文件独立通过；记录实际总事件、大小、异常和版本，再切换正式分析输入 |
| 物理性能比较 | 同版本三模式、真值匹配与完整 cutflow | 同一分母比较效率、来源、假轨迹和重复率，提供统计/系统不确定度，量化非正自由度与官方诊断影响 |
