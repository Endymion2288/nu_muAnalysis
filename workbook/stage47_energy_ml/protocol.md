# stage47 正式提取/拟合前冻结协议

起点44b5898，ml/configs/ordinary_calo_information.json含UTC冻结时刻；此时仅已执行预定40例pilot，无能量fit。
仅新族S_Calo：普通Ecal四物理模块保存敏感沉积，按(row,module)=(0,0),(0,1),(1,0),(1,1)，hitID=[0,8,2,10]。
production 1ec47efe源码确认EcalCaloNu=0、row/module位段和EcalHits命名；pilot实际四ID覆盖，未知ID=0。
保存energyLoss含生产Birks/局部非均匀性修正，MeV→GeV，仅数学单位转换，不称完整强子能量或EM标定。
不筛时间/阈值/粒子类型、不扣truth μ、不拼其他敏感读出；hit数仅QA，不进入能量输入。
精确全局模块变换尚未测量，不从GDML推断实际containment/路径长度。

## 支持和执行

同3703例/21来源（pi8/k10/charm3），F6全65+22局部X87、原三折及unit MC。
保持最高pz/original truth fiducial含lead/PMT veto，重点reco pμ100–1000 GeV、100–250/250–1000子层，≥1TeV参考。
不截Eν，不删高y/代理失败/缺失/离群/最高能箱。旧stage34/35 test不重开。
pilot首π0/首K46各20例，无标签/信号筛选；全量仍按原21来源，最多4000例。
requests归档仅原PHYS指纹，无located entry，必要重定位记录见prepilot_protocol.md；不改变事件。
只读取最小PHYS指纹/ν签名列及HITS EcalHits/EventInfo/BeamTruth三个分支，单源每HITS文件一次打开。
先pilot后21个CPU1 Condor提取，内存请求2GB（站点可调整），wall每源≤1800s；无新G4/RDO/PHYS生产。
最多每源2次提取尝试，只能因可定位技术错误重试；成功输出不盲目覆盖，先XRootD检查可见性。
空hit可定义为零；缺失branch/未知ID/身份或layout失败不可补零，不能删例换完整子集。
全3703例匹配后才启动能量比较；不完整则报告不可测量，不新开生产链。

## 固定模型与信息门槛

仅普通Calo oracle S=X+S_Calo（91列）、SZ=X+S_Calo+连续真z（92列）。
S、z均oracle，禁止部署或truth gate；没有真实方向/PDG/matching作为模型输入。
复用stage45精确I0/X/Z基线；不重训基线、不扫模型/噪声/模块/阈值/种子。
3外折eval=f、train=(f+1)%3、cal=(f+2)%3；来源无交叉。
固定400轮depth3/eta.04/minchild20/lambda10/subsample.8/hist/nthread1，种子20261101+fold。
独立cal offset与灵活scalar六箱映射；不用eval标签拟合/校准。
≤6正式fit（2模型×3折）+≤1个20轮/200训练/200cal/100评估小smoke，仅S做smoke。
同一CPU1 Condor作业内三折，单fit≤120s，训练任务≤1800s。

重点S对X相对log-RMSE改善≥2%且500次pi/k/charm分层来源配对95%下限>0；
SZ对Z条件增量点值非负是既定扩展必要条件，强条件信息证据另要求来源下限>0。
同时给SZ对S、S对I0和Z对X参考，不机械相减为因果比例或严格信息上界。
报告全p/Eν/y/z/component/primary独立运动学parent代理、mean/median bias、R68、尾>50%/>100%、proper/Brier与原六箱N=1000固定响应经验谱。
来源bootstrap条件于固定拟合/校准，不含重训/系统/研究选择；不把barcode不可得代理称confirmed。
不以少数离群或有利层终止/夸大全体收益，不用truth_st1模长测能损。

## 决策与交付

有实用且已知z后仍有条件收益才决定可实现的普通Calo响应/独立确认；局部收益保留占比和区间。
无实用收益结束此理想采样支线，转来源/生产谱系独立支持，不追加网络/电子学/区域扫描。
真实data/系统/归一化/最终谱收益均未测量，不以开发MC结果替代。
紧凑聚合、实际I/O/CPU/RSS/吞吐、模型/offset/scalar回读、身份/角色/缓存/预算核验。
归并后精确核对pilot与逐源shard，再只保留一份敏感摘要和一份压缩located requests，不留ROOT/逐hit副本。
先中文报告，再Conventional Commit，更新路线/信息计划/下一Prompt，回读blob/clean，不推送。
