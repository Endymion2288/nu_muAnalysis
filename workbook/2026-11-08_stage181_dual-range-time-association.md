# Stage181：普通Ecal双量程时间一致性与幅度响应

## 目标、输入和事前定义

承接Stage180实测，检查低幅大电荷比是否与存储时间不一致关联，以及高幅趋势是否仍在时间一致者中存在。[协议](stage181_energy_ml/protocol.json)固定同run15838的780874条PHYS、原Lo0–3/Hi16–19物理对应、原Q尺度、even拟合/odd验证及幅度箱。输入为 `/eos/experiment/faser/data0/phys/2024_back/r0022/015838/Faser-Physics-015838-00000-00049-r0022-PHYS.root`。

原charge重叠仍要求两端status0、有限正raw Q、RMS>0及peak/RMS≥10，其他全留分母。时间只用两端status0、有限正localtime、有限且不为−999的bcidtime；无fallback/额外phase校正，不对坏hit赋时间。local与bcid分别分析，不宣称跨板时基已校准。每模块/时间定义恰一个even-only median(Hi−Lo)；Q比例完全复用Stage180，**不重新标Q、不扫描时间窗**。

固定abs(时间残差)≤2ns只描述关联，并非校准分辨率门、pulse身份/μ纯度认证或新的能量cut。保留不一致事件，不挑选新的data或模型。历史raw是正sample整流积分，不能当当前signed积分。

## 实测支持、时间offset与留出残差

全部原charge重叠均有严格时间，无新增缺时：四模块5802/7489/4989/5850，even/odd分别2839/2963、3751/3738、2464/2525、2908/2942；780874总分母不变。

| 模块 | even local offset (ns) | even bcid offset (ns) | odd bcid abs95残差 (ns) |
|---|---:|---:|---:|
|0|3.6673126221|3.6673126221|5.6704121113|
|1|2.5457611084|2.5457611084|6.5792369366|
|2|4.4858169556|4.4876174927|2.4089065552|
|3|3.7016372681|3.7016372681|5.5143470764|

## 电荷异常与时间的关联

以下均odd验证、bcid定义，电荷残差为QHi/(Stage180固定比例×QLo)−1，无量纲。低幅Lo peak 0–50mV：

| 模块 | 全部N | ±2ns内N | 外N | 全部Q残差中位 | 外组时间残差中位 (ns) |
|---|---:|---:|---:|---:|---:|
|0|154|6|148|5.61156071|-5.93783545|
|1|782|21|761|6.14544026|-5.84768677|
|2|57|9|48|3.81338823|-6.04393005|
|3|177|12|165|4.58653227|-5.81194305|

四模块低幅异常多数位于固定时间带外，外组中位约−6ns，支持**电荷大正尾与时间不一致关联**。但带内低幅仍存在大Q尾，且同一脉冲也可能受timewalk/fit/积分窗口影响；不能由这个关联证明不同pulse、或认为时间cut已完全修复电荷。

高幅Lo500–1000mV、±2ns内的电荷残差：

| 模块 | 带内N | Q残差中位 |
|---|---:|---:|
|0|188|-0.0941674142|
|1|178|-0.1362060290|
|2|187|-0.0828986938|
|3|183|-0.0858682832|

−8%至−14%量级高幅趋势在固定时间带内仍在，故简单地去掉时间不一致者不足以恢复常比例。实际PMT非线性、两路时基/fit、整流窗口、幅度与选择混合各贡献仍**未测量**；本阶段不做幅度依赖标定，不将Lo或Hi当绝对真值。[完整分箱](stage181_energy_ml/full_diagnostics.tsv)保留local/bcid、全/内/外和全部原幅度箱。

## 独立验证、资源与存储

[独立审计](stage181_energy_ml/independent_validation.json)再次读取完整780874条并精确重现诊断表，Python statistics独立重算8个even时间中位数；原128native raw/peak/RMS/status标量和4个实际status0 native localtime精确，原8192前缀复现。4个时间标量是native控制本身的有限支持，不冒称32个或全事件原生波形认证。

pilot完整GNU2.18CPU秒，两块读取0.139555144CPU秒，三倍full预测46.029165≤600，已用+预测+150audit≤900才准入。3job/3start全exit0、0live，scheduler 15CPU/60聚合wall秒。提交4核8000MB，CERN实际4核12000MB；无GPU训练/能量fit/forward/G4/重建或新独立ν。full内部5.014971056CPU/15.415496366wall秒、RSS334932KiB，ROOT实际请求105243821B，嵌套GNU不重复累加。

[归档](stage181_energy_ml/storage_cleanup.json)保留1084536B原8192前缀缓存，删除3361790B重复运输/日志/spool；源/成功审计/计时精确保存software/stage181，清理前核队列引用，Stage54原12资产保持。没有保存full ROOT或全文件事件数组。

```bash
python3 ml/stage181_freeze.py
python3 ml/stage181_ops.py submit --phase pilot
python3 ml/stage181_ops.py collect --phase pilot
python3 ml/stage181_admit.py
python3 ml/stage181_ops.py submit --phase full
python3 ml/stage181_ops.py collect --phase full
python3 ml/stage181_ops.py submit --phase audit
python3 ml/stage181_ops.py collect --phase audit
python3 ml/stage181_finalize.py
python3 ml/stage181_document.py
python3 ml/stage181_validate_docs.py
```

## 阶段结论与下一步

常比例双量程的低幅异常有明显时间关联，高幅响应偏差则在固定时间一致带内保留。这个有限问题已回答，**不追加时间/幅度网格，不将±2ns变成能量cut**。双读出联合能量训练仍需实际匹配MC/响应及独立高幅参考，不能由原4有cable MC补造第二读出。能量改善、电荷覆盖与data–MC迁移未测量。

下一有限实验优先检查Stage172尚未回答的上游弱信号严格timing覆盖与实际源支持：复用Stage179原12父的同窗记录及Stage129原μ校准范围，保留所有父/status/缺失。必须区分其他根、上游活动与有实际方向证据的backscatter；无joint支持即结束该固定探索，不外推μ校正或按脉冲重新选父。独立原生方向若缺，明确未测量，不用local坐标猜global方向。

Stage179控制Veto clip大、普通Ecal噪声主导不构成新部署校准。S0困难侧缺面、相关控制/误差覆盖、背景与效率/加权生成账目及真实辅助约束、乳胶和独立确认继续开放。Stage87/原八层三尾/所有原门、K/角色及reserved关闭保持，原低能与完整物理目标未完成。
