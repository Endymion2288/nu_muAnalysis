# Stage105：真实 SpacePoint 局部关系可交付，冻结一次性三格实验

日期：2026-11-05；起始提交 `a334e68`。执行修订路线§86、信息计划§66和 Stage103 §5，本轮仅完成有界几何 QA 与下一次实验合同，**0 能量 fit、0 预训练 step、0 test 载荷/推断/风险、0 全样本提取**。没有恢复本地 CERN 环境；全部 ROOT 读取与几何运算在唯一 HTCondor 作业中执行。本地 Python 仅标准库打包、元数据联结、字节核验和文档整理。

## 1. 阶段目标和结论

要回答的是：现有 PHYS 的真实 SpacePoint 坐标，能否支持完整点集合的局部关系和遮挡面任务，并保留原角色、缺失与 K 样本？不是再选一次固定密度的动作权重，也不把 Stage19 已做的全点 mean 池化称作新方法。

**几何可行性通过。** 固定原 40 个 train/cal incoming 身份、24 个来源；37 个原可读身份全部成功，3 个已知缺源原样保留。5718 个点没有截断或去重，全部有限且可映射到 12 个名义层；局部图共 56822 条有向边，独立近邻距离核验、排序不变性与遮挡输入隔离通过。37 个固定遮挡目标中 36 个非空、1 个为空，没有观察到目标格外点。

这只支持进行一次有界的 A/B/C 实验；**没有测量模型收益、GPU 成本、全角色 SP 覆盖或真实有效读出**。尤其不能从此宣称低能不足由训练数据量、ghost 或几何池化导致。下一次的 [三格合同](stage105_energy_ml/experiment_contract.json) 已具体冻结，仍须新一次零优化 CPU/GPU 接线与成本 QA 准入；本轮不执行 Stage106。

## 2. 输入、身份和样本分母

身份来自 `ntuples/energy_ml_stage95/cohort.json` 中原 `qa=True` 的恰 40 条，而不是重新取样。对原可读记录，用已有 `ntuples/energy_ml_stage95/QA_events.tsv` 的实际 `input_entry` 联结，避免为 eventID 全树扫描。冻结的 [identities.json](stage105_energy_ml/identities.json) 仅保留 row/key/source/role/component/run/eventID/entry/pz0 及精确来源路径，剥离了 truth、y 和原 raw 特征；worker 不读 truth branch。40 个 key 不重复，全部 role1/2。来源仍是原 Stage55/70/81/82/83 池，不递归寻找 REC，不替换临时源。

|本轮分母|实际数量|解释|
|---|---:|---|
|固定身份 / 来源|40 / 24|沿用 Stage95 QA，未经新点活动或能量筛选|
|实际可读 / 原可读|37 / 37|没有新增读取失败|
|已知缺源|3|row81325 的 `70:0`，row82784/82790 的 `82:2`|
|几何图核验|37|全部可读身份，原身份与 pz0 联结均通过|
|test 载荷 / 新 fit / 预训练 step|0 / 0 / 0|本轮范围硬限制|

两个缺源入口原 scratch PHYS 已删除；Stage82 旧 bck 路径来源错误，依据 `workbook/stage95_energy_ml/provenance_correction.json` **没有拿来替代**。保留缺源行而不补同类“好事件”，包括两条 K。

完整角色支持只引用 Stage96 已有 [input_support.json](stage96_energy_ml/input_support.json)，**不是本轮重新测量**：

|角色|pi 记录|K 记录|charm 记录|已知缺 PHYS|保留的总记录|
|---|---:|---:|---:|---:|---:|
|train|23748|18901|3926|345|46575|
|cal|5160|5722|730|343|11612|
|test|5397|7091|701|356|13189|

原 71376 条活动视图中，Stage96 历史 70332 条有载荷、1044 条缺源；280source 中历史 276 条路径可用。这不是新测 SP 可读率。后续所有缺源事件保留原标量及明确 `geometry_missing`，几何 embedding 置零，不删 K、困难或缺源；可读空集合与缺源分开。原隔离 17657、incoming 总权重1、原新增1016 K、标量 missing21/6/5、pz0>50 GeV 全部保持。

一次方动量继续仅用 pz0；原 px/py、q/p、弯折允许。监督标量继续原 audited62、raw11/status、typed NaN、合法 signed 负值和 Calo 缺项政策；不引入 p0/p1/pz1 或 ln(p0/p1)。Stage19 旧 baseline YAML 仅供历史实现阅读，不作为新模型的输入清单。

## 3. 冻结几何和实际 QA

[protocol.json](stage105_energy_ml/protocol.json) 在事件作业前冻结并打包；[packaging_validation.json](stage105_energy_ml/packaging_validation.json) 已核对 worker、协议和名单与实际输入包逐字节相同，不做 SHA。只读 `nt` 的 run、eventID、SpacePoints、SpacePoint_x/y/z、Track_pz0 七列。标量是 int32，坐标和 Track_pz0 是 `std::vector<double>`，具体逐来源见 [schema.tsv](stage105_energy_ml/schema.tsv)。逐 entry 核原 run/eventID、max Track_pz0/1000 与旧 leading pz0、标量点数与三个向量长度；实际 pz 差各行均为 0 GeV。

复用 `ml/configs/spatial.yaml` 的毫米名义几何：station center 为 −1860.15、47.4、1237.4、2427.4 mm，各站层偏移 −31.5、0、31.5 mm。按最近 station/layer 映射，要求 z 残差≤10 mm。它是名义层分组，不是 exact module surface 或历史 conditions 证明。

|逐点/逐图核验|实际测量|
|---|---:|
|原 SpacePoint 总数|5718 点|
|有限且映射成功 / 未映射|5718 / 0 点|
|最大名义层 z 残差|6.400048828124909 mm|
|float64→float32→float64 坐标最大差|0 mm，仅此 QA 支持|
|局部有向边总数|56822 条|
|单事件最大点 / 边|1117 / 11856|
|独立暴力近邻与树查询的最大距离差|0 mm|
|排序输入改变后坐标/边完全一致|37/37 事件|
|改变隐藏面 XY 和增加隐藏点后，可见输入完全不变|37/37 事件|
|固定隐藏面非空 / 空|36 / 1 事件|
|隐藏 target sum 与原隐藏点数一致|37/37 事件|
|目标 overflow 点|0 点|
|可读完整空集合|0 事件，本轮未实际覆盖此状态|

逐事件完整数字见 [events.tsv](stage105_energy_ml/events.tsv)，逐面点数和 z 范围见 [planes.tsv](stage105_energy_ml/planes.tsv)，图见 [graph_cost.svg](stage105_energy_ml/graph_cost.svg)。例如 row39001 的 1117 点全部保留，IFT 三名义层分别372/375/340点，三个 downstream station 各层均有原点；其第0面名义z=−1891.65 mm，实测z范围[−1898.050048828125,−1885.25] mm。不能把6.4 mm差当作读错单位，也不能据名义层映射声称真实粒子关联。

建边定义固定：**同一 station 内相邻层，每个有向源点取目标层 XY 最近 k=min(8,N目标) 个点，双向都建**。层间不跨 station/磁铁，不限制全部点数。每节点最多对两侧各8条，故 E≤16N。边是几何邻近假设，不是真实轨迹或共同粒子标签；不拿“未配上”当 ghost/强子/纯 noise。

保留所有重复坐标；这次表中实际重复XYZ、全XYZ=−999、坐标=−1、单坐标=−999均为0。程序不会把 signed 坐标−1/单个−999一律删除：非有限、全XYZ=−999、任意abs=999999、或名义z不支持均明确标记，保留事件和原点数、停止该图核验，不能静默删点后报通过。**本轮未碰到真实异常占位，未测其物理发生率**；原 raw 负电荷合法性仍按已有 typed/status 协议，不能套坐标或正值变量的规则。

隐藏面取 `3+row%9`，即九个 downstream 名义层之一，选择不看目标活跃度。先删除隐藏面，再规范排序、构可见图与可见面计数。输入不含原62标量、原总点数、隐藏面计数/矩或 truth。目标是 XY∈[−200,200)² mm 的16×16格、每格25 mm，加一个 overflow 共257个**观测 collection 点计数**；hidden sum逐点守恒。泄漏probe将隐藏XY平移[17,−29]mm并追加两点，完整可见tuple仍逐项完全一致。

没有测 active sensor/channel、readout mask、噪声效率、SP组成、真实ID/TSOS/covariance。这些仍是 response/机制缺口，不是任何局部几何编码的绝对前置。没有完整空事件、实际 sentinel、overflow 目标的真实 QA 支持，下一次必须以显式合成接线 probe补核这些分支，不能伪称已实际观测。

## 4. 实际成本、准入和存储

唯一作业 `9667789.0`，首start/exit0、0重试；提交在 `~/condor/nu_muAnalysis/stage105/`。申请4CPU/6000MB，站点实际 ad为4CPU/12000MB，0GPU；4个独立来源子进程、进程内线程1。CPU几何/ROOT读取为主，本轮没有值得用GPU的优化器或矩阵训练。

先单源 `55:116` 的原4个QA身份，实测后才在同一任务扩到固定40：

|窗口|CPU / wall|接口请求 bytes|说明|
|---|---|---:|---|
|pilot4身份|1.823182800 / 2.924049212 s|301738|可读4/4，缓存底层读取243134 bytes|
|pilot准入投影|121.159140000 / 176.202460583 s|9052140|CPU/wall×(40/4)×5+30；bytes×(40/4)×3，启发式而非保证|
|所有source窗口相加|14.219627093 CPU s|3823241|包含文件、完整几何/暴力核验；source wall并行不可直接相加当任务wall|
|main内层|self1.877486686 / child12.457493 CPU s；wall8.761233570 s|同上|不包括最终绘图/部分导入；不能再与外层相加|
|GNU time完整worker|user16.51+sys0.84=17.35 CPU s；wall15.16 s|同上|含导入、子进程、绘图，作为主要资源计量|
|Condor job ad|user16+sys1 CPU s；wall21 s|传输11122入/1958出|整数资源/整个任务窗口，与GNU time不重复加|

主预算CPU/wall各900s、接口请求1,000,000,000bytes均满足；payload timeout850s，parent CPU硬180s、4child各170s；本次无child替换路径合计860s，另留启动开销。最外层GNU time峰RSS135212KiB；内层parent峰108.042969MiB，不能当4进程内存和。实际4CPU占用和114%CPU表明小QA有I/O/导入/串行开销，**单核对照与加速比未测量**，不声称4倍加速。

接口请求3823241bytes，底层native文件read返回3569873bytes，uproot逻辑请求3823241bytes；三者区分，均非物理EOS网络流量测量。64MiB exact-range LRU、稀疏一entry/basket读取，无整文件拷贝。完整源成本见 [source_performance.tsv](stage105_energy_ml/source_performance.tsv)，预算/结果见 [admission.json](stage105_energy_ml/admission.json)、[complete.json](stage105_energy_ml/complete.json)，外层 [time.txt](stage105_energy_ml/time.txt)、[condor_history.json](stage105_energy_ml/condor_history.json)。

最高点数row39001建图0.009488170967s，完整几何QA0.869690608233s；此处后者还包括对每查询暴力近邻对照、置换/遮挡反复构图，**不能拿总QA逐事件成本直接认证全池提取预算**。未来正常提取的CPU、GPU前后向和完整输入最大规模均未测；下一次准入要在相同40身份实测正常提取（不重复O(N²)暴力核验）及真正Torch接线，再按固定公式外推，不通过就停，不靠丢高活动或增加预算。

输入传输包实际11024bytes，Condor接收11122bytes还含脚本。返还包逐字节收集，核源、名单和QA协议不变后删除输入/结果传输副本；不保存点云或逐边数组。收集后仅将TSV空格位显式写成NA（未测量/不适用）、清理SVG行尾空格，原非空单元格逐项不变、XML仍合法；没有重算物理数值。最终紧凑体积见 [storage.json](stage105_energy_ml/storage.json)，≤20MB。GNU time之外的终端编辑/会话CPU和物理流量未测，不混入任务测量。

实际命令：

```bash
python3 ml/package_stage105.py package
bash -n AnalysisZipFramework/submission/run_ml_stage105.sh
condor_submit -dry-run /tmp/nu_mu_stage105.ad AnalysisZipFramework/submission/ml_stage105.sub
condor_submit AnalysisZipFramework/submission/ml_stage105.sub
python3 ml/package_stage105.py collect
condor_history 9667789 -limit 1 -json -attributes ClusterId,ProcId,JobStatus,ExitCode,NumJobStarts,RequestCpus,RequestMemory,RemoteUserCpu,RemoteSysCpu,RemoteWallClockTime,ResidentSetSize,DiskUsage,BytesSent,BytesRecvd,LastRemoteHost,QDate,JobStartDate,CompletionDate,NumJobMatches
```

batch实际执行 `/usr/bin/time -v ... timeout --signal=TERM --kill-after=5 850 python -u ml/stage105_point_feasibility.py`，LCG_109/x86_64-el9-gcc15-opt，内线程1；不更改C++，不需重编Calypso。

## 5. 下一次冻结合同：A / B / C

完整可执行字段以 [experiment_contract.json](stage105_energy_ml/experiment_contract.json) 为准，所有资源均为**拟议上限，尚未准入**。研究主比较是整体C/A；B/A、C/B解释关系及预训练。A不是强BDT的替代成功标准。

- **共同输入**：原62标量、Stage94 C train-only变换127维；所有原SpacePoints，毫米坐标，canonical plane/x/y/z排序，重复点保留。10维点特征为asinh(x/100)、asinh(y/100)、station onehot4、layer onehot3、名义z残差/10。可读空集合独立标记；缺源或有无法编码坐标时保留全事件和原计数、明确missing并整事件标量fallback，不做部分图或静默删点。
- **共同编码器**：10→32→32 SiLU。两轮共享权重消息/残差更新：消息为destination32+source32+4几何边特征，共68→32→32；incoming mean聚合，update64→32→32后加原h。边特征为asinh(dx/100)、asinh(dy/100)、dz/31.5、log1p(XYdistance/100)。每面mean32，共384；加12个log1p计数、12非空、available/available-empty共26项。与标量127拼成537→64→64→1，输出自然log(E/GeV)，不强制E≥pz。
- **A**：消息MLP只读固定零68向量并向各节点广播常量，更新只编码单点；保持所有真实点与逐面mean。**B**：同声明模块使用真实局部边。**C**：与B完全同架构，预训练只转移point/message/update参数；其余监督模块重置为与B相同初始化。相同声明参数不代表有效容量完全隔离；C额外预训练计算，主比较检验整体方案，不能声称纯计算控制。
- **C遮挡预训练**：恰一次、原train-only；按seed和epoch/key选择九个downstream名义面之一，独立于内容，包含观测空面。严格visible-only输入，不接62标量；hidden plane onehot可输入。上述257-bin目标，decoder422→64→257，softplus+1e−6给Poisson rate，事件内257格平均(rate−count log rate)，再用原incoming权重。没有geometry的train行无此目标，明确不参与这一步，监督仍保留。固定20epoch取最终状态，无cal/test无标签混入、无按预训练loss选checkpoint；不造粒子/ghost标签。
- **监督预算**：恰3fit、单seed2026110506；各最多200epoch，每5epoch原cal_select weighted logMSE选严格最优/最早tie，patience30epoch。Adam lr.001、betas(.9,.999)、eps1e−8、无decay/调度/dropout，clip global norm10；预训练同优化器。目标为原incomingweighted log-MSE，全尾保留。有效batch256且同一epoch置换；ragged disjoint union，微批≤16384nodes/262144edges，累加整有效批的正确加权梯度。超大单事件singleton；不fit就停，绝不截断。
- **选择和后处理**：原cal_select5443、cal_post5746、423退出select仍交完整cal；每格恰一个cal_post加权mean(logtruth−point) offset，raw/shifted均交。三个checkpoint及offset冻结后才提取test点及一次完整评价，不在训练准入时查看test的实际活动/点数。强对照复用同split Stage87 direct62和传统pz0/0.8，不用可能见过新test的旧F7研究对照。
- **成本准入**：同40身份零optimizer CPU/GPU QA，补空/缺/invalid/overflow合成probe，核梯度/同初始化/置换/disjoint无跨事件边/遮挡泄漏；CPU/GPU max logE差≤3e−6。有效256做一次warmup+3次实测，含传输/回传/decoder。由实际节点边计数外推每full-train epoch，最慢成本×620×3+600s须≤7200 GPU-task wall；正常提取成本另实测并按原280source/70332历史可读、factor3+1000CPU reserve外推，所有工作总CPU≤21600s。先train/cal全点数量核预算后才optimizer，不为准入读test活动。
- **资源/存储**：GPU并发1，累计任务wall7200s，实际设备内存QA峰≤75%；优先现成Kubeflow或HTCondor CUDA GPU，由实测选择，不扫设备。批量提取/评价8CPU/申请8GB/线程1。一次临时按角色float32坐标ragged cache≤512MB，边按需生成；最终≤20MB，仅checkpoint/三格点输出/配置/紧凑证据，验字节与身份后删临时坐标。上限不准入就停止，不自动放宽。

设计参考 Stage19 已有普通全点池化、[Interaction Networks](https://arxiv.org/abs/1612.00222)、[FASERCal预训练v2](https://arxiv.org/abs/2604.07037v2)，文献适用性已在 [Stage103 §5](2026-11-04_stage103_research-reset-and-decision-budget.md)讨论。本轮是落实该合同，不作新的文献性能迁移：没有voxel truth监督，不复制千GPU小时预算，不把分类提升当本项目能量改善。

## 6. 物理验收、局限和停止

主开发指标固定为原cal_post的 `max(RMSE_C/RMSE_A in E50–100,E100–200)`，500次共同component内incoming抽样的条件95%上端<1，才称共同低能增量。B/A与C/B完整交付但不据其临时换主比较。使用原cal seed2026110389/test2026110390及相同draw，原八层all、两低能、≥200、低pz、低pz真≥200、high-y、未确认均报告logRMSE、bias/R68、总/正/负tail50和配对区间；保留缺失/高端/confirmed低transfer等原诊断，并单列几何缺源。

最终要求不变：两低能相对传统RMSE比上95≤1.05；all/direct≤1.01；其余≥200及困难/direct≤1.03；八层三向tail50均相对原Stage87 direct_cal的差上95≤+2pp（传统仅作两低能RMSE门槛参考）。C是事前指定方案，不能test后从A/B/C换赢家。不用训练loss或比弱A好代替最终全联合通过；点模型不编造NLL、PIT、coverage。

当前是反复使用的开发test。incoming区间不包括完整source/parent、重训、offset估计/研究选择、真实response/interaction/FSI/材料/Calo/接受度/背景，也没有独立新blind；名义plane并非已核真实active读出。Stage105未测模型风险，不能断言本方案会恢复50–100GeV性能或数据已经充分。

**具体下一任务是Stage106一次性三格实验，先实施零优化器接线/正常提取与GPU成本QA，通过固定资源准入才恰3fit+1预训练。** 输入是本阶段冻结合同/原40身份/原完整角色及精确PHYS，验收是角色和全部K/缺源无损、输入/遮挡/梯度/预算核验、完整成对风险和原最终门槛。任何未解决系统schema/身份或资源失败，交精确缺口并在optimizer前停止；完整实验没有主增量或最终不过，记录有限机制结论、不晋升、不自动加seed/深宽/epoch/预训练任务。没有新数据授权或生产，不重开旧REC搜索、温度/专家/权重族。

## 7. 交付与验证

本阶段新增worker/标准库打包收集器、唯一Condor脚本/descriptor及本报告和紧凑表图；路线只追加§87、信息计划只追加§67，下一Prompt改为执行上述合同或精确停止。Stage54原Prompt后缀及五个未跟踪资产保持，不自动执行历史noise支线。输入包/返还包字节核验通过后去重；本地Conventional Commit，不push、不自动Stage106。

验证记录见 [validation.json](stage105_energy_ml/validation.json)：Python AST、shell语法、JSON/SVG/TSV结构、报告链接、Markdown表/fence、历史前缀和Stage54后缀逐字节、固定身份/entry映射、预算与收集完整性检查。没有本地运行数值worker或新增物理复算，也没有为低影响文档编辑建立镜像单元测试。
