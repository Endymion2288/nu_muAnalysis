# Stage164：真深度与几何未接受能流的条件互补性

## 目标与冻结范围

执行[Stage163冻结合同](stage163_energy_ml/next_execution_contract.json)，沿Stage132§5.2回答：Stage137几何未接受非μ出靶动能H的强oracle增量，是否在真相互作用深度已知后仍存在？H不是绝对不可见能量，更不是Eν−Eμ；有限树模型下条件冗余不等于因果分解或信息界。真z同Stage129：`truth_diagnostics`取first truth neutrino的decay-z，单位mm，不用拟合轨迹z0替代。

Stage134原总K的第二test箱未触发z×K支线，原结论保持。本次触发来自Stage137另一个预定H/A比较：cal两低箱.636260/.718486、test.757378/.701130，四项point≤.95及upper95<1。Stage163固定普通Calo raw4阴性不自动扩大G4、旧X或raw模型网格。

仅同原Stage131的4032父中重新selected3002行，train/cal/test=1708/653/641；原HT逆纳入概率权重、全部K、角色和199个边界缺失NaN保持。原界外/缺失父不从分母删除；不forward原reserved/隔离。A=原X62+7真值可用性、H=原A+log1p(未接受KE/GeV)，两者缓存直接复用，不重训。新AZ=A+真z、AZH=AZ+H，70/71列、原三seed×400轮共6fit，每臂一个原cal global logoffset，不earlystop/扫描/选winner。只作机制oracle，不部署、不晋升。

## 输入、执行和程序修复

输入为`ntuples/energy_ml_stage131/matched_input.npz`、Stage137的`boundary_components.npz`/`fit_matrix.npz`/`bootstrap_draws.npz`及`ml/artifacts/stage137/energy_predictions.npz`；完整路径与语义见[本阶段协议](stage164_energy_ml/protocol.json)，与上一冻结合同逐字相同。

HTCondor目录`~/condor/nu_muAnalysis/stage164/`，4核12GB、最多1job，900累计CPU秒按QA100/analysis600/audit200分配；MaxRuntime86400秒，无应用短超时。所有数组/fit/统计只在Condor，本地仅文本、调度、exact归档及已验证表绘图。不重建Calypso、无ROOT读取/G4/digi/reco/新独立ν，固定小hist BDT不为GPU改变算法。

首QA包遗漏前驱合同JSON，静态检查发现后在IDLE且NumJobStarts=0时撤销9676241.0；补入原JSON，不改变科学政策，实际QA9676262.0退出0。首analysis包的绘图要求H/A，而报表只含四个新比较；同样在IDLE/0starts时撤销9676281.0，补报原缓存H/A供图及独立验证，实际analysis9676286.0退出0。两个修复均在首次新fit/风险前完成，不重训A/H、不追加新臂、不按结果修输入。原提交包和撤销审计保留。

```bash
python3 ml/stage164_ops.py submit --phase qa
# 未启动即撤销，按原100CPU allowance补漏包
python3 ml/stage164_ops.py submit --phase qa_retry
python3 ml/stage164_ops.py collect --phase qa_retry
python3 ml/stage164_ops.py submit --phase analysis
# 首analysis未启动即撤销，保留analysis_unstarted_submission.json
python3 ml/stage164_ops.py submit --phase analysis
python3 ml/stage164_ops.py collect --phase analysis
python3 ml/stage164_ops.py submit --phase audit
python3 ml/stage164_ops.py collect --phase audit
python3 ml/stage164_finalize.py
```

## 精确缓存准入、支持与拟合

[零fit QA](stage164_energy_ml/qa_summary.json)确认3002唯一incoming身份、原角色/pz0>50GeV、A的69列及H列全部精确、原Stage137与131的500draw完全相同、全部z有限、H有效2803/缺失199不变。原X62逐列typed NaN和合法signed规则保持，其他一次方动量不重加；保留raw11、非0status禁timing、Calo缺失、全部原cuts/K/角色。QA内部CPU.547061491秒、wall.681005399秒，无fit。

[实际支持](stage164_energy_ml/cohort_support.tsv)：π/K/charm的train=973/668/67，cal=391/242/20，test=378/246/17，K总1156全部保留；不是原89033全队列的新独立测试。z范围随角色/成分详表，实际全队列最小−2993.548095703125mm、最大−1626.4482421875mm；合法负z不当占位。有效边界不等于所有事件可测H，199缺失仍NaN，合法零不改缺失。

| 保护层 | cal N / ESS | 开发test N / ESS |
|---|---:|---:|
| 真E 50–100 GeV | 161 / 161 | 163 / 163 |
| 真E 100–200 GeV | 163 / 163 | 160 / 160 |
| all | 653 / 321.737701 | 641 / 307.627339 |
| pz0 50–100 GeV | 221 / 147.296419 | 212 / 132.222891 |
| 低pz且真E≥200 GeV | 27 / 26.985970 | 21 / 20.996713 |
| high-y | 35 / 34.765141 | 40 / 39.036141 |
| unconfirmed | 21 / 20.756066 | 18 / 17.088820 |

[原固定拟合记录](stage164_energy_ml/fits.json)：seed2026110255/256/257、400round/depth5/hist/nthread1；训练HT权重归一均值1、加权logE base_score、关闭boost_from_average。AZ三个fit CPU分别2.653521/3.000445/2.307230秒；AZH为2.870275/3.012811/1.636262秒。两个role2 global logoffset为.01309044029179441和.010411863538293924。恰6fit一次，4进程共享父输入，每个fit单线程；6模型reload精确。旧A/H/X/AK/U/F/传统/Stage87预测不变。

## 条件能量实测

以下是无量纲log-RMSE比，括号为原500draw的条件配对95%区间；全部[配对表](stage164_energy_ml/paired.tsv)、[绝对指标](stage164_energy_ml/metrics.tsv)、[原八层门](stage164_energy_ml/gates.tsv)及[图](stage164_energy_ml/energy_comparisons.png)均保存。区间只含原samplingstratum×component incoming重抽样，不含source/refit/GENIE/响应系统/研究选择或同时覆盖，也不是独立确认。

| 比较 | 真E层 | cal | 开发test |
|---|---|---|---|
| AZ/A，单独加真z | 50–100 GeV | .886052 [.841950,.937557] | .941217 [.886604,1.003907] |
| AZ/A | 100–200 GeV | .875976 [.831625,.921818] | .904839 [.851723,.960830] |
| AZH/AZ，已知z后加H | 50–100 GeV | .718646 [.640872,.805974] | .807279 [.701427,.904019] |
| AZH/AZ | 100–200 GeV | .823290 [.713752,.922919] | .770997 [.672326,.862127] |
| AZH/H，已知H后加z | 50–100 GeV | 1.000783 [.989261,1.012827] | 1.003230 [.989521,1.020072] |
| AZH/H | 100–200 GeV | 1.003753 [.988516,1.018921] | .995006 [.979745,1.010951] |
| AZH/A，两者联合 | 50–100 GeV | .636758 [.566972,.717839] | .759824 [.654201,.855934] |
| AZH/A | 100–200 GeV | .721182 [.617945,.830010] | .697628 [.604147,.794423] |

**本固定学习政策中，H给定真z仍有明确双低箱增量，不能把原H效果全归于深度。** 四项AZH/AZ均point≤.95且upper95<1。反方向AZH/H四个低箱区间均含1、下端均大于.95，没有支持已知H后真z再提供5%改善。单独z的最低test区间含1，因此不能把“单独z有效”说成四项均确认。这种条件不对称只限有限模型/HT目标及本支持，不是H物理上包含完整深度、因果分解或理论信息界；H仍不等于实际可读出能量。

all的AZH/AZ cal=.921434 [.867793,.957941]、test=.859563 [.791430,.927396]；AZH/H为1.000932 [.993136,1.006692]及.987342 [.980395,.994850]。后者test全谱约1.27%改善不能替代双低箱标准或据此选部署winner。

## 尾部、传统对照与继续门

[机制验收](stage164_energy_ml/mechanism_summary.json)中低箱5%门True，但尾部门False，故conditional_H_continuation=False。唯一AZH/AZ原八层三尾上端超过+2pp的是开发test pz0∈[50,100)GeV正tail50：点差−2.084095pp，95%区间[−6.281520,+2.123522]pp。该区间未认证安全，不等于证实H使正尾变坏；不能删掉尾例、修改阈值或再扫seed。原低pz真高E仅21test父及high-y40父，也不能据其他负尾改善宣称全尾部已充分支持。

与传统pz0/.8的AZH比较：

| 真E层 | cal比及95%区间 | 开发test比及95%区间 |
|---|---|---|
| 50–100 GeV | 1.182494 [1.033720,1.325595] | 1.000832 [.815305,1.180136] |
| 100–200 GeV | .767016 [.644367,.897984] | .685519 [.553247,.847364] |

第二箱明显改善不代表最低箱非劣通过：最低两项上95均>1.05。AZ/AZH×cal/test的4个原joint全部False。AZH最低箱、cal all/高E、两角色低pz真高E及unconfirmed仍有RMSE或尾保护失败。例：AZH相对Stage87在低pz真高E的负tail上95，cal+7.788034pp、test+8.509243pp；不能用相对AZ的改善遮住原champion保护失败。完整其他层见gates/paired，不笼统写“全部尾部恶化”。

## 独立验证、性能和紧凑留存

[独立审计](stage164_energy_ml/independent_validation.json)通过：原62特征typed域和signed负数、原角色/incoming不重叠、pz0-only、A69/z/H各列、原199NaN及全部旧预测精确；6模型逐一重载推理和独立fsum两个offset通过。对每个非空层逐一重建真实重抽样行列表，独立核算3504项中心风险/区间/三尾，最大绝对差4.973799150320701×10⁻¹⁴。该结果认证程序数值闭合，不认证生成家族独立性、真实探测器系统或最终科学覆盖。图已视觉检查。

[终态资源](stage164_energy_ml/resource_audit.json)：5次提交、3次实际start全部exit0、2次未启动撤销、0live；总52 scheduler CPU秒、61聚合execute wall秒，低于900秒。实际RequestCpus=4/RequestMemory=12000MB；scheduler最大报告RSS175000KiB是采样值，不等于GNU峰值。[GNU](stage164_energy_ml/process_resources.tsv)测得QA .88CPU秒/1.32wall秒/46764KiB、analysis19.73CPU秒/11.62wall秒/173648KiB、audit26.55CPU秒/28.60wall秒/185116KiB。6fit内部CPU和父进程/绘图/验证为嵌套计时，不与scheduler重复相加；169%是本次analysis进程组的GNU平均CPU利用，未做受控串行加速测试。ROOT请求字节未测量，因为本阶段不读ROOT；0GPU/G4/digi/reco/新独立ν。

[精确清理](stage164_energy_ml/storage_cleanup.json)：使用中的源码/配置版本、worker、descriptor、GNU和日志逐字节读回归档在`software/stage164/`，旧事件/模型输入仅与传输包逐字节核对，不在源码档案复制。最终fit_matrix/bootstrap/6模型/预测合5578139B<32MiB；删除41784036B重复运输/计时/日志/spool副本，当前stage164提交目录仅留紧凑execution_index。清理前查当前队列Iwd无引用；不删其他项目、不持久ROOT/xAOD，Stage54十二文件size/mtime保持。没有SHA或重新读取大ROOT。阶段静态AST/bash、合同原字节、文档链接、旧历史原文保持和diff检查另记[文档验证](stage164_energy_ml/document_validation.json)。

## 阶段结论与下一步

本阶段回答了已冻结的深度机制问题：**H给定真z仍有双低箱增量；给定H后再加z的双低箱5%增量未获支持。** 但条件H尾部安全和原联合门失败，既不是部署候选，也不触发同类G4/模型/代理扩大。最低箱对传统仍未通过非劣；Stage87及原全部门保持，整体低能优越性和真实物理精度未完成。

下一[Stage165零fit合同](stage164_energy_ml/next_execution_contract.json)直接承接Stage132§4.2/5.3的来源依赖问题：仅同原3002和固定AZH/AZ、AZH/H、H/A预测，按预定π/K/charm及原manifest nominal/alternative两组边际划分，报告两低箱/all/低pz/低pz真高E/high-y的N/ESS、RMSE/三尾和原500draw条件区间。先核source到Stage130原manifest的component映射，空组/稀疏区间如实保留，不挑有利源、不造来源混合prior、不改阈值/重训/forward；600累计CPU秒，4核12GB、无ROOT/G4/新父。验收为旧inclusive结果精确、全部预定分组完整且独立标量/行空间数值闭合、实际成本与紧凑存储；无论分组如何都不自动扩大生产。这可判断inclusive收益是否依赖组成，不能认证domain transfer、材料因果或H可测性。

真实data联合纯度/增益/时基/轨迹covariance与宽能区辐射尾校准、乳胶锚点、GRL曝光/背景/全生成接受度、真实相关辅助系统和独立确认继续缺失；不重复Stage136/140已完成的有限MC toys，也不用任意prior补缺。后续实际探测器研究仍需新的物理观测和输入专属有界合同，不能靠本轮oracle替代。
