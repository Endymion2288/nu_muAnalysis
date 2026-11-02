# stage53 SCT重放的配置与表示审计

## 已知生产与本轮运行环境

- 原μ production：Calypso 22.0.49 / CaloNuMC `1ec47efe`，geometry `FASERNU-CALONU`，global tag `OFLCOND-FASER-05`。证据为stage36 production_audit及明确的100049 `RDO-merge-0.rdo.log`、`00000-00004-RDO.rec.log`。
- 原`/afs/cern.ch/work/f/fasermc/mc24/s0015`安装已不存在。使用既有`software/calypso-master-d32b0ff3-el9-gcc13.tar.gz`，Athena24.0.41/gcc13，无Calypso包重编译。仅新分析摘要辅助代码用同gcc13编译；Cling内直接构造ACTS参数曾崩溃，失败不当物理结果。
- `git diff 1ec47efe d32b0ff3 -- Tracker/TrackerDigitization/FaserSCT_Digitization`、cluster/SP/segment相关包及p4转换器无源码差异。CKF seed mask含义由layer编号变为side编号，故本轮0..5对应原0..2，均排除全部IFT。诊断输出关闭。跟踪浮点复现差异必须另报，不声称所有历史构建细节已相同。
- 仅SCT几何足以数字化和计数；ACTS还必须加载Scint与Dipole几何。原日志和本轮均出现相同五条上游layer overlap警告；不得把警告当本轮噪声效应。未调用不匹配的CaloNu ID helper。

## actual前端与条件

| 项 | 原生产证据 / 名义重放 |
|---|---|
| Threshold | 日志6242.20电子；配置1 fC |
| TimeOfThreshold | 30 ns |
| DataCompressionMode / ReadOutMode | 1 / 1；不是compression=3的any-hit模式 |
| NoiseOn / AnalogueNoiseOn / UseCalibData | 源码/config默认True/True/True；生产日志未逐项打印，不仅凭默认认定。还须名义逐strip验证 |
| ChipNoise | global tag解析`SCT-DAQ-Calibration-Noise-02`，日志实际读192行 |
| ChipGain | `SCT-DAQ-Calibration-ChipGain-02`，实际读192行 |
| 当前DB实读 | 两run各192 channel，occupancy全部3.5e−5（无量纲）；gain folder NoiseByChip全部1600电子，gain52、gainRMS1.25、offset45、offsetRMS1.75 |
| fallback | NOBarrel3=2.1e−5不作为本轮实际occupancy |
| noise时间箱 | compression1/readout1时随机noise strip用010；cluster要求01X，接受该时间箱。三倍因子仅compression3/readout1，本轮不启用 |
| masking | checkBadChannels=True；本轮conditions日志192 sensor、0 bad strip/module；随机disabled-cell默认1%保持不变，不能把它与静态mask混淆 |

DB原值与字段长度见`conditions_audit.json`。ChipNoise的occupancy文本每行13个相同值，ChipGain每行12个值；没有修改条件数据或为此另开网格。占据率按实际tool读取，不从DB总行数推断有效sensor数。

`FaserSCT_FrontEnd::process`中的NoiseOn只门控独立`randomNoise`调用；AnalogNoiseOn单独控制信号及邻道模拟噪声。关`DoInnerDetectorNoise`还会关analog且可改OnlyHitElements，故不使用。移除noise调用会改变后续共用RNG draw位置；同seed不能声称所有信号随机涨落完全相同。

## 原生RDO表示和严格名义门槛

原RDO内保存了`FaserSiHitCollection_p3a_SCT_Hits`、`SCT_RDOs`、SDO与BeamTruth。初版直接用RDO中的HITS副本，但完整2048例出现28例strip/timebin不符；这组结果只保留为程序诊断，不用于噪声因果判断。最终改用对应60个原HITS文件中相同entry的SCT collection，只启用这一branch并在内存转换，保留原RDO作为同事件参考，无新G4、无文件副本。输入映射沿用stage37/38工具：子文件编号=合并文件起始编号+entry//10000，原条目=entry%10000；PG eventID重启时仍以source/entry区分。

初次把刚数字化的transient word直接与从POOL读回的word比较，所有word不同但strip ID/cluster完全相同。**这不是时间箱或响应不符。** `FaserSCT_DigitizationTool.cxx`将strip编号放word的11..21位；原生`FaserSCT3_RawDataCnv_p4`把row/strip另存，p4 word只存group size和timebin，persToTrans不恢复重复strip位。

因此使用生产同一个已编译转换器在内存中transToPers/persToTrans重放结果，再与原POOL读回的完整strip ID/word多重集精确比较。原参考再次转换必须幂等。保留pilot的转换前诊断，未手工mask不明位、未放宽数值容差，也不生成POOL文件。

必须同时通过原条目号、run/event、原PHYS/reference/replay全部六计数、原选择及名义两重建轨迹摘要精确一致的检查。旧PHYS与本轮tracking浮点值另列偏差；旧选择未复现时不准开展噪声因果解释。`IEvtSelectorSeek::curEvent`读真实原条目号；`SkipEventRanges`使用一基闭区间，已预检跨10000-entry子文件及重复eventID。


## 完整验证后的两项配置修正

- `embedded_hits_diagnostic.json`是结果选择的4例程序诊断，不估总体率：原HITS和RDO副本的decoded hit ID/顺序、能损及时间一致，但端点位置最大差1.9073486328125e−6 mm。p3a再次写出改变角度/微小位置；不能把RDO内HITS副本当作原数字化输入的逐bit等价物。原HITS重放解决所测失败例的strip/timebin不符，不以手工mask位或放松阈值补救。
- 原重建日志指定`/cvmfs/faser.cern.ch/repo/sw/database/DBRelease/current/acts/material-maps-alma9.json`，此前重放未设置。显式加载原材料图后，6个原失败/对照例全部恢复原选择。小诊断不能代替冻结2048例全量门槛；两臂均使用原HITS/同材料图，其他定义不变。
- 修正前完整结果归档`ntuples/energy_ml_stage53/pre_correction_nominal.tar.gz`，失败率/幅度表在`pre_correction/`；修正协议在`nominal_correction_protocol.json`。两臂结果前冻结的事件名单、单干预、重复次数和严格门槛均未改变。最终完整结果见本阶段报告，不以修正前结果判定噪声机制。
