# 下一轮执行 Prompt：一个更有信息的轻量专家gate，先冻结再执行

先读AGENTS.md、[stage58完整报告](../workbook/2026-11-02_stage58_constrained-physical-experts.md)、修订路线§39、stage57§4–5和[F7契约](nu_mu_energy_ml_features.md)。stage58已完成四格实验；不要重跑`prepare_expert_combination.py`或`run_expert_combination.py`，它们拒绝覆盖成功产物。复核用validate，不额外优化。

## 当前结论与唯一下一问题

三专家true50–100/100–200 log-RMSE=.262665/.252439，相对F7改善16.032%/4.745%，仍差于传统.145487/.226876。最低能bias仍+17.675%，tail50=8.654%/传统0%。全体代价通过，但reco低p/high-y对F7的95%比上限1.042697/1.038256超过1.03，cal OOF也不稳定。因此当前保持F7，不放宽验收、不在旧四格扫描λ/阈值/seed。

理想三专家低E下界=.023980/.081975，理想二专家也优于传统；这不是部署结果或信息极限。唯一下一问题是：在有限cal支持下，一个加入counts/Calo的轻量读出gate能否改善专家选择，同时保持共同风险约束和OOF稳定性？不要同轮连开新flux/低E生产、F7重训、多头transfer或连续似然网络。

## 下一阶段执行范围

1. 复用`audited_features.load()`、stage56 cal/eval原始log预测及`workbook/stage58_energy_ml/{protocol,models,acceptance}.json`、stage58预测`ml/artifacts/stage58/predictions.npz`。保持train41447/cal8440/eval14057及所有原保护，cal已是开发集、eval已暴露，不叫blind。不读locked test、不为alternative伪填raw、不恢复transport/shards。
2. F7输入不回退：线性模长/纵向仅pz0，允许px/py/q/p/弯折；11闪烁体raw，VetoNu reduced保留。统一build处理状态、有效域、依赖；signed负值保留。完整nominal42个缺失者中本轮eligible21/3/7，另11既有保护排除，不按缺失或残差新增删除。选择仍含部分fit-charge cut，不改接受度。
3. **先写不可覆盖的有界协议。** gate仅用pz0、Timing raw严格总和、总cluster、清理后的calo EM四个读出；变换/中心尺度仅由train X冻结，signed量可用asinh，缺失显式路由F7。建议一个固定8单元hidden+3权重softmax gate、固定seed，不比较深度/宽度/学习率网格。执行前明确数值算法、F7可行参照、收敛/失败报告和实测CPU/存储预算；若合理实现需改变这一建议，先在看新结果前记录理由，不能用eval调结构。
4. 仅现有cal保守来源三折+最终全cal，共4次gate拟合、0新F7能量fit/ROOT/RDO/生产/toy。每折offset只用其余cal，沿用stage58 fold映射；不能套全cal offset冒充OOF。cal只有16组/2charm，低E150/14组且无charm，必须报不足。权重非负和为1，推理不读truth/y/component/group。
5. 目标与验收保持stage57/58：最小化两低E相对传统log-MSE最坏比；全体对F7 RMSE≤1.01、true≥200/reco pz50–100/high-y/未确认≤1.03，次级全体风险且不扫λ。truth只用于训练目标/诊断。两低E恢复需来源配对95%上限均≤1.05，突破需改善下限>0；全体/困难组同样按区间验收，关键tail50增加≤2pp，报告双方向tail50/100、bias/R68、分能量/两reco低p与全部缺失。不得改门槛或仅报有利层。
6. 小样本先核路由/约束/梯度/OOF来源和offset；再一次完整拟合评价。报cal OOF各折/来源、固定F7及stage58四格主候选和新gate；500次component分层来源bootstrap只重抽样固定预测，不另做数百次重拟合，不把其称全流程确认。保持全部尾，不能用预测截断获得收益。
7. 若通过，冻结并规划共同raw与独立低E确认；若仍失败但理想下界好，区分gate学习/条件支持/来源不稳定，给一次定向独立补样需求或单独冻结连续E似然实验。下一投入要具体：所需样本/component/条件、固定候选、成本与共同验收，不把粗gate阴性当全信息无用。新生产和下一模型在本阶段结束后另列方案，不自动连开。
8. 写下一编号中文workbook，记录实际N/单位/选择/配置/命令、wall/CPU/RSS/I/O、模型/预测体积、验证、区间限制与科学决定；更新路线和下一Prompt，本地Conventional Commit，不推送。既有stage54文件实际状态先检查，不混入新阶段提交。

当前MC raw有符号整窗积分与data旧源码只积正样本不同；共同raw定义、stage54占据、ν interaction/FSI/材料、独立生产与最终能谱收益继续必须完成。本轮MC方法研究不能宣称data改善。

## 保留的stage54 data占据支线

以下§1–5为尚未完成的原协议，仅进入该支线时适用；其中“本轮”均指stage54 data控制。保留其工具/缓存及当前实际工作树状态，历史“未提交”描述不能代替当前状态检查。当前低能优先级按上面的§0，data可靠性交付仍需完成。

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
