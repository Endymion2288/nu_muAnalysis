# Stage192：未用IFT候选的真实主μ沉积链接控制

日期：2026-11-08。沿[电子观测路线A](2026-11-08_stage187_electronic-only-observables-research.md)，本阶段把Stage188的“与fit共享barcode贡献”进一步区分为**实际TruthEvent中唯一主μ的直接正权沉积**、次级/其他贡献及未知。全部使用原160父、原surface预测与候选，不做新运输/重建/G4或能量fit。该控制解释条件残差的关联混合，不能认证真实data正确关联率、无条件误差覆盖或低能收益。整体目标未完成。

## 目标、输入与冻结定义

[协议](stage192_energy_ml/protocol.json)在新链接输出前冻结，固定MC100012前64与原π/K/charm各32train，pilot各前4共16，full160；保留原未匹配μ父与全部缺面，不替换父。输入REC/PHYS路径和逐父entry见协议，精确复用 `ntuples/energy_ml_stage188/full_native.json.gz`，不从truth择选最小残差或nearest hit。全部K、原角色/quarantine/reserved、pz0-only、signed raw/typed NaN/status0及Stage87/原八层三尾门保持。

C++小bridge读取StoreGate实际 `TruthEvent` 和 `SCT_SDO_Map`。只有恰1个GenEvent才寻找主μ：来自status4 νμ的直接status1同符号μ；无ν的gun为唯一无入边生产顶点status1 μ。多个或缺失保持歧义。每个候选的全部strip读取原SDO deposit，存barcode、event index、collection char、原weight、实际HepMC指针是否有效/属于选中GenEvent/就是唯一主μ、linked PDG与barcode；不保存内存地址。同barcode本身不足以证明同一粒子指针。

四类固定为：所有正stored-weight贡献均来自唯一主μ且所有strip有SDO，称纯直接主μ；有主μ和其他已解析正贡献，称混合直接主μ；全部正贡献已解析且没有直接主μ，称已解析无直接主μ；非唯一主μ、任一strip无SDO、无正贡献或正贡献无效/外来指针，则未知。stored weight单位/阈值响应未标定，不当作模拟dE/dx测量。每候选无权barcode集合与Stage188原缓存逐值核对。

残差/pull汇总只在原leading精确匹配、起始面支持、成功运输且几何界内的原候选上进行。候选彼此相关，候选N不是独立粒子N。直接主μ的truth条件筛选也会改变分布；abs(pull)≤1/3计数仅是本条件样本描述，不当作68%/99.7%无条件覆盖。无直接主μ可包含真实次级或δ射线，未知可有无SDO响应；均不能自动称fake hit或电子噪声。

## pilot、成本准入与完整支持

pilot16主μ图及全部候选贡献检查通过，比较2767个候选；内部50.182711723 CPU秒/82.203654398 wall秒，ROOT请求读取17415157 B、峰RSS1562600 KiB。完整pilot+编译GNU 61.740000 CPU秒、slowest后续event 0.209384544 CPU秒。冻结三倍公式投影285.724581120<600 CPU秒、总预算与RSS均通过才提交full160；没有扩大1200 CPU秒预算（pilot400/full600/audit200）。

| 来源 | 原父N | 唯一主μ图N | 原匹配且起始面支持N | 原pz0 50–100GeV父N | 其中匹配支持N | fit贡献中有主μbarcode父N |
|---|---:|---:|---:|---:|---:|---:|
| MC100012 | 64 | 64 | 19 | 57 | 17 | 61 |
| pi_0 | 32 | 32 | 32 | 3 | 3 | 31 |
| k_48 | 32 | 32 | 32 | 2 | 2 | 32 |
| charm_113 | 32 | 32 | 32 | 2 | 2 | 30 |

最后一列只是原fit贡献的barcode成员诊断，不认证fit一定属于主μ；同样不能用它筛掉父。μ控制原100GeV gun并非真实低能ν覆盖。

## 固定条件下的残差与pull

pull为无量纲，residual为真实测量轴上的mm；不将单轴strip伪造为二维命中，不改变Stage188材料/场/covariance。

| 来源 | 固定类别 | 候选N | pull RMS | pull中位 | abs(pull)95% | abs(pull)≤1数 | abs(pull)≤3数 | residual RMS/mm |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| MC100012 | 纯直接主μ | 102 | 1.59598235 | 0.187617654 | 3.56384719 | 65 | 90 | 1.62686533 |
| MC100012 | 混合直接主μ | 0 | 未测量/无支持 | 未测量/无支持 | 未测量/无支持 | 0 | 0 | 未测量/无支持 |
| MC100012 | 已解析但无直接主μ | 12 | 45.1181544 | -29.3769761 | 77.4186633 | 0 | 0 | 17.403081 |
| MC100012 | 未知 | 121 | 57.7073387 | 8.78684505 | 103.387481 | 2 | 10 | 17.2548161 |
| pi_0 | 纯直接主μ | 139 | 1.10498685 | -0.152401205 | 2.11375833 | 85 | 137 | 0.130270489 |
| pi_0 | 混合直接主μ | 5 | 1.5888807 | 0.540113221 | 2.589833 | 3 | 5 | 0.136026051 |
| pi_0 | 已解析但无直接主μ | 333 | 166.558688 | -6.33112389 | 364.590553 | 2 | 4 | 15.5463411 |
| pi_0 | 未知 | 669 | 185.850801 | 65.8639991 | 402.63479 | 9 | 24 | 19.317888 |
| k_48 | 纯直接主μ | 169 | 1.12849124 | 0.337562354 | 2.09340128 | 100 | 167 | 0.142151285 |
| k_48 | 混合直接主μ | 6 | 0.441224768 | 0.264267184 | 0.709200307 | 6 | 6 | 0.0631425379 |
| k_48 | 已解析但无直接主μ | 846 | 208.674699 | -3.40885842 | 441.169691 | 0 | 7 | 19.698761 |
| k_48 | 未知 | 977 | 210.913452 | 30.246091 | 443.938469 | 9 | 19 | 21.8387245 |
| charm_113 | 纯直接主μ | 149 | 17.6600277 | -0.211878844 | 4.02277273 | 82 | 135 | 2.05434645 |
| charm_113 | 混合直接主μ | 20 | 19.7786575 | 0.140511382 | 7.43654042 | 14 | 18 | 2.48780732 |
| charm_113 | 已解析但无直接主μ | 945 | 155.448045 | -9.34380533 | 329.639948 | 10 | 40 | 18.6982729 |
| charm_113 | 未知 | 910 | 152.069044 | -12.5385074 | 310.239716 | 15 | 28 | 18.572753 |

π/K纯直接主μ的pull RMS约1.10/1.13；charm纯直接主μ仍为17.660027730、abs95=4.022772733，不能把全部宽尾归因于无直接主μ或未知候选。charm原fit贡献有主μbarcode为30/32，单凭该计数不能证明宽尾来自那两父；μ控制RMS1.595982347亦不认证覆盖。必须保留所有父核查拟合关联、主μ沉积与残差的共同分母，而非丢掉大残差或只报接近1的组。

未知原因按固定解释性flag记录，允许重叠，不形成新的候选类或训练特征：

- MC100012：{'some_strip_SDO_absent': 121, 'no_positive_stored_deposit': 114, 'known_primary_positive_also_present': 5}；invalid deposit=0，foreign pointer deposit=0。
- pi_0：{'some_strip_SDO_absent': 669, 'no_positive_stored_deposit': 560, 'known_primary_positive_also_present': 11}；invalid deposit=0，foreign pointer deposit=0。
- k_48：{'some_strip_SDO_absent': 977, 'known_primary_positive_also_present': 12, 'no_positive_stored_deposit': 777}；invalid deposit=0，foreign pointer deposit=0。
- charm_113：{'some_strip_SDO_absent': 910, 'no_positive_stored_deposit': 738, 'known_primary_positive_also_present': 12}；invalid deposit=0，foreign pointer deposit=0。

flag `known_primary_positive_also_present` 表示未知候选里也可能同时有已知主μ贡献，不能将未知等同非主μ。这些条件结果支持区分“主μ直接沉积一致性”和“全候选混合”，但不能由MC条件宽度推出真实data纯度、错误率、动量尺度或Eν修正；Stage190的真实data没有这些truth标签。

## 验证、资源与存储

独立原身份/原cached contributor、实际链接flag/PDG/barcode一致性检查通过，总11497个full候选比较，11806条pilot/full deposit flag检查；原16 pilot/full链接payload逐值相同。审计为独立身份/结构/标量闭合，分类统计复用同函数，不声称第二套HepMC指针解析或独立实验确认。[审计](stage192_energy_ml/independent_validation.json)、[完整分组标量](stage192_energy_ml/full_prediction_summary.json)保留。

full内部84.186712124 CPU秒/139.366789720 wall秒、ROOT请求读取27244390 B、峰RSS1573832 KiB。任务每份申请4核/12 GB，最多1个stage job；实际主要是单event StoreGate读取，未测量4核相对单核加速，不使用GPU。调度4 starts/177 CPU秒/297聚合wall秒、失败0、0live。GNU嵌套进程不重复加进scheduler总量；详细见[进程资源](stage192_energy_ml/process_resources.json)。

命令：`python3 ml/stage192_freeze.py`，`python3 ml/stage192_ops.py submit/collect --phase pilot/review/full/audit`，`python3 ml/stage188_finalize.py 192`，`python3 ml/stage192_document.py`。科学读取/统计全部HTCondor，提交目录 `~/condor/nu_muAnalysis/stage192/`；本地只源码/标量渲染、调度、原字节归档。cache `ntuples/energy_ml_stage192/` 留462426 B<16MiB，精确源码/日志/标量历史/spool在 `software/stage192/`，删除6936027 B重复运输；Stage54原12项size/mtime不变，无新ROOT/xAOD持久化。

## 阶段结论与下一步

本阶段固定真链接控制结束，不以truth标签部署、扫候选窗口或重选父。结合Stage191的原完整队列能量对照判断IFT固定内容包；条件pull接近1也不替代双低能验收或真实误差覆盖。

下一Stage193在新300 CPU秒有界缓存诊断中固定同160父，零native重读/运输/G4/fit，逐父关联直接主μ候选pull平方和及原fit主μbarcode贡献。全部父/来源和未知保留，先核原16pilot再全160与独立标量验证；验收是账目闭合、查清大平方和属于何种fit贡献支持，而非选残差cut证明覆盖。仅作事后机制诊断，不重开Stage191或扩大192预算。

下一B方向观测仍需原时期LOS的单位/符号/参考平面与实际active/badstrip条件。现有GenieEventInfoAlg只复制gFaser字段、MC FaserEventInfo头未给完整LOS约定；ShiftLOS实际execute调用横向boost与vertex平移，不能把其未调用的rotate函数或默认参数当原输入证据。现有条件summary只读NoisyStrips，不能认证完整DAQ active mask。需要实际producer/beam条件与原native几何/strip支持后，另冻一个少量signed矩和同条件打乱轴的新能量对照；未获得输入不补造束轴/holes。D/E/F及物理谱分别仍需同设置真实转换/overlay/testbeam、匹配四像素平面和ν/MC覆盖、真实status0多pulse与对应模拟、背景效率生成权重/相关辅助误差和独立确认。收益、真实覆盖和当前未支持输入均明确为未测量；整体目标不标完成。
