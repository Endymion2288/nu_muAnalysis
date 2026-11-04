# Stage89：完整既有cal/test的冻结后验准确推断与配对评估

日期：2026-11-04。起点`82ca171`，遵循路线§70、信息预算§50与stage88交接。本轮**0能量fit、0校准优化、0网络forward、0新ROOT/生成/重建**。主模型、b/T、名义prior和原角色保持；精确CRPS未测量。不将已曝光研究池称新blind，不把积分修复当作32点训练/校准优化偏差已修复。

## 1. 目标与冻结定义

stage88证明GH32大量CDF/quantile/density误差，GH256也未全部达标；但552子集的准确积分没有保证能量风险改善。本轮只回答：在原完整cal11612/test13189上，固定同一个stage87后验、原b/T和名义prior，准确推断究竟改变多少低E、困难侧、尾部、覆盖与PIT？不得从stage88的9条低能或512cal替代完整评估。

主参考为**未改动**的`ml/posterior_numerics.py:Reference`：s方向自适应积分、解析r逆变换/Jacobian、原split points、epsabs/epsrel=1e−10、analytic normal尾界和safeguarded quantile root。b=**.011721733230708156**、T=**1.2001641697078562**，原nominal bin ratios全保留；GH32保存的五quantile只作初始化/对照，不据test选择节点/算法/先验。代码与stage88已提交版本逐字比较相同，无SHA扫描。

主输出为median、q05/q16/q84/q95、PIT、名义及training-prior log-density/NLL、ESS，配对原同split新direct62和传统pz0/.8预测；不运行新网络或旧F7。一次方动量仍仅pz0、允许px/py/q/p/弯折、raw11/typed NaN/Calo缺项、pz>50 GeV与困难侧均不改。已交付1016K原支持保留，旧K生产禁令/时限不恢复。

## 2. 实际样本、身份与状态

输入`ml/artifacts/stage87/{posterior_parameters,predictions}.npz`与`ntuples/energy_ml_stage87/split.npz`，保存head.row与compact predictions.row逐项相等，再按pooled row联结原group/key/component/role/weight。status由stage56 raw/readout及stage70/81/82/83现成support原生origin_row联结，未以fitted charge替代。stage87全标签physical/unknown0审计保持，truth不作部署输入。

客户端仅切分已有紧凑数组、核身份/权重并按角色打包；全部逐事例积分、全量指标/500draw及独立复核通过HTCondor执行。两个包只传各自角色head/必要标量与共同的一个cal控制事例，不传train head或重复模型文件。

| 角色 | N | 唯一incoming | canonical组/连通块 | 权重和 | record ESS | missing | fit失败 | wave-invalid | Calo-invalid | K记录 |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| cal |11612|10811|19/3|10811|11198.044296|6|807|0|6|5722|
| test |13189|12125|19/3|12125|12641.593732|5|997|0|5|7091|

cal/test group、精确native-MeV incoming及key跨角色无交集；每角色所有重建视图保留，每key总权重1。record ESS不是独立生成事件数。六/五缺失、未确认、fit失败、低pz真高能、high-y和高端全部保留；只标数值未知，不因表现删除或以GH32替代。wave-invalid当前0，其物理风险不作测量结论。

## 3. 先QA再提交

事前固定原首40cal身份，与stage88双向认证的40个参考值逐项核对，五quantile/PIT/log-density最大差 **0**；新算一个reverse控制CDF差 **2.775558e−15**、log-density差 **1.088347e−10**。40例完整主推断含逐例端点/单调性检查 **11.794594 CPU s/11.995261 wall s**，完整QA **12.210291 CPU s/12.506653 wall s/134.839844 MiB**。未计算test风险，算法/主参数在test全量前冻结。

协议在正式提交前保存至`workbook/stage89_energy_ml/protocol.json`。每个实际传输包再核完整角色N、每key权重1及同一cal控制的参考quantile/PIT、真实数值元数据JSON序列化；两个包均通过，0fit/无test试探。正式包cal/test **1983696/2220194 bytes**，角色input NPZ **1889757/2143072 bytes**。

唯一cluster **9667192**，proc0 cal、proc1 test，≤2并发；实际ads各1CPU/3000MB/MaxRuntime5400s，worker soft/hardCPU5200/5300s、wall timeout5340s，0自动retry。累计CPU预算10800s、最终紧凑≤20,000,000bytes。stage88 cal512主参考.337494984秒/例、24801外推8370.213102CPU秒仅规划依据，实际资源见§6；本次40cal速度不冒称全test速度。

## 4. 指标与不确定度

沿用原log-RMSE、relative bias/R68、总/正/负tail50定义：正为(Epred/Etrue−1)>.5，负<−.5。incoming加权主值，普通逐记录次要；低真E50–100/100–200 GeV与同reco pz50–100的真高E≥200分开，high-y=f≥.8、未确认、missing、fit/Calo状态、高端逐层报告。

同一角色原key内保留全部视图，component内incoming重抽样500次，seed=2026110387+角色code(2/3)，固定预测/b/T/prior。每个角色仅pi/k/charm各1个source/incoming连通块，source95继续“未测量”；条件区间不覆盖跨key parent/source相关、重训、校准估计、真实response或研究选择。稀少missing的无事件draw单列有效draw数，不用稀少子层认证总体。

主门槛不降：两低E/传统RMSE条件95上端≤1.05、all/direct≤1.01、≥200/低pz/低pz真高E/high-y/未确认≤1.03，七层及额外低pz真高E的总/正/负tail50差上端≤+2pp。68/90覆盖下端≥名义−5pp、meanPIT95含.5；稀少不认证。PIT十箱、quantile可靠性、宽度、名义/training-prior NLL完整交付，不以总体覆盖替代联合风险。

## 5. 正式实际结果

### 5.1 完整test实际结果

proc1 **一次正常exit0、无重试**；13189/13189逐例数值认证，原5条缺失全保留。指标见`test/metrics.tsv`、`test/paired.tsv`、`test/coverage.tsv`、`test/scores.tsv`，图见[准确推断对照](stage89_energy_ml/accurate_posterior.svg)。下表均为incoming加权log-RMSE（无量纲）：

| test层 | 记录N | 传统 | 新split direct | 后验GH32 | 后验准确 |
|---|---:|---:|---:|---:|---:|
| true50–100 GeV |183|.145661386|.282644343|.172272930|.169295525|
| true100–200 GeV |856|.247936985|.246328767|.232802758|.231280537|
| all |13189|.557189970|.287491236|.326580146|.326782523|
| reco pz50–100 GeV |659|1.275309885|.498965866|.596988573|.597693291|
| 同低pz且true≥200 GeV |297|1.887789515|.658177334|.825772791|.828213265|
| high-y |385|1.618799491|.609394510|.805320967|.807754127|
| 未确认 |468|1.638613231|.551305420|.688140023|.688944558|
| true3200–6400 GeV |264|.995785214|.683270830|.758164403|.758477352|
| input-missing |5|.253033508|.203231447|.226801851|.226801412|

准确/GH32最低能RMSE比 **.982716929 [.966235679,1.002900836]**，未证固定预测条件改善；第二低能 **.993461328 [.989105161,.996817848]** 有小幅条件改善。all **1.000619687 [1.000108997,1.001212531]**、high-y **1.003021355 [1.001076114,1.005418998]** 小幅变差；低pz真高能 **1.002955383 [.999956597,1.006173556]** 未证变化。不把准确积分的物理风险改善当成数学必然，也不把这些小幅区间解释为source稳健或独立确认。

最低能median bias +8.109339%、正tail50 2.732240%，direct分别+19.882536%/13.114754%，确有互补收益；但相对传统的RMSE条件上端 **1.442100>1.05**，最低能保护仍失败。第二低能/传统上端 **1.011943≤1.05** 仅该条件保护通过。all/direct上端 **1.160113>1.01**；≥200/低pz/同低pz真高能/high-y/未确认上端 **1.178789/1.256784/1.340732/1.409985/1.335194** 均超过1.03。不能用第二低能或总体coverage通过宣称联合恢复。

原总/正/负tail50保护中，all及两低E/≥200相对direct条件上端均≤+2pp；低pz、同低pz真高能、high-y、未确认仍失败。同低pz真高能总/正/负tail差上端 **+17.879739/+5.129332/+15.006049pp**；high-y **+21.125703/+5.561430/+17.389294pp**。准确后验同低pz真高能负tail **35.122383%**（direct24.329106%），high-y负tail **31.585221%**（direct18.069130%）；全部保留，不以低pz硬切传统来掩盖。

准确test整体68/90coverage **68.819244% [67.954333,69.661718] /90.951065% [90.474677,91.437320]**，meanPIT **.522151542 [.517459303,.526744990]** 不含.5。最低能/第二低能meanPIT **.330496797/.381377145**；同低pz真高能/high-y **.629871801/.630641839**，体现两类truth状态的PIT分布不同，不等同于可由部署观测量完全区分。high-y68/90coverage **67.461263%/85.864124%** 的条件下端 **62.298663%/82.236813%** 仍低于63%/85%门槛。true3200–6400仍 **22.343750%/59.947917%**，与GH32相同；该严重欠覆盖不是本轮积分修正可消除的。missing5例覆盖 **22.222222%/44.444444%**（incoming权重）且区间宽，不认证。

统计解释需区分：按true E或truth transfer分层后，即使一个条件后验正确，PIT也不必在这些truth子层均匀、中心区间也不必逐truth箱恰等于名义覆盖。这里沿用事前工程保护门槛，并把truth分层当风险定位；不能仅凭某truth层PIT偏离.5就证明后验失准。全体PIT、同一部署观测量条件下的诊断、点估计/尾部及目标覆盖要求需共同解释；本轮联合失败不依赖单个truth层PIT判据。

test全体名义logE NLL GH32/准确 **−.020506873/−.043037457**，training-prior **−.020899102/−.043427593**。准确NLL下降不代表重新训练/校准最优或风险门槛通过；主b/T和训练头始终未变。

### 5.2 cal与全量数值认证

proc0同样**一次正常exit0，无重试/恢复**。cal/test全部 **24801/24801**通过逐例认证、exception0、quad precision flag0，原missing6/5全部通过数值检查；这只认证该已训练概率模型的数值推断，不认证真实响应或物理覆盖。

| 完整角色数值证据 | cal N11612 | test N13189 |
|---|---:|---:|
| GH32 PIT差>1e−4记录 |2899|3176|
| GH32任一quantile logE差>1e−3记录 |5198|5438|
| GH32 log-density差>1e−3记录 |3537|3866|
| 最大PIT差 |.038974041|.039168732|
| 最大quantile logE差 |.204998954|.218637202|
| 最大log-density差 |3.236787679|3.732729847|
| 最大quad误差估计 |6.099533e−11|6.445630e−11|
| 最大解析尾界 |1.012698e−22|2.574584e−22|
| 最大quantile root残差 |1.999632e−10|1.999628e−10|
| 最大CDF端点差 |1.059286e−11|7.061018e−13|
| 最小相邻CDF增量 |2.105103e−155|3.632967e−150|
| 缓存后实际新CDF调用 |274543|309768|
| 被积函数实际计算 |172143783|192990651|

合计GH32 PIT/quantile/log-density超限 **6075/10636/7403**条；全部保留，没有用这些差值挑事件/分层/主方法。详细逐例`{cal,test}/numerical_checks.tsv`、紧凑`numerical_summary.tsv`与原row联结保留。

完整cal传统/direct/GH32/准确all log-RMSE **.533278863/.278756681/.311120438/.311413637**；最低能 **.145329395/.299854502/.236479558/.235912479**、第二低能 **.229156109/.262429444/.225755934/.223852298**。准确同低pz真高能/high-y **.746843700/.783272588**（GH32 .743677835/.779808872），与test均不支持积分修正足以消除困难侧风险。cal最低能准确.235912与test.169296并不相同，不把它们当新独立确认或据test挑校准；具体来源/混合与统计原因未在本轮唯一分解。

cal准确68/90coverage **69.164894%/91.642000%**，meanPIT **.510276055**；高端3200–6400仅 **35.897436%/64.102564%**。cal missing6条准确log-RMSE **.213056704**，覆盖 **50%/80%**（incoming加权），稀少不认证。完整cal名义NLL GH32/准确 **−.062589759/−.085742022**，training-prior **−.063295544/−.086449009**。移除名义prior所得完整cal GH32目标与stage87保存的`cal_logE_NLL`差 **1.387779e−17**，独立验证先验归一化、权重与角色；差值不是重新校准收益，b/T没有改变。

## 6. 命令、资源、程序验证与留存

```bash
/usr/bin/time -v -o /tmp/stage89_qa.time \
  bash /tmp/stage69_python.sh ml/accurate_posterior.py qa
# 小样本通过后冻结protocol与真实资源，再实际包检查/提交：
/usr/bin/time -v -o /tmp/stage89_submit.time \
  bash /tmp/stage69_python.sh ml/accurate_posterior.py submit
# 全量作业结束后取回同一角色结果，不重新推断：
xrdcp --silent root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage89/result_cal.tar.gz /tmp/stage89_cal.tar.gz
bash /tmp/stage69_python.sh ml/accurate_posterior.py collect --role cal --result /tmp/stage89_cal.tar.gz
xrdcp --silent root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage89/result_test.tar.gz /tmp/stage89_test.tar.gz
bash /tmp/stage69_python.sh ml/accurate_posterior.py collect --role test --result /tmp/stage89_test.tar.gz
```

复用CVMFS LCG109 numpy/scipy，BLAS单线程，正式计算不依赖torch/XGBoost，不安装或重编译。QA外层13.77CPU秒/17.43wall秒，submit外层4.84CPU秒/9.19wall秒，和内部计时重叠不重复相加；初始AST/metadata/文档等未完整计时。正式实际资源如下，完整证据`resources.json`、两角色`job.time`及Condor history：

| 资源 | cal | test |
|---|---:|---:|
| remote CPU s |5175|3762|
| execute wall s |5221|3789|
| 全worker CPU/wall s |5172.940063/5215.080352|3761.107859/3783.752997|
| 推断CPU/wall s |5151.605878/5193.569978|3738.148327/3760.627135|
| 推断记录/CPU s |2.254054|3.528217|
| worker peak RSS MiB |186.351563|202.093750|
| 独立复核CPU s（已含worker） |11.517546|10.607297|

remote累计 **8937CPU秒、9010wall秒（两作业之和，非历时）**；已逐项计时外层QA/提交/报告smoke/收集/绘图/汇总 **30.13CPU秒**，与remote合 **8967.13CPU秒<10800**。内部计时不重复加入；全部metadata/监测/文档/静态检查与XRootD客户端未全计时，不能称严格所有命令总量。cal worker CPU距soft5200约27.06秒、执行wall距5400约179秒，本轮没有触限；首500cal耗时高并非故障，不能据此提前放弃。预测外推3915.56/4440.49CPU秒与实际5151.61/3738.15不相等，样本/节点/机器和额外检查成本没有逐项因果分解，不将外推当保证。

两个角色各 **2908**项独立指标/区间检查，其中各 **1008**个原stage87基线值复现；合 **5816**项、最大差 **4.263256e−14**。每角色500incoming draw逐项重建、全部key权重1、原GH32/direct/传统指标及GH32 coverage/PIT闭合；新准确值也逐项独立算术核对。包内8源文件×2角色与本地逐字相同，原stage88数值核心与HEAD逐字相同。提交前额外40cal报告smoke只测试表/JSON路径（临时归一权重/借GH32 ESS、未调用完整角色旧基线校验），不是新物理测量；正式完整验证均在worker执行。客户端曾用不存在的`python`启动静态检查一次失败，随后用`python3`通过；没有积分重算、训练或作业重提，失败静态命令未单独计时。逻辑包字节不当物理EOS请求/网络字节，后者未测量。

只保留紧凑角色输入/准确预测和数值状态、指标/图及实际资源，原模型不复制，临时500draw在worker验证后只留seed/配对表。传输包/回传archive已完成去重，删除的四个精确路径和字节见`transfer_cleanup.json`，NPZ不入Git。最终实际留存 **11,324,175 bytes**，清单见`storage.json`（≤20,000,000bytes），包含角色input/预测/控制与完整紧凑证据；原stage87模型不复制。原stage54五项未跟踪路径只读、prompt后缀逐字保留；阶段报告/代码/配置/紧凑证据最终本地Conventional Commit，不push。

## 7. 阶段结论与下一步

本轮完成全cal/test准确推断和全部数值认证，明确区分了“推断积分错误”与“训练/校准目标、先验和真实响应的剩余问题”。第二低能相对GH32有小幅条件改善；最低能仍未恢复到传统、总体与困难侧仍显著差于同split direct，严重高端欠覆盖也保持。**继续既有部署，不晋升本后验，不按test换先验/节点/校准，也不据此宣布数据无关或信息上限。**

唯一下一stage90为**保存head上的可微准确marginal log-likelihood与梯度认证，0fit/校准优化/新test评价**。用stage88固定40train＋512cal原row/head/weight/truth/pz；训练点b=0,T=1，校准点用原b/T。仅在truth能量处评价density及对15维head、b/T的导数，不再计算全部quantile/CDF或扫GH节点；GH32旧值/梯度作为被审计项，不能选赢家。先≤40固定cal实际包/计时QA，独立自适应参考＋双步长差分核值和梯度，之后冻结一种可微实现、容差和样本；目标值误差≤1e−6、梯度|差|≤1e−4＋1e−3|参考|，参考数值不确定度另报，不满足即准确交缺口。

正式建议≤1Condor/1CPU3000MB/MaxRuntime1800s、累计CPU1800s、紧凑20MB，QA不满足成本/精度则不启动完整诊断。实测GH32值/梯度误差分布、原−joint−.25marginal loss的梯度影响与cal b/T目标方向；有限样本/最终head点审计不证明完整训练轨迹偏差已修复，512cal不能代替完整cal最优性判断。交付可复用的经认证可微loss或具体失败原因、成本、下一次原模型单次重训/校准所需合同；**本轮不执行stage90，不自动优化或更换模型**。详见`followup_input_request.json`与更新后的下一轮Prompt。
