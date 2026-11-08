"""Render measured JSON summaries; no event-array or metric recomputation."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage174_energy_ml'
def read(n):return json.loads((OUT/n).read_text())
report=ROOT/'workbook/2026-11-08_stage174_timing-dual-end-control.md'
s=report.read_text();s=s.split('\n## 实测结果')[0]
rows=read('calibrations.json');full=read('full_summary.json');audit=read('independent_validation.json');storage=read('storage_cleanup.json')
s+='''
## 实测结果

三份源每份原前4096例，合计12288输入；没有用ν能量挑选控制。实际CableMapping及PHYS histogram title均确认硬件8/9对应Timing0/1同plate、10/11对应Timing2/3同plate，每对PMT不同。两真实来源与MC均逐源独立校准；原Stage129控制run/event及Veto21观测精确一致，三源pilot前缀全部精确保持。

| 来源 | 原输入 | μ控制 | strict端0/1/2/3/参考 | ROOT读取B | CPU秒 | wall秒 |
|---|---:|---:|---|---:|---:|---:|
'''
for r in full['sources']:
 s+=f"| {r['label']} | {r['N']} | {r['control_N']} | {'/'.join(map(str,r['strict_end_N']))} | {r['read_bytes']} | {r['CPU_s']:.4f} | {r['wall_s']:.4f} |\n"
s+='''
下表Δ为双端差时，M为相对Veto21的均时；位置误差仅Δ定义。所有值来自冻结模型奇数entry留出，不删大残差。门判定是本实验的有限条件门，不是独立运行期迁移认证，也不是ν能量门。

| 来源 | pair | 量 | train/valid | RMSE ns | abs95 ns | 有效位置abs95 mm | 通过 |
|---|---|---|---:|---:|---:|---:|---|
'''
for r in rows:
 x=r.get('validation_position_abs95_mm');pos=f'{x:.3f}' if x is not None else '不适用'
 s+=f"| {r['label']} | {r['pair'][0]}/{r['pair'][1]} | {'Δ' if r['kind']=='difference' else 'M'} | {r['train_N']}/{r['validation_N']} | {r['validation_RMSE_ns']:.6f} | {r['validation_abs95_ns']:.6f} | {pos} | {'是' if r['usable'] else '否'} |\n"
s+='''
12项均rank4、condition小于1e6，训练x SD为50.24–71.99mm；不存在仅因设计退化而误报物理失败的行。完整系数、训练Q/x/y范围、差时符号和有效传播速度保留于[校准表](stage174_energy_ml/calibrations.json)。速度是拟合参数诊断，不能据此声称真实shower位置。

**真实数据两片的差时/位置均未通过预定门，MC两片均通过；不能把MC约13–31mm的留出有效位置精度当作真实数据精度。** data8006两片相对均时及data15838第一片通过abs95≤2ns，但数项RMSE明显大于abs95，说明尾部影响不能忽略。尚未分辨大残差来自非prompt/附加活动、时钟/重建还是控制选择；这些原因均为未知，不删离群事件、不调门或更换拟合族。下一小型覆盖实验同时给固定尾部诊断，不因少数异常终止全部均时研究。真实跨run迁移、弱信号与ν多沉积闭合均未认证。

三源本次rawQ负值和-999占位计数均0；这只描述有限控制，不是把全队列负Q改0。bcidtime/triggertime和clockPhase只保留诊断，未作为特征；非0status不产生差时、均时或有效位置。所有输入与未通过/缺时事件仍在分母。

## 验证、资源与存储

'''
s+=f"[独立验证](stage174_energy_ml/independent_validation.json)：三源实际重读原前4例、全部数组精确；{audit['calibration_rows_scalar_checked']}项留出残差逐行标量重建，最大RMSE/abs95差{audit['max_metric_difference_ns']:.3g}ns。它验证实现，不认证物理迁移。\n\n"
s+=f"调度{storage['starts']} start，全部exit0、0live；累计{storage['scheduler_CPU_s']}CPU秒、{storage['scheduler_aggregate_wall_s']}聚合execute wall秒。请求4CPU/8000MB，站点实际RequestCpus={storage['scheduler_RequestCpus']}、RequestMemory={storage['scheduler_RequestMemory_MB']}MB；实际资源以调度账为准。冻结预算1200CPU秒，无应用短timeout。\n\n"
s+='| GNU任务 | CPU秒 | wall秒 | maxRSS KiB |\n|---|---:|---:|---:|\n'
for r in read('process_resources.json'):s+=f"| {r['phase']} | {r['CPU_s']} | {r['wall_s']} | {r['RSS_KiB']} |\n"
s+=f'''
[存储账](stage174_energy_ml/storage_cleanup.json)在队列Iwd核对无引用后完成原字节归档与重读：源码{storage['source_logical_N']}个逻辑版本/{storage['source_unique_N']}个独立内容；删除{storage['deleted_bytes']}B重复运输、日志、提交文件和已验证prefix。保留3份完整控制数组{storage['retained_control_array_bytes']}B，路径`ntuples/energy_ml_stage174/full_0.npz`至`full_2.npz`；软件/执行/终态提交审计在`software/stage174/*.tar.gz`。Stage54原12项大小/mtime保持。能量fit/forward/G4/新独立ν/GPU作业均0；这一小规模线性控制不需要GPU。

完整执行命令：

```bash
python3 ml/stage174_ops.py collect --phase pilot
python3 ml/stage174_admit.py
python3 ml/stage174_ops.py submit --phase full
python3 ml/stage174_ops.py collect --phase full
python3 ml/stage174_ops.py submit --phase audit
python3 ml/stage174_ops.py collect --phase audit
python3 ml/stage174_finalize.py
python3 ml/stage174_document.py
python3 ml/stage174_validate_docs.py
git diff --check
```

## 阶段结论与下一步

新双端观测具有有限真实均时支持，真实差时位置支持尚不足；未训练能量模型、未宣称能量改善，Stage87及全部原验收门保持。

下一Stage175固定旧89033队列/280来源的真实保存Timing状态、localtime/rawQ、pz0与Trig外推，先原pi/K/charm各32个train的接口/成本pilot，再按成本门读所有明确selected entry，缺源不替换、无时间父不删除。只对通过真实控制门且MC也通过的两片均时检查MC校准范围覆盖；data系数不直接移植到MC。同步固定检查μ留出中|残差|>2ns的数量、状态/采集坐标/参考差异，以区分实现与物理未知，不能按结果修门。若有实际支持，再另冻X/状态V/状态+均时T的同支持新训练及原八层三尾评估；没有支持则结束该部署候选。全队列覆盖、均时能量改善及跨时期系统误差仍未测量。

S0实际参考面/材料修正和前后辐射的小型同父instrumentation、匹配同窗读出干预、实际双量程/独立高幅参考、backscatter及背景效率/生成加权物理路线继续；不以本校准作为无限前置。项目整体与独立最终确认仍未完成。
'''
report.write_text(s)
