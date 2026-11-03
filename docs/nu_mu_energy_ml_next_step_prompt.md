# 下一轮执行Prompt：stage78 损失互补与完整训练支持的条件风险组合

先读AGENTS.md、[stage77研究复盘](../workbook/2026-11-03_stage77_research-reassessment.md)、[stage73](../workbook/2026-11-03_stage73_reconstruction-energy-reweight.md)、[stage74](../workbook/2026-11-03_stage74_conditional-energy-hypotheses.md)、[stage76](../workbook/2026-11-03_stage76_exact-conditional-energy-decision.md)、stage58–60与路线§58/信息预算§38。最新物理实测仍为stage76，stage77仅研究，没有执行旧PHYS增补或本实验。保留F7，不把stage76分类分数密度叫校准后验，不继续其q/温度/估计器/架构续调。

本轮完整回答一个问题：stage73普通U与均衡F，加上传统μ的误差是否互补；使用完整训练支持和62读出学习条件损失差，能否在原风险门槛下将端点收益与困难组保护结合？这是新专家族/完整支持/嵌套来源隔离的有限检验，仍属专家组合，不将旧gate改名当新架构。

## 1. 输入与不可改变的物理合同

- 只用stage55 dataset、stage56 readout经audited_features.load/build的62列，stage73已有U/F raw来源OOF及fold/final模型和预测、确定性传统μ=log(pz/.8)；F7/stage73 S/stage76等既存结果作固定评价参考，不新推理F7、不把其训练内预测当OOF。
- 原nominal d32b0ff3、without-IFT、TI12MC04/FASERNU-04/OFLCOND-FASER-06，unit MC，train/cal/eval41447/8440/14057、91/16/22保守来源。原truth νpz/reco highest-pz leading>50GeV及其余选择不变；所有历史角色/曝光/incoming保护保留。cal/eval仍是开发，不是新blind。
- 线性模长/纵向仅pz0，保留px/py、q/p及弯折；11signed raw/VetoNu reduced、typed/domain/status/dependency NaN、合法负数与缺一Calo总和NaN保留，不fit补raw、不nansum。42缺失21/3/7 eligible＋11既有保护保持；全部high-y、未确认、巨大动量/负修正和尾不删。
- 本轮0新ROOT/RDO、重建、生成、stage70 π28加入、K重试、locked确认、谱toy或SHA。stage70 x不得再次缩放。旧PHYS支持交付完整保存在[独立协议](nu_mu_energy_ml_support_delivery_prompt.md)，作为数据准备入口，本轮不自动连开；缺谱系不阻断这次缓存开发，也不等于允许称独立确认。

## 2. A：当前专家族的损失互补，0新能量fit/推理

使用完整stage73 raw来源OOF U/F和μ；保持逐row、来源、incoming和fold。t=log(E/GeV)，h=(U,F,μ)。报告两低E、完整真E箱、高端、低reco pz两侧、高y/未确认/缺失的N/来源/唯一incoming、各误差方向和交叉矩C_g,jk=mean[(h_j−t)(h_k−t)]、共同大错及平方log损失集中度。常数log组合风险为wᵀC_gw；不能误用能量算术平均。

同时计算h_oracle=clip(t,min_j h_j,max_j h_j)的逐例凸包下界，含全部尾/未确认。它是这一有限专家族的真值知情乐观潜力，不能部署或叫观测信息极限；stage58旧μ/pz/F7下界不能代替新U/F/μ下界。

μ本身在专家集合中，所以凸包oracle的逐例平方误差必≤μ，也必≤U/F；不能拿“oracle低E达到传统”作准入条件，它必然通过。oracle仅作共同错误与潜力诊断，不能证明reco可识别。输入有效后在同一阶段直接推进B，由整个组合的留出风险裁决，不能只交诊断表后等待新指令。A不把cal/eval残差用于分区或权重设计，未来评价的oracle若另报必须明确仅为开发诊断。

## 3. B：一次固定分区与受约束凸组合

三个专家固定为h=(U_raw,F_raw,μ)，不增加S/F7/其他模型作可学习专家。监督损失差D_F=(U−t)^2−(F−t)^2、D_μ=(U−t)^2−(μ−t)^2，正值为相对U的收益；全部大尾保留，不只学winner类别或y类别。

每个实际头训练端以其OOF专家输出构造D，训练一个双输出DecisionTreeRegressor：max_depth=3、min_samples_leaf=200、criterion=squared_error、random_state=2026110378，最多8叶。两输出各除以本训练端RMS；为0时保持0并记录，不因held效果另改。输入为原62读出；若环境需缺失预处理，用本训练端finite median（全缺列填0仅作路由并加mask）＋明确missing mask，保持原基模型X原样。预处理只服务分区，不把填补后的值反馈到F7/BDT。不能把truth E/y、来源、身份或确认状态作为部署分区特征。

分区L(X)固定后，每叶三个w≥0且sum(w)=1，组合log能量f=Σw_L,j h_j。以epigraph τ最小化两低E的R_g(f)/R_g(μ)最大值；训练保护：R_all(f)≤1.01²R_all(U)，≥200/reco pz50–100/high-y/未确认≤1.03²R_g(U)。R均为本头训练端OOF平方log风险。U顶点可行，不要求两低E目标事前可行。

主问题为凸QC问题。用可用的有解析导数的求解器，一次预定起点U、预定容差/上限；有合适conic solver可直接使用，不能为了结果轮换优化器。主解后仅允许一次次级求解：在τ≤τ主解+1e−8及原保护内，最小化各叶按训练N加权的sum_j(w−U顶点)^2，以固定接近U的解，不扫正则。数值状态、实际风险/slack/恒等式独立核实；若未求得合格解，如实数值未定，不能当物理不可行或启动认证链。凸性不自动保证每次软件输出是全局解。

另用同目标/保护拟合全局常权重Q0，作为条件分区的机制控制；主候选Q_local_cal事前固定。两者都保留，不从控制挑赢家，不增加深度/叶数/专家/seed/dual/alpha网格。tail率不因均方约束自动安全，必须独立完整评价。

## 4. 整条管道必须嵌套隔离，最多12个新基模型fit

不能直接将原stage73完整OOF用于训练头，再按相同三折评价头：头训练行的基模型可能用过外held，形成整管道泄漏。

1. 外三折完全沿用stage68/73 v2，原held不删、outer train按exact incoming purge。
2. 每个outer train中按剩余两个原来源折作inner2折；inner train再purge与inner held共享incoming。每个inner train各fit U/F一次，共4/outer、总12新基模型。F由其实际train计数做相同七倍程箱均衡，均值1；完整stage73参数、400轮、seed2026110373、base_score=未加权实际train mean(t)/boost_from_average=0，不改容量/初始化策略。所有outer train行恰获一次inner OOF。
3. inner OOF构造D、分区树、Q0/Q_local；outer held用stage73已有对应fold U/F模型/预测和μ，再用本outer train冻结头预测。不能让outer held参与inner模型、任何预处理/树/权重/约束/停止选择。
4. 最终头用完整41447的stage73 OOF拟合，final专家复用stage73最终U/F。最终cal/eval冻结推理；不重训原8个outer/final U/F，也不把F7最终预测冒充OOF。

预算：12新基模型fit＋4分区树＋8凸问题（Q0/Q_local各三外折及final），每凸问题最多主/次两次求解，最多16次优化调用。原U/F已有模型只复用。科学候选为Q_local，Q0控制。记录全部实际train/held支持，内层低E/高端稀疏如实报告，不将多fold当独立生成。

## 5. 评价、成功与失败的解释

- 整管道41447各一次outer OOF，raw；最终Q0/Q_local报raw及原8440cal一个unit global mean-log offset，主Q_local_cal。raw/cal不择优，不分E校准，推理只读reco及冻结模型。
- 完整eval对传统、原F7、U/S/F、stage76固定参考；OOF只与真正存在的OOF比较。原门槛不降：两低E/传统来源95%上限≤1.05为恢复，正改善下限>0才叫超越；all/F7上限≤1.01，≥200/低pz/high-y/未确认≤1.03，原关键层总/正/负tail50增量上限≤2pp。
- 相对Q0的增量用于说明分区价值，不替代以上标准。报告全E箱、低reco pz的真低/高E两侧、高端/≥6400空层、缺失、mean/median bias、R68、双向tail50/100/损失份额、unit与macro。空层性能未测，正能量negative-tail100为结构性0。
- 500次component分层保守来源配对bootstrap，固定预测/头/offset，seed2026111378（cal+1、OOF+2）。不含重训/分区学习/校准/完整谱系/响应/研究选择，也不是各重叠门槛的联合95%保证。cal/eval已开发，任何通过只冻结研究候选，另需真正未开发确认及共同响应。
- 本固定分区族连训练都不能兼顾→记录风险冲突并转新响应信息/实际支持，不推广为所有reco策略不可行；训练可行而outer/eval差→支持/来源泛化；Q_local不优于Q0→本分区未测出额外收益；两低E好而其他层代价超标→仍只是风险前沿。只有同时过原门槛才安排候选确认。不据任何一项失败宣称全方法不可能，也不继续参数网格。

## 6. 资源与交付

先冻结上述科学政策，做解析风险/梯度、原row/两层隔离、NaN与X-only接口及小资源pilot。拟议≤4Condor任务、各1CPU/3000MB、累计CPU≤7200s、wall/job≤3600s、新紧凑产物≤20MB；实际成本/收益未测，代表性pilot后按实测冻结。输入一次打包、scratch复用，避免逐任务重复JSON/输入长期留存，不重建C++或安装整套环境。求解器缺失/资源不可交付时给具体最小阻碍，不自动训练其他模型。

本阶段交付应覆盖A及一次固定B；若实际输入/求解器/资源不能交付，说明具体障碍，不以oracle或metadata替代B，也不偷偷改变科学候选。中文stage78 workbook记录实际公式/支持/目标/全部风险与尾、泄漏控制、命令/CPU/wall/RSS/I/O/产物、程序与物理解释，下一项只能据结果选择一个。先报告后代码/配置/紧凑表图本地Conventional Commit，不push、不外发消息、不自动连开后续生产。

后备研究优先考察62列没有包含的脉冲形状/基线噪声/相对时序和μ条件响应；若取对象关系，要区别于已做的SP Deep Sets、局部计数与segment角摘要。不能在本次62列实验暗加新信息。实际π/K PHYS增补、真正新谱系/随机确认、stage54共同raw、interaction/FSI/材料、接受度/背景继续保留；不能用少量增补或概率评分代替最终单事例与物理目标。

以下stage54原后缀逐字保留，仅进入该支线时适用。

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
