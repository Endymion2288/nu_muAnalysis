#!/usr/bin/env python3
"""Render measured integration tables as a compact Chinese physics report."""
import argparse
import csv
import json
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    out = args.report
    summary = json.loads((out / 'summary.json').read_text())
    lines = ['# 最新 master 几何旋转版：实测性能明细', '',
        f"源码 `{summary['source_commit']}`。{'全量' if summary['full_sample'] else '局部验证样本'}："
        f"{summary['common_events']:,} 个输入事件，{summary['fiducial']:,} 个 truth-fiducial，"
        f"{summary['accepted']:,} 个 truth-station-accepted proxy。未经权重修正。", '',
        'old 为 d32b0ff3；strict 为前阶段已验证的 strict 材料旋转版；latest 为合入官方 '
        '7f2d1681 master、保留旋转及 isolated smoothing 的本次版本。nominal 排除 alternate run 200080。', '',
        '局部 truth 参考是 SiHit 方向乘 HepMC 产生点动量模长，不能作为精确 G4 局部动量。'
        '动量残差定义为 reco/reference−1；MAD 为相对残差绝对值的中位数；宽度为 (q84−q16)/2。'
        '所有相对误差以无量纲量给出，例如 0.1 表示 10%。', '']

    def read(name):
        path = out / (name + '.tsv')
        if not path.exists():
            return []
        with path.open() as f:
            return list(csv.DictReader(f, delimiter='\t'))

    def filtered(name, **keys):
        return [r for r in read(name) if all(r.get(k) == str(v) for k, v in keys.items())]

    def table(title, rows, columns):
        lines.extend(['## ' + title, ''])
        if not rows:
            lines.extend(['该选择下未测量或无有效条目。', ''])
            return
        lines.append('| ' + ' | '.join(label for _, label in columns) + ' |')
        lines.append('| ' + ' | '.join('---' for _ in columns) + ' |')
        def display(value):
            text = str(value)
            if text.lower() in ['nan', 'inf', '-inf']:
                return text
            try:
                if '.' in text or 'e' in text.lower():
                    return f'{float(text):.6g}'
            except ValueError:
                pass
            return text.replace('|', '\\|')
        lines.extend('| ' + ' | '.join(display(r.get(k, '')) for k, _ in columns) + ' |' for r in rows)
        lines.append('')

    eff = read('efficiency')
    table('从完整共同输入开始的 Merge cutflow', filtered('full_input_cutflow', mode='merge'),
        [('version', '版本'), ('cut', 'cut'), ('passed', '通过'), ('initial', '原始输入分母')])
    lines.extend(['首六项仅依赖共同 RDO truth，使用本次计数作为所有版本共享的 truth 前缀；'
                  '重建选择部分分别从对应版本累计 cut bits 精确计算，latest 另与 worker 完整 cutflow 闭合。'
                  '这不是对旧版重新读取全部 RDO 的计数。', ''])
    stages = ['any_primary_raw', 'any_primary_long', 'any_primary_quality', 'correct_leader',
              'track_cuts', 'track_cuts_correct', 'final', 'final_correct', 'final_fixed_old_scintillator']
    table('Merge 接受度及正确 primary 效率',
        [r for r in eff if r['mode'] == 'merge' and r['group'] in ['all', 'nominal']
         and r['denominator_name'] == 'truth_station_acceptance' and r['stage'] in stages],
        [('version', '版本'), ('group', '样本'), ('stage', '阶段'), ('denominator', '分母'),
         ('passed', '通过'), ('failed', '未通过'), ('efficiency_percent', '效率 %'),
         ('wilson68_low_percent', '68% 下限 %'), ('wilson68_high_percent', '68% 上限 %')])
    table('Merge 同事件通过 / 丢失 / 新增',
        [r for r in filtered('paired_efficiency', mode='merge', denominator_name='truth_station_acceptance')
         if r['group'] in ['all', 'nominal']],
        [('baseline', '基线'), ('variant', '新版'), ('group', '样本'), ('stage', '阶段'),
         ('before', '基线通过'), ('after', '新版通过'), ('lost', '丢失'), ('gained', '新增'),
         ('delta_pp', '差值 pp'), ('low95_pp', '95% 下限 pp'), ('high95_pp', '95% 上限 pp'),
         ('mcnemar_p', 'McNemar p')])
    table('truth 可通过但 Merge 未通过的完整分类',
        filtered('truth_accepted_losses', mode='merge', group='all'),
        [('version', '版本'), ('category', '类别'), ('events', '事件'), ('denominator', 'truth 分母')])
    table('Merge 首个失败 cut（truth-accepted）', filtered('first_failed_cut', mode='merge', group='all'),
        [('version', '版本'), ('first_failed_cut', '首个失败 cut'), ('events', '事件'), ('denominator', 'truth 分母')])
    table('Merge 正确 primary 纯度',
        [r for r in filtered('selection_purity', mode='merge', group='all') if r['stage'] == 'correct_primary_purity0.7'],
        [('version', '版本'), ('denominator_name', '选择'), ('denominator', 'leaders'), ('passed', '正确 primary'),
         ('efficiency_percent', '纯度 %'), ('wilson68_low_percent', '68% 下限 %'), ('wilson68_high_percent', '68% 上限 %')])
    table('Merge 数值异常与电荷符号错误', filtered('numerical_and_charge', mode='merge', group='all'),
        [('version', '版本'), ('scope', '选择'), ('events', 'leaders'), ('nonfinite_chi2', '非有限 chi2'),
         ('nonpositive_ndof', 'ndof≤0'), ('nonfinite_pz', '非有限 pz'),
         ('primary_pairs', '正确 primary pairs'), ('primary_charge_flips', '符号错误')])
    table('Merge 最终粒子组成', filtered('particle_content', mode='merge', group='all', scope='final'),
        [('version', '版本'), ('particle_class', '粒子类别'), ('events', '事件'), ('denominator', '最终事件')])
    table('三站动量响应（Merge，正确 primary leader）',
        [r for r in filtered('station_residuals', mode='merge', group='all')
         if r['scope'] in ['matched_leader', 'matched_final_leader'] and r['metric'] in ['p_relative', 'pz_relative']],
        [('version', '版本'), ('station', '站'), ('scope', '选择'), ('metric', '量'), ('valid', 'pairs'),
         ('median', '偏差中位数'), ('central68_half_width', '68% 半宽'), ('median_absolute', 'MAD'),
         ('q68_absolute', '绝对误差 q68'), ('tail_absolute_gt_half', '|误差|>50%')])
    table('三站同事件动量准确度（Merge）',
        [r for r in filtered('paired_station_accuracy', mode='merge', group='all', scope='truth_accepted_common')
         if r['metric'] in ['p_relative', 'pz_relative']],
        [('baseline', '基线'), ('variant', '新版'), ('station', '站'), ('metric', '量'), ('pairs', 'pairs'),
         ('old_closer', '基线更近'), ('new_closer', '新版更近'), ('ties', '相同'),
         ('old_median_absolute', '基线 MAD'), ('new_median_absolute', '新版 MAD'), ('sign_p', 'sign p')])
    table('分动量区间的同事件准确度（Merge，truth-accepted，pz）',
        filtered('paired_momentum_bands', mode='merge', group='all', scope='truth_accepted_common', quantity='pz'),
        [('baseline', '基线'), ('variant', '新版'), ('station', '站'), ('low_gev', '下限 GeV'),
         ('high_gev', '上限 GeV'), ('pairs', 'pairs'), ('baseline_median_absolute', '基线 MAD'),
         ('variant_median_absolute', '新版 MAD'), ('baseline_closer', '基线更近'),
         ('variant_closer', '新版更近'), ('baseline_tail_gt_half', '基线尾部'),
         ('variant_tail_gt_half', '新版尾部'), ('sign_p', 'sign p')])
    table('三站动量 bin purity / stability / diagonal efficiency（Merge 最终样本）',
        [r for r in filtered('momentum_bin_purity', mode='merge', group='all', scope='final')
         if float(r['low_gev']) >= 100],
        [('version', '版本'), ('station', '站'), ('low_gev', '下限 GeV'), ('high_gev', '上限 GeV'),
         ('truth_accepted_events', 'truth 分母'), ('reco_bin_events', 'reco 分母'),
         ('momentum_bin_purity_percent', 'bin purity %'), ('bin_stability_percent', 'stability %'),
         ('accepted_diagonal_efficiency_percent', '对角效率 %')])
    lines.extend(['bin purity = 正确 primary 且 truth/reco 同 bin 的事件 / 该 reco bin 全部选中 leaders；'
                  'stability 的分母是对应 truth bin 的正确匹配 selected leaders；对角效率分母是 '
                  'truth-accepted 中该 truth bin 的事件。完整区间与 Wilson 误差见原始 TSV。', ''])
    table('duplicates：三种模式，全部 truth-accepted（purity≥0.7）',
        filtered('duplicates', group='all', denominator_name='truth_station_acceptance', purity_threshold='0.7'),
        [('version', '版本'), ('mode', '方法'), ('scope', '质量'), ('denominator', '事件分母'),
         ('matched_tracks', '匹配 tracks'), ('duplicate_events', 'duplicate events'),
         ('duplicate_groups', 'duplicate groups'), ('excess_tracks', '多余 tracks'),
         ('duplicate_event_percent', 'duplicate %')])
    table('primary duplicates：raw / long / quality',
        filtered('primary_duplicate_counts', mode='merge', group='all', denominator_name='truth_station_acceptance'),
        [('version', '版本'), ('scope', '质量'), ('matched_primary_events', '匹配事件'),
         ('duplicate_primary_events', '重复事件'), ('excess_primary_tracks', '多余 tracks'),
         ('duplicate_given_primary_match_percent', '条件重复率 %')])
    lines.extend(['duplicate 指同一事件、同一 truth barcode 被至少两条满足 hit-purity 阈值的轨迹匹配；'
                  '不是简单按轨迹数大于一计数。quality 要求 layers≥7、ndof≥9、有限 chi2 且 chi2/ndof<15，'
                  '不等同于完整事例选择。完整 TSV 同时保留 purity 0.5 / 0.7 / 0.9。', ''])
    table('Forward / Backward / Merge 的效率',
        [r for r in eff if r['group'] == 'all' and r['denominator_name'] == 'truth_station_acceptance'
         and r['stage'] in ['any_primary_quality', 'track_cuts', 'final', 'final_correct']],
        [('version', '版本'), ('mode', '方法'), ('stage', '阶段'), ('passed', '通过'),
         ('denominator', '分母'), ('efficiency_percent', '效率 %')])
    table('波形电荷逐值比较旧版', filtered('waveform_comparison', population='accepted'),
        [('version', '版本'), ('channel', '通道'), ('events', '事件'), ('exact_old_events', '逐值一致'),
         ('nonfinite', '非有限'), ('finite_negative', '有限负值'), ('maximum_finite_difference_pc', '最大差 pC')])
    table('各 run 的 Merge 最终结果',
        [r for r in eff if r['group'] not in ['all', 'nominal'] and r['mode'] == 'merge'
         and r['denominator_name'] == 'truth_station_acceptance' and r['stage'] == 'final'],
        [('version', '版本'), ('group', 'run'), ('denominator', '分母'), ('passed', '通过'), ('efficiency_percent', '效率 %')])
    if (out / 'momentum_tail_audit.tsv').exists():
        table('保留全部有限极端值的 Merge 动量尾部审计', read('momentum_tail_audit'),
            [('version', '版本'), ('station', '站'), ('scope', '选择'), ('pairs', 'pairs'),
             ('median', '绝对相对误差中位数'), ('q95', 'q95'), ('q99', 'q99'),
             ('mean', '算术均值'), ('maximum', '最大值'), ('error_gt_thousand', '|误差|>1000')])
        lines.extend(['上述相对误差无量纲。中位数、q95/q99 与 >50% 的尾部均明显改善，'
                      '但极少数巨大有限动量仍通过当前 cuts，足以恶化算术均值；不能声称所有误差指标都改善。'
                      '未截断或删除这些事件，run/event 与拟合质量见 `extreme_momentum_events.tsv`。', ''])
    residual = out / 'residual_audit.json'
    if residual.exists():
        audit = json.loads(residual.read_text())
        lines.extend(['## strict 与 latest 的少量非波形差异', '',
            f"全量有 {audit['strict_latest_changed_long_track_events']} 个 fiducial 事件的 long track 或状态数组不同，"
            f"合计 long tracks 差 {audit['strict_latest_long_track_delta']}；"
            f"event scalar 差 {audit['strict_latest_changed_event_scalar_cells']} 个单元。"
            '因此 pilot 的非波形数组精确相同不能外推到全量。事件与逐轨内容见 '
            '`strict_changed_track_events.json`，标量见 `strict_changed_scalars.tsv`。', '',
            '固定旧电荷后 strict / latest 的 accepted Merge final 为 102810 / 102807，'
            '丢失 3、新增 0。实际 final 为 101692 / 102807，净增加 1115；'
            '按固定电荷控制分解为恢复波形 +1118、少量轨迹差异 −3。'
            '尚未证实这 9 个事件的具体源码原因，不将静态 seed map 等候选问题写成已确认因果。', ''])
    replay_path = out / 'drift_replay_comparison.json'
    if replay_path.exists():
        replay = json.loads(replay_path.read_text())
        differences = {version: [k for k, value in rows.items() if not value['exact']]
                       for version, rows in replay['comparisons'].items()}
        lines.extend(['额外短片段重放（同一冻结源码及运行包，index 166、skip 2250、10 输入事件，'
                      '2 个 fiducial，含 200083:652256）与 strict 全量的差异数组为 '
                      f"`{', '.join(differences['strict_full'])}`；与 latest 全量为 "
                      f"`{', '.join(differences['latest_full'])}`。"
                      '即该片段重放的非波形 science arrays 与 strict 精确一致。'
                      '两个运行使用不同 worker，尚未区分事件历史、数值环境及未定义行为。'
                      '不能将它直接归因为一个固定的 master 配置变更。完整证据见 '
                      '`drift_replay_comparison.json`。', ''])
    performance = json.loads((out / 'performance_summary.json').read_text())
    rows = []
    for version, measured in performance.items():
        for step, value in measured['steps'].items():
            rows.append(dict(version=version, step=step, events=measured['events'], jobs=measured['jobs'], **value))
    table('全作业资源实测（各 worker wall 相加）', rows,
        [('version', '版本'), ('step', '步骤'), ('events', '事件'), ('jobs', 'jobs'),
         ('wall_total_s', '累计 wall s'), ('median_job_wall_s', 'job 中位 wall s'),
         ('max_rss_kib', '最大 RSS KiB'), ('events_per_summed_wall_s', 'events/s')])
    paired = out / 'paired_old_replay.json'
    if paired.exists():
        rows = []
        replay = json.loads(paired.read_text())
        totals = {version: {} for version in ['old', 'latest']}
        for job in replay:
            for version in ['old', 'latest']:
                for step in ['reco', 'forward', 'backward', 'merge', 'extract']:
                    value = job[version][step]
                    measured = dict(re.findall(r'(\w+)=(\d+(?:\.\d+)?)', value))
                    aggregate = totals[version].setdefault(step, dict(wall_s=0., cpu_s=0., max_rss_kib=0))
                    aggregate['wall_s'] += float(measured['wall_seconds'])
                    aggregate['cpu_s'] += float(measured['user_seconds']) + float(measured['system_seconds'])
                    aggregate['max_rss_kib'] = max(aggregate['max_rss_kib'], int(measured['max_rss_kib']))
                    rows.append(dict(index=job['index'], version=version, order=job['order'],
                                     host=job['host'], step=step, events=job['events'], **measured))
        table('同节点、交替顺序的旧版重放与计时', rows,
            [('index', 'index'), ('version', '版本'), ('order', '顺序'), ('host', 'worker'), ('step', '步骤'),
             ('events', '事件'), ('wall_seconds', 'wall s'), ('user_seconds', 'user s'), ('max_rss_kib', 'RSS KiB')])
        timing = dict(jobs=len(replay), events=sum(j['events'] for j in replay),
            all_old_cache_exact=all(j['exact_old_cache'] for j in replay), sums=totals,
            ratio_latest_over_old={step: {key: totals['latest'][step][key] / totals['old'][step][key]
                for key in ['wall_s', 'cpu_s']} for step in totals['old']})
        (out / 'paired_timing_summary.json').write_text(json.dumps(timing, indent=2) + '\n')
    lines.extend(['## 验证与可追溯数据', '',
        f"共同 truth 检查：{summary['exact_truth']}；全量输入 ID 检查：{summary['exact_all_ids']}；"
        f"分片 science arrays 回读恢复：{summary['exact_shard_science_readback']}；"
        f"全部 fiducial 波形与旧版逐值一致：{summary['exact_old_waveforms']}。", '',
        '完整统计见本目录 TSV，逐事件迁移见 `truth_accepted_migration_events.tsv`，'
        '局部 truth-pass/reco-fail 见 `local_cut_migrations.tsv`，材料与四个 smoothing 的实际配置见 '
        '`effective_configuration.json`，源码 provenance 见 `runtime_source_provenance.json`。'
        '误差条、nominal / 分 run 及阈值变化保留在原表，稀疏高能 bin 不作过度外推。', ''])
    lines.extend(['表中 p=0 是浮点数值下溢，不能解读为真实概率严格为零。', ''])
    (out / 'detailed_results.md').write_text('\n'.join(lines))
    print(out / 'detailed_results.md')


if __name__ == '__main__':
    main()
