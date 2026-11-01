# stage37冻结协议：原生CaloNu响应链与通道映射

UTC 2026-11-01T14:51:06.325607+00:00，起点b93abf4。
冻结前只读MC100049首HITS/RDO/rec文件的第0条原生事件、其schema/源码及只读兼容性；
该条hit能量和四通道raw量已见。读取程序的失败/修正必须记录，不伪称完全未知的独立确认。
源固定1ec47efe；原CaloNu AFS build不可读，使用已有d32b0ff3 runtime中与源逐文件相同的
p1a/p0及WaveformHitAuxContainer_v1持久化字典、能量转换器。不得调用普通版本的CaloHit行列解码，
不运行普通几何重建；原native id由匹配源bit布局/conditions独立解码。

## 样本、用途和预算

从stage36已有cache固定group 0/5/6/11（μ−/μ+各首/末），每组32例，共128。
每组regular为reco 100–250、250–1000GeV各12个按选后行序等距例，无CaloNu质量cut；
另8例按非有限、有限|EM|>1TeV、fit-failed、负值优先级，类内按行序取不重复诊断对照。
96 regular/32 diagnostic分开汇总，不能用富集样本推总体失败率。
原生来源均已有HITS/RDO/xAOD；取实际PHYS entry，由(eventID,p,x,y,raw0)唯一fingerprint定位，
不把重复eventID或selected row当原entry。合并顺序必须与生产日志/完整事件数核对，
HITS file序号与entry、RDO/rec EventInfo还须逐例一致，raw/fit读回须与stage36 cache对照。
阶段最多8个Condor jobs（含smoke/技术修正），0 ML fits、0 G4事件、0重模拟、0重跑全量PHYS提取。
先局部单例smoke再4组Condor，直接随机读所需branches/entries，不拷贝整份ROOT到EOS或保存新xAOD。

## 冻结对照和物理验收

1. 从匹配GDML遍历和factory编号、CaloNuID布局、正确MC/data数据库/IOV认证
   region→hit id→readout id→hardware→分支；与stage36的事后候选排列比较但不以它调映射。
   几何旋转/安装survey若未认证需明确；不得用路径代理做精确沉积标尺。
2. 原生p1a转换器读保存的敏感hit energyLoss（MeV）、时间和位置。
   注意源包含Birk/nonuniform修正，不能冒充未修正G4原始沉积或精确全detector能损。
   同例比较RDO ADC、rec保存baseline/rms/time/wave/raw/fit/status、PHYS电荷和MIP换算。
   分别重算signed与正半波积分，使用保存窗口或独立conditions窗口；不从响应峰挑窗口。
   raw电荷绝对容差3e−5pC、wave容差3e−4mV；非有限保留并计覆盖。
3. 查询digitization kernel、MIP、range、timing、HV payload，区分MC OFLP200与data CONDBR3。
   按源卷积构造无噪声期望（若所需TOF/几何未全部native认证，称名义响应预测而非严格生产重放），
   对比信号peak/5σ、窗口捕获率、signed积分和整流pedestal，定位弱信号/漏窗/标度原因。
   可做冻结公式的同例信号/噪声分离，不改stage35模型、不给新BDT收益。
4. 对代表非有限/未标flag与正常case作有界原算法重放；若匹配完整工具不可用，
   明确哪些是持久化读回、代数传播定位、源函数重放，不能互相冒充。
   data15838两时期条件/trigger记录有界核查，不以总EM峰猜增益故障。

主验收为有数据支持的具体响应环节结论，含覆盖/失败/单位与程序机制，不只搜索目录。
regular样本按来源组、两个p子层报告中位/范围，固定1000次group bootstrap（seed20261104，
两符号内各抽两个来源组；只有四组，区间不代表总体/系统精度）。诊断例逐例列出，不计算总体概率。
没有合适的独立data几何/响应条件就保留物理闭合未测量；不得直接乘25或按关联峰换排列。
只留紧凑最终NPZ和去重汇总；完整计wall/CPU/RSS及失败成本。中文workbook、路线和Prompt，
Conventional Commit、逐blob读回、工作区干净，不push。
