# Stage156：相同几何定义下的真实 μ 空间活动控制

## 目标、输入和冻结政策

执行 [Stage155 下一合同](stage155_energy_ml/next_execution_contract.json)，[protocol](stage156_energy_ml/protocol.json)逐字节复制。问题是：Stage155 取得的非leading cluster位置，在原始μ根、辐射后代及探测器噪声控制中呈现什么活动？这一步取得真实方法控制，尚无固定其他根判别器，非leading存在不能直接叫误报或强子活动。

唯一HITS输入为 `/eos/experiment/faser/sim/mc24/particle_gun/100012/sim/s0012/FaserMC-MC24_PG_muon_fasernu_100GeV-100012-00000-s0012-HITS.root`。原身份来自Stage146，当前06参考来自 `ntuples/energy_ml_stage149/event_records.json.gz`；Stage151的04对照只保留历史边界。原HITS entry0–3先作物理/成本pilot，准入后才允许同前64；不按活动、风险、能量或辐射尾选父，不替换父，不创建新独立μ/ν家族。

旧PHYS为 `/eos/experiment/faser/sim/mc24/particle_gun/100012/phy/s0012-r0023/FaserMC-MC24_PG_muon_fasernu_100GeV-100012-00000-00004-s0012-r0023-PHYS.root`，用于既有身份及选择对照；不要求当前pz/raw等于旧PHYS，不把旧PHYS当真实无误的测量。输入输运conditions04、当前数字化/重建06及release差异继续明确；tag相同不是data迁移认证。

## 实现和验收方法

复用Stage149的pinned d32/FASERNU04/tag06官方完整数字化、重建、ntuple及RNG政策。波形private seed仍为 `720000000+10000*event+1000*detector_index`，顺序Calo/VetoNu/Veto/Trigger/Preshower；SCT Random.SeedOffset仍为2026110749。没有新G4、tracking refit修改、gain/time/tag/seed扫描或全栈build。

新增 [原生capture](../ml/stage156_native.py)及[几何转换](../ml/stage156_geometry.py)。[实现审计](stage156_energy_ml/implementation_audit.json)确认三个纯helper与Stage155原文相同，仅将硬编码role1改为显式μ控制角色；C++几何本体直接复用Stage155。实际新REC再次核文件内streamer和两个MergeTrack输入，再用float32相邻数中点表示区间、真实wafer逆变换及64eps64算术余量；无未知基底covariance缩放或位置修补。

每个原父核current06 run/event、leading/full state/全5×5 covariance、真实PRDcompact IDs、cluster4/SP/longTracks、raw/status/presence/baseline及原根/seed/private RNG初末状态。额外位置仅用于测量，不改官方输入输出。第一父同进程重复；若full准入，独立前4的native/geometry/QA/raw/RNG和schema均须精确。无leading父保留，未支持位置仍未知；有支持但无候选，candidate_N=0，距离统计为null，不能填假距离。

固定四层报告：all、current-leading、leading pz0∈[50,100) GeV、合同raw15任一status&4 overflow。不把这些分组当独立样本，不把无非leading活动当pilot失败。原cuts、全部K及角色/reserved、pz0-only一次方动量、raw11+4Calo、typedNaN/合法signed负值/非0status无timing/Calo缺失保持；Stage87和原风险门、Stage137双低箱5%扩大门保持。

## 实测数据

[完整审计](stage156_energy_ml/summary.json)、[逐父配对](stage156_energy_ml/paired_checks.tsv)和[四层站表](stage156_energy_ml/station_support.tsv)均已通过。64个原根身份及current06逐父配对全精确，61当前leading/选中，entry11/30/47无leading保留。原前4 native/geometry/小QA/raw/RNG及schema（除scratch路径）独立精确复现。

| 检查 | 实测结果 |
|---|---:|
| 不同原父／物理执行次数／重复执行 | 64／68／4 |
| leading anchors／真实PRD链接／measurement-detector同面 | 各1063 |
| float32精确／plane-box相容／有效anchor | 各1063 |
| 仍超过Stage154旧1e−6 mm门 | 743 |
| 非leading eligible候选 | 98 |
| 至少一候选的父 | 43／64（有leading的43／61） |
| state往返最大差 | 2.1316282072803006e−14 mm |
| PRD／candidate往返最大差 | 0／0 mm |
| C++独立点积dx最大差 | 2.1316282072803006e−14 mm |
| 最大candidate dx表示区间宽度 | 7.704157562571368e−6 mm |
| 非0status提供timing | 0 |
| 保留的合法负signed raw视图 | 245 |

1063是本阶段leading COT anchor口径；不将其与Stage149全部measurement计数1097强行等同。全部candidate的RDO/local/surface/element/roundtrip失败为0，实际检查已到达。Python独立点积全过1e−8 mm，精确最大差未单独记录。实际新REC的两输入均tlp6、文件内streamer p2/vector<float>，逐作业再认证；表示区间不当统计误差或历史writer模式认证。

| station | 总clusters | leading-owned | nonleading | measured-wafer上／eligible | 其他wafer上 | 有候选父 | 可用父 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | 706 | 0 | 706 | 0／0 | 706 | 0 | 0 |
| 1 | 536 | 357 | 179 | 39／39 | 140 | 17 | 61 |
| 2 | 491 | 353 | 138 | 34／34 | 104 | 21 | 61 |
| 3 | 441 | 353 | 88 | 25／25 | 63 | 19 | 61 |

三个站非空父相互重叠，union43；站0无leading面、未测wafer和无leading父都不是物理零。站1–3总405个nonleading只覆盖98个，其他307个没有本方法的leading测量wafer。不能把未覆盖部分当作没有活动。

| 固定层 | 原父N | 有leading N | 至少一候选父N | 站1／2／3候选数 |
|---|---:|---:|---:|---:|
| all | 64 | 61 | 43 | 39／34／25 |
| current-leading | 61 | 61 | 43 | 39／34／25 |
| pz0∈[50,100) GeV | 57 | 57 | 41 | 33／33／24 |
| raw15任一status&4 | 3 | 3 | 1 | 2／0／0 |

这些分组重叠，overflow只3父，不能认证辐射尾或总体误报率。低pz是重建μ动量分层，本源为标称100 GeV μ控制，不是ν真实E=50–100 GeV的能量回归评估。新ntuple的18映射通道有1152视图、1136有效presence；status0/1/4分别642/505/5视图，不把5视图当5个overflow父。

| station | 每父candidate_N范围 | 非空mean abs dx中位／范围（mm） | max abs dx最大值（mm） |
|---|---:|---:|---:|
| 1 | 0–6 | 14.503713839／0.639087921–23.700017202 | 35.696990158 |
| 2 | 0–6 | 7.820277419／0.245492787–47.420495605 | 47.420495605 |
| 3 | 0–4 | 8.334394910／0.320259774–46.817903351 | 47.745464158 |

完整mean/min/max/RMS分布见审计JSON，以上中位只条件于各站17/21/19个非空父，不是全部64父的平均活动。数十mm变化远大于数值表示宽度。μ根加后代和噪声控制中真实出现这些活动，**非leading存在或大dx本身不能认证其他根/强子能量**；本阶段没有逐cluster辐射/噪声来源标签，不猜具体成因。与Stage155的22/40比例属于不同来源、选择和能谱，不能直接相减当判别效率。

没有μ/其他根判别器、留出FPR、responsefit、能量fit/风险或低能胜传统结果。fitted covariance仍只是原样配对，未测同面truth覆盖、transport或校准。

## 执行、资源与存储

```bash
python3 ml/stage156_submit.py pilot
python3 ml/stage143_monitor.py --stage 156
tar -xzf ntuples/energy_ml_stage156/pilot_result.tar.gz
python3 ml/stage156_submit.py admission
python3 ml/stage156_submit.py admission_retry
python3 ml/stage143_monitor.py --stage 156
tar -xzf ntuples/energy_ml_stage156/admission_retry_result.tar.gz
python3 ml/stage156_submit.py full
python3 ml/stage143_monitor.py --stage 156
xrdcp --silent --force root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage156/full_result.tar.gz /tmp/nu_mu_stage156_full_result.tar.gz
tar -xzf /tmp/nu_mu_stage156_full_result.tar.gz
rm /tmp/nu_mu_stage156_full_result.tar.gz
python3 ml/stage156_submit.py audit
python3 ml/stage143_monitor.py --stage 156
tar -xzf ntuples/energy_ml_stage156/audit_result.tar.gz
python3 ml/stage156_finalize.py
```

提交目录 `~/condor/nu_muAnalysis/stage156/`，worker传scratch并按basename执行。请求4CPU/12000MB、MaxRuntime86400秒，累计3000CPU秒、pilot800秒、最终审计预留150秒；无应用wall超时，0GPU。官方串行Athena/Cling链没有在本阶段测GPU或多线程加速，不用请求核数冒称加速。ROOT临时上限1GiB、最终合并事件上限8MiB。科学数组、ROOT/Cling、digi/reco与统计审计均在HTCondor，本地只作文本、提交、监控和精确运输合并。

第一次admission作业9674985在读Stage149 native顶层 `configured_conditions` 时KeyError（exit1）。Stage149的实际native未保存这个后来新增的字段；修复为核当前native实际配置与双方原seeds中实际digi条件/几何，同时明确旧native配置元数据未保存。没有补造旧字段或放宽逐事件raw/state配对，旧native条件边界仍单列。第一次失败GNU CPU0.33秒/wall0.60秒，scheduler计0CPU秒/5wall秒；不把嵌套GNU重复加到scheduler。以admission_retry9674991重做审计，不重复物理pilot。

[事前成本门](stage156_energy_ml/full_admission.json)以pilot各子进程GNU及end4−end1估计：digi/reco/native的full64预测为78.68005594/30.40363870/82.51345236 CPU秒，extract4 GNU3.37秒×16；总乘3为736.551441 CPU秒，加150预留小于当时剩2824秒，准入true。first/lazyJIT保留；这是预测，不能当实测吞吐。μ合法零候选可以准入，实际前4有12候选但未把正活动设为选择条件。

| phase | job | scheduler CPU秒 | 执行wall秒 | GNU CPU秒 | GNU wall秒 | GNU peak RSS KiB |
|---|---|---:|---:|---:|---:|---:|
| pilot4 | 9674970.0 | 176 | 308 | 171.64 | 297.44 | 1926984 |
| admission失败 | 9674985.0 | 0 | 5 | 0.33 | 0.60 | 32392 |
| admission_retry | 9674991.0 | 1 | 5 | 0.33 | 0.60 | 30404 |
| full64 | 9674996.0 | 183 | 248 | 177.36 | 235.97 | 1936216 |
| 最终audit | 9675010.0 | 1 | 8 | 0.48 | 0.85 | 48080 |

[唯一scheduler账](stage156_energy_ml/scheduler_accounting.json)为5job/5starts、361CPU秒/574聚合执行wall秒、0live；一次失败与4次成功全部计入，不叠加嵌套GNU或进程内部时钟。full各GNU子进程digi/reco/native/extract为75.05/23.01/74.95/3.74 CPU秒；native内部68.477636299CPU秒/81.701203869wall秒、ROOT读17498706B。未测并行/GPU加速，也不把EOS等待当事件CPU开销。

Pilot/full临时ROOT总量319061/2240544B，全部RDO/REC/ntuple当场删除。Full作业返回时EOS挂载短暂缓存未显示文件，按记录的精确root URL复制到临时运输文件再解包、删除临时文件；不是物理失败，也没重跑full。

[清理审计](stage156_energy_ml/storage_cleanup.json)：合并事件文本 `ntuples/energy_ml_stage156/event_records.json.gz` 为2155857B，原native/paired/seed文本逐字节回读相同。源码胶囊137106B，23份日志胶囊75834B已回读核对；删除22261548B重复事件/seed/包/结果运输，合并两份相同输入metadata。无持久ROOT，原HITS/PHYS、其他阶段和Stage54资产未动。

## 阶段结论和下一步

真实μ方法控制已闭合，同时直接表明单纯非leading活动不是其他根识别。低pz组支持57父、overflow只3父，后者不能以低比例或少数零候选宣称安全。下一步必须推进有判别规则的联合响应与留出控制，不能继续将访问schema成功当物理收益，或再开旧网络/增益/时间/seed网格。

[Stage157冻结合同](stage156_energy_ml/next_execution_contract.json)使用同一原HITS、Stage146已核身份的前4096父，先0–127 sequential与64–127 suffix核分块不改变实际state/raw/PRD/RNG，再在实测成本门通过后固定64个64-entry chunk、16job×4独立进程链、初始最多4job并发。累计60000CPU秒、pilot1500秒、audit500秒是新实验的事前预算，实际4096成本/并行加速未测量；不自动增加预算，无新G4或独立ν。

只冻结Q15与Q15+G6两个低维控制：站1–3的candidate_N和sum abs dx保留新位置内容，已有raw15配固定point条件OLS/经验响应covariance及95th split-conformal阈值；entry modulo4的fit/cal/留出，报告all/低pz/overflow/highactivity的报警N/分母/Wilson95和缺失支持。合法空集合sum=0须有wafer支持；距离mean/min等仍null。不把未评分当未报警，不把控制误报外推总体/data，不拟合ν能量。

实际data8006只有已核旧raw控制，尚无匹配native REC/PRD/空间manifest，联合data校准继续input_missing，不制造空间data或默认producer相容。之后才根据实际μ控制限制另冻全原ν队列能量/八层三尾比较，所有原门和Stage137扩大门保持。真实covariance校准、宽能区/来源与data迁移、乳胶、GRL/背景/接受度、实际相关nuisance和独立确认仍开放，Stage87 direct62保持、整体目标未完成。
