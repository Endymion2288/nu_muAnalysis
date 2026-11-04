# Stage90：保存head上的准确可微marginal likelihood及梯度认证

日期2026-11-04，起点`5df6db3`。依据路线§71、信息预算§51及stage89输入合同；本轮0能量fit/校准优化/optimizer step/网络forward/新test评价/ROOT/生成/重建。现有train/cal角色和全部1016K支持保留，不恢复K旧生产时限。一次方动量仅pz0，允许px/py/q/p/弯折，raw11/typed NaN/合法负raw/Calo缺项及pz>50GeV/困难侧不变。

## 1. 目标与输入

stage89已对完整24801cal/test认证准确推断，最低能仍差于传统、总体与困难侧仍差于同split direct；因此本轮只量化原GH32训练/校准目标的值与导数误差，交付可复用的一阶准确loss，不宣称修复物理风险。

复用`ntuples/energy_ml_stage88/input.npz`固定等间隔40train＋512cal，共552记录；head/row与stage87保存head/predictions及split逐项核对，weight/group/key/pz/truth/y一致，无test。缓存没有`label_physical`列，按stage87全unknown0审计及finite0≤y<1、(1−y)Eν>mμ重建且552全部物理有效，truth只用于监督。固定552没有missing/wave/Calo-invalid，相关梯度精度未测，不以此证明所有状态覆盖。

训练40条固定b=0/T=1；cal512固定b=.011721733230708156/T=1.2001641697078562。使用原training-prior raw marginal密度，不包含nominal重加权；原loss为−joint−.25marginal，joint部分不变。主考察15个head与b/T共17维一阶导数，无优化。

## 2. 数值定义和先QA后冻结

新`ml/differentiable_posterior.py`以高斯score恒等式积分解析密度导数。每成分积分[density, mr-score, ms-score, raw-sr-score, raw-ss-score, T-score]，logit梯度=responsibility−mixture weight；b梯度为三个mr梯度之和，T直接积分(t²−1)/T避免除以饱和sigmoid导数。沿用原standardized-s坐标、响应窄峰split和≥10σ截断、epsabs/epsrel1e−10、quad_vec limit400。自适应分区是求积工具，不是模型参数，不对求积器分支求导。

PyTorch custom Function使用积分导数给出固定观测量下的CPU float64一阶VJP，支持batch上游权重与共享b/T累加；不支持观测量导数、高阶梯度、CUDA或原float32训练直接替换。密度尾界独立保存，不冒称为梯度尾的严格解析界；本轮认证是在指定点与独立参考的实测一致性。

独立参考是**未改动**stage88 `Reference`，在truth logE处重新积分每个±扰动参数：central h=1e−4和5e−5，两步Richardson(4d_half−d_full)/3。参考不确定度=|d_half−d_full|/3＋(4noise_half＋noise_full)/3，noise由参考quad相对密度误差传播；这是误差估计与步长一致性，非严格全局数学界。认证要求值|差|＋参考误差≤1e−6，梯度|差|＋参考不确定度≤1e−4＋1e−3|参考|，并要求参考不确定度≤该容差1/4。不能事后放宽或挑容易行。

先原固定cal前4条QA（≤40），68导数全部通过，最大值差6.661338e−16、最大梯度差1.099326e−11；带[.3,−.7,1.2,.4]上游权重和共享b/T的VJP与保存解析导数最大差0。原GH32与独立numpy GH32值最大差6.661338e−16，其68坐标已有5个不达梯度门槛。QA计算3.671415CPU秒，完整QA4.003423CPU秒/4.438658wall秒，552外推506.655CPU秒仅规划依据。

QA后冻结`protocol.json`，一个实际包包含552紧凑input与同4cal控制；实际包重新计算首个cal值/17导数闭合并通过JSON序列化后才提交。唯一Condor **9667276.0**，实际1CPU3000MB/MaxRuntime1800秒，CPU soft/hard1600/1620秒、worker wall1700秒、累计CPU预算1800秒、紧凑20,000,000bytes，无自动retry。每10条覆盖一次紧凑NPZ/表检查点，保留未完成/不认证行，避免重算已完成积分。

## 3. 实际完整结果

正式唯一作业一次正常exit0、无重试/恢复，**552/552值及全部9384导数坐标通过冻结门槛**，参考未解析坐标0。原逐例身份、17坐标表、参考误差与认证标记全部保留：`audit_events.tsv`、`audit_gradients.tsv`及`ntuples/energy_ml_stage90/audit_values.npz`；未按坏梯度/困难状态删除事件。图见[梯度审计](stage90_energy_ml/gradient_audit.svg)。

| 指标 | train40（b0/T1） | cal512（原b/T） |
|---|---:|---:|
| 原incoming权重和 |33.583333|472.666667|
| 认证值/全部17导数的事例N |40/40|512/512|
| 准确/参考最大log-density差 |6.661338e−16|1.776357e−15|
| 准确/参考最大梯度差 |2.953726e−11|7.962786e−11|
| 最大参考导数不确定度估计 |2.284368e−6|1.408596e−5|
| 最大参考不确定度/容差 |.008048|.140597|
| GH32 value误差>1e−6事例N |38|424|
| GH32至少一个梯度不通过事例N |30|319|
| GH32不通过坐标N |207/680|2207/8704|
| GH32最大log-density差 |1.380193|1.807749|
| GH32最大梯度差 |37.427121|31.280986|
| GH32原raw NLL |−.149931212|−.124483590|
| 准确raw NLL |−.186490944|−.130228601|

合计**349/552事例、2414/9384坐标**的GH32梯度未通过；不是只有几条可忽略离群。准确/参考实际差约1e−11，仍需和参考不确定度估计一起解释，不能仅凭小残差声称全域1e−11严格精度。原torch GH32与独立numpy GH32密度最大差 **1.067202e−14**。同4个固定cal的原GH32 autograd再与numpy GH32独立双步长差分核对，68坐标最大差 **4.860701e−11**，说明本轮发现的是32点求积近似对梯度的偏差，而非torch自动微分实现不一致。cal512准确/GH32 NLL与stage88原中心值闭合（仅浮点舍入），新实现没有改变物理密度定义。

train40原−joint−.25marginal对head输出的逐事件梯度，准确与GH32差的L2 median/p95 **.000697047/2.928563260**；相对准确总loss梯度范数的差median/p95 **.000137530/1.048319926**，即典型事件变化小但上尾可与真实监督方向同量级。按原权重平均head梯度后，差L2 **.526722733**、准确/GH32总梯度L2 **1.342746149/1.441246488**、cosine **.930826110**。这些是**对15个head输出的导数**，平均相当于共享head平移敏感性；没有乘各事件网络Jacobian，**不是网络权重梯度、参数更新或完整训练轨迹偏差**。40train有限，不把p95当总体稳健量。

例如train40 marginal NLL的mr1加权导数，GH32 **+1.677312353**而准确 **−.029643718**；ms1为 **+.765354721/−.097699829**，某些方向已变号。保留全部成分，不借这些truth信息改部署输入或调专家开关。

cal512对实际校准变量的原raw NLL加权导数：

| 坐标 | GH32 | 准确score | 独立差分参考 | 加权参考不确定度 |
|---|---:|---:|---:|---:|
| b |−.199055627|−.225396542|−.225396542|1.898261e−7|
| T |+.044483847|+.078842712|+.078842712|1.031528e−7|

这512cal子集在原完整cal优化点的导数本来就不必为0；不能据此宣布原完整cal未收敛，也不能把子集T梯度差直接当完整cal最优偏移。cal head的−joint−.25marginal汇总只作假想敏感性，cal优化器实际仅变b/T，报告没有更新模型。

固定子层GH32梯度失败：train最低能1/1、第二低能4/5、低pz2/2、high-y1/1、fit-failure4/5；cal分别5/8、28/43、22/28、7/9、20/34。相关准确梯度全通过；低E/high-y支持仍少、missing等未覆盖，不作物理性能或power结论。

## 4. 资源、验证、失败与产物

```bash
# 现成LCG109 CPU torch/numpy/scipy，BLAS单线程，不安装或重编译
/usr/bin/time -v -o /tmp/stage90_QA_retry.time \
  bash /tmp/stage69_python.sh ml/audit_posterior_gradients.py qa
/usr/bin/time -v -o /tmp/stage90_submit.time \
  bash /tmp/stage69_python.sh ml/audit_posterior_gradients.py submit
# 正式worker由HTCondor运行；取回原结果后仅汇总数组，不重新积分
bash /tmp/stage69_python.sh ml/report_posterior_gradients.py
```

开发首例差分一度在float32保存head上直接做1e−4扰动，产生约2.104e−4梯度差；正式代码在扰动前转float64，双步长闭合至约1e−11，故不能把舍入噪声当算法导数错误。首次VJP测试传float32 head被接口明确拒绝，随后float64通过。首次正式QA因缓存没有label_physical报KeyError，未进入数值计算；已按原truth审计补齐，正式前重跑成功。上述失败如实保留成本范围，不伪称全部首次通过，不影响固定正式样本/门槛；没有optimizer step或test试探。

同4个固定cal身份的两次CPU float64 forward＋backward计时，GH32 **.006567746/.003407907秒**、准确score **.068235054/.065789735秒**；平均每条 **.001246957/.016753099 CPU秒**，无optimizer/网络forward。按46575×150=**6,986,250**次事件目标计算粗外推，仅当前串行准确密度/VJP即 **117041.335269 CPU秒（32.511482 CPU小时）**，未含网络/joint/预处理/cal/验证；这是4个最终cal head的外推，不是实测训练成本或上界，也不证明全部训练head可用。原stage87 float32训练不能直接用本CPU float64接口替换，需先解决批量计算与精度保留。

准确score正式被积函数计算 **392133**次、独立差分参考 **25551477**次，precision flag0，vector quad最大误差估计 **3.267180e−10**、density尾界最大 **1.205675e−22**；向量误差同时含score与density，不把它当log-gradient误差，最终导数按独立差分认证。正式remote **840 CPU秒/856 execute-wall秒**；worker **833.771225 CPU秒/840.610915 wall秒/263.851563 MiB**，其中552完整计算含旧GH32/双步参考/检查点 **833.703408 CPU秒/840.538221 wall秒**。4cal外推506.66CPU秒低于实际833.70，未把预测当保证；实际仍低于1600进程CPU/1700worker wall/1800阶段预算。

独立保存数组复核全部 **65,688个数值**、552身份、9384参数坐标及全部认证/参考标记，最大差0，原weight保留；没有重算准确积分。完整统计与图表及已计时外层开发/失败QA/重跑/提交/benchmark/报告/closing QA合 **50.68CPU秒**，与remote合 **890.68CPU秒<1800**，逐命令CPU/wall/RSS见`resources.json`；和remote合计不重复加入内部同进程计时。未计完整metadata/文档/监测/静态检查与EOS物理网络I/O，不能把逻辑包字节当物理I/O。正式实际传输包88,912bytes，源文件与包逐字核对，原`posterior_numerics.py`/`transfer_posterior.py`与起点逐字相同；没有SHA扫描。最终实际留存 **3,129,285 bytes**，以`storage.json`清单为准（≤20MB），已收集传输包完成后去重。原stage54五项只读，prompt保留后缀逐字保持；NPZ/模型/ROOT不入Git，不push。

## 5. 方法依据与物理解释范围

Louis (1982), “Finding the Observed Information Matrix When Using the EM Algorithm”, DOI [10.1111/j.2517-6161.1982.tb01203.x](https://doi.org/10.1111/j.2517-6161.1982.tb01203.x)，其中观测likelihood score可表示为完整数据score的后验期望，为本混合模型的score积分提供依据。原始文献metadata经Crossref实际检索；本轮不使用其observed-information Hessian结论认证高阶梯度。SciPy [quad_vec文档](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.quad_vec.html)支持向量积分与误差估计，实际读取文档；PyTorch extending网页本次HTTP403，未冒称已读，接口功能通过本地实际VJP验证。检索状态见`references.json`。

完整40train/512cal最终head点的数值审计，不代表原150epochs全部轨迹梯度误差或完整cal最优性；不提供source95、population风险区间或独立确认。新test此前已研究，本轮没有新test评价。即便数值通过，物理收益、真实响应、interaction/FSI/材料/接受度/背景与真正未开发确认仍未由本阶段测量。

## 6. 阶段结论与下一步

本轮以全固定552的独立值/导数证据认证了可微准确score loss，也实测GH32值与训练/校准梯度存在显著偏差。它是一个已确认的程序因素；尚未量出该因素对低能/困难侧风险的因果份额，不能单归因或宣称数据无关/信息极限。**继续既有部署，本轮没有fit或新test评价。**

唯一下一stage91：**同一score likelihood的批量CPU/GPU实现、数值保真与训练执行成本认证，0fit/校准优化/新test**。输入本轮原552 head/参数点及保存独立参考gradient/误差，原stage87模型/输入语义保持；无需重复9384个差分积分。以一套确定性分段Gauss–Legendre32求积为拟议实现，分点来自同一s积分的响应尺度/边界，固定密度/score模型与原损失，不扫描GH阶数/架构/先验。先≤40固定cal的实际包值/VJP/计时QA，再冻结单一实现/容差和批量执行资源；应检查分点随参数移动的一阶score导数、float64积分与float32原网络的梯度传递、非均匀上游权重和共享b/T汇总。若不通过，保留具体失败/缺口，不按事件删行、换目标或无界扫阶。

正式完整552对本轮保存参考沿用同容差值1e−6、梯度1e−4＋1e−3|参考|及参考不确定度；CPU/GPU输出/梯度一致性和两种固定batch256/1024的吞吐/peak内存、构造节点及数据搬运全计量。仅小QA交互，完整数组及吞吐通过≤1Condor/≤2CPU6GB（GPU可用时1GPU），QA后冻结MaxRuntime与阶段CPU≤1800秒/紧凑20MB；GPU真实可用性与成本尚未测，不虚构CUDA支持。目标完整数值通过且较当前scalar约.01675CPU秒/例明显加速，能在明确实际资源下提出可执行的**一次原模型posterior150epochs＋原cal一个b/T校准**合同；direct/bounded/旧模型预测不重训，role/features/seed/prior/门槛不变。尚未批准/执行该后续fit；若实现仍太慢，交具体瓶颈而非自动加训练/降低精度。

本轮不执行stage91。完整训练轨迹数值稳定、真正物理收益、全cal准确最优、真实系统效应与独立确认均未由本阶段证明。见`followup_input_request.json`及更新后的下一轮Prompt。
