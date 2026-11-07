# Stage133：边界动能监督代理的固定可部署检验

## 阶段目标与结论

执行 Stage132 研究报告 §5.1，兑现 Stage131 原合同中未执行的边界代理，编号顺延为 Stage133。**固定 B63 未达到 cal/test 两低箱均改善至少5%且条件区间上端<1的标准，原联合门也未通过。结束这一 X-only 边界监督实现，不续 depth/seed/loss 网格；保留 Stage87 direct62。** 这不否定新观测或边界可测性研究，也不是理论信息界。

## 输入、选择与政策

输入为 `ntuples/energy_ml_stage131/matched_input.npz`、`ml/artifacts/stage131/energy_predictions.npz`、`ntuples/energy_ml_stage131/bootstrap_draws.npz`，完整冻结见 [protocol.json](stage133_energy_ml/protocol.json)。3002 个历史自然父的 fresh/reselected 响应，train/cal/开发test=1708/653/641；无新增独立ν、无新G4。风险条件于历史 selected 框且本次重新 selected，不是生成接受度或新blind。

继承全部来源/K/角色、逆纳入概率权重和原 pz>50 GeV/正式 cuts；一次方动量只用 pz0，允许 px/py/q/p/弯折，raw11、typed NaN、合法 signed、Calo 缺失保持。原reserved、新role4和隔离均不打开。边界标签是已有 `log1p(nonmu first-exit KE/GeV)`，不是 H、可见E或 Eν−Eμ；125个train标签缺失不参与代理拟合，事件仍参加能量训练与预测。

四个固定150轮depth3代理：train source%3三折交叉预测，再全train拟合给cal/test；cal/test标签训练数0。标签不足20/常数的预定均值fallback本次未触发；输出裁非负。三折训练标签1003/1056/1107，全train1583；对应32个全train真0标签保留。B=X62+预测边界量，63列，不含truth availability。三个原seed、400轮depth5能量fit，train权重均值归一，cal仅一个加权ensemble log offset=0.005784322131603524。X、传统和大池f0预测直接复用，不重训或重新forward。

这是开发结果引出的有限随访。X的确定函数不创造传感信息，阳性也不自动晋升。7fit已完整执行，不重复。

## 实测能量与标签结果

以下均为无量纲 log-RMSE 比，括号为复用原500次 sampling-stratum×component 内 incoming 配对bootstrap的条件95%区间；不含source/refit、研究选择、GENIE/FSI或真实系统，也非联合95%。

| 比较 | cal 50–100 GeV | cal 100–200 GeV | test 50–100 GeV | test 100–200 GeV |
|---|---|---|---|---|
| B/X |0.968984 [0.933020,1.000105]|0.925564 [0.868385,0.990655]|0.963769 [0.926541,1.007304]|1.009502 [0.955762,1.065988]|
| B/传统 |1.800384 [1.572553,2.010636]|0.989552 [0.853476,1.175597]|1.322747 [1.140512,1.511036]|0.998977 [0.843160,1.194851]|

cal/test两低箱支持161/163、163/160 incoming；相应B log-RMSE=0.268195/0.197144、0.209074/0.199585。最低箱平均相对bias=+24.424864%/+17.150759%，总tail50=13.043478%/5.521472%。cal第二箱的局部改善未在test共同复现；最低箱对传统依旧明显较差。

全体 B/X：cal 1.005037 [0.993365,1.017703]、test 0.999147 [0.984833,1.013886]。B/f0全体上95=1.149513/1.138522，高于1.01门；高-y总尾差/f0上95=+11.607328/+25.881850 pp。原八层、总/正/负tail50、高端和缺失/status层均在 [metrics](stage133_energy_ml/metrics.tsv)、[paired](stage133_energy_ml/paired.tsv)、[gates](stage133_energy_ml/gates.tsv)。两角色joint均False，promotion=False。1.05仅是非劣效，不代表胜传统。

边界代理 log1p(KE/GeV) RMSE：train source-OOF 0.632736（1583有效标签）、cal 0.638778（618）、test 0.599281（602）；它只描述代理精度，不替代能量收益。见 [代理诊断](stage133_energy_ml/proxy_diagnostics.tsv)。[比较图](stage133_energy_ml/energy_comparisons.svg)及PNG已人工视检，误差棒和标签清楚。

## 验证、执行与成本

科学数组读取、7fit、风险和独立复算全部在HTCondor执行；本地仅源码、紧凑文本及返回包运输检查。命令：

```bash
python3 ml/stage133_submit.py
condor_q 9673919 -af JobStatus RemoteHost HoldReason
condor_history -since 'CompletionDate < 1794075500' -constraint 'ClusterId == 9673919' -limit 1 -json
```

实际worker命令为 `/usr/bin/time -v -o workbook/stage133_energy_ml/analysis_time.txt python -u ml/stage133_analysis.py`，LCG109/el9/gcc15；提交目录 `~/condor/nu_muAnalysis/stage133/`，固定4CPU/12000MB，CPU预算900s，无重试。新步骤先在同worker检查角色/schema/pz及逐列domain，再进入一次冻结fit，不额外消耗小样本fit。

作业9673919.0，1attempt/1start、exit0、失败0；scheduler唯一CPU=26s、execute wall=28s，0GPU，未超预算。GNU进程user+sys=24.77s、wall=22.17s、峰RSS=193796KiB（不是多进程总峰）。4代理fit CPU合计约1.87s，3能量fit合计约8.97s，fit阶段wall=5.226453s；嵌套时间不与scheduler重复相加。该小型CPU树任务的GPU收益未测，不虚构加速比。

[独立验证](stage133_energy_ml/independent_validation.json)重建876个标量，最大差3.552713678800501e−14；模型重载逐值相等，冻结X/f0/传统及bootstrap与Stage131逐数组完全一致。source交叉拟合无训练/预测来源交集，所有代理fit仅role1；62列非法正值域−1、有限sentinel及Inf均0，合法signed值保留。实际源/完整生成家族独立性仍未认证。

提交包2686978B，返回包1657312B；逐成员解压及落盘逐字节回读通过，见 [运输记录](stage133_energy_ml/transfer.json)。这是逻辑运输大小，不是全链物理网络I/O。没有读取事件ROOT，未生产大中间文件；模型/fit矩阵/bootstrap/预测均为ignored紧凑缓存。scheduler证据见 [资源](stage133_energy_ml/resource_summary.json)，精确描述符在 [提交记录](stage133_energy_ml/submission.json)。旧Stage132草稿未执行，已迁至当前编号，Stage132研究正文和历史合同不改写；Stage54五项资产保持。

## 下一步与未完成项

按Stage132 §5.2进入一次独立机制诊断A+K/A：同3002父、同7个availability、相同缺失和权重；新增3固定能量fit、复用A/X/U/F和bootstrap，验收cal/test两低箱的增量和原尾部；不作部署。若支持继续，再补同支持U+z、U+z+K，判断深度互补；不得跨支持相乘收益。

主研究仍需最小observer分退出面/粒子类别/几何接受/相对时间，并核真实hit→DAQ响应；现有聚合缓存无法补出这些字段。μ辐射控制联合响应、有限MC与真实nuisance/背景/接受度后的谱精度、可认证独立确认、外部乳胶匹配锚点均未完成/未测量；不以本阶段阴性关闭新观测，也不以已交计算缩小整体目标。原1.05/1.01/1.03及八层三尾+2pp保持。
