# Stage139：稀疏有限MC轮廓似然的数值诊断

## 阶段目标与输入

落实Stage132§6：从Stage136局部高斯误差走向允许零MC格的非负模板轮廓与覆盖检验。使用Stage119原role2响应、role3参考份额及Stage129冻结traditional/direct62预测；不重新训练或forward，不打开reserved/role4/隔离，不做G4。原事件目标、全部K、pz0-only一次方动量、raw11/status、typed NaN、合法signed、Calo缺失和原选择不改，Stage87direct62仍为参照。

为得到整数辅助MC计数，role2每个精确float64 incoming代理固定取原序第一view，共10811个；七个真E箱计数为182、899、2342、3522、2742、1020、104。真E边界为50/100/200/400/800/1600/3200/∞ GeV。incoming代理不是已认证独立GENIE家族。本轮响应与Stage136家族平均响应不同，不能混用两者数值。

固定selected数据量1000，七个份额自由，关注ψ=f₀+f₁，即selected E<200 GeV份额。traditional9、direct9、联合direct9×pz0四箱，共三种表示。似然为

`logL = Σ d_k log(Σ f_t q_tk) + Σ m_tk log(q_tk)`。

f及每行q均为非负simplex；零MC格可以取得正概率。0.1只初始化q，不进入似然，不是先验。真实系统、背景、接受度约束未输入。

## 冻结实验及实际执行

[pilot协议](stage139_energy_ml/protocol.json)和[正式覆盖协议](stage139_energy_ml/coverage_protocol.json)在对应计算前冻结。pilot三表示各4个nominal toy，仅用于成本与收敛，不以12个toy估计覆盖。原正式实验为三表示×两个场景×500 toy，共3000个，LR阈值3.841458820694124；固定seed为202611071390（nominal）及加100（stress）。每个toy先抽七行辅助MC，再抽1000个数据事例。500 toy在95%附近的MC标准误约0.009747。

stress逐真箱把min(0.05,3/n_t)质量均分给原空格，仅为人为categorical敏感性；不是实测探测器/物理变体或置信集，三表示的stress不是同一物理shift。只检验冻结ψ点的参数模型覆盖，不认证uniform或真实data覆盖。

实际执行命令：

```bash
python3 ml/stage139_submit.py
python3 ml/stage139_submit_coverage.py
python3 ml/stage139_submit_repair.py
```

修复提交有一次明确失败后重提，记录分别保留；第二次修复仅更正梯度数组dtype。科学计算全部在HTCondor，LCG_109、4 CPU、单线程BLAS，提交目录`~/condor/nu_muAnalysis/stage139/`。最终产物在`workbook/stage139_energy_ml/`，模板计数和完整运输记录在ignored `ntuples/energy_ml_stage139/`。

## 数值结果与故障原因

pilot 12个toy均达到原EM停止条件，最高1974次迭代；三个Asimov与已知最大似然差绝对值≤4.784×10⁻⁷。科学部分1.371408068 CPU秒、1.407700494 wall秒。这不足以保证稀疏边界全toy优化可靠。

正式EM-only计算在direct stress toy150失败：自由logL=−9509.54864510044，受限logL=−9509.50756445241。自由模型包含受限模型，前者低0.041080648违反包含关系；nominal direct/joint两个EM初值的最大LL差另为0.2224848/2.569293。乘法EM可能把份额压到零后不能复活，仅用LL增量停止并不能认证最大值。失败不是物理负LR，也不能删掉该toy。

原程序已输出四个500-toy组，但**全部仅作程序诊断、不得用于最终覆盖结论或表示比较**。诊断计数为traditional nominal482/500、stress484/500、direct nominal476/500、joint nominal467/500；其余两组未完整输出。没有据此改bin、prior、种子或删toy。[无效声明](stage139_energy_ml/coverage_attempt0_invalid.json)明确要求原3000个全部完成修复计算。

使用解析梯度SLSQP约束优化，并总从最佳受限解重启自由解，允许恢复EM失去的simplex面。MC>0格使用10⁻¹⁴纯数值下界，不给零MC格加统计伪计数。五个事前诊断case取两个nominal表示各自初值差最大的两例及已失败的stress150；[详细表](stage139_energy_ml/optimizer_repair.json)：

| 表示/场景/toy | 原EM LR | 修复LR | 自由LL改善 |
|---|---:|---:|---:|
| direct nominal 114 | 0.083359186181 | 0.083359183955 | 6.253886×10⁻⁷ |
| direct nominal 417 | 0.095996569966 | 0.095996565957 | 3.181933×10⁻⁶ |
| joint nominal 487 | 0.405092616853 | 0.405092632209 | 5.120837×10⁻⁷ |
| joint nominal 344 | 0.151495002327 | 0.151494963131 | 2.813176×10⁻⁷ |
| direct stress 150 | −0.082161296061 | 0.219830839978 | 0.150997199631 |

五例修复科学CPU11.290696308秒、wall11.381137775秒；已知失败被数值修复，但不等于全部3000例已认证，也不是理论全局最优证明。另一次修复job因整数counts继承到numpy浮点除法输出而失败，已显式转float；无科学结果，成本保留。

## 成本、验证及存储

[完整scheduler账](stage139_energy_ml/scheduler_accounting.json)：4作业/4 starts，2失败全部计入，共1448 CPU秒、564聚合execute wall秒、0 GPU，未超原3000 CPU秒正式预算。pilot/coverage/失败repair/成功repair分别2/1430/3/13 CPU秒、7/531/7/19 wall秒。已保存GNU计时中的峰值RSS最大111904 KiB；失败repair独立GNU记录未保存，故全尝试RSS峰值未测量，不把已保存最大值当完整峰值。嵌套科学CPU不再加到scheduler总数。三模板均保持10811个incoming代理；Asimov最大值和已知失败复现检查通过。

四份重复提交manifest原121576 B，压缩为5779 B紧凑记录加5795 B共享gzip；完整原字典逐字段回读验证，未删除模型、计数或toy记录。job包只作运输，后续仅在队列无引用时清理。没有扫描/删除其他项目目录，Stage54资产不动。AST语法检查、shell语法和`git diff --check`随提交验证；不在本地做数组或拟合计算。

## 结论与下一步

本阶段确认：原EM停止条件不足以支持稀疏有限MC覆盖认证；解析梯度和受限解自由重启修复了已知失败。**最终覆盖、全toy数值可靠性、真实nuisance后精度均未测量完成**。Stage136局部结果保持，但本轮partial不提供新覆盖结论，更不晋升单事例模型。

Stage140保持原似然、全部输入/种子/抽样顺序/3000 toy及LR阈值，先以固定18例（3表示×2场景×index0/150/487）测EM100步warmstart+双初值SLSQP成本，再冻结完整批量资源。验收需完整3000例，无失败删例，约束可行、自由LL≥受限LL、已知case一致、点覆盖Wilson区间及Asimov轮廓、独立数值复核和全尝试成本。18例成本pilot作业9674130现已exit0：科学CPU121.617043735秒，已知失败LR=0.219830842008，与长EM+梯度修复差2.03×10⁻⁹；该成本只供Stage140冻结资源，不充当正式覆盖。Stage137边界机制继续，analog来源与μ辐射联合控制、真实系统/背景/接受度、乳胶锚点及独立确认仍未完成，整体目标保持active。
