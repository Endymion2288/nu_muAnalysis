# Stage146：μ 初始根身份回接与固定响应尾部

## 阶段目标与输入

按[事前合同](stage146_energy_ml/protocol.json)推进 Stage132 §5.5：检查 Stage145 nominal100 GeV μ MC 的尾部报警是否属于实际 μ 初始根，避免把后代 e/γ 当作其他根污染。仅使用原已知 MC100012 的一个 HITS 文件和对应 PHYS 控制，不扩大库存、选择或样本范围。

输入 HITS：`/eos/experiment/faser/sim/mc24/particle_gun/100012/sim/s0012/FaserMC-MC24_PG_muon_fasernu_100GeV-100012-00000-s0012-HITS.root`。

输入 PHYS：`/eos/experiment/faser/sim/mc24/particle_gun/100012/phy/s0012-r0023/FaserMC-MC24_PG_muon_fasernu_100GeV-100012-00000-00004-s0012-r0023-PHYS.root`。

固定应用 [Stage145 参数](stage145_energy_ml/models.json)，没有重新拟合均值、协方差、阈值或高活动定义。仍为原前4096条、单 long track、50<pz0<2000 GeV、≥7层、非负χ²、ndof>0、χ²/ndof<10；entry%4=3留出。正式ν选择没有变更。

## 方法、实际接口与计算准入

复用 pinned d32 Calypso/PyAthena，只读取 `McEventInfo` 和 `TruthEvent`，不加载几何、重新输运或数字化。对每个保留 HepMC 图逐粒子读取实际 production vertex 的 incoming parents，以 Kahn 拓扑消解检查缺失父链接、重复粒子 ID、环／受环阻塞节点，再判定所有无父根的 PDG。图内 `id()` 只作局部标识，**不假定它是 ATLAS barcode，不按 barcode 大小推祖先**。

HITS 与 PHYS 要求 run/event 唯一，并且每个根的 PDG、三动量及生产顶点 xyz 在 float32 精度逐值相等；多重或不匹配身份保留 unknown。HepMC 单位枚举实测记录为0/0，不把枚举整数当单位换算；本次根动量／位置按 PHYS 已有 MeV/mm 数值约定逐值核对。HepMC 顶点第四分量未作为 ns 使用。first-record 的完整数值例见[原生摘要](stage146_energy_ml/full_native.json)。这证明的是**实际保留 truth 图的 μ 根连通**，不认证未持久化的完整 G4 次级历史或具体辐射过程。

64条 pilot 全通过，实测74 scheduler CPU秒、原生主逻辑64.778033 CPU秒、ROOT读取2,171,248 B。pilot 未独立记录逐事件成本，不能将含初始化的总CPU直接线性外推。后续同一有界作业先在64条内测量首事件后63个间隔 CPU，再以 factor3 投影余下4032条，只有落入191 process CPU秒上限才继续；另留35 CPU秒给环境和评分，并保留300累计scheduler CPU秒限制，无应用短超时。见[准入记录](stage146_energy_ml/full_admission.json)。

实测63间隔0.114586960 CPU秒，投影总process CPU66.311145秒，通过191秒门；最终实际读取完整4096条。原生主逻辑50.989161 CPU秒／71.731606 wall秒，图算法嵌套36.144743 CPU秒／37.886344 wall秒；ROOT读取7,619,474 B，峰RSS1,511,848 KiB。pilot进程含冷初始化开销，不能据此声称后续吞吐改善来自代码优化。最终4096父不是新增独立ν，不把pilot与其重叠64条相加。

## 实测身份、祖先与固定评分验证

[汇总](stage146_energy_ml/summary.json)显示：

| 项目 | 实测 |
|---|---:|
| HITS／PHYS原分母 | 各4096事件 |
| 唯一run/event且根动量／顶点匹配 | 4096/4096 |
| 保留truth粒子 | 172248个 |
| μ−根／μ+根 | 2033／2063个 |
| 缺失父边／重复粒子ID／环或阻塞节点 | 0／0／0 |
| 原控制选中／已匹配μ根选中 | 3612／3612事件 |
| 选中且truth列表含非μ粒子 | 3512事件 |
| 未匹配或祖先未知 | 0事件 |

因此 Stage145 “整个truth列表全μ只有100例”不等于只有100个纯μ初始根。剩余3512个选中事件虽有非μ truth 粒子，实际保留图仍连到μ根。不能把这些父当其他初始根污染删除。

原两种固定评分、四分组各五项整数检查全部精确复现，共40项：原留出数、可评分数、报警数、缺失和超point范围数。没有使用 Stage145 的训练函数。PHYS raw提取读取1,715,060 B，额外身份读取1,315,588 B。完整原分母与unknown行见[24行结果](stage146_energy_ml/heldout_by_root.tsv)。下表全为已匹配μ根控制，百分数区间为Wilson95：

| 分组 | 原留出／可评分 | Q15报警 | Qshape30报警 |
|---|---:|---:|---:|
| all | 897／878 | 26/878=2.96128% [2.02874,4.30363] | 25/878=2.84738% [1.93599,4.16959] |
| overflow | 17／16 | 10/16=62.5% [38.6410,81.5188] | 11/16=68.75% [44.4044,85.8354] |
| high activity | 6／6 | 6/6=100% [60.9666,100] | 6/6=100% [60.9666,100] |
| 重建pz50–100 GeV | 766／759 | 22/759=2.89855% [1.92183,4.34965] | 21/759=2.76680% [1.81667,4.19264] |

all未评分15缺失、4超point范围；overflow未评分1个超范围；pz50–100未评分5缺失、2超范围。全部保留分母。两个分组有重叠，不相加事件数。

## 物理结论与局限

**本源中的 overflow／高活动报警发生在已核 μ 初始根控制中，不能解释成其他初始根混入。** 这使“高联合残差就需要强子根”的解释在当前固定评分上不成立。现在可以将这些数称为本PG源、当前选择下的μ根控制经验报警比例；不认证总体FPR、data纯度、独立生产外推或条件尾部覆盖。低全体报警比例并不能保护强活动μ尾部。

尚未确定具体机制：辐射过程、波形截断、point均值模型、重建轨迹匹配／状态偏差都未因果区分。本阶段无真实track covariance、PRD不确定度和匹配生产条件认证；保留图不含所有未记录后代。不能仅因6例高活动就关闭全部联合观测分支，也不通过改阈值或网络扫描掩盖尾部。

## 执行、资源与存储

```bash
python3 ml/stage146_submit.py pilot
python3 ml/stage143_monitor.py --stage 146
# 写入实测准入后
python3 ml/stage146_submit.py full
python3 ml/stage143_monitor.py --stage 146
python3 ml/stage146_submit.py score
python3 ml/stage143_monitor.py --stage 146
python3 ml/stage146_finalize.py
```

3jobs／3starts：9674461、9674468、9674479，全部exit0。累计 **145 scheduler CPU秒／207 aggregate execute wall秒／0 GPU**，低于300秒预算。描述请求1 CPU／4 GB，站点实际将RequestCpus／内存提升为2／6 GB；算法及BLAS仍单线程，本次单文件图遍历和小矩阵不需GPU。原生pilot GNU峰RSS1,586,156 KiB为本阶段最大；评分主逻辑12.156129 CPU秒／13.251382 wall秒，GNU峰RSS114360 KiB。嵌套计时不与scheduler再相加。

提交目录为 `~/condor/nu_muAnalysis/stage146/`，无home根提交目录。核3任务终态后，三份事件文本精确合并为 `ntuples/energy_ml_stage146/event_records.json.gz`，400922 B；顶层原路径→原JSON文本字符串，gzip原件可无损恢复。源码版本胶囊 `software/stage146/source_snapshots.tar.gz` 为10797 B；删除1,112,193 B重复运输及分散事件副本，未删除原HITS／PHYS。见[存储审计](stage146_energy_ml/storage_cleanup.json)。代码语法、shell语法及diff空白检查通过，无新G4、能量fit、响应fit或reserved forward。

## 下一步与整体状态

[Stage147合同](stage146_energy_ml/next_execution_contract.json)继续同一PHYS原4096条，先64条schema／向量对齐，再只诊断缓存评分：检查选中轨迹的 `t_pdg/t_barcode/t_truthHitRatio`、实际根身份及pz0相对匹配truth pz偏差，交付原分组计数／Wilson和尾部见证表。t字段只是记录的ntuple truth matching，不冒充原生PRD／协方差认证；不变模型、阈值或正式选择。预算60累计CPU秒，无新输运／拟合。验收包括身份、选择、原报警分母精确复现及unknown保留，阴性照报，不按结果补样本。

Stage132 §5.5仍仅部分完成；§5.4一般Ecal混合／截断和总体响应、真实空间／covariance及当前producer/data关联、乳胶、曝光GRL／背景／全生成接受度、相关系统辅助约束和独立生成确认仍缺，未交付部分保持“未测量”。Stage87 direct62、原1.05/1.01/1.03和八层三尾+2 pp、Stage137双低箱5%扩大门保持；pz0-only、允许px/py/q/p/弯折、raw11、typed NaN／合法signed、非0 status无timing、全部K／角色与reserved关闭不变。整体目标未完成。
