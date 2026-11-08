# Stage175：Timing均时全队列支持、固定尾部与实际S0位置清点

## 阶段目标与输入

承接Stage174提交`b83e2ee`。三份控制中MC两片均时和真实data8006两片均时通过冻结条件门，但真实差时位置全部失败。下一步只检查两片相对prompt均时的真实保存支持，不能把MC位置精度移植到数据，不能把均时门当能量门。

[冻结协议](stage175_energy_ml/protocol.json)引用Stage129原280来源89033 selected entry合同，角色不变；先原π/K/charm源0/48/113各前32个train，再成本门，全量包括缺原PHYS和隔离分母、不替换来源。只读pz0、Trig位置/角度、Timing四端和Veto21原status/raw_charge/localtime；同领先pz0的Track_x0/y0/z0只作S0实际坐标清点，不读p0/p1/pz1，不额外加回能量。各明确目标run的实际CableMapping及各PHYS histogram title必须与控制映射一致。

原status精确0且localtime有限正值才存在派生时间；timewalk另需正rawQ，仍保留原signed负Q。全量均时仅使用MC100012系数及其训练Q/x/y范围，data系数不移植；真实及MC两者条件门均需通过。不合格差时/有效位置不输出。原八层/三尾/角色/K/reserved/quarantine/Stage54、pz>50GeV及Stage87均保持。

## 小样本、成本与补充计时

原96例run/event/领先pz0完全对齐，所有所需分支和S0坐标分支存在；三源原始负电荷计数分别16、25、22，-999电荷计数均0，全部原值保留。两片均时范围内分别8/15、10/9、6/10例；不据此推断全队列覆盖或能量收益。

初始完整GNU=11CPU秒、worker读取4.009494584CPU秒；若把全部文件/字典开销按每事例放大，三倍外推11246.295646CPU秒，不通过4500总预算与3600全量phase门。该初始阴性记录原字节保留于[初始成本判定](stage175_energy_ml/initial_admission.json)。

随后先冻结[计算开销补充合同](stage175_energy_ml/cost_profile_addendum.json)，只重读同96例，未加物理输入、未改选择/模型/校准/总预算。profile200CPU秒从未用完的原pilot300中支出（原pilot实际28+profile实际20=48CPU秒），原full3600/audit600和总4500均不扩大。profile所有数组与原96例精确一致；后31例循环合计0.143540517CPU秒，文件/首例/保存等合计5.006812202CPU秒，进程启动9.579647281CPU秒，完整GNU14.73CPU秒。按文件开销×280/3、后续事例开销×89033/93及启动进程×8/3分开三倍外推，1925.627590CPU秒，通过原门，才提交全量。

请求8核/12000MB，8个独立文件worker，max1job/MaxRuntime86400秒，无应用短timeout；实际站点调度资源另列。ROOT只按明确selected entry和启用分支读取，不扫目录、不保留大ROOT。

```bash
python3 ml/stage175_freeze.py
python3 ml/stage175_ops.py submit --phase pilot
python3 ml/stage175_ops.py collect --phase pilot
# 首次成本判定未通过，原结果保留于initial_admission.json
python3 ml/stage175_ops.py submit --phase profile
python3 ml/stage175_ops.py collect --phase profile
python3 ml/stage175_admit.py
python3 ml/stage175_ops.py submit --phase full
```

## 全量实测

原280来源89033身份/角色精确，原96例全部精确；8个明确run的实际CableMapping均支持，所有有PHYS来源的histogram映射均一致。

实际PHYS支持88677例；源257未保存PHYS的356例仍保留，另有146例领先pz0不匹配，派生时间不输出。没有猜测替代来源或删事例。原rawQ负值合计53534个测量、精确-999电荷0个；负电荷保留。ROOT读取187612175B，仅为本次明确启用分支/selected entry的实际读取，不代表全ROOT物理大小。

| role | 层 | 分母 | 第一片strict/范围内 | 第二片strict/范围内 | 至少一片 | 两片同时 |
|---|---|---:|---:|---:|---:|---:|
| -1 | E50_100 | 1318 | 627/614 | 704/686 | 1217 | 83 |
| -1 | E100_200 | 6147 | 2693/2559 | 2996/2865 | 5040 | 384 |
| -1 | all | 89033 | 26675/23324 | 30046/26900 | 45783 | 4441 |
| 0 | E50_100 | 12 | 5/5 | 7/7 | 11 | 1 |
| 0 | E100_200 | 142 | 54/53 | 71/70 | 113 | 10 |
| 0 | all | 17657 | 4399/3689 | 4929/4275 | 7185 | 779 |
| 1 | E50_100 | 940 | 453/444 | 492/482 | 864 | 62 |
| 1 | E100_200 | 4245 | 1906/1806 | 2069/1973 | 3505 | 274 |
| 1 | all | 46575 | 15003/13276 | 16639/15012 | 25848 | 2440 |
| 2 | E50_100 | 183 | 86/85 | 99/97 | 173 | 9 |
| 2 | E100_200 | 904 | 361/346 | 454/440 | 730 | 56 |
| 2 | all | 11612 | 3443/3018 | 4110/3694 | 6131 | 581 |
| 3 | E50_100 | 183 | 83/80 | 106/100 | 169 | 11 |
| 3 | E100_200 | 856 | 372/354 | 402/382 | 692 | 44 |
| 3 | all | 13189 | 3830/3341 | 4368/3919 | 6619 | 641 |

role=-1为全部含隔离，0为隔离、1/2/3为原train/cal/development-test；这里仅覆盖统计，无隔离预测。原八层完整表见[支持表](stage175_energy_ml/timing_support.tsv)。开发test至少一片6619/13189、最低箱169/183、第二箱692/856；存在值得进行一次固定新训练的内容支持，但不是模型已改善或可跨数据部署的证据。无时间事件和未通过范围者全部保留。

## μ控制尾部的固定诊断

[尾部诊断](stage175_energy_ml/muon_tail_diagnostics.json)重建原校准奇数entry留出残差，不改系数/门/窗口。下表全部为相对均时，|残差|>2ns为预定描述阈值。

| 来源 | pair | 留出N | >2ns N | 其中仍在训练范围N | 最大绝对残差 ns |
|---|---|---:|---:|---:|---:|
| data8006 | 0/1 | 953 | 35 | 31 | 139.684630 |
| data8006 | 2/3 | 661 | 15 | 13 | 13.829077 |
| MC100012 | 0/1 | 878 | 6 | 4 | 17.125327 |
| MC100012 | 2/3 | 993 | 4 | 2 | 5.531864 |
| data15838 | 0/1 | 711 | 23 | 21 | 98.056371 |
| data15838 | 2/3 | 674 | 91 | 88 | 96.523968 |

大残差并不只出现在Q/x/y超训练范围者：例如data8006第一片35例中31例仍在范围内，data15838第二片91例中88例仍在范围内。所有这些留出组的clockPhase均有限；这不认证实际相位质量。2022/旧MC的local采集时间主要在约810–975ns、2024约172–295ns，证实绝对采集坐标不可跨时期直接共用，不能把localtime当飞行时间或再统一减一次phase。两端/参考的固定时间分箱、极值和首8个确定尾部身份/时基/Q/位置均保留。

这些结果排除了“所有大残差仅为范围外外推”这一单一解释，尚不能区分附加/迟到脉冲、参考hit、时钟转移或重建原因；原因保持未知。未因为这些事例停止整个均时分支，也不据尾部剔除事件、换拟合族或补出坏hit时间。跨运行期真实误差和ν多沉积响应仍未认证。

## S0实际参考点清点

实际同领先pz0的有限物理Track_x0/y0/z0有88531例，缺失/不匹配/占位502例；精确-999坐标成分0个。z0共有20个实际值，范围9.5–84.41500091552734mm，x/y极值见[S0清点](stage175_energy_ml/S0_inventory.json)。完整原XYZ在cohort中，未以均值或名义几何代替逐父参考点。


静态pinned producer证明这些坐标和pz0来自同一个`trackParameters()->front()`；实际fitter启用散射与能损。**这不是G4 μ过面能量、不是顶点μ能量，也不是已认证可直接加回的辐射能。** 原PHYS没有实际surface normal/type及每步材料修正，旧compact observer也没有出生/过面细节，需Stage176固定小型同父observer与native state补充，不自动4032重放。

## 独立验证、资源与存储

[独立验证](stage175_energy_ml/independent_validation.json)实际重读三源各原首个selected entry全部字段精确；50224个有支持均时逐行标量重建，最大差2.84e-14ns；全队列派生量/缺失精确及各role独立计数通过。

终态4 start，全部exit0、0live，累计511.0调度CPU秒、178.0聚合execute wall秒。实际RequestCpus=[8]，站点RequestMemory=[24000]MB。无应用短timeout、无能量fit/forward/G4/新ν/GPU。本次稀疏ROOT读取和固定小线性诊断不适合GPU加速。

| GNU任务 | CPU秒 | wall秒 | maxRSS KiB |
|---|---:|---:|---:|
| audit_time | 8.65 | 10.52 | 656936 |
| full_time | 443.83000000000004 | 77.31 | 632196 |
| mapping_time | 11.61 | 26.24 | 603360 |
| pilot_time | 11.0 | 6.18 | 578476 |
| profile_time | 14.73 | 11.42 | 563360 |

[终态存储账](stage175_energy_ml/storage_cleanup.json)原字节归档/重读源码84逻辑版本/34独立内容，队列无Iwd引用才清理；保留`ntuples/energy_ml_stage175/cohort.npz` 8283583B，删117011795B重复运输、prefix、日志和提交文件。280份重复source summary已逐项与full_summary核对一致后合并，未产生中间ROOT；8核读取的临时NPZ分片在worker完成合并/验证后删除。软件版本与资源/提交审计在`software/stage175/*.tar.gz`，Stage54原12项大小/mtime保持。


收尾命令：

```bash
python3 ml/stage175_ops.py collect --phase full
python3 ml/stage175_ops.py submit --phase audit
python3 ml/stage175_ops.py collect --phase audit
python3 ml/stage175_finalize.py
python3 ml/stage175_document.py
python3 ml/stage175_validate_docs.py
git diff --check
```

## 阶段结论与下一步

两片均时在原全队列有有限支持，真实尾部和跨时期迁移仍未知；真实差时位置分支保持未通过。本阶段没有训练能量模型、没有能量改善结论或晋升，Stage87及原八层三尾完整验收门保持。

下一Stage177待本阶段终态验证提交后，冻结同支持X62/V66/T68：X从头复现Stage87，V追加每片strict/范围可用状态共4维，T再追加两片校准均时；3seed×400轮、train/cal/开发test、原incoming权重与500分组bootstrap不变。先单X成本/精确复现，再V/T新训练，比较内容T/V与各臂/传统及原完整门，报告无时全样本而非只展示Good Hit子集。MC条件研究不认证真实迁移或独立最终确认；GPU若改变原CPU hist复现口径则不用来伪造基线一致。

Stage176先原50父新只读observer/native surface preflight，验证旧谱系与HITS不变、实际S0面/协方差、主μ能量bracket和直接子粒子出生标签；过原成本门才固定其余11父，禁止自动4032扩产。之后再按同窗模拟响应和可测伴随量决定机制与部署分支。真实双量程/独立高幅参考、匹配噪声/信号保真、backscatter覆盖及实际背景/效率/生成加权输入继续，外部匹配缺口保留；项目整体未完成。
