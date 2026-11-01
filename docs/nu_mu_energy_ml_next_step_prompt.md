# 下一轮执行 Prompt：stage48 冻结X/Z的来源迁移检验，零新fit

先读AGENTS.md、stage47中文报告/完整表/配置/验证、修订路线§29及信息计划§14。
stage47已完成，同3703例/21来源，X=F6全65+stage44冻结22项，重点3024例。
普通Calo四模块保存敏感沉积S对X改善−.2008% [−.6860%,.2982%]，SZ对Z−.1982% [−.7642%,.3483%]；
SZ对S仍3.6549% [2.5421%,4.7179%]，未建立风险交互，全部扩展门槛false。
中间区197例有局部收益；全3703例S对I0固定响应谱σ区间[3.982%,35.016%]为正，
但S对X [−2.736%,15.015%]跨零，不能概括成所有谱均无价值或把合并变化全归S。
6正式+1smoke预算耗尽，模型/offset/scalar回读精确。原HITS/pilot sharding和payload已归并删除，勿重跑归并器。
普通Calo采样模型/响应链、模块/时间/阈值/噪声、深度区域/容量和网络扫描到此关闭。

本轮唯一物理问题：**连续z的条件收益能否迁移到当前X/Z拟合和校准之外的来源？**
它可决定是否值得投入真正新的生产/信息支持；有限浅树oracle不是因果或信息论上界。
本轮0个新fit、0个新target offset/概率映射校准，不重新调模型；不开始新HITS/Geant4/RDO/PHYS生产。

1. 先一次有界metadata审计：只读现有manifest、阶段记录/来源列表和开发缓存，
   记录geometry/生产reference、run/source、角色和过去训练/选型/测试暴露；不全EOS递归找数据。
   优先认证同几何、同定义且从未用于开发/选型/校准/测试的来源。
   未能认证就明确记“无可认证新blind支持”，不凭文件路径或新划分称独立确认，不重开stage34/35旧test。
   已知可执行后备是stage35 fit/stage42 A中当前21来源之外的10606例/60来源（pi22/k31/charm7，重点8634），
   见stage47/next_support_counts.json；它们早期开发已暴露，仅当前stage44-X/stage45-Z未见，
   必须命名“来源外开发复现”，不叫新blind test、独立生产或真实data验证。
2. 在看新支持预测/残差前，写冻结配置/协议与逐源暴露表。
   若有认证新支持，优先用它；否则用上述后备，支持等级从此固定，不混合后改名。
   对合格来源按group字典序、源内(run,eventID,cache_row)排序，逐源轮转取样，直到4000例或耗尽；
   选择不依Eν/y/z/沉积/残差/新性能。不按重建p挑事例，重点只在后续评价定义。
   要求≥12来源、目标≥2000例。后备保留原stage42 assigned fold，不能以新标签优化角色。
   若真新支持无既定fold，先仅按来源身份确定并冻结fold；所有来源必须与三个旧模型的train/cal集合均不交叉。
   原最高pz leading、truth fiducial含lead、PMT veto/unit MC不变；不截Eν，不丢高y/代理失败/缺失/尾部/最高箱。
3. 复用原F6全65缓存，提取完全相同的stage44冻结22项reco局部摘要（station counts、相对leading μ活动）。
   先按已冻结来源顺序首pi/首K各≤20例，总≤40例pilot，检查身份、branch/单位、missing和已有F6一致性。
   原local_activity.py硬编码selected/3703支持，须新增适配器，不能把新特征误join原21来源。
   完整≤4000例通过Condor、必要列/entries/单文件读取、小摘要；不加半径/新信息族/null模型。
   pilot是特征/推理回读检查，不是拟合；完整支持失败不得填0、删难例或换有利完整子样本报告。
4. 仅加载每例原assigned fold的已存模型：
   X=`ml/artifacts/stage44/formal/{f}/local.ubj`，Z=`ml/artifacts/stage45/formal/{f}/oracle_z.ubj`。
   offset和scalar六箱映射使用各模型原独立cal数据/已存元数据，必要时从原cal确定性重建映射；
   重建只许使用原cal标签，不使用新支持标签、先验比例或残差，不算新target校准。
   用原3703例做小型冻结推理readback，确认模型/列顺序/offset/映射与已有预测精确一致，不能重训补救。
   新支持仅比较同事件X与Z；真z只oracle，truth方向/PDG/matching不得进入模型，不能用truth_st1模长估能损。
5. 主指标为100≤reco pμ<1000 GeV中Z对X的相对log-RMSE改善；
   预设有用迁移验收≥2%且500次pi/k/charm分层来源配对95%下限>0，条件于冻结模型/校准。
   同报总体、100–250/250–1000、≥1TeV参考、原六Eν箱、leptonic y、真z区域、component、独立primary运动学parent代理，
   各层N/来源/误差、mean/median bias、R68、尾>50%/>100%、proper/Brier与原六箱固定响应谱诊断。
   barcode不可得不称primary-confirmed。标注charm小来源/训练条件/研究暴露及系统未传播。
   同报原21来源结果作为历史参照，不把不同支持的点值差直接称物理因果或恢复比例。
6. 若通过，结论限定为当前支持等级的来源迁移，提出有界的真正新生产/新信息确认需求；
   若未通过，报告点值/区间与来源组成，不以少数离群或统计不足证明缺口不存在。
   任何结果都不能通过追加fit、目标重校准、重新选来源/区域/模型来“修复”。
   本轮必须交付跨来源物理风险比较，不能只交metadata清单或软件检查；支持确实不可得则如实写未测量。

资源与交付：CVMFS现成LCG，CPU1/限线程，小pilot后正式I/O走Condor；不需要GPU或新Calypso生产。
切schedd先hold并回读starts/输出，不并发重复任务。记录实际wall/CPU/RSS/读取字节/吞吐。
只留单份特征/预测/来源暴露表和紧凑JSON/TSV/SVG，复用旧模型，不复制ROOT/xAOD。
先写中文stage48报告（目标、输入/选择、全部实测、统计/系统边界、程序原因检查、下一步输入/验收），
再报告与相关代码/配置Conventional Commit；更新两份路线与本Prompt，回读blob/clean，不推送。
真实data、独立生产、正式flux/接受度/背景归一化和最终能谱总误差仍未测量，不能由unit开发MC替代。
