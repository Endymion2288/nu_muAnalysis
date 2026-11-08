# Stage176：实际pz0参考面与μ子粒子出生位置的小型同父验证

## 阶段目标与冻结输入

按用户Stage172新方案，在小型自然父支持上明确pz0的实际拟合参考面S0、已有材料约定及G4主μ在该面前后的源分解；不能用总μ根比例替代辐射位置，不能把源能量机械加回Eν。

[冻结协议](stage176_energy_ml/protocol.json)使用原Stage131/135既定12个train父：原每六层各前2个、原hash顺序，先frame50，其余固定11；无能量风险/clip挑选，不新增独立ν。EVNT/entry、G4 seed、HITS原文件名、私有数字化seed、几何TI12MC04、FTFP_BERT、条件tag06均保持。只编译新增只读observer插件，不重建Calypso。

新增记录包括主μ初始状态、每步pre/post位置/总能量/动能/时间/方向、从主μ直接产生的子粒子出生位置/时间/过程/能量和继承谱系、逐实际DAQ hit的并行出生group。原14字段hit和所有旧observer字段不改、不改变RNG、步长、输运或track信息。直接主μ/子粒子出生group/其他根/未知根分开，不把所有次级都叫辐射光子。

actual ntuple同一次merged-withoutIFT拟合中只读保存每条track的首个TrackParameters的原位置、px/py/pz0、surface名称/type/center/normal和原5×5协方差；按float32界面匹配实际领先轨迹，缺/多重匹配仍未知。仅实际PlaneSurface且单primaryμ才按实际法向计算前后出生侧与G4过面step bracket，不用线性插值得到伪精确过面能量；多个往返均记录，不靠名义z替代逐父面。原逐父材料修正明细未保存；pinned fitter已开启散射与能损不授权重复加回。

资源冻结：4核/12000MB、3并行父、max1job、10000CPU秒，preflight1500/pilot7000/audit1500；MaxRuntime86400秒，无应用短timeout。先一父实际闭合/成本再其余11，禁止自动4032重放。Stage87/原所有门、pz0-only/raw11/typedNaN/signed/status0-only时间/Calo缺失、pz>50GeV/K/角色/reserved/隔离和Stage54保持。

## 首次preflight与实现修正

首次作业9676788.0结束：调度460CPU秒/530execute wall秒、job exit1。新observer构建成功，原frame50模拟/旧谱系精确及实际HITS顺序/ID/能量闭合通过；observer on/off敏感HITS精确保持。HITS共有VetoNu0、Veto50、Trigger14、Preshower20、Ecal258、SCT49条；这只是一个原父的工程验证。

后续digitization和reco成功，ntuple native header的`Trk::SurfaceType`为scoped enum，不能直接`ostream<<enum`，Cling编译失败；ntuple子进程129，尚未产生有效S0测量。此为程序错误，不是物理阴性。已改显式`static_cast<int>`，并按既有native接口方式在PyAthena initialize阶段加载header/StoreGate bindings。原所有日志/资源/报告原字节保存在`software/stage176/preflight_failure.tar.gz`，含失败成本，不删除或冒充成功。

[修正记录](stage176_energy_ml/repair_record.json)固定同一原父、同一已成功编译observer runtime及全部物理输入；重跑额度1040CPU秒从原preflight1500余量支出，不扩预算，不重复已通过且observer字节未变的开/关额外模拟。

```bash
python3 ml/stage176_freeze.py
python3 ml/stage176_ops.py submit --phase preflight
python3 ml/stage176_ops.py collect --phase preflight
# scoped-enum实现错误；保留原字节失败记录后修正
python3 ml/stage176_ops.py submit --phase preflight_repair
python3 ml/stage176_ops.py collect --phase preflight_repair
python3 ml/stage176_admit.py
python3 ml/stage176_ops.py submit --phase audit
python3 ml/stage176_ops.py collect --phase audit
python3 ml/stage176_finalize.py
python3 ml/stage176_validate_docs.py
```

## 实际参考面、出生位置与源支持

[单父实测摘要](stage176_energy_ml/physical_pilot_summary.json)与[完整S0记录](stage176_energy_ml/parent_50_S0.json)确认唯一native/ntuple领先匹配，truth为primary μ（PDG13、barcode5、母ν14/barcode1、truthHitRatio1）。实际PlaneSurface/type4的中心为(−30.2488021851,35.8303031921,17.4449996948)mm，拟合(px,py,pz0)=(174.101089478,−429.976989746,73436.65625)MeV；法向(0.00237071818,−0.00585495628,0.99998004939)。原5×5 covariance保留但不声称覆盖已校准。拟合Eμ(S0)=73.4381973926GeV，不是独立动量输入。

主μ初始总能量89.7286261616GeV；实际前向过面唯一step bracket为76.4370482772→76.4369723046GeV，面两侧距离−0.1407610168→+0.1442441623mm、时间0.0580151896→0.0589658656ns。拟合与过面真值存在单父差异，不能归因于单一能损/程序原因，不能线性插值得到精确过面能量或机械加回Eν。

1345个直接主μ子粒子的出生分类：面前muIoni电子1123、muPairProd电子/正电子各9、muBrems光子1；面后muIoni电子203。这些是出生计数，非独立事例、辐射能损或能量误差总体证据。

| sensitive collection | 直接主μ corrected SD (MeV) | S0前子粒子后代 (MeV) | S0后子粒子后代 (MeV) |
|---|---:|---:|---:|
| EcalHits | 43.6352582060 | 0 | 17.5313202501 |
| PreshowerHits | 6.4625993604 | 0 | 1.7711819899 |
| TriggerHits | 1.5651339460 | 1.0295967981 | 0 |
| VetoHits | 12.7644283324 | 5.6434835895 | 0 |

表中0仅为本父完整hit分区的零支持；全时、已含SD响应修正的沉积**不是同窗analog电荷**。例如此父Ecal附加响应来自面后谱系，而上游Trigger/Veto有面前谱系；不能把μ根响应全部当面前辐射。实际同窗响应、能量误差两侧关联及总体比例仍**未测量**。

## 成本门、独立验证与存储

[成本准入](stage176_energy_ml/admission.json)：修正完整GNU214.27CPU秒，3×214.27×11=7070.91CPU秒，超过固定pilot7000。虽然总10000预算可容纳，分阶段门仍False；其余11保持未测量，没有提交pilot或自动4032生产。

[独立审计](stage176_energy_ml/independent_validation.json)逐标量检查1345出生、4211主μsegments、实际过面bracket、逐hit源partition；全部通过。旧observer字段/ordered HITS精确，observer on/off闭合，旧raw11/status/pz0逐值保持。成功repair没有重做非干涉额外模拟；不将复用工程证据冒称第二次独立物理样本。

[调度账目](stage176_energy_ml/scheduler_accounting.json)共3starts：9676788 exit1、9676831/9676848 exit0，678scheduler CPU秒/831聚合execute wall秒、0live。audit GNU0.12CPU秒/0.19wall秒，scheduler取整0并非零成本。实际申请4核12000MB，只有首父完整链，无并行加速比；GNU repair峰值RSS1854904KiB。[子进程资源](stage176_energy_ml/process_resources.json)含嵌套时序，不重复累加。无能量fit/forward、新独立ν或GPU作业；此类官方链非GPU任务。

[存储审计](stage176_energy_ml/storage_cleanup.json)保留事件/父摘要1036179B、observer runtime3808184B；删除40589451B运输/重复日志/spool，先核当前队列Iwd。失败原返回包及原日志分别精确保存在`software/stage176/failed_worker_result.tar.gz`与`preflight_failure.tar.gz`；源版本、GNU、日志、终态spool分别存source_snapshots/execution_audits/worker_logs/terminal_spool档案。未提交的错误audit打包目录明确记录且清除，未作作业计数。12个原Stage54资产size/mtime保持。[文档验证](stage176_energy_ml/document_validation.json)核协议原字节、用户研究文件、链接与语法。

## 阶段性结论与下一步验收

本固定首父证明实际S0、出生位置及过面bracket可观测，不能证明总体修正或能量收益。原完整重建方案因成本门结束，不增加预算继续原实现。

下一Stage178先验证新的成本实现：pinned fitter构造的是以拟合位置为中心、法向沿拟合动量的curvilinear PlaneSurface。用原compact位置/px/py/pz0的float32舍入单元包络构造面侧符号区间；必须先证明源码语义、实际首父native落在包络内、出生/过面符号与实际面一致，跨0或缺状态保持unknown。仅通过后另冻同原11父的G4-only重放预算，复用已认证observer和旧谱系/ordered HITS，不重做digitization/reco/ntuple，不称rounded状态为exact面。输入为原matched_input、生产清单和本阶段首父native/lineage；验收为严格区间与实际面闭合、完整分母及成本，不是放宽Stage176门。

足量源支持后再进入匹配几何/通道/窗口的analog相加、统一噪声/量化/clip干预。可测伴随量、真实系统/高幅参考/双量程、最终独立确认仍缺；Stage87/原全部能量及尾部门保持，整体目标未完成。
