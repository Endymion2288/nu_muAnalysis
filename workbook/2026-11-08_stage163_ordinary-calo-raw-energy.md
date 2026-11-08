# Stage163：普通Calo raw幅度的原队列能量检验

## 目标与冻结比较

按[Stage162合同](stage162_energy_ml/next_execution_contract.json)，检验普通Calo实测rawQ4在原X62及状态/可用性控制之外是否有自然ν能量增量。不是重新扫旧X模型、Stage158固定G6族或已完成Stage136/140有限MC toys。原89033记录/角色0–3为17657/46575/11612/13189，71376active和全部K不变，不forward隔离/reserved。

三固定臂X62、X62+M12、X62+M12+Q4。M12逐四module为raw_valid、fit_invalid、overflow；Q4为asinh(as-produced raw_charge/1pC)。现有X62中的fitted/calibrated E_EM及其NaN传播不变。有效raw需finite、已知非负整型status且不含8/128/256，以及正finite baselineRMS；fit失败16/32或overflow4不抹掉测得raw，overflow不被恢复为真电荷。合法signed负值/-1不统一删；原producer无raw -999特殊sentinel声明，不把所有signed -999当占位，status/RMS按类型处理。

Stage162已证4data父96旧raw为正采样积分，不能自动等同当前有符号积分。本实验保留原producer输出，不拟合跨producer转换、不认证data迁移。[源码字段映射](stage163_energy_ml/field_mapping.json)明确isMC Calo0–3和raw_integral/50；不猜CaloLo/Hi别名。

## 来源与pilot

输入`ntuples/energy_ml_stage119/old_input.npz`、Stage124原source_requests及五origin的原manifest，完整文件见[冻结合同](stage163_energy_ml/protocol.json)。按真实run/event和原保存entry核对，逐一对照原raw11及pz0。没有entry=event−1。早期临时PHYS未留存的来源保持父/角色，仅新增raw未知，不用其他REC重建成替代producer。

五固定request0/254/255/257/260，各原前最多40个role1，零train不换source；独立request0原前4。先字段、身份、实际raw内容及成本，再准入全队列。pilot不读cal/test能量风险、不做能量fit。

实测pilot148父，其中120原PHYS可读、28缺原PHYS；120身份/pz0和1320个finite原raw11精确，480 Calo有效raw中201合法负值。独立4逐字段精确；同source/channel rawQ/E_EM的12项中11项跨度超过64float epsilon预定界，另一项不超，不能写12/12。pilot没有raw有效且原fitted缺失的支持，不把幅值动态范围冒充此类恢复已被测到。准入3倍CPU投影945.634862676秒、分支字节投影249151261.349 B、I/O聚合wall投影1413.379184秒，后两者不是实测或硬完成界。

首次全量batch02/03未通过raw11精确门。查Stage82原报告及官方worker可知，production_protocol中两个input为被拒绝的historical backward候选，训练support实际来自另行生产、随后清理的scratch merge PHYS。将它们当原producer是本阶段映射错误。剩四批在verified IDLE/NumJobStarts0时撤销；不降低精确门、不转换rectified raw、不删K或替换X。有限原候选核查和按原“缺原PHYS则新增变量未知”政策修正，均在首次能量fit/新cal-test风险前进行。保留原source_manifest和全部失败成本。

[有限来源审计](stage163_energy_ml/source_repair_audit.json)实际确认request258/259的343/317父身份精确，但pz0非精确；VetoNu0 raw分别180/343、163/317不一致，最大差1.003847718/0.859921873pC，其他通道也有广泛差异。因此不仅是未知raw定义，实际不是原PHYS。修正后三个Stage82原PHYS均不可用，加原Stage70，共1044active父新增变量未知；其原X62、角色与K全部保留。诊断首次未处理空Track_pz0而exit1、4CPU秒，修复保留NaN后exit0，6CPU秒；不将该空轨迹程序失败当物理零。

## 资源、命令及验证

12000累计CPU秒、pilot700、audit/fit预留1500；独立准入完成后实际已用14秒，重新冻结8×1310秒分批额度及1500秒预留，承诺11994秒，修正旧准入1311秒向下取整时刻造成的2秒超额。失败分批的修复只使用该批剩余额度，来源诊断计入1500秒预留；4核16GB/最多4job、8个全量批次、每批4个I/O线程，fit三臂fork共享原输入/各单线程。GNU/CPU/ROOT字节及I/O壁钟实测、三倍full投影、disjoint CPU allowance，失败也计入，不用app wall timeout。科学ROOT/数组/统计/拟合只走`~/condor/nu_muAnalysis/stage163/`。小型固定hist BDT保持既有算法，无需为GPU改变对照。

```bash
python3 ml/stage163_ops.py submit --phase pilot
# 成功后独立repeat、admission；仅admitted才batch_00–07、fit、validate
```

原Stage87三seed2026110255–257/depth5/eta.04/400轮/incoming权重，恰9fit；每臂一个原role2 global logoffset。X62需逐值复现Stage87，所有模型reload精确。不earlystop或扫描。配对500incoming bootstrap seed20261108163+role；原八层三尾及两低箱/传统上95≤1.05、all/X≤1.01、其他≤1.03与尾差+2pp均保持；Stage137四项cal/test双箱5%门另核。开发test非独立确认，区间不含来源/重训/研究选择/真实系统。

## 全量支持与原模型闭合

[准备审计](stage163_energy_ml/preparation.json)记录89033行、71376active均保留，148个pilot/full对照精确；原62列逐列typed清理不变。280个active来源中276个有原PHYS，70332个父身份/raw11/pz0精确。1044个缺原PHYS父新增字段未知；再有5个父不满足完整四路raw有效域，共1049父非全四路可用，不能把它们从风险分母删除。

| 实测项目 | 数值 |
|---|---:|
| 四路raw全有效的active父 | 70327 |
| 有效raw通道视图 | 281308 |
| 有效raw且原fitted Calo缺失的通道视图 | 31 |
| 合法负raw通道视图 | 113320 |
| cal/test两最低箱有效raw、但原fitted缺失 | 均0 |
| cal/test overflow父 | 均0，不能认证overflow总体 |
| cal/test最低箱父数 | 183/183，全部四路有效 |
| cal/test第二低箱父数 | 904/856，完整raw为902/851 |

[成分/来源覆盖](stage163_energy_ml/cohort_support.tsv)保留原active π/K/charm=34305/31714/5357，K的train/cal/test=18901/5722/7091。1044缺原PHYS不等于K未进入训练：这些父仍用原X62训练/预测。全量各批有效raw中精确−1/−999均0；本轮合法负数没有统一删除，也没有用signed域无依据的数值列表充当sentinel。RMS默认0及非有限/非法status另按类型处理。

[九模型记录](stage163_energy_ml/fits.json)：每臂46575 train/11612 cal，global logoffset分别0.0251936905960、0.0237102662125、0.0233300312924。原X62逐值复现Stage87 cached direct_cal，最大log差0；三seed×三臂均reload精确，未重训以挑结果。

## 能量与尾部实测

下表为content臂X62+M12+Q4相对状态/可用性控制X62+M12的无量纲log-RMSE比，括号是500次配对incoming条件95%区间。完整结果见[paired](stage163_energy_ml/paired.tsv)、[metrics](stage163_energy_ml/metrics.tsv)、[八层门](stage163_energy_ml/gates.tsv)及[图](stage163_energy_ml/calo_raw_energy_comparison.png)。

| 真E层 | cal | 开发test |
|---|---|---|
| 50–100 GeV | 0.990793 [0.977914,1.000999] | 1.006770 [0.998989,1.014749] |
| 100–200 GeV | 0.998796 [0.995081,1.003146] | 1.003566 [0.998652,1.009052] |
| all | 1.001153 [0.999790,1.002541] | 1.000325 [0.999499,1.001381] |
| pz0 50–100且真E≥200 GeV | 1.002888 [0.998182,1.006982] | 1.000386 [0.997191,1.003435] |
| high-y | 1.000913 [0.996409,1.005041] | 0.999786 [0.996378,1.003555] |

两低箱四项均未建立原定义的5%增量，开发test两项区间下端也高于0.95。该固定测量/政策的5%级收益没有获得支持；这不是所有波形信息的理论上界，也不是完整source/refit/真实系统区间。

开发test实际log-RMSE如下：

| 层 | Stage87 X62 | 状态控制 | 加raw4内容 | 传统pz0/0.8 |
|---|---:|---:|---:|---:|
| 50–100 GeV | .282644343 | .282365265 | .284276742 | .145661386 |
| 100–200 GeV | .246328767 | .244951731 | .245825140 | .247936985 |
| all | .287491236 | .287376434 | .287469765 | .557189970 |
| pz0 50–100 GeV | .498965866 | .497698359 | .498798658 | 1.275309885 |
| 低pz真E≥200 GeV | .658177334 | .657183052 | .657436989 | 1.887789515 |
| high-y | .609394510 | .609780753 | .609650528 | 1.618799491 |

最低箱content/传统=1.951627 [1.653734,2.308464]，第二箱=.991482 [.927037,1.065149]；cal相应2.065816 [1.784644,2.389394]、1.143186 [1.052310,1.239607]。因此两箱cal/test的原1.05非劣门均未通过。content最低test median bias+20.054590%、R68=18.956859%、正tail50=13.661202%，传统为+14.060708%、10.330065%、0%；传统对低pz真高E则严重低估，不能据最低箱直接用pz门控替换模型。

三臂×cal/test的6项原joint均False，原因不能笼统写为全部保护失败：content相对Stage87的其他六层RMSE保护及原八层三向tail保护均通过，主要低E/传统要求失败。另一个content/M12的保护检验中，test低pz真高E负tail差上95=+2.058764 pp，未低于+2 pp；不能用原tail通过掩盖这个额外对照。完整原门和Stage137四项5%扩大门分开记录于[comparison](stage163_energy_ml/comparison_summary.json)。

31个坏拟合可读raw视图证实新增读数存在，但两低箱cal/test中此类支持为0，不能声称本轮检验了“大量低能坏拟合恢复”。rawQ与原fitted E的不同、原producer缺失及精确程序控制均已显式检查；本固定raw4表示仍未建立低能收益。没有证据把原最低箱失败归因于这次修复的两个来源映射错误，Stage87输入本身未改变。

## 独立验证、性能与紧凑留存

[独立审计](stage163_energy_ml/validation_summary.json)通过：285504个通道用独立标量status/RMS/合法signed规则核查，9个保存模型重新推理、三臂offset用fsum独立核算，3718项风险/区间/三尾最大绝对差2.842170943×10⁻¹⁴。原角色/完整K和incoming跨角色交集0保持，quarantine/reserved预测0。原模型对照及保存预测精确；没有对新cal/test追加模型选择。

```bash
python3 ml/stage163_ops.py submit --phase pilot
python3 ml/stage163_ops.py collect --phase pilot
# repeat、admission_repair；原admission未启动撤销
# batch00–03后，raw11失败使未启动04–07撤销
python3 ml/stage163_ops.py submit --phase source_repair_retry
python3 ml/stage163_ops.py collect --phase source_repair_retry
# batch02–07_repair，逐批collect；保留原失败及剩余CPU额度
python3 ml/stage163_ops.py submit --phase fit
python3 ml/stage163_ops.py collect --phase fit
python3 ml/stage163_ops.py submit --phase validate
python3 ml/stage163_ops.py collect --phase validate
python3 ml/stage163_finalize.py
# 下行只用已验证TSV修正图中文字布局，不打开事件数组/重算统计
python3 ml/stage163_plot.py
```

[终态资源账](stage163_energy_ml/resource_audit.json)为22次提交/17次实际start/0live，438 scheduler CPU秒、526聚合execute wall秒；3次执行失败全计，另5次未启动撤销。所有最终8批、fit、validate均exit0。全量成功提取内部187.968297 CPU秒、198.003513聚合wall秒，ROOT请求200943606 B；线程source wall重叠比3.753792仅描述实际并发，不是受控串行加速。含失败的全链ROOT总请求字节未测量。提交4核16GB，CERN加传输资源后实际Request6核18GB，未声称这些附加核用于科学计算。

fit GNU126.42 CPU秒/65.12 wall秒/751536 KiB峰RSS；三臂模型CPU分别31.748732/32.749838/33.058581秒。validate GNU24.80 CPU秒/27.28 wall秒/521460 KiB峰RSS。scheduler的MemoryUsage为未求值表达式，不冒充数值峰值；嵌套GNU/子进程计时不与scheduler重复累加。0GPU/新G4/新独立ν；小型固定hist BDT不为GPU更改政策。具体作业、失败及GNU见[scheduler](stage163_energy_ml/scheduler_accounting.json)、[逐进程](stage163_energy_ml/process_resources.tsv)。

[清理记录](stage163_energy_ml/storage_cleanup.json)：两个原/修正manifest精确gzip各3258543/3258640 B；10份实际pilot/repeat/full NPZ按原字节归档4397515 B。事件/新数组/模型合26383050 B<64 MiB；实际源码/配置版本、完整审计、GNU和日志逐字节回读归档在`software/stage163/`，删除678712536 B重复运输/摘要/数组副本。无持久ROOT/xAOD，无SHA。归档本地首次因重复phase关键字TypeError退出，修复前未删除文件，不重跑科学计算。绘图初次遇旧matplotlib不支持layout参数，改constrained_layout兼容，仅渲染原验证表；本地绘图时间未测量，原Condor图和最终图另精确归档。Stage54十二文件size/mtime保持，未清理其他项目或正在用的提交文件。一次condor_q安全协商读失败后原handle重查成功，无重复提交。

## 阶段结论与下一步

本阶段完成普通Calo raw幅度这一固定三臂/九fit全原队列实验，**未修复最低能，也未达到扩大门，不晋升；结束该Q4实现，不追加seed/tree/loss或raw变换网格**。Stage87及原全部门保持，整体单事例低能优越性和真实物理精度目标未完成。

下一[Stage164有限合同](stage163_energy_ml/next_execution_contract.json)回到Stage132§5.2的深度—逃逸机制。Stage134总K第二箱未触发的z×K支线保持原文；新的触发证据是Stage137几何未接受H/A四个低箱5%检验通过。仅用原3002缓存补AZ=A+真z、AZH=AZ+原H两臂/6fit，与既有A/H配对，问H是否在已知真z后仍有增量，避免把深度相关性直接叫额外可见能量。真z沿Stage129的同一vertex_z_mm（第一truth neutrino decay vertex）口径、H沿原几何定义，保留199NaN/原HT权重和角色/K；不声称因果或部署，不重训A/H、不重开原总K/G/raw4网格。900累计CPU秒、4核12GB、零fit缓存QA后分析/独立审计，无ROOT/G4/新父。验收四个条件H比与原八层三尾、实际资源/独立数值闭合；区间宽不写成已证明深度解释全部H。

真实data联合纯度/增益/时基/轨迹covariance与宽能区辐射尾校准、乳胶锚点、GRL曝光/背景/全生成接受度、真实相关辅助系统和独立确认继续缺失；不重复Stage136/140已完成的有限MC toys或用任意先验补缺。后续研究依照实测条件转向，不把本阶段阴性外推成整个探测器信息极限。

阶段关闭补充：[spool清理](stage163_energy_ml/spool_cleanup.json)在查询当前Iwd队列为空、原worker/sub/log各字节核对归档后，删除100个重复提交文件92855 B，`~/condor/nu_muAnalysis/stage163/`只保留紧凑execution_index。home根旧nu_mu_stage*目录实测0。空队列的condor_q -json返回空字符串，元数据清理脚本首次JSON解析退出且未删除文件，按空队列语义修复后通过；无科学执行或预算变化。[文档验证](stage163_energy_ml/document_validation.json)与[图排版记录](stage163_energy_ml/publication_render.json)随阶段提交。
