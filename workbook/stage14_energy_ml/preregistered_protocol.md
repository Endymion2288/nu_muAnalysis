# 阶段14预注册（2026-10-30，读取本阶段新模型结果之前）

研究问题：在同一 ordinary MC 选择下，station/事件计数和闪烁体电荷能否在
控制 μ 运动学、来源/时期及增加树容量后仍预测 ν 能量？Calo/全局矩的独立增益
是否被原先 600 棵树的容量限制掩盖？本阶段不更改选择，不开 calibration/test/challenge。

固定阶段12 train/validation：54,196 / 13,375 events，来源组91/22。
详细试验在 `ml/configs/robustness.yaml`：3 seeds × 3 capacities × 7 feature sets；
共享 squared logE loss、learning_rate=0.04、subsample=0.8、min_child_weight=20、lambda=10。
600、2400 棵 depth3 与1600棵depth5，早停100轮；同一容量所有输入版本同预算。
以 validation 早停，因此全部结果都是开发诊断，组bootstrap只给条件于模型的区间。

容量实验之外，第一个seed固定 depth3/2400 再做：
1. F1/F3/F5 使用 train 各 truth-energy bin 等总权重，权重仅由 train 计算、归一到均值1。
   validation早停使用train确定的同一权重映射；同时以不变unit validation指标比较。
   这是训练谱敏感性，不冒充物理flux权重。
2. F1/F3 在随机但固定的25%/50% train来源组训练；validation完全相同。
3. 在run、电荷、log p、theta、rVetoNu格内整组置乱新增变量，同一行所有组内变量共用
   donor，以保留组内相关性；coarse/fine两档、10 repeats。记录singleton、可置乱比例、
   实际p/theta/r donor差。F2打乱计数、F3打乱电荷、F5分别打乱电荷/Calo/shape。
   不用truth E或truth坐标分格。分格近似会破坏其他相关性，不称精确因果/独立性检验。
4. F2/F3在coarse格内将新增组分别在train与validation置乱后重新训练，判断原本增益
   是否可以由格内源/μ分布和树容量产生。train、validation不互换donor，不按label置乱。

主统计：预注册[100,200,400,800,1600,3200,6400] GeV六bin的macro log-RMSE，
同时报告bin bias、R68、尾部、六run与两电荷分层；500次同来源组配对bootstrap，
另独立报告3seeds的范围，不将模型预测ensemble冒充单模型结果。
未达到明确增益时也报告数值及界限；未知机理不作为最终结论。

大批量训练一律HTCondor，先做受限小样本smoke。每job 1 CPU，禁止嵌套BLAS线程。
保留小型预测和聚合表，避免保存每个试验的重复checkpoint。性能以实际wall/CPU/RSS计。
