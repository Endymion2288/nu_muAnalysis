# 当前交接：执行 Stage112 已有 PHYS 的选择与响应机制实验

先读 AGENTS.md、路线§93、信息计划§73、[Stage111研究报告](../workbook/2026-11-05_stage111_selection-response-reassessment.md)、[冻结合同](../workbook/stage111_energy_ml/experiment_contract.json)、[六源manifest](../workbook/stage111_energy_ml/source_manifest.json)和[Stage110实际报告](../workbook/2026-11-05_stage110_bdt-anchored-relation-transfer.md)。用户明确要求“没有新输入，请重新研究并制定下一实验”；Stage111已完成研究设计，**Stage112尚未执行**。后续用户按路线继续时，执行下述一次实验；不是再复盘或重做Stage110。

## 1. 科学问题与边界

其余名义MC cuts保持，reco pz0>50 GeV在多大程度上改变了低能样本的传统估计器风险、真实能量转移和μ纵向响应？此前Stage73只对已选事件作分解，没有共同父分母。测量选择效应不能独自解释模型失败，且确定选择在完整X的选中支持内不改变p(t|X)。

原Stage110主cal_post最坏两低能比1.001249542 [.988791330,1.027119908]未通过，test最低能局部收益准确保留、最终jointFalse；不扩α。Stage108三格/遮挡及旧门控/重权结束。0新模型fit/forward/offset/温度或阈值优化，0生产/重建/谱toy/广泛EOS搜索；不对pz≤50做无支持的BDT外推。模型收益和新效应仍未测。

## 2. 输入与人口定义

严格使用manifest的六个完整PHYS，π/K/charm×历史train/cal各一源；数值最小(origin,source_index)事前规则，无可读性/产额/效应筛选或替换。六源stat存在、逻辑275663702bytes，schema/entries/产额未测。其为便利PHYS父分母，不能称GENIE/输运/full incoming接受度或自然flux。

G0=所有有效名义MC cuts去掉reco LeadTrack_pz0>50，保留truth νpz>50、拟合电荷、质量/几何/有效requires。G+=G0且正有限pz和Eν；S50=G0且pz0>50，S100只历史对照。不改旧选择/角色/隔离/全部K。完整PHYS和G0中无效/未知/无轨迹分别计数，NaN不补0。

batch只按合同白名单读Stage87 split身份字段；test>cal>train，已知test-key仅保留完整cutflow计数而隔离主要开发对比，不读取test-only PHYS/特征/预测/风险。source+entry核run/event；旧隔离不被source角色覆盖，新父entry只diagnostic-only、不加入训练集。incoming为精确原生MeV四元组代理，不冒充真实独立谱系。

每源内eligible incoming全部父视图权重合1，选择前冻结、不在幸存者重分；主端点六源等权不是物理flux。源/角色/支持/冲突/未知和record-weighted控制完整交付。

## 3. 一次比较与输出

真[50,100)/[100,200)GeV各报一个预定主端点：六源平均的传统pz0/0.8 **S50∩G+减G+ log-MSE差**；0.8固定，不拟合offset。任一来源任一边无支持，该六源主端点不可估，不丢源重归一。两箱均报，效应正负/零都可完成。

同子集唯一真主μ有效时：r=ln(pz0/Eμ_vertex)、u=ln(Eμ_vertex/Eν)、c=ln0.8，逐例e=r+u−c及完整六项平方分解，交叉项保留。r含角度/材料/参考面/错leading，不等于纯tracker分辨率。主风险保留未确认/主μ未知；分解缺支持单报。

完整cutflow/独立fail和unknown、native-invalid-through-cut影子审计、两侧RMSE/偏差/R68/总正负tail50、incoming/权重和/ESS、truth transfer/y<.2、主μ有效和确认率、顶点z/radius及固定E/pz箱和原八层/高端/困难/未知状态。不clip非物理truth ratio来改善曲线。

固定seed2026110512、500次全键Poisson(1) cluster共同乘数bootstrap，两选择成对、源/视图权重固定，同键跨源共用乘数。percentile95区间至少475有效draw才报；不能重抽到够数。仅条件于六源，不覆盖source/refit/研究选择/系统/新blind；不拿两源/成分冒充外推认证。

## 4. 必须一起完成的程序核验与资源

优先用现有匹配build，显式配置路径并存有效requires/aux/校准和实际命令。最高pz0 leading保持；adapt truth_diagnostics空轨迹/空真值/多候选路径，一entry一记录，不用flatten压短。SafeAt NaN、非负/count的−1/−999/unsigned-wrap、合法signed raw/charge sign/module_eta，以及fallback−1234“无需fallback”分清。原模型typed62/raw11/status/Calo缺失传递保持；旧Veto/Timing/Preshower切选仍有fitted charge，本轮记录其失效影响，不能未经标定换成raw同阈值。

单阶段内完成≤40真实QA：六源各最前4entry，加原Stage105六源记录按row最多16条、去重不补；合成empty/unknown/sentinel另核。schema/entry完整metadata先读，每源≤20000、总≤120000，否则不截前缀。原生S50完整成员与独立掩码完全一致；旧缓存只核交集、不是完整selected父分母；native pz差0GeV、truth E相对差≤1e−12、逐例分解≤1e−12/汇总≤1e−10。

单HTCondor6CPU/12000MB/6worker、内线程1、0GPU；spool ~/condor/nu_muAnalysis/stage112/。CPU≤3600s/wall≤900s/接口≤2GiB/临时≤128MiB/最终≤20MB。QA实际成本和完整branch/basket/entries作factor3保守投影，另留CPU300s/wall120s/接口128MiB；预算不通过交具体缺口，不循环更换规则。只读必要标量、truth和关联向量、复用basket，不保存SP/波形/xAOD；紧凑暂存后去重，外层CPU/wall/RSS和真实请求bytes实测，不混加嵌套计时、不把逻辑大小当物理网络。

## 5. 停止与交付

一次完整六源测量后结束，零/反向效应同样有效；缺源/schema/aux/闭合/资源不达交精确原因，不替换源/延长metadata阶段/自动加预算。若invalid-through-cut存在，保留原生结果和数量，另冻修正合同，不能先修后称风险变好。结果可量化选择组成并指导未来双侧支持，不能自动改cut/训练/扩源/生产/晋升。

先写中文Stage112实际workbook及紧凑汇总/图/验证/资源，再本地Conventional Commit，无push。Stage111研究已完成不再重复。原两低能/传统上95≤1.05、all/direct≤1.01、其他五层/direct≤1.03，八层三向tail差direct上95≤+2pp保持；真实response/interaction/FSI/材料/Calo/接受度/背景及新独立确认仍待交付，整体项目未完成。

Stage54五资产和以下历史后缀保持，noise支线实际状态以Stage85为准，不自动重做。

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
