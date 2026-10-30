# 阶段27预注册：独立抽样下的单侧响应MC与第二层经验均值MC

2026-10-30，在阶段27正式计算及物理结果前冻结。承接阶段26，先完成误差层次分离，
不把阶段26的双侧有限MC缺口直接外推到单侧响应模板。不训练、不打开保留集。

## 固定总体、样本与独立抽样

固定13,375例validation、六truth箱100–6400 GeV、十reco类及全部流出/异常事件。
μ/0.8、stage22 BDT UU与stage21 TabM UU均保留原三seed（μ仅seed0）。
以全部validation的经验联合分布(箱内真能量、预测reco)定义toy总体；
六箱truth fractions取原pooled nominal计数/13375，固定不随抽样或alpha改变。
alpha=-1/0/+1时用exp(alpha log(E/Ecenter))在每truth箱内归一，拟合共同未知alpha域[-3,+3]。
这只是固定经验总体的条件控制，不能称独立生成器或真实data无条件覆盖。

响应MC和伪数据均值MC各自逐truth箱有放回抽样，规模均floor(n_pool_bin/2)，
预计365/1227/2123/1966/870/134例，合计6685例；两侧独立，不是互补拆分。
独立抽样包括run混合的有限样本波动，不固定run比例，也不模拟来源组相关性。
不重抽六箱truth积分。每个trial在所有模型/seed/注入间共享事件抽样索引；
源与均值两侧SeedSequence([seed,27,0,side,trial])彼此独立。

每model-seed/alpha做400个trial，四个case配对：
oracle=总体响应+总体均值；source_mc=抽样响应+总体均值；
mean_mc=总体响应+独立抽样均值；both_mc=抽样响应+独立抽样均值。
每case同时保留无计数的均值(Asimov)和N1000 multinomial观测。
同seed/alpha/trial使用同1000个uniform生成四case计数，跨模型同seed也共享；
seed不同的计数RNG不同，但MC索引仍共享，推断误差以trial整块聚类。
总400个独立trial块，不能把模型/seed/case/注入/计数开关当独立样本。

## 拟合、覆盖、宽度与局部传播

复用阶段25/26连续16阶矩、三全局起点、解析导数、simplex、ftol1e-13/maxiter500。
每case/count/trial保留已知alpha与profile-alpha点解；实际profile LR真值检验六fractions和alpha。
只有计数开启的四case称覆盖；Asimov的LR≤1只称真值接受率/MC偏移诊断。
空reco支持/数值失败全部记录，不补伪计数或丢事件，覆盖同时报请求数与有效数。
预定主检验为名义未知alpha六箱macro覆盖差：source_mc−oracle、both_mc−source_mc，
三模型合计六项，统一Holm校正；paired trial块95% MC区间完整报告。
alpha±1、逐bin及mean_mc对照全部保留，不以结果挑选模型或谱形。

名义alpha0前32个trial、四case、有计数、最高fraction与alpha计算真实LR=1端点，
报告配对区间宽度、域限、重入与数值失败；不在每个trial全参数反演昂贵端点。
端点沿用阶段25扫描及数值域，不因观察边界而修改域或阈值。

另在总体truth点计算局部delta传播：对每bin的归一加权响应，使用独立事件均值的
精确一阶协方差，再经共同alpha/五维simplex切空间的得分Jacobian传播。
分别给计数、源MC、均值MC、组合协方差和相对sigma，与400个trial实测SD比较。
源与均值同规模应给相同的一阶贡献，这是层次/符号核验，不保证非线性拟合分布相同。
这是oracle总体真值诊断，不是可部署区间，不宣称实现MC辅助似然或覆盖校准。
MC辅助似然/明确bootstrap区间随后在此明确总体上检验，不能用局部sigma替代覆盖实测。

## 执行、验证与验收

先μ和TabM小trial smoke及直接事件积分/梯度/协方差独立检查，再提交21个单核CPU作业
（model×seed×alpha），单线程BLAS、3000 MB、microcentury；可选空闲bigbird schedd。
保存紧凑拟合、LR、计数、抽样种子/汇总及少量区间，重放索引替代保存中间事件副本。
独立重放全部抽样约束/计数，检查固定位置全局拟合及条件LR、端点与局部协方差。
按trial聚类汇总，保留所有失败及MC边界，不打开calibration/test/SIBYLL challenge。
验收为有数据支持地回答：单侧源MC造成多大覆盖/方差变化，第二侧均值MC增加多少，
局部方差能否解释量级，固定模板LR宽度是否跟随新增MC波动；记录CPU/wall/RSS和存储。
中文workbook报告、路线图更新与Conventional Commit完成本阶段。
