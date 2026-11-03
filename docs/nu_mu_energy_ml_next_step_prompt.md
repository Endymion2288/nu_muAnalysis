# 下一轮执行 Prompt：stage86 latent-state 实测表与 transfer posterior 合同

先读 `AGENTS.md`、路线§66–67、信息预算§46–47、[stage85研究复盘](../workbook/2026-11-03_stage85_research-reassessment.md)、[stage85实际读出控制](../workbook/2026-11-03_stage85_tracker-occupancy-control.md)及[输入请求](../workbook/stage85_energy_ml/followup_input_request.json)。本轮唯一任务是用已存在缓存交真实latent-target/transfer-state诊断表与固定后验实验合同；**0新能量fit、0新ROOT读取/重建/F7推理/ν replay/GENIE/G4/toy**。不自动启动后续模型训练。

## 1. 当前结论

stage85已经交付2048data＋原2048MC、312REC原生身份/四站cluster全闭合，不能再用metadata-only控制代替。data/MC共有三站raw137.606445/29.061523 strip/event，但实际01X接受只有32.892578/29.057617；raw差96.467%位于不接受时间箱。邻域外cluster反向为3.718750/6.427734，MC未知ID上界6.428223；SP小样本差区间跨0，segment差+0.126465。共同历史active DAQ分母及quiet/random trigger没有认证：B条件活动可测，纯noise为C。结束本有界纯noise参数支线，保留响应未识别标记，不用raw比值、DB参数或stage53 on/off全差当校准/1σ。

这不是50–100GeVν低能问题的已证原因。F7继续作为现成基线，stage84已完整用49167支持及1016K，低能仍失败；不继续无条件随机补样、seed、权重或架构网格。

## 2. 本轮实际交付

1. 输入仅原完整stage84支持/旧角色及已有F7、传统、stage84预测、source/incoming谱系。先做≤40个已有缓存身份的schema、单位、角色和实际包零fit QA；不生成新F7预测。
2. 核实真正的vertex μ能量、transfer/transfer fraction监督标签、confirmed/high-y/status及缺失值。部署输入不能含truth；**不得用重建pz0/0.8或传统估计制造非负truth transfer**。若标签缺失，交现有truth状态的实际表，并精确列出缺列/来源/最小输入，不能编造标签或丢缺失事件。
3. 至少按true Eν50–100/100–200/≥200、reco pz0 50–100及其真高E反例、confirmed低transfer/high-y/未确认、response/missing状态交叉，报告N、来源数、既有F7/传统/stage84的log-RMSE、median bias、正/负/总tail50与500来源draw区间。稀少/空层保留并标注未测量，不以几个尾事件裁决信息极限。
4. 在这张实表基础上冻结一次后续比较：F7旧direct-logE基线、bounded residual/shrinkage、hurdle/连续正transfer mixture。固定输入族、gate/target语义、少量混合成分、loss、点估计functional、calibration、68/90%区间coverage、PIT/可靠性和tail验收，不从eval扫描挑模型。近零transfer质量不等同真实严格零点。
5. split必须source/incoming隔离；实际核认证明一个真正未参与研究选择的locked source/production，若现有入口都曝光就直报缺口。已有cal/eval是开发样本，不得换名独立blind或因此删高-y困难侧。
6. 两类reweight分开预注册：后验πtarget/πtrain的平坦logE/名义/低能压力谱及capped权重/ESS；data/MC density ratio只在共同条件进一步认证后另立，不把本轮条件活动当可训练的noise correction。未识别response nuisance继续显式保留。

## 3. 固定保护、资源和停止条件

模型输入一次方动量仅pz0，允许px/py/qOverP/弯折；禁止p0/p1/pz1及ln(p0/p1)。signed raw11、原typed NaN/status/missing政策、Calo缺项总NaN、原pz>50GeV与全部困难事件保留。真值标签另作监督/诊断，不能混入部署输入。

原两低E/传统95%上限1.05、all/F7 1.01、困难1.03及七层总/正/负tail50+2pp保护不降；后续新增68/90后验coverage/PIT。当前只交实际表与合同，所有新后验收益和训练功效仍为未测量。

先QA和传输包，后≤1Condor、1CPU/3000MB、累计CPU1800s、紧凑20MB；不做新ROOT、能量fit、F7推理或生成。复用现成环境、旧预测和完整π＋K支持，用户解除的K生产时限/禁令不恢复。验收必须有实际数字、单位、来源/缺失和可执行标签/谱系审计，不能仅写metadata方案。

若标签或真正未开发holdout不足，记录可识别层和准确缺口，再决定后续最小输入；不伪造监督或blind。只有该实表证明标签/split可用后，才另冻具体训练与预算，不自动执行。中文stage86报告写在根目录workbook，再与代码/配置/紧凑证据本地Conventional Commit，不push；原stage54五项工作只读保留。

以下保留的 stage54 原后缀逐字不改，仅作已完成控制的历史合同，不自动重新启动。

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
