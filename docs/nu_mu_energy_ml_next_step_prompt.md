# 下一轮执行 Prompt：Stage106 一次性完整点关系／遮挡预训练三格实验

先读AGENTS.md、路线§87、信息计划§67、[Stage105实测报告](../workbook/2026-11-05_stage105_point-relation-feasibility.md)与[冻结合同JSON](../workbook/stage105_energy_ml/experiment_contract.json)，并参照Stage103 §5和Stage19完整点集合实现。Stage105已完成：原40train/cal身份37可读+3已知缺源、5718全点/56822边、遮挡泄漏和排序QA通过。**本Prompt只在用户后续调用路线时执行；本轮没有启动Stage106。**

## 1. 唯一问题、输入与保留政策

唯一问题：整体局部点关系＋train-only遮挡方案C，相对完整点逐面mean A，是否降低共同两低能点风险且保护总体/困难？B解释关系和预训练；不能只拿弱A输赢替代强Stage87 direct62。不是复做Stage19普通mean、候选几何深宽、Stage100摘要浅树、固定q权重/温度/专家，禁止新seed/任务/网络网格和旧REC搜寻链。

严格执行上述JSON的具体字段，不临时另选架构。原Stage87角色46575/11612/13189、17657隔离、incoming总权重1、原Stage94 select5443/post5746（423退出select仍完整报告）、全部1016新增K、missing21/6/5保持。精确源复用Stage95/96，原40QA名单见Stage105 identities.json，不能替换已知缺源或读test做QA。Stage96历史70332可读/1044缺PHYS，train/cal/test缺345/343/356，不是Stage105新测全角色SP覆盖；全部保留原标量与geometry_missing，不丢K。82:2旧bck错误路径不替代。

标量是原audited62、Stage94 C train-only state/representation127维；一次方动量仅pz0，允许原px/py/q/p/弯折，raw11/status/typed NaN/合法signed负值/Calo政策不改；pz0>50GeV。不要从Stage19历史baseline.yaml恢复p0或fitted charge。所有原点/计数与重复坐标保留；几何无效明确整事件fallback/原因，不静默部分删点。观测空集合与源缺失分开，不按真E挑点或裁尾。

## 2. 已冻结架构与任务

名义几何及邻接按Stage105 protocol：四station各三层，z映射≤10mm，10维点为asinh(x/100)、asinh(y/100)、station4/layer3 onehot、z残差/10；10→32→32。k8 XY最近、同station相邻层双向、E≤16N，不跨磁铁/事件，不称真实共同粒子ID。68→32→32消息（destination32/source32/4几何边），incoming mean和64→32→32残差更新，两轮共享权重。每面mean32共384＋可见/实际count和状态meta26＋标量127，经537→64→64→1输出logE，无E>=pz clamp。

A消息仅MLP固定零68输入广播，各点仍完整独立编码逐面mean；B真实局部消息；C与B同架构，预训练只迁移point/message/update，监督head/其余模块按同seed重置。A/B/C同声明不声称有效容量完全隔离，C多预训练计算，主比较整个方案。

C恰一次原train-only预训练20epoch取最终状态，无cal/test无标签、无预训练checkpoint扫描。每epoch/key随机但固定seed选择九个downstream名义面之一，独立于实际活动/点数，允许观测空目标；名义plane不是已证active读出。先移隐藏面再构图/汇总，只visible坐标/plane/可见counts状态和hidden onehot，**不传原62标量、全局总数/矩、隐藏计数/坐标或truth**。目标257格观测SP计数（16×16的25mm格覆盖[-200,200)²mm，加overflow），422→64→257 decoder，softplus+1e−6 rate，格平均Poisson NLL去常数、原incomingweight。缺geometry无此目标，仅预训练明确跳过，监督仍全部保留。不造ghost/强子/共同粒子伪标签，loss下降不代替能量增量。

## 3. 必须先做的成本／程序准入

全部事件/数值工作在batch，当前终端不恢复CERN环境或复算模型。先相同40train/cal身份，0optimizer正常提取和CPU/GPU接线QA；Stage105没有Torch/GPU成本，也没有认证完整提取预算，其总CPU含逐查询暴力近邻对照，不能当正常提取外推。

核输入联结、B/C初始参数、全梯度有限/非零、点/事件置换不变、ragged无跨事件边、visible-only隐藏XY/数量扰动完全隔离，以及合成empty/missing/invalid/overflow分支。CPU/GPU max logE差≤3e−6。有效batch256做1warmup+3实测F/B（含传输/回传、预训练decoder）和真实峰显存；原40中最大1117点/11856边，无截断，微批≤16384nodes/262144edges，正确累加整个有效256的weighted numerator梯度。超大事件singleton，不能fit就停，不能截断高活动尾。

正常提取单独测basket/坐标/建边成本，按原280source和70332历史可读记录factor3+1000CPU reserve准入，所有提取/训练host/evaluation总CPU≤21600s。GPU用最慢实测full-train epoch外推×620（3×200+20）×3+600s≤7200任务wall，峰显存≤实际设备75%。准入后先完整train/cal坐标数量审计修正投影，optimizer前再次核预算，不提前读test实际点数/活动来调batch。任何超限保留已测结果并停止，不放宽合同或缩成有利子集。

最多1GPU并发/累计任务wall7200s；用现成Kubeflow或HTCondor GPU并实测，不为此扫设备。批量独立源提取/完整评价8CPU/申请8GB、内线程1，计实际ad/CPU/wall/读bytes/RSS/GPU峰。临时按角色坐标ragged cache≤512MB，边按需生成，避免逐hit副本/重复JSON；最终≤20MB，核字节/身份后删除坐标和传输包。spool统一~/condor/nu_muAnalysis/stage106/，不在home根建nu_mu_stage*。

## 4. 恰3fit、冻结与一次完整风险

单seed2026110506，A/B/C相同监督初始化策略及每epoch row shuffle，最多200epoch，Adam lr.001/betas(.9,.999)/eps1e−8/no decay或scheduler/dropout，clip10。incomingweighted natural-log MSE，完整尾保留。每5epoch原cal_select weighted pointMSE严格最优/最早tie选checkpoint，patience30epoch，无按低能/test选；C预训练20epoch固定无早停。恰3监督fit+1预训练，不加重启/seed/目标/epoch/任务或模型候选。

每格checkpoint后恰一个原cal_post mean(logtruth−point) offset。三checkpoint/offset全部冻结后才提取test点并一次完整推断/风险；raw/shifted均交，不test后回选。复用Stage87同split direct62和传统pz0/0.8，不用旧F7当同split科学控制。

主开发证据是原cal_post两低能C/A RMSE比的最大值，500次共同component内incoming配对95上端<1；B/A、C/B解释，不能事后换主比较。所有三格和raw/offset交原八层all、E50–100、E100–200、≥200、pz50–100、低pz真≥200、high-y、未确认，以及原高端/缺失/confirmed低transfer/X诊断、geometry_missing来源层。logRMSE、bias/R68、总/正/负tail50及配对区间齐全。原cal/test bootstrap seed2026110389/2026110390，复用相同draw，不存500draw副本。

最终两低能/传统RMSE比上95≤1.05；all/direct≤1.01；其余五层/direct≤1.03；**八层总/正/负tail50均相对direct_cal差上95≤+2pp**，不要把传统RMSE参考误套到tail。主增量不等于最终联合通过，不用预训练loss/NLL/AUC代替。点模型没有新density/PIT/coverage；开发test不是新blind，区间不含source/refit/offset估计/研究选择/response、interaction/FSI/材料/Calo/接受度/背景。

## 5. 停止和阶段交付

输入/角色无损或成本QA不通过就在optimizer前给精确缺口，不自动延长metadata链/重建。完整实验无主增量或最终未过，交有限机制结论与差距，不晋升、不续seed/深宽/遮挡任务，不宣布信息界或几何无用。有增量也先保留限制及原最终门槛，不自动执行Stage107或新生产。

先写中文Stage106 workbook，实际输入/数量/单位/命令/校验、全部成功与失败/资源/学习轨迹/checkpoint/offset/完整风险与尾/统计和物理程序解释、未测项目及明确下一任务，再相关源码/配置/紧凑证据本地Conventional Commit；不push。路线/信息计划历史只追加，Stage54下列原后缀逐字保留、五个资产不动，其实际完成以Stage85为准，不重做noise支线。

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
