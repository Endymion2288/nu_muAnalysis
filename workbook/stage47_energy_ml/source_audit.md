# 普通Ecal敏感沉积定义审计

生产reference沿用stage35：CaloNuMC/1ec47efe、FASERNU-CALONU、OFLCOND-FASER-05。
只读`/eos/home-x/xcheng/FASER/calypso`的`git show 1ec47efe:<path>`，未重建生产；
现成d32b0ff3字典仅按每个文件layout兼容性读取，不冒充完整历史生产认证。

## 分支、模块与单位

- `Calorimeter/CaloG4/EcalG4_SD/python/EcalG4_SDToolConfig.py`：输出`EcalHits`，
  LogicalVolumeNames指向`Ecal::_dd_Geometry_DownstreamRegion_Ecal_Modules_OutCell`。
  这是普通下游Ecal的独立分支，未读取`CaloNuHits`或其他读出族。
- `EcalG4_SD/src/EcalSensorSD.h`：`m_ecal_calonu=0`；`EcalSensorSD.cxx`从module/row copy number构造hit，
  用Geant4 TotalEnergyDeposit（MeV）乘Birks及localNonUniformity后写入`energyLoss`。
  所以本S是**生产保存的修正后敏感能损**，不是未修正全介质总能损、完整强子能量或已标定EM能量。
- `Calorimeter/FaserCaloSimEvent/src/CaloHitIdHelper.cxx`：EcalCaloNu占1bit，Row/Module各2bit；
  Ecal ID=0+(row<<1)+(module<<3)。按物理(row,module)=(0,0),(0,1),(1,0),(1,1)得到[0,8,2,10]。
  `channel_hit_ids`是复用输出字段名，表示这个原始hitID，不是DAQ cable channel。
  未调用普通几何runtime helper解CaloNu，不照抄CaloNu的[9,1,11,3]或其增益。
- `EcalGeoModel/src/EcalDetectorFactory.cxx`：row0=BottomRow、row1=TopRow，全局变换来自geometry DB。
  **精确全局模块z/在本生产中的alignment未测量**，不从GDML或旧proposal猜路径/containment。
- `CaloEventCnv/FaserCaloSimEventTPCnv/src/CaloHits/CaloHitCollectionCnv_p1a.cxx`：能损持久化有压缩，
  使用原生converter还原后逐hit求和，不直接把packed shorts相加或自行替换能量解码。

聚合所有已保存粒子的所有hit，不选barcode/PDG/时间/阈值，不扣truth μ；GeV仅为MeV/1000。
hit_count保留QA但不进入模型。S与z都是oracle，未进入部署输入。
参考源码中的参数默认值不是实际完整生产参数证明；不据此恢复Birks之前的能量。

## 身份、完整性及I/O

原stage42压缩请求只保留PHYS指纹，located entry/ν签名没有归档，stage44也无原始entry。
因此必要重定位同21个原PHYS文件：唯一leading p/位置/CaloNu raw-charge/eventID指纹，
再核对HITS run/event及独立ν PDG/px/py/pz签名；这不改变样本/物理选择。
CaloNu raw-charge只作为身份指纹，未加入S特征或新训练gate。
批量严格覆盖3703例/21来源，不以匹配成功子集替代原支持；失败不补0。

实际210个HITS文件三分支loaded/saved layout checksum均一致，见schema_checks.json。
40例pilot与全量聚合逐项完全一致；输出归并后精确回读。
ROOT/uproot字节计数是客户读取的压缩basket/元数据量，不等于总EOS网络线速流量，
不计算全文件SHA，也不复制任何ROOT/xAOD。CPU1/每源一次文件打开，逐源成本与实际I/O见HITS_resources.tsv。

## 解释边界

F6已经含普通Calo四模块/总EM读出；新增S回答保存敏感层信号相对现有读出的潜在条件信息。
信号与EM读出的比值受采样/标定/时序/噪声/拟合和定义影响，不能只凭量纲或比值认定标定错误。
理想保存信号不等于实验可实现的读出，有限BDT无增益也不是信息论不可恢复证明。
真实data、强子响应、生产/材料/相互作用/谱系统与正式归一化均未测量。
