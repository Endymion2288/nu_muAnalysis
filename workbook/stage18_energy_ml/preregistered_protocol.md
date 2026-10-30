# 阶段18预注册：station空间信息（2026-10-30）

主问题：在F5及逐station/逐layer SpacePoint计数已知时，横向分布与station位置
的关联是否仍改善能量响应？先完成固定BDT消融，不在本阶段选择Deep Sets架构。
原20项选择、最高pz leading、单位MC权重、54,196/13,375 train/validation和
91/22来源组保持不变，异常事件保留；不评价calibration/test/challenge。

几何采用FASERNU-04的SCTTopLevel-02：IFT中心1237.4−3097.55=−1860.15 mm，
后3站中心47.4/1237.4/2427.4 mm；3层相对中心−31.5/0/+31.5 mm。
每点匹配最近station/layer，实际偏离层中心须≤10 mm（覆盖module错层）；
若失败先调查几何/程序，不删除点。全量报告xyz对齐、层占有、坐标范围。

输入组与固定对照：

- F5：原46变量，重跑以核对stage16 BDT seed结果。
- counts：F5+12个逐层点数，包含station计数信息；不与cluster数混称。
- moments：counts+每站mean x/y、RMS x/y、cov(x,y)，共20变量。
- centroids：counts+8个mean x/y；widths：counts+12个RMS/cov。
- tangent：moments+每站质心相对leading上游切线在station中心的8个偏移。
  切线仅是现有μ输入的确定性特征交互，不是穿磁场输运或真实track距离。
- reassigned：counts+在事件内将xy点对随机分配到原z槽位后计算的20个矩。
  保持所有逐层计数、全局xy点对集合和原F5不变，破坏xy与station/layer关联；
  train和validation都变换并重训，不仅在推理时扰动。三seed使用独立随机实现。
  此为关联对照，不是物理可实现的探测器系统误差；可能改变局部接受度关系。

七模型×三seed共21 fits。固定stage16 F5 BDT配置depth7/1200轮、早停100轮，
其余参数相同；全组使用stage16同一train-only asinh/填充/标准化/缺失mask。
目标仍标准化logE，无本阶段选参或展平能谱。主要配对比较moments−counts、
moments−reassigned；其他组用于分解信息。500次来源组配对bootstrap，报告
六能量bin等权macro log-RMSE、整体误差、偏差、尾部以及y/primary/位置分层。
区间条件于已用于早停和之前选参的validation，不当作独立test保证。

先用单文件提取核对全局矩与冻结缓存，1200/400事件、20轮验证训练路径，
再Condor批量提取和训练。仅保存紧凑标量与seed0模型/三seed预测，记录
wall/CPU/RSS/GPU及I/O字节；确认合并和读回后删除重复shard及传输包。
