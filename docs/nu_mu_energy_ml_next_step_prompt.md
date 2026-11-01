# 下一轮执行 Prompt：100–1000 GeV非μ能量分配与同事件CaloNu控制

先读AGENTS.md、修订路线第16节、`workbook/2026-11-01_stage34_frozen-low-momentum-evaluation.md`及冻结协议。
stage30 A/B、stage31固定BDT、stage32/33原生审计及stage34独立性能检验均完成，不重跑。
用户重点扩大为100–1000 GeV，保留100–250、250–1000子层，≥TeV仅参考，不追求高p达到低p精度。

**唯一物理主线：转向非μ能量分配的新读出控制，先核验并冻结同事件CaloNu有/无实验。**
保留完整F5/F6固定BDT，不新增tracking变量/架构/扫参，不扩大原生审计或全量重模拟。

已完成的独立证据：

- stage34协议先于解封；固定三个log预测ensemble，calibration 9727例仅两个global log offset，
  乘数F5/F6=0.9967673425/0.9966439731。先冻结再test，test报告固定后challenge，零新fit。
- test 12488例/22组：校准后macro F5/F6=0.354272/0.337954，改善4.6062% [2.0160%,6.8809%]；
  reco p 100–1000的10014例改善2.7976% [2.3098%,3.3915%]。
  中心未达预注册5%架构扩展门槛，但区间未排除5%，保留有限候选，不事后改门槛。
- confirmed truth p 100–250的2162例ν改善0.1626% [−0.5033%,0.7537%]，250–1000的7482例
  改善2.3031% [1.6593%,2.9647%]。原始μ对产生动量R68分别3.4608%/8.8527%；
  ≥TeV参考35.2943%。reco低箱有true高p迁入，不能把reco低箱改善全说成真实低p改善。
- confirmed truth重点且y≥0.8的104例/21组：原始μ log-RMSE=0.066595，ν=0.811343/0.811514，
  无明确F6收益，mean bias约−44%/−45%。支持研究能量分配/非μ响应，不等于现有所有读出不可恢复。
- SIBYLL π reco重点改善1.7674% [1.1124%,2.5000%]；nominal π test与SIBYLL π共同100–1600
  四真能箱macro差区间跨0，未确立整体恶化，也未证明等效。不是完整相互作用/探测器系统检查。
- 全局offset不能消除低真能上偏、高真能/高y下偏；未确认及部分尾率未一致改善。
  不能宣布data部署/无偏校正/最终能谱收益。

当前状态与禁区：

1. **calibration/test/challenge均已解封并评价**，不得反复返调后再称新独立确认。
   `ntuples/energy_ml_stage34/{calibration,test,challenge}.npz`为5695131bytes最终紧凑cache，
   含19维、六固定模型log预测及隔离truth诊断；11shards与3payload已清，不重复PHYS提取。
   历史native archive也保留，不重跑。无flux归一化新资料就按已授权默认unit，不再询问flux。
2. 原nominal六run/ordinary geometry/official withoutIFT/20cuts/最高pz leading/truth fiducial不变；
   truth p、方向、PDG、matching/isForward不得入部署。不能按truth p切换模型。
   raw μ对产生点响应不是同面pull；truth_st1/t_st*模长禁止测材料能损。
3. 来源组互斥不保证完整生成谱系独立；旧flux-library入射ν复用局限保留。
   unit-MC不是物理flux平均性能。SIBYLL是flux/母粒子挑战，不能说是相互作用生成器变体。

下一阶段具体执行：

1. 先在仓库和源路径找**已有**CaloNu读出及同事件F5/F6/primary/y支持，审计事件键、几何、
   材料、conditions、能量单位、status/双增益与选择，记录真实来源与缺失。
   不以ordinary与CaloNu不同几何的性能差来估计读出增益，不自动启动全量生产。
2. 输入具备时，先小样本验证读出非恒定、特征定义、配对及选择；在看新保留标签前冻结
   同事件有/无CaloNu、有限BDT预算（建议最多2输入×3seed）、来源划分及简单允许校准。
   其余重建输入和事件完全相同，真值仅标签/诊断；新来源保留支持不能冒充旧test仍未使用。
3. 用Condor做有限比较，给出100–1000、两个子层、高y、全selected支持的误差、bias/R68/尾部和
   来源组配对区间。明确CaloNu是否增加能量分配信息，不以少数尾停止分支或扩大TeV tracking预算。
4. 若同事件输入不存在，明确未测量和所缺输入/conditions，不造读出增益、不拿重复训练当物理推进。
   在扩大生产之前先给出具体、可审阅的小样本方案与数据依据。实际阶段必须有物理数据支持的结论。
5. data仍需匹配时期、参考面、几何/对齐/conditions及选择；旧data无isForward。
   MIP/强子校准与真实data闭合未完成，不能将活动相关性称已标定强子能量。

环境优先LCG109_cuda现成CVMFS；大批量走Condor，可换空闲schedd。stage34的bigbird21可用。
先小样本、记录wall/CPU/RSS/吞吐及失败；只留紧凑cache，清ROOT/xAOD和分片/重复JSON。
每阶段写中文workbook含实际数值/单位、输入/命令/验证/产物/局限/下一验收标准，
更新路线和本Prompt，Conventional Commit、提交blob读回、不push。最终回答给新结论、限制、报告和commit。
