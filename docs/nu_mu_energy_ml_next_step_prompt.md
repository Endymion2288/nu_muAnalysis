# 当前交接 Prompt：Stage106 资源停止后的未完成证据与继续条件

先读AGENTS.md、路线§88、信息计划§68、[Stage106实际报告](../workbook/2026-11-05_stage106_point-model-resource-admission.md)、[decision.json](../workbook/stage106_energy_ml/decision.json)和[逐项完成审计](../workbook/stage106_energy_ml/completion_audit.tsv)，以及Stage103 §5–7。用户持续目标仍是完成现有规划，**整体目标尚未完成**；不能把完成有限QA/stop改成达成能量重建或独立物理确认。

## 1. 已完成和未完成的区别

Stage104固定q两权重动作唯一优化/原风险完成，共同两低能及最终联合未过，该族结束。Stage105原40中37可读、5718全点/56822局部边、可见输入隔离完成。Stage106实际8CPU提取QA和H100 NVL MIG3g.47gb CPU/GPU接线均首次成功：90242参数，CPU/GPU max差4.768372e−7、置换/同初始化/无跨事件边/遮挡泄漏/合成空缺invalid/overflow通过，独立外层22.281917CPU秒。

固定准入投影GPU任务wall15468.536715s>7200、总CPU22692.597896s>21600（正常提取估计8118.720840s已含reserve）；GPU计时窗口allocated峰361.045898MiB，不是显存失败。最慢批的统一最坏外推较保守，不代表真实全训练必需15469秒或计算下界。按冻结stop已在optimizer前结束，**0fit、0预训练更新、0完整提取、0test载荷/风险/晋升**。三格C/A、B解释、学习轨迹/offset/最终gate均未测。QA诊断平方输出不等于完整真实incomingweighted训练验证；未执行的条件trainer不是已交付模型。

## 2. 没有新输入时的边界

不默认启动Stage107/新fit、重做相同QA、改成更有利成本公式/少epoch/样本、加预算/seed/深宽/遮挡任务，也不回到固定q权重/温度/专家、collection浅树或旧REC无新线索搜索。当前合同已结束，不能按旧Stage106 Prompt再启动。没有新样本不是一切开发都应停止的原理；这里是具体冻结合同的资源退出及尚未认证的物理终点。

持续目标的完成必须有当前权威证据支持；原低能/总体/困难和完整双向尾未达、真实系统与独立确认缺失，不能标complete。若当前确无可独立推进的任务，精确报告实际缺口并保留未完成目标；不要用重复状态或重写计划替代进展。

## 3. 有明确新输入/规划时怎样继续

优先按completion_audit.tsv逐项核交付，而非重新列模型清单：

1. 新source/incoming生成谱系及与现有池不重叠，真50–100/100–200GeV、同pz真≥200/high-y反例和高端控制，原接受度/提议密度与权重、pilot选中产额/成本、真正未开发locked确认角色。现有7720增补/1016K已入池，不重复叫新独立支持；无实际产额不硬造样本量或功效。
2. 实际IOV/逐事件DAQ有效mask/coverage、无偏quiet/random trigger或等效校准及PHYS身份联结。Stage85已完成2048data+2048MC条件活动，110592是名义非active分母；缺口未变时不重复测条件活动或用raw比值/noise-on/off全差造1σ变体，100–1000GeV单μ不认证50–100GeV ν/shower。
3. 原incoming可联结的有依据interaction/FSI、材料/输运、Calo/读出等变体及原选择分母、接受度/背景，之后才能认证真实系统与选择迁移；旧模板/prior重权不是这些变体。
4. 若用户明确修订资源/准入或提供另冻可执行实现合同，先冻结新的科学比较、成本与停止条件，在真实batch小QA后才准入；不能无声重开失败合同。原C/A主比较与强Stage87 direct62、角色/权重/cal子分区、全部K/缺源/typed规则以及原最终门槛必须保持。生产或新任务范围以实际新规划为准，不自行扩成大网格。

原输入政策：pz0>50GeV、一次方动量仅pz0、允许原px/py/q/p/弯折，raw11/status/typed NaN和合法signed负值/Calo缺项；保留原46575/11612/13189、17657隔离、1016新增K、missing21/6/5和全部缺源view。边只是几何邻近，不是真实ID/ghost。原两低能/传统RMSE比上95≤1.05，all/direct≤1.01，其余五层/direct≤1.03；八层总/正/负tail50均相对direct差上95≤+2pp。开发test不是新blind，500incoming条件区间不覆盖source/refit/offset估计/研究选择/真实response。

所有数值/事件工作在batch，GPU适用则实测使用；批量独立CPU源分片合理多核/内线程1，计实际请求和站点资源及CPU/wall/接口bytes/RSS/GPU峰。spool统一~/condor/nu_muAnalysis/，最终紧凑、去重，不保存逐hit中间文件。先中文阶段报告、再相关代码/配置/紧凑证据本地Conventional Commit，不push；历史只追加。以下Stage54后缀逐字保留，五资产不动，实际完成状态以Stage85为准，不自动重做noise支线。

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
