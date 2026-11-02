# 冻结前定义核对

参考 Calypso `1ec47efe` 的 `PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.cxx`，用 `git show`/`git grep` 有界读取；不将参考源码等同于实际 r0022 的完整配置认证。

- L245–266：primary waveform (status &2)==0；charge=integral/50、raw_charge=raw_integral/50，mV ns/Ω=pC。status清零默认1（未过阈值）；不按status删除probe。
- L404–412、1834–1884：nClusters按SCT station ID0–3累加cluster collection大小；SpacePoints累加所配置collection的大小。无μ归属裁剪。
- L1884–1902：TrackSegments为普通segment collection条目数，不是GhostBusted；data六文件均无GhostBusted branch，本轮只测共有普通collection。不是总tracking效率。
- L1603–1716：传播失败坐标999999；Timing-plane为z=0mm；backward ACTS传播到该面。取严格|x|,|y|<80mm的共同中央坐标域，不把此域当作材料/对准一致证明。
- `xAOD/xAODFaserWaveform/.../WaveformHit_v1.h` enum：THRESHOLD_FAILED bit0、SECONDARY bit1、WAVE_OVERFLOW bit2、WAVEFORM_MISSING bit7、WAVEFORM_INVALID bit8。
- L875–975：可选DoScintFilter可能用Timing、Veto或Preshower组合。实际r0022开关未核实。TBP/TAP/inputBits保留pattern计数，但硬件菜单映射未认证，不据它宣布独立在线tag。
- L1330–1350：data blinding可能删去高Calo且各Veto低信号事件。当前四Veto raw>40pC tag不在该低Veto区；不测Veto完整分布。
- L1816–1831：data DoTrackFilter可要求碰撞BCID有longTrack；本轮已条件于恰一longTrack，不能测全tracking效率。
- 仓库 `AnalysisZipFramework/config/definitions.yaml` Timing总电荷为四通道sum；hitsTiming使用20pC，且y>20选top2/3、y<−20选bottom0/1、否则四路。这里20pC只作低信号描述阈值，不据此选样，亦不称无偏低信号效率。

MC是CaloNu几何粒子枪，data是2024_back/r0022；没有已认证相同材料、数字化、触发和噪声条件的成对生产变体。不把条件分布差异直接解释成增益系统，也不由单μ推出强子shower或ν能量bias。

## 有界补核 data 已知源码

stage37已记录data source `d0b1b2dd`，本轮仅在该已知commit核对应片段：`FillWaveBranches` L249–274同样只取primary且integral/50；L401–411的计数branch，L1750–1810的station/SpacePoint/普通segment累加，与MC参考代数相同；Timing面L1621仍z=0mm、坐标失败哨兵999999。排除了这些已核片段中的分母/单位或station重命名差别，未排除collection配置、tracker噪声/clusterization、触发、对准或实际生产条件差别。不递归扫描历史生产。

## 结果后的有限机制核查（不是定因）

MC参考源码 `Tracker/TrackerDigitization/FaserSCT_Digitization`：`FaserSCT_FrontEnd.cxx` L345–435有独立随机噪声strip注入，expanded readout/compression特定组合会用mode=3；header的fallback NOBarrel3=2.1e−5。`FaserSCT_DigitizationConfigNew.py` L170–190依DoInnerDetectorNoise配置NoiseOn/AnalogueNoiseOn，并默认UseCalibData=True，可由DB覆盖fallback。

所以必须核对**实际**噪声occupancy、threshold、timebin/compression/masking及collection配置，不能拿header默认值作为这些文件已用参数，更不能凭当前μ条件差异反求一个noise/gain系数。此处未重读历史生产、未重建、未测量噪声的因果份额。
