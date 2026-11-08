"""Render audited scalar accounting; no event processing on the login node."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage193_energy_ml'
def read(name):return json.loads((OUT/name).read_text())
def num(v):return 'NA' if v is None else f'{v:.9g}'
if __name__=='__main__':
 audit=read('independent_validation.json');cleanup=read('storage_cleanup.json');assert audit['passed'] and cleanup['passed']
 full=read('full_accounting.json');cost=read('full_summary.json');admission=read('admission.json')
 rows=[]
 for r in full['groups']:
  if r['deposit_class']!='pure_direct_primary':continue
  rows.append(f"|{r['source']}|{r['fit_support_category']}|{r['parents_N']}|{r['matched_supported_parents_N']}|{r['candidates_N']}|{num(r['pull_RMS'])}|{r['abs_pull_gt3_N']}|{num(r['pull2_sum'])}|{num(r['fraction_of_class_pull2_sum'])}|")
 text=f'''# Stage193：同父IFT直接主μ残差与原拟合贡献的机制账目

日期：2026-11-08。[Stage192](2026-11-08_stage192_IFT-direct-primary-deposit-control.md)发现charm纯直接主μpull RMS17.66，故本阶段明确为**事后机制诊断**，不重新训练、校准或改变任何门。使用原160父缓存、原16pilot，逐父核对直接主μ候选的残差平方和与原leading fit的主μbarcode贡献。整体目标仍未完成。

## 固定问题、输入和选择

[协议](stage193_energy_ml/protocol.json)在本阶段逐父诊断前冻结。输入为 `ntuples/energy_ml_stage188/full_native.json.gz` 与 `ntuples/energy_ml_stage192/{{pilot,full}}_native.json.gz`，不读新ROOT/NPZ、不做新运输/reco/G4/模型fit或forward。原MC100012的64及π/K/charm各32train全部保留；原matching、起始面、几何界内与四deposit类别严格复用192。所有原K/角色/pz0-only/raw/typed NaN/status0/Stage87和八层三尾/低能门不变，没有隔离/reserved预测。

五个fit支持类事先固定：graph_unknown、no_fitted_track、no_primary_fit_barcode、primary_and_other_fit_barcodes、primary_only_stored_fit_barcodes。后两类只依据原Stage188 fit逐cluster的无权SDO barcode贡献计数；没有新fit-strip完整性/实际粒子指针测量。即使只有主μbarcode，也不能认证所有fit measurement纯主μ；没有主μbarcode也不自动等于错轨。这个限制与Stage192实际IFT候选上的指针解析不同，不能混淆。

原父逐class记录候选N、Σpull²、Σresidual²/mm²、最大abs(pull)及abs(pull)>3计数；全部逐父表保留，未按大残差选top-k或cut。全父按source/五fit支持类分解并闭合原192 N/RMS，平方和份额只是条件候选损失分布，不当作事件错误率、独立粒子概率或总体物理比例。

## pilot、完整账目与结论依据

原16pilot通过身份/内容和成本，三十倍完整process CPU加三倍160×最大逐父处理成本投影{admission['projection_CPU_s']:.9f}<100 CPU秒，准入后才全160；总300 CPU秒，pilot/full/audit各100，2请求核/4 GB、最多1job。初始化与gzip解压一次、源缓存复用，没有每父重复读入。pilot提交时monitor显示了继承的1200标签；实际协议/descriptor和submit执行上限始终分别为300/100/100/100，首次提交后修正通用monitor的参数化显示，不改预算或科学输出。首次本地collect因继承的硬编码Stage192下载路径失败；改为按实际CACHE路径构造URI后收回原作业，不重提、不重算科学结果。

下表为纯直接主μ类，各source的all行与五个分区同时列出。份额分母是同source全部纯直接主μ候选Σpull²，空分母为NA；RMS无量纲。parentN保留未匹配/无候选，candidateN仅原条件支持，不因分组删父。

| 来源 | 原fit支持类 | 原父N | 匹配且起始面支持父N | 纯直接主μ候选N | pull RMS | abs(pull)>3数 | Σpull² | Σpull²份额 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

charm原32父中，原fit没有主μbarcode贡献的2父包含9个纯直接主μIFT候选，其Σpull²=46262.420360826，占该来源纯主μ总平方和0.995541388；另外29个仅存主μbarcode父的134候选RMS1.219141183，1个混合barcode父的6候选RMS1.156508571。故17.66的汇总宽度主要与原拟合轨迹的主μ贡献支持相联系，不能直接当作正确主μ轨迹的协方差失配。这个全父分解不删那两父，也不证明它们的fit一定是错轨：原fit-strip缺失SDO或正权指针尚未测量。π无主μfit barcode的1父本次没有纯直接主μIFT候选，保持NA而非用作阴性证据。

全部四deposit类与逐父账目见[完整标量](stage193_energy_ml/full_accounting.json)、[逐父表](stage193_energy_ml/full_parents.tsv)。这些对照是已见192宽尾之后的解释性分解，不作显著性/覆盖/晋升验收，不将小类的0或NA当总体阴性。物理原因和程序原因仍须区分：原r/S、frame、实际truth指针与原父身份已数值闭合；其本身不证明fit身份、误差覆盖、材料模型或真实data纯度正确。

## 独立验证、计时和存储

不同标量实现重算所有160父的五fit支持类和四deposit分类、计数与平方和，{audit['independent_scalar_checks_N']}项通过，最大平方和浮点差{audit['max_absolute_square_sum_difference']:.12g}；原16pilot/full逐父全字段精确、所有category分区闭合、原192各source/class N和RMS复现。[验证](stage193_energy_ml/independent_validation.json)不是第二套HepMC解析或真实数据确认。

full内部{cost['CPU_s']:.9f} CPU秒/{cost['wall_s']:.9f} wall秒，峰RSS{cost['RSS_KiB']} KiB；两核未做受控加速测量，GPU无适用训练。调度{cleanup['starts']}start/{cleanup['scheduler_CPU_s']:.0f}CPU秒/{cleanup['scheduler_aggregate_wall_s']:.0f}聚合wall秒，失败{len(cleanup['failed_jobs'])}、0live。进程GNU计时见[资源](stage193_energy_ml/process_resources.json)。

命令：`python3 ml/stage193_freeze.py`；`python3 ml/stage193_ops.py submit/collect --phase pilot/full/audit`（顺序）；`python3 ml/stage188_finalize.py 193`；`python3 ml/stage193_document.py`。全部科学gzip读取/统计/验证在HTCondor，本地只源码、标量渲染、调度与精确字节归档。提交目录 `~/condor/nu_muAnalysis/stage193/`，紧凑cache `ntuples/energy_ml_stage193/` 留{cleanup['retained_cache_models_B']}B<1MiB；源码/日志/原标量/spool在 `software/stage193/`，清理{cleanup['deleted_B']}B重复，Stage54原12项size/mtime保持，无ROOT/xAOD持久化。

## 下一步的具体任务、输入和验收

本阶段结束同160父固定分解，不通过删除异常事例、改拟合轨迹、择窗或新seed降低RMS；Stage191能量阴性不重开。下一Stage194另冻1200 CPU秒、同16/160原父，读实际原fit-cluster逐strip正权粒子指针与SDO完整性，重复原确定性merge仅恢复同collection，cached collection index/pz0/charge/原barcode贡献必须精确。先16成本/身份/主μ支持门，通过才160和独立审计；无新fit或IFT运输，不用当前barcode成员关系替代实际指针。验收是原选择/贡献闭合及真实支持范围，不把MC标签当可部署错轨率或真实data覆盖。

B的有符号散射平面需实际LOS单位/符号/上游参考面及坏strip和DAQ active条件，才可冻结少量矩/打乱轴新训练；条件缺失不以探测器轴/全active代替。D需真实同设置conversion或RDO overlay/testbeam清单和误差；E需匹配2025+四平面像素/MC/共同ν覆盖；F需原status0实际非单pulse结构与支持的MC。物理谱需真实背景效率/加权生成账目/相关辅助误差及独立确认。这些未取得或未测量的项不判物理阴性；不借固定模型实验宣布整体完成。
'''
 (ROOT/'workbook/2026-11-08_stage193_IFT-parent-fit-support-accounting.md').write_text(text)
 print('WROTE Stage193 Chinese report')
