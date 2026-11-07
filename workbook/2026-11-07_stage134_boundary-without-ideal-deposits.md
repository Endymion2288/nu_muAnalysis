# Stage134：没有理想沉积时，边界动能是否仍有增量

## 目标与结论

按Stage132 §5.2，补一个A+K/A机制对照；不将Stage131的F/U结果直接当答案。**最低箱增量在不提供五项理想沉积时仍然明显：cal/test AK/A=0.687973/0.704447；但test第二箱上95=1.036741，未过事前固定的双箱5%继续标准。** 因此不自动追加z×K oracle臂，下一主投入为Stage132要求的能流可测成分与DAQ对应。不是认定深度无用、总K不可测或信息已饱和。AK是truth机制臂，不可部署；原joint两项均False，保留Stage87 direct62。

## 输入、模型和统计

同Stage131完整3002行matched_input，train/cal/开发test=1708/653/641。A为原X62+7个真值可用性，AK只加原先的`log1p(非μ非ν首次出实际EmulsionStationA包络KE/GeV)`，70维；不含五项固定窗理想沉积。199例K缺失照旧NaN并保留父/预测，availability与A完全相同，不按oracle可用删分母。K包含中性与所有方向，既不是H也不是探测器可见能量。

冻结合同在 [protocol](stage134_energy_ml/protocol.json)，在新风险前保存；3个原seed、400轮depth5、均值1训练逆纳入概率权重，cal仅一个全局加权log offset=0.004498783802890511。只新增3fit，直接复用A/X/U/F/f0/传统与原500draw；无新G4/新ν，未重训reference，未打开reserved/role4/隔离，全部K/角色/原pz>50 GeV和正式cuts保持。pz0唯一一次方动量、raw11/typedNaN/合法signed/Calo缺失保持，无新增timing。

继续标准预先定为AK/A在cal/test两个低箱均point≤.95且上95<1；未满足则不扩大同类oracle网格。所有结果为历史selected框fresh/reselected的开发条件风险，不是新blind、生成接受度、因果或Bayes信息分解。区间仅固定模型、sampling-stratum×component内incoming配对，未含source/refit/GENIE/真实系统/研究选择与联合覆盖。

## 详细实测

无量纲log-RMSE比与条件95%区间：

|比较|cal 50–100 GeV|cal 100–200 GeV|test 50–100 GeV|test 100–200 GeV|
|---|---|---|---|---|
|AK/A|0.687973 [0.617206,0.759322]|0.812632 [0.715852,0.924369]|0.704447 [0.635589,0.779231]|0.905402 [0.777200,1.036741]|
|F/U（原结果复用）|0.703812 [0.636507,0.772896]|0.885643 [0.792215,0.986080]|0.706057 [0.632191,0.786692]|0.880740 [0.766331,0.994613]|
|AK/传统|1.277603 [1.120170,1.438621]|0.864278 [0.748673,1.008007]|0.927890 [0.788722,1.084892]|0.889686 [0.702802,1.065735]|

两低箱cal/test支持161/163和163/160。A/X同时报告于[paired](stage134_energy_ml/paired.tsv)，没有把availability的作用归给K。最低箱改善不需要先有这五项理想沉积，但它仍条件于truth availability；不能进一步外推X-only部署、真实测量或完整物理能量闭合。

AK/A全体cal 0.940107 [0.887847,0.981998]、test 0.959612 [0.913870,1.010036]。high-y cal/test=0.874218 [0.753916,0.974944]、0.904420 [0.832697,0.983808]；对应总tail差上95=+7.019283/+4.007115 pp，负tail上95=+8.325282/+2.004323 pp。点值方向有利仍不足尾部认证。AK/f0全体上95=1.096936/1.093261，未过1.01；最低箱/传统上95=1.438621/1.084892，未过1.05，不能称胜传统。

原八层与三向tail、bias、R68、缺失/status和高端见[metrics](stage134_energy_ml/metrics.tsv)、[gates](stage134_energy_ml/gates.tsv)、[support](stage134_energy_ml/support.tsv)。[比较图](stage134_energy_ml/energy_comparisons.svg)和PNG已人工视检；不同支持上的百分比不相乘，没有按最优点值选择部署。

## 执行、验证与资源

命令为`python3 ml/stage134_submit.py`，worker执行`/usr/bin/time -v ... python -u ml/stage134_analysis.py`。全部科学读取/拟合/统计在HTCondor，目录`~/condor/nu_muAnalysis/stage134/`，4CPU/12000MB，CPU预算900s，LCG109/el9/gcc15。原3fit规模已由Stage133实测验证，无额外重复fit。

作业9673926.0，1attempt/1start、exit0、0失败，scheduler唯一CPU25s、execute wall30s、0GPU。GNUuser+sys24.46s、wall23.26s、单进程峰RSS204664KiB；3fit各CPU2.791877/2.298776/2.034091s，fit阶段wall2.978501s。嵌套时间不重复相加；GPU加速未测。

[独立验证](stage134_energy_ml/independent_validation.json)1460标量最大差4.973799150320701e−14，模型重载预测逐值相等，A/X/U/F/f0/传统和500draw与原数组一致。AK前62列、availability7、K列分别与原输入逐数组相等；有限sentinel/正域非法−1/Inf均0，合法signed保留。程序原因检查未见身份、输入顺序或数值不闭合，不能据此排除未测物理系统。

精确提交/资源和逻辑运输大小见[submission](stage134_energy_ml/submission.json)、[资源](stage134_energy_ml/resource_summary.json)、[transfer](stage134_energy_ml/transfer.json)。返回包逐成员长度与落盘逐字节回读通过，没有ROOT输出或新事件大缓存；ROOT读取字节为0，无新全链成本。没有重跑Stage129–131，Stage54五资产保持；先中文报告再本地Conventional Commit，不push。

## 下一步与未测量项

Stage135按Stage132 §5.3–5.4先新增最小observer小pilot：固定自然train父、原seed及原cuts，不看能量风险筛分量；分首次退出面、带电强子/EM/中性强子/其他、下游实际敏感体几何射线接受、位置方向和相对事件时间。核分类能量求和、去重及observer on/off非干涉；对DAQ通道/响应核/采样基准/有限积分窗给出实测闭合与实际CPU/I/O，然后才冻结正式量及能量对照。保持出生在靶外父和缺失原因分母，不能将几何接受直接叫探测效率。

z×K为未执行的条件支线，本次固定双箱继续门失败，不以它阻挡主研究。μ辐射控制联合响应、完整真实nuisance/有限MC/背景接受度的谱精度及认证独立确认仍未完成；外部乳胶锚点没有真实匹配输入。各项在[Stage132执行清单](stage132_energy_ml/execution_tracking.tsv)持续跟踪，整体goal未完成。1.05仅非劣效，原1.05/1.01/1.03与八层三尾+2pp保持。
