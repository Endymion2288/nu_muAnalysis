# 下一轮执行 Prompt：stage46 真实粗区域oracle，拆开粒度与估计质量

先读AGENTS.md、stage45中文报告/协议/全量表，信息预算计划§12、修订路线§27。
当前stage45完成：3703例/21来源，重点3024例；X=F6全65+stage44的22摘要。
9个来源OOF/全外train深度classifier、6个能量BDT、1 classifier smoke；没有重开旧test或删例。
区域accuracy68.188%→79.134%、log score差−.424965 [−.446229,−.402454] nats；
但ν I0/X/R（X+预测粗区域概率）/Z（X+连续真z）log-RMSE
.28709694/.28740092/.28710998/.27690373。
R对I0 −.0045% [−.8410%,.7364%]、对X .1012% [−.2224%,.3984%]；
Z对X3.6525% [2.2156%,5.0617%]，下游2062例4.3215%，高y90例8.0636%。
小scalar proper收益只在R对X确认，对I0及六箱谱未确认，不抹去也不升级为实用ν风险改善。

本轮唯一主线：**同X增加真实五区域one-hot控制C**。
理由是Z与R同时改变连续/粗粒度与真值/估计质量，不能由当前差距归因全部精细z或分类误差。
这不是继续扩大区域模型预算；只补3正式fit的明确oracle控制，完成后停止区域/容量扫描。

1. 只读复用stage42 development.npz、stage44 features.npz、stage45预测与冻结区域；
   精确cache_row/run/event/fold rejoin。同3703例/21来源（pi/k/charm=8/10/3）、原三折。
   F6全65项+22摘要/最高pz/original truth fiducial含lead/PMT veto/unit MC不变。
   重点100≤reco pμ<1000 GeV及100–250/250–1000，不截Eν，≥1TeV参考；困难事件全保留。
2. 五个固定半开z区间[-3000,-2928),[-2812,-2600),[-2600,-2300),[-2300,-1950),[-1769.65,-1619.65) mm。
   沿用62/246/568/2510/317支持，不能依ν标签/预测合并区域；-2600/-2300是分析分界非模块边界。
   C=X+5个真类one-hot（92列，与R同列数），truth仅oracle；不能部署真z/类gate、真实方向/PDG/matching。
3. 拟合前冻结预算/参数/种子/验收。仅3正式能量BDT+最多1个小smoke；
   原400轮depth3/eta.04/min_child20/lambda10/种子/来源角色和独立cal offset/scalar完全一致。
   I0/X/R/Z允许精确缓存，不再训练classifier，不新ROOT/G4/Athena，不扫容量/区域/半径。
4. 冻结并报告重点C对X、C对R、Z对C的来源配对区间；C对X≥2%且下限>0为信息诊断门槛，
   不是部署验收。保留all/p/Eν/y/z/component/primary独立运动学parent代理、mean/median bias/R68/尾、
   灵活scalar proper与原六箱谱。barcode不可得不称confirmed；真z只诊断，不用truth_st1估材料能损。
5. C接近Z说明完美粗知识可能足够，约束当前估计/其利用的不足；C接近X且Z有益支持当前粒度不足。
   但连续z与one-hot对有限BDT的可用表示也不同，C可能优于Z，不当严格信息上界/唯一因果分账。
   不以一次不显著当相等；报告差值区间与无法区分的范围。
   完成该控制后只选有效新读出信息或新的独立物理支持，不追加区域分类器/分箱扫描。

先小smoke，再单Condor作业内3折（CVMFS LCG_109、1CPU/1GB足够，站点可能改3GB）。
参考stage45 wrapper，只读小缓存；资源计时、模型回读/精确rejoin、预算与角色验证必须完成。
切schedd先hold并回读实际启动状态/完整折；stage45的12队列等8分多无启动，安全迁10后51s匹配，
不保证未来排序相同，不根据低idle独断资源合适。EOS文件先XRootD核验再决定，不能盲目重训。

写中文stage46报告：实际样本/配置/命令/数字/单位、物理和程序原因、统计/系统边界、资源/产物、具体下一步。
未测量明确写出；不把unit开发MC风险/proper/经验谱当真实data收益或独立确认。
更新两份计划和本Prompt，Conventional Commit提交、回读blob与clean，不推送。
最终给本轮物理结论及下一条单主线，不以分类准确率代替ν收益。
