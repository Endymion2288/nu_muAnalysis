# stage38 冻结协议：稳定积分/回退修复与弱信号确认

冻结UTC 2026-11-01T16:17:56.234576+00:00；起点ef5dc89。开发只用stage37原波形；尚未打开本次四来源的原生波形/HITS。
固定源1ec47efe；修复patch与StableWaveformIntegral.h在冻结前由84组合成参数和旧保存参数独立积分核验。
不限制原尾参数范围，不删除大/负/非有限保存事件；不修改原PHYS或stage35模型/test。

## 支持、预算与独立性

新来源group1/4/7/10，μ−/μ+各两组，与stage37不重叠；每组两p层各12常规+8诊断，共128例。
常规沿已选行等距，无CaloNu cut；诊断每类最多2例，依次非有限/饱和/raw>10pC/fit失败/负值，不足按行填充。
stage36汇总读出已用于诊断挑选，不能宣称样本完全未知；原生波形仅在算法冻结后打开。
不将富集诊断用来估总体故障率，不把来源文件隔离当生成谱系独立性证明。
沿用实际entry/fingerprint/HITS-RDO三动量/rec-PHYS逐例核验，历史cable payload显式固定。
最多8个Condor jobs（含技术重试），0新ML fit/G4，不全量重模拟，不保存大HITS中间数组。
先在stage37首例验证compact读取，再提交四组；每组原/修复函数重放全部128模块。

## 修复与读出验收

固定参数稳定解析积分与独立分段quadrature比较；函数重放检查最终有限性、failure位及raw/Gaussian fallback。
正常可辨认正脉冲固定参数相对差门槛3e−6（绝对1e−5mVns）；有差异不能自动调松门槛或删尾。
CB time NaN做显式故障注入，不冒充真实发生原因；饱和/窄峰如实报覆盖，有限不等于精确物理信号。

部署候选只用保存波形、ADC、baseline/rms、时间和已固定conditions模板，接口不接HITS。
比较正半波raw、signed、固定baseline模板、模板+常数项；后者为主候选，不裁负、不选峰、不逐例调时间。
模板取生产kernel，固定820ns；±2ns仅为预定义敏感性控制，不选择更优者。
另对baseline统一±1个保存rms做敏感性；noise control为ADC[100:176]的76个离峰采样。
目标仅在评估端取名义HITS窗内线性信号pC，包含Birk/nonuniform/名义TOF限制，不称绝对能量标定。
报告事件四通道总量的RMSE、bias、R68[pC]和绝对误差>0.25/1pC尾率、离峰RMS及两个p层。
固定1000次来源block bootstrap（各符号内抽2组，seed20261105），配对区间；四组不包系统误差。
门槛：主候选相对signed的常规RMSE改善95%下限>0、离峰RMS下降、baseline常数扰动不变，才进入后续CC小预算。
若不通过保留失败结论，不追加调参；本阶段不声称ν能量、data闭合或最终能谱收益。
中文workbook记录全部数值/命令/成本/局限，更新路线与Prompt，提交代码/patch/报告，不push。
