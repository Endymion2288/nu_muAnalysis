# 下一轮执行 Prompt：stage96 冻结候选几何的两格匹配输入消融

先读AGENTS.md、[stage95报告](../workbook/2026-11-04_stage95_track-candidate-information.md)、修订路线§77、信息计划§57、stage93研究复盘与stage94 cal协议。**stage95信息测量完成；本轮恰两fit检验新增轨迹候选/leading几何。不要重复stage95小队列测量，不自动执行stage97。** 下方stage54为保留历史支线，stage85已完成条件活动控制，不因此重做。

## 1. 已测依据与问题

stage95固定2048个不同train/cal incoming、一视图，24source中22可读，1923事件/2110候选/227边。125个源载荷因历史临时PHYS清理不可用，原摘要/身份/K支持不丢。多轨迹153，leading未确认132，其中4个备选primary确认；最低真E50–100GeV的81个可读者均单轨迹。换leading已确认机会有限，不表示次级轨迹几何对Eν无用或达到信息极限。μ-pz truth oracle只改善2例，不是ν能量oracle。source/X富集队列不当自然flux，matching未确认不能当物理无μ。

Track_hitSet是层/面覆盖24bit，实际52事件与保存track不等长，不是共享hit ID。禁止按位交/截断强配构造共享hit或重复判据。Calo/VetoNu/Timing共同参考面z=2760/−3112/0mm，坐标有效2110/2108/2109；没有逐轨迹实测协方差或通道读出关联。保留22维节点＋5维leading-to-other几何边的`track_candidates_leading_geometry_v1`，见stage95 representation/source_semantics。当前表以原index存储，consumer按有效pz0降序/index稳定排序，保留所有无效候选与mask，无截断去重；原端点可不同z。

本轮回答：**在同62 typed摘要、同模型声明结构/目标/预算/后处理下，新增候选和leading几何是否改善能量风险，尤其最低能与低pz真高E/high-y？** 不用truth gate选备选，不把集合分支效果全归因为primary替换。

## 2. 输入扩展与先行QA

复用stage87 89033兼容池、46575train/11612cal/13189test/17657隔离及incoming总权重，stage94既定cal_select5443/cal_post5746/冲突423仍全cal报告。全部1016新增K、missing21/6/5、低能/低pz/未确认/high-y/高端/尾保持，不重划角色、不新MC或reconstruction。主体pz0>50GeV；一次方动量只pz0，允许px/py/q/p/弯折，不加p0/p1/pz1或动量比。raw11/status、合法负raw、typed NaN、Calo缺项合同不改。

从既有完整source清单按精确source/entry/incoming联结向原完整角色扩候选输入；只遍历已知清单，不递归扫EOS。stage70/82临时PHYS删除的来源保留原摘要及candidate_available=False，不能将其当0轨迹/替换来源/丢K；其他源schema差异如实标缺。每个原事件重建视图保持原行和incoming权重，不能把所有轨迹当独立训练事例。truth只另表作最终诊断，不进特征、候选排序/选择或超参准入。

先冻结≤40个不同train/cal incoming（原QA可复用，跨新来源需预先整体给定名单，总计≤40），覆盖新增source schema、低pz与missing/失败；若所有来源不能逐一覆盖，说明按schema/production分组覆盖及残余风险，生产worker仍逐源核schema/联结。核typed占位和合法负数、raw/status/leading pz闭合、空与缺集合、候选重排不变性/leading边对齐、batch前向反向finite和实际CPU/GPU成本。仅forward/backward QA，0optimizer试训；不得先看候选test或能量诊断调模型。原小队列有样本不代表全源全部字段可用。

两格模型/特征/资源和评价协议在新test候选载荷准备前冻结。完整test候选仅作为最终评价输入；test真值/预测/分层诊断到两fit及cal后处理固定后才打开。原研究池不是新blind，不能宣称独立最终确认。

## 3. 恰两fit与冻结表示

固定一个seed2026110496，两格使用同声明参数量、初始化规则、训练与后处理：A仅62摘要且新增分支恒定，B同摘要＋真实候选/几何。A用固定dummy集合/掩码和常数availability/count，禁止通过padding形状、缺源标记、pool分母等泄露真实新信息。B区分candidate unavailable、真实空和逐值missing，不拿truth代替缺值。同结构不自动证明有效容量完全一致；报告实际参数/梯度和限制，不称家族最优。

唯一小模型：节点22值＋22缺失mask，共享2×32 SiLU编码；masked mean/max和leading表示；5边值＋5mask，经2×16 SiLU编码后masked mean/max；联合原62摘要typed输入（沿stage94预处理）、availability/empty/count，接2×64 SiLU点回归head。没有边时pool固定0且mask显式，B保留所有候选、leading到其他候选稀疏边。A新增分支输入恒定但保留相同计算图/声明结构；QA后在未看新cal风险前记录精确维数/参数，不能因评价表现修改结构。

新正域pz0用log、非负计数/距离log1p、signed连续asinh、离散identity和独立缺失mask；尺度/中位/IQR只train拟合，复用stage94摘要typed规则、不任意截断。边距离不是显著性，x0/y0端点距离不冒充同面距离；hitSet/true matching/真E/y都不进模型。输入类别规则在QA后、cal候选风险前冻结，保留精确配置。

两格都incomingweighted log-MSE、Adam lr.001/default betas/无decay、clip10、batch1024、NumPy seeded permutation，最多300epochs/每5轮cal_select验证/patience30epoch，按cal_select点MSE选checkpoint。仅两fit，无额外seed/预训练/warmstart/候选扫描；训练曲线train/cal objective和点误差保存。原cal_post只一次全局log-offset，raw/offset分列，不能按真值分箱校准或test选gate/offset。旧传统/direct/stage92/stage94预测复用，不重训旧控制。若QA发现schema无法交付，就报告可交付输入和缺口，不开始不匹配训练。

## 4. 并行、成本与完整验收

批量候选提取/评价必须HTCondor；足够独立source分片申请8CPU、内线程1，单文件复用basket/范围缓存，避免每个进程重复全文件打开。stage95实际37.848wall/159.512childCPU秒仅为1923载荷小队列，不能直接承诺全池成本。先≤40实际包QA计时/内存/字节，冻结全源投影与准入；拟议阶段CPU≤21600秒、GPU任务累计wall≤7200秒/1GPU并发、紧凑最终≤20MB。没有实测优势的提取不用GPU；两fit优先授权GPU batch（HTCondor GPU或Kubeflow，使用仍有效的用户令牌），不重用过期凭证或无限排队。记录站点改写的实际资源，不能把分配核数当使用核数。

默认完整原train/cal/test；资源不准入则交真实已完成状态/输入与具体缺口，不自动删困难者/缩有利子集/加预算。节点表只保留紧凑数值/掩码/稀疏边，不存逐hit点云或ROOT/xAOD副本；共享原缓存不复制，完成后清传输重复归档。统计按role/stratum有足够独立任务时4–8CPU复用incoming draws，报告单核/多核实际成本；只有限小QA和轻量保存表核验在交互节点。

完整cal/test报同一预测的低E50–100/100–200、all、≥200、低pz、低pz真高E/high-y/未确认/高端/missing与全部正负tail。保留原两低能/传统比上95≤1.05、all/direct≤1.01、≥200及困难/direct≤1.03、原七层加低pz真高E的双向tail差上端≤2pp；两格配对500component内incoming条件重抽（同incoming多视图一起移动），报告条件限制/source95未测/单seed不含重训分布。另给新增信息A/B差、可用/不可用来源与单/多候选的事前X组支持，不能用事后分组挑主模型。点回归无概率密度，不编造PIT/coverage；可复用旧概率诊断但不冒充新分布输出。

成功是一次可复核的新增信息对照及完整风险/成本结论，不要求GNN收益或强行晋升。最低能/困难未联合通过就继续既有部署，不能因4个恢复例少就取消整个关系信息实验，也不能从负结果断言信息极限。真实response、interaction/FSI/材料/Calo/接受度/背景与最终未开发确认仍待完成。

## 5. 交付

先写中文stage96 workbook，记录精确输入/身份/来源/选择/缺源、配置与命令、两fit曲线/参数、全部数值/单位/区间/图表、联结和程序验证、实际资源/I/O/保留字节、失败/未测项和下一具体任务。再与代码/紧凑manifest和表图本地Conventional Commit，不push、不自动进入stage97。历史路线/信息计划仅追加，保留下方stage54后缀逐字和原五项工作树。

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
