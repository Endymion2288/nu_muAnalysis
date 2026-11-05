# Stage115：逐通道测量状态与强BDT锚定残差——有限两臂未获得共同低能收益

日期：2026-11-05；起始commit `522f6db`。按用户更新的[路线§96](../docs/nu_mu_energy_ml_revised_roadmap.md)和[Stage114研究重置§4](2026-11-05_stage114_measurement-state-and-risk-research-reset.md)，完成一次实际能量实验，未再以综述/单独QA代替能量结果。

## 1. 结论、完成范围和决策

**唯一HTCondor任务9668138首start/exit0，完整71376 active事件的固定A/B消融与四次预定凸求解已完成；主候选B没有同时改善两个低能组，未建立逐通道状态增量，两臂均未通过最终联合验收。** 本次数据阴性针对冻结的两个有限方案，不是所有残差/状态或现有信息的极限。

|cal_post比较|两低能最坏RMSE比|95%条件区间|有效draw/500|共同改善|
|---|---|---|---|---|
|B/direct_cal|1.024843205547326|[1.0058712848637628, 1.0508710279789928]|500|False|
|B/A|1.0|[1.0, 1.0]|500|False|
|A/direct_cal|1.024843205547326|[1.0058712848637628, 1.0508710279789928]|500|False|


主端点为原cal_post两个真低能组RMSE相对参考的最大值，B为唯一主候选。B/f0的95%条件区间整个高于1；单组检查显示第二箱恶化。B/A本端点等于1，且两臂全部已报风险及训练目标相同；本次未见状态增量。不能据此宣称所有逐事件输出已经独立证明逐位相同，也不能推论状态没有任何条件信息。

cal_post最低能B/f0=.9218487357175409 [.870637970642671,.9699406347472291]有局部下降；第二低能1.024843205547326 [1.0058712848637628,1.0508710279789928]、总体1.0173137142634907 [1.0121110600932808,1.0227634158996477]有代价。开发test也出现同方向取舍，具体表见下文。没有从A/B选择另一个赢家、增加offset、扩大树数或再训seed。

两臂都已实际完成，**本固定方案结束，不晋升**。Stage110固定差、Stage108三格/遮挡、旧重权/门控的结束状态保留。原项目“全区域改善并恢复两低能”的目标仍未达到；真实响应/interaction/FSI/材料/Calo/接受度/背景和独立确认仍未交付。

## 2. 输入、角色、状态回接和变量政策

只使用现有选中缓存，没有ROOT/EOS源扫描、新样本、生产/重建、split重划或选择变化。输入和实际字节清单见[package.json](stage115_energy_ml/package.json)：

- 原Stage94 `evaluation_input.npz`、`cal_partition.npz`，Stage87 `split.npz`与强direct的`predictions.npz`。
- Stage55 `dataset.npz`＋Stage56 `readout.npz`，以及Stage70/81/82/83 `support.npz`，按(origin,origin_row)回接原62和11路status，逐项核incoming/run/eventID/group/component和truth E。
- 原Stage87树配置、Stage94已存标量风险供只读控制核验。基线f0=同split原strong direct_cal log能量，**缓存已包含train输出，0新基线预测/重训**。

完整兼容池89033行，原隔离17657行不参与拟合/风险；active=71376，train/cal/test=46575/11612/13189，对应incoming代理37556/10811/12125。原1016新增K全部保留。各角色incoming全部视图权重和1，未按真能量重抽样/删除难尾。cal内原分区purged/select/post=423/5443/5746不改，保留原post权重；cal_select和cal_post均未参与本次字典/头训练。它们早已开发使用，不称新blind。

状态/特征回接各origin active行数为55:63656、70:28、81:742、82:1016、83:5934；全部71376行11通道status有效可用，缺status=0。未知状态路径仍事前定义为NaN＋共同availability；本次没有靠删除缺失状态事例获得结果。原62缺项在train/cal/test为21/6/5行，全部保留；例如test缺项层5行B log-RMSE=.24018819554231716，稀少不能泛化。[input_validation.json](stage115_energy_ml/input_validation.json)、[状态全表](stage115_energy_ml/state_coverage.tsv)保留完整证据。

A=原typed62＋wave_invalid/fit_failure/calo_invalid＋共同status_available，共66维；B=A＋11通道×4布尔状态，共110维。四族为overflow=4、threshold_failed=1、fit_failure=16|32、wave_invalid=8|128|256，非互斥；status不是连续整数大小。通道顺序沿原SCINTILLATORS，未知/负/非整数/未识别>511状态标通道NaN，不当正常0。共同availability表示11通道全已知，不将某通道缺失当物理信号。

|train通道|分母/行|overflow|threshold_failed|fit_failure|wave_invalid|
|---|---|---|---|---|---|
|VetoNu0|46575|0|34716|11|0|
|VetoNu1|46575|0|34139|4|0|
|Veto10|46575|19825|223|1254|0|
|Veto20|46575|19174|0|1168|0|
|Veto21|46575|18443|0|885|0|


计数是本次全部train行的channel状态数，有重叠、与incoming独立数不同，不能相加称独立异常事件。Veto10/20/21有大量overflow，VetoNu0/1的threshold_failed也大量存在；新增位并非全池恒定零。wave_invalid本表为0，不能据此推断真实data/全部来源不存在坏波形。完整cal/test及全部11通道在TSV；test overflow_any=7511行、threshold_any=12176行，均留风险报告。

一次方重建动量仅pz0，原px/py、q/p、弯折仍允许；raw11/status、typed NaN、合法signed负值和Calo缺项规则不改。现行VetoNu reduced为signed、无通用数值sentinel列表，未将所有负reduced变NaN，也没有换回fitted charge。原native fitted/reduced选择不改，pz0>50 GeV保持，无低于50 GeV的模型外推。Stage113正文误排的影子表继续以原TSV/Stage114澄清为准，不反写历史。

## 3. 两个固定字典与凸风险头的实际求解

[协议](stage115_energy_ml/protocol.json)在提交/新数值结果前冻结，seed2026110515。每臂一次8棵depth3/min_child_weight200的小树，eta=.04、subsample=.8、colsample1、reg_lambda10、hist/线程1沿原基线配置，目标为train的logtruth−f0、原incoming权重，base_score为该train残差加权均值−.025135357974598052。该train基线已经拟合过train，**不是OOF残差**。

两臂实际各52个叶指示基（上限64），train加权Gram去数值零特征值后rank45；保留>1e−10×最大特征值，变换后global train Gram为单位阵，便于数值求解/二次修正规模计算，不利用cal/test标签。叶系数允许正负，f=f0+Φθ，无局部gate/新offset/按真E推理；truth E/y/confirmed只定义train损失组或评价。原树保存重载train叶完全一致；头系数与叶编码随产物保存。

主解min τ：两低能各自MSE≤τ×传统MSE；all相对f0≤1.01²，其余原五层≤1.03²。原八层各H+和H−不超过f0的train值，H+=mean_w max(e−ln1.5,0)²，H−=mean_w max(ln.5−e,0)²。次解在τ≤τ主+1e−8下最小化global train修正平方。约束按max(reference risk,1e−4)定标，归一化可行容差1e−7预先冻结，没有用容差掩盖实际大尾变化。

使用既有SciPy SLSQP、解析Jacobian，每次max200/ftol1e−10，无安装、求解器/初值/参数网格；每臂恰好两次，合四次。A/B实际数值相同：

|求解|success/迭代|目标|最大归一化违反|近似KKT驻点∞范数|互补残差∞范数|
|---|---|---:|---:|---:|---:|
|主解|True / 124|τ=2.032000317154125|1.0731496969647966e−12|1.4413578114047532e−5|1.3046086480272811e−12|
|次解|True / 151|mean train correction²=.0023840304354885724|1.5647325728963386e−11|5.918279875462805e−6|2.2554220855002626e−10|

次解τ上限2.032000327154125。KKT以归一化slack≥−1e−6的active set做非负乘数NNLS诊断；这是**近似**数值证据，未交严格dual下界/全局最优性认证，不能仅以success声称训练已最佳。主解活跃风险约束为最低能箱及all保护，第二低能箱未活跃；相对传统的minimax目标不等价于“每一低能都优于f0”。

直接预测空间另核了train MSE与16个平方hinge约束，没有用优化器公式自证全部结果。[A尾约束](stage115_energy_ml/A_train_tail_constraints.tsv)、[B尾约束](stage115_energy_ml/B_train_tail_constraints.tsv)完整保留。例如train低pz真高E负H由.027203992915664946变.027203992915731265，差6.631847848659334e−14为数值量级；对应实际负tail50率却从14.458958830538437%增至15.024850003690593%。**连续尾损失保护既不等于tail率保护，也不保证留出表现。**

[fitting锁定记录](stage115_energy_ml/fits_frozen.json)在两臂模型与θ保存后、任何新test前向/风险前落盘；随后统一推断，两臂points保存重读逐位一致。基线本来已经保存，不新增f0 forward。所有已报A/B目标、约束和风险相同；本次未另外输出逐split特征使用表，具体“新增位未被小树采用”还是“旧值/缺项已能代理状态”等原因**未识别**，不从相同风险推出普遍冗余或信息极限。输入66/110与状态接线QA通过，未发现把B误用成A输入的程序证据。

## 4. 留出风险、原最终验收与统计限制

所有log-RMSE为自然对数误差的RMSE，无量纲，不是百分比分辨率；真能量箱单位GeV。

|总体|真E/困难层|N|传统log-RMSE|f0 log-RMSE|A log-RMSE|B log-RMSE|
|---|---|---|---|---|---|---|
|cal_post|E50_100|97|0.1439865896221742|0.3302750377973743|0.30446362603257254|0.30446362603257254|
|cal_post|E100_200|482|0.2202463119953314|0.23791278627021972|0.24382330252186785|0.24382330252186785|
|cal_post|all|5746|0.5322635017699718|0.2710722215695275|0.2757654885585519|0.2757654885585519|
|cal_post|pz50_100_trueE200|138|1.988087051438159|0.6121586076276818|0.632526925360319|0.632526925360319|
|test|E50_100|183|0.14566138607809218|0.2826443432138452|0.27000596185790005|0.27000596185790005|
|test|E100_200|856|0.2479369852672039|0.24632876683885355|0.25209277854701256|0.25209277854701256|
|test|all|13189|0.5571899699197073|0.2874912363762959|0.2925201050800155|0.2925201050800155|
|test|pz50_100_trueE200|297|1.887789515111577|0.6581773340614371|0.6654605127703488|0.6654605127703488|


开发test最低能B/f0=.9552852138760723 [.9110136195214891,.9910576797620401]有局部收益；第二低能1.0233996694017056 [1.0067818476529087,1.0393287932897426]和all1.01749225043207 [1.0143193624201685,1.0210241068453176]有恶化条件证据。test最低能仍.270006对传统.145661，不能以局部下降称低能恢复。

B/A的主端点1[1,1]，两臂门槛同值；以下完整列B，A原值在[gates.tsv](stage115_energy_ml/gates.tsv)：

|B test层|RMSE参考|RMSE上95|门槛|RMSE通过|总尾差上95/pp|正尾差上95/pp|负尾差上95/pp|三尾通过|
|---|---|---|---|---|---|---|---|---|
|E50_100|traditional|2.24741154874121|1.05|False|1.1627906976744187|1.1627906976744187|0.0|True|
|E100_200|traditional|1.092172120790316|1.05|False|1.532218156110948|1.1550257353921645|0.9397930022399009|True|
|all|direct_cal|1.0210241068453176|1.01|False|0.3693127147766321|0.13955326460481088|0.3065979381443298|True|
|E200_inf|direct_cal|1.0218004094590312|1.03|True|0.3585041662867725|0.1489206771384541|0.2979678543336501|True|
|pz50_100|direct_cal|1.0200756703039817|1.03|True|2.6833701185510583|1.4608356261058189|1.871894902860302|False|
|pz50_100_trueE200|direct_cal|1.0245610543381602|1.03|True|3.3915984934671846|1.4937416708040445|2.5832813935115806|False|
|high_y|direct_cal|1.0210279997828304|1.03|True|2.128440451144139|0.30355840197117023|2.360973449717028|False|
|unconfirmed|direct_cal|1.0282589776045112|1.03|True|2.0409832115029305|0.0|2.7575455774895943|False|


A/B joint均False。最低两箱和all风险门槛失败；若干困难/未确认层的三尾保护也失败。test低pz真高E的总尾/负尾差上95为+3.3915984934671846/+2.5832813935115806 pp，high-y负尾+2.360973449717028 pp，均超过原+2 pp。不能只按RMSE五个困难保护通过而忽略尾。

[全部metrics](stage115_energy_ml/metrics.tsv)和[paired](stage115_energy_ml/paired.tsv)涵原八层、状态/缺项、confirmed低transfer、高端；train in-sample另表，不混称泛化。test真1600–3200 GeV为1603行、B log-RMSE=.40492066936705934；3200–6400为264行、B=.6938329953227038，这些高端没有裁去。无样本层不生成伪风险/区间；status_missing本次为0。图见[风险比较SVG](stage115_energy_ml/state_residual_risks.svg)。

原component内incoming multinomial500次，cal及cal_post seed2026110389、test2026110390，候选/参考共享draw；≥475有效才给percentile95，三个主端点均500有效。独立record-space核40个test配对比较及三主端点，最大区间误差1.4210854715202004e−14，主端点最大2.220446049250313e−16；504个原Stage94基线标量差0，证明参考与权重兼容。[measurement_validation.json](stage115_energy_ml/measurement_validation.json)、[独立检查表](stage115_energy_ml/independent_checks.tsv)、[旧控制表](stage115_energy_ml/old_controls.tsv)已交。

incoming精确键仍是谱系代理，3个component connected blocks不是丰富的来源重复。上述CI不含source/完整parent/refit/研究选择/基线offset/真实系统，cal/test均开发过，不是新blind或联合全流程95%覆盖。训练约束本次可行，不代表探测器响应闭合；数据稀缺、字典表示、条件分布/目标取舍和响应失配均未完成因果分账。

## 5. QA、实际计算资源、I/O与产物

提交前做Python AST、bash语法和Condor dry-run，核Args/Iwd/CPU/内存/MaxRuntime/no retries。任务内完整身份回接后、正式字典拟合前用40个固定train身份QA，包含全部21个train缺项；0额外QA树拟合。状态四族/unknown NaN、A/B共同前缀、零修正逐位回f0、typed NaN通过；所有24个约束解析梯度与独立有限差分最大2.339781701721222e−9。[QA.json](stage115_energy_ml/QA.json)给实际行号。未在本终端导入数值包/事件/模型或重算风险；本地只读JSON/TSV、stdlib打包/文本检查。

唯一新任务9668138首次start/exit0，无重试、无恢复提交、无先测小批成本外推。申请4CPU/8000MB，站点改写/分配12000MB；字典/凸解两臂并行2worker，配对风险4worker，ROOT/BLAS/OpenMP内线程1，0GPU。是小树与凸风险问题，未训练神经网络。监督器复用Stage113进程树CPU方法，计活进程自身及已reap子CPU；1740 CPU秒和840 wall秒留余量，外层880秒timeout，总上限1800/900不变。

|实际口径|CPU / s|wall / s|内存或说明|
|---|---:|---:|---|
|GNU外层权威|73.72（user68.97+sys4.75）|42.38|最大RSS515116 KiB|
|watchdog|73.7|42.18866473250091|最大观察6进程，无stop|
|Condor slot|75（70+5取整）|48|RequestMemory12000MB；ResidentSetSize1000000 KiB|
|worker自身，嵌套|6.0386587469999995|39.65986488573253|已包含于GNU|
|A拟合，嵌套|23.51959456|23.737971836701035|已包含于子进程/GNU|
|B拟合，嵌套|25.839046277|26.055683191865683|已包含于子进程/GNU|

worker reaped children65.824632 CPU秒已包含拟合/推断/风险，不与GNU再相加。GNU RSS不是整个并发树同时总峰；整树峰、单核加速、物理网络、GPUbusy及整会话CPU均**未测量**。任务资源明显在冻结上限内，没有因结果不好补预算。[accounting.json](stage115_energy_ml/accounting.json)、[resources.json](stage115_energy_ml/resources.json)、[time.txt](stage115_energy_ml/time.txt)、[Condor history](stage115_energy_ml/condor_history.json)和[watchdog](stage115_energy_ml/watchdog.json)保留实际口径。

worker本地缓存archive reader请求/返回均40315471 byte，见[io.json](stage115_energy_ml/io.json)；只计本地读接口，不含包分发/OS cache，更不是EOS物理流量。21项输入逻辑49033243 byte，实际运输包47484324 byte；结果归档1020335 byte。运输后21项逐原字节一致，没有SHA或本地解码事件验证。收集后仅清除SVG行尾空白/表空文本格式化，数值与坐标不变，记录于[text_normalization.json](stage115_energy_ml/text_normalization.json)。

保留两套小树/唯一head JSON和单个紧凑71376行A/B点表于`ml/artifacts/stage115/`（按仓库政策忽略，不提交二进制数据），风险/约束/状态/协议/计时/图表于`workbook/stage115_energy_ml/`。固定产物路径、实际byte与运输副本删除见[storage.json](stage115_energy_ml/storage.json)。只有约1MB紧凑点输出，无新整套事件副本、ROOT/xAOD/波形。确认job终态并核验运输后清理本阶段重复输入/结果包；spool `~/condor/nu_muAnalysis/stage115/`保留必要worker/log，不清理其他项目。Stage54五个原资产与Prompt后缀保持，不按旧后缀重做Stage85已完成的占据控制。

实际命令：

```bash
python3 ml/package_stage115.py package
condor_submit -dry-run /tmp/nu_mu_stage115.ad AnalysisZipFramework/submission/ml_stage115.sub
condor_submit -terse AnalysisZipFramework/submission/ml_stage115.sub  # 9668138
# worker: /usr/bin/time -v ... timeout --signal=TERM --kill-after=5 880 python -u ml/stage115_supervise.py
python3 ml/package_stage115.py collect
condor_history 9668138 -limit 1 -json -attributes ClusterId,ProcId,JobStatus,ExitCode,NumJobStarts,RequestCpus,RequestMemory,RemoteUserCpu,RemoteSysCpu,RemoteWallClockTime,ResidentSetSize,LastRemoteHost,CompletionDate
python3 workbook/stage115_energy_ml/validate.py
git diff --cached --check
```

[逐项完成审计](stage115_energy_ml/completion_audit.tsv)与[文档验证](stage115_energy_ml/document_validation.json)对应原固定A/B的全部交付，不将本次实验完成写成最终项目完成。先写中文报告，再连同代码/配置和紧凑文字证据本地Conventional Commit，不push。

## 6. 下一任务、输入和验收

按Stage114的结束条件，停止这两个固定状态/残差方案；不追加树数、seed、状态子集、约束尺度或换主候选，也不把当前阴性归结为严格信息上限。父分母扩展/producer精确定义继续是解释支线，不重读原60000条当新增研究。

下一项新观测问题优先为**固定VetoNu0/1相对一个事前指定Veto参考的时序族，是否在电荷/状态/pz之外有连续能量风险增量**。所需入口为Stage79的`measurements.npz`/时基production证据、已有μ控制清单`ml/configs/calonu_muon_files.tsv`、原PHYS精确版本与固定选中身份；Stage80持久`shape.npz`只保存peak/width派生族，不能凭文件名假定已有完整localtime。新split全池相对时间的可用率、匹配μ控制与clock/offset/path/time-walk闭合、完整提取成本均**未测量**。

下一次另冻一个有界科学合同，在同一任务内核两路是否共享加性时基，明确通道常数/路径/time walk/fit fallback的来源；固定参考和仅两路VetoNu差分，不能按test结果挑通道/时间窗。若现有证据足够，进行一次同split强基线对照，所有弱信号/饱和/缺时者保留为新增NaN/availability，不以时间有效性选净化样本。验收是原cal_post两低能与困难/高端的配对能量风险增量和实际可用率/资源，原全部最终门槛不改；不是“时间有变异/可分类”即成功。若时基或μ控制无法交付，交准确缺口并结束该实现，不能以未校准差分称物理时间或模型阴性，也不恢复无限波形/metadata扫描。共同绝对时钟无效并不数学上否定共模可消差分，但不替代实际时基证明。

本阶段未启动该后续，也未承诺收益/功效/预算实测值。真实系统与独立确认缺口仍属于整体目标；只有本次固定两臂实验可标完成。
