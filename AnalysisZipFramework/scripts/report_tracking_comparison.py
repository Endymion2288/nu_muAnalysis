#!/usr/bin/env python3
"""Combine paired tracking summaries into cutflow tables and scientific figures."""

import argparse
import csv
from pathlib import Path
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from compare_tracking import MODES, PAIRS, ENERGY_EDGES, RADIUS_EDGES, selection

COLORS = ["#0072B2", "#D55E00", "#009E73"]


def fraction(n, d):
    return np.divide(n, d, out=np.full(np.broadcast_shapes(np.shape(n), np.shape(d)), np.nan),
                     where=np.asarray(d) != 0)


def wilson(n, d):
    p = fraction(n, d)
    center = (p + fraction(.5, d)) / (1 + fraction(1., d))
    half = np.sqrt(fraction(p*(1-p), d) + fraction(.25, np.asarray(d)**2)) / (1+fraction(1., d))
    return center-half, center+half


def save_table(path, fields, rows):
    with path.open("w") as target:
        writer = csv.DictWriter(target, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(counts, names):
    lines = ["| Cut | Forward Pass | Eff (%) | CumEff (%) | Backward Pass | Eff (%) | CumEff (%) | Merge Pass | Eff (%) | CumEff (%) |",
             "|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for stage, name in enumerate(names):
        cells = [name]
        for mode in range(3):
            n = int(counts[mode, stage])
            previous = counts[mode, stage-1] if stage else n
            cells += [f"{n:,}", f"{100*fraction(n, previous):.3f}",
                      f"{100*fraction(n, counts[mode, 0]):.3f}"]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def figure_save(fig, root, stem):
    svg = root / f"{stem}.svg"
    fig.savefig(svg, bbox_inches="tight")
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    fig.savefig(root / f"{stem}.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def report(repo, manifest, output, combined_input=None, cluster=None, retries=None):
    output.mkdir(parents=True, exist_ok=True)
    records = [line.split("\t") for line in manifest.read_text().splitlines()]
    arrays = []
    missing = []
    if combined_input:
        with np.load(combined_input) as source:
            assert np.array_equal(source['manifest_indices'], [int(r[0]) for r in records])
            assert np.array_equal(source['runs'], [int(r[1]) for r in records])
            keys = [k for k in source.files if k not in ('manifest_indices', 'runs')]
            arrays = [(record, {key: source[key][i] for key in keys})
                      for i, record in enumerate(records)]
    else:
        for record in records:
            path = Path(record[5])
            if not path.is_file():
                missing.append(record[0])
                continue
            with np.load(path) as source:
                arrays.append((record, {key: source[key] for key in source.files}))
    if missing:
        raise RuntimeError(f"comparison summaries missing: {missing}")
    combined = {key: np.stack([a[key] for _, a in arrays]) for key in arrays[0][1]}
    indices = np.array([int(r[0]) for r, _ in arrays])
    runs = np.array([int(r[1]) for r, _ in arrays])
    combined.update(manifest_indices=indices, runs=runs)
    np.savez_compressed(output / "paired_results.npz", **combined)
    active, skipped = selection(repo)
    names = ["NoCuts"] + [n for n, _ in active]
    fi = int(combined["fiducial_index"][0])
    ti = int(combined["tracking_index"][0])
    assert np.all(combined["fiducial_index"] == fi)
    assert np.all(combined["tracking_index"] == ti)
    assert np.all(np.diff(combined["counts"], axis=2) <= 0)
    assert np.all(combined["counts"][:, :, 0] == combined["counts"][:, :1, 0])
    assert np.all(combined['existing_merge_verified'] == 1)
    assert np.all(combined['nontrack_columns'] == 17)
    for pair, (left, right) in enumerate(PAIRS):
        overlap = combined['overlaps'][:, pair]
        assert np.array_equal(overlap[:, :, 1] + overlap[:, :, 3], combined['counts'][:, left])
        assert np.array_equal(overlap[:, :, 2] + overlap[:, :, 3], combined['counts'][:, right])
        assert np.all(overlap.sum(axis=2) == combined['counts'][:, :1, 0])
    for label in ('energy', 'radius'):
        assert np.array_equal(combined[f'{label}_den'].sum(axis=-1), combined['counts'][:, 0, fi])
        assert np.array_equal(combined[f'{label}_pass'].sum(axis=-1),
                              combined['counts'][:, :, [fi+1, ti, len(names)-1]])
    groups = {"all": np.ones(len(runs), dtype=bool), "nominal": runs != 200080}
    groups.update({str(run): runs == run for run in sorted(set(runs))})
    table_rows, deltas, run_rows = [], [], []
    for group, select in groups.items():
        counts = combined["counts"][select].sum(axis=0)
        overlaps = combined["overlaps"][select].sum(axis=0)
        baseline = int(counts[0, fi])
        for stage, cut in enumerate(names):
            for mode, mode_name in enumerate(MODES):
                n = int(counts[mode, stage])
                d = int(counts[mode, stage-1] if stage else n)
                table_rows.append(dict(group=group, stage=stage, cut=cut, mode=mode_name,
                                       passed=n, before=d, efficiency_percent=100*fraction(n,d),
                                       cumulative_percent=100*fraction(n, counts[mode,0]),
                                       truth_baseline=baseline,
                                       truth_normalized_percent=100*fraction(n,baseline) if stage>=fi else "NA"))
            if stage >= fi:
                for pair, (left, right) in enumerate(PAIRS):
                    neither, only_left, only_right, both = overlaps[pair, stage]
                    difference = (only_right-only_left)/baseline
                    error = np.sqrt(max(0.,(only_left+only_right)/baseline-difference**2)/baseline)
                    deltas.append(dict(group=group,stage=stage,cut=cut,
                                       pair=f"{MODES[right]}-{MODES[left]}",
                                       first_only=int(only_left),second_only=int(only_right),
                                       both=int(both),denominator=baseline,
                                       delta_percentage_points=100*difference,
                                       paired_se_percentage_points=100*error))
        for mode, mode_name in enumerate(MODES):
            run_rows.append(dict(group=group,files=int(select.sum()),mode=mode_name,
                                 input_events=int(counts[mode,0]),truth_baseline=baseline,
                                 long_track_events=int(counts[mode,fi+1]),
                                 through_theta_events=int(counts[mode,ti]),
                                 final_events=int(counts[mode,-1]),
                                 final_efficiency_percent=100*counts[mode,-1]/baseline))
        (output / f"cutflow_{group}.md").write_text(markdown_table(counts,names)+"\n")
    save_table(output / "cutflow.tsv", list(table_rows[0]), table_rows)
    save_table(output / "paired_differences.tsv", list(deltas[0]), deltas)
    save_table(output / "by_sample.tsv", list(run_rows[0]), run_rows)
    per_file = []
    for (record, result) in arrays:
        row = dict(index=record[0],run=record[1],input_rdo=record[3],existing_merge=record[4],
                   events=int(result["counts"][0,0]),truth_baseline=int(result["counts"][0,fi]),
                   existing_merge_verified=int(result["existing_merge_verified"]))
        for m, mode in enumerate(MODES):
            row[f"{mode}_final"] = int(result["counts"][m,-1])
            row[f"{mode}_nonfinite_leading_quality"] = int(result["nonfinite_leading_quality"][m])
        per_file.append(row)
    save_table(output / "files.tsv",list(per_file[0]),per_file)
    if cluster:
        performance = []
        retries = retries or {}
        for proc, record in enumerate(records):
            job = retries.get(int(record[0]), f'{cluster}.{proc}')
            log = (repo / f'logs/tracking_comparison_{job}.out').read_text()
            assert f'completed index={record[0]} ' in log
            assert 'code_commit=d32b0ff3cc4a2dad4abfb1474a82422c3c25b305' in log
            assert 'tracked_source_changes=none' in log
            row = dict(index=record[0], job=job)
            pattern = (r'^(input|reco|forward|backward|merge|comparison) wall_seconds=([\d.]+) '
                       r'max_rss_kib=(\d+) user_seconds=([\d.]+) system_seconds=([\d.]+)$')
            for stage, wall, rss, user, system in re.findall(pattern, log, re.M):
                row.update({f'{stage}_wall_s':wall, f'{stage}_rss_kib':rss,
                            f'{stage}_user_s':user, f'{stage}_sys_s':system})
            assert len(row) == 26, job
            performance.append(row)
        save_table(output / 'performance.tsv', list(performance[0]), performance)
    save_table(output / "cut_definitions.tsv",["stage","cut","expression"],
               [dict(stage=i+1,cut=n,expression=e) for i,(n,e) in enumerate(active)])

    plt.rcParams.update({"font.size":10, "axes.spines.top":False,"axes.spines.right":False,
                         "svg.fonttype":"none"})
    counts = combined["counts"].sum(axis=0)
    baseline = counts[0,fi]
    y = np.arange(len(names))
    fig, axes = plt.subplots(1,2,figsize=(14,10),sharey=True,
                             gridspec_kw={"width_ratios":[1,1]})
    for m, mode in enumerate(MODES):
        axes[0].plot(100*counts[m]/counts[m,0],y,"o-",ms=4,color=COLORS[m],label=mode)
        previous = np.r_[counts[m,0],counts[m,:-1]]
        axes[1].plot(100*fraction(counts[m],previous),y,"o-",ms=4,color=COLORS[m],label=mode)
    axes[0].set_yticks(y,names);axes[0].invert_yaxis()
    axes[0].set_xlabel("Cumulative efficiency / NoCuts (%)")
    axes[1].set_xlabel("Efficiency relative to previous row (%)")
    for ax in axes:
        ax.grid(alpha=.25);ax.set_xlim(-2,102);ax.legend()
    axes[0].axhline(fi+.5,color="grey",ls="--",lw=1)
    axes[1].axhline(fi+.5,color="grey",ls="--",lw=1)
    fig.suptitle(f"Same-source MC cutflow · {len(records)} paired files · {counts[0,0]:,} events\n"
                 "Official master d32b0ff3 · native VetoNu reduced charge · unweighted MC")
    fig.tight_layout();figure_save(fig,output,"cutflow_efficiency")

    for label, edges, xlabel in [("energy",ENERGY_EDGES,"Truth neutrino pz (GeV)"),
                                 ("radius",RADIUS_EDGES,"Truth interaction radius (mm)")]:
        denominator=combined[f"{label}_den"].sum(axis=0)
        passed=combined[f"{label}_pass"].sum(axis=0)
        # Plot only finite energy bins; retain >=10000 GeV in the exported NPZ/TSV.
        finite=np.isfinite(edges[1:]); left=edges[:-1][finite];right=edges[1:][finite]
        x=np.sqrt(left*right) if label=="energy" else (left+right)/2
        fig,axes=plt.subplots(1,3,figsize=(15,4.8),sharey=True)
        for j,title in enumerate(["At least one long track","Through theta cut (incl. scintillators)","Full selection"]):
            for m,mode in enumerate(MODES):
                p=passed[m,j,finite];d=denominator[finite]
                value=fraction(p,d);lo,hi=wilson(p,d)
                axes[j].errorbar(x,100*value,yerr=100*np.vstack([np.maximum(0,value-lo),np.maximum(0,hi-value)]),
                                 fmt="o-",ms=4,capsize=2,color=COLORS[m],label=mode)
            axes[j].set_title(title);axes[j].set_xlabel(xlabel);axes[j].grid(alpha=.25)
            axes[j].set_ylim(0,105)
            if label=="energy":axes[j].set_xscale("log")
        axes[0].set_ylabel("Pass / common truth-fiducial denominator (%)")
        axes[-1].legend();fig.suptitle("Paired MC · 68% Wilson intervals · no event weights")
        fig.tight_layout();figure_save(fig,output,f"efficiency_vs_{label}")
        bin_rows=[]
        for b in range(len(edges)-1):
            for m,mode in enumerate(MODES):
                for j,title in enumerate(["long_track","through_theta","full_selection"]):
                    bin_rows.append(dict(bin_low=edges[b],bin_high=edges[b+1],mode=mode,stage=title,
                                         denominator=int(denominator[b]),passed=int(passed[m,j,b])))
        save_table(output/f"{label}_bins.tsv",list(bin_rows[0]),bin_rows)

    fig,axes=plt.subplots(1,2,figsize=(13,6),gridspec_kw={"width_ratios":[1.4,1]})
    stage_ids=list(range(fi+1,len(names)))
    for pair,(left,right) in enumerate(PAIRS):
        subset=[r for r in deltas if r['group']=='all' and
                r['pair']==f'{MODES[right]}-{MODES[left]}' and r['stage'] in stage_ids]
        axes[0].errorbar([r['delta_percentage_points'] for r in subset],np.arange(len(subset))+pair*.15,
                         xerr=[r['paired_se_percentage_points'] for r in subset],fmt='o-',ms=4,
                         color=COLORS[pair],label=f'{MODES[right]} - {MODES[left]}')
    axes[0].set_yticks(np.arange(len(stage_ids))+.15,[names[s] for s in stage_ids])
    axes[0].invert_yaxis();axes[0].axvline(0,color='grey',lw=1)
    axes[0].set_xlabel('Efficiency difference (percentage points)\ncommon truth denominator; paired 1 SE')
    axes[0].legend(fontsize=8);axes[0].grid(alpha=.25)
    labels=[]
    for j,run in enumerate(sorted(set(runs))):
        result=[r for r in deltas if r['group']==str(run) and r['stage']==len(names)-1 and r['pair']=='merge-backward'][0]
        axes[1].errorbar(result['delta_percentage_points'],j,xerr=result['paired_se_percentage_points'],
                         fmt='o',color=COLORS[2],capsize=3)
        labels.append(str(run))
    axes[1].set_yticks(range(len(labels)),labels);axes[1].invert_yaxis();axes[1].axvline(0,color='grey',lw=1)
    axes[1].set_title('Full selection: merge - backward, by run')
    axes[1].set_xlabel('Efficiency difference (percentage points)');axes[1].grid(alpha=.25)
    fig.tight_layout();figure_save(fig,output,"paired_efficiency_differences")

    both=combined['overlaps'].sum(axis=0)
    lines=["# 同来源 forward / backward / merge cutflow 对照", "",
           f"完整比较：{len(records)} 个相同 RDO，{int(counts[0,0]):,} 个配对事件；"
           f"公共 truth fiducial 分母 {int(baseline):,}。", "",
           "Pass 为未加权事件数；Eff 为相对上一行的百分比；CumEff 为相对 NoCuts 的百分比。"
           "所有行按仓库 cuts.yaml 顺序累计，原生 VetoNu reduced charge。", "",
           markdown_table(counts,names), "",
           "## 公共 truth 分母下的选择效率", "",
           "| 阶段 | Forward (%) | Backward (%) | Merge (%) |", "|:---|---:|---:|---:|"]
    for s in [fi+1,ti,len(names)-1]:
        lines.append('| '+names[s]+' | '+' | '.join(f'{100*counts[m,s]/baseline:.3f}' for m in range(3))+' |')
    lines += ["", "## 同事件的获得与损失", "",
              "| 对照（后者减前者） | 前者独有 | 后者独有 | 共同通过 | 差值（百分点） | 配对统计 SE（百分点） |",
              "|:---|---:|---:|---:|---:|---:|"]
    for d in [d for d in deltas if d['group']=='all' and d['stage']==len(names)-1]:
        lines.append(f"| {d['pair']} | {d['first_only']:,} | {d['second_only']:,} | {d['both']:,} | "
                     f"{d['delta_percentage_points']:+.4f} | {d['paired_se_percentage_points']:.4f} |")
    lines += ["", "全样本汇总含 SIBYLL π 200080，属于替代生成器，不能作为标称 flux 的加权预测。"
              "六个 nominal EPOS/POWHEG run 的单独汇总见 cutflow_nominal.md；各 run 表和 TSV 同时提供。", "",
              "这些是相同真值条件下的事件选择效率，不是经过 muon truth matching 的单径迹效率。"
              "通过 theta 的阶段包含此前 scintillator cut；full selection 还包含 VetoNu veto。"
              "68% Wilson 误差只用于各自 binomial 比例；模式差值使用同事件配对协方差，"
              "不包含几何、拟合、生成器等系统误差。", "",
              "## 图表", "",
              "![Cutflow](cutflow_efficiency.png)", "![Truth pz](efficiency_vs_energy.png)",
              "![Truth radius](efficiency_vs_radius.png)",
              "![Paired differences](paired_efficiency_differences.png)", "",
              "SVG 为可编辑矢量图。energy_bins.tsv 包含 pz≥10000 GeV 的溢出档，图中只展示有限 bin。", "",
              "## 配置与复核", "",
              "实际 cut 表达式见 cut_definitions.tsv；本次跳过的 DATA/aux/raw-charge 分支：", "",
              "\n".join('- '+name for name in skipped), "",
              f"全部 {len(records)} 项均逐事件验证三种模式的 17 个非轨迹输入完全一致，"
              "新旧 merge 的分析标量、cut 决策和事件 ID 完全相同。"
              "未比较全部 ntuple 分支的每个数值。", ""]
    (output/'comparison.md').write_text('\n'.join(lines))
    print('reported',len(records),'files',counts.tolist(),flush=True)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--combined',type=Path,help='Regenerate from the consolidated NPZ after shard cleanup')
    parser.add_argument('--cluster',type=int,help='Read completed worker logs to export performance.tsv')
    parser.add_argument('--retry',action='append',default=[],metavar='INDEX=CLUSTER.PROC')
    args=parser.parse_args()
    retries={int(item.split('=')[0]):item.split('=')[1] for item in args.retry}
    report(args.repo,args.manifest,args.output,args.combined,args.cluster,retries)
