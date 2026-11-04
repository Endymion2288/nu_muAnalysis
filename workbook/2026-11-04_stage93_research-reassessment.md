# Stage93 研究复盘：尚未达到训练上限，恢复可归因的架构比较

日期：2026-11-04。本阶段回应用户最新问题：当前训练是否已经最好、换架构是否还有机会、下一步应怎样取得能量重建的实质进展。范围为读取已有 workbook、模型实现和配置，并检索论文；**没有训练、网络推断、读取事件 ROOT/NPZ、重建、提交作业或 SHA 校验**。本报告中的实验数值均引用已完成阶段，新增方法的收益、功效、资源及系统效应均为**未测量**。

## 1. 研究判断与路线修正

**没有证据说明训练已达到最佳效果，也没有证据说明现有观测已到信息极限。** stage88–92 找到并修复了真实的积分和梯度问题，但准确训练后主要风险几乎不变。下一轮应检验输入、表示、决策函数和能量输出模型，而不是继续把数值修复当成主要物理进展。

上次将 seed、结构试验一概关闭过于保守。本次明确修正：不恢复无边界模型扫描，但恢复一次同 split、同权重、同评价条件下的有限架构实验。优先级为 **匹配输入的点回归 MLP → 合理数值变换 → TabM → 直接能量概率模型**；带轨迹/击中关联的集合或图网络作为后续增加信息的路线。没有理由现在优先上大型 Transformer。

原 [stage92 后续请求](stage92_energy_ml/followup_input_request.json)计划的“三 prior 完整准确 quantile stress、0fit”没有在本阶段执行。它保留为历史待办，**不再是进入新模型实验的强制前置**。本报告占用 stage93；下一次实际实验编号为 stage94，以免把研究建议写成已完成测量。

## 2. 最新证据：哪里真的进步，哪里仍然失败

### 2.1 只在同一新划分内比较

[stage87](2026-11-04_stage87_resplit-retraining.md)合并出 89033 条兼容记录，全部 1016 条新增 K 支持保留；14435 条缺少审计 raw/status 的旧记录没有用 fitted charge 填回。source 分组和跨角色 incoming 冲突隔离后，train/cal/test 为 **46575/11612/13189 条记录**，分别为 **37556/10811/12125 个唯一 incoming**；同 incoming 的全部重建视图总权重为 1。

这个 test 是已研究样本池对本次拟合的留出，不是未开发 blind。stage84 与 stage92 的 split、权重不同，不能直接拿两阶段中心值当配对增益；当前正确的主对照是同新 split 从头训练的 direct BDT，而不是可能训练过新 test 的历史 F7 缓存。

下表引用 [stage92 §4](2026-11-04_stage92_accurate-loss-retraining.md)，为 incoming 加权的自然对数能量 RMSE，无量纲；传统估计为 pz/0.8。记录数不等于独立生成事例数。

|test 层|记录数|传统|同 split direct BDT|stage89 准确后验|stage92 准确 loss 后验|
|---|---:|---:|---:|---:|---:|
|真 E 50–100 GeV|183|0.145661|0.282644|0.169296|0.165630|
|真 E 100–200 GeV|856|0.247937|0.246329|0.231281|0.232842|
|全体|13189|0.557190|0.287491|0.326783|0.326058|
|真 E ≥200 GeV|12150|0.578219|0.290487|0.334911|0.334085|
|重建 pz 50–100 GeV|659|1.275310|0.498966|0.597693|0.597293|
|低 pz 且真 E ≥200 GeV|297|1.887790|0.658177|0.828213|0.826918|
|high-y|385|1.618799|0.609395|0.807754|0.781673|
|未确认|468|1.638613|0.551305|0.688945|0.665024|
|输入缺失|5|0.253034|0.203231|0.226801|0.290567|
|真 E 3200–6400 GeV|264|0.995785|0.683271|0.758477|0.756072|

这里有真实的方向性进展：当前后验在最低能区明显优于同 split BDT，并在 100–200 GeV 中心值优于传统。但它没有同时保住总体和困难高能事例。最低能相对传统的条件 95% 比值上端 **1.411172**，全体相对 direct 的上端 **1.155451**，低 pz 真高能和 high-y 相对 direct 的上端 **1.325036/1.337601**，仍未通过原目标。新/旧后验的主要配对区间含 1，不能把 stage92 的小变化称为显著物理改善。

最低能 median bias 为 **+7.209845%**，正 tail50 为 **3.278689%**；低 pz 真高能 median bias 为 **−33.435078%**，正/负 tail50 为 **12.916544%/34.237688%**。后一层相对 direct 的 total/positive/negative tail50 差的条件上端为 **+16.822348/+4.816155/+14.337707 pp**。这不是只差一点总体分数，而是“低能过修正”和“隐含大 transfer 的高能被低估”仍同时存在。

cal 最低能新/旧 RMSE 为 **0.243608440/0.235912479**，方向与 test 不同；183 条最低能 test 和单 seed 都不支持精细选模型。现有 500 次 incoming 条件 bootstrap 不含来源、parent、重训、校准估计、系统效应和研究选择；每角色 source/incoming 图只有 3 个连通块，使现有 source95 不可估，但**不是说只有 3 个独立生成事件**。

### 2.2 已经回答过的问题，不再当作新方案重做

|已完成阶段|实际发现|对下一步的约束|
|---|---|---|
|[stage73 重建取证与能谱重权](2026-11-03_stage73_reconstruction-energy-reweight.md)|当前 X 没有发现可复现的行对齐、单位或状态传播错误；低能正尾大多 raw/Calo 有效。固定重权改善低能，但伤总体及低 pz/high-y 等层。|不再把“重权后低能变好”当作新发现；仍不能排除所有真实重建系统效应。|
|[stage85 tracker 控制](2026-11-03_stage85_tracker-occupancy-control.md)|各 2048 data/MC；raw strip/event 为 137.606445/29.061523，raw excess 的 96.467% 在实际 01X clustering 接受窗之外；远离轨迹邻域 cluster/event 为 3.718750/6.427734，方向相反。active-channel 分母、quiet/random trigger 缺失。|测到的是条件活动，不是纯电子噪声占据标定；停止反求 noise 参数。data/MC 失配本身不能解释 nominal MC 内部回归失败。|
|[stage86 transfer 标签](2026-11-03_stage86_latent-transfer-diagnostics.md)|严格 zero transfer 为 0；旧最低能 208 条均 response-nominal，确认低 transfer 子集 181 条；低 pz 真高能 299 条的 transfer fraction 中位数 0.806796。|不做严格零点质量模型，不按低 pz 硬切传统估计；普通有效事例也有正尾。此处人数来自旧划分，不能替代 stage92 的 183/297。|
|stage88–92 数值链|stage92 完整 cal/test 24801/24801 通过准确推断检查；准确 loss 和完整 cal 单次优化可执行。|复用已认证核；改变模型时只核新增数学部分，不重开全链认证。|

能量分箱 reweight 仍可作为**事前固定的风险政策**，不是增加低能信息的方法。它改变优化时谁更重要，不能把少量低能事例变成新的独立支持，也不能凭空区分同一低 pz 下的低能与高-y 高能。

## 3. 为什么还不能声称训练最优

### 3.1 当前只是一个较窄的训练点

当前 posterior 是 **41 项观测量 → 85 项网络输入**（41 变换值、41 missing、3 status），**2×64 SiLU MLP**；单 seed 2026110387，Adam lr=0.001、batch=1024、150 epochs/6900 steps、无 weight decay、无 early stopping。loss 为 **−joint NLL−0.25 marginal logE NLL**，不是直接的点能量平方误差。

stage92 的 train loss 在 25/50/75/100/125/150 epochs 为 **3.819538898/3.743086890/3.702413284/3.668432253/3.645791900/3.623436926**，仍下降；这只证明还在拟合训练目标，既不证明应继续训练，也不证明已经收敛。当前没有对应的验证学习曲线、多个 seed、匹配输入的架构对照和损失消融来回答最优性。

### 3.2 BDT 与后验没有用相同输入

direct BDT 有 62 项审计输入，当前后验只用其中 41 项。缺少的族包括 nDoF、VetoNu 位置/约化读出、SP 横向均值和 RMS、px1/py1、轨迹下游端点/跨度/斜率、module eta/phi、z_atMaxRadius、SCT_error。它们未被证明有增益，但也未在当前准确后验和新 split 下被证明无用；这里的下标 1 是轨迹另一端的状态，不是第二条轨迹。

恢复 62 项应是一项受控消融：保留 raw11、typed NaN、状态掩码、合法负 raw、Calo 缺项语义，以及 **pz0-only 的一次方动量约定**；不借此偷偷加入 p0/p1/pz1 或历史禁用的动量比。

### 3.3 输入表示也没有匹配

当前 posterior 对 raw 量直接做 train-only median/IQR，再硬截断到 ±20；stage87 记录 train 被截断单元 **18352 个**。计数、正能量和有符号读出量的量纲/长尾不同，同一个阈值会把一些合法远尾压到完全相同的网络输入。

应单独比较：正量 log、计数 log1p、有符号量 asinh，尺度只从 train 得到；保留 missing/status，不把合法负 raw 截成 0，也不删尾部事例。分箱边界、变换尺度和 clipping 比例需报告，具体可用性由小 QA 验证。类似变换在 stage62/69 出现过，**本轮的新问题是移植到当前 split、统一输入并控制其他变量，不是发明了新变换**。

数值 embedding 是之后的小幅结构扩展，优先于直接扩大 attention。论文表明收益可能来自数值表示本身，而不全来自 Transformer。[On Embeddings for Numerical Features，NeurIPS 2022](https://arxiv.org/abs/2203.05556)

## 4. 优先检验的新方向

### 4.1 对同一个后验，先让点估计与评分一致

令 z=ln(Eν/GeV)。若主要评分是 log-RMSE，则在正确后验下的平方损失最优决策为：

\[
\hat z(x)=\mathbb E[z\mid x],\qquad
\hat E(x)=\mathrm{GeV}\,\exp\{\mathbb E[\ln(E_\nu/\mathrm{GeV})\mid x]\}.
\]

当前主输出是 posterior median，对应绝对 log 误差的决策。**exp(mean logE)、mean E、median E 是三种不同输出**。先在同一 stage92 后验、同一名义 prior、同一 b/T 上比较 median 与 exp(mean logE)，无需重新训练。

这不是保证所有真能箱都改善：若分布有右尾，mean logE 往往比 median 大，可能改善低 pz 真高能却伤最低能；模型失配时，连总体改善也不保证。需要完整保留困难层和全部正负尾。stage76 曾对旧条件 score 密度做过 mean-log 决策，但那不是当前 stage92 的物理后验，不能据旧失败跳过此检查，也不能将这项想法写成首次提出均值决策。

只对 training prior，利用 z=ln(mμ+pz·exp r)−ln(1−f) 可把每个独立分量的期望化为平滑一维期望；名义 prior 的分段重权破坏简单因式分解，必须纳入归一化。已有 density/CDF 认证不能自动认证新增 moment。只需对新增 moment 做固定小 cal 的独立误差/尾界检查和计时，不重建 stage88–91 链；若成本不合适，此诊断不阻塞新模型训练。

### 4.2 先回到能量目标，检验物理潜变量瓶颈是否必要

当前模型按 f=0.1 分区：一个低 transfer 分量和两个高 transfer 分量，每个分量对变换后的 r、s 采用独立 Normal；混合可以诱导相关，但单分量内没有可学习相关系数。这样的输出族和 joint 权重可能把有限容量花在 latent 分解，而非能量目标上。**这是结构性假设，不是已测因果结论。**

建议先做容易归因的一维 residual MDN：

\[
u=\ln(E_\nu/\mathrm{GeV})-\ln[(p_{z,0}/0.8)/\mathrm{GeV}],\quad
p(u\mid x)=\sum_{k=1}^{3}\pi_k(x)\,\mathcal N(u;\mu_k(x),\sigma_k(x)^2).
\]

使用相同 62 输入、相同 typed 变换和相同 MLP 主干，只用 marginal NLL 训练。均值、CDF、密度可直接算；点输出用 exp(mean logE)。用 residual 只是重参数化，**不按 pz 硬切传统，也不强迫 Eν≥重建 pz**，因为重建动量可能高估。

若能量概率路线有增益，再比较单调一维 rational-quadratic spline，或将联合分解改为 **p(z,f|x)=p(z|x)p(f|z,x)**：能量是主输出，transfer 标签用作辅助或诊断，不强制成为能量推断的瓶颈。对比原 joint 监督时另做固定消融，不同时扫辅助权重。Spline 的可逆性有方法依据，但本项目精度收益未测量。[Neural Spline Flows，NeurIPS 2019](https://arxiv.org/abs/1906.04032)

另一低成本概率对照是 NGBoost，用树直接输出分布参数；单 Gaussian NGBoost 只能检验概率树基线，不能假定它解决多模态。[NGBoost，ICML 2020](https://proceedings.mlr.press/v119/duan20a.html)

### 4.3 恢复一次当前条件下的 TabM 比较

[stage16](2026-10-30_stage16_tabular-model-physics.md)已经测过 TabM：旧 F5 的全体 log-RMSE **0.283253→0.280664**，macro **0.373879→0.367379**，旧 macro 差的报告区间为 **[−0.012371,−0.001845]**；high-y 差区间跨 0。旧普通 MLP 和 ResNet 没有同等收益。这是“TabM 值得复测”的内部证据，不是当前 clean62/new split 的显著性证据。

TabM 用共享参数的多 MLP 集成，在表格任务中是合适的候选；当前约 3.76 万唯一训练 incoming，也更适合先做这一级别的试验。复用 `ml/train_tabular.py` 中已有实现，但重接当前 split、权重和审计特征，不能直接重用旧 loader/旧 fitted-charge 语义。[TabM，ICLR 2025](https://arxiv.org/abs/2410.24210)

架构建议排序如下，收益均未测量：

|方案|当前优先级|要回答的问题|
|---|---|---|
|匹配输入/表示的 MLP 点回归|最高，必要控制|问题是否主要来自 41/62 输入差异、表示或训练目标？|
|TabM 点回归|高|同一信息和目标下，集成式结构能否改善低能与困难组？|
|直接能量 MDN，随后一维 spline/NGBoost|高|是否应绕开当前 latent 联合模型和高成本边缘积分？|
|ResNet / FT-Transformer|第二轮|先验没有普适赢家；第一轮不能解释现象时再用一个固定配置交叉验证。|
|TabPFN 类预训练表格模型|探索备选|先核当前版本的支持规模、样本权重和成本；不能把原论文 ≤10000 样本的主要实证直接外推到本项目。|
|多轨迹集合 / GNN / 带关联的 Transformer|信息升级后优先|是否有被 leading-track 和总体摘要压掉的事例拓扑？|

表格架构没有普适赢家，Transformer 不是天然优于树或 MLP。[Revisiting Deep Learning Models for Tabular Data，NeurIPS 2021](https://arxiv.org/abs/2106.11959) TabPFN 的预训练思想可保留为后备，但不应以截掉困难事例凑小数据集来迁就模型。[TabPFN，Nature 2025](https://www.nature.com/articles/s41586-024-08328-6)

### 4.4 更有物理动机的 GNN：软缪子候选与击中关联

真正值得新增的信息方向不是把 62 个数当作图节点，而是避免过早只保留最高 pz leading track。`AnalysisZipFramework/config/output_columns.yaml` 已列出全轨迹的 hitSet、Chi2/nDoF、端点/方向、station/layer、module eta/phi、charge，以及向 veto/Timing/Calo 的外推位置。**配置里有列名，不等于当前全部缓存实际有有效载荷；协方差和关联可靠性未核实。**

在后续允许提取新摘要时，先保留小规模候选集合：轨迹—击中共享、跨 station 延续、与 veto/Calo 响应几何匹配，学习软缪子身份，再与其余活动融合预测能量。可以先用 Deep Sets 或小 attention；有实际边关系再上 GNN。未来新增候选动量变量需单独冻结物理约定，不能默默解除当前 pz0-only 规则。

[stage19](2026-10-30_stage19_deep-sets-physics.md)已做过普通全 SP Deep Sets，未建立超越 summaries 的增量；这不等于否定轨迹—击中关联，也意味着不能把再跑同一全 SP 网络包装成新方向。Particle Transformer 的启发是把有意义的成对关系放入 attention，而非机械借用 jet tagging 模型。[Particle Transformer，ICML 2022](https://arxiv.org/abs/2202.03772)

新近的 FASERCAL 研究用异质探测器编码器、masked reconstruction 和关系辅助预训练，支持“先保存关系，再研究表示学习”这一长期方向；但它研究的是拟议的高粒度 FASERCAL，不是本项目现有探测器，收益不可照搬。[Alonso-Monsalve 等，Nature Machine Intelligence，2026-09-30](https://www.nature.com/articles/s42256-026-01309-6) 当前没有必要为此启动大规模自监督预训练。

### 4.5 一个便宜的机制诊断，留作后续而非再开大网格

若 posterior 的能量读出仍差，但主干可能已经提取有效特征，可固定 stage92 主干，只拟合 weighted ridge/线性 logE readout，观察点损失是否明显恢复。成功说明表示中有可用信息、读出/目标值得改；失败不证明信息极限。它需要在有环境的节点做一次 forward 和小拟合，**本阶段未执行，也不额外塞进 stage94 的五格主实验**。

## 5. 必须修正的统计解释：真值分箱 PIT 不是后验均匀性条件

正确连续后验满足 **U=F(Y|X) 在给定观测 X 时均匀**，因此在由 X 定义的组内也应均匀。它一般**不要求给定真实 Y 区间后仍均匀**。反例：没有信息的 X，Y 在 [0,1] 均匀，完美后验 F(Y)=Y；只取 Y<0.2 后，PIT 自然只在 [0,0.2]，均值 0.1。

因此 stage92 的最低能 meanPIT **0.329238**、低 pz 真高能 **0.633521** 是有用的真值分层诊断，却不能单独证明后验错误。真值高端 coverage **18.784722%/51.901042%** 是物理使用上的警示，也不能自动解释成贝叶斯后验失准。过去路线把这些真值组的 PIT 必须含 0.5 当作后验正确性要求，解释过强，本次修正。

原始表和点风险/尾部保护全部保留；不因解释修正把旧模型改判通过。后续：

1. 同时明确评估总体、incoming 权重与名义 prior 是否对应同一个目标分布；旧风险表不改，校准诊断另报事前定义的目标权重，不能从 test 估计新谱。
2. 检查总体 PIT 全形状，而不只检查均值。stage92 总体 meanPIT **0.527489560 [0.522613,0.532034]** 仍是需要解释的总体偏移，但须考虑目标谱及现有条件区间的局限。
3. 在 cal 上预先定义 pz、活动、Calo、质量/缺失等 **观测空间**分组，必要时用 cross-fit Cal-PIT 找局部校准问题；新 post-calibration 拟合不能再用 test。
4. 如果物理要求是固定真 E 的频率学 coverage，应通过 forward response/Neyman 或明确的频率学区间目标构造，不能要求后验 credible interval 自动具有这一性质。

Cal-PIT 提供局部观测空间诊断与重校准的方法依据；它不是补回缺失信息的工具，也不保证点重建门槛自动通过。[LADaR / Cal-PIT，2025 修订版](https://arxiv.org/abs/2205.14568) HEP 文献也强调回归校准的 prior 和损失依赖。[Bias and Priors in Machine Learning Calibrations for High Energy Physics](https://arxiv.org/abs/2205.05084)；[Learning Uncertainties the Frequentist Way](https://arxiv.org/abs/2205.03413)

## 6. 下一轮最小可归因实验：stage94

### 6.1 输入、选择与测试边界

复用 stage87 的角色、权重和兼容输入，完整保留 missing、K、高端、低 pz 真高能、high-y 和全部尾部。复用已有同 split direct/传统控制。**没有新样本不是停止开发实验的理由**；但所有结果仍标为开发，不宣称独立确认，不按 test 选择 checkpoint、模型、变换、prior 或阈值。

在看新候选结果前，将原 cal 按 source 分成 `cal_select` 与 `cal_post`，共享 incoming 冲突按事前优先级 purge，完整记录被隔离的 cal 记录；新子集人数/低能支持目前**未测量**。outer train/test 不变，全部 outer cal 仍在最终报告中，只有拟合用途分开。若来源和低能支持不足以可靠分开，改用固定预注册训练轮数与完整 cal 单次后处理，**放弃本轮 early stopping/候选选择，不借 test 补位**。

所有点模型使用 weighted log-MSE；同类网络采用相同 optimizer、预注册最大 300 epochs、每 5 epochs 检查 cal_select、patience=30 epochs。超参数是本轮提议，不是已测最佳配置；在读取候选 cal 指标前冻结。MDN 用 marginal NLL 训练，cal_select 同时报 NLL 与对齐点风险，checkpoint 依据预先固定的点风险规则。不同架构的参数量、训练时间必须报告，不能声称严格等容量。

各点输出只在 cal_post 拟合一次共同定义的全局 log-offset；不做分箱/真值校准、逐模型先验扫描或困难事例 gate。缓存 BDT 可用已存 cal 预测重新计算同一定义的 offset，不算重新训练；旧原样基线另列，原物理门槛仍与原样对照。密度输出必须与所用 offset 一致变换，报告未校准与校准两组 NLL/PIT，不能只平移点估计而仍称原密度的决策。

### 6.2 恰好五格，不做大网格

|格|输入与预处理|模型/目标|主要解释|
|---|---|---|---|
|A|41；当前 median/IQR±20 与掩码|2×64 SiLU，log-MSE|去掉 latent/joint 路线后的点回归控制|
|B|62；同 A 的预处理规则|同 A 主干与目标|B−A：补齐输入的作用|
|C|62；typed log/log1p/asinh 与掩码|同 A 主干与目标|C−B：输入表示的作用|
|D|与 C 相同|TabM、log-MSE；首轮不额外加 numerical embedding|D−C：TabM 结构方案；报告参数/算力差异|
|E|与 C 相同|同 C 主干，3 分量 residual logE MDN、marginal NLL|E−C：能量分布建模方案；输出族与 loss 一起变化，不单独归因为其中一项|

主实验最多 **5 个预注册单 seed 拟合**。若有 cal_select，在打开新 test 结果前，根据两个低能层和困难组保护的预注册排序，最多选 2 格，各增加 2 个 seed，故总上限 **9 个新网络 fit**。不得从 test 上选幸运 seed；预先定义单 seed 展示和固定 seed 集成。没有有效 cal_select 则停在固定五格，并将 test 比较仅作开发探索，另轮预注册确认。

同时可交付 stage92 median/exp(mean logE) 固定读出诊断；准确 prior stress 的 bin/PIT/NLL/ESS 可代数复用，但不为三个新 quantile 全量重积分挡住五格实验。所有新 moment、density 数值只检验新增部分；旧准确核不重复审计。

### 6.3 评价、资源和验收

必须交付：train 与 cal_select 学习曲线；各格及原样控制的完整 cal/test 点风险；50–100、100–200、全体、≥200、低 pz、低 pz 真高能、high-y、未确认、高端和 missing 分层；log-RMSE、median bias、R68、总/正/负 tail50；概率模型 NLL、区间宽度、总体和 X 分组 PIT/coverage；500 次相同 incoming 条件配对及 seed 波动。真 E 和真 y 分组用于物理风险诊断，不能作为部署 gate。

原**点风险**验收保留：两低能/传统的条件 95% 比值上端 ≤1.05，全体/direct ≤1.01，≥200 与困难层/direct ≤1.03，既有七层及额外低 pz 真高能双向 tail50 差上端 ≤2 pp。通过有限开发条件门槛不是最终物理证明；没有通过全部目标也不等于实验无价值，若能隔离出输入/表示/目标的稳定增量，就得到明确的研究结论。

拟议资源边界为 ≤9 个新网络 fit、同时 ≤1 GPU、累计 GPU 任务 wall ≤2h、累计 CPU ≤6h、紧凑最终 ≤20 MB；**均待小 QA 实测后冻结，不是性能承诺**。先 ≤40 固定 train/cal 记录核 schema、单位、权重、缺失、梯度/输出和计时；大批量只通过配置好的 batch 服务，不保存事件/逐 hit 副本，模型/紧凑预测不入 Git，复用原缓存避免重复大 I/O。不能在预算失败后静默缩样或删困难事例；精度与资源不能同时满足时先报告缺口。

### 6.4 结果如何改变后续路线

- **B 优于 A：**把输入合同统一作为主修正，后续后验不能继续使用未经消融的 41 项压缩。
- **C 优于 B：**优先修表示；不能把 raw MLP 的失败归咎于神经网络家族。
- **D 稳定优于 C：**沿 TabM 做一轮小范围容量/embedding 消融；不立即扩大为所有架构竞赛。
- **E 恢复总体/困难侧且保住低能：**将直接能量分布列为主概率路线，transfer 变成辅助分解；再研究 spline/局部校准。
- **所有格均未建立联合收益：**不是“无思路”，而是现有摘要上的这一轮方法变化没有解决问题；转向轨迹候选/关联信息预算，或明确测量可辨识的概率/总体物理目标，不能无限重复 reweight、gate 或积分阶段。

若只出现真实 Pareto 改善，即部分层改善、另一些层受损，应如实给出风险前沿。stage68 的旧对偶权重饱和和当前单个模型均不能证明最终目标不可能；也不应承诺一个模型一定在所有真实能箱逐箱击败不同基线。

## 7. 文献取舍与最终目标

外部中微子研究支持利用可见末态推断不可见能量，但不同探测器的信息条件不同。Kopp 等在 DUNE 场景使用 dense NN 的工作，支持“先问输入和可见/不可见分解，再选架构”，不支持把文中改善倍数搬到 FASER。[Improving Neutrino Energy Reconstruction with Machine Learning，2025 修订](https://arxiv.org/abs/2405.15867)

近期 FASER 乳胶探测器的公开说明也强调多条带电粒子的动量与角度用于能量重建；可借鉴保留末态结构的思路，但本项目的电子学读出不等于乳胶重建，不能直接引入这里不可观测的变量。[FASER 官方说明，2026-03-25](https://faser.web.cern.ch/briefing-20260325/)

最终项目目标仍为：**利用可部署的实测观测，在 pz>50 GeV 的完整选择中，同时改善低能和整体能量重建，并控制困难事例、尾部和真实数据迁移风险。** 下一轮先取得一个可归因的模型结论；后续才将有增益的方案送入 interaction/FSI、材料/输运、Calo、接受度/背景和真实响应变化检查，最后寻求真正未开发支持上的确认。当前阶段不能用 data/MC 重权、总体 coverage 或新架构名字代替这些证据。

## 8. 本阶段工作、验证与产物

本阶段读取 stage16/19、stage68/69/73/74/76、stage85–92 及当前模型/配置；检索上述原论文、Nature/会议官网与 FASER 官方资料。没有计算新的事件指标，表中的中心值和区间直接引用 workbook。新增文档为本报告；在修订路线 §75、信息计划 §55 追加结论，重写下一步 Prompt 主任务为 stage94，并逐字保留 stage54 后缀。历史 stage92 JSON 请求不改，只明确其研究优先级已由本报告更新。

文档验收已通过：`git diff --check`、13 处本轮新增本地引用、Markdown fence/表行检查；两份路线旧正文的完整字节前缀与修改前一致，stage54 后缀的完整字节与修改前一致。另核对 stage16 的 TabM 原表、62−41 输入差集和轨迹端点定义；未导入分析运行环境。这些检查不是 SHA 校验，也不是代码/物理结果复现。实际新增模型收益、训练/推断时间、I/O、显存、功效、系统效应和独立确认：**未测量**。
