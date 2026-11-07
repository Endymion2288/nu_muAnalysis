# Stage136：有限响应MC后的选中能谱精度（与Stage135并行）

## 阶段目标与结论

执行Stage132 §6明确允许并行的物理精度线，在既有低维响应模型上加入**实际测得的有限MC模板统计协方差**，并比较相关的Ehat与pz0联合观测；不重复把已知响应Fisher当新成果，不引入虚构的探测器/flux prior，也不训练SBI。

在Nselected=1000、七个真E份额自由、当前selected MC响应和局部渐近近似下，E<200 GeV份额标准差：传统 **1.490009 pp**、direct62 **1.235155 pp**、(direct62,pz0)联合 **1.139170 pp**。有限MC统计没有消除当前条件收益；联合量的相关性已在同一响应矩阵中处理，没有当独立测量重复相乘。**这是条件信息计算，不是完整data测量、覆盖率认证或最低能单事例成功。** 零MC格导致非正则边界风险，真实相关系统、接受度、背景和独立确认仍缺。

## 输入与冻结定义

[protocol](stage136_energy_ml/protocol.json)在新计算前冻结。输入为`ntuples/energy_ml_stage119/old_input.npz`和`ml/artifacts/stage129/depth_predictions.npz`中的原冻结traditional/direct_cal两列，不使用Z真z预测。原角色、全部K/pz0/raw11/typedNaN/合法signed/Calo缺失/原正式cuts不变；不训练、重载模型或新forward，reserved/role4/隔离零预测。

role2响应11612行、10811个精确incoming代理；role3参考混合13189行。重复view在incoming簇内按1/重复数权重，沿原存储float64精度作身份比较；不是完整GENIE家族认证。七真E箱边界50/100/200/400/800/1600/3200/∞ GeV；传统和direct能量观测边界0/50/100/200/400/800/1600/3200/6400/∞ GeV。联合为同direct9箱×pz0边界50/100/200/400/∞ GeV的4箱，事前固定，不看test选分箱。

参考混合E<200份额0.08527835051546391，条件于已选样本；不是全生成谱、data测得份额或全接受度。保持七份额simplex六个自由方向，未将两大类内部谱固定来人工提高精度。

## 有限MC方法与验证边界

每个真E箱j中，以incoming家族的归一化观测贡献向量C测响应Rj及其均值的簇协方差Cov(Rj)。同家族view相关保留；不同incoming簇的独立性只作为当前代理假设。概率向量q=φR，数据多项式协方差为`[diag(q)−qqᵀ]/1000`，有限模板贡献为`Σφj² Cov(Rj)`。删去一个观测概率坐标后，以完整协方差计算六个份额的有效局部信息，所报E<200标准差对其余自由份额共同profile。

另用显式模板辅助协方差的Schur补独立验证，和协方差求和实现的最大绝对信息矩阵差1.355147105641663e−10，数值容差通过；不是设置任意强物理prior。七个真E层内各500次incoming多项式重抽样，三种表示共用同序列；模板q协方差trace/bootstrap对解析比为传统1.075059、direct1.027782、联合0.995329。500draw本身有Monte Carlo波动，这不是coverage检验。

簇数各真E箱182/899/2342/3522/2742/1020/104。样本中未见的格没有加伪计数或假定概率；局部经验协方差对零格不给非零变化。联合最低箱32/36格为空，最高箱28/36为空；全混合有18个非零观测格。很多零格来自选择/运动学，但不能证明所有零格为结构零。这限制局部高斯/渐近解释，**区间实际覆盖和稀疏边界的有限样本轮廓仍未测量**，不得称最终误差。

## 详细数据

|观测|已知响应σ(E<200份额)，pp|加入有限MC后σ，pp|已知/有限MC信息秩|有限MC条件数|
|---|---:|---:|---|---:|
|传统pz0/0.8|1.452039559|1.490009273|6/6|139.031785|
|direct62 Ehat|1.212660546|1.235154684|6/6|141.780775|
|joint(Ehat,pz0)|1.122092183|1.139170198|6/6|122.993726|

前两项已知响应值与Stage129 [原表](stage129_energy_ml/spectrum_precision.tsv)在浮点舍入内一致，是实现控制而非新发现；新结果是有限模板统计和预定联合观测。全表见[precision](stage136_energy_ml/precision.tsv)，逐真E箱/空格/簇数见[response_support](stage136_energy_ml/response_support.tsv)，局部作用范围见[scope](stage136_energy_ml/scope.json)。没有能量模型晋升、对真实响应变体作无依据1σ解释、或把谱收益替代单事例两低箱目标。

## 执行、资源与产物

科学读取/协方差/500draw/数值验证全部HTCondor；本地仅源码、返回包运输和紧凑表读取。实际命令：

```bash
python3 ml/stage136_submit.py
# worker: /usr/bin/time -v -o workbook/stage136_energy_ml/analysis_time.txt python -u ml/stage136_analysis.py
condor_history -since 'CompletionDate < 1794075500' -constraint 'ClusterId == 9673962' -limit 1 -json
```

作业9673962.0，目录`~/condor/nu_muAnalysis/stage136/`，4CPU/12000MB，固定CPU预算1800s，无重试；1attempt/1start、exit0、失败0。scheduler唯一CPU3s、execute wall8s、0GPU；GNU user+sys2.45s、wall2.95s、峰RSS154436KiB。科学主函数CPU2.120590s/wall2.278168s。嵌套时间不重复累计，GPU收益未测。资源/描述符见[资源](stage136_energy_ml/resource_summary.json)、[submission](stage136_energy_ml/submission.json)。

返回成员长度和落盘逐字节回读通过，逻辑运输大小见[transfer](stage136_energy_ml/transfer.json)；紧凑ignored证据`ntuples/energy_ml_stage136/response_evidence.npz`保存响应、家族协方差及500个q重抽样，未保存家族逐hit或ROOT，ROOT输入读取0B。模板数组由NPZ读取，不能将压缩包大小冒称物理网络I/O。Stage54历史五资产保持；先中文报告再本地Conventional Commit，不push。

## 后续及整体目标

本阶段只补有限响应MC和少量相关联合维度。下一需在同一低维模型中认证稀疏模板的有限样本轮廓/覆盖，并随真实输入加入run/channel gain/timing、材料、GENIE/FSI/flux的相关约束及同选择背景/接受度。现有Muon GRL的存在不等于ν正式曝光和背景模板已齐，不能编造辅助协方差。

主线Stage135仍独立推进实际边界分解pilot，随后才按新标签与测量对应决定规模；外部乳胶匹配和独立确认家族无认证输入，原reserved不打开。整体goal未完成，原单事例1.05/1.01/1.03与八层三尾+2pp不变，1.05仅非劣效。
