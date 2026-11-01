# stage34：100 GeV–1 TeV重点与冻结F5/F6独立检验

## 阶段目标

按用户最新要求，将重点从100–250扩大到**100–1000 GeV**，保留100–250、250–1000子层；
≥1 TeV只作参考。执行修订路线第10/15节的有限候选冻结、calibration和独立性能检验。
不新增架构、扫参或扩大原生tracking审计，保留F5的全部非μ输入。

**新结论：新增19维轨迹表示在250–1000 GeV有独立、有限的ν收益，但不能解决高y能量分配缺口。**
test的data可执行reco重点区间改善2.7976% [2.3098%,3.3915%]；真实primary-confirmed
250–1000 GeV改善2.3031% [1.6593%,2.9647%]，100–250 GeV则未确立改善。
总体macro改善4.6062% [2.0160%,6.8809%]，中心值未达到预注册5%架构扩展门槛。
保留F6有限候选，不把门槛事后下调，也不据此宣称没有可能的5%收益。

本报告区间均为500次来源组bootstrap的95% percentile区间；候选比较为配对抽样。
校准后结果的区间同时传播独立calibration来源组的不确定度。百分比为相对风险改善；
偏差/R68/尾率用%，尾率差用百分点。log-RMSE为无量纲，能量/动量为GeV。

## 冻结、样本与工作内容

[预注册协议](stage34_energy_ml/preregistered_protocol.md)及
[配置](../ml/configs/frozen_evaluation.yaml)在读取保留分区事件/标签前写入，指定冻结UTC
2026-11-01 12:05:51，起点`06224d5`。冻结前仅读开发结果、模型metadata及manifest文件数/选择数。
执行顺序为validation smoke→calibration→冻结offset→test→固定test报告→challenge，未倒序。

| 分区 | PHYS文件 | 来源组 | 原PHYS事件 | 原选择保留事件 | confirmed | 用途 |
|---|---:|---:|---:|---:|---:|---|
| validation smoke | 1 | 1 | 10000 | 315 | 仅核对旧结果 | 程序验收，不拟合 |
| calibration | 32 | 16 | 318614 | 9727 | 9539 | 两个全局offset，不据此选候选 |
| locked test | 43 | 22 | 412227 | 12488 | 12229 | 独立保留分区性能 |
| SIBYLL π challenge | 45 | 45 | 440784 | 15144 | 14843 | 冻结参数后的迁移检查 |

nominal仍为六run 200082/200083/200089/200093/200094/200100，ordinary几何、official
merge d32b0ff3/withoutIFT、原20 cuts、最高pz leading及truth fiducial不变，unit MC。
calibration/test含π/K/charm，challenge只有SIBYLL π，不能当六run总体的直接系统替代。
train、validation、calibration、test、challenge的manifest来源组两两不交。

- F5固定46维：μ、质量/几何context、station计数、闪烁体电荷、普通Calo与全局SpacePoint shape。
  F6保留全部F5，再加原stage31的19维端点状态、弯折、纵向跨度和模块变量，共65维。
- 使用stage30的`A0.ubj`和stage31的`nu_F6.ubj`，各三个seed 20261029/30/31。
  取各自best_iteration+1，三个log(Eν/GeV)输出作算术平均，再float64指数化。
  与旧报告“各seed风险的平均”不是同一个统计量，不能直接作精确前后差。
- 两个模型族的train内部fit/stop/map来源分配、reference配置、seed、F5特征前缀逐一相同；
  模型内特征顺序逐一核对。详见[固定模型审计](stage34_energy_ml/fixed_model_audit.tsv)。
  F5三seed最佳iteration=691/728/581，F6=819/899/825；停止预算保持原样，本轮零新fit。
- 原始pμ、pμ/0.8为两个固定物理基线。μ辅助回归不部署。truth p/y/xyz及matching仅为MC诊断，
  不输入模型、不按truth p切换部署候选。`lead_isForward`也不输入；其false不解释为实际逆行粒子。
- 只从原PHYS单遍读取所需branches，复用原19维定义，F5复用stage12缓存；不读truth_st1，
  不重新重建RDO，不用产生动量的station模长测材料能损。run/eventID/manifest_index、reco p/charge、
  truth E/xyz全部与原cache核对，三个新分区37359例的19维全部有限，SCT错误均为0。

最终输入和预测缓存为`ntuples/energy_ml_stage34/{calibration,test,challenge}.npz`，
包含事件键、19维reco、隔离的truth诊断、六个固定模型的log预测，合计**5695131 bytes**。
未提交NPZ/UBJ/ROOT。每分区逐字段压缩读回完全一致后，删除11个shard和3个payload，
释放24330004bytes；顺序、事件键、预测有限性和存储核验见
[archive_verification.json](stage34_energy_ml/archive_verification.json)。

## 校准和解封顺序

每候选仅一个全局c=mean_cal(log Etrue−log Epred)，校准预测为exp(log Epred+c)。
它优化calibration的micro log-MSE，既不保证线性能量均值无偏，也不保证各能区无偏。
没有条件校准、bin/coverage/seed选择或任何test后参数修改。

| 候选 | 冻结log offset | 能量乘数 | test报告中校准来源重抽的offset 95%区间 |
|---|---:|---:|---|
| F5 | −0.003237893841 | 0.9967673425 | [−0.0278162570,+0.0198631553] |
| F6 | −0.003361670969 | 0.9966439731 | [−0.0259449645,+0.0180891325] |

调整幅度不足0.4%，统计区间包含0，不能称发现了显著整体尺度错误。
[冻结状态](stage34_energy_ml/calibration_state.json)保存于12:13:31.572 UTC；
test报告保存于12:16:51.250 UTC，之后才打包/提交challenge；challenge报告保存于12:20:14.886 UTC。
两个模型offset的bootstrap共享calibration重抽，评价集使用另一套独立来源重抽，所有方法共享评价重抽。
headline macro用六个真能箱等权，中心N≥100的active集合在重复中固定；test六箱全纳入。

## 独立test的ν性能

主比较为校准后的固定三seed ensemble。全体12488例全部保留，含259个未确认leading；
primary候选缺失/歧义为0。以下风险未按truth信息选择部署模型。

| 评价支持 | N | F5 log-RMSE | F6 log-RMSE | F6相对改善及95%区间 |
|---|---:|---:|---:|---|
| 全体micro | 12488 | 0.284682 | 0.275737 | 3.1423% [2.6934%,3.6671%] |
| 全体六能箱macro | 12488 | 0.354272 | 0.337954 | 4.6062% [2.0160%,6.8809%] |
| **reco p 100–1000** | **10014** | **0.282968** | **0.275051** | **2.7976% [2.3098%,3.3915%]** |
| reco p 100–250 | 2493 | 0.355059 | 0.349627 | 1.5300% [0.6527%,2.4157%] |
| reco p 250–1000 | 7521 | 0.254606 | 0.245380 | 3.6236% [2.9604%,4.4271%] |
| reco p ≥1000，参考 | 2474 | 0.291520 | 0.278494 | 4.4681% [2.7638%,6.1974%] |
| confirmed truth p 100–1000 | 9644 | 0.261849 | 0.257529 | 1.6497% [1.2034%,2.1368%] |
| confirmed truth p 100–250 | 2162 | 0.304408 | 0.303913 | 0.1626% [−0.5033%,0.7537%] |
| confirmed truth p 250–1000 | 7482 | 0.248195 | 0.242479 | 2.3031% [1.6593%,2.9647%] |
| confirmed truth p ≥1000，参考 | 2583 | 0.334625 | 0.310634 | 7.1692% [5.8259%,8.6864%] |
| 未确认leading | 259 | 0.484194 | 0.479936 | 0.8795% [−0.5560%,2.6811%] |

这里重点区间的收益在250–1000 GeV也存在，不能全部归于≥TeV事件。
但真实100–250 GeV支持上未发现明确ν风险收益，不能用reco低箱的1.53%代替此结论。
未确认支持的R68从37.4982%变为38.4132%、>50%尾率从19.6911%变为21.2355%，
不能说全部支持或所有指标一致改善。

### 基线、偏差、R68与尾部

| 支持 | 方法 | log-RMSE | mean bias % | median bias % | R68 % | >50%尾率 % | >100%尾率 % |
|---|---|---:|---:|---:|---:|---:|---:|
| 全体 | 原始pμ | 0.591739 | −5.0933 | −21.8736 | 23.0081 | 17.8652 | 1.5935 |
| 全体 | pμ/0.8 | 0.505113 | +18.6333 | −2.3420 | 28.7601 | 13.9174 | 2.3062 |
| 全体 | F5 | 0.284682 | +3.7812 | +3.4713 | 22.4411 | 6.6864 | 0.7447 |
| 全体 | F6 | 0.275737 | +3.5081 | +3.2079 | 21.9999 | 6.0618 | 0.6006 |
| reco 100–1000 | pμ/0.8 | 0.464495 | −10.0935 | −5.1131 | 28.1081 | 11.5039 | 0.0599 |
| reco 100–1000 | F5 | 0.282968 | +3.4298 | +3.8796 | 21.3816 | 6.1514 | 0.5392 |
| reco 100–1000 | F6 | 0.275051 | +3.2706 | +3.4661 | 21.0080 | 5.7420 | 0.5592 |

重点区间F6−F5的>50%尾率差为−0.4094个百分点 [−0.7161,−0.1604]，但>100%尾率
中心值略升，不能只看单一风险。reco 100–250 GeV的>50%尾率为10.5897%→10.8704%，也如实保留。
F5相对pμ/0.8的重点风险改善39.0806% [36.5708%,41.3098%]，包含非线性回归和unit先验作用，
不是全部由新读出独立贡献；更不是新增19维轨迹变量的贡献。

raw控制：全体F5/F6 log-RMSE=0.284696/0.275746；重点=0.282958/0.275042，
与校准后接近。全体raw macro=0.353659/0.337336；微小全局offset在test上没有优化macro，
不能因此在test后改选raw或更换校准形式。

逐真能箱结果显示全局尺度不能消除条件偏差：

| Eν真能箱 GeV | N | F5/F6 log-RMSE | F5/F6 mean bias % |
|---|---:|---|---|
| 100–200 | 629 | 0.232803 / 0.227832 | +18.4421 / +17.7686 |
| 200–400 | 2261 | 0.229336 / 0.225346 | +12.1971 / +11.5000 |
| 400–800 | 4003 | 0.238105 / 0.234525 | +7.6013 / +7.1375 |
| 800–1600 | 3717 | 0.290763 / 0.280732 | +1.7416 / +1.3164 |
| 1600–3200 | 1664 | 0.380384 / 0.364699 | −12.7195 / −11.7302 |
| 3200–6400 | 214 | 0.600276 / 0.561934 | −35.9540 / −34.1780 |

这与有限输入、log回归及训练先验收缩相容，但本阶段没有单独隔离各自贡献，不能唯一归因tracking。
全体、逐能量、六个leptonic y层、confirmed/未确认及交叉层的全部误差、mean/median bias、
R68、relative RMS、两尾率及其95%区间见
[test_metrics.tsv](stage34_energy_ml/test_metrics.tsv)，来源组配对差和改善区间见
[test_paired.tsv](stage34_energy_ml/test_paired.tsv)，macro见
[test_macro.tsv](stage34_energy_ml/test_macro.tsv)。所有非空层的缺支持bootstrap次数逐项记录。
test charm为905例/仅3来源组，20/500次重抽没有charm支持，其区间只使用480次有效重复，
不能解释成包含这部分未定义重复的无条件95%覆盖；headline、重点及主要配对风险区间均500次有效。

## μ响应与高y缺口

下表补充描述性MC诊断，是**原始reco p对产生动量**的复合响应，含传播与拟合，既不是同面pull，也不是新μ校准。
均为primary-confirmed，重点9644例/22组；完整区间见
[muon_production_response.tsv](stage34_energy_ml/test_muon_production_response.tsv)。

| primary p GeV | N | 原始μ log-RMSE | median bias % | 原始μ R68 %及95%区间 |
|---|---:|---:|---:|---|
| 100–1000 | 9644 | 0.185851 | −1.5030 | 7.3881 [6.9955,7.8401] |
| 100–250 | 2162 | 0.070233 | −1.6171 | 3.4608 [3.3074,3.6155] |
| 250–1000 | 7482 | 0.207596 | −1.4267 | 8.8527 [8.5329,9.2434] |
| ≥1000，参考 | 2583 | 0.641234 | −2.0354 | 35.2943 [32.4353,38.6616] |

扩大区间后的μ核心仍明显好于≥TeV参考，但不能把100–1000全段当相同3%分辨；
250–1000核心较宽，log风险还包含尾。不删任何离群或未确认事件，不要求高p达到低p精度。

重点truth p且y≥0.8的**104例/21来源组**：原始μ log-RMSE=0.066595、R68=4.1245%；
ν F5/F6=0.811343/0.811514，改善−0.0210% [−1.5562%,2.0618%]，未建立收益。
两者mean bias=−44.3153%/−44.9659%，>50%尾率=51.9231%/48.0769%；
尾率差区间[−7.9261,+2.0106]个百分点跨0，不能靠中心尾率声称解决问题。
固定pμ/0.8在该层mean bias为−80.5477%，R68却仅4.5763%，说明单看核心宽度会严重误判准确度。

**物理解释的边界**：该支持上μ产生动量已较准，更多轨迹表示没有显著降低ν误差，
主要待检问题在能量分配/非μ读出响应。不能把所有oracle缺口解释成μ拟合，也不能据一个BDT断言
现有所有读出都达到不可恢复的极限；传播/模型/选择/先验仍未完全分离。

## 事后解释性控制：reco低箱不是纯真实低p

test结果固定后，补充**描述性**迁移核算，不用于选模型、阈值或重训，也不当新的确认性检验。
见[迁移分解](stage34_energy_ml/test_posthoc_migration.tsv)。按matching及预设truth p边界划分，
各单元的平方log误差改善加和严格复现对应reco箱总改善。

reco 100–250的2493例中，2112例为confirmed且true p 100–250；193例confirmed true p 250–1000，
23例confirmed true p≥1000，另有165例未确认（其中6例true p≥1000），1例confirmed true p<100。
23例confirmed高p跨入该箱的ν F5/F6 log-RMSE=1.374515/1.245738。
23+6个true p≥1TeV事件贡献8.203210的平方log误差和改善，约占该reco箱总改善9.543272的
85.9580%。该百分比为本样本事后点分解，无独立来源置信区间，少数事件影响不可外推为总体定律。
它解释了为什么reco低箱改善不能等同真实低p改善；这些事件仍保留，未因此停止低p分支。
真实250–1000的独立收益也不能被这个低箱迁移现象抹去。

## SIBYLL π挑战：支持有限迁移，不替代系统闭合

使用完全相同冻结模型和nominal calibration，没有在challenge再校准。15144例/45组全保留，
primary候选均唯一，301例未确认。全体micro F5/F6=0.251438/0.245869；
macro=0.264205/0.257014，改善2.7221% [1.7248%,3.8143%]。
challenge macro的active箱仅0–4（100–3200），与test的六箱不同，二者数字不能直接比较。

| 挑战支持 | N | F5/F6 log-RMSE | 相对改善及95%区间 |
|---|---:|---|---|
| reco p 100–1000 | 13951 | 0.244792 / 0.240465 | 1.7674% [1.1124%,2.5000%] |
| reco p 100–250 | 4386 | 0.301294 / 0.298877 | 0.8022% [−0.2619%,2.0152%] |
| reco p 250–1000 | 9565 | 0.213950 / 0.208273 | 2.6533% [1.7719%,3.5977%] |
| confirmed truth p 100–250 | 3983 | 0.283872 / 0.282341 | 0.5395% [−0.2652%,1.1886%] |
| confirmed truth p 250–1000 | 9683 | 0.223497 / 0.218244 | 2.3500% [1.3581%,3.2969%] |
| confirmed truth重点且y≥0.8 | 63 | 0.784962 / 0.780387 | 0.5829% [−0.8656%,1.7748%] |

为避免混合谱误读，另取test nominal π的4707例/8组，与challenge π比较。
共同有N≥100支持的真能箱只有**100–200、200–400、400–800、800–1600 GeV**，按四箱等权macro：

| π样本 | F5 macro及95%区间 | F6 macro及95%区间 |
|---|---|---|
| nominal π test | 0.245573 [0.233358,0.256160] | 0.239252 [0.227921,0.248508] |
| SIBYLL π | 0.248330 [0.240000,0.256999] | 0.243401 [0.235222,0.251663] |

SIBYLL−nominal的macro差：F5 +0.002757 [−0.006813,+0.013473]，
F6 +0.004149 [−0.004925,+0.014716]；未确立整体恶化，也不能声称等效性或无系统依赖。
两样本中F6−F5的共同能区macro差分别为−0.006321 [−0.008481,−0.004134]、
−0.004929 [−0.006680,−0.003095]，有限收益保留。
逐π真能箱的bias/R68/尾部在`component_pi_energy_*`和`component_sibyll_pi_energy_*`行完整报告。
SIBYLL是flux/母粒子模型挑战；共同真能箱仍未隔离所有谱内形状、来源和生成差异。

产物：[challenge_metrics](stage34_energy_ml/challenge_metrics.tsv)、
[paired](stage34_energy_ml/challenge_paired.tsv)、[macro](stage34_energy_ml/challenge_macro.tsv)、
[π共同支持](stage34_energy_ml/challenge_pi_common_energy.tsv)、
[π对比区间](stage34_energy_ml/challenge_pi_contrasts.tsv)。
图：[独立test](stage34_energy_ml/locked_test.svg)、[π挑战](stage34_energy_ml/pi_challenge.svg)。

## 执行、验证、性能与存储

LCG109_cuda/x86_64-el9-gcc13-opt，PYTHONNOUSERSITE=1，OMP/OPENBLAS/MKL线程=1。
仅固定CPU BDT推理，无GPU/新训练需求。大批量PHYS提取全部经`bigbird21.cern.ch`；
schedd队列可匹配并迅速完成，无需切换。各job申请1 CPU/1500 MB，站点实际分配1 CPU/3000 MB。

主要命令（每步成功才执行后续分区）：

```bash
source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
export PYTHONNOUSERSITE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python3 ml/frozen_evaluation.py extract --partition validation --index 47 --output /tmp/stage34_smoke.npz
python3 ml/frozen_evaluation.py smoke --input /tmp/stage34_smoke.npz --output workbook/stage34_energy_ml/smoke_validation.json
python3 ml/package_frozen_evaluation.py --partition calibration
condor_submit -name bigbird21.cern.ch AnalysisZipFramework/submission/ml_frozen_evaluation.sub 'part=calibration' -queue 3
python3 ml/frozen_evaluation.py collect --partition calibration
python3 ml/frozen_evaluation.py calibrate
python3 ml/package_frozen_evaluation.py --partition test
condor_submit -name bigbird21.cern.ch AnalysisZipFramework/submission/ml_frozen_evaluation.sub 'part=test' -queue 4
python3 ml/frozen_evaluation.py collect --partition test
python3 ml/report_frozen_evaluation.py --partition test
python3 ml/package_frozen_evaluation.py --partition challenge
condor_submit -name bigbird21.cern.ch AnalysisZipFramework/submission/ml_frozen_evaluation.sub 'part=challenge' -queue 4
python3 ml/frozen_evaluation.py collect --partition challenge
python3 ml/report_frozen_evaluation.py --partition challenge
python3 ml/diagnose_frozen_evaluation.py --partition test
python3 ml/diagnose_frozen_evaluation.py --partition challenge
python3 ml/plot_frozen_evaluation.py
```

资源收集使用`ml/collect_tabular_resources.py --cluster <ID> --jobs <N> --log-dir
/afs/cern.ch/user/x/xcheng/nu_mu_stage34/logs --prefix <partition> --report-dir
workbook/stage34_energy_ml/resources_<partition> --gpus 0 --cpus 1 --memory-mb 1500`。
提交描述与worker：[ml_frozen_evaluation.sub](../AnalysisZipFramework/submission/ml_frozen_evaluation.sub)、
[wrapper](../AnalysisZipFramework/submission/run_ml_frozen_evaluation.sh)。

| 分区 | cluster / jobs | exit0 | wrapper墙钟总和 s | wrapper CPU总和 s | 最大RSS KiB | 提交至末完成 s |
|---|---|---:|---:|---:|---:|---:|
| calibration | 2187194 / 3 | 3/3 | 92.28 | 54.21 | 366212 | 208 |
| test | 2187195 / 4 | 4/4 | 121.80 | 72.81 | 367636 | 128 |
| challenge | 2187196 / 4 | 4/4 | 130.94 | 73.59 | 367192 | 107 |
| 合计 | 11 jobs | 11/11 | 345.02 | 200.61 | 367636 | 分区依次执行，非单批跨度 |

这里wrapper指标是其被`/usr/bin/time`包围的Python段，包含模型加载、抽取和六模型推理，
不含shell环境setup、解包和上传；200.61s为user+system，Condor远端CPU按秒记录合计202s。
抽取函数内部（不含进程启动/模型加载）总wall237.702706s、CPU148.077281s；
读取1171625个原PHYS事件，保留37359例，按总wrapper wall为108.2807个selected事件/s/分配CPU。
总wall是并行job墙钟之和，不等于用户等待时间。逐文件和逐job计时均落盘，资源表见
`stage34_energy_ml/resources_{calibration,test,challenge}/`，抽取summary/profile同目录按分区命名。

本地smoke抽取6.00s、CPU3.77s、峰值349824KiB；315例的19维、matching、truth p/y/E逐项复现，
六模型预测最大绝对差均为**0 GeV**，见[验收记录](stage34_energy_ml/smoke_validation.json)。
12组随机来源重抽样的七项指标，与显式按整数权重复制事件计算逐项一致至1e−12。
Python编译与shell语法检查通过，图已目视检查；没有以残差筛事件或重新fit。
本地test统计程序20.20s/CPU18.22s/RSS314076KiB，challenge含π控制23.51s/CPU21.86s/RSS367672KiB；
这些在Condor成本以外，未把绘图/打包/合并的未单独计时部分说成零成本。

技术失败：最初smoke误填manifest index=45（不在validation），在`assert rows`处退出，
未读事件、未生成预测、零fit；随后改用实际validation index=47。该次失败独立wall/CPU/RSS
**未测量**，不混入11个正式Condor成功作业的成本，也不声称统计了所有开发成本。
没有正式失败job、重复fit或重复PHYS批处理。19维定义未变，收集器后补profile仅读紧凑cache。

## 限制与阶段决策

1. 来源组独立不等于完整生成谱系独立。旧flux-library存在train/validation入射ν三动量复用证据，
   尚无全生成谱系独立性证明；本阶段不夸称完全生成独立。区间反映当前来源组统计，不含所有系统误差。
2. unit混合不是经亮度/flux归一化的物理能谱，不从本表推断最终能谱测量改善。
   真detector/interaction变体、data控制区、Calo双增益/MIP/强子响应闭合均**未测量/未完成**。
   CaloNu同事件有/无增益**未测量**，普通几何不能代替。
3. 校准后单事件平均风险较好不意味着能量无偏：低真能均值上偏、高真能与高y明显下偏。
   不宣称F6可部署到真实data。stage32/33同面界限不在本阶段重新解释成精确pull。
4. 完整保留输入的F6有独立收益，尤其250–1000 GeV；100–250与高y没有明确ν风险收益。
   预注册总体5%中心门槛未满足，不扩网络/概率/拓扑架构，也不再次追逐TeV精度。
5. calibration/test/challenge现在均已按用途解封。今后不能用这些标签继续调模型后，
   再称它们为新模型的独立确认样本；本阶段结果和两个offset保持冻结。

## 下一步计划（唯一物理主线）

**转向非μ能量分配的新读出控制，先核验并冻结同事件CaloNu有/无实验。**
已有F5/F6固定BDT作参考，不新增tracking变量或扩大高p审计。

- 输入：有CaloNu读出的同一批事件、事件键、truth E/primary p/y、原F5/F6重建量，
  明确几何、材料、conditions、选择及校准；同事件模型只屏蔽/启用CaloNu读出。
  先查仓库与源样本目录，不再询问已说明缺失的flux归一化。
- 执行：先小样本验证读出非恒定、事件join/单位/接受度和来源独立性；配对支持具备后，
  预注册有限同预算BDT有/无比较和新的来源保留分区，再Condor推进。
- 验收：100–1000及两个子层、高y的风险、bias/R68/尾部、来源组配对区间和真实资源成本，
  必须形成读出有/无增益的物理结论；不能拿ordinary/CaloNu几何间差异当读出收益。
  若无匹配输入，明确“未测量”，不造配对、不全量重模拟；此时须先解决输入/conditions问题，
  不能以重复训练旧特征代替物理推进。
