# Stage140：完成原3000个稀疏有限MC轮廓覆盖实验

## 目标、冻结输入与数值方案

完成Stage139因EM边界优化失败而未认证的原实验，统计问题不变：10811个role2 incoming代理各取第一view，七真E箱整数MC为182/899/2342/3522/2742/1020/104；role3参考selected E<200 GeV份额ψ=0.08527835051546391，Nselected=1000。traditional9/direct62_9/联合direct9×pz0四箱，七自由真份额及非负逐行响应simplex，零MC格允许正概率。仍为`Σd log(fq)+Σm log(q)`，无统计伪计数或虚构系统prior。不是已认证独立GENIE家族，与Stage136家族平均响应不同。

继承[Stage139协议](stage139_energy_ml/coverage_protocol.json)，保留三表示×nominal/人为empty-cell stress×500toy=3000、原seed202611071390（stress加100）、先MC后数据的抽样顺序及LR阈值3.841458820694124。不删失败toy，不按coverage改bin/估计器/先验。stress各表示单独向零格分配min(.05,3/n_t)质量，非真实同一物理shift或校准系统置信集，不能横向当物理迁移比较。

[18例成本协议](stage140_energy_ml/pilot_protocol.json)预定三表示×两场景×toy index0/150/487。EM只作100步warmstart，reference/uniform各做解析梯度SLSQP，再总从最佳受限解重启自由解。MC>0格10⁻¹⁴仅为数值下界，零MC格不加prior。所有调用要求成功、约束残差<10⁻⁷、自由LL≥受限LL−10⁻⁵；记录所有初值差，多个起点不等于理论全局最优证明。

pilot 18例通过，科学CPU121.617043735秒、wall44.194951807秒；原失败direct stress150 LR=.219830842008，与Stage139长EM+梯度修复差约2.03×10⁻⁹。实测每toy平均传统.478942/direct.510330/联合19.280235 CPU秒，投影全toy20269.507289 CPU秒，仅作投影。随后[正式协议](stage140_energy_ml/protocol.json)冻结45000 CPU秒预算、60批×50toy，每批8进程，最多12批物化；另6个独立Asimov轮廓job。逐toy持久化，数值汇总失败不需重新拟合已完成toy。

## 执行与验证

```bash
python3 ml/stage140_submit_pilot.py
python3 ml/stage140_submit.py batch
python3 ml/stage140_submit.py profile
python3 ml/stage140_monitor.py
python3 ml/stage140_submit.py summary
```

HTCondor目录`~/condor/nu_muAnalysis/stage140/`，LCG_109、单线程BLAS。pilot9674130.0、toy9674142.0–59、profile9674143.0–5、summary9674163.0。批量8 CPU/12 GB（实际站点可能按核上调内存），profile/summary1 CPU；没有应用短超时，没有GPU加速假设。零新回归fit/forward/G4/ν父/reserved/role4/隔离读取；原K/pz0/raw11/status/typed NaN/signed/Calo缺失/选择及单事例门全部保持。

[完整结果范围](stage140_energy_ml/coverage_scope.json)：3000例索引完整、没有失败删例，所有约束通过。36项预定长EM100000步+双初值梯度及受限解自由重启交叉检查，最大LL差1.295771654×10⁻⁶，低于.001；18个pilot的LR与正式逐值完全相同。独立检查还复核逐例自由/受限LL与LR/covered一致、各组500唯一索引及Asimov已知最大值。详见[数值验证表](stage140_energy_ml/independent_validation.tsv)。这检验了具体数值路径，不认证任意case全局最优。

## 点覆盖及精度结果

所有数值均来自完整正式计算，[完整六组表](stage140_energy_ml/coverage_summary.tsv)、[3000逐例标量](stage140_energy_ml/all_toys.tsv)、[轮廓及覆盖图](stage140_energy_ml/finite_MC_profiles_coverage.png)。Wilson为各组500toy的边际95%区间，不是多个表示联合认证；在95%附近MC标准误约0.975个百分点。

| 表示 | 场景 | 覆盖数/500 | 覆盖率及Wilson95% | ψ bias / RMS（pp） | Asimov 95%宽度（pp） |
|---|---|---|---|---|---:|
| 传统 | nominal | 482 | 96.4% [94.3816%,97.7109%] | +.002584 / 1.443948 | 5.846968 |
| direct62 | nominal | 476 | 95.2% [92.9573%,96.7535%] | −.060166 / 1.260374 | 4.859313 |
| 联合 | nominal | 467 | 93.4% [90.8761%,95.2621%] | −.001872 / 1.188163 | 4.466929 |
| 传统 | 人为stress | 484 | 96.8% [94.8655%,98.0208%] | +.007611 / 1.483085 | 5.866842 |
| direct62 | 人为stress | 476 | 95.2% [92.9573%,96.7535%] | −.046075 / 1.254250 | 4.881199 |
| 联合 | 人为stress | 466 | 93.2% [90.6479%,95.0933%] | −.091071 / 1.203941 | 4.481373 |

nominal Asimov区间为传统[5.722777838%,11.569745580%]、direct[6.276394190%,11.135707678%]、联合[6.423380514%,10.890309712%]，中心真份额约8.527835052%。这是一份固定Asimov的轮廓，不是toy区间平均宽度，也不是一个标准差。有限MC条件下direct相对传统的条件谱精度收益仍在；联合更窄，但覆盖点估计偏低，**不能认证其95%覆盖或完整物理精度**。各Wilson包含.95不等于等效或充分覆盖证明；没有调高阈值掩盖这一不确定度。

正式最大初值LL差传统nominal2.4374×10⁻⁶、direct .222483175、联合2.569292348；stress direct .948907641、联合1.903954216。均使用最高目标值而非平均；受限解自由重启最大改善stress direct .150996400、联合 .245771621。此记录表明数值边界问题确实需要处理，不能仅看原EM停止标志。正式最大simplex残差≤7.383×10⁻¹³。

## 成本、存储与阶段结论

[scheduler账](stage140_energy_ml/scheduler_accounting.json)：68job/68starts，全部exit0，无失败，共14802 CPU秒、2851聚合execute wall秒、0GPU，低于45000 CPU秒预算。逐toy科学CPU14063.692136秒、轮廓524.507484秒，pilot另121.617044秒；这些嵌套计时不重复加到scheduler。完整GNU峰RSS108776 KiB（summary；66个正式toy/profile任务最大76192 KiB）。Stage139此前1448 CPU秒及两次失败保留在其独立账，不隐藏或重计为本阶段成本。

检查队列全终态后，逐toy JSON所有标量与合并TSV逐类型完全回读一致，六份profile与合并JSON在去除三个新增审计字段后原字典一致；保留全部逐例/轮廓、批次计时及紧凑提交记录，删66份重复结果archive共446290 B，完整原manifest在ignored共享gzip。未保存任何大ROOT/xAOD或新增训练缓存。图已视觉检查；AST/shell、阶段链接和`git diff --check`通过后本地Conventional Commit，不push。

本阶段完成原有限MC的**冻结参数点工作模型实验**，不再把Stage139部分输出当覆盖结果。尚未测量uniform覆盖、实际data/真实相关gain/timing/材料/GENIE/FSI/flux辅助约束、背景/全生成接受度及独立确认；没有任意强prior。模型排序的条件精度不能取消50–100 GeV单事例目标，原1.05仅非劣效、1.01/1.03与八层三尾+2pp保持，Stage87direct62不变，整体目标未完成。

下一步将本结果与Stage137几何机制、Stage138/141实际DAQ控制合并制定有限后续：不再开旧X网络或追加同点toy/阈值网格，优先需要真实外部约束的响应/逃逸敏感性；任何新物理nuisance须列可用变体和辅助样本、相关结构及校准范围，不能将人为empty-cell stress冒充实测系统。验收为同selected定义的可追溯响应/辅助似然及剩余非识别方向；真实乳胶匹配、曝光/GRL/背景、全生成接受度或新独立家族缺失时如实保留缺口，不打开保留集。
