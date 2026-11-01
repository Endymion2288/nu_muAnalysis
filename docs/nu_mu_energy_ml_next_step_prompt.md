# 下一轮执行 Prompt：扩大同参考面响应的独立来源覆盖

继续本仓库νμ能量研究。先读AGENTS.md、修订路线第13–14节、
`workbook/2026-11-01_stage32_reference-momentum-bounds.md`及
`workbook/stage32_energy_ml/source_audit.md`。stage30 A/B、stage31九个BDT、stage32原生288/24审计已完成，不重跑。

**唯一主线：有预算扩大独立来源的同参考面响应与真实拟合协方差审计，随后冻结有限F5/F6校准和独立检验。**
不无限复用validation继续调模型，不加第二个信息族/概率架构/拓扑网络，不全量重模拟。
保留F5全部46维和F6新增19维。stage31 ν macro log-RMSE 0.378062→0.363245，
改善3.919% [1.957%,6.485%]；还未达到中心5%扩展门槛，未排除5%收益。

已有新结论与可复用产物：

- 现有RDO的TruthEvent含真实G4 post-incident μ再生链；288例0个精确参考面状态，但145例可给保守双侧p界限。
  143例开口链最后保存状态在上游，不能将它外推为同面p，也不能说μ没到tracker。
- 24次原RDO重建全部复现原front并取得5×5协方差及真实curvilinear associatedSurface；15例有界，
  κ区间宽/σκ中位0.038928，最大0.135021。7例高p的传播损失0.08613%–3.48890%，
  其中6例reco相对产生点动量低19.5997%–52.2282%，不能全由材料传播解释。
- 15例同面标准化残差区间全部在±3内；不是精确pull，不是总体零尾上限或协方差闭合。
  q_true乘残差的R68界1.367908–1.395190，来源端点区间外包络0.891970–1.747613。
  3例confirmed高p电荷误判的|κ_reco|/σκ均<2。未确认例的巨大primary残差不能当primary fit pull。
- 覆盖与能量/matching相关，本轮cov没有confirmed高y支持，不能外推stage31的99例高y结论。
  6来源组、稀少区抽样设计不能当全unit总体估计；不因0个尾事件就给[0,0]置信区间。
- 紧凑原生archive：`ntuples/energy_ml_stage32/native_results.json.gz`（166,109bytes），含cfg、requests、truth、cov，
  `ml/report_reference_audit.py --compact`支持读回重算；源JSON已去重删除。已有表/图不需再跑批处理。

执行顺序：

1. 冻结预算与抽样协议。至少新增12个独立source groups、≤96次单事件重建，保留两个生产时期但不当独立来源。
   只读原train/validation。按p/Eν/y/z/charge覆盖，不按残差挑选，不删除未确认/离群事件。
   说明有意分层设计及权重，先规定终点和关键支持不足时怎样报告，不以重复调参替代来源统计。
2. 复用stage32准备/native reader/cov导出/界限算法。官方环境必须用`source setup_env.sh --official`，
   build info应为d32b0ff3/Athena24.0.41/gcc13.1；邻目录旧build不匹配，不盲目重编。
   HepMC enum声明GEV但GENIE/G4数值约定MeV/mm，每事件与原PHYS primary p/xyz及mass核验。
   `LeadTrack_pz0`已是GeV，准备native比较时乘1000。不得把enum问题解释为模拟能量放大1000倍。
3. 小样本先验收front p/xyz/charge、SDO matching、协方差及surface，然后Condor。
   可用较空闲schedd；上次bigbird21顺利完成。每文件本地copy一次供多事件重建，限制线程/磁盘，
   只传紧凑结果，不保存xAOD/RDO中间件。不得只交作业后结束，必须收结果形成新物理结论。
4. 在不改支持下报告κ=q/p、κ真值上下界、偏差/R68/尾与σκ，按p/Eν/y/z/charge/matching分层、
   来源组同步重抽样；端点识别区间与统计区间区分。未确认与无界支持单列保留。
   被动材料、静态纯B场、同μ同号再生、连续、动量非增及唯一有限跨面段条件须验证。
   不用truth_st1/t_st*模长测材料损失，不对近零曲率倒数再截断，不用区间中点造精确pull。
5. 评估无界支持能否从真实保存状态得到有物理依据的单侧限制，不把缺失当0损失。
   如关键支持仍不能判别传播/响应，只导出少量精确G4参考面状态，**新transport truth必须配同一次新reco**，
   不能配旧RDO；不自动全量重模拟。若范围已足够窄，则不为“精确”额外付大计算成本。
6. 用更多来源判断条件偏差/展宽是否稳定，解释程序和物理机制，不能将oracle全部归于拟合。
   data控制须核对参考面、时期/几何/对齐/conditions与可执行reco选择；旧data无isForward，尚不能部署。
   在控制后，为F5/F6两个有限候选冻结允许校准、评价、nuisance及一次性locked test协议，再启用正式保留分区。
   不按test结果调参再称独立。

保持原六nominal run/普通几何/official merge withoutIFT/原20cuts/最高pz leading/truth fiducial/unit权重，
不再问flux。data MIP、双增益/status/饱和语义及强子响应仍未闭合，不能拿“四Calo同时MIP”失败选择声称校准。
同事件有/无CaloNu、物理系统变体与最终能谱收益未测量，不作可部署收益宣称。

每阶段必须获得有实测支持的新物理结论，写中文workbook、更新修订路线和下一Prompt，
记录值/单位/来源区间、样本与局限、命令、失败成本、CPU/RSS及产物；去重JSON并清理中间件。
Conventional Commit，提交blob读回验证，不push。最终回答给新结论、范围限制、报告/commit及唯一下一任务。
