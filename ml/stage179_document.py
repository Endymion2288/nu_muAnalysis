"""Chinese report renderer, reads only worker-produced aggregate tables."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage179_energy_ml'
s=json.loads((OUT/'physical_summary.json').read_text());c=json.loads((OUT/'storage_cleanup.json').read_text());a=json.loads((OUT/'admission.json').read_text())
parents=list(csv.DictReader((OUT/'parent_diagnostics.tsv').open(),delimiter='\t'))
resources=json.loads((OUT/'process_resources.json').read_text());full=next(r for r in resources if r['phase']=='full_time')
text='''# Stage179：同父同窗实际读出、无噪声/无截断与S0源响应

## 阶段目标与冻结输入

落实用户Stage172匹配读出干预方案，回答原固定12自然父的电荷读出误差由什么造成，及同窗响应中有哪些S0前后来源。[协议](stage179_energy_ml/protocol.json)沿Stage178原50/70/6/21/8/63/2/15/0/1/5/12，不按clip、风险或是否重选换父。仅注入已有persistent HITS，pinned d32/FASERNU04/tag06/原private seeds，实际11闪烁体特征和普通Ecal4对应；官方digitizer同时输出的其他有cable几何通道保留于控制分母，不冒充新能量特征。保留全部8 Ecal几何PMT噪声抽样，再取4有cable通道；无新G4/重建/独立ν/能量fit或forward。

原scint实际780–980ns、Ecal780–930ns，2ns采样并含端点，逐波形向官方重建接口取原窗验证；不扫描窗口、不换fit charge、非0status不赋物理到达时间。无ADC的空集合与合法signed负raw分开。原Calo raw未保存，不伪造它的历史参考。

在同一实际窗定义：原official signed raw；加入相同噪声并保留原估计pedestal但取消clip的受控量；已知模拟pedestal下、无噪声/量化/clip的analog量。逐项分解signal、float幅度表示、实际噪声抽样、float相减/ADC round、clip和pedestal估计误差，保留raw float存储差。无clip量**没有重新拟合基线**，不等于完整假想重建结果；ideal analog为模拟干预真量，不是部署可读出的准确电荷。

源类别为直接主μ、S0前出生后代、S0后出生后代、其他根、未知根及未知S0；先按实际hit时间传播、卷积和同窗积分，再加一次共同噪声/量化/clip。不存在把已数字化ADC或分来源fit charge直接相加。8/63/2无本次拟合面继续未知，尤其lowpz_highE两父的前后机制仍缺。

## 工程失败与数值定义修正

首次9676909 exit1，79scheduler CPU秒/112wall秒：空VetoNuHits的observer标签键不写出，程序直接索引导致KeyError。不是物理或支持门失败；修正为在实际hit数为0时使用空标签，并检查timing/hit/标签基数。[修正记录](stage179_energy_ml/repair_record.json)与software/stage179/preflight_failure.tar.gz保留原字节，原preflight1000剩921CPU秒支出repair，不增加预算或重跑G4。

另在回收full前按源码发现原Python counterfactual将baseline−amplitude提升double，而C++先以float相减再round，个别半ADC边界会误归1code到clip。Stage141Analog实际ADC、RNG、原raw和source signal始终正确；独立audit用保留样本显式float32相减重建无clip与round/clip三项，原逐父TSV及返回包不改。最终科学表以[charge_interventions.tsv](stage179_energy_ml/charge_interventions.tsv)为准；原表仅作执行审计。[原因与实际改动](stage179_energy_ml/counterfactual_arithmetic_correction.json)和[事前记录](stage179_energy_ml/counterfactual_implementation_note.json)区分实现修正与物理干预，没有改阈值、窗口、输入或任何能量指标。

## 实测同窗电荷误差与来源

'''
text+=f"实际{s['parents_N']}父/{s['original_selected_N']}原重选父，{s['ADC_samples']}个ADC采样逐值精确、{s['channels_N']}个带实际ADC的通道记录、signed负raw{s['negative_signed_raw_N']}条。ADC等于0共{s['clipped_samples']}采样；这只是触底计数，真正clip电荷损失另由同噪声无clip差确定。float相减修正涉及{s['counterfactual_corrected_channels_N']}个通道，完整清单不隐去。\n\n"
text+='''下表单位均pC，绝对差为本固定控制集逐通道绝对差之和，非总体MAE、方差、独立N或已校准不确定度。类别内同父通道相关、原六层取样比例不代表总体；不以此给能量风险置信区间。

| detector | 通道记录 | status0 | Σabs(raw−ideal) | Σabs(no-clip−ideal) | Σabs(noise+pedestal) | Σabs(clip) | Σ同窗analog |
|---|---:|---:|---:|---:|---:|---:|---:|
'''
for r in s['summary']:
    text+=f"|{r['detector']}|{r['channels_N']}|{r['status0_N']}|{r['sum_abs_raw_minus_ideal_pC']:.9g}|{r['sum_abs_unclipped_minus_ideal_pC']:.9g}|{r['sum_abs_noise_plus_pedestal_pC']:.9g}|{r['sum_abs_clipping_pC']:.9g}|{r['sum_signal_pC']:.9g}|\n"
text+='''
[response_summary.tsv](stage179_energy_ml/response_summary.tsv)同时保留各S0源同窗电荷、零信号/负raw/非0status与实际完整分母；所有原逐通道和分来源数值在最终科学表，不用SD全时MeV代替charge。本固定12父的Veto有26/48通道存在非零截断损失；Σabs(clip)=354493.432617pC，而取消clip后Σabs(raw−ideal)降至9.416048pC。普通Ecal则48条均无非零clip损失，原误差8.842335pC与噪声加基线项8.783342pC接近。因而该控制支持“Veto数字截断确实严重、普通Ecal此处的误差主要来自噪声/基线”这一分探测器机制判断，不能把Veto干预收益套到Calo或推广为总体比例。

同窗普通Ecal的S0前/后来源合计0.0251198714/0.823696626pC，未知S0仍0.304313038pC；Trigger分别423.103174/0pC，Preshower43.9557998/89.0555715pC。这里按源**出生位置**分类，不是穿越S0的完整能量流，不能将这些charge作为μ损失或Eν修正加回。噪声/基线与clip对不同detector的贡献不同，单一“修电荷就能修能量”的推论不成立。该控制没有给出可部署修复器、误差覆盖、data迁移或独立高幅真值。

## 固定旧预测逐父诊断

仅按原frame读Stage131已存direct_cal/traditional预测，不重新推理/拟合或选择误差父；以下为原重选train上的相对误差Ehat/Etrue−1，无独立泛化含义，未选父明确未知。

| 原frame | 真Eν (GeV) | pz0 (GeV) | direct相对误差 | 传统相对误差 | 原重选参考 |
|---|---:|---:|---:|---:|---|
'''
for r in parents:
    show=lambda k:r[k] if r[k] else '未测量/无原重选参考'
    text+=f"|{r['index']}|{show('truth_E_GeV')}|{show('pz0_GeV')}|{show('direct_cal_relative_error')}|{show('traditional_relative_error')}|{r['original_selected_reference_available']}|\n"
text+='''
最低两父的响应与误差只是该固定条件支持，不推断总体相关或因果；lowpz_highE两父没有原重选参考/面，不能补造该困难侧错误机制。既有Stage129/177能量阴性结果不被这些train诊断推翻。

## 验证、成本与存储

'''
text+=f"修正首父9600实际ADC/raw11/status/Calo status及完整private RNG初末精确，原无Calo raw参考明确。完整preflight GNU{a['complete_preflight_CPU_s']:.2f}CPU秒、三倍×11为{a['threefold_remaining11_CPU_s']:.2f}≤6000，连已用与1000audit≤8000，才full。原协议/门保持。\n\n"
text+='''[独立标量审计](stage179_energy_ml/independent_validation.json)从保留actual samples按C++ float运算重建每个ADC、signed窗raw、六源analog积分、所有代数分项和原status；source相加沿原32float32eps界。新的全量读出不冒称新独立ν或全data校准；原3个无重选参考不按失败删掉。

'''
text+=f"[调度](stage179_energy_ml/scheduler_accounting.json)共{c['starts']}start（含1失败），全终态/0live，{c['scheduler_CPU_s']:.0f}CPU秒/{c['scheduler_aggregate_wall_s']:.0f}聚合execute wall秒；申请/实际4核12000MB，3父进程并行、BLAS1。full GNU{full['CPU_s']:.2f}CPU秒/{full['wall_s']:.2f}wall秒/RSS{full['RSS_KiB']}KiB，未测受控加速比；无GPU训练。嵌套资源见[子进程表](stage179_energy_ml/process_resources.json)，不与scheduler重复相加。\n\n"
text+=f"[存储审计](stage179_energy_ml/storage_cleanup.json)留{c['retained_response_B']}B紧凑response，删{c['deleted_bytes']}B重复运输/日志/spool；核队列Iwd后清理。源版本/所有成功及失败原日志/GNU/终态spool精确归档software/stage179；失败返回包另存failed_worker_result，Stage54的12原资产保持。无ROOT/xAOD中间文件、无全量ν生产。\n\n"
text+='''```bash
python3 ml/stage179_freeze.py
python3 ml/stage179_ops.py submit --phase preflight
python3 ml/stage179_ops.py collect --phase preflight
python3 ml/stage179_ops.py submit --phase preflight_repair
python3 ml/stage179_ops.py collect --phase preflight_repair
python3 ml/stage179_admit.py
python3 ml/stage179_ops.py submit --phase full
python3 ml/stage179_ops.py collect --phase full
python3 ml/stage179_ops.py submit --phase audit
python3 ml/stage179_ops.py collect --phase audit
python3 ml/stage179_finalize.py
python3 ml/stage179_document.py
python3 ml/stage179_validate_docs.py
```

## 阶段结论与下一步

同窗原actual ADC、无噪声/无clip模拟统计量和S0来源分解已取得；这是物理机制与响应误差的有界控制，不是低能精度改善。后续只有实际可测伴随量/新校准和匹配支持成立，才另冻一次有功效的内容/状态能量实验；不在9个train上伪造验证、不自动扩大4032、不重复Stage129同族模型。

普通Ecal双量程Stage180已测真实支持与幅度依赖，Stage181正核strict双端时间与异常比例关系，之后需区分同pulse/窗口与真实响应。相关噪声/信号保真/电荷误差覆盖、高幅独立参考、上游backscatter真实覆盖、S0困难侧、背景效率/加权生成与相关辅助约束、乳胶及最终独立确认仍开放。Stage87/原所有低能与保护层/八层三尾门/全部K/角色/reserved关闭保持，整体目标未完成。
'''
(ROOT/'workbook/2026-11-08_stage179_matched-window-readout-and-S0-sources.md').write_text(text)
print('Rendered Stage179 Chinese report from verified worker summaries')
