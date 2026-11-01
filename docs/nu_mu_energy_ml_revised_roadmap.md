# νμ 能量研究路线修订：先识别信息缺口，再选择模型

日期：2026-11-01。依据：workbook stage13–28，重点复核 stage15、16、19、23–28；文献检索截至本日。

本次是研究复盘，不执行 ROOT、训练、伪实验或 SHA 验证。下文数值均引用已有报告；新方法的收益、可达分辨率和系统误差均为**未测量**。原路线图保留为历史记录，后续优先级以本文为准。

**判断：已有实质进展，但主线需要调整。新增计数和电荷的信息已经得到支持；架构替换的边际收益较小。当前应优先区分可观测信息缺失、概率信息被压缩、模拟响应不可靠这三类问题。stage27–28 的有限 MC 研究保留为必要统计基础，暂不继续以逐参数覆盖率调校为主线。**

## 1. 最终项目应交付什么

应分别完成两个相互关联的成果：

1. **单事例重建**：仅使用可在 data 定义的电子读出，给出入射 νμ 能量估计及其不确定性，明确高能、高非弹性度和误选 leading 的局限。
2. **物理收益**：相对 μ 动量基线，在同一选择、统计量、背景和系统误差条件下，证明这些读出改善选中事例的能谱信息；最终再连接接受度、背景和物理归一化。

区间覆盖率改善不会自动提高单事例能量分辨率；较低 log-RMSE 也不会自动改善能谱测量。前者与后者需要各自的验收指标。unit-weight 条件研究可以继续，缺失的正式 flux/亮度归一化不应反复阻断方法研究。

## 2. 已有发现的证据与边界

| 发现 | 已有实测证据 | 当前可以支持的判断 |
|---|---|---|
| 电子读出确有新增信息 | stage13：macro log-RMSE，μ/0.8 为 0.631674；F1 μ context 为 0.516713；加入计数 F2 为 0.434073；加入闪烁体 F3 为 0.390037；F5 为 0.385054 | 主要跃升来自计数和电荷；这一阶段的提升不能直接换算成最终谱精度 |
| 增益不只是在修正 μ 拟合 | stage15：已知真实 primary μ 产生动量、方向、符号和真实顶点，O0/O1/O2 为 0.344342/0.241081/0.212329；O2−O1 为 −0.028752，95% 来源组区间 [−0.035312,−0.022389] | 电荷还有关于能量分配的条件信息；尚未分清 shower、泄漏、材料位置等原因 |
| 表格架构排序已有答案 | stage16，同 F5：BDT 0.373879，MLP 0.384301，ResNet 0.373799，TabM 0.367379；TabM−BDT 为 −0.006500 [−0.012371,−0.001845] | BDT 是强且便宜的基线，TabM 是候选；暂缺扩大架构竞赛的理由 |
| 简单空间表示未获得明确新增收益 | stage18 station moments−counts 为 +0.000011 [−0.003151,+0.003107]；stage19 full Deep Sets−summary 为 −0.000451 [−0.002160,+0.001491] | 暂停同类点云扩容；这不证明真实轨迹关系、局部拓扑完全没有信息 |
| 高能与高 y 仍是难点 | stage16：3200–6400 GeV 的 BDT/TabM median bias 为 −36.598%/−37.064%；stage15：y≥0.8 的 F3 macro log-RMSE 为 0.648738 | 均值回归、动量响应、能量分配和先验都可能参与；不能简单归为网络容量不足 |
| 已有条件能谱收益 | stage23，假设 N=1000 个选中事例、响应已知：fraction 相对统计 σ 的 RMS，μ/0.8 为 39.797%，BDT UU 为 26.752%，TabM UU 为 28.049% | 新读出对能谱有价值；仍不是含背景、接受度和系统误差的最终物理测量 |
| 输出表示影响模型排序 | stage23：energy/rank 分箱下架构与 flat 训练的排序改变；rank 尾箱合并大量高能事例 | 需要测试单值回归加分箱的压缩损失，不能只选有利分箱宣布赢家 |
| 有限 MC 确实影响区间 | stage27：BDT oracle/单侧 MC 覆盖为 67.097%/65.333%；stage28：固定/校准 macro 为 65.556%/68.444%，校准后最高箱仅 63.000% | 已定位一项统计效应；macro 校准不是逐参数、跨谱形或真实 data 有效性的证明 |

以上 log-RMSE 无量纲，bias 为相对能量偏差；不将 log-RMSE 直接称为百分比能量分辨率。各阶段容量、训练设置不同，跨阶段中心值不能用来计算单一严格配对提升。

来源：[stage13](../workbook/2026-10-29_stage13_energy-ml-bdt-first-results.md)、[stage14](../workbook/2026-10-30_stage14_bdt-information-robustness.md)、[stage15](../workbook/2026-10-30_stage15_primary-muon-inelasticity.md)、[stage16](../workbook/2026-10-30_stage16_tabular-model-physics.md)、[stage18](../workbook/2026-10-30_stage18_station-spatial-information.md)、[stage19](../workbook/2026-10-30_stage19_deep-sets-physics.md)、[stage23](../workbook/2026-10-30_stage23_forward-spectrum-closure.md)、[stage27](../workbook/2026-10-30_stage27_independent-mc-physics.md)、[stage28](../workbook/2026-11-01_stage28_mc-bootstrap-physics.md)。

共同样本为普通几何、官方 merge/without-IFT、六个 nominal run、原 20 cuts、最高 pz leading、原 truth fiducial、unit weights。train 为 54,196 例/91 来源组，validation 为 13,375 例/22 来源组。后者已被多次用于早停、模型选择和研究诊断，所以这里的证据是**开发阶段证据**，不是多次独立确认。

calibration 9,727 例、locked test 12,488 例、SIBYLL challenge 15,144 例尚未用于模型评价；应在新的有限实验结束后冻结协议，再按用途分次启用，不能长期只优化同一 validation。

## 3. 当前真正的卡点

**第一，可见量到物理隐变量的映射还没有拆清。** stage15 的好 oracle 同时改变了 μ 动量、方向、身份信息和顶点。它与部署模型的差距不能全部算给动量拟合，更不能作为可实现的 tracker 改善上限。应该先定位缺口，再决定补什么信息。

**第二，一个预测能量可能不足以描述事例。** 两个事件可以有相同的回归均值，但一个主要由精确的 μ 测量约束，另一个可能是低 μ 动量加大 shower 活动、能量分布更宽甚至多峰。把二者混在同一个 reco-energy 箱，会损失对谱形有用的差异。这是有根据、尚未验证的解释。

**第三，新增信息尚未跨到真实探测器响应。** 电荷可能是有效 shower 代理，也可能对饱和、增益、阈值、位置和模拟细节敏感。stage14 的条件置换排除了部分简单混杂，但没有替代 data 校准或相互作用/强子 shower 模型检验。

**第四，稀少区域与验证设计限制了结论。** validation 最高能量箱仅 268 例，其中 251 K、17 charm、0 π；stage24 的最细内部尾箱两折仅 26/23 例。stage28 重抽样没有增加独立高能事例或来源组。继续生成更多同总体 toys，主要降低的是玩具实验的数值误差。

因此，不宜将接下来的主问题定为“哪个大网络可以解决”“能否把平均覆盖调到 68.27%”。需要问：**缺了哪个可恢复的物理量，丢了哪部分概率信息，哪些增益能经受真实响应和模型变化？**

## 4. 优先实验 A：拆开 oracle 缺口，决定物理投入方向

下一阶段先使用相同部署特征 X=F5、相同事件、固定 BDT 容量和三个 seed，做四格实验：

| 模型 | 输入 | 所回答的问题 |
|---|---|---|
| A0 | X | 当前可部署基线 |
| Ap | X + primary μ 的真实产生动量大小 | 增加该潜在量还能改善多少？ |
| Av | X + 真实交互顶点 x/y/z | 增加位置/深度知识还能改善多少？ |
| Apv | X + 上述动量与顶点 | 两者是否相互依赖、共同解除简并？ |

这是**增加信息**的实验，不替换掉重建特征。truth 只能进入隔离 oracle；不得进入部署 allowlist。四格在完全相同事件支持上比较，不删错配、离群和高 y 事件。

用 L0、Lp、Lv、Lpv 表示相同评价风险，可报告 Gp=L0−Lp、Gv=L0−Lv、Gpv=L0−Lpv，以及 I=Gpv−Gp−Gv。I 只是选定损失上的协同量，不是因果份额，也不是探测器分辨率的百分比分解。总体主评价之外，分别报告能量、leptonic y、primary-confirmed 状态和真值顶点分层。真值动量还会在非 confirmed 事件引入正确 primary 的信息，因此尤其需要 confirmed 子集的诊断。

若 Av 有大增益，再用 z-only 与 xy-only 的小控制区分深度和横向接受度；不能把 xyz 的全部收益都称为 shower 深度。stage15 还使用了真实方向和符号，因此本四格不一定复现其完整 oracle 差距。

结果对应的下一步：

- **Ap 主导**：优先研究 μ 响应，取得真实 tracker 入口/同参考面动量、曲率与拟合协方差，区分物理传播和拟合误差。在高 p 区采用有符号曲率 q/p 的响应模型，避免把接近零的曲率直接倒数后用截断掩盖尾部。
- **Av 主导**：先验证仅靠重建读出是否能预测深度/区域，再尝试深度条件模型或 mixture of experts。候选量是沿程活动变化、station 间计数/电荷比例、已核实关联的 segments；若深度无法由现有读出恢复，转向新读出而不是扩大网络。
- **Apv 出现明显协同**：尝试联合推断 μ 产生能量、transfer energy 和深度，保留联合不确定性；单独校正某一个量可能不足。
- **四格都只剩小增益**：主要问题可能是 F5 已有信息有限、损失/先验或尚未测试的方向/拓扑；不能据此宣布达到探测器信息极限。

特别限制：`truth_st1` 的动量模长来自产生动量，不能用它测量材料能损。stage15 validation 中 leading 确认 primary 的有 13,104 例，任意保存轨迹可确认的有 13,131 例，仅多 27 例；剩余 244 例为未确认，不能说一定没有重建。大规模 all-track GNN 之前，应先区分候选是否存在、匹配信息是否足够。tracking 的 89 例 backward-pass/merge-fail 诊断不能代表整个能量样本。

## 5. 优先实验 B：将“回归一个数”扩展为“保留能量概率信息”

### 5.1 先用便宜的分类器检验压缩损失

不增加探测器变量，仍用 F5。用 BDT 预测原六个真能量箱的概率向量 q(x)，保留全部六个概率（五个独立自由度），不能只保留最大概率箱或概率加权均值。[P1]

最少需要三个对照：

1. 既有 scalar Ehat + 十 reco 类，保留为历史基准。
2. 同一个新分类器的完整 q，与将 q 压成单个平均 log-energy 后的表示比较，隔离一部分输出压缩影响；补充足够表达力的 scalar-only 概率映射，检查收益是否仅来自旧十箱过粗。映射训练和概率校准用 train 内来源组隔离样本或 cross-fitting。
3. 完整 q 与二维摘要（例如 Ehat、pμ）的廉价对照，检查新增维度是否已经足够，不立即升级高维密度网络。

应统一可用训练数据、开发评价样本和统计问题。既有模型与新模型训练样本/目标不同的比较只能作为整体方法比较，不能全部归因为输出维数。不得把同一事例的 Ehat 与 q 当成独立观测相乘。

在固定 nominal 箱内形状和来源混合下，设训练先验为 πb=P_train(b)，校准后的 qb(x)=P_train(b|x)，则选中样本六箱 fractions f 的条件似然可写为：

\[
\mathcal L(f)\ \propto\ \prod_i\sum_{b=0}^{5} f_b\,\frac{q_b(x_i)}{\pi_b},\quad \sum_b f_b=1.
\]

这是 Bayes 公式导出的固定分量混合似然；不能直接把各事例 qb 求和当成测得的真谱。训练若用了类别平衡/重权，πb 必须对应实际训练分布，并使用与之相容的概率校准。

先固定 α=0，测已知响应下的条件信息、有限样本偏差和最弱谱方向；N=1000 继续只是与 stage23 对齐的假设，不是观测 data 数。完整 q 可能没有收益，甚至因概率误差而更差，必须报告。

### 5.2 不让新表示重复走入旧陷阱

六类概率只在**固定箱内连续能量/组件分布**的模型下可能保留相应混合信息，不会自动消除 stage24–25 的 within-bin 敏感性。nominal 成功后，才用固定的 within±1、来源组和有限 MC 压力测试验证可迁移性；不能通过调 LR 阈值宣称消除了形状偏差。

如果训练依赖 α 的 q(x;α)，分母参考分布 p_ref(x;α) 也会依赖 α。它不能在联合拟合 α 时作为常数丢掉。后续需使用相对**同一固定参考分布**的参数化似然比，或有明确生成先验的连续条件密度。

六箱输出还不足以提供精细单事例能量分辨率。若此实验支持概率表示，再研究 log Eν 的分位数、轻量 mixture density 或连续条件密度，评价 proper log score/CRPS、偏差、尾部和条件区间表现。训练先验下的后验区间，不等于在每个真能量/每个新谱上都具有同样覆盖的频率学区间。

## 6. 有物理结构的概率模型，比直接堆层数更值得尝试

可利用的结构是：定义 E_transfer=Eν−Eμ,vertex，y_lepton=1−Eμ,vertex/Eν。E_transfer 是转移能量代理，**不是**已测量的可见强子能量，也不是包含靶静止质量的完整能量账本。

一个候选模型联合学习 μ 的产生能量、transfer energy、交互深度及其相关不确定性，再形成 Eν。truth 用作辅助训练标签；推理只输入重建量。相比直接预测 Eν，该设计可检验计数/电荷是否主要约束能量分配，以及不同深度是否对应不同响应。

IceCube 对 μ 与 cascade 信息的联合利用支持这种物理分解思路，但其光学读出和事件包含关系与本项目不同。[P3] Kopp 等的工作提示：可观测末态、不可见能量推断和生成器迁移比“网络是哪种”更关键；其 DUNE/LArTPC 精度不能搬到 FASER。[P4]

辅助任务不创造新的可见信息。只有 oracle 分解显示缺口、且该潜在量确实能由 reco 预测时，才值得实现相应分支。对于误选 primary 的事件，若候选审计支持，可用“多个候选 + 未捕获 primary”混合概率，避免硬选一个候选或事后删事件。

## 7. 优先补充的真实信息与物理控制

### 7.1 CaloNu 是尚未完成的原始主问题

普通几何 F3→F5 的结果不能回答 CaloNu 是否有用。后续用来源、几何、conditions 和校准匹配的 CaloNu 样本，在**同一事件**比较输入有/无 CaloNu。普通几何和 CaloNu 几何之间的差异包含材料、接受度和谱，不能作为读出增益。

先确认非占位读出、单位、零值意义、饱和与数据兼容，再做单变量组 BDT 消融。对真实安装的额外量热信息做一次干净测试，优先于在普通几何上继续扩大点云网络。

### 7.2 当前 F5 之外的小规模信息族

候选包括 peak、width、相对时间、status/饱和标志和经过融合校准的双增益。先验证它们在 MC 和 data 是否都有效、是否仅为占位或未模拟信号；原始时间、脉宽本身不能未经校准就解释为 shower 迟发成分。每次只新增一个信息族，避免同时改变选择、生产和架构。

若要再研究空间结构，应使用经核实的 track/segment 关联、距 μ 的局部活动、跨 station 的连接和纵向变化。stage19 的 mean-pooling Deep Sets 没有完整表达这些关系，但这只给出一个待检验方向。当前有错位风险的 `Track_hitSet` 不能直接建图；pooled points 的 90.617% 来自 IFT 是“点的比例”，不是“事件的比例”。

### 7.3 现在就安排 data 控制

用穿透 μ 检查 MIP、增益、位置、阈值和状态；用可解释的高活动控制区检查电荷/计数分布、饱和和跨探测器相关性。MIP 校准不能单独校准强子能量。SND@LHC 的 test-beam 工作表明 shower 起点、不同区域的能量份额和饱和值得联合处理，但其 SciFi+HCAL 结构不同，不能照搬分辨率或校正常数。[P2]

SIBYLL 对 EPOS 的变化是入射 flux/母粒子产生模型挑战，不是中微子相互作用生成器挑战。后续分别列出 flux、interaction、材料/shower、电子学响应的变体；没有相应样本就写未测量。电荷增益的模型依赖还可能来自非线性材料响应，而不只是不可见能量；其他探测器的 2026 研究提供了这一机制提醒，不能把其 MeV 级偏差数值搬到本项目。[P5]

原 truth-fiducial 选择中的真值条件也不能直接用于 data；正式部署需定义可执行的 reco 选择、接受度与迁移。这不妨碍当前在固定选择下比较方法。

## 8. 更有研究创新性的第二步：针对谱参数学习 score

如果完整概率输出显示收益，下一步可以使用 simulator score / 局部充分统计量思路，而非继续最小化能量均方误差。[P6]

本项目的一个优势是谱形重权已知。对五个独立 fractions，以第 5 箱为参考，在名义 f0 附近的 truth-level score 为：

\[
s_b(E)=\frac{\mathbf1(E\in b)}{f_b^0}-\frac{\mathbf1(E\in5)}{f_5^0},\quad b=0,\ldots,4.
\]

如果箱内形状由 exp(αu(E)) 重权并逐箱归一化，u(E)=log(E/Ecenter,b)，则在名义点：

\[
s_\alpha(E)=u(E)-\mathbb E[u(E)\mid b].
\]

从 reco X 回归这些 truth score，得到的条件期望近似观测空间 score。这里所需的是**已知谱重权**的导数，不要求从 GENIE 取得完整矩阵元导数。五个 fractions score 与六类 posterior 含有紧密关系；真正值得增加的是箱内连续能量方向及经过物理定义的 nuisance 方向。

此压缩只在参考点附近适用，且依赖正确的响应模拟；不能解决未知探测器系统误差。需要全局谱变化时，应使用统一参考的参数化似然比并检验插值。真实 nuisance 变体建立后，才考虑 INFERNO 或 Wunsch 等方法，把 profile 后的谱误差直接作为训练目标。[P7,P8] 不应先对 run、深度或能量盲目做 adversarial 去相关，可能去掉真实信号。

## 9. 有限 MC 分支：保留，但限定预算与目标

stage27–28 已证明单侧响应 MC 有影响，且经验阈值能改善名义 macro。stage28 校准不改变点估计或 bias，BDT 最高箱宽度增加 4.777%，只在 16 个测试 trial 上测了宽度；这不是新增物理信息。

有限 MC 导致低覆盖有成熟研究。[P9] 可以安排**一次有上限的标准方法对照**：先做 unit-count、固定 α 的辅助多项式响应列似然，或适合该生成模型的 Barlow–Beeston/ASY/Dembinski 类方法。[P10,P11] 每 truth 箱内固定总数意味着归一化迁移概率相关；不能把连续重权后的归一化单元格机械当成彼此独立 Poisson。标准方法也需要在本问题的边界和预算下检验覆盖，不能引用论文即宣布解决。

暂不将“每个参数各调阈值、再扩大 α 网格、再加 bootstrap 层数”设为连续主线。当前 α 是人工箱内压力参数，不是经过物理校准的全部系统误差。应先冻结有物理收益的观测表示，统计方法再服务于它。

## 10. 后续阶段与决策条件

| 阶段 | 必要输入与工作 | 交付与验收 | 结果怎样改变路线 |
|---|---|---|---|
| stage30：缺口定位与压缩检验 | 已有 train/validation F5、stage15 truth 缓存、原 source groups；实验 A 四格 BDT，实验 B 小规模多类概率对照；单一预设容量、三个固定 seed | oracle 增益及交互、逐能量/y/matching 分层；概率校准；同支持上的条件谱信息、偏差及成本；全部新结果明确为开发结果 | A 决定优先 μ/深度/联合隐变量；B 决定是否保留概率或二维表示 |
| stage31：只推进一条有依据的物理分支 | 根据 A/B 结果选择曲率响应、深度代理、联合概率模型或同事件 CaloNu；同时做新增信息的 data 控制 | 对应潜在量的可恢复性、单事例误差、条件谱收益和响应敏感性；无增益也形成明确预算决定 | 若潜在量不可恢复，转向新读出/新样本；若仅表示有益，保持简单输入模型 |
| stage32：冻结与独立检验 | 有限候选、固定评价和 nuisance 方案，必要的高能/组件样本；先用 calibration 做允许的校准，再一次启用 locked test 与挑战集 | 独立重建性能与稳健性；有限 MC 方法有上限对照；报告局限 | 锁定可部署方法，或限定适用能区/时期；不按 test 结果回头调参再称独立 |
| 最终测量阶段 | reco 选择、背景、接受度、flux/亮度和经过物理定义的 detector/interaction 变体 | 对最终谱/截面误差的收益，而非仅 unit-MC 回归排名 | 决定是否替换原分析观测量及可发表的物理范围 |

具体预算门槛在运行前写入协议：可把“相对基线至少 5% 的风险或谱误差改善”作为是否值得扩大计算的示例阈值；这是建议的资源决策标准，**不是预期收益，也不是现有测量**。用来源组配对区间说明其是否得到支持：区间足以排除该量级收益时降低优先级；区间宽时写证据不足，并列出缺少的是事例还是来源组，不用继续调参代替样本。

原六真能量箱保留为开发诊断。正式报告分箱应根据预先设计的信息量和物理问题确定；可预注册较粗尾箱、累计高能 fraction 或可辨识谱本征模作为补充。不能看了 test 闭合后才合箱。N=1000 的单位混合中最高箱约 2%，对应约 20 个期望事例只是预算量级估算，不是实际观测。

训练/早停/概率校准优先在 train 内按来源组划分；validation 只做明确标记的开发比较。冻结候选后启用新的检验样本，避免永久封存 test 却无限复用 validation。小样本先检查，再 HTCondor 批处理；复用现成软件与紧凑缓存，记录时间/内存，避免全量 ROOT/xAOD 重生产。

## 11. 文献、可迁移内容及限制

- **[P1] Cranmer, Pavez, Louppe，Approximating Likelihood Ratios with Calibrated Discriminative Classifiers**，2015/2016，[arXiv:1506.02169](https://arxiv.org/abs/1506.02169)。支持用分类学习似然比；六箱混合公式是本项目的具体推导，不代表 paper 已验证 FASER 响应。
- **[P2] SND@LHC，Studies of Hadronic Showers in SND@LHC**，2025，[arXiv:2504.01716v2](https://arxiv.org/abs/2504.01716v2)，[全文](https://arxiv.org/html/2504.01716v2)。100–300 GeV test beam，研究 shower 起点和 target/HCAL 信号组合；有助于设计深度、饱和与校准控制，不提供本探测器的可达精度。
- **[P3] IceCube，Measurements using the inelasticity distribution of multi-TeV neutrino interactions in IceCube**，2018/2019，[arXiv:1808.07629](https://arxiv.org/abs/1808.07629)。支持联合使用 μ 和 cascade 信息研究 Eν 与非弹性度；光学探测器结果不直接迁移。
- **[P4] Kopp 等，Improving Neutrino Energy Reconstruction with Machine Learning**，2024/2025，[arXiv:2405.15867v3](https://arxiv.org/abs/2405.15867v3)，[全文](https://arxiv.org/html/2405.15867v3)。关注不可见运动学与跨生成器测试；聚合末态的鲁棒性思路可借鉴，不能照搬 LArTPC 的数值收益。
- **[P5] Lachner 等，Interaction-model dependence in calorimetric energy reconstruction methods due to non-linear material effects in modern neutrino detectors**，2026，[arXiv:2607.20419](https://arxiv.org/abs/2607.20419)。区分非线性材料响应和缺失能量导致的模型依赖；机制提示适用，长基线实验能区与绝对偏差不适用。
- **[P6] Brehmer 等，A Guide to Constraining Effective Field Theories with Machine Learning**，2018，[arXiv:1805.00020](https://arxiv.org/abs/1805.00020)。score 的局部信息压缩；本项目可利用已知谱重权构造标签，探测器 nuisance 仍需另外提供。
- **[P7] de Castro, Dorigo，INFERNO: Inference-Aware Neural Optimisation**，2018/2019，[arXiv:1806.04743](https://arxiv.org/abs/1806.04743)。优化推断目标；有物理 nuisance 后再引入，不能代替响应建模。
- **[P8] Wunsch 等，Optimal statistical inference in the presence of systematic uncertainties using neural network optimization based on binned Poisson likelihoods with nuisance parameters**，2020/2021，[arXiv:2003.07186](https://arxiv.org/abs/2003.07186)。为 nuisance-aware 训练提供可实施方向；当前人工 α 尚不代表完整系统误差。
- **[P9] Alexe 等，Under-coverage in high-statistics counting experiments with finite MC samples**，2024/2026，[arXiv:2401.10542v3](https://arxiv.org/abs/2401.10542v3)。有限 MC 与渐近区间的低覆盖已有系统研究；不能由此把所有跨来源偏差解释成有限 MC。
- **[P10] Dembinski, Abdelmotteleb，A fast and stable approximate maximum-likelihood method for template fits**，2022，[arXiv:2206.12346](https://arxiv.org/abs/2206.12346)，期刊题名为 *A new maximum-likelihood method for template fits*，[DOI](https://doi.org/10.1140/epjc/s10052-022-11019-z)。有限模板的有界方法对照候选，注意本项目列归一化和重权结构。
- **[P11] Argüelles, Schneider, Yuan，A binned likelihood for stochastic models**，2019，[arXiv:1901.04645](https://arxiv.org/abs/1901.04645)。处理 stochastic/weighted MC 的候选，不预先保证本项目边界问题覆盖。

下一轮可直接使用[执行 Prompt](nu_mu_energy_ml_next_step_prompt.md)。本次工作记录见[stage29](../workbook/2026-11-01_stage29_research-reassessment.md)。
