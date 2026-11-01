# stage39 冻结协议：CC同事件波形联接与固定读出控制

起点d25c353；算法保持stage38，配置冻结时间以`ml/configs/calonu_cc_waveform.json`为准。
此前只读已有stage35 fit汇总/文件名与RDO/rec/HITS的branch和entry元数据，未读本次CC波形/HITS值。
准备阶段依次发现旧cache status为float、K末文件为8184例、charm第二文件低p层仅11例；
显式转整数，按既定完整文件规则跳过partial，低p不足12时保留全部且不补来源。
这些修正均在配置冻结和打开原生波形之前，无原生物理结果用于选择。

## 支持、预算、身份

选stage35 fit的π/K/charm各两个完整10000事件来源组，index1/44、47/106、110/120；
不选各组件pilot首文件，取第二个与最后一个完整fit文件。不是新的独立ν能量测试分区。
每组100–250/250–1000 GeV各至多12常规（不足则全部），按eventID排序等距取样，无CaloNu cut；
另8诊断，依次非有限/饱和/high_raw>10pC/负值/fit失败/零读出/high-y，每类最多2，剩余按已选行填充。
上限192例，实际190例（142常规、48诊断），保持事件支持；未覆盖类型标未测量，不临时加例。
最多8个Condor jobs含技术重试，0 ML fit/新G4，无全量PHYS/xAOD再生产。
先固定第一例smoke，程序更正不改物理定义/样本/门槛。大批量只走Condor。

PHYS真实entry由eventID、leading p/x/y、raw0唯一fingerprint定位，不用cache行号冒充entry。
每1000例一个HITS子文件，实际entry商余数定位，再核验HITS/RDO/rec run/event，
HITS/RDO BeamTruth所有保存粒子的PDG/status/三动量，以及PHYS入射ν三动量。
rec/PHYS四模块raw/fit/status逐例匹配，读取class layout兼容；映射固定历史payload的[1,0,3,2]。
审计124文件已有RDO/rec/HITS覆盖；原生实际联接的确认限于冻结190例。
CaloNu缺容器/空波形必须与真实零分开，明确present mask；不补造baseline或把缺失ADC当0信号。

## 冻结读出与评价

stage38原生产kernel，mean820ns；比较正半波raw、signed、固定baseline模板、模板+常数项。
后者为主候选，不裁负、不选峰、不逐事件调时间。固定±2ns只作敏感性，不按HITS挑较好结果。
baseline统一±1保存rms，offpulse ADC[100:176]，不得以本次CC结果重新调权重。
算法接口只用wave/ADC/baseline/conditions；HITS只作评估端名义窗内线性信号标签，含Birk/nonuniform/名义TOF局限。
总电荷RMSE、bias、R68、|误差|>0.25/1pC尾率、离峰RMS及bias、无噪声模板响应误差；单位pC。
按两p层、y（<.4/.4–.8/≥.8）、真交互z（上游/下游名义CaloNu中心）、组件及诊断/存在性分层。
严格primary barcode不可得，单独列kinematic-parent代理，不能宣称严格confirmed。
所有分层支持不足就报告实际N或未测量，不删除总体中的离群事件。

1000次来源block bootstrap，组件内各抽2组，seed20261106；读出共用权重。
富集诊断不计算发生率或确认CI。六来源少，来源区间不含系统误差或完整总体不确定性。
缺失波形保留为覆盖结果；数值读出误差只在共同有效波形支持计算，另明确各分母，不将其当新选样物理精度。

## 有限验收与决策

联接、ADC→保存波形和raw单位检查先通过；正常主候选相对signed的RMSE改善95%下限>0、
离峰RMS下降，才支持CC弱信号读出收益。恒定baseline扰动必须不变。
另固定名义HITS窗内信号≥1pC为高信号参考；名义模型模板相对误差和±2ns模型响应变化如超过5%，
视为必须解决的时间/形状局限，不以总体平均改善掩盖，不立即开展ν能量模型训练。
无高信号或饱和支持则标未测量，不视为通过该区域验证。
若有缺失，需说明原始生产及已有读出的含义，不能把程序空容器归为物理零沉积，除非HITS及源代码支持。

本阶段不预报ν能量增益。后续只有读出/支持适用才另冻有限模型实验；
stage35已用test不可再作为修改模型后的独立确认。真实data/强子标定/系统及最终谱收益继续未测量。
报告中文workbook、实测单位/命令/资源及失败成本，紧凑cache读回后清分片/payload，更新路线与Prompt，Git提交，不push。

## 技术补记：质量联接检查

六个初始作业被沿用PG的1keV绝对动量学质量容差拦住，未改样本或读取算法。
失败代表run200140/entry2的ν，HITS/RDO PDG、status、barcode、生成质量和三动量逐值相等，
仅m=−.00390625/+ .0055242716 MeV，signed m²差4.5776367e−5 MeV²，
在E²−p²重算的double舍入范围；见beam_mass_probe/validation.json。
CC改用signed m²差≤64ε_double·|p|²+4ε_float·max(m²)+1e−12 MeV²，
同时严格要求barcode/生成质量相等和能量符号一致，不把质点三动量容差放宽。
这只修正身份检查的数值表达，不改变任何物理读出、标签或验收门槛。
以两个合并作业重读原六来源，作业总数严格保持8；技术失败与重读成本全部保留。
