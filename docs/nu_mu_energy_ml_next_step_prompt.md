# 当前交接：Stage110固定关系差已完整评估，主比较与最终联合未过

先读AGENTS.md、路线§92、信息计划§72、[Stage110实际报告](../workbook/2026-11-05_stage110_bdt-anchored-relation-transfer.md)、[选择](../workbook/stage110_energy_ml/selection.json)、[decision](../workbook/stage110_energy_ml/decision.json)及[完成审计](../workbook/stage110_energy_ml/completion_audit.tsv)。Stage109§4的实验已完成，不能再当待执行任务。Stage104动作、Stage108三格/遮挡和本固定差方向均结束。

## 1. 已交付与允许的结论

原71376 active、46575/11612/13189角色、17657隔离、全部1016新增K和缺标量21/6/5、缺几何345/343/356保留。fα=Stage87 direct_cal+α·geometry_available·(B_raw−A_raw)，只取Stage108 raw差、无新offset、缺几何/α0逐位回原强点。40cal QA含6缺标量/5缺几何及解析退化例通过；唯一cal_select解析求解选α1、可行[0,1]、六开发保护不活跃，冻结落盘回读后才test差分。上界活跃不授权扩α。

主cal_post max两低能new/f0=1.001249542 [.988791330,1.027119908]，未支持共同改善。test最低能.282644→.274991，比.972924 [.948277,.995675]有局部用途；第二低能.246329→.243557，比.988748 [.972972,1.004560]含1。最低能仍弱于传统.145661；all .287491→.288039，区间含1；cal_post all有退步。test低pz真高E .658177→.662660但区间含1，不声称显著恶化。

最终jointFalse：两低能/传统上95=2.262071713/1.059345213>1.05；其他六层RMSE通过，high-y总/负尾差direct上95+2.975030/+3.013768pp>+2。负尾差区间含0，不能称证明超过2pp。完整cal/post/test八层及高端/missing/geometry_missing/confirmed低transfer/X诊断、bias/R68/三向尾、C/D/A与实际风险差均已交付；主区间独立差0，40区间max1.776357e−15，840旧控制max1.421085e−14。不晋升，继续原部署；差包含标量重学习/优化，不是纯几何或信息界。

唯一Condor9668033首start/exit0，4CPU/申请6GB站点12GB/0GPU/4worker内线程1；GNU外层15.39CPU/7.96wall秒、RSS283924KiB。内部计时不与外层相加，单核加速比/物理EOS流量/全会话CPU未测。18运输输入核原字节后去重；唯一新点表在忽略的ntuples/energy_ml_stage110/points.npz。全部数值在batch，本地仅标准库文本/字节/打包操作。

## 2. 停止条件与重开输入

**没有自动Stage111。** 不重训A/B/C、不换计数遮挡任务/seed/深宽/正则、不续T/offset/固定q权重，也不扩α符号/范围/局部系数/C或更多专家。单组收益准确保留，主阴性结束这个方向，不把有限负结论推广到所有可训练残差。

Stage109另列的主要投入目前仍需实际交付，不由本次Prompt授权提交新生产或对外发消息：

1. 新独立source/parent和可执行生成接口、提议密度/纳入概率；真50–100/100–200GeV、同低reco pz真≥200/high-y及自然高端，按transfer、z/材料/几何分层。先pilot给selected产额/选择失败分母/ESS，验收不重复旧池、不删困难者、源在生产前分训练/校准/locked。实际路径和产额未交付。
2. 相同生成/输运历史上、有IOV/有效DAQ/quiet依据与物理尺度的读出/校准变体，并留紧凑measurement→cluster→SP组成引用；另做匹配incoming/靶核/顶点的generator比较。两种配对目的不同，不能硬当同末态或正式1σ。Stage85既有条件活动不认证纯噪声/active分母，不再重复同控制或无目标扫EOS/旧REC。
3. 原最终能量与八层三尾要求、interaction/FSI/材料/Calo/接受度/背景依据、新未开发locked来源及完整source/refit/研究选择/参数不确定度确认。开发test与cal_post有历史用途，500incoming条件区间不替代它们。

只有具体新输入或用户明确另冻科学问题时才安排可失败完整比较。原pz0>50GeV、一次方动量仅pz0、允许px/py/q/p/弯折、raw11/status/typed NaN/合法负值/Calo缺项、全部K和原角色保持。两低能/传统上95≤1.05、all/direct≤1.01、其他五层/direct≤1.03，八层三向tail50差direct上95≤+2pp保持。阶段实验完成与项目物理终点未达分开记录，不自动重复状态审计作为新阶段。

后续真实工作仍在batch，适用时GPU、CPU合理多核内线程1，spool统一~/condor/nu_muAnalysis/<stage>/；先中文实际报告再本地Conventional Commit，无push。Stage54五资产和以下历史后缀保持，实际状态以Stage85为准，不自动重做noise支线。

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
