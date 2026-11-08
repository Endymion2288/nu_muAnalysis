"""Render only worker-produced summaries, never event arrays."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage178_energy_ml'
s=json.loads((OUT/'physical_summary.json').read_text());f=json.loads((OUT/'feasibility_summary.json').read_text())
a=json.loads((OUT/'admission.json').read_text());c=json.loads((OUT/'storage_cleanup.json').read_text())
resources=json.loads((OUT/'process_resources.json').read_text());r=next(v for v in resources if v['phase']=='replay_time')
rows=list(csv.DictReader((OUT/'parent_support.tsv').open(),delimiter='\t'))
text='''# Stage178：舍入区间约束的S0前后来源与固定自然父G4-only验证

## 目标、输入与方法改变

按用户Stage172物理方案继续研究pz0参考面前后的μ辐射位置。[Stage176](2026-11-08_stage176_S0-birth-and-crossing-pilot.md)原完整重建的11父三倍投影7070.91CPU秒超过7000，保持未准入。本阶段改变成本实现：使用原compact拟合状态的保守舍入区间，省掉重复digitization/reco/ntuple；新预算4500CPU秒、feasibility300/replay3000/audit1200，未追认或提高旧门。

[冻结协议](stage178_energy_ml/protocol.json)仍为原每六层前2个train共12父，50已有native/谱系作为控制，其余固定70/6/21/8/63/2/15/0/1/5/12。EVNT/entry/seed/HITS文件名、FASERNU04/tag06/FTFP_BERT及Stage176只读observer runtime保持，无Calypso或observer重建、新独立ν/能量fit/forward。三独立单线程父链并行、4核12000MB、无短应用timeout、最多1job。

[源码证据](stage178_energy_ml/source_semantics.json)核pinned d32的CreateTrkTrackTool以拟合pos/mom构造CurvilinearParameters；Athena24.0.41构造中心为pos、curvT为momentum.unit，NtupleDumper取first TrackParameters的double xyz/px/py/pz。原导出动量除1000后转float32、位置转float32，清理只保留有效typed值；不读取p0/p1/pz1作为新输入。

每个保存float32用前后邻数中点包络原double。GeV动量边界额外向外包络double除法和×1000换单位；每次减/乘/加向外nextafter。面侧用未归一化p·(r−center)区间，跨0保持unknown，不线性插值过面能量、不用名义z。另构造法向区间核真实native首父。它是语义与数值表示的保守包络，不是恢复出精确原面；per-track材料修正明细仍未保存，不把已有fitter能损重复加回。

## 首父可行性与新成本准入

'''
text+=f"[首父验证](stage178_energy_ml/feasibility_summary.json)实际xyz/动量/法向均在区间内；{f['native_points_checked']}个出生位置/步端点全部有稳健符号，和真实native面逐项一致，1142个面前/203个面后出生、唯一过面步及hit源分区保持。原12中9个有缓存状态，8/63/2原重选失败，没有面，不替换父、不借原选择前旧状态冒充本次拟合面。\n\n"
text+=f"[准入](stage178_energy_ml/admission.json)用实测成功Stage176 sim+HITScheck={a['actual_sim_plus_HITScheck_CPU_s']:.2f}CPU秒与完整feasibility={a['complete_feasibility_CPU_s']:.2f}CPU秒，三倍×11投影{a['threefold_remaining11_CPU_s']:.2f}秒≤3000，并含1200audit后≤4500，才提交。不是从新少量数据估计总体速度保证。\n\n"
text+='''## 实测支持与物理边界

| 原frame | 原层 | 来源 | 真Eν (GeV) | 面支持 | 面前出生数 | 面后出生数 | 未知出生数 | 稳健过面步 |
|---|---|---|---:|---|---:|---:|---:|---:|
'''
for v in rows:
    text+=f"|{v['index']}|{v['sampling_stratum']}|{v['component']}|{float(v['truth_E_GeV']):.6f}|{v['state_supported']}|{v['before_births_N']}|{v['after_births_N']}|{v['unknown_births_N']}|{v['robust_crossings_N']}|\n"
text+=f"\n[完整父支持](stage178_energy_ml/parent_support.tsv)和[源响应](stage178_energy_ml/source_response.tsv)实际{s['births_N']}个出生：面前{s['robust_before_births_N']}、面后{s['robust_after_births_N']}、未知{s['unknown_births_N']}；9个支持父各1个前向稳健过面步，无已支持父的未知端点。所有117行实际SD源响应保留，零或未知不删。\n\n"
text+='''这是有界条件train控制，不是总体发生率或独立ν样本。特别是**lowpz_highE的两个原父都缺本次拟合面**，尚不能对该困难侧完成S0前后能量错误机制结论；不能以其余9父替代这个分母。出生计数多数为电离电子，不能把全次级数叫辐射光子数，出生KE之和也不是主μ能损。逐hit源对应全时corrected SD响应，尚不是实际raw窗电荷、可测radiation伴随量或Eν修正。

## 独立审计、资源与存储

'''
text+=f"[独立审计](stage178_energy_ml/independent_validation.json)用Python Fraction逐运算精确有理数重算{s['rational_bounds_N']}个区间边界，对全部稳健出生/过面步和逐hit源partition核查；旧observer字段逐项精确，原ordered HITS的ID/barcode及量化能量容差全部通过。50的真实native与observer on/off非干涉沿用Stage176实际证据，本阶段不冒称重做native或额外独立G4对照。\n\n"
text+=f"[调度账目](stage178_energy_ml/scheduler_accounting.json)3start全exit0、0live，{c['scheduler_CPU_s']:.0f}CPU秒/{c['scheduler_aggregate_wall_s']:.0f}聚合execute wall秒；实际4核12000MB。完整11链GNU{r['CPU_s']:.2f}CPU秒/{r['wall_s']:.2f}wall秒，吞吐{11/r['wall_s']:.6f}父/秒，仅描述本次3进程实际运行，不是受控并行加速比；峰RSS{r['RSS_KiB']}KiB。无GPU适用的训练，G4/ROOT均CPU。完整嵌套时序在[资源表](stage178_energy_ml/process_resources.json)，不和scheduler重复相加。\n\n"
text+=f"[存储审计](stage178_energy_ml/storage_cleanup.json)保留{c['retained_event_B']}B必要lineage/HITS/区间标签供同窗实验复用；清{c['deleted_bytes']}B运输/日志/spool，先核队列Iwd，未保留ROOT。source_snapshots/execution_audits/worker_logs/terminal_spool在software/stage178精确归档。原Stage54的12文件size/mtime保持。Stage176逐出生S0载荷从Git索引移出并加入ignore，本地实际文件及原审计包保持，紧凑physical_pilot_summary继续受版本控制；不把事件载荷作代码提交。\n\n"
text+='''```bash
python3 ml/stage178_freeze.py
python3 ml/stage178_ops.py submit --phase feasibility
python3 ml/stage178_ops.py collect --phase feasibility
python3 ml/stage178_admit.py
python3 ml/stage178_ops.py submit --phase replay
python3 ml/stage178_ops.py collect --phase replay
python3 ml/stage178_ops.py submit --phase audit
python3 ml/stage178_ops.py collect --phase audit
python3 ml/stage178_finalize.py
python3 ml/stage178_document.py
python3 ml/stage178_validate_docs.py
```

## 阶段结论与下一步

区间方法在原固定父中取得9个参考面支持，省去重复重建并保留困难缺口。尚未证明μ面前辐射解释低能错误，也未证明面后活动能可靠从读出中剔除，不能做能量加回、扩大4032或替换Stage87。

下一Stage179按已冻结同12父、实际原几何/随机种子/积分窗，注入已有persistent HITS并合成actual ADC，比较同窗analog理想量、同噪声无clip量及原signed raw，分解噪声/基线/量化/clip和S0来源。先50实际闭合与完整成本，再决定11；要求所有ADC/旧raw11状态/首父RNG及源相加闭合。仅复读固定9个已选train的旧Stage131预测用于逐父诊断，无新fit/forward、总体功效或收益宣称。lowpz_highE缺面继续未知。

另按用户双量程路线，Stage180将有限核已知run15838同源真实普通Ecal两路/实际模块映射与留出相对响应；不能从CaloNu坏设置否定普通Calo，也不能从两路存在虚构旧MC第二读出。真实绝对高幅参考、弱信号backscatter/相关噪声与信号保真、背景效率加权账目/乳胶及独立确认仍未交付。Stage87/全部原低能及尾部门、全部K/角色与reserved关闭保持，整体目标未完成。
'''
(ROOT/'workbook/2026-11-08_stage178_rounding-enclosed-S0-and-G4-only-pilot.md').write_text(text)
print('Rendered Stage178 Chinese report from worker summaries')
