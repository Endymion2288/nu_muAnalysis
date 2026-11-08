# Stage173：原运行读出条件的一次性适用性判定

## 阶段目标、输入与约束

执行用户新Stage172研究报告§4/§10及补充§4/§5的第一步：从实际inclusive/CaloNu专用GRL和有限条件IOV给逐子系统结论，再推进Timing双端联合测量与S0前后μ辐射。不将随机噪声统计设为能量研究的无限前置。基准HEAD为`e973721`，Stage172两份用户研究原文与Stage171历史合同不改写。

[冻结协议](stage173_energy_ml/protocol.json)只读明确两份v10 JSON、两官方页面、两个COOL replica的六个明确folder。pilot取两GRL、run15838 cable及RAW00400首秒HV；过实际完整GNU成本后才其余data条件、53587秒有限HV IOV及MC100012/100049同明确folder。MC100049只是已知控制参考，不冒称原全部队列几何。实际folder缺失、tag/instance不支持、记录缺口或配置快照缺失逐项记录，不换条件/无界追版本。最大64 channel、4096记录/folder。所有科学JSON/COOL解析走HTCondor，未读事件ROOT/NPZ/RAW。

旧未提交的Stage172随机控制草稿6文件已精确归档至`software/stage173/deferred_stage172_draft.tar.gz`并从执行入口移除；它们未提交过作业，当前队列在本轮开始时为空。用户已提交的Stage172文档和资料未改动。原32文件合同是历史候选，不在本阶段执行。

资源预算900累计CPU秒，pilot200/full450/audit250，2核6000MB/max1job/MaxRuntime86400秒，无应用短timeout；pinned d32现成runtime、不重建Calypso。先小pilot，以完整GNU CPU三倍按full16次/pilot2次查询放大，并保留audit250秒，才准入full。该成本门在读新增full结果之前确定，不据结果改预算。HTTP30秒只为有界远端文档请求，不限制数据生产。

Stage87、原1.05/1.01/1.03/八层三尾+2pp与两低箱目标、全部K/原角色/reserved/quarantine、pz0-only一次方动量、raw11/typedNaN/合法signed/status0-only timing/Calo缺失、pz>50GeV及Stage54原资产保持。无fit/forward/G4/新ν，无prior或曝光外推。

## 执行命令

```bash
python3 ml/stage173_freeze.py
python3 ml/stage173_ops.py submit --phase pilot
```

整体需求逐项列于[goal requirements](stage173_energy_ml/goal_requirements.tsv)，尚未完成的实测/条件任务不由本阶段判定代替。

## 实测GRL、通道与条件结果

[pilot摘要](stage173_energy_ml/pilot_summary.json)实际读取v10 physics JSON141894B、physics_calonu JSON73215B。前者run15838存在，稳定秒区间[1720449636,1720503223]、无excluded_list；后者整个run15838键不存在。因此固定四个秒端点的inclusive成员均True，CaloNu专用成员均False。不能把Stage171四严格随机控制称正常CaloNu物理时期。两官方页面原字节也取得并归档；FaserLuminosity明确run15838 CaloNu voltages not nominal、only removed from CaloNu dataset；BadFASERRuns说明设置优化期间数据不佳。本阶段不把网页未给出的坏时间或增益曲线补造出来。

[实际16次查询](stage173_energy_ml/condition_records.json)全部打开成功，无超限/截断；这不表示每个channel都有payload。data replica实际解析到CABP200_261028.db、ALLP200_261030.db，CONDBR3；MC查询为OFLP200/tag05，run100012/100049两组仅作明示控制，完整内容保留。实际run15838 data cable有32键：calo4、calo2 4、calonu4、vetonu2、veto4、trigger4、preshower2、none7、clock1。

| 通道/条件 | 实测结果 | 解释范围 |
|---|---|---|
| 普通Ecal硬件0–3 / 16–19 | cable分别type=calo / calo2，同模块双读出存在 | 支持双路实际接线，未测交叉标定/非线性/能量收益，原四路MC不凭此增加第二路 |
| Timing硬件8/9、10/11 | 同plate0、plate1各一对，PMT分别1/0 | 下一同片双端测量须按目标时期实际map，不猜左右符号 |
| CaloNu硬件20–23 | 实际cable有calonu、两row/两module | 专用GRL排除15838；正常物理校准未认证 |
| 硬件31 | type=clock | Stage171全部硬件可读仍成立，31不解释为普通探测器信号/应扣共同噪声 |
| `/WAVE/DAQ/Range` | 32键range2.0 V | 当前明确条件元数据，不是全部历史producer等价证明 |
| `/WAVE/DAQ/Timing` | 全局NominalTriggerTime200.0 ns | 与原MC820 ns时基不可直接混用 |
| `/WAVE/DAQ/TimingOffset` | 返回24键 | 各键值/IOV原样保留，缺失键不补0 |
| `/WAVE/Calibration/HV` | 固定RAW400首秒20键，整个稳定秒区间各0–19只有1份IOV；20–23/31无记录 | 无记录是库支持缺口，不是实际HV=0或已证明优化未发生 |

[逐通道证据](stage173_energy_ml/regime_evidence.json)记录实际payload、完整IOV及缺口。稳定端点差53587秒；本次IOV以离散秒闭区间转换到半开纳秒[1720449636,1720503224)，覆盖53588个一秒bin。0–19在该查询口径无gap，20–23及31各缺53588秒bin；这不是活时间或曝光。没有取得原DAQ exact config snapshot、CaloNu优化过程的完整历史记录、真实gain/timewalk、高幅独立参考或目标MC/data响应协方差。一次有界判定在此结束，不继续历史构建搜索。

逐子系统结论：CaloNu只作原条件工程描述；普通Ecal、Veto/VetoNu/Timing/Preshower的映射及条件可读，物理校准/迁移仍未知，不由CaloNu排除推导其他子系统坏；clock按实际字段使用。对原wo_caloNu队列，CaloNu控制不认证direct62迁移。没有给RAW/PHYS子集附850.979pb⁻¹整run亮度，也没有接受度/效率比。

## 验证、成本、存储与物理衔接

[独立验证](stage173_energy_ml/independent_validation.json)通过两GRL实际原字节、独立成员算法、两原条件点重查询及全IOV交集检查；未认证物理校准。[静态物理入口](stage173_energy_ml/static_next_physics_evidence.json)记录pinned d32准确源码片段：pz0取首个TrackParameters；fitter/CKF显式启用散射和energyLoss；trigger_time减nominal/offset/digi shift，bcid_time已用clock；Timing两端数字化传播项相反。它们约束下一实验口径，不当作历史全生产或逐事件S0已测证据。

调度pilot9676706.0/full9676710.0/audit9676714.0均exit0，3提交/3start/0live，合46CPU秒/195聚合execute wall秒；2核6000MB在schedd保持。GNU完整进程分别CPU10.13/12.11/11.99秒、wall32.09/34.54/97.43秒，最大RSS591332KiB。pilot三倍16/2投影243.12CPU秒，加已用14及audit250在900预算内才full。审计wall包含实际等待，不把wall当CPU，也未测受控并行/GPU加速比。新ROOT事件/fit/forward/G4/独立ν为0。

[精确归档清理](stage173_energy_ml/storage_cleanup.json)保留官方源胶囊52503B，源45逻辑版本内容唯一23份，删除174044B运输/log/spool重复；未保存事件ROOT/xAOD/数组，无SHA。旧6文件草稿精确归档后退出执行入口，原Stage171合同与用户Stage172全文保留。清理前核队列Iwd无引用、Stage54原12文件size/mtime保持。[文档验证](stage173_energy_ml/document_validation.json)检查AST、bash、冻结phase协议字节、历史入口、链接/围栏和diff。

## 阶段结论与下一步

一次适用条件判定已完成：不能迁移的真实边界比此前明确，且31已识别为clock；未测的真实校准、DAQ配置和曝光继续明确缺失。这不会阻止真正新观测的小pilot，不执行旧32文件噪声计划作为前置。

下一Stage174固定两份已用μ控制data8006/MC100012及已定位data15838 PHYS，先每份前256/schema/实际map/原参考与成本，再原前4096。测同片Timing0/1、2/3的严格差时、相对Veto21的均时及tracker x兼容性，训练/留出按原entry奇偶分开，各源分别校准、不把data offset搬给MC；正电荷仅限制timewalk可识别支持，全部signed raw及无时父保留。先交真实留出残差和支持范围，后续全ν覆盖/固定新表示训练另冻，暂不训练能量。并行研究S0 actual state与已存observer可用量，仅缺关键量时固定自然小pilot补仪器化，不自动重放4032父。需求清单中其余读出干预、backscatter、双量程/高幅、物理背景/效率/加权账目及独立确认仍未完成，整体目标active。

```bash
python3 ml/stage173_ops.py collect --phase pilot
python3 ml/stage173_admit.py
python3 ml/stage173_ops.py submit --phase full
python3 ml/stage173_ops.py collect --phase full
python3 ml/stage173_ops.py submit --phase audit
python3 ml/stage173_ops.py collect --phase audit
python3 ml/stage173_requirements.py
python3 ml/stage173_static_evidence.py
python3 ml/stage173_finalize.py
```
