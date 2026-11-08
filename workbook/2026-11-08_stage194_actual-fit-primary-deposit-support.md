# Stage194：原拟合cluster的实际主μ正权沉积支持

日期：2026-11-08。接续[Stage193](2026-11-08_stage193_IFT-parent-fit-support-accounting.md)，在相同160父上直接读取原fit的PRD strip/SDO/HepMC指针，区分barcode成员记录与实际主μ正权贡献和缺失SDO。**没有改变原leading选择，没有新轨迹fit、IFT运输、G4或能量模型。** 此控制回答条件宽尾的拟合贡献支持，不能直接给真实data错轨率或覆盖，Stage191固定能量阴性及整体未完成保持。

## 目标、原输入及固定定义

[协议](stage194_energy_ml/protocol.json)在本阶段实际fit-strip读取前冻结。原MC100012前64和π/K/charm各32train，原16pilot/全160无替换。完整路径/entry在协议；使用Stage188原 `CKFTrackCollectionMergeWithoutIFT` 的cached collection index，并严格断言pz0/charge及全部原barcode逐cluster贡献计数不变。原确定性 `MergeTrackCfg` 仅恢复同一collection，不改forward/backward候选、共享hit规则或拟合，不按新truth标签挑轨迹。无轨迹、无原匹配、缺面父全部保留。

gcc13小bridge沿实际TSOS取每个SCT ClusterOnTrack的PRD和rdoList，保存PRD是否存在、实际state index及全部原strip ID；对这些strip调用Stage192已使用的实际TruthEvent/SDO指针解析。GenEvent必须恰1，唯一主μ与正stored-weight的四类定义原样保持。正weight单位未校准，不当dE/dx或测量概率；无PRD/空strips明确unknown。几何04/tag06，复用现成runtime，只有小bridge编译。

固定四fit支持分组为graph_unknown、no_fitted_track、至少一个fit-strip正权真实主μ指针、无此正权指针。最后一组不自动称错轨，因为SDO可不完整；另外明确记录“所有fit clusters均解析且没有直接主μ”的父N。已解析非主μ也可能是主μ产生的物理次级，不能自动当电子噪声。

IFT部分完全复用Stage188预测和Stage192分类，只汇总原匹配/起始面支持/几何界内的纯直接主μ候选N/Σpull²/RMS；不在本阶段重新传播或删除大残差。新fit-cluster标签仅用于这个MC机制控制，不进入训练/selection，更不反演动量。原Stage87、全部K/角色/隔离/reserved、pz0-only、raw/合法负/typed NaN/status0及所有八层三尾/低能门保持。

## pilot、准入和完整实测账目

pilot16原身份、leading index/pz0/charge/barcode计数闭合，原μ及ν都有主μfit支持。内部80.114518201 CPU秒/120.655435659 wall秒、ROOT请求17670830B、峰RSS1741412KiB。完整pilot+compile GNU 110.640000 CPU秒，三倍投影494.007313440<600 CPU秒才准入full160；预算1200 CPU秒，pilot400/full600/audit200，无扩大旧192/193预算。

各cluster四类为pure=纯直接主μ、mixed=混合直接主μ、other=已解析无直接主μ、unknown=未知。表中“全other父”要求所有fit clusters均可解析无直接主μ，空轨迹不计；IFT RMS无量纲、份额分母为同source全部原纯直接主μIFT候选的Σpull²。原父N包括无匹配/缺失，候选相关，分数不是独立事件率。

| 来源 | fit正权支持组 | 原父N | fit cluster N | pure | mixed | other | unknown | 全other父N | 原IFT候选N | IFT pull RMS | IFT Σpull²份额 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|MC100012|all|64|1063|1040|0|0|23|0|102|1.59598235|1|
|MC100012|graph_unknown|0|0|0|0|0|0|0|0|NA|0|
|MC100012|no_fitted_track|3|0|0|0|0|0|0|0|NA|0|
|MC100012|direct_primary_positive_pointer|61|1063|1040|0|0|23|0|102|1.59598235|1|
|MC100012|no_direct_primary_positive_pointer|0|0|0|0|0|0|0|0|NA|0|
|pi_0|all|32|557|529|0|17|11|1|139|1.10498685|1|
|pi_0|graph_unknown|0|0|0|0|0|0|0|0|NA|0|
|pi_0|no_fitted_track|0|0|0|0|0|0|0|0|NA|0|
|pi_0|direct_primary_positive_pointer|31|540|529|0|0|11|0|139|1.10498685|1|
|pi_0|no_direct_primary_positive_pointer|1|17|0|0|17|0|1|0|NA|0|
|k_48|all|32|551|542|0|0|9|0|169|1.12849124|1|
|k_48|graph_unknown|0|0|0|0|0|0|0|0|NA|0|
|k_48|no_fitted_track|0|0|0|0|0|0|0|0|NA|0|
|k_48|direct_primary_positive_pointer|32|551|542|0|0|9|0|169|1.12849124|1|
|k_48|no_direct_primary_positive_pointer|0|0|0|0|0|0|0|0|NA|0|
|charm_113|all|32|566|515|1|35|15|2|149|17.6600277|1|
|charm_113|graph_unknown|0|0|0|0|0|0|0|0|NA|0|
|charm_113|no_fitted_track|0|0|0|0|0|0|0|0|NA|0|
|charm_113|direct_primary_positive_pointer|30|531|515|1|0|15|0|140|1.21652307|0.00445861222|
|charm_113|no_direct_primary_positive_pointer|2|35|0|0|35|0|2|9|71.6956688|0.995541388|

charm的2个无主μ正权fit支持父，35个fit clusters全部解析为非直接主μ、unknown=0、无strip SDO缺失=0；它们仍占原纯主μIFT候选Σpull²的0.995541388。这直接排除了这35个cluster仅因缺失SDO而被分入无主μ的解释。π另1父17个fit clusters也全部解析为无直接主μ；K没有此父，μ控制的3个原无fit父保持无fit，不据此算总体误识别率。

| 原charm run/event | 原pz0/GeV | 原真Eν/GeV | fit cluster N | 已解析无直接主μ N | 无SDO/unknown N | 原纯主μIFT候选N | 原IFT Σpull² |
|---|---:|---:|---:|---:|---:|---:|---:|
|200089/944|52.6450546875|188.08|18|18|0/0|5|208.73630641617737|
|200089/1094|75.412859375|875.07|17|17|0/0|4|46053.68405440949|

这两父均在原50–100GeV低pz区，但不是真E50–100GeV箱的代表；真E分别来自协议的原incoming能量，未换成reco低pz验收。原fit身份/pz/计数与原缓存精确，故不是本阶段换父、选轨或单位改写造成的差异。它们的fit measurement正权贡献不支持把该fit当成直接主μ轨迹来测主μcovariance覆盖；尚未区分具体非主μ粒种/谱系或给出可部署主μ选择。没有把少数父删除后重新宣称误差覆盖或能量收益。

[逐父结果](stage194_energy_ml/full_parents.tsv)保留全部160父、缺失PRD/无SDO/无正贡献/invalid或foreign正指针计数；[完整标量](stage194_energy_ml/full_prediction_summary.json)保留所有分组。主μfit支持标志回答实际沉积是否存在，不能证明拟合参数无偏、主μ纯度100%或原primary truth就是可部署身份。Stage193的99.55%平方和集中属于同160父的事后机制发现，本阶段验证其实际fit贡献解释，不通过删去两父让RMS变好。

## 独立验证、资源与存储

全160的原leading index/pz0/charge和无权barcode计数精确，2737项fit-cluster无权贡献集合检查；不同标量实现核2737个fit cluster正权分类，原16pilot/full实际fit/links payload逐值相同；原192所有source纯主μIFT N/RMS复现。[独立审计](stage194_energy_ml/independent_validation.json)为身份/结构/分类闭合，未独立实现HepMC resolver或认证SDO效率、真实μ身份/coverage。

full内部94.338768811 CPU秒/145.383912465 wall秒、ROOT请求读取29145249B、峰RSS1847020KiB。每job4请求核/12GB、最多1份；runtime跨源复用，无逐父初始化。未做受控线程/GPU加速测量；本阶段非GPU训练。调度4start/246CPU秒/373聚合wall秒，失败0、0live；GNU不重复加计调度总量，见[资源](stage194_energy_ml/process_resources.json)。

命令：`python3 ml/stage194_freeze.py`，`python3 ml/stage194_ops.py submit/collect --phase pilot/review/full/audit`（逐次），`python3 ml/stage188_finalize.py 194`，`python3 ml/stage194_document.py`。科学ROOT/gzip/统计/审计全部Condor，本地只源码/标量渲染、调度和精确字节归档。统一提交目录 `~/condor/nu_muAnalysis/stage194/`，紧凑cache `ntuples/energy_ml_stage194/` 留89917B<16MiB；源码/日志/标量/spool在 `software/stage194/`，清理7640882B重复，Stage54原12项size/mtime保持，无新ROOT/xAOD。

## 阶段结论与下一步

本阶段结束这组固定MC拟合身份控制，不凭少数父关闭路线A、不估计真实data错轨率，也不扫描新候选以降低条件RMS。Stage188/190/191/192/193/194共同给出同面预测可执行、候选关联混合和固定表示能量阴性三类结论；它们不等价于所有电子观测无信息或低能目标已经解决。

逐路线的具体输入、验收及停止边界见[任务需求表](stage194_energy_ml/goal_requirements.tsv)。该表记录有限目录检查，只对所列路径负责，未读取新时期事件或证明不存在其他输入。

后续B新方向矩/χ代理训练所需输入为实际LOS单位/符号/参考面、原native测量几何和坏strip/DAQ active条件；验收仍需X/availability/内容/条件打乱轴的新训练及原cal/test双低5%和八层三尾，不用detector axis或全active替代缺失条件。D需同设置转换/overlay/testbeam具体manifest、selection、校准误差；E需2025+四像素平面数据/匹配MC/ν共同覆盖；F需原status0真实非单pulse结构及支持的MC。物理谱还需背景、完整效率/生成权重/相关辅助输入与独立确认。目录存在不证明输入已经配对，也不证明不存在；缺失支持必须明确，不能在同一旧输入上无限增加模型/窗口或metadata步骤。所有未测量收益/系统/真实覆盖保持未测量，整体goal不标完成。
