# Stage150：既有训练父的 Ecal overflow 支持审计

## 目标与输入

执行 [Stage149 冻结合同](stage149_energy_ml/next_execution_contract.json)，为 Stage132 §5.4 尚缺的真实 Ecal ADC clipping 方法控制寻找**事先定义的有限支持**。只审计原4032个父的role1，在实际保留的 Calo status 中按bit4判断候选；若有候选，只取原frame顺序首个。没有按 Eν、模型风险、残差、来源比例或性能挑例。

[本阶段协议](stage150_energy_ml/protocol.json)与原合同逐字段相同。实际输入为：

- `ntuples/energy_ml_stage131/production_cases.json.gz`：原父／角色／固定stratum身份。
- `ntuples/energy_ml_stage131/matched_input.npz`：只提取 `frame_index` 和 `calo_status`，未读取预测或训练新模型。
- `ntuples/energy_ml_stage137/boundary_evidence.json.gz`：核对原父身份及原重新选择标记。

先检查前64父schema、全体4032身份以及保留status矩阵 `(3002,4)` 的唯一frame关联。角色非1不参与候选选择；未选中且无status参考的父保留未知，不能补0或称未饱和。所有科学数组读取和计数均在 HTCondor 中完成。

## 实测结果

[支持汇总](stage150_energy_ml/support.json)、[35行分层表](stage150_energy_ml/support.tsv)记录实际计数。

| 项目 | 实测 |
|---|---:|
| 原父总数 | 4032 |
| matched_input 保留status的全角色选中行数 | 3002 |
| role1训练父 | 2304 |
| 训练父有合法原Calo status参考 | 1708 |
| 训练父无原status参考，仍未知 | 596 |
| 1708父×4 Calo通道视图 | 6832 |
| status1 | 6512 |
| status0 | 318 |
| status32 | 2 |
| 带overflow bit4的训练父／通道视图 | 0／0 |
| 准入重放的父 | 0 |
| 实际新增G4／独立ν／fit／reserved forward | 均0 |

status32保留原数值，不当成status0、overflow或有效timing。对status先要求有限、非负整数，避免对负占位值直接作bit判断。缺失status的596父在35行表中均属于原selected0；没有从2304训练父分母删除。

低能支持也保留π/K/charm：原E50–100 GeV选中参考分别340/72/1父，E100–200 GeV分别317/114/6父，全部没有原Calo overflow位。stratum是原采样设计的描述性标签；这些计数未作总体权重或生成接受度修正，不是自然样本混合率或总体饱和概率。

[运输准入](stage150_energy_ml/transport_admission.json)为False，原因是**无符合冻结定义的父**，不是CPU不足。没有追加G4、换父、扩大库存、人工裁切波形或改用高电荷排名。该固定支持审计已完成，而真实Ecal clipping/source控制本身仍**未测量**；尤其不能从0/1708参考父推广“真实Ecal没有饱和”，也不能把6832个相关通道视图当独立总体样本。PMT非线性和无status参考父同样不能由此排除。

## 执行、资源与验证

```bash
python3 ml/stage150_submit.py
python3 ml/stage143_monitor.py --stage 150
python3 ml/stage150_finalize.py
```

作业9674717.0，HTCondor目录 `~/condor/nu_muAnalysis/stage150/`，4CPU/12GB、MaxRuntime86400秒，无应用短timeout。worker脚本随任务传输，不在执行节点依赖AFS读取启动脚本。LCG109 Python/numpy、BLAS1线程，无模型训练或可由GPU加速的重任务。

[调度计数](stage150_energy_ml/scheduler_accounting.json)：1次start、exit0、5 scheduler CPU秒、10聚合execute wall秒、GPU0，低于1000秒。support专用CPU allowance82秒，是为原合同可能的单父响应及审计保留预算的约束，没有扩大阶段预算。

[GNU time](stage150_energy_ml/support_time.txt)：CPU user3.78／system0.30秒、wall4.47秒、最大RSS271308 KiB；内部主函数CPU3.643705701秒、wall3.680559849秒。内部计时／GNU均包含在scheduler，不能重复相加。ROOT读取、G4时长和实际ADC rail数均未测量，因为没有准入这些执行步骤。

验证包括：原4032父／证据身份、前64schema、3002唯一frame的4通道status、合法status类型、仅role1候选、固定首父规则，以及Python/shell语法。源码未访问模型预测、打开reserved或新增能量输入；原pz0-only、raw11、signed／typedNaN和status0-only timing规则保持。

[存储清理](stage150_energy_ml/storage_cleanup.json)：无新ROOT/xAOD和逐事件响应输出。仅保留紧凑支持JSON／35行TSV、计时／调度及源码审计；源码和实际worker归档为 `software/stage150/source_snapshots.tar.gz`，5013 B。删除重复运输23887349 B，原输入与其他阶段未动。无需运行或删除任何新的G4任务。

## 结论与下一步

有限既有训练队列没有可用于该预定真实Ecal clipping控制的status支持。Stage148混合来源非clipping闭合、Stage149原生协方差／读出配对结果仍有效，但它们不能补出未测量的混合×clipping响应。本阶段不关闭所有波形或饱和研究，也不将支持缺口当作低能能量信息不存在的证明。

接下来按[Stage151合同](stage150_energy_ml/next_execution_contract.json)利用已有实际元数据提出一次有界物理对照：原μ HITS前4→最多64父，仅将官方digi/reco/ntuple的conditions06改为输入元数据的conditions04，其他几何、代码和显式随机规则固定。与Stage149保留的同父06控制，以及原PHYS同父raw/status/point状态比较，交付实际channel map、raw/status、状态／covariance和选择变化。它直接检验已知conditions差异的响应影响，不做metadata-only库存追查、gain/seed网格或性能择优。

预算1000累计CPU秒、首pilot400秒；先真实4父及同一新REC/ntuple身份／raw支持，再按实测三倍affine成本与100秒审计reserve准入64。无G4／fit／新ν，不把tag对照当1σ系统或已校准covariance，更不要求新raw／pz等于未知随机流的旧PHYS。所需输入均为已知HITS／旧PHYS与Stage149缓存，验收与未知项在合同中明确。

完整低能优越性、协方差pull／关联后验、宽能区及data迁移、乳胶匹配、真实曝光GRL／背景／完整接受度、相关辅助约束与独立确认仍未交付。Stage87 direct62、全部原门与Stage137双低箱5%扩大门、全部K／角色及reserved关闭保持；整体研究目标未完成。
