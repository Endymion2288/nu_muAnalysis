# stage31：保留全部F5，加入轨迹状态信息并定位复合曲率尾部

日期：2026-11-01；前一提交 `4f4eb4d`。阶段协议见[预注册](stage31_energy_ml/preregistered_protocol.md)，
字段审计见[源码记录](stage31_energy_ml/source_audit.md)，配置为 `ml/configs/track_response.yaml`。
本阶段完成提取、9个正式BDT、500次来源组配对统计、data读出控制及模型读回；不是只提交作业。

## 阶段结论

1. **F5之外的轨迹信息族有实测开发收益。** 同13,375例、同容量、同train划分三seed，
   ν能量macro log-RMSE从0.378062降至0.363245，相对改善3.919% [1.957%,6.485%]，
   绝对变化−0.014817 [−0.025382,−0.007406]。完整保留F5的计数、电荷、Calo和空间变量。
   该族可保留为有限候选；中心值未达预定5%的ν主目标扩展门槛，区间也不能排除5%收益，
   因而不继续扫参或升级网络。**这不证明19个变量各自都有用，也不证明新增了独立的动量测量。**
2. **现有读出能恢复部分产生点μ信息，但校正不是无偏tracker测量。** F5/F6辅助μ回归macro
   log-RMSE为0.389132/0.366357，增加该族改善5.853% [2.440%,10.051%]；
   F6相对原始reco的0.517336改善29.184% [22.328%,35.085%]。此目标是产生动量，含传播、
   身份误选和拟合效应；训练truth仅作标签。风险下降伴随核心与偏差的折中，不能当作分辨率提升百分比。
3. **高动量曲率尾与高y缺失能量是不同的限制。** confirmed且primary p=3.2–6.4TeV的110例中，
   18例电荷符号不一致，16.364% [8.996%,23.334%]；归一化曲率残差R68=1.49577。
   confirmed且y≥0.8的99例原始μ产生动量log-RMSE仅0.063531，ν却为0.814759；
   加轨迹族后的ν风险0.816543，变化+0.001784 [−0.005251,+0.009037]，没有明确收益。
   改善μ读出本身不能解决这部分能量分配简并；不因这99例而丢弃整个轨迹分支。
4. **同参考面传播/拟合分解仍未测量。** PHYS无真实输运动量与拟合协方差；实际RDO保存TruthEvent，
   不能宣布原始输入也没有真值。单例uproot解码遇到不支持的memberwise序列化，需native POOL字典继续。
   本轮不使用truth_st1模长、不做伪pull、不把oracle差距全部算给拟合。

## 样本、选择与预设比较

普通几何、官方merge d32b0ff3/without-IFT，六nominal run：200082/200083/200089/200093/200094/200100；
原20 cuts、truth fiducial、最高pz leading和unit权重全部不变。文件清单 `ml/configs/files.tsv`，
222个train/validation PHYS共2,203,362个raw事件，选中67,571例。
train 54,196例/91来源组，validation 13,375例/22组；train内fit/stop/map为36,668/6,340/11,188例，
对应60/11/20来源组。map本轮不用；calibration、locked test、challenge均未启用。
保留全部271个未确认primary事件、离群值和高y，所有模型完全同事件。

F5=46维。F6=65维，新增：back状态p/px/py/pz（GeV）、x/y/z（mm），q/p0与q/p1（GeV^-1），
log(p1/p0)，z跨度（mm），两方向端点slope差与chord slope，首measurement模块eta/phi，
最大半径状态z（mm），事件SCT错误。具体公式在协议与 `ml/track_response.py`。
19维全部有限，train/validation没有因缺值删事件；SCT错误恒0，另外18维有变化，未按validation筛选。
`Track_isForward`只用于MC诊断，旧data无此分支，不入部署输入；hitSet/nMeasurements不使用。

三seed=20261029/30/31，固定depth5、最多1600round、patience80、4CPU、120s/fit。
每seed仅训练F6 ν回归、F5/F6 μ残差回归；复用stage30相同来源分配和seed的F5 ν基线，没有重新训练。
μ标签为log(p_primary,vertex/p_reco)，输出p_reco exp(residual)。9fit均由patience停止，无时间截断。
额外3个20round小样本smoke明确另记成本，不当作正式结果。

## 详细性能

log-RMSE无量纲；bias、R68、tail是相对误差的量，以下表格后者转为%。R68=(q84−q16)/2。
主macro风险先对各能量箱/三seed的log平方误差平均，再开方；不是ensemble预测，也不把seed当独立事件。
原六能量箱均保留，最高ν能量箱268例/14来源组。CI为22来源组的500次成对重抽样（seed20261101），
median/R68以整数来源权重重建分位数。既有validation已反复开发，区间不包含全部模型选择不确定性。
完整逐能量/y/primary p/z/charge/confirmed/forward指标、配对区间及同confirmed交叉分层见
[metrics](stage31_energy_ml/metrics.tsv)、[paired](stage31_energy_ml/paired.tsv)、
[curvature](stage31_energy_ml/curvature.tsv)、[逐seed](stage31_energy_ml/seed_metrics.tsv)。
同confirmed交叉表作诊断，未据此选择新模型或改变预算。

| 任务/输入 | macro log-RMSE | 95%来源CI |
| --- | --- | --- |
| nu_F5 | 0.378062 | [0.351707,0.403018] |
| nu_F6 | 0.363245 | [0.340095,0.386905] |
| mu_F5 | 0.389132 | [0.360657,0.418908] |
| mu_F6 | 0.366357 | [0.339705,0.396345] |
| mu_reco | 0.517336 | [0.480553,0.546907] |

总体（按事件频率评价，区别于macro）：

| 模型 | log-RMSE | mean bias (%) | median bias (%) | R68 (%) | |误差|>0.5 (%) | |误差|>1 (%) |
| --- | --- | --- | --- | --- | --- | --- |
| nu_F5 | 0.284965 | 3.832 | 3.716 | 22.744 | 6.707 | 0.653 |
| nu_F6 | 0.276280 | 3.539 | 3.471 | 22.143 | 6.014 | 0.533 |
| mu_reco | 0.393198 | 88.216 | -1.564 | 10.743 | 6.774 | 2.856 |
| mu_F5 | 0.292435 | 11.945 | 0.613 | 11.295 | 4.770 | 1.274 |
| mu_F6 | 0.278568 | 10.692 | 0.415 | 10.822 | 4.162 | 1.131 |

原始μ的总体mean bias为+88.216%，反映保留的长尾；F6辅助回归降低到+10.692%，
但总体R68从10.743%到10.822%，**不能把尾部风险降低解释成全样本核心变窄**。
confirmed子集μ log-RMSE为原始0.327565、F5 0.219396、F6 0.203345，
所以收益不只来自271例未确认primary。未确认子集ν F6−F5为+0.010626
[−0.000733,+0.021544]，仍困难，未将其删除。

逐ν能量箱F6−F5：

| 真Eν (GeV) | N | F5 | F6 | Δ log-RMSE及95%CI |
| --- | --- | --- | --- | --- |
| 100_200 | 731 | 0.244143 | 0.246721 | +0.002578 [-0.003807,+0.008140] |
| 200_400 | 2455 | 0.218251 | 0.214487 | -0.003764 [-0.006285,-0.001582] |
| 400_800 | 4247 | 0.237459 | 0.232953 | -0.004506 [-0.006626,-0.002275] |
| 800_1600 | 3933 | 0.281384 | 0.271760 | -0.009624 [-0.012377,-0.007015] |
| 1600_3200 | 1741 | 0.377546 | 0.362305 | -0.015241 [-0.024746,-0.007724] |
| 3200_6400 | 268 | 0.687198 | 0.652242 | -0.034956 [-0.069161,-0.011417] |

最高ν能量箱的median bias仍为F5 −37.985%、F6 −35.786%，并未解决高能下偏。
同箱μ辅助回归虽降低风险，median bias从原始−7.288%变为F6 −30.977%，
表现出向样本主区间收缩的折中；尚未分开训练先验、正则化与真实响应因素，不部署为无偏μ校正。
高y-confirmed的μ F6反而比原始恶化+0.060031 [0.030670,0.089490]；
只看macro会掩盖这一点。

## 曲率：有物理证据的复合响应

κ_reco=q_reco/p_reco，κ_vertex=−sign(PDG_primary)/p_primary，单位GeV^-1；
归一化残差为p_primary(κ_reco−κ_vertex)，无量纲。这里vertex是产生点，未声称与reco同面。
在confirmed支持上看不同primary产生动量：

| primary p (GeV) | N | R68 Δκ (GeV^-1) | R68归一化残差 | 电荷不一致 |
| --- | --- | --- | --- | --- |
| 100_200 | 1474 | 0.00023734 | 0.035981 | 0 (0.000%) |
| 200_400 | 3448 | 0.000189142 | 0.055478 | 2 (0.058%) |
| 400_800 | 4244 | 0.000181484 | 0.103172 | 11 (0.259%) |
| 800_1600 | 2831 | 0.000202601 | 0.215353 | 45 (1.590%) |
| 1600_3200 | 993 | 0.000232533 | 0.485920 | 60 (6.042%) |
| 3200_6400 | 110 | 0.00034837 | 1.495771 | 18 (16.364%) |

主要能区的Δκ核心宽度处于约2×10^-4 GeV^-1量级，最高p箱增至3.48×10^-4 GeV^-1；
归一化宽度随p迅速变大，最高p箱电荷符号差异也明显。这与高p处q/p靠近零、相对动量约束变弱相容，
但缺少同面输运真值，不能给材料与拟合的份额。没有对接近零κ取倒数再截断。

全部confirmed 13,104例的电荷不一致136例，1.038% [0.763%,1.324%]；
未确认271例为192例，70.849% [65.615%,75.357%]，后者还包含primary身份不同，不能称tracker signflip率。
在3.2–6.4TeV的ν箱，confirmed 258例中30例电荷不一致，11.628% [7.615%,14.692%]；
全体268例则38例、14.179% [10.494%,17.565%]。
高y-confirmed 99例观察到0个符号差异；bootstrap的零区间只反映未观察到该尾，不能排除总体稀有率。

[图：同事件ν性能与confirmed复合曲率](stage31_energy_ml/track_response.svg)。

## 物理原因和程序原因检查

- 222份输入逐vector检查对齐，逐run/eventID/manifest重排；reco p与charge对旧缓存逐值相等；
  67,571例共同支持及全部缓存读回通过。9个保存模型重新加载，对13,375例预测逐值等于保存预测。
  模型输入严格为reco，primary PDG/xyz/y/matching仅作诊断；μ truth仅作标签。
- 两端来自同一拟合。validation的log(p1/p0)中位数−1.02581×10^-5，
  |log比|>0.001仅13例，>0.01仅2例，不能将p1当新独立谱仪。
  F6还包括q/p等已有F5量的重表达；这轮只证明整个信息/表示族的可利用收益，
  没有隔离每变量的独立信息。BDT split gain保存在各seed，相关变量的重要度不能当物理归因或消融。
- 两端状态差、module、弯折和chord可携带几何及拟合条件，真实原因尚需同面输运/协方差控制。
  不能因p1 split gain大就宣称测得了材料能损，也不能把产生动量oracle全部变成可实现收益。
- 整数来源bootstrap分位数已与显式重复事件的np.quantile核对一致；三seed ν macro全部改善，
  具体为F5 0.378281/0.377032/0.378871，F6 0.363959/0.363093/0.362681。
  多个诊断区间未经多重检验校正，不将每个分层当独立发现。

## data控制：读出可定义，尚未闭合

run016000 r0022 PHYS（完整URL在配置）只读前16,000例。原预注册穿透MIP代理的cutflow：
16,000→15,855（恰1保存轨迹）→11,238（pz>100GeV）→10,948（layers≥7）→10,511（nDoF≥9）
→10,477（chi2/nDoF<15）→4,910（rmax<95mm）→4,908（两VetoNu charge>40pC）→0（四CaloHi同时0.5–2nMIP）。
没有改阈值去追求非零产额。四Calo横向块不应要求一条穿透轨迹同时在四块为MIP；
原代理失败，不得称完成了MIP校准。

补充事后诊断保留pre-Calo的4,908个tracker候选，19维全部有限，18维有变化、SCT错误恒0；
MC-only isForward仍禁入特征。此候选CaloHi0/Lo0 nMIP中位数5.17460/0.218871，
Lo0有1例非有限；status多值，未审计其bit语义，不能凭数值称饱和比例。
详见[data字段表](stage31_energy_ml/tracker_data_feature_profile.tsv)、
[双增益表](stage31_energy_ml/tracker_data_calo_profile.tsv)及cutflow JSON。

新变量在data可定义不等于已校准迁移。例：validation MC的z1仅16个离散值，data tracker候选为4,312个；
两者span中位数2443.885/2443.851mm。样本组成、geometry/alignment和conditions不同，
不能直接归为mismodeling；需匹配生产和track状态参考面控制。
MIP/双增益校准、真实νdata能量闭合、CaloNu同事件增益、本轮条件谱收益及detector/interaction系统误差均**未测量**。

## 执行、性能和产物

软件：CVMFS `LCG_109_cuda/x86_64-el9-gcc13-opt`，不重新编译Calypso；
提取单CPU，BDT与小样本验证4CPU，BLAS线程1。本轮没有用GPU扩大架构。
代表命令：

```bash
source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
export PYTHONNOUSERSITE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=4
python3 ml/extract_track_response.py --index 101 --output /tmp/stage31_smoke.npz
python3 ml/extract_track_response.py --data --entry-stop 400 --output /tmp/stage31_data_smoke.npz
condor_submit -name bigbird21.cern.ch -dry-run /tmp/stage31_extract.ad AnalysisZipFramework/submission/ml_track_response_extract.sub
condor_submit -name bigbird21.cern.ch AnalysisZipFramework/submission/ml_track_response_extract.sub
python3 ml/prepare_track_response.py
python3 ml/train_track_response.py --seed-index 0 --smoke --output-dir /tmp/stage31_train_smoke
condor_submit -name bigbird21.cern.ch -dry-run /tmp/stage31_train.ad AnalysisZipFramework/submission/ml_track_response_train.sub
condor_submit -name bigbird21.cern.ch AnalysisZipFramework/submission/ml_track_response_train.sub
python3 ml/report_track_response.py
python3 ml/plot_track_response.py
```

每个Args经dry-run检查，避免上一阶段mode覆盖问题。tracker data补充使用 `AnalysisZipFramework/submission/ml_track_response_data.sub`（队列表为
`tracker_data 0`），wrapper实际运行 `extract_track_response.py --data --tracker-control`；
本轮未发生技术性训练重复或失败重试。模型及紧凑缓存在ignored路径，代码、配置、报告、表与SVG提交Git。

- MC单文件smoke：10,000 raw→323 selected，0.728868s、92.211MiB；leading p和charge逐值一致。
- MC批提取19作业：内部wall总和253.625s、CPU 150.660s，
  峰值RSS 151.844MiB，按raw数/内部wall约8687.5 events/s。
  单次读取只取必要分支，最终仅保存选中scalar；合并2.206s，缓存6,503,518bytes。
- 正式9fit训练wall总和95.325s、CPU 353.069s；
  各fit 5.686–17.552s。
  F6 ν单模型吞吐102843–133454 events/s；非3seed ensemble成本。
- Condor集群2187187（19MC+1原data）、2187188（3seed）、2187189（1tracker data），24作业全部exit0；
  wrapper wall总和466.12s、CPU 566.75s、峰值347.504MiB。
  此wall为作业总和，不是日历耗时；训练submit→最后结束163s。site将4CPU训练内存配置提升到12,000MB，
  实际allocation逐作业记录，不能把sub的3,000MB当实际分配。详见[资源表](stage31_energy_ml/condor_resources.tsv)。
- 原data/补充data内部读出分别1.309/1.234s，峰值106.883/114.133MiB；
  小样本3fit、模型读回和报告计时另存smoke/model_readback/report_resources JSON。
  最终报告生成22.505s、CPU 22.142s、209.219MiB。

最终产物：`ntuples/energy_ml_stage31/{train,validation}_tracks.npz`、
`data_control.npz`、`tracker_data_control.npz`；`ml/artifacts/stage31/seed_{0,1,2}/`内9模型及预测；
`workbook/stage31_energy_ml/`全部汇总表、图、成本和协议。来源分配与共同训练配置集中到
`training_shared.json`，不保留19份重复提取shards或一次性源包，不保存新ROOT/xAOD中间文件。

## 下一步唯一优先任务与验收

继续同参考面曲率分解，保留F5/F6这两个有限候选，不追加架构或盲目加读出族：

1. 用匹配native POOL/ROOT字典读取现有RDO TruthEvent，审计μ continuation/barcode、真实输运顶点覆盖；
   同时用匹配d32b0ff3现成构建，在分层代表性来源/能量/y/z样本导出reco状态参考面、q/p、完整协方差。
   所需输入是manifest的原RDO、固定selected键及生产conditions，不能只挑尾部事件。
2. 核实能否取得真正输运时刻、与reco同参考面的μ动量。若现有TruthEvent不足，用有预算的小样本G4步/参考面导出，
   只存紧凑诊断；不将最近一个产生/相互作用顶点当精确同面状态。先smoke、后Condor。
3. 验收：同事件将产生→参考面传播与reco→同面truth残差分开，确认primary支持上报告κ bias/R68/尾部/pull及来源组区间，
   保留未确认诊断；数据需匹配几何/参考面/协方差控制。只有通过该检查后再冻结F5/F6的独立校准/检验协议。
   原始truth若不足，必须给代表性覆盖率与可操作的新导出方案，不能只写“缺字段”。

F6证明值得保留一组更丰富的reco输入；其名义收益尚不等于最终谱/真实data收益。
不继续扩大概率网络、coverage调参或大型拓扑；同事件CaloNu仍是后续有新读出证据时的分支。
