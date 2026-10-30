# 阶段24预注册：箱内谱形响应积分（2026-10-30）

本协议与ml/configs/within_response.yaml在本阶段任何12-bin/shape响应、谱拟合或统计结果出现前冻结。
沿用stage23的13375例validation、22来源组、A/B双向交叉折、unit MC及全部异常/流出。
只比较μ/0.8、阶段22 BDT UU和阶段21 TabM UU（三seed）；不再训练、选参或打开保留集。
主reco固定为stage23十类energy bins；不改变六个100–6400 GeV倍增报告truth bins。
不继续在统计不足的rank分箱上选模型。所有结果是既有validation再诊断，不是独立test/data。

## 预先固定的方法与假设

注入alpha=-1,0,+1：伪数据按(E/报告箱几何中心)^alpha重加权，
每个报告truth箱恢复原bin计数；每次bootstrap也如此。六bin真谱严格不变。
响应仅从另一来源折构造，不读伪数据的truth箱内形状。alpha作为已知注入条件给响应，
不拟合它、不用真实data/伪数据truth推断它；正确alpha是诊断性已知条件，不是已解决的nuisance。

1. coarse6：固定nominal六箱平均响应，全部alpha使用同一R0，复现stage23。
2. fine12：每个报告箱仅在几何中心分成两个半对数内部箱，不扫其他划分。
   R_sub按响应折nominal子箱计数归一；子箱混合比例g(alpha)由响应折的
   sum (E/Ecenter)^alpha计算。R_b(alpha)=sum_sub R_sub*g_sub(alpha)。
   保留六个待估fractions，不自由拟合12个子箱产额；子箱内响应仍不随alpha变化。
3. continuous：直接在响应折按同一连续权重估计六箱R_b(alpha)，包含子箱内变化。
   是给定alpha下的事件积分参考，不用伪数据标签修正响应，也不代表新增探测器信息。

alpha0时三方法R与所有拟合应一致。fine12仅近似处理两个半箱的相对占比，
比较fine12与continuous可检验半箱内部剩余依赖；不能把减小closure bias当成信息增加。

## 主评价和统计

主指标：相对本方向nominal拟合的注入偏移
s_b(alpha)=(fhat_b(alpha)-fhat_b(0))/ftrue_b，
对六报告bin、seed、双向及alpha±的s²等权平均后开方。不抵消相反signed偏移。
先对每个alpha单独报告，再作预注册±合并；同时报告总闭合bias=fhat/ftrue-1、逐bin值、deviance、
已知R/alpha的N=1000 Fisher相对σ及相关。总闭合改善和消除注入偏移是不同问题。

500次来源组配对bootstrap，沿用stage23 seed及11/11组抽样规则，跨方法/模型/alpha共用抽样。
组权重同时用于响应、子箱占比、伪数据truth/reco；重做各truth箱内权重归一。
保存signed bias/shift的紧凑数组，主方法差给共同有效重复的95%百分位区间。
所有区间未作多重校正、条件于模型/折/所选模板，不作最终独立确认显著性。
空内部truth箱也保留并计失败，不借伪计数/合并/删事件修复；报告失败比例与有效重复。
coarse/continuous即使fine12失败也独立保留。失败>1%不能将条件区间当无条件稳定性证据。
RMS非负，不用其正的百分位区间检验零bias。模型间比较仅描述性，不新增架构选择。

补充局部Fisher：在alpha0用响应折精确导数
R'_b=E[I_reco log(E/Ecenter)|b]-R_b E[log(E/Ecenter)|b]。
将一个全箱共同alpha方向R'f加入五个simplex谱方向，计算无先验/无边界的局部profile协方差，
对比alpha已知时的σ、alpha的σ、相关和条件数。仅一个全局alpha是乐观的形状自由度诊断，
不是六箱独立nuisance或经过toy验收的实际拟合；不加人为先验来制造好看的精度。
每个bootstrap同步重估此导数。不可辨识按原1e-10阈值报告，不用伪逆。

## Toy与程序控制

每seed/方向/alpha生成200个N=1000多项式toy，两种law：
- cross_source：均值为伪数据折的相应重加权reco分布，包含有限MC和跨来源闭合偏移；
- response_control：均值为响应折continuous R(alpha)*ftrue，是已知响应的积分近似控制，
  不冒充独立MC物理闭合。
每种law同一组toy counts用于三方法，逐方法拟合；alpha0三方法只算一次并复制。
记录bias/RMS、±Fisherσ覆盖率、pull、碰边界及失败。
这些coverage条件于两折经验分布，不是包含响应MC/系统学的真实data置信区间。

合成反例同时验证fine12能修正子箱混合而仍可能遗漏子箱内变化；
导数差分验证、alpha0三方法恒等、权重归一/报告真谱守恒、source子箱总数、
实际响应exact forward self-closure、事件键及stage23 nominal复现均须检查。
SLSQP/梯度/容差/失败处理完全沿用stage23，无平滑、ridge或正则化。

## 执行、验收与边界

先本地每折每报告bin最多150例、seed0、8 bootstrap/8 toys验证μ/TabM。
再3个Condor单核CPU作业，无GPU训练；CVMFS LCG109，BLAS/OpenMP单线程，3000MB，espresso。
预聚合group×12内部truth×reco×权重矩，只在小数组上bootstrap，不重复EOS扫描；
最终只保留紧凑表/矩阵/重采样数组，无逐事件新缓存、模型checkpoint或ROOT输出。

验收必须回答：已知形状时，12内部箱是否减小±注入偏移？连续积分还有多少剩余？
总闭合改善是否也获支持？放开一个共同shape方向损失多少统计信息？
有限MC、子箱稀疏及toy边界是否限制判断？结果可为负，不根据结果改分箱/权重/协议。
写中文阶段报告、更新路线图，完成一次Conventional Commit及提交内容读回核验。
flux/生成归一化沿用用户授权默认unit；背景/接受度、生成器/探测器系统学及data未测量。

方法参考沿用stage23的前向推断文献，并补充检索nuisance/profile信息的标准统计参考。

补充检索（冻结时读取arXiv标题）：Cowan et al., arXiv:1007.1727，
“Asymptotic formulae for likelihood-based tests of new physics”；Cranmer, arXiv:1503.07622，
“Practical Statistics for the LHC”。采用其nuisance/profile与渐近区间的适用性思想，
具体执行为一个共同alpha方向的局部Fisher和有边界toy检查；不直接套用高斯结论于稀疏高能bin。
