# Stage152：固定 μ 前缀的实际 Ecal HITS／有限窗响应诊断

## 阶段目标与冻结范围

执行 [Stage151 冻结合同](stage151_energy_ml/next_execution_contract.json)，承接 Stage132 §5.4–5.5。Stage151实际04/06的共同raw完全相同，不能用只切换GlobalTag解释当前相对旧PHYS的Calo响应差。本阶段只检验同一已知HITS前缀的实际Ecal信号、时间约定、有限窗与ADC闭合，不扩大为旧producer/release追查或gain／seed扫描。

原entry0为唯一物理pilot，身份／actual ADC／同current raw-status／private RNG和实际成本通过后，最多原entries0–3。没有按能量、风险、电荷或状态换父；pilot与正式前缀重复不计独立事例。无新G4／独立ν／能量fit／响应模型fit／旧评分refit／reserved forward。官方waveform重建仍执行其原定脉冲算法，不把“模型fit为0”误解成停用官方波形拟合。

## 输入、实际配置与测量口径

[本阶段协议](stage152_energy_ml/protocol.json)原样复制Stage151合同。

- 原HITS：`/eos/experiment/faser/sim/mc24/particle_gun/100012/sim/s0012/FaserMC-MC24_PG_muon_fasernu_100GeV-100012-00000-s0012-HITS.root`。
- 同父raw／status／private初末状态参考：`ntuples/energy_ml_stage151/event_records.json.gz`中的full paired与seeds；同父旧PHYS值只作描述性参考，不当校准真值。
- 复用 pinned d32现成构建，`FASERNU-04/OFLCOND-FASER-04`，`OFLP200`、项目`mc20`，原事件run/lumiblock/timestamp不覆盖；只创建Ecal geometry与Calo digitizer/reconstruction，不重跑SCT／track／整链。
- Calo实际算法私有seed为`720000000+10000*event`，同Stage151；必须保留8个几何PMT的全部噪声draw，再由官方cable map过滤为可读通道。不能仅按4路生成噪声。
- 从实际persistent SD修正`EcalHits`读取encoded energyLoss及globaltime；不施加第二次Birks／非均匀修正，不将该量当incident energy或独立幅度参考。实际corrected time为官方float约定的`meanTime−center.z/c`。
- 独立实现沿已验证Stage141核：真实conditions、2ns采样、20倍oversampling、10 presamples、600点；float能量／time histogram、CB卷积、实际噪声、取整和ADC下限。逐可读采样与actual算法比较，不用ADC线性叠加代替非线性输出。
- raw目标是实测Ecal `780–930 ns`含端点。报告同有限窗analog、full600点采样analog及比值（分母正才定义），并用原生TH1.FindBin检查histogram支持之外及原算法忽略的最后一bin。full acquisition也不是完整迟到粒子输运。

每路另独立复算实际raw：官方baseline均值减ADC、2ns/50Ω积分，遵守原float波形精度。分解为digitizer float signal、baseline估计／噪声项和取整／clipping项，只要求这些测量项加和闭合，不把负raw裁为0。非0status不导出到达时间；原弱／无hit状态保留。

主要执行命令如下，科学读取、ROOT／Cling、数值分解和统计均在HTCondor：

```bash
python3 ml/stage152_submit.py pilot
python3 ml/stage143_monitor.py --stage 152
tar -xzf ntuples/energy_ml_stage152/pilot_result.tar.gz
python3 ml/stage152_submit.py admission
tar -xzf ntuples/energy_ml_stage152/admission_result.tar.gz
# full/audit四条命令仅在准入后执行；本阶段未准入，未执行
python3 ml/stage152_submit.py full
tar -xzf ntuples/energy_ml_stage152/full_result.tar.gz
python3 ml/stage152_submit.py audit
tar -xzf ntuples/energy_ml_stage152/audit_result.tar.gz
# 所有实际作业终态并检查输出后，合并保留本次证据
python3 ml/stage152_finalize.py
```

提交目录`~/condor/nu_muAnalysis/stage152/`，4CPU/12GB，MaxRuntime86400秒，无应用短timeout；400CPU秒pilot、1000累计CPU秒、100秒audit reserve。worker transfer到scratch并以basename执行，BLAS1线程；没有可用GPU加速的训练步骤。先测初始化和实际单例event CPU，再作3倍affine4准入；没有实际interevent分布的部分须明确，累计CPU移除上限仍有效。

## 实际测量

[实测汇总](stage152_energy_ml/summary.json)、[逐通道表](stage152_energy_ml/pilot_channels.tsv)和[pilot身份审计](stage152_energy_ml/pilot_summary.json)给出唯一原父entry0、run100012/event0的结果。157个实际Ecal hit全在可读Calo2；8个几何PMT生成噪声后实际保留4路，共2400ADC采样，与独立实现逐值差0。current04 raw/status及真实private RNG初末状态均精确匹配Stage151对应父；不是只比较seed整数。

| 实测量 | Calo0 | Calo1 | Calo2 | Calo3 |
|---|---:|---:|---:|---:|
| SD修正hit数 | 0 | 0 | 157 | 0 |
| encoded SD energyLoss，MeV | 0 | 0 | 48.329432259 | 0 |
| finite780–930ns模拟电荷，pC | 0 | 0 | 0.064892711495 | 0 |
| full600样本模拟电荷，pC | 0 | 0 | 0.064895476622 | 0 |
| finite/full模拟信号比 | 未定义 | 未定义 | 0.999957391063 | 未定义 |
| 实际signed raw，pC | 0.03275390625 | 0.017890625 | 0.04904296875 | 0.31142578125 |
| status | 1 | 1 | 1 | 1 |
| baseline估计／噪声项，pC | 0.031413993836 | 0.008186988830 | −0.004319877624 | 0.319799041748 |
| 取整／clipping项，pC | 0.001339912415 | 0.009703636169 | −0.011529865457 | −0.008373260498 |
| 实际触底ADC点 | 0 | 0 | 0 | 0 |
| 旧PHYS同名raw，pC | 0.461254894733 | 0.409824222326 | 2.349575281143 | 0.486499011517 |

这里Calo0/1/3虽没有该通道SD hit，仍有真实生成／读取的ADC和baseline噪声；**不能把它们标为无ADC缺失或把非零raw叫真实沉积**。finite/full为0/0，保留未定义。整个Ecal collection非空，官方算法生成几何PMT噪声的行为和collection完全为空时的早退不同。全部status1均不提供timing。

Calo2实际corrected hit time范围−1.067843437至+0.307808876 ns；落在原histogram支持外／被最后bin规则排除的hit和encoded能量均0。逐hit原globaltime、实际center-z TOF及corrected time原数值完整保存于事件缓存，本报告没有另外汇总globaltime／TOF分位数。实际条件为baseline15650 ADC、RMS3 ADC，CB α=−0.319999993、n=1000、σ=3.670000076 ns、mean820 ns、norm0.550000012（native工具单位；不臆造独立gain校准单位）。返回向量还含preshower slope0.004347825889，此字段不参与Ecal卷积。参数取自本次实际条件工具，没有挪用Stage129其他IOV的payload。

独立baseline−ADC积分最大差5.551115123e−17 pC；signal_float+baseline/noise+rounding/clipping对raw最大加和差2.430278201e−13 pC。Calo2用于该精确分解的float信号为0.064892711832 pC，与double模拟覆盖积分的差只作实现精度记录，不把浮点闭合当区间覆盖。

**本例有限窗捕获99.9957391%的已模拟full acquisition信号，且histogram外hit为0。** 因而本例的弱current Calo2 raw不能用大量漏出有限窗／histogram解释。其0.06489pC前ADC模拟信号本身很小，加上实际噪声／baseline和取整得到0.04904pC，链条测量层闭合。旧PHYS raw2.34958pC的差仍是描述性事实；没有认证旧随机流／producer／完整条件和响应，不将其直接判为gain／单位bug，也不将一个弱μ事件推广成μ辐射总体或强子响应结论。

## 成本准入、停止与存储

[冻结准入审计](stage152_energy_ml/full_admission.json)：physical_pilot_passed=True，但admitted=False。pilot GNU CPU117.14秒，实测单次execute CPU64.921099922秒；3倍affine4预测为`3×(117.14+3×64.921099922)=935.709899298 CPU秒`。准入时已用122、剩878CPU秒；加100秒审计预留后不满足原预算，**未提交full四例，也未修改预算、换父或重开同一控制**。

该单次execute包含首次调用／处理成本，未测interevent分布或逐项lazy初始化成本。935.71秒是保守预测，不是已经测得四例总时长；不能以“后续应该更快”代替准入证据。正式四父、pilot/full前缀重复、其他μ能量／辐射尾／data迁移为未测量。本冻结方法控制以实际1父及成本限制结束，不将未准入当物理阴性。

| 作业 | 用途／结局 | scheduler CPU s | execute wall s |
|---|---|---:|---:|
| 9674813 | entry0真实Ecal控制，exit0 | 122 | 147 |
| 9674827 | 缓存统计及成本准入，exit0 | 0 | 5 |

[累计账](stage152_energy_ml/scheduler_accounting.json)：2次start全部终态，122CPU秒、152聚合execute wall秒、0GPU，预算1000秒；轻审计scheduler CPU0是整数计数精度，不代表不耗CPU。pilot GNU user105.00/system12.14秒、wall135.78秒、RSS1810616KiB；内部CPU110.568835573、wall126.655585770秒均包含在GNU／scheduler，不能重复相加。实际ROOT累计读取2088416B，含初始化和条件读取，不当HITS独占或物理网络字节。GPU加速、全树峰RSS、不同线程加速比未测量；本任务没有训练，也未开展大批量生产。

[紧凑存储](stage152_energy_ml/storage_cleanup.json)：唯一事件原JSON文本精确合并回读为 `ntuples/energy_ml_stage152/event_records.json.gz`，13560B，格式仍为原相对路径→原JSON文本字符串。源码／实际worker胶囊 `software/stage152/source_snapshots.tar.gz` 为26759B；六份真实调度／stdout／stderr压缩为 `software/stage152/worker_logs.tar.gz`，6109B，逐文件字节回读通过。删除4402897B运输／事件重复副本；没有写出或保留ROOT/xAOD，没有动Stage149/151原证据、输入HITS或Stage54历史资产。

真实首例已作为小样本验证；Python／shell语法、文档本地链接／原历史全文保留、协议原字节与`git diff --check`另核，记录于[文档验证](stage152_energy_ml/document_validation.json)。按仓库要求先本中文报告，再与代码和紧凑实测表本地Conventional Commit，不push。

## 下一科学问题及文献可行性

本次排除的是一个实际前缀父的明显有限窗损失；不再把旧PHYS条件／gain／seed追查串成无期限前置。下一按[Stage153冻结pilot](stage152_energy_ml/next_execution_contract.json)，回到Stage132 §5.5需要的真实新测量：**同一leading测量面上，未被leading使用的cluster相对轨迹局部位置和拟合误差是否可读取、闭合，并提供旧count摘要没有的空间分离量？**

只读Stage124已知request0原REC的前最多40个role1父，不看cal/test或新风险、不重做数字化／G4。要求真实PRD归属、同面／同基底、loc1及正方差；记录其他cluster的scaled squared separation、固定排列无关汇总和coverage。拟合状态误差尚未校准、误差独立性未认证，因此该量不是χ²覆盖、pull或关联后验。没有候选／基底不匹配／身份未知仍保留原父。Stage149已有μ TSOS只作basis-access参考，不能冒充已持有未归属cluster空间的μFPR控制。先取得真实原生内容和成本，之后才另冻μ辐射控制／全原队列固定能量消融，不能因pilot通过自动训练。

本轮读取[CMS PF原文摘要](https://arxiv.org/abs/1706.04965)，其依据是实际track／cluster联系与分辨率，而FASER无同等粒度，不照搬性能。[Deep Sets摘要](https://arxiv.org/abs/1703.06114)说明集合聚合可与输入排列无关；这里只用事前固定和／均值，不开网络网格，聚合本身不算新信息。另用Crossref核实[Kalman track/vertex fitting题录](https://doi.org/10.1016/0168-9002(87)90887-4)及[Adaptive vertex fitting题录](https://doi.org/10.1088/0954-3899/34/12/n01)，本轮未读两篇全文，不把其方法当当前已校准概率依据。[检索与适用性记录](stage152_energy_ml/research_sources.json)明确排除一次题名不相干的arXiv查询，未将其错误引用。

Ecal真实clipping／μ总体响应、同面truth协方差校准、真正关联后验／宽能区与data迁移、乳胶匹配、真实曝光GRL／背景／全生成接受度、相关nuisance辅助约束及独立确认仍未完成。原Stage87direct62、1.05/1.01/1.03、八层三尾差上95≤+2pp与Stage137双低箱5%扩大门保持；1.05仅非劣效。pz0-only一次方动量、允许px/py/q/p/弯折、raw11／typedNaN／合法signed／非0status无timing／Calo缺失、全部K及角色／reserved均保持。整体目标未完成。
