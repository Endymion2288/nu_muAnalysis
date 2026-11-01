# 下一轮执行 Prompt：stage44 相对leading μ的局部活动信息

先读AGENTS.md、stage43中文报告/冻结配置/全量表，信息预算计划§10、修订路线§25。
当前stage43完成：同3703例/21来源，重点3024例I0 .28709694；理想S+sum .27076618
（改善5.688% [4.174%,7.179%]），data离峰噪声+40点pedestal .28325981
（1.337% [.572%,2.032%]）。正收益仍在，但未通过冻结2%点估计门槛，区间上沿仍包含2%。
半信号增益压力1.489% [.788%,2.176%]，不能由此宣称真实强子gain不重要/已标定。
S4→S+sum还有.764%有限BDT表示收益，理想参考不是严格上界。

z[−2300,−1950) mm的2062例：理想6.141%、实测噪声后.019% [−1.007%,1.063%]。
MC名义增益下99.56%所有模块SNR<1，中位总信号.00204 pC；总噪声RMS .11984 pC。
上游三层仍有正收益，保持局部价值；高y90例和最高Eν11例证据不足，不能剔除。
真实data gain/time/shower/系统和新独立ν确认均未测量。

本轮只选一条主线：**信息预算计划§5.1的相对leading μ局部活动变量BDT消融**。
利用现有SpacePoint/track/segment关系问是否有超出F6计数/全局矩的信息，先不升级GNN/Transformer。
重点100≤reco pμ<1000 GeV和100–250/250–1000子层，不截Eν，不恢复TeV动量修复主线。
保留原F6全部65项、highest-pz leading、truth fiducial含lead区、PMT veto、unit MC及困难事件。
不将truth/HITS/真实方向/PDG/matching变成部署输入，不把管道外活动直接称真强子。

先只读小样本审计，再冻结协议，最后才运行ν拟合：

1. 优先复用stage42/43的相同3703例/21来源与三折，输入原CaloNu PHYS的
   SpacePoint_x/y/z、Track_*参考面/传播面或TrackSegment_*。
   参考ml/extract_spatial.py、extract_sets.py，但不能直接套旧without-CaloNu几何。
   配置output_columns.yaml已有这些列，**实际源文件是否保存/对齐仍需审计**。
2. 核对run/event/cache row、所有向量对应关系、mm单位、actual station/layer位置；
   用可靠的局部reco位置/方向作为μ轴，不跨磁场用单条直线代替拟合传播。
   不用未对齐Track_hitSet索引建图。缺局部轴则显式missing并保留事件，不能悄悄丢弃。
   若现有列不足，先写明确几何/可观测量缺口，提出有物理依据的有限替代，不虚构可靠传播。
3. 拟合前冻结一组≤24个变量：可选各station距μ轴10/50 mm管道外计数、
   相对偏心与相邻station的活动增长。半径须有tracking分辨率/几何依据，不能用ν标签扫描。
   保留计数与原点云但破坏μ关联的一个预定义null；若用donor轴，留在同来源/角色与
   预定义reco p层，固定种子，不用truth z/y/E选配，不跨折。
4. ≤4000事件、≤9正式BDT+1小smoke，固定stage42 depth3/400轮和独立offset/scalar映射。
   同输入/事件/预算的I0允许缓存复用；若支持/容量变化必须重训公平基线并计预算。
   初始安排关系模型3 fits + null3 fits；剩余3不是自动扫描额度。
   不先读取本轮预测再选择半径/null/特征/种子，不重开stage34/35旧test冒充独立确认。
5. 预定验收重点相对I0 log-RMSE改善≥2%、来源配对95%下限>0；
   必须同报相对null的配对区间，避免把增加计数/随机容量效应当μ关联信息。
   同报mean/median bias、R68、尾及逐p/Eν/y/z/component/primary独立代理，
   重点检查多数下游弱CaloNu区域与高y；真z只作分层，不能部署gate。
   保留灵活scalar proper score及六箱谱诊断，区间宽时报告证据不足，不以风险替代最终谱收益。
6. 若有实用关系增益，再冻结新来源/谱系的独立确认；若无或统计不足，
   明确新增信息/支持缺口，不自动扩大空间网络或回到波形无上限调参。
   CaloNu原生修复/data增益保留为条件工作，不作为本轮所有ν研究的前置工程。

先smoke再Condor，只抽取紧凑摘要，不保存新大型ROOT/xAOD、不新跑G4。
表格训练RSS约200 MiB，可请求1GB（站点可能分配3GB）；CVMFS/现成runtime优先。
可切资源合适schedd，但stage43曾发生idle查询后恰好启动的竞态：
先hold并核对实际启动与已有完整折，再迁移，避免额外部分训练和预算不明。
EOS输出不见先XRootD核验，不盲目重训；exact rejoin后去重复缓存，记录耗时/RSS/吞吐/排队。

写中文stage44报告：目标、输入/选择、实际数值/单位、执行命令、统计/系统边界、
物理与程序原因、产物和下一步具体验收；未测量项明确标注，不以未知原因作结论。
更新两份计划和本Prompt，Conventional Commit提交并回读/确认clean，不推送。
最终给出本轮有效物理结论与下一条单主线。
