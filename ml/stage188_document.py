"""Chinese Stage188 report from measured scalar artifacts; no event processing."""
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1];out=root/'workbook/stage188_energy_ml'
read=lambda n:json.loads((out/n).read_text())
proof=read('independent_validation.json');cleanup=read('storage_cleanup.json')
assert proof['passed'] and cleanup['passed']
full=read('full_native_summary.json');groups=read('full_prediction_summary.json')['groups']
rows='\n'.join(f"| {g['label']} | {g['parents_N']} | {g['original_leading_matched_N']} | {g['start_supported_N']} | {g['matched_pz50_100_N']} | {g['inside_geometric_wafer_predictions_N']} | {g['geometric_no_cluster_N']} | {g['multi_candidate_wafer_N']} | {g['compatible3_multiple_N']} |" for g in groups)
pulls='\n'.join(f"| {g['label']} | {g['all_candidate_pull']['N']} | {g['all_candidate_pull']['RMS']:.6f} | {g['SDO_shared_with_fit_contributor_pull']['N']} | {g['SDO_shared_with_fit_contributor_pull']['RMS']:.6f} | {g['SDO_shared_with_fit_contributor_pull']['abs_gt3_N']} | {g['SDO_no_shared_fit_contributor_pull']['RMS']:.6f} | {g['material_over_no_material_sigma_ratio']['median']:.6f} |" for g in groups)
resources=read('process_resources.json')
times='\n'.join(f"| {r['task']} | {r['CPU_s']:.2f} | {r['wall_s']:.2f} | {r['RSS_KiB']} |" for r in resources)
text=f'''# Stage188：withoutIFT轨迹对未用IFT真实测量面的预测

日期：2026-11-08。按[最新电子观测方案](2026-11-08_stage187_electronic-only-observables-research.md)A推进。**原π/K/charm的96个train父全部精确匹配原pz0，并可产生真实IFT测量面预测；候选关联混杂显著，共享SDO贡献的候选pull较集中。** 这建立了有具体支持的新电子观测入口，尚未认证真实data误差覆盖、主μ身份、关联错误率或Eν收益。

## 阶段目标与冻结输入

本阶段只测未参与拟合的station0测量，不把smoothed拟合内残差称独立pull。完整[协议](stage188_energy_ml/protocol.json)冻结4800 CPU秒，pilot1200/full3000/audit600、4请求核/12 GB、同阶段最多1作业、内层1线程、16 MiB最终事件摘要；无G4、digitization、重建或能量fit/forward。科学数据处理全部在HTCondor，本地仅源码、调度、已有标量和字节归档。

输入为原MC100012 REC/匹配PHYS第一64例，以及Stage129原请求0/48/113的π200082、K200083、charm200089各前32个train父，合计160；pilot各前4、共16，和full重叠，不是额外独立N。完整绝对路径、run/event/entry/role在协议；原8/63/2困难父缺面保持历史未知，没有替换或新reserved/隔离使用。

MC100012 REC为 `/eos/experiment/faser/sim/mc24/particle_gun/100012/rec/s0012-r0023/FaserMC-MC24_PG_muon_fasernu_100GeV-100012-00000-00004-s0012-r0023-xAOD.root`；ν为原s0014 REC与 `ntuples/merge_mc24_master_d32b0ff3/` 原PHYS。固定集合 `CKFTrackCollectionMergeWithoutIFT`，仍保留每个不匹配父，不事后改选forward/backward。通过float32原PHYS接口精确匹配pz0，而非可调容差。

## 原生坐标、协方差及传播

源码pin d32b0ff3cc4a2dad4abfb1474a82422c3c25b305，geometry FASERNU-04、OFLCOND-FASER-06，FASER磁场，显式官方 `material-maps-alma9.json`，多重散射和能损开启；固定零材料分支仅诊断，不作补偿或调优。

[源码证据](stage188_energy_ml/pinned_source_evidence.json)说明转换器把ACTS测量面bound完整5×5直接复制到Trk curvilinear对象，再按MeV变换q/p行列，未作局部frame Jacobian；6d6与d32相应转换函数文本一致。故不能按对象名把其loc0/loc1当任意curvilinear轴。只在首TrackParameters指针实际对应某TSOS cluster测量时恢复原wafer surface，反变换完整矩阵单位，检查ACTS/native真实测量轴与global/local闭合。独立dummy time与五参数无互相关，不是arrival time特征。该源码表示问题**不是已经证明低能失败源于协方差错误**。

对所有48个实际IFT wafer作backward、4000 mm路径上限传播，保存真实bounds/transform、完整参数/协方差与所有cluster/strip/可用SDO贡献；不选最近候选、不伪造每条strip二维点。逐候选 `r=u-predloc0`（mm）、`S=V+C00`（mm²），raw pull为r/√S。geometry不相交、传播失败、无cluster与多候选均保留；坏strip/DAQ mask仍未知，不能把几何无cluster称已认证hole。

## 实测支持与物理区分

| 来源 | 原父N | 原leading精确匹配N | 起始面支持N | 匹配pz0 50–100 GeV父N | 匹配且在界内wafer预测N | 无cluster预测N | 多候选wafer N | ≥2个abs(pull)≤3候选wafer N |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
{rows}

完整160例有156起始面支持、115原leading匹配；ν96/96匹配，MC100012仅19/64匹配。MC控制另有3无long track、1原position闭合超冻结1e−6 mm门；45个不匹配/不支持控制均保留，不能以匹配19个代表整个100 GeV μ总体。各来源全部wafer传播失败数2522/1358/1342/1342，包含几何范围和到面失败，不全是缺命中；不能将这些数当母事件失败率。详见[支持逐面表](stage188_energy_ml/full_wafer_support.tsv)及[完整摘要](stage188_energy_ml/full_prediction_summary.json)。

| 来源 | 全候选N | 全候选pull RMS | 与fit共享SDO贡献候选N | 共享候选pull RMS | 共享abs(pull)>3数量 | 无共享候选pull RMS | 开/关材料σloc0中位比 |
|---|---:|---:|---:|---:|---:|---:|---:|
{pulls}

ν三个来源的共享贡献候选pull RMS约1.10–1.22，非共享候选约154–211；这支持在拥挤活动里保留关联歧义，不能用全部候选的巨大RMS直接诊断拟合误差。共享标签是“与参与fit的strip SDO有共同贡献”，**不是已认证主μ/正确关联标签**；也有材料次级、共享PRD与误关联可能。SDO分组是在pilot后为解释已保存贡献ID作的探索性诊断，不参与冻结准入、选父、最近命中或模型特征。各wafer和候选高度相关，不能以候选N作独立统计N；未给其总体覆盖区间或data迁移认证。

材料开/关σ比为该明确配置的观测，不证明material-map逐项正确、producer covariance有正确覆盖或应再加一次能损。此次没有部署能量修正；完整Eν收益未测量。

## 程序验证、成本与失败

[独立审计](stage188_energy_ml/independent_validation.json)通过6832项有理数残差/方差及标量pull检查，172个source表示检查（含pilot/full重复），native/ACTS frame、单位及q/p重构动量检查；最大source位置闭合9.15527259337523e−7 mm。172次source实际传播roundtrip均成功，前五参数最大混合单位绝对差1.4210854715202004e−14，仅作数值诊断，不是统一物理误差。原pilot16的native内容与full逐值完全一致。

首JIT调用ACTS传播崩溃，265 CPU秒；换gcc13/C++20小bridge并显式材料图，首次compile因缺Athena聚合include失败4 CPU秒，补路径后成功。两项改变联合修复，未单独证明崩溃唯一原因；均为程序失败，无物理阴性。版本、失败日志、命令及耗时原字节归档，见[修复记录](stage188_energy_ml/implementation_repairs.json)。不改父、不提高原预算。

pilot成功后完整GNU+compile/稳态成本按原三倍公式预测904.073741760 CPU秒<full3000，预期RSS2163.515625 MB，通过才提交160。full内部CPU {full['CPU_s']:.6f}秒、wall {full['wall_s']:.6f}秒、ROOT请求读取{full['ROOT_read_bytes']} B、峰RSS {full['RSS_KiB']} KiB；第一execute结束83.635533322 CPU秒，表明初始化占主要成本，四REC同进程复用，而非每父重启runtime。不是受控CPU/GPU或串并行加速比。

| 进程 | GNU CPU/s | GNU wall/s | 峰RSS/KiB |
|---|---:|---:|---:|
{times}

调度共{cleanup['starts']}次start（2失败）、{cleanup['scheduler_CPU_s']:.0f} CPU秒/{cleanup['scheduler_aggregate_wall_s']:.0f}聚合wall秒/0 live，4800 CPU秒内；不把嵌套GNU再次加进调度总CPU。执行命令为 `python3 ml/stage188_freeze.py`，ops submit/collect pilot、pilot_repair、pilot_repair2、review，通过admission后full、audit，最后 `python3 ml/stage188_finalize.py 188`；提交目录 `~/condor/nu_muAnalysis/stage188/`。

最小native cache在 `ntuples/energy_ml_stage188/{{pilot,full}}_native.json.gz`，保留{cleanup['retained_cache_models_B']} B；源码版本/日志/标量历史/终态spool在 `software/stage188/`，精确回读后清理重复{cleanup['deleted_B']} B。[存储记录](stage188_energy_ml/storage_cleanup.json)验证Stage54 {cleanup['Stage54_preserved_N']}项不变；home根无旧nu_mu_stage目录，无持久化新ROOT/xAOD。

## 阶段结论和下一步

IFT未用测量是可执行的新电子内容；当前证据要求对关联/覆盖作区分，不能直接把pull或材料诊断称已校准μ修正。下一Stage190用已认证run15838 REC–PHYS原4/64配对、真实geometry04/tag05和原backward集合测试相同预测支持/歧义，保留非μ/不匹配及低pz分母，不借旧scintillator raw mismatch否决这个不同物理问题。需真实μ纯度/关联支持才认证data覆盖。

同轮Stage189按路线C从头训练固定组成包及availability/条件打乱对照；两条分支独立。后续A的内容能量比较须另冻原全队列、matched availability/σ和内容/打乱控制及成本，验收仍是真E双低箱、原八层三尾和全部原门；σ或关联区分单独改善不算能量成功。B还需实际LOS与active mask；D/E/F按实际控制manifest、匹配四平面新时期数据、严格status0真实非单pulse结构与相应MC支持开启，不重开旧Q/窗口网格。原Stage87/K/角色/pz0-only/raw/typed NaN/合法signed/status0 timing、reserved关闭保持；整体低能和真实系统物理目标未完成。
'''
(root/'workbook/2026-11-08_stage188_unused-IFT-surface-predictions.md').write_text(text)
print('WROTE Stage188 Chinese report')
