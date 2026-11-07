# Stage144：缓存Ecal hit到实际DAQ的来源闭合

## 目标、输入和事前范围

补上Stage142/143尚未认证的Ecal数字化方法缺口，执行[冻结协议](stage144_energy_ml/protocol.json)。四父固定为Stage142的50/6/2/0，包含两个K和原重选失败的frame2；仅复用`ntuples/energy_ml_stage142/event_records.json.gz`中的实际持久化SD修正hit与逐hit根标签。原case、selected Calo status及frame50完整private RNG状态来自Stage131。没有新G4、新独立ν、能量fit或reserved/role4/隔离预测。

预算600累计scheduler CPU秒，先frame50小测试，再根据实测成本准入其余三父，HTCondor目录`~/condor/nu_muAnalysis/stage144/`。复用pinned d32官方runtime，只在worker用ROOT Cling装入新增CaloHit/timing读取函数，不重新构建Calypso或observer。原cuts、角色、所有K及pz0/raw11/status/typed NaN/signed/Calo缺失政策保持。

## 方法和程序故障检查

按原字段逐值恢复`CaloHit`，包括实际SD已做Birks/局部非均匀修正的能量、压缩后时间/位置；不再次做Birks修正。真实`CaloWaveformDigiAlg`处理恢复的hit，保持原run990131/lumiblock=index+1、private seed规则及当前几何/条件。frame50实际初末private RNG状态均与原件精确；另三父没有原完整末状态，明确不作该比较。

独立模拟使用实际Ecal几何中心TOF、CB核、oversampling、noise/round/clip规则，在ADC前按根类别分信号。波形重建采用**官方Calo默认配置**，不套用Scint的100 ns fit窗。实际窗口由工具返回；非0 status不输出可用到达时间，合法signed raw保留。

三次失败均有程序原因与完整计账，未当作物理阴性：

| 尝试 | 观测失败 | 修复 | scheduler CPU/wall（秒） |
|---|---|---|---:|
| preflight | 官方primary reconstruction缺`/WAVE/DAQ/Timing` | 合并官方`WaveformTimingCfg` | 81 / 92 |
| preflight_repair | 原RNG初末状态/status通过，独立模拟ADC失败 | 官方先对所有几何PMT耗噪声，再删无cable通道；独立重算必须保留那些随机数 | 86 / 114 |
| preflight_rngmap | Cling头文件路径错误，未开始事件处理 | 按pinned archive核对为`FaserCaloIdentifier/EcalID.h` | 41 / 51 |

诊断与原日志末端保存在`preflight_failure/`、`preflight_repair_failure/`、`preflight_rngmap_failure/`。新增helper从真实EcalID取得**8个几何PMT的原std::map顺序**；其中4个无cable的CaloNu PMT虽然不持久化为可读波形，仍会消耗噪声。修复后比较全部4个实际可读PMT，不删除任何原本应比较的ADC、不放宽零差或来源浮点界，也不把未读出CaloNu通道编成测量。

成功首例96 CPU秒；含三次失败已用304 CPU秒、余296。按3×96=288 CPU秒的实测成本投影加轻量stdlib汇总，冻结[三父准入](stage144_energy_ml/pilot_admission.json)，明确余量很小，投影不是测量。实际三父并行作业283 CPU秒，未超预算。

## 实际测量

[正式汇总](stage144_energy_ml/summary.json)：**4父、9600个可读ADC样本逐值0差**，无触底采样；来源模拟逐采样/有限窗加和差均0。这里每个父的Ecal恰只有一个根类别响应：50/6/0全μ、2全非μ，因此**没有认证混合根Ecal或Ecal截断的加和控制**。不能把本轮0差外推为一般浮点严格线性。混合/截断Scint证据仍以Stage142/143为准。

全部16路实际Calo raw积分窗均为**780–930 ns含端点，76个2 ns采样点**，与Scint的780–980 ns、101点不同。记录的是官方工具定义，不按ν风险选择窗。

| frame/通道 | 来源 | 模拟有限窗电荷（pC） | 实际signed raw（pC） | 实际fit charge（pC） | status |
|---|---|---:|---:|---:|---:|
| 50/Calo3 | μ | 0.080416381 | 0.020312500 | 0.020312500 | 1 |
| 6/Calo2 | μ | 0.209380524 | 0.006718750 | 0.006718750 | 1 |
| 2/Calo0 | 非μ | 3.528330184 | 3.650703125 | 3.679343567 | 0 |
| 2/Calo1 | 非μ | 2.952546808 | 2.897656250 | 3.006323547 | 0 |
| 0/Calo0 | μ | 0.001167248 | −0.224511719 | −0.224511719 | 1 |

完整[16通道表](stage144_energy_ml/source_charge_summary.tsv)保留全部噪声/低信号路。不能将修正后hit MeV、模拟pC、截断后raw或calibrated E_EM混成守恒能量。fit charge仅为工具审计输出，未作为Scint模型特征。status1的非零模拟或负raw均不是可用timing，也不改成“测得零”。

50/6/0的原selected Calo status精确；frame2没有原selected参考，明确缺失而保留。**原Calo逐路raw charge未保留，未测量与原selected raw的相等性**；本轮实际digitizer的ADC与独立模拟闭合，不冒充与原已删除ADC逐值比较。frame50完整RNG初末状态精确重复，为原上下文/噪声流提供额外控制。四父没有能量预测或新的物理风险指标。

## 执行、计时和存储

```bash
python3 ml/stage144_submit.py preflight
python3 ml/stage144_submit.py preflight_repair
python3 ml/stage144_submit.py preflight_rngmap
python3 ml/stage144_submit.py preflight_idheader
# 成功首父和累计成本通过后
python3 ml/stage144_submit.py pilot
python3 ml/stage144_submit.py audit
python3 ml/stage143_monitor.py --stage 144
```

作业9674268/9674275/9674290/9674303/9674314/9674373，共6starts、3失败、3成功，全部终态。响应4 CPU/12 GB，后三父并行，stdlib audit1 CPU。[唯一scheduler账](stage144_energy_ml/scheduler_accounting.json)共**587 CPU秒、538聚合execute wall秒、0GPU**，低于600预算；audit的scheduler CPU为0秒粒度，实际进程0.002186 CPU秒。四个成功native测量自身CPU为84.305979/83.775733/91.006988/83.957491秒，计时在imports/输入文本读取之后开始，均为嵌套测量不与scheduler相加。成功三父驱动GNU计时合计278.69 CPU秒，wall107.09秒；峰GNU RSS1,898,636 KiB。四次native实际ROOT读取分别2,999,452/2,999,456/4,013,091/3,668,291 B。未测GPU加速；没有GPU实现或训练任务。

AST/shell语法、报告链接、`git diff --check`以及全部实际ADC/RNG/status/来源界验证通过。确认本阶段队列为空后，四份事件控制gzip原632,278 B精确合并为ignored `ntuples/energy_ml_stage144/event_records.json.gz`，631,182 B；这是减少分散文件，压缩收益很小，不虚报存储提升。原相对路径→JSON文本回读一致，保存53,746 B源码版本胶囊，删除53,358,725 B结束作业的重复输入/结果运输包。[恢复说明及尺寸](stage144_energy_ml/storage_cleanup.json)可用于恢复，不再重跑旧native控制。未提交ADC/HITS数据、未改Stage54或其他项目。

## 阶段结论和下一步

本阶段补上四父实际Ecal DAQ的方法闭合，实测并纠正积分窗口/全几何PMT随机流语义。没有完成一般混合Ecal、高幅PMT非线性、μ辐射尾/真实data迁移或ν能量增量。Stage137几何分解仍有局部增量而双箱5%扩大门未过，不因方法闭合自动大生产或追加旧X网络/代理网格。

下一Stage145用既有data8006及MC100012的固定前4096条，各做64条小测试后，执行两种事前固定的raw联合评分；在独立entry分段检查总体与overflow/high-activity、pz50–100 GeV侧的报警比例和测量覆盖。只用重建point状态时，真实track covariance缺口必须明示；data报警比例不是误报率，PG文件名和次级truth列表不能代替原始根认证。原1.05/1.01/1.03及八层三尾+2 pp、Stage87、全部角色/K和整体goal未完成状态保持。
