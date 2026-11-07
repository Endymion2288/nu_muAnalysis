# Stage131：下游 μ 谱系、固定边界能流与能量风险

本阶段计算完成；全部固定父、18次能量拟合、独立复算与清理已交付。原物理联合门未通过，整体项目仍未完成。

## 1. 阶段目标

承接 [Stage123](2026-11-06_stage123_native-observables-and-sample-strategy.md)第二条机制线、[Stage130](2026-11-07_stage130_full-depth-support-curve.md)执行合同：在相近重建 μ 动量下，下游活动中 generator-final-state μ 根及其后代的贡献，与其他根的贡献，能否区分低能正尾和低 pz 真高能？固定靶边界首次外穿的非 μ 输运动能有无额外线索？仅用测量 X 学到的谱系代理能否改善能量风险？

Stage124 已完成原生关联摘要对照，Stage130 已检验原规模附近 926→1852 和 4100→8200 incoming 代理曲线；不重开旧 X 架构、seed、数量或几何网格。参照仍为 Stage87 direct62，当前阶段不晋升任何模型。完整物理目标尚未完成。

## 2. 输入、角色与有限取样框

输入为 Stage130 已精确回接的 EVNT 文件/entry 与现成 pinned 官方全链。历史 selected 框中，排除 role0/4、旧 locked-test 和重复 float32 incoming，保留 114945 个 incoming 代理。canonical source 先确定，再按 `person=b'nuMu131'` 的固定 hash 排序。原角色、所有旧 1016 K、46575/11612/13189/17657 原划分均不改。

在任何新能量风险之前，12 父成本/闭合 pilot 后冻结 [4032 父合同](stage131_energy_ml/production_contract.json)：

| 原角色 | 真50–100 GeV | 真100–200 GeV | 低pz真高E | high-y | 连续过渡 | 自然高端 | 合计 |
|---|---:|---:|---:|---:|---:|---:|---:|
| train1 |512|512|256|256|512|256|2304|
| cal2 |192|192|96|96|192|96|864|
| 开发test3 |192|192|96|96|192|96|864|

六层互斥，具体判定顺序在 `stage131_frame.py`；high-y 取样层 y>.75，与原验收 high_y 的 y≥.8 不混称。逐父纳入概率 `n/N_cell`、身份和 seed 存于 ignored `ntuples/energy_ml_stage131/production_cases.json.gz`。训练、校准、风险均用逆纳入概率；train 权重归一到均值1保持正则尺度。响应重放重新通过原 cuts 后才进入能量风险，所有未选中父保留在迁移分母，不按产额换父。

本阶段新增独立 ν 相互作用 N=0。风险目标是历史 selected 框上的 fresh response 且重新 selected 的条件风险，并非自然 ν 全接受度；旧 incoming 代理和精确文件/entry 隔离也不认证完整 GENIE 家族或新 blind。

## 3. 只读 G4 记录器与物理口径

精确源码 commit `d32b0ff3cc4a2dad4abfb1474a82422c3c25b305`，现成 Athena24.0.41/gcc13 runtime。只构建小型新 observer 插件，不重编既有模拟/重建库。源码核查见 [接口证据](stage131_energy_ml/source_interface_audit.json)。普通 HITS 的 particleLink 受持久化 truth 策略限制；本轮在真实 G4 tracking/stepping action 中记录出生时继承的根信息，不把 barcodes 当完整谱系。原 GENIE/FSI 历史仍 flattened，未宣称恢复。

根类别为 generator-final-state μ 及其后代、其他根、unknown；只在唯一 μ 根且关联干净、分母>0时定义 μ 沉积比例，缺失为 NaN。零沉积保留实测0，不能将未定义比例写成0。下游固定 veto/trigger/preshower/SCT/Ecal 五类，上游 VetoNu 不作主标签。

所有时间和 `[0,1000) ns` G4 globaltime 两套沉积均保留；只拟合冻结的后者，前者仅审计。该窗不是已校准 DAQtime，也不是对各平面的脉冲到达对齐。普通 Ecal 使用官方同一步 transient EcalHits 已作 Birks/local-nonuniformity 修正的响应，不能当未经修正的原始沉积做能量守恒。其他类别与实际 persistent HITS 独立闭合。

边界是实际逻辑包络 `Emulsion::EmulsionStationA`，按分支首次外穿计 KE 与 totalE，回穿及已计外穿后出生后代不重复相加。输入源在包络外、未见包络或 unknown 时，flow oracle=NaN，父/X保留。只把非 μ、非 neutrino 的首次外穿 KE 入模；包括中性强子，不能叫“探测器可见能量”，也不是 H。totalE、Eν、由 Eν 构成的能量闭合残差均不入模。stack-killed neutrino 的外穿能流未测量，不能用记录0证明闭合。

## 4. 工程闭合、随机流与已修正问题

首 12 父 pilot 发现原始 G4 edep 与官方 Ecal 校正响应不等；结合 P1a/P3a 1e-5 MeV 压缩量子，改为只读官方真实 transient hit，闭合容差为 `max(1e-6, Nhit*5.1e-6+abs(E_MeV)*2e-7)`。不是按结果任意放宽。第二次 pilot 发现 StoreGate handle 未 retrieve 导致崩溃，修正初始化；停止同一错误的剩余父，失败资源全部计入。见 [响应接口修正](stage131_energy_ml/pilot_interface_correction.json)、[StoreGate修正](stage131_energy_ml/pilot_store_correction.json)。

frame50 固定父/seed 下 observer on/off 重放，所有敏感 HITS 逐项完全相等，见 [非干涉实测](stage131_energy_ml/observer_noninterference.json)。12 父最终全部成功、9 父重新通过选择，平均常规全链130.428333 CPU秒/父；frame50 全链274.511910 wall秒含额外 on/off 模拟和逐 hit 比较。该成本只用于事前冻结规模，不替代正式实测。

G4 SeedOffset 和以输出文件名命名的框架 stream，与波形真实私有 TRandom3 区分。首 pilot 保留原 seed，其余波形用 `650000000+10000*frame_index+1000*detector`（真实工具顺序Calo/VetoNu/Veto/Trigger/Preshower）。框架 offset 内、所有私有波形 seed 内均不重复；跨命名空间有两个数字相等项，不能写成“所有 seed 数字全局唯一”，也不能把数字相等当相同 engine state。依据见 [随机流命名空间审计](stage131_energy_ml/random_namespace_audit.json)。完整初始/末状态首父保存，其余保留 seed/state长度/实际推进记录；不宣称统计独立性的数学证明。

## 5. 冻结模型与统计验收

| 臂 | 维数 | 内容 | 受控信息对照 |
|---|---:|---|---|
| X |62|原 audited62|同支持基准|
| A |69|X+7 oracle availability|A/X 检查可用性贡献|
| U |74|A+5 固定窗总沉积 log1p(GeV)|U/A 检查理想总响应|
| L |79|U+5 同窗 μ 根沉积比例|L/U 检查来源划分增量|
| F |75|U+1 首次外穿非μ KE log1p(GeV)|F/U 检查边界能流|
| P |67|X+5 train监督谱系预测|P/X 检查可部署有限政策|

六臂共享原3 seed、400轮、depth5强树政策，18 次能量 fit，无搜索；cal 每个 ensemble 仅一个逆概率加权全局 log offset。P 只用 train 的 source_index%3 三折监督，train 真正交叉预测、cal/test 用全train拟合；最多20个固定150轮depth3标签模型，稀少/常数标签预定均值 fallback，不借留出标签或 oracle availability。P 是旧 X 的监督变换，不产生新传感信息。

大池 f0 重载三原模型和原 offset 只作 reference，不能将小支持 X 对 f0 的差解释为新信息效应。传统固定 `pz/.8`。一次方动量仍仅 pz0；px/py、q/p、弯折允许，raw11、typed NaN、合法 signed 负数、Calo缺失、pz>50及原 fitted/reduced charge cuts 均保持。

原八层、bias/R68、三向tail50、缺失/状态/高端全部报告；500次 sampling-stratum×component 内 incoming 条件配对 bootstrap，逆概率权重。主机制继续目标要求 cal/test 两低箱均 point≤.95且上95<1；原最终两低箱/传统≤1.05、all/f0≤1.01、其余五层/f0≤1.03、八层三尾差/f0上95≤+2pp不降。1.05只是非劣效。边际95%并非联合95%，区间不含完整source/refit/研究选择/GENIE/真实系统不确定度。功效只作固定配对损失的条件正态ESS近似，宽区间不证明等效或信息界。

## 6. 实测结果

**本固定机制实验发现边界能流的强条件增量；μ 来源比例只有局部小增量，可部署 μ 比例代理未达到双低箱目标。六臂 cal/test 的12项原 joint 全部失败，保留原 Stage87 direct62。**

### 6.1 完整父与选择迁移

4032/4032 固定父全部成功，3002 重新通过原 cuts，train/cal/开发test=1708/653/641。24192 个 detector-parent HITS 闭合全部通过，最大绝对差1.0099300197907723e-5 MeV。记录1775802498个 G4 tracks、10949703638个 steps，unknown_root和missing_birth均0。这里完整关联指实际被追踪的 G4 tracks；不补出已 stack-killed 的粒子。4031父只有1个μ根，1父有3个；后者不进入已选择能量样本。选中边界oracle有效2803/3002，余199仍保留X和事件，以NaN/availability表示。包络外primary累计6733条，是track数，不能当父数。

| 固定取样层 | train选中/模拟 | cal选中/模拟 | test选中/模拟 |
|---|---:|---:|---:|
|E50_100|413/512|161/192|163/192|
|E100_200|437/512|163/192|160/192|
|lowpz_highE|104/256|35/96|31/96|
|high_y|96/256|33/96|40/96|
|transition|449/512|176/192|173/192|
|highE|209/256|85/96|74/96|

原层依据旧响应pz，风险层使用fresh response重建pz，所以取样lowpz层和最终低pz风险层并非同一个分母。test低pz真高E仅21例/ESS20.996713，high_y40例/ESS39.036141，cal相应27/35例；不能把宽尾率区间写成稳定无害。全部分母见 [迁移表](stage131_energy_ml/migration_summary.tsv)和[风险支持](stage131_energy_ml/support.tsv)。

### 6.2 同支持主比较

所有比值为log-RMSE比，方括号为固定模型条件95%区间。

| 对照 | cal50–100 | cal100–200 | test50–100 | test100–200 |
|---|---:|---:|---:|---:|
|A/X|0.999485 [0.982139,1.017790]|0.994781 [0.980030,1.006086]|0.959719 [0.938483,0.979535]|0.992995 [0.975048,1.010689]|
|U/A|0.973448 [0.945759,1.004352]|0.919626 [0.876590,0.963440]|0.987010 [0.964772,1.011864]|1.029604 [0.984496,1.081996]|
|L/U|0.967664 [0.953538,0.982762]|0.985954 [0.962362,1.007710]|0.977156 [0.959777,0.994962]|0.997501 [0.967692,1.023001]|
|F/U|0.703812 [0.636507,0.772896]|0.885643 [0.792215,0.986080]|0.706057 [0.632191,0.786692]|0.880740 [0.766331,0.994613]|
|P/X|0.978272 [0.957304,1.003666]|0.960279 [0.936481,0.985498]|0.986502 [0.965061,1.009293]|1.001139 [0.965998,1.032856]|

F/U 在两角色两低箱均point≤.95且上95<1，达到冻结的机制继续方向目标；test最低/第二箱约下降29.39%/11.93%。L/U最低箱有约2%–3%局部改善，第二箱未复现5%级改善。P/X test两低箱区间均含1，且下端>.95，不支持当前固定政策下5%级代理恢复。这里P预测的是μ沉积比例，**不是边界KE代理；边界代理尚未测量**。不能把P阴性当作已检验了有效边界标签的可部署性。

F/U test all=.949378 [.898489,.999696]；L/U=1.002935 [.996371,1.008448]，P/X=1.002656 [.987313,1.016445]。大池f0只是reference，同支持信息效应必须用上述配对。完整值见 [配对表](stage131_energy_ml/paired.tsv)、[点风险/偏差/R68/三尾](stage131_energy_ml/metrics.tsv)和[图](stage131_energy_ml/energy_comparisons.svg)；PNG已人工视检，坐标、误差棒和图例清楚。

| 角色/模型 | 50–100 log-RMSE | 100–200 log-RMSE | all log-RMSE | 最低箱mean bias(%) |
|---|---:|---:|---:|---:|
|cal/traditional|0.148965570|0.199225450|0.412314426|11.475836|
|cal/direct_cal|0.301928287|0.224467613|0.287170335|27.422814|
|cal/X|0.276779870|0.212998706|0.314553869|25.583557|
|cal/A|0.276637232|0.211887027|0.312308480|25.470168|
|cal/U|0.269291951|0.194856802|0.307684007|25.334722|
|cal/L|0.260584058|0.192119763|0.307717536|24.018846|
|cal/F|0.189531011|0.172573628|0.292996973|14.057776|
|cal/P|0.270766054|0.204538195|0.314322122|25.051407|
|test/traditional|0.158060501|0.199789274|0.422046270|11.827256|
|test/direct_cal|0.229908004|0.218107080|0.258336404|18.756658|
|test/X|0.216933763|0.197706297|0.282174458|18.262431|
|test/A|0.208195510|0.196321407|0.279429119|17.020755|
|test/U|0.205491094|0.202133261|0.280100350|17.336520|
|test/L|0.200796796|0.201628045|0.280922478|16.658852|
|test/F|0.145088410|0.178026910|0.265921229|9.055006|
|test/P|0.214005552|0.197931413|0.282923990|17.945860|

### 6.3 传统与危险侧保护未过

F/传统最低箱cal=1.272314 [1.115817,1.441918]，test=.917930 [.780917,1.075671]；第二箱cal=.866223 [.744687,1.014301]，test上95=1.062756。即使test最低箱点值低于传统，也没有通过1.05非劣效上端，更不能宣称独立胜出。cal/test F的all/f0上95=1.093956/1.088779，原1.01门失败。小支持与大池f0训练量不同，不能从这一差距归因新增oracle有害。

同支持 F/U test低pz真高E RMSE比=.898003 [.737025,1.075984]，总/负尾差点值−9.497163pp，但上95=+7.558934pp；high_y比=.908647 [.834375,.992378]，总尾差−4.100665pp，上95=+7.272239pp。这些点值支持局部方向，不满足尾部稳定要求；不能把宽上端当作已证明伤害，也不能忽略其风险。相对f0，F在test困难低pz负尾上95=+25.341688pp、high_y总尾+24.255817pp。所有模型/八层/三尾见 [原门](stage131_energy_ml/gates.tsv)；12项joint均False，promotion=False。

固定配对5%效应的正态规划ESS：test L/U两低箱54.947544/147.856912，P/X78.553060/152.613903，F/U981.123178/1604.304655；实际163/160。该估算针对小5%目标及当前损失方差，不能解释成发现大幅F效应还必须先有1604条，也不是训练N或系统/来源稳健功效保证，见 [条件功效](stage131_energy_ml/conditional_power.tsv)。

### 6.4 窗口覆盖与物理描述

| test探测器 | all-time比例可用/N | 固定窗比例可用/N | 固定窗事件μ比例加权均值 |
|---|---:|---:|---:|
|veto|641/641|393/641|0.028929352|
|trigger|641/641|158/641|0.150699174|
|preshower|641/641|641/641|0.928238173|
|sct|641/641|641/641|0.820773646|
|ecal|641/641|641/641|0.942025006|

固定窗内veto/trigger分别248/483个test零沉积，而all-time均非零；它们的μ比例与all-time大幅不同。该结果直接限制本轮L/P结论适用的窗口，不能升级成全时间谱系或真实DAQ信息界。本轮按预注册仅拟合一个窗，不临时追加all-time模型挑赢家。真实到达时间/DAQ对齐及校准后的分层响应尚未测量。

在相同粗pz50–100 GeV条件下，test低真E161例与真E≥200的21例，SCT事件μ比例加权均值=.986143/.551064，Ecal=.992835/.574325；有效边界非μKE均值1.073940/88.787688 GeV。支持活动来源与出靶输运组成不同的描述，不是控制全部μ状态/深度后对误差的因果分解。低E f0正尾11例中Ecal10例仍全μ、SCT7例全μ；不能用单个强活动事例的均值归结全部低能误差。全表及各自可用分母见 [机制诊断](stage131_energy_ml/mechanism_diagnostics.tsv)。

### 6.5 数值和数据语义验证

4964个独立record-space标量由math.fsum/显式重采样行复算，与矩阵实现最大差5.3290705182007514e-14；18模型各自重载预测精确相等。62列非法正值域−1、有限sentinel和Inf均0；合法signed −1特征项3256个保留，不把所有负数误删。P只有X和train监督预测，不携oracle availability；原reserved、新role4和隔离均零forward，精确EVNT文件/entry及incoming无角色重叠。

4032份selected NPZ的72576个源数组逐项可由matched_input+selected_extra精确重建，含未选中空数组；原metadata JSON字符串及四种报告值压缩保留，不宣称ZIP容器字节相同。独立验证见 [验证JSON](stage131_energy_ml/independent_validation.json)、[逐比较复算](stage131_energy_ml/independent_validation.tsv)、[字段审计](stage131_energy_ml/feature_domain_audit.tsv)、[压缩证明](stage131_energy_ml/compact_verification.json)。

## 7. 资源、I/O与保留产物

正式每批最多8父、8CPU/24000MB，最多materialize32，scheduler MaxRuntime86400秒，无应用timeout，不截 K；CPU预算1500000秒。科学读取/重建/拟合/统计全部HTCondor，提交目录 `~/condor/nu_muAnalysis/stage131/`。未测GPU加速，不编造加速比。

EOS 负缓存曾造成新结果可列目录但暂不可stat；通过 XRootD 取精确已完成压缩包，不重跑物理。生产逐成员解压核长度并记录索引；只在分析worker scratch展开并逐字节读回，避免在EOS落数万小文件。完整合并数组、原JSON/metadata、GNU时间、失败和运输/调度证据压缩保留后才删重复；只称逻辑删除字节，不冒充物理空间释放。

全部511个精确attempt/511starts已终态，3失败（两次pilot接口错误、一次最终审计断言）；另一次成功audit因运输前缀过滤漏两张汇总表，做一次audit-only补回，全部计成本。唯一scheduler CPU **652569秒**、aggregate execute wall116022秒、allocated execute core-seconds921798、秒级峰32作业/256请求CPU、0GPU。GNU子进程不重复相加。正式4020新响应648997CPU秒、日历跨度4353秒，pilot外推524321.9CPU秒比实际低约23.8%，仍未超1500000预算。见 [逐作业资源](stage131_energy_ml/resource_jobs.tsv)与[总计](stage131_energy_ml/resource_summary.json)。

18能量fit进程CPU合计54.666434292秒；包含20个实际proxy fit和校准/forward的fit阶段wall14.193387秒。后处理修正没有重训。GNU单子进程峰RSS2367896KiB，不是八进程总峰；详细成本见 [执行表](stage131_energy_ml/parent_execution_steps.tsv)。昂贵部分为CPU官方链，GPU加速未测量。observer本地小构建CPU/wall未测量，未混入scheduler数字。

HITS独立checker ROOT实际读16252119537B，只覆盖checker而非全链。成功父累计scratch ROOT输出17258825072B、运回ROOT=0B，不称EOS峰占用。503生产包30439225B、69849成员/274092616解压字节，inventory实测24.277414秒；均为逻辑字节而非物理网络量。源数组/原JSON在worker scratch逐字节回读，见 [运输摘要](stage131_energy_ml/transport_summary.json)。

最终audit发现“所有private RNG必须推进”的断言过强：官方Scint/Calo算法遇整个HITS collection为0提前SUCCESS返回。按源码核`advanced == (Nhit>0)`全部通过；Calo/VetoNu/Veto/Trigger/Preshower分别81/2709/0/17/72父零hit且状态不动。见 [修正](stage131_energy_ml/rng_usage_correction.json)、[真实使用表](stage131_energy_ml/private_rng_usage.tsv)。没有改变响应、模型、offset、bootstrap或风险。两张汇总表运输修正见 [记录](stage131_energy_ml/audit_transport_correction.json)。

终态及72576数组证明后清理6610文件，删除逻辑重复 **405252441B**。缓存13282601B、模型15425767B，合计28708368B，另保留3750314B编译observer。保留matched_input、selected_extra、固定bootstrap/fit矩阵、模型/预测、parent原JSON/metadata、GNU时间和失败/调度/运输压缩证据。重复frame索引、逐父分片及运输/软件包已删，不能重跑旧collect/prepare/fit当新实验。恢复见 [清理记录](stage131_energy_ml/cleanup.json)。home根本项目nu_mu_stage*提交目录=0，AFS本阶段保留descriptor/worker，终态日志核后打包；Stage54五资产保持。

实际命令为`python3 ml/stage131_sourceaudit.py`、`stage131_submit.py frame/pilot/preflight/production`（精确indices/CPU/memory/命令见每个submission JSON）、`python3 ml/stage131_productionplan.py`、`python3 ml/stage131_progress.py`、`python3 ml/stage131_submit.py analysis --cpus 8 --memory 24000`、`python3 ml/stage131_submit.py audit --cpus 4 --memory 12000`、`python3 ml/stage131_resources.py`、`python3 ml/stage131_cleanup.py`。EOS负缓存时以XRootD取精确返回包，collector使用`--archive /tmp/<return>`。analysis前七phase全成功，只补audit，不重复模型/风险。最终AST、bash -n、JSON/本地链接、Git whitespace和历史前缀/后缀检查通过，先中文报告再本地Conventional Commit，不push。


## 8. 阶段结论与下一步

本阶段完成真实G4来源/边界标签、同支持oracle、μ比例部署代理和连续能量风险。原联合门未恢复，f0保留。F强条件增量支持可测性研究；L/P结果只结束本固定窗/五比例/固定树组合，不否定全时间或更细测量，也不因少量尾例或宽区间声称信息极限。

下一可执行Stage132见 [冻结合同](stage131_energy_ml/next_execution_contract.json)：复用matched_input、既有X预测和500 bootstrap，只新增一个log1p(非μ首次出包络KE/GeV)的train-only三折source监督代理，再做B=X+预测量63维与冻结同支持X比较。四个150轮depth3代理fit＋原三seed400轮能量fit，共7fit，无新G4/新相互作用，无truth availability，不重复X。900CPU秒预算、4CPU/12GB，输入已具备，任何B风险前冻结。

这是看到Stage131开发结果后的有限目标随访，不冒称Stage131事前预注册或新blind。要求cal/test两低箱point≤.95且上95<1，完整原八层/三尾报告，promotion始终False；阴性就结束该X-only边界监督实现，不续轮数/depth/seed/组合网格。X确定函数不创造传感信息；监督是真实G4出包络量，不是H/Eν恒等式或旧X后验换名。真实新测量Z、DAQ对齐和neutralhadron可测性没有被代理自动解决。

真正独立确认、真实data曝光/GRL/背景/接受度及相关interaction/FSI/材料/读出/flux nuisance完整物理精度均未交付。整体goal不能标完成。原角色/全部K/pz0/raw11/typedNaN/signed/Calo缺失、正式cuts和1.05/1.01/1.03、八层三尾+2pp不变。计算完成与物理缺口分别记录在 [完成审计](stage131_energy_ml/completion_audit.tsv)。

显示格式核验：18张TSV的空显示格统一为NA，所有非空单元格逐格完全一致；原表及15份完整提交清单压缩保留，最新清单镜像和重复文件目录删除636912B。SVG仅移除行末空白，不改图。见 [显示与清单审计](stage131_energy_ml/display_finalization.json)。
