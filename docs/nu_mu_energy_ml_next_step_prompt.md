# 下一轮执行 Prompt：冻结有限候选，低p ν信息缺口优先

先读AGENTS.md、修订路线图第15节、`workbook/2026-11-01_stage33_low-momentum-information.md`及其协议。
stage30 A/B、stage31九个BDT、stage32与stage33原生控制均已完成，不重跑。
用户已明确：TeV tracking精度有限，不以修好很高动量为主任务；较低动量重点保留。

**唯一优先：先冻结有限F5/F6允许的校准与一次性独立检验协议，再执行保留分区推理/评价。**
停止扩展tracking审计，不增加变量族/网络/扫参，不全量重模拟。完整F5 46维及F6新增19维保留。

已有实测决策依据：

- 原选择reco pz>100GeV，不能据此检验完整25–100GeV。该primary区train+val437例仅19例确认，
  本轮实际重点100–250GeV；更低控制要另建放宽门槛选择，未测量就明确说明。
- 2315例confirmed低p validation原始μ对产生动量R68=3.3984%、log-RMSE=0.065516；
  ν F5/F6=0.296955/0.297415，相对改善−0.1550% [−0.9064%,+0.5914%]。
  μ辅助F6回归反而变差，不能当低p无偏校正。≥1TeV参考F6 ν改善7.0181%，保留证据但不追求低p同等精度。
- 低p且y≥0.8的57例μ log-RMSE=0.041918，ν为0.816307/0.816974，缺口在能量分配/非μ信息。
  既有匹配历史模型中，计数及闪烁体顺序增益约21.8%/16.6%；普通Calo边际约0.53%。
  后者不是CaloNu结果，活动相关性不是data校准好的可见强子能量。
  相对固定pμ/0.8的38%收益含非线性标定/先验，不能全部归因新读出。
- stage33新增12组、576 native/96 reco全部成功。44例可给真实参考面双侧界限，其中低p18例/9组，
  同面相对误差R68界2.9631%–3.7416%，均值界−0.2779%–+0.6909%。仍有1例>20%尾且r约2.29–2.46σ。
  没有精确pull闭合，不依据这18例标定σκ，不删尾。无双侧界限及未确认支持全部保留。
- 紧凑archive `ntuples/energy_ml_stage33/native_results.json.gz`为324,778bytes，含cfg/requests/truth/cov，
  9张表复算及96例区间读回一致；不再跑原生作业。stage32缓存也保留，正式calibration/test/challenge未读。

执行顺序与边界：

1. **读取任何保留分区事件/标签前写冻结协议**。只用现有模型和已知manifest元信息规划；
   明确两个候选、物理基线、三seed如何合并、允许的校准形式/参数预算、评价、统计区间和挑战顺序。
   推荐首先限定为不校准对照及简单全局log能量offset，不临时扩展条件校准或覆盖调参。
   协议解释原unit混合先验、data/系统变体尚缺的限制，不把人工α或SIBYLL当全部物理系统误差。
2. 保持原六nominal run/普通几何/official merge withoutIFT/原20cuts/最高pz leading/truth fiducial/unit权重，
   不再询问flux。旧stage31训练配置与metadata保持冻结；为新分区另写提取配置，复用已验证19维定义。
   F5缓存已经存在；F6新增特征从对应原PHYS提取，不重新重建RDO，不加入truth p/方向/PDG/matching。
   特征名/次序/单位/缺失策略与固定模型严格一致，事件键和来源组核对；先小样本后Condor。
3. calibration只做协议允许的校准，不训练新架构、选seed或用test调参数。
   一次启用locked test，保留全部selected事件，包括未确认和离群，按冻结的准则报告。
   headline使用完整支持；truth p/y/matching只作MC诊断，不能据truth p选择部署模型。
   逐Eν、reco p与低p真值层比较风险、bias、R68、尾与资源，来源组配对区间；不以全局改善掩盖低p损失。
4. 按已冻结顺序检查允许的挑战与响应敏感性，缺匹配的真实detector/interaction变体就写未测量。
   SIBYLL/EPOS是flux/母粒子模型挑战，不是相互作用生成器挑战；unit-MC不提供最终flux平均收益。
   若独立检验不支持收益，报告并限定候选适用范围，不能按test结果回头调参再称独立。
5. 做可得的物理解释与程序核查，形成有实测支持的新结论。低p μ已准确时优先解释剩余ν能量分配，
   不回到无限TeV曲率变量/拓扑扩容。data仍需参考面、时期/几何/对齐/conditions及reco选择匹配，旧data无isForward。
   MIP/双增益/status/强子响应尚未闭合，不声称可部署或最终能谱收益。CaloNu只能以同事件有/无读出来判增益。

原生方法只在必要解释时复用：用官方d32b0ff3（`source setup_env.sh --official`），
HepMC数值MeV/mm与枚举不一致必须逐值核验；truth_st1/t_st*模长禁止测材料能损。
κ=q/p，稀疏post-incident链上下界不是精确pull，不以中点造真值；新transport不可配旧RDO。
无需再为本阶段问题扩大原生审计预算。

每次推进要有有效物理结论，不能只交作业。写中文workbook，记录真实数值/单位/组区间、
输入与配置、命令、成本/失败、产物、统计/物理局限及未测量项目；更新修订路线和下一Prompt。
大批量用Condor，可选空闲schedd；小样本验证、去重JSON、清理ROOT/xAOD中间件，Conventional Commit，
提交blob读回，不push。最终回答给新结论、限制、报告/commit与唯一下一任务。
