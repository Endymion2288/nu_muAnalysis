# stage44 拟合前冻结协议

冻结配置见 ml/configs/local_activity.json；冻结时尚未执行本轮ν拟合/读取本轮预测。
同stage42 B的3703例/21来源/三折/F6全65项，unit MC、原选择/highest-pz lead。
重点reco p100–1000 GeV，保留全部Eν/高y/lead区/缺失/尾部；开发证据不称新独立确认。

## 可观测量与物理尺度

CaloNu PHYS 8例无标签pilot已核对向量、mm单位、实际station/layer；最近点距局部μ轴0.027–1.566 mm。
生产源码1ec47efe NtupleDumperAlg front/back及传播面定义：IFT用Veto1 z=-1769.65 mm，
首站用Trig z=0，末站用拟合back state。仅在同station ≤150 mm短程直线外推，
不跨磁铁直线连接；中间station2缺leading局部状态，不以独立segment伪造关联，仅保留计数。
参考面转到各station中心存[x,y,dx/dz,dy/dz]；角为rad，斜率tan(theta)。
全量检查actual层偏差≤10 mm及局部距离；无效/sentinel999999轴设NaN，axisvalid=0，保留事件。
10 mm作为超出μ核心的粗活动尺度，50 mm作为宽活动尺度；不是hit归属或tracking分辨率。
80 μm strip pitch（TrackerReadoutGeometry/SCT_BarrelModuleSideDesign.h），stereo方向更粗；
无标签pilot的核心距离远小于10 mm。保守假设B≤2 T、p≥100 GeV、L≤.15 m时
0.3BL²/(2p)≤.0675 mm，远小于10 mm；这是局部弯曲量级估算，不是场图测量。
station横向范围~100 mm量级。两个尺度由几何选定，不依ν标签调整。
管道外是reco活动，不称真强子。没有truth方向/z/PDG/matching部署输入。

## 三候选和预算

counts=F6+四station SP计数（69输入）；local=F6+22冻结摘要（87输入）；
null=同点云、同四计数+换用donor三局部轴所得18摘要（87输入）。
22摘要：四计数+每s0/s1/s3的nout10/nout50、outside10的mean dx/dy、
sqrt(mean(r²))、axisvalid；无outside点则均值/RMS=NaN，计数=0。
原始非有限点不能定位时计入审计；station计数仅用可定位z，全部事件保留。
null在同来源/折、reco p预定[100,250),[250,1000),[1000,inf)、三轴有效模式内，
固定种子打乱池再循环移位；池>1无自配，singleton保持自身并报告。整套三轴一起换，
不使用truth选配，不跨来源/角色，保留计数/点云和有效模式。null是条件破坏关联控制，
不保证所有全局物理分布完全相同，不把一个null当唯一因果证明。
增加counts对照使用剩余3fit的理由：F6只含总SP和station cluster计数，必须隔离新SP计数。
总计9正式fit+1 smoke；400轮depth3、同独立cal offset/scalar，无调参/半径/种子扫描。
I0精确缓存复用；不改支持、容量、fold。每fit≤120 s，训练进程≤1800 s，提取≤1800 s。

## 验收与解释

重点local相对I0 log-RMSE改善≥2%且来源分层配对95%下限>0为实用门槛。
声称μ关系增量还需local对null及counts的区间下限>0；否则分别说明证据不足。
500次pi/k/charm分层来源bootstrap，条件于本次固定交叉拟合，不传播重训/生产系统。
报告all/focus/p/Eν/y/z/component/primary独立运动学parent proxy的log-RMSE、mean/median bias、
R68、|相对误差|>.5/>1；没有barcode不称primary-confirmed。
独立cal灵活scalar proper log/Brier及原六箱经验谱score，N=1000局部固定响应诊断非真实data误差。
无实用增益不自动开GNN/Transformer/波形扫描；有增益先冻结新来源独立确认。
先8例reco pilot与1小smoke，再Condor正式提取/训练；紧凑摘要、记录吞吐/RSS/排队和exact rejoin。

执行优化：调度等待期间、仍为0次启动时，将同一Condor作业改为all模式：先提取、再三折共9正式fit，避免二次排队；没有改特征/预算/事件/模型。
