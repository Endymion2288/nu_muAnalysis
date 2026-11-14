# 阶段 208：将几何旋转与 isolated smoothing 合入最新 Calypso master

## 阶段目标

建立保留双方历史的新几何旋转分支，吸收最新官方 master，默认使用验证过的 strict 旋转材料图及 isolated candidate smoothing。编译、运行验证后，使用相同 RDO 与分析 cuts，完成旧版 Merge 对集成版 Merge 的全套性能比较，同时保留 Forward / Backward 诊断。

## 源码与 Git 工作流

- 官方 master：`7f2d16812070a263210d2b2dc56633345e5a10b1`（2026-11-13）。旧版基线：`d32b0ff3cc4a2dad4abfb1474a82422c3c25b305`。
- 旋转历史：`88c457c1e4bf4154e67b96114ee8e7020d9b1a97`，包含前序 `73c97758`；isolated smoothing 修复 `1c06c7b6`、验证文档 `25147d80`。
- 双亲 merge commit：`a2c3e5228c0cbce4493494200591bcea3be3ba9f`，两个父提交为 `25147d80` 与 `7f2d1681`。没有 squash、rebase 或强制推送。
- MR：[xcheng/calypso !1](https://gitlab.cern.ch/xcheng/calypso/-/merge_requests/1)，source `feature/georotation-master-20261114`，target `geoRotation_latestMaster`。编译及两对 pilot 验收后，已通过普通 fast-forward push 将目标分支从 `25147d80` 更新至 `7fd40df8`；双亲 merge 历史保留。GitLab 网页受 anti-bot 限制、REST Kerberos 返回未认证，网页 MR 状态未核实，不能据此声称网页状态已 merged。
- 新工作目录：`/eos/home-x/xcheng/FASER/geoRotation_calypso_latest`；本机编译使用 `/tmp/xcheng_calypso_master20261114{,_build,_run}`。原 `/eos/home-x/xcheng/FASER/geoRotation_calypso` 的研究改动保持原样，预先保存紧凑审计。

官方 Tracking 包重组保留，旋转改动随文件移动至 `RootWriterTools` / `TrackFinders`。唯一文本冲突是 `KalmanFitterTool.cxx`，同时保留旋转的 geometry-context 引用和 master 的 `ActsInterop/IndexSourceLink.h`。`Waveform/`、`Tracker/`、`Simulation/`、`Generators/`、`xAOD/` 已逐目录验证与官方 master 完全一致。原工作目录中的可选 truth / material audit / covariance 实验控制未批量移入生产分支。

官方相对旧基线的新功能包括 Tracking 包重组、waveform xAOD 旧容器缺失 `trigger_time` 时置 0、FlukaReader event ID、tau decay / quirk simulation / volume debugger。后几项是否影响当前 RDO 比较必须通过运行结果判断，不以提交名称推断性能。

## 材料、坐标与 smoothing

打包材料 `Tracking/Acts/FaserActsGeometry/data/material-maps-alma9-rotated-rowmajor.json.gz` 与阶段 205 冻结 strict 图逐字节一致：压缩 **2,271,338 bytes**，解压 **11,866,364 bytes**。使用 PathResolver 定位安装文件，在每个进程的临时目录仅解压一次，生产配置无需依赖个人 EOS 路径。ACTS 内部坐标变换为 `(x_A,y_A,z_A)=(z_F,y_F,-x_F)`；分析显式转回 FASER 坐标。

`CKF2.IsolateCandidateSmoothing=True` 为默认值。回归测试已通过：能复现共享状态覆盖，验证隔离后的参数 / 协方差、候选顺序独立、输入不变及单状态情况。实测 wall **0.09 s**，详见 [测试记录](stage208_master_integration/smoothing_test.log)。材料安装定位与逐字节比较已通过，实测 wall **5.571 s**，见 [材料验证](stage208_master_integration/packaged_material_validation.json)。本次环境 ACTS JSON decoder 进一步验证全部 **22 frames 最大旋转误差 0**、无遗漏材料，wall **9.44 s**，RSS **724,568 KiB**，见 [decoder 验证](stage208_master_integration/material_runtime_decoder.json)。后续每个 RDO 作业还会断言实际材料 bytes 与全部四个 CKF2 的 smoothing 属性。

## 样本、选择与定义

共同样本沿用阶段 203 / 205：342 个 RDO，**3,374,987 events**；排除旧版缺少有效结果的 manifest index 291。truth-fiducial **383,670 events**，truth-station-accepted proxy **140,132 events**；nominal 单独排除 alternate generator run 200080，所有表保留分 run 结果。使用相同 TI12MC04 / OFLCOND-FASER-06、原 YAML cuts、不加权计数。

Station 1 / 2 / 3 动量参考仍为 **SiHit 方向 × HepMC 产生点动量模长**；对应位置 reco 采用拟合状态插值或 5 mm 内最近状态。样本没有 G4 局部输运动量，已获用户确认按该限制继续；不能将它标记为精确的 G4 station momentum 或忽略能损带来的系统效应。

小样本在同一 worker 依次重跑旧版与集成版，按 index 奇偶交替运行先后顺序，旧版 21 个 science arrays 对冻结缓存逐值检查，记录相同机器上的耗时与 RSS。全量复用已验证旧版及 strict 缓存，只重新重建集成版。检查所有事件 ID、truth 字段、分片恢复闭合、实际配置与材料、波形数值以及 cut 迁移。

## 编译与运行验证

状态：完整编译通过（exit 0）。CMake 配置 210 packages，通过，wall **84.86 s**；Athena 24.0.41、GCC 13.1、ACTS 32.0.2、ROOT 6.28/12，编译并发 8，完整 build wall **3,042.60 s（50 min 42.60 s）**，累计 user **11,323.80 s**、system **5,157.95 s**，time(1) 报告最大进程 RSS **2,858,332 KiB**（不是全部并行进程 RSS 之和）。GeoGetIds、GeoVisitVolumes、CandidateIsolatedSmoothing 三个 CTest 均通过（0 失败，测试总 wall 2.05 s），见 [CTest](stage208_master_integration/ctest.log)。安装通过，wall **60.06 s**。独立 runtime 解压后 4 个库加载、5 个组件配置、材料精确性、smoothing 默认值均通过，内部 wall **5.738 s**，进程 wall **6.64 s**、RSS **628,860 KiB**。runtime archive **61,699,093 bytes**，1,760 entries、regular payload **206,500,351 bytes**，无 symlink、无 debug symbols、无源码 / 构建树；压缩 wall **10.56 s**。见 [组件验证](stage208_master_integration/portable_runtime_validation.json)、[运行包](stage208_master_integration/runtime_package.json)。

30-event smoke 全链路通过，truth-fiducial 4 events，但无跨三站 long track，因此不能作为轨迹诊断验收。实际四个算法为 `CKF2 / CKF_Back / CKF_woIFT / CKF_Back_woIFT`，全部 isolated，实际材料 exact。reco / forward / backward / merge / extract wall 分别 **16.58 / 10.95 / 11.16 / 78.70 / 20.79 s**；merge 含首次诊断 JIT，不能据这个样本作速度结论。补充 index 0、skip 380、10-event 片段通过：truth-fiducial 2 events（383 / 388），3 条 long tracks 均通过官方 ntuple 的逐轨核对，见 [长轨迹 smoke](stage208_master_integration/smoke_long_validation.json)。7 个、每个最多 2,500 events 的 paired pilot 已提交 HTCondor **9718286**，运行先后次序交替。index 342 输入实际仅 **343 events**，首个配对归约通过：16 个 fiducial / 6 个 accepted，旧版 21 个 science arrays 对冻结缓存完全一致，truth 与分片回读通过，新版波形全部与旧版逐值一致。其后加入正常 2,500-event 的 index 63：两对合计 **2,843 input / 320 fiducial / 102 accepted events**，旧版 21 science arrays 精确重放、两版全部输入 ID 相同、truth 精确、材料与四个 smoothing 检查通过、fiducial 全部波形与旧版逐值一致；归约 wall **33.316 s**，RSS **1,535,240 KiB**。old / strict / latest 的 accepted Merge final 为 **77 / 73 / 74**，该样本不足以得出效率差异结论。其余复杂样本 pilot 继续运行。

## 详细性能结果

全量已提交 HTCondor **9718288**，351 jobs；结果尚未归约，不能据已有 strict 结果代替。计划输出效率及 Wilson 区间、同事件迁移及 McNemar/sign test、三站 p / pz / q/p / 角度 / 位置响应、动量 bin purity / stability / diagonal efficiency、truth 可过而 reco 不过的 cut 分解、正确 leader 与错误粒子组成、电荷筛选、duplicates（hit purity 0.5 / 0.7 / 0.9）、Merge / Forward / Backward 比较及 runtime / RSS / I/O。

## 执行命令与产物

源码审计脚本：`AnalysisZipFramework/scripts/audit_calypso_master_integration.py`；生产重建配置验证：`run_tracking_master_integration.py`；独立运行包组件与材料验收 `validate_calypso_master_runtime.py`；批量准备与 worker：`AnalysisZipFramework/submission/prepare_tracking_master_integration.py`、`run_tracking_master_integration.sh`；归约脚本：`report_tracking_master_integration.py`、`prepare_tracking_master_report.py`；中文数据报告由 `summarize_tracking_master_integration.py` 从实测表直接生成。

所有提交目录使用 `~/condor/nu_muAnalysis/stage208_master_integration/`。worker 先暂存 RDO / runtime 至 scratch，仅上传紧凑 NPZ，退出清除 xAOD 与 ROOT 中间文件。运行缓存计划保留于 `ntuples/tracking_master_stage208/`，最终小表与图保留于 `workbook/stage208_master_integration/`。

## 阶段性结论与下一步

已完成历史合并、完整编译与安装、运行包搬迁、三项 CTest、本机完整链路和两对独立 worker pilot。集成代码已发布到自有目标分支，全量共同样本与其余复杂 pilot 正在运行。下一步验收所有全量事件 / truth / 分片回读闭合，分析高动量准确度、效率损失、电荷与 duplicate 差异，更新本文及数据报告并提交。输入为旧版 / strict 冻结 cache 与最新运行包的全量结果；验收标准为 3,374,987 全量 ID 与 383,670 fiducial 精确一致、全部分片配置一致、结果可追溯至源码提交，未知项明确保留。
