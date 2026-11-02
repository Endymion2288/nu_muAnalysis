# 下一轮执行 Prompt：stage53 tracker额外活动的同事件噪声机制控制

先读AGENTS.md、stage49审查§7、[stage52报告](../workbook/2026-11-02_stage52_f6-muon-response-control.md)、修订路线§34、信息计划§19，以及stage37/38已验证的μ HITS/RDO/reco身份联结工具与manifest。**只推进一次有界tracker读出机制问题，不恢复CaloNu波形/历史生产或架构扫描。**

## 1. 已知物理结果与本轮问题

stage52完整18文件6,021,535条，选中data940,724/MC199,239，来源隔离40格标准化主评价data511,500/MC99,421。station3>6的data26.069%、MC71.210%，差−45.141 [−45.441,−44.866] pp；station1/2也大幅MC偏多。SpacePoints>12、普通segment>4却是data多4.417/4.233pp。两动量层、三个run、MC符号和位置都保持。Timing总电荷中央尺度接近，不替代宽度/状态/触发或强子闭合。

MC/data已核计数branch代数、charge单位和Timing面一致，但生产、noise、masking、timebin/compression及tracking未完全匹配。SCT FrontEnd源码有随机noise-strip注入，expanded特定模式可改变占据；DB可覆盖fallback。**尚未测该噪声项是否解释多出来的cluster，不能已当成定因或正式系统。**

本轮只回答：在已核实同事件、同生成/输运末态和相同重建配置下，独立随机noise-strip注入对额外cluster、SpacePoint/segment及μ选择产生多大因果变化？这一机制份额能否解释stage52的部分模式，哪些差异仍不能解释？

0新能量fit、0新概率映射、0谱反演/toy/coverage、0新G4事件。不对data残差训练或反调BDT，不把MC on/off全差当正式1σ，不宣称μ控制证明ν hadron响应。

## 2. 必要输入与有界预检

- 使用既有12个MC μ PHYS来源和 `ml/configs/calonu_muon_files.tsv`；配套stage37/38的 `ml/locate_calonu_native.py`、`ml/read_calonu_native.py`、`ml/prepare_calonu_native.py`、`ml/prepare_calonu_repair.py` 和已保存case manifest。先读其真实产物路径，不猜新路径，不递归扫EOS/全历史生产。
- 从**已知**对应production logs/config与CVMFS已编译构建核实actualSCT NoiseOn、AnalogueNoiseOn、UseCalibData、occupancy/threshold、timebin/compression、masking和collection。header默认不是actual；noIFT目录字样不是物理几何或collection证明。
- 最多40例预检只用于schema/事件身份/名义重放、输出/计时。PG merged eventID会重启：用source/entry与生成子文件映射、primary指纹/原生标识验证，不按重复run/eventID强配。
- 先验证nominal重放能复现原RDO的SCT strip/timebin及reco计数/选择；规定允差，实际报告不符比例/幅度。原始配置未复现则不能把nominal-vs-新臂差冒充单一噪声效应。优先运行现成匹配build，只有确需源码变化才隔离补编译。
- 预检用最小branches/collection，统计实际wall/CPU/RSS/I/O；大规模读出和重放通过Condor，不在交互节点批量运行。不保存xAOD/RDO/HITS副本或逐hit点云，临时产品scratch内处理并删除。

不能只交元数据库存结束：若nominal不可重复，至少给出同事件SCT/计数的实测不符、已定位与未知配置边界及缺失的具体输入；不得以小pilot否定整个读出方向。

## 3. 看两臂结果前冻结唯一实验

- 目标跨12来源、两μ符号和100–250/250–1000GeV的**2048例**；按已知身份哈希/固定分层从完整已知范围选，不能看计数/噪声残差挑例。尽量扩大支持而非机械复用旧128。选择权重、source混合与两动量N事前冻结；小机制样本不得称为全ν性能确认。
- 受实际映射/资源限制时，明确全部来源覆盖、可用范围、无法测的结论；重要总体判断须扩大来源/样本，不能用少数异常终止分支。旧128例可作程序对照，不单独承担最终推广判断。
- 两臂为actual nominal，以及**仅**NoiseOn=False、AnalogueNoiseOn保持nominal、其他occupancy/threshold/timebin/masking/几何/重建不变的机制臂。预检必须从工具实现确认该配置确实只移除独立随机strip注入；不能未经核实把DoInnerDetectorNoise=False当同义，它可能同时去掉analog噪声。
- 实际noise已关闭或语义不支持时，不强造干预；报告nominal验证和为何此机制不适用，不自动扩展成任意noise/timebin网格。
- 相同HITS/初态，记录两臂随机配置；不以共用随机种子宣称除该项外所有随机流完全配对。尽可能复用同一信号处理/已有RDO去噪重建时，要核实可追踪noise身份，不用“无SDO”未经证明就当noise。
- stage52最高pz、tag、质量、几何/动量定义保留。原事件名单以nominal参考固定，**同时**报全部配对事件选前读出，以及各臂通过/失败迁移，不只留两臂都通过。不能用重新匹配运动学把真实选择效应抹掉。

## 4. 指标、成本与解释

主报nClusters0–3、SpacePoints、普通TrackSegments的配对均值、>6/>12/>4额外率、中央分位数与尾；两动量层、μ符号、所有来源、选择迁移。来源配对500次区间，稀少source的限制明确；如noise随机波动过大，可事前冻结少量重复，不看结果追加seed。

把noise开/关对μ控制的变化与stage52同条件差异方向/幅度并列，明确运动学/生产支持差别。若cluster下降而SP/segment基本不变，可支持特定孤立噪声机制；若方向/幅度不足，报告能排除的范围，不能自动说所有噪声/几何/读出已排除。不用统一计数或gain比例替代变体。

资源先由预检测量冻结：默认不超过8个并发Condor、每进程1–2CPU/≤6GB、累计CPU≤8h、请求输入≤10GB、紧凑最终输出≤20MB；这是后续上限，不是已测成本。若2048例重放真实超限，先用已测耗时说明可交付支持，不悄悄缩为有利子样本。schedd忙可换，但先核旧任务0启动后hold/remove，避免重复。按stage52经验避免固定entry块跨basket重复读，先验证iterate/basket复用效果，不把理论byte数当实际I/O。

## 5. 结束条件与后续

- nominal重放通过且单机制差异有清楚配对证据：交付该噪声项的因果份额及剩余差异；下一轮才考虑有data依据的真实读出变体及固定F6对同事件ν的压力，on/off不直接作为正式1σ。
- 机制不足或nominal不匹配：给出实际差异、区间/覆盖和最小缺失配置，结束这一臂；不续开参数/seed/读出族扫描，不宣布F6全部不可部署或达到硬件极限。
- 本轮不启动ν重训练/谱toy。独立ν interaction/FSI、G4/材料输运、预定可辨识正向谱硬度及真正未开发生产确认仍必须交付；μ噪声控制不能替代它们。六箱病态结论保留，不以改箱/更多toy遮蔽。

先写中文stage53 workbook报告，记录协议、actual配置/身份、全部数值/单位/分层/区间、程序与物理解释、执行命令、计时/资源/I/O/最终路径及具体下一任务。代码/配置/紧凑表图一起本地Conventional Commit，不推送；不自动启动stage54。
