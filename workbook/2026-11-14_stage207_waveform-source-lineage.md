# 阶段207：Preshower电荷差异的源码与版本历史定位

## 阶段目标与结论

回答同一个RDO事件的Preshower电荷为什么不同、哪版修改了配置、是否由坐标旋转造成。本阶段只读外部Calypso，核查Git历史、调用链、配置和既有真实事件重放，并在相同ROOT环境重新检查固定参数积分；没有更改重建实现或cuts。

**定位结果：这是两套软件基线中的波形实现不同。名为“旧版”的master已经包含较新的波形更新，名为“新版”的旋转分支没有该更新。不是`geometryRotation`提交改坏了Preshower，也不是旋转让同一条ADC波形的物理沉积发生变化。**

阶段204曾写“新源码改回Integral”，阶段206按old→strict方向展示“移除/改变”等差异，这只是两版源码对照方向，不能作为历史修改方向。本阶段纠正：旋转分支继承较早的`Integral`及拟合流程，master后来更新为`IntegralOneDim`等实现。此前测得的电荷、效率和迁移数不变。

## 哪个版本、哪次提交改变了什么

本次比较的实际版本和Git提交日期如下，日期不是文件夹创建时间：

| 标签 | commit | Git提交日期 | 波形实现 |
|---|---|---|---|
| strict的旋转源码基线 | `88c457c1`，`geometryRotation` | 2026-07-08 | 较早波形实现，另叠加已冻结的tracking本地修改及strict材料图 |
| 上游波形更新 | `dd56a65e`，Eric Torrence，`Waveform reco update` | 2026-08-16 | 更新波形拟合、积分器、overflow和cleanup配置 |
| old的master基线 | `d32b0ff3` | 2026-10-09 | 包含上述波形更新 |

`88c457c1`的author date为2025-11-04、commit date为2026-07-08，不能混用。两个比较版本相互都不是祖先；不能将用户所谓“新版”理解为“旧master加一次旋转”。

逐字节核查的五个文件为`WaveformReconstructionTool.cxx/.h`、`WaveRecAlgsConfig.py`、`WaveformCleanupTool.cxx/.h`：

- old五个文件全部等于`dd56a65e`更新后的版本。
- strict五个文件全部等于`dd56a65e^`更新前的版本，也等于旋转提交的父版本`73c97758`。
- 当前外部工作树的五个文件全部等于`88c457c1`，没有本地波形修改。
- `88c457c1^ → 88c457c1`在整个`Waveform/`目录的改动文件数为**0**。
- `dd56a65e → d32b0ff3`在整个`Waveform/`目录的改动文件数为**0**；更新是old祖先，不是strict祖先。
- old/strict的`Waveform/WaveformConditions/`目录改动文件数为**0**。

因此这五个关键文件的差异可以精确定位到上游`dd56a65e`。见[提交元数据](stage207_waveform_lineage/commits.json)、[机器可读逐文件核查](stage207_waveform_lineage/source_audit.json)、[按真实历史方向保存的更新补丁](stage207_waveform_lineage/upstream_waveform_update.diff)。

## 配置不同，还是算法不同

两者都有，但不是Preshower分析阈值或几何窗口被旋转：

| 项目 | strict：更新前 | old：更新后 | 影响 |
|---|---|---|---|
| Preshower配置 | `FitWindowWidth=100`、`BaselineSampleHi=60` | 相同 | 窗口宽200 ns、基线前60 samples没有改变 |
| 工具默认`RemoveOverflow` | `true` | `false` | 来自C++头文件默认值的改变，不是用户的旋转配置 |
| Python cleanup参数 | `KeepAll/Prescale` | 增加`KeepOverflow` | 保存overflow波形的配置接口改变；不要将保留vector直接当成电荷算法 |
| CB积分API | `TF1::Integral` | `TF1::IntegralOneDim` | 后者代码明确注明规避symbolic integrator的FPE |
| Gaussian约束 | width 0–20 ns；没有同等正peak约束 | peak 1–5000 mV、mean在窗口内、width 1–50 ns；分步拟合及emergency fit | 同一ADC可以拟合成不同参数，失败率/非物理解不同 |
| 拟合失败处理 | Gaussian重试后仍保存gfit；CB失败保留该结果 | Gaussian失败保留raw，CB从此前可用估计起步；overflow失败另有raw回退 | 失败拟合能否污染最终charge不同 |
| raw积分 | 全窗只加正samples | 全窗带符号求和 | 两版raw本身就不是同一个估计量 |
| raw初始mean/width | 全窗正samples | 峰附近±10 samples的正samples | 改变拟合起点；原始ADC无需变化 |
| overflow拟合 | 删除饱和点后普通CB流程 | 增加专用overflow拟合、170 ns相关配置 | 主要影响高信号尾；精度优劣不能只根据电荷大小判断 |

`WaveformHitRecCfg`给Preshower工具传入的重建参数在两版都是`PeakThreshold/FitWindowWidth/BaselineSampleHi`这组可接受参数；生产runner没有额外覆盖积分器或`RemoveOverflow`。`faser_reco.py`两版的波形调用另有`KeepOverflow`存储参数差异，但不是改变PS阈值。MC标志、FASERNU-04几何及OFLCOND-FASER-06条件延续共同重建配置；没有为本阶段重新计算数据库payload。

**主要差异是编译进工具的算法和默认属性，不能仅修改一个Preshower Python参数就宣称两版已经一致。** 其中哪些更新值得采用仍留待下一阶段逐项决定。

## 为什么旋转不会进入这条电荷计算链

实际源码路径如下（完整带原文件行号的定位见[源码摘录](stage207_waveform_lineage/source_excerpts.md)）：

```text
RDO: PreshowerWaveforms（已经digitize的ADC samples）
  → RawWaveformRecAlg::execute
  → WaveformReconstructionTool::reconstructPrimary
     用ADC估计baseline，用条件库trigger time/offset确定sample窗口
  → fillRawHitValues
     wave[i] = baseline_mean - mv_per_bit × adc_counts[i]
     time[i] = 2 ns × sample index
  → reconstructHit → Gaussian/CrystalBall fit → integral [mV·ns]
  → PreshowerWaveformHits
  → NtupleDumperAlg::FillWaveBranches
     m_wave_charge[ch] = hit->integral()/50  [pC]
```

这个计算链依赖ADC、基线、通道、时间条件和波形工具；不读取CKF轨迹、ACTS材料、轨迹外推到Preshower的位置、旋转后的theta/phi。两个Ntuple writer完整函数不同（old新增overflow诊断、secondary判定改用等价helper等），但**charge和raw-charge赋值语句逐字相同**，两版secondary逻辑均排除`SECONDARY`标志。坐标旋转修改的`Track_X/Y/Theta*_atPreshower*`是另一组轨迹外推量，不参与这里的积分电荷。

本比较读取同一批已经生成的RDO，没有重新做Geant4或digitization。若重新模拟并错误地只旋转部分探测器，当然可能改变路径长度和ADC；那是另一种实验，本批固定RDO不属于该情形。这里也不能把“理想正交坐标变换不改变物理量”理解为“任意软件版本及数值积分实现都会逐bit一致”。

已有独立控制还支持调用链判断：阶段204的material/seed等tracking控制之间波形数组精确相同；阶段205全量材料图控制的`exact_new_waveforms=true`。所以材料修正虽改善动量，未改变Preshower电荷。没有在本阶段声称完成“仅开关旋转、其他所有源码完全相同”的新全量消融。

## 同一真实事件的具体故障机制

复用阶段204的两段各30事件、old/strict各一遍共120次事件执行；四个目标电荷与历史缓存逐值一致。本阶段没有重复重建这些RDO。

| run 200080事件 | old PS0 | strict PS0 | 已有源码及重放解释 |
|---|---:|---:|---|
| 383 | 4.7842822 pC | −∞ | strict的CB拟合status=0，但`Integral`返回−∞；同一真实参数改用数值积分得到约4.78435 pC |
| 1915 | 4.4452720 pC | −0.00589046 pC | status=48，即GFIT_FAILED+CBFIT_FAILED；负peak −1474.76 mV、width约7.967×10⁻⁵ ns仍流入最终hit；raw为4.6946287 pC |

event383的固定参数积分检查完全不需要几何、轨迹或ADC输入，直接说明**积分API本身就足以产生该异常**。数值积分得到的4.78435 pC与old 4.78428 pC略有不同，是因为这里固定strict拟合参数；这不是把old重新拟合的结果强行说成精确一致。

event1915说明另一条路径：失败后的参数/积分写入问题；不能声称只换积分器必然修复所有负电荷。也不能将全部−∞未经逐例重放都归为同一机理。两类是已确认实例，尚未测量全量各机制独立占比。

全量影响沿用阶段206：140,132个truth-accepted事件中，strict PS0/1分别有308/330个−∞、333/342个有限负电荷，old均为0；正常中位数几乎相同。固定strict tracking，只替换旧PS电荷，merge净恢复1,047个事件；全部电荷替换净恢复1,118个。通道/机制存在重叠，不能直接相加。见[阶段206报告](2026-11-14_stage206_old-strict-properties-inventory.md)、[既有重放验证](stage204_causal/waveform_cache_validation.json)。

## 本阶段执行与验收

执行命令：

```bash
export NU_MU_SKIP_LCG=1 FASER_CALYPSO_RUN=/tmp/xcheng_stage204/runtime
source setup_env.sh
nu_mu_calypso_setup
/usr/bin/time -v -o workbook/stage207_waveform_lineage/resources.txt python AnalysisZipFramework/scripts/audit_tracking_waveform_lineage.py --calypso /eos/home-x/xcheng/FASER/geoRotation_calypso --output workbook/stage207_waveform_lineage --check-integrals
```

该runtime为阶段204已记录的Athena 24.0.41/GCC13冻结构建，不是重编译；实测ROOT版本为6.28/12。审计内部wall为33.08625 s，含Python启动的进程wall为35.18 s，最大RSS为520,340 KiB，exit 0。event383的数值积分为239.21744092873178 mV·ns（4.784348818574635 pC），误差估计1.54785×10⁻⁷ mV·ns；另一个正常PS通道的两种积分相差约1.49×10⁻¹⁰ pC。

本阶段只处理小型源码和单个已保存真实事件的拟合参数，交互运行；不新建批量重建、不复制NPZ或保存xAOD。数值和资源测量见[固定参数结果](stage207_waveform_lineage/fixed_parameters_integrals.json)、[time记录](stage207_waveform_lineage/resources.txt)、[源码审计](stage207_waveform_lineage/source_audit.json)。

验收包括：五文件三种历史对照和当前工作树对照全部通过，更新祖先关系通过，波形/条件目录空差异断言通过，两个电荷赋值语句精确一致；event383两个通道的数值积分与阶段204记录在1e−10相对容差内一致。未测量新的全量效率、ADC逐sample比对或独立波形配置消融。

## 下一阶段计划与验收标准

1. 审阅后再决定是否在strict上仅移植`IntegralOneDim`：输入共同RDO、固定拟合参数与阈值；验收非有限电荷、正常通道偏差、PS cut迁移及CPU，不能把失败拟合一起悄悄改动。
2. 另行审阅Gaussian约束和失败回退：覆盖负积分、普通MIP、overflow及低信号；保留ADC、全部拟合参数和status；验收电荷/时间稳定性、信号效率和背景拒绝，不能只最大化通过数。
3. 若要建立严格“纯旋转”控制，需同一上游波形版本、条件和RDO，仅切换tracking坐标实现；验收PS电荷逐值相同，并将Timing按轨迹Y选择通道的变化单列。当前证据已定位波形基线不一致，不需要用新的大生产来代替源码事实。
