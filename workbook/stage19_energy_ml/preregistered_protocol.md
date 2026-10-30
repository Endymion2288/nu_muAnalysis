# 阶段19预注册：完整SpacePoint集合（2026-10-30）

问题：全点集合的非线性分布是否提供超出F5、逐层点数及低阶station矩的能量信息？
进一步区分全局xy高阶形状与xy和station/layer几何关联，不能仅胜过随机关联对照。

保持stage12的20项选择、最高pz leading、全部异常事件、单位MC权重、
54,196/13,375 train/validation及91/22来源组；不评价calibration/test/challenge。
完整保留选中事件16,287,628个点，无点数上限、抽样、能量权重或坐标截断。
采用stage18已验证几何，按事件/station/layer保存；重排只用于连续内存布局。

四变体共享78个真实标量输入、训练变换及同一ResNet事件输出网络：
- summary：共享两层MLP编码每站10个固定汇总量（5矩、总点数、3层比例、空标识）；
  与点编码器同样10→64→32，每站输出32维。
- global：点编码器只看xy，其他8个输入置零，事件全局均值池化后复制为4个32维槽。
- full：点编码器看xy、station/layer one-hot及层内z偏移，每站均值池化，共128维。
- reassigned：在事件内重分配配对xy到原z槽位，保持所有点与计数、全局xy集合；
  与full相同编码/池化，train和validation均变换重训，三seed采用独立随机实现。
  共同真实标量仍保持不变；这不是物理系统误差，可能破坏局部几何接受度。

φ为10→64→32 ReLU MLP；ρ为输入标量变换156维+128维集合编码后的表格ResNet。
均值池化与显式计数共同保留sum所需信息，空station输出0。所有对象无能量权重，
采用PFN式对象编码思路，不把SpacePoint当真实粒子或将其位置误作能量沉积。
global复制槽约束不同，精确参数数目与实际成本单列，不冒充每种表示有相同有效自由度。

每变体2个seed0超参候选（width128/256、blocks3、lr.001/.0005，见sets.yaml），
按validation整体log-MSE选优，然后固定配置重训seed1/2，共16 fits。
最多200epochs、15epoch早停、每fit墙钟600s；同上限不等于同FLOPs。
目标train标准化logE，无谱展平/新损失/真值约束，不平均独立seed预测。
主要比较full−summary及full−reassigned；global−summary、full−global分解信息来源。
保留stage18 BDT与stage16 TabM精度参照，后两者不是本阶段同预算架构排名。

500次同来源组配对bootstrap，六能量bin等权macro log-RMSE为主，同时报告整体误差、
偏差/R68/两种尾率、能量/y/primary确认/材料区域/run分层。区间条件于用于早停/选参
的validation，非独立test。不得将随机输入变差本身解释为新增物理信息。

先单文件及1200/400事件×2epochs验证，再HTCondor提取、合并和GPU训练。
检查点数、全局/站内矩、随机对照守恒、事件/标签/来源一致、对象顺序不变性、
checkpoint读回及完整点处理成本。记录wall/CPU/RSS/GPU、训练触顶/学习曲线。
仅保留紧凑float32点缓存、seed0 checkpoint及三seed预测；验证后删重复shard和传输包。

依据：Deep Sets https://arxiv.org/abs/1703.06114 与PFN/EFN
https://arxiv.org/abs/1810.05165；本阶段不加图边或attention，先检验集合分布收益。
