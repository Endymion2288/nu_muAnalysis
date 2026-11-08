"""Render only measured, independently audited scalar results in Chinese."""
import csv
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage191_energy_ml'
read=lambda name:json.loads((OUT/name).read_text())


if __name__=='__main__':
    audit=read('independent_validation.json');cleanup=read('storage_cleanup.json')
    assert audit['passed'] and cleanup['passed']
    decision=read('content_decision.json');summary=read('ift_summary.json');prep=read('preparation.json')
    pairs=list(csv.DictReader((OUT/'ift_paired.tsv').open(),delimiter='\t'))
    support=list(csv.DictReader((OUT/'content_support.tsv').open(),delimiter='\t'))
    rows=[]
    for role in [2,3]:
        for layer in ['E50_100','E100_200']:
            for ref in ['X','A','V','S','traditional']:
                r=next(q for q in pairs if int(q['role'])==role and q['stratum']==layer and q['candidate']=='C' and q['reference']==ref)
                rows.append(f"| {role} | {layer} | C/{ref} | {r['N']} | {float(r['RMSE_ratio']):.9f} | [{float(r['low95']):.9f}, {float(r['high95']):.9f}] |")
    ratios='\n'.join(rows)
    coverage='\n'.join(f"| {r['role']} | {r['stratum']} | {r['N']} | {r['matched_start_N']} | {r['any_valid_layer_N']} | {r['all_valid_layers_N']} | {r['moved_rows_N']} |" for r in support if int(r['role']) in [2,3] and r['stratum'] in ['all','E50_100','E100_200','pz50_100_trueE200'])
    fits=read('fits.json')
    fitrows='\n'.join(f"| {f['arm']} | {f['dimensions']} | {f['CPU_s']:.6f} | {f['wall_s']:.6f} | {f['RSS_KiB']} | {f['offset']:.12g} |" for f in fits)
    resources=read('process_resources.json')
    totals=dict(CPU_s=sum(r['CPU_s'] for r in resources if r['task'].startswith('full_')),wall_s=sum(r['wall_s'] for r in resources if r['task'].startswith('full_')))
    native=[read(f'full_{g}_summary.json') for g in range(35)]
    admission=read('admission.json');proof=read('pilot_validation.json')
    report=f'''# Stage191：原完整队列IFT留出测量内容与误差、打乱对照

日期：2026-11-08。按[电子观测路线A](2026-11-08_stage187_electronic-only-observables-research.md)完成原完整队列提取和15个新fit。**冻结的IFT三层全候选内容包是否通过双低能扩展：{decision['expand']}；原cal/test联合门：{summary['joint']}。** 这是固定表示和当前开发队列的有限实验，不是所有IFT表示的信息上限，也不认证真实data误差覆盖。Stage87保持，整体目标未完成。

## 目标、原输入和固定科学对照

[协议](stage191_energy_ml/protocol.json)在新IFT能量结果产生前冻结，使用Stage129原280 REC/PHYS来源和Stage119原89033父中71376 active，train46575/cal11612/devtest13189，quarantine17657及reserved不作新native读取或预测；全部K与原pz>50 GeV保持。输入绝对路径/逐父身份沿用 `workbook/stage129_energy_ml/extraction_contract.json`，X62与原Stage87角色/权重/seed/capacity不改。没有新ν独立样本或G4，完整新表示从头训练，不将新值直接喂旧模型。

Stage188/190已经建立实际surface/full covariance/field/material及真实data预测入口；此次固定geometry04/tag06、原 `CKFTrackCollectionMergeWithoutIFT`，gcc13 Stage188 bridge，FASER磁场、显式官方材料图，MS/eloss开启。原生SDO指针对所有父为null，truth不进入部署特征。所有原不匹配、缺面、失败父保留原X/role，新内容为typed NaN，不改pz0容差或选择replacement。

| 臂 | 维度 | 新输入 |
|---|---:|---|
| X | 62 | 原X62 |
| A | 66 | 原leading匹配且起始面支持标志、三层valid-wafer数量 |
| V | 69 | A加每层mean(log(预测σloc0/1 mm))，只使用完整cov运输的测量轴投影 |
| C | 81 | V加每层4项全部候选摘要 |
| S | 81 | 保留X/A/V，12项内容在固定可观测条件内联合打乱 |

valid-wafer要求预测成功、在实际几何界内、C00>0且候选pull全部有限；没有此类wafer时该层sigma/内容均NaN。每层内容固定为log1p(全部候选数)、log1p(abs(pull)≤3数)、log1p(Σexp(−pull²/2))、Σpull·exp(−pull²/2)/(1+Σkernel)。有valid-wafer而没有候选时四项均0；没有nearest hit、truncation择优或真贡献标签。真实measurement local u定义符号，跨wafer方向及立体角可能使有符号矩抵消，这属于本表示的限制，不事后挑方向/层。

打乱仅一个seed20261108191，保留role/component、固定pz箱、asinh(六路signed raw电荷和/1 pC)箱、精确A数量/有限模式及各层sigma箱。完整边界在协议；singleton保持，移动分母保留。sigma-only对照用于区分误差规模与真实测量内容；条件打乱不被称成数学条件独立证明。旧X中的raw电荷/typed NaN/合法负数及原status恰0 timing保持，p0/p1/pz1未作为新一阶动量加入。

五臂各3原seed、400round/depth5/CPUhist，共15fit；每臂只用train拟合和cal单一加权log offset，原incoming权重和500按component/incoming条件bootstrap。没有超参/变量包/窗口/seed扫描；X重新训练对原Stage87预测逐值精确。GPU未用于当前CPU ACTS运输及已冻结CPUhist；没有未经测量的GPU加速比。

## 小样本、程序修复及成本准入

原来源0/48/113/254/255/257/260/129各前min(40,trainN)，实际40/40/40/28/40/0/40/40，共268父；257无原train，保持0、不替换。268原pz精确匹配、267起始面支持；三层有支持父按来源为{proof['pilot_support']}，其中255保留1个无支持。pz50–100有{admission['pz50_100_N']}父、真E50–100有{admission['trueE50_100_N']}、真E100–200有{admission['trueE100_200_N']}。

独立pilot检查{proof['scalar_checks_N']}项r/S/pull、268原身份/角色与typed X62、真实frame/full covariance单位通过，最大位置闭合{proof['max_position_closure_mm']:.12g} mm。首次review在所有科学检查后因NumPy int64无法JSON序列化失败，3.05 GNU CPU秒；显式int转换两项计数，在原1000 review预算内修复。没有新native重读、样本替换、科学结果或特征改动。生产family4另有group32在观察算法前失败：原source257的PHYS路径为null，而该来源有356个K cal/test父、0train，故pilot未进入此支。改为该来源专用的原冻结manifest run/event/pz参考，准备及审计逐父与原输入核对，float32匹配不改；不寻找replacement PHYS或删父。首次重跑又在观察算法前发现旧origin82现存PHYS的pz与原缓存不一致；统一以所有父的原冻结run/event/pz为权威参考，现存legacy PHYS差异写入[参考QA](stage191_energy_ml/reference_source_qa.tsv)。此前成功34组均已逐父断言两者相等，参考值和特征不变。只重跑32，原family9600 CPU秒扣原1018和第一次repair43后剩8539，不加预算。最初失败reader为7.45 GNU CPU秒/11.38 wall秒；原失败日志在原字节归档，成功重跑日志使用同group名。[修复记录](stage191_energy_ml/implementation_repairs.json)和原失败日志归档。

pilot内部74.374707856 CPU秒/201.631082908 wall秒、请求ROOT读取38180689 B、峰RSS1836716 KiB。完整GNU78.79 CPU秒/207.44 wall秒，加bridge编译24.07 CPU秒/30.82 wall秒；后续事件全局均值{admission['subsequent_mean_CPU_s']:.12g} CPU秒。冻结三倍公式把35次完整初始化/编译、所有父成本和额外source transition均保守计入，投影{admission['projection_CPU_s']:.9f}<48000 CPU秒，8读者×1.25 RSS投影{admission['eight_reader_RSS_projection_MB']:.9f}<24000 MB，通过后才全队列。

总预算60000 CPU秒：pilot3000/review1000/production48000/fit3000/audit5000，未扩旧阶段预算。生产35组×8原来源，5固定family×7组，每family9600 CPU秒、最多4并发job，每job8核/24 GB、最多7原生reader并发；每reader独立cwd，避免POOL临时文件互相覆盖，复用单一runtime批读多个源，不逐父初始化。保留紧凑summary及原first2active/source的原生审计内容；全部科学ROOT/NPZ/gzip/statistics在Condor，本地只源码、标量、调度和精确字节归档。

## 完整支持和低能实测结果

完整加载{prep['loaded_N']} active，pilot/full {prep['pilot_full_exact_N']}原父summary与匹配逐值精确。缺失、源和失败原因见[支持表](stage191_energy_ml/content_support.tsv)、[逐源原因](stage191_energy_ml/native_reason_support.tsv)、[身份/起始面例外](stage191_energy_ml/native_identity_exceptions.tsv)。候选相关，不能把候选N当独立粒子N；几何内无cluster不是经坏道mask认证的hole。

| 角色 | 层 | 原父N | 匹配且起始面支持N | 任一有效层N | 全三有效层N | 条件打乱移动N |
|---|---|---:|---:|---:|---:|---:|
{coverage}

以下为自然对数Eν RMSE比，无量纲、越小越好；区间是原incoming/component条件95%，不含source/refit/研究选择及真实相关系统误差。角色2为cal、3为已开发test，非独立确认。

| 角色 | 真Eν箱/GeV | 对照 | 原父N | RMSE比 | 95%区间 |
|---|---|---|---:|---:|---|
{ratios}

![原两个真低能箱的固定对照和相对传统表现](stage191_energy_ml/low_energy_comparison.svg)

独立[PDF图](stage191_energy_ml/low_energy_comparison.pdf)可直接导出。上排比较固定内容与可用性/σ/打乱，下排相对传统；虚线分别为0.95扩展点门和1.05非劣效上界，门判断还需原区间及保护层。

双低能扩展逐对照：{decision['expansion']}；相对Stage87原三尾保护通过：{decision['original_tail_guards_pass']}。完整原八层三尾、额外高能/缺失等描述层见[配对表](stage191_energy_ml/ift_paired.tsv)和[原门](stage191_energy_ml/ift_gates.tsv)。原低能相对传统上95%≤1.05只是非劣效，不能改写成优越；all/Stage87≤1.01、其他五层≤1.03、八层三尾上95%≤+2 pp不放宽。sigma/association改善本身不作为能量成功。

## 独立审计、性能与存储

实际15个保存模型重新加载，所有active raw/cal预测和offset逐值精确、隔离/reserved无预测。全35原生组的first2active/source独立r/S/frame审计，以及{audit['scalar_transform_checks_N']}项不同NumPy实现的内容公式对照通过；最大float32差{audit['max_scalar_transform_float32_difference']:.12g}。{len(audit['central_metrics_checks'])}组原八层中心RMSE/三尾用math.fsum复核，最大差{audit['max_central_metric_difference']:.12g}；{len(audit['independent_row_bootstrap_checks'])}组C/V与C/S区间及三尾用独立row-space重算通过。全体父的content有限模式、shuffle角色/来源/可观测箱及A保持，不用truth挑shuffle。

| 臂 | 维度 | fit进程CPU/s | wall/s | 峰RSS/KiB | cal log offset |
|---|---:|---:|---:|---:|---:|
{fitrows}

35 reader GNU CPU和{totals['CPU_s']:.6f}秒、聚合wall{totals['wall_s']:.6f}秒、ROOT请求读取总{sum(r['ROOT_read_bytes'] for r in native)} B、最大单reader峰RSS{max(r['RSS_KiB'] for r in native)} KiB。CPU/wall是此次实测资源，不是受控线程数或GPU加速结论；GNU层级嵌套不再重复加进调度总量。调度{cleanup['starts']}start、失败{len(cleanup['failed_jobs'])}、{cleanup['scheduler_CPU_s']:.0f} CPU秒/{cleanup['scheduler_aggregate_wall_s']:.0f}聚合wall秒、0live。详细进程表见[资源](stage191_energy_ml/process_resources.json)。

命令：`python3 ml/stage191_freeze.py`；`stage191_ops.py submit/collect --phase`依次pilot、review、review_repair、production_0至4（并发≤4）、repair_4、repair2_4、fit、audit；`python3 ml/stage188_finalize.py 191`。提交目录统一 `~/condor/nu_muAnalysis/stage191/`。最终native/control在 `ntuples/energy_ml_stage191/`、模型预测 `ml/artifacts/stage191/`，共{cleanup['retained_cache_models_B']} B，小于96 MiB上限；源码/日志/标量历史/spool原字节在 `software/stage191/`，清重复{cleanup['deleted_B']} B，Stage54原{cleanup['Stage54_preserved_N']}项size/mtime保持，无新ROOT/xAOD。细节见[清理](stage191_energy_ml/storage_cleanup.json)。

## 阶段结论和下一步

本次回答固定IFT物理表示相对可用性、预测σ和条件打乱的单事例能量增量；按冻结双低能结果结束或保留该固定包，不继续选新层、seed或容量追显著。未取得独立μ纯度/正确关联/真实误差覆盖，不把内容收益转成已认证动量修正。原Stage87、所有K/角色/pz0-only/signed raw/typed NaN/status0 timing及科学门保持，整体低能真正优于传统和物理谱目标仍未完成。

后续B必须取得实际时期LOS与active/badstrip条件才冻结少量有符号方向矩及条件打乱轴；D需同设置conversion/raw-overlay或testbeam实际控制身份、selection和误差，E需2025+实际四平面和对应MC/ν共同覆盖，F需真实status0非单pulse结构及支持相应时间物理的MC。目录检查确认EOS存在2025/2026 data、TestBeam2021及tb21模拟，但目录名不认证这些条件，也不等同没有样本；本地当前固定Calypso源码检索未提供已配对的新像素接口。上述输入的可用性/覆盖尚未测量，不反演旧摘要伪造。真实背景/效率/生成权重/相关辅助误差和独立确认仍须实际输入；不以已有条件toys替代真实谱结论。
'''
    (ROOT/'workbook/2026-11-08_stage191_original-cohort-unused-IFT-energy.md').write_text(report)
    print('WROTE Stage191 Chinese report')
