# 下一轮执行 Prompt：stage102 一次原MDN训练轨迹，分别保存概率与点checkpoint

先读AGENTS.md、路线§83、信息计划§63、[stage101研究报告](../workbook/2026-11-04_stage101_checkpoint-and-information-reassessment.md)和[stage102冻结合同](../workbook/stage101_energy_ml/stage102_contract.json)，再核stage94原实现/协议。stage101只做研究，下一实验尚未执行。**本轮最多一条训练轨迹，两个checkpoint，不是两个fit；不重做五格九fit或stage99 T/classifier，不自动后续实验。**

## 1. 研究问题与固定事实

原E以NLL训练却按point MSE保存；三个seed旧point-best65/90/65，已记录NLL最低50/25/35，早期权重未独立保留。stage99唯一T改善概率但保持mean logE/点不变，不能改善低能点RMSE。stage10042新值有效但B没有使用新列，当前collection族停止；不是物理信息极限。

本次问题仅为：同一不变MDN训练轨迹，NLL选模相对point选模在out-of-selection支持上有何概率收益和点代价？不承诺低能恢复。原低能传统/direct/E94为.145661/.282644/.276027，全体direct/E94为.287491/.289843，联合风险仍未通过。

## 2. 输入、训练、可靠保存

严格使用合同的原stage87角色89033兼容记录、train/cal/test46575/11612/13189、17657隔离、incoming权重；原stage94 cal_partition select5443/post5746/purged423（后者仍完整cal评价）。全1016新增K/missing21/6/5/困难支持保持，无新样本/ROOT/native读取/生成/重建。

原stage94 E62typed值+62mask+wave_invalid/fit_failure/calo_invalid=127维，用原train-only preprocessing E状态；不要混入stage100 status/availability。pz0-only第一幂动量，允许px/py/q/p/弯折、raw11/status/typed NaN及合法负raw/charge/module_eta=-1/Calo缺项/pz>50GeV不改。源码 `ml/compare_energy_architectures.py` 是make/decode/objective和原训练循环依据，其他模型不重训。

唯一seed2026110494、原12937参数2x64SiLU/三Normal residual MDN around log(pz0/.8)、sigma=.05+softplus、float32/noAMP/noTF32、Adam lr.001/default/no decay/clip10、batch1024/原numpy permutation/incoming NLL。每5验证，原point-MSE patience30、最多300epochs仍控制停止；NLL准则只保存、不改梯度/停止。P取raw cal_select point-MSE严格最小，N取raw NLL严格最小，ties保留早轮；不预定50/65为新最佳。NLL-best仅是原point停止前已记录轮次中的最佳。

fit前one-attempt ledger；训练中原子持久化两state/epoch/score，结束回读并先保存预测后统计。0自动第二轨迹/seed/模型重启；失败能零训练回收/报告已存结果，不能悄悄重fit。两checkpoint选择和协议冻结前不载入/forward test。

## 3. 主要比较与完整风险

0新offset/T/局部校准优化。主比较两raw分布和mean logE点，b0/T1。唯一固定辅助为两格共同应用旧seed494 b=.02017839294662559，平移点和分量均值；无新拟合、不套ensemble b/T、不据test在raw/shifted中选赢家。stage99三seedT集成仅历史上下文，不当匹配优越性对照。

唯一主证据：原cal_post上raw NLL(N)−raw NLL(P)的500component内incoming配对条件95%上端<0；原subrole权重，cal/cal_post seed2026110389，test2026110390，按原incoming_draws。cal_post已历史复用，source/refit/参数/研究选择/response区间不覆盖。

主结果无论正负，完整交cal11612/cal_post5746/开发test13189两格raw及旧固定b：NLL、68/90coverage/宽度、meanPIT/十箱可靠性、原X组及真值/困难诊断；解析Normal-mixture CDF/逆CDF，不重开stage92积分。真E/y组不要求PIT均匀。mean logE后exp为点能量，交原八层全部RMSE及总/正/负tail50与500配对区间/传统/direct旧控制。0test择epoch/gate/拒绝预测/删事件。

两低E/传统上95≤1.05、all/direct≤1.01、≥200及困难/direct≤1.03、八层三向tail差上95≤2pp不改。概率主证据、点保护和最终联合通过分别记录，0自动晋升。当前test是开发池，不是新blind；同轨迹N/P也不是两个独立重训确认。

## 4. QA、batch资源与交付

数值QA/fit/推断/统计/画图全部在batch，不恢复本地CERN栈。先原qa_rows固定40 train/cal（21train/6cal missing）0optimizer实际包核身份/权重/原cal子角色/原变换/signed值、CPU/GPU forward/VJP/独立MDN密度/CDF及state回读；合同明确数值门槛，禁止事后放宽。记录实际batch1024成本后才准入。旧seed494保存model/head只读QA核原输出；新P跨平台不保证逐位复现旧P，量化差异，不把它归因checkpoint。

拟议最多1GPU batch/2CPU6000MB/内线程1、含QA任务wall≤600秒；报告申请8CPU8000MB/最多8进程、内线程1、共享已加载数组/同draw，阶段最多1并发，累计CPU≤1800秒/最终≤20MB。记录申请与站点实际、外层CPU/wall/峰内存/GPU allocated peak，嵌套计时不重复相加。GPU现状/token有效性和新成本未测，不能假定旧10h令牌仍有效；用可用的已授权GPU batch平台实测准入。

不准入、非finite、输入/QA不闭合或预算失败则保留state/row/head及精确问题，0自动重训/删事件/降容差/无限延长。无确证概率增量则结束本checkpoint比较，不追加seed/loss/局部校准或collection族；有概率收益也不自动扩新载荷或宣布低能恢复。

先写中文stage102 workbook（真实数值/支持/输入/命令/校验/资源/失败/未测/下一最小任务），再相关代码/配置/紧凑证据本地Conventional Commit，不push，不自动下一阶段。模型/head/逐事件表放忽略目录，去重传输包、不保存原生副本。历史正文只追加，原Stage54五项及以下后缀逐字保持。

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
