# stage31 预注册：扩展轨迹读出与复合曲率响应

2026-11-01，全部提取/训练前冻结；小样本字段检查不用于选择收益。配置为 `ml/configs/track_response.yaml`。

## 问题与固定支持

stage30 动量 oracle 主导，保留完整46维F5（动量上下文、station计数、闪烁体电荷、常规Calo、空间矩）。只增加一个轨迹状态/几何信息族，不改变选择、truth fiducial、最高pz leading或unit权重；不删错配、离群和高y。使用原train 54,196例/91来源组和validation 13,375例/22组。train内部fit/stop/map沿用stage30的来源组分配；本轮map不用。calibration/test/challenge不读。

## 新信息族（19维）

F6=F5加配置的19项：back状态p/px/py/pz（MeV转GeV），x/y/z（mm），q/p0和q/p1（GeV^-1），log(p1/p0)，z1-z0（mm），px1/pz1-px0/pz0、py1/pz1-py0/pz0（无量纲），(x1-x0)/(z1-z0)、(y1-y0)/(z1-z0)（无量纲），首measurement的module eta/phi（离散无量纲），最大半径状态z（mm），事件SCT错误（0/1）。逐分支vector长度和原leading p/charge逐值核对；999999 sentinel在单位变换前转NaN，零分母/非有限值转NaN。不依据validation重要度筛变量；常数也保留并记录。

`Track_isForward`在旧data不存在，只作MC分层，不进入allowlist。`Track_PropagationError`实际是事件SCT Error，不是逐轨迹传播误差。p0/p1是同一拟合front/back状态；差异不是实测材料能损。hitSet/nMeasurements未核实关联，不用。

## 预算与验收

固定3 seed 20261029/30/31，每seed新增3个BDT：F6预测log Eν、F5/F6预测log(p_primary,vertex/p_reco)，后者输出p_reco exp(residual)。truth只作辅助标签，部署不输入truth。沿用stage30的depth5、1600rounds、patience80、4CPU、每fit120s，不扫描、不refit。复用stage30同seed F5 ν基线，总9个新fit。小样本20round smoke另记成本。

主风险为原六能量箱平均MSE再开方的macro log-RMSE；配对来源组bootstrap500次（seed20261101），三seed平均损失，报告逐seed及整体/能量/y/产生p/z/charge/confirmed/forward的log-RMSE、mean/median bias、R68、|relative error|>0.5/1尾部。辅助μ风险也用同六ν能量箱macro。相对风险改善5%为扩展预算门槛，区间不能排除时写证据不足；有害改善的符号照实报告。

另测κ_reco=q_reco/p_reco、κ_vertex=−sign(PDG_primary)/p_primary，报告差值（GeV^-1）、无量纲(p_primary κ_reco−q_primary)、median/R68/尾部及signflip；按上述层分开confirmed。它是产生点到重建的**复合响应**，包含传播、误选、拟合，绝不是同参考面pull。未取得真实输运动量/协方差，材料与拟合分解未测量，不使用truth_st1模长。

## data控制与范围

仅扫描run016000原PHYS前16,000例，预定穿透μ/MIP代理：恰好1条保存长轨迹、pz>100GeV、layers>=7、nDoF>=9、chi2/nDoF<15、rmax<95mm、两VetoNu charge>40pC、4路CaloHi nMIP均(0.5,2)。实测cutflow、19维有效性/分布与读出成本；不以此校准强子能量，不将与νMC不同选择/组成的差异称为mismodeling。旧data无isForward，暂不部署该标记。该控制不解除正式νdata的truth选择问题。

## 源码证据与尚缺输入

官方d32b0ff3 NtupleDumperAlg.cxx：1675起三站筛选后front/back状态；1691首measurement module；1742–1761 track type标记；1556的EventInfo SCT Error。PHYS无covariance/qOverP error。FaserSiHit.h仅保存局部步起终点、沉积能、时间和particleLink，无输运动量；不能用沉积能替代该粒子同参考面的动量。此检查不代表全部RDO/HITS绝无输运状态；后续需要检查实际TruthEvent/模拟持久化对象或另行小规模生产。

## data检查补充（主训练前，小样本及冻结控制区结果后）

原400例smoke最终0例；完整16,000例也是0例，pre-Calo保留4,908例。这个零产额不能用来证明tracker变量不可用。四Calo通道是横向分块，单条穿透轨迹不要求四块都在MIP；旧data双增益字段也需独立校准，前400例CaloHi各通道nMIP中位数约5，而CaloLo约0.2。故原预注册MIP定义失败，完整保留零产额结果，不调MIP阈值。

补充只读同前16,000例、原cutflow中pre-Calo的tracker+VetoNu候选（4,908例），测19维tracker变量有效性、Hi/Lo电荷/nMIP/status。命名tracker control，不称MIP校准，不选择新阈值；此为事后读出诊断，不改变MC特征/选择或9fit预算。
