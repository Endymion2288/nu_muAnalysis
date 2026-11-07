# Stage141：有限DAQ窗模拟信号到真实ADC的逐样本闭合

## 目标、输入与范围

承接Stage132§5.4及Stage138：在指定原生响应中，把来源监督定义在噪声、取整、ADC截断之前的模拟信号，而非直接相加分来源ADC。先用已有单个自然train父frame50做方法控制，无新G4、ν父、数字化自然样本、模型fit/forward或reserved读取。该父Eν=90.288000701 GeV，原pz0=80.614109375 GeV；下游沉积均来自μ根，只验证方法，不认证一般μ/非μ归属或辐射尾覆盖。

输入为`ntuples/energy_ml_stage138/control_0.json.gz`已有实际ADC、逐PMT校正hit时间、通道条件，及Stage131保存的真实private RNG seed。Stage138已认证初末随机状态和原raw11/status；本轮不再初始化整个Athena或读取EVNT。完整协议见[冻结协议](stage141_energy_ml/protocol.json)。

## 方法及执行

按pinned d32 `WaveformDigitisationTool.cxx`的`generate_scint_timing_waveforms`与`convolve_waveforms`复制计算：2 ns采样、20倍oversampling、10个pre-samples；同TH1时间分箱、严格`ih<NbinsX`端点；每格能量及kernel乘积使用float、累加使用double，再降采样。输入校正时间已包含实际几何TOF和光传播。kernel用原CrystalBall条件参数。按原Identifier顺序从同TRandom3 seed生成float Gaussian baseline，随后原样取整和下限截断。代码为`ml/stage141_analog.hxx`及`ml/stage141_control.py`。

模拟真值电荷只积分780–980 ns含端点101个采样，转换为pC：`2 ns × (2 V/16384 ADC) × 1000 mV/V / 50 Ω`。分别保留无噪声模拟信号、带噪声未取整、取整截断后固定baseline、实际重建baseline得到的signed raw。它们口径不同，不强求模拟真值与带噪声实测raw相等；ADC逐值相等才是方法闭合门。非0 status不提供arrival time，原事件及signed raw均保留。

```bash
python3 ml/stage141_submit.py
```

HTCondor作业9674154.0，1 CPU/4000 MB、单线程BLAS、LCG_109，目录`~/condor/nu_muAnalysis/stage141/`。复制的C++仅在批处理worker的Cling编译，本地只读源码/紧凑结果和运输。

## 实际测量

[ADC闭合结果](stage141_energy_ml/analog_control.json)：**7200个ADC样本，0个差异**。Veto、Trigger、Preshower各4路×600点，原VetoNu无HITS/无ADC，保持原raw0/status1默认，不能当测得零。全部12路ADC均验证，包括未进入原raw11的辅助通道15/24/25；不将这些额外通道自动加入模型。

完整[逐通道电荷表](stage141_energy_ml/analog_charge.tsv)包括所有12路，以下列主要raw11中9个实际有ADC通道，单位均pC：

| 通道 | 无噪声模拟窗电荷 | 取整后固定baseline | 原实际raw | status |
|---|---:|---:|---:|---:|
| Veto ch14 | 164.054527850 | 164.008789063 | 164.121718750 | 0 |
| Veto ch6 | 74.283714462 | 74.321289063 | 74.321289063 | 0 |
| Veto ch7 | 81.670215755 | 81.782226563 | 81.791103516 | 0 |
| Trigger ch8 | 0 | −0.136718750 | −0.060278320 | 1 |
| Trigger ch9 | 0 | 0.268554688 | 0.461381836 | 1 |
| Trigger ch10 | 40.274781092 | 40.009765625 | 39.926420898 | 0 |
| Trigger ch11 | 40.274591062 | 39.980468750 | 39.718105469 | 0 |
| Preshower ch12 | 6.288798837 | 6.113281250 | 6.077280273 | 0 |
| Preshower ch13 | 4.365050798 | 4.296875000 | 4.098129883 | 0 |

本例12路ADC触底采样均0，未验证饱和极限；ch8模拟信号确为0但实测raw为合法负噪声，不是−1/−999占位值，也不能赋予到达时间。实际raw与固定baseline积分差来自重建baseline口径；本轮没有改写原raw。pC是当前MC响应映射，不是未经校准的全探测器能量或Eν−Eμ。

## 成本、验证与结论

[scheduler账](stage141_energy_ml/scheduler_accounting.json)：1job/1start，exit0，无失败，8 CPU秒、42 execute wall秒、0 GPU，低于300 CPU秒冻结预算。程序内部科学/Cling部分6.060897629 CPU秒、33.938169904 wall秒、峰RSS687588 KiB；内部数不重复加到scheduler。GNU完整计时保存在`control_time.txt`。输出仅紧凑JSON/TSV及小运输包；复用已有控制，未增加ROOT/xAOD/HITS。所有新增Python AST、shell语法和`git diff --check`通过后本地提交，Stage54资产和其他项目目录不动。

本阶段认证：在此实际通道/随机流/时间约定下，可以从模拟信号经噪声、取整、截断精确回到原ADC，因此可将下一步来源标签放在模拟信号层。**未测量**：一般多根分解、Ecal官方Birks/非均匀响应来源标签、μ-only辐射尾联合分布、真实data迁移、模型风险收益和全物理精度。单例无触底不能证明有饱和时分来源ADC可线性相加；即使连续kernel线性，每格float舍入也需报告数值闭合误差。

下一步先完成Stage137预定能量/消融对照，并结合其增量与不确定度决定广泛来源标签/μ控制的有限规模。若进入该线，输入必须有可追溯逐hit根谱系与自然μ辐射尾，保留未知来源和原selected分母；小样本先测成本、模拟成分加和误差及真实通道闭合，再冻结自然ν能量与原八层三尾验证。若几何可接受成分未支持继续，不自动扩大G4或旧X网络。Stage140原3000toy继续，真实系统、背景/接受度、乳胶锚点及独立确认缺口保留。整体goal未完成，Stage87direct62、pz0/raw11/status/typedNaN/signed/Calo缺失和原1.05/1.01/1.03及tail+2pp门不变。
