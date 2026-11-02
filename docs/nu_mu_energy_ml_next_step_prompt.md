# 下一轮执行 Prompt：同一轻量gate的解析可行性修正

先读AGENTS.md、[stage59报告](../workbook/2026-11-02_stage59_lightweight-expert-gate.md)、路线§40、`ml/lightweight_gate.py`及`workbook/stage59_energy_ml/{protocol,models,optimizer_diagnostics,acceptance,validation}.json`。stage59已运行4次，全部status9/maxiter500；不要重跑prepare/fit或覆盖失败记录。当前继续使用F7。

## 当前证据与本次唯一任务

stage59 eval true50–100 log-RMSE .169719，较F7 .312816大幅改善但仍差于传统.145487；100–200 .256517/传统.226876。全体/低reco p/high-y/未确认代价均失败，最低能cal OOF .245862且一折回退F7。梯度/推理QA通过，但4次优化都不收敛，严格完整可行checkpoint稀疏，不能把该结果当已充分优化gate的物理否定。

本次只验证**同一gate的ρ解析可行性/profile修正**，不更换输入/网络/seed/验收，不追加连续似然、F7重训、flux生产或其他架构。不反复增加旧SLSQP迭代或做多起点网格。

## 冻结后一次完成的执行范围

1. 复用`audited_features.load()`、stage56 cal/eval原始预测、stage58 fold/对照、stage59 train-only变换和已存checkpoint。保持train41447/cal8440/eval14057与全部保护，cal已开发、eval已暴露，不叫blind。不读locked test，不补造alternative raw，不恢复transport/shards。
2. F7契约不回退：线性模长/纵向仅pz0，允许px/py/q/p/弯折，11闪烁体raw、VetoNu reduced保留，统一build状态/物理域/依赖。四个gate输入仍是pz0、Timing raw严格总和、total cluster、清理calo EM；沿用stage59 median/IQR及log/asinh变换，缺失或pz0不在[50,250)精确F7。保留负raw、全部尾和完整42缺失者原角色，不按风险新增删除。
3. **先写不可覆盖协议，不先看新eval结果。** 网络仍4→tanh(8)→两相对logit+F7固定0，58网络参数[-8,8]；seed2026110259、同初值。给定网络，软专家相对F7修正Δ，预测为F7+ρΔ。每个代价组相对F7 MSE=`1+βρ+αρ²`，α≥0。解析五个二次不等式与[0,1]交集，得到从0起的可行区间；不放宽1%/3%。再在该区间解析profile两低E二次风险的最大值（端点、活跃二次极小点、交点；固定数值次级全体风险同处理），消除ρ/epigraph的外层约束。不能把profile称λ或阈值扫描，也不能称外层全局最优。
4. 数值pilot先验证：解析可行区间含F7、二次根退化/接近边界、直接经验MSE、profile极小值、缺失默认、有符号量与导数/有限差分；仅小型合成或cal小样本，不增加未记录fit。明确外层梯度/不光滑处理及收敛判据后再运行。建议一个L-BFGS-B、单一起点、maxiter500/maxfun50000、每次wall90s，3折+全cal最多4次，CPU≤400s/RSS≤1200MiB/新逐例≤2MB；若合理算法实现需不同数值选项，必须在新结果前记录理由，不扫算法族。实际收益/收敛/成本未测量。
5. 沿用stage58保守fold，每折offset只由其余cal标签计算；不能用全cal offset冒充OOF。cal16组/2charm、最低能150/14组且无charm，原样报告支持限制。保存末端网络参数、profileρ、逐约束值/违反、stationarity、选择原因和训练轨迹；不要只留总违反。数值失败不伪装成物理阴性，不将不可行末端当结果；4次预算内完成，不在本阶段反复重启。
6. 目标及共同验收不变：两低E相对传统最坏log-MSE最小；全体/F7 RMSE≤1.01、true≥200/reco pz50–100/high-y/未确认≤1.03。低E恢复须两层来源95%比上限≤1.05，突破须改善下限>0，关键tail50变化≤2pp，报告双方向tail50/100、mean/median bias/R68、完整能量箱、两reco低p和缺失者。OOF与冻结eval均要报告，与F7、stage58四格、stage59可行但未收敛gate比较；不只报漂亮最低能eval。
7. 500次component分层保守来源配对bootstrap仅重抽样固定预测，不多次重拟合，不叫全流程确认。参数化保证的是训练样本约束，不自动保证OOF/eval风险。若修复后通过，冻结并规划独立低E/共同raw确认；若数值修复后仍来源不稳或代价外推失败，结束gate调参支线，给下一次单项连续E响应似然或定向独立样本方案。不要再无界更换门控网络或关掉低能方向。
8. 写下一编号中文workbook，实际N/单位/输入/选择/配置/命令、wall/CPU/RSS/I/O、紧凑产物、数值/物理原因和验收逐项记录；更新路线/Prompt并本地Conventional Commit，不推送。stage54工具/缓存先查实际状态，不混入新提交；data共同raw定义、占据、ν interaction/FSI/材料、独立生产及最终谱收益继续必须交付。

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
