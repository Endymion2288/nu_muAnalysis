# Stage114：从选择诊断回到能量学习——逐通道测量状态、强基线残差与相对时序

日期：2026-11-05。本阶段是研究复盘与下一实验设计，依据最新Stage113及既有汇总、实现和原始论文。**没有读取ROOT/事件NPZ/模型载荷，没有训练、推断、重算物理结果、恢复CERN环境、提交作业或做SHA校验。** 下述旧数值均引用已有报告/汇总；新方法的效果、统计功效、资源和系统误差均为**未测量**。

## 1. 结论与路线修正

目前不能说训练已达到最佳，也没有证据证明现有观测的物理信息已经用尽。但是，重权、门控、概率模型、候选关系、完整点图和遮挡预训练都已有实测，继续更换架构名称的预期研究价值下降。

现在的核心困难是：**同一低重建动量可以对应真正低能、低transfer的事例，也可以对应大transfer的高能事例；减少前者的过修正，常伴随后者的低估。** 数据稀缺、有限表示、优化和响应失配仍可能共同参与，尚未完成因果分账。不能把所有失败归于某一个原因。

建议修订Stage113交接的优先级：下一次实际计算直接做一次**强BDT锚定、具有困难侧保护的逐通道测量状态消融**。已有父分母扩展和producer定义核实保留为解释支线，不再要求六个稀有单元全部有精确区间，才允许任何能量学习。更具物理突破潜力的后续分支是**VetoNu相对延时**以及强子方向约束，不是再做一次计数遮挡预训练。本阶段只交设计，不启动这些实验。

## 2. 最新证据及其边界

|证据|已有实际结果|可以支持的判断|
|---|---|---|
|[Stage113选择测量](2026-11-05_stage113_selection-response-measurement.md)、[主端点](stage113_energy_ml/primary.tsv)|六个完整PHYS，共60000父行；20cut独立/native差0，pz差0 GeV。真50–100 GeV两个charm源零支持；100–200 GeV六源等权Δlog-MSE=−0.09447554689537985，只有309/500完整draw，低于475。|本次程序成员闭合；选择机制已有条件点证据，但最低能主端点不可估、第二箱无约定CI。不是新模型收益，也不是六源普遍改善。|
|Stage113来源55:4，真100–200 GeV|传统log-MSE 0.305088091499621→0.0756443845471646；平均y 0.2444648699331247→0.18247734483038694。|切选伴随transfer组成变化。另一个π来源最低能略反向、K最低能不变、charm无支持，不能统一归因。|
|[Stage110](2026-11-05_stage110_bdt-anchored-relation-transfer.md)、[门槛表](stage110_energy_ml/gates.tsv)|固定关系差转移后，开发test最低能log-RMSE 0.274991，传统0.145661；最低能/传统95%上端2.262072；100–200上端1.059345；all/direct上端1.004233。high-y负tail50差上端+3.013768 pp。|最低能有局部增益，总体保护通过，但两个低能及困难尾未共同恢复。固定α方向已结束，不延长α范围。|
|[Stage108完整点关系](2026-11-05_stage108_full-point-relation-comparison.md)|A/B/C最低能test log-RMSE 0.290846/0.273792/0.310558，all为0.297337/0.297717/0.301478；同split强direct的all为0.287491。|局部关系可以有局部作用；完整网络重学标量映射损失总体优势，遮挡任务优化成功不等于能量表征成功。不是尚未读全点。|
|[Stage73重权](2026-11-03_stage73_reconstruction-energy-reweight.md)，旧split|flat训练最低能OOF log-RMSE 0.148594，对照U 0.270367；eval为0.163625，对照0.310913，但总体/困难侧恶化。|重权不是没试过，也不是完全没作用；它确实改变风险取舍，不能制造独立低能信息。旧split绝对数值不直接与Stage110排名。|
|[Stage68约束优化](2026-11-03_stage68_group-risk-regression.md)，旧split|乘法dual先偏向第一低能组；第400轮第二组dual仍约9.62368e−7。|该次训练不是minimax鞍点或全局最优证据。不能由失败认定当前训练已到极限。|
|[Stage78凸组合](2026-11-03_stage78_nested-risk-complementarity.md)，旧split|五叶、三个专家的受约束组合已实际求解；头训练最坏低能MSE/传统为1.831164。|有限专家凸包/分区存在取舍；本次不能再把“凸组合一下专家”称作新方法，也不能把该结果当所有X策略的界。|
|[Stage79脉冲审计](2026-11-03_stage79_pulse-information-audit.md)|22528通道记录中overflow 2751；Veto10/20/21分别861/872/835，均以2048事件为分母。VetoNu0/1有效形状仅542/505。|读数的测量状态值得研究；这是旧固定样本，不是新split最低能或全池的饱和率测量。|

这里RMSE均是自然对数能量误差的RMSE，无量纲，不等同于百分比能量分辨率。Stage113的N是父行，不自动等于独立incoming；PHYS又已经经过生产/重建过滤，不是完整生成分母。既有区间不含来源抽样、完整parent谱系、refit、研究选择及真实物理系统；开发test反复使用，不能称新blind确认。

Stage113正文§5的“INVAL”附表误放了身份计数表；负reduced的channel计数应引用[原始计数表](stage113_energy_ml/invalid_native_pass_counts.tsv)。例如55:4/VetoNu0的单项影子invalid-pass为432、最终S50为41、eligible S50为32。它们也不是已经证明的坏事件；这里只澄清引用，不改写历史报告。

## 3. 目前真正缺少的三个区分

### 3.1 重建误差、模型附加修正和选择富集

Stage73已在旧split确认低能普通有效事例的大部分误差出现在附加能量修正，而不是所测的muon响应项；Stage113又提示部分选择后总体的低y富集。二者相容，但既没有证明所有重建都正确，也没有证明选择是唯一原因。

令完整观测为X，选择S若是X的确定函数，在其支持上仍有p(t|X,S)=p(t|X)。边缘低能组成变化不能自动成为“模型不可能学会”的理由。另一方面，当前62列并非完整切选/波形记录，不能把该恒等式误用于一个不包含全部相关观测的缩减输入。

### 3.2 状态用于清洗，不等于状态已经作为观测输入

本次静态核实了一个可直接利用现有输入检验的差别：

- [audited_features配置](../ml/configs/audited_features.json)的62列没有11路逐通道status位；[清洗实现](../ml/audited_features.py)使用状态决定NaN。
- [Stage94输入构造](../ml/compare_energy_architectures.py)是62值、62 mask及wave_invalid/fit_failure/calo_invalid三个**事件级**flag；[response实现](../ml/latent_transfer_diagnostics.py)用any把各通道合并。overflow与threshold并不由这三个flag完整表达。
- [原readout读取器](../ml/read_audited_features.py)及[Stage87组装](../ml/resplit_energy.py)的上游缓存路径保有status；可以按(origin,origin_row)回接，而不是按重复run/event猜联结。当前终端未打开这些数组，完整角色的可用性/联结仍须在未来正式任务内验证。
- VetoNu reduced在现行配置中已经是**signed、无数值sentinel清单**；Stage113负读数发现不是“现有模型将所有负reduced设NaN”的证据，不应凭此重写清洗或cut。

物理假说是：同一个积分读数，在正常、触顶、低于阈值或拟合失败时，可靠性及潜在信号解释不同；事件级any可能丢失通道位置和状态组合。**尚未测得这些位在给定62列后的独立增量**，也可能已有读数/mask足以推断，或状态只学到生产差异。因此必须匹配A/B，而非直接宣布找到了原因。

### 3.3 有限模型训练失败，不等于目标不可实现

Stage110只优化一个固定方向；Stage78限制在少数专家的局部凸包；Stage68的有限轮dual存在具体优化限制。这些都不是最优性认证。值得一次检验的剩余问题是：**允许模型学习少量有正有负的新修正方向，同时显式控制困难侧错误幅度，是否能保留强BDT并改善低能？**

## 4. 推荐下一实验：测量状态消融，强BDT固定，残差头可求解

### 4.1 假说、输入及两个匹配臂

使用Stage87现行角色/权重与原62，固定f0=同split strong direct_cal的log能量输出。主候选B与匹配控制A都采用

`fθ(X)=f0(X)+Φ(X)θ`。

传统pz0/0.8和f0为只读参照。不是重新拟合整个神经网络，不是转移旧B108−A108的固定差，也不是按真实能量选择专家。

|臂|残差结构输入|作用|
|---|---|---|
|A|原62＋三个既有事件flag＋共同status_available，共66列|检验仅改善残差策略/优化能做多少；不把train拟合残差称OOF。|
|B，唯一主候选|同A＋11通道×4个布尔状态，共110列|检验通道测量状态的增量，保持同容量、同目标和同预算。|

四位族预定为overflow(bit4)、threshold_failed(bit1)、fit_failure(16|32)、wave_invalid(8|128|256)，依据Stage79已审计语义；它们**不是互斥类别**。不把status整数当连续大小。未知状态保留NaN/availability，不能当正常0；两臂保留全部角色/全部K、缺失及困难者。不要用饱和flag删除事例、把饱和值当坏波形、恢复fitted-charge输入，或从状态直接推算真能量。

### 4.2 有限学习与凸风险头

每臂在train上只建立一次小型残差规则字典：拟议固定8棵depth3树、min_child_weight200，沿用已有树学习率/正则与一个事前seed；目标为t−f0，原incoming权重，不扫描结构。叶指示规则最多64个；保留NaN路由。结构冻结后，θ允许正负，零θ逐位返回f0，部署只读X与真实测量状态。规则字典思路来自RuleFit，但此处头目标由本项目另定，不宣称照搬其算法或性能。[L2]

主拟议头为：最小化τ，使两低能组各自`R_g(fθ)≤τ R_g(traditional)`；all相对f0的MSE≤1.01²，原其余五层≤1.03²。R全部使用该组原incoming加权均值，truth E/y/确认标签只定义train损失组，不作推理输入。

另外对八层分别限制两种连续尾损失不超过f0在train中的值：

`H+_g=mean_w[max(fθ−t−ln1.5,0)²]`

`H−_g=mean_w[max(ln0.5−(fθ−t),0)²]`。

这针对Stage104/110反复出现的困难侧负尾代价，既惩罚越界，也惩罚错误幅度。固定字典后，平方风险和这些单侧平方hinge均对θ凸，θ=0给保护约束可行点；第二次预定求解在τ≤τ*+1e−8下最小化train平均修正平方，避免无依据的大修正。不加事后offset/局部gate，不从开发test选字典、soft-tail尺度或解。

**连续尾损失保护不等于tail50率差≤+2 pp，也不保证留出风险。** 最终仍逐层报告实际正/负/总tail50及原RMSE门槛。凸性只是固定字典中的结构性质；要报告实际可行性、残差和适用的KKT/界信息，不能仅由求解器success称严格最优。找不到好解也只是否定该有限字典/实验，不是信息极限。

该方案比Stage78增加了可学习的signed修正方向、逐通道测量状态以及幅度敏感的单侧尾保护；比Stage68减少了乘法dual与非凸结构同时追逐的混淆。它仍是既有思路的有界扩展，不是新增探测器硬件信息或全新统计理论。[L2–L4]

### 4.3 评价、结束条件与开销

主开发证据为原cal_post中两个低能组的最坏B/f0 RMSE比上95<1，同时交B/A的同一配对端点；只有B/A也有支持，才能把增量归于这个输入族。A/f0有益而B/A不清楚时，只支持残差策略，不支持status增量。区间仍为原500 incoming条件口径，不包装成新独立确认。

两臂/全部输出先锁定，开发test只作一次完整报告，交原八层、状态可用性/缺失、高端、bias/R68及三向tail。最终两个低能/传统上95≤1.05、all/direct≤1.01、其余五层≤1.03、八层三向tail差direct上95≤+2 pp不改。开发增益与最终达标分开判定；不从A/B或raw/offset事后挑赢家晋升。

拟议一个CPU批任务完成缓存联结、必要的固定f0预测、两个小字典、每臂两次预定凸求解及报告；4CPU/8GB、进程内线程1、0GPU，累计CPU≤1800 s、wall≤900 s、最终紧凑产物≤20MB。**这些是拟议上限，不是成本测量或保证**；复用现成软件，QA与计时并入任务，不拆另一阶段。不保存完整新事件副本。若旧train f0输出未存，仅在batch补该固定模型预测，不在本终端加载模型，也不重新训练f0。模型与已有offset已经开发使用，cal_post也不是完全未用数据。

未通过就结束这两个固定方案，不追加树数/seed/状态子集网格。之后选择新的观测问题，而不是延长到一个有利点。若缓存状态缺失，先交精确可用性，在同任务保留A及B的显式missing；不自动扫EOS补源。

## 5. 更有物理新意的后续：相对时间与角度，而非再猜架构

### 5.1 VetoNu迟发信号：值得研究，但尚不能直接投入模型

FASER已发表论文说明：靶内相互作用可经钨核退激产生低能中子，使VetoNu与下游Veto的信号时差区别于穿透μ；reduced charge是在预期背景μ时间窗的积分，附加35 ns用于覆盖脉冲尾。[L5] 这也解释了为什么不能把reduced当普通正能量沉积、把所有小负值视为坏事件。该论文不是当前PHYS精确producer/sentinel定义的替代。

新的待检验假说是：**在给定pz、raw/reduced电荷与状态后，迟发时间结构是否帮助区分“低transfer但有额外活动”与“大transfer且下游漏失”的事例？** 它不同于Stage80已完成的peak/width消融。

可先使用已有PHYS的localtime，不要求完整波形或新模拟。构造少数通道相对时间，例如VetoNu0/1相对一个固定、可靠的Veto参考，并减去由匹配μ控制确定的通道常数和传播/路径项。必须先证明同一采集时间基准；**共同事件时钟若确实作为相同加性项进入两路，差分可以抵消它，所以缺有效绝对trigger时间不在数学上自动否定一切相对时序。** 实际MC clock关闭、通道常数、time walk、光传播、fit fallback及形状有效性仍要处理，不能从这句话跳到“现有时间已校准”。

保留弱信号/饱和/缺失者，新增时间无定义时只新增缺失标记，原模型仍预测；不借有效时间cut净化低能样本。Stage79中VetoNu有效率低、低pz匹配只有1对，是明确限制，不是已获得低能时序证据。单μ的100–1000 GeV控制也不能认证50–100 GeV ν/shower响应。μ超相对论飞行时间本身不是这里的能量计。

CALICE的钨/钢淋浴时间测量支持研究迟发中子成分，并提醒其对材料/Geant4 neutron处理敏感。[L6] 2026-10-30的新预印本将空间、时间等读出逐层比较，也发现时间增量依赖响应建模；这是铜中单强子truth记录的模型条件研究，不是FASER的分辨率承诺。[L7] 两者提供动机，不提供本项目收益数值。

该分支的最小成果应是一个固定相对时间族对原输入的**留出连续能量风险增量**，同时报告可用率和困难侧，不以“时间有变异/可分类”作为成功。若同一时间基准或控制不可交付，结束该分支的当前实现，列缺口；不恢复无限波形/metadata扫描。

### 5.2 强子方向/横向平衡：旧建议未实测，应以可测性为先

Stage67已经提过Myatt/双角思路，本轮不是首次发明。其吸引力是使用方向约束，而非仅总计数/总电荷；近似横向平衡下，可构造类似`pLμ + pLhad·pTμ/pThad`的估计。它需要可靠的强子系统方向/动量流，尤其不能把缺中性粒子、核反冲、磁场后弯折和材料次级当零。

NOMAD原论文确实将Myatt/双角作为不同能量计算方法比较；本轮其PDF正文访问403，仅检索到原文页31片段，公式沿用Stage67引用，不声称重新读到脚注全式。[L8] 当前候选短段的固定名义动量、SP几何弦线或简单中心差不能直接代入。未来只在现有PHYS上先测一个可部署的方向proxy对真实强子轴的来源留出可预测性、覆盖和增量，不把truth角度oracle当部署收益。若可测，再用小的几何模型预测物理量；不再用任意遮挡计数任务作为能量能力代理。

## 6. 怎样处理Stage113尚未解决的支撑和重建问题

1. **保留已有六源实验的失败/不可估状态。** 不删charm、改变draw规则、补到显著或反写端点。
2. 后续若扩Stage105已知允许train/cal来源，应事前固定清单，明确回答“现行基准总体中两个低能与同pz高E由哪些来源支持、传统优势如何随来源/选择变化”。六成分×历史角色仍分层展示；主混合权重应由声明的项目参考总体事前确定，不能因看到空格再挑权重。若目标赋非零权重的单元无支持，该目标仍不可估。不能将unit-MC或历史train/cal各占一半叫自然flux。
3. 不要求一个人为六源等权端点可估，才认为所有现有能量研究有意义；也不能以大量unknown父行等同可加入训练的新低能事件。旧S50已缓存的事件不因重新读取PHYS而变新样本。保持原隔离，未知父行仅诊断。
4. 重建支线只追有机制后果的差异：响应r、transfer u、主μ/leading、拟合/饱和状态、能量依赖的效率/选择；程序成员闭合不等于物理响应闭合。当前选择仍是fitted/reduced，不将40/20/2.5 pC阈值直接套raw，也不因negative标签修cut。
5. 扩展测量与producer核查放在一次完整任务中，报告实际支持/ESS/层级不确定度；复用Stage113已验证实现和已知入口，不重做36例或60000父行作为独立“进展”。没有资源或定义时交具体缺口，但不让无关缺口阻断本来可做的缓存学习实验。

## 7. 架构判断与研究顺序

|顺序|研究问题|方法选择|本阶段能否保证收益|
|---|---|---|---|
|下一次实际计算|逐通道测量状态能否减少错误能量修正？|固定强BDT＋小型规则残差；同一凸风险头，66/110维A/B|不能；效果/功效/成本未测量。|
|解释支线|原目标总体中的低能支撑及选择组成有多稳？|已有明确来源的一次父分母汇总，保留层级与相关incoming|不能用它代替ML改善。|
|新观测优先探索|电荷之外的迟发结构是否增加信息？|少量校准的通道相对时间＋状态；先小BDT/残差消融|未测量；低信号有效性和时基是关键限制。|
|后备物理表示|方向proxy是否能约束transfer？|方向/平衡任务驱动的小几何模型|未测量；不能把几何近邻当真实粒子关联。|
|最后才扩容量|明确的观测/任务有收益后，哪个编码更有效？|小GNN或Transformer作匹配编码对照|Stage108阴性不否定所有架构，但不支持现在再扫大模型。|

TabPFN一类预训练表格模型改变了有限样本归纳偏置，可以作为将来的外部控制；2025原论文主要验证≤10000样本，而当前train为46575条，不能无声抽小训练集后与全量BDT排名。[L9] 同理，FASERCal的多模态/voxel关系预训练来自不同探测器与标注；本项目Stage108的计数任务不等同其语义任务，但该差别也不是再做大规模预训练的充分理由。[L10]

项目目标保持“全区域改善并恢复两个低能层”，不转成只优化概率分数、某一箱、单一AUC或unfolding。来源/parent独立性、真实interaction/FSI、材料、Calo/读出、接受度、背景及未开发确认仍是最终物理使用的缺口。本阶段既没有达到目标，也没有证明目标不可实现。

## 8. 原始文献及对本项目的作用

检索日期2026-11-05。未使用搜索摘要作为本项目测量，不引用二手页面作方法定论。

|编号|原始来源|本次采用的内容和限制|
|---|---|---|
|L1|Gambhir, Nachman, Thaler, [Bias and Priors in Machine Learning Calibrations for High Energy Physics](https://arxiv.org/abs/2205.05084), PRD106 (2022)|回归校准可依赖训练谱；说明检查目标/条件偏差的必要性，不证明所有失败源于prior。已读摘要及HTML统计章节。|
|L2|Friedman, Popescu, [Predictive learning via rule ensembles](https://arxiv.org/abs/0811.1679), AOAS2 (2008)|数据导出的规则可组成线性预测族；本文的残差锚定、约束/尾损失和容量是本项目另拟，不是论文已验证方案。已读原始摘要。|
|L3|Globus-Harris et al., [Multicalibration as Boosting for Regression](https://proceedings.mlr.press/v202/globus-harris23a.html), ICML2023|条件残差/弱学习与回归改进有理论联系；其假设及Bayes结论不认证本实验、真值组或来源相关样本。已读原始摘要，不宣称照搬其算法。|
|L4|Cotter et al., [Training Well-Generalizing Classifiers for Fairness Metrics and Other Data-Dependent Constraints](https://proceedings.mlr.press/v97/cotter19b.html), ICML2019|训练约束与总体/留出约束不同；分类泛化结论不能直接移植为本项目回归与tail保证。已检索原始出版摘要。|
|L5|FASER, [First Measurement of the Muon Neutrino Interaction Cross Section and Flux as a Function of Energy at the LHC](https://arxiv.org/html/2412.03186), PRL134 (2025)|电子探测器信号选择、VetoNu中子时序及reduced时间窗；读到正文与Supplement A。不是现行PHYS精确producer/基线/占位的认证。|
|L6|CALICE, [The Time Structure of Hadronic Showers in Highly Granular Calorimeters with Tungsten and Steel Absorbers](https://arxiv.org/abs/1404.6454), JINST9 P07022 (2014)|不同材料与响应的时间结构实测动机；不是FASER通道时间分辨率或中微子能量收益。已读原始摘要，并检索原文的中子模型讨论。|
|L7|Chung, [Calorimetry as inference: the information content of particle showers and the limits of energy measurement](https://arxiv.org/html/2610.41894v1), 2026-10-30预印本|读出维度的信息阶梯和时间/空间互补的研究设计；铜中单强子truth模拟，与本电子探测器/ν相互作用不同，未据其数值预言提升。已读原文HTML；不是既成实验共识。|
|L8|NOMAD, [Measurement of the Λ polarization in νμ charged-current interactions](https://www.research.unipd.it/bitstream/11577/2467304/1/Nomad_lambda_NPB588.pdf), NPB588 (2000)|页31列Myatt/双角/可见能量作方法比较。本轮完整PDF返回403；仅原文检索片段和Stage67旧引证可用，不伪称读完。|
|L9|Hollmann et al., [Accurate predictions on small data with a tabular foundation model](https://www.nature.com/articles/s41586-024-08328-6), Nature637 (2025)|小表格任务预训练归纳偏置；论文规模边界与本train不同。出版页面正文跳转不可用，实际读取出版检索摘要/方法片段，不据此认证最新软件规模。|
|L10|Alonso-Monsalve et al., [Towards foundation-style models for energy-frontier heterogeneous neutrino detectors via self-supervised pre-training](https://arxiv.org/abs/2604.07037v2), Nature Machine Intelligence (2026)|多模态和voxel语义关系任务与单纯计数重建不同；不同探测器/标注和下游目标不允许移植性能。已读原始摘要。|

## 9. 本阶段交付、验证及下一步

交付本报告、修订路线§96、信息预算§76及[下一步Prompt](../docs/nu_mu_energy_ml_next_step_prompt.md)。历史路线、信息计划、Stage113原报告和Stage54后缀保持；Stage85已完成原data占据控制，不因保留旧后缀重做。当前管理记录仍未晋升后续能量候选；科研基线用同split Stage87 direct，实际服务部署未核查。

只执行Markdown/源码/已有TSV读取、网络论文检索和文档检查。主要本地命令为`rg`、`sed`、`head`、`tail`、`git status`、只读`git show HEAD:<文档>`及`git diff --check`；检查脚本只用标准库验证本地链接、围栏、原历史字节和Stage54后缀，不导入分析包。[文档验证记录](stage114_energy_ml/document_validation.json)给出具体计数：新增本地链接缺失0，围栏/空白检查通过，路线与信息计划历史前缀及Stage54后缀逐字保留。CPU/物理吞吐、I/O和新方法结果未测量。随后仅本地Conventional Commit，不push。

下一任务的验收不是再写研究综述，而是§4固定A/B的完整风险结果、状态增量或明确反证、实际计算资源及失败/不可估原因。计算在有环境的批处理端完成，本终端无需复现。真实信息不足时，与用户讨论具体物理输入，而不是声称又一个架构必然可解。
