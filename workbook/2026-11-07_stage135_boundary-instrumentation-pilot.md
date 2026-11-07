# Stage135：最小边界能流分解的原生G4 pilot

## 目标与结论

执行Stage132 §5.3要求的新仪器化小pilot，先验证首次外穿的面、粒子类、下游几何接受和相对事件时间，再测成本；没有无条件重跑4032父。**12/12固定自然train父成功，72个探测器—父HITS闭合通过，原Stage131全部旧observer字段逐值复现，首例on/off敏感HITS逐项完全相同。** 11例有非μ出靶KE，5例有Ecal几何射线接受。工具已可用于正式同支持机制比较，但尚未证明这些能量是电子可测信号。

本阶段不训练或forward能量模型、无新独立ν、无新digitization/reco/选择；使用原响应选择结果（9/12），未选中3例保留。DAQ响应闭合、μ辐射联合控制及正式能量增量尚未执行。

## 冻结输入与实现

[pilot_protocol](stage135_energy_ml/pilot_protocol.json)在新增输运前保存。精确父为Stage131原pilot：frame50/70、6/21、8/63、2/15、0/1、5/12，对应两低E、低pz真高E、高-y、transition、高E各2个train自然父。使用`production_cases.json.gz`和`parent_evidence.json.gz`恢复精确EVNT/entry/原G4seed、原HITS输出文件名，避免框架stream名变化。没有按K或新风险选父。

固定d32b0ff3/Athena24.0.41/FASERNU-04/OFLCOND-FASER-06/FTFP_BERT；仅构建新`NuMu135::ObserverTool`插件，原输运、物理、SD、重建库不改。继承Stage131根谱系与首次外穿语义：排除generator-final μ根及所有后代，非μ且非ν根分支只计第一次出实际EmulsionStationA包络；回穿及已计出射后出生后代不再计。靶外primary仍记录并保留父，正式oracle继续NaN，不填0。原生neutron timeLimit150ns保持，不称完整迟发中子响应。

新增冻结定义：

- 出射面：实际G4Box包络表面法向变换到全局，normal.z>.5为下游、<−.5为上游，其余侧面；非box立即报错，不以近似静默替代。
- 类别：e±/γ、带电强子（meson/baryon/nucleus）、中性强子、其他带电、其他中性；末两类保留，不丢罕见粒子。KE与totalE分开，不混入静质量或Eν闭合量。
- 几何接受：从实际全局退出位置和方向作正z直线，与几何中全部真实下游Veto/Ecal敏感G4Box作有向射线交集。Veto bit1/Ecal bit2，共8个实际敏感box。它忽略后续磁弯曲、散射、相互作用和探测效率，**仅叫几何射线接受，不叫可见能量**。侧面出射也可能随后有下游接受。
- 时间：退出globaltime减该G4事件最早真实primary vertex t0；仅为truth描述，冻结t<0、[0,1)、[1,10)、[10,100)、[100,1000)、≥1000ns。不是DAQ到达时间，不给非0 status提供timing。没有按ν风险扫描窗。

输出稀疏face×class×acceptance×time分箱的计数、KE/totalE与KE加权位置/方向/时间；每父最多首64条确定顺序QA，不以能量挑QA。全部保存在紧凑JSON/TSV，不运输ROOT。代码在`ml/stage135_observer/`、`ml/stage135_pilot.py`，新增C++按Athena要求C++20构建；分析主工程C++17不变。

## 实际数据与物理解读

每层仅2父，以下是**未加权pilot描述**，不是自然谱混合或效率；完整数值见[pilot_parents](stage135_energy_ml/pilot_parents.tsv)、[稀疏分解](stage135_energy_ml/pilot_components.tsv)。

|父|层|原selected|总非μKE，GeV|侧面KE，GeV|Ecal射线KE，GeV|中性强子KE，GeV|
|---|---|---:|---:|---:|---:|---:|
|50|50–100|1|0|0|0|0|
|70|50–100|1|0.129293493|0.129293493|0|0.121137834|
|6|100–200|1|1.356122828|1.356122828|0|1.208088228|
|21|100–200|1|0.724719617|0.724719617|0|0.652800577|
|8|低pz真高E|0|6.998733358|6.998708476|0|5.988842467|
|63|低pz真高E|0|144.549975902|0.011757718|113.332689533|9.591939902|
|2|高-y|0|437.274411358|2.962073494|296.837399576|62.498202349|
|15|高-y|1|186.152935443|67.098731509|50.631471963|75.919993692|
|0|transition|1|4.135537495|2.389802431|0|2.086995211|
|1|transition|1|20.750845232|17.894620861|0|12.156269604|
|5|高E|1|196.097933649|49.771057549|91.318769364|128.931314898|
|12|高E|1|321.346367076|4.777764072|3.377845278|122.971285565|

最低两层的4父中，非零K均为侧向、以中性强子为主；困难侧/高E可有明显前向几何接受。**不能以这4个低能父就断定全样本增量不可见，也不能以5个有接受父宣称可测。** Stage134最低箱K真值很有用与这里局部侧向并不矛盾：总K还可能通过训练谱/深度/组成相关性整理有限模型，机制尚须同支持正式比较。原未选中困难父不能用来代替selected能量风险。

最早event t0各父−9.396070至−6.582275ns；frame50的Veto/Trigger全时沉积分别18.407912/2.594731MeV，而旧[0,1000)窗均为0。事件参考和负globaltime确需核对，**尚不能仅凭这一描述认定DAQ bug或已完成时窗修复**。固定源码核已记录HepMC t/c、官方plane.z/c和光传播校正、CB核/过采样/有限积分窗，见[DAQ接口](stage135_energy_ml/DAQ_source_interface.json)。实际DAQ对齐和条件参数/逐通道raw闭合未测量。

## 闭合与非干涉

首例frame50（90.288001GeV ν）非μK=0，不能单凭它验证正值分支，因此仅放行原剩余11个pilot，见[admission](stage135_energy_ml/pilot_admission.json)。随后11例均有正K，所有类别范围、KE≥0、totalE≥KE通过。12父boundary有效，实际敏感box数均8，nonbox计数0。

12父稀疏分箱KE求和与旧非μKE最大差 **1.3387762010097504e−9 MeV**，totalE最大差 **1.0244548320770264e−8 MeV**；采用独立math.fsum复算。每父全部旧observer字段精确相等；72个persistent HITS/SD能量闭合通过，保留原P1a/P3a压缩容差，不放宽。frame50额外on/off模拟的全部六类敏感HITS含ID、能量、时间、trackNumber和局部端点逐项完全相同，见[非干涉](stage135_energy_ml/parent_50_noninterference.json)。其他父不冒称做过on/off双重模拟。

## 执行命令、性能、I/O与存储

全部编译及科学读取/G4/校验/聚合走HTCondor；本地只文本、传输、runtime重打包与资源元数据。命令为：

```bash
python3 ml/stage135_submit.py preflight
python3 ml/stage135_submit.py pilot
python3 ml/stage135_submit.py audit
```

精确描述符/包路径在各`*_submission.json`，目录`~/condor/nu_muAnalysis/stage135/`。4CPU/12000MB，首例串行，剩余11父最多4并行；scheduler MaxRuntime86400s，无短应用timeout，不按K耗时删父；总CPU预算30000s。复用匹配官方构建，仅新observer由cmake -j4构建。

9673945.0首例+构建、9673975.0剩余11、9673990.0汇总：3attempt/3starts、全部exit0、0失败。scheduler唯一CPU **1045s**、聚合execute wall **650s**、0GPU。其中首例含构建和on/off=219CPU/359wall秒；剩余11=826CPU/286wall秒；audit=0schedulerCPU（秒级取整）/5wall秒，GNU实际0.10CPU秒，不能称无成本。未超预算。[资源汇总](stage135_energy_ml/resource_summary.json)可查原scheduler字段。

构建含打包GNU92.65CPU秒/155.41wall秒；首父完整工程179.408590wall秒；普通11父各65.721103–137.635781wall秒，单子进程峰RSS最大1463464KiB，不是4并行总峰。持久HITS主检查ROOT实际读 **66208624B**，另首例on/off再读680241B；仅覆盖checker，不冒称整个G4输入I/O。没有新digi/reco产额或GPU加速测量。

初始runtime错误地携带150144736B未用debug符号，使返回包约59MiB；已核对所有必需运行成员逐字节一致后压缩为 **3755701B**，不重编、不改物理库，后续worker排除`.dbg`。该额外首轮运输成本不隐去，见[runtime整理](stage135_energy_ml/runtime_compaction.json)。全部返回包逐成员长度和落盘逐字节回读通过，保留紧凑命令/时间/summary和首例20KB HITS QA；无ROOT运回EOS，不保留大xAOD。缓存忽略规则和Stage136的紧凑证据规则一并保存；Stage54五资产未动。

## 下一实验与未完成项

Stage137在新增cal/test风险前冻结同支持正式问题：几何接受的非μKE（G）与未接受KE（H）分别相对A；在总K已知时再加G的D/AK；按预定EM/带电强子/中性强子作必要分量消融。统一原3002 selected分母和4032父框，复用12个pilot，剩余只做原seed G4与必要HITS闭合，避免重新digi/reco或训练X/A/AK；新标签若旧字段不一致则先修程序，不静默换父。正式数量必须结合本pilot成本和现有配对损失功效冻结，不称当前N足够认证最终尾部，不按结果筛分量。

DAQhit→通道/响应核/采样/有限raw窗的对齐和控制可与几何机制独立推进；下一实际读出pilot需含μ及辐射尾、正确signed/status/零/缺失语义，非0不赋到达时间。只有标签与测量闭合且有自然ν收益才扩大新观测，不直接预测总K替代可测性。真实相关系统、背景/接受度、乳胶匹配、认证新家族和完整物理精度仍未完成，Stage136仅有限MC条件收益。整体goal继续；原1.05/1.01/1.03及八层三尾+2pp、pz0/raw11/status/typedNaN/signed/Calo缺失、原cuts/全部K/角色保持，1.05仅非劣效。
