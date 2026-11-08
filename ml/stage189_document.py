"""Render the Chinese report from already measured scalar summaries only."""
import csv
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
out=root/'workbook/stage189_energy_ml'
read=lambda name:json.loads((out/name).read_text())
proof=read('independent_validation.json');assert proof['passed']
cleanup=read('storage_cleanup.json');assert cleanup['passed']
decision=read('content_decision.json')
summary=read('composition_summary.json')
paired=list(csv.DictReader((out/'composition_paired.tsv').open(),delimiter='\t'))
selected=[r for r in paired if r['role'] in ['2','3'] and r['stratum'] in ['E50_100','E100_200'] and r['candidate']=='C' and r['reference'] in ['X','A','S','traditional']]
table='\n'.join(f"| {'cal' if r['role']=='2' else 'test'} | {r['stratum']} | {r['reference']} | {r['N']} | {float(r['RMSE_ratio']):.9f} | [{float(r['low95']):.9f}, {float(r['high95']):.9f}] |" for r in selected)
resources=read('process_resources.json')
resource_table='\n'.join(f"| {r['task']} | {r['CPU_s']:.2f} | {r['wall_s']:.2f} | {r['RSS_KiB']} |" for r in resources)
text=f'''# Stage189：固定有符号电荷组成交叉包与打乱对照

日期：2026-11-08。依用户更新后的[电子观测研究方案](2026-11-08_stage187_electronic-only-observables-research.md)§5/C执行；该分支独立于IFT传播，不等待乳胶。**固定四变量包未通过内容扩展或原联合门，结束此包，不晋升。** 不是旧X的信息极限，也不是所有物理交叉变量均无用的证明。

## 阶段目标与冻结方案

问题是有限深度BDT能否利用“组成”和“整体活动”分离后的表示。冻结前不读事件数据、不按test选择变换：[协议](stage189_energy_ml/protocol.json)仅四项 `asinh(Q_i/1 pC)-asinh(Q_j/1 pC)`，依次为VN0–VN1、V20–V21、PS0–PS1、PS0–VN0。Q0=1 pC是预定表示尺度，未作扫描；不同探测器响应不能相减成能量守恒或强子真值。保留原X62，raw负值合法，缺失继续NaN；不增加p0/p1/pz1或任何timing。

X62、A66（X+四可用性）、C70（A+四对比）、S70（A+同条件联合打乱的对比）四臂从头训练。打乱固定seed20261108189，限定原role、component、观测pz0分箱、六路总raw的asinh分箱及完整有限模式，不使用真实E、误差或标签。只用一个实现，不重复seed或选择有利打乱。各臂均原三seed、400轮、depth5、CPUhist、每臂一个incoming加权cal全局offset；共12个fit，原X不直接接受新列。

## 实际输入与支持

输入 `ntuples/energy_ml_stage119/old_input.npz`，总89033；train46575、cal11612、开发test13189、隔离17657。完整原K、原角色与pz0>50 GeV保持；隔离与reserved预测均0。Stage87保存预测作为原基线参考。

[支持表](stage189_energy_ml/content_support.tsv)显示四项在train/cal/test均完全可用，因此本次A与X的可用性差别是常量，不能把它解释成独立内容；实际预测也相同。VN0/VN1两路中保留负primitive计数train4566、cal1108、test1370（两路合计，非独立父数）。同条件打乱实际移动46504/11561/13123行，单例桶和恰巧固定点保持；不把移动次数当新独立N。

## 详细能量结果

下表为无量纲自然log能量RMSE比C/参考，越小越好；E分箱是真Eν而不是重建pz。所有区间均原固定500次component内incoming重采样，只是开发队列的条件区间，未包括来源、重训、研究选择及真实系统。

| 队列 | 真E层/GeV | 参考 | 行N | C/参考 | 条件95% |
|---|---|---|---:|---:|---|
{table}

完整[指标](stage189_energy_ml/composition_metrics.tsv)、[配对与八层三尾](stage189_energy_ml/composition_paired.tsv)、[原门](stage189_energy_ml/composition_gates.tsv)保留所有层及分母。最低test箱C/X=1.016564868，区间完全大于1；第二低箱约0.998936946且区间含1。C相对X、A、S在cal/test双低箱的5%扩展门均失败；四臂所有cal/test原joint均false。C/传统test最低箱1.972563334，第二箱上95%=1.065846661，两个低能非劣效门均未过。不能以低重建pz层或全体均值替代上述目标。

[固定决策](stage189_energy_ml/content_decision.json) expand={decision['expand']}；原1.05/1.01/1.03及八层三尾+2 pp未放松。C不晋升，不继续该包的Q0、变量对、容量或seed网格；不会用一项阴性来否定其他新测量。

## 程序核查、资源和产物

pilot重训X与Stage87全active预测最大log差为0；成本三倍投影309.106451613 CPU秒<full1400门，才提交其余9fit。独立审计实际重载{proof['actual_models_reloaded_N']}个模型，全部active ensemble及cal offset精确一致；独立math.asinh逐标量核查{proof['scalar_transform_checks_N']}项，最大float32差{proof['max_scalar_transform_float32_difference']:.12g}。打乱为同角色/成分/支持的双射；{len(proof['central_metrics_checks'])}项cal/test原层中心RMSE与三尾以math.fsum另算，最大差{proof['max_central_metric_difference']:.12g}。见[审计](stage189_energy_ml/independent_validation.json)。

| 进程 | GNU CPU/s | GNU wall/s | 峰RSS/KiB |
|---|---:|---:|---:|
{resource_table}

调度共{cleanup['starts']}次start、{cleanup['scheduler_CPU_s']:.0f} CPU秒、{cleanup['scheduler_aggregate_wall_s']:.0f}聚合执行wall秒、0 live，未超过2400 CPU秒新预算。full三个ensemble并行于4请求核；CPUhist保留原拟合路径，没有测量或宣称GPU加速比。full GNU CPU/wall比是包含评估的实际并发利用，不能作与串行受控加速比较。

首次audit已完成变换、模型和中心指标核查，决策阶段因提交包漏带既有paired.tsv退出，消耗21 CPU秒；补入原表，只在原600 audit预算剩余579秒内重跑审计，实际15 CPU秒通过。模型、预测、协议及所有训练均未改动；失败日志与版本原字节保留，见[修复记录](stage189_energy_ml/implementation_repairs.json)。

命令：`python3 ml/stage189_freeze.py`；`python3 ml/stage189_ops.py submit --phase pilot`；终态collect后 `python3 ml/stage189_admit.py`；通过才依次submit/collect full、audit；最后 `python3 ml/stage188_finalize.py 189`。全部NPZ、fit、forward和统计均在HTCondor `~/condor/nu_muAnalysis/stage189/`；本地仅源代码/调度、已有标量报告与字节归档。

模型和全active预测在 `ml/artifacts/stage189/`，打乱/四对比最小cache在 `ntuples/energy_ml_stage189/control.npz`；字节核对后的来源版本、日志、标量历史和终态spool在 `software/stage189/`。保留cache/模型{cleanup['retained_cache_models_B']} B，清理重复{cleanup['deleted_B']} B，原Stage54 {cleanup['Stage54_preserved_N']}项size/mtime保持；不持久化新ROOT/xAOD。[存储与失败记录](stage189_energy_ml/storage_cleanup.json)。

## 阶段结论与下一步

本次物理表示没有改善最低真能量区。可能原因仍包括已输入原始电荷与其有限组合的信息重叠；当前实验不能唯一归因训练N不足、所有强子漏失不可观测或模型Bayes极限。程序层已通过基线精确复现、独立变换/角色/模型/中心指标检查；没有据阴性结果修改配置。

下一步执行Stage188/190真实surface、全cov、field/material的IFT未用测量及真实run15838对照，记录原未匹配、几何外推失败、所有候选和低pz支持；验收首先是支持范围与关联/误差可解释性，不能把全部候选pull RMS称覆盖。路线B需实际时期LOS、上游运输与active/bad-strip支持才冻结少量散射平面矩及条件打乱。转换/overlay/测试束、2025+像素和非单pulse波形均只在相应真实manifest或物理结构/MC支持下启动；现有旧年份不能补造。真实背景/效率/权重及独立确认仍未测量，完整低能优势与物理目标保持未完成。
'''
(root/'workbook/2026-11-08_stage189_signed-charge-composition-control.md').write_text(text)
print('WROTE Stage189 Chinese report')
