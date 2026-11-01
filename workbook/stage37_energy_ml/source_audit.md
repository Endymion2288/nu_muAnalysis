# stage37 原生来源、映射及响应机制审计

固定 MC 源 `1ec47efe`，data reconstruction reference `d0b1b2dd`。
原 CaloNu AFS build 不可读，采用已有 `d32b0ff3` runtime **只读持久化布局**；
不使用其普通几何的 CaloHit identifier helper，不进行普通几何重建。
冻结及输入见 [协议](preregistered_protocol.md)、四份 `request_*.json`。

## 原生身份与兼容性

`ml/locate_calonu_native.py` 在每份 50000 条 PHYS 的必要七列中，用
`eventID,p,x,y,raw0` 唯一 fingerprint 找实际 entry；最高 pz 轨迹、float32 与旧 cache 对齐。
不是把 selected row 当 input entry，也不是按重复 eventID 去重。
entry 的商/余数对应五份各 10000 条 HITS，随后逐例验证 HITS/RDO/rec run/event、
HITS/RDO primary PDG/status/三动量、rec/PHYS 四模块 raw/fit/status。
全部 128 例通过；两个初始 μ+ 作业的严格质量相等检查失败，实际质量仅相差
7.62939453125e−6 MeV（一个 float32 ULP），三动量逐分量完全相等。
质量容差为 0.001 MeV，其余身份/三动量仍要求精确相等，没有换 case 或配到别的子文件。
这个诊断只支持本 128 例的合并次序，不认证所有 PG 的生成谱系独立性。

以下文件在 `1ec47efe` 与 `d32b0ff3` 逐文件文本相同：

- `Calorimeter/CaloEventCnv/FaserCaloSimEventTPCnv/src/CaloHits/CaloHitCollectionCnv_p1a.cxx`
- 同包 `FaserCaloSimEventTPCnv/CaloHits/CaloHitCollection_p1a.h`
- `Waveform/WaveEventCnv/WaveEventAthenaPool/WaveEventAthenaPool/{RawWaveformContainer_p0,RawWaveform_p0}.h`
- `xAOD/xAODFaserWaveform/xAODFaserWaveform/versions/WaveformHitAuxContainer_v1.h`

每个实际 POOL branch 的持久化/加载 class layout checksum 相等；
只读 p1a 转换器的 energyLoss 与独立编码展开逐 hit 核对，含 65535 溢出编码。
这是字典布局和能量转换核验，不声称完整 release/conditions 等同。
见 [conditions_audit.json](conditions_audit.json)、[native_schema_checks.json](native_schema_checks.json)。

## 独立映射

源 `CaloNuDetectorFactory.cxx:313–318` 按 GDML 遍历计数，每行两个模块；
`CaloNu00.gdml` 的实际顺序是 TopLeft、TopRight、BottomLeft、BottomRight。
`CaloHitIdHelper.cxx` 定义 CaloNu bit、row 两 bit、module 两 bit，
故 hit id 为 `1 + (row<<1) + (module<<3)`。
`WaveformCableMappingTool.cxx` 由条件库 row/module/pmt 建立 CaloNu readout id；
`NtupleDumperAlg.cxx:initializeChannelMap/defineWaveBranches` 按 hardware channel 的有序 map 编号分支。

| GDML region | 物理体名字后缀 | row/module | hit id | readout id32 | MC hardware | PHYS branch |
|---:|---|---|---:|---:|---:|---|
| 0 | TopLeft | 0/0 | 1 | 3758096384 | 21 | CaloNu1 |
| 1 | TopRight | 0/1 | 9 | 3892314112 | 20 | CaloNu0 |
| 2 | BottomLeft | 1/0 | 3 | 4026531840 | 23 | CaloNu3 |
| 3 | BottomRight | 1/1 | 11 | 4160749568 | 22 | CaloNu2 |

历史 `CABP200_250908.db/OFLP200` payload 和本次原生 RDO/rec id32 都支持
branch→region `[1,0,3,2]`，与 stage36 关联峰相合；不是用关联峰调整的映射。
当前 `CABP200.db` 由 global tag `OFLCOND-FASER-05` 解析出的 `CableMapping-00`
却把 MC20–23 标为 `none`。**现今相同 tag 字符串不能复现旧生产。**
历史四条 payload 的数值、IOV、路径已保存在 conditions_audit，后续须显式固定，不静默使用当前 map。

data15838 hardware20–23，data16000/16923 为6/7/14/15，均按 row/module 对应上述编号。
但这没有认证 data 实际安装方向/测量 survey；stage36 data 空间关联候选 `[3,2,1,0]`
尚不能解释成 cabling 翻转，也不能把模拟 GDML 的全球 region 坐标直接搬到 data。

## HITS、kernel、时间窗和单位

`CaloNuG4_SD/src/CaloNuSensorSD.cxx` 的保存 energyLoss 含生产 Birk/nonuniform 响应修正，
这里只称**敏感层保存能量**，不是未修正 G4 总沉积、全探测器能损或 `truth_st1` 能损。

`CaloDigiAlgsConfig.py` 为 CaloNu 使用 `Detector="Calo"`。
本次 `/WAVE/Digitization` 的 Calo/CaloNu 两个 COOL channel 的实际 payload 相同：
baseline mean=15650 ADC、rms=3 ADC，kernel norm=.5500000119 ADC·ns/MeV，
mean=820 ns、sigma=3.670000076 ns、alpha=−.3199999928、n=1000。
`WaveformDigitisationTool.cxx:generate_calo_timing_waveforms/convolve_waveforms`：
hit 时间减 element center z/c；0.1 ns histogram；正时间 Crystal Ball PDF 卷积，再20采样平均至2 ns。
本阶段复写这一无噪声卷积，采用已审计名义 GDML center z/c；kernel 与 ROOT PDF 8 个点交叉核验。
未加载原生完整 GeoModel 或重现随机种子，所以叫名义响应预测，不是严格 digitization 重放。
2 V 是匹配 `RawWaveform` 默认量程；p0 未保存实际 range，
但以此换算 `(baseline_mean−ADC×2/16.384)` 与全部保存波形逐点**完全相等**。

保存窗口全部为780–930 ns，共76个采样；独立 conditions nominal trigger=820 ns，
`WaveformReconstructionTool.h` 默认 windowStart=−20、width=75，与窗口一致。
raw 是 `2*sum(max(w,0))/50` pC；signed 是 `2*sum(w)/50` pC。
raw 复算最大差1.9531250e−5 pC；rec/PHYS 电荷最大差2.6855469e−5 pC，均在冻结精度要求内。
阈下 raw 的整流 pedestal 不能通过减一个中位数就当作无偏信号：
`E[max(signal+noise,0)]` 对 signal 非线性，baseline 估计与选窗也有影响。

## 更正 stage36 的 HV 说明

前阶段引用 `CaloRecTool` 通式时，把普通 Calo 的 data HV 外推也描述成 CaloNu 的实际调用。
本次直接检查 `CaloRecAlgs/src/CaloRecAlg.cxx:148`，MC源 `1ec47efe` 和 data源 `d0b1b2dd`
均明确 `reconstruct(..., correct_gain=false)`。因此 **CaloNu 不做这项 HV 外推**。
stage36 所测 q/nMIP 是本调用的 MIP_ref，而不是隐藏 HV 比例。

以 stage36 已有 MC/data cache 共2040682个有限非零 q/nMIP 对照，
全部通过 `q=MIP_ref*nMIP` 的 float32 精度前向关系；正常浮点对的最大相对差5.95251e−8。
10对 subnormal 小值保留，按最小 subnormal 的绝对误差核查；不以近零比值的误差声称增益漂移。
MC payload=.0757 pC/MIP，data=1.892/1.847/1.902/1.986 pC/MIP。
这些不同常数不自动说明25倍错误，也不认证实际 PMT 增益相同。
本地 `/WAVE/Calibration/HV` 在15838两时期四个时间端点均无对应 CaloNu payload，
不能声称硬件 HV 稳定；但本调用不依赖该 HV 外推，所以不以此解释软件标度差。

15838 的 cable/MIP/range/timing IOV 在本 run 内相同，range=2 V，nominal=200 ns，offset=−48 ns。
已有 TBP/TAP15/15 占两文件96.3034%/96.1681%，同模式下 total 中位仍4.86558/.618096 GeV EM；
14/14 同模式下仍1.64596/.384149 GeV EM。简单更换这两种模式混合比例不能解释差异。
没有控制实际触发接受度、活动/位置或波形时序，原因仍未唯一确定，不归为某个硬件故障。

## 非有限积分的具体机制

8个诊断模块的保存 integral 均为−inf、status=0；其 raw 和 CB参数有限。
原源码函数 + 原 ROOT6.28/12 对4个代表逐波形重放，4个均重现−inf且 CB valid=1、fit_status=0；
时间813.83、815.21、814.21、814.49 ns均有限，**这四例不能归因到 time NaN 分支**。
一个正常 fit 55.320175→55.320174 mV·ns，阈下 raw 对照17.16455078125逐值相等。
两个故障拟合对照 status 相等、数值不精确复现；不声称完整作业拟合顺序/未初始化状态的重现。

ROOT6.28解析积分使用 `A=pow(n/abs(alpha),n)*exp(-alpha²/2)`。
[对应源代码](https://github.com/root-project/root/blob/v6-28-12/math/mathcore/src/ProbFuncMathCore.cxx)
中虽然后续乘负幂后理论结果有限，中间 A 已可能溢出。
这8例 log(A)=710.214–741.665，全部大于 double 上限709.782713。
同一保存参数用 log1p 的稳定点函数加分段积分得到0.858457–65.9948 pC的有限正积分，
并与30001点细网格梯形积分在1e−6相对容差内相合；没有重新拟合或覆盖保存读出。
因此这些例子的非有限来自积分数值路径，不是无限物理沉积或简单传输损坏。

`WaveformFitResult::clear()` 未初始化全部字段、time NaN fallback 未同步 valid、
valid/status不检查最终积分有限性，仍是需要有界补丁验证的独立程序问题；不以本8例解释所有异常。
不将负的有限瘦峰全部归为同一积分溢出机制。
