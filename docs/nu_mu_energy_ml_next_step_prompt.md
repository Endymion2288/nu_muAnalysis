# 当前执行更新：Stage166 已取得真实GRL/整run亮度，局部文件曝光未认证

[Stage166报告](../workbook/2026-11-08_stage166_real-GRL-and-shard-exposure.md)实际取得六份官方v10源，run15838记录亮度850.979pb⁻¹、稳定区间53587秒；同原PHYS780874条全通过时间GRL、四项数据质量后774232条，原1024prefix精确。该文件时间包络只有3004秒，不能直接附整run亮度，也不按时间/事件比例缩放；[输入清单](../workbook/stage166_energy_ml/exposure_input_manifest.json)仍标文件曝光未认证。实际C++3004秒/6边界、独立1024身份/DQ及六源原字节通过；4start含一次CSV列名解析失败全计11CPU秒/43聚合wall秒、0live/fit/forward/G4/新ν。最终源/1024输入66794B，删6292436B重复；源码3857逻辑版本按精确内容存975份，再减4264543B，Stage54保持。

[下一Stage167合同](../workbook/stage166_energy_ml/next_execution_contract.json)仅同run15838已知PHYS和RAW目录各一次非递归listing，≤64PHYS/4096RAW；原前3header/首尾/有限metadata和reference64先验收/成本，再4进程全目录PHYS header及独立审计。1500CPU秒/4核12GB、无RAW payload/ν选择/模型/G4；文件名区间与端点不能单独认证完整处理/DAQ曝光，不无界追目录。真实背景/全生成接受度/相关校准/乳胶/独立确认仍缺，Stage87和所有原门保持，整体未完成。

以下保留此前入口原文。

# 当前执行更新：Stage165 完成固定H来源诊断，名义通量支持为空

[Stage165报告](../workbook/2026-11-08_stage165_fixed-H-source-composition.md)完成同原3002、578source及216预定比较单元，零fit/forward/G4。π的条件H两低箱cal .715567/.832242、开发test .808396[.700383,.912952]/.762770[.656478,.880233]；K test28/35父，.798155[.564649,1.122367]/.863245[.644905,1.140405]，未共同确认，不等于K无收益或π/K差异显著。charm低箱只有0/1父，退化经验区间不认证总体；原全部3002来自alternative，nominal0，跨通量效果未测量。原inclusive432项差≤2.49e−14、独立2016项差≤2.14e−14、48缺失区间保留；2start全exit0、26CPU秒/37聚合wall秒、0live、0新事件/模型持久化，删6.255MB重复，Stage54保持。

Stage164条件H尾部未过、4原joint失败及Stage87/所有原门保持；不能据π局部收益扩大同类G4/代理/模型。下一步见[实际输入与验收清单](../workbook/stage165_energy_ml/research_status.json)和报告：名义H同口径支持、真实run/channel联合校准及宽μ辐射尾控制、新电子可测量、乳胶匹配、曝光GRL/背景/全生成接受度/真实相关辅助约束及独立确认仍需实际取得。未定义自动Stage166生产合同，不造prior或重跑已完成有限MC toys；具体新物理实验须先给实际测量/输入/成本/验收。整体低能优越性和完整物理精度目标未完成。

以下保留此前入口原文。

# 当前执行更新：Stage164 的H增量在给定真深度后仍存在，但尾部未认证

[Stage164报告](../workbook/2026-11-08_stage164_depth-and-unaccepted-energy.md)完成原3002缓存的AZ/AZH两臂6fit；1708/653/641角色、全部K1156、199NaN和原500draw保持。H给定真z的cal两低箱.718646/.823290、开发test.807279[.701427,.904019]/.770997[.672326,.862127]，四项5%门True；z给定H四低箱约1、均未支持5%改善。不能把H效果全归于深度，也不能将有限政策条件不对称叫因果或H可测。条件H test低pz正tail上差+2.123522pp未过+2门，continuation=False；最低箱AZH/传统cal1.182494、test1.000832且上95均>1.05，4原joint均False。3504独立标量/模型重载通过，最大差4.97e−14；5提交/3start全exit0/2未启动撤销、52CPU秒/61聚合wall秒/0live/GPU/G4/新ν，最终5.578MB、删41.784MB重复，Stage54保持。

[下一Stage165合同](../workbook/stage164_energy_ml/next_execution_contract.json)只作零fit来源依赖诊断：原3002、固定AZH/AZ、AZH/H、H/A，预定π/K/charm及manifest nominal/alternative边际划分、原HT/500draw/N/ESS/三尾；先核source/component，600CPU秒/4核12GB、不改模型/父/门、不自动扩大G4，空组和宽区间保持未知。实际data校准/宽μ辐射尾、乳胶、曝光GRL/背景接受度/真实相关系统/独立确认仍缺；Stage87和原全部门、整体未完成保持。

以下保留此前入口原文。

# 当前执行更新：Stage163 普通Calo raw幅度未建立低能增量

[Stage163报告](../workbook/2026-11-08_stage163_ordinary-calo-raw-energy.md)完成原71376active/全部K/三固定臂九fit；可读原PHYS70332，原Stage82临时merge不留存，误映射的两个旧bck候选被精确门拒绝后改为新增字段未知，1044父原X/角色保留。281308有效raw视图、113320合法负数、31raw有效而原fitted缺失；最低cal/test箱均无后者。content/M12 cal两低箱.990793/.998796，开发test1.006770[.998989,1.014749]/1.003566[.998652,1.009052]；最低test/传统1.951627[1.653734,2.308464]，正tail13.661202%对0%。原joint及Stage137双5%门False，原其他RMSE/尾保护通过不等于低能恢复，固定Q4结束。X62精确复现Stage87；285504独立标量域检查、9模型及3718风险标量通过，最大差2.84e−14。22提交/17start含3执行失败和5未启动撤销，全计438CPU秒/526聚合wall秒、0live/GPU/G4/新ν；26.38MB事件/新增数组/模型，删678.71MB重复，Stage54保持。

[Stage164冻结合同](../workbook/stage163_energy_ml/next_execution_contract.json)只用既有3002缓存，以新的Stage137未接受H/A双箱5%支持，补AZ/AZH两臂6fit问真深度已知后H是否仍有条件增量。Stage134原总K未触发分支保持，非G/raw4/旧X网格；同199NaN/HT权重/原角色/K，复用A/H及500draw，900CPU秒/4核12GB、无ROOT/G4/新父。仅机制oracle，不等于可见能量或因果解释；真实data校准/GRL曝光/背景接受度/乳胶/相关系统/独立确认仍缺，Stage87/全部原门和整体未完成保持。

以下保留此前入口原文。

# 当前执行更新：Stage156 真实μ空间控制闭合，非leading本身不能标为其他根

[Stage156报告](../workbook/2026-11-08_stage156_muon-native-spatial-control.md)完成原HITS前4→64：64根/current06状态/covariance/PRD/raw/RNG配对精确，61leading、3无leading保留，1063leading anchors全通过相同float32区间几何。站1–3分别39/34/25候选，43/64父非空；pz0[50,100)GeV组41/57非空，overflow只有3父/1非空。μ根加辐射/噪声控制本身有数十mm活动，不能把nonleading或大dx直接叫hadronic或FPR；逐cluster成因未测。前4跨作业精确，五作业含一次旧metadata字段审计失败全计361CPU秒/574聚合wall秒，0live/G4/能量fit；2155857B事件文本回读精确、删22261548B重复。下一[Stage157合同](../workbook/stage156_energy_ml/next_execution_contract.json)转真正联合响应/留出控制：同一已核4096μ根前缀，先128sequential/64suffix分块复现与成本，再准入64chunks/16job×4进程，60000CPU预算、初始最多4job并发；Q15与Q15+真实空间G6两个固定低维评分，不扫描，不forward自然ν。实际联合native data仍缺manifest，不假造data空间，不将有限留出误报当总体/data认证。全原ν能量比较另冻，原门/Stage137双5%扩大门/Stage87和整体未完成保持。

以下保留此前入口原文。

# 当前执行更新：Stage155 实际持久化认证通过，取得真实非leading空间量

[Stage155报告](../workbook/2026-11-08_stage155_persistence-aware-cluster-spatial-observables.md)完成原role1前4→40：实际REC两输入均tlp6、文件内streamer为TrackParameters_p2/vector<float>；697真实anchors的身份/同面/float32及邻数中点plane-box全通过。148非leading候选分布在22/40父，站1–3为63/29/56；另872在未测wafer，站0未知，不当物理零。独立dx闭合≤1.421086e−14mm、表示宽度≤7.704158e−6mm，距离变化不只是量化幅度；未认证writer模式、covariance、关联概率、FPR或能量收益。独立前4精确，4job全exit0、155CPU秒/222聚合wall秒/0GPU/G4/fit，13230B事件文本精确合并、删14508839B重复。下一[Stage156合同](../workbook/stage155_energy_ml/next_execution_contract.json)为已知MC100012原HITS前4→最多64的同定义μ空间控制，复用官方digi/reco/RNG，先配对current06实际状态/raw/schema及成本；3000CPU秒，无新G4/独立ν/能量fit，合法零活动不阻止准入。总体μ/data响应和留出FPR、全原ν风险需后续独立合同；Stage87/全部原门/Stage137双5%扩大门及整体未完成保持。

以下保留此前入口原文。

# 当前执行更新：Stage154 几何往返闭合，离面精度门阻止候选，未扩大

[Stage154报告](../workbook/2026-11-08_stage154_global-to-wafer-geometry-pilot.md)完成同原前4role1父：身份/旧计数精确，70真实PRD及measurement-detector变换全同，70二维COT明确记录。state往返≤1.464822e−14mm、PRD往返0，但54/70超冻结1e−6mm离面容差，16支持wafer上无非leading候选；站1/3各1未评分候选保留未知，不作物理零。小QA的GLOBAL坐标/离面区间与float32舍入相容，已查p2转换源码；旧REC实际persistent schema/全70原因尚未认证，未事后调容差。原成本模型2216.79CPU秒+100>剩1083且物理门False，未full40/fit。2job全exit0、119CPU秒/200聚合wall秒/0GPU/G4/新ν，2936B事件精确合并、删7225660B重复。下一Stage155先核真实persistent格式，显式float32区间几何pilot，首执行初始化与steady成本事前分开；不修covariance、不任意加半径、不自动fullpool/energyfit。Stage87/原门/Stage137扩大门/整体未完成保持。

以下保留此前入口原文。

# 当前执行更新：Stage153 原生同面支持审计完成，保存的 local state 不能直接与 cluster 相减

[Stage153报告](../workbook/2026-11-08_stage153_native-cluster-surface-basis-pilot.md)完成原REC request0前40role1：原身份/pz0及cluster4/SP/longTracks全匹配，第一父精确重复。697真实PRD链接/identifier/Measurement均通过、完整covariance有限且loc1方差正，但一维locX及measurement/state同面均0；参数为curvilinear，不能因同为PlaneSurface就直接相减。站1–3同wafer非leading候选63/29/56真实存在，因anchor不支持而score全缺失；不是空间活动物理零，也没有r2/roundtrip数值认证或能量fit。2job全exit0、116CPU秒/156聚合wall秒/0GPU/G4/新ν；事件10812B精确合并、删7245092B重复。旧Stage124直接locX残差不再作物理pull证据，Stage87保持。下一Stage154另冻真实GLOBAL位置→wafer的几何闭合/未归一化dx pilot，前4→最多同40、1200CPU秒、无covariance修补/fullpool/fit；原全部门和Stage137扩大门/整体未完成保持。

以下保留此前入口原文。

# 当前执行更新：Stage152 实际Ecal控制闭合，本例有限窗损失很小

[Stage152报告](../workbook/2026-11-08_stage152_Ecal-HITS-window-diagnosis.md)完成已知μ原entry0：157 SD修正hit/48.329432MeV，2400ADC零差、同current04 raw/status/privateRNG精确；Calo2 finite/full=.999957391063、histogram外hit0，弱raw不能由本例大量漏窗解释。实际模拟信号.064892711495pC，baseline/噪声与取整后raw.04904296875pC；其他三路无hit但有ADC噪声，不填缺失或当沉积。3倍四父预测935.71CPU秒+100预留>剩878，未扩四例/预算；2start全部exit0、122CPU秒/152wall秒/0GPU/G4/fit，保留一父方法结果而非总体校准。事件文本13560B精确合并、删4402897B重复。下一Stage153只读原已知REC最多40train父，测真实同面cluster局部位置/拟合误差/PRD归属及固定scaled-separation摘要；无新G4/能量fit，不重开旧gain/time/seed追查，先物理基底/新内容/成本。原门/Stage137扩大门/Stage87及整体未完成保持。

以下保留此前入口原文。

# 当前执行更新：Stage151 实际conditions配对完成，共同raw／轨迹未随tag改变

[Stage151报告](../workbook/2026-11-08_stage151_actual-conditions-paired-muon-control.md)完成原μ前4→64：真实04/06分别解析生效，实际map16/18路、共同16物理通道；1010合法raw对差全0pC、1024视图status/presence精确，4项baselineRMS差≤1.192093e−7mV单列。61同面reference/PRD/state/fullcovariance精确、3无leading保留；4pilot前缀及64初始/全部末RNG精确。切换tag没有恢复旧PHYS的Calo响应，旧map／随机流／release未认证，不把差当tracking bias或1σ。5start全部exit0、431CPU秒/577聚合wall秒/0GPU/0G4/0fit；事件文本2.162MB精确合并、删19.959MB重复。下一Stage152同一原μentry0→最多0–3的Ecal HITS→analog→ADC实际有限窗诊断，1000CPU秒/400pilot/100audit reserve，不重复SCT整链、不扫gain/time/seed。原门／Stage137扩大门／Stage87及整体未完成保持。

以下保留此前入口原文。

# 当前执行更新：Stage150 Ecal overflow 有限支持审计完成，无父准入

[Stage150报告](../workbook/2026-11-08_stage150_Ecal-overflow-support-audit.md)仅原4032父/2304role1，1708有status参考、596原未选中父仍未知；6832Calo视图status1/0/32为6512/318/2，overflow位0，候选0。按冻结合同不换父/扩库存/人工裁切，不执行G4；这不是总体无饱和结论，真实Ecal clipping方法仍未测量。1job exit0、5CPU秒/10wall秒/0GPU/0fit，删除23887349B运输。下一Stage151同一原μ前4→最多64做conditions04对已有06固定物理对照，明确input/current元数据和18vs15映射；1000CPU秒、实测准入，无G4/新ν/模型网格。原全部门/Stage137扩大门/Stage87及整体未完成保持。

以下保留此前入口原文。

# 当前执行更新：Stage149 真实 μ covariance／PRD／raw 配对控制完成

[Stage149报告](../workbook/2026-11-08_stage149_native-covariance-and-raw-control.md)已完成原MC100012 HITS前4→64的当前官方数字化／重建控制。64父全部保留，61选中leading及full5×5 covariance/同新ntuple身份精确；18实际映射通道包含原raw15，64/64逐字段闭合。61 covariance正定且每条20非零offdiagonal，最大相关系数中位.941346；局部σ(logpz0)中位.023718、最大.394096，未校准pull/覆盖率。1097测量链接缺失0、2174clusters的5个共享归属不当关联概率。16无hit视图保留，245signed负raw保留，非0status无timing；旧输运conditions04/当前06差异明确。前4native/raw/RNG精确复现；含JSON/AFS失败6starts、497CPU秒/699聚合wall秒/0GPU；64不同原entry而非72独立，0新G4/ν/fit。事件压缩2245381B、无持久ROOT。下一Stage150仅既有train父Ecal overflow支持审计，非空才最多1同父clipping控制/1000CPU秒；原全部门/Stage137扩大门/Stage87和整体未完成状态保持。

以下保留此前入口原文。

# 当前执行更新：Stage148 自然混合 Ecal 来源／DAQ 方法控制完成

[Stage148报告](../workbook/2026-11-07_stage148_mixed-Ecal-DAQ-source-control.md)在2304个train父中审计266个混合Ecal支持，事前固定原frame7（π、848.11GeV、原selected0保留）。实际1672μ/71其他根hits、2400可读ADC零差；通道0/1/2同780–930ns窗混合来源加和通过，最大积分差6.23498e−10pC。全部Calo status1，弱信号及signed负raw保留；固定raw窗含各来源完整采集信号≥99.9953%，不能归因于大量漏窗。无Ecal触底，旧参考及完整private状态缺失不冒充精确。4job全exit0、272CPU秒/477聚合wall秒/0GPU、1同父G4/0新独立ν/0fit。下一Stage149原PG HITS前4→最多64条真实state covariance/PRD/raw控制，先物理pilot和成本、3000CPU秒，无新G4/模型网格或自然ν大生产。原全部门/Stage137扩大门/Stage87和整体未完成状态保持。

以下保留此前入口原文。

# 当前执行更新：Stage147 μ根尾部的记录轨迹匹配诊断完成

[Stage147报告](../workbook/2026-11-07_stage147_recorded-muon-track-tail-control.md)同MC100012前4096条，原身份/3612选中/评分分组计数精确。3612全部记录为μ匹配；878可评分留出均直接匹配已核初始μ根，记录hit ratio中位1且低于0.8数0。overflow10/16、11/16和高活动6/6报警不由记录的非μ轨迹误选解释。高活动pz0相对生产truth pz中位差−.141474，非同面不能称重建误差或已测能损。1job全exit0、4CPU秒/11wall秒/0GPU；不重训/改阈值，不认证真实PRD/covariance或data/ν迁移。下一Stage148最多一个既有train混合Ecal父、1000CPU秒，闭合实际来源/DAQ，不大生产。原全部门/Stage137扩大门/Stage87和整体未完成状态保持。

以下保留此前入口原文。

# 当前执行更新：Stage146 μ根身份与固定评分尾部完成

[Stage146报告](../workbook/2026-11-07_stage146_muon-root-identity-and-response-tails.md)核已知MC100012单HITS前4096条，172248个保留truth粒子全部连到μ根，缺父/重复/环均0；4096 PHYS逐run/event及根动量/顶点float32精确匹配。3612 selected中3512含非μtruth列表但仍为μ根，不可当独立其他根污染。原评分40项计数精确，μ根overflow报警10/16、11/16，高活动6/6；全体低比例不认证条件尾部。3job全exit0，145CPU秒/207聚合wall秒/0GPU，无新G4/fit。下一Stage147仅在同PHYS核记录的选中轨迹truth匹配/质量和pz偏差，60CPU秒、固定缓存评分，不冒充真实PRD/covariance或新观测。原全部门/Stage137扩大门/Stage87和整体未完成状态保持。

以下保留此前入口原文。

# 当前执行更新：Stage145 μ联合留出控制完成，下一查真实初始根与尾部

[Stage145报告](../workbook/2026-11-07_stage145_muon-joint-response-heldout-control.md)固定data8006/MC100012各4096条，选中2998/3612控制。Q15/Qshape30全体留出报警data18/768、33/768，MC26/878、25/878；MCoverflow为10/16、11/16，高活动6/6均报警，不能凭全体低比例认证辐射尾。只用point状态，covariance/生产匹配/data纯度未认证；truth列表全μ仅100例不等于其余有非μ初始根。χ²负占位值路径已修，实际受影响0/0，模型与留出表精确保持。2job全exit0、9CPU秒/22聚合wall秒/0GPU，无νfit/forward。下一Stage146沿已知PG HITS核实际根/身份/固定评分尾部，300CPU秒、无新G4，不扫模型或库存。原全部门/Stage137扩大门/Stage87和整体goal未完成状态保持。

以下保留此前入口原文。

# 当前执行更新：Stage144 Ecal DAQ闭合完成，转入μ联合尾部控制

[Stage144报告](../workbook/2026-11-07_stage144_Ecal-DAQ-source-control.md)复用四父缓存，无新G4，9600可读ADC零差；Ecal实际780–930ns窗，须保留8几何PMT的噪声抽样后再比较4可读PMT。原Calo status三父/原完整private状态首父精确；frame2原selected参考缺失保持，原Calo raw未保留不冒充比较。三次程序失败全计，共587CPU秒/538聚合wall秒/0GPU，低于600预算，四父无Ecal触底/混合来源，不认证总体尾部或低能收益。下一Stage145固定两来源μ联合raw/shape留出控制，真实point/covariance/祖先及data纯度边界明确。原门/Stage137扩大门/Stage87和整体goal未完成状态保持。

以下保留此前入口原文。

# 当前执行更新：Stage143含信号VetoNu来源控制完成，Ecal与μ联合控制继续

[Stage143报告](../workbook/2026-11-07_stage143_VetoNu-signal-source-control.md)在2304个train父中审计736个正VetoNu支持，按原frame顺序固定1/5两父。16800ADC零差、84触底、原raw11/status精确；VetoNu分别为全非μ和混合来源，最大来源模拟积分差4.619815e−5pC。4job全部exit0、415CPU秒/552聚合wall秒/0GPU，无新ν/能量fit。两父均为charm中高能，仅认证通道方法，不冒充低能或总体辐射尾。紧凑证据已合并回读，删44.11MB重复运输。Stage144缓存Ecal控制及Stage145有限μ联合留出检验继续；Stage137扩大门/原全部门/Stage87和整体goal未完成状态保持。

以下保留此前入口原文。

# 当前执行更新：Stage142四父来源/DAQ控制完成，下一补VetoNu含信号覆盖

[Stage142实测](../workbook/2026-11-07_stage142_live-ancestry-and-DAQ-source-control.md)在4个既有train父（含2个K）验证真实hit根谱系、持久化顺序与有限窗模拟来源：28800ADC零差，覆盖159触底采样；最大来源模拟积分加和差.001361557pC。三个selected父原raw11/status精确，高-y K父原selected参考缺失而保留。完全μ根的Veto也可大电荷/触底，不以平均MIP或大电荷直接判强子。4job全部exit0、668CPU秒/526聚合wall秒/0GPU。四父VetoNu均无HITS，Ecal只认证官方修正hit标签；μ辐射总体控制和真实系统/独立确认未完成。下一按最多2父/1000CPU秒合同补有信号VetoNu控制，先查train支持；原Stage1375%扩大门不绕过、不自动大生产，整体goal未完成。

以下保留此前入口原文。

先读Stage142报告和next_execution_contract.json。Stage137的4032父/18fit、Stage140的3000toy、Stage138/141总响应与Stage142四父来源控制已完成，不重复。下一Stage143仅补已知缺口：在Condor审计既有4032证据中的train正VetoNu支持，冻结最多两父，首父测成本与实际DAQ来源闭合后再准入第二父；预算1000CPU秒、无应用短超时、K不删、原选择失败保留并显式参考缺失。若无支持，记录实际0、不泛扫旧库存。此为通道覆盖方法控制，不绕过Stage137双箱5%门或启动大自然ν生产，不训练旧X代理。μ辐射总体、真实系统/背景接受度/乳胶及独立确认仍需实际输入，不能标整体goal完成。

## 此前入口（原文保留）

# 当前执行更新：Stage137/140/141计算与验证完成，转入可追溯响应约束

本轮完成[边界机制](../workbook/2026-11-07_stage137_geometry-accepted-energy-mechanism.md)、[3000toy有限MC覆盖](../workbook/2026-11-07_stage140_finite-MC-profile-coverage.md)及[模拟响应到ADC控制](../workbook/2026-11-07_stage141_analog-to-ADC-control.md)。G及D有局部能量增量、未过双箱5%扩大门，H的oracle增量更强；不自动扩大同类G4/模型网格。direct62条件谱区间仍比传统窄；联合nominal覆盖93.4% [90.8761%,95.2621%]，不能认证95%覆盖。7200ADC闭合只认证一个控制父，未完成一般来源/μ辐射尾、真实系统/背景/接受度/乳胶和独立确认。原全部门与Stage87direct62保持，整体goal未完成。

以下保留此前入口原文。

先读上述三份实测报告与Stage132执行清单。Stage137的4032父/18fit和Stage140的3000toy已完成，不重复提交；Stage138/141的单例ADC控制亦不重跑。G/A、D/AK有局部增量但未过冻结双箱5%门，禁止自动扩大同类G4/代理/网络；H/A强oracle增量不是可测或理论不可见证明。若继续一般多根/Ecal来源及μ辐射控制，只做新问题明确、输入可核、成本pilot后冻结的有限方法控制，不自动启动自然ν大生产。真实匹配、data曝光GRL、背景、全生成接受度与相关系统辅助输入仍需认证；不可编prior/开放reserved或标整体goal完成。

## 此前执行入口（原文保留）

# 当前执行入口：Stage138控制完成，Stage137正式批与Stage139稀疏优化继续

**2026-11-07 Stage138更新：** [实际DAQ控制](../workbook/2026-11-07_stage138_DAQ-control-and-time-convention.md)已闭合：同一父两个独立进程7200ADC逐值重复，原raw11/status含2路无ADC默认精确复现，9路有限窗积分独立复算差0pC。Veto18.407908094MeV全为负globaltime而校正hit约±0.033ns，固定global窗不能代表本例DAQ。547schedulerCPU秒/745aggregatewall秒/0GPU；μ辐射尾与一般analog归属未认证。Stage137正式4032父/18fit进行中；Stage139稀疏profile的EM边界优化需修复，部分toy覆盖不得当结论。整体goal未完成，原门/角色/保留集全部保持。

先读Stage138报告、Stage137已冻结protocol/freeze_note与Stage139覆盖合同。Stage137生产已启动，复用12pilot，不重复submit/旧G4/digi/reco，待全部旧字段/HITS闭合后执行冻结18fit及独立验证；查精确cluster和有界history。Stage139覆盖初轮存在EM simplex边界驻留，正在有限数值repair，先验证可复活边界的约束梯度优化再按原toy全部认证，不删除失败toy、不按coverage择bin或prior。Stage138已完整闭合，不重跑控制；后续analog来源与μ辐射需另冻pilot/预算，完整物理和独立确认仍缺。所有角色/K/pz0/raw11/typedNaN/signed/Calo缺失/原cuts及原门保持。

## 此前执行入口（原文保留）

# 当前执行入口：Stage135仪器化pilot完成，冻结Stage137正式分解；DAQ控制并行

**2026-11-07 Stage135 主线更新：** [最小能流仪器化pilot](../workbook/2026-11-07_stage135_boundary-instrumentation-pilot.md)12/12自然train父通过，72探测器-父HITS闭合、旧字段精确复现、首例on/off敏感HITS完全相同。11父有非μKE，5父有Ecal几何射线接受；低两层4父局部仅侧向，不以小样本关闭分支。1045schedulerCPU秒/650aggregatewall秒，0GPU。下一Stage137按实测成本冻结同支持几何接受/未接受/总K条件与粒子类消融；DAQ对齐和μ辐射控制继续独立推进。Stage136并行有限MC条件收益已测，完整物理目标未完成。

先读[Stage135报告](../workbook/2026-11-07_stage135_boundary-instrumentation-pilot.md)与Stage132§5.3–5.5。新observer可用，但正式风险尚未执行；以既有4032自然父/3002selected同支持、原seed与basename精确回放G4，复用12pilot，必要HITS核对、避免重复digi/reco和X/A/AK训练。在新cal/test风险前冻结G=几何接受K、H=未接受K、D=总K+G，以及预定粒子类别必要性消融和成本/功效边界。不得称ray接受为可见能量，不以12pilot作自然比例/最终尾部认证。DAQ实际hit/硬件通道/响应核/采样/有限窗闭合和μ辐射控制独立推进，不把[0,1000)globaltime当DAQ。原角色/K/pz0/raw11/status/typedNaN/signed/Calo缺失/原cuts/验收保持。整体goal未完成。

## Stage135之前入口（原文保留）

# 当前执行入口：Stage134完成，Stage135最小可测能流与DAQ pilot

**2026-11-07 Stage134 更新：** [不含理想沉积的边界机制](../workbook/2026-11-07_stage134_boundary-without-ideal-deposits.md)已完成3fit。AK/A cal/test最低箱0.687973/0.704447，表明最低箱K增量不依赖五项理想沉积；test第二箱0.905402 [0.777200,1.036741]未过固定双箱继续门，不自动追加z×K。下一Stage135转主研究小pilot：最小边界分解与DAQ对应，先闭合/测成本再定正式量。不是新部署；整体goal和原全部门保持。

先读Stage132 §5.3–5.5及[执行清单](../workbook/stage132_energy_ml/execution_tracking.tsv)。不重跑Stage133/134或旧全链。Stage135先只用固定小自然train父检验新增observer分类/首次计数/几何接受/相对时间、非干涉及DAQ响应闭合，实测成本后才冻结正式量；保留靶外/未重选和缺失分母，不挑oracle最优父。不改原cuts/角色/K/pz0/raw11/status/typedNaN/signed/Calo缺失或原门，非0不给timing。整体goal继续。

## Stage134之前入口（原文保留）

# 当前执行入口：Stage133完成，按Stage132继续A+K机制与可测能流

先读[Stage133实测](../workbook/2026-11-07_stage133_boundary-supervised-proxy.md)及[Stage132路线](../workbook/2026-11-07_stage132_boundary-observability-research.md)。原7fit已执行，B/X未达双低箱标准，不重跑或续代理网格；Stage87direct62仍参照。下一Stage134同缓存固定A+K/A三fit，隔离理想沉积依赖；按其结果决定同支持z×K。随后按小pilot冻结最小边界类别/面/接受/相对时间与DAQ响应对应，不无条件重跑4032父。整体goal保持，μ辐射控制/真实系统/有限MC/背景接受度及独立确认未完成。所有角色、全部K、pz0/raw11/status/typedNaN/signed/Calo缺失、正式cuts与原门不变。

## Stage132历史入口（原文保留）

# 当前研究入口：Stage132复盘完成，下一计算Stage133有限边界监督随访

先读[Stage132研究报告](../workbook/2026-11-07_stage132_boundary-observability-research.md)、路线§111与[Stage131原合同](../workbook/stage131_energy_ml/next_execution_contract.json)。本轮无环境，只读既有报告/紧凑表/静态源码并检索论文，没有读取事件数组、计算新风险、训练、推理、重放或提交作业。Stage129–131均已完成，不依下方历史重跑。Stage131合同里的未执行Stage132代理顺延Stage133；旧JSON和所有历史入口原文保留。

**当前判断：主问题是有用边界能流的可测性。** F/U cal/test双低箱都有明显增量，但U有理想沉积/真值可用性，K含全部方向与中性，不等于可见H或X端已获益；P_mu未测K代理。Stage129饱和/严格时序/实际IFT未修复低能，Stage130原规模翻倍已测，不能再把它们列为尚待首次执行的主线。强f0仍Stage87direct62，未有新晋升。

下一有环境计算Stage133先保持原有限合同：Stage131 matched_input、固定X预测和bootstrap；train-only source三折log1p(非μ首次外穿KE/GeV)监督，B=X+预测量63维。4代理+3原能量fit=7，900CPU秒预算、4CPU12GB，无新G4/ν、无truth availability、不重训X。cal仅原全局offset。cal/test两低箱point≤.95且upper95<1，完整八层/三尾/原门，promotionFalse。这是开发结果引出的随访，不是新blind；阴性结束此X-only实现，禁止续模型/seed网格。该阴性不终结真正新观测研究。

后续按报告分支，勿在Stage133里自动追加网格或全链：必要时同缓存补A+K/A区分理想沉积依赖；按明确问题做同支持z×K机制对照。主研究需新最小observer，把前向可响应能流与侧/后向、neutral分开，并建立G4hit→DAQ通道/采样/有限积分窗对应。当前cache有all-time和[0,1000)沉积，却无退出面/粒子类别/方向/时间明细；不能凭聚合量补出。固定窗Veto/Trigger覆盖问题限制谱系外推，具体原因未分辨；不扫描窗口对ν能量选优。

候选新观测是包含μ辐射尾的校准联合响应、真实track/PRD空间归属与必要波形内容；不是再加Stage124已测计数、Stage108点关系或减平均MIP。若只是X的函数，只能称表示改进。任何连续timing仍双端原status==0且存在finite及校准有效，非0内部拟合平移不提供timing；原事件保留。实测raw是780–980ns含端点、samples390:491，不能沿用整600点假设。

条件谱收益Stage129已量化；下一物理读数应加入有限MC、真实相关nuisance、接受度/背景，输入缺口明确标未测，不先重做已知response Fisher。独立确认另锁真实新家族，原reserved/新role4/隔离不开。最终单事例两低箱真正胜传统、1.05/1.01/1.03、八层三尾+2pp和完整物理收益不改，1.05只非劣效；所有新收益/功效/全链成本未测。

未来批量HTCondor用~/condor/nu_muAnalysis/stage133/，先中文workbook再本地Conventional Commit、不push。Stage131已压缩清理，用merged/selected_extra/parent_evidence，不重跑旧collect/prepare/G4。新仪器化先小pilot闭合/实测成本后定规模，避免无条件再跑4032父。pz0/raw11/typedNaN/signed/Calo缺失/原cuts/全部K与角色、Stage54资产和以下历史入口保持。整体目标仍未完成。

## Stage132历史计划入口（原文保留；该计算尚未执行，现顺延Stage133）

# 当前执行入口：Stage131机制线完成，执行Stage132有限边界监督代理

先读[Stage131报告](../workbook/2026-11-07_stage131_muon-lineage-and-boundary-energy.md)、路线§110和[合同](../workbook/stage131_energy_ml/next_execution_contract.json)。4032响应/18能量fit/20μ代理fit/4964复算/72576数组证明/511attempt清理均已完成。逐父/运输/原frame已删，使用merged+extra+parent_evidence；不要再collect或重跑Stage131 prepare/fit/G4。

F/U cal/test两低箱均过5%机制方向，P_mu/X未恢复，P_mu未测边界KE代理。12原joint全False，保留Stage87direct62；固定G4窗不是DAQtime，oracle不是部署或信息界，新独立νN=0。

Stage132输入全在Stage131 cache：matched_input、固定energy_predictions和bootstrap_draws。只新增train-only source三折log1p(nonmu首次出包络KE)代理及B=X+预测量63维；4代理+3原seed能量fit=7，900CPU秒、4CPU12GB、无新G4，不重复X，cal仅一offset。不得带truth availability/cal-test标签训练，X函数不创造传感信息。完整原8层/三尾/5%主目标交付，promotionFalse；是开发结果引出的有限随访，不是新blind。失败结束该X-only实现，不追加网格。

原角色/全部K/pz0/raw11/typedNaN/signed/Calo缺失/正式cuts和reserved零forward保持；原1.05/1.01/1.03、八层三尾+2pp不降，1.05仅非劣效。独立确认和真实data/GRL/背景/接受度/相关nuisance完整精度仍需输入，整体goal未完成，但不阻塞现有缓存实验。HTCondor用~/condor/nu_muAnalysis/stage132/，每阶段先中文workbook再本地Conventional Commit，不push。Stage54五资产及以下历史入口原文保留。

## Stage131历史入口（原文保留）

# 当前执行入口：Stage130完成，继续Stage131谱系与边界能流机制实验

先读[Stage130报告](../workbook/2026-11-07_stage130_full-depth-support-curve.md)、路线§109及[下一执行合同](../workbook/stage130_energy_ml/next_execution_contract.json)。666来源含358 K全部完成，222515 selected逐例EVNT联结；原规模926→1852、4100→8200数量对照及9fit/独立复算已完成，禁止按下方历史入口重跑。

最低箱仍未恢复：augmented/传统old/new test1.910765/1.799716，所有12项joint失败；全体小增益不是低能验收。保留Stage87 direct62，不追加同旧X网络/seed/数量网格，不把条件阴性当理论信息界。原角色、pz0/raw11/typedNaN/signed/Calo缺失/原cuts/全部K保持，原reserved、新role4及隔离均零预测。

下一步推进Stage123第二机制线，先核已固定d32实际HITS/truth-link/G4接口能否标记下游μ谱系、非μ谱系活动和固定边界能流；使用Stage130精确EVNT路径/entry及`ntuples/energy_ml_stage130/pilot_complete_parents.tar.gz`中16份逐字节认证完整末态，可tarfile直接读取，不再生产旧metadata。Stage129 full-chain/privateRNG工程已完成，只补新仪器化必须的工程闭合。先冻结有限自然父框与纳入概率、小pilot测成本和选择迁移，再同工作包冻匹配支持X/X+oracle/可部署proxy的能量风险。分割模拟是人工响应干预，不能当自然ν训练或假设ADC可相加，不把H/Eν恒等式塞入oracle。历史GENIE FSI谱系仍flattened，不冒充恢复；也不将该缺口升级为所有可测研究的全局阻塞。

真正独立确认、真实data曝光/GRL/背景/接受度及相关系统的完整物理精度尚未测量。原1.05/1.01/1.03与八层三尾+2pp不降，1.05仅非劣效；最终两低箱真正胜传统和独立确认仍必要。整体goal保持未完成。

批量继续HTCondor，目录~/condor/nu_muAnalysis/stage131/；先测成本再冻规模，适当多核、GPU收益须实测。每阶段先中文workbook，再本地Conventional Commit，不push。Stage130已回读去重，原数组分片和运输已删，不能重新调用旧collect当新实验；使用合并缓存和紧凑证据。Stage54五资产及以下全部历史入口原文保留。

## Stage129历史入口（原文保留）

# 当前执行入口：Stage129完成，继续Stage130完整深度独立扩样

先读[Stage129报告](../workbook/2026-11-07_stage129_saturation-timing-material-energy.md)、路线§108和[执行合同](../workbook/stage129_energy_ml/next_execution_contract.json)。三类观测、压力、条件谱、独立复算、21例全链和固定EVNT census已完成，不按下方旧Stage128入口重复执行。

Q/T/G均未通过原joint，保留Stage87 direct62；真z增量不作为可部署成果。严格status0、pz0一次方动量/raw11/typed NaN/signed/Calo缺失/原cuts/全部K及角色保持。原reserved不开。371attempt已终态，CPU60633s；完整原始资源/失败和清理记录见报告。

继续有界查原nominal run200082的log/s0014与log/master_dev中少量精确retained生成/模拟日志，定位完整深度EVNT/GHEP/entry/seed。已知五下游EVNT固定327680记录只有272个最低箱重建前候选，不足原940增量；不能据此判全项目无输入。取得支持后先原cuts全链成本与产额pilot，再冻结N₀附近→约2N₀的受控曲线和新确认，覆盖两低箱与同低pz高E/high-y及自然控制。完整GENIE家族、真实data/背景/接受度和外部响应系统仍需实测。联合前向模型继续门未满足，不做旧表示seed/网络/几何网格。

批量HTCondor用~/condor/nu_muAnalysis/stage130/。每阶段中文workbook+本地Conventional Commit、不push；Stage54五资产及以下全部旧入口保留。整体目标仍未完成。

## Stage128历史入口（原文保留）

# 当前研究入口：Stage128复盘完成，下一工作包优先下游Veto饱和恢复

先读[Stage128完整研究报告](../workbook/2026-11-07_stage128_vertex-timing-saturation-research.md)、路线§107及已完成的[Stage125](../workbook/2026-11-06_stage125_frozen-direct62-geant4-performance.md)/[Stage127](../workbook/2026-11-06_stage127_cuboid-cut-optimization.md)。下面Stage124及更早入口逐字保留为历史，不能再按旧标题重做已完成阶段。本轮用户要求无环境研究：0事件数组/ROOT/NPZ读取、0重算/训练/推理/重建/作业，无SHA；以下是未来有环境时的Stage129建议，当前不执行。

科学参照仍为Stage87 direct62，三seed/400轮/固定offset。Stage125证实五G4整体优势保留，但五组最低能均劣于传统、高端负偏约−41%至−45%；不等于完整系统或等效性认证。Stage127横向truth工作点240×230 mm与材料union交集，pz100产额+2.3170%、test log-RMSE+0.1189%，z固定，没有重建顶点入模。保持强基线和已有选择成果，不默认继续旧输入架构/seed/几何网格。

下一有环境科学工作包在看新风险前冻输入、有限pilot、训练/校准/留出和预算，完成可行部分的能量及尾部对照：

1. **主实验：下游Veto10/20/21受约束饱和恢复。** Stage56三路overflow为38363/37102/35762（每路81313），官方CB曾有不稳定外推；VetoNu0/1当时无overflow。先回接真实ADC/status/官方fit及rail/增益/窗口条件，测两侧风险与边沿支持。用真实未饱和波形人工截断、来源留出比较raw/官方CB/带删失约束与模板不确定度的恢复；人工ADC截断不认证PMT模拟非线性。有限窗Q及区间/触顶样本比例/残差/可用标记加入原raw，保留实测部分，不整条平滑替换。之后同支持、同学习政策交X62/可用标记控制/X62+恢复族的连续能量和三尾；波形改善不能替代Eν收益。缺ADC时报告确切持久化层/支持，不能凭raw标量补出真实波形。
2. **独立的便宜时序对照。** 明确上游VetoNu pair、下游层和同片PMT映射；严格两端status==0、存在且finite。任何非0均无可用到达时间/Δt，不用历史容许1/16/512的Good辅助量、不重标512；电荷/事件保留，Δt=NaN+pair-valid。用真实μ控制与run/channel条件校正时基、offset/光传播/timewalk/路径，测联合覆盖，再交X、X+valid、X+valid+校正Δt全事件消融，不扫pair/窗口。缺绝对clock不自动否定相对时间，但status0也不自动证明共同基准。非0饱和电荷拟合内部平移只作nuisance，不输出timing。same-prompt两下游TOF不直接测z或高能μ能量。
3. **深度投入先有当前依据。** direct62的z0是首measurement位置；旧真z改善来自不同CaloNu支持，Stage51局部会聚未回推靶。先在当前audited62/普通几何完整支持检验真z/剩余λI、X0增量，再决定真实多track/IFT协方差及靶区兼容度。单μ与LOS交点无唯一顶点，短段名义100GeV不是强子动量。无早期轨迹者保留，不以z回归精度或GNN大小替代全队列能量收益。
4. **独立双侧支持与系统继续。** 原最低箱940行/926 incoming代理，Stage119仅新增52，不以9→36小曲线宣布训练饱和；争取有纳入权重的N₀→约2N₀，并覆盖同低pz高E/high-y、过渡与自然高端。完整父/末态/entry/seed家族同role，新确认另锁，响应重复不计新νN，原reserved不开。G4级联、GENIE/FSI、flux及gain/clip/template/time响应分别检验；旧producer未知不成为已有窗内波形的无限前置。已有Stage125结果不重做；新G4仅按明确机制或新支持所需，先全链成本pilot再定规模。

Stage122只用VN0/1、Pres0的绝对粗窗，未对齐脉冲/表征精细前后沿，未覆盖下游Veto饱和；其同HITS数字化方差也只变化VN/Pres。不能把小队列阴性或小随机方差称为全波形/全探测器信息上界，也不继续泛化降噪研究。各支线共享提取但可独立推进；不能连续只交metadata，不能以小子队列相对大池f0的差归因新增信息。全部新增可用率/能量收益/功效/CPU/I/O/RSS未测，先测实际pilot再冻正式规模，不按旧scalar或digitization速率外推。

批量科学工作HTCondor目录~/condor/nu_muAnalysis/stage129/；按来源批读、受控多线程，只保存必要波形/紧凑摘要，避免xAOD/重复输出，GPU加速须实测。一次方动量仍只pz0、允许px/py/q/p/弯折，raw11/status/typed NaN/合法signed/Calo缺失、原fitted/reduced cuts/pz>50、全部K及角色不变。原两低箱/传统上95≤1.05、all/direct≤1.01、其余五层≤1.03、八层三向tail差上95≤+2pp保持；1.05只非劣效，最终两低箱真正胜出及真实系统/背景/接受度/独立确认和能谱收益仍必需。先中文workbook再本地Conventional Commit、不push；历史Stage54资产与以下所有旧后缀保留。

## Stage124历史入口（原文保留）

# 当前执行入口：Stage124原规模关联能量实验完成，下一步买可追溯独立支持

先读[Stage124完整实测](../workbook/2026-11-06_stage124_native-association-energy.md)、路线§106、信息预算§86、[完成/缺口审计](../workbook/stage124_energy_ml/completion_audit.tsv)及[扩样账](../workbook/stage124_energy_ml/sample_strategy.json)。以下Stage123及更早入口完整保留为历史，不再照旧重跑。

本轮已完成280 REC/RDO、原89033行真实strip/cluster/SP/PRD关联，全PHYS计数闭合；1cal leading-pz接口未知保留NaN、10688个越域strip ID保留未知，不删父/放宽匹配。原train/cal/开发test/隔离46575/11612/13189/17657、全部1016 K和reserved零预测保持。固定X62/XZ119各3seed400轮，X/f0预测差精确0。

主结论：test两低箱log-RMSE XZ=.282478340/.244916238，传统=.145661386/.247936985；XZ/X=.999412677 [.979539244,1.024001700]、.994265678 [.981327591,1.007733216]，cal只第二箱改善，低能未共同复现。test all比.992806720 [.990084548,.995835898]有小增量；cal/test八层三尾/非低箱RMSE保护过，低箱/传统失败，joint均False，保留f0。1936独立标量差≤2.842171e−14。当前57维摘要＋固定树组合结束，不续GNN/邻域/seed/树/特征网格，不称原生观测全无效或理论信息界。

下一计算Stage125应优先实际可追溯的新ν父支持与成本，不做又一轮旧模型调参：

1. 精确输入为Stage124已读schema的五EVNT（epos-pi-0/-1、epos-k-0/-1、powheg-pythia-charm-central；完整路径见sample_strategy.json）、Stage119旧曝光合同与现成官方链。另在任何新风险前冻结有限pilot、预算、来源/角色/纳入概率和失败处理；实际解码完整末态/parent-entry-seed并比对旧曝光。若EVNT只有入射粒子，须从GENIE生成开始记录完整身份，不用p6 schema猜完整相互作用。不要泛扫已结束的旧目录/日志，不把旧证据缺失设为所有物理工作的全球前置。
2. 测双低能、连续过渡、同pz高y/高E与自然高端支持和ESS，确认家族另锁；只有新的确需步骤才做完整G4/reco成本pilot。以实际CPU/I/O/RSS/选中与困难侧产额在同一工作包定接近N₀→约2N₀，继而交固定组成/政策的能量及尾风险；不能只交metadata/字段表或两父响应图。当前旧train最低940行/926代理/ESS933.053、第二4245/4100/4172.079、困难1086/1079/985.267；Stage119新增52/180/57，不是翻倍，独立完整家族仍未认证，新全链成本未测，不能宣布数量饱和。
3. 有完整过程/祖先时开展Stage123下游μ/非μ谱系及固定边界首次外穿能流机制→可部署代理→全队列能量/尾；不用H/Eν当新信息，不以单粒子枪或同父重复增加νN。新两父G4只按需作工具/成本验证，不作总体方差或历史producer认证。
4. secondary三父51视图（14含secondary）安全channel-primary/first-two差0 pC；官方UB、历史两条原生选择未知界仍保留。极晚4.3153e35 ns已核float持久化/源码默认，但真实历史physics constructors/time/过程仍未认证；仅在新精确producer证据出现时有界核因，不自动删大值/归中子/称可DAQ收回。1cal PHYS–REC差异已有定向诊断，未知不等于低能物理原因，不继续无限接口审计。

科学读取/ROOT/重建/训练/forward/统计仍HTCondor，Stage125专用~/condor/nu_muAnalysis/stage125；本地只代码/文本结果/stdlib运输。Stage12452作业含4失败共5305 CPU秒、聚合wall14176秒、0GPU，紧凑事件+模型73523751 B，删477625121 B重复副本。原输入已与Stage119 old_input逐字节核对去重，若重放Stage124清单先按报告cp恢复，勿重做旧物理结果。依任务实际资源并行，GPU确适用时使用，不编造加速比；新G4成本不能按digitization速度外推。

一次方动量仅pz0，允许px/py/q/p/弯折；raw11/status/typed NaN/合法signed/Calo缺失、pz>50与正式fitted/reduced cuts、全部K/原角色保持。最终两低箱/传统上95≤1.05、all/direct≤1.01、其余五层≤1.03、八层三向tail差≤+2pp保持，1.05仅非劣效；真正低能胜出/真实响应与系统/背景/接受度/独立确认仍必需。整体目标未达。完成阶段先中文workbook再本地Conventional Commit，不push，Stage54五资产与所有历史后缀只读。

## Stage123历史入口（原文保留）

# 当前研究入口：Stage123已评估，Stage124优先原生关联观测与有效扩样

先读[Stage123完整报告](../workbook/2026-11-06_stage123_native-observables-and-sample-strategy.md)、路线§105、信息预算§85和[Stage122实测](../workbook/2026-11-06_stage122_response-information-and-digitization.md)。本轮用户只要求研究评估：0事件数组/ROOT读取、0训练/推理/重放/提交。Stage122旧JSON中Stage123仅计划未执行，本报告占用Stage123，下一实际计算编号Stage124；以下历史入口完整保留。

最新结论：Stage122三通道粗波形B/A两低箱未稳定改善，最低箱train50/test20 incoming，四臂joint全失败；固定f0的VN/Pres数字化条件方差仅占最低两箱log-MSE1.419037%/1.524472%，不是全噪声/输运/Bayes界。Stage119新增52/旧940、小曲线9/18/36没有测试原规模饱和。不再把旧输入调网络/树/seed/损失/门控或继续scint噪声优化作为默认主线。

Stage124建议完成一个实际科学对照，不能只交metadata：

1. 新观测Z限真实RDO/REC的strip/cluster唯一身份、SP到cluster联结、三位timebin和track实际measurement/可用协方差。复用Stage85已做的读出控制和Stage95身份经验，构造少数唯一测量/组合歧义/跨层一致性/纵向延续摘要；保留合并/共享、未归属与缺失，不真值清洗、不把hitSet当ID、短段100GeV当动量、SCT当模拟电荷或精密TOF。Stage95–97已有候选动量/几何、Stage108点关系不是新输入。
2. 在同支持、同固定学习政策下用强X与X+Z一对模型测连续能量及实际三尾；原f0和传统保留，缺Z不删，truth仅诊断/训练监督。可用关联/匹配准确率或AUC不替代能量收益。不把小队列相对大池f0的差距当信息效应。
3. 独立扩样按两个低箱/同pz高H困难侧的家族N、ESS、覆盖和纳入概率冻结，力争检验接近原规模N₀→约2N₀，不再用9→36推论940附近饱和；约2N仅设计跨度非充分N。若可恢复全Z，做输入×N的2×2；否则分别做同支持输入实验与原规模X扩样，不跨队列伪造因果。保留连续过渡/自然高端、原角色/全部1016 K；新确认家族单留，reserved不开。
4. 新G4只在具体的下游μ谱系/非μ谱系与边界能流机制问题需要时启用。旧两父×2G4×2digi只是工程pilot，不能给总体归因；先测成本再冻结多父机制支持，不因缺旧完整家族而阻塞其他可做实验。secondary三父producer、source36/45/49极晚时间有界处理，不把巨大时间当可回收中子信息，不无限扫描旧metadata。

Stage85已完成2048data+2048MC共同读出控制，纯noise参数不可识别；不重开统一噪声标定，不把大部分01X不接受的raw差归因于模型cluster。若Z缺失则报告精确对象/字段并转可独立执行的扩样；若足量Z对照无增量则结束此观测族，不续GNN/邻域/seed网格。若只有机制oracle改善，转可测代理，不反复旧X latent posterior。全过程真实data/MC和系统/接受度/背景与独立确认仍必要。

一次方动量pz0、允许px/py/q/p/弯折、raw11/status/typed NaN/signed/Calo缺失、pz>50和正式fitted/reduced cuts保持。最终两低箱/传统上95≤1.05、all/direct≤1.01、其余五层≤1.03、八层三向tail差≤+2pp不变；1.05是非劣效，不等于赢传统。未来在有环境终端小QA测CPU/I/O/内存后冻结规模，科学计算走HTCondor，目录~/condor/nu_muAnalysis/stage124/。本轮新可用率/收益/功效/资源均未测，不直接执行。每阶段先中文workbook再本地Conventional Commit，不push；Stage54五资产和所有历史后缀只读保持。

## Stage122历史入口（原文保留）

# 当前执行入口：Stage122已交付，Stage123核producer/time并做完整末态输运pilot

先读[Stage122完整报告](../workbook/2026-11-06_stage122_response-information-and-digitization.md)、路线§104、信息预算§84、[R1–R8审计](../workbook/stage122_energy_ml/completion_audit.tsv)及[下一执行合同](../workbook/stage122_energy_ml/next_execution_contract.json)。本段覆盖下面Stage121及更早入口的当前优先级，全部历史原文保留。

Stage122已完成27来源7501行同队列A/B/C/D，train最低箱50、开发test20 incoming。B/A两低箱未稳定改善，C/D局部变化不跨角色复现，四臂cal/test原joint全False；保留原强f0，无新赢家。9来源252父×16同HITS流，115 active父1840新视图＋115原控制，0fit/reserved/隔离forward；最低两箱数字化方差/log-MSE约1.42%/1.52%，只能说明当前两组scint数字化不足解释大部分错误。小支持/有限模型阴性不称时序无用、Bayes误差或全探测器信息界。

正确MC显式OFLP200/data20/FASERNU-04/OFLCOND-FASER-06；历史ID通过当前官方CableMapping→硬件channel回接；reduced MC时间差27.21/51.41 ns、35 ns窗，Veto2参考channel6/7。最终40父六维差0 pC、完整252父原选择闭合，2父跨进程ADC/状态一致；独立192 RMSE复算差0。旧错误ID/窗外hit-count/时间差/Veto参考结果只作实现诊断。protocol.json内pending/旧planning条件是历史，最终验收见completion_audit.tsv。

下一Stage123在同一科学工作包推进：

1. 对固定source51 entry4386、54:7875、57:8429，闭合安全detector/primary积分及secondary语义。官方长度2数组越界的3父13视图中，前一父有2视图原生选择未知，通过概率[.875,1]；后两父其他cuts失败。保留全部父/hit，不模拟UB或静默改正式cut；无secondary控制应闭合。安全定义下零迁移不能写成全官方链零迁移。
2. 用现有source36/45/49精确记录核持久化时间/实际producer physics constructors、decay/kill/time cuts；max持久化4.3153e35 ns，原因未分辨，不删大值或称可回收迟到能量/中子。C/D风险已量；原G4终止未认证，不续事后时间分箱网格。
3. 从合同内两个精确pi0/K0 EVNT入口、每文件最多前10000父的固定框，按truth和CRC32冻一低能/一高y父；认证完整末态/entry/转换，另起可追溯机制队列，不能冒充当前252父同GENIE。先2父×2 G4×2数字化pilot测成本与实际风险/选择；最多四任务、2CPU/8GB、wall各7200 s/总CPU28800 s、紧凑200 MB。先一真实父/流小样本闭合；成本后、扩展风险前同阶段冻后续规模。新支持/成本未测，不能按同HITS数字化速率外推G4。若缺精确输入/转换，交准确对象/字段/命令与已测producer/time结果，不泛扫EOS或无限metadata前置。

科学读取/ROOT/重建/训练/forward/统计仍全部HTCondor，目录~/condor/nu_muAnalysis/stage123；本地仅代码/文本/stdlib打包运输。CPU多来源并行、内线程受控，有GPU适用任务时按实际工具/计时采用，不能编造加速比。Stage122122提交/119执行全计CPU11506 s，紧凑缓存+模型103684329 bytes，已删693206423 bytes重复副本；不重跑已通过计算。下一阶段不加模型网格，不开放reserved、不平均视图部署、不增独立N。旧池R7补证已结束，同EVNT文件不证明同entry，缺祖先不阻挡实际波形研究。

原角色/全部1016 K/pz0-only一次方动量（允许px/py、q/p、弯折）/raw11/status/typed NaN/signed/Calo缺失与pz>50及正式fitted/reduced-charge cuts保持；最终两低箱/传统上95≤1.05、all/direct≤1.01、其余五层≤1.03、八层三向tail50差上95≤+2pp不改。真实data/MC ADC、系统/背景/接受度与独立确认仍未交，整体能量目标未达。完成先中文workbook再本地Conventional Commit，不push；Stage54五资产/历史后缀保持。

## Stage121历史入口（原文保留）

# 当前研究入口：Stage121读出信息与可控响应路线

先读[Stage121完整研究报告](../workbook/2026-11-05_stage121_response-information-and-replica-strategy.md)、路线§103、信息预算§83，以及Stage119/120的实测证据。本轮用户只要求研究评估，无环境、不复现；0事件读取/训练/重放/作业。下面Stage120及之前入口保留为历史，当前优先级由本段覆盖。

Stage119小模型曲线有数量效应，但新增最低箱52、原940，尚未裁决原规模饱和；扩样候选联合目标失败。JEFF/direct最低箱相对名义1.488752 [1.027589,2.165737]，33对36条且混杂未除；窗外约18–19%为沉积比例，不是信息损失或可部署收益。完整祖先缺失，不能称物理oracle阴性。

**修正当前停止规则：** 200187/188同EVNT文件不是同entry的证明，继续不计未经认证的独立N；200131–136缺日志只限制该旧池，不是所有科学工作的前置。旧池补证只做一次有界任务，取不到就结束该支线；可选另一已核父—HITS—读出队列，或记录完整身份的定向小父生产开展机制实验。完整祖先是中子归因前提，不是窗口内波形/沉积增量前提。旧门值/历史代码不改，不把这些修正当允许泄漏或开启reserved。

下一有环境科学工作包按报告§3–7：

1. 用明确输入冻结双侧父队列，覆盖两个低能、过渡区、可能进入同低pz的高y高能及自然控制。现有开发父可做机制实验、不称blind；独立确认另留新家族。若支持不足，定向GENIE/已核父采样记录全部纳入概率；新G4成本先实测，不先全量生产。
2. 同队列比较A旧62/状态→B累计加入实际可保存窗内VetoNu0/1与固定下游参考联合波形→C加窗内敏感沉积时序→D加窗外沉积。C/D只作理想诊断；完整祖先不阻塞A/B/C。窗口/参考/容量事前固定，missing、弱/零/饱和全保留，交连续能量和实际三尾，不以波形可用或标签分类精度代替收益。
3. 预定子队列先同HITS重复数字化，必要时同完整GENIE末态重复G4，分辨读出与输运波动及稳定偏差，所有父通过/失败路径保留。随机流/处理顺序须验证，不能凭同seed称响应配对；重复视图不增加父N、不跨角色、不能平均后当部署观测。
4. B有稳定增量才尝试有限联合波形测量似然，保留幅度/时序不确定度与通道相关；仅C/D有增量则检查读出/DAQ可行性。足量支持后才做名义/变体训练×评价的固定N小矩阵，区分响应迁移和环境内难度。各层阴性只限制固定族，不宣称全探测器信息界，不重开旧门控/树/seed/GNN网格。

同一工作包完成可做部分的物理测量，避免再次只交metadata。预算按pilot实际CPU/event、读字节、内存与有效支持冻结；HTCondor目录~/condor/nu_muAnalysis/<stage>/，只存紧凑摘要/必要波形和父身份。所有新性能/功效/成本未测，本轮不自动执行。原pz0/raw11/status/typed NaN/signed/Calo缺失、全部1016K和角色保留；两低能1.05、all1.01、其他五层1.03、八层三尾+2pp不变，1.05仅非劣效。真实系统/背景/接受度和独立确认不可省，原reserved继续关闭。完成先中文workbook再本地Conventional Commit、不push，Stage54历史资产/后缀保留。

## Stage120历史入口（原文保留）

# 当前执行入口：Stage120 身份门未通过，先获取 producer / parent 证据

先读 [Stage120报告](../workbook/2026-11-05_stage120_provenance-gate-and-k-lineage.md)、路线§102、信息预算§82和 [Stage119报告](../workbook/2026-11-05_stage119_support-curve-and-response-mechanisms.md)。Stage120只做目录/保留日志审计：200131–136六个log目录为空，producer身份未认证；200187/188日志的Input File相同，不能把K c2称独立家族。不要因目录文件数、不同run号或文件名继续扩大训练N。

下一阶段只接受下列输入：

1. 200131–136每个被纳入文件的producer子作业、EVNT输入、entry/skip、seed、release、geometry/calibration和parent/incoming映射；必须同时给出与旧曝光的逐文件/逐parent交集。验收是可核的独立家族和低能支持，不能只给目录计数。
2. 200187/188的job分块、seed和entry范围。若无法证明独立重放，将两者视为同一K家族的响应诊断，不纳入新增训练或确认N。
3. 只有身份门通过后，才对JEFF最低能共同支持做同parent、材料/深度、完整GENIE末态和数字化条件成对核查，并同时保留父通过/失败与实际读出风险。当前条件环境比不是中子库因果或正式1σ。

身份门未通过期间不重训、不增加树/seed、不开放reserved、不全量新G4/GENIE。一次方动量仍只用pz0，px/py、q/p、弯折允许；raw11、status、typed NaN、合法signed负值、Calo缺失和原cut/pz>50保持。最终1.05/1.01/1.03及八层三向tail+2pp、真实系统/背景/接受度和独立确认要求不变。所有事件和统计计算走HTCondor；先中文workbook，再本地Conventional Commit，不push。

## Stage119历史入口（原文保留）

# 当前执行入口：Stage119联合实验完成，下一步核独立低能支持和响应归因

先读[Stage119完整报告](../workbook/2026-11-05_stage119_support-curve-and-response-mechanisms.md)、路线§101、信息预算§81及[完成/缺口清单](../workbook/stage119_energy_ml/requirements.tsv)。下面Stage118及更早入口均为历史；其“本轮不计算”已经被用户继续推进的授权覆盖，本阶段已实际计算并完成本地阶段提交。

实际结果：兼容生产63文件620947父→58064真值超集→11894 selected；扩样排旧后train1428（最低箱52）、dev287、reserved286。固定组成N/2N/4N330/660/1320的最低箱9/18/36，曲线有小模型数量效应，不能裁决原train940条已饱和。旧train+新增候选最低/第二箱 .280688/.244959，对direct .282644/.246329的区间都含1；相对传统 .145661/.247937和困难尾，原joint失败，继续保留原强direct。精确同N旧对照已纠错为1320，不重跑曲线或追加超参预算。

固定环境已测名义/JEFF/ENDF和Standard/NUX；后者18000父全数字化再稀疏RDO重建，不能用已失败的稀疏digitization。JEFF共同最低箱direct/名义1.488752 [1.027589,2.165737]，尚有producer/材料/末态混合，不作1sigma或中子库因果；Pythia最低箱1/8且共同支持缺失。527 selected全部按真实p6 float入射/vertex/主μ回接，523有W，direct失败而传统通过的13条全W≥3。实际VetoNu时窗和多数祖先unknown已测，不能把窗外沉积或unknown当新中子标签/部署增益。oracle→代理风险仍未测，准确缺口见报告；不要重复把这点当“物理路线阴性”。

下一有界科学任务按报告§7：

1. 用已知输入认证200131–136 producer、200187/188 K同EVNT分块/重复和旧全部曝光的parent/subjob/entry/seed。按已知纳入率及实际独立低能/困难侧产额冻下一规模，大池未穷尽时不先全量新G4；上游或独立支持缺口持续才冻新GENIE proposal的小pilot。目录行数不是独立selected数，不从旧开发曝光造新blind。
2. 对JEFF最低箱信号核完整同GENIE末态、材料/符号/深度和数字化条件；父通过/失败及实际raw/status/时序与固定模型两侧风险一起交。当前conditional matched states未全认证，不能只报共同selected或将环境差全部归中子。
3. 完整祖先与实际匹配读出可交付后，才冻单一非退化oracle→同容量无特权对照→家族/来源留出代理→连续能量及三尾；zero/unknown/弱/饱和不删，真H/E不补答案。不在缺输入时继续同缓存树/seed/惩罚或换GNN名字。

原89033身份/17657隔离、1016 K、pz0/raw11/signed/typed NaN/Calo缺失和原pz>50/fit-charge选择保持；新reserved零预测，HERMES保持能量迁移用途。原1.05/1.01/1.03和八层三尾+2pp、真实系统/接受度/背景及独立确认不改，逐事件目标仍未达。

事件级证据已字节验证压缩至 `ntuples/energy_ml_stage119/persisted_evidence.tar.gz`，需要重现时先按 `workbook/stage119_energy_ml/persisted_evidence.json` 恢复原路径再打包；源与模型/紧凑缓存保留，运输包已去重。全科学计算走HTCondor，提交仍 `~/condor/nu_muAnalysis/<stage>/`，并行/CPU/GPU由实测瓶颈选；先中文workbook再Conventional Commit、不push。下方历史全文和Stage54资产/后缀保持，不据历史措辞重跑。

## Stage118历史入口（原文保留）

# 当前执行入口：Stage118库存与物理机制路线，研究完成、计算未启动

先读[Stage118完整报告](../workbook/2026-11-05_stage118_mc-inventory-and-physics-strategy.md)、路线§100、信息预算§80。用户本轮要求研究思路与可用MC评估，不恢复环境、不运行训练/事件分析。本次只审阅已有结果和57页PDF，所有新增性能/产额/资源均未测量。以下Stage117及更早入口为历史，当前优先级由本段覆盖。

Stage117四臂已经结束；最低箱direct .282644→.246473，仍差于传统.145661，联合风险/尾门槛未达。Stage116物理B仅有输入缺口，没有oracle/代理实验，不能称已失败。旧Stage82/84低能扩样仅约3%/24%，不证明数量充分，也不证明更多MC一定成功。不要继续同缓存树/种子/温度/惩罚、旧门控或无新语义图网络。

下一有环境任务应一次交付“独立支持学习曲线＋最小响应机制对照”，具体分工/判定见Stage118§4–6：

1. 定向核查MC24下游200131–136和200184–189（均z>−2.2 m）的现成PHY/HITS/日志。PDF数量不是独立selected数；认证实际parent/种子/旧全部曝光、producer/geometry/calibration和纳入概率，pilot测两低能、同低pz真高E、高端的支持及成本。缺上游支持不能靠重权解决；不递归扫全EOS。
2. 新生成/输运/数字化家族先固定train/development/confirmation角色。共同支持内固定组成、特征、损失和一个强基线政策，pilot可行后冻结N/2N/4N嵌套规模；数量参考不是充分性承诺。原全目标继续评价，不按truth z部署分流。新确认先锁，旧test不再称blind。
3. 对固定传统/direct做一个事前选定强子化或G4/中子库环境对照，优先200300–311或相应年份G4族，留一环境用于迁移。家族未核不按行号配对；父分母/选择迁移与共同selected风险都报告，不把变体数充独立N或包络充1σ。先看W/模型分支，不把低E等同低W。
4. 修正Stage117非μ比例oracle：上游VetoNu主要响应退激中子，非μ比例可能退化，尚未测定。先定位发生器组成→中子祖先/敏感沉积时间结构→实际读出哪层保留条件能量信息，探索上游迟到活动与下游泄漏联合约束。有可交付读出时同阶段做oracle→部署代理→连续能量风险；HITS/乳胶ntp不默认含完整电子祖先，缺项只定向小重放，不伪造标签/时间窗。仅同旧X代理不增加信息，真H/E或真边界能流收益不当部署证明。

这是一项科学工作包，输入QA之后应给可做部分的物理结果，不无限拆metadata阶段；若某部分不可交付，交准确缺口并推进另一可做部分。批量仍走HTCondor，~/condor/nu_muAnalysis/<stage>/，预算/读字节/CPU/event由小样本实测先冻，只保留紧凑摘要。原pz0/raw/status/signed/typed NaN/缺失、全部1016 K与原角色政策保持。两低能1.05、all1.01、其余五层1.03和八层三尾+2pp不变，1.05只是非劣效，突破需预定改善证据。真实系统、背景/接受度和独立确认不可省略。

本轮没有自动执行上述后续计算。完成阶段先中文workbook再本地Conventional Commit、不push。Stage54原控制已在Stage85完成，历史资产/后缀保留，不据旧措辞重跑。

## Stage117历史入口（原文保留）

# 当前执行入口：Stage117四臂已完成，固定方法预算结束

先读[Stage117报告](../workbook/2026-11-05_stage117_oof-risk-direction.md)、路线§99和信息计划§79。Stage116缓存工作包A已经实际交付：训练内/真实OOF×普通/分层方向四臂，同110维、来源/incoming清除、训练内部4/8树选择（均选4）、最终全train强BDT锚定，以及匹配μ-only对照。15次真实折baseline fit+3次μ-only fit、24次凸解，全部完成；不重新跑该四臂或追加树/seed/温度/惩罚网格。下面Stage116/115入口均为历史，当前状态由本段及Stage117报告覆盖。

预定OOF分层臂test最低箱direct .282644→.246473、传统.145661；第二箱 .246329→.252963、all .287491→.290225。cal_post最坏两低能/direct=1.022398 [.999284,1.047816]、对OOF普通=1.016797 [.992371,1.046633]；共同主比较失败。两低能/传统上95=2.029808/1.096984，all/direct上95=1.012629，低pz真高E总尾差上95+4.320406pp等失败，四臂joint均False。局部改善不抵销困难尾或原最终标准，继续保留强direct。OOF确实生成，但source purging/训练量/offset使其误差分布不同，最终完整管道已测，不能称OOF自动消除迁移。

当前优先是Stage116物理工作包B的可交付输入：[准确缺口与候选中间量](../workbook/stage117_energy_ml/observability_input_gap.json)。七个明确缓存没有谱系敏感沉积/边界能流或新独立生成家族；不扫描旧源或用truth H/E、SP离轴代替新观测。需要预定双侧独立pilot，真实generator/输运/重放family身份、选择分母/纳入概率、实际VetoNu volume map与μ/非μ/unknown谱系沉积、匹配raw/reduced/status。候选是非μ敏感沉积组成量，实际schema未认证、覆盖/收益未测，零/unknown保留、不除H称效率。一次工作包完成原读出→中间量oracle→部署代理→同容量能量消融，代理源留出、全队列风险/尾/资源，成立才扩大编码器；新生产另冻合同并先测小pilot，不自动启动。

有已知共同控制和时基可直接交付时，相对时间可作有限独立分支；无真实波形/响应就不伪造删失幅度或prompt/late。物理工作包B尚未执行，不能称其阴性或完成。原pz0/raw/signed/NaN/缺失、全部K/角色、1.05/1.01/1.03和8层三尾+2pp保持；1.05只表示恢复/非劣效。真实系统、接受度/背景、新blind与完整能量目标仍未完成。每阶段先中文报告再本地Conventional Commit、不push，HTCondor提交目录仍为~/condor/nu_muAnalysis/<stage>/；Stage54原控制已在Stage85完成，保留下方历史资产/后缀，不按旧措辞重跑。

## Stage116历史研究入口（原文保留）

# 当前研究入口：Stage116双线研究路线，有限方向学习与非μ可见度

用户于2026-11-05重新要求文献研究和路线评估，本次仅完成研究设计，未执行训练/生产。优先阅读[Stage116完整评估](../workbook/2026-11-05_stage116_research-strategy-and-observability.md)及路线§98、信息预算§78。**下面保留的Stage115交接是历史记录；其中“下一唯一相对时序”和“不需另做研究阶段”的安排已被本次请求及Stage116路线更新覆盖。** Stage115、110、108的固定实验仍已结束，不重复执行。

下一次现有缓存方法研究：有限比较训练内/OOF残差×普通/分层风险方向学习，四臂同读出、同复杂度与最终保护。它检查Stage115先用总体残差选字典、后加风险约束的具体缺口，不是追加状态子集或树数网格；OOF需实际训练内分折，不把现成train预测冒充训练外。完整管道的OOF→全train基线变化、来源相关、最终风险和实际尾率必须评价，不能由训练可行性宣称泛化保证。具体实施合同与资源需在有环境时按输入冻结，本报告未执行。

主要物理投入转向独立双侧样本及非μ活动的粒子来源/可见度：同一阶段交一个物理中间量的oracle、可部署代理和能量增量，输入及判定见Stage116§5/§8/§9。先明确新样本、关联和响应是否可交付，不无限扫描旧源；新生产是后续工作包，本次不提交。相对时间保留为有共同控制时可先完成的有限消融，不再是唯一主线；联合prompt/late脉冲模型还需真实波形及弱信号/饱和响应，不能用status伪造。

最终目标、原特征/角色/全部K/困难缺失保留、八层风险和尾部保护不变。1.05仅是低能恢复/非劣效；宣称超过传统须另有比值区间上端<1的证据。真正未开发确认和物理系统仍缺。本次阶段报告与路线已形成，后续按明确科学工作包执行，不反复把同一复盘当新实验。

## Stage115历史交接（以下原文保留）

先读AGENTS.md、路线§97、信息计划§77、[Stage115实测报告](../workbook/2026-11-05_stage115_measurement-state-residual.md)、[原Stage114设计](../workbook/2026-11-05_stage114_measurement-state-and-risk-research-reset.md)§5以及[主端点](../workbook/stage115_energy_ml/primary.tsv)/[门槛](../workbook/stage115_energy_ml/gates.tsv)。**Stage115已完成，不重复作业或继续其树/seed/状态子集网格。** 原Stage110固定差、Stage108三格/遮挡与旧门控/重权均结束。本次用户授权的下一阶段已兑现为实际能量结果，不需另做无实验研究阶段。

## 1. 最新实际结果

唯一Condor9668138首start/exit0。原71376 active（train/cal/test46575/11612/13189）、17657隔离、全部1016新增K和原incoming视图权重保持。origin/origin_row回接原62/11路status，incoming/run/event/group核验；全部状态可用、缺状态0，原62缺项21/6/5不删。原Stage87 direct_cal缓存含train，0新基线fit/forward，无ROOT/生产/换split/cut。

A原62+三flag+共同availability=66，B增11×4位=110。每臂8棵depth3/min_child_weight200、原eta.04/λ10/固定seed2026110515，52叶/rank45；固定字典signed残差和四次预定凸解已实际完成。主τ2.032000317154125、次修正平方.0023840304354885724，124/151迭代均success；主/次最大归一化违反1.073e−12/1.565e−11，近似KKT驻点1.441e−5/5.918e−6，无严格dual界或全局最佳宣称。主目标最低箱/all保护活跃，第二箱未活跃。

**B/f0主cal_post最坏两低能RMSE比1.024843205547326 [1.0058712848637628,1.0508710279789928]，失败；B/A1[1,1]，无受支持状态增量。** 最低箱cal .330275→.304464、test .282644→.270006有局部下降，但test传统.145661；第二箱test .246329→.252093，all .287491→.292520恶化。A/B目标及已报风险相同，不宣称独立核过逐行A/B完全相同，也未保存逐split特征使用表，不能把当前阴性归为所有状态冗余/信息界。状态非全常数，train Veto10/20/21 overflow19825/19174/18443（分母46575）。

两臂/θ锁后才新test前向与风险，完整原八层/状态/缺项/高端/三尾已交。B test两低能/传统上95=2.247412/1.092172、all/f0=1.021024失败；低pz真高E总/负尾差上95+3.391598/+2.583281pp、high-y负尾+2.360973pp等失败，A/B joint均False。不以train平方hinge保护冒称实际尾率或留出保护。40test配对独立区间max1.421085e−14，三主2.220446e−16，504旧参考标量差0，500draw主端点全有效。

## 2. 资源、产物与不变政策

4CPU申请8GB站点12GB，内线程1/0GPU，GNU73.72CPU/42.38wall秒/RSS515116KiB<1800/900；worker/两臂嵌套成本不重复相加。worker本地archive接口40315471byte，不是物理网络，整树峰/单核加速/全会话成本未测。21项输入原字节一致，运输副本核后删除；两小规则头和一个约1MB紧凑A/B点表保留于ml/artifacts/stage115，表/图/协议/资源于workbook/stage115_energy_ml，spool ~/condor/nu_muAnalysis/stage115/。完整[完成审计](../workbook/stage115_energy_ml/completion_audit.tsv)区分实验完成与项目未达。

一次方动量仅pz0，允许px/py/q/p/弯折，raw11/status/typed NaN/合法signed和Calo缺项、pz>50/原角色/全部K不变。负reduced已允许signed，不修cut/设通用NaN；不把fit坏与wave坏混同。unknown status是新增NaN/availability，不当正常零，弱/饱和/缺失事件不删。无新offset/主候选或阈值事后选择。Stage54原控制已在Stage85完成，保留旧资产/后缀，不据旧“未完成”措辞重跑。

## 3. 下一有界新观测问题

按Stage114§5，优先研究**VetoNu0/1相对一个事前固定Veto参考的时间族在给定电荷/状态/pz后是否增加连续能量风险信息**，区别于Stage80 peak/width。先另冻该科学合同/参考/两路差分/允许来源与预算，再同一任务内校准检查和一次匹配能量消融，不另拖成小QA/metadata阶段。不是再次扩Stage115字典或多状态头。

已知入口为ntuples/energy_ml_stage79/measurements.npz、Stage79生产证据与原PHYS精确producer，μ控制清单ml/configs/calonu_muon_files.tsv，及现行Stage87固定身份。Stage80 shape.npz只持久peak/width派生族，不能声称已有完整localtime。全池相对时序可用率/实际cost及匹配μ控制未测。只沿既知入口定位，不能扫全EOS/恢复旧REC/全部波形或新生产；如需已知PHYS定向读取，须在新合同列完整同split身份和资源，保留全样本missing路径。

必须证明两路共用可消的加性时基，并核通道常数/μ路径传播/time walk/fit fallback；trigger绝对时间无效不数学上否定共模差分，但不是校准证据。参考与窗口不得由test挑选；弱信号/overflow/无有效时间只新增NaN/availability，原能量仍预测，不用有效时间cut净化样本。若时基/μ控制可交付，再一个固定相对时间族与强基线匹配对照、头/输出先锁再cal_post/test全报告；验收为两个低能及困难/高端的配对能量风险、实际可用率/资源和原最终全部门槛。不以时间变异/可分类或truth时间oracle代替部署收益。若不可校准则交准确缺口并结束该实现，不硬造常数/1σ或称物理阴性。

父分母扩展/producer精确定义仍为解释支线，不因重新读取旧selected而称新训练支持，不改Stage113零charm/稀少draw端点，不以六稀有单元都能报CI作为能量学习前提。下个任务真实功效/效果/资源未测，本阶段不自动执行。

## 4. 最终要求

两低能RMSE/传统上95≤1.05、all/direct≤1.01、其他五层/direct≤1.03、八层总/正/负tail50差direct上95≤+2pp不改。真实response/interaction/FSI/材料/Calo/接受度/背景及新独立确认仍未交付，整体能量目标未完成。incoming条件CI不含source/parent/refit/研究选择/真实系统和新blind，不能以开发test重复改善冒称确认。每阶段先中文workbook，再本地Conventional Commit，不push；不自动新训练/生产或网格。

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
