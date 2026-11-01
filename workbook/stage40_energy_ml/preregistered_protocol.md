# stage40 冻结协议：空HITS噪声路径与有限时间自由度

起点7485e05，冻结UTC及完整门槛见ml/configs/calonu_response.json。
旧stage39波形仅作开发：先固定模板、一次时间导数诊断，再一个有界时间残差拟合；无后续方法扫描。
导数振幅近乎与时间正交，未修正二阶振幅损失；改用四通道共享一个时间、四个有符号振幅与常数基线。
以波形残差最小选择时间，绝非用HITS/truth或逐例挑不同读出。精确并列取较早时间。
固定中心820ns，时间范围±4ns、0.25ns网格；中心±2ns为预定义鲁棒性控制，不扩大边界或事后扣偏差。

## 支持与预算

stage35已有fit内π/K/charm第三和倒数第二个完整10000例文件：index2/43、49/105、111/119。
与stage39六来源及各组件pilot首文件不重叠；不是新独立ν能量test，也不证明flux-library谱系独立。
每组两p层100–250/250–1000 GeV各最多12常规，eventID稳定排序后等距取，无CaloNu cut。
每组8富集诊断，顺序/每类最多2沿stage39：非有限、饱和、highraw、负值、fit失败、零读出、高y。
不足按已有行填满；charm低p不足12全保留，不换源；实际181例=133常规+48诊断，上限192。
先冻结、再看新原生波形/HITS；只用旧fit汇总选支持。缺失不补造ADC或零估计，区分完整/缺失分母。
身份联接/历史mapping与数值检查沿stage39；正常新读出接口只用waveform/ADC/baseline/conditions。
最多10个Condor jobs含技术重试；计划两原生合并job（各三来源）+一源码噪声job，0 ML fit/新G4。
先单例native和小型源码noise smoke，大批量走Condor；不自动全量PHYS/GeoModel重建。

## 显式空CaloNu修复范围

原生产1ec47efe：简单删早退会解引用空集合首hit。patch仅新增显式CaloNu noise方法、接口2.0、
默认关闭的DigitizeEmptyCaloNu；仅CaloNuHits为空且显式开启时调用历史CaloNu映射及原convolve(empty)。
Ecal空路径和全部非空生成/卷积函数保持；需重建接口、工具与调用模块才能投入完整Athena。
本阶段使用原源码函数+显式历史ID/conditions替身的受限控制，不冒充完整Athena或原始随机种子重放。
2048独立合成noise例，TRandom3固定seed20261107，历史base15650ADC/rms3ADC。
256对无hist/全零hist比较相同seed下全部ADC相等，四通道均600samples。
baseline均值容差0.02ADC、量化noise RMS相对理论sqrt(3²+1/12)容差2%。
这是合成源函数验证，不将新噪声写回旧缺失观测；不估stage35模型收益中缺失标记贡献。

## 波形读出验收与报告

同事件比较signed、固定模板+常数和有界时间主候选。名义HITS窗内线性信号仅作评估标签，
保留Birk/nonuniform/名义TOF限制。逐总体、两p层、能量、y、名义z、组件及primary代理报告
RMSE、bias、R68[pC]、|误差|>0.25/1pC尾率、offpulse RMS和时间边界率；诊断不估总体异常率。
1000次组件内来源组paired bootstrap，seed20261107；每组件两来源；六组不含系统误差。
主候选常规RMSE相对signed改善区间下限>0、离峰RMS低于signed且≤固定模板1.25倍；
baseline±1保存rms下电荷最大差<1e−10pC，负输出不截断。
高信号参考固定≥1pC：三中心每个事件无噪声模型相对误差≤5%，相对名义中心变化≤5%。
全部高信号保留，不删除失败、不临时改变阈值；饱和/严格barcode primary不足明确未测量。
若通过只是响应控制的条件MC证据，仍需分清源函数与完整Athena修复范围，才能另冻有限能量模型实验。
若不通过先定位形状/噪声/时间原因，不立即扩网络或用旧test反复确认。
中文报告、实测资源/失败成本、紧凑cache读回清分片、更新路线/Prompt、Conventional Commit，不push。
