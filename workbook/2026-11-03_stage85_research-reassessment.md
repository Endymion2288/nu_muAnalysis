# Stage85：低能失败的研究复盘与路线改写

日期：2026-11-03。本文只读取当前 `main`（`1d5e103`）已有的 stage78–84 workbook、路线文档和输入合同，并结合公开论文重新评估研究问题。**没有读取逐事件 ROOT/NPZ，没有运行重建、训练、推理或 Condor，也没有产生新的物理测量。** 因此本文新增的收益、功效、资源和系统效应均标记为“未测量”。

## 1. 阶段目标与结论

目标是判断低动量/低能区停滞是否还应通过补样、reweight、换模型继续推进，并给出能达到全区能量重建目标的下一条可证伪路线。

结论是：路线需要修正。stage78–84 已经证明现有摘要中有可学习的互补信息，也证明“再加入一批随机的 π/K 支持并沿用同一个直接 logE 回归”没有在 50–100 GeV 建立收益。下一步应把问题拆成三个可验证对象：

1. 共同的 data/MC 读出与响应是否在低动量相关变量上发生了域偏移；
2. 低能事件的困难是否来自 Eν 与可见末态之间的多解/转移能分布，而不是一个单峰的直接回归问题；
3. 训练谱先验和低 p_z 混合了哪些物理状态，能否用显式先验修正和针对性补样分别识别。

因此，stage85 仍应完成实际 tracker occupancy/readout control，但它的定位是**响应与域偏移证据**，不是低能修复实验。若 stage85 不能定义可信的响应变体，就应停止噪声支线，转到带响应 nuisance 的 transfer posterior；不再把随机扩样、通道扫描、seed 扫描或 Transformer/GNN 扫描当作默认下一步。

## 2. 最新 workbook 的证据链

| 证据 | 已测结果 | 对路线的含义 |
|---|---:|---|
| stage78 条件专家组合 | Q_local eval 的 50–100/100–200 GeV log-RMSE 为 **0.225775/0.242931**，优于 F7 的 0.312816/0.265014；仍高于传统估计 0.145487/0.226876 | U/F/传统估计的错误确实互补，不能说机器学习完全没有信息；但固定组合仍无法恢复传统方法，继续增加相同专家不是充分解释 |
| stage79–80 脉冲形状 | 物理 hit-time convolution 已核实；shape 有效比例 **62.5755%**。固定加入 11 路 `raw_peak+width` 后，主 50–100/100–200 为 **0.311694/0.258639**，低能仍远差传统 | 读出形状可能包含信息，但当前 pulse family 不是低能瓶颈的已证修复；不能再靠通道、mask、seed 或时间细调来追收益 |
| stage81–83 支持交付 | 新增唯一 key **7720**（π **6704**、K **1016**，26 来源）；两低能训练支持各增加约 **23.7%** | 支持量实际增加，但仍需区分物理谱、来源谱系和响应覆盖；新增数量不能自动等同独立生成统计量 |
| stage84 完整训练 | 原 41447＋7720 = **49167**，三 seed/400 轮/原 62 维直接 logE；主 50–100/100–200/all/低 p_z 为 **0.313532/0.265800/0.295944/0.502276** | 24% 支持增加没有改善两低能；这是关闭“无条件随机扩样”主线的证据，但不是“数据无关”或“信息极限”的证明 |
| stage84 低能偏差 | 50–100 GeV eval 约 **+16.0655%** median bias，32/208 个正 tail50 事件贡献 **73.8522%** 的平方 log 损失；训练内低能仍约 **+15.6033%** median bias、正 tail50 **10.9589%** | 低能问题不只是 208 个 eval 事件的偶然统计波动；应检查状态混合、响应和损失/先验，而不是只扩大总体 N |
| 低 p_z 语义 | 低 p_z eval 中有 **299** 个真 Eν≥200 GeV 事件；该层与 F7 的比值约 0.9986，且 high-y/未确认子层风险仍存在 | 低重建动量不是低真能量的同义词，不能按 p_z 硬切换传统估计；需要 soft gate 和两侧对照 |
| stage84 风险保护 | all/F7 上 95% 区间 **1.000424**，原五个 RMSE 保护和七层总/正/负 tail50 保护通过 | 不能把总体安全写成低能成功，也不能把低能失败写成全区失败；下一实验必须继续保护全区和歧义高能侧 |

两项现象尤其关键。第一，最低能的主要损失集中在一个正偏 tail，而不是整体均匀变差；第二，同一低 p_z 层同时包含真低能和真高能/high-y 事件。它们共同指向“条件分布/状态混合”问题，而不是单纯的网络容量问题。

## 3. 当前卡点的重新分解

### 3.1 训练先验与物理后验被混在一起

直接拟合 `log(E_true)` 学到的是训练样本先验下的条件均值。训练谱、来源混合和低能支持变化会改变这个均值，即使 p(x|E) 没变。Gambhir、Nachman 和 Thaler 对 HEP calibration 的研究明确指出，ML calibration 会依赖训练谱先验；这与当前全区 direct-logE 结果相符（[Bias and Priors in ML Calibrations for HEP](https://arxiv.org/abs/2205.05084)）。因此，用户提出的能量分区 reweight 有价值，但它应被当作**先验敏感性实验**，不能被解释为凭空创造低能信息。

更稳妥的做法是先学习一个可校准的条件分布，再在推理时改变先验：

\[
 p_{\rm target}(E\mid x) \propto p_{\rm train}(E\mid x)\,
 \frac{\pi_{\rm target}(E)}{\pi_{\rm train}(E)}.
\]

这样可以分别测试平坦 `logE` 先验、名义物理谱和低能压力谱，而不把三种效应混成一次重训。若必须在训练时加权，只允许预先固定的 capped importance weight，并报告每层 effective sample size；不能用 eval 结果调权重。

### 3.2 目标更像转移能的多解问题

对一个事件，已测到的缪子动量、veto 活动、station multiplicity 和 Calo 响应并不一定唯一决定入射中微子能量。更自然的隐变量是顶点处缪子能量、转移能和响应状态。低 transfer 事件可能接近传统 μ 估计；大 transfer、强子活动或漏能事件需要另一种后验。若把这些状态平均成一个单峰 MSE/log-RMSE 目标，模型会在最困难层向正偏或过度收缩。

因此下一模型应预测

\[
 q(c\mid x),\qquad q(h\mid x,c),\qquad
 E_\nu=E_\mu^{\rm vertex}+h,
\]

其中 c 是低 transfer、大 transfer 或响应状态，h 是非负转移能；在定义不适用的事件上，可用有界转移比例 r=Eμ/Eν 的后验替代。最终输出 p(Eν|x) 的中位数、区间和尾概率，而不是只有一个均值。这里的 Eμ(vertex)、h 或 r 只在 MC truth 中用于监督和诊断，部署时仍只使用 ntuple 中实际可用的观测量。

### 3.3 data/MC 响应偏移仍未被识别

stage53 的 on/off 结果说明独立 strip 噪声可以制造额外 MC cluster，但不能同时解释 data 的 SP/segment 过量；stage79–80 又显示脉冲摘要有明显 threshold、overflow 和 fit-failure。当前还没有共同 data/MC active-channel 分母、timebin、孤立性和站间相关的实际计量。因此不能把低能失败归因于噪声，也不能把 data/MC reweight 当作已经可做的校正。

stage85 应先回答：共同读出定义下，哪些差异可量化，哪些只能给含背景的上限，哪些因为缺少 quiet/random trigger 而不可识别。若只有条件活动率，就不能声称得到了纯电子噪声；若没有共同 collection 或 active-channel 分母，必须明确列出最小缺失输入。

## 4. 文献启发与适用边界

| 方向 | 参考资料 | 对本项目可用的启发 | 当前边界 |
|---|---|---|---|
| 先验与校准 | [Gambhir–Nachman–Thaler, 2205.05084](https://arxiv.org/abs/2205.05084) | 做 prior-shift 公式、平坦 logE/名义谱压力测试和 calibration 诊断 | 不会自动解决低能信息缺失；data-based prior-independent calibration 仍需证据 |
| 条件多峰后验 | [Yang–Lee–Goh, 2609.22979](https://arxiv.org/abs/2609.22979) | Transformer encoder＋mixture density 的思路说明中微子动量可有多峰后验，点估计可由闭式密度得到 | 该论文是 hadron-collider semileptonic top benchmark，不能直接把 Transformer 收益移植到本 62 维标量 ntuple |
| 中微子 ML 重建 | [Kopp et al., 2405.15867](https://arxiv.org/abs/2405.15867) | 从可见末态相关性推断不可见能量，支持“先建转移/可见能，再组合”的分解 | 目标探测器、选择和能区不同，不能直接套其网络或门槛 |
| response/domain reweight | [CMS, 2411.03023](https://arxiv.org/abs/2411.03023)；[CMS calorimeter calibration, 2609.15377](https://arxiv.org/abs/2609.15377) | 用 classifier density ratio 或 normalizing flow 在多维控制变量上校准 MC 到 data；需 clipping、ESS 和独立 control | 只有共同 data/MC 观测量时才可做；不能用 data 反调 BDT 或把控制样本当 ν shower 真值 |
| 不确定度与响应 nuisance | [Gambhir–Nachman–Thaler, 2205.03413](https://arxiv.org/abs/2205.03413) | 同时报告校准值、区间和 detector-response mutual information；可把 response 变体作为 nuisance | 需要实际 response 变体或可识别的 control，否则只能交上限/缺口 |
| 主动补样 | [Caron et al., 1905.08628](https://arxiv.org/abs/1905.08628) | query-by-committee 依据模型分歧选择昂贵模拟点，比均匀扩样更适合低 p_z 两侧 | 先要有可解释 acquisition score；不能用当前 eval 误差直接挑源 |
| 物理模型系统效应 | [Liu–Munteanu–Dolan, 2511.03964](https://arxiv.org/abs/2511.03964)；[Lachner et al., 2607.20419](https://arxiv.org/abs/2607.20419) | FSI、材料非线性和可见能响应可能与能量偏差退化；最终应有 interaction/response nuisance envelope | 这些研究主要面向其他中微子探测器，不能把偏差大小直接移植到本实验 |
| 高粒度预训练/SBI | [FASERCal self-supervised pretraining, 2604.07037](https://arxiv.org/abs/2604.07037)；[Simulation-based inference for precision neutrino physics, 2507.23297](https://arxiv.org/abs/2507.23297) | 若未来取得逐 hit/时间/几何输入，可考虑关系预训练或 neural likelihood/ratio；当前先作为远期分支 | 当前 ntuple 主要是标量摘要，且 response/label 谱系还未完整认证，不宜现在跳到 foundation/flow |

## 5. 改写后的研究路线

### Phase A：stage85 共同响应与域偏移控制

按现有 Prompt 只读取 6 个 data、12 个 MC 入口和 stage53 固定摘要，先做不超过 40 个身份的 schema/native collection/单位/联结/active-channel 分母 QA，再冻结 data2048 与一个有物理依据的缪子邻域排除定义。正式产物必须包括每 active-channel/event 活动、孤立 strip/cluster、timebin/大小、站间相关、run/来源/动量/位置分层，以及 data/MC 支持差异和来源重抽样区间。

验收分三种：

- 有共同分母且能测出稳定的 data/MC response 差异：只定义一个或一族有依据的 response nuisance variant，记录其条件范围；
- 只能测到 PHYS 条件活动：报告含真实次级/beam 背景的上限，不称纯 noise，不立即改模型；
- 缺少共同 collection、quiet/random trigger 或 coverage：明确不可识别结论和最小缺失输入，结束这条 noise 支线。

这一阶段没有新的能量 fit、F7 推理、ν replay、GENIE/G4 或谱 toy；资源和实际成本尚未测量。

### Phase B：一次固定的 physics-constrained transfer posterior

若 Phase A 没有否定输入可用性，下一项只做一次预注册的条件分布实验，固定三类模型并停止架构网格：

1. F7 direct-logE 作为已存在基线；
2. **bounded residual/shrinkage**：以传统 Eμ(base)=p_z/0.8 或经定义确认的缪子能量为锚，学习 `δ=log Eν−log Eμ(base)`，并令 gate `g(x)∈[0,1]`，使输出在低 transfer 状态向传统估计收缩，在证据充分时才允许大修正；
3. **hurdle/zero-inflated transfer mixture**：先预测 q(c|x)，再对正转移部分拟合 log-normal/Student-t mixture 或少量 MDN 成分；输出后验 median、68/90% interval、正 tail 概率和点估计。

这里的 “zero-inflated” 指低 transfer/近零 transfer 质量与连续正转移的两部分混合，不预设真实转移能严格等于零。模型输入只从已核实 ntuple schema 选择：缪子三动量与曲率/电荷、两个 veto 的电荷/命中/时间摘要、每个 station 的 hit 数、Calo 各模块值与 status/mask、已通过语义审计的 pulse summary。不要把所有列一次性塞入模型；缺失模式必须显式编码并保留事件。

训练用 NLL/CRPS 或预定 quantile loss，评价仍以原 log-RMSE、median bias、R68、双向 tail50 和低 p_z 真高能保护为主，并新增后验 coverage 与 PIT/可靠性图。所有 split 以来源/incoming 隔离，使用一个真正未参与模型选择的 locked source holdout；当前 cal/eval 已开发，不能把它们重新称作独立 blind。

### Phase C：先验修正和 data/MC domain reweight

这两个 reweight 必须分开。

- **能量先验 reweight：** 对已训练的条件后验做 `π_target/π_train` 修正，至少比较平坦 logE、名义物理谱和低能压力谱。训练时若使用权重，固定 bins/公式、设上限、报告每层 ESS 和权重分布；禁止按 eval 结果反向选择谱或权重。它能修正 prior bias，不能补齐没有观测区分度的低能事件。
- **响应域 reweight：** 只在 stage85 证明共同定义可比后，用 track p/位置、station occupancy、veto/Calo/pulse 状态和 run 等 control 变量训练 data-vs-MC density-ratio classifier。采用 cross-fit、权重 clipping、ESS、sideband closure 和来源留出；若域差异无法由 control 变量识别，就把它作为 response nuisance，而不是强行校正。

### Phase D：针对性 active simulation，而非随机扩样

只有 Phase B/C 显示某类 transfer 状态有可识别但支持不足时，才启动主动补样。用 F7、bounded residual、mixture/ensemble 的 disagreement，加上输入密度/OOD 分数，构造 acquisition score；每一轮同时选：

- 真低 Eν、低 p_z 的低 transfer 事件；
- 低 p_z 但真 Eν≥200 GeV/high-y 的反例；
- 与两侧相邻的中间 transfer 和高端控制事件。

每次补样都要保留 matched control、source/incoming 去重、谱系和实际响应条件。不能用当前 eval 的单事件 loss 或几例异常直接挑源。Caron 等人的 query-by-committee 结果支持把昂贵模拟集中到模型分歧/边界区域，但本项目的 acquisition gain 和样本功效目前均未测量。

### Phase E：最终交付标准

最终候选必须同时满足：

1. 50–100 和 100–200 GeV 相对传统估计的 95% 上限达到原 1.05 目标，或明确证明该目标在当前 response/覆盖条件下不可识别；
2. all、Eν≥200 GeV、低 p_z 真高能、high-y、未确认和七层双向 tail50 的原保护继续通过；
3. 68/90% 后验区间在来源留出和 response/prior 变体下有可解释 coverage；
4. 报告模型选择、先验变化、domain weight、source bootstrap 和 response nuisance，不能把单一 seed 或 source count 当联合 95% 结论。

如果只得到总体小幅改善而低能 gate 失败，应交付 calibrated posterior、低能/高-y 的可识别边界和缺失条件，而不是继续无边界地换架构。

## 6. 下一步的最小执行清单

1. 完成现有 [stage85 Prompt](../docs/nu_mu_energy_ml_next_step_prompt.md) 的共同 data/MC occupancy/readout control；不做能量 fit。
2. 根据 stage85 的三种验收结果，冻结一次 Phase B 的 transfer posterior 合同；固定输入族、loss、split、prior、response variant 和门槛。
3. 先做一个小型 latent-table/后验可识别性诊断：按真实 transfer、p_z、high-y 和 response 状态交叉列出 bias、tail、事件数与来源数；新表的资源、功效和收益均未测量。
4. 仅在 posterior 诊断显示明确支持缺口时，执行一次 committee-driven active simulation；若没有可识别增益，停止扩样。
5. 最后才决定是否值得把标量 ntuple 升级为 station/Calo hit graph、set encoder 或 Transformer。当前结构下，BDT/小型 MLP/MDN 是合理候选，GNN/Transformer 不是默认突破。

## 7. 记录边界与产物

本文的实际输入是 stage78–84 报告和其中链接的 JSON/TSV 摘要；未读取逐事件数据。没有新的命令、作业、CPU、内存、EOS I/O、模型收益或系统误差测量，均为**未测量**。本报告只新增研究判断，不修改历史 stage1–84 结论；stage85 的实际控制仍按输入合同执行。

下一步阶段报告必须在完成真实控制后记录实际样本、变量、单位、命令、资源、活动率/上限、产物路径和不可识别缺口；若没有随机/quiet trigger，应明确写“条件活动或上限”，不得写成纯电子噪声最佳值。
