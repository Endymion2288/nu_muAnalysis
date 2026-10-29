# 阶段 13：普通几何精简数据集与首轮 μ 基线、BDT 信息增益

## 阶段目标

将阶段 12 的输入合同推进为真实可重复数据集，完成物理基线和第一轮 BDT
变量组累加/去组比较。回答在当前 MC 选择与单位权重先验下哪些重建信息有用，
同时检查偏差、尾部、来源依赖与成本。不把本轮 validation 结果当作最终物理精度，
不提前进入表格神经网络或空间拓扑模型排名。

## 工作内容、配置与执行

实现 `ml/audit_dataset.py`、`train_bdt.py`、`plot_bdt.py`、`diagnose_inputs.py`，
新增 HTCondor BDT worker 与 DAG：等全部原子发布的分片就绪，先验收合并再训练。
使用现成 LCG 109 / XGBoost 2.1.3；无 C++ 源码或原物理选择变化，无新 xAOD。
新增特征仍经既有 Analysis::Define/YAML 提取，输入清单与配置保持阶段 12 版本。

采用 seed **20261029**，所有 BDT depth=3、learning_rate=0.04、最多 600 trees、
min_child_weight=20、lambda=10、subsample=0.8、early_stopping_rounds=40、
1 CPU、hist。F0–F5 各比较 direct log E 与 residual log(E/p)；
另做完整 F5 去掉 μ context、counts、scintillator、Calo、shape 的五个对照。
合计 **17 个 BDT、4 个物理/解析基线**，只有一个配置与一个 seed；没有做 20 trials
或多 seed 优化。主排序是预注册六个能量 bin 的 macro log-RMSE，区间采用
**500 次同源组配对 bootstrap**，各模型共享抽样。

```bash
source AnalysisZipFramework/setup.sh
python3 ml/make_manifest.py
mkdir -p ntuples/energy_ml_stage12/shards
# payload 的内容列表与原始提取命令见阶段 12；小样本验收后执行：
condor_submit -name bigbird24.cern.ch AnalysisZipFramework/submission/ml_extract.sub
# 冻结的 BDT payload：
tar -czf software/energy-ml-bdt-stage13.tar.gz \
  ml/train_bdt.py ml/audit_dataset.py ml/plot_bdt.py \
  ml/configs/baseline.yaml ml/configs/files.tsv
condor_submit_dag -no_submit -outfile_dir logs \
  AnalysisZipFramework/submission/ml_stage13.dag
condor_submit -name bigbird24.cern.ch \
  AnalysisZipFramework/submission/ml_stage13.dag.condor.sub
# 对少量 validation 异常事件/同入射动量配对的独立输入诊断：
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python3 ml/diagnose_inputs.py \
  --output-dir workbook/stage13_energy_ml
```

提取 cluster **1540833**；DAG **1540841**；其 BDT 子作业 **1540845**，
schedd 均为 bigbird24。默认 bigbird28 拒绝提交文件里的直接 EOS 路径；
显式选用已支持 EOS 的 bigbird24 后成功，参考
[CERN EosSubmit 文档](https://batchdocs.web.cern.ch/local/eossubmit.html)。
DAG PRE 原本逐路径 exists 的 EOS 负缓存延迟了就绪判断，改为每次仅列目录一次，
已看到 bigbird24 的 342/342 就绪状态；DAG 和 BDT 最终均以 0 退出。
没有重复提交提取作业或同时运行两套 BDT。

阶段 12 的首次 Git commit 碰到新生成的空 loose object，HEAD 当时未更新；
将该空对象移到 `/tmp/nu_mu_stage12_empty_git_object`，启用
`git -c core.fsync=loose-object commit` 后提交为 **8445d75**，已核对其对象类型为
commit。该环境问题未改变输入、参考计数或计算结果。

## 数据集验收与实际资源

**342/342 个作业成功；共 3,374,987 raw events，104,930 selected events。**
每个文件的全部 20 项 cutflow 与阶段 09 一致，最终事件键与阶段 10 一致；
唯一 (run,eventID) 数也是 104,930，无重复。ordinary nominal 六 run 选择后
**89,786 events**，SIBYLL challenge **15,144 events**；缺失 index 291 未恢复。
逐文件、逐来源及 cutflow 见
[`extraction_files.tsv`](stage13_energy_ml/extraction_files.tsv)、
[`extraction_sources.tsv`](stage13_energy_ml/extraction_sources.tsv)、
[`extraction_cutflow.tsv`](stage13_energy_ml/extraction_cutflow.tsv)。

最终分区的 files/groups/events 与预注册预期全部一致：train **178/91/54,196**，
validation **44/22/13,375**，calibration **32/16/9,727**，test **43/22/12,488**，
challenge **45/45/15,144**。表中 Σw=Σw²=Neff=N 仅表示本轮单位权重。
**没有在 calibration、test、SIBYLL challenge 上计算模型指标或调参**；
其标签只用于必要的输入完整性/重复来源 QA。

- 全样本 used-track/truth 向量对齐、独立 C++/NumPy 标签验证通过；
  46 个输入标量的非有限值计数全部 0。
- 全部 raw GenWeights 值为 1、CrossSection 值为 1，仍不能恢复物理 flux 配比。
- 选后 truth 索引 0 barcode **104,930/104,930 为 1**；PDG +14 **74,129**，
  −14 **30,801**；最大 neutrino mass **0 MeV**。
- `truth_P` 与分量模长最大相对差 **0**；E 标签独立实现最大相对差 **0**；
  reco p 与分量模长最大相对差 **4.44×10⁻¹⁶**。
  全 raw 最大 E−pz **0.001344069 GeV**。因此已排除本轮检查中的 MeV/GeV
  或 p/pz 标签混淆，不能由此排除 tracking 本身的问题。
- 全 raw 最大 **32,105 SpacePoints/event**，无点数截断或高占有率事件删除。
- 精确 `(ν px,py,pz,vertex x,y,z)` 跨分区重复数 **0**。
  进一步发现 **6,272/13,375 validation events** 的入射 ν 三动量在 train 中出现。
  随机抽 12 对读原始 PHYS，前十粒子 PDG 列表相同 **0/12**、完整前十粒子
  四动量相同 **0/12**，并非该小样本中的同一完整相互作用记录。
  这支持区分“入射 flux 动量复用”和“完整生成事件重复”，但只核查 12 对，
  尚未证明完整生成谱系独立；保留来源独立性/flux-library 依赖作为后续检验。
  见 [`配对表`](stage13_energy_ml/repeated_incident_momentum_pairs.tsv)。

缓存从 342 个分片 **35,185,104 bytes** 合并成五个按分区的 NPZ，合计
**24,498,825 bytes（23.364 MiB）**，逐列重新读回、以零容差验收后删除原分片。
数据在 `/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage12/dataset/`；
模型与 validation 预测在 `ml/artifacts/stage13/`，共 **12,279,749 bytes**，
均不进入 Git。重复 pilot 事件缓存也已删除，保留聚合报告和异常事件键。

| 资源项目 | 实测结果 |
|---|---:|
| 提取提交到最后完成 | 399 s |
| 第一个提取开始到最后完成 | 373 s |
| 342 作业合计 remote wall | 10,113 s |
| 合计 remote CPU user+system | 6,627 s |
| 提取器内部合计 wall | 7,166.005 s |
| 单文件提取 wall 中位数 / P90 / 最大 | 20.911 / 27.389 / 41.394 s |
| analysis 子进程最大 peak RSS | 873.695 MiB |
| Python 提取父进程最大 peak RSS | 456.312 MiB |
| 合并验收外部 wall / peak RSS | 33.59 s / 149,328 KiB |
| BDT 全部计算内部 wall / CPU | 66.808 / 65.727 s |
| BDT 外部进程 wall / peak RSS | 69.74 s / 324,896 KiB |
| 整个 BDT worker remote wall | 121 s |

提取每作业请求 1 CPU/1800 MB，BDT 1 CPU/3000 MB；BLAS/OMP 固定 1。
Condor 定期采样的内存最大 733 MiB、BDT 仅 37 MiB，显然低于 `/usr/bin/time`
峰值，故不把 Condor 短作业采样当作峰值 RSS。
GPU 训练/显存/推理均**未测量**，本轮 BDT 使用 CPU。
完整成本在 [`costs.tsv`](stage13_energy_ml/costs.tsv)；F5 direct 单模型训练
**4.745 s**、NumPy inplace 推理 **164,160 events/s**（13,375 events，预热一次后
五次中位数），模型 **700,089 bytes**。推理不包括 ROOT 提取或文件 I/O，
采用 inplace_predict 避免把 DMatrix 缓存读取误报为推理吞吐。

## 基线与首轮信息增益

以下仅为 **unit-weight validation development**。能量范围 train
100.660–6206.900 GeV，validation 100.250–6206.900 GeV。
预注册 bins [100,200,400,800,1600,3200,6400] GeV 的 validation N 分别为
**731 / 2455 / 4247 / 3933 / 1741 / 268**，均≥100，无范围外事件。
log 指标无量纲；bias/R68/tail 在表中用百分比。
bootstrap 区间条件于已拟合模型，未包含重新训练波动、物理权重与模拟系统误差。

| 模型 | macro log-RMSE | 分组 bootstrap 95% 区间 | 整体 log-RMSE | median bias % | R68 % | P(abs(r)>0.5) % |
|---|---:|---|---:|---:|---:|---:|
| pμ | 0.704103 | [0.670912, 0.732679] | 0.584182 | -21.496 | 22.461 | 17.436 |
| pμ / 0.8 | 0.631674 | [0.597279, 0.659677] | 0.497994 | -1.871 | 28.076 | 13.308 |
| 已有 pz / 0.8 | 0.631695 | [0.597299, 0.659698] | 0.498024 | -1.875 | 28.076 | 13.308 |
| train 标定 a·pμ | 0.622912 | [0.588739, 0.650840] | 0.488374 | 8.069 | 30.920 | 13.996 |
| F0：仅 pμ 的一维 BDT | 0.543307 | [0.519745, 0.569451] | 0.406504 | 9.441 | 34.028 | 15.021 |
| F1：+ μ 方向/质量/几何 | 0.516713 | [0.494323, 0.541051] | 0.387710 | 8.939 | 31.062 | 12.374 |
| F2：+ station/事件计数 | 0.434073 | [0.412896, 0.456988] | 0.325843 | 6.033 | 25.897 | 8.778 |
| F3：+ 闪烁体电荷 | 0.390037 | [0.368643, 0.410740] | 0.292255 | 3.942 | 23.327 | 7.088 |
| F4：+ 常规 Calo | 0.387153 | [0.365067, 0.408606] | 0.290767 | 3.889 | 23.122 | 7.043 |
| F5：+ 全局 SpacePoint 矩 | 0.385054 | [0.362119, 0.407205] | 0.288171 | 3.836 | 22.916 | 6.774 |

训练集 log-MSE 最优 a=**1.376615672**，不是重新证明了普适的 μ/ν 能量比例。
F5 对比 p/0.8 的 macro log-RMSE 相对下降 **39.04%**，对比同输入信息的 F0
下降 **29.13%**；这两项不能解读为最终能谱测量精度提高相同百分比。
原 pz/0.8 与 p/0.8 很接近，与小角度选择和准确 E/pz 核查相容。

分组配对增量（右模型−左模型，越负越好）：

| 对照 | Δ macro log-RMSE | 95% 配对区间 |
|---|---:|---|
| F1−F0：μ context | −0.026595 | [−0.034034, −0.019486] |
| F2−F1：计数 | −0.082640 | [−0.093575, −0.072267] |
| F3−F2：闪烁体 | −0.044035 | [−0.051107, −0.036575] |
| F4−F3：Calo | −0.002884 | [−0.005350, −0.000771] |
| F5−F4：全局空间矩 | −0.002099 | [−0.004244, +0.000080] |
| F5−去 counts | −0.000586 | [−0.002623, +0.001176] |
| F5−去 scintillator | −0.035399 | [−0.041144, −0.028688] |
| F5−去 Calo | −0.000631 | [−0.003371, +0.002003] |

**当前数据支持计数和闪烁体在 μ-only 之后的预测增益，闪烁体在完整模型中仍有
清晰条件增益。计数的累加增益不等于在含电荷/空间矩模型中的不可替代贡献。**
Calo 累加增益小，完整模型去 Calo 的区间包含零；全局空间矩的增益区间也包含零。
因此未验收“空间拓扑超出总计数有用”，尚无依据直接升级 GNN/Transformer。
物理上计数/电荷可以代理 shower 活动，统计上也可能识别来源、运行条件或拟合
误差；本次消融不能单独区分这些机制，不作因果声明。

F5 direct / residual 的 macro 为 **0.385054 / 0.392521**；本次 direct 较好，
不能认为 residual 参数化在所有谱/容量下必然更差。六个 nominal run 和两种
重建电荷分层中 F5 整体 log-RMSE 均低于 F0（逐源表中已有实际数值），
但还没有固定 p/方向后的条件置乱、flux 挑战或多 seed 检验。

## 偏差、尾部与原因诊断

[`能量分箱指标`](stage13_energy_ml/validation_energy_bins.tsv)、
[`分层表`](stage13_energy_ml/validation_strata.tsv)、
[`响应图`](stage13_energy_ml/validation_response.svg)、
[`bias/R68/tail 图`](stage13_energy_ml/validation_energy_metrics.svg)
显示显著的训练先验/边界效应：

- 100–200 GeV，p/0.8 median bias **+11.8%**，F0 **+57.1%**，F5 **+14.2%**。
- 3200–6400 GeV，p/0.8 bias **−21.9%**，F0 **−45.1%**，F5 **−38.4%**。
  F5 的 R68 **18.7%** 比 proxy **67.3%** 窄，却仍有很大的负偏差；
  该 bin 的 |r|>0.5 为 **26.1%**。不能仅凭窄 R68 宣称已校准的高能响应。
- p-only 树在训练范围外趋于常数；未人为裁剪 Ehat，也未强制 Ehat≥p。
  一维模型改善大尾的一部分来自训练谱下的回归收缩，不等同新探测器信息。

proxy 整体 relative RMS **4.583755（458.4%）**，与 R68 **28.1%** 极不相同。
validation 中 **35 events** 有 |r|>10，最大 |r|=**424.430**；最大 reco μ p
**461,971.187 GeV**，中位数 **496.262 GeV**。
异常事件全部保留，清单见
[`large_proxy_tail_events.tsv`](stage13_energy_ml/large_proxy_tail_events.tsv)。

独立读取最大的 10 个 proxy-tail 事件，其 t_* 与轨迹向量在这 10 个事件中均对齐：
**9/10** 匹配 μ（barcode 5，parent 为入射 ν），**1/10** 匹配 π−（barcode 34）；
matched_hit_ratio 均为 **1.0**。例如 `(200094,342799)`，Eν=**966.880 GeV**，
truth-matched μ p=**939.264 GeV**，reco p=**329,072.090 GeV**，
χ²/nDoF=**3.936**，通过了原选择。说明既有 **μ 动量严重偏移**，也有
**最高 pz leading track 并非 μ** 的个例；不能将二者都归咎于 MeV/GeV 错误，
也不能把 9/10 外推为全样本匹配率。truth-matching 表只用于诊断，未进入模型输入。
尚未取得动量协方差/受控重拟合，不能把拟合算法缺陷和有限曲率分辨率的份额
进一步量化。不会因这些事件停止分析分支或偷偷收紧选择。
详见 [`匹配表`](stage13_energy_ml/large_proxy_tail_truth_matches.tsv) 与
[`诊断摘要`](stage13_energy_ml/lineage_and_matching_summary.json)。

## 验证、阶段结论与边界

全量经 HTCondor 执行且输出/数据完整性验收通过。另以解析的 perfect prediction、
恒定 2 倍 prediction 检验 log-RMSE/偏差/R68 和分组 bootstrap；前者误差全 0，
后者 log-RMSE=ln2。显式 truth 特征允许清单测试拒绝泄漏；Python 编译、shell
语法、Git diff 检查通过。两张科学图已实际渲染检查。没有为修改框架重建 C++。

本阶段完成 ordinary MC 的 R1 数据交付和 R2 首轮探索；**R0/R2 尚未完整验收**：
物理 flux 权重、完整生成谱系、Calo data/MC 校准、容量学习曲线、训练波动、
条件置乱、全样本 primary-μ matching/oracle、独立 test 与系统误差均未完成。
尤其多个 F2–F5 模型最佳树数接近 600 上限，存在明显需要扩展容量检查的信号，
不能以当前区间替代“已排除欠拟合”的证据。MLP/ResNet/TabM、Deep Sets、
GNN/Transformer、GPU 成本、data 闭合和最终能谱测量收益均**未测量**。

## 下一步计划

1. **权重与来源**：需要各 nominal GENIE 样本生成 luminosity、π/K/charm flux
   归一化与原 EVNT/生成谱系元数据。重建 w/Σw/Σw²/Neff，核实共同入射 flux
   记录的处理；验收为可解释的物理权重和无同生成事件跨分区。SIBYLL 保留独立
   challenge，不用作调参集。
2. **BDT 稳健性**：在相同分区/输入上预注册更大树数/深度与 3–5 seeds、train-size
   学习曲线，比较物理权重和 logE 平坦训练先验；做固定 run、p、方向后的组条件
   置乱。验收为计数/电荷/Calo/形状的增量与去组结论在容量/seed/来源上稳定，
   同时报告分能量 bias、R68、tail 的区间，不能只用整体 macro。
3. **物理分解**：需要全样本对齐审计后的 t_* 与原 truth ancestry，输出匹配/错配组
   和 primary-μ truth-only oracle；对高动量尾做协方差或受控重拟合诊断。验收为
   随机非弹性损失与重建/材料损失分开的定量证据；不改变既有主选择。
4. **架构推进**：待上述输入/预算冻结后，用相同权重、loss、分区和调参预算比较
   MLP、表格 ResNet、TabM。之后 Deep Sets 与同对象手工矩/计数对照，证实空间
   关系增益后再测试 GNN/Transformer。所需输入是按实际几何分站、对齐验证后的
   SpacePoint/track/segment 集合，不能直接使用错位 hitSet/nMeasurements。
