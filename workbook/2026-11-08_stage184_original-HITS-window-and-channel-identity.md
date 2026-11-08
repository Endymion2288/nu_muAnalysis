# Stage184：原队列 HITS 同窗快速积分与历史通道身份

## 阶段目标与输入

承接 Stage172 §7 尚未回答的能量信息问题：同父同窗去噪声/去 ADC clip 后，能量估计能改善多少。Stage179 的12父电荷误差控制没有完成这一能量比较，本阶段不把它重新命名为已完成的能量实验。

[冻结协议](stage184_energy_ml/protocol.json)先验证现有官方 HITS 能否提供同父15路理想积分，不新做 G4、不重建、不训练或预测。原 Stage129 280请求、89033身份、71376 active、全部K/原角色/隔离/reserved/pz>50 GeV 保持；不增加一次方动量或使用坏状态时间。原始路径由 RDO 文件名的 run/subfile/tag 精确回接；[路径清单](stage184_energy_ml/existing_hits_inventory.json)实查2800/2800 HITS存在、280/280 RDO存在。存在性不是内容或读出匹配认证。

固定 π/K/charm 各第一个来源（0/48/113）、各前32个原train，原计划96父。先执行来源0的前4父，原row0/1/2/3、entry19/52/59/62，均run200082；没有按真能量、预测误差或clip选父。参考为Stage179原12父、202条带实际ADC通道。新cal/test能量结果未读，原隔离与reserved无读出提取或预测。

## 工作内容与计算口径

[快速积分](../ml/stage184_window.hxx)使用 d32 实际 CB kernel、2 ns采样、20倍过采样、TH1D时间分箱、float hit/value/time cast与严格省略最后一bin，积分原scint780–980 ns、Ecal780–930 ns并包含端点。预计算正kernel的窗口权重，省去逐点float乘积舍入及改变加和次序；**不是逐bit相同**。事前容差为 `32*float32eps*max(1 pC,abs(reference Q))`，结果后没有放宽。

HTCondor原HITS读取用实际CollectionTree总条数闭合parent_N=10000，稀疏selector按原entry；逐父实际run/event和float32 incoming与原合同精确一致。RDO分别以实际run/event核对。读取五个实际RawWaveformContainer，不解码旧ID到当前字典；官方primary接口重建保存的ADC，取得原窗口、signed raw和status。无ADC与理想计算零分别保留，坏fit没有替换成fitted charge或删除负raw。

这里初版把硬件channel当作历史到当前物理PMT的连接。新增Veto前端核查表明这一假设不能无条件使用，见下文；因此本阶段的 `ideal_pC` **只是当前cable元素的模拟积分**，尚未取得全15路与原RDO同一PMT的认证，不能直接进入去噪声能量实验。

## 实测数值与程序验证

[参考验证](stage184_energy_ml/reference_summary.json)：Stage179原12父202通道全在原容差内，最大绝对差 `4.4344080379232764e-05 pC`，最大容差占比 `0.0018311249224464373`。原4父的前2父×15路另用不变的Stage141逐点卷积独立计算30条，最大绝对差 `3.4690037864493206e-07 pC`，最大容差占比 `0.0007548467587900949`。不是将全时SD沉积当作电荷。

新4父共60通道记录，6条无ADC，10条实际signed raw为负。无ADC的VetoNu仍保留，未当成测得零。[独立读取验证](stage184_energy_ml/independent_validation.json)在另一个作业重读这4父的HITS/RDO，60行raw/status/ideal/窗口等标量完全一致；202个历史参考积分与原Stage179最终表逐项核对。全部身份与输入事件总数闭合。原96父未生产，K/charm本次没有事件内容认证。

## 发现：硬件channel一致不足以连接历史PMT

[原来源真实日志](stage184_energy_ml/original_source_producer_evidence.json)准确对应00000–00009 RDO、Calypso6d6ab70b、OFLCOND-FASER-04、五算法improved timing，Veto kernel norm8890、mean825 ns、sigma3.35 ns、alpha−0.32、n9，与当前计算参数一致。日志同时有 `No channel found for identifier 0x4000000000000000` 警告。仅此尚不能确定历史物理板身份。

[审计原记录](stage184_energy_ml/audit_source_0_summary.json)保留全部实际stored/current id32。旧channel14的id32为1107296256，当前cable channel14为1073741824。ID布局变化本身不证明物理板改变；但对实际四个Veto cable元素分别积分后，得到下表。单位pC，数据直接来自已执行的audit，不是把另一通道指定成事后训练赢家。

| 原row | 原RDO channel14 signed raw | 当前cable channel14理想积分 | 当前cable channel15理想积分 |
|---|---:|---:|---:|
|0|252.94853515625|289.24220467465614|252.60456657734943|
|1|110.51953125|88.21731831569203|110.49245606946165|
|2|0.3108154296875|0|0|
|3|247.6834375|830.0950765972515|247.18873121197697|

这支持优先查历史前端板/PMT映射，**不支持将原差额直接归因于噪声或可恢复clip**；这4父channel14均无ADC==0。实际历史标识到station/plate/pmt的独立解码及其COOL payload连接仍**未认证**，没有在本阶段交换通道、修改原X62、重训或声称定位了原低能失败原因。Stage122只涉及VetoNu/Preshower的历史控制，不因为本发现自动失效；也不能把其硬件连接经验直接扩大到所有detector。

## 成本门、资源与清理

首4父完整GNU进程91.61 CPU s、104.07 wall s、RSS1801496 KiB；其中新reader内部88.137351666 CPU s、100.06441447592806 wall s、ROOT requested bytes8016930 B。逐父日志中的快速积分CPU为0.393270272、0.006017741、0.004551378、0.004857737 s（首父含接口/JIT首次成本），并非完整事件吞吐量。

[原成本门](stage184_energy_ml/admission.json)按完整4父CPU的三倍外推余92父，6321.09 CPU s，超过固定full2200 CPU s；不放宽门，未提交full96。[范围记录](stage184_energy_ml/cost_stop_audit_note.json)将audit限于已测4父、202参考和实际Veto元素身份诊断，audit仍在原1000 CPU s、总4000 CPU s预算内。该外推重复计入每4父启动及逐点验证，不是280来源全队列的实测费用或不可行证明；后续需按独立问题认证同进程多源复用，不能拿快速积分局部计时替代全链成本。

调度查询代码复制阶段号时误改日期常量到1844084000，造成已结束作业的history查询为空；已恢复1794084000并核真实终态，没有重复提交或科学worker失败。两个作业9677043/9677064均exit0，共204 scheduler CPU s、323聚合execute wall s、2 starts/0live；4核12000 MB，科学读数不在登录节点计算。无GPU：Athena读出及这个固定小积分没有GPU执行路径，GPU加速比未测量。

过程资源见[GNU表](stage184_energy_ml/process_resources.json)，嵌套时间不与scheduler相加。物理网络I/O、完整原队列时间、能量拟合成本和改善均**未测量**。[清理记录](stage184_energy_ml/storage_cleanup.json)核终态及队列Iwd后精确归档source/所有日志/GNU/spool到software/stage184，删除已回读核对的重复运输文件；不保存新ROOT/xAOD或波形数组，Stage54原12资产保持。

```bash
python3 ml/stage184_freeze.py
python3 ml/stage184_ops.py submit --phase preflight
python3 ml/stage184_ops.py collect --phase preflight
python3 ml/stage184_admit.py
# admission=false: full96未提交；固定已测支持的独立audit
python3 ml/stage184_ops.py submit --phase audit
python3 ml/stage184_ops.py collect --phase audit
python3 ml/stage184_finalize.py
python3 ml/stage184_validate_docs.py
```

## 阶段结论与下一步

快速同窗积分的数值实现已通过原12参考与原源小样本独立卷积，原HITS路径覆盖也实际存在。**全15路历史PMT回接尚未闭合，去噪声能量增量仍未测量。** 当前前端Veto差异应先区分程序映射与读出误差；不把它当物理增益、离群父删选或新噪声模型的依据。

下一Stage185固定研究历史PMT语义及启动复用：输入本4父真实stored id、原6d6源码/对应字典、该来源04/当前06实际MC cable payload；独立还原station/plate/pmt后核源，不按幅度择配对。只在同一实际物理PMT、原15路/原窗闭合后，用π/K/charm事前固定train验证单进程多来源稀疏selector、身份/内容、CPU/I/O/RSS；保留缺失、全部父和失败，不重复Stage184被成本门拒绝的96独立源进程方案。验收是明确的物理对应、无替代父、实际生产级成本及独立内容复核。

通过后才另冻原队列的状态/实际同窗内容/理想同窗内容能量比较，保持原8层3尾、两低箱及所有原门；不是只用9或4个train比较模型。S0困难侧、真实高幅参考、data/MC条件迁移、背景/效率/加权归一化/相关辅助、乳胶与独立确认仍缺。Stage87保持，整体目标未完成。
