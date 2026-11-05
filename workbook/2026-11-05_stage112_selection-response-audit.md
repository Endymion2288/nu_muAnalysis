# Stage112：选择分母实验的原生 QA 通过，冻结成本外推未准入

日期：2026-11-05；起始 commit `1cf3ade`。依据用户本次“按照现在的计划继续推进下个阶段”，执行路线§93和[Stage111合同](stage111_energy_ml/experiment_contract.json)。

## 1. 结论与完成范围

**本轮完成36条固定真实记录的原生选择、单位及空轨迹/占位值QA；在冻结的资源准入处停止，没有完成六文件物理测量。** 两个低能主端点、全父分母选择效率、transfer/response组成变化、原八层风险、500次条件区间及模型改善均为**未测量**，不能把程序/资源停止当物理阴性。

六个原定 PHYS 各10000条父记录，合计60000条，67个必要branch齐全。原生20项有效MC切选与独立掩码逐例一致，leading/pz单位核验通过、pz差0 GeV；真能量比较满足相对容差1e−12。真实QA去重后为36条（5/5/5/5/8/8），40是上限，不是实际测量数；对话中的“40条QA通过”已更正。

实际QA中有4个 `(source,cut)` 计数出现“按既有非负域规则无效的 reduced charge，通过原生 `<30 pC` 单项切选”。这证明模型 typed 清洗不会自动改变分析切选，但不证明这些事件通过完整S50，更不证明它们造成低能失效。具体负值、身份及最终选择影响没有保留到该QA汇总，总体发生率**未测量**。

资源外推为 **14665.550938 CPU秒 / 3371.318452 wall秒**，超过原3600/900秒；接口字节投影411896777 byte低于2GiB。按原规则不全量读取、不事后改变外推或预算。小批Awkward调用的固定开销被逐事件线性放大；没有测量完整向量化调用的真实成本，因此这个外推不是全量耗时测量或计算下界。

## 2. 输入、总体和变量政策

精确路径沿用[六源清单](stage111_energy_ml/source_manifest.json)，无availability/产额/效果筛选或来源替换。π/K/charm各历史train/cal一源；没有扫描其他EOS目录、恢复旧REC或生成新样本。

|source|成分/历史角色|父entry数（metadata）|实际QA条数|QA原生S50条数|独立切选差异|
|---|---|---:|---:|---:|---:|
|55:4|π/train|10000|5|1|0|
|55:164|π/cal|10000|5|1|0|
|55:84|K/train|10000|5|2|0|
|55:67|K/cal|10000|5|1|0|
|55:116|charm/train|10000|8|6|0|
|55:118|charm/cal|10000|8|4|0|

QA规则为每源最前4条，加原Stage105六源记录按row排序最多16条，去重不补；实际entry列表见[qa_manifest.json](stage112_energy_ml/qa_manifest.json)。它含原已选记录，不能用本表S50比例估计选择产额或效率。各源完整60000条未被作为事件载荷读入；父entry数来自ROOT头信息。

G0仍为所有实际名义MC切选仅去reco pz0>50，保留truth νpz>50、真位置、fitted-charge、质量/几何及有效requires。G+要求有限正pz/Eν，S50/S100保持原定义。主要端点仍是固定传统pz0/0.8在真[50,100)/[100,200)GeV的六源等权 `MSE(S50∩G+)−MSE(G+)`。选择前每来源incoming视图总权重1、空来源不删源重归一、test>cal>train和原隔离政策均未更改。

本轮在全量及身份联结前停止，**没有打开Stage87 split的数值字段**；它只作为原字节输入包被运输核验。未来必须实际执行身份白名单/test-key隔离后才能计算主端点。原71376 active、原角色/17657隔离、全部1016新增K和缺源策略不受本轮改变。

没有模型fit/forward/offset/温度、低于50GeV的BDT外推、切选优化或晋升。模型一次方动量仅pz0，允许px/py、q/p、弯折；raw11/status、typed NaN、合法signed负值及Calo缺项传播规则保持。真μ能量只用于诊断接口。

## 3. 程序实现与实际QA

新增[独立选择与真值诊断](../ml/stage112_selection.py)、[批执行器](../ml/stage112_audit.py)、[冻结统计实现](../ml/stage112_statistics.py)及[运输工具](../ml/package_stage112.py)。统计实现的完整样本身份/权重/分解/bootstrap路径本轮**未运行、未验证**；不能因源码已写就记为物理交付。

复用现成`build/analysis`，没有重编。只选择原YAML中切选和三个核验输出所需的定义依赖闭包，表达式保持原样；67列包含必要scalar、truth和leading关联，**不读取SP、波形或p0/p1/pz1分支**。源文件读取采用有限8MiB精确请求缓存；将所需原始值/primitive类型写入短生命周期本地TTree，调用原compiled分析程序产生完整`eventID_pass`及名义selected。保留native reduced分支、无aux；没有用raw替换fitted cut。原生20个有效MC cuts及requires、每个实际命令/有效definitions/file/output配置均在[QA.json](stage112_energy_ml/QA.json)。

Python独立掩码逐条对照native flag、累积cutflow及最终成员；核最高pz leading、run/event、pz和truth能量。空轨迹/空真值不flatten丢行；多主μ标未知；向量错长被拒绝；−999、非负变量−1、NaN、unsigned wrap变NaN，而合法raw负值和charge sign=-1保留。fallback−1234为“无需fallback”控制值，单独解释。合成检查通过，但不表示真实数据中所有占位约定均已识别。

|真实QA中的非负域无效而单项native-pass|计数|
|---|---:|
|55:164，VetoNu0 reduced charge <30 pC|1|
|55:164，VetoNu1 reduced charge <30 pC|1|
|55:67，VetoNu1 reduced charge <30 pC|1|
|55:116，VetoNu0 reduced charge <30 pC|1|

这四个是单项cut计数，不等于四个独立incoming或四个最终selected事件。当前判据是`q非有限或q<0`；已知比较NaN不会pass，因此这些条目涉及负值，但**具体是否−1/−999或其他值未测量**。不擅自把所有负读数当通用sentinel，不删这些父事件，也没有修改native reduced veto。旧Veto/Timing/Preshower切选仍用fitted charge；其状态失效、raw差异和最终效率影响要在完整测量中交付。

## 4. 两次作业、接口修复和资源停止

原计划单任务。首次`9668058`在uproot暂存写入接口失败：当前版本`mktree`要求类型schema，代码误传数组。没有启动native选择、产生QA比较或拟合/主端点。该可避免的接口错误已修正为显式Awkward element datashape后`extend`；在重提前写[launch_amendment.json](stage112_energy_ml/launch_amendment.json)，明确最多两次提交、原科学合同及总预算不增，并保留失败产物/成本。不是调效应、换来源或隐藏重试。

补跑`9668059`首start/exit0，实际QA通过后`admitted=False`，正常返回resource_stop。没有第三次提交，也没有在结果后重定义本阶段的准入公式。[admission.json](stage112_energy_ml/admission.json)保存每源公式项。

|source|QA独立decode CPU / 秒|真实条数|全量/QA条数比|
|---|---:|---:|---:|
|55:4|0.179147299|5|2000|
|55:164|0.239165046|5|2000|
|55:84|0.223573153|5|2000|
|55:67|0.265223851|5|2000|
|55:116|0.222714061|8|1250|
|55:118|0.203256498|8|1250|

冻结实现以native QA setup一次、完整branch/basket I/O估计、`2×decode_CPU×N/n`作为Python/native变长调用代价代理，再factor3加CPU300/wall120秒和失败成本。由此得到CPU14665.550938秒、wall3371.318452秒。Awkward的Python调度/类型操作有固定开销，此处按5–8行均摊后乘1250–2000，没有完整向量批次测量支持这一比例假设。因此“这笔估计不能准入”和“全量实际需要四小时”是不同判断，后者**没有证据**。本轮只执行前者的冻结stop。

|GNU外层，含等待的子进程CPU|CPU / 秒|wall / 秒|最大RSS / KiB|退出|
|---|---:|---:|---:|---|
|9668058，写入API失败|8.09|6.32|79080|1|
|9668059，QA＋准入停止|61.24|18.48|625752|0|
|实际累计|69.33|24.80|不相加|原3600/900秒内|

GNU最大RSS是所测进程/已等待子进程的最大值，不是六worker整棵树同时占用的总峰；该总峰**未测量**。原descriptor申请6CPU/12000MB，站点按每核最低内存改写/分配18000MB；0GPU，六worker、ROOT/BLAS内线程1。native六任务及worker计时属于外层嵌套口径，不再加到69.33秒。Condor slot wall为10/24秒，包含任务准备/清理，不与GNU wall相加。单核加速比、GPU busy、整会话CPU和物理EOS网络流量未测量。

接口请求与底层read不同：补跑源＋native本地输入实际请求 **28043817 byte**；其中六QA源的底层read合计 **6867600 byte**、native本地返回 **1946701 byte**，另一次两行合成测试输入的底层counter未单独保留。首次失败未保留实际请求counter，其读取仅为与补跑相同确定性六源QA工作流的前缀，以补跑完整六源请求 **25344369 byte**作保守上界；这是上界、不是首次实测。累计源/native接口上界 **53388186 byte**，低于2GiB。计数推导及限制见[resources.json](stage112_energy_ml/resources.json)。不能把manifest逻辑275663702 byte当实际I/O。

## 5. 验证、产物及执行命令

实际命令：

```bash
python3 ml/package_stage112.py package
condor_submit -dry-run /tmp/nu_mu_stage112.ad AnalysisZipFramework/submission/ml_stage112.sub
condor_submit AnalysisZipFramework/submission/ml_stage112.sub  # 9668058
python3 ml/package_stage112.py collect
# 收集失败证据，写launch_amendment，修正mktree API后：
python3 ml/package_stage112.py package
condor_submit AnalysisZipFramework/submission/ml_stage112.sub  # 9668059
python3 ml/package_stage112.py collect
python3 workbook/stage112_energy_ml/validate.py
git diff --check
```

提交前做Python AST及bash语法检查、Condor dry-run核Args/Iwd/CPU/memory/MaxRuntime/输入；真实小样本检查在batch入口、全量前进行。第一次接口错误说明仅语法检查不等于运行通过；失败已计入资源及提交次数。

第一次16项输入、第二次17项输入（含amendment）运输后逐字节一致；不做SHA或重新读取事件作本地数值计算。回收[完成状态](stage112_energy_ml/complete.json)、[36例QA](stage112_energy_ml/QA.json)、[来源小表](stage112_energy_ml/qa_sources.tsv)、原生日志、两次time/history、失败证据、协议和预算。暂存ROOT/trace由worker清理，不保留PHYS/SP/xAOD副本；运输包及重复结果归档在核验后删除，紧凑留存见[storage.json](stage112_energy_ml/storage.json)。既有Stage54五资产和Prompt后缀保持，不动其他项目9668047–9668051的作业/目录。

[逐项完成审计](stage112_energy_ml/completion_audit.tsv)和[文档验证](stage112_energy_ml/document_validation.json)区分“QA与冻结stop完成”和“物理问题未测”。原最终两低能/传统上95≤1.05、all/direct≤1.01、其他五层/direct≤1.03及八层三尾差direct上95≤+2pp不改，整体目标仍未达；没有新独立、source/refit或真实系统确认。

## 6. 下一步：一次完成测量，不续小批成本外推阶段

Stage112按原规则结束，不改写它的资源拒绝。为持续推进这项测量的下一步另冻[Stage113工程执行合同](stage112_energy_ml/next_execution_contract.json)，**Stage112结束时尚未执行**。不需要新的输入，复用这六个完整PHYS及已经通过的36例QA；不再单设metadata/接线/计时阶段。

唯一变化是取消没有全批次依据的`decode_CPU×N/n`准入，改为一次完整六源测量，实际累计CPU/wall/读取请求由进程树watchdog和共享pre-read cap限制。两阶段共用原3600 CPU秒/900任务wall秒/2GiB接口预算；已耗69.33/24.80秒和53388186 byte保守上界先扣除，剩余3530.67 CPU秒、875.20 wall秒、2094095462 byte。最多新增一个6CPU任务，保持临时128MiB/最终20MB；native子进程也计CPU、留清理余量，实际达cap就停止并标不完整，不能挑已完成的有利来源报联合端点。

输入、定义/原生切选、角色/全部K、选择前incoming权重、两低能端点、六源标准化、完整signed分解、原八层与三尾、固定500共同incoming抽样和统计限制均不改。应补交本轮未测的完整native/身份闭合、全分母/风险/响应及真实无效值审计；对invalid-native-pass保留source/entry、值、status和最终S50去向的紧凑例表，不能先修cut再称风险改善。验收是完整结果或确切零支持/实际资源停止原因，不要求效应有利。

此合同仅安排下一次有界实际测量，不授权新模型、阈值、源、生产或晋升。完整问题仍是PHYS条件分母，不能认证生成/输运接受度、50GeV背景或固定完整X下条件信息增加。
