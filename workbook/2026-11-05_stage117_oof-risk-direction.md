# Stage117：真实OOF与分层风险方向的四臂实验

## 1. 阶段目标与结论

执行用户按最新路线继续工作的请求，落实[Stage116](2026-11-05_stage116_research-strategy-and-observability.md)§4/§9的缓存工作包A：训练内/真实OOF残差 × 普通/分层风险树方向。四臂使用同110维读出、同容量上限、同保护头和最终Stage87强BDT锚定。另交付同split、同BDT政策的固定μ-only归因对照。协议在作业前冻结于[protocol.json](stage117_energy_ml/protocol.json)，起点`5a811e7`。

**四臂已实际完成；共同验收全部失败，不推广。** 预定OOF_stratified在developed test最低箱log-RMSE从direct的0.282644降至0.246473，配对比0.872026 [0.839350,0.897017]，但仍远弱于传统0.145661；第二箱从0.246329升至0.252963，总体从0.287491升至0.290225，困难层尾率保护失败。cal_post两低能最坏比OOF_stratified/direct为1.022398 [0.999284,1.047816]；相对OOF_ordinary为1.016797 [0.992371,1.046633]，主比较失败。

这次确实补上了OOF与方向发现的实现缺口，也发现低能方向可以改变，但没有得到两个低能与保护层的共同收益。结束本固定方法预算；不能把阴性结果解释成状态完全无信息、所有风险学习失效或物理目标不可达，也不继续树/seed/温度/惩罚网格。

## 2. 样本、变量与真实分折

完整保留Stage87：89033兼容记录、17657隔离；active71376，train/cal/test分别46575/11612/13189，incoming分别37556/10811/12125；全部1016新增K保持。无新ROOT、模拟、重建、事件cut或角色更换。原pz0>50 GeV，一次方动量只用pz0，允许px/py、q/p、弯折；11路raw电荷、signed reduced、status、typed NaN及Calo缺失规则保持，没有拟合电荷回退或通用负数删除。原62缺项train/cal/test为21/6/5，status全部已知；困难事件照常预测。

输入为`ntuples/energy_ml_stage94/{evaluation_input,cal_partition}.npz`、Stage87的`split.npz`及`ml/artifacts/stage87/predictions.npz`，以Stage55+56、70、81、82、83缓存按origin/origin_row恢复原62和11路status，核incoming/run/event/group与truth。四臂全部用62+三共同flag+status availability+11×4状态位=110维。[身份验证](stage117_energy_ml/input_validation.json)、[状态覆盖](stage117_energy_ml/state_coverage.tsv)。

原train只有3个来源/incoming连通块，不据此直接宣布无法OOF。事前固定seed2026110517，按charm/k/pi分别将排序来源组打乱后轮流分3折；每折留出完整来源组，并从训练侧清除所有与留出侧incoming相同的记录。每个训练/评价子集重新按incoming赋视图总权重1，最终外层权重保持原值。

| 折 | 留出记录 | 清除incoming后的训练记录 | 训练最低/第二低能记录 |
|---|---:|---:|---:|
| outer0 | 14749 | 27212 | 605 / 2853 |
| outer1 | 15581 | 26470 | 644 / 2739 |
| outer2 | 16245 | 25579 | 615 / 2693 |

91个来源组全部分配，46575条train全部获得真正留出预测，不把被清除的训练视图从最终样本删除。outer0作为训练内部开发集；其purged训练侧27212条为发现集，再按原fold1/2作嵌套OOF，实际inner1/2训练12187/11667、验证13345/13867。嵌套模型也不见outer0来源或incoming。每个pair两侧均满足事前总体≥30个最低箱、≥100个第二箱、每component≥100 incoming及≥1来源条件。[完整支持表](stage117_energy_ml/fold_support.tsv)、[来源分折](stage117_energy_ml/source_folds.tsv)、[分折审计](stage117_energy_ml/fold_audit.json)。

这里只能认证canonical source与exact native incoming proxy隔离；没有新生成parent UUID或完整重放谱系，不能声称恢复了未记录的生成家族身份。最低箱charm在各留出侧仅1/1/2条，不能作来源/分量外推或独立确认。

## 3. 实际模型、开发与方向梯度

匹配Stage87 baseline：原62维、三seed2026110255/56/57、400轮、depth5、eta.04、subsample.8、min_child_weight20、λ10、hist、nthread1，base_score为相应训练侧加权mean logE，boost_from_average=0。五个fold训练集各拟合三模型，共15次真实折模型fit；外加μ-only三模型，共18次。fold offset仅为其训练侧ensemble平均残差；无cal/test流入。完整训练内分支用保存的direct_raw及train-only offset0.0000583326214；原最终direct_cal的cal offset为0.0251936905960，仅保留作最终部署锚定。[18次fit证据及参数](stage117_energy_ml/baseline_fits.json)。

四臂的字典均最多8棵depth3、min_child_weight200、eta.04、λ10、subsample.8、固定seed2026110517，初始修正0。普通臂按incoming权重拟合平方残差。分层臂每轮使用

`smoothmax_T=.1(两个低能MSE/传统MSE) + 10 Σ positive(归一化保护风险−限额)²`，

其中保护包括6层MSE及8层正/负平方hinge。每轮重算全部组梯度，因而保护参与分裂发现；采用正的对角曲率近似，忽略组乘子的非局部Hessian项，梯度/曲率共同归一化至incoming总权重。不是FairGBM原分类公平算法，也不宣称该近似提供硬尾率保证。[方向实现](../ml/stage117_head.py)；逐轮组风险、乘子、L1梯度以及逐split的feature/gain/cover均保留于`stage117_energy_ml/*_direction_gradients.tsv`、`*_splits.tsv`。

叶指示变量经训练加权Gram正交化，沿用Stage115同一凸头：主解最小化两个低能MSE/传统的最大值，保护all/direct≤1.01、其余5层≤1.03及8层正/负平方hinge不增；次解在τ≤主τ+1e−8下最小化修正平方。每解SLSQP最多250次，ftol1e−10；有限可行解需最大归一化违反≤1e−7。共8个开发容量候选+4个最终头，24次解，无重试。

每臂只在outer0内部开发集比较4/8树。先最小化6层MSE和24个实际尾率相对事前保护的最大正违反，再比较两低能最坏RMSE/传统，最后少树优先。四臂均选择4树；8树虽然各自降低内部开发低能最大比，却更损保护。[8个候选经验前沿](stage117_energy_ml/development_frontier.tsv)。分层臂选出的4树也有非零开发保护违反（IS .004279881、OOF .003850470），完整报告，不声称内部开发通过保护。锁容量后在全train重拟合；全部头持久化锁定后才新作cal/test前向和风险计算，无外层选臂、调offset或阈值。

| 臂 | 最终树 / 叶 / rank | 训练主τ（MSE/传统） | 主/次迭代 | 次解近似KKT∞ |
|---|---|---:|---|---:|
| IS_ordinary | 4 / 29 / 26 | 2.147861 | 54 / 111 | 1.588551e−5 |
| IS_stratified | 4 / 31 / 27 | 1.743158 | 93 / 84 | 3.285681e−6 |
| OOF_ordinary | 4 / 19 / 16 | 2.987402 | 54 / 49 | 3.768633e−4 |
| OOF_stratified | 4 / 30 / 27 | 2.451949 | 75 / 130 | 9.587637e−6 |

四个最终主/次解全部success；24次总计23次success。未选中的IS_stratified_dev8主解success=False、147次、违反1.404453e−9、KKT∞3.214024e−7，按事前有限可行规则继续原次解与报告，没有换solver。该解终止message/status码未保存，具体终止文案**未测量/未保留**，不能猜作某个确定数值故障。全部解最大违反1.404453e−9，最大近似KKT∞.004740964；没有严格dual下界或全局最优认证。[臂摘要](stage117_energy_ml/arm_summary.tsv)、各`*_solve.json`保留近似乘子及活跃约束。

分层方向初始几乎由最低箱驱动：IS低能乘子.999998794/1.205733e−6，OOF为.999999995/5.365330e−9；到第4轮，OOF的第二箱正/负hinge乘子.339320/.642533，E200+正尾1.196076、低pz真高E负尾.594460已参与方向。最终两分层头最低箱与all保护活跃，第二低能epigraph不活跃。说明当前目标仍主要压最低箱，并未自动同时改善第二箱，不能只看优化器success。

选中四树的split数为25/27/15/26；其中状态位split数为1/0/0/0，唯一为IS_ordinary的f76，即Veto10 fit_failure。该事实只描述这四个字典，不能证明状态在其他条件下无信息。

## 4. 留出风险、实际尾与校准

所有log-RMSE为无量纲自然对数能量误差；能量单位GeV。下表是同一完整developed test，固定四臂结果均报告，不事后选赢家。[cal_post/test完整有限候选前沿](stage117_energy_ml/heldout_frontier.tsv)、[全部风险与幅度](stage117_energy_ml/metrics.tsv)、[配对区间](stage117_energy_ml/paired.tsv)、[图](stage117_energy_ml/four_arm_risks.svg)。

| 模型 | 真50–100 | 真100–200 | all | pz50–100且真E≥200 | high-y |
|---|---:|---:|---:|---:|---:|
| traditional | .145661 | .247937 | .557190 | 1.887790 | 1.618799 |
| direct_cal | .282644 | .246329 | .287491 | .658177 | .609395 |
| μ-only | .784898 | .383917 | .423401 | 1.235100 | 1.216258 |
| IS_ordinary | .280318 | .244690 | .290750 | .663776 | .610481 |
| IS_stratified | .265717 | .253870 | .290517 | .671247 | .620073 |
| OOF_ordinary | .282596 | .245363 | .292579 | .657968 | .607901 |
| OOF_stratified | .246473 | .252963 | .290225 | .656851 | .609792 |

μ-only用原前14个轨迹/几何特征加q/p0、q/p1、bend x/y共18维，无计数、电荷或Calo；三seed、400轮、原train/权重/参数及一次full-cal mean offset均与direct政策相同。μ-only先锁模型再校准，不参与四臂选模。[特征与fit](stage117_energy_ml/baseline_fits.json)、[calibration](stage117_energy_ml/mu_calibration.json)。这支持额外非μ读出在本匹配学习政策下对总体/困难组有价值；μ-only不是最优μ信息界，其全局MSE学习也会受训练谱先验影响，不能替代传统低能基准。

主统计为cal_post每个draw中两个低能RMSE比的最大值，原500个component内incoming多项式重抽样，cal/post seed2026110389、test2026110390；所有主统计500draw有效。四臂/direct分别为：

| 臂 | 点估计 | 条件95%区间 |
|---|---:|---|
| IS_ordinary | .993957 | [.985791,1.004277] |
| IS_stratified | 1.027179 | [1.006083,1.052245] |
| OOF_ordinary | 1.005508 | [.994871,1.020584] |
| OOF_stratified | 1.022398 | [.999284,1.047816] |

同源内分层/普通：IS为1.033424 [1.007187,1.063829]，OOF为1.016797 [.992371,1.046633]；同方向OOF/IS：普通1.011622 [1.002849,1.032567]、分层.995345 [.963587,1.031818]。均无预定共同改善证据。[8个主/因子对照](stage117_energy_ml/primary.tsv)。这些是固定候选有限经验风险，既非全函数空间前沿，也非统计信息下界。

预定OOF_stratified在test的两低能/传统比上95分别2.029808、1.096984，均失败；all/direct上95=1.012629>1.01。其余五层MSE相对direct上95均≤1.03，但下列实际尾保护失败：

| 层 | total尾差上95 / pp | positive / pp | negative / pp |
|---|---:|---:|---:|
| pz50–100 | +2.874605 | +2.034536 | +1.574496 |
| pz50–100且真E≥200 | +4.320406 | +3.028187 | +2.733402 |
| high-y | +3.958741 | +2.222955 | +2.633746 |
| unconfirmed | +2.579368 | +2.260014 | +1.190658 |

原八层、每层总/正/负tail50差上95≤+2pp要求不变，[32行完整门槛](stage117_energy_ml/gates.tsv)四臂joint均False。最低箱OOF_stratified总尾率13.114754%→10.382514%，最低箱median bias+19.882536%→+14.277849%、p95绝对相对误差81.571914%→72.648535%，仍有明显过估；第二箱R68从17.188604%升至18.209445%，p95从62.531664%升至63.078790%。[预测能量固定分箱校准](stage117_energy_ml/calibration.tsv)另报mean预测/真E及mean log error，无额外校准优化。不能以训练平方hinge不增代替留出实际尾率。

## 5. OOF到完整基线的分布变化与解释边界

实际训练端基线风险如下，[完整表](stage117_energy_ml/residual_source_risks.tsv)：

| 残差源基线 | 最低箱log-RMSE | 第二箱 | all | 低pz真高E |
|---|---:|---:|---:|---:|
| IS，train-only offset | .220469 | .211087 | .239280 | .523896 |
| 真OOF，fold-train-only offset | .255522 | .236992 | .267426 | .634632 |
| 最终全train direct_cal锚定 | .238537 | .224653 | .240597 | .513352 |

OOF的残差确实更大；来源留出、incoming purging和折模型训练规模同时变化，不能把差值全部归为基线过拟合。最终部署基线使用全train强BDT及原cal offset，明显不同于OOF折模型。完整外层管道已实际评价，上述四臂结果包含这种迁移；OOF不自动消除它。IS与OOF都用各自train-side offset而非cal offset拟合头，这一共同政策变化也意味着Stage115只作历史对照，不是完全匹配的第五臂。

物理上，分层方向使最低箱的偏高修正减少，但第二箱及困难侧出现风险/尾交换；程序上，真实分折、嵌套开发、梯度、保存回读及配对统计均有实际核验。尚未分解哪个具体沉积/逃逸机制导致逐例歧义，也未测独立新样本、source/parent/refit/研究选择误差及真实系统。原cal/test已反复开发，所有区间只是给定来源混合下incoming条件区间，不能当新blind确认。1.05只表示低能恢复/非劣效，宣称超过传统须对应上95<1；本实验远未满足。

## 6. 主物理工作包的准确输入缺口

只检查7个明确缓存的ZIP成员名（不读本地事件数组、不扫描EOS）及Stage99/105既有schema/collection协议：[已检查字段](stage117_energy_ml/observability_cache_schema.json)。这些缓存没有G4祖先联结的敏感沉积、非μ边界能流及新独立生成家族；Stage99关联字段缺失、Stage105只有SP位置和Track_pz0的限制保持。不能把真H/E、truth_st1模长、SP离轴或primary未确认当新粒子来源标签。

[紧凑输入规范](stage117_energy_ml/observability_input_gap.json)给出一个待实际hit schema认证的首要中间量：两个真实VetoNu敏感体内，非primary-μ谱系沉积占总可归属沉积的比例`D_nonmu/(D_mu+D_nonmu)`；D用MeV，primary μ及其全部G4后代归μ类，不除以H，不称能量采样效率。零沉积独立状态、谱系不明保留unknown、全事件预测。该量只是可选择的粒子来源组成标签，不覆盖全部逃逸/不可见机制，其可用率与价值**未测量**。

需要新pilot的generator parent UUID、生成/G4/数字化seed及重放家族、source/native entry/incoming、纳入概率与选择分母、预定train/cal/confirmation；实际VetoNu volume map、沉积/谱系、顶点/材料路径及匹配raw/reduced/status读出。支持需同时覆盖真50–100低transfer、100–200过渡、同低pz真≥200/high-y及自然高端，不能只选旧模型错误。没有提交新生产，没有称旧缓存为新独立支持。

## 7. 执行命令、资源、验证与产物

关键命令（本地只做标准库打包/元数据/表格整理）：

```bash
python3 ml/package_stage117.py package probe
condor_submit -terse AnalysisZipFramework/submission/ml_stage117.sub
python3 ml/package_stage117.py collect probe
python3 ml/package_stage117.py package experiment
condor_submit -terse -append 'phase = experiment' -append 'request_cpus = 8' AnalysisZipFramework/submission/ml_stage117.sub
python3 ml/package_stage117.py collect experiment
```

两作业9668195/9668197均首start、exit0、无重试，spool统一`~/condor/nu_muAnalysis/stage117/`。probe描述请求2CPU/16GB、站点实际6CPU/18GB；正式描述8CPU/16GB、实际8CPU/24GB。8个独立模型fit并发、4个臂并发、8个统计worker，内部线程1；GPU=0，小hist树及≤64维凸头不构成大批密集GPU工作，未测CPU/GPU或串行加速比。

| 测量 | probe | 正式四臂 |
|---|---:|---:|
| GNU user / sys CPU秒 | 3.33 / .61 | 157.31 / 6.01 |
| GNU wall秒 | 4.98 | 60.03 |
| GNU最大RSS KiB | 354196 | 469316 |
| Condor slot busy秒 | 11 | 66 |

GNU累计CPU167.26秒、两个任务wall合计65.01秒，均远低于冻结7200 CPU秒及每任务3600 wall秒；wall不含排队。正式watchdog实测163.29 CPU秒、59.763723 wall秒、最多10个进程，未触发预算。[probe计时](stage117_energy_ml/probe_time.txt)、[正式计时](stage117_energy_ml/time.txt)、[嵌套资源](stage117_energy_ml/resources.json)、[watchdog](stage117_energy_ml/watchdog.json)。GNU RSS不是同时进程树总峰；整树峰、GPU忙时、全会话成本、物理网络/I/O流量未测量。

正式archive读取接口40,610,233 byte，不是物理网络。probe/formal包47,487,087/47,499,167 byte，20/26项输入在收集时与归档逐字节一致，无SHA扫描；[probe transport](stage117_energy_ml/probe_transport.json)、[正式transport](stage117_energy_ml/experiment_transport.json)。独立行空间核112个test配对区间，最大差2.131628e−14；8个主统计最大差4.440892e−16；504个旧标量控制最大差1.421085e−14。[统计验证](stage117_energy_ml/measurement_validation.json)。40个train身份QA，风险梯度最大差1.409796e−8、共同头梯度2.074216e−10，[QA](stage117_energy_ml/QA.json)。未更改C++，无需重新构建分析框架。

worker删除15,959,121 byte的折模型/开发中间模型，保留最终四个小规则头、紧凑train基线及一份完整点表于`ml/artifacts/stage117/`（2,549,628 byte，忽略不入Git）；中文报告、代码/提交脚本、协议、表图和紧凑资源证据入Git。输入/结果运输副本在字节核验后删除，清单见[清理记录](stage117_energy_ml/cleanup.json)；Stage54五项既有未跟踪资产保持。未保存xAOD或新ROOT。重复solver/decision JSON经字典完全相等核验后替换为本目录引用，去重65479 byte，见[无损JSON记录](stage117_energy_ml/json_compaction.json)；命令`python3 ml/package_stage117.py compact`仅标准库处理。格式整理仅空TSV为NA、SVG尾空白，不改任何非空测量值。

## 8. 阶段性结论、下一步与验收

本阶段完成了Stage116工作包A及匹配μ-only归因对照；物理主线B只交准确输入缺口，没有交oracle/代理/能量收益，不冒称B完成。固定四臂未同时恢复低能和困难尾，继续保留强direct，整体点能量目标未完成。

下一阶段具体任务：取得上述明确身份、实际volume/谱系沉积及匹配读出的预定双侧独立紧凑pilot；先认证单一中间量的定义和全队列unknown/零路径，在同一工作包完成原读出→oracle→仅由部署输入预测的代理的同容量能量比较。教师/代理只用train训练，来源/家族留出，所需输出包括标签覆盖、跨来源代理误差、两低能/总体/困难层风险和实际尾、CPU/内存/I/O；不能以辅助分类好看扩大编码器。生产前另冻结实际已有输入与资源、先用小pilot测选择产额，不能在本阶段自动追加生产。

若必要新输入仍不可交付，保留上述精确缺口，不重复扫描旧源或把方法阴性改写成无限调参。相对localtime仍只是有共同控制时可独立实施的有限分支；没有波形、时基和响应就不伪造prompt/late或删失观测。最终接受度/背景、interaction/FSI/材料/读出系统及真正未开发确认均未测量，原1.05/1.01/1.03与八层三尾+2pp门槛不变。

实现与解释沿用Stage116原始文献L1（谱先验/校准，arXiv:2205.05084）及L7（约束影响boosting方向，arXiv:2209.07850）的有限动机，本阶段没有新增网络检索或移植外部性能。先完成本中文报告，再与相关代码、配置、证据做一次本地Conventional Commit，不push。
