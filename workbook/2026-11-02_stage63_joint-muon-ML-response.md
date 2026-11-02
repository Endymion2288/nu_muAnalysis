# Stage63：选中低能成分的μ/ML联合响应

## 1. 阶段目标与范围

按修订路线§43和stage61/62分流，只回答一个问题：已有F7的显式μ约束与ML修正二维表示，能否在有限模板MC、来源留出闭合与形状压力下，比灵活标量F7更稳健地约束选中低能成分？本轮0个新能量模型fit，0个ROOT/RDO/生产/coverage toy，不开展六自由箱或网络、先验、点估计器扫描。继续原F7部署状态；cal/eval是已开发比较，不是新盲测。

保留pz0这一种线性动量；px/py、q/p、弯折等已审计输入不受该限制。F7三模型均按`audited_features`的62列、11个scintillator raw charge及VetoNu reduced约定回读；合法signed值保留，非物理占位、状态和依赖无效值转NaN。没有回退到p0/p1/pz1或拟合charge，也没有删除缺失、高y、未确认、负ML修正和困难尾。

## 2. 输入、选择与冻结设计

- 输入为`ntuples/energy_ml_stage55/dataset.npz`、`ntuples/energy_ml_stage56/readout.npz`、stage56三个`{2026110255,2026110256,2026110257}/model.ubj`及`predictions.npz`。不索引locked-test标签，不恢复删除分片，不新增raw定义或做SHA。
- 原pz>50 GeV选择及事件/来源保护不变：train 41,447例/91个保守来源，cal 8,440/16，eval 14,057/22。原42个输入缺失者中eligible 21/3/7，另11个既有保护者保持原角色。输入NaN但F7推理有限者正常落箱。
- F7标量S为三个原始log预测均值加stage56同一global cal offset **0.004602409250700414**；所有cal/eval逐seed回读预测与历史数组精确一致。只增加必要的train推理，没有能量重训。
- 三种统计量为M=log(pz0/GeV)、S=log(E_F7/GeV)、J=(M,S−M)。M/S各用train的16个等占据分位箱；J用M四层、层内修正四分位共16格。三者均另保留一个无效统计量格，端点隐含±∞，重复分位只按预定规则合并；本轮实际均为16+1格。truth不参与部署落箱。
- 真值组件为选中50≤E<200 GeV与E≥200 GeV；train计数4,331/37,116，f0=4331/41447=**0.10449489709749801**。固定选中总N=1000，以`f(r)=r*f0/(1-f0+r*f0)`定义相对低/高成分强度r，r=1仅为train参考。这是selected-spectrum条件形状，不是未选中flux测量。

原始不可覆盖协议见[protocol.json](stage63_energy_ml/protocol.json)；数值补充见[protocol_v2.json](stage63_energy_ml/protocol_v2.json)。两者的物理参数、分箱、输入、压力和验收完全相同。

## 3. 有限MC、来源与压力

负log似然（略去常数）为数据multinomial与低/高两个独立条件MC multinomial的KL之和，q=f a+(1−f)b，a/b分别在simplex上。已知响应对照固定a/b为train直方图；有限MC对照profile两个概率向量，不添加MC伪计数。数据直方图均按各case实际低能比例缩放到N=1000，而不是强制闭合到train r=1。

外层使用冻结的17个f网格点，在所有局部/端点网格极小附近作有界细化，再求ΔNLL=0.5的区间端点。记录全部网格、停止状态、simplex KKT、边界与profile调用数。这是有限网格全局检查，不是任意非凸函数的严格全局最优证明。profile区间是渐近参考，未测覆盖率；零低能来源保留区间并单列，不作常规pull/相对r误差解释。

内部高精度求解由KKT导出：令t_i是分给低成分的数据计数，T=Σt_i，则a_i=(mLi+t_i)/(ML+T)，b_i=(mHi+d_i−t_i)/(MH+N−T)。给定T每格有一个物理二次根，Σt_i(T)−T单调，一维求根同时满足两simplex；对纯数据/零MC格保留退化分配支路。有效协议v2使用该解，不使用数值概率下界，目标函数没有变化。

Fisher参考采用数据减模板的协方差：

`V=(diag(q)−qqᵀ)/N + f²(diag(a)−aaᵀ)/ML + (1−f)²(diag(b)−bbᵀ)/MH`，`σ_f=[(a−b)ᵀV⁺(a−b)]^(−1/2)`。

已知模板去掉后两项；内点与完整simplex nuisance Fisher的Schur补数值相符。零MC格时该曲率仅是切向Gaussian近似，同时报告精确profile区间，不能当边界覆盖证明。σ_r由同一点的df/dr转换；偏移同时报告f与r参数化，主验收用r偏移/σ_r。非Asimov闭合的σ是在拟合点计算的expected Fisher，不冒充observed Hessian；profile区间另行数值求得。

500次按pi/k/charm分层的保守train来源配对重加权，固定F7/binning/f0，重算M/S/J曲率误差比，不重训、不做谱coverage toy。它度量来源稳定性；MC似然处理条件计数统计，两者都不包含完整生成谱系、detector、interaction/FSI、材料、校准拟合和研究选择误差。

cal/eval pooled各做nominal和四个压力，另对全部16+22个来源分别做nominal。低组件压力将true50–100乘0.75/1.25；高组件压力将true≥200且reco pz50–100 GeV、y≥0.8乘0.75/1.25。每组件内重归一，保持各角色原始f与总N，全部权重正、全部事件保留。这些是规定幅度的敏感性检验，不是正式1σ系统变体。所有case均比较三表示、已知/有限MC，共294个一参数profile。

事前研究验收为：有限MC下J/S配对来源误差比95%上限<1；J pooled nominal及四压力的|r偏移|/σ_r≤1；J比S增加的绝对偏移≤0.25σ。逐来源全表保留，但不要求每个经验来源的偏移都≤1；将每来源缩放N=1000没有消除其有限响应支持。阈值是研究取舍，非实测detector容忍度。

## 4. 数值故障、修复与验证

首次交互prepare在读取事件和冻结协议前，零MC合成例的EM近区间端点达到5000迭代，资源未测量；没有据此作物理判断。冻结v1前改成EM+解析梯度SLSQP后，四个合成profile、Fisher Schur、端点及零格检查通过；另六个稀疏合成计数例通过。成功prepare实测wall **2.891487 s**、CPU **2.768538 s**、峰值RSS **556.805 MiB**，缓存 **2,236,976 bytes**。初始两条四格合成profile外推约9.678 s/300条，仅是资源估算，不冒充实际17格成本。

首个Condor **9661816.0**完成四个case后，在后续固定f=0.8125处KKT残差**3.128430701×10⁻⁶**超过冻结10⁻⁶阈值而中止，未生成完整物理结果。它证明SLSQP的函数停止精度不足以保证这个KKT阈值，不证明联合物理表示失败。[原始stderr](stage63_energy_ml/numerical_failure/stderr.txt)和[stdout](stage63_energy_ml/numerical_failure/stdout.txt)保留。remote user/sys CPU为2/1 s、wall 8 s；无自动重试。

随后在公开保留原协议的前提下，冻结v2精确KKT分配求根。任务上限由v1自设1个改为路线/Prompt允许的≤2个，累计CPU≤3600 s、单任务1CPU/3000 MB和最终≤10 MB不变；未按物理结果改分箱、压力、模型或验收。该修改已在执行前告知。9个合成profile（含数据独占零MC格）、36个固定f独立比较的最大NLL差**8.1073×10⁻¹²**；复现失败固定f的三表示KKT≤**5.7267×10⁻¹⁶**、与独立SLSQP的NLL差≤**2.0623×10⁻¹⁰**。修复QA wall **1.1577 s**、CPU **1.1033 s**；完整记录见[numerical_amendment_QA.json](stage63_energy_ml/numerical_amendment_QA.json)。未追加能量fit。

## 5. 实测：二维表示没有通过统计或闭合验收

最终唯一完整结果来自**9661825.0**，ExitCode=0、NumJobStarts=1。共**294**个完整profile、**17,262**次固定f评价；最大simplex KKT **5.2888×10⁻¹⁵**，v2没有调用EM/SLSQP fallback。27个独立凸优化复核覆盖三表示×train/cal/eval nominal×极小/两区间端点，NLL最大差**1.8472×10⁻⁹**。294条计数和、冻结分箱回读、网格及KKT检查全部通过，见[validation.json](stage63_energy_ml/validation.json)。独立SLSQP自身使用10⁻¹⁴数值正下界；有正MC计数格的解析概率下界≥2.6236×10⁻⁵，该数值界不活跃；正式v2没有该界。保留输入中的极端重建动量：全选择pz0范围50.0298–3.73886×10⁶ GeV、true E为50.2850–6206.9000 GeV，端点落箱，没有裁掉离群者。

### 5.1 train参考灵敏度

所有误差均对应选中N=1000、r=1；σ_f为无量纲比例的绝对误差，σ_r/r为百分数。

| 表示 | 已知响应σ_f | 有限MC σ_f | 已知σ_r/r | 有限MC σ_r/r | 有限MC r的68% profile区间 |
|---|---:|---:|---:|---:|---|
| M μ-only | .01378597 | .01387014 | 14.7324% | 14.8224% | [.856658,1.153282] |
| S 灵活scalar F7 | .01142936 | .01146840 | 12.2140% | 12.2557% | [.882093,1.127363] |
| J μ/ML二维 | .01415007 | .01424070 | 15.1215% | 15.2184% | [.853007,1.157556] |

有限MC误差比J/S=**1.241734**，500次component分层来源配对95%区间**[1.230569,1.252341]**；M/S=**1.209422 [1.195693,1.223109]**。J误差高24.173%，不是降低；已知响应对照同样较差，有限MC仅使J和S误差各增加约0.64%/0.34%，所以这次排序不能归因于有限MC修正突然放大。该说法只适用于本固定分箱/模型/选中参数，不证明训练样本已饱和或全部额外信息无用。[完整Fisher/来源抽样结果](stage63_energy_ml/bootstrap.json)。

### 5.2 留出来源pooled闭合

实际cal低/高为841/7599，eval为1114/12943。各自r_true为**.948446/.737604**，不是1。下表为有限MC结果；区间是profile参考区间，最后一列按拟合点σ_r计算。

| 角色 | 表示 | r_true | r_hat | 68% profile区间 | (r_hat−r_true)/σ_r |
|---|---|---:|---:|---|---:|
| cal | M | .948446 | .865368 | [.730294,1.009968] | −.592110 |
| cal | S | .948446 | .898340 | [.788181,1.017573] | −.432303 |
| cal | J | .948446 | .844405 | [.706878,.992054] | −.729013 |
| eval | M | .737604 | .580984 | [.462954,.707747] | −1.270816 |
| eval | S | .737604 | .636584 | [.544791,.736824] | −1.031638 |
| eval | J | .737604 | .491540 | [.376838,.615410] | −2.042975 |

J的eval低成分强度偏低约33.36%，区间没有包含经验真值；S也略超1σ阈值，不能把S当已验证物理模板。已知模板拟合也保留在[all_fits.csv](stage63_energy_ml/all_fits.csv)，不是用有限MC掩盖偏差。这里的偏移是两组件固定内部谱形状和该来源响应的综合失配，不能直接解释成能量尺度或detector系统。

### 5.3 两类预定压力

下表为有限MC的r偏移/σ_r；所有压力仍保持原role的低比例和N=1000。

| role/压力 | M | S | J |
|---|---:|---:|---:|
| cal nominal | −.592110 | −.432303 | −.729013 |
| cal low×.75 | −.629596 | −.541242 | −.725438 |
| cal low×1.25 | −.558057 | −.334964 | −.732292 |
| cal high-y×.75 | −.830136 | −.448091 | −.758755 |
| cal high-y×1.25 | −.360578 | −.416641 | −.699363 |
| eval nominal | −1.270816 | −1.031638 | −2.042975 |
| eval low×.75 | −1.311237 | −1.155152 | −2.047378 |
| eval low×1.25 | −1.234380 | −.922205 | −2.038969 |
| eval high-y×.75 | −1.536846 | −1.050882 | −2.071419 |
| eval high-y×1.25 | −1.012929 | −1.012553 | −2.014644 |

低能压力的目标支持train/cal/eval为767/150/208例，high-y混合目标为466/93/154例。cal压力实际加权ESS范围8431.570–8434.297，eval为14045.376–14047.552例，不是新增独立事件；组件内归一、权重正和总N均验证。J最高压力偏移2.071419σ；J比S增加绝对偏移最大**1.116764σ**（eval low×1.25），超过预定.25σ。四项研究验收全部失败，未后改阈值。[pooled全部参数/区间/ESS](stage63_energy_ml/pooled_fits.csv)。

### 5.4 全部来源与支持

| 角色/表示 | 来源 | 拟合落边界 | 常规内点来源的绝对r偏移/σ_r中位数 | 最大值 | 经验真值落入68%区间的来源数 |
|---|---:|---:|---:|---:|---:|
| cal M | 16 | 5 | 1.970928 | 3.949576 | 0 |
| cal S | 16 | 2 | 1.512184 | 3.543352 | 3 |
| cal J | 16 | 6 | 3.672542 | 4.577663 | 0 |
| eval M | 22 | 9 | 1.773604 | 3.322198 | 2 |
| eval S | 22 | 0 | 2.111971 | 3.770176 | 4 |
| eval J | 22 | 14 | 1.703481 | 2.502626 | 0 |

实际cal/eval没有零低组件来源，但有大量f_hat=0边界拟合，全部保留，不计算其常规pull；统计程序也明确处理真实比例边界。cal来源每组341–640例、低组件2–119例；eval每组344–705例、低组件4–117例。上述落区间个数是有限经验来源响应的描述，**不是coverage估计**：不同来源内部E谱、生产组件和位置等混合本来不同，部分来源事件有限，机械放大到N=1000会放大经验响应噪声。不能将不闭合全归咎少数尾事件，也不能因J内点中位数小于某对照就忽略14个边界解。[完整逐来源结果](stage63_energy_ml/source_fits.csv)、[全部支持](stage63_energy_ml/support.csv)。

eligible输入缺失21/3/7，未确认1495/301/510，负修正1963/431/913均保留。三表示的无效统计量格实际都为空；这与输入NaN不矛盾，F7仍给有限预测。train低组件90/91来源有支持，高组件91/91；三表示低组件在17总格中的零格数11/8/10，高组件均仅专用无效格为零。

## 6. 物理与程序原因：明确阴性范围，下一步检查宽组件形状

程序故障已独立修复，最终精度远优于冻结阈值；没有证据把最终24%误差损失归为优化未收敛。一个直接的表示因素是**等总格数不等于保留同样的低能细节**：J的M分位边界为222.5064/396.6403/693.9848 GeV，train 4331个低能中**4328个（99.9307%）**集中第一M层，只分得四个修正格；另外12格主要描述高组件。S的16个能量分位格是不同的划分，J的离散格并不包含S格，连续(M,S−M)能恢复S的代数事实不能保证这个4×4离散表示更有信息。[逐层支持](stage63_energy_ml/joint_layer_support.csv)。这是预定特定布局的阴性，不是所有联合统计量或连续读出信息的否定；按停止规则不再开更细格/布局扫描。

来源响应失配也有可测形状迹象。eval相对train低组件的M/S/J响应TV为**.016837/.021189/.029874**，高组件为**.078489/.083202/.074421**；高组件mean(log true E/GeV)从**6.498560**变为**6.642640**，相差+.144080。cal高组件mean为6.560084，漂移较小，闭合偏移也较小。这些是回收后的描述性诊断，没有用于改验收。固定整个≥200 GeV响应，把其内部谱混合差也吸收到r，存在模型失配的具体路径；规定high-y子类只占高组件约1.2%，其±25%压力并未覆盖所有宽高能谱变化。**尚未分离**内部E谱/生产组件/条件响应/训练模板乐观性：F7用train事件训练，而模板也来自train，cal global offset同样不是独立；不能据TV差唯一宣布detector失配或训练过拟合。[完整组件响应/真能中心](stage63_energy_ml/component_response.csv)。

因此保持F7，结束本次二维扩展；低能点重建仍未解决，本轮没有新的点误差测量。stage55替代flux仅+139个低能训练、stage62的概率增量和旧低能点失败都继续有效；本轮没有重新用这些run训练，更未证明样本量饱和。

**下一单项拟定stage64：固定M/S和原选择，分解宽组件内部谱混合与条件响应迁移。** 输入仅本轮紧凑缓存和模板，不新增模型/分箱/ROOT/RDO/谱profile/toy。事前冻结真E粗箱50/100/200/400/800/1600/3200/6400 GeV与pi/k/charm分层、train参考顺序，将每组件cal/eval与train的有符号格概率差精确分成共同支持上的混合改变、条件响应改变、未匹配支持三项；不将重加权计数冒充独立MC。用同一预定线性敏感度投影比较三项对既有f偏移的贡献，500来源重抽样说明稳定性，保留全部未匹配质量和原始响应。不自动做新的nuisance拟合、加格或能量训练。验收是分解逐格守恒、支持/权重/来源区间透明，物理归因不唯一时给未定及最小独立低E/同p高E补样需求；只有证据支持才安排响应或新独立样本。拟议1CPU/2GB、≤1个Condor、CPU≤10分钟、最终≤5 MB，先pilot冻结，收益/实际成本**未测量**。本轮不执行。

共同signed/rectified raw、stage54 data占据、interaction/FSI/材料、接受度/背景及真正独立生产确认仍须交付。本轮选中条件参数研究没有成为最终flux结果；stage54现存工具/缓存未改变、未混入本次提交。方法入口沿用stage61的有限MC模板与FASER flux文献，没有新增文献检索。

## 7. 实测资源与存储

最终脚本内部wall **13.462264 s**、CPU **13.312096 s**、峰值RSS **93.671875 MiB**；`/usr/bin/time`含启动/导入为wall **15.49 s**、user/sys **14.20/.34 s**、maxRSS **95,920 KiB**。Condor两个任务各启动一次，退出码1/0，合计remote CPU **18 s**、remote wall **28 s**，均1CPU/3000 MB；没有第三任务或自动重试。[Condor实际记录](stage63_energy_ml/condor.json)。

Condor接收字节两次2,164,364/2,165,453，共**4,329,817 bytes**；BytesSent为1,137/1,929 bytes，仅Condor返回控制/日志，不是XRootD结果归档字节。最终XRootD返回压缩包实际文件148,688 bytes，失败诊断包2664 bytes；大小不等同实际网络流量。最终脚本`/proc` rchar=2,356,193、wchar=959,447、read_bytes=0、write_bytes=974,848 bytes，缓存/导入和kernel记账有明确限制。**actual EOS物理/网络I/O未测量**，不将read_bytes=0写成零I/O。最后一次独立报告/验证wall **2.130979 s**、CPU **1.586960 s**、峰值RSS **137.285156 MiB**，不混作batch CPU；此前一次同样QA也通过，资源未累加进该值。

最终缓存与目录证据合计 **3,580,216 bytes（3.414360 MiB）**，不含清单自身、源代码和本主报告，低于10 MB冻结上限；逐文件实测见[storage.json](stage63_energy_ml/storage.json)。

图表：[PNG](stage63_energy_ml/joint_response.png) / [PDF](stage63_energy_ml/joint_response.pdf)；机器可读完整拟合、曲线、模板、500来源误差、支持和QA均在stage63目录。原始输入不复制，临时payload和返回归档核实后删除；不保存逐事件能量网格或新ROOT。

## 执行与复现入口

```bash
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
export PYTHONNOUSERSITE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python ml/prepare_joint_response.py
# 原协议冻结后首个任务因数值KKT检查中止；保留记录，不覆盖历史。
python ml/validate_joint_solver.py
# 按submission/runner打包紧凑缓存与代码，经XRootD交给AFS spool中的Condor任务。
condor_submit AnalysisZipFramework/submission/ml_joint_response.sub
python ml/report_joint_response.py
python -m py_compile ml/joint_response.py ml/prepare_joint_response.py ml/validate_joint_solver.py ml/run_joint_response.py ml/report_joint_response.py
bash -n AnalysisZipFramework/submission/run_ml_joint_response.sh
```

冻结prepare/验证程序有不可覆盖保护，上述为实际工作流程入口，不应在现有产物上重新执行prepare或正式profile。正式payload为`software/energy-ml-joint-stage63.tar.gz`，仅含必要Python文件、v2协议和紧凑观测缓存；AFS spool为`/afs/cern.ch/user/x/xcheng/nu_mu_stage63`，EOS返回目录为`ntuples/energy_ml_stage63/`。解包核实后删除重复归档/临时payload；没有复制原ROOT/RDO、模型或全量能量扫描网格。最终缓存为`ml/artifacts/stage63/observables.npz`，物理表图/数值/协议为`workbook/stage63_energy_ml/`。
