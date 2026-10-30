# 阶段16预注册：同输入强表格模型（2026-10-30）

物理问题：在stage15确认电荷含超出真实μ运动学的能量分配信息之后，更强表格
表示能否改善高y的能量响应、偏差及尾部？不得只依整体精度排名。

保持20项选择、最高pz leading及stage12来源组划分，完整train54196、validation13375。
只用F3/F5原始允许输入，不输入truth μ、y、真实顶点或匹配标识。
所有架构共享train-only的asinh缩放、缺失填充/标识及标准化，预测标准化logE。
真值y/匹配仅用于训练后分层，不作为训练或调参条件；不评价calibration/test/challenge。

BDT/MLP/表格ResNet/作者实现TabM，每个输入版本各3个seed0调参trial，
按同一validation log-MSE选最优，再固定该配置重训seed1/2。共8作业、40次拟合；
每fit最多180s训练墙钟，NN最多250epochs、25epoch早停；BDT轮数/深度见tabular.yaml。
共同上限不等于实际相同FLOPs；记录GPU型号、CPU/GPU内存、各fit实际时间、
预算触顶与收敛情况，按实测成本讨论。只保留seed0最终checkpoint及三seed预测，
不平均独立seed预测。TabM内部32个共享参数成员是该架构本身，不隐藏其计算成本。
NN不做本阶段额外能谱展平、目标/损失变化或空间集合输入。

500次同来源组配对bootstrap，主指标仍为六能量bin的macro log-RMSE；
同时报告整体误差、每能量bin偏差/R68/尾率、y、primary匹配及box/lead分层。
特别检查y≥0.6/0.8且primary已确认子集，区分表示能力与leading规则的限制。
所有比较条件于已接触validation的拟合与调参，不冒充独立test泛化区间。

TabM依据作者仓库https://github.com/yandex-research/tabm（main实查
28e47ae301c92ec37787dde1ce923a0793f405b4，2025-11-10）及PyPI tabm0.0.3；
论文https://arxiv.org/abs/2410.24210。采用推荐的数值特征embedding，
并正确对各内部成员分别计算训练损失，预测取log输出均值。
ResNet使用数值表格PreNorm残差块（LayerNorm/两层线性/ReLU/dropout），
不是图像ResNet。依据https://arxiv.org/abs/2106.11959，当前实现不声称逐行复刻作者默认超参。

软件：LCG_109_cuda x86_64-el9-gcc13-opt，实查PyTorch2.10.0、CUDA12.5、XGBoost2.1.3
支持CUDA；本地T4仅做小样本验收，大训练通过HTCondor request_gpus=1。
提交语法参考https://batchdocs.web.cern.ch/gpu/index.html，不限定具体GPU型号以减少排队。

物理权重审计继续追溯原EVNT/正式生产设置；在不能核实时明确只给单位权重结论。
相邻目录“100_iab”的名字不是当前输入的归一化证据，不据此赋权或读取新事件样本。
