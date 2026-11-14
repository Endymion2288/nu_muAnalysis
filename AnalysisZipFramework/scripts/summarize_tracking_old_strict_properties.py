#!/usr/bin/env python3
"""Render the measured old/strict property inventory tables for review."""
import csv
from collections import Counter
import json
from pathlib import Path
import sys


def enrich_event_table(out, repo):
    """Add all channel values for the small set of already identified migrations."""
    import numpy as np
    path=out/'waveform_changed_final_events.tsv'
    with path.open() as f: events=list(csv.DictReader(f,delimiter='\t'))
    if not events:return
    caches={}
    for version, name in [('old','workbook/stage203_station_truth/old.npz'),('strict','workbook/stage205_material/full/strict.npz')]:
        with np.load(repo/name) as z:
            keys=z['run'].astype(np.int64)*1000000000+z['eventID'].astype(np.int64)
            target=np.array([int(r['run'])*1000000000+int(r['eventID']) for r in events])
            idx=np.searchsorted(keys,target);assert np.array_equal(keys[idx],target)
            caches[version]=z['scintillator'][idx]
    channels=['Veto20','Veto21','Preshower0','Preshower1','VetoNu0_reduced','VetoNu1_reduced','Timing0','Timing1','Timing2','Timing3']
    for i,r in enumerate(events):
        for version in caches:
            for j,ch in enumerate(channels):r[version+'_'+ch+'_pc']=str(caches[version][i,j])
        if r['actual_final']=='True':
            c=caches['old'][i];failed=[]
            if not(c[0]>40 and c[1]>40):failed.append('veto')
            if not(c[2]>2.5 and c[3]>2.5):failed.append('preshower')
            if not c[4]<30:failed.append('VetoNu0')
            if not c[5]<30:failed.append('VetoNu1')
            # Current recovered sample has no old-only Timing failures.
            assert failed,(r['run'],r['eventID'],'unclassified old-waveform failure')
            r['failed_blocks']=','.join(failed)
            r['category']='old_preshower_below_threshold' if 'preshower' in failed else 'old_other_waveform'
        r['failed_waveform_version']='old' if r['actual_final']=='True' else 'strict'
    with path.open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(events[0]),delimiter='\t');w.writeheader();w.writerows(events)


def main():
    out = Path(sys.argv[1])
    if len(sys.argv)>2: enrich_event_table(out, Path(sys.argv[2]))
    lines = ['# Old/strict：电荷和接受度详细实测表', '',
        '所有计数未加权；accepted 分母为三站 truth acceptance proxy。电荷替换是缓存条件控制，未重建或修改任何波形。', '']
    def rows(name):
        return list(csv.DictReader((out/(name+'.tsv')).open(), delimiter='\t'))
    def show(title, headings, values):
        lines.extend(['## '+title, '', '| '+' | '.join(headings)+' |', '| '+' | '.join(['---']*len(headings))+' |'])
        for row in values:
            cells=[]
            for value in row:
                if isinstance(value, float): value=f'{value:.5f}'
                cells.append(str(value).replace('|', chr(92)+'|'))
            lines.append('| '+' | '.join(cells)+' |')
        lines.append('')
    selected=lambda r:r['group']=='accepted'
    x=rows('four_corner_efficiency')
    show('相同事件四种 tracking/waveform 组合', ['方法','轨迹和 Timing Y','波形电荷','最终事件','相对 old 损失','新增','效率差 pp','配对95% CI pp'],
        [[r['mode'],r['tracking'],r['waveform'],r['after'],r['lost'],r['gained'],float(r['delta_pp']),f"{float(r['low95_pp']):.5f}～{float(r['high95_pp']):.5f}"] for r in x if selected(r)])
    x=rows('charge_distributions')
    show('通道电荷分布与异常，单位 pC', ['通道','版本','NaN','+Inf','−Inf','有限负值','0.1%','中位数','99%','99.9%'],
        [[r['channel'],r['version'],r['nan'],r['posinf'],r['neginf'],r['finite_negative'],float(r['q001_pc']),float(r['median_pc']),float(r['q99_pc']),float(r['q999_pc'])] for r in x if selected(r)])
    x=rows('channel_threshold_migrations')
    show('单通道阈值迁移，包含非有限值的实际比较结果', ['通道','阈值 pC','旧通过','strict通过','旧通过/strict失败','旧失败/strict通过'],
        [[r['channel'],r['threshold_pc'],r['before'],r['after'],r['lost'],r['gained']] for r in x if selected(r)])
    x=rows('single_channel_replacement')
    show('固定 strict 轨迹，仅换一通道为旧电荷', ['方法','通道','strict原通过','替换后通过','丢失','恢复','净效率 pp'],
        [[r['mode'],r['channel'],r['before'],r['after'],r['lost'],r['gained'],float(r['delta_pp'])] for r in x if selected(r)])
    x=rows('waveform_shapley')
    show('五组电荷的全部32种组合：跨替换顺序平均边际恢复', ['方法','电荷组','平均边际恢复事件','效率 pp'],
        [[r['mode'],r['block'],float(r['average_marginal_restored_events']),float(r['efficiency_pp'])] for r in x if selected(r)])
    events=rows('waveform_changed_final_events'); counts=Counter((r['mode'],r['actual_final'],r['category']) for r in events)
    show('固定 strict tracking，全部换旧电荷的 final 迁移互斥分类', ['方法','actual strict final','类型（优先非有限、负值、其余）','事件数'],
        [[*k,n] for k,n in sorted(counts.items())])
    x=rows('tracking_stage_migrations')
    show('轨迹效率各层迁移', ['方法','层级','old事件','strict事件','丢失','新增','效率差 pp'],
        [[r['mode'],r['stage'],r['before'],r['after'],r['lost'],r['gained'],float(r['delta_pp'])] for r in x if selected(r)])
    x=rows('forward_backward_overlap')
    show('Forward/backward 的互补性', ['版本','层级','事件集合','事件数'],
        [[r['version'],r['stage'],r['population'],r['events']] for r in x if selected(r) and r['stage'] in ['primary_raw','primary_long','has_long','track_cuts','fixed_old_waveform']])
    x=rows('fixed_waveform_cutflow')
    show('固定旧电荷后的 cutflow；首失败互斥', ['方法','版本','cut','单cut通过','累计通过','首失败'],
        [[r['mode'],r['version'],r['cut'],r['individual_pass'],r['cumulative_pass'],r['first_failed']] for r in x if selected(r)])
    x=rows('single_cut_removal_diagnostic')
    show('固定旧电荷，仅移去一项轨迹cut的敏感性（诊断，不代表可接受修改）', ['方法','版本','移去cut','额外通过事件'],
        [[r['mode'],r['version'],r['removed_cut'],r['extra_events']] for r in x if selected(r)])
    x=rows('timing_y_charge_controls')
    show('Timing 位置和电荷四组合', ['方法','Timing Y版本','电荷版本','Timing单cut通过','仅替换Timing后的strict final'],
        [[r['mode'],r['y_version'],r['waveform'],r['timing_pass'],r['final_replacing_only_timing']] for r in x if selected(r)])
    x=rows('track_charge_sign')
    show('轨迹正负电荷识别（全 fiducial，正确主μ，purity≥0.7）', ['方法','版本','选择','truth pz下限 GeV','上限 GeV','主μ样本','错误sign'],
        [[r['mode'],r['version'],r['scope'],r['truth_pz_low_gev'],r['truth_pz_high_gev'],r['matched_primary_events'],r['wrong_charge']] for r in x if r['group']=='fiducial' and r['scope'] in ['final','fixed_final']])
    (out/'detailed_results.md').write_text('\n'.join(lines)+'\n')
    print(out/'detailed_results.md')


if __name__=='__main__': main()
