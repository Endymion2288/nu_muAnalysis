# 下一轮执行 Prompt：stage55后的低能条件诊断，并保留stage54 data控制

先读AGENTS.md、[stage55报告](../workbook/2026-11-02_stage55_low-energy-flux-training.md)、修订路线§36、`ml/configs/low_energy.json`及`workbook/stage55_energy_ml/{support,metrics,paired,raw_metrics}.tsv`。用户优先关心真实低能不如传统方法，以及50–100 GeV和替代flux。已完成15正式fit，不重复训练或重建；stage54未提交文件保持原状，不误当stage55成果。

## 0. 当前低能优先任务

已测：门槛受控100→50将true50–100 log-RMSE从.558448降到.318419；混训.316318、残差.291938，仍差于传统.145526。true100–200残差.267378/传统.226855。替代flux增加139低能训练例，unit混训50–100收益+.660% [−1.335,3.034]，不足以解决；matched先验+1.851% [.433,3.642]也很小。不可说低能已修复或已经证明只有缺数据。

reco p50–100的682例只有208个true50–100，其余含高E/high-y；混训总体降低62.072%，不能用这个数字替代trueE指标，不能把全部低p切回传统。真低E的206/208 leading确认primary，median y=.0643，μ产生p复合R68=2.172%，不支持将巨大ν上偏直接归为低pμ核心失效。residual低E有益但全样本退化，不能truth-gate选赢家。

下一轮首先做一次**0新fit、0新RDO、0谱toy**的有界条件诊断：

1. 输入`ntuples/energy_ml_stage55/dataset.npz`、`predictions.npz`及`seed_predictions.npz`、保留的15模型和`training_metadata.json`。shards已逐301源验证归档，不重建它们；历史F6只作已开发参照。cal8,440、nominal/替代eval14,057/4,876，精确四动量保护排除已写入cache，不撤销。完整谱系独立仍未证明。
2. 只用train冻结少量p/活动格，活动量沿用已有部署读出（cluster/SP、Timing、calo EM）；不得根据validation残差或trueE调边界，不使用truth作部署gate，不拓展大量变量/阈值网格。可先在train独立来源中定义边界，再固定评价；保留缺失读出者与尾。
3. 在相同读出格内量化true50–100、100–200与≥200/high-y/未确认的比例、已有传统/mixture/residual风险、bias/R68/尾、来源支持及区间。明确低活动剩余上偏、连续谱/先验与读出混合的可辨识边界；不能以少数离群者结束低能分支，不能宣称观测信息严格不可恢复。
4. 验收为给出一个可核查结论：何种data可定义条件有机会保留μ低E精度，同时保留高y收益；或为何现有读出在相同条件内无法稳定区分。新训练前再冻结一次来源内cross-fitting的μ/残差收缩方案、fit预算与低E对传统/高E-highy代价的共同验收。此诊断阶段不追加fit、不立即换架构或扩无边界生产；已暴露validation不能再次称blind。
5. 读取紧凑cache，小规模交互验证计wall/CPU/RSS；若扩到批量ROOT必须Condor并先小样本测试。写中文workbook报告、实测表图与明确下一任务，再作一次Conventional Commit，不推送。低能MC结果不取代data响应、interaction/FSI、材料或归一化谱收益。

## 保留的stage54 data占据支线

以下§1–5为尚未完成的原协议，仅进入该支线时适用；其中“本轮”均指stage54 data控制。原未提交工具/缓存不得混入stage55提交。当前低能优先级按上面的§0，data可靠性交付仍需完成。

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
