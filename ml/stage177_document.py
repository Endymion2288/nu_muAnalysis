"""Measured training and physics tables into the Chinese stage report."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage177_energy_ml'
def read(name):return json.loads((OUT/name).read_text())
p=ROOT/'workbook/2026-11-08_stage177_timing-mean-energy-content.md';s=p.read_text().split('## 待回收结果及验收')[0]
pairs=list(csv.DictReader((OUT/'slab_paired.tsv').open(),delimiter='\t'));gates=list(csv.DictReader((OUT/'slab_gates.tsv').open(),delimiter='\t'));audit=read('independent_validation.json');store=read('storage_cleanup.json');sentinel=read('control_sentinel_validation.json')
s+='''## 新训练实测与物理结论

V/T分别从头训练各3seed，共加6fit，与X合计9fit/3600轮。训练数和cal数原样保持，保存后重载预测精确；完整全样本和原八层/三尾均已评估，没有挑Good Hit子集或剔除缺时父。全部原配对数字见[配对表](stage177_energy_ml/slab_paired.tsv)。以下比值为log-RMSE，无量纲，越小越好；区间为原条件incoming分组95%区间。

| role | 能量箱 GeV | 对照 | 比值 | 条件95%区间 |
|---|---|---|---:|---|
'''
for r in pairs:
 if r['role'] not in ['2','3'] or r['stratum'] not in ['E50_100','E100_200'] or r['candidate']!='T' or r['reference'] not in ['V','X','traditional']:continue
 s+=f"| {r['role']} | {'50–100' if r['stratum']=='E50_100' else '100–200'} | T/{r['reference']} | {float(r['RMSE_ratio']):.6f} | [{float(r['low95']):.6f},{float(r['high95']):.6f}] |\n"
s+='''
**新增两片均时没有在这一次固定表示中兑现有统计支持的双低能改善。** 开发test的T/V分别0.997941、0.997533，两个95%区间均包含1；T/X最低箱1.002528、第二箱0.996298。最低箱仍明显差于传统（T/traditional=1.945326，95%[1.653993,2.264715]）；第二箱点估计0.989835，但上95%=1.063122，仍未过1.05非劣效门，不能据点估计声称胜出。

| test T层 | RMSE上95% | 原门 | RMSE通过 | 三尾同时通过 |
|---|---:|---:|---|---|
'''
for r in gates:
 if r['role']=='3' and r['arm']=='T':s+=f"| {r['stratum']} | {float(r['RMSE_upper95']):.6f} | {r['limit']} | {r['RMSE_pass']} | {r['tail_pass']} |\n"
s+='''
原[门表](stage177_energy_ml/slab_gates.tsv)的cal/test X、V、T joint均false；Stage87冠军不替换。test中T最低箱相对X正tail50点差+0.546448pp、第二箱负tail50点差+0.235018pp，仍按原95%上界而非仅点差验收。其他六层RMSE保护和八层三尾对本T均通过，但不能补偿两低箱主门失败。

这一区间只覆盖原已开发输入上的incoming统计、固定模型及校准；没有认证独立生成族、重训不确定度、真实条件/控制校准系统误差。真实μ校准的大尾/跨期误差未被本结果解决。结论限于这两片均时的固定X/V/T表示，不推广为所有时间/波形均无信息，也不因阴性调整门、再扫窗口或增加模型容量。

## 输入占位值的实际独立核对

[附加审计合同](stage177_energy_ml/sentinel_audit_addendum.json)在原audit600CPU秒内，只实际重读Stage174同三源各4096例，验证非物理χ²与精确-999位置是否混入μ控制；没有改拟合输入或扫新样本。单独的χ²上cut可能容许负χ²，因此先作实际检查，若有污染必须停止解释并另冻校准修正，不能静默删尾。

'''
for r in sentinel['actual_sources']:
 s+=f"- {r['label']}：{r['original_N']}输入/{r['original_control_N']}原控制，负χ²{r['negative_Chi2_N']}、非有限χ²{r['nonfinite_Chi2_N']}、Trig x/y精确-999 {r['position_minus999_N']}，原控制中非物理值{r['invalid_original_controls_N']}例。\n"
s+='''
此次控制不受该实现缺口影响，原校准系数/实际控制/物理结果不变。后续入口补上有限非负χ²和明确位置占位排除；没有把合法负rawQ或有符号坐标中的-1当缺失。原audited62对非负χ²、pz0正域、计数、charge sign、producer 999999位置及合法signed raw的typedNaN规则保持。

## 独立验证与计算/存储

'''
s+=f"[独立验证](stage177_energy_ml/independent_validation.json)实际重载{audit['reloaded_actual_models']}个模型，在全部active独立重建ensemble和cal-offset，全部精确；cal/test×8层×3臂的{len(audit['scalar_checks'])}组RMSE/正负总tail50中心指标逐项标量核对，最大差{audit['max_scalar_difference']:.3g}。隔离/reserved预测均0。\n\n"
s+=f"调度{store['starts']}start全部exit0、0live，累计{store['scheduler_CPU_s']}CPU秒、{store['scheduler_aggregate_wall_s']}聚合execute wall秒；实际RequestCpus={store['scheduler_RequestCpus']}、RequestMemory={store['scheduler_RequestMemory_MB']}MB，在原2400CPU秒内。GNU成本如下（子步骤不再与调度CPU相加）：\n\n"
s+='| GNU任务 | CPU秒 | wall秒 | maxRSS KiB |\n|---|---:|---:|---:|\n'
for r in read('process_resources.json'):s+=f"| {r['phase']} | {r['CPU_s']} | {r['wall_s']} | {r['RSS_KiB']} |\n"
s+=f"\n[存储账](stage177_energy_ml/storage_cleanup.json)保存9模型和预测于`ml/artifacts/stage177/`，合计{store['retained_model_prediction_bytes']}B；来源{store['source_logical_N']}逻辑版本/{store['source_unique_N']}独立内容原字节归档重读，删{store['deleted_bytes']}B重复运输/日志/提交文件。仅在本stage队列Iwd无引用后清理`~/condor/nu_muAnalysis/stage177/`，Stage54原12项大小/mtime保持。原事件ROOT不改，无新G4/新独立ν/GPU或role改变。\n\n"
s+='''
收尾命令：

```bash
python3 ml/stage177_ops.py collect --phase full
python3 ml/stage177_ops.py submit --phase audit
python3 ml/stage177_ops.py collect --phase audit
python3 ml/stage177_finalize.py
python3 ml/stage177_document.py
python3 ml/stage177_validate_docs.py
git diff --check
```

## 下一步与分支边界

这一次新Timing均时表示已完成训练和原完整评估，按未达标结束，不扩同族窗口/模型网格。Stage176继续实际S0过面/出生位置小pilot，先闭合和成本后才原其余11父；若面前/后源分解在同窗响应有明确机制支持，再寻找可测伴随量，不能直接部署真位置或重复计入已测μ能量。匹配实际DAQ的同窗actual/noiseless/no-clip响应仍是新问题，不以本均时阴性替代它。

只有真实新高幅参考/新支持到来才考虑hybridQ或Q+T；普通Ecal双量程不能移植到原单路MC。弱信号上游backscatter须真实status0/采集范围/校准支持；实际背景、效率、全生成加权及相关辅助约束缺口继续，外部乳胶/独立确认仍需实际输入。整体目标未完成，最低能优于传统及物理精度仍未实现。
'''
p.write_text(s)
