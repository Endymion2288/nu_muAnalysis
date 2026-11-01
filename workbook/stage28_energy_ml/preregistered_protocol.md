# 阶段28预注册：响应MC bootstrap校准 profile-LR

日期：2026-11-01。正式计算前冻结。承接阶段27，目标是检验有限响应MC是否可以通过
明确的辅助 bootstrap 校准 profile-LR 的临界值恢复覆盖。没有训练新模型，不打开保留集。

## 固定总体和样本

固定阶段27的13,375例validation、六truth箱100–6400 GeV、十reco类、全部异常和流出，
以及μ/0.8、BDT UU、TabM UU已有预测。以pooled经验联合分布定义总体，truth fractions
固定为731/2455/4247/3933/1741/268除以13375。响应MC每truth箱独立有放回抽样365/1227/
2123/1966/870/134例；本阶段只传播响应MC，伪数据均值固定为pooled总体，N=1000计数由总体
响应生成。alpha注入为0，未知alpha拟合域仍为[-3,+3]。

每个model-seed 200个独立trial。观测计数的uniform固定为
`SeedSequence([20261101,28,1,seed,trial])`，与阶段27序列不同。trial 0–99仅用于校准，
trial 100–199只用于验收覆盖，不能用测试trial修改阈值。

## 校准定义

每个trial先用有限响应MC拟合观测计数，得到profile MLE。随后在该有限响应MC内按truth箱
有放回重抽16个bootstrap响应样本，以重抽前有限响应及观测MLE的(f,alpha)生成每个N=1000伪计数，使用重抽后的响应对每个
伪计数重新拟合并计算七个实际profile LR。校准临界值为前100个trial、16×6个fraction
LR和16×1个alpha LR的共同0.682689492137分位数；fraction和alpha分别校准。
这是一种明确的参数自助法诊断，保留weighted-column相关性和simplex约束，不把每个加权格
子当独立Poisson。它不是已经实现的Baker–Cousins/Barlow–Beeston辅助似然。

后100个测试trial分别计算固定阈值1与冻结校准阈值下的逐bin、macro和alpha覆盖；主检验为
三模型的macro覆盖差（校准−固定），先平均各seed并保留trial相关性，三个配对比较统一Holm；
μ/0.8和各seed的逐身份结果完整保留。覆盖不使用校准trial。

前16个测试trial对最高fraction和alpha计算固定/校准两种LR=阈值区间宽度，记录边界和重入。
不以区间宽度挑选阈值；若bootstrap拟合失败、支持失败或边界出现，全部记录且不补伪计数。

## 数值、验收和限制

复用阶段25–27的16阶矩、解析导数、三全局alpha起点、SLSQP、simplex和ftol1e-13。
先μ/TabM smoke，再7个单核CPU Condor作业。验收为：测试trial中校准阈值的覆盖是否改善，
区间宽度、alpha覆盖、边界频率和CPU成本如何变化；报告前100校准与后100测试严格分开。
本阶段只检验固定经验总体下的响应MC层，不处理第二层均值MC、来源组相关性、生成器/探测器
系统学、flux/接受度、背景或真实data；校准阈值不能直接移植到最终测量。

参考候选为Baker–Cousins/Barlow–Beeston有限MC似然及Argüelles等随机模型似然；本阶段
先用可复现bootstrap量化效果，不宣称实现这些方法。
