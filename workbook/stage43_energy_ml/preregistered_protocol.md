# stage43：ν结果读取前冻结

冻结时间、起始提交和精确参数见 `ml/configs/calonu_data_noise.json`；此前只读
stage42已有结果和16000/RAW0的2例解码/schema pilot（包含在正式504例中）。
没有stage43 ν拟合或预测。主问题：真实离峰噪声与有限pedestal下，CaloNu约2%的
开发MC风险收益是否保留？本实验不声称完成data强子增益或原生生产闭合。

## 输入和预算

- 复用stage42 B的3703例/21来源/三折、F6全部65项、原选择/PMT veto/truth fiducial
  及lead区/unit MC/highest-pz；重点reco pμ=100–1000 GeV，两个子层；不截Eν。
- 独立噪声：15838/16000/16923各RAW文件0、1、400的前56个PhysicsTag事件，
  共504例/9文件，精确路径见raw_manifest.json。inclusive trigger，不施加CaloNu、track
  或GRL选择；因此这是data电子学离峰控制，不冒充全部是μ控制或物理fiducial样本。
- 每通道280个2 ns ADC，模块顺序按已审计CableMapping：15838为20/21/22/23，
  其余为6/7/14/15，对应MC敏感ID9/1/11/3。量程2V，mV/ADC=2/16.384。
- 原生xAOD窗口pilot为112–262 ns；pedestal固定ADC[0:40]即0–78 ns，
  联合离峰块固定[180:256]即360–510 ns（76点）。不围绕ν标签更换窗口。
  [32:56]即64–110 ns仅作前后平稳性诊断，不作为第二候选或挑选块的标准。
  原始脉冲和ADC/mask不改；异常/尾部原样记录，不按幅度裁噪声。
- 各RAW文件0、1、400分别进入噪声折0、1、2，每折包含三个run；不跨ν折共享
  原始噪声事件。每ν事件使用一个完整4×76块；折内固定种子打乱并循环均匀复用，
  复用不增加独立物理样本。顺序和种子只看cache row/fold，不看ν能量/y/z/HITS时间。
- 信号仍用stage42同步单脉冲MC名义增益；噪声为(前40点ADC均值−离峰ADC)×mV/ADC，
  保留均值漂移、采样和通道相关；不额外把每个离峰块中心化，不假定pedestal已知。
  固定stage42模板，输出4 signed电荷+确定性和；S=0/非零使用完全相同处理。

## 冻结的三候选/9 fits

1. ideal_sum：F6+四模块S及确定性和；隔离stage42 S4与C5输入表示的有限容量差异。
2. data_noise_nominal：F6+MC名义信号与真实联合离峰残差的固定模板电荷4+和。
3. data_noise_half_gain：同一噪声块，信号增益减半。物理含义是因未闭合增益导致的
   因子2 SNR压力；**不是实测data增益或其置信区间**，不乘25、不扫描增益。

I0与旧3ADC白噪声固定模板直接用同事件缓存，不新增fit。三个候选×三折=9；
另最多1个20轮小smoke；400轮/depth3/单线程与stage42一致；来源隔离train、cal、eval。
offset和灵活scalar映射只用独立cal预测；不添加容量、分箱、随机种子或噪声副本。
每fit120s、每job1800s；大规模提取和9 fits走Condor，先smoke，允许切schedd。
最小Athena控制仅在RAW身份/代数无法闭合时触发，≤24例；没有必要则不启动。

## 验收和报告

重点相对I0 log-RMSE改善≥2%，来源组配对500次bootstrap的95%下限>0。
同报mean/median bias、R68、tails，逐p/Eν/y/z/组件/primary独立代理及proper score、六箱谱。
对ideal_sum的比较隔离表示；对旧toy的比较同时改变噪声相关、有限pedestal及噪声幅度，
不能称纯噪声因果量。来源区间条件于本噪声库/训练，不覆盖增益或噪声库有限性的系统误差。
标注原test已开发使用，不重开或称为新确认；独立噪声来源不等于独立ν test。
若异常/缺失导致提取不完整，不删ν事件：记录具体不闭合点并终止该响应外推。
如果离峰块有非平稳/残余脉冲，保留并量化；不在结果后再换窗口追求通过。
按实测结果决定下一条单主线，data强子增益、外部时序、晚shower形状/饱和和最终
含系统的谱收益若未测量就明确写未测量，不把已知同步当data能力。
