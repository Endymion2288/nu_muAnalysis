"""Render the Chinese measurement report from actual saved tables (no new inference)."""
import csv
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage125_energy_ml'
REPORT=ROOT/'workbook/2026-11-06_stage125_frozen-direct62-geant4-performance.md'


def rows(name):return list(csv.DictReader((OUT/name).open(),delimiter='\t'))
def number(value,n=4):return f'{float(value):.{n}f}'
def mdtable(headers,data):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,r))+' |' for r in data])


def main():
    metrics=rows('metrics.tsv');summary=rows('sample_summary.tsv');select=rows('selection_yields.tsv');contrast=rows('tune_contrasts.tsv');quality=rows('migration_quality.tsv')
    validation=json.loads((OUT/'validation.json').read_text());independent=json.loads((OUT/'independent_validation.json').read_text())
    audit=json.loads((OUT/'production_audit.json').read_text());resources=json.loads((OUT/'condor_resources.json').read_text())['summary']
    figures=json.loads((OUT/'figure_catalog.json').read_text())
    assert validation['complete_source_inventory'] and figures['complete_source_inventory']
    assert audit['returned']==904 and audit['failed']==0 and independent['passed']
    assert resources['current_queue_jobs']==0
    tunes=['FTF_BIC','FTFP_INCLXX','JEFF33','ENDFB8','QGSP_BERT']
    find=lambda scope,t,layer,model:next(r for r in metrics if r['scope']==scope and r['tune']==t and r['stratum']==layer and r['model']==model)
    lines=['## 实际结果与物理解释','',f'正式 **{audit["returned"]}** 个来源全部返回，非零退出 **{audit["failed"]}**；最终 selected **{validation["selected_N"]:,}** 条，剔除已知 Stage87 train/cal incoming 响应 **{validation["fit_overlap_N"]:,}** 条后，主样本 **{validation["primary_N"]:,}** 条。原 Stage87 active 三模型 raw/cal 逐元素复现；原开发 test 的 direct log-RMSE **{validation["stage87_test"]["log_RMSE"]:.9f}**。以下数值全部来自实际缓存/输出，没有新拟合。','']
    lines += [mdtable(['tune','主样本行','唯一 incoming 代理','已知 train/cal 重叠行','已知原 test 重叠行','E/成分匹配 ESS','E/成分/y/z 匹配 ESS'],[[r['tune'],r['primary_N'],r['primary_unique_incoming'],r['fit_overlap_N'],r['known_test_overlap_N'],number(r['standardized_ESS'],1),number(r['matched_ESS'],1)] for r in summary]),'']
    for scope,title in [('primary','原样本组成，按 incoming/纳入率加权'),('standardized','共同 E × 成分分布'),('fully_standardized','共同 E × 成分 × y × 深度分布')]:
        lines += ['### '+title,'',mdtable(['tune','direct log-RMSE [条件95%]','传统 log-RMSE','direct median bias %','direct R68 %','direct 总尾 %','direct 正/负尾 %'],[[t,number((a:=find(scope,t,'all','direct'))['log_RMSE'])+' ['+number(a['log_RMSE_low95'])+','+number(a['log_RMSE_high95'])+']',number(find(scope,t,'all','traditional')['log_RMSE']),number(a['median_bias_pct'],2),number(a['R68_pct'],2),number(a['tail50_pct'],2),number(a['positive_tail50_pct'],2)+' / '+number(a['negative_tail50_pct'],2)] for t in tunes]),'']
    lines += [f'E/成分共同 overlap mass **{validation["common_component_energy_overlap_mass"]:.6f}**；再控制 y/深度后 **{validation["common_component_energy_y_depth_overlap_mass"]:.6f}**。这两个量衡量匹配前共有归一化质量，不是事件选择效率或独立样本比例。','', '### 低能与困难侧','',mdtable(['tune','true50–100 direct/传统 log-RMSE','true100–200 direct/传统','低pz真≥200 direct/传统','high-y direct/传统','unconfirmed direct/传统'],[[t]+[number(find('primary',t,layer,'direct')['log_RMSE'])+' / '+number(find('primary',t,layer,'traditional')['log_RMSE']) for layer in ['E50_100','E100_200','lowpz_highE','high_y','unconfirmed']] for t in tunes]),'']
    lines += ['### tune 差异的相关区间','',mdtable(['组成控制','tune / JEFF33','direct log-RMSE 比 [条件95%]','direct 总尾差 pp [条件95%]'],[[scope,t,number((a:=next(r for r in contrast if r['scope']==scope and r['tune']==t and r['stratum']=='all' and r['model']=='direct' and r['quantity']=='log_RMSE'))['estimate'])+' ['+number(a['low95'])+','+number(a['high95'])+']',number((b:=next(r for r in contrast if r['scope']==scope and r['tune']==t and r['stratum']=='all' and r['model']=='direct' and r['quantity']=='tail50_pct'))['estimate'],2)+' ['+number(b['low95'],2)+','+number(b['high95'],2)+']'] for scope in ['primary','standardized','fully_standardized'] for t in tunes if t!='JEFF33']),'']
    lines += ['JEFF33 只是事前固定的比较基准，不是宣称其为 Stage87 的训练物理模型。区间跨1/0代表本条件统计下未分辨该差异，不是等效性/非劣认证。多个能区与指标的区间未作全局同时覆盖修正，探索性逐项显著不能单独升级为全局系统学结论。','', '### 选择与组成','',mdtable(['run','tune','成分','实际父条数','fiducial CC νμ pz>50 条数','selected','fiducial 选择效率 %'],[[r['run'],r['tune'],r['component'],r['parent_N'],r['fiducial_CC_numu_pz50_N'],r['selected_N'],number(100*float(r['fiducial_selection_efficiency']),2)] for r in select]),'','[selection_yields.tsv](stage125_energy_ml/selection_yields.tsv) 的分母先于任何 BDT 与重叠排除，使用原累计真值条件；是制作视图效率，不是完整生成家族独立二项效率。QGSP 采样、空文件、原文件末尾不足1000/10000事件均按实际父计数保留。','']
    lines += ['### 有数据支持的阶段结论','']
    direct=[find('primary',t,'all','direct') for t in tunes]
    traditional=[find('primary',t,'all','traditional') for t in tunes]
    lines += [f'1. **现有模型在五组样本上均保留整体收益，但尚不能认证全物理鲁棒性。** 原组成 direct log-RMSE 范围 {min(float(r["log_RMSE"]) for r in direct):.4f}–{max(float(r["log_RMSE"]) for r in direct):.4f}，传统法为 {min(float(r["log_RMSE"]) for r in traditional):.4f}–{max(float(r["log_RMSE"]) for r in traditional):.4f}。共同 E/成分/y/深度组成下，全部非基准 tune 的整体 log-RMSE 比值区间覆盖1；这只说明当前条件统计未分辨整体差异，未预设容许误差的等效性检验没有进行。','']
    lines += [mdtable(['tune','绝对能量方格 direct 同箱率 %','传统同箱率 %'],[[t]+[number(next(r for r in quality if r['scheme']=='paper' and r['tune']==t and r['model']==model and r['bin']=='0')['all_bin_agreement_pct'],2) for model in ['direct','traditional']] for t in tunes]),'','同箱率使用所示[0,100,300,600,1000,∞) GeV绝对能量方格、主样本原组成和 incoming/纳入率权重；它依赖分箱和入射谱，不是无条件选择效率或完整30维 unfolding 的精度。','']
    lines += [mdtable(['tune','50–100 GeV incoming 数','50–100 GeV median bias %','共同 E/成分/y/z 下50–100 log-RMSE / JEFF33 [条件95%]','3200–6400 GeV incoming 数','3200–6400 GeV median bias %'],[[t,find('primary',t,'E50_100','direct')['incoming'],number(find('primary',t,'E50_100','direct')['median_bias_pct'],2),number((a:=next(r for r in contrast if r['scope']=='fully_standardized' and r['tune']==t and r['stratum']=='E50_100' and r['model']=='direct' and r['quantity']=='log_RMSE'))['estimate'])+' ['+number(a['low95'])+','+number(a['high95'])+']',find('primary',t,'E3200_6400','direct')['incoming'],number(find('primary',t,'E3200_6400','direct')['median_bias_pct'],2)] for t in tunes]),'']
    lines += ['2. **低能区仍有正偏与 tune 依赖，高能端有负偏。** 在所选50–100 GeV样本中，所有 tune 的 direct log-RMSE 均劣于传统法（见低能表）；整体收益不能外推为每个能区的收益。原选择包含重建 pz0>50 GeV，该低能比较条件于这一选择，不能直接外推全生成低能总体。上表低能差异在进一步控制粗 y/深度后仍存在，因此只用总体平均或粗 E/成分差异不足以解释全部观测。能量估计包含 μ 子与强子淋浴信息，强子级联、低能中子与可见能量响应变化是物理上可能的机制；本轮没有逐粒子能量账本，不能将某一机制确认为原因。3200–6400 GeV高能负偏在五组均出现，与现有模型的能区响应压缩一致；≥6400 GeV在主样本没有支持，性能未测量。超出训练能区和非线性响应各自贡献未测量。QGSP 的低能 incoming 数较少，不能据单个能区排序宣称某 physics list 更正确。','',
              '3. **程序与物理制作差异需分别看待。** 62维表示、实际 payload 转换、原预测复现和逐行身份验证排除了本轮已检查的表示/校准错误；它们不能消除原模拟提交不同、顶点/种子与 GENIE 完整末态未认证等混杂。相同 incoming 的配对图只约束该代理，保留两侧选择条件，不能单独解释选择损失。','',
              '4. **统计精度有明确边界。** source/incoming 图中 π、K、charm 各仅一个连通块，不能把904文件当904个独立生成块。完整 source/parent 稳健95%区间、全物理系统学与匹配估计误差均为**未测量**；本报告区间仅为固定模型、固定匹配目标下的 incoming 条件区间。','']
    reference=rows('stage87_reference_metrics.tsv')
    ref_low=next(r for r in reference if r['model']=='direct' and r['stratum']=='E50_100')
    ref_high=next(r for r in reference if r['model']=='direct' and r['stratum']=='E3200_6400')
    lines += [f'原 Stage87 已曝光 test 参照中，50–100 GeV的 median bias 为 **{float(ref_low["median_bias_pct"]):.2f}%**，3200–6400 GeV为 **{float(ref_high["median_bias_pct"]):.2f}%**。两端偏差在原模型参照中已存在，不能全部归因于新 tune；能量曲线保留该参照作直观比较，不把两组不同组成的点估计当作配对因果差。','']
    available=next(r for r in select if r['run']=='200104')
    lines += [f'用户清单 run200104 标称560154事件，实际可用父记录为 **{available["parent_N"]}**，相差 **{560154-int(available["parent_N"])}**；按实际记录报告，没有把该差异当效率损失或擅自补到标称曝光。','']
    lines += ['## 图集与实际验证','','完整浏览入口：[完整图集](stage125_energy_ml/index.html)。每图提供 PNG/PDF，固定色标、真值横轴、重建纵轴；PDF可直接用于讨论/汇报。','', '![能量迁移矩阵](stage125_energy_ml/migration_paper.png)','', '![无能量分箱的连续密度](stage125_energy_ml/continuous_density_direct.png)','', '![稳健性及组成控制](stage125_energy_ml/robustness_overview.png)','', '![能区响应](stage125_energy_ml/energy_profiles_direct.png)','', '![π/K/charm分别的迁移矩阵](stage125_energy_ml/component_migrations.png)','', '其他产物包含传统法连续密度与能区曲线、细箱迁移、全部事件散点、tune 差异矩阵、正负尾、selection、stability/purity、62列输入响应/缺失率及分成分响应。逐图定义见 [figure_catalog.json](stage125_energy_ml/figure_catalog.json)。','', f'独立验证 [independent_validation.json](stage125_energy_ml/independent_validation.json)：通过 **{independent["passed"]}**；主样本 train/cal incoming 交集 **{independent["primary_train_cal_overlap"]}**；行空间点值与聚类计算最大差 **{independent["point_max_abs_delta"]:.3g}**，95%区间边界最大差 **{independent["CI_bound_max_abs_delta"]:.3g}**；全部有支持的真值列概率和为1。训练模型和校准参数保持原值。','',f'新样本三模型总推理 wall **{validation["new_inference_wall_s"]:.6f} s**、吞吐 **{validation["new_inference_events_per_s"]:.2f} selected events/s**（含三模型读取和 DMatrix；4线程CPU，无GPU）；整个评估 Python process CPU **{validation["CPU_s"]:.3f} s**、wall **{validation["wall_s"]:.3f} s**、峰 RSS **{validation["RSS_KiB"]} KiB**。','']
    step={}
    for r in audit['results']:
        for n in ['parent','digi','reco','ntuple','extract']:
            if n in r:
                a=step.setdefault(n,[0,0,0]);a[0]+=r[n].get('CPU_s',0);a[1]+=r[n].get('wall_s',0);a[2]=max(a[2],r[n].get('RSS_KiB',0))
    lines += [mdtable(['正式步骤','逐步 CPU 秒合计','逐作业步骤 wall 秒合计','最大单步骤 RSS KiB'],[[n,number(a[0],2),number(a[1],2),int(a[2])] for n,a in step.items()]),'',f'整作业 Condor 账本 [condor_resources.json](stage125_energy_ml/condor_resources.json)：历史 **{resources["completed_history_jobs"]}** 条、移除 **{resources["removed_history_jobs"]}** 条、当前队列 **{resources["current_queue_jobs"]}** 条；整作业总 CPU **{resources["CPU_s"]:.1f} s = {resources["CPU_s"]/3600:.3f} CPU h**，wall逐作业之和 **{resources["sum_job_wall_s"]:.1f} s**。它包含 pilot/重跑/统计等已结束任务；不与上表再相加。完整实际网络字节、全集群同时峰内存、GPU加速比和全物理系统误差 **未测量**。','',
              f'最终 **{len(figures["figures"])}** 组图采用4进程计算独立 KDE，图集内部计时 **{figures["wall_s"]:.3f} s**。两种能量方法各有64个查询点逐值复算，与并行结果完全相同。903来源预览串行绘图计时494.58 s；最终输入和图数略有增加，此比较仅为工程计时记录，不是严格同输入加速比。GNU整进程计时与峰RSS见 [plot_time.txt](stage125_energy_ml/plot_time.txt)。保留紧凑 NPZ/审计和最终图表，生产 ROOT/xAOD 临时文件均由 worker 退出清理；缓存目录不提交Git。','']
    source_bytes=sum(r['transport_bytes'] for r in audit['results'])
    cache=ROOT/'ntuples/energy_ml_stage125'
    prediction_bytes=sum((cache/name).stat().st_size for name in ['evaluation.npz','reference.npz','selected_inputs.npz'])
    figure_bytes=sum((OUT/(r['name']+suffix)).stat().st_size for r in figures['figures'] for suffix in ['.png','.pdf'])
    lines += [f'实际紧凑产物：904份 selected/审计来源压缩包共 **{source_bytes} B**，三个可复用 NPZ 共 **{prediction_bytes} B**，最终 PNG/PDF 共 **{figure_bytes} B**。已回收的 preview/evaluate/plot 传输包不作为额外事件副本保留；回收文件清单保存在 transfer.json 中。','']
    lines += ['最终迁移图直接从已独立验证的 [matrices.tsv](stage125_energy_ml/matrices.tsv) 汇总表渲染；无支持列使用灰底短横线，真实零概率保留概率色标。最后的迁移矩阵与能量曲线汇总表绘图属于本地小规模可视化检查，另记 [matrix_render_time.txt](stage125_energy_ml/matrix_render_time.txt) 和 [profile_render_time.txt](stage125_energy_ml/profile_render_time.txt)，未重新处理事件，不计入上面的 Condor 账本。相同 incoming 的配对响应见 [paired_response_shift.pdf](stage125_energy_ml/paired_response_shift.pdf)，其中色带为事件中央68%离散范围，不是置信区间。','']
    text=REPORT.read_text()
    marker='## 实际结果、阶段结论' if '## 实际结果、阶段结论' in text else '## 实际结果与物理解释'
    start=text.index(marker);end=text.index('## 复现与下一步',start)
    text=text[:start]+'\n'.join(lines)+'\n'+text[end:]
    text=text.replace('**本文件为执行中的阶段记录，实际结果和最终结论在作业结束后补全；当前不作鲁棒性通过判断。**','本阶段已完成兼容生产、固定模型推理、独立统计验证及图集。')
    REPORT.write_text(text)
    print('Updated',REPORT)


if __name__=='__main__':main()
