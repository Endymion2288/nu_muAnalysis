# stage44 可观测量源审计

原生产参考沿用stage35 production_reference.tsv：CaloNuMC 1ec47efe / Calypso22.0.49，
FASERNU-CALONU、OFLCOND-FASER-05；pi log明确backward，K/charm对应bck的确切log未确认。
本轮直接核对所有选定实际PHYS，不以其他几何的schema代替检查。

可重复源码命令：

```bash
git -C /eos/home-x/xcheng/FASER/calypso show \
  1ec47efe:PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.cxx
```

- 1467附近：long track要求经过stations1/2/3；选择lead仍由最高Track_pz0决定。
- 1469–1506：Track_*0与*1分别取trackParameters front/back，坐标mm、动量MeV。
- 1660附近：Veto1 z=-1769.65 mm、Trig z=0；保存theta=atan(px/pz)，本轮tan还原斜率。
- 1885–1898：TrackSegment来自独立collection，无leading-track关联；不能任意选最近segment作已认证局部状态。
- Track_hitSet在long-track筛选前追加，因此本轮不用其索引。
- 没有存station2的leading拟合状态；本轮保留其SP计数，暂不构造跨磁铁直线或不明关联。

无标签8例输入审计：实际station中心[-1860.15,47.4,1237.4,2427.4] mm，
三层偏移[-31.5,0,31.5] mm，stereo/sides实际z最大偏离6.40005 mm。
三个本地轴最大点到参考面dz分别128.40005/85.30000/67.85498 mm。
最近点距离约0.027–1.566 mm；这是pilot观测，不作为分辨率测量。
事件255有2条long track，leading index=1，验证不是取首条轨迹。
事件304末站0点，仍保留局部轴及0计数，空outside集合的形状量为NaN。
事件68有8670 SP，说明不可用低占有率假设截点；保留全部点后只存摘要。

全量复核由local_activity.py断言run/event、全部所用Track向量长度、p0和F6首态坐标，
SP xyz与SpacePoints长度、station计数和F6总SP、actual层位置及局部dz。
实际全量数值见extraction.json；无可靠轴保留NaN+axisvalid，不丢事件。

80 μm strip pitch源码：Tracker/TrackerDetDescr/TrackerReadoutGeometry/TrackerReadoutGeometry/SCT_BarrelModuleSideDesign.h。
10/50 mm是粗活动尺度，远大于pitch和pilot核心距离；stereo方向更粗，不将pitch称三维分辨率。
B≤2 T、p≥100 GeV、L≤150 mm为保守量级假设，tangent偏离≤0.0675 mm；未作精确场图积分。
此上界远小于10 mm，但不认证跨station传播，更不定义真强子归属。
