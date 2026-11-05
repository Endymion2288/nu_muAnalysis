# Stage119：兼容扩样学习曲线与实际响应机制联合实验

日期：2026-11-05。起始 `main` / `befa412`。依据 [Stage118](2026-11-05_stage118_mc-inventory-and-physics-strategy.md) 和路线§100执行；用户本次继续工作的授权覆盖旧入口中“研究轮不运行计算”的限制。事件读取、重建、数字化、拟合、推理和统计均在 HTCondor；终端只做文本、运输、作业管理及文件归档。本阶段没有新 GENIE/G4 生成，没有源码重建 Calypso，没有 push。

## 1. 阶段结论与验收范围

**新增样本已经实际用于固定学习曲线和扩样候选，原逐事件能量目标仍未达到。** 兼容原 merge 读出的新训练池只有最低箱52、第二箱180个 incoming 代理；固定组成曲线最低箱实际为9/18/36，远未把旧940条最低箱训练支持翻倍。小模型随量改善，不能据本次小增量裁决数据饱和。扩样候选相对强 direct 的两低能改善区间均包含1，仍远差于最低箱传统法。

**物理机制不是只做清单。** 已测实际 VetoNu 几何和数字化输入时窗、谱系未知覆盖、GENIE W/FSI组成及固定模型在名义/JEFF/ENDF/Standard/NUX中的能量风险。共同支持内 JEFF/名义最低箱 direct RMSE 比为 **1.488752 [1.027589,2.165737]**；有环境敏感性信号，但不是已认证同末态随机干预或1σ系统。Pythia最低箱只有1/8条，且共同支持中缺该箱，不能估计其可靠环境效应。

完整祖先标签/边界流及其匹配部署读出仍缺，**oracle→代理→能量增量未测量**；本报告交付准确缺口，同时完成另一个可做的物理分支，符合 Stage118 末段的验收例外。不把该缺口写成 oracle 阴性、全探测器信息极限或项目完成。任务逐项见 [requirements.tsv](stage119_energy_ml/requirements.tsv)。

## 2. 输入、库存与兼容生产

输入总合同 [protocol.json](stage119_energy_ml/protocol.json)，目录/日志实测见 [inventory.json](stage119_energy_ml/inventory.json)、[production_evidence.json](stage119_energy_ml/production_evidence.json)、[schema_probe_summary.json](stage119_energy_ml/schema_probe_summary.json)。原始电子样本基址为 `/eos/experiment/fasernu-data0/faser/sim/mc24/genie`，不是只凭PDF猜测的目录。

- 下游扩样池：200131–136、200184–189；名义控制：200082/83/89；JEFF：200110–112；ENDF：200113–115。21个run各均匀冻结3个canonical PHY文件，共63文件；seed `2026110519`，每文件纳入率持久化。没有按产额/误差换源。
- PHY父pilot实际 **620947条**，不同incoming代理 **389985**，旧producer选择9765。此9765不能作为原merge训练数。请求字节 **249517719 B**，worker CPU **65.707955 s**、内部wall **19.095548 s**；GNU全作业 **71.76 CPU s /23.02 wall s**。初始schema请求 **9439062 B**。
- 12个扩样PHY缺 `Track_isForward`，其中200131–136还缺 `truth_barcode`；G4 PHY来自backward配置。直接 REC→旧d32 merge 因waveform v1缺 `trigger_time`/`hit_status`失败，未虚构默认值。实际解决为 **RDO→官方d32 reco→merge noIFT**。
- 六个200131–136目录缺production日志，精确原producer仍未知。200184–189已有日志记录22.0.49 / `cd9679e2`、forward/noIFT及03-LG；旧名义日志 `6d6ab70b`/01-LG，G4日志 `54a9026b`/03-LG且旧PHY backward。统一重建解决可交付表示，不等于消除原HITS/数字化/材料全部差异。
- **200188是K c2，不能标成charm。** 其首个sim日志却指向与200187相同的K c1 EVNT，须继续核实际分块/重复；没有按run名认证独立性。

兼容QA：三run各40父事件原生选择与独立mask一致，typed62通过；稀疏RDO重建三个来源各6个entry `[0,3,9,15,23,39]`，**全部528列逐项完全一致，包括NaN**，见 [sparsecheck.json](stage119_energy_ml/sparsecheck.json)。

63个正式作业 `9668380.0–62` 全部exit0：保留全部父分母，按原truth νμ/pz/r/z的保守超集重建 **58064 entry**，不按reco或模型选择输入。最终兼容选中 **11894条**，扩样池其中 **4393条**。实际每run COOL 01/03-LG payload已读取；原生 `E/q=330/charge_ref` 通过检查，例为 **4359.313 MeV/pC**。Calo仅按实际payload比一次转换到原01-LG表示，没有拟合truth/residual缩放。见 [兼容来源支持](stage119_energy_ml/compatible_source_support.tsv)、[合同摘要](stage119_energy_ml/production_contract_summary.json)。

## 3. 旧曝光、角色和变量政策

旧输入为 Stage55+56、70/81/82/83及原Stage87 split；重建 **89033行**，原 **17657隔离**及active train/cal/test **46575/11612/13189**不动。原Stage82的 **1016个K**全部保留。旧曝光排除包含全部Stage55 dataset/pilot、各支持缓存和Stage87隔离/开发输入，实测 **74563个唯一incoming**；它不是所有历史未持久化父事件的完整认证。

新增所有响应视图按精确native-MeV incoming分到同角色，预定BLAKE2b、person `nuMu119`，70/15/15 train/development/reserved；不把不同run或同父重放计成新独立N。新增三角色互不交叉，且与已列旧曝光无交集；完整GENIE父/种子链仍未认证，**预留不称新blind**。

| 新扩样角色 | 全部记录/代理 | 真50–100记录/代理 | 真100–200记录/代理 | 低pz真≥200记录 | high-y记录 | 上游记录 |
|---|---:|---:|---:|---:|---:|---:|
| train |1428/1414|52/52|180/180|57|89|0|
| development |287/283|15/14|39/38|11|18|0|
| reserved，仅支持计数 |286/283|6/6|37/37|8|9|0|

旧曝光扩样响应另有2392条，不纳入新训练池。上游支持为零，不用truth z部署切换或极端权重伪造。统计表中ESS是行权重ESS，独立支持另列incoming数，不能把前者当完整生成家族数。

模型仅用原62维 `F7_pz0_raw_v1`：一次方动量只保留 **pz0**，保留允许的px/py、q/p、弯折；不含p0/p1/pz1或ln(p0/p1)。11路闪烁体输入为 **raw_charge**，不以坏fit电荷回填。原typed NaN、signed reduced负值、Calo缺模块传播和状态政策保持；拟合电荷的**选择cut未改**，原reco/truth pz>50 GeV。新11894行共22个typed NaN、残留`-999`为0；合法signed负数不统一删除。见 [support_audit.json](stage119_energy_ml/support_audit.json)。

## 4. 固定组成N/2N/4N及扩样候选

[curve_protocol.json](stage119_energy_ml/curve_protocol.json)在兼容产额确定后、任何新模型结果前冻结。年份×成分×真E×y×深度的canonical incoming家族单元内，预定随机顺序严格1:2:4嵌套；粗单元内剩余连续分布差异、稀疏单元不支持及来源效应仍存在。没有拟三点幂律或外推无限样本极限。

| 曲线点 | incoming代理 | 记录 | 真50–100 | 真100–200 | 低pz真≥200 | high-y |
|---|---:|---:|---:|---:|---:|---:|
|N|330|332|9|40|9|15|
|2N|660|665|18|80|24|31|
|4N|1320|1333|36|160|51|61|

另有一个事前指定部署候选：原完整train46575＋全部新增train1428（共38970个incoming代理），**不称数量唯一改变的曲线点**。同N旧来源对照在共同下游、成分/E/y/深度canonical单元抽1320唯一incoming，年份/flux仍不同，不称随机source因果效应。首版误按response cell计数导致1316唯一代理，审计后按canonical家族修正并仅重算该对照；原三点/扩样候选完全不动，旧结果留归档，不择优采用。见 [修正锁摘要](stage119_energy_ml/same_N_correction_lock_summary.json)、[same_N_control_fixed.tsv](stage119_energy_ml/same_N_control_fixed.tsv)。

所有fit同原强政策：3固定seed `2026110255/56/57`，400轮、depth5、eta.04、min_child20、λ10、hist、每fit1线程、incoming等权和训练均值logE初始化；各模型都只在原完整cal拟一个offset，新dev不调offset。正式曲线/候选/初版control15次seed fit，加纠错control3次，无架构/超参数网格。原3模型在原active上逐项精确复现Stage87 raw/cal缓存后，才推理新增非预留数据。所有模型及传统法在新reserved上 **0预测、0风险、0拟合**；隔离同样不前向。

下表为原已开发test、incoming加权自然log能量RMSE（无量纲）。能区单位GeV。

| 方法 | 真50–100 | 真100–200 | 全体 | 低pz真≥200 | high-y |
|---|---:|---:|---:|---:|---:|
|传统pz0/0.8|.145661|.247937|.557190|1.887790|1.618799|
|原direct_cal|.282644|.246329|.287491|.658177|.609395|
|新池N_cal|.428385|.280964|.371218|.837543|.783966|
|新池2N_cal|.339850|.262517|.357587|.842033|.787149|
|新池4N_cal|.291845|.277192|.346762|.843948|.794718|
|原train＋新增train|.280688|.244959|.287404|.659989|.611568|

扩样候选/原direct的两低能比：**.993077 [.970467,1.015871]**、**.994439 [.985865,1.002957]**；all **.999695 [.997849,1.001403]**。新增dev的对应两箱比 **1.001580 [.958076,1.016718]**、**.981738 [.965544,1.001234]**。均无支持的共同两低能改善。

4N/N最低箱：旧test **.681269 [.629642,.730800]**、新增dev **.723444 [.559690,.838133]**；全体也下降，证明这段小模型学习曲线仍有有限样本效应，**不证明在原大train上扩足量就能赢传统**。第二箱曲线不单调。纠错后的4N/旧同N对照：旧test最低箱 **.824452 [.776980,.873445]**、第二箱 **1.084060 [1.044183,1.129012]**；新增dev两箱均含1。保留不同来源的取舍，不把单一最低箱点称source全面优越。

原最终标准未放松：test候选两低能/传统上95 **2.308522/1.066553**，均超过1.05；all/direct上95 **1.001403**通过1.01，其余五层RMSE保护通过，但最低箱总尾上95 **+2.007389 pp**、低pz真高能负尾 **+2.465092 pp**、high-y负尾 **+2.581655 pp**、unconfirmed负尾 **+2.110815 pp**失败。cal/test/newdev联合均False，保留原强direct。完整raw/cal、八层/缺失/高端/上游、三向尾和500次共同incoming条件区间见 [metrics](stage119_energy_ml/curve_metrics.tsv)、[paired](stage119_energy_ml/curve_paired.tsv)、[gates](stage119_energy_ml/curve_gates.tsv)及 [曲线图](stage119_energy_ml/learning_curve.png)。旧test不称blind；区间不含重训、研究选择、完整source/parent或真实系统不确定度。

## 5. 固定模型的输运/强子化环境风险

Pythia 200300–305仅有HITS/乳胶NTUP，不能把乳胶NTUP当电子读出。预先均匀冻每run3个HITS文件、全部 **18000父事件**；实际真值保守重建超集 **2437**。小样本40×2先跑通全digitization→reco→merge；随后发现稀疏digitization与完整读取的波形/噪声不逐项相同，**拒绝该优化**。正式 `9668439.0–17`改为全部父事件数字化，再稀疏RDO重建，18作业全部exit0，不剪掉父分母/失败事件。波形工具的TRandom3(0)及随机流语义不能当作同seed响应认证。

固定原direct/传统、零能量重训，最终名义/JEFF/ENDF/Standard/NUX选中 **2572/2379/2550/250/277**。保留HERMES 200306–308不作能量推理/开发；此前仅schema和固定时窗沉积诊断，不能称环境完全未看过。全父分母按文件纳入率记录，[parent_support](stage119_energy_ml/response_parent_support.tsv)不只报告共同selected交集。

以成分、E=[100,200,400,1000]、y=[.2,.5,.8]、z=[−2200,−1950]固定粗单元取共同overlap分布，含各环境采样率和incoming权重。G4共同97单元，overlap mass **.849656**；Pythia49单元、**.763719**，不能用加权制造未支持单元。已保存有/无匹配全结果和实际bias/三尾。进一步使用同一incoming的共同bootstrap，保留跨环境同proxy相关性；weights/overlap目标条件固定，未估计全部匹配/producer/真实系统误差。

| 共同支持内direct RMSE环境比 | 最低箱 | 第二箱 | 全体 |
|---|---|---|---|
|JEFF/名义|1.488752 [1.027589,2.165737]|1.043516 [.838128,1.292264]|1.073977 [.995723,1.155179]|
|ENDF/名义|1.246634 [.917876,1.774368]|1.116180 [.919001,1.335097]|1.024399 [.953951,1.105574]|
|NUX/Standard|**无共同支持，不可估**|1.605734 [.564249,3.906382]|1.126626 [.905747,1.378275]|

Pythia最低箱原selected只有Standard1、NUX8；困难侧部分bootstrap有效draw431/463，低于475/500标准，相关95%明确缺失，不把大点比值当效应。全年份、材料/符号/靶核和producer并未完全匹配，故这是条件环境比较，**不是把差全归因于中子库或强子化**，也不当1σ。见 [环境对比](stage119_energy_ml/response_environment_contrasts.tsv)、[支持](stage119_energy_ml/response_common_support.tsv)、[固定模型指标](stage119_energy_ml/response_metrics.tsv)。

另对记录的同incoming/z/r/主μ能量状态作条件匹配：名义/JEFF **7574父状态**，both selected276、名义only49、JEFFonly61、neither7188；JEFF/ENDF **11190**，417/97/95/10581；名义/ENDF无共同状态。首个1000 HITS的JEFF/ENDF还核到相同incoming、完整vertex和y及文档同EVNT/skip0。但**完整GENIE末态记录及source-entry/seed链未全认证**，表中明标conditional matched states，不冒称已认证同父随机干预。见 [迁移](stage119_energy_ml/response_parent_migration.tsv)、[条件匹配风险](stage119_energy_ml/response_matched_transport.tsv)。

## 6. 从发生器到敏感沉积、实际读出窗口

### 6.1 W/FSI已关联到当前选中失败，不把低E等同低W

实际定位六个Pythia父EVNT相邻的 `faser_filtered.gfaser.root`；不依赖无法反序列化的GHEP `TClonesArray`。按eventID提出候选generator entry后，必须核实际入射、vertex和主μy。首版严格double比较失败，native p6头文件确认momentum/mass和vertex为float：按**真实持久化Float_t转换**精确核入射和vertex，再重建主μy。没有按能量损失放松身份容差。最终 **10331/18000父事件**满足唯一primary关联；选中 **527/527全部关联，523可算W**。

W²=(status11 struck nucleon+ν−primary μ)²，Q²=−(ν−μ)²，GENIE GeV四矢量；独立status12系统闭合Standard195/NUX204例，最大abs W²差 **9.308e−13/3.766e−13 GeV²**。status14/1仅作FSI前/后组成，不认证通用interaction channel或逐粒子FSI对应。材料/ν符号另表 [material](stage119_energy_ml/genie_selected_material.tsv)，没有唯一status0核的target0保留free/unknown语义，不填钨。

未选generator子作业中，Standard最低箱717条、712 W已知，W<2.3/2.3–3/≥3为 **50/39/623**，W中位 **6.440593 GeV**；NUX **61/41/623**、中位 **6.444125 GeV**。这些是原生成子作业组成，不是旧test失败的构成。

当前选中Standard/NUX W已知 **249/274**，其中W≥3为 **235/259**。两环境“direct相对误差>50%而传统≤50%”分别 **5/8条**，全部W≥3；NUX最低箱此类仅1条，W **3.500572 GeV**、FSI前/后中子 **1/30**，单例只作描述。能支持“这批失败不全来自低W区”，不能支持W/中子数造成失败、旧模型全失败原因已找到，或把真W/中子作为部署输入。见 [关联审计](stage119_energy_ml/genie_link.json)、[失败组成](stage119_energy_ml/genie_failure_W_FSI.tsv)、[覆盖](stage119_energy_ml/genie_selected_link_coverage.tsv)。

### 6.2 原HITS祖先缺失使非μoracle不能点值识别

五来源各1000 HITS父事件原生读取，保持零、已知μ、已知非μ、unknown。200184 VetoNu总 **26.218699 MeV**，51非零/949零；已知非μ **.344610 MeV**、μ0、unknown **25.874089 MeV**。JEFF总 **2313.102008 MeV**，328非零/672零；已知非μ **238.226944 MeV**、μ **15.662763 MeV**、unknown **2059.212300 MeV**，仅3个非零事件完整已知。不得把缺父链算成已知非μ或中子；事件非μ比例只报告 `[known_nonmu/E,(known_nonmu+unknown)/E]`。见 [coverage](stage119_energy_ml/hits_coverage.tsv)。

JEFF/ENDF首1000条件匹配父事件的VetoNu均值 **2.313102/2.293775 MeV**，ENDF−JEFF **−.019327 [−.422958,.433304] MeV**；fiducial178父事件 **4.618557/4.036666 MeV**，差 **−.581891 [−2.020507,.989159] MeV**。这是敏感沉积，不是电荷或能量风险系统。下游Veto/Trigger/Preshower同样保存 [transport](stage119_energy_ml/hits_transport.tsv)。

### 6.3 实际几何下的时窗覆盖确实已测

native几何 `FASERNU-04` / `OFLCOND-FASER-06`，VetoNu两plate中心z **−3122.5/−3101.5 mm**。官方工具使用 `hit.meanTime−center.z/c`，VetoNu无位置传播项；600×2ns、10 presamples的沉积直方图范围 **[−20,1200) ns**，正时响应卷积还会进一步限制可用ADC。固定7个首文件各1000父事件，不从风险选延迟阈值。

| 来源，1000父事件 | 总VetoNu沉积MeV | 窗口内MeV | ≥1200ns MeV | 窗外比例及条件95% |
|---|---:|---:|---:|---|
|200110 JEFF|2313.102008|1873.122457|439.979550|.190212 [.142800,.257667]|
|200113 ENDF|2293.775288|1882.835445|410.939842|.179154 [.140665,.247595]|
|200184下游π|26.218699|26.218699|0|0，当前样本|
|200300 Standard|1429.878134|1429.313894|.564240|.000395 [.000046,.000881]|
|200303 NUX|1786.190138|1772.685847|13.504292|.007560 [0,.023993]|

所有early能量本样本为0。JEFF/ENDF中分别53/46父事件只有late沉积而无窗口内沉积；总沉积与独立HITS reader逐事件一致。fiducial子样本和其余诊断环境见 [window_coverage.tsv](stage119_energy_ml/window_coverage.tsv)。不同来源绝对差仍混合深度/producer/物理模型，不以此推断单一机制。**直方图窗口外沉积不是已测真实迟到电荷，也不能因其存在就宣称扩大窗口会改善Eν**；大部分谱系未知，无法认证其中中子份额。准确oracle/代理输入缺口和有条件新生成proposal见 [observability_input_gap.json](stage119_energy_ml/observability_input_gap.json)。

## 7. 确认量、下一阶段决策

原最终门槛不改；1.05只是非劣效。新reserved最低箱只有6 incoming，候选又失败，完整家族未认证，**不开确认**。开发配对平方log误差方差及1pp尾率精度规划见 [confirmation_plan.tsv](stage119_energy_ml/confirmation_plan.tsv)。例如最低箱候选/direct的正态5%改善条件量级7 incoming，但候选/传统为472363；仅14个开发incoming的方差极不稳定，两者均不是已认证的联合门槛确认设计或“必需N”。本次原始经验表中零discordance产生的N=0不可作为样本量结论，已明确被纠正方案替代：零经验方差标不可估，并用discordance的95%上界给保守规划量级（最低箱/direct 1pp半宽7401）。不靠bootstrap制造低能支持。

下一阶段定义为**有限的低能支持认证与响应归因**，不是继续同缓存调树：

1. 在已定位的大池和原EVNT/日志中认证200131–136的producer、200187/188重复/分块及旧全部父曝光；所需输入是生成子作业/entry/seed链。验收为可核独立低能家族和明确交集，不只是更多PHY行数。未认证的缺口继续显式保留。
2. 保持均匀或已知纳入概率，在现成RDO共同支持内增加独立低能/困难侧父家族；先按实际产额和成本冻结规模，使最低箱支持产生可辨别增量。当前大池远未穷尽，不能因本次52条增量无效就优先全量新G4。上游仍缺时再冻结已知proposal混合的新GENIE父pilot，生成/G4 CPU/event仍**未测量**，须小pilot后再扩。
3. 对JEFF最低箱的环境信号核完整GENIE末态、材料/符号/深度及原数字化条件，用真正同父名义/输运小对照购买归因能力；验收包含所有父通过/失败、实际raw/status/时序和固定模型两侧风险，不把环境差自动命名中子库因果效应。
4. 只有完整祖先与匹配实际读出交付后，再预定一个非退化oracle→同容量无特权对照→源留出代理→连续能量/三尾实验。保留zero/unknown/弱信号/饱和及漏能语义；无输入不以真H/E补答案。HERMES继续保留能量迁移用途。

这些是后续具体任务，未在本阶段自动启动新生成或再训练。真实data、接受度/背景、完整response/interaction/FSI/材料系统和独立确认仍未交付；原逐事件目标没有完成。

## 8. 实际资源、程序失败与验证

全体科学作业在 `~/condor/nu_muAnalysis/stage119/`，没有在home新建散落提交目录。父读取/统计申请8核，训练最多5并发×各1线程；重建63个单CPU任务、Pythia18个任务并发，站点可因内存提高分配。无GPU fit；当前全部18次单seed树拟合只需几十CPU秒，主要成本在native事件生产，未测GPU相对加速，不能声称GPU更快。

| 实测项目 | CPU秒 | wall秒 | 备注 |
|---|---:|---:|---|
|63个兼容生产step合计|25348.70|28072.82，逐作业之和|reco19952.94、ntuple4670.98、extract724.78 CPU秒；峰1290584KiB|
|再含Pythia全部生产step|44226.36|47787.80，逐作业之和|数字化18步16849.34 CPU秒；全生产峰2105796KiB|
|首批5策略ensemble训练及参考推理|65.80|35.82|GNU父/子总量；不能再加子fit计时|
|同N纠错control|11.92|14.21|仅改错误control成员；3 seed|
|固定环境推理/汇总|10.77|13.01|0新fit|
|环境共同bootstrap及失败W汇总|10.34|12.66|0新forward/fit|
|最终GENIE关联|15.35|18.55|请求317796701B，超过事前300MB预算，明确记超支|

这里的生产合计不再与包含它们的Condor整作业CPU重复相加。所有本阶段作业（含纠错）的原生userlog资源账本见 [condor_resources.json](stage119_energy_ml/condor_resources.json) / [condor_userlogs.json](stage119_energy_ml/condor_userlogs.json)，包括失败与移除，不是只报成功成本。实际共126条作业记录，125完成（111 exit0、14非零）、1移除、0运行；整作业累计CPU **50842 s**、wall之和 **59270 s**。完整会话网络/ROOT读取字节、并发整树峰及新GENIE/G4 CPU/event **未测量**；EOS文件大小、Uproot请求和物理网络不是同一量。

失败均保留实际日志/退出和成本，不把它们当物理阴性：REC旧v1转换缺字段；9668353打包语法失败后误提立即移除；稀疏QA漏建目录；共享worker被覆盖导致9668367 exit127（改immutable逐phase worker）；window/window2/window3的PyAthena字典、空几何/Cling缺HepMC头（window4显式几何、整数plate访问后通过）；9668428/29错误macro仍指probe（改`-append phase=...`）；稀疏digitization的实际非等价；supportaudit误把1016K归到83（应82）；GENIE关联先漏目录、后过严double比较及I/O预算超支；同N control非唯一家族；末次检查引用compact cache未保存eventID，改回接native parent。没有隐藏重试或选择有利物理结果，旧失败工件保留紧凑证据。

原3模型raw/cal逐行缓存精确；最终252个原标量控制max差 **7.105427e−15**、48组配对区间的独立行空间max差 **1.421085e−14**，以及56项环境loss行空间/cluster核对max差 **4.365575e−11**，详见 [final_validation.json](stage119_energy_ml/final_validation.json)。选择、528列稀疏重建、payload、原角色/K/raw/NaN和预留0前向分别有独立QA。额外通用单元测试/重新编译不适用于本次未改C++的批量分析；科学验证使用实际代表ROOT输入和完整结果。

## 9. 产物、复现及存储

代码为 `ml/stage119_*.py`、运输/压缩工具及三类Stage119 Condor脚本；保留紧凑输入/模型/预测于 `ntuples/energy_ml_stage119/`、`ml/artifacts/stage119/`，表格/合同摘要/资源在 `workbook/stage119_energy_ml/`。未提交事件数据、ROOT、模型或运输包；原Stage54未跟踪资产和交接后缀不改。

事件级父身份/祖先沉积JSON和完整请求名单集中到 **`ntuples/energy_ml_stage119/persisted_evidence.tar.gz`**，每成员与原字节核对后才删除展开副本；[persisted_evidence.json](stage119_energy_ml/persisted_evidence.json)记录成员和恢复命令。各阶段运输包在原始源字节与返回工件核验后去重；模型和必要紧凑结果保留，不保留新xAOD/HITS/RDO中间副本。资源/清理实际字节见 [storage_cleanup.json](stage119_energy_ml/storage_cleanup.json)：所列范围清理前 **1344191227 B**，清理后、账本本身写入前 **101841772 B**，净减少 **1242349455 B**；其中必要缓存82667333 B、模型16634534 B。保留一个未通过collect的稀疏QA失败输入包，其余已验证运输包去重；未做SHA扫描。为通过Git空白检查，仅将TSV换行规范为LF并显式引用末列空字段，CSV解析后的全部字段逐项相同；45份表格/日志的格式化原字节另存已核归档，见 [格式记录](stage119_energy_ml/formatting_normalization.json)。

主要命令（在仓库根目录，批量提交而非交互执行分析）：

```bash
# 如已压缩，先恢复事件级合同/证据；不重读EOS全部源
tar -xzf ntuples/energy_ml_stage119/persisted_evidence.tar.gz -C .
python3 ml/package_stage119.py package <phase>
condor_submit -append 'phase = <phase>' AnalysisZipFramework/submission/ml_stage119.sub
python3 ml/package_stage119.py collect <phase>
# EOS挂载metadata迟延时，用xrdcp到临时文件并给collect --result，核后删临时副本
condor_submit AnalysisZipFramework/submission/ml_stage119_production.sub
python3 ml/package_stage119_pythia.py
condor_submit AnalysisZipFramework/submission/ml_stage119_pythia.sub
python3 ml/compact_stage119.py --remove-expanded
git diff --check
```

执行顺序与实际cluster/失败见资源账本、每phase package/transport及时间文件；批量archive接口固定原源码/配置/输入。[完成审计](stage119_energy_ml/completion_audit.json)记录52份Python AST、3个worker的shell语法、JSON和全部43个新增本地链接检查；路线/预算HEAD原文字节前缀与交接HEAD原文字节后缀均保持，Stage54无改动。先写本中文报告、完成记录和历史前缀检查，再本地 Conventional Commit，不push。
