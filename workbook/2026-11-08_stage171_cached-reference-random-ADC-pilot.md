# Stage171：单次参考解压后的严格随机联合ADC pilot

## 目标、输入与冻结合同

Stage170提交`577d5ef`后按[冻结协议](stage171_energy_ml/protocol.json)修正参考NPZ循环重复解压：每个所需成员只加载一次，循环外按file_index=2取56例，gzip运输用compression1。Stage170原成本门与未执行8192的历史保持，不改其阴性准入。当前新阶段同样1200累计CPU秒、smoke300/pilot600/audit300、2核4000MB/max1job/MaxRuntime86400秒；不以性能修正增加物理规模或改变选择。

固定同run15838 RAW00400、原Stage43参考、Stage166 GRL、Stage170官方header与**同一个C++reader**。smoke要逐字段和全部硬件ADC复现`ntuples/energy_ml_stage170/smoke_rows.jsonl.gz`，另独立核原Stage43四路62720 ADC code。随后完整GNU CPU三倍8192/56加已用与300audit reserve门通过才pilot；pilot同前8192 PhysicsTag/16384frames/128MiB边界，严格唯一有效TLB TAP=TBP=16，不加input bits零要求、不按电荷/status/尾删样本。保存原56和最先8个严格控制全部实际PMT通道。GRL/两板/同硬件集/等长度及至少4控制支持通过、独立重读精确后，才支持后续联合统计另冻合同。

全部科学解析/数组/统计通过`~/condor/nu_muAnalysis/stage171/`；本地只源码、调度、精确归档和文档。没有新G4/重建、ROOT payload、能量fit或forward。Stage87和全部原门、pz0/raw11/typedNaN/合法signed/status0-only timing/Calo缺失、pz>50GeV、全部K、角色/reserved/quarantine及Stage54资产保持。

## 执行命令

```bash
python3 ml/stage171_freeze.py
python3 ml/stage171_ops.py submit --phase smoke
```

## 执行修正与完整账目

初次smoke job9676543.0 exit0、schedd CPU4秒/wall10秒，GNU科学进程CPU0.96秒，但输出CACHE误留Stage170目录，写输出后才读取的Stage170 reference变成自身比较。因此该项原56全硬件比较无效，初次准入仅作[被取代记录](stage171_energy_ml/initial_admission_superseded.json)，不据此启动pilot。原Stage43独立四通道比较仍执行，但不能代替被破坏的全硬件reference。

收集后立即将新字节迁到Stage171缓存，从冻结smoke输入包**精确恢复**Stage170原429481B gzip，修正CACHE并禁止输出目录等于reference目录。记录见[修正说明](stage171_energy_ml/smoke_execution_correction.json)。随后smoke_retry job9676548.0在原smoke300秒剩余296秒内重跑；不增加原1200预算，不隐藏初次已完成运行。pilot此前打包发现预期新路径缺失而失败，没有调用condor_submit或发生8192扫描；未完成运输包在最终归档清理时计入删除。此处为程序路径错误，不解释成物理或ADC问题。

修正重跑smoke_retry成功终态，原56全部硬件ADC/身份/触发/board与恢复后的Stage170逐值相等，原Stage43四路62720 ADC code独立相等，最大差0 ADC。完整GNU CPU1.05秒，三倍投影460.800000秒，加已用8秒和300秒audit reserve在1200预算内，[最终准入](stage171_energy_ml/admission.json)True。此时才提交pilot9676555.0。与Stage170完整CPU4.39秒的差为3.34秒，但同时改变单次加载、gzip压缩级和附加reference检查，不把它称为单独解压的受控因果加速比。

```bash
python3 ml/stage171_ops.py collect --phase smoke
# 路径问题后的纠正重跑，仍在原smoke余量
python3 ml/stage171_ops.py submit --phase smoke_retry
python3 ml/stage171_ops.py collect --phase smoke_retry
python3 ml/stage171_admit.py
python3 ml/stage171_ops.py submit --phase pilot
```

## 有限pilot实测与支持边界

[8192摘要](stage171_energy_ml/pilot_summary.json)实读69200748B、8192 raw/PhysicsTag，时间1720473060859252–1720473064991134 μs，包络4.131882秒。8192个TLB唯一有效，0坏/缺失/歧义，严格TAP=TBP=16恰4例，未因status2剔除：全部4例status2；全8192的status2/0为7958/234。

4严格控制raw entry为1284、3724、5956、8163，eventID为13815007、13817447、13819679、13821886。实际两板均有效无board-fail，通道集为0–23及31，25通道、各280采样；不将硬件31猜为某个探测器或自动移除。4例current/next input bits均0，但它不是事前筛选条件；4例均通过原Stage166时间GRL。原56prefix及Stage170全部硬件ADC/元数据、Stage43原62720 ADC code均精确。reader子进程CPU0.878244秒/wall1.290765秒，Python CPU1.003653秒/wall1.893612秒，reference单独CPU0.148496秒。

该结果使联合控制在本有限支持上“可用”，但只有4个随机事例，25维经验协方差秩最多3；尚未计算该协方差，不可假设独立通道、可逆高斯误差或全run校准。随机不等于无物理活动/纯电子noise，GRL通过也不提供曝光或ν背景纯度。独立重读job9676558.0已提交，只有独立验收后才冻结后续有限统计。

## 独立重读与审计补完

job9676558.0已完成第二次RAW读取：8192逐行身份/TLB/元数据及60个保留事例的全部硬件ADC与pilot精确，另写独立标量严格触发选择同4例，[独立回放证据](stage171_energy_ml/independent_validation.json)通过。这里独立的是第二次实际读取及标量选择实现，共享官方decoder，并非另一套硬件解码器。

该worker随后因传输包漏带`pilot_summary.json`而在补充evidence步骤exit1，不能把整个audit记为exit0或隐藏这次执行。补入原摘要及已保存pilot/audit rows，提交job9676562.0只完成原标量统计和科学rejoin；**不重复RAW扫描**，296秒来自原audit300秒扣该次schedd4秒的余量，原总预算不变。程序原因与物理支持分开，最终验收须连同补完job终态记录。

## 最终验证、资源、存储与结论

补完job9676562.0 exit0，[审计完成](stage171_energy_ml/audit_completion.json)、[控制证据](stage171_energy_ml/control_evidence.json)、[科学rejoin](stage171_energy_ml/storage_rejoin.json)全部通过：8192 TLB均header4272750752/version2/valid；严格4例status2、input bits0/0。严格占所读PhysicsTag为0.00048828125，仅为有限控制的事例比例，**不是活时间、物理接受度或效率**。

[最终资源与清理](stage171_energy_ml/storage_cleanup.json)共5提交/5start，含首smoke参考自比较失效和audit补充metadata的exit1，后续修复均保留原资源；schedd总CPU17秒/聚合execute wall44秒、0live/GPU/G4/fit/forward。完整科学进程GNU CPU依次为smoke0.96、retry1.05、pilot2.15、audit2.41、finish1.79秒，编译另2.54/2.46/1.51/1.42秒；不把这些和schedd相加。请求2核4000MB，schedd实际RequestMemory6000MB；峰值进程RSS186128KiB。没有测量受控多核/GPU加速比。

原smoke/重跑/audit与pilot的全部字段和ADC经worker科学精确rejoin后只留`ntuples/energy_ml_stage171/pilot_rows.jsonl.gz`1021640B。删除16482236B运输、重复rows、GNU/log/spool及一次未提交的部分package；部分包里的源码版本同样精确归档，不隐藏未提交历史。71逻辑源版本按内容唯一存27份；Stage170原429481B reference由冻结输入包恢复并逐字节验证。无ROOT/xAOD/持久化reader二进制，无SHA；Stage54原12文件size/mtime通过，清理前核终态和队列Iwd无引用。文档静态验证见[验证记录](stage171_energy_ml/document_validation.json)。

**本阶段证实严格随机控制有25通道联合ADC可读，但不等于已校准噪声或μ响应。** 仅4事例与4.13秒支持不足以认证25维协方差；硬件31保留，实际物理mapping未知。没有能量风险/谱精度新收益，Stage87和原完整门/角色/K保持，整体目标未完成。

下一[Stage172合同](stage171_energy_ml/next_execution_contract.json)限定Stage167已实际列出的同run RAW400–431共32文件，各固定前8192 PhysicsTag（最多128MiB/16384frame边界），400/401先pilot，过成本门才4进程其余30，再原两文件独立重读。2400CPU秒/4核8GB，无目录发现/全文件生产/能量模型。保留全部严格控制至每文件256事例，坏/缺失和超上限明确未知，不按幅度删；固定pre[0:40]、signal诊断[60:140]、offpulse[180:256]的signed ADC积分，全部25硬件相关描述及CaloNu四路固定和方差比/1000file-block区间，另前16/后16稳定性。实际新通道数/统计量/区间与成本未测量；不反演协方差、不造prior、不把随机当纯noise，不做模型注入。该合同推进真实相关响应辅助量，不替代gain/timewalk/宽μ辐射尾、背景接受度、乳胶或独立ν确认。

```bash
python3 ml/stage171_ops.py collect --phase pilot
python3 ml/stage171_ops.py submit --phase audit
python3 ml/stage171_ops.py collect --phase audit
python3 ml/stage171_ops.py submit --phase audit_finish
python3 ml/stage171_ops.py collect --phase audit_finish
python3 ml/stage171_finalize.py
python3 ml/stage171_next_contract.py
```
