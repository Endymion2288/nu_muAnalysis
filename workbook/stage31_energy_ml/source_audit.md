# 轨迹字段与真值边界审计

版本：官方Calypso d32b0ff3，NtupleDumperAlg.cxx（不是当前工作区未冻结源码）。

| 字段 | 源码语义 | 本阶段用途 |
|---|---|---|
| Track_*0 / *1 | 三站要求后同一Trk::Track的trackParameters front/back；位置mm、动量MeV | p0/p1为同一拟合的相关状态，不作独立测量或材料能损 |
| Track_charge | upstreamParameters->charge()取int | q/p，单位GeV^-1 |
| module_eta0/phi0 | measurementsOnTrack()->front()的SCT module | 已关联的几何变量 |
| Track_z_atMaxRadius | 同一track states中最大半径位置的z | 几何/拟合响应变量 |
| Track_isForward | merge中KalmanFitter=true、Unknown=false，三站填充块内 | MC分层；旧data缺失，禁入部署输入 |
| Track_PropagationError | EventInfo SCT::Error=1，否则0 | 正名ML_event_SCT_error，事件级，不是逐轨迹传播拟合错误 |
| Track_hitSet / nMeasurements | 三站筛选之前的不同填充范围 | 不按保存轨迹索引，不使用 |
| covariance | PHYS无q/p误差或拟合协方差；源码的单位矩阵是临时传播输入 | pull、分辨率协方差闭合未测量 |
| truth_st* / t_st* | stage15已核实模长来自产生动量 | 禁止测材料能损 |
| FaserSiHit | 局部步起/终点、沉积能、时间、particleLink；无输运动量 | 不以沉积能冒充粒子同参考面动量 |

复核命令：

```bash
git -C ../calypso show d32b0ff3:PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.cxx
git -C ../calypso show d32b0ff3:Tracker/TrackerSimEvent/TrackerSimEvent/FaserSiHit.h
git -C ../calypso show d32b0ff3:Simulation/ISF/ISF_HepMC/FaserISF_HepMC_Tools/python/FaserISF_HepMC_ToolsConfigNew.py
```

NtupleDumper关键行：1556–1560（SCT错误）、1675–1715（筛选、front/back、module、q、状态）、1742–1761（方向来源）。复合曲率使用产生点p，只能定位尾部/符号问题，不能分开产生点到参考面的传播和同参考面拟合。

## 实际原始输入检查

manifest index101，run200083，K组件00000–00009，原RDO：
`/eos/experiment/fasernu-data0/faser/sim/mc24/genie/200083/rdo/s0014/FaserMC-MC24_Genie_epos_k-200083-00000-00009-s0014-RDO.root`。

只读ROOT目录/CollectionTree分支元数据，并尝试1例TruthEvent。存在：
`McEventCollection_p6_BeamTruthEvent`、`McEventCollection_p6_TruthEvent`、
`FaserSiHitCollection_p3a_SCT_Hits`、`TrackerSimDataCollection_p3_SCT_SDO_Map`和raw waveforms/SCT RDO。
该文件未列出TrackRecord或拟合轨迹分支。uproot读取1例unsplit TruthEvent时遇到
`NotImplementedError: memberwise serialization of Model_McEventCollection_5f_p6_v1`，没有获得输运动量。
这只是当前reader限制，**不是TruthEvent无相关信息的证据**。

官方TruthStrategyGroupCfg保留指定EM/核过程及衰变，ParentMinEkin/ChildMinEkin=100MeV；
不能据此假定在任意tracker参考面有完整步状态。下一步需用匹配native POOL/ROOT字典读取实际
TruthEvent的μ continuation/顶点，核实覆盖率、barcode延续和参考面；如不足再设计少量输运步导出。
已有本地Calypso构建目录 `../calypso/build/x86_64-el9-gcc13-opt`，但本轮未运行该构建做新的重建或模拟。

## data边界

run016000 r0022旧PHYS含所需front/back、module、SCT error字段，缺Track_isForward。
Calo是Hi/Lo双增益，不能直接拿MC单增益字段名替代。原定“四块同时MIP”选择失败；
仅作tracker候选的字段有效性检查，不宣称νdata闭合、曲率truth校准、MIP或强子能量校准完成。
