# 阶段14：BDT 增益的容量、条件关联与训练先验检验

## 阶段目标与有效物理结论

本阶段从阶段13的探索继续，要求每次推进都产出有数据支持的物理判断。
明确问题是：电子探测器的 station/事件计数和闪烁体电荷，是否在已知重建 μ 的
运动学、拟合质量与几何之后仍含 ν 能量信息，或者主要来自 MC 组分/时期与模型容量？

**本阶段结论限定为现有 ordinary MC 和冻结选择：计数与闪烁体电荷均携带超出 μ
重建信息及来源分层的逐事件能量关联；它们的增益在三档容量、三个 seed 和六个 run
内保留，格内置乱并重训会使相应增益消失。闪烁体增益主要由 FASERν box 区域的
选中事例支持；在铅块区域尚未测得清晰增益。训练能谱先验会改变偏差与尾部的
取舍，不能只用更小的宏平均误差宣称物理响应更好。**

上述是模拟内的重建信息结论，不是 data 中已校准的强子能量测量，未声称因果贡献、
生成器稳健性或最终能谱误差已改善。物理权重尚未恢复，所有主指标仍为单位权重。

## 输入、选择与预注册

沿用 stage12 官方 `d32b0ff3` merge / without-IFT、FASERNU-04、TI12MC04、
OFLCOND-FASER-06、s0014。nominal 六 run：200082/200083/200089/200093/200094/200100；
既有20项 cut、最高 pz leading-track、truth pz>100 GeV fiducial 均未修改。
train **54,196 events / 91 来源组**，validation **13,375 / 22**，同组不跨分区。
calibration、locked test、SIBYLL challenge 未做模型评价或选择。

[预注册文本](stage14_energy_ml/preregistered_protocol.md) 在本阶段新训练结果产生前写入；
[robustness.yaml](../ml/configs/robustness.yaml) 固定：

- seeds **20261029、20261030、20261031**；depth3最多600/2400棵，depth5最多1600棵；
  早停100轮。learning_rate=0.04、subsample=0.8、min_child_weight=20、lambda=10，
  目标均为 squared log E，输入允许清单与 stage12 相同。
- F1/F2/F3/F5，以及 F5 去 scintillator/Calo/shape，共 **63 个容量/seed 模型**。
  不平均不同模型的预测；比较表是单模型指标的seed均值/范围，bootstrap 使用seed均方损失。
- seed0 再做 F1/F3/F5 的 train-energy-bin等总权重、25%/50% train来源组学习曲线、
  F2/F3新增组格内置乱后重训，额外 **9个模型**，总训练模型 **72个**。
- 在 run、重建电荷、log p、theta、rVetoNu 格内整组置乱，同组所有特征共用 donor。
  coarse宽度为 **0.35、5 mrad、60 mm**，fine为 **0.2、2.5 mrad、30 mm**；
  每对照10次。没有用 truth E/位置分格，train/validation从不交换donor。
  对F2 counts、F3 scintillator及F5 scintillator/Calo/shape共 **100个置乱预测**。

主统计仍为六个预注册能量bin `[100,200,400,800,1600,3200,6400] GeV` 的
macro log-RMSE；validation计数 **731/2455/4247/3933/1741/268**。
500次同来源组配对bootstrap；模型训练和早停都接触validation，区间条件于已拟合
模型，不是独立test泛化区间。多重探索比较没有做family-wise校正，弱小增益谨慎解读。

## 实现、执行和验证

新增 `ml/robustness.py`、`report_robustness.py`、`inspect_generation_sources.py`，
HTCondor worker/submission 与配置；不改变C++，不新增ROOT数据或xAOD。
训练读取紧凑缓存一次，1 CPU/job，BLAS/OMP固定1。保留seed0必要F2/F3/F5模型和
各试验validation预测，避免72份重复checkpoint，产物总 **16,631,612 bytes**。

```bash
source AnalysisZipFramework/setup.sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python3 ml/robustness.py \
  --seed-index 0 --smoke --output-dir /tmp/nu_mu_stage14_smoke
# 打包固定脚本/配置，批量训练只通过HTCondor：
tar -czf software/energy-ml-stage14.tar.gz ml/robustness.py ml/train_bdt.py \
  ml/configs/baseline.yaml ml/configs/robustness.yaml ml/configs/files.tsv
condor_submit -name bigbird24.cern.ch AnalysisZipFramework/submission/ml_robustness.sub
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python3 ml/report_robustness.py \
  --report-dir workbook/stage14_energy_ml --artifact-dir ml/artifacts/stage14
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python3 ml/inspect_generation_sources.py \
  --output-dir workbook/stage14_energy_ml
```

当前 lxplus908；LCG109 / ROOT6.38 / XGBoost2.1.3。smoke用1200 train /400 validation、
20棵树，通过全部分支（平坦谱依赖完整能量覆盖，smoke中不拟合该分支），wall
**1.926 s**、CPU **1.476 s**、peak RSS **208.777 MiB**；不从该小样本推断物理性能。
另以合成输入核对donor不跨run/charge、训练权重均值1和各bin总权重一致、
perfect prediction/两倍prediction的group bootstrap分别给0/ln2。实际训练的run/eventID、
truth标签及分组在三seed预测文件中逐值一致；特征允许清单由既有check_features验证。
Python编译、shell语法、diff检查通过；科学图已渲染检查。

HTCondor **cluster1542983，3/3 jobs exit0**，schedd bigbird24。
提交到最后完成 **456 s**，合计remote wall **775 s**，CPU **733 s**。
脚本内部wall合计 **732.948 s**、CPU **722.846 s**，peak RSS最大 **415.922 MiB**。
外部 `/usr/bin/time` 三作业wall **298.33/214.70/232.44 s**，
peak RSS **425904/400580/389692 KiB**。每作业请求1 CPU、2500MB RAM；
GPU成本未测量。完整资源在
[resources.tsv](stage14_energy_ml/resources.tsv)、[Condor资源](stage14_energy_ml/condor_resources.tsv)。
报告聚合wall/CPU成本另记在 `report_resources.json`；不把它计入训练CPU。

## 容量和seed：新增读出的信息增益保留

下表为macro log-RMSE的 **3seed均值 [最小,最大]**，无量纲；不是ensemble精度。

| 容量 | μ context F1 | +计数 F2 | +电荷 F3 | +Calo/全局矩 F5 |
|---|---:|---:|---:|---:|
| d3_600 | 0.516652 [0.516423, 0.516774] | 0.433887 [0.433666, 0.434073] | 0.389884 [0.389340, 0.390275] | 0.384629 [0.384366, 0.385054] |
| d3_2400 | 0.516378 [0.515938, 0.516774] | 0.425119 [0.424137, 0.426409] | 0.380672 [0.380234, 0.380960] | 0.376669 [0.376287, 0.376960] |
| d5_1600 | 0.515220 [0.514887, 0.515820] | 0.422954 [0.421772, 0.423628] | 0.379952 [0.379844, 0.380026] | 0.374455 [0.374261, 0.374803] |

600棵上限确实限制了F2/F3/F5；depth3/2400相对600有改善，不能沿用原报告将其
视为充分训练。但depth5的21个模型全部在1370轮以内停止，最佳轮数最大1269，
仍保留同量级的输入增益，说明原增益并非单纯的600轮容量假象。仅验证这三档容量，
不声称所有模型均达全局最优。

3seed均方损失的同来源配对结果：

| 对照 | Δ macro log-RMSE | 95%区间 |
|---|---:|---|
| depth3/2400：F2−F1，新增计数 | −0.091258 | [−0.103324, −0.078859] |
| depth3/2400：F3−F2，新增电荷 | −0.044448 | [−0.052897, −0.035873] |
| depth5/1600：F2−F1 | −0.092265 | [−0.104281, −0.078958] |
| depth5/1600：F3−F2 | −0.043003 | [−0.051526, −0.033726] |
| depth3/2400：F5−去电荷 | −0.037037 | [−0.044148, −0.029612] |
| depth3/2400：F5−去Calo | +0.000060 | [−0.002256, +0.002652] |
| depth3/2400：F5−去全局空间矩 | −0.003356 | [−0.005684, −0.001239] |
| depth5/1600：F5−去全局空间矩 | −0.003972 | [−0.006546, −0.001759] |

因此电荷在完整模型中仍有明显增益；常规Calo在本选择、已有读出条件下**未测得
稳定不可替代增益**。全局横向矩本次出现小而一致的条件改善，值得推进按station
分组和Deep Sets对照，但这些均值/宽度不证明局部空间关系或图模型有效。
详细表见 [capacity_seed_summary](stage14_energy_ml/capacity_seed_summary.tsv)、
[paired_comparisons](stage14_energy_ml/paired_comparisons.tsv)。

## 来源控制、置乱重训与条件关联

六个run分别计算的F2−F1、F3−F2整体log-RMSE差值95%区间全部低于0，
不是只有混合样本才改善。电荷增量在各run约 **−0.0240至−0.0530**。
进一步在相近μ运动学与同run/charge内置乱：

| fine格、seed0固定模型 | Δ macro（置乱−原模型） | 95%区间 |
|---|---:|---|
| F2 counts | +0.080657 | [+0.068794, +0.090053] |
| F3 scintillator | +0.076125 | [+0.063709, +0.086386] |
| F5 scintillator | +0.066960 | [+0.056877, +0.075122] |
| F5 Calo | +0.005898 | [+0.003893, +0.008107] |
| F5 shape | +0.011221 | [+0.008160, +0.014034] |

fine格 **88.43%**事件位于非单例格，平均 **69.93%** donor实际变化；coarse分别
98.50%/92.16%。fine平均donor差 **|Δlogp|=0.04650、|Δtheta|=0.57259 mrad、
|ΔrVetoNu|=6.46394 mm**。粗/细两档方向一致，区间来自固定的10次置乱平均损失，
并非10次波动的标准误。控制不是逐事件完全匹配，singleton未变、也会破坏未控制的
组间相关性，因此不是精确条件独立/因果检验。

为避免把固定模型的离分布依赖当成独立信息，再做coarse格内独立置乱train与validation
并重训（同容量、seed0）：

- 真实F1 **0.516423**；打乱计数后F2 **0.514707**，相对F1差
  **−0.001716 [−0.004406,+0.000593]**，计数原增益消失。
- 真实F2 **0.424812**；打乱电荷后F3 **0.426623**，相对F2差
  **+0.001812 [−0.000056,+0.003491]**，电荷原增益消失。
- 真实F3 **0.380822**；打乱电荷并重训后变差
  **+0.045802 [+0.037071,+0.054001]**。

**保留run/charge及近似μ运动学后，只有保持新增读出与本事件的配对，才能恢复原增益。**
这排除了“只凭文件来源或粗粒度μ谱就能产生全部改善”的解释；仍不能区分信号来自
shower可见能量、材料/几何、tracking误差与更细的先验。
Calo固定模型置乱有损失，但去Calo后重训几乎不变，正说明“模型使用了该变量”与
“该变量有不可替代新增信息”不同，不能依据置乱importance宣称量能器测得强子能量。

## 相互作用区域：更具体的物理限制

按原truth fiducial几何分层，仅用于评价，truth z不进入预测：

| 区域 | validation N | 加计数：log-RMSE差 [95%区间] | 加电荷：log-RMSE差 [95%区间] |
|---|---:|---|---|
| FASERν box | 12747 | −0.064564 [−0.070569,−0.058902] | −0.035908 [−0.039445,−0.031246] |
| 下游lead block | 628 | −0.093041 [−0.124401,−0.066375] | +0.001813 [−0.006113,+0.010002] |

这支持：**计数在两个区域均有用；电荷增益目前由box事件支持，下游铅块未测得
明确的条件改善。** shower传播路径、材料和选择使两个区域的可见读出不同，
该趋势与电荷携带上游shower信息相容。但两区域Eν/μ谱、接受度及统计量不同，
这里只是诊断分层，不能断言材料位置导致了增益差异；后续须匹配谱和几何并引入
y_inel/truth-primary μ分解。不能把“不显著”写成“铅块电荷信息为零”。
详见 [stratified_gains.tsv](stage14_energy_ml/stratified_gains.tsv)。

分能量看，F3相对F2在 **100–3200 GeV** 五个bin的R68均改善，配对区间不含0。
例如800–1600GeV：R68 **26.00%→23.44%**，差
**−2.562个百分点 [−3.381,−1.564]**，|r|>0.5尾部 **8.92%→6.53%**，
差 **−2.390个百分点 [−2.937,−1.852]**。
3200–6400GeV R68差 **−0.634个百分点 [−2.167,+1.489]**，分辨率改善未确定，
但tail **30.60%→26.49%**，差 **−4.104个百分点 [−7.062,−0.807]**。
这比只报告macro改善更接近实际能量响应；还不是无偏能谱测量。
非线性指标bootstrap使用来源组整数权重及inverse-CDF分位数，点估计保留NumPy
原定义，细微分位数约定差异不冒充物理差异。
见 [energy_gain_intervals](stage14_energy_ml/energy_gain_intervals.tsv)。

## 训练先验：减少端点偏差的代价

train六bin N为 **2944/9776/17237/15790/7303/1146**，等总权重映射为
**3.06816/0.92396/0.52403/0.57205/1.23684/7.88191**，全部仅由train拟合；
Σw=**54196**、Σw²=**128326.677**、Neff=**22888.510**。
这是bin总权重展平，不是精确连续logE均匀，也不是物理flux权重。
validation早停使用同一train映射，以下最终评价仍用不变unit权重。

seed0 F5展平前后：

| 指标 | 原train先验 | bin展平 |
|---|---:|---:|
| macro log-RMSE | 0.376287 | 0.349667 |
| 整体log-RMSE | 0.283652 | 0.303242 |
| 整体P(abs(r)>0.5) | 6.602% | 9.817% |
| 100–200GeV median bias | +13.84% | +6.93% |
| 1600–3200GeV median bias | −14.28% | +0.07% |
| 3200–6400GeV median bias | −36.35% | −24.90% |
| 800–1600GeV P(abs(r)>0.5) | 6.66% | 13.48% |

macro差 **−0.026621 [−0.032384,−0.020995]**，但整体误差与中能尾部恶化。
改变训练谱后端点偏差明显变化，说明它不全是探测器不可观测性；同时高能负偏差
仍大，不能只靠训练谱修正就宣称能量标定完成。后续必须使用含效率的response和
独立pseudo-data谱倾斜闭合比较，而非将逐事件posterior叠加作无偏谱。

学习曲线也表明数据仍有价值：25%/50%/100%来源组对应train **14168/27394/54196**，
F1 macro **0.521168/0.518914/0.516423**，F3 **0.387563/0.384129/0.380822**。
新增读出的增益在较小训练集仍保留，增加数据继续改善，尚无“数据已足够”的依据。
图见 [capacity_and_prior.svg](stage14_energy_ml/capacity_and_prior.svg)。

## 物理权重溯源与未测量项

沿每个run首个simulation log追到其原始EVNT，完整路径与日志在
[generation_sources.tsv](stage14_energy_ml/generation_sources.tsv)。读取早期200082和
2024的200093两个EVNT的schema/元数据树头，entries分别 **559607 / 541884**，
未读取事件payload。6份日志和2个文件头审计wall **1.198 s**。
`GenieReaderAlg.fillEvent`显式push单位HepMC weight，说明ntuple中GenWeights=1
并不意味着六个来源物理luminosity相同。未找到经验证的flux/luminosity映射，
也没有把dumper的缺省GenieLuminosity=150当成当前生成样本真实归一化。
本阶段**物理flux加权结论未测量**，权重问题仍是正式模型比较的前置依赖。

其余未测量：全样本primary μ ancestry/oracle、y_inel分解、MC shower/interaction
替代模型响应、data控制区校准、独立test、最终响应闭合、NN/DeepSets/GNN成本。
本阶段关于有效信息的结论只覆盖已冻结nominal模拟与选择；不能称data已验证。
异常高p事件继续保留，主选择未因模型表现改动。

## 下一步计划与验收

1. **做物理分解**：从同一官方PHYS提取对齐验收后的truth primary μ及leading匹配诊断，
   原始truth ancestry只进标签/诊断，不进可部署输入。比较Eν−Eμ、y_inel、muon动量
   响应，按box/lead及匹配/错配分层；需要足够的独立谱/几何匹配统计。验收为能
   区分电荷增益主要跟强子活动还是μ重建误差相关，明确无法观测部分，不修改主选择。
2. **补物理归一化与闭合条件**：需要GENIE生成配置、输入flux单位/归一化和各源
   生成luminosity，经元数据/生成记录对照再给w/Σw²/Neff。获取后用固定模型和
   响应矩阵检验谱形变化，验收加权结论不由文件数决定。
3. **进入同输入强表格模型**：以已有明确计数/电荷增益为基础，预注册F3以及含全局矩
   的对照，固定权重、loss、partition和CPU/GPU预算比较MLP/ResNet/TabM；应保留
   原先先验敏感性和尾部指标，不以macro最优直接换主分析。物理权重未解决时结果
   仍标模拟诊断。下一阶段须得到新的物理结论而非仅增加架构代码。
4. **空间模型**：小幅全局矩增益足以支持先做按station矩和DeepSets的有针对性试验；
   验收真实空间布局在总计数及μ信息之外仍有增益，之后才升级GNN/Transformer。
