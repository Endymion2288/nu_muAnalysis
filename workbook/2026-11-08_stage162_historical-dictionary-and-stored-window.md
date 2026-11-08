# Stage162：历史字典兼容性与真实data的raw积分定义差异

## 目标与冻结定义

承接[Stage161下一合同](stage161_energy_ml/next_execution_contract.json)，不放松Stage161失败的物理ID门。唯一候选是pinned `IdDictScintillator_2024.xml`，源码证明其与2025扩展前a443e427默认文件逐字节相同；不根据新数据选layout。精确[同源manifest](stage162_energy_ml/matched_manifest.json)仍为run15838 REC00006与PHYS原前64父，原4pilot→ID/内容/三倍成本门通过才原64→独立原4。Stage159不同REC原64无支持父保持原文。

仅作业临时目录shadow一个`ScintIdDictFiles/IdDictScintillator.xml`，精确cmp冻结字节。静态ExpatCoreParser源码显示先fopen相对路径、再prefix、再XMLPATH；因此除原DATAPATH外同时prepend XMLPATH，并在CWD放唯一shadow，**不改变其他XML、geometry04、tag05、CONDBR3或cable payload**。读取actual IdDictManager文件名/tag/region数证明实际旧四region，而不是凭env声称生效。相对源码控制的路径解析为实现细节补充，科学问题/候选不变。

[事前数值定义](stage162_energy_ml/numerical_definition.json)来自pinned `fillRawHitValues`/`findRawHitValues`：保存的是baseline减ADC换算后的float mV窗口，raw_integral为`2*accumulate(...,0.)`，即double累加、最终持久化float。瞬时读取sample sum/absSum/max/finiteN，仅存摘要：`Q=sum(sample)*2ns/50ohm` pC，peak取max。接受界固定为reported raw_integral的half-float-ULP/50加double γ(N+2)累计界；不看差值后调容差。只有status==0读取time-vector端点/2ns间隔结构；非0status只读长度，禁止其到达时间或相对时序输入。无样本数组持久化，无baseline/CB fit或自选窗口。

## 执行与预算

所有ROOT/事件数组/统计通过`~/condor/nu_muAnalysis/stage162/`，复用d32现成构建。2000累计CPU秒/650pilot/200audit，2核8GB、最多1job，0GPU/G4/新ν/自然ν或隔离forward/能量fit。小样本顺序读不为使用GPU改算法。实际GNU含startup和post-first完整边界，原三倍full64预测与全部已用一起校验；不抬预算。

```bash
python3 ml/stage162_ops.py submit --phase pilot
# 原门/内容/实际字典证明及预算全过才full，再repeat
```

## 详细实测数据与验证

### 两项原门均未通过，不扩64

第一作业9675632.0成功读取原4的全部waveform，随后native几何初始化失败，实际native事件数0。错误明确为`FaserDetectorID ERROR initLevelsFromDict - unable to find VetoGm label`、VetoNuID初始化失败；helper还提示旧字典无Muon region。见[实现限制](stage162_energy_ml/implementation_limit.json)。当前pinned helper要求新label，与冻结旧四region不兼容；不能把旧XML文件已cmp说成actual旧helper认证，也不能推断旧data损坏。没有更改布局、helper、geometry或tag，没有重建/降容差/换旧构建继续尝试。

原数值门的[内容审计](stage162_energy_ml/summary.json)和[逐路表](stage162_energy_ml/pilot_window_content.tsv)给出：

| 实测量 | 结果 |
|---|---:|
| actual raw4与Stage161原raw控制 | 全部原字段精确 |
| primary保存窗口 | 96 |
| finite samples | 8496/8496 |
| 每窗口采样数 | 76或101 |
| max(sample)与raw_peak | 96/96精确 |
| 有符号整窗积分与旧raw在原误差界内闭合 | 0/96 |
| 最大电荷差 | 1.1296728515625034 pC |
| 原数值界的最大值 | 9.765627569272904e−6 pC |
| 非0status窗口／提供time-vector值 | 45／0 |
| status0窗口2ns间隔 | 51/51 |

status0端点为112–262、124–324、156–306、160–360、178–378 ns，均为原保存重建窗；76/101点不是600点全采集。禁止将这些窗外未保存的信号当0或据此训练迟到响应。当前raw读ROOT2440448B，内部9.914375408CPU秒/25.729154264wall秒、RSS774980KiB；只有4不同父。

### 有符号积分失败的原因：旧producer的正采样整流定义

读回差值后查源码版本，而非放宽数值界。历史3de41ab4以及7b61d3fc父版本的`findRawHitValues`遍历整窗，跳过`wave[i]<=0`并令raw_integral=`2*tot`；dd56a65e（2026-08-16）才改为整窗有符号double累加。完整[源码摘录和变化](stage162_energy_ml/producer_integral_source.json)保留。Stage162事前使用的是当前pinned语义，所以原0/96结果保持，不将事后原因诊断包装为原门通过。

仅用已保存sum S和absSum A，另冻一个源码指定的诊断：positive-part sum=(S+A)/2，检查float32(2×positive-part)/50是否逐值等于actual旧raw。不重读ROOT/采样、不扫窗口/版本公式、不修改源波形。[独立producer诊断](stage162_energy_ml/producer_definition_summary.json)、[逐路结果](stage162_energy_ml/producer_definition.tsv)实测：

- **96/96旧raw_charge按float32精确复现正采样积分**，peak亦已96/96精确。
- 17/96实际有符号整窗积分为负，而旧raw是正采样积分；最大整流偏移1.1296728515625034pC。
- 这解释本次raw积分差异，并不认证确切历史producer commit或所有run/MC定义。没有测量噪声偏置总体分布、μ纯度/FPR、gain校准或ν能量影响。

不能把同名旧raw_charge与当前signed integral当相同观测再拟合统一响应。弱信号可能受整流影响是可检验的物理机制候选，**尚未证明它导致Stage87最低能失败**。合法signed负值政策继续保留；也不能因此把已有负raw全部判为占位或篡改历史结果。

## 资源、产物与验证

3job/3start：9675632.0 exit1，24scheduler CPU秒/51wall秒；9675638.0原缓存审计exit0，scheduler0秒/4wall秒；9675654.0源码定义缓存诊断exit0，scheduler0秒/4wall秒。整数取整不代表免费：两JSON-only审计GNU实际0.06/0.05CPU秒。总24scheduler CPU秒、59聚合execute wall秒，最终0live；无full/repeat、0GPU/G4/新ν/自然ν或reserved forward/能量fit。

[实际资源](stage162_energy_ml/resource_audit.json)：申请2核8GB，CERN实际3核9000MB包含传输资源，不作科学加速宣称。raw GNU12.95CPU秒/32.04wall秒、RSS774980KiB；失败native GNU7.64CPU秒/10wall秒、RSS716532KiB。CPU预算充分也不能绕过物理门。

```bash
python3 ml/stage162_ops.py submit --phase pilot
python3 ml/stage162_ops.py collect --phase pilot
python3 ml/stage162_ops.py submit --phase content_audit
python3 ml/stage162_ops.py collect --phase content_audit
python3 ml/stage162_ops.py finalize
# 查到源码定义后，仅补已有缓存诊断，并精确追加归档
python3 ml/stage162_ops.py submit --phase producer_audit
python3 ml/stage162_ops.py collect --phase producer_audit
python3 ml/stage162_ops.py finalize_supplement
```

事件胶囊`ntuples/energy_ml_stage162/event_records.json.gz`6732B，源码/worker/GNU日志归档`software/stage162/`。初次归档后补诊断逐member保留原archive内容，不覆盖或漏计早期失败；[清理审计](stage162_energy_ml/storage_cleanup.json)累计删202067B已验证重复。无持久ROOT/采样数组。Stage54全部12文件size/mtime、原HEAD路线图全文、合同逐字节、源AST/bash、预算/终态/无full及Git diff检查见[完成核对](stage162_energy_ml/completion_checks.json)。

## 阶段结论与下一步

本阶段没有取得旧字典native认证，当前helper兼容性阻止该固定实现；也没有通过原signed积分门。它取得了更具体的测量结论：**这4真实data父的旧raw使用正采样积分，与当前有符号积分不同，且源码定义能96/96精确闭合。** 不把读取或格式修复当最终能量成果，不继续布局/转换器小网格。

[下一Stage163合同](stage162_energy_ml/next_execution_contract.json)回到能量问题：原89033角色、71376active及全部K，固定普通Calo原producer rawQ4对X62的新增内容，三臂X62、X62+状态/可用性M12、X62+M12+Q4，恰9原政策BDT。先五origin原train小样本身份/字段/producer语义与成本，再准入全原活动队列；12000CPU秒、4核16GB/最多4job、无新G4/新父或旧X网格。保留as-produced定义，不把旧正采样raw冒充signed，也不借data结果认证MC/data迁移。原八层三尾和双低箱5%门保持，阴性结束该固定Q4实现。

[既有研究排查](stage162_energy_ml/next_observable_source_audit.json)确认X62仅普通Calo fitted/calibrated E_EM、Stage47是理想HITS沉积、Stage129恢复是scint；Stage145/157确曾在μ控制使用Calo raw，所以不称raw首次测量。下一是自然ν同原支持的幅度增量相对状态控制，而非重复那些控制。

低能ν优越性、μ/data纯度/FPR、covariance覆盖、真实gain/time/producer迁移、GRL曝光/背景/全接受度/乳胶/真实相关辅助约束和独立确认仍未完成；Stage136/140有限MC工作模型及3000toy不重做。Stage87和全部原门、Stage137双低箱5%、pz0-only（允许px/py/q/p/弯折）、raw11/status/typed/signed/Calo缺失、全部K/角色/reserved保持，整体目标未完成。
