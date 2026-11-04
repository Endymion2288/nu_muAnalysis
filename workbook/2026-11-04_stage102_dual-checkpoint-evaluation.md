# Stage102：同轨迹双checkpoint，概率选择有增量，最低能点风险没有恢复

## 1. 阶段目标与结论

按路线§83、信息预算§63及[Stage101冻结合同](stage101_energy_ml/stage102_contract.json)，完成**唯一一条原Stage94 E residual MDN训练轨迹**，分别保存point-MSE最佳P和NLL最佳N。起点提交为 `3e2f7df`。NLL只决定第二份保存，不改变优化、原point patience或停止时间。本轮不是两个fit，也没有重做五格比较、classifier、温度校准或原生提取。

主结果成立：原cal_post的raw配对NLL(N)−NLL(P)=**−0.006808016**，500次条件95%区间 **[−0.011119210, −0.001855240]**，上端<0。完整cal和开发test的raw概率比较方向相同。但是最低真能50–100 GeV的点log-RMSE从P的0.271190506升至N的0.281532026，N/P=1.038134 [1.019380,1.061752]；传统为0.145661386。**概率checkpoint选得更合适，不等于低能能量恢复。** 四种预定输出均未通过原八层点/三向尾联合门槛，不晋升，继续既有部署。

本阶段结束checkpoint对照；不追加seed、loss、局部校准或当前collection统计族。下一最小交付是从已提交汇总形成有界的风险与产品交接表，详见§9；本轮未执行下一阶段。

## 2. 输入、物理政策与训练

输入复用 `ntuples/energy_ml_stage87/split.npz`、Stage55/56/70/81/82/83紧凑缓存、Stage90 QA身份，以及Stage94原cal分区、预处理和X分组。评价输入是 `ntuples/energy_ml_stage94/evaluation_input.npz`；传统/旧direct/bounded取Stage87保存预测，旧P取Stage94 seed494保存点输出。没有ROOT/native读取、新MC、重建或新增样本。

|支持|记录数|incoming数|
|---|---:|---:|
|兼容池|89033|不另测|
|train|46575|37556|
|完整cal|11612|10811|
|cal_select|5443|5272|
|cal_post|5746|5539|
|purged_select，仍在完整cal评价|423|不另测|
|开发test|13189|12125|
|隔离|17657|不另测|

原incoming总权重不改，cal_select/post使用原子角色重归一权重。全部1016新增K支持保留；输入缺失train/cal/test=21/6/5，全部困难和高端/尾事件保留。pz选择仍为>50 GeV，原50–100 GeV支持没有删除或切回传统。

输入严格为原E的62 typed数值＋62 mask＋`wave_invalid/fit_failure/calo_invalid`，127维；不是同维数的Stage100 availability输入。train-only typed变换/median/IQR状态与原保存状态完全一致，无cal/test尺度拟合。一次方动量只用pz0；不引入p0、p1、pz1或ln(p0/p1)，保留px/py、q/p和弯折量。scintillator沿原raw11输入和status，typed NaN处理-999及按变量域非法的-1；合法负raw/charge及module_eta=-1不统一删掉，Calo缺项保持mask。`stage102_common.py:frozen_inputs`逐列复核audited rules与原清洗状态。

模型是原2×64 SiLU/9-head/三Normal residual logE MDN，anchor=log(pz0/0.8)，sigma=0.05+softplus，**12937参数**。seed2026110494；float32、无AMP/TF32，Adam lr0.001原defaults/no decay、clip10、batch1024，原numpy permutation和incoming加权marginal NLL。每5epochs验证，最大300，原point-MSE patience30停止；严格更小才替换保存，ties保留早者。

实际停止epoch95，共**4370 optimizer steps**。P选epoch65，cal_select raw point MSE=0.08349312096834183；N选epoch50，cal_select NLL=−0.14398983120918274。两者不是预先强指定旧轮次；是本轮同轨迹按冻结准则实际选出。参见[learning.tsv](stage102_energy_ml/learning.tsv)、[selected.json](stage102_energy_ml/selected.json)。N最佳仅覆盖原point停止前的已记录轮次，不认证300轮全程概率最优。

fit前写唯一attempt ledger；训练中原子保存state并回读，选择先落盘，随后才重建/forward test。24801条cal/test的两个head和实际float32点输出已持久化、回读逐位核对。统计阶段不再forward或fit。主分布与点为raw b=0/T=1；辅助两者共同施加旧seed494固定b=0.02017839294662559。**0新b/T优化**，不使用ensemble b/T，不从test回选raw或shifted。

## 3. 概率结果：raw主比较成立，完整可靠性仍不成立

NLL针对自然对数能量密度，无单位；宽度为自然logE宽度，coverage为%。完整表见[probability.tsv](stage102_energy_ml/probability.tsv)、[paired_probability.tsv](stage102_energy_ml/paired_probability.tsv)、[PIT.tsv](stage102_energy_ml/PIT.tsv)。

|角色/策略|P NLL|N NLL|N−P|条件95%区间|
|---|---:|---:|---:|---|
|cal/raw|−0.152862469|−0.160736421|−0.007873952|[−0.011438159,−0.004597322]|
|cal_post/raw，主比较|−0.174292213|−0.181100230|−0.006808016|[−0.011119210,−0.001855240]|
|开发test/raw|−0.099782991|−0.109987764|−0.010204774|[−0.013522582,−0.006804995]|
|cal/旧固定b|−0.144887180|−0.144616445|+0.000270735|[−0.003471548,+0.003642619]|
|cal_post/旧固定b|−0.165820794|−0.164003896|+0.001816898|[−0.002673025,+0.006848055]|
|开发test/旧固定b|−0.096512949|−0.099232123|−0.002719175|[−0.005966229,+0.000559106]|

辅助旧平移的区间均含0，不能把raw收益推广到任意平移/后处理，也不能依test择优。旧b是为旧P点目标得到的值，对N并非重新适配；本轮未测重新优化的作用，不据此追加校准。

|开发test总体|68% coverage|90% coverage|68%平均宽度|90%平均宽度|meanPIT及95%区间|
|---|---:|---:|---:|---:|---|
|P raw|65.104742|87.563162|0.437290019|0.753368832|0.527201577 [0.521977096,0.531971251]|
|N raw|65.633952|88.156289|0.452012972|0.783883391|0.515219191 [0.509974991,0.519962679]|
|P旧b|63.005086|86.346667|0.437290019|0.753368832|0.493635367 [0.488386688,0.498471771]|
|N旧b|63.079313|86.899931|0.452012972|0.783883391|0.482329022 [0.476911992,0.487194240]|

N raw区间更宽、覆盖率有所改善，但68%覆盖上95仅66.372206%，90%上95仅88.726045%，均低于名义值；meanPIT区间仍排除0.5。十箱PIT比例，P raw为0.093416/0.090928/0.095408/0.094069/0.093553/0.092184/0.096084/0.104661/0.103845/0.135853，N raw为0.098344/0.094907/0.098830/0.097753/0.092440/0.095513/0.093431/0.102005/0.102621/0.124155。右端过量减小，没有消失；meanPIT不是完整均匀性认证。

原X组均完整报告。N raw的X_pz50–100 meanPIT=0.500788 [0.478228,0.520879]，X_pz100–200=0.497049 [0.482778,0.511534]，但X_pz≥200=0.518930 [0.513379,0.524047]；X_activity1/2为0.517470 [0.508515,0.526017]/0.521321 [0.513279,0.530797]，仍有条件失配。cal_post raw meanPIT区间含0.5不消除开发test残差。

真E/y困难分组仅作诊断，不要求这些PIT均匀。N raw低pz真高E/high-y/未确认68/90覆盖分别58.979652/83.662636%、53.921335/79.785459%、58.638034/82.104856%；3200–6400 GeV为21.024306/43.463542%。这些风险保留，不因总体改善而隐去；不能仅凭真值组PIT偏离证明条件后验失准。missing test仅5条，68/90覆盖44.444444/55.555556%，支持稀少，不认证该层性能。

## 4. 点结果与原联合门槛

点定义为exp(mean logE)，不是mean E。log-RMSE无单位，能区和pz单位GeV。原八层均保留，high-y/未确认沿旧定义；不同层重叠，incoming数不能相加。完整[points.tsv](stage102_energy_ml/points.tsv)、[paired_points.tsv](stage102_energy_ml/paired_points.tsv)及[gates.tsv](stage102_energy_ml/gates.tsv)保留全部角色/诊断层和三向尾。

|开发test层|记录/incoming|传统|原direct|P raw|N raw|P旧b|N旧b|
|---|---|---:|---:|---:|---:|---:|---:|
|真E50–100|183/183|0.145661|0.282644|0.271191|0.281532|0.285933|0.297026|
|真E100–200|856/851|0.247937|0.246329|0.246321|0.248027|0.256110|0.258736|
|all|13189/12125|0.557190|0.287491|0.293615|0.293792|0.292090|0.292810|
|真E≥200|12150/11091|0.578219|0.290487|0.297284|0.297208|0.294769|0.295193|
|pz50–100|659/659|1.275310|0.498966|0.512987|0.513586|0.511347|0.512241|
|pz50–100且真E≥200|297/297|1.887790|0.658177|0.677343|0.676720|0.668651|0.667912|
|high-y|385/384|1.618799|0.609395|0.630169|0.621585|0.622983|0.614413|
|未确认|468/466|1.638613|0.551305|0.561282|0.559600|0.555775|0.554042|

同轨迹N/P raw总体比1.000605 [0.997995,1.003194]，没有总体点增量支持；最低能比1.038134 [1.019380,1.061752]有恶化证据；high-y比0.986379 [0.978476,0.994649]有本条件下改善；低pz真高能比0.999080 [0.989688,1.009157]含1。point与density的最优保存准则不同，实际代价呈分层权衡。不是因一次读出缺失或少数离群而停止分支，也没有估计物理信息上限。

新P与旧P的已报各角色/层配对RMSE比均1、三向尾差均0；训练选择数值也重现原seed494。这是已报风险指标控制，不将其写成未经另测的全逐事件预测逐位相等。旧传统/direct/旧seed494 raw及旧b控制共960项标量复现max0。N−P来自同轨迹，不混入跨平台重训变化。

|层|原RMSE上95门槛|P raw上95|N raw上95|P旧b上95|N旧b上95|
|---|---:|---:|---:|---:|---:|
|50–100/传统|1.05|2.239170|2.312052|2.336321|2.414738|
|100–200/传统|1.05|1.074117|1.085690|1.118265|1.133189|
|all/direct|1.01|1.030102|1.030372|1.024562|1.026542|
|≥200/direct|1.03|1.032499|1.031827|1.023647|1.024977|
|pz50–100/direct|1.03|1.051520|1.051902|1.048759|1.049254|
|低pz真高E/direct|1.03|1.059030|1.055120|1.044679|1.041733|
|high-y/direct|1.03|1.062163|1.048157|1.050131|1.035083|
|未确认/direct|1.03|1.045575|1.041220|1.035212|1.030800|

尾定义为相对误差绝对值>50%、正误差>50%、负误差<−50%。全部八层均要求相对原direct三种尾差的条件95%上端≤+2pp。本轮N raw总体总/正/负尾率6.502680/3.354639/3.148041%，传统最低能尾为0，N raw最低能为8.743169%且全为正尾，P raw为9.289617%。最低能N的median bias=+19.717012%，传统为+14.060708%，点风险并未恢复。

|N raw相对direct|总尾差上95 pp|正尾差上95 pp|负尾差上95 pp|
|---|---:|---:|---:|
|all|+0.615155|+0.239570|+0.513436|
|50–100|−1.019887|−1.019887|0.000000|
|100–200|+2.795992|+2.664950|+0.495798|
|≥200|+0.633336|+0.207169|+0.549723|
|pz50–100|+2.287988|+0.895637|+2.137472|
|低pz真高E|+4.268601|+1.240318|+4.626078|
|high-y|+4.350785|+0.156321|+5.500774|
|未确认|+2.728629|+0.382337|+3.628937|

最低能相对direct尾改善不替代相对传统RMSE失败；总体尾通过也不替代困难侧保护。P/N raw/旧b四者均联合失败，见[decision.json](stage102_energy_ml/decision.json)。图见[checkpoint_comparison.svg](stage102_energy_ml/checkpoint_comparison.svg)，PDF同目录。

## 5. QA、独立复核与程序问题

原固定40 train/cal身份包括全部21 train/6cal missing，0optimizer；通过后才准入fit。成功QA的CPU/GPU点logE最大差0，参数梯度最大差8.940697e−8；float64独立logdensity差4.440892e−16、head中心差分差1.938028e−10（原门槛1e−7），逆CDF残差2.498002e−16；旧seed494已保存模型对QA点控制差0，state回读预测逐位一致。batch1024 forward/backward中位wall=0.001082376秒，带余量fit投影194.683944秒<600。见[QA.json](stage102_energy_ml/QA.json)。未改变容差。

完整24801记录四种分布的独立scipy density/CDF最大差1.776357e−15；解析float64解码均值与实际float32保存点差P/N为8.876250e−7/9.879719e−7，均<原3e−6门槛。点表仍使用实际网络float32输出，不偷换为float64解码均值。四分布逆CDF残差均<1e−10，所有预测finite。

主区间用原500次component分层incoming重抽样，cal/cal_post seed2026110389、test2026110390，所有候选共享draw。独立按incoming显式展开主NLL/区间，与矩阵聚合差max8.500145e−17；32候选×层的RMSE和三向尾共128区间，另按逐记录空间重算，端点差max4.884981e−15。旧标量960项max0。见[validation.json](stage102_energy_ml/validation.json)、[independent_gate_checks.tsv](stage102_energy_ml/independent_gate_checks.tsv)。

实际发生一次程序失败：首Kubeflow QA已运行数值断言，但包内未含Stage102文件时输出目录缺失，写QA.json触发FileNotFoundError，随后计时/归档也失败。保留[QA1_failure.txt](stage102_energy_ml/QA1_failure.txt)。修复worker先mkdir输出目录及Kubeflow原生EOS原子cp/mv后，只重做0optimizer QA；**没有失败fit或第二训练轨迹**。训练前还固定同batch1024回读形状，避免把GPU不同batch形状的舍入差误判为保存失败。

Condor GPU QA9667721.0无立即可用匹配，确认hold/0starts后删除，再用用户已配置授权的Kubeflow；没有同时占两个stage作业。QA2成功后fit，fit成功后CPU报告9667745.0，一次start/exit0。QA2 Pod在查询时已被平台清理，保存Job成功状态与时间；不能把空Pod查询当资源证据。失败QA与fit的实际Pod资源有快照，QA2实际CPU/内存未测量。没有访问或保存OAuth令牌。

## 6. 性能、资源与存储

所有数值QA/fit/预测/统计/绘图均在batch。成功GPU为H100 NVL MIG3g.47gb，torch2.10.0/CUDA12.5；原计划2CPU/6000MB，失败QA和成功fit实际Pod由平台注入22CPU/63G，torch/BLAS仍1线程，不将计划资源称为实际分配。GPU只一份MIG，最大同时stage作业1。成功fit allocated GPU峰93.818848 MiB，不是平台显存预留量或全容器显存。

|独立外层worker范围|CPU秒|wall秒|峰RSS KiB|
|---|---:|---:|---:|
|成功QA2，含imports|2.954903|3.325343|1194500|
|唯一fit，含imports/重建/预测|11.912124|14.224981|1621540|
|8进程报告，含imports/子进程|32.900000|14.880000|292992|

已计成功外层合计47.767027 CPU秒，不叠加嵌套worker/child时间。首失败QA主容器wall15秒、22核硬上限，CPU实耗因计时持久化失败**未测量**；保守按22×(15+2秒时间戳余量)=374 CPU秒作该容器上界预留，不伪称实测。已计成功外层＋此失败预留421.767027 CPU秒<1800预算；shell打包/平台/全会话CPU未测，不能声称精确总耗时。失败容器wall15秒、fit容器wall15秒，QA2 Job start→complete14秒，成功GPU worker分别3.325343/14.224981秒；均未触及600秒任务上限，时间口径分别记录。

CPU报告申请8CPU/8000MB，站点ad和实际为8CPU/24000MB；Condor remote wall21秒、CPU34秒、首次exit0，与GNU time外层32.90/14.88秒口径不同，不相加。原90个role×stratum任务共享只读数组、draw一次生成、fork8进程/内线程1；含独立复核和表图的计时窗口6.963077wall秒、child23.424979CPU秒，平均3.364171核。该窗口不是纯pool测量，完整单核对照未测，不宣称8倍加速。更多细节见[resources.json](stage102_energy_ml/resources.json)、[condor_report.json](stage102_energy_ml/condor_report.json)。

模型/head保留于忽略目录 `ml/artifacts/stage102/{P.pt,N.pt,heads.npz}`，大小54221/54221/1866841 bytes；逐事件数组不入Git。代码、JSON/TSV及SVG/PDF是紧凑可审查证据。四个运输输入包及三个返回包在源码/原输入字节核对后去重删除，不留ROOT/REC/xAOD副本，不动共享缓存。最终字节及清理明细见[storage.json](stage102_energy_ml/storage.json)；限额20,000,000 bytes。Condor已报传输字节不等同完整EOS物理网络/I/O，物理流量**未测量**。

## 7. 主要执行命令与产物

先本地标准库打包/源码检查，事件运算仅worker执行；没有在当前终端恢复CERN软件栈。

```bash
python3 ml/package_stage102.py package qa
condor_submit AnalysisZipFramework/submission/ml_stage102.sub
# 9667721.0确认0starts后hold/remove，再转Kubeflow
kubectl apply -f AnalysisZipFramework/submission/ml_stage102_qa_kubeflow.json
python3 ml/package_stage102.py collect qa
python3 ml/package_stage102.py package fit
kubectl apply -f AnalysisZipFramework/submission/ml_stage102_fit_kubeflow.json
python3 ml/package_stage102.py collect fit
python3 ml/package_stage102.py package report
condor_submit AnalysisZipFramework/submission/ml_stage102_report.sub
python3 ml/package_stage102.py collect report
```

首失败QA job名为 `nu-mu-energy-stage102-qa`，修复后QA模板现名 `nu-mu-energy-stage102-qa2`，唯一fit为 `nu-mu-energy-stage102-fit`。运输包按清理策略已删除；重建审查包不意味着允许重训。`fit_started.json`和已存在state会拒绝第二次fit。所有成功任务源码和原缓存与包逐字节一致，见[packaging_validation.json](stage102_energy_ml/packaging_validation.json)。

主要新增代码为 `ml/stage102_common.py`、`stage102_qa.py`、`stage102_fit.py`、`stage102_report.py`和 `package_stage102.py`；通用worker为 `AnalysisZipFramework/submission/run_ml_stage102.sh`。旧point/direct/bounded只读，不调用旧report的后处理拟合prepare。协议/准入/ledger/选择/时间/报告均在 `workbook/stage102_energy_ml/`。

## 8. 统计与物理解释边界

本次只隔离同一已训练轨迹的保存准则；NLL更好、meanPIT更接近0.5、区间更宽与低能RMSE恶化可以同时成立。它修正了Stage101提出的具体概率选模缺口，没有证据称该缺口是最低能失败的原因。更早轮次不等于已知物理更准确；不把raw/旧b差异事后拆成唯一因果份额。

cal_post历次复用，test为开发集，500 incoming条件区间固定checkpoint和参数。没有source95、重训/seed分布、旧b估计、阈值估计、研究选择或真实response系统不确定度；不称新blind或独立确认。interaction/FSI、材料/输运、Calo响应、接受度/背景及真实data闭合未测。缺失5例不足认证，真值条件诊断不代替X条件校准。

原生轨迹—measurement/cluster唯一ID、TSOS、SP constituent引用、实际covariance与有效读出分母仍缺；本轮0原生定位，不将PHYS collection弦线摘要等同这些产品。当前collection族停止扩展不等于这些真实信息无用。没有支持“唯一缺训练数据”“已到信息极限”或“ML家族无效”的结论，也没有按test构造低pz切换部署策略。

## 9. 下一最小任务与阶段交付

本checkpoint实验已完成，有条件概率增量，但最终点目标失败，继续既有部署。**下一次若按当前路线继续，仅做一次终态交接整合（拟编号Stage103），不是再训练或再做无界研究复盘。** 输入为已提交Stage92/94/96/97/99/100/102汇总、既有部署记录和原生产品缺口；不读事件/模型载荷，不fit/forward/积分/重做风险，不重新定位EOS，也不自动恢复Stage54支线。

交付一份明确区分现行部署、开发候选点风险、概率产品和缺失真实输入的中文交接表；原1.05/1.01/1.03与八层三向tail+2pp验收不改。至少逐项覆盖50–100、100–200、总体、低pz真高E/high-y、概率总体/X组、真实response/独立确认；每个数字可回指原提交表，未测量明确标识。另列真实ID/TSOS/SP组成/covariance/有效读出所需的最小持久产品与身份闭合条件，及何种新证据才值得另冻实验。**验收为一个可审查的终态交付和停止/重开条件，不生成又一条训练/校准/metadata扫描链。** 成本以文档工作计，不占GPU或事件batch预算；本轮未执行。

先写本中文报告，再追加路线§84/信息计划§64、更新下一Prompt。历史正文只追加，Stage54逐字后缀和五项原工作树资产保持；代码/配置/紧凑证据本地Conventional Commit，不push。文档、AST、shell、JSON、历史前缀/后缀和存储检查见[delivery_validation.json](stage102_energy_ml/delivery_validation.json)。
