# Stage94：同split输入、表示、架构与直接能量目标的五格实验

日期2026-11-04，起点`7db5aa1`，执行路线§75/信息计划§55和stage93研究修订。任务是一个可归因的有限模型实验，检验输入、表示、架构与直接能量目标。批量训练与评价分别使用Kubeflow GPU和HTCondor四核CPU；未测量项不能用投影代替。

## 1. 输入和预注册边界

复用stage87已有89033兼容记录、46575train/11612cal/13189test、17657隔离及37556/10811/12125唯一incoming，原跨角色source/incoming排重和每key权重1保持。全部1016新增K和missing21/6/5、高端、未确认、high-y、低pz真高E和尾部保留，缺raw/status的旧14435记录不以fitted charge填回。一次方动量仅pz0；既有px/py、q/p、弯折保持，不加p0/p1/pz1或对数动量比。raw11、typed NaN、合法负raw、Calo缺项与status语义不改，pz>50GeV，无ROOT/生成/重建/新样本。

cal在看新模型指标前，以seed2026110494、component内source随机顺序前半select/后半post；共享incoming的post优先，select冲突行退出拟合用途。实测cal_select5443记录/5272incoming/9source，cal_post5746/5539/10source；退出select423记录/389incoming仍在最终全cal报告中。两子集最低能85/97、第二低能418/482、低pz真高能135/138、missing1/5。预设支持门槛每子集≥2000incoming/50最低能/150第二低能/50低pz真高能通过。source和精确incoming不重叠不表示parent/source系统独立；每component连通块和研究池开发限制仍在。

五格A41 raw median/IQR±20、B62同规则、C62 typed变换、D同C的TabM、E同C的3Normal residual MDN。A–D weighted log-MSE，E marginal NLL且点输出exp(mean logE)。A/B/C/E同2×64SiLU；D复用TabM0.0.3、k32、2×64ReLU、dropout0、无数值embedding，参数和计算不假称等容量。C/D/E按物理域：positive log(x/train medianabs)、nonnegative/count log1p、连续signed asinh、离散identity，再train-only median/IQR、不截断；missing/status保持。新增21输入清单见feature_difference.json；逐列变换/scale/各角色missing及|标准化值|>20计数见feature_transforms.tsv。

全部Adam lr.001默认/无decay、clip10、batch1024、NumPy seeded permutation、最多300epochs/每5epoch验证/patience30epoch。相同MLP使用同规则，E checkpoint也按cal_select加权点MSE最低而非test或NLL；训练曲线保留point与objective。五个主seed2026110494；在新test forward/风险前按cal_select原两低E/全体/困难风险上限归一化比值的最大值、平均值、总体MSE依次排序，最多2格补2026110495/496；固定3seed点均值集成，最多9fit。ensemble offset单独在cal_post一次定义；E若入选，其ensemble密度为等权seed混合，统一平移所有分量。

每个点模型/集成仅cal_post incomingweighted mean(logtruth−point)一次全局offset，E密度/均值一起平移，不做分箱/真值校准或test选谱。传统和direct原样缓存、direct_raw共同postoffset对照分列。概率评价目标是同incoming经验谱，不另加nominal reweight；总体完整PIT和cal定义的X(pz、Calo、活动、质量/缺失)组为可靠性诊断，真E/y组PIT只作真值条件描述，不要求其中均匀。

## 2. QA、执行与资源

固定40沿stage92 QA身份＝21train missing＋6cal missing＋原train13；五格前向/反向finite，0optimizer。T4测得batch1024（重复同40身份，非新事例）forward/backward median A/B/C/D/E=.001316082/.001222719/.001217932/.003673485/.002304749 wall秒，参数9729/12417/12417/28608/12937，网络输入85/127/127/127/127维。MDN独立密度差4.440892e−16、九head坐标双边差分最大1.938028e−10通过。该40预处理只作接线QA，正式变换仅在完整train拟合并核A与旧归一化完全一致。

以最慢batch×46×300×9×5＋180秒投影2461.234194 wall秒准入（不是实测训练保证），GPU任务上限7200wall秒/1GPU并发、阶段CPU21600秒/紧凑20MB。实际48,253,081bytes包完整QA通过。首个训练包QA因工具把PYTHONPATH覆盖掉LCG导致numpy不可导入，0optimizer/0batch作业；修为追加LCG环境后通过，数值代码未变、没有模型试训。依赖使用已有本地wheel，无新网络下载。

GPU使用用户已授权Kubeflow同H100 NVL MIG3g.47gb，平台自动配置22CPU/63G内存，训练torch/BLAS线程1。九fit合计52440 optimizer steps；外层含import、完整重组、全部训练/验证/最终forward实测112.157179 wall秒、82.837277 CPU秒，peak RSS1839624KiB。worker内部104.369529 wall秒、80.918701 CPU秒与外层嵌套，不能相加。各fit资源见fit_summary.tsv，最大allocated GPU peak222.694336MiB，非整卡物理显存占用或CUDA context峰。

首个4CPU统计作业9667459在import阶段缺latent_transfer_diagnostics.py而exit1，事件统计尚未开始；补齐依赖并实际解包导入后另提交9667460。后者为补独立审计被hold，但实际已启动32 execute-wall秒/61CPU秒；原备注“before first execution”与日志不符，已保留真实eviction记录。release后相同作业完成统计和独立审计，最后因初次失败留下876byte同名结果，xrdcp未允许覆盖而exit50，结果表未回传；本次执行另用239CPU秒/83remote-wall秒。为回收完整结果，修正xrdcp --force，使用同一冻结统计包另交9667473；没有重训、追加候选或依据test改选择。原始失败/中断与修复分别见history_report_import_failure.json、report_eviction_before_audit.json、report_transfer_correction.json和history_report_transfer_failure.json。

CPU统计申请4CPU/12GB内存、4process，BLAS每process1线程，按role/stratum分片，共享fork只读数组，每key聚合后复用同一500draw。独立实现用bincount复算，区别于报告的scatter矩阵聚合；与主统计顺序执行，各自内部四进程。所有大批量走batch，只交互做≤40身份QA。小QA的同8任务1/4process输出逐项一致，wall .157801/.086427秒，此结果不能外推完整任务加速比。

## 3. 实际训练、校准和评价

### 3.1 九次有限拟合、选择与预处理

下表的seed尾数494/495/496分别表示2026110494/495/496。学习曲线完整保留为learning_*.tsv，checkpoint核对为每5epoch cal_select点MSE严格最小者，earlystop均满足30epoch无改善。学习曲线/fit记录中无test参与，九个唯一fit、52440steps闭合。E与B在任何新test forward前按冻结排序入选，worst normalized risk分别1.526485/1.532496；C/D/A为1.590321/1.706176/1.652206。该排序使用raw点输出，不按后续test优劣补D种子。

|格/seed尾数|参数量|epochs / best|steps|wall秒|GPU allocated peak MiB|
|---|---|---|---|---|---|
|A/494|9729|105 / 75|4830|10.899571|86.197754|
|B/494|12417|105 / 75|4830|6.020346|93.858887|
|B/495|12417|90 / 60|4140|5.169669|94.578613|
|B/496|12417|100 / 70|4600|5.775762|94.676270|
|C/494|12417|185 / 155|8510|10.703095|93.956543|
|D/494|28608|245 / 215|11270|37.754372|222.694336|
|E/494|12937|95 / 65|4370|7.984613|94.310547|
|E/495|12937|120 / 90|5520|8.975995|94.412109|
|E/496|12937|95 / 65|4370|7.105565|94.513672|

A/B在train截断的单元分别18352/31155，cal5152/8532，test6323/10371。C/D/E变换后仍有10960/2923/3465个标准化绝对值>20的单元，但**没有截断**；这些是单元数，不是独立事件数或缺失数。各输入方案每角色NaN单元42/12/10，对应事件21/6/5；median/IQR与尺度全部只拟合train，A与stage87逐数完全一致。原typed清理将位置-999、正域/计数中的非法负值等变NaN；raw允许合法负读出并按wave status处理，不能把所有-1都当占位。新增21列完整列于feature_difference.json，VetoNu reduced charge沿原审计合同作为额外读出，11路普通scintillator charge全部是raw。

cal_post全局offset：A .012615405、B .009155534、C .015230804、D .000062289、E .020178393；B/E集成分别.016395221/.021153708，均为自然对数能量偏移，无量纲。传统/direct_raw同后处理offset为.126269911/.025841401，原direct_cal不覆盖；完整值、额外seed和拟合支持见offsets.tsv。集成先平均三seed log点值，再单独拟合一个offset；E密度为九个Normal等权seed混合，其各分量均值加同一offset。

### 3.2 同一test完整比较

以下均为incoming加权log-RMSE，无量纲，50–100/100–200 GeV指**真能量**。对应记录数183/856，全体13189、低pz真高能297、high-y385、未确认468。低pz指50<pz0<100 GeV；这些真值风险组不是部署时的gate。所有格使用postoffset结果，原传统/direct与stage92保持各自原样。

|模型|50–100 GeV|100–200 GeV|全体|低pz真E≥200|high-y|未确认|
|---|---|---|---|---|---|---|
|传统pz/.8|0.145661|0.247937|0.557190|1.887790|1.618799|1.638613|
|原direct BDT|0.282644|0.246329|0.287491|0.658177|0.609395|0.551305|
|direct同postoffset|0.283112|0.246685|0.287459|0.657895|0.609173|0.551132|
|stage92准确后验|0.165630|0.232842|0.326058|0.826918|0.781673|0.665024|
|A|0.290127|0.280065|0.305048|0.697933|0.664641|0.583452|
|B|0.283979|0.275297|0.301516|0.691025|0.651332|0.574241|
|C|0.278092|0.270090|0.299024|0.689558|0.634970|0.569016|
|D|0.296680|0.251313|0.294126|0.693514|0.624048|0.569645|
|E|0.285933|0.256110|0.292090|0.668651|0.622983|0.555775|
|B三seed|0.282077|0.266121|0.296658|0.684633|0.642857|0.564202|
|E三seed|0.276027|0.251510|0.289843|0.671125|0.616675|0.554151|

完整补充分层如下，仍为test incoming加权log-RMSE；全部模型、raw/offset与两种权重另见selected_metrics.tsv/metrics.tsv。

|层|记录数|E三seed|direct|
|---|---|---|---|
|E200_inf|12150|0.292797|0.290487|
|pz50_100|659|0.508218|0.498966|
|E3200_6400|264|0.658846|0.683271|
|input_missing|5|0.312064|0.203231|

真高端指3200–6400 GeV；missing只有5条，不能把其seed/表示差异解释为总体缺失鲁棒性。C在missing层.381194与B .207393的差异也只作稀少支持描述。

cal并没有支持“低能恢复”：E集成cal最低能.288105778，对应test .276027157；raw最低能cal/test .273599233/.260288756。E集成全体raw→offset的test RMSE .291453704→.289842620，但最低能.260288756→.276027157，100–200 GeV .241230413→.251509778。**全局offset减少整体残差，同时加重低能上偏**，所以不能用选一个test offset或回退raw来宣布通过；前后结果均保留。

### 3.3 可归因的增量与seed波动

配对为相同500次component内incoming重抽，全部重建视图一起移动。区间是在固定本次拟合/校准/来源及研究选择条件下的95%区间，不是模型家族或source系统不确定度。

- **B/A（补齐输入）**：全体RMSE比.988423736，区间[.980350280,.996793238]，本次拟合的总体改善1.157626%；≥200比.988911138，[.980799133,.997372345]。最低能比.978807426，[.899213202,1.075603999]，没有确证低能增益。补齐输入有用，但没有解决最低能；输入层参数量随维度增加，不称等参数实验。
- **C/B（typed表示）**：全体比.991733757，[.982293925,1.000675976]，本轮区间仍含1。最低能.979272263，[.908047088,1.053484362]；不能把中心值改善称为稳定表示收益，也不能据此否定全部typed表示。
- **D/C（TabM方案）**：全体比.983619815，[.976471818,.992437198]；100–200 GeV .930477837，[.900530742,.969729462]。最低能却为1.066838405，[.997090215,1.152740669]，低pz真高能1.005736496，[.972810255,1.042012311]。本次结构方案在主体和第二低能有效，没有建立困难组或最低能联合收益；D只有一个seed，参数28608对12417，不单归因为集成或某个结构组件。
- **E/C（直接能量MDN方案）**：全体比.976812136，[.969199832,.985863201]；100–200 GeV .948238904，[.913107740,.986322931]；低pz真高能.969679572，[.934549986,1.001884906]。最低能1.028195305，[.952486645,1.095689716]。输出族、目标和residual参数化共同变化，不声称NLL本身单独造成收益。

预注册B/E三seed单模型test结果如下；没有按test挑最佳seed，三seed集成规则不变。

|格/seed尾数|50–100 GeV|100–200 GeV|全体|低pz真E≥200|high-y|
|---|---|---|---|---|---|
|B/494|0.283979|0.275297|0.301516|0.691025|0.651332|
|B/495|0.296312|0.278978|0.300868|0.694500|0.645245|
|B/496|0.288835|0.262219|0.302542|0.693686|0.660177|
|E/494|0.285933|0.256110|0.292090|0.668651|0.622983|
|E/495|0.276855|0.252723|0.293999|0.682367|0.622057|
|E/496|0.269887|0.252132|0.292170|0.677342|0.620637|

E三seed全体单模型范围.292090–.293999、最低能.269887–.285933；B对应.300868–.302542和.283979–.296312。种子波动真实存在，但三次不代表完整重训分布；A/C/D未追加seed。E集成相对stage92的全体/低pz真高能/high-y比值分别.888929[.871284,.902770]、.811599[.768676,.852674]、.788918[.751987,.829163]，却把最低能变为1.666524[1.478641,1.953064]。这是风险取舍，不是能同时保留旧后验低能优势的升级，也不把多个条件比较当作经多重选择校正的发现。

### 3.4 原门槛与正负尾完整保留

11个单seed或固定集成候选均未通过所有层的RMSE+双向tail联合要求；88条gate见gates.tsv。下面列E集成，原七层加低pz真高能，没有下降门槛。

|层|参考/上端限值|E三seed比值上95|RMSE通过|双向tail通过|
|---|---|---|---|---|
|all|direct_cal/1.01|1.015960|False|True|
|E50_100|traditional/1.05|2.249753|False|True|
|E100_200|traditional/1.05|1.099747|False|True|
|E200_inf|direct_cal/1.03|1.015419|True|True|
|pz50_100|direct_cal/1.03|1.040436|False|True|
|pz50_100_trueE200|direct_cal/1.03|1.046307|False|False|
|high_y|direct_cal/1.03|1.036155|False|False|
|unconfirmed|direct_cal/1.03|1.033699|False|True|

E集成全体/direct比1.008179，条件区间[1.000798,1.015960]，虽中心值只高.8179%，上端仍超过1.01。采用共同postoffset direct后为1.008292[1.000915,1.016071]，结论不由旧基线后处理造成。最低能/传统上端2.249753远大于1.05；第二低能1.099747也未通过。B集成八层RMSE全部未过（全体上端1.039601、最低能2.283067）。

E集成最低能median bias +19.212418%、R68 13.424818%、正/负tail50 9.289617%/0%；传统为+14.060708%、10.330065%、0%/0%，direct为+19.882536%、18.178848%、13.114754%/0%。核心比direct变窄，仍明显劣于最低能传统风险；不能据R68替代RMSE与尾。

E集成低pz真高能median bias −21.966986%，正/负tail50 11.501032%/25.007372%；相对direct的总/正/负tail差条件上端+4.493944/+2.712061/+3.628938 pp，均越过+2 pp。high-y对应+3.745037/+1.389279/+4.079430 pp，负尾保护失败。全体的三种tail上端仅+.448144/+.372577/+.201478 pp，不能用总体保护掩盖困难层。

### 3.5 直接概率输出的可靠性

E的密度/CDF为解析Normal混合；quantile二分的最大CDF残差9.270362e−15。独立固定40身份检查已覆盖九head梯度、单Normal分位数及共同平移不变性；没有重开stage88–91的旧数值链，也没有计算stage92的新moment。该CDF残差认证本模型分位数求解，不证明分布真实。

概率评价使用incoming经验目标谱、与E训练权重一致，无额外nominal-prior重权。X的Calo/活动三分位边界只用outercal X得到（X_calo_groups.json、X_activity_groups.json），不使用Y或test分位数。下表是E集成postoffset的test；完整raw/各seed、cal及十箱PIT见coverage.tsv、scores.tsv、PIT_reliability.tsv。

|test观测X组|记录数|68coverage %|90coverage %|mean PIT|
|---|---|---|---|---|
|all|13189|62.602337|86.253883|0.491101|
|X_pz50_100|659|57.582418|84.124111|0.479552|
|X_pz100_200|1556|60.258446|86.628703|0.469614|
|X_pz200_plus|10974|63.285468|86.334455|0.495132|
|X_calo_0|4238|63.321315|86.834864|0.483772|
|X_calo_1|4394|62.102470|85.798967|0.491412|
|X_calo_2|4552|62.413754|86.178842|0.497685|
|X_activity_0|4103|61.244626|86.052348|0.473804|
|X_activity_1|4515|63.381467|86.924643|0.496859|
|X_activity_2|4571|63.103928|85.761457|0.501747|
|X_status_other|1002|62.064433|84.297662|0.511092|

全体68/90coverage条件95%区间分别[61.681838,63.398361]%/[85.662856,86.912447]%，低于名义68/90%。mean PIT .491100702的条件区间[.485794484,.496036323]；十箱质量依次.129746/.103766/.101511/.090268/.086969/.088819/.087830/.094514/.095474/.121104，呈两端增多。68/90 mean logE宽度.433694182/.754108721，无量纲。说明当前概率输出仍有区间/形状或偏差失配，不能仅凭均值接近.5声称可靠，也不能将问题唯一归因温度。

E集成test NLL(raw/offset)=−.114574734/−.107503598、cal=−.167737982/−.155169210；offset改善点MSE未改善本次NLL，均为logE密度的每incoming平均无量纲负对数分数。没有NLL增益区间或局部概率校准，本轮不追加校准优化。真E/y层PIT只保留为真值条件描述，不要求其中均匀，也不拿这些组单独否决后验；这里总体和X组已足以说明可靠性仍不足。实际response/systematics、跨source可靠性、准确CRPS：未测量。

## 4. 验证、资源与产物

成功CPU作业9667473首次exit0/1start，4CPU/12GB、80remote-wall秒/223remote-CPU秒；任务内GNU time为76.86wall秒、167.36user+54.51sys秒、peak RSS413056KiB，scope不同不相加。主报告83个role/stratum任务：全流程54.284104wall秒，子进程151.100112CPU秒，父进程15.667622CPU秒；其中并行段39.138680秒，平均实际子进程占用3.860634核。独立审计13.959241wall秒/49.283593child-CPU秒，约3.530535核。完整任务单核对照加速比未测；四核得到实际使用，不把请求核数当加速比。

全部Condor尝试含import失败、eviction和传输失败共525CPU秒；九fit外层82.837277CPU秒、已记录本地计时49.41CPU秒，三者不重叠合计657.247277CPU秒。轻量编辑、最终包仅import检查、若干shell和文档操作未逐项计时，因此这是记录范围合计，不冒称完整进程审计。无追加训练、无新ROOT读取。已记录CPU及GPU worker wall均低于冻结的21600CPU秒/7200GPU任务wall秒；平台分配的22CPU不是训练并行数。实际EOS物理读字节、整卡context峰、完整相同工作量单核加速：未测量。打包/传输逻辑字节不代替EOS I/O；成功Condor记录接收19672944bytes，含19672827byte冻结统计包及启动脚本。

独立实现按incoming的bincount聚合重算14992个点指标/配对区间/尾上端，最大差7.105427e−14；旧传统/direct/bounded表3024值复现，最大差1.421085e−14。11个模型/集成的cal_post offsets独立复算通过，九fit checkpoint、epoch/steps及E/B排序复核通过；4488条点指标、4404条配对、88条gate有限。未复算所有概率分位数的独立积分，因为本轮新模型是解析混合；原Normal检查和CDF残差对应其数值验收范围。

关键产物：

- [主比较与学习曲线图](stage94_energy_ml/architecture_comparison.svg)、[种子训练曲线](stage94_energy_ml/seed_learning.svg)。
- [完整点指标](stage94_energy_ml/metrics.tsv)、[配对](stage94_energy_ml/paired.tsv)、[联合门槛](stage94_energy_ml/gates.tsv)、[紧凑主层表](stage94_energy_ml/selected_metrics.tsv)。
- [概率覆盖](stage94_energy_ml/coverage.tsv)、[完整十箱PIT](stage94_energy_ml/PIT_reliability.tsv)、[NLL](stage94_energy_ml/scores.tsv)。
- [合同](stage94_energy_ml/protocol.json)、[划分](stage94_energy_ml/cal_partition.json)、[fit与checkpoint](stage94_energy_ml/fit_summary.tsv)、[offset](stage94_energy_ml/offsets.tsv)、[数值验证](stage94_energy_ml/independent_validation.json)、[资源](stage94_energy_ml/resources.json)、[存储](stage94_energy_ml/storage.json)。

九模型及训练/评价点预测在ml/artifacts/stage94；evaluation_input/cal_partition紧凑缓存在ntuples/energy_ml_stage94，不入Git。head只保留完整cal/test24801条，train头可由保存模型/预处理/原缓存重算；没有从点指标中删除训练事件。回收校验通过后去重本阶段打包和返回归档，最终逻辑字节见storage.json，≤20000000bytes；没有删除原输入、模型、完整表、stage54五项或历史后缀。

主要执行入口（依赖使用CVMFS和已有TabM/rtdl wheels，包内保留相同目录结构；不直接重跑已完成fit）：

```bash
source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
python ml/compare_energy_architectures.py prepare-protocol
python ml/compare_energy_architectures.py qa
kubectl --context ml-prod -n xcheng create -f AnalysisZipFramework/submission/ml_architecture_kubeflow.json
condor_submit -terse AnalysisZipFramework/submission/ml_architecture_report.sub
```

训练worker由run_ml_architecture_study.sh启动；统计、独立审计和作图由run_ml_architecture_report.sh串行调度三个Python入口，前两者各四进程；最大wall1770秒、单作业+MaxRuntime1800秒。现有结果不会被这段说明自动重算。复现须先按本报告输入清单打包并放入sub所指AFS spool脚本和EOS输入路径；GPU包包含stage55/56/70/81/82/83缓存、stage87 split/normalization/BDT缓存及stage90/92 QA/cal输入，统计包只需紧凑evaluation/partition/预测/heads、原stage87/92预测及fit/学习曲线。包字节与代码一致性及导入QA分别保留package_QA.json/report_final_package_QA.json。

## 5. 阶段结论与下一最小任务

本轮测得当前摘要上的若干学习增量，**不能把原后验视为已优化完毕。** 补齐输入对本次总体有可测增量，TabM/直接能量MDN相对匹配MLP也在总体和第二低能得到条件配对增量；typed变换单独增益尚未确证。这五格仍未解除最低能与主体/困难风险的取舍：E改善stage92困难侧，却明显损失其低能优势；E集成仍稍逊同split direct，最低能远逊传统，概率区间也欠覆盖。因此保留既有部署，候选不自动晋升，不称现有观测信息极限或传统在所有能量最优。

程序方面，split/weights、NaN/status、pz0/raw合同、checkpoint选择、配对算法和基线算术均闭合；工程失败都留证，不把缺依赖/回传错误写成物理失败。物理方面，低pz可对应低能或大transfer的高能、全局损失/offset对两侧产生竞争，与观测风险相容；**尚未实测哪条额外轨迹或关联能够解除歧义**，本轮不能把该解释写成已证明因果。单seed控制、三个补充seed、同一开发池和source相关限制，亦不能支撑最终物理显著性。真实data迁移、interaction/FSI、材料/Calo/接受度/背景及新blind确认未测量。

按stage93 §6.4“五格无联合收益”分支，下一stage95转向**可部署轨迹候选及hit/外推关联的信息合同与紧凑可用性测量**，本阶段不执行它。输入是现有已知PHYS/审计source清单、当前split/incoming联结和output_columns全轨迹定义；先≤40个固定train/cal身份核实际载荷/单位/状态/关联可靠性，随后冻结来源覆盖的小批量，通过≥4核Condor按源分片只提取紧凑候选与共享hit/几何关联摘要。保留已有全选择与K支持，不复用旧普通全SP Deep Sets作为新关系信息，不新增p0/p1/pz1一次方量；多候选的允许动量仍只用各候选pz0及已允许的px/py、q/p、弯折。

验收需给出实际分母：全轨迹/候选数、有效载荷与缺失率、候选间共享hit/重复率、通道与station/layer一致性、leading与可区分候选比例、选中/困难组支持及可部署数据语义。若真值到轨迹关联确实可核，则只作为诊断给leading误选和候选oracle上限及其统计依据；不可核时写未测量，不猜真μ身份。冻结一种紧凑表示与后续一次匹配输入的消融方案，先证明买到了新信息再训集合/GNN，不在本轮追加模型或重新对test选择。下一轮先做代码/schema/小QA，正式提取资源依据实测准入，默认≥4核/每进程1线程、紧凑≤20MB，不启动新G4/xAOD副本；独立支持仍为最终确认需求，不是继续开发前置。
