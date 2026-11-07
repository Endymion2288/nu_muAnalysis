# Stage151：实际 conditions04/06 的同父 μ 读出与完整轨迹对照

## 阶段目标与冻结范围

执行 [Stage150 冻结合同](stage150_energy_ml/next_execution_contract.json)，推进 Stage132 §5.5。只改变当前官方 digi/reco/ntuple 的 GlobalTag：由 Stage149 实测的 `OFLCOND-FASER-06` 改为输入 HITS 元数据所记的 `OFLCOND-FASER-04`。几何、pinned d32 代码、原父与显式随机规则固定；目的为测量这个已知条件差异对实际读出／轨迹的影响，不将条件匹配本身当作校准。

先原 entries0–3 的4父物理 pilot，通过身份、raw／baseline及有限 full covariance 后，按测得成本准入原 entries0–63。原父未按能量、电荷、风险、辐射尾或选择结果更换。正式64个不同原父，pilot4次重叠不计独立样本；本阶段物理执行68个 entry，无新 G4、新独立 ν、能量或响应 fit、旧评分 refit、reserved forward。

## 输入、配置与实际执行

[协议](stage151_energy_ml/protocol.json)原样复制上一阶段合同。

- HITS：`/eos/experiment/faser/sim/mc24/particle_gun/100012/sim/s0012/FaserMC-MC24_PG_muon_fasernu_100GeV-100012-00000-s0012-HITS.root`。
- 旧 PHYS：`/eos/experiment/faser/sim/mc24/particle_gun/100012/phy/s0012-r0023/FaserMC-MC24_PG_muon_fasernu_100GeV-100012-00000-00004-s0012-r0023-PHYS.root`。
- 名义06证据：`ntuples/energy_ml_stage149/event_records.json.gz`；旧原根／身份依据沿 Stage146，未重提 Stage149。
- 现成 Calypso d32、`TI12MC04/FASERNU-04` 不变。digi/reco/ntuple 三步实际锁定 GlobalTag04，由各输出配置和真实日志交叉核对。官方 reco 的 `--cond` 分支存在打印 `args.config` 的错误，本实现只在 `configFlags.lock()` 前覆盖 GlobalTag；未修改官方算法。
- silicon `Random.SeedOffset=2026110749`；waveform 每父 `720000000+10000*event+1000*detector_index`，顺序 Calo/VetoNu/Veto/Trigger/Preshower，同 Stage149。比较真实 private 初末状态，不假定不同 mapping 下末状态必相同。
- μ 控制选择保持：单长轨迹、`50<pz0<2000 GeV`、至少7层、非负 χ²、ndof>0 且 χ²/ndof<10。正式 ν cuts、全部 K、原 split／角色／隔离保持。

命令如下；科学数组、ROOT、Cling、digi/reco 与统计全部在 HTCondor，提交目录 `~/condor/nu_muAnalysis/stage151/`。本地仅文本代码、调度、日志和精确运输合并。

```bash
python3 ml/stage151_submit.py pilot
python3 ml/stage143_monitor.py --stage 151
tar -xzf ntuples/energy_ml_stage151/pilot_result.tar.gz
python3 ml/stage151_submit.py admission
tar -xzf ntuples/energy_ml_stage151/admission_result.tar.gz
python3 ml/stage151_submit.py full
tar -xzf ntuples/energy_ml_stage151/full_result.tar.gz
python3 ml/stage151_condition_logs.py
python3 ml/stage151_submit.py audit
tar -xzf ntuples/energy_ml_stage151/audit_result.tar.gz
python3 ml/stage151_finalize.py
```

AFS worker 脚本随任务 transfer 到 scratch，并以 basename 启动。复用官方构建，只按需加载 helper；BLAS1线程、事件串行保持私有随机流顺序，没有适用 GPU 的训练。底层精确 argv／退出状态见 [full pipeline](stage151_energy_ml/full/pipeline.json)。

## 实际 conditions 与映射

[真实解析日志表](stage151_energy_ml/resolved_conditions.json)保留04 pilot/full与149原06日志来源。

| 步骤／folder | tag04实际解析 | tag06实际解析 |
|---|---|---|
| digi、native `/WAVE/DAQ/CableMapping` | CableMapping-00 | CableMapping-01 |
| digi `/WAVE/Digitization` | WAVE-Digitization-02-LG | WAVE-Digitization-04-LG |
| reco `/WAVE/Calibration/MIP_ref` | WAVE-Calibration-02-LG | WAVE-Calibration-03-LG |
| 已解析 `/Tracker/Align` | TRACKER-ALIGN-02 | TRACKER-ALIGN-02 |
| 已解析 BField Maps／Scales | GLOBAL-BField-Maps-03／GLOBAL-BField-Scale-03 | 相同 |

这些是本次真实解析的 folder tags，不是全部 payload 数值的测量或1σ系统定义。MIP 校准与 raw 积分是不同测量层；不能仅凭 MIP tag 变化就预期 raw 必变。未从 folder tag 相同推出所有条件、历史 release、输运或 data 迁移已等价。

04实际16路、06实际18路，16个共同物理 Identifier 逐一匹配，而不是只按 branch 名称匹配。06独有 Preshower2/3；04仍覆盖合同原11 scint+4 Calo，额外 Veto11保留。[通道表](stage151_energy_ml/channel_mapping.tsv)给出真实64bit Identifier及channel。旧 PHYS 没有认证物理 cable map，旧随机流未知，其同名 branch 比较仅作描述性对照，不当真值或要求 raw 精确相等。

## 成本准入与本次直接验证

[原始准入](stage151_energy_ml/full_admission.json)在查看正式风险前冻结，物理 pilot 通过。pilot GNU CPU：digi80.53秒、reco20.54秒、native84.50秒、extract3.27秒；三个 post-first-event 总间隔为0.740049641／0.833426218／0.135742701 CPU秒。按含初始化的3倍 affine64估计669.0731136 CPU秒，另预留100秒审计；准入时已用194、剩806 CPU秒，满足原1000秒累计预算。准入轻作业随后实际记1秒；full提交限制705秒，未抬预算或缩 prefix。

[正式提取审计](stage151_energy_ml/full/summary.json)：64父新旧run/event／原根身份精确，61 selected／leading state 与同新 ntuple 精确，61有限／对称／正定 full5×5 covariance，3无leading保留；没有同面truth pull或关联概率认证。64父 actual mapped raw/status/baseline 与同新 ntuple 精确。1024通道视图，1010实际可测、14缺失保留；status0/1/4为642/377/5。额外两路 Preshower从06消失不当探测效率变化，实际mapping差与无hit区分。

正式 pipeline wall313.209577189秒，digi167.612681409／reco31.195564643／native107.359490238／extract7.034527350秒；含初始化的全链吞吐约0.20434父/秒，仅适用本次小控制。GNU CPU分别95.69／27.61／99.73／4.93秒，包含在scheduler账内不重复相加；最大GNU RSS1965720 KiB。提取ROOT请求1769169 B，不当整链网络流量；全链累计 ROOT读取和物理网络字节未测量。临时ROOT合2173065 B，成功提取后全部删除，无持久xAOD/ROOT。

## 最终配对结果与局限

[最终审计](stage151_energy_ml/summary.json)及[同父配对表](stage151_energy_ml/comparison.json)均通过，前4例 current04 native、paired、private RNG before/after精确复现。64父与既存06的run/event、根、seed及初始RNG精确；Calo/VetoNu/Veto/Trigger/Preshower末状态各64/64也相同。这是实测结果，未将“必须末状态相同”作为准入前提。

| 04对06配对项目 | 实测 |
|---|---:|
| 共同物理通道视图／实际可测视图 | 1024／1010 |
| 存在性／status不一致 | 0／0 |
| 各通道有限raw charge的差值 min/median/max/RMS | 全部0 pC |
| stored raw/peak/status/baseline/RMS全部逐字段精确视图 | 1020/1024 |
| leading PRD集合／reference surface／native状态／完整covariance精确 | 各61/61 |
| pz04−pz06及相对差 | 全部0 GeV／0 |
| 两tag均未选中／仅04选中／仅06选中／均选中 | 3／0／0／61 |

额外field审计发现4项baselineRMS差，未将其隐去或放宽为精确一致：entry6/17/55的Preshower1分别为−8.940696716e−8／−2.980232239e−8／+1.192092896e−7 mV，entry59的Timing1为+8.940696716e−8 mV。其他stored字段无差。其量级很小，但这只描述差的大小，未认证具体浮点／平台原因，也未将其赋成物理1σ。不需为此重做物理链，新增一次轻量audit_detail读取现成缓存，全部成本计入。

旧PHYS同名branch对照的Calo结果如下。raw差条件于两侧都有合法读数，status比较保留原64父，不能互换分母。

| 通道 | 有效raw对数 | current04−old raw中位 pC | 均值 pC | RMS pC | status不同父／64 |
|---|---:|---:|---:|---:|---:|
| Calo0 | 61 | −0.639731452 | −1.402751506 | 2.272949648 | 23 |
| Calo1 | 61 | −0.550664067 | −1.678051285 | 4.253485411 | 12 |
| Calo2 | 61 | −0.676298827 | −1.572574135 | 2.410212235 | 23 |
| Calo3 | 61 | −0.593813449 | −0.904197626 | 1.340929991 | 12 |

04和06这四路raw相同，因此把当前GlobalTag换回输入tag04没有恢复旧PHYS的Calo raw。不能从本有限前缀直接指认gain、单位或输运bug；旧噪声、producer/release、实际旧map未认证。其他通道的同父完整值在[raw表](stage151_energy_ml/paired_raw.tsv)，没有只挑Calo或离群父保存。旧／当前pz0差61对：中位0、均值−0.828562884 GeV、RMS13.027578552 GeV、范围−97.694953125至+22.445617187 GeV；04/06完全同值。它不是同面truth残差、tracking bias或covariance pull，不能据此校准。

本阶段足以排除“仅切换这个GlobalTag即可解释本64父共同raw或轨迹差异”这一具体机制；真实mapping范围确有改变。没有新能量训练／风险评估，低能胜传统和总体μ辐射FPR为未测量；正定covariance和真实测量归属仍不等于校准或后验概率。

## 完整资源、存储与验证

| 作业 | 用途 | exit | scheduler CPU s | execute wall s |
|---|---|---:|---:|---:|
| 9674753 | 原前4pilot | 0 | 194 | 232 |
| 9674767 | 准入与pilot配对 | 0 | 1 | 6 |
| 9674778 | 原前64正式 | 0 | 233 | 326 |
| 9674793 | 正式配对／前缀复现 | 0 | 1 | 5 |
| 9674798 | 4项stored字段差定位 | 0 | 2 | 8 |

[累计账](stage151_energy_ml/scheduler_accounting.json)：5次start全部终态／exit0，431 CPU秒、577聚合execute wall秒、0GPU，低于1000预算。无物理失败或父替换。audit原有regex字符串触发Python SyntaxWarning，已改为等价raw字符串并通过语法检查，不据此重跑已通过的科学计算。一次EOS FUSE结果文件暂不可见，XRootD stat实有63125 B且job exit0；从同一远端文件下载临时运输再解包，未重复提交。临时下载已删除。

[紧凑存储审计](stage151_energy_ml/storage_cleanup.json)：原native／paired／legacy／seeds文本逐字回读合并为 `ntuples/energy_ml_stage151/event_records.json.gz`，2162085 B，小于8MiB。格式为原相对路径→原JSON文本字符串；恢复gz条目时重新gzip该文本。两份相同input metadata合一；8份实际日志压缩为 `software/stage151/worker_logs.tar.gz`，67303 B，逐文件字节回读通过；含实际执行wrapper的源码胶囊 `software/stage151/source_snapshots.tar.gz` 为98635 B。删除19958668 B重复事件／运输文件，未动原HITS/PHYS、Stage149及Stage54。未删除正在引用的提交目录或其他项目目录。

验证包括真实4→64前缀复现、原身份、所有current raw／track精确检查、actual物理Identifier对照、61fullcovariance及stored字段差逐项审计；另运行Python语法、shell语法、文档链接／历史全文保留与 `git diff --check`。文档结果见[验证记录](stage151_energy_ml/document_validation.json)。本阶段先保存本中文报告，再与代码／紧凑表本地Conventional Commit，不push。

## 阶段结论与下一步

本控制表明：真实conditions04/06分别解析生效，映射相差两路Preshower；共同raw charge/status/presence和61条完整轨迹／covariance无差，只有4项极小baselineRMS差。输入tag匹配没有解决当前对旧PHYS的Calo响应差，不能把原conditions不匹配继续当作已经证实的成因。

下一按[Stage152有限合同](stage151_energy_ml/next_execution_contract.json)，在同一μ HITS原entry0做实际Ecal HITS→analog→ADC→有限窗raw控制。先核已保存current04的raw/status/private随机流和实测成本，最多原0–3，不重跑SCT或整链。记录实际SD修正hit信号／时间／TOF、实际kernel条件、780–930ns与fullacq模拟电荷、落在histogram支持外的信号，回答有限DAQ时间窗是否解释本例偏弱；不做第二次Birks修正、gain/time/seed扫描或要求旧PHYS相等。1000累计CPU秒、400pilot、100audit reserve、0G4/fit，实际pilot闭合和3倍成本准入后才能做4例。

Stage132真实covariance／关联校准、宽能区与data迁移、Ecal真实clipping总体响应、乳胶匹配、曝光GRL／背景／完整生成接受度、真实相关nuisance辅助约束及独立确认继续开放。原Stage87direct62、1.05/1.01/1.03、八层三尾上95≤+2pp及Stage137双低箱5%扩大门保持；1.05仅非劣效。pz0-only一次方动量、允许px/py/q/p/弯折、raw11、typedNaN／合法signed、非0status不提供timing、Calo缺失、全部K及角色/reserved均保持。整体目标未完成。
