# Stage197：真实低pz重建支持与VetoNu辅助电荷缺口

执行日期：2026-11-08。依据[Stage187谱路线§7.1](2026-11-08_stage187_post-readout-research-roadmap.md#71-用已有观测定义可审查的前向响应)，目标是测实际选中样本的探测器层分布，重点看原pz0>50GeV下50–100GeV支持，并检查与原calibration MC的观测支持交集。**本阶段实际取得最终VetoNu veto之前的重建切流；最终选择和MC交集未测量，不能把已确认通过0条写成真实零候选或零ν产额。**

用户随后明确：“目前没有，可以暂时空置，之后如果有了我再做”。按此要求，VetoNu辅助输入与相应独立LED/MIP/转换控制保持待补充；不继续寻找其他私有目录、补造输入或为同一缺口反复询问。该具体分支暂留空，整体研究不标完成。[输入状态](stage197_energy_ml/input_status.json)保存这一决定。

## 原目标、冻结输入与不变项

[协议](stage197_energy_ml/protocol.json)起点为Stage196提交`7c494fd`，原知run15838的16份PHYS总header记录14237355条，路径继承[Stage167目录证据](stage167_energy_ml/inventory.json)。本阶段**只实读首份**`/eos/experiment/faser/data0/phys/2024_back/r0022/015838/Faser-Physics-015838-00000-00049-r0022-PHYS.root`的前8192条，两块4096；其他15文件及首文件其余事件均未读科学payload。

使用原`AnalysisZipFramework/config/ml_low_energy_cuts.yaml`、`definitions.yaml`和`Analyis.cxx`的DATA/ALL选择，沿用Stage166真实run15838 GRL inclusive秒区间。原leading按Track_pz0 argmax，pz0由MeV→GeV；不读p0/p1/pz1，不生成额外一次方动量。原阈值选择继续依赖其既有fitted-charge字段，**新增展示量使用raw charge**，没有在本阶段悄改原筛选。px0/py0只用于原Theta；没有arrival/lag/late fraction或其他新timing。

原isCaloNuPeriod真，GoodVetoNuStatus保留(0/1,0/1)或(0,16)，Veto20/21排528；这只是既有选择，不把status1/16/512升级为可用timing。原TimingOK的`(status & ~512)==0`也只用于既有aux信任/fallback逻辑，未据此提取时间。原轨迹质量/空间切流逐项保持，VetoNu最终阈值之前不增加“μ纯度”或低E挑选。

拟定新观测仅pz0、Veto10 signed raw charge及IFT nClusters0；固定边界和缺失格见协议，没有选择最佳bin或加入run/trigger作能量标签。原计划仅MC role2、所有组分/K的条件支持，不读truth作选择、不读隔离/reserved、不fit或forward；**因未准入，本阶段实际MC读取N=0**。未输出任何MC/data响应比、似然、模型校准或能谱。

提交前核对`analysis.cxx`实际`addAuxFiles("tree", auxFiles)`，将最初草稿的猜测tree名改为真实`tree`；在任何本阶段事件读取/提交之前完成，[修正记录](stage197_energy_ml/prepilot_source_correction.json)和各提交源码字节可核。未在观察结果后换tree、目录、阈值或研究问题。

## 实际切流与低动量支持

输入首文件N=780874，实读原前8192条；所有run=15838。所有必需Track/charge/raw/status和nClusters0分支实际存在，**原生VetoNu0/1_reduced_charge均不存在**，完整实际schema映射见[pilot结果](stage197_energy_ml/pilot_summary.json)。

| 累积选择 | 通过读出记录N |
|---|---:|
|input|8192|
|colliding|8101|
|trigger|8101|
|GoodTimes|8101|
|notExcluded|8101|
|longTracks|8101|
|CaloNuStatus|7872|
|Veto2|7758|
|TimingCharge|7757|
|Preshower|7744|
|pz0_gt50|6351|
|layers|6190|
|nDoF|5941|
|chi2|5907|
|rMax|2730|
|rIFT|2647|
|rVetoNu|2647|
|theta|2647|

最终VetoNu veto之前2647条，其中pz0=50–100GeV为351条，pz0≥100GeV为2296条。它们经过谱仪质量和几何选择，但尚未经过上游VetoNu veto，含穿透μ及未知背景，**不是ν候选清单或低真E样本**。低reco pz与低真E不同，不由351条声称解决原真E=50–100GeV模型劣势。

全部2647条因辅助电荷未知而最终选择状态未知；最终低pz通过数、总体候选率/背景率、selected detector-level分布和MC支持交集均为**未测量**。pilot JSON中的`observed_selected_N=0`是“确认selected记录0、unknown2647”的程序记账，不能作为产额测量。没有用raw-only veto替代原reduced+fallback，也没有将unknown当vetoed或把缺失填0。

展示raw11按原wave-invalid mask392清理，fit-failure不使raw自动缺失；保留合法signed负值。计数的负值、非整数和uint sentinel无效转null。原fallback使用其实际原raw值，不用清理后的数值悄改选择；当前缺aux使fallback实际未评价。实际占位值频数、最终特征总体分布和源分类本阶段**未测量**，不据本阶段改旧typed NaN或signed规则。

## 实际aux访问结果与解释

配置指向`/eos/user/b/bewilson/El9CalypsoForWaveForm/WaveformsCaloNuPeriod/015838`。只对此run路径执行一次非递归listing：

```bash
xrdfs root://eosuser.cern.ch ls /eos/user/b/bewilson/El9CalypsoForWaveForm/WaveformsCaloNuPeriod/015838
```

返回exit54，服务器为`[3010] Unable to open directory ...; Operation not permitted`，见[实际返回](stage197_energy_ml/aux_inventory.json)。这证明本次访问被拒绝，**不证明目录或样本不存在**。没有读取任何辅助ROOT、header或电荷行；`paths=[]`是未取得清单，不是测得目录为空。审计没有再次listing、猜测其他用户目录或换版本。

原框架aux需要`tree`中的run/event和`myVetoNu0_rawCharge35`、`myVetoNu1_rawCharge35`，精确匹配后才可判断原TimingOK、2024 zero+raw>30有效性、reduced<30pC及无效时raw<40pC fallback。缺少这项可访问的真实输入时，现有PHYS与GRL无法独立重建同一个最终选择。根据用户回复，该输入暂时留空，之后由用户取得再继续。

## 成本准入与停止范围

新独立预算20000CPU秒，pilot/full/audit上限400/16000/3600，不扩大前阶段预算；最多1个8核/24GB请求，拟full四个文件进程、每进程解压/解释1线程。实际只执行pilot和audit，无full多核处理。运行LCG109 GCC15（实际Python3.13.11），没有新Calypso构建、GPU、G4、digi/reco、能量fit或模型forward；小样本I/O/逐行提取没有GPU加速基准。

pilot两4096块CPU分别4.922960242/7.000885274秒；原文件内部12.42067257CPU秒/13.8714486wall秒，ROOT实际请求3310176B，峰RSS91492KiB。完整GNU为14.3CPU秒。基于慢postfirst块与固定14237355记录的三倍保守投影为**73046.38313CPU秒>16000**，且原预算不能同时容纳，故[准入拒绝](stage197_energy_ml/admission.json)。这一外推不是实测full成本，也不是不可优化的理论下界；未为追求全量而抬预算、删除父或替换选择。

本实现逐条组装2647个原始控制记录包含实际Python/Awkward标量访问，属于后续可优化的实现点；本阶段未做受控profile/加速比，不能给它分摊一个未经测量的耗时比例。即使加速通过，仍缺实际aux，无法据此取得最终选择。按用户决定不重跑该分支或追加数据版本；本次固定pilot包结束。

[完整进程资源](stage197_energy_ml/process_resources.json)与内部时间分别保留，不重复加总：

| 进程 | GNU总CPU/s | GNU wall/s | 峰RSS/KiB |
|---|---:|---:|---:|
|audit_time|45.93|49.98|105544|
|pilot_time|14.3|17.79|91492|

## 独立验证、执行命令与清理

[独立审计](stage197_energy_ml/independent_validation.json)重新读同8192条原PHYS；另一套`math`/Python逐记录原选择实现验证全部8192条的累积切流，原2647条身份/raw/status、351条低pz计数与prefix64逐值精确。不是只从原JSON复述计数。读取和公式路径独立，实际阈值结果完全相同；没有据此认证MC/data响应、background purity或真实误差覆盖。

审计内部44.65540859CPU秒/46.3432514wall秒；数据重读不重试私有目录，既有服务器拒绝文本按原字节保留。未运行full/audit-full或MC代码，未把这些未执行路径称为已验证生产工具。

```bash
python3 ml/stage197_freeze.py
python3 ml/stage197_ops.py submit --phase pilot
python3 ml/stage197_ops.py collect --phase pilot
python3 ml/stage197_admit.py
# admitted=False，不提交full
python3 ml/stage197_ops.py submit --phase audit
python3 ml/stage197_ops.py collect --phase audit
python3 ml/stage188_finalize.py 197
python3 ml/stage197_document.py
python3 ml/stage197_validate_docs.py
```

两cluster9678786/9678798，实际2start、全exit0、61累计调度CPU秒/78聚合execute wall秒、0live。full成本门拒绝是准入结果，不是失败作业，未隐去实际访问被拒绝。终态spool/源码/原worker/descriptor、完整GNU/log/历史标量逐字节归档`software/stage197/`，留353246B<8MiB紧凑pilot控制，清理812224B重复包/日志；无ROOT/xAOD持久副本。原Stage54十二资产size/mtime不变；用户其他未跟踪文件未操作。

本地只源码/标准文本/返回标量渲染/调度/精确字节归档；ROOT/gzip科学读取、统计与审计均在HTCondor。首次本地系统Python3.9不接受现代starred subscript语法，而实际LCG109 Python3.13 AST及pilot均通过；后续将该处改成兼容的tuple表达式，未改变算法、数据或预算。最终系统Python AST、bash语法、JSON/TSV、报告链接、历史入口后缀及Git whitespace检查见[验证](stage197_energy_ml/document_validation.json)。

## 全路线状态与后续验收

[完成审计表](stage197_energy_ml/completion_audit.tsv)按实际研究要求区分完成的有限实验与未取得的最终目标。A的IFT内容新训练阴性已结束、主μfit身份诊断完成；C的固定signed组成表示阴性；F有真实status0形状与原生MC时间支持但源未识别；有限双量程支线没有识别任意幅度下的真实误差/非线性。B的实际LOS与active支持、D真实转换/overlay/测试束、E2025四像素平面/匹配MC，以及真实谱的背景、权重/完整效率、匹配曝光与相关辅助仍未认证。目录或文件名不能填补物理支持，已开发的条件谱toy也不替代实际数据结果。

用户保留待补充输入后，本分支不再自动继续。未来若用户取得可访问的同run aux清单/副本，应先核原身份与duplicate/缺失、原reduced/fallback选择和status，再以实际成本单独冻结一个改进实现的小pilot；验收是同选择最终候选数/低pz支持、raw/occupancy固定条件分布和原role2/K MC支持交集。无背景/曝光/加权接受度时仍只报含背景探测器层分布，不报ν纯度、flux/截面或完整能谱。不可追溯放大Stage197预算。

LED/MIP/源标签与转换控制同样按用户决定待补充；其他支线仅在相应真实输入到位时继续，不把全部候选串作前置或重新扫描旧模型/窗口/seed。原Stage87、全部K、角色/reserved/隔离、pz0-only/raw/typedNaN/合法负值/严格status0 timing和原八层三尾/双低能全部门保持。**整体低真E优于传统、真实标定及完整物理谱/独立确认仍未完成。**
