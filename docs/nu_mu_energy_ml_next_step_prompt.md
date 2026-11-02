# 下一轮执行 Prompt：stage63 联合μ/ML响应的一个低能物理参数

先读AGENTS.md、[stage62实测](../workbook/2026-11-02_stage62_smooth-continuous-response.md)、[stage61研究复盘§5](../workbook/2026-11-02_stage61_research-reassessment.md)、路线§43及信息预算§23。stage62三个fit已完成，不重跑prepare/fit/collector、不覆盖历史协议。当前继续F7；这次只执行联合物理响应研究，不追加能量训练、网络/先验/估计器扫描。

## 已知结果与唯一问题

stage62完整读出相对μ-only有跨22来源的概率增量，但主候选低E log-RMSE=.277739/.259126，传统=.145487/.226876，总体比F7差2.105%，原始及校准推广均失败。训练unit/flat在共同先验下粗概率TV=.145348，不能称消除先验依赖或精确互信息。完整分布有用不代表一个点已经兑现物理收益。

本次回答：**在相同支持/有限模板MC/来源与形状压力下，显式保留μ约束与ML修正轴，是否比灵活scalar F7更可靠地约束选中低能成分？** 不重做stage23–30 full-q或六自由箱反演；旧full-q未胜灵活scalar的阴性继续保留。

## 1. 输入、参数和执行前冻结

1. 复用stage55/56紧凑缓存、F7三个模型`ml/artifacts/stage56/{2026110255,2026110256,2026110257}/model.ubj`和cal/eval预测。只在必要时对train推理已有F7，验证cal/eval预测及global offset与stage56精确一致；0新能量fit。F7的62列、pz0-only线性动量、11raw/VetoNu reduced、合法负数/状态/依赖NaN规则不回退。原pz>50选择、train41447/cal8440/eval14057及全部来源/事件保护不变，不读locked test/ROOT/RDO，不生产、不补alternative raw、不恢复大文件。
2. 不删缺失/负修正/溢出/高y/未确认/大尾。原42缺失eligible21/3/7、另11原保护保持。cal/eval已开发，不叫blind；unit选中MC不冒充正式flux/接受度/背景。完整生产谱系独立未认证。
3. 主参数固定为选中true50–200相对≥200成分强度r，参考f0只由train确定，固定总N=1000：`f(r)=r*f0/(1-f0+r*f0)`。r=1为参考，实际真低E比例用于闭合标签，不能读入部署统计量。报告sigma(f)、sigma(r)/r及其范围，说明只测selected-spectrum形状，不测未选中flux。不得同时自由浮六能量箱。
4. 在任何新灵敏度/闭合结果前冻结不可覆盖stage63协议，记录目标、分箱/零计数处理、模板、有限MC算法、来源定义、压力、profile/停止判据、资源与验收。先小样本核标量映射/权重归一/有限MC公式及计算成本，不用eval挑布局或压力幅度。

## 2. 三个公平响应与有限MC

1. 可部署统计量：M=log(pz0/GeV)；S=log(E_F7/GeV)；J=(M,S−M)。F7取三原始log预测均值加同一已保存global offset。联合修正可负，不硬施E≥pz。三表示用同一事件与truth组件定义，不通过缺失或压力筛选改变支持。
2. 默认同名义容量16常规格：M和S各用train的16等占据分位箱，J用train M四分位层、每层修正四分位，共4×4。边界外以±infinity保留，统计量无效有明确独立missing分支。重复分位边界只按冻结规则合并，并记录实际容量；不看结果增加箱数/平滑。原输入有NaN但F7能推理者继续正常落箱，不给μ-only额外输入全X状态。所有边界仅由train冻结。
3. 每表示构造低/高两组件响应及来源计数，报告稀少/零格、有效样本量和统计支持。先给固定模板的Asimov/profile曲率，再用明确有限模板MC约束profile（例如固定总N的数据多项式与两组件MC多项式约束，组件概率带simplex约束）。若采用等效Poisson方法，说明归一化/曝光参数及与条件模型关系；不能只加任意伪计数后称处理了有限MC。算法/数值选项在结果前冻结，保留边界/收敛诊断。
4. 同一参数化/数据/模板MC同时比较M/S/J。报告有限MC前后误差；不拿更多维/不同MC或错误归一化来制造优势。500次component分层来源配对区间用于固定分箱下的来源稳定性，可用经pilot冻结的曲率/误差重算，不重新训练F7，不增加coverage toy。明确来源bootstrap与模板MC约束的不同含义及未包含的detector/interaction系统。

## 3. 来源闭合与事前形状压力

1. 模板只由train构造，cal/eval的独立保守来源用于留出闭合；与各自实际truth低能比例对应的r_true比较，不能把train f0与cal/eval组分混合差直接当响应偏差。报告总体与逐来源/预定汇总支持；零低能来源保留并标明边界/无定义pull，不能只留两组件都漂亮的来源。不要把已暴露eval叫新独立确认。
2. 将cal/eval的经验响应按同一总N=1000做Asimov闭合，并报告实际有限事件支持对其限制。主比较为J/S的sigma(r)比和闭合偏移/统计误差，M为物理对照。nominal已知响应曲率变窄不足以成功。
3. 两类预定压力均只叫敏感性，非正式1sigma：低组件内部50–100相对100–200形状；高组件内部同reco pz50–100的high-y≥.8混合。默认对目标子类乘1±.25并在其truth组件内重归一，保持总f(r)与N不变；明确覆盖/N/来源。所有事件保留，权重不为负，不用truth改部署统计量。精确幅度/归一化在新结果前冻结，不按压力结果改箱/调模型。
4. 验收需要J相对灵活S有来源稳定的误差降低，并且名义闭合与两类压力没有与之相比明显更大的偏差/不稳定。建议事前量化：误差比95%上限<1支持统计增益，名义/压力偏差以sigma单位完整并列；若要设偏差门槛须先冻结，不能结果后放宽。MC/来源不足写未定，不把未定称成功。失败则保留阴性、停止扩维，不追加更细箱/六参数/网络。

## 4. 预算、报告和停止

0新能量fit、0生产/ROOT、0谱coverage toy。先pilot实测profile成本再冻结有限计算，拟议≤2个Condor任务/每个≤2CPU与3GB、累计CPU≤1h、紧凑最终≤10MB；批量经Condor，小QA可交互，不静默追加预算。只保留模型复用说明、紧凑模板/曲线/结果，不复制输入或保存大事例网格。记录wall/CPU/RSS/实际I/O，文件大小不当网络字节。

写stage63中文workbook，包含实际N/来源/输入/选择/参数/命令、实测数值与单位/区间、有限MC/闭合/压力、技术问题、资源/产物、结论和具体下一单项验收；更新路线/信息预算/Prompt后本地Conventional Commit，不推送、不自动部署或启动下一研究。stage54已有工具/缓存保持原状且不混入提交。

有稳健联合收益才连接有依据nuisance、接受度/背景和新独立来源；无增量则停止这次扩维，转共同raw/响应或定向独立低E及同p困难样本。共同signed/rectified raw差异、stage54占据、ν interaction/FSI/材料、真实独立确认仍必须交付；不把有限选中MC条件研究称最终flux结果。方法入口沿用stage61的有限MC模板与FASER flux论文。

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
