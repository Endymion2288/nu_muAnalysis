# 阶段15预注册：primary μ、非弹性度与重建响应（2026-10-30）

保持stage12选择、train/validation分区及全部异常事件；不读calibration/test/challenge。
读取同一官方PHYS原生truth/t_*分支，仅新增诊断缓存，不修改部署特征白名单。
先审计保存前十truth中符号正确且产点与ν衰变点吻合的μ候选，要求唯一才定义primary。
不默认索引4或barcode5；无候选/多候选单独计数保留。leading仍取最高pz，逐文件检查
全部使用的t_*与Track_pz0对齐，parent PDG+barcode核对入射ν。

按配置三个seed、depth5/1600、早停100轮，训练独立oracle：O0=primary真实p/斜率、
PDG、truth顶点；O1加计数；O2再加电荷。真值只在明确标识的oracle诊断中使用。
同一验证事件比较O2/O1与已冻结deploy F3/F2，500次同来源组配对bootstrap。
若oracle在固定真实μ运动学/顶点后电荷仍改善Eν估计，则μ动量重建误差不足以单独
解释电荷增益；这仍不将电荷当量热强子能量，不把oracle列入可部署模型排名。

诊断：y_lepton=1-Eμ(vertex)/Eν、ΔE=Eν-Eμ(vertex)；非弹性度/位置/leading匹配分层。
将μ p(vertex)、truth station1 p、reco p的log比拆开，station1与fit参数参考面不同，
后一项是包括面差异的重建响应，不冒充纯曲率误差。未穿过参考站的粒子用有效性mask，
不将零或缺失truth动量当物理值。没有协方差不声称完整误差因果分解。

物理验收：定量回答电荷是否含不依赖μ动量重建错误的ν→μ随机能量分配信息；报告
匹配率、μ材料传播能损/重建响应尾部、box/lead及y依赖。无显著增益也如实给出区间。
小样本完整输入文件先验收，批量读取和训练经HTCondor；只保存紧凑诊断缓存及聚合图表。

## 源码审计修订（训练前，2026-10-30）

官方d32b0ff3的FiducialParticleTool::getMomentum以
`hit.particleLink()->momentum().rho()`取产生动量模长，以hit端点推算方向，
getTruthMomenta再对同station向量平均；缺失为NaN。因此truth_st1不是输运后的
真实动量，不能实现上述材料能损/纯重建误差拆分。本阶段将材料能损标为未测量；
只审计station参考可用性/产生动量一致性，并报告reco/vertex响应。
oracle及非弹性度实验不受此语义问题影响。详细出处见source_semantics.md。
