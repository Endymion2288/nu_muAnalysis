# stage36：正半波积分、标度、几何与生产来源审计

本阶段只读匹配源commit `1ec47efe`，不是当前Calypso工作树的实现；未修改/重编译Calypso。
完整生产片段见[production_audit.json](production_audit.json)。37个有界日志reference全部找到，
它们不能证明所有实际bck文件的maker、完整conditions/HV或生成谱系一致。

## 1. 从波形到约8 GeV EM的非零噪声尺度

`Waveform/WaveRecTools/src/WaveformReconstructionTool.cxx:395–425`的fillRawHitValues：
每2ns采样，`baseline_mean - mv_per_bit * adc`为mV，窗口含两个端点。
对应头文件的FitWindowWidth=75，通常得到76采样；实际每例窗口是否截断尚未逐波形测量。
同源`:706–735`的findRawHitValues明确跳过`wave[i] <= 0`，然后`raw.integral = 2*tot`。
`:119`在peak小于5倍baseline rms时标threshold failed并保留raw hit，不是丢弃容器。

NtupleDumper `FillWaveBranches:244`保存`charge=integral/50`、`raw_charge=raw_integral/50`，单位pC。
因此即使真实信号为零，零均值高斯噪声的正半波积分期望也是

\[
q_{noise}=\frac{2\,76\,\sigma_{baseline}}{50\sqrt{2\pi}}\ {\rm pC}.
\]

该公式在协议冻结前由源码提出，76未从正式样本调参。用于解释**量级**，
不是单例信号扣除或严格噪声模型；baseline拟合、时间相关、量化、窗口选择和残余信号尚未分离。
相关噪声不改变固定边际分布的期望，但会改变分布宽度；实际边际分布也未完整测量。
四通道总量按上述q_noise、各模块全样本有限`charge/nMIP`中位值和0.330 GeV/MIP换算。
这是读取生产有效尺度后的诊断，不是原始DB payload或独立绝对标定。

MC四模块都阈值失败的231519例占88.2865%；实测总量中位8.26571 GeV EM，
噪声期望中位7.93610 GeV EM，事件逐个总量/预期之中位1.04178 [1.04106,1.04246]。
data对应12170例，0.287250/0.276203 GeV EM，比例1.04523 [1.03424,1.05126]。
区间均不包含1，不能声称精确纯高斯闭合；但足以证明约8GeV窄响应有主要的整流噪声pedestal贡献，
不是凭非零读出认定穿越μ沉积或shower峰。MC μ控制并非原CC事件的逐例噪声扣除，
也未据此分解stage35 BDT的3.34%信息收益。

## 2. 能量与有效增益

`Calorimeter/CaloRecTools/src/CaloRecTool.cxx:265–310`：
`nMIP = charge * gainRatio / MIPcharge_ref`，data有HV外推，MC不做该外推。
头文件定义E_dep=58.5 MeV/MIP、E_EM=330 MeV/MIP。
`charge/nMIP`因此是**有效参考电荷MIP_ref/gainRatio**；不能把data该比值直接当DB原始payload。
MC为0.0757 pC/MIP，data模块0–3为1.892/1.847/1.902/1.986 pC/MIP，相差约24.4–26.2倍。
raw电荷和baseline rms却在相近量级，说明直接比较EM-scale峰是不充分的。
这不证明某个25倍错误，未作统一乘法修正或重新训练。

NtupleDumper约1290行：模块E_EM是fit值，total_fit是其和；total_raw将每模块fit乘raw/fit比，
total在overflow bit4时用fit，否则用raw换算。因此即使raw电荷有限，fit非有限仍可能污染total；
不能据raw有限宣称派生total一定有限，也不能拿各模块中位数的和等同total中位数。
stage35有限单位代数核验仍适用，本阶段没有重测独立绝对能量标定。

两符号代表RDO/rec日志解析到WAVE-Digitization-03-LG、WAVE-Calibration-03-LG；
CaloNu digitization核参数Norm=.55、Mean=820ns、Sigma=3.67ns、Alpha=−.32、N=1000。
同源CaloNu使用CaloDigiConditionsTool的Detector="Calo"。实际HITS沉积、原生波形signed积分、
逐通道kernel/gain和时窗闭合尚未测量，不能唯一归因于增益、噪声、时序或几何。

## 3. 名义位置不能替代通道/硬件映射

[geometry_audit.json](geometry_audit.json)只读CVMFS geometry SQLite文件并解析固定GDML：
FASERNU-CALONU(107964)→Calorimeter-CALONU(107963)→CaloNu-00(107960)，
top-level(107962)位置[10,−21,−2505.68]mm、旋转0；GDML box再偏−100mm，
box中心[10,−21,−2605.68]mm。core半尺寸[60.6,60.6,216]mm，RxRy各+.05rad。
四个名义中心见JSON；这些是**模型名义值**，不是实测安装/对齐坐标。

保存VetoNu z=−3112mm处的轨迹位置/角度作直线，求交并用前后面10mm内缩定义interior；
±tilt控制不是原生GeoModel方向认证。MC/data nominal interior121557/97577例，
两tilt均成立104679/83447；改变tilt影响41565/34370个模块interior判断。
约433mm交长是core包络代理，不是有效闪烁体长度或MIP能量标尺。

冻结计算曾把几何region序号直接与分支序号对应；这是**未验证的假设**。
由此得到的paired interior−off负值仅作为该假设的原始结果保留，不能解释成穿越信号反向或物理抑制。
事后4×4位置关联的raw电荷峰指向MC[1,0,3,2]、data[3,2,1,0]候选排列，
见[module_association_posthoc.tsv](module_association_posthoc.tsv)。这是描述性证据，
不是硬件映射认证；本阶段没有按此重排、修改选择或重算“匹配MIP峰”。
主噪声结论按status/四通道总量成立，不依赖这一未证排列。

## 4. 拟合质量位的覆盖缺口

status值1=threshold failed，4=overflow，16/32=Gaussian/CB fit failed；128/256分别missing/invalid。
MC 1048944个模块观测有21个非有限E_EM，21个均无fit failure位且raw有限；
data 993292个有117个非有限，114个无failure位，117个raw均有限。
有限|E_EM|>1000GeV的35/102例只有3/2例带failure位；大有限值不自动等同技术错误，
可能包含辐射损失/真实高响应，未作删值、截尾或异常标签训练。

固定源的fitCBall约863–889行先设`cbfit.valid=(fit_status==0)`；
若time为NaN，仅把time退回gfit并写`cbfit.fit_status=false`，没有将valid清false。
这是可审查的有效性/状态不一致路径。reconstructHit失败回退也须逐例审查；
仅凭源码不能断言21/117个非有限都由这一分支导致。原生失败case replay尚未测量。

## 5. 数据时期与生产证据边界

MC使用Calypso22.0.49、CaloNuMC/1ec47efe、OFLCOND-FASER-05、FASERNU-CALONU。
μ−六个reference均显式backward；**μ+的0020/0040/0059 ntp reference没有--backward**，
而0000/0079/0099有。实际输入全部来自bck/s0015；reference不能认证那三份bck maker配置。
协议只在冻结前看过首文件日志，当时“首日志backward”仍属实；正式全部审计在冻结后发现该缺口，
没有修改协议或悄悄排除这些文件。符号分层和全部文件中位数保留，完整生成谱系独立性未证。

data六个ntp reference均backward，v8 producer GRL；离线选择用官方v10子集。
三个代表rec日志是reco/r0022/d0b1b2dd、TI12Data04/noIFT，
与MC的几何/材料、实际通道和HV/时序尚不等同。相同global tag字符串不能替代IOV/payload匹配。

事后[file_total_response_posthoc.tsv](file_total_response_posthoc.tsv)发现run15838首/中文件
总量中位4.76952/0.610798 GeV EM，事件时间1720449636–1720450117 /
1720473060–1720473375 Unix s。四模块有效q/MIP基本不变，baseline rms约.32–.33mV，
但raw中位从.571–.687降到.469–.493pC，四通道阈值失败比例由2.7134%变5.7694%。
因此**简单用有效MIP系数变动解释该文件差异不受数据支持**；触发、事件活动、
时序/响应条件等贡献未分离，不能把差异全部归某个硬件故障。
run16000/16923两个文件各约.652–.656GeV EM，不能选择性忽略15838。
data层级bootstrap保留run/file差异，不能以逐事件bootstrap缩窄系统性变化。

物理data/MC闭合、MIP绝对标定、强子标定、HITS→waveform因果分解、真实谱收益：**未测量**。
