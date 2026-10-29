# 阶段 12：能量 ML 输入合同、标签核查与提取小样本验收

## 阶段目标

按 `docs/nu_mu_energy_ml_roadmap.md` 从 R0/R1 开始，固定普通几何官方 merge，
为 μ 物理基线与 BDT 信息增益研究建立可复现输入。优先验证输入与选择，随后
再进入 MLP/ResNet/TabM、Deep Sets 和更复杂的空间模型。

## 工作内容与输入

新增 ML 专用 definitions/output YAML、46 个标量的分组允许清单、342 文件
manifest 与固定分区、调用已有 `build/analysis` 的精简提取脚本、HTCondor
提取 worker/descriptor。C++ 物理实现未修改，直接用现成 LCG 109 构建。
全部新增定义经框架 `Analysis::Define` 注入；只将最终选中标量写入 NPZ，
临时 ROOT/cut flags 在 scratch 完成验收后删除，不保留 xAOD。

完整输入、单位、角色、权重缺口与实验预算见
[`执行合同`](../docs/energy_ml_stage12_protocol.md)、
[`特征合同`](../ml/configs/baseline.yaml)、[`来源与分区`](../ml/configs/files.tsv)。
普通几何固定 `d32b0ff3` / without-IFT、TI12MC04、FASERNU-04、
OFLCOND-FASER-06、s0014；继续排除原 index 291。nominal 六 run 与
SIBYLL 200080 challenge 分离。同成分、同原始生成范围的跨时期文件保守分组。

冻结的预期分区（事件数来自阶段 09，尚非本次批量提取结果）：
train 178 文件/91 组/54,196 events；validation 44/22/13,375；
calibration 32/16/9,727；locked test 43/22/12,488；challenge 45/45/15,144。
validation 才用于早停与开发，calibration/test 不用于模型选择。

## 实际测量与验证

当前节点 `lxplus908.cern.ch`，Tesla T4，显存 15,360 MiB。LCG 109
x86_64-el9-gcc15-opt：ROOT 6.38.00、NumPy 2.2.6、Awkward 2.8.9、
uproot 5.6.0、scikit-learn 1.8.0、XGBoost 2.1.3、PyTorch 2.10.0。
本阶段未使用 GPU 训练，GPU 训练成本未测量。

对官方 merge 200093、旧公开 nominal bck 200093、CaloNu 200139、data 16000
分别扫描前 128 个未选择事件。路径与原始数值见
[`schema`](stage12_energy_ml/audit/schemas.tsv)、
[`profiles`](stage12_energy_ml/audit/branch_profiles.tsv)、
[`audit`](stage12_energy_ml/audit/audit_summary.json)。

| 样本 | 分支数 | open s | scan s | events/s | scan bytes |
|---|---:|---:|---:|---:|---:|
| 官方 200093 merge | 527 | 0.629029 | 1.287962 | 99.382 | 16,599,068 |
| 公开 200093 bck | 487 | 0.044536 | 0.848240 | 150.901 | 16,507,555 |
| 公开 200139 CaloNu bck | 487 | 0.028783 | 0.833032 | 153.656 | 17,269,098 |
| data 16000 r0022 | 553 | 0.031480 | 0.974732 | 131.318 | 2,272,658 |

四个前缀 SpacePoint xyz 长度均一致、(run,eventID) 无重复。**新官方 merge
的 Track_nMeasurements 与 Track_hitSet 均有 34/128 events 与 Track_pz0
长度不一致**，不能直接按轨迹索引使用。实际使用的 p/方向/χ²/nDoF/层数/charge
等前缀全部对齐。CaloNu 200139 和 data 16000 是兼容性核查，未与普通几何混训。

完整小样本是 manifest index 196：
`/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/merge_mc24_master_d32b0ff3/200093/FaserMC-MC24_Genie_24_xing_angle_wo_caloNu_epos_pi-200093-00000-00009-s0014-merge-PHYS.root`。

- 原始 10,000 events；truth-fiducial 1,290 events；最终 315 events。
- **全部 20 项 cutflow 与阶段 09 一致；最终 315 个 (run,eventID) 与阶段 10 完全一致。**
- 使用的 truth 与 Track 向量全文件对齐失败数均 0。
- truth 索引 0：PDG +14 为 7,628，−14 为 2,368，+12 为 4；选后全部 |PDG|=14。
  前三事件索引 0 barcode 均为 1；dumper 按原 TruthParticle 容器顺序输出前十项，
  未重排。完整上游母子谱系尚未重审，保留为后续依赖。
- 原始事件 `truth_P` 与 sqrt(px²+py²+pz²) 最大相对差 **0**；
  C++ `ML_truth_E_GeV` 与独立 NumPy 标签最大相对差 **0**；无无效标签。
- 全文件 max(E−pz)=**0.000409272 GeV**；最终样本 median(E−pz)=
  **0.00000316143 GeV**，max=**0.0000564299 GeV**。
  该样本中能量与纵向动量差很小，仍使用准确 E 标签，未更改 fiducial。
- 最终 46 个输入标量非有限值数全部 0；没有为改善模型删除事件或裁剪输出。
- 最大 SpacePoint 数 **12,161 points/event**，超过前缀核查值；继续支持先用矩与
  Deep Sets、测占有率，再考虑大 N attention 的工程顺序，尚不能推断拓扑增益。
- GenWeights 10,000/10,000 为单元素 [1]；CrossSection 全部 1。
  生产 maker 未传 `--genie`，源码缺省权重路径写常数 1。首轮只能作单位权重诊断，
  物理 flux 混合权重未测量/未恢复，不将 π/K/charm 文件数当物理配比。

性能均为独立进程单次测量，包含首次 JIT、I/O 和缓存效应；非重复性能基准。

| CPU/线程 | audit s | analysis s | total s | raw events/s | analysis peak RSS MiB | NPZ bytes |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.015001 | 13.289063 | 14.640576 | 683.033 | 876.066 | 104,121 |
| 2 | 1.057395 | 14.755016 | 16.108549 | 620.788 | 901.242 | 104,131 |
| 4 | 1.023867 | 14.995880 | 16.314718 | 612.943 | 1,040.277 | 104,127 |

按 (run,eventID) 排序后，1/2/4 线程的所有数值列、标签与 cutflow **逐值完全一致**，
浮点容差设为 0。不同 NPZ 大小来自不同资源/命令元数据。未见增加线程的提速证据，
故批量选择 1 CPU/job，BLAS/OMP 固定 1，内存请求 1800 MB。
详见 [`performance.tsv`](stage12_energy_ml/performance.tsv)、
[`pilot_summary.json`](stage12_energy_ml/pilot_summary.json)。

## 执行命令与产物

```bash
source AnalysisZipFramework/setup.sh
python3 ml/make_manifest.py
# 对上述完整 index 196 文件分别执行 --threads 1 / 2 / 4：
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python3 \
  AnalysisZipFramework/scripts/export_ml_dataset.py \
  --input /eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/merge_mc24_master_d32b0ff3/200093/FaserMC-MC24_Genie_24_xing_angle_wo_caloNu_epos_pi-200093-00000-00009-s0014-merge-PHYS.root \
  --index 196 --executable build/analysis --threads 1 \
  --output ntuples/energy_ml_stage12/pilot_1.npz
bash -n AnalysisZipFramework/submission/run_ml_extract.sh
python3 -m py_compile AnalysisZipFramework/scripts/export_ml_dataset.py ml/make_manifest.py
condor_submit -dry-run /tmp/ml_extract.classads AnalysisZipFramework/submission/ml_extract.sub
```

schema 审计命令为 `inspect_energy_ml_inputs.py --entries 128`，四个 `--input`
路径已逐项记录在 audit_summary.json。上述语法与 dry-run 检查通过。
提取过程先后捕获了手工测试命令的错误 index（cutflow 验收拒绝）及阶段 10
分片已合并的路径变更；改为正确 index 196 与现有 `fiducial_events.npz` 后通过，
未改参考计数或选择。未生成新的逐事件 Git 数据。

另用 payload 解包、独立 LCG 环境和完整 worker，在 index 342（200100 最后
343 events）验证实际 EOS 上传：最终 5 events 与阶段 09/10 一致；
analysis 14.837895 s、提取 15.578389 s、外部进程墙钟 17.10 s，
峰值 RSS 896,164 KiB（875.160 MiB）。`worker_pilot.npz` 上传后可读，
含 46 个输入、独立标签和来源元数据；这只是 worker 验证，未用于模型评价。

本阶段最终保留 `ntuples/energy_ml_stage12/pilot_1.npz`；重复 2/4 线程 pilot
在聚合计时和逐值验证后删除。正式批量作业和 ML 指标在本阶段未测量。
常规 Calo 双增益 data 校准、CaloNu 增益、系统误差和最终能谱测量收益均未测量。

## 阶段性结论

官方产品已经具备构建 μ 基线及 station 计数/电荷/Calo/全局横向矩消融的输入，
精简提取不改变原选择与事件集合；标签与线程一致性已由完整文件支持。
同时确认了不能使用的轨迹分支以及物理权重缺失。以上是程序/输入结论，
不是关于变量能量信息增益或最终分辨率的物理结论。

## 下一步计划

1. 用本次已通过的小样本 worker 经 HTCondor 提取 342 个既有官方文件；输入为
   files.tsv 与阶段 09/10 参考。验收全部 cutflow/精确事件键一致，nominal
   89,786、challenge 15,144 events，逐列汇总非有限值、对齐与资源数据。
2. 对 train/validation 运行 p、p/0.8、a*p、仅 p 的一维 BDT，以及 F0–F5
   累加/去组和 direct/residual log-loss 对照；输出分能量 bias/R68/尾部、
   同源组配对 bootstrap 500 次和成本；calibration/test 保持封存。
3. 恢复生成 luminosity/flux 归一化，补来源/时期/μ匹配和条件置乱、容量/seed
   检查；正式信息增益须同时有物理权重与独立统计支持，随后才比较表格 NN。
