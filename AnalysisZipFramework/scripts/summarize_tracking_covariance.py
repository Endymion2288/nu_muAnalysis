#!/usr/bin/env python3
"""Render the measured three-configuration tables as a Chinese report."""
import argparse
import csv
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(); out = args.report
    summary = json.loads((out / 'summary.json').read_text())
    lines = ['# 旧版与几何旋转两组 seed covariance：实测明细', '',
        f"{'全量' if summary['full_sample'] else '小样本验证'}：{summary['input_events']:,} input events，"
        f"{summary['fiducial']:,} truth-fiducial，{summary['accepted']:,} truth-accepted proxy。", '',
        '`old`：旋转前 d32b0ff3；`large`：latestMaster 7fd40df8，inflation '
        '[100,100,100,10000,100000]；`small`：同一旋转源码，inflation [100,100,100,100,1000]。'
        '两种旋转版本共用 strict rowmajor 材料图与 isolated smoothing，仅改变 θ、q/p 种子方差。', '',
        'Station 1/2/3 动量参考为 SiHit 方向乘 HepMC 产生点动量模长，没有 G4 局部输运动量。'
        '相对误差无量纲；0.1 表示 10%。中位绝对误差表示 |reco/reference−1| 的中位数。'
        '正确 primary 指 barcode/PDG 对应主粒子且 hit purity≥0.7，不额外要求动量或电荷符号正确。', '',
        'old / large 复用已验证全样本，small 新重建。所有共同输入 ID、truth、波形电荷、'
        'small 分片回读及实际材料 / covariance / isolation 设置已验证。nominal 排除 alternate run 200080。', '']

    def read(name):
        with (out / (name + '.tsv')).open() as stream:
            return list(csv.DictReader(stream, delimiter='\t'))

    def filtered(name, **keys):
        return [r for r in read(name) if all(r[k] == str(value) for k, value in keys.items())]

    def table(title, rows, columns):
        lines.extend(['## ' + title, ''])
        if not rows:
            lines.extend(['该选择没有有效条目，未测量。', '']); return
        def display(value):
            try:
                if '.' in str(value) or 'e' in str(value).lower():
                    return f'{float(value):.7g}'
            except ValueError:
                pass
            return str(value).replace('|', '\\|')
        lines.extend(['| ' + ' | '.join(label for _, label in columns) + ' |',
                      '| ' + ' | '.join('---' for _ in columns) + ' |'])
        lines.extend('| ' + ' | '.join(display(r[key]) for key, _ in columns) + ' |' for r in rows)
        lines.append('')

    efficiencies = filtered('efficiency', group='all', denominator_name='truth_station_acceptance')
    table('真实主粒子与最终重建效率', [r for r in efficiencies if r['stage'] in
        ['any_primary_raw', 'any_primary_long', 'any_primary_quality', 'correct_leader', 'final', 'final_correct']],
        [('version','版本'),('mode','方法'),('stage','阶段'),('passed','通过'),('failed','未通过'),
         ('denominator','分母'),('efficiency_percent','效率 %')])
    table('同事件最终通过与丢失', [r for r in filtered('paired_efficiency', group='all',
        denominator_name='truth_station_acceptance') if r['stage'] in ['final','final_correct']],
        [('baseline','基线'),('variant','对照'),('mode','方法'),('stage','阶段'),('before','基线通过'),
         ('after','对照通过'),('lost','丢失'),('gained','新增'),('delta_pp','差值 pp'),
         ('low95_pp','95% 下限'),('high95_pp','95% 上限'),('mcnemar_p','McNemar p')])
    table('Nominal 最终效率', [r for r in filtered('efficiency', group='nominal',
        denominator_name='truth_station_acceptance') if r['stage'] in ['final','final_correct']],
        [('version','版本'),('mode','方法'),('stage','阶段'),('passed','通过'),('denominator','分母'),('efficiency_percent','效率 %')])
    table('三者共同正确 leaders 的 Station 精度（不要求 final）', filtered('common_cohort_station_accuracy', scope='truth_accepted_common'),
        [('version','版本'),('mode','方法'),('station','站'),('valid','共同 pairs'),('median_absolute','中位绝对误差'),
         ('median','偏差中位数'),('central68_half_width','中央 68% 半宽'),('tail_absolute_gt_half','|误差|>50%')])
    table('三者共同最终正确轨迹的 Station 精度（truth-accepted）', filtered('three_way_final_station_accuracy', group='all'),
        [('version','版本'),('mode','方法'),('station','站'),('valid','共同 pairs'),('median_absolute','中位绝对误差'),
         ('median','偏差中位数'),('central68_half_width','中央 68% 半宽'),('tail_absolute_gt_half','|误差|>50%')])
    table('三者共同最终正确事件的 S1 分动量精度', filtered('three_way_momentum_bands', group='all', station=1, scope='all_final_correct'),
        [('version','版本'),('mode','方法'),('low_gev','下限 GeV'),('high_gev','上限 GeV'),
         ('common_pairs','共同 pairs'),('median_absolute','中位绝对误差'),('q95','绝对误差 q95'),('tail_gt_half','|误差|>50%')])
    table('两两配对 S1 精度', filtered('paired_station_accuracy', group='all',
        scope='truth_accepted_common', station=1, metric='pz_relative'),
        [('baseline','基线'),('variant','对照'),('mode','方法'),('pairs','pairs'),
         ('old_median_absolute','基线中位绝对误差'),('new_median_absolute','对照中位绝对误差'),
         ('old_closer','基线更近'),('new_closer','对照更近'),('sign_p','sign p')])
    table('最终正确 primary 的 S1 尾部（truth-accepted）', filtered('momentum_tail_audit',
        scope='accepted_final_correct', station=1),
        [('version','版本'),('mode','方法'),('pairs','pairs'),('median','中位绝对误差'),('q95','q95'),('q99','q99'),
         ('mean','绝对误差均值'),('maximum','最大绝对误差'),('error_gt_half','>0.5'),('error_gt_ten','>10'),('error_gt_thousand','>1000')])
    table('最终选择的 primary 身份纯度', filtered('selection_purity', group='all',
        denominator_name='final', stage='correct_primary_purity0.7'),
        [('version','版本'),('mode','方法'),('denominator','最终 leaders'),('passed','正确 primary'),
         ('efficiency_percent','纯度 %')])
    table('最终选择的数值与电荷符号', filtered('numerical_and_charge', group='all', scope='final'),
        [('version','版本'),('mode','方法'),('events','最终 leaders'),('nonfinite_chi2','非有限 χ²'),
         ('nonpositive_ndof','ndof≤0'),('nonfinite_pz','非有限 pz'),('primary_pairs','正确 primary'),('primary_charge_flips','电荷符号错误')])
    table('同事件最终正确轨迹的命中点与电荷变化', filtered('paired_track_properties', scope='both_final_correct'),
        [('baseline','基线'),('variant','对照'),('mode','方法'),('pairs','共同事件'),
         ('measurements_fewer','测量点减少'),('measurements_equal','测量点相同'),('measurements_more','测量点增加'),
         ('charge_disagreements','电荷符号不同'),('wrong_to_right_charge','错→对'),('right_to_wrong_charge','对→错')])
    table('Merge 三站最终动量 bin 指标', [r for r in filtered('momentum_bin_purity',
        group='all', mode='merge', scope='final') if float(r['low_gev']) >= 100],
        [('version','版本'),('station','站'),('low_gev','下限 GeV'),('high_gev','上限 GeV'),
         ('truth_accepted_events','truth 分母'),('reco_bin_events','reco 分母'),
         ('momentum_bin_purity_percent','bin purity %'),('bin_stability_percent','stability %'),
         ('accepted_diagonal_efficiency_percent','对角效率 %')])
    table('Duplicates（同 barcode，hit purity≥0.7）', filtered('duplicates', group='all',
        denominator_name='truth_station_acceptance', purity_threshold='0.7'),
        [('version','版本'),('mode','方法'),('scope','质量'),('duplicate_events','重复事件'),
         ('excess_tracks','多余 tracks'),('denominator','事件分母')])
    table('Primary raw / long / quality 重复', filtered('primary_duplicate_counts', group='all',
        denominator_name='truth_station_acceptance'),
        [('version','版本'),('mode','方法'),('scope','质量'),('matched_primary_events','匹配事件'),
         ('duplicate_primary_events','重复事件'),('excess_primary_tracks','多余 tracks')])
    table('两两版本的损失分类', read('version_loss_causes'),
        [('baseline','基线'),('variant','对照'),('mode','方法'),('migration','迁移'),('category','类别'),('events','事件'),('total','总迁移')])
    table('truth 可通过但 reco 首先失败的位置', filtered('first_failed_cut', group='all'),
        [('version','版本'),('mode','方法'),('first_failed_cut','首个失败 cut'),('events','事件'),('denominator','truth 分母')])
    lines.extend(['## 图表', '', '![三者共同事件精度](common_station_accuracy.png)', '',
        '![动量 bin 指标](momentum_bin_metrics.png)', '', '![动量分布](momentum_spectra.png)', '',
        '完整分 run、三站 p/pz、cutflow、粒子组成、所有配对迁移与资源使用数据保存在同目录 TSV / JSON。'
        '身份纯度与动量 bin purity 含义不同；本样本不能直接给出完整背景污染率。'
        '尾部保留有限极端值，图显示范围不表示已删除溢出事件。', ''])
    (out / 'detailed_results.md').write_text('\n'.join(lines).rstrip() + '\n')


if __name__ == '__main__':
    main()
