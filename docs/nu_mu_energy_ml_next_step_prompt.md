# 下一轮执行 Prompt：stage45 粗深度的reco可预测性与ν收益

先读AGENTS.md、stage44中文报告/协议/全量表，信息预算计划§11与§5.2、修订路线§26。
当前stage44完成：同3703例/21来源，重点3024例；I0/counts/local/null log-RMSE
.28709694/.28643710/.28740092/.28731079；9正式BDT+1 smoke，没有删例或重开旧test。
local对I0 −.106% [−.934%,.614%]、对counts −.336% [−1.130%,.433%]、对null −.031% [−.678%,.649%]。
当前摘要没有实用关系增量；不能外推所有空间关系无信息，不自动升级网络或扫描10/50mm。
下游2062例.333% [−.590%,1.195%]、高y90例.465% [−1.292%,1.986%]，概率/六箱谱也未建立改善。
三局部参考面全有效，station2无leading状态仅计数；不以独立segment/跨磁场直线伪造几何。

本轮只选信息计划§5.2：**reco能否恢复粗深度，以及软区域概率是否改善ν能量**。
stage42同开发支持真z约4.09%参考增益、CaloNu的深度依赖是动机，不预认成功。
重点仍100≤reco pμ<1000 GeV（100–250/250–1000子层），≥1TeV参考，不截Eν。
保持F6全65项、stage44冻结22项、最高pz、原truth fiducial含lead区、PMT veto、unit MC及全部困难事件。
truth z只作辅助标签与oracle，禁止部署truth gate；不混入真实方向/PDG/matching。

执行顺序：先只读审计输入/区域支持→冻结协议/模型/预算/种子→1小smoke→Condor正式→物理评价。

1. 复用ntuples/energy_ml_stage42/development.npz与stage44/features.npz，精确cache_row/run/event/fold rejoin；
   不重扫ROOT。用actual target/material几何预定义粗区域，建议保留已报告五个深度层，
   先核对覆盖/稀疏/材料gap，缺失必须保留；不可根据本轮ν预测合并标签。
2. 只用X=F6+22个reco摘要预测区域完整软概率。每外折训练角色内部按来源固定两折：
   两个内部classifier给外训练事件OOF概率；第三个classifier在全部外训练来源拟合，给独立cal/eval概率。
   内部折不跨来源，类缺失/先验处理预先冻结，禁止in-sample stacking或以真z选配/gate。
3. 同X的小BDT比较：缓存local（X）、X+reco软区域概率、X+真z隔离oracle；I0作物理基线。
   原能量400轮depth3/种子/offset/独立cal scalar不变。区域模型也冻结单一小容量，不做架构或阈值扫描。
   总预算≤15正式fit+1 smoke：9区域classifier（3外折×[2内部+1完整]）、3reco能量、3oracle；≤4000事件。
   若因支持必须变事件/容量，对照须公平重训并计入预算，不默认突破上限。
4. 拟合前冻结验收：重点reco候选对I0 ν log-RMSE改善≥2%、来源配对95%下限>0；
   同时报告对local的配对增量。区域log/Brier相对训练先验、混淆/来源迁移是可预测性诊断，不能替代ν验收。
   同报all/p/Eν/y/z/component/独立primary代理的bias/R68/尾，重点下游多数与高y/最高能支持完整保留。
   灵活scalar proper和六箱经验谱保留；真z oracle只隔离缺口，不称部署收益或严格信息上界。
5. 根据结果只选一条下一主线：oracle有益但reco难恢复→明确现有观测量缺口，转新有效读出/独立物理支持；
   区域可恢复却无ν增量→不扩架构；若ν有实用增量→冻结新来源/生产谱系独立确认。
   不回用stage34/35已解封test冒充确认，不靠少数离群值停分支，不把全部差距归给高p tracker。

CVMFS LCG_109/现成runtime；缓存小，1CPU/1GB足够，站点可能改3GB。
参考stage44 all模式，在同一Condor作业内完成有限训练，避免重复排队；不在交互节点跑批量任务。
切schedd前hold并回读启动状态/完整折；低idle不保证合适资源，Hostgroup限制在多个schedd相同。
EOS文件不见先XRootD核验；不盲目重训，不留大型副本或重复JSON，回读后清理临时产物。

写中文stage45报告（实际输入/命令/数值/单位/统计与系统边界/物理及程序原因/成本/产物/具体验收下一步），
未测量项明确记录。更新两份计划和本Prompt，Conventional Commit提交、回读blob与clean，不推送。
最终给本轮有效物理结论和下一条单主线，不以分类准确率、风险或proper score替代最终真实谱收益。
