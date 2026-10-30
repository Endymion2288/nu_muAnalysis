# 阶段21预注册：训练权重与早停目标的分离（2026-10-30）

阶段14的seed0/depth3 BDT已经测得展平谱改善端点偏差，但训练与validation早停权重
同时改变。阶段19强表格/全点模型仍有高能欠响应。本阶段不重复把前者当新发现，
而在阶段16固定F5 BDT(depth7)/TabM(width256)配置上，分离两个因素并重复3seeds。

UU=unit训练/unit早停，FU=flat训练/unit早停，UF=unit训练/flat早停，
FF=flat训练/flat早停；2架构×4设置×3seeds=24 fits，无新增超参搜索。
主比较FU−UU隔离固定unit早停下的训练权重效应；FF−FU、UF−UU检查早停目标，
FF−UU与阶段14方向对照。所有设置最终评价都用同一unit validation和六bin等权macro。
另报告相同UU/FU/FF设定下TabM−BDT增量，以及每架构FF−FU−UF+UU的macro交互对比，
检验既有模型排序与两个因素的组合效应；不据这些辅助结果重新选权重或架构。

train/validation为54,196/13,375事件、91/22来源组，46个F5原输入变换为92维。
保持原20项cuts、最高pz leading、全部异常事件及现有划分；不读calibration/test/challenge。
真值能量仅作训练标签/训练权重或验证目标，y/primary/vertex仅诊断，均不作模型输入。

权重由完整train六个倍增能量bin计数拟合w_b=N/(6n_b)，无裁剪、抽样和额外事件。
全train均值1，报告sumw/sumw²/Neff；可选flat monitor使用同一train映射，
不是按validation重新拟合权重，也不等于严格macro目标。
标量预处理与logE目标中心/尺度均仍仅用原unweighted train拟合，避免改变归一化。
TabM每成员平方误差先乘事件权重再取原batch均值，不按每batch权重和再归一化；
unit分支保持原损失表达式。验证以加权误差和/权重和评价monitor。
BDT将权重传给DMatrix，原超参和正则化不变；这会改变有效梯度/节点权重，
不能把结果解释为纯物理flux先验或对探测器响应的因果份额分解。

沿用阶段16：180 s/fit，NN250epochs/patience25/batch1024，BDT1200rounds/patience100，
所有fit单线程并在GPU Condor执行；正式作业统一H100 NVL，减少硬件与权重因子的混淆。
最初优先A100-PCIE-40GB以复现阶段16，排队期间实查A100全部占用而有可用H100；
2026-10-30 13:17 CET前后、全部作业尚未开始时，先挂起再统一改硬件后释放。
这项资源修订在任何正式结果出现前完成，不改模型/输入/种子/预算/权重或统计判据。
UU单独调用原fit函数，核对阶段16三seed预测；跨硬件不预设bitwise相同，
所有权重效应相对本轮同硬件UU计算，逐位/数值差异实测记录。
其余设置每次独立重置相同seed/初始化/事件顺序，各自早停，记录轨迹和预算触顶。
先本地1200/400事件×2epochs/20trees跑通两架构四设置，再提交正式8个GPU作业。

主统计为500次同来源组配对bootstrap；三seed先平均事件损失，不平均预测。
报告macro/整体log-RMSE、bias/R68、正负0.5尾部和1.0尾部，以及全部能量、y、
primary确认高y、材料和run分层。median bias的主高能差额外作来源组bootstrap，
使用各seed的加权经验CDF分位数再平均；NumPy插值描述值与CDF估计分别标明。
主结论须同时回答：高能欠响应是否减小、改善是否来自训练或选择目标、
是否以低/中能精度和总体尾部为代价，以及高y residual是否仍在。
区间条件于调参/早停validation，不是独立test、物理加权产额或能谱闭合。

不因看到结果改架构/权重幅度/删事件。只保存seed0模型、三seed预测、紧凑统计及学习曲线；
源码传输包完成后清理，记录CPU/wall/RSS/GPU实际硬件及资源。每阶段先写中文报告再commit。
