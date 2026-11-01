# stage30 运行前冻结协议

2026-11-01；新训练之前写入。全部是开发研究，保持原选择、unit MC和全部事件。
输入为stage12 train/validation F5、stage15 primary真值；不访问正式保留分区。

## A：主实验

配置 `ml/configs/information_gap.yaml`，三个seed为20261029/30/31。train内按
charm/k/pi分别固定随机置换来源组，20%向上取整用于独立预测映射，10%向上取整
用于早停，其余拟合。ν/反ν配对组不拆分；所有模型使用相同fit/stop/map和事件。
四格保留46个F5重建变量，只额外加入log真实产生
动量、真实xyz，禁止真实方向/PDG/matching作为输入。BDT统一depth5、最多1600轮、
patience80，其余沿用baseline，4线程CPU，每fit最多120秒。主风险L为六箱MSE(logE)
均值开根号，三seed先平均逐事件平方损失；辅助报告integrated log-RMSE。
Gp=L0-Lp、Gv=L0-Lv、Gpv=L0-Lpv、I=Lp+Lv-Lpv-L0；I仅为该损失的协同量。

500次validation来源组配对bootstrap，模型/seed共享重抽样；报告总体、六能量箱、
leptonic y六层、primary-confirmed/未确认、真实z四区间以及横向r<50/≥50mm。
每层给逐seed误差、mean/median bias、R68、|r|>0.5/1尾率，并给线性指标与加权CDF
median/R68的配对区间。区间条件于冻结模型，不包含重训练不确定度，未多重校正。
若Av主风险改善≥5%且配对95%区间增益下限>0，才启动三seed z-only、xy-only控制，
同容量、同划分；否则不运行。oracle不是tracker拟合误差分解，不用truth_st1测能损。

## B：最多三个新多类BDT，不扫描

同F5、fit/stop、depth5/1600轮/patience80，每classifier最多240秒，原六箱unit类别
先验π为fit实际频率。使用map子集的独立预测，以π_fit/π_map类别权重拟合温度及
五个class intercept；校准目标先验始终π_fit。对比完整q、同一校准q的平均log箱中心
再用8结点三次样条+多类logistic(C=1)映射的qmean、A0scalar同样映射、以及A0scalar
沿用原9边界的十reco类。温度校准在map内再做两折来源组cross-calibration，qmean
映射的输入来自未见该事件标签的温度模型；validation用全map温度模型。
十类空映射箱以π返回无信息，并计数，不添加伪计数。所有映射都只拟合map子集，不用validation标签。每seed
还保存未经映射的同模型平均logE用于回归诊断。总预算12个oracle+3个classifier+
最多6个控制BDT；9个廉价样条/十箱映射，不扩大架构/深度/分箱搜索。
stage23既有scalar22+十类结果作为历史基准，明确训练数据、早停、响应估计不同，
不把与它的全部差异称为压缩损失。本轮A0十类用于更严格的同训练对照。

推断固定α=0，N=1000只是条件基准，f0取共同validation unit六箱频率。
L(f)∝∏Σ f_b q_b/π_b。单独测概率log score、Brier、reliability/ECE、最高箱。
报告该似然的Asimov拟合偏差、曲率误差和100个共同经验伪数据toys/seed（真实有限
N偏差/方差/边界）。不将误校准的曲率直接称作真实Fisher信息：另用冻结的5维
likelihood score，在实测truth条件响应下构建均值导数G和协方差V，报告已知响应的
N GᵀV⁻¹G信息下界及最弱谱方向；使用正交simplex基、无伪逆/正则化。
它是给定摘要下线性估计方程的信息，不宣称等于全部观测的最大信息。

200次共同来源组bootstrap给该信息/闭合偏差配对区间，另在原stage23来源A/B两折
分别评价固定概率似然，衡量有限来源MC敏感性；不重新拟合validation映射。
若完整q相对qmean的score谱误差改善≥5%且95%配对区间下限>0，仅增加固定within±1
箱内形状压力（逐truth箱归一保持f不变）；否则不扩展。任何calibration失准、弱方向
不稳定、尾箱统计不足均照实报告。不能直接sum(q)当真谱，不能把q与scalar独立相乘。

## 验收及资源

先用各split小样本和20轮smoke验证共同支持、标签/特征隔离、概率归一、映射独立性、
优化梯度及已知合成混合闭合，再HTCondor三seed计算。资源4CPU/3000MB，每seed
主实验硬上限4×120+240秒（不含廉价映射/报告）；控制最多240秒/seed。
重用25MB缓存；本地小数组报告，较重toys走Condor；只保存紧凑预测/模型及汇总表。
达到上述有意义增益阈值时才扩大相应物理分支；区间宽则写证据不足，不追加调参。
阶段结束写中文实测报告、更新修订路线、Conventional Commit。下一阶段只选一条
由oracle/表示证据支持的物理主线，并安排对应data控制；未测量项目明确标注。
