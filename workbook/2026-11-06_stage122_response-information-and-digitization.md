# Stage122：真实波形、敏感沉积层级与同 HITS 响应重复

本阶段执行路线图 §103 和 Stage121 的可交付读出工作包，起点 `0dff970`，分支 `main`。目标是判断现有摘要之外的真实波形/沉积时序是否改善连续能量风险，并测量固定模型对同 HITS 数字化涨落的敏感性。以下给出实际测量、实现核对与尚未交付的输入缺口。

## 1. 输入、角色与不变量

沿 Stage119 已冻结的 27 个 nominal/JEFF/ENDF 文件（source_index 36–62），每环境 π/K/charm 各 3 文件，保留原文件纳入概率。不是根据新波形效果补源，也没有开放 expansion reserved。原 selected 队列 **7501 行**：train **3454**、cal **1725**、开发 test **1882**、隔离 **440**。真 50–100 GeV 对应 60/25/20/0 行；100–200 GeV 为 263/120/54/6 行。train 两低箱独立 incoming 代理为 **50/225**（60/263行），cal 为22/95，test为20/53；共享环境视图不增加独立父数。多个来源/环境共享 incoming 只归一个 active role；原隔离 run/event 仍隔离。已有响应曝光和 incoming 代理不认证完整 GENIE 家族，不称新 blind。

原 89033 身份、17657 隔离、46575/11612/13189 active 与全部 1016 K 不改。模型一次方动量只有 pz0；px/py、q/p、弯折量可用；11 路 raw charge、status/typed NaN、合法 signed 负值、Calo 缺失传播保持。pz0>50 GeV 和原 fitted/reduced-charge 选择不改；不得把 −1 或所有负电荷一律替换。模型输出/风险均不访问 Stage119 新 reserved。

## 2. 实现闭合与排错

使用已编译官方 Calypso `d32b0ff3`，不重编框架。原 RDO 稀疏重建继续使用官方 `faser_reco.py --isMC --geom TI12MC04`，新独立 HITS 读取/数字化显式配置 `OFLP200`、`FASERNU-04`、`OFLCOND-FASER-06`。

历史 RDO 的标识位布局比当前字典旧，不能用当前字典直接解码历史 id32。最终联结为：当前 digitizer ID → 官方 CableMapping → 实际硬件 channel → 历史 RDO 持久化 channel；几何 station/plate 由当前 cable 元素确定。完整生成波形/随机状态保留，未接线 PMT 按官方数字化算法在消耗噪声流后过滤，不按 plate 合并 PMT。

首轮直接解码旧 ID 的 27 源结果、初版 C 使用窗外总 hit 数的结果均为**实现排错记录，不能用于物理结论**。C 已改为 7 个窗内 log1p(MeV) 分箱、窗内 log1p(total MeV) 和窗内零标记。40 个原 selected 父的 6 项 raw/reduced charge 与原 typed62 **最大差0 pC**，全部选择一致；全9源官方Veto2映射已复核为channel6/7，完整252父的原选择闭合，119个其他cuts有效候选的六维最大差0 pC；2父独立进程的 ADC/重建/before-after随机状态完全一致。原 reduced 核对失败来自误用类默认时间差，固定版本 MC 脚本实际覆盖为 Veto 27.21 ns、Preshower 51.41 ns（积分35 ns）；按 producer 修正，未放宽容差。见 [QA](stage122_energy_ml/reconstruction_qa.json)。完整失败、重做与原因见 [实现审计](stage122_energy_ml/implementation_audit.md)，费用计入总账。

## 3. 固定 A/B/C/D 比较定义

A=原 62 维；B 累加三个固定通道（VetoNu0/1、Preshower0）各 6 个 signed ADC 积分窗、前 20 点基线均值/RMS、ADC=0 比例与 availability，共 92 维。真实 ADC 每路 600×2 ns；缺波形保持 NaN+availability，不将无容器解释为精确零测量。C 累加 27 个窗内沉积量，共 119 维；D 再加 12 个窗外量，共 131 维。

敏感沉积时间扣实际几何 z/c，Preshower 再扣条件库给定的纵向光传播项。窗内为 [−20,1200) ns，D 为 <−20、[1200,10⁴)、[10⁴,10⁶)、≥10⁶ ns。D 仅代表实际持久化历史；原生产的 G4 终止值未认证，不能称完整无限迟到能量或中子标签。

四臂各 3 seed、400 round、depth 5、eta .04、min_child_weight 20、lambda 10，CPU hist/nthread=1；4 个臂并行。train-only 拟合，cal 一个 incoming 加权 log offset；不调参、不选赢家。权重为 incoming 归一后除原文件纳入概率。500 个 component 内共同 incoming 抽样，完整原八层、missing/上游/高端、bias/R68/实际总正负 tail50 与配对风险。区间不覆盖 source/refit/研究选择/真实系统，开发 test 不当确认。

## 4. 同父数字化与选择路径定义

事前固定 9 个来源（每环境×成分取原冻结第一个 source），按两个低能、E≥200 high-y、200–400 GeV 过渡、自然高端控制 × 原通过/失败分层，每个非空单元 CRC32 抽最多 3 父。共 **252 父**，纳入概率见 [支持表](stage122_energy_ml/replica_sampling_support.json)。不按新模型误差挑父。

每父计划 16 个不同数字化流，另把 replica0 从完整保存的 TRandom3 Streamer before state 恢复一次并逐字核 ADC/after state。非零 seed 由 run/event/detector/replica 稳定确定，不使用 TRandom3(0) 或 Python hash。原始波形经官方 primary/secondary 工具重建，先对 native raw/reduced charge 和选择闭合，再传播到固定 Stage87 f0；只改变 VetoNu/Preshower，tracker/Calo/Veto/Timing 固定。

全部父的选择分母保留；其他 cuts 失败者不能因波形变化迁移，也不强塞任意模型输出。有效候选仅在 worker 的不可变代码副本中暂去三条相关 scint cut 提取，正式 cuts 未变。输出均值只用于条件方差恒等式，不能平均后当部署预测；重复实现不增加独立父 N，不称 Bayes error。

## 5. 预定分支与未测量范围

每环境每低箱需 ≥100 train incoming、≥50 evaluation incoming 才做环境 2×2。最低箱 train 目前 nominal/JEFF/ENDF=21/16/23、开发 test=3/14/3，未达门槛。仅当 B/A 在两个低箱有预定留出支持且实际尾不退化，才启动联合波形似然，不因新输入多就自动重开网络搜索。

完整 sameGENIE G4 重复还需可认证的完整末态、EVNT entry 与重放随机状态；当前响应队列只核 incoming/主 μ/HITS—RDO 联结，尚未认证该输入。不能把少数 truth 粒子重造为完整 GENIE，也不能把另一批 Pythia 父当本队列的同末态重复。真实 data/MC 的共同 ADC 标定、时基、背景/DAQ 可用率闭合未测量；MC B 的工程可实现性不等于 data 已可部署。

## 6. 旧库存有界补证

对 200131–136、200184–189 各一个已知精确 RDO，仅 `MetaReader(mode='full')`，共 12 文件、各 10000 entry。实际只得到 GUID/大小/压缩信息和空 `/TagInfo`；没有 EVNT entry/seed/parent。内部实测 **2.312516388 CPU s、4.890049724 wall s、RSS 568116 KiB**。见 [原始紧凑记录](stage122_energy_ml/metadata_supplement.json)。本支线完成，不再扫描；旧池独立性门未认证，不阻挡上述响应实验。200187/188 同 EVNT 文件仍不等于同 entry。

## 7. 执行、资源与产物

科学读取、重建、训练、forward 和统计全部通过 `~/condor/nu_muAnalysis/stage122/` 的 HTCondor 执行；本地仅代码/文本/stdlib 打包运输。27 源 native 任务和 9 源候选任务独立并行；小规模 hist 拟合各臂并行，内线程 1。Athena waveform 工具没有 GPU 实现；这些小型固定 BDT 尚无实测 GPU 加速收益，因此本轮使用 CPU。GPU 单核/多核加速比与物理网络流量均未测量。

复现入口为 `ml/stage122_prepare.py`、`stage122_native.py`、`stage122_compare.py`、`stage122_replica_prepare.py`、`stage122_replica_extract.py`、`stage122_replica_analysis.py`；官方接口 helper 和 submission shell 同阶段入库。包内文件清单保存在 `*_package.json`，不可变 worker/descriptor 见 [batch templates](stage122_energy_ml/batch_templates.json)。返回 tar 逐成员原字节核验，FUSE 不可见时用 XRootD 运输；只保留紧凑最终产物，不保存 xAOD/RDO 中间文件。

```bash
python3 -m py_compile ml/stage122_*.py
for stage122_script in AnalysisZipFramework/submission/run_ml_stage122*.sh; do
    bash -n "$stage122_script"
done
condor_submit <固定 phase>.sub
# 标准库打包/逐字节收集，不在本地运行科学计算
python3 ml/stage122_transport.py <phase> --fetch
python3 ml/stage122_resources.py
git diff --check
```

原最终门槛保持：两低能/传统 upper95≤1.05，all/direct≤1.01，其他五层≤1.03；八层总/正/负 tail50 差 direct upper95≤+2pp。1.05 仅非劣效，不能称突破。独立确认、真实系统、背景与接受度仍未交付，整体逐事件能量目标尚未完成。

## 8. 同队列连续能量比较：未支持两低箱稳定增量

以下仅为修正 MC 条件和硬件通道后的最终结果；排错版本不参与结论。log-RMSE 无量纲，tail 为加权事件百分比。开发 test 的 50–100/100–200 GeV 支持为 **20/53 个 incoming（20/54 行）**；总体 1882 行、1682 incoming。

| 开发 test 层 | A | B | C | D | 原强 f0 | 传统 pz0/0.8 |
|---|---:|---:|---:|---:|---:|---:|
| E50_100 | 0.338493035 | 0.335125321 | 0.328611227 | 0.331184716 | 0.348886111 | 0.161655797 |
| E100_200 | 0.240402836 | 0.236674833 | 0.251275574 | 0.249062959 | 0.247746263 | 0.235828088 |
| all | 0.322733895 | 0.324238250 | 0.322667466 | 0.322574660 | 0.304950632 | 0.589189864 |
| pz50_100_trueE200 | 0.724560164 | 0.735448581 | 0.736794101 | 0.734075029 | 0.673507404 | 1.894357045 |
| high_y | 0.680605224 | 0.704157863 | 0.672151487 | 0.665134015 | 0.651764099 | 1.702067949 |

| 层级配对（开发 test） | 50–100 GeV 比值 [95%区间] | 100–200 GeV 比值 [95%区间] |
|---|---|---|
| B/A | 0.990050863 [0.885922098, 1.132788373] | 0.984492683 [0.916288558, 1.056657245] |
| C/B | 0.980562214 [0.923045729, 1.028610535] | 1.061691142 [0.983765291, 1.139084491] |
| D/C | 1.007831409 [0.963673568, 1.050784766] | 0.991194469 [0.970958779, 1.017136767] |

B/A 两低箱点估计有约 1–2% 下降，但两个条件区间都跨 1；cal 两箱比为 1.143882405 [0.875641127,1.290543861]、1.002875774 [0.962501345,1.052696990]，也没有共同增量。C/B、D/C 的两低箱 test 同样未支持一致改善。最低箱 B 的 log-RMSE 0.335125321 仍大于传统 0.161655797；B/传统 2.073079520 [1.352615344,3.081704491]，本条件队列中有明显差距。不是原大池总体性能的重新估计。

局部信号完整保留：test high-y 的 C/B=0.954546590 [0.913360811,0.993455728]，但 cal high-y 的 C/B 区间含 1；cal 的 D/C 最低箱=0.925892761 [0.896309551,0.992044140]，test 未复现。cal 总体 C/B、D/C 也有下降，但 test 对应区间含 1。不能据这些开发层选赢家或声称排除时序信息。

A/B/C/D 在 cal 和 test 的原最终联合门槛全部 False。以 B 为例，test 两低箱/传统上95=3.081704491/1.269570131（要求≤1.05），all/f0 上95=1.087773866（要求≤1.01），困难低pz真高E/f0 上95=1.161936425（要求≤1.03）；high-y 负尾差 f0 上95=+18.958780920 pp（要求≤+2 pp）。最低箱 B 总/正 tail50=29.180327869%，f0=20%、传统=0%；B−A 的点差虽为0，区间仍约±14 pp，不能称尾已受控。

完整 train/cal/test 的八层及 missing、上游、高端风险、bias/R68/三尾、配对MSE差与500抽样在 [metrics.tsv](stage122_energy_ml/metrics.tsv)、[paired.tsv](stage122_energy_ml/paired.tsv)、[gates.tsv](stage122_energy_ml/gates.tsv)。A/B/C/D 只在本较小队列训练（最低箱60行）；f0是保留的大池强基线，两者训练支持不同，不能把相对f0的差距解释为新输入损害信息。

本固定学习政策和有效支持下未分辨出低能稳定增量；不等价于理论信息减少或物理假说阴性。开发 cal 的条件正态近似给出 B/A 检出5% RMSE改善所需 incoming约2971/169；这是22/95个 cal incoming 的方差规划，未计来源/重拟合/系统或联合尾，不是保证充分的训练/确认量。见 [planning_support.tsv](stage122_energy_ml/planning_support.tsv)。不追加 seed/树/容量网格。

## 9. 同 HITS 重复：本次读出涨落占比小，错误可跨实现持续

**252个(source,entry)父路径全部保留**；119个通过其他 cuts，原名义118个最终通过。4个有效候选处于隔离，0forward；115个active父作1840次不同数字化视图推理，另115次原读出控制推理，共1955个固定f0输出、0fit。不是252个新增独立相互作用；incoming代理、历史曝光与不同环境仍限制家族独立性。原始波形重建的全部有效候选通过6维特征闭合和完整252父的原选择核对。

下表为全部active有效候选的**安全双primary定义**、所有16视图（含未通过scint选择者）的条件诊断。权重包含原文件权重与事前父抽样概率；9来源是原冻结来源中的固定首文件，这些权重不把便利子队列认证为整个flux的无偏总体。active合并含train/cal，只用于机制，不冒充泛化检验。log误差、MSE、方差均无量纲。

| 真值/运动学层 | 父N | log-RMSE [95%] | 平均条件方差 | 方差/MSE（%）[95%] | 16次全尾N（正/负） |
|---|---:|---|---:|---|---|
| E50_100 | 13 | 0.360380149 [0.237357660,0.465223412] | 0.00184295834 | 1.419037 [0.032783,2.399622] | 3（3/0） |
| E100_200 | 24 | 0.166191958 [0.122551660,0.208798771] | 0.000421055724 | 1.524472 [0.109031,3.150828] | 0（0/0） |
| pz50_100_trueE200 | 14 | 0.677129877 [0.425329935,0.892273508] | 0.00387924757 | 0.846065 [0.349973,2.504415] | 6（2/4） |
| high_y | 24 | 0.571032131 [0.389397884,0.734266217] | 0.00212821683 | 0.652672 [0.254101,1.654920] | 7（3/4） |
| all | 115 | 0.265870515 [0.216042974,0.309313031] | 0.00017550089 | 0.248278 [0.110872,0.539644] | 12（7/5） |

两低箱重复视图平均 fractional bias 为 **+36.111130% / +8.672960%**，实际总tail50为 **25.548902% / 0%**；第一个箱中的3个正尾父在16次实现中都仍是正尾。低pz真高E中6/14父16次全处于尾，2正、4负；不能因输出波动小就称预测正确。恒等式 `mean(e²)=Var16(Z)+mean(e)²` 最大残差4.440892099e−16；无偏ddof=1方差另逐父保存。

开发test重复子集只有20个有效父（最低/第二低箱4/3；困难低pz真高E2、高y4），远小于连续比较队列。test最低箱var/MSE=2.428680%，第二箱0.001548%；不以其少数事件裁决总体物理原因。所有环境、角色与八层/抽样类别、missing/上游/高端的bias、MSE、正负实际尾及parent-cluster区间见 [replica_risk.tsv](stage122_energy_ml/replica_risk.tsv)，逐父原读出误差、repeat均值减原预测、样本方差见 [replica_parents.tsv](stage122_energy_ml/replica_parents.tsv)。

这支持的有限结论是：**在当前HITS、固定f0和已生成的VetoNu/Preshower读出条件下，仅靠这两组数字化涨落不足以解释所测的大部分log平方误差**。tracker、Calo、Veto、Timing及原读出availability固定；没有测全探测器数字化或输运方差，不归因为唯一物理原因，不称Bayes误差。16流有限，parent bootstrap不覆盖有限流的方差估计误差、source/refit、条件标定或研究选择。

安全双primary选择下，252父的16次实现均未发生名义通过/失败迁移；1个其他cuts有效但scint失败的父16次都失败，全部保留。这个零观察不认证零迁移率。完整分母与概率在 [replica_migration.tsv](stage122_energy_ml/replica_migration.tsv)。

**必须区分producer边界：** 重复中发现3父共13个额外VetoNu hit。固定官方NtupleDumper在按container ordinal循环时仍使用长度2的数组，超过两hit后的C++行为不受定义；本实现明确只计算前两个primary积分，保留额外hit计数，不模拟越界、不删实现。因此上述风险/选择是安全定义下的诊断，不能把所有实现称为完整官方producer闭合。独立核对确认source51 entry4386（开发test high-y，其他cuts通过）有2/16视图原生选择未知，原生通过概率保守为[0.875,1]；source54 entry7875和source57 entry8429共11视图由其他cuts确定失败，通过概率[0,0]。每父明细见[选择界限](stage122_energy_ml/replica_availability_and_selection_bounds.tsv)；其他cuts失败者即使有secondary仍不能迁移。低能结论不由丢弃这些事例获得。

图：[响应层级风险](stage122_energy_ml/response_risk.svg)、[条件方差占比](stage122_energy_ml/conditional_variance.svg)。重复平均值仅作分解，从未作为可部署多视图能量估计。

## 10. 持久化窗外时间：已测现象和未认证的生产边界

最终独立核对给出27来源×4敏感板的 **108条** 时间覆盖记录，见 [persisted_time_coverage.tsv](stage122_energy_ml/persisted_time_coverage.tsv)。全表持久化校正时间极值为 **−0.682764263 ns 至 4.315339342423439×10³⁵ ns**，后者出现在source49 JEFF VetoNu0。source45 JEFF VetoNu0总敏感沉积 **132.477243096 MeV**、窗内 **63.105124638 MeV**，窗外比例 **52.365309571%**，最大时间 **2.5317022954946665×10¹⁵ ns**。对照source36 nominal VetoNu0/1窗外均0；同源Preshower1总 **7312.004963932 MeV**、窗内 **7305.907701457 MeV**，窗外 **0.083387012%**、最大 **3007.213519500 ns**。这些是各源已选父的条件记录，不是同末态输运配对。

固定源码中 `ScintHit::m_meanTime` 为float、`meanTime()`直接转double，p1a converter把每条hit的时间存为float；这些接口本身没有把大时间替换为−999或按当前DAQ窗裁剪。极晚记录可能涉及物理衰变/追踪终止或生产/持久化问题，但当前输入的实际physics constructors、decay、kill与最大时间设置没有足够producer证据，**原因未分辨**。不能把大值自动视为坏值删除，也不能把它直接解释为中子迟发或可被延长DAQ窗口收回的能量。

D实际量到了固定窗外能量分箱及其风险；没有直接输入巨大时间数值。C只用窗内沉积，不含窗外总hit数。原生产终止未认证，因此R3是**持久化诊断已完成、完整物理时窗解释未完成**。不追加事后时间网格，不以这些极值代替全队列结论。

## 11. 独立最终验证与完整成本

最终正确条件27源重读任务 **9669253.0–26**、四臂比较 **9669267.0**、九源16流 **9669268.0–8**、九源官方Veto参考映射 **9669278.0–8**、全父安全分析 **9669279.0** 和独立核对 **9669283.0** 均exit0。9669273在原生特征闭合失败时、任何模型forward之前退出；随后9669274查明Veto2参考通道错误，修正后全父重核。失败和重做不从资源账删去。

[最终核对](stage122_energy_ml/final_validation.json)实测：40父六维raw/reduced最大差 **0 pC**；2父跨独立进程完整ADC、before/after随机状态一致；**192项**已存RMSE独立复算最大差 **0**；修正前后A原62维预测数组完全相同；**115父**条件方差/平方误差分解复算最大差 **3.9406683211701266×10⁻¹⁶**，8个风险标量最大差 **8.326672684688674×10⁻¹⁷**。这认证计算与存储一致，不认证尚未有输入的物理系统。secondary的2个原生未知视图继续保留上述界限。 入库前仅规范TSV换行/末列空字符串及SVG行尾空白，逐字段/逐XML token核验完全相同，见[文本格式审计](stage122_energy_ml/text_formatting_audit.json)；不重算物理结果。报告30个test RMSE和18个配对比值/区间逐项匹配原TSV，[交付检查](stage122_energy_ml/delivery_validation.json)记录历史全文与本地链接验证。

[资源总账](stage122_energy_ml/resource_summary.json)覆盖 **122个**提交记录：**119 starts/119 terminated**，**3个idle取消**，其中 **21个执行失败**，本阶段pending **0**。scheduler取整总CPU **11506 s**，所有并发任务的execute wall相加 **18430 s**（不是会话历时），GNU单进程最大RSS **2053044 KiB**，GPU作业 **0**。具体失败与申请/分配核数在[逐任务账](stage122_energy_ml/resource_jobs.tsv)，133份GNU时间记录在[进程账](stage122_energy_ml/resource_GNU.tsv)。GNU子过程与scheduler重叠，不能相加；RSS不等于并发整棵进程树峰值。

| 工作 | 实测CPU s | 聚合wall s | ROOT读字节 | 限制 |
|---|---:|---:|---:|---|
| 正确条件27源、7501父 | 2980.747139532 | 4906.360914740 | 11192805050 | 内部计时；0.397379968 CPU s/父；maxRSS1999736 KiB |
| 九源252父×16数字化流 | 932.096701681 | 1489.464992004 | 3004820476 | 内部计时，非新独立父事件吞吐量 |
| 最终四臂训练/比较 | 75.99 | 39.09 | 未测量 | GNU，4臂并行、各nthread1 |
| 最终全父安全分析 | 11.90 | 13.45 | 未测量 | GNU，maxRSS472212 KiB |
| 独立最终核对 | 18.34 | 20.65 | 未测量 | GNU，maxRSS419252 KiB |

27源任务每个申请2 CPU/6000 MB，比较/分析申请4 CPU/8000 MB，内层线程1；按来源/臂并行。实际成本主要在Athena读出与重建，当前工具为CPU实现。未测GPU加速、单核对照加速或物理网络流量，不以申请更多核当已证实加速。

[存储审计](stage122_energy_ml/storage_summary.json)按文件stat：最终事件缓存 **94431650 bytes**，模型 **9252679 bytes**，合 **103684329 bytes**，低于cohort60 MB＋replica80 MB合计140 MB预算。该账含必要QA/过时诊断的压缩副本，workbook文本/表图另约6.5 MB；逻辑大小不是物理磁盘占用。已逐成员原字节核验并删除 **219个**运输/软件/过时重复文件，合 **693206423 bytes**，另去重27份GNU日志。不同实现源码在删除旧软件包前逐字回读保存于ignored `ntuples/energy_ml_stage122/implementation_sources.tar.gz`，清单见[版本记录](stage122_energy_ml/implementation_source_versions.json)。软件可按manifest重打包；没有运行任务再引用被删副本。未删除原始ROOT/HITS/RDO/EVNT、其他项目、旧stage或Stage54五资产；不保留xAOD中间件。

## 12. 阶段结论与验收边界

[R1–R8完成审计](stage122_energy_ml/completion_audit.tsv)区分实际测量和未满足的条件。`protocol.json`及冻结合同内pending是执行前历史清单，不是最终执行状态；初始planning中的条件标签不能替代最终显式 **OFLP200/data20/FASERNU-04/OFLCOND-FASER-06**。原始合同与修正记录均保留。

本阶段已交付同队列A/B/C/D连续能量与实际尾、同HITS可复现条件波动及选择分母、有界旧池补证和独立复算。四臂两低箱均未稳定恢复传统、原joint全部False，因此保留原强f0；没有选B/C/D中的局部赢家。固定两组scint数字化波动仅占所测log-MSE小部分，持续低能上调/高y错误仍存在。这个机制结果支持继续研究输运和可见性，不证明唯一起因、时序无用或信息界。50个最低箱train incoming及20个开发test不足以结束整个时序假说；A/B/C/D与大池f0训练量不同，也不是纯信息上限比较。

R3仍缺实际producer的终止/时间解释，R4有2个原生secondary选择未知视图；R5当前252父缺完整同末态EVNT重放输入，未做sameGENIE G4重复。R6的B增量/环境支持条件未满足，因此没有联合波形似然或环境2×2重训。R7补证已结束，旧池身份门未认证不会重设为全局前置。真实data/MC ADC/时基/背景共同性、系统/接受度及独立确认均**未测量或未交付**。这完成本阶段能够完成的工作，整体逐事件能量目标仍未完成。

## 13. 下一阶段：有界producer/时间闭合与完整末态输运pilot

[下一执行合同](stage122_energy_ml/next_execution_contract.json)给出Stage123具体输入、选择与验收，尚未执行。

1. **安全producer与时间控制。** 只用source51 entry4386、source54 entry7875、source57 entry8429及无secondary控制父，按真实detector/primary身份实现安全积分，保留额外hit与全部父，逐例报告和原生未知的差异；不模拟越界或静默改正式cut。对source36/45/49的已有时间记录，核匹配producer实际physics constructors、decay/kill/time cuts与float持久化；有精确证据才归因，不再泛扫旧日志或按大时间删除事例。验收是无secondary路径闭合、secondary语义明确与时间解释的实证范围。
2. **另冻完整EVNT微队列并做真实G4。** 从Stage120已明确的pi0、K0两个精确EVNT入口（见合同）各至多前10000父entry的固定框，按完整truth共同选一个真50–100 GeV父、一个E≥200 GeV/y≥0.5/产生μ的pz在50–100 GeV父，各层按CRC32(file,entry)最小，不依模型误差选父。先认证完整末态与转换输入；这不是当前252父的同源证明，也不称新blind/独立扩样。缺层如实交付，不换来源补有利事件。
3. **先2父×2 G4×2数字化流测成本，再同阶段定规模。** 每G4任务初始2 CPU/8 GB，最多4任务、各wall≤7200 s、合CPU≤28800 s，紧凑保留≤200 MB；先一个真实父/流闭合再完成pilot。实测CPU/父、I/O、选择支持后，在看扩展风险前另冻后续父数/重复数；不把本阶段数字化速率当G4速率，不直接全量生产。输出父选择概率、连续风险/实际正负尾与G4及读出条件波动；有限父/流不强作总体裁决，不平均多视图当部署能量。原reserved零预测，不增加独立训练N。

下一阶段同一工作包交实际机制结果和精确缺项；若精确EVNT入口或完整末态转换不可用，交缺对象/字段/命令与已完成producer/time结果，不再续无限metadata阶段，更不宣称所有G4都不可做。这个有限成本pilot用于判断持续错误是否随输运改变；低能新增有效支持/功效和新G4成本目前**未测量**。没有追加树/seed/时间网格或解冻旧方法族。原角色、全部K、pz0-only一次方动量、raw11/status/typed NaN/signed/Calo缺失、正式选择、最终联合门与真实系统/独立确认要求保持。
