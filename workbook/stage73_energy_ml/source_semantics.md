# stage73 有界源码核对

2026-11-03，只读 `/eos/home-x/xcheng/FASER/calypso` 中已知生产版本
`d32b0ff3:PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.cxx`，没有读新事件、
修改 Calypso 或重建。执行 `git show d32b0ff3:PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.cxx`
配合 `rg -n -C 4` 和 `sed -n '2080,2165p'`。

- L1656–1685：`layerMap` 来自 track 的 cluster-on-track station/layer；
  `m_nMeasurements` 在 station1/2/3 与参数有效性筛选之前 push，
  `m_nLayers`、χ²、DoF 和后面的 p0/px0/py0/pz0 则在筛选之后 push。
  这解释为什么 measurement 向量可以与保留轨迹数不同；当前 62 列不读该向量。
  不把历史 measurement 长度问题改称当前 ML 的逐行错位证据。
- L1683–1715：层数、fit χ²/DoF、前后参数在同一个保留轨迹循环填充。
  `ml/track_response.py:derive` 检查实际提取 Track 向量长度，取最高 pz0；
  `ml/frozen_evaluation.py:truth_diagnostics` 独立检查匹配向量长度。
- L2083–2119：nClusters0–3 按 `m_clusterContainer` 的 station ID 累加 collection size。
- L2121–2132：SpacePoints 累加 `m_spacePointContainerKey` 下 collection size；位置同时填充。
- L2135–2150：TrackSegments 计普通 `m_trackSegmentCollection` 的非空轨迹，
  GhostBusted 是随后另一 collection。两者未混用。

上述是 collection/记录顺序语义核查，不是选前重建效率、同一参考面 pull、
生产材料/对准/读出响应闭合或几何日志的逐例因果验证；这些项目未测量。
计数包含非 μ 活动与噪声，不能直接称为纯强子能量。
