#!/usr/bin/env python3
"""
Step 1.1: High-statistics multi-process measurement of thoroughgoing-muon station
localtime differences relative to VetoNu (ch 4, 5) across all 7 Run-3 Data eras
and MC (GENIE + FLUKA), matching MyWaveformTimeRangeAlg / NtupleDumperAlg semantics:
  - accept hits with (status & ~512) == 0
  - add +16.0 ns when (status & 512) != 0 (2nd digitizer offset)
  - Veto2 = {Veto20, Veto21} (ch 6,7 / 22,23)
  - Timing = {Timing0..3} (ch 8,9,10,11)
  - Preshower01 = {Preshower0, Preshower1} (ch 12,13)
  - Preshower0123 = {Preshower0..3} (ch 12,13,24,25 in 2025-2026)

Outputs:
  - workbook/stage216_timing_t5/reduced_charge_station_timediffs.tsv
  - workbook/stage216_timing_t5/fig0_reduced_charge_timediffs.png
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import glob
import json
import os
from pathlib import Path
import time
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit
import uproot

REPO_DIR = Path("/eos/home-x/xcheng/FASER/nu_muAnalysis")
MANIFEST_PATH = REPO_DIR / "AnalysisZipFramework/config/timing_calib/run3_timing_manifest.json"
OUT_DIR = REPO_DIR / "workbook/stage216_timing_t5"


def _resolve_run_files(run: int, reco_tag: str, max_files: int = 8) -> list[str]:
    r6 = f"{run:06d}"
    cands: list[str] = []
    if reco_tag == "2022_unfilt/r0021-r0023":
        cands = glob.glob(f"/eos/experiment/faser/phys/2022_unfilt/r0021-r0023/{r6}/*-PHYS.root") or glob.glob(
            f"/eos/experiment/faser/data0/phys/2022_back/r0021/{r6}/*-PHYS.root"
        )
    elif reco_tag == "2023_unfilt/r0021-r0023":
        cands = glob.glob(f"/eos/experiment/faser/phys/2023_unfilt/r0021-r0023/{r6}/*-PHYS.root") or glob.glob(
            f"/eos/experiment/faser/data0/phys/2023_back/r0021/{r6}/*-PHYS.root"
        )
    elif reco_tag == "2024_unfilt/r0022-r0023":
        cands = glob.glob(f"/eos/experiment/faser/phys/2024_unfilt/r0022-r0023/{r6}/*-PHYS.root") or glob.glob(
            f"/eos/experiment/faser/data0/phys/2024_back/r0022/{r6}/*-PHYS.root"
        )
    elif "/" in reco_tag:
        cands = glob.glob(f"/eos/experiment/faser/phys/{reco_tag}/{r6}/*-PHYS.root")
    elif reco_tag.startswith("mc_genie_"):
        cands = glob.glob(f"/eos/experiment/fasernu-data0/faser/sim/mc24/genie/{r6}/bck/s001*/*-PHYS.root")
    elif reco_tag.startswith("mc_fluka_"):
        era = reco_tag.split("_")[-1]
        cands = glob.glob(f"/eos/experiment/faser/sim/{era}/fluka/{r6}/bck/s001*-r0019/*-PHYS.root")
    good = [f for f in sorted(cands) if os.path.getsize(f) > 500_000]
    if not good:
        good = [f for f in sorted(cands) if os.path.getsize(f) > 10_000]
    return good[:max_files]


def _scan_single_file(task: tuple[str, str, int]) -> dict[str, Any]:
    group, path, max_entries = task
    try:
        f = uproot.open(path)
        if "nt" not in f:
            return {"group": group, "ok": False}
        nt = f["nt"]
        if nt.num_entries == 0:
            return {"group": group, "ok": False}
        keys = set(nt.keys())
        vpre = "VetoSt" if "VetoSt20_localtime" in keys else "Veto"
        has_ps23 = "Preshower2_localtime" in keys and "Preshower3_localtime" in keys
        cols = [
            "longTracks",
            "VetoNu0_raw_charge",
            "VetoNu1_raw_charge",
            f"{vpre}20_charge",
            f"{vpre}21_charge",
            "VetoNu0_localtime",
            "VetoNu0_status",
            "VetoNu1_localtime",
            "VetoNu1_status",
            f"{vpre}20_localtime",
            f"{vpre}20_status",
            f"{vpre}21_localtime",
            f"{vpre}21_status",
            "Timing0_localtime",
            "Timing0_status",
            "Timing1_localtime",
            "Timing1_status",
            "Timing2_localtime",
            "Timing2_status",
            "Timing3_localtime",
            "Timing3_status",
            "Preshower0_localtime",
            "Preshower0_status",
            "Preshower1_localtime",
            "Preshower1_status",
        ]
        if has_ps23:
            cols += [
                "Preshower2_localtime",
                "Preshower2_status",
                "Preshower3_localtime",
                "Preshower3_status",
            ]
        stop = min(nt.num_entries, max_entries) if max_entries > 0 else nt.num_entries
        a = nt.arrays(cols, entry_stop=stop, library="np")
    except Exception:
        return {"group": group, "ok": False}

    # Thoroughgoing muon selection (clean MIPs in VetoNu + track + Veto2 hit)
    m = (
        (a["longTracks"] > 0)
        & (a["VetoNu0_raw_charge"] > 40.0)
        & (a["VetoNu1_raw_charge"] > 40.0)
        & ((a[f"{vpre}20_charge"] > 40.0) | (a[f"{vpre}21_charge"] > 40.0))
    )
    if not np.any(m):
        return {"group": group, "ok": False}

    def _mean_lt(pairs: list[tuple[str, str]]) -> np.ndarray:
        s = np.zeros(int(np.count_nonzero(m)), dtype=np.float64)
        n = np.zeros(int(np.count_nonzero(m)), dtype=np.int32)
        for lk, sk in pairs:
            st = a[sk][m].astype(np.int64)
            lt = a[lk][m].astype(np.float64)
            ok = ((st & ~512) == 0) & np.isfinite(lt) & (lt != 0.0)
            corr = np.where((st & 512) != 0, 16.0, 0.0)
            s += np.where(ok, lt + corr, 0.0)
            n += ok.astype(np.int32)
        return np.where(n > 0, s / np.maximum(n, 1), np.nan)

    t_vn = _mean_lt([("VetoNu0_localtime", "VetoNu0_status"), ("VetoNu1_localtime", "VetoNu1_status")])
    t_v2 = _mean_lt([(f"{vpre}20_localtime", f"{vpre}20_status"), (f"{vpre}21_localtime", f"{vpre}21_status")])
    t_tr = _mean_lt(
        [
            ("Timing0_localtime", "Timing0_status"),
            ("Timing1_localtime", "Timing1_status"),
            ("Timing2_localtime", "Timing2_status"),
            ("Timing3_localtime", "Timing3_status"),
        ]
    )
    t_ps01 = _mean_lt([("Preshower0_localtime", "Preshower0_status"), ("Preshower1_localtime", "Preshower1_status")])
    res = {
        "group": group,
        "ok": True,
        "vv": (t_v2 - t_vn).astype(np.float32),
        "vt": (t_tr - t_vn).astype(np.float32),
        "vp01": (t_ps01 - t_vn).astype(np.float32),
    }
    if has_ps23:
        t_ps0123 = _mean_lt(
            [
                ("Preshower0_localtime", "Preshower0_status"),
                ("Preshower1_localtime", "Preshower1_status"),
                ("Preshower2_localtime", "Preshower2_status"),
                ("Preshower3_localtime", "Preshower3_status"),
            ]
        )
        res["vp0123"] = (t_ps0123 - t_vn).astype(np.float32)
    return res


def _fit_peak(arr: np.ndarray, lo: float = -10.0, hi: float = 80.0) -> dict[str, Any]:
    arr = arr[np.isfinite(arr) & (arr > lo) & (arr < hi)]
    if len(arr) < 30:
        return {"n": int(len(arr)), "peak_ns": float("nan"), "sigma_ns": float("nan"), "median_ns": float("nan"), "edges": None, "counts": None}
    edges = np.arange(lo, hi + 0.02, 0.02)
    counts, _ = np.histogram(arr, bins=edges)
    centers = 0.5 * (edges[:-1] + edges[1:])
    ib = int(np.argmax(counts))
    mode_c = float(centers[ib])
    fit_m = np.abs(centers - mode_c) <= 1.2
    xc = centers[fit_m]
    yc = counts[fit_m].astype(np.float64)
    win = arr[np.abs(arr - mode_c) <= 1.5]
    med = float(np.median(win)) if len(win) else mode_c
    sig_est = float(np.std(win)) if len(win) else 0.5

    def _gauss(x: np.ndarray, amp: float, mu: float, sig: float) -> np.ndarray:
        return amp * np.exp(-0.5 * ((x - mu) / sig) ** 2)

    peak = med
    sigma = sig_est
    try:
        popt, _ = curve_fit(
            _gauss,
            xc,
            yc,
            p0=[float(np.max(yc)), mode_c, max(0.2, sig_est)],
            bounds=([0.0, mode_c - 1.5, 0.05], [1e12, mode_c + 1.5, 5.0]),
            maxfev=2000,
        )
        peak = float(popt[1])
        sigma = float(abs(popt[2]))
    except Exception:
        pass
    return {
        "n": int(len(arr)),
        "peak_ns": round(peak, 4),
        "sigma_ns": round(sigma, 4),
        "median_ns": round(med, 4),
        "edges": centers,
        "counts": counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=28)
    parser.add_argument("--max-entries-per-file", type=int, default=250000)
    args = parser.parse_args()

    t0 = time.perf_counter()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    m = json.loads(MANIFEST_PATH.read_text())

    # Pick top-luminosity runs for every era + 2025/p0013 vs p0014 split
    by_tag: dict[str, list[tuple[float, int, str]]] = {}
    for r_str, info in m["runs"].items():
        per = info["period"]
        rt = info["reco_tag"]
        key = per if per != "2025" else f"2025_{rt.split('/')[-1]}"
        by_tag.setdefault(key, []).append((info["lumi_pb_inverse"], int(r_str), rt))

    groups: list[tuple[str, list[str]]] = []
    ordered_keys = ["2022", "2023", "2024_preCaloNu", "2024_CaloNu", "2024_postCaloNu", "2025_p0013", "2025_p0014", "2026"]
    for gk in ordered_keys:
        lst = sorted(by_tag.get(gk, []), reverse=True)
        files: list[str] = []
        for _, rn, rt in lst[:3]:
            files.extend(_resolve_run_files(rn, rt, max_files=4))
        groups.append((gk, files[:8]))

    # Add 2025 combined + GENIE + FLUKA
    groups.append(("MC_GENIE_2022_23", _resolve_run_files(200082, "mc_genie_22", max_files=8)))
    groups.append(("MC_GENIE_2024_noCN", _resolve_run_files(200093, "mc_genie_24", max_files=8)))
    groups.append(("MC_GENIE_2024_CaloNu", _resolve_run_files(200139, "mc_genie_cn", max_files=8)))
    groups.append(("MC_FLUKA_2024", _resolve_run_files(210021, "mc_fluka_mc24", max_files=12)))

    tasks: list[tuple[str, str, int]] = []
    for gk, fl in groups:
        for fn in fl:
            tasks.append((gk, fn, args.max_entries_per_file))

    print(f"[Step 1.1] Scanning {len(tasks)} files across {len(groups)} eras using {args.workers} processes...", flush=True)
    collected: dict[str, dict[str, list[np.ndarray]]] = {gk: {"vv": [], "vt": [], "vp01": [], "vp0123": []} for gk, _ in groups}
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for res in ex.map(_scan_single_file, tasks):
            if not res.get("ok"):
                continue
            g = res["group"]
            collected[g]["vv"].append(res["vv"])
            collected[g]["vt"].append(res["vt"])
            collected[g]["vp01"].append(res["vp01"])
            if "vp0123" in res:
                collected[g]["vp0123"].append(res["vp0123"])

    # Combine 2025_p0013 + 2025_p0014 for overall 2025 and 2025+2026 unified peak check
    for comb_name, parts in [("2025_all", ["2025_p0013", "2025_p0014"]), ("2025_2026_all", ["2025_p0013", "2025_p0014", "2026"])]:
        collected[comb_name] = {
            k: sum((collected[p][k] for p in parts if collected[p][k]), [])
            for k in ("vv", "vt", "vp01", "vp0123")
        }

    rows: list[dict[str, Any]] = []
    fit_cache: dict[str, dict[str, Any]] = {}
    all_order = ordered_keys + ["2025_all", "2025_2026_all", "MC_GENIE_2022_23", "MC_GENIE_2024_noCN", "MC_GENIE_2024_CaloNu", "MC_FLUKA_2024"]
    for gk in all_order:
        d = collected[gk]
        vv_f = _fit_peak(np.concatenate(d["vv"])) if d["vv"] else _fit_peak(np.array([]))
        vt_f = _fit_peak(np.concatenate(d["vt"])) if d["vt"] else _fit_peak(np.array([]))
        vp_f = _fit_peak(np.concatenate(d["vp01"])) if d["vp01"] else _fit_peak(np.array([]))
        vp03_f = _fit_peak(np.concatenate(d["vp0123"])) if d["vp0123"] else _fit_peak(np.array([]))
        fit_cache[gk] = {"vv": vv_f, "vt": vt_f, "vp01": vp_f, "vp0123": vp03_f}
        row = {
            "era": gk,
            "N_muons": vv_f["n"],
            "Veto2_minus_VetoNu_peak_ns": vv_f["peak_ns"],
            "Veto2_minus_VetoNu_sigma_ns": vv_f["sigma_ns"],
            "Timing_minus_VetoNu_peak_ns": vt_f["peak_ns"],
            "Timing_minus_VetoNu_sigma_ns": vt_f["sigma_ns"],
            "PS01_minus_VetoNu_peak_ns": vp_f["peak_ns"],
            "PS01_minus_VetoNu_sigma_ns": vp_f["sigma_ns"],
            "PS0123_minus_VetoNu_peak_ns": vp03_f["peak_ns"],
            "PS0123_minus_VetoNu_sigma_ns": vp03_f["sigma_ns"],
        }
        rows.append(row)
        print(
            f"  {gk:22s}: N={row['N_muons']:7d} | Veto2-VN={row['Veto2_minus_VetoNu_peak_ns']:7.4f}±{row['Veto2_minus_VetoNu_sigma_ns']:.2f} "
            f"| Trig-VN={row['Timing_minus_VetoNu_peak_ns']:7.4f}±{row['Timing_minus_VetoNu_sigma_ns']:.2f} "
            f"| PS01-VN={row['PS01_minus_VetoNu_peak_ns']:7.4f}±{row['PS01_minus_VetoNu_sigma_ns']:.2f}",
            flush=True,
        )

    tsv_path = OUT_DIR / "reduced_charge_station_timediffs.tsv"
    with open(tsv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter="\t")
        w.writeheader()
        w.writerows(rows)

    # Diagnostic Figure fig0: Veto2-VetoNu & Preshower-VetoNu spectra across Run-3 periods
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2), dpi=160)
    plot_eras = [
        ("2022", "2022 (r0021-r0023)", "#1f77b4", "-"),
        ("2023", "2023 (r0021-r0023)", "#ff7f0e", "-"),
        ("2024_preCaloNu", "2024 pre-CaloNu", "#2ca02c", "-"),
        ("2024_CaloNu", "2024 CaloNu (ch 22,23 +16 ns)", "#d62728", "-"),
        ("2024_postCaloNu", "2024 post-CaloNu", "#9467bd", "-"),
        ("2025_all", "2025 (p0013+p0014, new PS PMTs)", "#8c564b", "--"),
        ("2026", "2026 (p0015, new PS PMTs)", "#e377c2", "-."),
    ]
    for ek, lbl, col, ls in plot_eras:
        fv = fit_cache[ek]["vv"]
        if fv["edges"] is not None:
            m_w = (fv["edges"] >= 30.0) & (fv["edges"] <= 39.0)
            y = fv["counts"][m_w] / max(float(np.max(fv["counts"][m_w])), 1.0)
            axes[0].plot(fv["edges"][m_w], y, color=col, ls=ls, lw=1.6, label=f"{lbl}: {fv['peak_ns']:.3f} ns")
        fp = fit_cache[ek]["vp01"]
        if fp["edges"] is not None:
            m_w = (fp["edges"] >= 10.0) & (fp["edges"] <= 58.0)
            y = fp["counts"][m_w] / max(float(np.max(fp["counts"][m_w])), 1.0)
            axes[1].plot(fp["edges"][m_w], y, color=col, ls=ls, lw=1.6, label=f"{lbl}: {fp['peak_ns']:.3f} ns")
    axes[0].set_title(r"Veto2 $-$ VetoNu localtime (thoroughgoing $\mu$)")
    axes[0].set_xlabel(r"$t_{\mathrm{Veto2}} - t_{\mathrm{VetoNu}}$ [ns]")
    axes[0].set_ylabel("Normalized counts / 0.02 ns")
    axes[0].legend(fontsize=8)
    axes[1].set_title(r"Preshower(0,1) $-$ VetoNu localtime (2025–2026 $-39.4$ ns shift)")
    axes[1].set_xlabel(r"$t_{\mathrm{PS01}} - t_{\mathrm{VetoNu}}$ [ns]")
    axes[1].axvline(53.625, color="black", ls=":", lw=1.2, label="Hardcoded NtupleDumper (53.625 ns)")
    axes[1].legend(fontsize=8, loc="upper center")
    fig.suptitle("Run 3 Station Localtime Differences Used in Reduced VetoNu Charge Window", fontsize=12)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig0_reduced_charge_timediffs.png")
    plt.close(fig)
    print(f"[Step 1.1 Done] wall={time.perf_counter() - t0:.2f}s -> {tsv_path}", flush=True)


if __name__ == "__main__":
    main()
