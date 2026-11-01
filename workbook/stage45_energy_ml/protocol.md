# stage45 拟合前冻结协议

冻结时本轮尚未执行classifier/ν拟合；配置ml/configs/coarse_depth.json含UTC时间和起点commit。
3703例/21来源/原三折，F6全65项+stage44冻结22项（87输入）原样使用，unit MC。
重点100≤reco pμ<1000 GeV，保留100–250/250–1000、≥1TeV参考、不截Eν/不删高y/尾/lead/代理失败事件。

## 区域、输入与覆盖

五个半开z区域[-3000,-2928),[-2812,-2600),[-2600,-2300),[-2300,-1950),[-1769.65,-1619.65) mm。
边界沿用原truth fiducial/material gap及已报告深度层；-2600/-2300是分析粗分界，不冒充探测器模块边界。
原选择已排除[-2928,-2812]材料窗口，lead单独保留；无新z cut或筛选。
全量覆盖62/246/568/2510/317例，unknown/outside=0；若后续回读覆盖失败则停止查错，不能丢例补齐。
truth z只作辅助监督标签或oracle输入，推理候选仅用reco；不混入真实方向/PDG/matching。
深度classifier不使用component/group/fold/run/eventID为输入，这些仅用于来源划分和诊断。

## 训练与OOF信息流

每外折evaluation=f、train=(f+1)%3、cal=(f+2)%3；角色严格来源隔离。
在外train内按来源组字符串排序、rank%2形成两个内部折，不按z/y/Eν表现调划分。
两个内部classifier各仅用另一半训练，生成自己未见来源的完整5概率向量；这是能量训练输入。
第三个classifier在全部外train拟合，供独立cal/eval；禁止以in-sample深度概率训练能量模型。
内部概率与全外train模型可能有样本量/先验/分布差异，报告OOF/cal/eval proper/来源诊断，不事后调模型。
每外训练角色只有1个charm来源，内部一半没有charm；保留该真实支持缺口，不跨折借样本。

深度classifier固定200轮depth3、eta.04、min_child_weight20、lambda10、subsample.8、hist、单CPU。
训练类别先验用(count+.5)/(N+5*.5)，作为每类log base_margin并用于其所有predict；参考常数先验同该fit。
即使某类在训练中缺失也保留5输出和正先验，不合并类；本次内部每类均≥5例。
无深度后校准/阈值/类权重扫描，评分对概率作固定1e-12数值保护，不以裁剪提升声称物理性能。
区域准确率不是验收；同报log/Brier相对训练先验、5×5混淆、每区域召回、来源/组件迁移。

能量候选reco_depth=X+5软概率（92列）、oracle_z=X+真z（88列，仅隔离诊断）。
能量400轮depth3及其余参数/种子与stage44完全相同；独立cal的offset与灵活scalar映射，不接触eval标签。
对照复用stage44精确相同X的local以及stage42 I0；不改事件/支持/容量。
计划15正式fit：9classifier（3外折×[2内部+1全train]）+3reco能量+3oracle；1 smoke仅20轮classifier。
每fit壁钟≤120s；单Condor进程含全部三折≤1800s，CPU1、请求1GB（站点可能配3GB）。
不额外扫描半径/容量/区域/种子，不运行新ROOT/G4/Athena或空间网络。

## 验收与统计

重点reco_depth对I0改善≥2%且来源配对95%下限>0；同时对local配对下限>0才声称新增表示有增量。
五区域模型是X的确定性学习表示，成功也不称新增独立读出信息。
500次pi/k/charm分层来源bootstrap，来源数8/10/3，条件于固定交叉拟合，不含重训/生产系统。
同报all/p/Eν/y/z/component/独立primary运动学parent代理的log-RMSE、mean/median bias、R68和尾部。
真z只用于分层/oracle，不能部署gate；barcode不可得不称confirmed。
独立cal灵活scalar proper/Brier、原六箱固定响应N=1000经验谱，宽区间不得当实际data谱精度。
主比较完成后不靠少数离群中止或追加架构；若oracle有益而reco无实用增量，区分区域可预测性与ν利用限制。
下一条主线由实际结果选择：新独立支持/有效新读出、或冻结候选独立确认；不默认继续重用开发样本调参。

## 产物与核验

只读紧凑stage42/44缓存，无需重新抽ROOT。先1smoke，再同一个Condor作业内三折训练。
保存OOF/fulltrain来源集合、每fit先验/轮数/资源与紧凑预测，用于角色与精确rejoin证明。
最终中文报告必须写物理和程序原因、实际数字/单位/命令/成本、未测量系统、下一步具体验收。
先报告后Conventional Commit，回读提交blob和clean，不推送。
