# Stage91：批量准确score likelihood、CPU/GPU数值与执行成本认证

日期2026-11-04，起点`3325e31`。依据路线§72、信息预算§52和stage90合同；本轮0能量fit、校准优化、optimizer step、网络forward、新test评价、ROOT读取、重建或生成。一次方动量仍只用pz0；允许px/py、q/p和弯折。raw11、typed NaN、合法负raw、Calo缺项、pz>50GeV、困难侧及实际交付1016K保持，不恢复用户已解除的K生产时限。

## 1. 目标与输入

stage90已确认GH32近似会造成训练/校准梯度偏差；其scalar准确loss粗外推原46575×150事件目标计算需要117041.335CPU秒，仅为4条最终head的外推，不是实测训练。stage91目标是在保持同一密度/score模型的条件下实现可批量执行的一阶loss，测量CPU/CUDA精度和吞吐，并据此定义下一次原模型训练合同。它不测量能量风险收益。

输入`ntuples/energy_ml_stage90/{input,audit_values}.npz`：原40train＋512cal，共552保存最终head、row、role、weight、pz、truth、key/group，以及stage90独立自适应/双步差分参考和不确定度。逐项保留，训练点b0/T1；cal点b=.011721733230708156/T=1.2001641697078562。raw training-prior marginal，原loss−joint−.25marginal；不把nominal先验引入优化目标。无test、无新的9384坐标差分。552不含missing/wave/Calo-invalid，这些状态的数值覆盖未测量。

## 2. 实现、初始失败与冻结

`ml/batched_posterior.py`沿用stage90的standardized-s密度与解析高斯score。每个区间固定32点Gauss–Legendre，响应尺度/质量边界全部保留；在[-L,L]增加整数标准化高斯分点，L仍由原10至16σ密度尾界规则决定。各成分42个固定槽位，重复边界为零宽padding；没有保存逐节点网格。积分和head参数解码用float64，原float32 head的梯度在VJP返回时转回float32；共享float64 b/T导数按上游权重求和。仅支持固定观测量的一阶导数，不支持观测量导数或高阶导数。

分点用于求积；导数来自同一分布score的积分，不对分点或求积器分支自动求导。若尾界准入失败、密度非正或梯度不有限，则显式产生NaN，后续训练合同要求停止并保留失败身份，不能静默改用GH32。

**首次response-only分点QA失败，不能省略。** 固定40cal CPU/CUDA均仅34/40认证：6条值失败、2个梯度坐标失败，最大值差8.036210433e−5、梯度差.004571326903；row5507移动分点双步差分最大差.000721514799。CPU/GPU一致，排除CUDA特有舍入作为主要原因。原response-only分点会留下跨越高斯包络的大区间；自适应参考会继续细分，固定GL32不会。保存原代码`startup_initial_source.py`、`startup_initial_QA.json`与`initial_qa_*`数组；进程exit0只表示QA脚本完成，数值结果明确为failed。

最终冻结前按标准化高斯单位尺度加入全部整数分点，每个区间宽度≤1σ，保留原响应窄结构分点；不改变阶数、物理模型、容差、样本或先验，不扫描阶数/候选网格。几何诊断见`partition_geometry.tsv`/`partition_diagnosis.json`，只重建分点，0新积分；该宽度限制本身不是全域精度证明。

修正后原固定40cal全部680坐标在CPU/CUDA通过：最大值差1.998401444e−15、梯度差2.707500890e−11，最大“差＋参考不确定度”/容差.004602009803。CPU/CUDA最大值差4.440892099e−16、梯度差7.549516567e−15。非均匀upstream linspace(-.7,1.3,40)，float32返回梯度与预期cast差0，共享b/T汇总差0（控制阈值1e−10）。首两固定QA身份5483/5507移动分点双步差分，各后端34坐标，最大差CPU5.687755822e−12、CUDA6.069034164e−12；这是candidate自洽检查，独立参考仍来自stage90。

先小QA、再冻结`protocol.json`、再实际包4cal CPU/CUDA控制，随后只提交一个Condor作业9667300.0，2CPU、6000MB、1GPU、MaxRuntime1800秒；CPU soft/hard1500/1520秒、worker wall1700秒、阶段累计CPU1800秒。完整552和固定batch256/1024吞吐均在Condor运行，无自动retry。值门槛1e−6；梯度|差|＋保存参考不确定度≤1e−4＋1e−3|参考|，没有事后放宽/删事件。

## 3. 完整结果和性能

唯一作业**9667300.0首次正常exit0、NumJobStarts1，无重试/恢复**。实际GPU为**NVIDIA H100 MIG 2g.24gb**，32个SM；torch属性报告total_memory=24362MB，池分配广告GlobalMemoryMb=21547（不同接口，均不是实测peak），CPU2线程。完整CPU/CUDA×batch256/1024四组均552/552认证，每组9384/9384梯度坐标通过，合37536次坐标比较；没有改变角色、head、权重或删除失败事例。

| 完整552指标 | CPU256/1024 | CUDA256/1024 |
|---|---:|---:|
| 最大log-density差 |2.835953694e−12|2.835953694e−12|
| 最大梯度差 |7.324036377e−10|7.324036932e−10|
| 最大(差＋参考不确定度)/容差 |.140596797615|.140596797615|
| 值/坐标失败数 |0/0|0/0|
| 非空区间总数/事件范围（三成分合计） |64–74|64–74|
| 最大密度尾界 |1.205674935e−22|1.205674935e−22|

train40最大值差≤2.386979503e−15、梯度差≤2.954081424e−11；cal512达到上表最大值，全部通过。CPU与CUDA最大值/梯度差1.110223025e−15/2.131628207e−14，同后端两batch差0；正式共享b/T、float32 VJP与移动分点控制也全部通过。独立报告脚本只用保存数组，逐项核对身份/head/role/weight/reference，重建全部四组认证和汇总，**40968项flags/值检查，汇总最大差0**；其中37536是梯度认证比较，不能把40968全部称独立实数计算。逐例552行及逐参数9384行在`events.tsv`/`gradients.tsv`，分角色表`role_summary.tsv`，图[数值与吞吐](stage91_energy_ml/batched_likelihood.svg)已实际查看。

固定cal按既定顺序重复至batch长度（不是更多独立样本），每组1次warmup＋5次测量，中位wall包括节点构造、host/device输入、同步、密度/score积分、VJP及返回传输：

| batch | CPU2线程wall s | H100 MIG wall s | CPU记录/s | GPU记录/s | GPU加速比 | GPU peak allocated MiB |
|---|---:|---:|---:|---:|---:|---:|
|256|.051055399|.002574557|5014.161186|99434.582263|19.830751|104.706543|
|1024|.176352353|.006124270|5806.557058|167203.601325|28.795653|425.679688|

batch1024对应CPU中位process约.351000秒/1024，即.000342774CPU秒/例；相对旧4条scalar .016753099CPU秒/例约48.9倍。这是不同规模/硬件/固定最终head的成本对照，不是训练物理赢家或全轨迹界。按6986250事件目标次数，仅GPU密度/VJP线性外推batch256/1024为**70.259761/41.782892wall秒**。不含CPU网络/joint/Adam、预处理、全cal优化、准确CDF/quantile推断、重抽样或排队；真实150epochs训练成本及收益仍未测量。不能把41.78秒当完整训练承诺。

本地仅固定40cal小QA使用Tesla T4（15360MiB物理显存），LCG109_cuda、torch2.10.0/CUDA12.5；CPU-only LCG109的torch.version.cuda为None，不能用它声明CUDA可用。CUDA编译架构有sm75/80/86/89/90及compute90，无sm70，因此作业排除V100，要求≥8192MB的T4/A100/H100/H200/L4系列（含兼容MIG）。未编译/安装新软件。

本地单CPU线程，1次warmup＋5次重复的40条端到端中位wall：CPU .029709429946秒（1346.373864记录/秒），T4 .004284904804秒（9335.096537记录/秒），约6.9335倍；含输入/输出传输、节点构造、同步、密度/score、backward，未含网络/optimizer。T4 peak allocated16.369629MiB，只是torch张量分配，不等于GPU context或物理显存占用。该小QA吞吐不替代正式batch256/1024结果，也不作为完整训练保证。

## 4. 命令、资源和验证

```bash
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
python ml/audit_batched_posterior.py qa
python ml/audit_batched_posterior.py submit
# 唯一worker由Condor执行，结果通过xrdcp回收；报告只读保存数组
python ml/report_batched_posterior.py
```

正式包`software/energy-ml-batched-stage91.tar.gz`294097bytes，source_identity逐字核对，无SHA；实际包控制保留552角色/权重并在CPU/CUDA首4cal通过。回收不通过EOS FUSE猜测文件完整性，使用XRootD；原数值核心与起点一致，不重算完整差分。NPZ不入Git，重复传输归档回收后删除。详细计量、独立验证、最终留存以本目录JSON清单为准；物理EOS网络I/O未测量，逻辑文件大小不冒充实际I/O。metadata/监测/文档等未完整计时，不声称全尝试严格资源认证。原stage54五项未跟踪工作只读、不暂存；prompt从指定marker起逐字保留，路线/信息计划仅追加。

正式remote **7CPU秒/27execute-wall秒**，slotbusy29秒，提交至执行等待1061秒。worker内部 **3.958526CPU秒/9.188081wall秒/1671.171875MiB peak RSS**；包含解释器/模块启动的`job.time`为4.40user＋2.67sys＝7.07CPU秒、21.41wall秒，同样峰1711280KiB。三种计时范围不同，不能相加；Condor采样RSS约191MiB漏过短峰，不用它替代实测usrtime峰。含初始失败QA/修正QA/本地benchmark/提交/几何诊断/回收/报告的已测外层共**31.49CPU秒**，与remote合**38.49CPU秒<1800**，各命令完整time见`resources.json`；内部计时不重复计。物理EOS I/O及部分metadata/文档/静态检查仍未全计量。

重复输入包294097bytes、结果包320450bytes已回收验证后删除，共614547bytes，紧凑数组、初始失败、protocol及详细表图保留。NumPy leggauss网页本次HTTP403，未冒称已读；score期望恒等式依据复用stage90已检索Louis(1982)，DOI [10.1111/j.2517-6161.1982.tb01203.x](https://doi.org/10.1111/j.2517-6161.1982.tb01203.x)，本轮没有新的物理机制文献结论，见`references.json`。

## 5. 阶段结论与下一步

本轮证明同一score loss可在CPU/CUDA批量执行，完整固定552通过原值/梯度门槛，GPU在正式batch1024端到端计时较CPU2线程快28.8倍。有限552最终head点的认证不保证初始化、150epochs全部中间head、完整cal最优或真实能量收益。密度截断尾界不等于score尾的严格上界，也不等于固定求积的全域误差保证。已有test是研究池中对新fit留出的角色，不是新blind；source95因每角色只有3个连通块仍未认证。真实响应、interaction/FSI/材料/Calo/接受度/背景与独立确认均未测量；继续既有部署，不晋升模型。


唯一下一**stage92：一次原posterior从头150epochs＋原cal一个b/T优化，再做完整准确cal/test配对评价**；本阶段没有执行。输入现有原89033兼容缓存和stage87 split/normalization/protocol/prior、旧direct/bounded/传统和stage89准确后验结果，无新样本/ROOT/生成。不得重新抽split或调用会覆盖stage87的prepare。重建后对原角色46575/11612/13189、隔离17657、key/weight、41特征与train-only归一化逐项闭合；train/cal/test缺失21/6/5全部保留。

只替换marginal求积为本轮冻结GL32 score，joint、seed2026110387、原CPU float32网络初始化/2×64 SiLU、原Adam lr.001/batch1024/150epochs、numpy permutation、incoming权重、clip10及训练点b0/T1不变；CPU1线程原网络/joint/optimizer、GPU float64 marginal，用跨设备autograd返回float32梯度，小QA验证完整网络参数梯度而非只测leaf。原float32监督张量先照旧构造再交积分上转float64，不悄悄重定义训练目标。禁用AMP/TF32，不换架构/先验/seed/early stopping，也不warm-start旧权重。GPU仅加速积分，数值精度升级仍会改变loss和训练轨迹，不能声称与旧训练逐bit相同。

训练前固定40条数值QA＝全部21train missing＋6cal missing＋stage90固定train前13条，若身份交集按row去重后取原固定train顺序补足；不读取test风险。初始化和每25epochs在同40条保存head上与未改stage90自适应score独立核值/15head导数，沿用原1e−6与1e−4＋1e−3门槛并报告参考积分误差；该检查不伪称完整9384双步FD或所有训练head保证。所有batch要求密度、loss、梯度、尾界准入有限；任一失败/预算耗尽保留row/head/资源并停止，不删除事件、不回退GH32、不挑中途checkpoint、不自动重训/加阶。若QA暴露未覆盖区域，先交具体缺口而非降低标准。

原完整cal单次L-BFGS-B从(0,1)起，b[-.2,.2]/T[.5,2]、maxiter100、原其他默认设置，准确raw training-prior NLL与解析b/T导数；记录nit/nfev/终点梯度/成功状态，禁止多起点或从test挑校准。初始化/终点的固定cal数值QA独立核验，完整cal目标最终与准确Reference汇总闭合到1e−6，失败不能宣称完成校准。

小包≤40身份/单位/跨设备完整网络梯度与实际成本、0optimizer QA后，冻结资源：**≤1GPU Condor（2CPU/6GB/1兼容GPU，wall5400秒/CPU7200秒）＋≤2准确推断CPU Condor（各1CPU/3GB/wall与CPU10800秒，并发≤2），含QA/报告累计CPU≤32400秒，最终≤20MB**。GPU任务包含缓存重建、唯一训练/校准与保存head；CPU任务各完整cal11612/test13189。此为封顶/失败策略而非实测上界；参考stage89原模型8937remote CPU秒和本轮密度外推，训练后≤40固定cal成本QA再确认推断预算可行，不能无限延长。模型保存后只做推断，不重新训练以迎合预算。

最终推断使用未改stage88/89自适应Reference CDF/quantiles及本次b/T，主nominal prior与median固定；**不能用未修正GH32评价新模型并宣布收益**。复用旧同split direct/bounded/传统及stage89准确旧posterior预测；主名义完整两低E/all/≥200/低pz两侧/high-y/未确认/missing/高端的log-RMSE、bias、R68、双向tail50、68/90coverage/PIT/十箱可靠性/NLL/宽度/ESS，500component内incoming条件配对区间与原所有联合门槛。旧CRPS16×32近似只作明确命名诊断，准确CRPS未认证不冒称解决；预定prior stress若计算必须使用同一准确CDF，不能按test选prior。每角色3块，source95仍不可估，研究池test非新blind，不能自动晋升。

交付完整唯一fit/校准状态及数值认证、旧准确posterior→新准确posterior和传统/direct/bounded配对表；区分程序修复、物理风险和真实响应未认证。先中文报告再本地Conventional Commit，不push，不自动启动stage93。详见`stage91_energy_ml/followup_input_request.json`和更新Prompt。

最终本阶段代码/文档/证据及紧凑NPZ逻辑留存合计 **2918044 bytes**（含storage.json自身），低于20,000,000bytes；各文件清单见`stage91_energy_ml/storage.json`。这是逻辑字节，不是EOS物理配额或网络读写量。
