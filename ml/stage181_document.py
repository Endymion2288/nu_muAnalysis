"""Render validated aggregate timing tables, with no event-array access."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage181_energy_ml'
s=json.loads((OUT/'full_summary.json').read_text());c=json.loads((OUT/'storage_cleanup.json').read_text());a=json.loads((OUT/'admission.json').read_text())
rows=list(csv.DictReader((OUT/'full_diagnostics.tsv').open(),delimiter='\t'))
text="""# Stage181：普通Ecal双量程时间一致性与幅度响应

## 目标、输入和事前定义

承接Stage180实测，检查低幅大电荷比是否与存储时间不一致关联，以及高幅趋势是否仍在时间一致者中存在。[协议](stage181_energy_ml/protocol.json)固定同run15838的780874条PHYS、原Lo0–3/Hi16–19物理对应、原Q尺度、even拟合/odd验证及幅度箱。输入为 `/eos/experiment/faser/data0/phys/2024_back/r0022/015838/Faser-Physics-015838-00000-00049-r0022-PHYS.root`。

原charge重叠仍要求两端status0、有限正raw Q、RMS>0及peak/RMS≥10，其他全留分母。时间只用两端status0、有限正localtime、有限且不为−999的bcidtime；无fallback/额外phase校正，不对坏hit赋时间。local与bcid分别分析，不宣称跨板时基已校准。每模块/时间定义恰一个even-only median(Hi−Lo)；Q比例完全复用Stage180，**不重新标Q、不扫描时间窗**。

固定abs(时间残差)≤2ns只描述关联，并非校准分辨率门、pulse身份/μ纯度认证或新的能量cut。保留不一致事件，不挑选新的data或模型。历史raw是正sample整流积分，不能当当前signed积分。

## 实测支持、时间offset与留出残差

全部原charge重叠均有严格时间，无新增缺时：四模块5802/7489/4989/5850，even/odd分别2839/2963、3751/3738、2464/2525、2908/2942；780874总分母不变。

| 模块 | even local offset (ns) | even bcid offset (ns) | odd bcid abs95残差 (ns) |
|---|---:|---:|---:|
"""
for module in range(4):
 local=next(r for r in s['offsets'] if r['module']==module and r['definition']=='local')
 bcid=next(r for r in s['offsets'] if r['module']==module and r['definition']=='bcid')
 text+=f"|{module}|{local['offset_ns']:.10f}|{bcid['offset_ns']:.10f}|{bcid['heldout_abs95_ns']:.10f}|\n"
text+="""
## 电荷异常与时间的关联

以下均odd验证、bcid定义，电荷残差为QHi/(Stage180固定比例×QLo)−1，无量纲。低幅Lo peak 0–50mV：

| 模块 | 全部N | ±2ns内N | 外N | 全部Q残差中位 | 外组时间残差中位 (ns) |
|---|---:|---:|---:|---:|---:|
"""
for module in range(4):
 subset={r['group']:r for r in rows if int(r['module'])==module and r['definition']=='bcid' and float(r['Lo_peak_lower_mV'])==0}
 all_,inside,outside=(subset[x] for x in ['all','within2ns','outside2ns'])
 text+=f"|{module}|{all_['N']}|{inside['N']}|{outside['N']}|{float(all_['median_charge_ratio_residual']):.8f}|{float(outside['median_time_residual_ns']):.8f}|\n"
text+="""
四模块低幅异常多数位于固定时间带外，外组中位约−6ns，支持**电荷大正尾与时间不一致关联**。但带内低幅仍存在大Q尾，且同一脉冲也可能受timewalk/fit/积分窗口影响；不能由这个关联证明不同pulse、或认为时间cut已完全修复电荷。

高幅Lo500–1000mV、±2ns内的电荷残差：

| 模块 | 带内N | Q残差中位 |
|---|---:|---:|
"""
for r in rows:
 if r['definition']=='bcid' and float(r['Lo_peak_lower_mV'])==500 and r['group']=='within2ns':
  text+=f"|{r['module']}|{r['N']}|{float(r['median_charge_ratio_residual']):.10f}|\n"
text+="""
−8%至−14%量级高幅趋势在固定时间带内仍在，故简单地去掉时间不一致者不足以恢复常比例。实际PMT非线性、两路时基/fit、整流窗口、幅度与选择混合各贡献仍**未测量**；本阶段不做幅度依赖标定，不将Lo或Hi当绝对真值。[完整分箱](stage181_energy_ml/full_diagnostics.tsv)保留local/bcid、全/内/外和全部原幅度箱。

## 独立验证、资源与存储

[独立审计](stage181_energy_ml/independent_validation.json)再次读取完整780874条并精确重现诊断表，Python statistics独立重算8个even时间中位数；原128native raw/peak/RMS/status标量和4个实际status0 native localtime精确，原8192前缀复现。4个时间标量是native控制本身的有限支持，不冒称32个或全事件原生波形认证。

"""
text+=f"pilot完整GNU{a['measured_complete_pilot_CPU_s']:.2f}CPU秒，两块读取{a['measured_two_chunk_CPU_s']:.9f}CPU秒，三倍full预测{a['threefold_full_CPU_s']:.6f}≤600，已用+预测+150audit≤900才准入。3job/3start全exit0、0live，scheduler {c['scheduler_CPU_s']:.0f}CPU/{c['scheduler_aggregate_wall_s']:.0f}聚合wall秒。提交4核8000MB，CERN实际4核12000MB；无GPU训练/能量fit/forward/G4/重建或新独立ν。full内部{s['CPU_s']:.9f}CPU/{s['wall_s']:.9f}wall秒、RSS{s['RSS_KiB']}KiB，ROOT实际请求{s['ROOT_read_bytes']}B，嵌套GNU不重复累加。\n\n"
text+=f"[归档](stage181_energy_ml/storage_cleanup.json)保留{c['retained_event_B']}B原8192前缀缓存，删除{c['deleted_bytes']}B重复运输/日志/spool；源/成功审计/计时精确保存software/stage181，清理前核队列引用，Stage54原12资产保持。没有保存full ROOT或全文件事件数组。\n\n"
text+="""```bash
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
"""
(ROOT/'workbook/2026-11-08_stage181_dual-range-time-association.md').write_text(text)
print('Rendered Stage181 from verified aggregates')
