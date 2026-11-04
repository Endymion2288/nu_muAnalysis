# 下一轮执行 Prompt：stage100 仅补齐丢失的A信息classifier与配对证据

先读AGENTS.md、[stage99报告](../workbook/2026-11-04_stage99_energy-ambiguity-and-activity.md)、路线§81、信息计划§61及stage98研究复盘。stage99 A已完成，B collection已测；A classifier在已完成fit后因XGBoost sklearn保存失败丢预测，B classifier保留。**本轮只补这一个A，不重做stage99两个fit、T优化、ROOT或能量实验；不自动进入stage101。计算和QA在有环境的batch节点，当前本地终端不恢复CERN栈/复现事件。**

## 1. 固定事实与研究边界

stage99共同pz支持test的direct/E94/stage92 AUC=.975092/.976727/.973852，但E94名义2%cal_select阈值实际L误判4.754309 [1.121885,10.158808]%、H识别91.725663%。低E风险增量.054973752，低pz真高E风险减少3.113340137，是修正权衡，不是Bayes界。唯一T=1.08691603355已使test NLL/coverage改善，点不变；不续温度/先验/局部校准，也不自动新NLL checkpoint训练。

B原2048 incoming/24source，1923 PHYS可读/125历史删源，1770单轨迹；实际原生ID/covariance/active readout未测。42维PHYS collection几何相对原端点弦线族已经提取，缺源/K身份和原62均保持；弦线不是拟合轨迹，SP entries不是唯一cluster/粒子，纵向量仅被支持的可见部分，不认noise/强子。原REC scratch只发布PHYS后清理、merge在ntuple阶段临时生成；同名官方6d6ab70b REC不等于原d32b0ff3 track/TSOS。不要重新定位扫描/重建、强配hitSet或造pull。

两格各已实际fit一次。9667677的A在save_model报`_estimator_type undefined`，没有保留可用A预测；9667683只完成剩余B，改为`get_booster().save_model`且先持久化预测。B cal N66/L20/H46、logscore .346455633 [ .252028743,.462819455 ]、Brier .101254665 [.061707997,.150646988]，AUC .929891304；这些不能替代B−A。0/20低能误判及bootstrap[0,0]不能认证2%总体保证。

原stage87 split/同incoming总权重1、train/cal/test46575/11612/13189及唯一37556/10811/12125、全部1016新增K和missing21/6/5/困难侧保持。一次方动量pz0-only，允许原px/py/q/p/弯折；raw11/status、合法负raw/charge与module_eta −1、typed NaN/Calo缺项、pz>50GeV不改。test是开发池，不是新blind；source95/重训/校准估计/response/研究选择区间仍未覆盖。最终原1.05/1.01/1.03与八层三向tail+2pp不改。

## 2. 唯一实验：一次冻结A，和已保留B做配对

输入：

- 原`ntuples/energy_ml_stage95/cohort.json`、原事件/候选身份表；2048一incoming一视图，只有原train/cal。
- `ntuples/energy_ml_stage99/{B_collection_features,B_identities,B_classifier_predictions}.tsv`及`ml/artifacts/stage99/B_classifier_B.json`；不覆盖B。
- 原62缓存stage55 dataset/stage56 readout和stage70/81/82/83 support；`ml/configs/audited_features.json`。
- `ml/stage99_bfinish.py`是B实际baseline和标签/角色/threshold实现；`workbook/stage99_energy_ml/{activity_contract,B_failure,B_complete,B_class_support}.json/tsv`及metrics/ROC工作点。

A输入严格匹配B中共同分支：62 audited值、62 missing mask、原status_other一列、PHYS collection可用一列、exact native可用0一列，共127列。B再加42值/42mask；本轮不改A定义、B输入/模型/预测。所有2048身份保留可用性报告，classifier域为观测50<pz0<100且诊断L=真50≤E<100、H=真E≥200；中间100–200只在支持分母保留。原train L/H65/82、cal20/46必须闭合，不按truth重选队列/来源；truth只标签。

唯一A XGBoost hist：seed2026110499、depth2、100trees、eta.05、min_child_weight10、lambda10、nthread1；原train147拟合，cal66评价。无earlystop/超参/seed/重启动，无B再fit或原stage99 A/T重跑。先≤40原flagged train/cal身份0optimizer QA核62/NaN/status/角色/incoming与序列，利用现有B booster做load/predict/save往返核保存接口，不能为QA另fit。完整A fit后**先写预测并确认可回读，再保存Booster**；不用有兼容问题的sklearn save_model，失败保留可恢复产物。

交A/B同cal支持的logscore/Brier、B−A配对差及500component内incoming条件区间、ROC/partial ROC；2/5/10%阈值各仅在对应模型的train L上定义严格score>t，cal只评价，复核B原工作点不变。报告实际FPR/TPR、原始计数/来源/独立incoming与区间，cal L20/4source不能认证2%总体保证；不按cal结果改classifier或test选赢家。程序独立复核预测分数/区间和原B值，明确只有一个新增A fit、0B refit。

## 3. 资源、判断与交付

建议≤1Condor2CPU6GB、阶段CPU≤300秒/紧凑最终≤20MB，QA实测后准入；小树/缓存处理不用GPU、无ROOT/native事件读取，不占8核做单线程小fit。共用原缓存，不留逐hit/原生副本，不保留重复传输包。不恢复整个历史Athena环境；LCG109 batch已有XGBoost/NumPy。

验收首先是原支持/输入闭合、A可靠持久化、B预测逐位不变和配对统计完成。只有支持的配对证据才讨论信息增量，不能把B单格或A保存失败当物理结论；无证据即停止这族collection工程扩展。若出现增量，仍须另冻完整角色与强BDT能量消融合同、说明geometry和真实关联缺口，不能本轮自动执行。严格低误判支持/真实响应/独立未开发确认仍缺，不因小pilot宣称最终通过。

先写中文stage100 workbook（实际数值/单位/输入/命令/资源/失败/产物/下一最小任务，未测标明），再代码/报告/紧凑证据本地Conventional Commit，不push，不自动stage101。模型和逐事件预测放忽略目录。保持历史正文和以下stage54后缀逐字不变，其实际状态沿stage85，不能默认重做noise支线。

## 保留的stage54 data占据支线

以下§1–5为尚未完成的原协议，仅进入该支线时适用；其中“本轮”均指stage54 data控制。保留其工具/缓存及当前实际工作树状态，历史“未提交”描述不能代替当前状态检查。当前低能优先级按上面的主任务，data可靠性交付仍需完成。

先读AGENTS.md、stage49审查§7、[stage53报告](../workbook/2026-11-02_stage53_tracker-noise-mechanism.md)、修订路线§35、信息计划§20，以及stage52/53的manifest、实际conditions和原生collection读取工具。本轮只做一次有界data占据/有效读出条件约束；不自动执行ν重放、能量训练或谱toy。

## 1. 已测结论与唯一问题

stage53使用12来源2048个100–1000 GeV μ，原HITS和原材料图补齐后，原RDO逐strip/timebin、六计数、选择及名义两次轨迹全通过。actual occupancy3.5e−5，threshold1fC，compression/readout1/1。只关NoiseOn、保留analog：每站平均少约1.3 cluster，station3>6从72.607%降18.750%，差−53.857 [−55.773,−52.036] pp；SP>12 −1.514 pp，segment>4与零相容。两动量层、两符号和12来源保持。53例退出选择，主要是重建动量越界，全部保留。

独立strip噪声确能产生MC额外cluster过量，却不能同时解释stage52 data的SP/segment较多。两轮混合不同，不能机械相减或从on/off反求occupancy。**本轮回答：真实data在可核实的共同读出定义下，对孤立strip/cluster活动及有效噪声占据能给出什么约束或上限？它是否足以定义一个有依据的响应变体？**

0新能量fit/概率映射、0ν重放、0新G4、0谱反演/toy/coverage。不得按data反调BDT，不将零噪声或on/off全差称为1σ，不恢复波形/架构/历史生产扫描。

## 2. 已知输入与有限metadata入口

- 既有`ml/configs/calonu_muon_files.tsv`中的6 data/12 MC来源；stage52完整18文件统计在`ntuples/energy_ml_stage52/source_histograms.tar.gz`。不要沿用manifest历史entry_stop前缀来挑data。
- stage53冻结2048个MC的sample与两臂紧凑摘要在`ntuples/energy_ml_stage53/replay_results.tar.gz`，用`ml/analyze_tracker_noise.py:read_result`回读；旧程序诊断在`pre_correction_nominal.tar.gz`。不重新生成名单、不重复做两臂重放。
- 原生工具`ml/replay_tracker_noise.py`及stage37/38读取器；已有源/entry/生成子文件联结不能只按重复run/eventID配对。data的实际REC/RDO对应关系需用原身份/指纹核实，不能猜一对多entry比例。
- 已知data日志在`/eos/experiment/faser/data0/rec/2024/r0022_log/{015838,016000,016923}/Faser-Physics-<run>-00000.rec.log`；stage36 production_audit记录了精确路径与release，stage52 source_semantics已核对应`d0b1b2dd`的branch代数。
- 只对这些已知production目录做有界metadata确认，找配套REC/RDO及collection schema。核actual几何/station/sensor、mask、active channels、timebin/cluster接受、trigger/filter。文件名noIFT、header默认和当前DB不能自动等同历史actual配置。不可用时列出最小缺失输入，不递归扫全EOS或恢复全部历史Athena环境。

## 3. 看data probe差异前冻结

1. ≤40个独立身份QA，仅核schema、单位、对齐/联结、collection、有效channel分母和I/O/计时；不扫描能量、半径或噪声参数。
2. 默认从6 data已知PHYS完整支持冻结2048个μ，100–250/250–1000 GeV均有来源覆盖；保留stage52独立四Veto tag、质量/几何和原动量定义，不按被测tracker活动取样。与stage53原2048 MC比较，明确来源/p/位置混合，必要标准化只用事前运动学，不按probe匹配。
3. 先明确真正共有的station/sensor与active-strip分母。IFT或collection不共有时独立报告，不能按同名branch强合并。有效mask/DAQ coverage改变必须进入分母，而非统一缩放cluster。
4. 只冻结一种有物理尺度依据的μ邻域/关联排除定义，测远离可靠轨迹的strip/cluster占据、timebin、孤立性及station间相关；无可靠传播/关联时保留未归属，不凭“无SDO”或“没配上leading”认定noise。
5. 未归属活动含真实次级、beam背景和漏重建粒子。缺quiet/随机触发或无偏时间窗时，只给**条件活动或可证明的上限**，不硬分解成纯电子噪声，也不把DB参数直接当data测量。空间sideband若不能分离污染，结论就是未识别，而非假定全是noise。

## 4. 指标、预算和验收

- 同一observable上报data/MC的每active-channel/event占据、timebin组成、孤立cluster大小/额外率、中央分位数/尾及来源/run、p、位置层；对μ条件及过滤边界明确限制，不测全tracker效率或ν shower闭合。
- 来源配对/分层重抽样500次，明确data仅6来源/3run的外推限制。不能以很多同来源事件冒充独立生产；稀少支持写明，重要判断不靠少数异常。
- 默认最多6并发Condor、每任务≤2CPU/6GB、累计CPU≤8h、实际输入≤10GB、紧凑最终≤20MB。QA后按实测冻结执行资源；完整读取/批量稀疏提取通过Condor。先试basket复用，计实际请求字节/ROOT读字节，不能把理论大小当I/O。不得保存RDO/REC/xAOD副本或逐hit点云。
- 目标样本/共同collection不可交付时，先说明覆盖与预算，交付可测的条件统计和具体缺失输入，不静默缩小成有利样本、不用metadata清单替代一切可做的物理测量。

**成功不要求得到一个非零noise最佳值。** 应能判断：data是否约束可信噪声范围；是否只有含背景的上限；或当前数据/定义无法识别电子噪声。只有有真实依据时才提出下一轮响应变体，不将on/off线性插值当标定或正式1σ。

## 5. 后续和交付

有可信范围后，下一阶段才对同事件ν做真实读出/重建变体，固定F6评价计数、动量、选择迁移、能量bias/R68/尾；不能给计数减常数或重训模型吸收失配。范围未识别则结束这轮有界控制，列出最小需要的quiet/calibration输入及仍可推进的预定可辨识谱目标，不延长成参数网格。

ν interaction/FSI、G4材料/输运、连续正向谱硬度及真正未开发生产确认仍是最终交付，单μ噪声结果不能替代。保留六箱自由谱未稳定的结论，不靠更多toy调覆盖。

先写中文stage54 workbook报告，包含实际样本/选择/单位/配置、数值/区间、物理与程序原因、命令/资源/I/O、产物和最小下一任务，再与代码/配置/紧凑表图本地Conventional Commit，不推送，不自动启动下一阶段。
