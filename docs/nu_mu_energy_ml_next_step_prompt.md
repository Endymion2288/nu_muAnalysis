# 下一轮执行 Prompt：Stage105 局部点关系的有界可行性QA与一次性合同

先读AGENTS.md、路线§86、信息计划§66、[Stage104实际报告](../workbook/2026-11-04_stage104_fixed-density-point-decision.md)及[Stage103研究设计](../workbook/2026-11-04_stage103_research-reset-and-decision-budget.md)§5。Stage104已完成，固定q两权重族结束；不重新求λ/温度/专家或网络fit。本Prompt仅在用户后续调用路线时执行，当前尚未开始Stage105，不自动三格训练。

## 1. 已有结论与新问题

Stage104最低能test log-RMSE .276027→.219374，有单层点增量；但第二低能未确证改善，cal_post预定两低能最大RMSE比上95=1.006171未<1，低pz真高E/负尾受损，原最终联合未过。不把这解释成ML/几何关系无效、训练充分或信息界。

唯一新问题是：Stage103提出的逐面全点mean A、局部跨层消息B、同B加遮挡面预训练C，是否有可交付的真实PHYS坐标、完整角色保留办法和有限成本，足以冻结一次可失败的三格实验？本轮先核可行性并交具体合同，**0能量fit/预训练/test载荷或风险，不先全量提取**。

## 2. 输入与有界QA

先读Stage19集合读取/完整点mean池化实现（`ml/extract_sets.py`、`ml/set_data.py`、`ml/train_sets.py`），Stage95固定2048train/cal身份/24source的manifest/QA和精确PHYS路径，以及Stage96已知缺源记录。只沿这些已知入口，不能递归扫EOS或无新线索找已清理scratch REC；不重建/生成补缺源，不换有利事例或丢K。

固定≤40个原train/cal身份，用已有来源覆盖的QA名单为起点，读取真实SP坐标/plane可用定义，核单位、探测面几何、branch/count对齐、空集合/缺源、原身份/角色联结。全部数值/事件读取在batch，当前终端不恢复CERN环境。若既有QA身份有实际缺源，保留分母与具体缺口，不能静默换人。只读已知文件并复用basket/缓存，计实际接口请求字节/CPU/wall/RSS和单事件点数/候选邻接边成本，不保留逐hit副本。

不把SP当唯一粒子、几何邻近边当真实track-cluster ID，未归属不等于noise/强子；真实ID/TSOS/SP组成/covariance/有效读出仍为机制与response缺口，但不作为任何几何消息的绝对前置。不能把跨磁铁直线当真实传播。

## 3. 一次性合同的验收

QA可交付时，冻结A逐面全点mean、B局部跨层关系、C同B加train-only遮挡面任务；A/B/C原62标量/角色/incoming权重/point目标/后处理和strong direct62对照保持，B/C同架构。主比较是整体C/A，B用于解释关系与预训练，不能以弱A胜出代替最终成功。局部邻居限制计算边数，保留全部原点/计数和高活动事例，不能截断困难尾来满足内存。

遮挡一张有效面时，构图只用可见点；遮挡面坐标、计数/矩及其他派生泄漏摘要全部从该步输入排除，只用原train预训练，不混入cal/test无标签事例后声称独立留出。不给ghost/强子/共同粒子伪标签。描述坐标/plane状态、缺源/空事件、几何边、任务标签、loss和点输出的具体可执行定义，不只列架构名称。

交实际QA分母、输入单位/局部邻接成本、原完整角色的来源覆盖/缺失保留方案，以及一次性三格fit的事前seed/停止/选择/资源与退出合同；未经合同不全量提取或训练。可行性不足就给精确不可交付字段/预算和停止条件，不延长metadata链。预训练loss下降不能替代能量风险增量；验收必须原两低能、总体/困难和八层三向tail。最终1.05/1.01/1.03及tail差上95≤2pp不改，开发test/source/refit/系统/研究选择限制保留。

原角色与全部K/missing/pz>50GeV、pz0-only一次方动量/允许px-py-q/p-弯折、raw11/status/typed NaN/合法负值保持。无新证据不恢复Stage19普通mean池化、候选几何深宽/seed扫描或Stage100摘要浅树调参。

## 4. 资源与交付边界

本轮拟议小QA≤1个Condor任务、最多4CPU/6GB/内线程1，CPU与wall各≤900秒，实际输入接口请求≤1GB/紧凑最终≤20MB；先以小身份子批测成本才读满固定≤40，不符合预算保留已测覆盖与缺口，不扩大范围。这是未执行上限，新成本/可读率/收益均未测。GPU及三格训练预算由这次实测后另冻，不从历史千GPU小时外推。

提交根统一 `~/condor/nu_muAnalysis/stage105/`，不再home根建 `nu_mu_stage*`；保留其他项目与Stage54资产。先写中文Stage105 workbook（实际输入/选择/单位/QA/资源/程序和物理解释/缺口/三格合同或停止），再相关代码/配置/紧凑证据本地Conventional Commit；不push、不自动训练或Stage106。历史只追加，以下Stage54后缀逐字保留，其实际完成状态以Stage85为准，不重做noise支线。

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
