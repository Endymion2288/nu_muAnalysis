"""Render measured summaries and static stage state, no event-array calculations."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage175_energy_ml'
def read(name):return json.loads((OUT/name).read_text())
p=ROOT/'workbook/2026-11-08_stage175_timing-cohort-support-and-S0-inventory.md';text=p.read_text().split('## 全量实测、独立验证与结论')[0]
full=read('full_summary.json');rows=full['sources'];s0=read('S0_inventory.json');audit=read('independent_validation.json');store=read('storage_cleanup.json')
text+='''## 全量实测

原280来源89033身份/角色精确，原96例全部精确；8个明确run的实际CableMapping均支持，所有有PHYS来源的histogram映射均一致。

'''
text+=f"实际PHYS支持{sum(r['present_N'] for r in rows)}例；源257未保存PHYS的356例仍保留，另有{sum(r['present_N']-r['leading_match_N'] for r in rows)}例领先pz0不匹配，派生时间不输出。没有猜测替代来源或删事例。原rawQ负值合计{sum(r['negative_rawQ_N'] for r in rows)}个测量、精确-999电荷0个；负电荷保留。ROOT读取{sum(r['ROOT_read_bytes'] for r in rows)}B，仅为本次明确启用分支/selected entry的实际读取，不代表全ROOT物理大小。\n\n"
text+='| role | 层 | 分母 | 第一片strict/范围内 | 第二片strict/范围内 | 至少一片 | 两片同时 |\n|---|---|---:|---:|---:|---:|---:|\n'
support=list(csv.DictReader((OUT/'timing_support.tsv').open(),delimiter='\t'))
for r in support:
 if r['stratum'] not in ['all','E50_100','E100_200']:continue
 text+=f"| {r['role']} | {r['stratum']} | {r['N']} | {r['pair01_strict']}/{r['pair01_calibrated']} | {r['pair23_strict']}/{r['pair23_calibrated']} | {r['any_calibrated']} | {r['both_calibrated']} |\n"
text+='''
role=-1为全部含隔离，0为隔离、1/2/3为原train/cal/development-test；这里仅覆盖统计，无隔离预测。原八层完整表见[支持表](stage175_energy_ml/timing_support.tsv)。开发test至少一片6619/13189、最低箱169/183、第二箱692/856；存在值得进行一次固定新训练的内容支持，但不是模型已改善或可跨数据部署的证据。无时间事件和未通过范围者全部保留。

## μ控制尾部的固定诊断

[尾部诊断](stage175_energy_ml/muon_tail_diagnostics.json)重建原校准奇数entry留出残差，不改系数/门/窗口。下表全部为相对均时，|残差|>2ns为预定描述阈值。

| 来源 | pair | 留出N | >2ns N | 其中仍在训练范围N | 最大绝对残差 ns |
|---|---|---:|---:|---:|---:|
'''
for r in read('muon_tail_diagnostics.json')['rows']:
 if r['kind']!='relative_mean':continue
 a,b=r['groups'][:2];text+=f"| {r['label']} | {r['pair'][0]}/{r['pair'][1]} | {a['N']} | {b['N']} | {b['inside_training_ranges_N']} | {b['max_abs_residual_ns']:.6f} |\n"
text+='''
大残差并不只出现在Q/x/y超训练范围者：例如data8006第一片35例中31例仍在范围内，data15838第二片91例中88例仍在范围内。所有这些留出组的clockPhase均有限；这不认证实际相位质量。2022/旧MC的local采集时间主要在约810–975ns、2024约172–295ns，证实绝对采集坐标不可跨时期直接共用，不能把localtime当飞行时间或再统一减一次phase。两端/参考的固定时间分箱、极值和首8个确定尾部身份/时基/Q/位置均保留。

这些结果排除了“所有大残差仅为范围外外推”这一单一解释，尚不能区分附加/迟到脉冲、参考hit、时钟转移或重建原因；原因保持未知。未因为这些事例停止整个均时分支，也不据尾部剔除事件、换拟合族或补出坏hit时间。跨运行期真实误差和ν多沉积响应仍未认证。

## S0实际参考点清点

'''
text+=f"实际同领先pz0的有限物理Track_x0/y0/z0有{s0['matched_physical_finite_state_N']}例，缺失/不匹配/占位{s0['missing_or_placeholder_N']}例；精确-999坐标成分{s0['exact_minus999_component_N']}个。z0共有{s0['unique_S0_z_N']}个实际值，范围{s0['S0_xyz_min_mm'][2]}–{s0['S0_xyz_max_mm'][2]}mm，x/y极值见[S0清点](stage175_energy_ml/S0_inventory.json)。完整原XYZ在cohort中，未以均值或名义几何代替逐父参考点。\n\n"
text+='''
静态pinned producer证明这些坐标和pz0来自同一个`trackParameters()->front()`；实际fitter启用散射与能损。**这不是G4 μ过面能量、不是顶点μ能量，也不是已认证可直接加回的辐射能。** 原PHYS没有实际surface normal/type及每步材料修正，旧compact observer也没有出生/过面细节，需Stage176固定小型同父observer与native state补充，不自动4032重放。

## 独立验证、资源与存储

'''
text+=f"[独立验证](stage175_energy_ml/independent_validation.json)实际重读三源各原首个selected entry全部字段精确；{audit['scalar_calibrated_values_N']}个有支持均时逐行标量重建，最大差{audit['max_scalar_difference_ns']:.3g}ns；全队列派生量/缺失精确及各role独立计数通过。\n\n"
text+=f"终态{store['starts']} start，全部exit0、0live，累计{store['scheduler_CPU_s']}调度CPU秒、{store['scheduler_aggregate_wall_s']}聚合execute wall秒。实际RequestCpus={store['scheduler_RequestCpus']}，站点RequestMemory={store['scheduler_RequestMemory_MB']}MB。无应用短timeout、无能量fit/forward/G4/新ν/GPU。本次稀疏ROOT读取和固定小线性诊断不适合GPU加速。\n\n"
text+='| GNU任务 | CPU秒 | wall秒 | maxRSS KiB |\n|---|---:|---:|---:|\n'
for r in read('process_resources.json'):text+=f"| {r['phase']} | {r['CPU_s']} | {r['wall_s']} | {r['RSS_KiB']} |\n"
text+=f"\n[终态存储账](stage175_energy_ml/storage_cleanup.json)原字节归档/重读源码{store['source_logical_N']}逻辑版本/{store['source_unique_N']}独立内容，队列无Iwd引用才清理；保留`ntuples/energy_ml_stage175/cohort.npz` {store['retained_cohort_array_bytes']}B，删{store['deleted_bytes']}B重复运输、prefix、日志和提交文件。{store['source_summary_duplicates_removed_N']}份重复source summary已逐项与full_summary核对一致后合并，未产生中间ROOT；8核读取的临时NPZ分片在worker完成合并/验证后删除。软件版本与资源/提交审计在`software/stage175/*.tar.gz`，Stage54原12项大小/mtime保持。\n\n"
text+='''
收尾命令：

```bash
python3 ml/stage175_ops.py collect --phase full
python3 ml/stage175_ops.py submit --phase audit
python3 ml/stage175_ops.py collect --phase audit
python3 ml/stage175_finalize.py
python3 ml/stage175_document.py
python3 ml/stage175_validate_docs.py
git diff --check
```

## 阶段结论与下一步

两片均时在原全队列有有限支持，真实尾部和跨时期迁移仍未知；真实差时位置分支保持未通过。本阶段没有训练能量模型、没有能量改善结论或晋升，Stage87及原八层三尾完整验收门保持。

下一Stage177待本阶段终态验证提交后，冻结同支持X62/V66/T68：X从头复现Stage87，V追加每片strict/范围可用状态共4维，T再追加两片校准均时；3seed×400轮、train/cal/开发test、原incoming权重与500分组bootstrap不变。先单X成本/精确复现，再V/T新训练，比较内容T/V与各臂/传统及原完整门，报告无时全样本而非只展示Good Hit子集。MC条件研究不认证真实迁移或独立最终确认；GPU若改变原CPU hist复现口径则不用来伪造基线一致。

Stage176先原50父新只读observer/native surface preflight，验证旧谱系与HITS不变、实际S0面/协方差、主μ能量bracket和直接子粒子出生标签；过原成本门才固定其余11父，禁止自动4032扩产。之后再按同窗模拟响应和可测伴随量决定机制与部署分支。真实双量程/独立高幅参考、匹配噪声/信号保真、backscatter覆盖及实际背景/效率/生成加权输入继续，外部匹配缺口保留；项目整体未完成。
'''
p.write_text(text)
