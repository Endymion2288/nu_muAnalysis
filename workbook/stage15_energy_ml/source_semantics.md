# 官方真值与匹配分支语义核查

固定源码版本：`git -C ../calypso show d32b0ff3:<path>`。

- `PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.cxx`：truth列表保存容器前十粒子，
  并非按PDG查找primary；保存产生/衰变顶点、PDG、barcode、产生四动量。
  原生t_pdg/t_barcode/t_pdg_parent/t_barcode_parent、t_truthHitRatio、t_px/py/pz
  与通过三站要求的Track_p0/pz0在相同分支填充；本阶段仍逐文件验证长度。
  Track_hitSet和Track_nMeasurements在筛选前填充，继续禁用其索引配对。
- `Generators/GenieReader/python/GenieReaderAlg.py`：GENIE产生单个交互顶点，
  status0初态映射HepMC入射状态4，status1为出射稳定粒子。primary候选要求
  与首个入射ν衰变顶点相同、ν/反ν符号对应的μ，且候选唯一；可重建时另以
  t_*的first-parent PDG与barcode确认。不能确认的子集单列，不能等价于错误候选。
- `Tracking/Acts/FaserActsKalmanFilter/src/FiducialParticleTool.cxx`：
  `getMomentum`中的`double p = hit.particleLink()->momentum().rho();`
  是truth粒子产生动量模长；方向由SiHit起止位置求得。`getTruthMomenta`对station
  内命中向量平均，模长的变化可能来自方向平均，而非真实材料能损。
  没有命中时返回NaN。truth_st1只能作为参考存在性/方向一致性诊断；
  不能用于测量产生点到spectrometer的物理能损。

核查命令：

```bash
git -C ../calypso show d32b0ff3:Tracking/Acts/FaserActsKalmanFilter/src/FiducialParticleTool.cxx
git -C ../calypso show d32b0ff3:PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.cxx
git -C ../calypso show d32b0ff3:Generators/GenieReader/python/GenieReaderAlg.py
```

实际输运能损及拟合曲率误差的独立分解：**未测量**，需SiHit时刻动量或可靠输运
状态输出；目前不为此重产xAOD。reco/primary产生动量比同时含物理与重建响应。
