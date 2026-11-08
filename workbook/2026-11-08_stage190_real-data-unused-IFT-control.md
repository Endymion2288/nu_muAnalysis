# Stage190：真实run15838的未用IFT预测与候选歧义

日期：2026-11-08。继续[电子观测路线A/D](2026-11-08_stage187_electronic-only-observables-research.md)。**原64个真实data父中63个原leading精确匹配且支持实际起始面预测，9个匹配父处于pz0=50–100 GeV；真实IFT预测可执行。** 单一run的全候选残差不能认证μ纯度、错误关联率、动量误差覆盖或MC→data迁移，未作能量训练或部署。

## 目标、输入和冻结配置

[协议](stage190_energy_ml/protocol.json)在读取新残差前冻结原[Stage160配对manifest](stage160_energy_ml/matched_manifest.json)的第一64 PHYS父，pilot为其中第一4；全部按run/event/native timestamp认证，保留失败父，无残差/pz筛选或替换。REC是 `/eos/experiment/faser/data0/rec/2024/r0022/015838/Faser-Physics-015838-00006-r0022-xAOD.root`，PHYS是 `/eos/experiment/faser/data0/phys/2024_back/r0022/015838/Faser-Physics-015838-00000-00049-r0022-PHYS.root`，native entry从58688到59065的原64配对。来源选择并非经独立μ纯度认证，也不是覆盖全部run的随机样本。

使用历史producer与Stage161状态闭合已经固定的 `CKFTrackCollectionBackwardWithoutIFT`，不按本阶段残差改挑集合、不再merge/reco。真实geometry FASERNU-04、OFLCOND-FASER-05、CONDBR3，FASER磁场、显式官方 `material-maps-alma9.json`、MS与eloss开启；零材料为固定诊断。Stage188相同gcc13/C++20 bridge及实际TSOS wafer/frame恢复、完整5×5反单位换算，48个IFT wafer与所有候选保留。复用已编译Calypso runtime，只有小bridge编译；没有完整框架重编译。

所有科学ROOT/gzip处理和审计在HTCondor，本地仅源码、调度、标量报告和精确字节归档。预算1200 CPU秒，pilot400/full600/audit200、4请求核/8 GB（池实际槽位可分配12或24 GB）、最大1并发；最终事件摘要上限16 MiB，不放宽门或借用旧阶段余额。Stage161的scintillator raw身份问题仍是独立缺口，不用于关闭本次不同轨迹问题。

## 实测数据与物理限制

| 指标 | 实测值 |
|---|---:|
| 原父N / 原leading精确匹配N / 起始面支持N | 64 / 63 / 63 |
| 匹配pz0 50–100 GeV父N | 9 |
| 起始面原因 | {'actual_measurement_surface_recovered': 63, 'no_long_track': 1} |
| 成功传播wafer N / 几何界内wafer N | 329 / 329 |
| 几何界内无cluster / 多候选wafer N | 12 / 63 |
| 无abs(pull)≤3候选 / 多个兼容候选wafer N | 62 / 11 |
| 全候选N | 442 |
| 全候选残差RMS / abs95（mm） | 8.563751089 / 23.331196747 |
| 全候选pull RMS / abs95（无量纲） | 42.379739360 / 89.677634429 |
| abs(pull)>3候选N | 157 |
| 材料开/关σloc0中位比（无量纲） | 1.001439075 |

逐候选r为原生一维u−预测loc0（mm），S=V+C00（mm²），raw pull=r/√S。没有最近hit择优或人为covariance inflation；不同wafer/共享PRD/同父候选相关，候选N不是独立父N。真实data无SDO，所有贡献标签保持缺失，不造“正确μ关联”。无坏道/DAQ mask认证时，几何界内无cluster不是已认证hole。全候选宽尾可能同时含关联、真实散射与条件误差，现有控制不能唯一分离其物理原因。

Stage188 MC100012原64仅19匹配，ν三个train来源96/96匹配；其混合物和本run并不相同，因此不把两个全候选RMS相除称data/MC分辨率差。原8/63/2困难父缺面仍未知。本阶段真实纯度、正确/错误关联率、独立pull coverage、低能Eν收益、真实beam LOS/mask迁移均**未测量或未认证**，不能用63/64支持率替代。

## 验证、性能、失败和存储

[独立审计](stage190_energy_ml/independent_validation.json)通过471项有理数r/S与独立标量pull检查、67个source表示检查，pilot/full原4逐值完全一致。最大source闭合8.59276696743e-07 mm；source实际传播roundtrip成功67，前五参数最大混合单位差2.84217094304e-14，只是数值诊断。审计不独立认证ACTS算法、原producer误差覆盖或绝对动量尺度。

首次pilot因COOLSQLiteVetoPattern在后续service merge前设置，配置冲突退出，37 CPU秒、没有观察算法执行。将同一真实CONDBR3 SQLite replica设置移到所有merge后，原tag/父/物理合同及400 pilot限额不变。完整失败日志归档，不将程序错误当物理阴性。审计另有一次socket断开/执行机找不到job的自动驱逐重排，原job未重复提交；该丢失attempt调度报告0 CPU秒/22 wall秒，实际CPU未测量，成功审计GNU为0.58 CPU秒。

成功pilot完整GNU+compile118.59 CPU秒，按原三倍公式预测full359.640577344<600 CPU秒，RSS上界2144.0625 MB，通过后才跑64。full内部80.455532164 CPU秒/110.065513085 wall秒、ROOT请求26006716 B、峰RSS1755896 KiB；初始化占主要成本，单进程复用runtime。不是受控CPU/GPU加速比；ACTS运输当前CPU实现，未假称GPU加速。

| 进程 | GNU CPU/s | GNU wall/s | 峰RSS/KiB |
|---|---:|---:|---:|
| audit_time | 0.58 | 1.05 | 60976 |
| full_compile_time | 31.20 | 52.02 | 1329188 |
| full_time | 86.07 | 120.76 | 1755896 |
| pilot_compile_time | 25.51 | 32.11 | 1333336 |
| pilot_repair_compile_time | 28.82 | 46.07 | 1330676 |
| pilot_repair_time | 89.77 | 163.36 | 1756416 |
| pilot_time | 7.31 | 10.74 | 666032 |
| review_time | 0.40 | 0.77 | 30720 |

调度共5start，失败1，282 CPU秒/592聚合wall秒/0live，未超1200。执行为 `python3 ml/stage190_freeze.py`，`stage190_ops.py submit/collect --phase pilot,pilot_repair,review,full,audit`（逐阶段，不是将逗号字符串作为参数），最后 `python3 ml/stage188_finalize.py 190`。提交目录 `~/condor/nu_muAnalysis/stage190/`。

最终 `ntuples/energy_ml_stage190/{pilot,full}_native.json.gz` 保留581447 B，精确源码/日志/标量历史/spool在 `software/stage190/`；清理重复1569514 B。[清理记录](stage190_energy_ml/storage_cleanup.json)确认全部终态、无队列引用、Stage54原12项size/mtime不变，无新ROOT/xAOD持久化。

## 阶段结论和下一步

真实未用IFT同面预测已有具体支持，也有缺失和关联歧义；不直接对μ动量作数值修正。下一Stage191固定原280来源/71376active、全部K/角色与pz>50的X62/availability/σ-only/12项三层候选内容/条件联合打乱对照，先原八来源训练父pilot认证身份、frame、r/S与成本；通过才完整新提取和15fit。验收仍为原两个真E低箱、八层三尾/所有原门，并要求内容胜过可用性、σ与打乱控制；只改善σ或关联区分不算能量成功。新实验独立冻结有限预算，不扩大本阶段预算。

路线B需实际时期LOS/坏道与active mask；D的转换/overlay/testbeam、E的2025+匹配四平面、F的真实非单pulse与相应MC支持不制造输入。原Stage87、所有K、原train/cal/devtest/quarantine/reserved、pz0-only、raw电荷/typed NaN/合法signed/status0 timing保持。整体低能优于传统、独立确认和真实系统谱目标仍未完成。
