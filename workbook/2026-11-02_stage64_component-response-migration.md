# Stage64：宽组件谱混合与条件响应迁移分解

## 1. 目标与阶段结论

按路线§44，只用固定M=log(pz0/GeV)和S=log(E_F7/GeV)解释stage63的低能成分闭合偏移。**宽组件内部真能谱×生产组件混合变化，确有来源稳定的负偏移贡献；不能将原闭合问题全归为ML过拟合或detector失配。** eval的M/S混合贡献分别为−1.179538/−.651509个百分点；S还存在−.398815 [−.687241,−.116617]个百分点的条件项。粗格内谱、几何、相互作用、模型训练内模板效应仍包含在条件项中，尚未唯一分离。

完成一个Condor任务9661865.0，500次来源重抽样、2004次代数分解；0新能量训练、F7推理、谱profile、ROOT/RDO/生产或coverage toy。维持F7、原选择/保护和全部困难事件，未恢复二维J推广、加格或新网络。该阶段解释现有MC条件参数偏移，没有改善点重建或测量data/未选中flux。

## 2. 输入、冻结与支持

只读`ml/artifacts/stage63/observables.npz`（2,236,976 bytes）、stage63的`protocol_v2.json`、`templates.json`、`fits.json`和`support.json`。没有复制新的持久事例缓存、重读locked test或原ROOT、重建raw、恢复删除分片、做SHA；stage63全部输入/历史协议未修改。

F7既有62列、pz0-only线性动量、11个scintillator raw charge、VetoNu reduced及signed/状态/依赖NaN政策继续有效；px/py、q/p和弯折不受线性动量限制。M/S使用原16常规格与专用无效格，端点/离群保留，部署统计量不接收truth。

| 角色 | 事件/来源 | true50–200 | true≥200 | 输入缺失 | 未确认 | S−M<0 |
|---|---:|---:|---:|---:|---:|---:|
| train | 41447/91 | 4331 | 37116 | 21 | 1495 | 1963 |
| cal | 8440/16 | 841 | 7599 | 3 | 301 | 431 |
| eval | 14057/22 | 1114 | 12943 | 7 | 510 | 913 |

这些计数与stage63完全相同；原42个输入缺失者中另11个既有保护者保持原角色，不混称本轮删除。原pz>50 GeV选择不变，巨大重建动量、high-y、未确认、负修正、尾部和溢出均保留。cal/eval是已开发比较，保守来源去重不等于完整生成谱系独立认证。

[执行前冻结协议](stage64_energy_ml/protocol.json)于2026-11-02 22:12:56 UTC冻结：true E边界50/100/200/400/800/1600/3200/6400 GeV，并保留外侧；与pi/k/charm交叉为27个k。低/高truth组件各自计算，不将f比例变化混入组件内部响应。所有162条角色×组件×k支持、空格、来源和困难子类计数见[support.csv](stage64_energy_ml/support.csv)。N<20或来源<3仅为预定薄支持标记，不筛事件/层。所有名义事例单位权重，ESS=N；没有以标准化重加权替代实际MC计数。

## 3. 方法和不确定性口径

对每个truth组件，train联合概率为J_T(k,z)=w_T(k)R_T(z|k)，role为J_R。参考顺序固定train，在两侧均非空的k上：

- 混合项：Σ_shared (w_R−w_T) R_T；
- 条件项：Σ_shared w_R (R_R−R_T)；
- 非共同支持项：其余k上原始J_R−J_T，只使用有实际定义的一侧。

三项逐格相加必须恢复原始ΔR。未匹配质量不删、不补造条件响应；有符号项范数用half-L1，只有原始总响应差的half-L1才是TV距离，分项范数不必相加为总TV，也不作“解释百分比”。该参照顺序定义的代数分解不是唯一因果分解。

各role用其实际f_true：cal=.09964454976303318，eval=.07924877285338265，固定选中N=1000。a/b为stage63 train原模板，v=a−b，q=f_true a+(1−f_true)b；协方差V沿用stage63有限MC公式与相同特征值截断。固定中央线性算子`L(δq)=vᵀV⁺δq/(vᵀV⁺v)`，低/高分项先分别乘f_true/(1−f_true)，再相加投影为δf。算子不按本轮新结果修改；对照仅为stage63已保存的精确profile `f_hat−f_true`，本轮没有新fit或无偏修正。

500次pi/k/charm分层保守来源多项式重抽样，train/cal/eval独立seed2026110264/265/266；同一train抽样用于cal/eval，M/S配对。每次重新计算共同/非共同支持，名义f_true及中央算子固定。区间为2.5/97.5百分位，条件于固定F7、分箱和算子，不包含重训、算子估计、完整谱系或detector/interaction系统；不是正式参数coverage，也未作多重检验修正。来源只有91/16/22组，稀少层的bootstrap不能产生新独立事件。

来源权重ESS 95%范围（事件等效计数）如下；它只描述每次重复来源权重的集中度，不替换原始支持或作为新增MC约束：

| role | 全体 | 低组件 | 高组件 |
|---|---|---|---|
| train | [18320.881,24565.651] | [1790.628,2604.425] | [16436.916,22043.803] |
| cal | [3342.108,6105.557] | [307.332,627.706] | [3021.108,5499.493] |
| eval | [5751.371,9759.499] | [425.576,826.483] | [5289.501,8984.752] |

## 4. 实测偏移分解

下表全部为**δf的百分点（pp）**，不是相对百分比；1 pp在固定N=1000的条件场景相当于10例成分份额。括号为500次来源区间，各项保持符号及相消。

| 角色/表示 | 混合 | 条件 | 未匹配 | 总线性偏移 |
|---|---|---|---|---|
| cal M | −.478205 [−.646397,−.317051] | −.309246 [−.920609,+.420121] | −.011560 [−.018509,−.004552] | −.799012 [−1.387475,−.081019] |
| cal S | −.291563 [−.414896,−.170202] | −.182103 [−.506529,+.143942] | −.013398 [−.021451,−.005276] | −.487064 [−.798318,−.156230] |
| eval M | −1.179538 [−1.330619,−1.023585] | −.419810 [−.910294,+.034221] | 0 [−.013044,0] | −1.599348 [−2.088732,−1.119703] |
| eval S | −.651509 [−.774186,−.535650] | −.398815 [−.687241,−.116617] | 0 [−.015490,0] | −1.050324 [−1.363779,−.712609] |

完整低/高/合并分项见[projection.csv](stage64_energy_ml/projection.csv)，全部有符号格向量见[vectors.csv](stage64_energy_ml/vectors.csv)，分层投影与来源区间见[stratum_projection.csv](stage64_energy_ml/stratum_projection.csv)。混合项在四个case均保持负向，且M不依赖新ML训练，支持原闭合偏移含宽组件固定形状失配这一判断。

| case | stage63精确profile δf/pp | 本轮总线性δf/pp | 精确−线性/pp |
|---|---:|---:|---:|
| cal M | −.792771 | −.799012 | +.006241 |
| cal S | −.476472 | −.487064 | +.010591 |
| eval M | −1.575900 | −1.599348 | +.023448 |
| eval S | −1.010323 | −1.050324 | +.040001 |

一阶投影与既有profile偏移相近，但不完全相同；这是诊断近似的实测误差，不是重算profile或“修正后闭合成功”。[linear_checks.csv](stage64_energy_ml/linear_checks.csv)。

eval高组件混合对M/S贡献−1.188140/−.675499 pp，低组件混合为+.008601/+.023990 pp；故合并负向主要来自高组件。eval S条件项中低组件为**−.183912 [−.359688,−.015364] pp**，高组件为**−.214903 [−.427708,+.009568] pp**。低/高条件变化同向，合并区间不跨零，但不能据单层未校正区间唯一指认物理机制；cal条件合并区间均跨零。

### 4.1 原始响应与分项范数

下表为无量纲half-L1；总列为原始TV，分项含相消，不能按列直接相加。

| role/组件/表示 | 混合 | 条件 | 未匹配 | 总TV |
|---|---:|---:|---:|---:|
| cal 低 M | .001366 | .007253 | .000577 | .007653 |
| cal 低 S | .000848 | .010258 | .000577 | .010485 |
| cal 高 M | .025103 | .018198 | 0 | .035099 |
| cal 高 S | .027728 | .021424 | 0 | .041100 |
| eval 低 M | .007424 | .011833 | 0 | .016837 |
| eval 低 S | .004418 | .021963 | 0 | .021189 |
| eval 高 M | .067864 | .017347 | 0 | .078489 |
| eval 高 S | .076073 | .014996 | 0 | .083202 |

与stage63描述性TV一致。本轮进一步表明高组件的混合项范数较大，但这没有消除条件项，也不等同对低能点误差作损失归因。全部区间见[component_norms.csv](stage64_energy_ml/component_norms.csv)，不以TV bootstrap区间离零当零假设显著性检验。

### 4.2 未匹配与薄支持

cal没有true50–100 charm，train该层有**5例/5来源**，占train低组件**.115447%**，全部作为未匹配质量保留；未匹配低组件质量来源区间为[.045460,.184839]%。eval该层仅1例/1来源，名义共同支持完整，但重抽样可能失去此层，train低组件未匹配质量区间为[0,.162832]%。名义为零不意味着独立支持充足。[unmatched_support.csv](stage64_energy_ml/unmatched_support.csv)。

| true E/生产 | train N/来源 | cal N/来源 | eval N/来源 |
|---|---:|---:|---:|
| 50–100 π | 649/34 | 132/6 | 179/8 |
| 50–100 K | 113/40 | 18/8 | 28/10 |
| 50–100 charm | 5/5 | 0/0 | 1/1 |
| 100–200 π | 2731/34 | 518/6 | 690/8 |
| 100–200 K | 778/46 | 167/8 | 199/11 |
| 100–200 charm | 55/10 | 6/2 | 17/3 |
| 200–400 π | 5910/34 | 1109/6 | 1574/8 |
| 200–400 K | 3067/46 | 545/8 | 899/11 |
| 400–800 π | 6327/34 | 1282/6 | 1927/8 |
| 400–800 K | 6689/46 | 1304/8 | 2157/11 |

分层条件项提示具体验证输入，但不作为事后cut：eval S的200–400 π贡献−.130848 [−.274344,−.000121] pp，train/eval支持5910/34与1574/8；eval低100–200 π为−.129139 [−.281659,+.001767] pp，支持2731/34与690/8。cal M的400–800 K为−.413681 [−.571928,−.222782] pp，支持6689/46与1304/8；不是全由稀少charm驱动。全部非空层及薄支持标记保留在[conditional_support.csv](stage64_energy_ml/conditional_support.csv)，排序只是描述性输入清单，未作多重检验校正或新模型选择。

## 5. 程序验证、物理限制与需要的输入

103个合成分解检验覆盖纯混合、纯条件、两侧非共同支持、专用空统计格，最大守恒误差5.5511×10⁻¹⁷；独立simplex切空间线性解与特征分解算子差1.9540×10⁻¹⁴。正式2004次分解的最大概率/投影守恒误差分别为**1.3054e-16 / 2.4286e-17**，均小于冻结10⁻¹²阈值。

回收后独立逐事例分层计数、显式k循环分解和完整V伪逆复核，最大误差：格向量**2.7756×10⁻¹⁷**、中央δf投影**6.9389×10⁻¹⁸**、线性算子**4.4409×10⁻¹⁶**。对bootstrap索引0/249/499独立重建逐事件来源权重，12个case最大投影差**1.5613×10⁻¹⁷**。原M/S落箱和全部角色/保护支持检查通过。[validation.json](stage64_energy_ml/validation.json)。代码没有优化器或新模型推理；数值不一致不是本轮负偏移的证据来源。

条件项不是“相同真值条件下纯detector响应”：真E粗箱内仍有连续谱，几何/入射方向/y/interaction/FSI/材料也未固定，F7与train模板使用同一训练事件，cal参与原global offset，bootstrap不重训。不能据本阶段给能标修正、反调BDT、称低能样本饱和或把未知写成原因。true50–100传统与F7的旧点风险及stage62概率增量没有在本轮重测，仍沿用其原结论。

最小后续输入清单：

- 对条件差的来源独立核查，需要保留未参与F7权重训练的来源身份/生成谱系、相同true E与生产分层，并检查格内E、y、入射/顶点几何混合；现有cal/eval已经开发，不能叫新独立确认。若要隔离训练内模板乐观性，需要诚实的训练外响应模板及其有限支持，不能把train多次重抽样当解决。
- true50–100 charm的cal零支持、eval单例，以及100–200 charm的6/17例，是具体缺层；π/K低能和同pz高E/high-y仍需保留共同支持。eval200–400 π中同reco pz50–100且high-y仅26例，400–800 π/K为28/31例；不能只补容易低能核心。精确新增事件数/功效**未测量**，不照抄历史3000–5000目标。
- 如需检验共同读出响应，必须有可核实的signed整窗/rectified raw定义、waveform状态/积分窗口、active-mask/有效读出与μ轨迹控制，再连接ν强子活动；本缓存没有Timing/calo等逐变量，**低可见活动条件支持和data差异未测量**，不能用小ML修正冒充quiet或把μ控制替代ν响应。stage54占据和共同raw仍须交付。

## 6. 实际资源、偏差与产物

synthetic pilot wall **.035074 s**、CPU **.024814 s**，ru_maxrss **616.605469 MiB**；100次分解内核wall/CPU .020599/.020430 s，外推2004次仅.412803 s，不是实际完整作业成本。单线程批量group直方图与来源矩阵复用，避免重复原ROOT I/O，不保存逐事例网格。

正式脚本内部wall **2.149879 s**、CPU **1.871746 s**、峰值RSS **105.691406 MiB**；`/usr/bin/time`含启动导入wall **3.82 s**、user/sys **2.66/.21 s**、maxRSS **108228 KiB**。Condor 9661865.0 **ExitCode=0、NumJobStarts=1**，remote CPU **2 s**、wall **7 s**；无重试/额外任务。报告/独立验证wall **2.045031 s**、CPU **1.709147 s**，ru_maxrss **616.605469 MiB**。ru_maxrss是进程高水位，不是内核独立RSS或GPU显存。

**内存请求存在记录明确的协议偏差：** 冻结值和`.sub`均为2000 MB，提交后独立dry-run也为2000；最终调度ClassAd的RequestMemory/MemoryProvisioned却为**3000 MB**。本轮提交前未核对站点最终请求变换；具体站点配置未进一步定位，不能宣称符合2GB请求上限。实际RSS约106 MiB，任务数/CPU/存储均在冻结预算内；保留原协议，不反写为3GB、不重交任务，下阶段按已观察到的3GB请求预算冻结。见[submission_resources.json](stage64_energy_ml/submission_resources.json)和[condor.json](stage64_energy_ml/condor.json)。

Condor接收**2,285,674 bytes**、返回控制/日志**310 bytes**；payload实际文件2,284,685 bytes，XRootD结果包326,469 bytes，两种文件大小均不冒充真实网络流量。batch `/proc` rchar=3,229,147、wchar=409,285、read_bytes=0、write_bytes=438,272 bytes；只是进程/kernel记账，**actual EOS物理/网络I/O未测量**。缓存复用，无新增逐事例文件；解包验证后删除临时payload和返回归档，未复制原输入作为持久产物。

本轮新增目录证据合计 **516,613 bytes（0.492681 MiB）**，不含清单自身、源代码及本主报告，低于5MB上限；既有输入只复用，没有持久副本。[逐文件实测清单](stage64_energy_ml/storage.json)。

图表：[PNG](stage64_energy_ml/response_migration.png) / [PDF](stage64_energy_ml/response_migration.pdf)；全部输出位于`workbook/stage64_energy_ml/`，bootstrap NPZ只含来源汇总投影/范数/未匹配质量/ESS，不含新逐事例数据。

## 7. 下一单项与停止规则

**保持F7，下一阶段只量化“高组件谱硬度自由后，低比例是否仍可辨识”。** 本轮混合项四case均稳定负向，为放松固定宽高组件形状提供了具体依据；这不是重开J或给残余条件差一个detector解释。

拟定stage65：固定M/S原格与输入，以高组件选中MC的`bα(E,z) ∝ (E/400 GeV)^α b0(E,z)`定义一个连续硬度方向，只在α=0做局部二维Fisher/线性响应研究。方向`∂q/∂α=(1−f) Σ_high,z [log(E/400)−mean_high log(E/400)]/MH`；与低比例方向a−b共同使用同一有限MC协方差V。报告固定α与自由α的σ_f/σ_r、相关性、秩/条件性，并投影既有响应差及本轮分项，保留线性模型未解释残差。500保守来源重抽样说明方向和来源稳定性；0新能量fit/推理/ROOT、0非线性谱profile或coverage toy，不把一阶偏移缩小单独当成功。

输入仅stage63缓存/模板/旧fit及stage64分解；先冻结导数、正交/共线数值QA、奇异处理、bootstrap与预算。验收是可辨识性/误差代价与残余全部透明，α无约束而r退化时给需要的独立谱/响应输入，不加事后先验、更多参数或toy调覆盖；条件项仍需上述独立响应和共同读出验证。拟议≤1个Condor/1CPU/**3GB**、CPU≤10分钟、最终≤5MB，实际成本/收益**未测量**，本轮不执行。

共同raw/stage54、ν interaction/FSI/材料、接受度/背景和真正独立生产确认仍须交付。物理参数是selected-spectrum形状，连续高能硬度同样不等于未选中flux；沿用stage61的FASER flux和有限MC文献入口，本轮未新增检索。stage54已有工具/缓存保持原状，不混入本阶段提交。

## 8. 执行命令

```bash
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
export PYTHONNOUSERSITE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python ml/prepare_response_migration.py
# submission runner将必要代码、stage64协议、stage63既有缓存/模板/fit打包传入scratch。
condor_submit AnalysisZipFramework/submission/ml_response_migration.sub
# XRootD返回并解包后：
python ml/report_response_migration.py
condor_history 9661865 -limit 1 -json -attributes ClusterId,ExitCode,NumJobStarts,RemoteUserCpu,RemoteSysCpu,RemoteWallClockTime,RequestMemory,BytesRecvd,BytesSent
condor_submit -dry-run /tmp/stage64-submit-dryrun.ad AnalysisZipFramework/submission/ml_response_migration.sub
python -m py_compile ml/response_migration.py ml/prepare_response_migration.py ml/run_response_migration.py ml/report_response_migration.py
bash -n AnalysisZipFramework/submission/run_ml_response_migration.sh
git diff --check
```

协议和正式结果有不可覆盖保护，上述记录实际入口，不应在现有产物上重跑prepare/正式任务。AFS spool `/afs/cern.ch/user/x/xcheng/nu_mu_stage64`；临时payload `software/energy-ml-migration-stage64.tar.gz`、返回目录`ntuples/energy_ml_stage64/`，核实后去重。先写本中文报告，再与代码/配置/紧凑结果本地Conventional Commit，不推送。
