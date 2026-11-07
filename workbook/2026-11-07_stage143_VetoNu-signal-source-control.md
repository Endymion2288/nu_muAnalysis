# Stage143：有信号VetoNu的实际来源与DAQ控制

## 阶段目标、输入与选择

兑现[Stage142下一合同](stage142_energy_ml/next_execution_contract.json)，补上四父控制中VetoNu全无HITS的通道覆盖缺口。仅复用原4032父的train支持，最多两个既有父、累计1000 CPU秒；先做支持审计，再固定原frame顺序前两例，首父实际闭合和成本通过后才准入第二父。无新独立ν、无能量fit/forward、reserved/role4/隔离零预测，不绕过Stage137未通过的双箱5%扩大门。

[冻结协议](stage143_energy_ml/protocol.json)输入为Stage131 `production_cases.json.gz`、`matched_input.npz`，Stage137 `boundary_evidence.json.gz`及Stage142现成observer runtime。支持审计在HTCondor读取原证据，只检查role1、VetoNu all-time沉积是否正，不读取cal/test风险，也不按来源比例选择。原HT纳入概率及角色保留。

## 实测支持及方法

[支持表](stage143_energy_ml/support.tsv)给出全部2304个train父，736个有正VetoNu沉积；这是当前分层父框中的计数，不是自然ν接受率。支持中仍保留K和原重选失败父，没有按失败/耗时删除；原frame排序的前两例恰为charm：

| frame | 原stratum | Eν（GeV） | 原selected参考 | 原all-time VetoNu沉积（MeV） |
|---|---|---:|---|---:|
| 1 | transition | 668.440007022 | 有 | 0.901909621 |
| 5 | highE | 3169.300046573 | 有 | 1.141164654 |

两例不是低能覆盖，不以它们解释或认证50–100 GeV的能量风险。原支持按成分/stratum/原selected状态的完整计数均保留，不泛扫其他库存补“更好”事例。[首父准入](stage143_energy_ml/parent_1_admission.json)先于执行；其164 scheduler CPU秒且全部闭合后，才写[第二父准入](stage143_energy_ml/parent_5_admission.json)，当时含支持审计已用168 CPU秒。

复用Stage142真实SD新hit根标签、按原索引转移到持久化hit的算法，不重新编译observer。只将三个Python驱动的输出目录参数化为`NU_MU_RESPONSE_STAGE`，默认142行为保持；本轮设143，G4 seed、HITS basename、run990131/lumiblock=index+1、private seed规则不变。六探测器HITS总量与旧observer字段检查通过，两父原字段精确。Scint未知根hit为0，但未知类仍保留，不能外推所有父。

## 实际结果与物理解释

[汇总](stage143_energy_ml/summary.json)：两父**16800个实际ADC样本逐值零差，包含84个触底采样**，两父原raw11/status均float32精确。来源模拟加和最大逐采样差0.001373434061 ADC单位，有限窗电荷最大差4.619814899×10⁻⁵ pC，均通过事前`32*float32eps*max(1,total_amplitude)`界。只相加取整/截断前的信号，不相加来源ADC或来源raw。两父完整原private末状态没有保留，明确未测量，不把同seed规则写成完整状态比较。

VetoNu两路每父1200 ADC：frame1有14个非μ根hit、无μ根hit；frame5有1个μ根hit和17个非μ根hit。持久化修正后响应分别0.901910007 MeV，及μ0.038020000/非μ1.103139996 MeV。微小SD与持久化能量差遵循原压缩量化检查。

| frame/通道 | μ根模拟电荷（pC） | 非μ根模拟电荷（pC） | 总模拟电荷（pC） | 实际signed raw（pC） | status |
|---|---:|---:|---:|---:|---:|
| 1/VetoNu5 | 0 | 22.904710492 | 22.904710492 | 23.205502930 | 0 |
| 1/VetoNu4 | 0 | 0 | 0 | −0.074916992 | 1 |
| 5/VetoNu4 | 0.967164676 | 28.026480649 | 28.993645326 | 28.880664063 | 0 |
| 5/VetoNu5 | 0 | 0 | 0 | −0.022675781 | 1 |
| 5/Veto14 | 102.023753620 | 8965.505397044 | 9067.529153927 | 2544.037500000 | 36 |

frame5有信号VetoNu路的非μ模拟份额0.9666421843。两个“零模拟信号”通道都有实际ADC及噪声raw，**不等同于Stage142无HITS、无ADC的默认零**。status1/36等非0不给arrival time；合法负raw保留。Veto触底数frame1/5为7/77，VetoNu均0；全部[ADC表](stage143_energy_ml/ADC_summary.tsv)及[28通道表](stage143_energy_ml/source_charge_summary.tsv)保留。

两父上游VetoNu/下游Veto有非μ响应，Ecal却全部μ根：63.372854927及157.410987741 MeV。这说明实际多层来源可以不同，单层大活动或“整事件其他根比例”不能替代按通道定义的联合响应。这里只认证两个来源控制，不给总体μ辐射尾误报率或ν能量收益。Ecal数值仍只是官方SD修正hit响应，Ecal DAQ在后续Stage144单独控制。

## 命令、资源、验证及存储

```bash
python3 ml/stage143_submit_support.py
python3 ml/stage143_monitor.py
python3 ml/stage143_submit_response.py 1
# 首父原字段/raw/status/ADC/source sum和成本通过后
python3 ml/stage143_submit_response.py 5
python3 ml/stage143_submit_support.py --phase audit
```

使用`~/condor/nu_muAnalysis/stage143/`，support/audit各1 CPU，响应4 CPU/12 GB；父内官方链为串行步骤，不声称用了四倍加速。作业9674246/9674253/9674270/9674304全部exit0、4starts、0失败，[scheduler唯一账](stage143_energy_ml/scheduler_accounting.json)合计**415 CPU秒、552聚合execute wall秒、0GPU**；support/首父/第二父/audit分别4/164/247/0 scheduler CPU秒，audit的0是调度计数粒度，实际stdlib汇总进程0.181261 CPU秒。两父驱动wall192.448100/314.512474秒；GNU父含子进程159.20/242.18 CPU秒是嵌套值，不与scheduler相加。峰GNU RSS1,789,308 KiB。未测GPU加速收益；本实验主要是官方CPU链与I/O。

所有科学提取与汇总在HTCondor；本地只做文本/语法、运输及紧凑证据回读。AST、shell语法、阶段文档链接和`git diff --check`通过。科学验收为原字段、六探测器HITS、原raw11/status、总ADC及事前来源浮点界；没有放宽容差或重训候选。

确认本阶段队列为空后，六份事件文本原2,694,806 B精确合并为ignored `ntuples/energy_ml_stage143/event_records.json.gz`，1,086,863 B；保留原相对路径→原JSON文本的可恢复映射。逐文本与原运输包再次回读一致后删除分散事件文件。源版本胶囊`software/stage143/source_snapshots.tar.gz`为37,619 B；删除已结束的输入/结果运输包44,111,049 B。清理记账脚本曾在删除完成后因`st_size`误写成函数报错，已从未改动的`/tmp`原运输副本及submission记录恢复精确尺寸/文本核对，未重跑物理。[存储记录](stage143_energy_ml/storage_cleanup.json)保留这一操作审计。Stage54五资产、其他项目和运行中的Stage144目录保持。

## 阶段结论与下一步

完成本合同的含信号VetoNu来源/DAQ方法控制；原pz0-only一次方动量、允许px/py/q/p/弯折、raw11/status/typed NaN/signed/Calo缺失、pz>50及其他正式cuts和全部K/角色保持。Stage87 direct62仍参照，无新晋升，原1.05/1.01/1.03及八层三尾+2 pp不变，1.05只非劣效。

下一Stage144已冻结四个Stage142父的缓存Ecal控制：原持久化修正hit、原seed/context、实际Ecal条件/积分窗、总ADC/模拟来源及可得原status，最多600累计CPU秒，先单父成本/闭合再准入其余三父，不做新G4或能量fit。Stage132§5.5进一步需要真实μ控制中包括高活动/截断的联合残差留出验证；只有point状态时明确协方差缺口，data报警比例不能冒充误报率，truth列表中的次级粒子不能直接当独立初始根。乳胶匹配、实际曝光GRL/背景/全生成接受度、相关系统辅助约束及独立生成确认仍需实物输入，整体goal未完成。
