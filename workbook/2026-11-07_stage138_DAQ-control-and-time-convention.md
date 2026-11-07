# Stage138：真实DAQ控制闭合与globaltime口径核验

## 阶段目标与结论

执行Stage132 §5.4的第一项实际控制：保留的精确HITS快照能否通过官方数字化，恢复原11路signed raw/status及实际积分窗。**同一自然train父的两个独立进程中，7200个ADC样本、全部重建结果逐值重复；9路实际读出raw/status与原ntuple在float32精度完全一致，另外2路无读出的producer默认值也一致。** 从ADC独立复算9路780–980ns含端点的101样本积分，最大差为0 pC。

这例Veto的18.407908094 MeV持久化沉积全部发生在负globaltime，但TOF校正后的hit时间范围是−0.033250332至+0.032790184ns，实际raw为74–164pC。原固定globaltime窗不能解释此例的DAQ响应。该证据只覆盖frame50控制，不能当完整DAQ谱系标签、μ辐射尾部校准或所有旧生产异常的解释。Stage137正式边界机制仍在运行，Stage139稀疏谱似然尚在修复数值优化；整体项目未完成。

## 输入与冻结政策

[protocol](stage138_energy_ml/protocol.json)在新增控制前冻结。父为Stage135/131原frame50，run200095、π来源、EVNT entry82990，真Eν=90.288000701 GeV；没有重新挑父。输入为`ntuples/energy_ml_stage135/parent_50_qa_hits.json.gz`、Stage131原private RNG状态和matched_input raw/status。精确EVNT路径及case保存在合同；EVNT仅供应事件框架上下文，不重新输运。该父下游沉积经原observer认证全部来自μ根及其后代，非μ出包络KE=0，但单例不能覆盖μ辐射尾部。

软件为pinned d32b0ff3/Athena24.0.41，FASERNU-04、OFLCOND-FASER-06、OFLP200；只新增Cling helper及控制脚本，不重编官方重建/输运。将四类ScintHit逐项重建至transient collection，验证id、E、t、track和局部端点完全相同；通过实际`ScintWaveformDigiAlg`及其algorithm-owned工具，恢复原每探测器seed和完整初末TRandom状态。并非只给未使用的public clone设seed。

原HITS文件名`FaserMC-Stage131Nu-990131-00050-stage131-HITS.root`对应producer的run/lumiblock/timestamp=990131/51/0，必须恢复该EventID override。原EVNT上下文不能直接代替它。[pinned源码证据](stage138_energy_ml/producer_context_evidence.json)记录了实际producer定义与ntuple默认值；错误上下文结果全部作为程序诊断，不混入控制结果。

## 实际测量

完整数据见[raw11_control](stage138_energy_ml/raw11_control.tsv)、[ADC积分复算](stage138_energy_ml/ADC_integral_validation.tsv)、[时间表](stage138_energy_ml/timing_control.tsv)及[波形图](stage138_energy_ml/DAQ_control_waveforms.png)。

|读出|原硬件channel|实际raw，pC|status|控制口径|
|---|---:|---:|---:|---|
|VetoNu0/1|4/5|无ADC；ntuple默认0|无hit；ntuple默认1|HITS为空且ADC为空；不是测得零信号|
|Veto10|14|164.121718750|0|原signed raw，非拟合charge|
|Veto20|6|74.321289063|0|同上|
|Veto21|7|81.791103516|0|同上|
|Timing0|8|−0.060278320|1|真实噪声负电荷，保留；不提供到达时间|
|Timing1|9|0.461381836|1|低阈值真实读出，保留raw；不提供到达时间|
|Timing2|10|39.926420898|0|原窗口|
|Timing3|11|39.718105469|0|原窗口|
|Preshower0|12|6.077280273|0|原窗口|
|Preshower1|13|4.098129883|0|原窗口|

工具double `/50` 与原ntuple float32分支最大差3.662109378e−6 pC；转换回原float32后精确一致，未放宽检查。VetoNu无ADC时严格同时要求原HITS为空、官方输出为空、原ntuple raw=0/status=1；不制造ADC或arrival time。额外硬件channel15/24/25保留在完整重复性证据中，没有加入原11维部署输入。

|探测器|PMT-hit贡献数|持久化E，MeV|global[0,1000)内E，MeV|global时间范围，ns|几何/光传播校正后hit时间，ns|
|---|---:|---:|---:|---|---|
|VetoNu|0|0|0|未定义|未定义|
|Veto|50|18.407908094|0|[−6.005382061,−5.301756859]|[−0.033250332,+0.032790184]|
|Trigger|28|5.189460006|0|[−0.138632983,−0.108180478]|[−0.244428322,+0.242203265]|
|Preshower|20|8.233779934|8.233779934|[8.581574440,9.615756035]|[−0.323557675,+0.576587796]|

Trigger每hit进入两个PMT，因此表中能量与贡献数均为PMT贡献口径，不能当两倍物理沉积；对应独立14个hit、物理沉积2.594730003 MeV。所有校正后hit都没有进入能量histogram的−20ns下溢。上述hit时间在CB卷积之前，**不是从status非0波形取得的到达时间**。Veto/Trigger有效CB核均值为825/830ns，Preshower为850ns；具体条件包括baseline15650 ADC counts、RMS3 counts及核形状，见[实际context](stage138_energy_ml/context_0.json)。原raw实际为780–980ns含端点、samples390:491，绝非整600点或globaltime矩形窗。

物理上，本例负globaltime在减去探测面z/c及光传播后接近0，经真实kernel/采样生成有效脉冲。该结果支持修正谱系监督的测量口径，不能将all-time沉积分数直接改名为DAQ分数，也不能假定ADC按μ/非μ来源线性相加。完整期望analog来源分解、Ecal的官方Birks/局部非均匀响应与μ辐射尾部联合控制仍未测量。

## 程序核因与验证

7个作业全终态，5失败全部计入成本。首轮helper误用AtlasHitsVector不支持的back；改为官方索引。随后Cling符号错误最先来自未加载ScintReadoutGeometry/Identifier实现库，后续vector转换错误是失败JIT事务的症状，已明确加载依赖。扁平10字段传输仍逐字段精确核验，没有改变物理数据。恢复990131/51/0后COOL条件有效。最后修正控制自身“11路均应有ADC”的错误假设，按原producer区分无hit默认与实际读出。逐次失败、原因、修复和scheduler记录均保存在本阶段目录；未调宽raw/status容差，未过滤父或切换样本。

[control_summary](stage138_energy_ml/control_summary.json)证明两个独立进程的ADC、工具结果、四套完整初末RNG状态完全相同；[独立积分验证](stage138_energy_ml/independent_integral_validation.json)为另一条float32 ADC算术复算路径。成功返回包的两个data成员逐成员长度与本地落盘字节完全一致，见[transport_validation](stage138_energy_ml/transport_validation.json)。未执行新的能量模型训练/forward、G4、完整digi/reco链或reserved预测；重复控制不增加独立ν N。

## 命令、资源与产物

```bash
python3 ml/stage138_submit.py
# Condor上的官方环境：两个独立 native.py 进程
python -u ml/stage138_control.py
python3 ml/stage138_submit_summary.py
# Condor上的LCG环境：不再数字化，独立ADC积分和时间/波形统计
python -u ml/stage138_summarize.py
```

提交目录统一为`~/condor/nu_muAnalysis/stage138/`。作业9674035、9674044、9674049、9674067、9674077失败；9674086控制、9674099汇总exit0。各请求4CPU/12GB，实际native串行独立进程，科学内部计时不与scheduler嵌套相加。[scheduler_accounting](stage138_energy_ml/scheduler_accounting.json)总7attempt/7starts、**547 CPU秒、745 aggregate execute wall秒、0GPU**，低于原1800 CPU秒控制预算（汇总单独300秒上限）。所有尝试的单native GNU峰值RSS1758516 KiB；成功两个进程内部合计133.708296 CPU秒、147.733793 wall秒。没有声称测得GPU加速；本规模由框架初始化和小ADC控制主导。

最终事件级证据为ignored `ntuples/energy_ml_stage138/control_0.json.gz`和`control_1.json.gz`；紧凑表、图、配置与审计在`workbook/stage138_energy_ml/`。核对Stage135队列为空、runtime压缩成员已有逐字节证明后，删除61,071,040 B重复preflight返回包，保留3,755,701 B可执行runtime及首例QA，见[清理记录](stage138_energy_ml/storage_cleanup.json)。home根目录未发现旧nu_mu_stage提交目录，所有新提交均在专用condor目录。

7份重复提交manifest经原字典完整回读验证后去重：212097 B压至10270 B紧凑记录＋6472 B共享gzip原manifest；恢复索引见[manifest_compaction](stage138_energy_ml/manifest_compaction.json)。未修改冻结的科学合同、实际提交descriptor或scheduler账。

## 下一步任务与验收

1. 完成已冻结Stage137全部4032父/3002selected的几何接受G、未接受H、总K条件D及粒子类消融；输入原角色、原seed/basename与新observer。验收为全部旧字段精确一致、24192 detector-parent HITS闭合、原八层/三尾与独立标量复算；在结果之前不追加候选臂。
2. 在此控制上冻结期望analog响应分解接口，随后以明确选择的μ-only与辐射尾部控制检查误报及适用范围；标签必须同通道/采样/有限窗，Ecal沿官方修正。验收不能只用本例或平均MIP扣除，也不能用status非0的内部shift作timing。是否扩大新仪器化由Stage137机制证据决定，不无条件再跑全队列。
3. Stage139对稀疏有限MC的覆盖进行数值优化修复。必须先解决自由似然低于受限似然及EM不同初值的边界驻留，全部冻结toy重新认证；不删除失败toy、不把当前局部结果当覆盖证明。

Stage87 direct62仍参照；原pz0一次方动量/raw11/typed NaN/合法signed/Calo缺失、原pz>50及fit/reduced cuts、全部K和角色保持。原两低箱/传统上95≤1.05、all/f0≤1.01、其他五层≤1.03、八层三尾上95≤+2pp保持，1.05仅非劣效。真实相关nuisance、data曝光/GRL/背景/接受度、乳胶逐例匹配和独立生成确认尚缺，完整物理目标未完成。先中文报告再本地Conventional Commit，不push；Stage54五资产和历史原文保持。
