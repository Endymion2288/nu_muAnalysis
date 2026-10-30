# 阶段26预注册：来源比例匹配与有限MC随机拆分对照

2026-10-30，在本阶段任何closure/coverage或随机化结果产生前冻结。
承接阶段25，不训练新模型，不读calibration/test/SIBYLL challenge标签或预测。
继续13375例validation、22来源组、六truth箱100–6400 GeV、十energy reco类、
μ/0.8、stage22 BDT UU三seed、stage21 TabM UU三seed；unit MC，全部异常/流出保留。
本阶段完成来源/有限MC诊断，真实data、MC响应nuisance拟合与一般无条件覆盖留待后续。

## 输入支持度审计（仅计数，不是本阶段物理结果）

按原A/B折检查六nominal run×六truth箱：200082/200093的最高truth箱两折均为0，
其余34个共同有占有的stratum在两折均>0；最少单侧计数2例。
不补伪计数，不删除任何事件；两侧都为空的stratum在该bin共同目标权重为0。
若随机group折只在一侧为空，matched诊断标记unsupported，不能丢掉该stratum强行匹配。
raw仍计算。所有随机化请求数、有效数与失败保留。

## 两个固定case及形状注入

raw完全复现阶段25 continuous response，原A/B双向、不改变数据/模型/分箱。
run_bin_matched：每个truth箱，以全部validation的nominal run占比为共同目标。
在每个run×truth箱内对exp(alpha log(E/Ecenter))独立归一，再混合为目标占比。
响应与伪数据共同匹配，且目标在alpha=-1/0/+1与拟合alpha间固定。
每case的六truth积分均为伪数据折原nominal fractions，不改变六箱真谱。
匹配case的alpha变化有意保持run混合不变；非零alpha下不声称它与raw的整体箱内倾斜是同一个干预。
这是使用truth/run信息的反事实诊断，不是可直接用在data的重建或可部署响应。
目标仅由原样本定义，随机化时固定；不按结果挑目标或分箱。

对每case沿用阶段25 known-alpha与unknown共同alpha的点拟合、三起点、约束、梯度、容差与数值域。
中心全部alpha给fraction/alpha/bias/deviance、直接响应与导数核验。
不做新的端点扫描或Fisher误差膨胀。

## 两级随机化：检验来源差异是否超出有限拆分波动

每级200次，跨模型/seed使用同一分配，保留双向相关性：
1. event_stratified：在每个run×truth箱内均匀置换A/B标签，严格保留原A/B stratum计数。
   破坏来源组归属但保持run混合、truth积分与两侧统计量。零假设是这些stratum内事件可交换；
   不自动保留组内相关性，不可直接称真实MC总体分布。
2. group_component：在charm/k/pi内整组置换A/B标签，保持原A组数2/5/4，ν/反ν组不拆。
   保留组相关性，允许run/bin计数波动；matched若缺共同支持明确记失败。
   group数很少尤其charm3组，不能把此检验当独立生成器系统学。

每置换双向、alpha=-1/0/+1、两case、known/profile点拟合。
报告closure RMS、alpha偏移RMS与原分配的相对位置；不以signed双向平均抹掉偏移。
预定主检验为alpha0/profile下三模型×两case×两null×两统计量=24个p值，统一Holm校正。
p=(k+1)/(B_valid+1)，并报告k/B/有效数；matched group-null若无支持，解释为条件于可支持分配。
所有alpha的未校正描述表都保留，不依结果筛选模型或注入。

## 覆盖与伪数据计数的分离

原分配：每model/seed、双向、三alpha、两case、两law各200 toy。
两law为cross_source（另一折经验分布）和response_control（本折响应×true fractions）。
在case/law间共享N=1000个uniform随机数，经各自CDF映射为multinomial计数，保留配对。
unknown-alpha实际profile LR≤1是主覆盖；固定真实alpha的点拟合仅复用来计算alpha自身LR，
不重复计算known-alpha六fraction LR（阶段25已有这一比较）。所有fraction LR和alpha LR都保存。
原raw中心与阶段25核对；本阶段toy RNG新冻结，不假称逐toy复现旧RNG。

event_stratified零假设的每次分配：仅alpha0、双向、两case/两law各一个独立N1000计数toy，
得到同时变动有限经验响应/伪数据均值及计数的随机拆分覆盖。与无计数的point结果并列。
group_component只做point诊断，不嵌套toy。这个有限池的互补拆分ensemble并非独立MC总体抽样，
不称已经包含真实MC模型/探测器误差，也不用于事后校准LR阈值。

原分配toy误差按seed/方向分层，case/law比较用共同uniform配对，六bin macro保留相关性。
随机拆分toy误差按permutation整块聚类，seed/方向/两case共享分配，不能按独立toy数虚增统计量。
随机化统计量先对seed/方向/bin平方平均，再对每置换开方；对24个主p统一校正。
没有新group bootstrap；阶段25组区间仍作既有证据，不把事件级随机化区间冒充来源组置信区间。

## 执行、数值和验收

先小样本（每run/原折/truth箱最多25例，所以每原折/truth箱最多150例）、2次随机化/2toys smoke；
若stratum在smoke中只在一侧为空，不删事件，日志标unsupported；正式样本以上审计不变。
匹配响应按run预聚合0–16阶矩，用解析归一化导数，中心网格与直接事件重权及差分核验。
独立toy计数CDF重放、全局扫描及真值条件LR检查，保留所有失败与数值边界。
正式7个model×seed作业单核CPU Condor、单线程BLAS/OpenMP、3000 MB、microcentury；
依小样本计时决定是否修订资源，但不据物理结果修改统计协议。可选较空闲schedd。
只保存紧凑矩、随机化point fits、toy counts/fit/LR与汇总；无逐事件副本/新checkpoint。
合并表/JSON并核对源码包后清理，中文报告记录资源和有效物理结论，然后Conventional Commit。

验收：明确匹配的中心变化与随机化统计证据，分开控制law和跨来源的coverage，
判断原分配的偏移在两种有限拆分零假设中是否异常，并说明可交换性/小来源数限制。
不能以更小deviance、p>0.05或未知原因宣称闭合、等效性或物理系统学已解决。

参考已联网核对：Phipson & Smyth (2010), PMID21044043，随机置换p不得为0；
Argüelles, Schneider & Yuan, arXiv:1901.04645，有限模拟统计须进入推断而非只看固定模板。
后者的加权模板似然是后续候选，本阶段不冒充实现了它；先用随机拆分量化问题。

预算修订：见[置换分辨率修订](permutation_resolution_amendment.md)，在正式物理结果前将point置换数由200增至1000，coverage分配仍为前200；其余协议不变。
