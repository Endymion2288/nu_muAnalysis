# 几何与对象语义核查

本阶段读取官方 d32b0ff3 merge 的 `SpacePoint_x/y/z`（globalPosition，mm），
不把 SpacePoint 计数等同于 SCT cluster 计数，不使用 truth 来建立 station。

对应本地 Calypso checkout `35c48423`：
- `PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.cxx:2117`：遍历原
  `FaserSCT_SpacePointContainer`，保存所有 `spacePoint->globalPosition()`；
  `SpacePoints` 累加 collection size，与 xyz 向量长度逐事件一致。
- `DetectorDescription/GeoModel/FaserGeoModel/data/geomDB.sql:2242`：
  `FASERNU-04 → SctTopLevel → SCTTopLevel-02 (107793)`。
- 同文件 3503/3504、3522–3526：SCT 平移 z=1237.4 mm，StationA/B/C
  相对−1190/0/+1190 mm，Interface 相对−3097.55 mm。
  得中心 −1860.15/47.4/1237.4/2427.4 mm。
- 同文件 2245/3534：`SCTFaserGeneral-01`、3 layers、pitch=31.5 mm。

逐点与最近 station/layer 中心比较，预先设10 mm容差。全量最大偏离
6.400048828 mm，与module错层相容；没有未分配点或几何边界上的点。
旧 EventDisplay 近似图和 ClusterFitAlg 的默认 zCenter 不作为此生产的几何真值。

上游切线偏移由原 leading 的(x0,y0,z0,px0,py0,pz0)和固定station中心计算。
这只是特征交互；没有求解带磁场传播，也不声称该偏移是点到拟合轨迹的物理距离。

audit中首次合并遇到YAML的未加引号null键变为None，而JSON键回写为字符串；
将配置键写为`'null'`后可与所有已产出的JSON配置逐项相等。数值参数、对象定义、
随机种子和输入均未改变，未重读或筛除事件。提取payload的原配置与最终配置在
JSON标准化后等价，代码另按字节核对。
