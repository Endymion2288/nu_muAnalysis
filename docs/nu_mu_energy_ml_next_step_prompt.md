# 下一轮执行 Prompt：完成低能三物理专家组合，而非只增加诊断

请在具备 CERN 工作环境的终端执行本轮有界研究。先读 AGENTS.md、[stage57研究报告](../workbook/2026-11-02_stage57_low-energy-research-reassessment.md)§2–5、[stage56实测](../workbook/2026-11-02_stage56_model-feature-validity.md)、stage55、[F7契约](nu_mu_energy_ml_features.md)和修订路线§38。stage57只检索/分析，没有新训练结果。若终端仍无工作环境，只完善执行协议和缺失输入，不伪造结果或在别的环境重复物理计算。

## 0. 当前主任务：同一阶段完成诊断、组合与决策

目标：在 true Eν=50–100 和100–200 GeV 恢复/超过传统方法，同时保住全体和高E/high-y/未确认leading收益。两种低E与两种reco低p分层各自保留，不按truth gate推理，不把低reco p整体切回传统。

当前 nominal train/cal/eval=41447/8440/14057；F7 全体/true50–100/100–200 log-RMSE=.296363/.312816/.265014，pz0/.8=.568069/.145487/.226876。低E训练0→767已证实有效，但+139替代flux、普通残差、全局offset和F7输入修订均未解决；不重开这些扫描。

**输入约定不可回退：** F7_pz0_raw_v1，62列；线性动量模长/纵向量仅pz0，允许px/py、q/p及弯折；不用p0/p1/pz1/log比，11闪烁体用raw_charge，保留VetoNu reduced。所有变量经过`ml/audited_features.load()`/`build()`的状态、有效域和派生依赖，不绕过build只拼matrix；合法负值保留，42个新标缺失calo事件、high-y、未确认者及全部大尾保留。原选择仍含fit-charge cut，不在本轮改接受度。

本轮按以下顺序自主完成，不停在诊断表后再请求启动已列明的组合实验：

1. **复用已有数据。** 读取F7紧凑缓存和`ml/artifacts/stage56/predictions.npz`的`cal_row/eval_row`、`cal_raw_log/eval_raw_log`；三seed平均log预测。保持现有保护分区。0新能量模型fit、0ROOT/RDO重读/新生产、0谱toy/SHA。alternative缺当前raw补充，不混用F6预测冒充F7。不读历史locked test，不恢复重复shards/transport。
2. **结果前固定四格。** pz0为50–100/100–250两层，各用本层train的Timing0–3 raw有效总和中位数分两格；仅train X定边界，不用eval或truth挑阈值。求和传播缺失，负数合法；Timing缺失和pz0≥250默认F7。counts/Calo只作本轮同格诊断，不增加边界搜索。先记录实际cal低E/困难组及来源支持，保护前150个cal低E不能当当前支持。
3. **建立三个专家。** t0=log(pz0/GeV)，tμ=log((pz0/.8)/GeV)，tF=F7 log能量。主候选为各格内非负、和为1的log输出组合，二专家w0=0为消融。pz0只作小transfer参照，其ν能量表现未测，不是产生面μ校准。
4. **只在cal开发组合。** 按保守generation/source groups作三折、尽量维持component支持。每折F7 offset只由其余cal原始预测计算，在其余cal拟合权重，再预测留出cal；不能套全cal offset冒充OOF。两族各三折+最终全cal，共≤8次低维组合优化，0新F7训练。全cal最终offset/组合拟合后，冻结评价完整14057例。cal改为组合开发集；eval仍是已暴露开发检验，不叫blind。支持不足或空组明示，不用eval补训练；不增加大门控网络。
5. **优化真正的低E取舍。** 以两低E组相对传统log-MSE的最大比值最小化；约束全体对F7 log-RMSE增加≤1%，trueE≥200、reco pz50–100、y≥.8、未确认者各≤3%（MSE约束用1.01²/1.03²）。同主目标的解以全体风险作次级选择，不扫λ。真值仅用于训练目标/诊断，权重查表只依赖读出。所有格取F7是代价约束的参照；达不到低E≤传统时量化最佳取舍，不改门槛宣布成功。
6. **一次完整报告。** 比较pz0、pz0/.8、F7、二专家、三专家；报true50–100/100–200及完整能量箱、reco低p、high-y、未确认者，N/来源、log-RMSE、mean/median bias、R68、正负tail50/100。预定恢复标准：两低E相对传统RMSE比的来源配对95%上限≤1.05；超过传统须改善下限>0。全体/困难组代价按上述1%/3%同验收，默认关键组tail50增加不得>2pp；这是拟议研究取舍，不是已测系统范围。500次来源分层bootstrap条件于最终模型；另报cal OOF来源/折间波动，不把固定模型区间说成全流程确认，不追加数百次组合优化。
7. **给出能决定下一投入的结论。** 只作诊断地计算真值投影到三专家log输出区间的理想损失下界，明确不可部署、不是通用信息极限。组合有效则冻结并规划独立低E/共同raw确认；理想下界好但粗格失败则定位gate/支持缺口；理想下界也无低E突破则转小transfer响应或连续E条件似然比。新生产、神经似然和多头模型不在本轮自动连开，给出下一次单项可执行方案即可。单个粗格阴性不能关闭整个低能方向。
8. **交付。** 小样本先核实现，记录实际wall/CPU/RSS/I/O和紧凑最终产物；新成本未测不能引用旧秒数。写下一编号中文workbook，含实际数值/单位、样本/选择/配置/命令、程序与物理原因、区间限制和下一科学决定；更新路线后本地Conventional Commit，不推送。保留stage54未完成支线及其他人的文件，不能沿用旧报告文字就认定当前仍有未提交文件。

已知当前MC raw有符号整窗积分与data旧源码正样本积分不同，噪声/活动响应也未闭合。当前MC方法研究可继续，但不宣称data改善；共同定义、stage54占据、interaction/FSI、材料、独立生产和最终能谱物理收益继续必须交付。

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
