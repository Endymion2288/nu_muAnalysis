# Stage185：历史物理PMT认证与同进程多来源读出

## 阶段目标与输入

修复Stage184暴露的历史硬件channel到当前PMT连接问题，并认证一个可减少重复Athena初始化的原HITS读取路径，为Stage172 §7的实际/理想同窗能量对照提供前置条件。不是再做一次Q89/T78、普通Calo raw4比较或12父能量训练。

[协议](stage185_energy_ml/protocol.json)冻结π/K/charm原请求0/48/113各前4个原train，共12父、15路；沿Stage184事前来源选择，不按真能量、风险、clip或电荷相似程度选父。原HITS/RDO、实际身份和原角色保持，没有隔离/reserved输出、新G4、重建或能量fit/forward。

输入包括Stage184实际stored id、原源日志、对应源码字典和旧标量控制。三个确切RDO日志均确认6d6ab70b、五算法improved timing及对应输出文件名，见[source0](stage185_energy_ml/source_0_producer_evidence.json)、[source48](stage185_energy_ml/source_48_producer_evidence.json)、[source113](stage185_energy_ml/source_113_producer_evidence.json)。

## 历史字典认证与实现排错

从6d6ab70b精确提取日志指定的FASER/Scintillator/Neutrino730/TrackerInterface/Calorimeter XML，组合为[独立解析输入](stage185_energy_ml/IdDict_6d6ab70b.xml)；源路径、commit、字节数在协议。XML保留上游原字节（含行尾空白），仅对此精确文件用.gitattributes关闭行尾空白告警。没有将旧ID交给当前扩展字典，也没有因为当前FaserDetectorID要求新Muon/VetoGm标签而反复初始化不兼容的旧helper。

[解码实现](../ml/stage185_identity.hxx)只使用独立IdDictParser：在字典实际声明区域内逐字段解码，检查声明取值范围，并要求唯一的完整compact→字段→compact逐位回环。区域匹配依据字典与标识，不依赖幅度或波形。

两次程序失败完整保留：[修正记录](stage185_energy_ml/identity_decoder_repair.json)。首轮错误使用通用带prefix的unpack接口处理完整compact ID，原回环门失败；没有作物理归因。详细诊断版本又把ExpandedIdentifier直接输出到不支持的ostream，Cling编译失败后ROOT退出报signal，实际exit129。修正为字段接口后原门通过，没有换字典、放宽容差或改输入。首轮9677080为exit1/13 CPU s，诊断9677089为exit129/32 CPU s；成功9677095为exit0/19 CPU s，均计入原500 CPU s身份额度、总2400 CPU s预算。

接口诊断参考公开[IdDictMgr实现](https://github.com/rolandjansky/athena/blob/master/DetectorDescription/IdDict/src/IdDictMgr.cxx)的pack/unpack函数；它是API解释材料，不冒称当前安装二进制的逐字源码。实际认证在pinned runtime执行。

## 认证结果：原channel14是前端第二片

[历史物理通道表](stage185_energy_ml/historical_physical_channels.tsv)11路全部唯一回环。关键结果如下，所有station/plate/pmt均无量纲索引。

| 原通道 | detector | 原stored id32 | station | plate | pmt |
|---|---|---:|---:|---:|---:|
|14|Veto|1107296256|0|1|0|
|6|Veto|1140850688|1|0|0|
|7|Veto|1174405120|1|1|0|
|8/9|Trigger|1224736768/1207959552|0|0|1/0|
|10/11|Trigger|1258291200/1241513984|0|1|1/0|
|12/13|Preshower|1342177280/1375731712|0|0/1|0|
|4/5|VetoNu|1476395008/1509949440|0|0/1|0|

原channel14因此接到当前 `(0,1,0)` 物理元素（当前cable channel15），而不是当前channel14的 `(0,0,0)`。这不是将原观测换成另一条原观测：原RDO channel14的ADC/raw/status保持，只把其HITS模拟积分指向同一实际PMT。

[真实条件查询](stage185_energy_ml/identity_summary.json)在三个实际MC run200082/200083/200089对04/06各查询一次：分别解析CableMapping-00/-01，当前两tag均为channel14→plate0、15→plate1。因此不能把历史差异归因于这两个tag的当前切换。当前DB快照不是历史payload字节；历史数据库字节仍未取得。直接解码实际保存标识提供了本次物理连接证据，不声称恢复了整个历史数据库。

对原4个π事例，修正后对应PMT积分为252.60456657734943、110.49245606946165、0、247.18873121197697 pC；实际raw分别252.94853515625、110.51953125、0.3108154296875、247.6834375 pC。原row3当前错误元素的830.0950765972515 pC不能当成可去除的读出噪声；物理回接后对应量247.18873121197697 pC才适合作为后续同PMT干预输入。没有以这些4父估计总体噪声方差、恢复区间或能量增益。

## 同进程三来源与数值验证

[执行代码](../ml/stage185_native.py)先独立核30个HITS CollectionTree总条数，每来源10000父；在同一Athena accumulator连接原π/K/charm文件，使用实际总数构造global entry和稀疏SkipEventRanges。逐父实际run/event、incoming float32、原entry/row/source/role精确检查；跨来源不按event-only碰撞联结。实际RDO硬件标识用原字典解码到物理PMT，再在当前几何找唯一对应元素，Trigger保留PMT端索引。

原scint780–980 ns、Ecal780–930 ns，2 ns采样含端点，不扫窗。15路原窗口、raw、status、缺ADC及合法负raw保留；窗口是采集定义，不是赋给坏fit的物理到达时间。理想积分使用Stage184认证方法及未变的32float32eps容差。每来源前2父×15路，另做90条未改Stage141逐点卷积。

批量小样本已取得12父/180通道。独立审计、通道误差统计及全部实际测量以[验证记录](stage185_energy_ml/independent_validation.json)、[同窗通道表](stage185_energy_ml/charges.tsv)、[原4父修正表](stage185_energy_ml/channel14_physical_correction.tsv)和[通道摘要](stage185_energy_ml/response_summary.tsv)为准。

独立审计已通过：4原父60路raw/status/可用性与Stage184精确，56路未改理想积分精确，4路物理回接与原诊断第二片积分精确。90次literal最大绝对差1.7762271454557776e-05 pC，最大容差占比0.0007548467587900949。全部12原身份/incoming/源总数精确，未剔除缺ADC或负raw。每路12条中VetoNu两路各只有7条实际ADC；Veto14/6/7有rail记录4/3/3条，raw−ideal最大绝对差分别37858.40967414883/24832.805735948063/15474.366040512396 pC。这里只报告固定train支持，不估总体比例。

运行时FPE auditor记录的overflow/invalid警告保存在[原警告](stage185_energy_ml/runtime_warning_evidence.json)。原父未因此删除，快速/逐点最终积分仍按原门核查；具体中间计算与fit警告机制未独立分类，不能将警告当作物理异常或能量失败原因。

## 成本与执行范围

12父完整GNU83.92 CPU s、201.99 wall s、RSS1871468 KiB；内部79.864634254 CPU s、194.124403744936 wall s、ROOT requested103130940 B。到首次execute为31.473090369 CPU s、137.672331440961 wall s；**第一个execute另含40.902990979 CPU s首次接口/JIT及事件成本**，不能将其全算作稳定事件吞吐量，也不能只拿31.47 s当完整初始化成本。逐父成本与literal费用见[事件资源](stage185_energy_ml/event_resources.tsv)。

[小样本资源准入](stage185_energy_ml/batch_resource_admission.json)使用Stage184完整4父91.61 CPU s×3来源×3保守倍数=824.49 CPU s，在本轮batch1200 s内；没有复活Stage184被拒绝的96独立进程方案或抬高其旧预算。当前同进程只初始化一次，3来源已实际验证；与旧4父的来源/逐点验证数量不同，受控serial加速比、全280来源I/O/CPU和能量训练费用均**未测量**。

所有科学ROOT/字典/积分/统计/重读通过 `~/condor/nu_muAnalysis/stage185/`；本地仅源码、日志、运输与文档。这个12父共享初始化pilot使用单Athena进程，申请4核12000 MB不冒称已用满4核。大规模下一阶段应在已认证单进程多源读取外再并行多个进程，用实际CPU/I/O/峰值确定并发，不凭GPU可用性把无CUDA实现的POOL/digitizer搬上GPU。

全部5个终态start（两次程序失败）合计262 CPU s、520聚合execute wall s，当前0live；仍在2400 CPU s原预算内。归档核验后清理340472 B重复运输与日志，新增事件cache为0 B。完整终态作业与含失败资源见[scheduler](stage185_energy_ml/scheduler_accounting.json)，GNU与scheduler嵌套不相加；物理网络流量未测量。[清理](stage185_energy_ml/storage_cleanup.json)在核终态/Iwd、原字节归档后删除重复包/日志/spool，源版本及两次失败完整保留software/stage185。不保存新ROOT/xAOD/ADC数组，Stage54原12资产保持。

```bash
python3 ml/stage185_ops.py submit --phase identity
python3 ml/stage185_ops.py collect --phase identity
python3 ml/stage185_ops.py submit --phase identity_repair
python3 ml/stage185_ops.py collect --phase identity_repair
python3 ml/stage185_ops.py submit --phase identity_fix
python3 ml/stage185_ops.py collect --phase identity_fix
python3 ml/stage185_ops.py submit --phase batch
python3 ml/stage185_ops.py collect --phase batch
python3 ml/stage185_ops.py submit --phase audit
python3 ml/stage185_ops.py collect --phase audit
python3 ml/stage185_finalize.py
python3 ml/stage185_validate_docs.py
```

## 阶段结论与下一步

历史11路实际物理PMT已独立认证，原channel14回接必须尊重其plate1身份；原HITS可在同进程跨π/K/charm读取，保留完整选择/身份和实际PMT。这解决了进入去噪声能量干预的一项程序前置，**不是已测低能能量改善，也不是原Stage87模型错误的证明**。原X62、实际raw11和Stage129波形恢复没有在本轮修改；Stage179是当前重新生产父、实际ADC已精确闭合，不把其结果套成历史源连接证明。

下一Stage186应完成有意义支持上的实际/理想能量比较：原89033身份、71376active、全部K/角色/隔离/reserved保持；先用已知源的producer与实际旧标识认证原输入及新增字段，再测生产级多源/多进程成本。状态单独对照、实际同窗积分对照与理想同窗积分三臂使用相同支持/容量/固定3seed学习政策，原Stage87作强基线；实际积分对照承认已有raw11/Calo raw4，不包装成新物理信息。所有新增表示须从头训练，报告两低箱和全部8层3尾、原门、paired incoming区间及真实缺项。

若不同源缺少可认证producer/PMT，原父保持、追加测量明确缺失，不按有利能量替换源；新cal/test特征与风险只在合同/成本准入后提取。无噪声模拟输入只回答条件信息增量，不部署为准确测量，不宣称Bayes上限或真实data迁移。完整资源上限与验收见[下一合同](stage185_energy_ml/next_execution_contract.json)。

S0困难侧/材料约定、独立高幅参考、真实响应与相关辅助、物理背景/效率/归一化、乳胶及独立确认仍缺。原最低能优势、Stage87/所有原门保持，整体目标未完成。
