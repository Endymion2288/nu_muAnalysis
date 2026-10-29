# 阶段 11：νμ 多变量能量重建的输入审计与研究路线图

## 阶段目标

在现有合作组电子探测器分析基础上，调查可用于预测入射 νμ/反νμ 能量的 ntuple 信息，检索机器学习和中微子重建文献，形成可分阶段执行、具有明确物理问题与验收标准的中文路线图。本阶段只完成研究设计和有界输入审计，没有训练回归模型或提交批量作业。

## 工作内容

- 调查 `AnalysisZipFramework` 的 definitions、cuts、output columns、兼容层和阶段 06–10 的已验收结果。
- 新增 [`研究路线图`](../docs/nu_mu_energy_ml_roadmap.md)，覆盖标签、变量组、BDT/MLP/ResNet/TabM/Transformer/Deep Sets/GNN、概率预测、系统误差、data 控制、响应与最终测量、资源和阶段交付。
- 新增 [`inspect_energy_ml_inputs.py`](../AnalysisZipFramework/scripts/inspect_energy_ml_inputs.py)：读取 `nt` schema，只启用所选诊断列，扫描指定数量的前缀事件，保存聚合分支分布、向量长度对齐和资源计时，不保存逐事件训练数据。
- 实际读取三个公开 MC PHYS 和一个 2024 data PHYS；结果见 [`输入清单`](stage11_energy_ml/inputs.tsv)、[`计时`](stage11_energy_ml/timing_summary.tsv)、[`MC 摘要`](stage11_energy_ml/audit_summary.json)、[`data 摘要`](stage11_energy_ml/data16000/audit_summary.json)。
- 检索并核实 19 项公开论文/官方材料，重点包括表格模型、公平比较、点集/图/attention、概率校准、FASER 电子/乳胶分析，以及 2026-09-30 的 FASERCAL 预训练论文。引用与适用性判断均放在路线图第 13 节。

## 输入与运行环境

本次仓库起点 `80d7827`。当前终端实测为 **Darwin/ARM64**，可 import PyROOT，ROOT **6.40.02**；不是阶段 01 中的 lxplus GPU 节点。`ssh -o BatchMode=yes -o ConnectTimeout=8 xcheng@lxplus.cern.ch hostname` 返回认证失败，退出码 255。官方 merge 用户目录的只读 `xrdfs stat` 返回服务器 3010 权限错误，退出码 54。因此没有直接读取新官方 merge，也没有在本机尝试重建 CERN 软件。

公开 `root://eospublic.cern.ch` 的实验目录可读，完整输入路径固定于 `stage11_energy_ml/inputs.tsv`。三个 MC 均为现成 `bck` PHYS，不是阶段 06–10 新官方 merge；文件中的 collection/config 仍需依据各自生产日志核查，不能仅凭目录名 bck 判定。data 位于 `2024_back/r0022/016000`，未使用 aux waveform。本次不施加 GRL、trigger 或分析 cuts。

| sample | production | 文件 entries | 分支数 | 实际读入前缀 events | 诊断分支数 |
|---|---|---:|---:|---:|---:|
| mc_200080 | SIBYLL π / s0014 / 普通几何 | 10,000 | 426 | 128 | 87 |
| mc_200093 | EPOS π / s0014 / 2024 wo_caloNu | 10,000 | 487 | 128 | 106 |
| mc_200139 | EPOS π / s0015 / CaloNu | 10,000 | 487 | 128 | 106 |
| data_16000 | 2024 / r0022 / 首个 PHYS | 868,756 | 553 | 128 | 125 |

文件总 entries 来自树元数据，实际合计只扫描 **512 events**。未进行全量物理分布、去重或模型性能测量。schema 汇总的字段角色为审计提示，不是训练特征允许清单。

## 执行命令与验证

本次实际使用以下两次审计调用，MC 和 data 分开输出以保留各自进程的峰值内存：

```bash
python3 AnalysisZipFramework/scripts/inspect_energy_ml_inputs.py \
  --input mc_200080 root://eospublic.cern.ch//eos/experiment/fasernu-data0/faser/sim/mc24/genie/200080/bck/s0014/FaserMC-MC24_Genie_sibyll_pi-200080-00000-00009-s0014-PHYS.root \
  --input mc_200093 root://eospublic.cern.ch//eos/experiment/fasernu-data0/faser/sim/mc24/genie/200093/bck/s0014/FaserMC-MC24_Genie_24_xing_angle_wo_caloNu_epos_pi-200093-00000-00009-s0014-PHYS.root \
  --input mc_200139 root://eospublic.cern.ch//eos/experiment/fasernu-data0/faser/sim/mc24/genie/200139/bck/s0015/FaserMC-MC24_Genie_24_xing_angle_caloNu_epos_pi-200139-00000-00009-s0015-PHYS.root \
  --entries 128 --output-dir workbook/stage11_energy_ml

python3 AnalysisZipFramework/scripts/inspect_energy_ml_inputs.py \
  --input data_16000 root://eospublic.cern.ch//eos/experiment/faser/data0/phys/2024_back/r0022/016000/Faser-Physics-016000-00000-00049-r0022-PHYS.root \
  --entries 128 --output-dir workbook/stage11_energy_ml/data16000
```

两次均正常退出，退出码 0。脚本语法编译通过；新增报告和源码的格式/引用另经本阶段最终核验。没有改变既有 cut、physics definitions、生产脚本或软件版本，因此不需要重新构建分析程序或重跑阶段 09 cutflow。后续实际新增提取配置时仍须按路线图 R1 完成代表性 cutflow 对照。

## 详细数据

### 实际分支与数值

完整类型和分支清单：[`schemas.tsv`](stage11_energy_ml/schemas.tsv)、[`data16000/schemas.tsv`](stage11_energy_ml/data16000/schemas.tsv)。聚合值保持原生输入单位，不把未经校准的 `E_EM/E_dep` 数值宣称为已经确认的 GeV。

| 项目 | 200080 | 200093 | 200139 | data 16000 |
|---|---:|---:|---:|---:|
| 常规原生 Calo 分支数 | 64 | 64 | 64 | 0 |
| CaloNu 分支数 | 0 | 61 | 61 | 61 |
| CaloLo / CaloHi 分支数 | 0 / 0 | 0 / 0 | 0 / 0 | 61 / 61 |
| Veto11 分支数 | 0 | 0 | 0 | 11 |
| `t_*` 分支数 | 43 | 43 | 43 | 43 |
| `Track_hitSet` 相对 pz 向量长度错位 events | 27 / 128 | 21 / 128 | 26 / 128 | 0 / 128 |
| SpacePoint xyz 长度不一致 events | 0 / 128 | 0 / 128 | 0 / 128 | 0 / 128 |
| 前缀内重复 `(run,eventID)` | 0 | 0 | 0 | 0 |
| `CaloNu_total_E_EM` 零值 events | 不存在 | 128 / 128 | 94 / 128 | 0 / 128 |
| `SpacePoints` 最大值（points/event） | 8,021 | 1,953 | 8,670 | 334 |

本次所查 `Track_p0/px0/py0/Chi2/nDoF/nLayers/charge` 与 `Track_pz0` 的长度，在四个前缀内逐项一致；这只验证长度，不自动证明逐索引物理对应。四个文件都没有 `Track_nMeasurements` 或 `Track_isForward`；后者在新官方 production 已有不同情况，不能以旧文件替代核查。

默认输出配置的静态扫描得到 465 个不同的显式条目。其中常规 Calo、CaloLo、CaloHi 条目各 **0**，CaloNu **61**，`t_*` **43**。因此需要 ML 专用输出，既补上有物理信息的原生 Calo，又避免把看似普通名称的 truth 匹配列当特征。

三个 MC 前缀的 `GenWeights` 均有 128 个元素，均为 1；data 该向量前缀内为空。各文件的 truth 分支或占位列存在，不等于 data 有真值。入射 ν 索引和精确标签的逐事例交叉验证**未测量**。

### 资源与 I/O

| sample | open wall（s） | prefix scan wall（s） | 吞吐（events/s） | scan bytes | scan read calls |
|---|---:|---:|---:|---:|---:|
| mc_200080 | 2.539982 | 48.613352 | 2.633 | 16,412,857 | 2 |
| mc_200093 | 0.848042 | 36.973771 | 3.462 | 16,507,555 | 2 |
| mc_200139 | 0.886886 | 43.382092 | 2.951 | 17,269,098 | 2 |
| data_16000 | 3.569735 | 7.236579 | 17.688 | 2,272,658 | 1 |

MC 审计进程峰值 RSS **405.328 MiB**，data 审计进程 **408.266 MiB**，按 macOS `ru_maxrss` 的 bytes 换算。表中扫描时间包括首次 Python/ROOT 分支转换、网络和缓存，不包括模型训练；不是逐文件的独立峰值内存。只取 128 entries 仍可能预取较大 ROOT basket/cache，不能按 entries 比例推断 I/O 节省或宣称已优化生产吞吐。

诊断使用单 reader，按 branch status 裁剪输入；没有在该小审计中开启多线程或 GPU，也没有大规模远端扫描。训练耗时、GPU 显存、模型推理吞吐、多线程加速比均**未测量**。最终报告保存的是元数据/聚合值，没有 ROOT、xAOD、逐事件表或重复全量数据。

## 阶段性结论

1. **输入具有开展两类 ML 研究的基础。** 四站计数、闪烁体与常规 Calo 支持汇总变量回归；已有 SpacePoint xyz 支持点集合研究。当前尚无证据量化它们对 Eν 的独立信息增益。
2. **几何可用性不能通过分支名判定。** 普通 200093 与 CaloNu 200139 都有 61 个 CaloNu 字段，但前者被查总能量列全零。须在对应几何内做同事件消融，并保留真实缺失与零信号的区别。
3. **当前默认快照不适合作为不经审查的训练表。** 它漏掉常规 Calo，保留大量 truth/匹配列；已有 alias 解决名称兼容，但不证明双增益校准匹配。
4. **track–hit 图存在已实测的序列化索引风险。** 三个 MC 前缀均出现 hitSet 长度错位。研究可先使用 SpacePoint/全事件关系，不能直接按该分支索引拼图；没有据此删除事件或停止图网络分支。
5. 文献与数据结构支持优先做 BDT 信息增益检验、强表格 NN、Deep Sets，再以对照实验决定是否采用 GNN/Transformer。任何最终模型排名、物理分辨率和系统误差结论目前均**未测量**。

## 下一步计划

下一阶段对应路线图 R0/R1：

| 具体任务 | 所需输入 | 验收标准 |
|---|---|---|
| 冻结主样本、几何、tracking | 已验收官方 merge 清单、nominal 六 run、对应 data 和 maker 日志 | 每条输入唯一标注来源/版本；替代 flux 单独留出 |
| 核实能量标签与 truth 拒绝清单 | 最终 production 的 truth 记录、源定义、动量/质量单位 | Eν 与四动量一致，入射 ν 索引明确；所有模型特征可由 data 获得 |
| 审计官方 schema、向量与 gain | 有权限的 lxplus/EOS、真实校准和 detector 状态 | 复核 hitSet/nMeasurements；Calo/CaloLo/Hi、CaloNu 和 reduced charge 处理有出处 |
| 制作一个代表性紧凑 ML 小样本 | 新增 ML 输出/定义配置、现成构建 | 原 cutflow 与事件键复现，单位/缺失记录完整；线程数不改变特征 |
| 测提取资源并冻结划分 | 同一代表输入、1/2/4 CPU、来源关联映射 | 实测 wall/RSS/I/O；分组划分无同源跨集合后才批量提交 HTCondor |
| 输出第一张研究对照表 | p/0.8、一维回归、逐组 BDT | 每能量 bin 给 bias、R68、log-RMSE、tails、N/Neff 和配对统计区间 |

进入模型研究时，每个工作包必须产出一个有证据的明确结论；未确认原因和未完成的系统检验继续明确记录，不将假设写成结果。
