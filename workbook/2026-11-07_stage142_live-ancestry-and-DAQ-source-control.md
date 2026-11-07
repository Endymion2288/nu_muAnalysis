# Stage142：真实hit谱系到有限DAQ窗的四父来源控制

## 目标与有界范围

执行Stage132§5.4尚缺的实际来源标签方法控制，承接Stage138/141的单例总响应闭合；不绕过Stage137未达到的双低箱5%扩大门，不启动自然ν大生产或新能量候选。先用原train frame50检验新增记录，实测成本/DAQ闭合后才按原协议列定的frame6/2/0扩展，共4个既有父、新独立ν数0、能量fit/forward0、reserved/role4/隔离读取0。

[初始协议](stage142_energy_ml/protocol.json)、[来源控制协议](stage142_energy_ml/source_control_protocol.json)和[三父准入](stage142_energy_ml/pilot_admission.json)分别先于对应执行。四父来自Stage135事前按原stratum/hash顺序的train pilot，不按模型风险、来源比例或成败挑选：

| frame | 成分 | 原stratum | Eν（GeV） | 原selected raw参考 |
|---|---|---|---:|---|
| 50 | π | 50–100 GeV | 90.288000701 | 有，精确闭合 |
| 6 | π | 100–200 GeV | 142.480001718 | 有，精确闭合 |
| 2 | K | high-y | 847.280002631 | 原重选失败，无参考，保留 |
| 0 | K | transition | 280.310000444 | 有，精确闭合 |

两个K父均执行，无应用短超时，不因frame2无selected参考删父或构造假参考。原角色/HT纳入概率/选择、pz0-only一次方动量（允许px/py/q/p/弯折）、raw11/status、合法signed/typed NaN/Calo缺失及最终门保持。只有方法控制，没有把truth来源作为部署输入。

## 仪器化及持久化语义

新`NuMu142::ObserverTool`在每个敏感探测器`ProcessHits`已完成后读取真正新生成的Scint/Ecal hit，记录根类别（μ根及全部后代/其他根/未知）、根ID/PDG、G4 trackID和实际hit字段。逐step检查新增hit基数，不用持久化barcode猜祖先。Ecal直接取官方SD已做Birks/局部非均匀修正的hit响应，不以未修正deposit替代。旧observer所有字段必须精确重复。

[原转换器源码证据](stage142_energy_ml/converter_evidence.json)说明：Scint p1a按原行序压缩/恢复，不删行或重排，hit串共享首hit时间，能量/长度/角度量化单位均10⁻⁵（MeV/mm/rad）。标签按真实live索引转移，并核对持久化的数量、ID和barcode；DAQ计算使用**持久化后的**时间/能量/位置，不把live坐标直接代入实际数字化。未知来源保留独立类。

frame50完整六探测器HITS快照与Stage135逐值相同，全部旧字段精确；Scint 84 hit、Ecal258 hit均为μ根。其Veto live/persistent单hit时间差最大.064983368 ns、位置差3.051758×10⁻⁵ mm，Preshower时间差.051604271 ns；这是压缩语义的实测差异，不放宽原ADC闭合门。四父逐hit能量在预定1.1×10⁻⁵ MeV加float界内，旧字段/六探测器HITS总量验证全过。

沿用真实通道条件、TOF/光传播/CB核、2 ns×20倍采样及780–980 ns含端点101点窗。每个来源只计算噪声/取整/截断之前的模拟信号，保留总信号走原噪声流/ADC链；**不相加分来源ADC**。逐采样模拟加和误差界在执行前固定为`32*float32epsilon*max(1,total_amplitude)`。

## 执行与验证命令

```bash
python3 ml/stage142_submit.py preflight
python3 ml/stage142_submit_control.py
# 上述两步实测闭合后才冻结并执行另外三父
python3 ml/stage142_submit.py pilot
python3 ml/stage142_submit.py audit
python3 ml/stage142_monitor.py
```

HTCondor目录`~/condor/nu_muAnalysis/stage142/`，作业9674197/9674205/9674214/9674228，4 CPU/12 GB；新C++只编译一次，后续复用3,803,113 B无debug runtime，三父并行。原G4 seed、HITS basename、数字化private seed及filename定义的EventID不改。frame50完整初末private状态与原件精确，另三父只认证原producer的seed规则；原完整末状态未保留，明确不声称精确比较。原raw11/status仅对有selected参考的50/6/0要求float32精确；frame2无参考这一项未测量。

## 实际结果与物理含义

[汇总](stage142_energy_ml/summary.json)：**28,800 ADC样本，0差异，包含159个触底采样**；三selected父原raw11/status精确。四父Scint未知来源hit均0，但程序保留未知类，不外推所有自然父均无未知。

| frame | Veto hit数（μ/非μ） | Preshower hit数（μ/非μ） | Ecal响应（μ/非μ，MeV） | Veto触底采样 |
|---|---:|---:|---:|---:|
| 50 | 50 / 0 | 20 / 0 | 61.166574 / 0 | 0 |
| 6 | 356 / 0 | 159 / 0 | 162.915035 / 0 | 12 |
| 2 | 41 / 30892 | 0 / 686 | 0 / 5351.478854 | 142 |
| 0 | 46 / 268 | 34 / 0 | 62.905074 / 0 | 5 |

Ecal数值为官方SD修正后再经持久化量化的响应，不是可守恒的原始能量，也未闭合Ecal硬件DAQ。详细[hit响应](stage142_energy_ml/source_hit_response.tsv)、[ADC表](stage142_energy_ml/ADC_summary.tsv)和[48通道模拟电荷表](stage142_energy_ml/source_charge_summary.tsv)保留实际数值。

四父VetoNu均无HITS/无ADC，保持原raw0/status1默认，**含真实信号的VetoNu响应未测量**，不能称测得零或全通道完备校准。

关键有限窗电荷，单位pC：

| frame/通道 | μ根模拟信号 | 非μ根模拟信号 | 总模拟信号 | 原实际signed raw | status |
|---|---:|---:|---:|---:|---:|
| 6 / Veto14 | 1441.539544 | 0 | 1441.539544 | 1099.780547 | 4 |
| 2 / Veto14 | 82.333412 | 70445.429177 | 70527.761228 | 3865.324063 | 4 |
| 0 / Veto14 | 79.944827 | 354.764084 | 434.708913 | 434.571211 | 0 |
| 0 / Veto6 | 84.476095 | 865.731998 | 950.208093 | 899.003828 | 4 |
| 0 / Preshower12 | 10.015840 | 0 | 10.015840 | 10.148345 | 0 |

frame2“实际raw”来自本轮同原seed/context的真实digitizer重放，原selected ntuple参考不存在，不能声称与原selected分支比较通过。其Veto14模拟信号非μ份额.998832629；frame0相同通道.816095722，但后者Preshower/Ecal全为μ根。frame6完全μ根的Veto也有大电荷和触底，说明**大电荷/大hit数本身不能直接标为强子活动**；四例不是误报率、μ辐射尾总体或可部署区分效率的统计标定，也未按具体辐射过程归因。

来源模拟积分加和最大差.001361557137 pC（frame2），最大逐采样差.032073974842 ADC单位，均过预定相对浮点界；frame0窗最大差8.226681643×10⁻⁶ pC，50/6为0。这里不是声称浮点逐值线性，真实总ADC仍全部精确。clip后raw与模拟电荷差很大不能只解释为噪声，进一步说明需在ADC之前定义来源监督。status4或其他非0波形不给arrival time，仍保留原signed raw。

## 资源、存储和阶段结论

[完整账](stage142_energy_ml/scheduler_accounting.json)：4job/4starts，全部exit0、无失败，668 scheduler CPU秒、526聚合execute wall秒、0GPU，低于原累计3600 CPU秒。build/preflight、首例来源控制、三父pilot、audit分别87/66/514/1 CPU秒；三父实测wall163.091121/229.533401/167.945587秒（并行），不与聚合wall混用。所有GNU记录峰RSS1,817,292 KiB，编译48.95 CPU秒、三父含子任务507.51 CPU秒均为嵌套数，不重复相加。

仅保留无debug runtime、紧凑统计与ignored合并事件证据。12份原event JSON文本回读精确后，24,230,915 B分散文件压为9,035,502 B合并gzip，删除四份重复结果archive12,874,780 B；按[恢复说明](stage142_energy_ml/storage_cleanup.json)可恢复原JSON/gzip路径，无需重跑G4。逐hit/ADC数据不进Git。确认前四阶段队列全空后另删110,988,294 B旧软件运输包；home根`nu_mu_stage*`候选为空，不删除其他项目目录或Stage54资产。AST/shell、阶段链接、`git diff --check`验证后先保存本中文报告再本地Conventional Commit，不push。

本阶段完成四父**来源监督方法控制**，包括两个K父、混合来源和真实截断；一般VetoNu信号、Ecal DAQ、μ辐射联合总体响应/真实data迁移、独立生成确认及新观测能量风险仍未测量。Stage137的局部增量不等于通过5%扩大门，故不自动全队列生产或再训旧X来源代理。Stage87direct62、原全部门和整体goal未完成的状态保持。

下一具体控制输入为`ntuples/energy_ml_stage137/boundary_evidence.json.gz`、原4032 case/角色/纳入概率和当前runtime：先在批处理审计train中有VetoNu HITS/沉积的支持与原状态，最多冻结两个事前按原frame顺序的信号控制，若无可用支持则给实际0计数，不泛扫旧库存。验收为有信号VetoNu的原raw/status或明确缺失参考、总ADC、来源模拟加和、成本；预算上限1000 CPU秒，先成本pilot，不开新能量fit或自然ν大生产。总体μ辐射控制仍需要真实μ状态/穿越位置/covariance与足够尾部支持，外部乳胶/data曝光GRL/背景/全生成接受度和真实相关辅助约束不能用虚构prior补齐。见[下一合同](stage142_energy_ml/next_execution_contract.json)。
