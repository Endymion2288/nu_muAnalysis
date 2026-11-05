# 当前交接：Stage113六源选择/响应测量完成，下一步解决已有来源低能支撑

先读AGENTS.md、路线§95、信息计划§75、[Stage113实际报告](../workbook/2026-11-05_stage113_selection-response-measurement.md)、[主端点](../workbook/stage113_energy_ml/primary.tsv)、[每源端点](../workbook/stage113_energy_ml/source_primary.tsv)、[原科学合同](../workbook/stage111_energy_ml/experiment_contract.json)、[原六源manifest](../workbook/stage111_energy_ml/source_manifest.json)。**Stage113已完成，不再提交或重做60000事件。** Stage112的失败/QA及资源拒绝是历史，报告保留不改写。

## 1. 当前实测结论

唯一新Condor9668067首start/exit0，六个完整PHYS各10000条、67必要branch。全部60000父事件20cut独立/native mask差0，leading一致、pz差0GeV；Stage87仅身份白名单联结，test>cal>train、原隔离/低优先来源保持。test-key仅全父cutflow，未知父行只诊断、不入训练。每源incoming父视图选择前权重和1，不向幸存者重分摊。

固定传统pz0/0.8，G0只去名义重建pz>50，保留truth νpz>50/原fitted-charge/质量/几何；G+正有限pz/Eν，S50=G0且pz>50，S100历史对照。主真[50,100)GeV因两个charm源G+/S50零支持不可估；[100,200)GeV六源等权ΔMSE=−0.09447554689537985，但309/500完整draw<475，**不报CI**。charm/train仅1条选中incoming。不能丢源、重抽到成功、事后合箱/扩样本把本端点改成可估。

55:4的100–200GeV MSE .3050880915→.0756443845、mean y .24446487→.18247734；u²下降但signed交叉/常数项也改变，r含材料/角度/参考面/错leading，不是纯tracker分辨率。π另一源最低能略反向、K最低能不变、charm空支持，不能概括为所有低能优势或ML失效的统一原因。固定完整X的确定选择不改变支持内p(t|X)，边缘富集不证明信息界。

[风险/困难高端](../workbook/stage113_energy_ml/risk.tsv)、[变量](../workbook/stage113_energy_ml/variables.tsv)、[分解](../workbook/stage113_energy_ml/decomposition.tsv)、[身份](../workbook/stage113_energy_ml/identity_audit.json)、[完整验证](../workbook/stage113_energy_ml/measurement_validation.json)已交。e恒等式/汇总/独立key-bootstrap差8.881784e−16/3.552714e−15/2.220446e−16。0fit/forward/offset/新ML对比/晋升，原Stage110固定差和Stage108固定三格/遮挡方案结束，不重开网格。

## 2. 异常值的已知与未知

[invalid完整channel计数](../workbook/stage113_energy_ml/invalid_native_pass_counts.tsv)与[首40例](../workbook/stage113_energy_ml/invalid_native_pass_examples.tsv)显示负VetoNu reduced可通过原native<30并进入S50。前40全来自首源VetoNu0，不代表全部来源；entry52为−.19242186844348907pC/status0、S50/eligible均True，不是−1/−999的证据。标签只表示既有非负域假设失败，producer signed/pedestal语义**未核实**，不能把所有负读数当非物理/NaN或删例。chi2ndf invalid单项pass在六源为7/10/8/8/4/4，最终S50均0；其他被审计track域无invalid-pass。

[fit/raw状态表](../workbook/stage113_energy_ml/scintillator_audit.tsv)保持FIT_INVALID与WAVE_INVALID区别。模型已用raw11/status，legacy cut仍可用fitted/reduced；本轮没有换cut。pz0-only一次方动量及允许px/py/q/p/弯折、typed NaN、合法signed负值、Calo缺项、全部K/原角色和pz>50保持；pz≤50不forward BDT。−999/非负count−1/uint-wrap/空轨迹与合法signed量、fallback−1234控制值分清。

## 3. 已计资源与留存

Stage113 GNU67.03CPU/25.91wall秒/RSS648868KiB；Stage112含首失败69.33/24.80，两阶段累计136.36CPU/50.71任务wall秒，<原3600/900。新增接口40935572byte，含首失败保守上界共94323758byte<2GiB，不是物理网络。整树同时内存峰/单核加速/全会话成本未测，worker/native嵌套成本不重复相加。

6CPU/12000MB申请、站点18000MB，六worker内线程1/0GPU；watchdog涵native全部后代。20项运输输入原字节一致，重复输入/结果包已验证后删除，必要图表/原生日志/协议/资源和提交记录保留，spool ~/condor/nu_muAnalysis/stage113/；其他项目/Stage54不动。[完成审计](../workbook/stage113_energy_ml/completion_audit.tsv)区分测量完成与项目未达。

## 4. 下一个有界科学问题

优先量化**已有完整来源能提供多少低能支撑和来源迁移证据**，不要另做计时/接线/metadata独立阶段。输入为`workbook/stage105_energy_ml/identities.json`及已知精确train/cal PHYS路径、Stage87身份白名单、已验证Stage112/113选择实现；不需要新模拟、不扫全EOS或旧REC、不读test-only源。下一次实际推进先在看到扩展结果前另冻完整允许来源manifest与预算，然后一次完整父分母测量。

预冻π/K/charm×历史角色六单元、来源层级统计定义和共同incoming相关处理；这是扩展单元的**新端点**，不能替换Stage113六个单文件端点。保留全部允许源及不可读/零支持原因，不按低能产额选择、逐步补到显著或改CI门槛。交每单元父支持/incoming/权重/ESS、两低能传统风险/选择差、transfer/response分解、原八层/同pz高E/高端、完整native和身份闭合与实际CPU/I/O。来源不确定度不足则明确不能外推。真实产额/功效/成本尚未测；不可无声沿用原六源预算当新授权，不自动扩训练集/换split/训练或生产。

同时沿精确匹配PHYS producer实现核VetoNu reduced/raw的积分/pedestal/fit、合法signed域/status/sentinel，输出逐变量依据表。只沿已知引用定位，不恢复历史环境或递归扫描；匹配定义缺失就记确切缺口。核实后才另定切选敏感性，不以负值影子标签直接修cut。本阶段无需重复研究状态或再问“是否有新输入”，当前既有输入已足以制定该有界测量合同。

## 5. 最终项目条件

原最终两低能RMSE/传统上95≤1.05、all/direct≤1.01、其他五层/direct≤1.03及八层三向tail差direct上95≤+2pp不改。真实response/interaction/FSI/材料/Calo/接受度/背景、新独立支持和locked确认未交付；整个能量目标未完成。条件区间不覆盖source/refit/研究选择/真实系统或newblind。每阶段先中文workbook，再本地Conventional Commit，不push；不把本测量完成写成模型已恢复。

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
