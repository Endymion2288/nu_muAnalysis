# Stage174：Timing同片双端的真实μ校准与联合支持

## 阶段目标、输入与冻结

承接Stage173提交`81e9b2f`和用户Stage172补充§4.1/§5.2，检验同一Timing闪烁体的双端差时/有效位置和相对prompt均时是否可校准。该观测不同于Stage129已训练Veto四pair；不重新包装Q89/T78，不凭论文分辨率判达标。

[冻结协议](stage174_energy_ml/protocol.json)固定三份已知来源：data8006 r0021、MC100012 s0012-r0023、data15838 r0022，字面路径见协议；先每份原前256，再完整GNU成本门，才原前4096。三份分别校准，不移植data offset给MC，不换源。先在pinned d32 runtime读各源实际CableMapping，再在LCG_109/Uproot仅读明确nt分支，3进程/4核8000MB/max1job/1200累计CPU秒（pilot250/full650/audit300），MaxRuntime86400秒，无应用短timeout，不重建Calypso。

μ控制保留所有输入分母及rawQ；选择单long track、最高pz0在50–2000GeV、≥7layers、chi2/ndof<10；实际X/Y_atTrig有限且abs<1000mm、角度abs<1rad排除999999占位。只用pz0一次方动量，不用p0/p1/pz1或比值。Timing0/1、2/3须实际cable同plate不同PMT，并与原ntuple随机电荷hist title的物理通道对应，不猜左右方向。Veto21只作相对均时prompt参考。

时间/时间位置只在所需端原status精确0、localtime有限正值时存在；timewalk还需正rawQ，负rawQ与无时父保留。时间定义是local采集坐标；不再减clockPhase，不把bcidtime/triggertime默认或-1占位当时间输入。data/MC路径按冻结1598.9mm和已有producer约定诊断，实际轨迹/材料/跨时期时钟误差不因此认证。

差时固定设计`[1,x/100,1/sqrt(qL),1/sqrt(qR)]`；相对均时固定`[1,1/sqrt(qL),1/sqrt(qR),1/sqrt(qRef)]`。原entry偶数校准、奇数留出，条件于同文件，不称独立run确认。门：train/validation均≥100、rank4、condition<1e6、训练x SD≥10mm；差时留出abs95≤2ns且有效位置abs95≤100mm，均时abs95≤2ns。只在训练x/y/Q范围内支持后续应用，不向弱信号外推。上述门为有限支持验收，不替代能量原完整门。

Stage87、pz0/raw11/typedNaN/合法signed/status0-only timing/Calo缺失、pz>50GeV、原角色/全部K/reserved/quarantine及Stage54保持。无ν真能量、无能量fit/forward/G4或新ν。先交支持和校准，不提前假定全ν可用或晋升模型。

## 执行命令

```bash
python3 ml/stage174_freeze.py
python3 ml/stage174_ops.py submit --phase pilot
```

## 实测结果

三份源每份原前4096例，合计12288输入；没有用ν能量挑选控制。实际CableMapping及PHYS histogram title均确认硬件8/9对应Timing0/1同plate、10/11对应Timing2/3同plate，每对PMT不同。两真实来源与MC均逐源独立校准；原Stage129控制run/event及Veto21观测精确一致，三源pilot前缀全部精确保持。

| 来源 | 原输入 | μ控制 | strict端0/1/2/3/参考 | ROOT读取B | CPU秒 | wall秒 |
|---|---:|---:|---|---:|---:|---:|
| data8006 | 4096 | 2998 | 2023/2027/1420/1415/2849 | 1176019 | 9.0968 | 10.0413 |
| MC100012 | 4096 | 3611 | 1761/1764/2054/2059/3573 | 755603 | 10.6979 | 11.4772 |
| data15838 | 4096 | 2587 | 1589/1590/1483/1501/2387 | 1197843 | 0.9664 | 1.9207 |

下表Δ为双端差时，M为相对Veto21的均时；位置误差仅Δ定义。所有值来自冻结模型奇数entry留出，不删大残差。门判定是本实验的有限条件门，不是独立运行期迁移认证，也不是ν能量门。

| 来源 | pair | 量 | train/valid | RMSE ns | abs95 ns | 有效位置abs95 mm | 通过 |
|---|---|---|---:|---:|---:|---:|---|
| data8006 | 0/1 | Δ | 985/1018 | 1.999532 | 2.125391 | 163.022 | 否 |
| data8006 | 0/1 | M | 935/953 | 4.661895 | 1.811471 | 不适用 | 是 |
| data8006 | 2/3 | Δ | 683/710 | 1.778002 | 2.282651 | 180.845 | 否 |
| data8006 | 2/3 | M | 640/661 | 1.086386 | 1.617080 | 不适用 | 是 |
| MC100012 | 0/1 | Δ | 870/888 | 0.694329 | 0.423412 | 31.481 | 是 |
| MC100012 | 0/1 | M | 851/878 | 0.641354 | 0.174394 | 不适用 | 是 |
| MC100012 | 2/3 | Δ | 1048/1005 | 0.281486 | 0.186556 | 12.783 | 是 |
| MC100012 | 2/3 | M | 1034/993 | 0.245393 | 0.168682 | 不适用 | 是 |
| data15838 | 0/1 | Δ | 768/785 | 3.969418 | 2.636573 | 219.930 | 否 |
| data15838 | 0/1 | M | 698/711 | 4.374557 | 1.431721 | 不适用 | 是 |
| data15838 | 2/3 | Δ | 701/758 | 2.118721 | 3.140225 | 311.102 | 否 |
| data15838 | 2/3 | M | 644/674 | 4.258487 | 3.561739 | 不适用 | 否 |

12项均rank4、condition小于1e6，训练x SD为50.24–71.99mm；不存在仅因设计退化而误报物理失败的行。完整系数、训练Q/x/y范围、差时符号和有效传播速度保留于[校准表](stage174_energy_ml/calibrations.json)。速度是拟合参数诊断，不能据此声称真实shower位置。

**真实数据两片的差时/位置均未通过预定门，MC两片均通过；不能把MC约13–31mm的留出有效位置精度当作真实数据精度。** data8006两片相对均时及data15838第一片通过abs95≤2ns，但数项RMSE明显大于abs95，说明尾部影响不能忽略。尚未分辨大残差来自非prompt/附加活动、时钟/重建还是控制选择；这些原因均为未知，不删离群事件、不调门或更换拟合族。下一小型覆盖实验同时给固定尾部诊断，不因少数异常终止全部均时研究。真实跨run迁移、弱信号与ν多沉积闭合均未认证。

三源本次rawQ负值和-999占位计数均0；这只描述有限控制，不是把全队列负Q改0。bcidtime/triggertime和clockPhase只保留诊断，未作为特征；非0status不产生差时、均时或有效位置。所有输入与未通过/缺时事件仍在分母。

## 验证、资源与存储

[独立验证](stage174_energy_ml/independent_validation.json)：三源实际重读原前4例、全部数组精确；12项留出残差逐行标量重建，最大RMSE/abs95差8.88e-16ns。它验证实现，不认证物理迁移。

调度3 start，全部exit0、0live；累计78.0CPU秒、108.0聚合execute wall秒。请求4CPU/8000MB，站点实际RequestCpus=[4]、RequestMemory=[12000]MB；实际资源以调度账为准。冻结预算1200CPU秒，无应用短timeout。

| GNU任务 | CPU秒 | wall秒 | maxRSS KiB |
|---|---:|---:|---:|
| audit_time | 36.33 | 40.36 | 101396 |
| full_time | 22.43 | 15.5 | 79852 |
| mapping_time | 9.74 | 24.96 | 539524 |
| pilot_time | 5.01 | 6.16 | 70420 |

[存储账](stage174_energy_ml/storage_cleanup.json)在队列Iwd核对无引用后完成原字节归档与重读：源码52个逻辑版本/26个独立内容；删除4809194B重复运输、日志、提交文件和已验证prefix。保留3份完整控制数组1258607B，路径`ntuples/energy_ml_stage174/full_0.npz`至`full_2.npz`；软件/执行/终态提交审计在`software/stage174/*.tar.gz`。Stage54原12项大小/mtime保持。能量fit/forward/G4/新独立ν/GPU作业均0；这一小规模线性控制不需要GPU。

完整执行命令：

```bash
python3 ml/stage174_ops.py collect --phase pilot
python3 ml/stage174_admit.py
python3 ml/stage174_ops.py submit --phase full
python3 ml/stage174_ops.py collect --phase full
python3 ml/stage174_ops.py submit --phase audit
python3 ml/stage174_ops.py collect --phase audit
python3 ml/stage174_finalize.py
python3 ml/stage174_document.py
python3 ml/stage174_validate_docs.py
git diff --check
```

## 阶段结论与下一步

新双端观测具有有限真实均时支持，真实差时位置支持尚不足；未训练能量模型、未宣称能量改善，Stage87及全部原验收门保持。

下一Stage175固定旧89033队列/280来源的真实保存Timing状态、localtime/rawQ、pz0与Trig外推，先原pi/K/charm各32个train的接口/成本pilot，再按成本门读所有明确selected entry，缺源不替换、无时间父不删除。只对通过真实控制门且MC也通过的两片均时检查MC校准范围覆盖；data系数不直接移植到MC。同步固定检查μ留出中|残差|>2ns的数量、状态/采集坐标/参考差异，以区分实现与物理未知，不能按结果修门。若有实际支持，再另冻X/状态V/状态+均时T的同支持新训练及原八层三尾评估；没有支持则结束该部署候选。全队列覆盖、均时能量改善及跨时期系统误差仍未测量。

S0实际参考面/材料修正和前后辐射的小型同父instrumentation、匹配同窗读出干预、实际双量程/独立高幅参考、backscatter及背景效率/生成加权物理路线继续；不以本校准作为无限前置。项目整体与独立最终确认仍未完成。
