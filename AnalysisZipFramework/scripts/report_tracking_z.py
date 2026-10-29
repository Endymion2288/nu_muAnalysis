#!/usr/bin/env python3
"""Plot paired tracking efficiencies against the true interaction z in mm."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from compare_tracking import MODES, PAIRS, Z_EDGES, selection
from report_tracking_comparison import COLORS, figure_save, fraction, save_table, wilson


def load_events(manifest, reference, output, combined=None):
    records = [line.split('\t') for line in manifest.read_text().splitlines()]
    with np.load(reference) as source:
        ref = {k: source[k] for k in source.files}
    reference_rows = {int(index): i for i, index in enumerate(ref['manifest_indices'])}
    if combined:
        with np.load(combined) as source:
            data = {k: source[k] for k in source.files}
        assert np.array_equal(data['manifest_indices'], [int(r[0]) for r in records])
    else:
        def read(record):
            with np.load(record[5]) as source:
                part = {k: source[k] for k in source.files}
            i = reference_rows[int(record[0])]
            assert int(part['reference_verified']) == 1
            assert int(part['nontrack_columns']) == 17
            assert int(part['manifest_index']) == int(record[0])
            for key in ('counts', 'overlaps'):
                assert np.array_equal(part[key], ref[key][i]), (record[0], key)
            return part
        with ThreadPoolExecutor(max_workers=4) as pool:
            parts = list(pool.map(read, records))
        keys = [k for k in parts[0] if k.startswith('event_')]
        data = {key: np.concatenate([p[key] for p in parts], axis=0) for key in keys}
        data['manifest_indices'] = np.array([int(r[0]) for r in records])
        data['file_offsets'] = np.r_[0, np.cumsum([len(p['event_run']) for p in parts])]
    fi = int(ref['fiducial_index'][0])
    n_reco = ref['counts'].shape[-1] - fi - 1
    assert n_reco <= 16
    bits = data['event_cut_bits']
    assert np.all(bits < 1 << n_reco)
    assert np.all((bits & (bits.astype(np.uint32)+1)) == 0), 'cuts must be cumulative'
    for row, record in enumerate(records):
        i = reference_rows[int(record[0])]
        start, stop = data['file_offsets'][row:row+2]
        assert stop-start == ref['counts'][i, 0, fi]
        assert np.all(data['event_run'][start:stop] == int(record[1]))
        passed = (bits[start:stop, :, None] >> np.arange(n_reco)) & 1
        assert np.array_equal(passed.sum(axis=0), ref['counts'][i, :, fi+1:])
    ids = np.rec.fromarrays([data['event_run'], data['event_eventID']])
    assert len(np.unique(ids)) == len(ids), 'duplicate paired events'
    np.savez_compressed(output / 'fiducial_events.npz', **data)
    return data, fi, int(ref['tracking_index'][0]), len(records)


def report(repo, manifest, reference, output, combined=None):
    output.mkdir(parents=True, exist_ok=True)
    data, fi, ti, files = load_events(manifest, reference, output, combined)
    cuts, _ = selection(repo)
    names = [name for name, _ in cuts][fi:]
    z = data['event_truth_dec_z_nu']
    bits = data['event_cut_bits']
    passed = ((bits[:, :, None] >> np.arange(len(names))) & 1).astype(bool)
    den = np.histogram(z, Z_EDGES)[0]
    assert den.sum() == len(z)
    hist = np.array([[np.histogram(z[passed[:, m, j]], Z_EDGES)[0]
                      for j in range(len(names))] for m in range(3)])
    assert np.array_equal(hist.sum(axis=-1), passed.sum(axis=0))
    previous = np.concatenate([np.broadcast_to(den, (3, 1, len(den))), hist[:, :-1]], axis=1)
    rows, paired_rows = [], []
    for b in range(len(den)):
        for j, name in enumerate(names):
            for m, mode in enumerate(MODES):
                n, d = int(hist[m, j, b]), int(den[b])
                lo, hi = wilson(n, d)
                rows.append(dict(z_low_mm=Z_EDGES[b], z_high_mm=Z_EDGES[b+1],
                                 cut=name, mode=mode, denominator=d, passed=n,
                                 truth_efficiency_percent=100*fraction(n, d),
                                 wilson_low_percent=100*lo, wilson_high_percent=100*hi,
                                 previous_passed=int(previous[m, j, b]),
                                 conditional_efficiency_percent=100*fraction(n, previous[m, j, b])))
    for left, right in PAIRS:
        for j, name in enumerate(names):
            a, b = passed[:, left, j], passed[:, right, j]
            only_left = np.histogram(z[a & ~b], Z_EDGES)[0]
            only_right = np.histogram(z[~a & b], Z_EDGES)[0]
            both = np.histogram(z[a & b], Z_EDGES)[0]
            delta = fraction(only_right-only_left, den)
            error = np.sqrt(fraction(fraction(only_left+only_right, den)-delta**2, den))
            for k in range(len(den)):
                paired_rows.append(dict(z_low_mm=Z_EDGES[k], z_high_mm=Z_EDGES[k+1],
                                        cut=name, pair=f'{MODES[right]}-{MODES[left]}',
                                        denominator=int(den[k]), first_only=int(only_left[k]),
                                        second_only=int(only_right[k]), both=int(both[k]),
                                        delta_percentage_points=100*delta[k],
                                        paired_se_percentage_points=100*error[k]))
    save_table(output/'z_bins.tsv', list(rows[0]), rows)
    save_table(output/'z_paired_differences.tsv', list(paired_rows[0]), paired_rows)
    stages = [0, ti-fi-1, len(names)-1]
    titles = ['At least one long track', 'Through theta cut (incl. scintillators)', 'Full selection']
    plt.rcParams.update({'font.size':10, 'axes.spines.top':False, 'axes.spines.right':False,
                         'svg.fonttype':'none'})
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=True)
    x = (Z_EDGES[:-1]+Z_EDGES[1:])/2
    for ax, stage, title in zip(axes, stages, titles):
        for m, mode in enumerate(MODES):
            value = fraction(hist[m, stage], den)
            lo, hi = wilson(hist[m, stage], den)
            ax.errorbar(x, 100*value, yerr=100*np.vstack([np.maximum(0, value-lo),
                                                        np.maximum(0, hi-value)]),
                        fmt='o-', ms=4, capsize=2, color=COLORS[m], label=mode)
        ax.axvspan(-1950, -1769.65, facecolor='#eeeeee', hatch='///', edgecolor='#cccccc')
        ax.axvline(-1769.65, color='grey', lw=.7)
        ax.set_title(title); ax.set_xlabel('Truth neutrino interaction z (mm)')
        ax.set_xlim(-3020, -1599); ax.set_ylim(0, 105); ax.grid(alpha=.25)
        ax.tick_params(axis='x', labelrotation=30)
    axes[0].set_ylabel('Pass / common truth-fiducial denominator (%)')
    axes[-1].legend()
    fig.suptitle(f'{files} paired RDOs · {len(z):,} truth-fiducial events · 68% Wilson intervals\n'
                 'FASERnu box: -3000 < z < -1950 mm; lead block: -1769.65 < z < -1619.65 mm')
    fig.tight_layout(); figure_save(fig, output, 'efficiency_vs_z')

    fig, axes = plt.subplots(1, 3, figsize=(16, 8), sharey=True, constrained_layout=True)
    for m, ax in enumerate(axes):
        image = ax.pcolormesh(Z_EDGES, np.arange(len(names)+1),
                             100*fraction(hist[m], previous[m]), vmin=0, vmax=100,
                             cmap='viridis', shading='flat', rasterized=True)
        ax.set_facecolor('#dddddd'); ax.set_title(MODES[m])
        ax.set_xlabel('Truth interaction z (mm)'); ax.tick_params(axis='x', labelrotation=30)
    axes[0].set_yticks(np.arange(len(names))+.5, names); axes[0].invert_yaxis()
    fig.colorbar(image, ax=axes, label='Conditional efficiency relative to previous cut (%)', shrink=.8)
    fig.suptitle('Existing reco cuts, in repository order · grey: no denominator events')
    figure_save(fig, output, 'conditional_cut_efficiency_vs_z')

    regions = []
    for name, low, high in [('FASERnu_box', -3000, -1950), ('lead_block', -1769.65, -1619.65)]:
        mask = (z > low) & (z < high)
        for j, title in zip(stages, titles):
            for m, mode in enumerate(MODES):
                regions.append(dict(region=name, z_low_mm=low, z_high_mm=high, stage=title,
                                    mode=mode, denominator=int(mask.sum()),
                                    passed=int(np.count_nonzero(mask & passed[:, m, j])),
                                    efficiency_percent=100*fraction(np.count_nonzero(mask & passed[:, m, j]), mask.sum())))
    save_table(output/'z_regions.tsv', list(regions[0]), regions)
    lines = ['# 三种 tracking 策略的效率随真值相互作用 Z 变化', '',
             f'与阶段 09 相同的 {files} 个 RDO，公共真值分母 {len(z):,} 个事件。', '',
             '`truth_dec_z_nu = truth_dec_z[0]`，单位 mm，表示入射中微子的真值相互作用点；'
             '不使用重建 track 的起点或外推 z。沿用 |PDG|=14、CC 和原有 fiducial/pz cuts。', '',
             '![Z efficiency](efficiency_vs_z.png)', '',
             '左、中、右分别累计到 long-track、theta、完整选择；分母均为对应 Z bin 的共同真值事件数。'
             '误差为 68% Wilson 区间，不含系统误差。', '',
             '阴影区是原分析 FASERν box 与 lead block 之间的真值选择空隙；没有分母，效率未定义，'
             '不连线插值、不画成零效率。box 使用 100 mm 分箱（最后一档 50 mm），lead block 使用 50 mm 分箱。', '',
             '![Conditional cuts](conditional_cut_efficiency_vs_z.png)', '',
             '热图展示全部 14 个重建阶段 cut 的逐步效率：本行通过数 / 同模式上一行通过数；'
             '首行分母为共同真值事件数。灰色表示分母为零。', '',
             '`z_bins.tsv` 提供所有 cut、模式、分箱计数与两种效率；`z_paired_differences.tsv` '
             '提供同事件模式差值和配对统计 SE；`z_regions.tsv` 提供 box/lead 的分区域统计。', '',
             '全样本为未加权比较，包含 SIBYLL 替代样本；不是标称 flux 预测或 truth-matched 单 muon 径迹效率。', '',
             '精简的 `fiducial_events.npz` 只保存共同真值事件的 run/eventID、truth pz/x/y/z 和三模式 uint16 cut 位掩码；'
             '可直接补充坐标图，不保留重复 ROOT ntuple 或 xAOD。', '']
    (output/'comparison_z.md').write_text('\n'.join(lines))
    print(f'reported z: files={files} truth={len(z)} denominator={den.tolist()}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--combined', type=Path)
    args = parser.parse_args()
    report(args.repo, args.manifest, args.reference, args.output, args.combined)
