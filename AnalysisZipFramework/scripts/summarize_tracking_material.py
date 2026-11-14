#!/usr/bin/env python3
"""Render the measured full-production tables into Chinese comparison tables."""
import argparse
import csv
import json
from pathlib import Path

VERSIONS = ['old','new','afs','strict']
MODES = ['forward','backward','merge']
LABELS = {'old':'旧版','new':'原生新版','afs':'新版＋AFS 原图','strict':'新版＋严格坐标图'}


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('report',type=Path); args = p.parse_args()
    root = args.report; text = ['# 材料图全量比较：详细实测表','',
        '版本：old=旧版，new=原生新版，afs=指定 AFS 原图，strict=手算图修正 JSON 矩阵序列化。所有计数均未加权。',
        'Station truth reference 为 SiHit 方向 × HepMC 产生动量大小，不是 G4 站内输运动量。','']
    def read(name):
        with (root/name).open() as f:return list(csv.DictReader(f,delimiter='\t'))
    def get(rows,**keys):
        selected=[r for r in rows if all(r[k]==str(v) for k,v in keys.items())]
        assert len(selected)==1,(keys,len(selected));return selected[0]
    def number(x,scale=1):return f'{float(x)*scale:.4f}'
    def render(title,headers,rows):
        escape=lambda x:str(x).replace('|',chr(92)+'|')
        text.extend(['## '+title,'','| '+' | '.join(escape(x) for x in headers)+' |','|'+'|'.join(['---']*len(headers))+'|'])
        text.extend('| '+' | '.join(escape(x) for x in r)+' |' for r in rows);text.append('')
    efficiency=read('efficiency.tsv');purity=read('selection_purity.tsv');paired=read('paired_efficiency.tsv')
    rows=[]
    for v in VERSIONS:
        for m in MODES:
            e=get(efficiency,version=v,group='all',denominator_name='truth_station_acceptance',mode=m,stage='final')
            c=get(efficiency,version=v,group='all',denominator_name='truth_station_acceptance',mode=m,stage='final_correct')
            f=get(efficiency,version=v,group='all',denominator_name='truth_station_acceptance',mode=m,stage='final_fixed_old_scintillator')
            q=get(purity,version=v,group='all',denominator_name='final',mode=m,stage='correct_primary_purity0.7')
            rows.append([LABELS[v],m,e['passed'],e['failed'],number(e['efficiency_percent']),c['passed'],f['passed'],number(q['efficiency_percent'])])
    render('Truth-accepted 分母内的最终通过、损失及全 fiducial 最终样本纯度',
           ['版本','方法','通过事件','未通过事件','效率 %','通过且正确主 μ','固定旧电荷通过','最终主 μ 纯度 %'],rows)
    rows=[]
    for base,v in [('old','new'),('old','afs'),('old','strict'),('new','afs'),('new','strict'),('afs','strict')]:
        for m in MODES:
            for stage in ['final','fixed_final']:
                r=get(paired,baseline=base,variant=v,group='all',denominator_name='truth_station_acceptance',mode=m,stage=stage)
                rows.append([base+'→'+v,m,stage,r['before'],r['after'],r['lost'],r['gained'],number(r['delta_pp']),number(r['low95_pp'])+'～'+number(r['high95_pp'])])
    render('同事件效率迁移；差为百分点，区间为配对 95% CI',
           ['比较','方法','电荷口径','前','后','损失','新增','净变化 pp','95% CI pp'],rows)
    common=read('common_cohort_station_accuracy.tsv');rows=[]
    for m in MODES:
        for st in [1,2,3]:
            for scope in ['common_primary_leaders','truth_accepted_common','all_final']:
                rs=[get(common,version=v,mode=m,station=st,scope=scope) for v in VERSIONS]
                assert len({r['valid'] for r in rs})==1
                rows.append([m,st,scope,rs[0]['valid']]+[number(r['median_absolute'],100) for r in rs])
    render('四组共同主 μ 的同站 pz 绝对相对误差中位数 %',
           ['方法','Station','共同选择','配对数']+[LABELS[v] for v in VERSIONS],rows)
    residual=read('station_residuals.tsv');rows=[]
    for v in VERSIONS:
        for m in MODES:
            for st in [1,2,3]:
                rs=[get(residual,version=v,group='all',mode=m,station=st,scope='matched_leader',metric=k) for k in ['p_relative','qop_normalized','slope_mrad','xy_mm']]
                rows.append([LABELS[v],m,st,rs[0]['valid'],number(rs[0]['median_absolute'],100),number(rs[1]['median_absolute'],100),number(rs[2]['median']),number(rs[3]['median'])])
    render('正确主 μ leader 的动量、带电 q/p、方向和位置；各组自身候选',
           ['版本','方法','Station','有效 p 对数','|Δp/p| 中位 %','归一化 |Δ(q/p)| 中位 %','方向差中位 mrad','横向差中位 mm'],rows)
    migrations=read('local_cut_migrations.tsv');rows=[]
    for m in MODES:
        for st in [1,2,3]:
            for cut in ['pz_gt100GeV','r_lt95mm','theta_lt25mrad']:
                rs=[get(migrations,version=v,group='all',mode=m,station=st,scope='all_primary_truth',cut=cut) for v in VERSIONS]
                assert len({r['truth_pass'] for r in rs})==1
                rows.append([m,st,cut,rs[0]['truth_pass']]+[r['truth_pass_reco_fail'] for r in rs]+[rs[-1]['truth_pass_missing_local_fit']])
    render('单个局部 cut：truth 通过而重建失败；包含缺失拟合',
           ['方法','Station','cut','truth 通过']+[LABELS[v]+' 失败' for v in VERSIONS]+['strict 中缺局部拟合'],rows)
    primary=read('primary_duplicate_counts.tsv');generic=read('duplicates.tsv');rows=[]
    for v in VERSIONS:
        for m in MODES:
            rs=[get(primary,version=v,mode=m,scope=s,group='all',denominator_name='fiducial') for s in ['raw','long','quality']]
            rows.append([LABELS[v],m]+[r['duplicate_primary_events'] for r in rs]+[r['excess_primary_tracks'] for r in rs])
    render('主 μ duplicate：hit purity≥0.7；truth-fiducial 分母',
           ['版本','方法','raw 重复事件','long 重复事件','quality 重复事件','raw 多余轨迹','long 多余轨迹','quality 多余轨迹'],rows)
    rows=[]
    for v in VERSIONS:
        for m in MODES:
            rs=[get(generic,version=v,mode=m,scope=s,purity_threshold=.7,group='all',denominator_name='fiducial') for s in ['long','quality']]
            rows.append([LABELS[v],m]+[r['duplicate_events'] for r in rs]+[r['excess_tracks'] for r in rs])
    render('所有粒子的 truth-matched duplicate：hit purity≥0.7',
           ['版本','方法','long 重复事件','quality 重复事件','long 多余轨迹','quality 多余轨迹'],rows)
    modepairs=read('mode_efficiency_migrations.tsv');rows=[]
    for v in VERSIONS:
        for left,right in [('forward','merge'),('backward','merge')]:
            for stage in ['final','fixed_final']:
                r=get(modepairs,version=v,left=left,right=right,stage=stage,group='all',denominator_name='fiducial')
                rows.append([LABELS[v],left+'→'+right,stage,r['lost'],r['gained'],number(r['delta_pp']),number(r['low95_pp'])+'～'+number(r['high95_pp'])])
    render('Merge 相对单方向方法：truth-fiducial 同事件迁移',
           ['版本','比较','电荷口径','单向通过 M 失败','M 新增','净变化 pp','95% CI pp'],rows)
    bins=read('momentum_bin_purity.tsv');rows=[]
    for m in MODES:
        for r in [r for r in bins if r['version']=='strict' and r['group']=='all' and r['mode']==m and r['station']=='1' and r['scope']=='final']:
            rs=[get(bins,version=v,group='all',mode=m,station=1,scope='final',low_gev=r['low_gev'],high_gev=r['high_gev']) for v in VERSIONS]
            rows.append([m,r['low_gev']+'～'+r['high_gev']]+[number(q['momentum_bin_purity_percent']) for q in rs]+[number(r['bin_stability_percent']),number(r['accepted_diagonal_efficiency_percent'])])
    render('Station 1 最终样本的动量 bin 纯度、稳定性及对角效率 %',
           ['方法','pz bin GeV']+[LABELS[v]+' 纯度' for v in VERSIONS]+['strict 稳定性','strict 对角效率'],rows)
    perf=json.loads((root/'performance_summary.json').read_text());rows=[]
    for v,d in perf.items():
        for step,s in d['steps'].items():
            rows.append([v,d['jobs'],d['events'],step,number(s['wall_total_s']),number(s['median_job_wall_s']),number(s['events_per_summed_wall_s']),number(s['max_rss_kib']/1024)])
    render('实际性能；墙钟为各作业该阶段时间之和，非整个 campaign 挂钟',
           ['材料图','作业数','事件数','阶段','墙钟合计 s','作业中位 s','events/合计 s','最大 RSS MiB'],rows)
    text += ['全部三站、逐 run、nominal、各阈值、cutflow、迁移矩阵、覆盖率和事件清单见本目录 TSV。',
             '完整 G4 局部动量、真实 data、加 flux 权重的产额和系统误差：未测量。','']
    (root/'detailed_results.md').write_text('\n'.join(text))
    print(root/'detailed_results.md')


if __name__=='__main__':main()
