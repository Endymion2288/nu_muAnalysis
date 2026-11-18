#!/usr/bin/env python3
"""
Stage T1 (Run 3 Scintillator Timing Calibration) Pass 1 & Pass 2 fitter.

Subcommands:
  fit-pass1: Merge per-run Pass 1 histograms/summaries across 717 Run 3 runs,
             fit circular bcidtime zero-points and full-aperture Preshower0
             triggertime offsets, audit Digitizer-2 (status & 512) alignment,
             and emit ref_offsets_run3.json + pass1_run_offsets_summary.tsv.
  fit-pass2: Merge Pass 2 unwrap residuals & stratified calibration records,
             run 5-iteration inverse-variance weighted Leave-One-Out (LOO)
             calibration (2D 12x12 TOF maps, low-charge time-walk, floored
             power-law resolution) across all 7 periods, and emit
             tof_maps_run3.json + pass2_unwrap_audit.tsv.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import glob
import json
import math
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import curve_fit
import uproot

CHANNELS = [
    "VetoNu0", "VetoNu1", "Veto10", "Veto11", "Veto20", "Veto21",
    "Timing01", "Timing23", "Preshower0", "Preshower1",
    "Preshower2", "Preshower3", "Muon0", "Muon1",
]
CH_TO_IDX = {c: i for i, c in enumerate(CHANNELS)}

CHANNEL_PLANE_IDX = [
    0, 0,  # VetoNu0, VetoNu1
    1, 1,  # Veto10, Veto11
    2, 2,  # Veto20, Veto21
    3, 3,  # Timing01, Timing23
    4, 5,  # Preshower0, Preshower1
    4, 5,  # Preshower2, Preshower3
    6, 7,  # Muon0, Muon1
]

MIP_THRESHOLDS = {
    "VetoNu0": 63.3, "VetoNu1": 64.1,
    "Veto10": 61.2, "Veto11": 59.0,
    "Veto20": 59.2, "Veto21": 57.0,
    "Timing01": 35.0, "Timing23": 35.0,
    "Preshower0": 3.50, "Preshower1": 3.12,
    "Preshower2": 0.90, "Preshower3": 0.60,
    "Muon0": 35.0, "Muon1": 35.0,
}

DEFAULT_SIGMAS = {
    "VetoNu0": 0.53, "VetoNu1": 0.54,
    "Veto10": 0.23, "Veto11": 0.23,
    "Veto20": 0.23, "Veto21": 0.24,
    "Timing01": 0.35, "Timing23": 0.35,
    "Preshower0": 0.28, "Preshower1": 0.28,
    "Preshower2": 0.30, "Preshower3": 0.32,
    "Muon0": 0.35, "Muon1": 0.35,
}

PRIMARY_DOWNSTREAM_CH_INDICES = [2, 3, 4, 5, 6, 7, 8, 9, 12, 13]
GRID_N = 12
GRID_MIN_MM = -150.0
GRID_MAX_MM = 150.0
GRID_STEP_MM = (GRID_MAX_MM - GRID_MIN_MM) / GRID_N  # 25.0 mm

PERIOD_ORDER = [
    "2022", "2023", "2024_preCaloNu", "2024_CaloNu",
    "2024_postCaloNu", "2025", "2026",
]


def period_for_run(run: int) -> str:
    if run < 10000:
        return "2022"
    if run < 13000:
        return "2023"
    if run < 15821:
        return "2024_preCaloNu"
    if run <= 16924:
        return "2024_CaloNu"
    if run < 18500:
        return "2024_postCaloNu"
    if run < 21500:
        return "2025"
    return "2026"


def active_channels_for_period(period: str) -> list[str]:
    base = [
        "VetoNu0", "VetoNu1", "Veto10", "Veto20", "Veto21",
        "Timing01", "Timing23", "Preshower0", "Preshower1",
    ]
    if period not in ("2022", "2023"):
        base.insert(3, "Veto11")
    if period in ("2025", "2026"):
        base.extend(["Preshower2", "Preshower3", "Muon0", "Muon1"])
    return base


def _gauss(x: np.ndarray, amp: float, mu: float, sig: float) -> np.ndarray:
    return amp * np.exp(-0.5 * ((x - mu) / sig) ** 2)


def fit_circular_bcid_peak(counts: np.ndarray) -> tuple[float | None, float | None, float, str]:
    """Fit peak of a 500-bin [0, 25) ns bcidtime histogram, returning (mu, sigma, R, method)."""
    total = float(np.sum(counts))
    if total < 20.0:
        return None, None, 0.0, "insufficient"

    n_bins = len(counts)
    bw = 25.0 / n_bins
    centers = (np.arange(n_bins) + 0.5) * bw

    # Circular harmonic initial guess + concentration R
    angles = 2.0 * np.pi * centers / 25.0
    c_mean = float(np.sum(counts * np.cos(angles))) / total
    s_mean = float(np.sum(counts * np.sin(angles))) / total
    R_conc = math.hypot(c_mean, s_mean)
    circ_mu = (math.atan2(s_mean, c_mean) * 25.0 / (2.0 * math.pi)) % 25.0

    if total >= 50.0 and R_conc < 0.55:
        return None, None, round(R_conc, 4), "uncorrelated_masked"

    # Local 3-bin wrapped smoothing to reject single-bin statistical spikes
    padded = np.roll(counts, 1) + counts + np.roll(counts, -1)
    peak_idx = int(np.argmax(padded))
    peak_x = float(centers[peak_idx])

    # Wrap centers into [peak_x - 12.5, peak_x + 12.5)
    dx = ((centers - peak_x + 12.5) % 25.0) - 12.5
    if total < 60.0:
        # Low-stat run: circular weighted mean within +-2.0 ns of mode
        m = np.abs(dx) <= 2.0
        if np.sum(counts[m]) <= 0:
            return circ_mu, 0.5, round(R_conc, 4), "circ_harmonic"
        mu = (peak_x + float(np.sum(counts[m] * dx[m]) / np.sum(counts[m]))) % 25.0
        sig = float(np.sqrt(np.sum(counts[m] * (dx[m] - (mu - peak_x + 12.5) % 25.0 + 12.5) ** 2) / np.sum(counts[m])))
        return round(mu, 5), round(max(0.05, sig), 4), round(R_conc, 4), "circ_window"

    # Iterative core Gaussian fit within +-2.5 ns -> +-2.2 ns
    m = np.abs(dx) <= 2.5
    mu_cur = float(np.sum(counts[m] * dx[m]) / max(1.0, float(np.sum(counts[m]))))
    sig_cur = 0.45
    for half_w in (2.4, 2.0):
        mw = np.abs(dx - mu_cur) <= half_w
        xw = dx[mw]
        yw = counts[mw]
        if len(xw) < 5 or np.sum(yw) < 30.0:
            break
        err = np.sqrt(np.maximum(yw, 1.0))
        try:
            p0 = [float(np.max(yw)), mu_cur, max(0.15, sig_cur)]
            popt, _ = curve_fit(
                _gauss, xw, yw, p0=p0, sigma=err, absolute_sigma=False,
                bounds=([0.0, mu_cur - half_w, 0.05], [1e12, mu_cur + half_w, 3.0]),
                maxfev=2000,
            )
            mu_cur = float(popt[1])
            sig_cur = float(popt[2])
        except Exception:
            break

    mu_abs = (peak_x + mu_cur) % 25.0
    return round(mu_abs, 5), round(sig_cur, 4), round(R_conc, 4), "gauss"


def fit_linear_peak(counts: np.ndarray, x_min: float, x_max: float) -> tuple[float | None, float | None, float, str]:
    """Fit core Gaussian peak on linear 1D histogram, returning (mu, sigma, f_core, method)."""
    total = float(np.sum(counts))
    if total < 20.0:
        return None, None, 0.0, "insufficient"

    n_bins = len(counts)
    bw = (x_max - x_min) / n_bins
    centers = x_min + (np.arange(n_bins) + 0.5) * bw

    # 3-bin moving sum for robust mode
    smooth = np.convolve(counts, [1.0, 1.0, 1.0], mode="same")
    peak_idx = int(np.argmax(smooth))
    peak_x = float(centers[peak_idx])

    m = np.abs(centers - peak_x) <= 3.5
    if np.sum(counts[m]) < 20.0:
        f_core = float(np.sum(counts[np.abs(centers - peak_x) <= 6.0]) / total)
        if total >= 50.0 and f_core < 0.50:
            return None, None, round(f_core, 4), "uncorrelated_masked"
        return round(peak_x, 4), 0.7, round(f_core, 4), "mode"

    mu_cur = float(np.sum(counts[m] * centers[m]) / np.sum(counts[m]))
    sig_cur = 0.7
    f_core = float(np.sum(counts[np.abs(centers - mu_cur) <= 6.0]) / total)
    if total >= 50.0 and f_core < 0.50:
        return None, None, round(f_core, 4), "uncorrelated_masked"

    if total < 50.0:
        var = np.sum(counts[m] * (centers[m] - mu_cur) ** 2) / np.sum(counts[m])
        return round(mu_cur, 4), round(math.sqrt(max(0.01, float(var))), 4), round(f_core, 4), "win_mean"

    for half_w in (3.5, 2.8):
        mw = np.abs(centers - mu_cur) <= half_w
        xw = centers[mw]
        yw = counts[mw]
        if len(xw) < 6 or np.sum(yw) < 25.0:
            break
        err = np.sqrt(np.maximum(yw, 1.0))
        try:
            p0 = [float(np.max(yw)), mu_cur, max(0.25, sig_cur)]
            popt, _ = curve_fit(
                _gauss, xw, yw, p0=p0, sigma=err, absolute_sigma=False,
                bounds=([0.0, mu_cur - half_w, 0.08], [1e12, mu_cur + half_w, 4.0]),
                maxfev=2500,
            )
            mu_cur = float(popt[1])
            sig_cur = float(popt[2])
        except Exception:
            break

    f_core = float(np.sum(counts[np.abs(centers - mu_cur) <= 6.0]) / total)
    if total >= 50.0 and f_core < 0.50:
        return None, None, round(f_core, 4), "uncorrelated_masked"
    return round(mu_cur, 5), round(sig_cur, 4), round(f_core, 4), "gauss"


# ─────────────────────────────────────────────────────────────────────────────
# Pass 1 Reader / Merger / Fitter
# ─────────────────────────────────────────────────────────────────────────────

def _open_uproot_retry(path: str, retries: int = 3):
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            return uproot.open(path)
        except Exception as exc:
            last_err = exc
            if attempt + 1 < retries:
                time.sleep(0.5 * (attempt + 1))
    raise last_err if last_err is not None else RuntimeError(f"Failed to open {path}")


def _read_pass1_file(path: str) -> dict[str, Any]:
    with _open_uproot_retry(path) as tf:
        sum_arr = tf["pass1_summary"].arrays(library="np")
        runs_summary: dict[int, dict[str, Any]] = {}
        hists: dict[int, dict[str, np.ndarray]] = {}

        n_runs = len(sum_arr["run"])
        for idx in range(n_runs):
            r = int(sum_arr["run"][idx])
            rs = {
                "run": r,
                "period": str(sum_arr["period"][idx]),
                "n_total": int(sum_arr["n_total"][idx]),
                "n_grl_fail": int(sum_arr["n_grl_fail"][idx]),
                "n_non_colliding": int(sum_arr["n_non_colliding"][idx]),
                "n_blinded": int(sum_arr["n_blinded"][idx]),
                "n_single_muon": int(sum_arr["n_single_muon"][idx]),
                "has_veto11": bool(sum_arr["has_veto11"][idx]),
                "has_preshower23": bool(sum_arr["has_preshower23"][idx]),
                "has_muon": bool(sum_arr["has_muon"][idx]),
                "n_v20_ref_events": int(sum_arr["n_v20_ref_events"][idx]),
                "n_v10_ref_events": int(sum_arr["n_v10_ref_events"][idx]),
                "ch_n_good": sum_arr["ch_n_good"][idx].astype(np.int64),
                "ch_n_st512": sum_arr["ch_n_st512"][idx].astype(np.int64),
                "ch_n_st16": sum_arr["ch_n_st16"][idx].astype(np.int64),
                "ch_n_st4": sum_arr["ch_n_st4"][idx].astype(np.int64),
                "ch_n_bcid_r50": sum_arr["ch_n_bcid_r50"][idx].astype(np.int64),
                "ch_n_bcid_all": sum_arr["ch_n_bcid_all"][idx].astype(np.int64),
                "ch_n_dtrig_v20": sum_arr["ch_n_dtrig_v20"][idx].astype(np.int64),
                "ch_n_dtrig_v10": sum_arr["ch_n_dtrig_v10"][idx].astype(np.int64),
            }
            runs_summary[r] = rs

            rdir_name = f"run_{r}"
            rh: dict[str, np.ndarray] = {}
            if rdir_name in tf:
                rdir = tf[rdir_name]
                for hkey in rdir.keys(cycle=False):
                    rh[hkey] = rdir[hkey].values(flow=False).astype(np.float64)
            hists[r] = rh

        return {"runs": runs_summary, "hists": hists}


def _fit_pass1_single_run(item: tuple[int, dict[str, Any], dict[str, np.ndarray]]) -> tuple[int, dict[str, Any], list[dict[str, Any]]]:
    run, rsum, rh = item
    period = period_for_run(run)
    active = set(active_channels_for_period(period))
    ch_results: dict[str, Any] = {}
    tsv_rows: list[dict[str, Any]] = []

    # Bridge offset Veto10 - Veto20 for v10 fallback
    v10_vs_v20_mu = None
    if "h_dtrig_v20_Veto10" in rh:
        mu10, _, _, _ = fit_linear_peak(rh["h_dtrig_v20_Veto10"], -250.0, 250.0)
        v10_vs_v20_mu = mu10

    for c_idx, cname in enumerate(CHANNELS):
        if cname not in active:
            continue

        # 1) BCID reference (prefer r<50, fallback all)
        bcid_arr = rh.get(f"h_bcid_r50_{cname}")
        bcid_src = "r50"
        mu_b, sig_b, r_conc, meth_b = fit_circular_bcid_peak(bcid_arr) if bcid_arr is not None else (None, None, 0.0, "missing")
        if mu_b is None and meth_b != "uncorrelated_masked":
            bcid_all = rh.get(f"h_bcid_all_{cname}")
            if bcid_all is not None:
                mu_b, sig_b, r_conc, meth_b = fit_circular_bcid_peak(bcid_all)
                bcid_src = "all"

        # 2) Trigger reference relative to Veto20 (fallback Veto10 bridge)
        if cname == "Veto20":
            mu_t, sig_t, f_core, meth_t, trig_src = 0.0, 0.0, 1.0, "ref_zero", "Veto20"
        else:
            dtrig_v20 = rh.get(f"h_dtrig_v20_{cname}")
            mu_t, sig_t, f_core, meth_t = fit_linear_peak(dtrig_v20, -250.0, 250.0) if dtrig_v20 is not None else (None, None, 0.0, "missing")
            trig_src = "vs_V20"
            if mu_t is None and meth_t != "uncorrelated_masked" and v10_vs_v20_mu is not None:
                dtrig_v10 = rh.get(f"h_dtrig_v10_{cname}")
                mu1, sig1, fc1, meth1 = fit_linear_peak(dtrig_v10, -250.0, 250.0) if dtrig_v10 is not None else (None, None, 0.0, "missing")
                if mu1 is not None:
                    mu_t = round(mu1 + v10_vs_v20_mu, 5)
                    sig_t = sig1
                    f_core = fc1
                    meth_t = f"v10_bridge_{meth1}"
                    trig_src = "vs_V10"

        # Joint coherence gate: if either bcid or dtrig failed coherence, mask both cleanly
        if meth_b == "uncorrelated_masked" or meth_t == "uncorrelated_masked":
            mu_b = None
            mu_t = None
            meth_b = "uncorrelated_masked"
            meth_t = "uncorrelated_masked"

        # 3) Status & 512 alignment shift audit vs Digitizer-1 VetoNu0
        n_st512 = int(rsum["ch_n_st512"][c_idx])
        n_good = int(rsum["ch_n_good"][c_idx])
        dtrig_shift_512 = None
        dloc_shift_512 = None
        if n_st512 >= 30 and f"h_dtrig_dig1_st512_{cname}" in rh and f"h_dtrig_dig1_st0_{cname}" in rh:
            m512, _, _, _ = fit_linear_peak(rh[f"h_dtrig_dig1_st512_{cname}"], -250.0, 250.0)
            m0, _, _, _ = fit_linear_peak(rh[f"h_dtrig_dig1_st0_{cname}"], -250.0, 250.0)
            if m512 is not None and m0 is not None:
                dtrig_shift_512 = round(m512 - m0, 4)
            l512, _, _, _ = fit_linear_peak(rh.get(f"h_dloc_dig1_st512_{cname}", np.zeros(1)), -250.0, 250.0)
            l0, _, _, _ = fit_linear_peak(rh.get(f"h_dloc_dig1_st0_{cname}", np.zeros(1)), -250.0, 250.0)
            if l512 is not None and l0 is not None:
                dloc_shift_512 = round(l512 - l0, 4)

        ch_results[cname] = {
            "t_ref_bcid": mu_b,
            "sigma_bcid": sig_b,
            "bcid_R": r_conc,
            "t_trig_rel_ref": mu_t,
            "sigma_dtrig": sig_t,
            "dtrig_f_core": f_core,
            "bcid_method": f"{bcid_src}:{meth_b}",
            "trig_method": f"{trig_src}:{meth_t}",
            "n_bcid_r50": int(rsum["ch_n_bcid_r50"][c_idx]),
            "n_dtrig_v20": int(rsum["ch_n_dtrig_v20"][c_idx]),
            "n_st512": n_st512,
            "dtrig_shift_512_ns": dtrig_shift_512,
            "dloc_shift_512_ns": dloc_shift_512,
        }
        tsv_rows.append({
            "run": run,
            "period": period,
            "channel": cname,
            "n_total": rsum["n_total"],
            "n_blinded": rsum["n_blinded"],
            "n_single_muon": rsum["n_single_muon"],
            "n_good": n_good,
            "n_bcid_r50": int(rsum["ch_n_bcid_r50"][c_idx]),
            "n_dtrig_v20": int(rsum["ch_n_dtrig_v20"][c_idx]),
            "n_st512": n_st512,
            "n_st16": int(rsum["ch_n_st16"][c_idx]),
            "n_st4": int(rsum["ch_n_st4"][c_idx]),
            "t_ref_bcid_ns": "" if mu_b is None else f"{mu_b:.5f}",
            "sigma_bcid_ns": "" if sig_b is None else f"{sig_b:.4f}",
            "bcid_R": f"{r_conc:.4f}",
            "t_trig_rel_ref_ns": "" if mu_t is None else f"{mu_t:.5f}",
            "sigma_dtrig_ns": "" if sig_t is None else f"{sig_t:.4f}",
            "dtrig_f_core": f"{f_core:.4f}",
            "dtrig_shift_512_ns": "" if dtrig_shift_512 is None else f"{dtrig_shift_512:.4f}",
            "dloc_shift_512_ns": "" if dloc_shift_512 is None else f"{dloc_shift_512:.4f}",
            "bcid_method": f"{bcid_src}:{meth_b}",
            "trig_method": f"{trig_src}:{meth_t}",
        })

    return run, {
        "period": period,
        "n_total": rsum["n_total"],
        "n_grl_fail": rsum["n_grl_fail"],
        "n_non_colliding": rsum["n_non_colliding"],
        "n_blinded": rsum["n_blinded"],
        "n_single_muon": rsum["n_single_muon"],
        "channels": ch_results,
    }, tsv_rows


def cmd_fit_pass1(args: argparse.Namespace) -> None:
    t0 = time.perf_counter()
    with open(args.manifest) as f:
        manifest = json.load(f)
    expected_runs = {int(r) for r in manifest["runs"].keys()}

    files = sorted(glob.glob(os.path.join(args.input_dir, "*.root")))
    if not files:
        raise RuntimeError(f"No ROOT files found in {args.input_dir}")
    print(f"[fit-pass1] Reading {len(files)} shard files using {args.workers} workers...")

    merged_runs: dict[int, dict[str, Any]] = {}
    merged_hists: dict[int, dict[str, np.ndarray]] = defaultdict(dict)

    sum_keys = [
        "n_total", "n_grl_fail", "n_non_colliding", "n_blinded", "n_single_muon",
        "n_v20_ref_events", "n_v10_ref_events",
        "ch_n_good", "ch_n_st512", "ch_n_st16", "ch_n_st4",
        "ch_n_bcid_r50", "ch_n_bcid_all", "ch_n_dtrig_v20", "ch_n_dtrig_v10",
    ]

    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as ex:
        for res in ex.map(_read_pass1_file, files, chunksize=4):
            for r, rs in res["runs"].items():
                if r not in merged_runs:
                    merged_runs[r] = rs
                else:
                    cur = merged_runs[r]
                    for k in sum_keys:
                        cur[k] = cur[k] + rs[k]
                    cur["has_veto11"] = cur["has_veto11"] or rs["has_veto11"]
                    cur["has_preshower23"] = cur["has_preshower23"] or rs["has_preshower23"]
                    cur["has_muon"] = cur["has_muon"] or rs["has_muon"]
            for r, rh in res["hists"].items():
                dst = merged_hists[r]
                for hname, arr in rh.items():
                    if hname not in dst:
                        dst[hname] = arr
                    else:
                        dst[hname] = dst[hname] + arr

    present_runs = set(merged_runs.keys())
    missing_runs = sorted(expected_runs - present_runs)
    print(f"[fit-pass1] Merged {len(present_runs)} runs (expected {len(expected_runs)}, missing={len(missing_runs)}).")
    if missing_runs:
        print(f"[fit-pass1] WARNING: missing runs sample: {missing_runs[:20]}")

    total_events = sum(d["n_total"] for d in merged_runs.values())
    total_blinded = sum(d["n_blinded"] for d in merged_runs.values())
    total_single_mu = sum(d["n_single_muon"] for d in merged_runs.values())
    print(f"[fit-pass1] Totals: n_total={total_events:,} n_blinded={total_blinded:,} n_single_muon={total_single_mu:,}")

    fit_items = [(r, merged_runs[r], merged_hists[r]) for r in sorted(merged_runs.keys())]
    runs_out: dict[str, Any] = {}
    all_tsv_rows: list[dict[str, Any]] = []

    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as ex:
        for r, rout, tsv in ex.map(_fit_pass1_single_run, fit_items, chunksize=8):
            runs_out[str(r)] = rout
            all_tsv_rows.extend(tsv)

    # Fill any rare low-stat active channel nulls via same-(period, reco_tag) median fallback
    by_pt_bcid: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    by_pt_trig: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for r_str, rout in runs_out.items():
        tag = manifest["runs"].get(r_str, {}).get("reco_tag", rout["period"])
        per = rout["period"]
        for cname, cobj in rout["channels"].items():
            if cobj["t_ref_bcid"] is not None:
                by_pt_bcid[(per, tag, cname)].append(float(cobj["t_ref_bcid"]))
            if cobj["t_trig_rel_ref"] is not None:
                by_pt_trig[(per, tag, cname)].append(float(cobj["t_trig_rel_ref"]))

    n_fallbacks = 0
    n_masked = 0
    for r_str, rout in runs_out.items():
        tag = manifest["runs"].get(r_str, {}).get("reco_tag", rout["period"])
        per = rout["period"]
        for cname, cobj in rout["channels"].items():
            if "uncorrelated_masked" in cobj.get("bcid_method", "") or "uncorrelated_masked" in cobj.get("trig_method", ""):
                n_masked += 1
                continue
            if cobj["t_ref_bcid"] is None and by_pt_bcid[(per, tag, cname)]:
                vals = np.array(by_pt_bcid[(per, tag, cname)])
                ang = 2.0 * np.pi * vals / 25.0
                cobj["t_ref_bcid"] = round((math.atan2(float(np.mean(np.sin(ang))), float(np.mean(np.cos(ang)))) * 25.0 / (2.0 * math.pi)) % 25.0, 5)
                cobj["bcid_method"] = "period_fallback"
                n_fallbacks += 1
            if cobj["t_trig_rel_ref"] is None and by_pt_trig[(per, tag, cname)]:
                cobj["t_trig_rel_ref"] = round(float(np.median(by_pt_trig[(per, tag, cname)])), 5)
                cobj["trig_method"] = "period_fallback"
                n_fallbacks += 1

    compact_runs: dict[str, Any] = {}
    for r_str, rout in runs_out.items():
        ch_min: dict[str, Any] = {}
        for cname, cobj in rout["channels"].items():
            entry: dict[str, Any] = {}
            if cobj["t_ref_bcid"] is not None:
                entry["t_ref_bcid"] = round(float(cobj["t_ref_bcid"]), 4)
            if cobj["t_trig_rel_ref"] is not None:
                entry["t_trig_rel_ref"] = round(float(cobj["t_trig_rel_ref"]), 4)
            if entry:
                ch_min[cname] = entry
        compact_runs[r_str] = {"period": rout["period"], "channels": ch_min}

    out_payload = {
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "n_runs": len(compact_runs),
        "n_total_entries": int(total_events),
        "n_blinded_entries": int(total_blinded),
        "n_single_muon_entries": int(total_single_mu),
        "n_period_fallbacks": n_fallbacks,
        "n_uncorrelated_masked": n_masked,
        "trigger_reference_channel": "Veto20",
        "runs": compact_runs,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out_payload, f, separators=(",", ":"))
    size_kb = out_path.stat().st_size / 1024.0
    print(f"[fit-pass1] Wrote {out_path} ({size_kb:.1f} KB, n_period_fallbacks={n_fallbacks})")

    if args.summary_tsv:
        tsv_path = Path(args.summary_tsv)
        tsv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(tsv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_tsv_rows[0].keys()), delimiter="\t")
            writer.writeheader()
            writer.writerows(all_tsv_rows)
        print(f"[fit-pass1] Wrote {tsv_path} ({len(all_tsv_rows)} rows) in {time.perf_counter() - t0:.2f}s")


# ─────────────────────────────────────────────────────────────────────────────
# Pass 2 Reader / Iterative Weighted LOO Fitter
# ─────────────────────────────────────────────────────────────────────────────

def _read_pass2_file(path: str) -> dict[str, Any]:
    with _open_uproot_retry(path) as tf:
        p2s = tf["pass2_summary"].arrays(library="np")
        runs_summary: dict[int, dict[str, Any]] = {}
        hists_r_unwrap: dict[int, dict[str, np.ndarray]] = {}

        for idx in range(len(p2s["run"])):
            r = int(p2s["run"][idx])
            runs_summary[r] = {
                "run": r,
                "period": str(p2s["period"][idx]),
                "n_total": int(p2s["n_total"][idx]),
                "n_grl_fail": int(p2s["n_grl_fail"][idx]),
                "n_non_colliding": int(p2s["n_non_colliding"][idx]),
                "n_blinded": int(p2s["n_blinded"][idx]),
                "n_clean_1trk": int(p2s["n_clean_1trk"][idx]),
                "n_clean_2trk": int(p2s["n_clean_2trk"][idx]),
                "n_clean_3trk": int(p2s["n_clean_3trk"][idx]),
                "ch_n_unwrap_pass": p2s["ch_n_unwrap_pass"][idx].astype(np.int64),
                "ch_n_unwrap_fail": p2s["ch_n_unwrap_fail"][idx].astype(np.int64),
                "anchor_counts": p2s["anchor_counts"][idx].astype(np.int64),
            }
            rdir_name = f"run_{r}"
            rh: dict[str, np.ndarray] = {}
            if rdir_name in tf:
                rdir = tf[rdir_name]
                for hkey in rdir.keys(cycle=False):
                    rh[hkey] = rdir[hkey].values(flow=False).astype(np.int64)
            hists_r_unwrap[r] = rh

        ce = tf["calib_events"]
        rec_arrays = ce.arrays(library="np") if ce.num_entries > 0 else {}
        return {"runs": runs_summary, "hists": hists_r_unwrap, "events": rec_arrays, "n_events": ce.num_entries}


def _weighted_core_gauss(vals: np.ndarray, weights: np.ndarray) -> tuple[float, float, float]:
    """
    Robust weighted truncated Gaussian core estimate (mean, std, effective count).
    Uses weighted median/IQR initialization + 2 passes of +-2.5 sigma clipping.
    """
    m = np.isfinite(vals) & np.isfinite(weights) & (weights > 0.0)
    if np.count_nonzero(m) < 5:
        return 0.0, 0.35, 0.0
    v = vals[m].astype(np.float64)
    w = weights[m].astype(np.float64)

    order = np.argsort(v)
    vs = v[order]
    ws = w[order]
    cw = np.cumsum(ws)
    tot = cw[-1]
    if tot <= 0:
        return 0.0, 0.35, 0.0

    # Weighted quantiles 16%, 50%, 84%
    med = float(np.interp(0.50 * tot, cw, vs))
    q16 = float(np.interp(0.15865 * tot, cw, vs))
    q84 = float(np.interp(0.84135 * tot, cw, vs))
    sig_init = max(0.08, min(2.5, 0.5 * (q84 - q16)))

    mu = med
    sig = sig_init
    # Histogram core Gaussian fit if high stats, else truncated moments + analytical Gaussian variance correction
    for n_sig in (3.0, 2.5):
        keep = np.abs(v - mu) <= n_sig * max(sig, 0.12)
        if np.count_nonzero(keep) < 5:
            break
        vk = v[keep]
        wk = w[keep]
        wsum = float(np.sum(wk))
        mu = float(np.sum(wk * vk) / wsum)
        var = float(np.sum(wk * (vk - mu) ** 2) / wsum)
        # Correct variance truncation for symmetric +-n_sig Gaussian clip:
        # Var(|Z| < k) = 1 - 2*k*phi(k)/(Phi(k)-Phi(-k)) -> 2.5 sigma factor = 0.9163, 3.0 sigma = 0.9733
        trunc_fac = 0.9163 if abs(n_sig - 2.5) < 0.1 else 0.9733
        sig = math.sqrt(max(0.04 ** 2, var / trunc_fac))

    # For large samples (>150 unweighted points), do binned core Gaussian fit to resist asymmetric radiative tails
    if len(v) >= 150:
        lo = mu - 2.6 * sig
        hi = mu + 2.6 * sig
        bins = np.linspace(lo, hi, 35)
        hist, edges = np.histogram(v, bins=bins, weights=w)
        c = 0.5 * (edges[:-1] + edges[1:])
        pos = hist > 0
        if np.count_nonzero(pos) >= 6:
            try:
                popt, _ = curve_fit(
                    _gauss, c[pos], hist[pos],
                    p0=[float(np.max(hist)), mu, sig],
                    bounds=([0.0, lo, 0.04], [1e14, hi, 3.5]),
                    maxfev=1500,
                )
                mu = float(popt[1])
                sig = float(popt[2])
            except Exception:
                pass

    n_eff = float((np.sum(w) ** 2) / max(1e-12, float(np.sum(w ** 2))))
    return mu, sig, n_eff


def _interp_grid_missing(t_bar: np.ndarray, sigma_2d: np.ndarray, counts: np.ndarray, min_hits: int = 25) -> tuple[np.ndarray, np.ndarray]:
    """Fill sparse outer/corner cells (< min_hits) via inverse-distance neighbor interpolation."""
    tb = t_bar.reshape(GRID_N, GRID_N).copy()
    sg = sigma_2d.reshape(GRID_N, GRID_N).copy()
    cnt = counts.reshape(GRID_N, GRID_N)
    valid = cnt >= min_hits
    if not np.any(valid):
        return tb.ravel(), sg.ravel()

    ys, xs = np.mgrid[0:GRID_N, 0:GRID_N]
    vy, vx = np.where(valid)
    v_tb = tb[vy, vx]
    v_sg = sg[vy, vx]

    for ix in range(GRID_N):
        for iy in range(GRID_N):
            if valid[ix, iy]:
                continue
            d2 = (ix - vy) ** 2 + (iy - vx) ** 2
            inv_d = 1.0 / np.maximum(d2, 0.5) ** 1.5
            tb[ix, iy] = float(np.sum(inv_d * v_tb) / np.sum(inv_d))
            sg[ix, iy] = float(np.sum(inv_d * v_sg) / np.sum(inv_d))

    return tb.ravel(), sg.ravel()


def _eval_tw_vec(qs_table: list[float], dts_table: list[float], q: np.ndarray) -> np.ndarray:
    if not qs_table:
        return np.zeros_like(q, dtype=np.float64)
    return np.interp(q, np.asarray(qs_table, dtype=np.float64), np.asarray(dts_table, dtype=np.float64),
                     left=dts_table[0], right=dts_table[-1])


def _fit_power_law_3param(q_vals: np.ndarray, sig_obs: np.ndarray, q_weights: np.ndarray, default_sig: float) -> tuple[float, float, float, bool]:
    """Fit sigma(Q) = sqrt((A * Q^-a)^2 + c^2)."""
    m = np.isfinite(q_vals) & np.isfinite(sig_obs) & (q_vals > 0.5) & (sig_obs > 0.05) & (q_weights > 0)
    if np.count_nonzero(m) < 4:
        return 0.0, 0.5, default_sig, False
    qv = q_vals[m]
    sv = sig_obs[m]
    wv = 1.0 / np.sqrt(np.maximum(q_weights[m], 1.0))

    def model(qq: np.ndarray, A: float, a: float, c: float) -> np.ndarray:
        return np.sqrt((A * np.power(qq, -a)) ** 2 + c ** 2)

    try:
        popt, _ = curve_fit(
            model, qv, sv,
            p0=[max(0.5, sv[0] * math.sqrt(qv[0])), 0.55, max(0.08, float(np.min(sv)))],
            sigma=wv,
            bounds=([0.0, 0.15, 0.05], [500.0, 1.50, 3.00]),
            maxfev=3000,
        )
        return float(popt[0]), float(popt[1]), float(popt[2]), True
    except Exception:
        return 0.0, 0.5, float(np.median(sv)), False


def _calibrate_one_period(period: str, ev: dict[str, np.ndarray]) -> tuple[str, dict[str, Any]]:
    t_p0 = time.perf_counter()
    active = active_channels_for_period(period)
    active_set = set(active)

    is_cat0 = ev["is_cat0"] == 1
    is_cat1 = ev["is_cat1"] == 1
    n_c0 = int(np.count_nonzero(is_cat0))
    n_c1 = int(np.count_nonzero(is_cat1))

    # Extract arrays needed for LOO
    cat0_idx = np.where(is_cat0)[0]
    cat01_idx = np.where(is_cat0 | is_cat1)[0]
    w01 = np.where(is_cat0[cat01_idx], ev["w0"][cat01_idx], ev["w1"][cat01_idx]).astype(np.float64)

    n_ev = len(cat01_idx)
    valid_mask = ev["valid_mask"][cat01_idx]
    t2 = ev["t2"][cat01_idx].astype(np.float64)         # (N, 14)
    q_raw = ev["q_raw"][cat01_idx].astype(np.float64)   # (N, 14)
    trk_x = ev["trk_x"][cat01_idx].astype(np.float64)   # (N, 8)
    trk_y = ev["trk_y"][cat01_idx].astype(np.float64)   # (N, 8)
    is_c0_sub = is_cat0[cat01_idx]

    # Precompute grid indices per plane (0..7)
    plane_cell = np.full((n_ev, 8), -1, dtype=np.int32)
    plane_valid_150 = np.zeros((n_ev, 8), dtype=bool)
    for p in range(8):
        px = trk_x[:, p]
        py = trk_y[:, p]
        ok = np.isfinite(px) & np.isfinite(py) & (np.abs(px) < 150.0) & (np.abs(py) < 150.0)
        ix = np.clip(np.floor((px - GRID_MIN_MM) / GRID_STEP_MM).astype(np.int32), 0, GRID_N - 1)
        iy = np.clip(np.floor((py - GRID_MIN_MM) / GRID_STEP_MM).astype(np.int32), 0, GRID_N - 1)
        plane_cell[:, p] = ix * GRID_N + iy
        plane_valid_150[:, p] = ok

    # Initialize parameters
    n_cells = GRID_N * GRID_N
    t_bar = {c: np.zeros(n_cells, dtype=np.float64) for c in CHANNELS}
    sigma_2d = {c: np.full(n_cells, DEFAULT_SIGMAS[c], dtype=np.float64) for c in CHANNELS}
    amp_a = {c: np.zeros(n_cells, dtype=np.float64) for c in CHANNELS}
    power_a = {c: np.full(n_cells, 0.5, dtype=np.float64) for c in CHANNELS}
    floor_c = {c: np.full(n_cells, DEFAULT_SIGMAS[c], dtype=np.float64) for c in CHANNELS}
    has_pl = {c: np.zeros(n_cells, dtype=bool) for c in CHANNELS}
    tw_q: dict[str, list[float]] = {c: [] for c in CHANNELS}
    tw_dt: dict[str, list[float]] = {c: [] for c in CHANNELS}

    # Precompute MIP masks & fiducial flags per channel
    ch_valid_bit = np.zeros((n_ev, len(CHANNELS)), dtype=bool)
    ch_above_mip = np.zeros((n_ev, len(CHANNELS)), dtype=bool)
    ch_fid_tw = np.zeros((n_ev, len(CHANNELS)), dtype=bool)
    for c_idx, cname in enumerate(CHANNELS):
        if cname not in active_set:
            continue
        p_idx = CHANNEL_PLANE_IDX[c_idx]
        bit_ok = ((valid_mask & (1 << c_idx)) != 0) & np.isfinite(t2[:, c_idx]) & np.isfinite(q_raw[:, c_idx])
        bit_ok &= plane_valid_150[:, p_idx]
        # Avoid opposite-bar contamination in Timing01/Timing23
        if cname == "Timing01":
            bit_ok &= (trk_y[:, p_idx] < 10.0)
        elif cname == "Timing23":
            bit_ok &= (trk_y[:, p_idx] > -10.0)
        ch_valid_bit[:, c_idx] = bit_ok
        ch_above_mip[:, c_idx] = bit_ok & (q_raw[:, c_idx] > MIP_THRESHOLDS[cname])
        ch_fid_tw[:, c_idx] = bit_ok & (np.abs(trk_x[:, p_idx]) < 120.0) & (np.abs(trk_y[:, p_idx]) < 120.0)

    # Current calibrated times & weights matrix for primary downstream planes
    def eval_channel_sigma_arr(c_idx: int) -> np.ndarray:
        cname = CHANNELS[c_idx]
        p_idx = CHANNEL_PLANE_IDX[c_idx]
        cells = np.clip(plane_cell[:, p_idx], 0, n_cells - 1)
        qr = np.maximum(q_raw[:, c_idx], 0.5)
        sig = sigma_2d[cname][cells].copy()
        pl_mask = has_pl[cname][cells] & (qr > 1.0)
        if np.any(pl_mask):
            aa = amp_a[cname][cells][pl_mask]
            pa = power_a[cname][cells][pl_mask]
            fc = floor_c[cname][cells][pl_mask]
            sig[pl_mask] = np.sqrt((aa * np.power(qr[pl_mask], -pa)) ** 2 + fc ** 2)
        return np.clip(sig, 0.08, 3.00)

    def eval_channel_tbar_tw(c_idx: int) -> tuple[np.ndarray, np.ndarray]:
        cname = CHANNELS[c_idx]
        p_idx = CHANNEL_PLANE_IDX[c_idx]
        cells = np.clip(plane_cell[:, p_idx], 0, n_cells - 1)
        tb = t_bar[cname][cells]
        tw = _eval_tw_vec(tw_q[cname], tw_dt[cname], q_raw[:, c_idx])
        return tb, tw

    # 5 weighted Leave-One-Out iterations
    n_iters = 5
    for it in range(n_iters):
        # Compute primary downstream weighted sums for LOO
        w_prim = np.zeros((n_ev, len(CHANNELS)), dtype=np.float64)
        wt_prim = np.zeros((n_ev, len(CHANNELS)), dtype=np.float64)
        for j in PRIMARY_DOWNSTREAM_CH_INDICES:
            cname_j = CHANNELS[j]
            if cname_j not in active_set:
                continue
            ok_j = ch_above_mip[:, j]
            tb_j, tw_j = eval_channel_tbar_tw(j)
            sig_j = eval_channel_sigma_arr(j)
            w = np.where(ok_j, 1.0 / (sig_j ** 2), 0.0)
            w_prim[:, j] = w
            wt_prim[:, j] = np.where(ok_j, w * (t2[:, j] - tb_j - tw_j), 0.0)

        sum_w_all = np.sum(w_prim, axis=1)
        sum_wt_all = np.sum(wt_prim, axis=1)
        n_prim_all = np.sum(w_prim > 0, axis=1)

        # Anchor global gauge to primary downstream center
        gauge_num = 0.0
        gauge_den = 0.0

        # Update each active channel: 2D TOF & intrinsic 2D sigma
        for c_idx, cname in enumerate(CHANNELS):
            if cname not in active_set:
                continue
            is_prim = c_idx in PRIMARY_DOWNSTREAM_CH_INDICES
            sum_w_loo = sum_w_all - (w_prim[:, c_idx] if is_prim else 0.0)
            sum_wt_loo = sum_wt_all - (wt_prim[:, c_idx] if is_prim else 0.0)
            n_loo = n_prim_all - (w_prim[:, c_idx] > 0).astype(np.int32)

            loo_ok = (n_loo >= 3) & (sum_w_loo > 0.0)
            t_loo = np.where(loo_ok, sum_wt_loo / np.maximum(sum_w_loo, 1e-12), np.nan)
            var_loo = np.where(loo_ok, 1.0 / np.maximum(sum_w_loo, 1e-12), np.nan)

            tw_cur = _eval_tw_vec(tw_q[cname], tw_dt[cname], q_raw[:, c_idx])
            sel_2d = is_c0_sub & ch_above_mip[:, c_idx] & loo_ok
            res_2d = (t2[:, c_idx] - tw_cur) - t_loo

            p_idx = CHANNEL_PLANE_IDX[c_idx]
            cells = plane_cell[:, p_idx]

            tb_new = t_bar[cname].copy()
            sg_new = sigma_2d[cname].copy()
            cnt_new = np.zeros(n_cells, dtype=np.int64)

            idx_sel = np.where(sel_2d)[0]
            cells_sel = cells[idx_sel]
            order_c = np.argsort(cells_sel, kind="mergesort")
            cells_sorted = cells_sel[order_c]
            idx_sorted = idx_sel[order_c]
            unique_cells, starts, counts = np.unique(cells_sorted, return_index=True, return_counts=True)

            for uc, st_pos, uc_cnt in zip(unique_cells, starts, counts):
                if uc < 0 or uc >= n_cells:
                    continue
                cnt_new[uc] = int(uc_cnt)
                if uc_cnt < 15:
                    continue
                ev_ids = idx_sorted[st_pos: st_pos + uc_cnt]
                r_cell = res_2d[ev_ids]
                w_cell = ev["w0"][cat01_idx[ev_ids]]
                mu_c, sig_obs_c, _ = _weighted_core_gauss(r_cell, w_cell)
                mean_var_loo = float(np.median(var_loo[ev_ids]))
                sig_int = math.sqrt(max(0.06 ** 2, sig_obs_c ** 2 - mean_var_loo))
                tb_new[uc] = mu_c
                sg_new[uc] = sig_int

            tb_interp, sg_interp = _interp_grid_missing(tb_new, sg_new, cnt_new, min_hits=20)
            t_bar[cname] = tb_interp
            sigma_2d[cname] = np.clip(sg_interp, 0.08, 3.00)

            if cname in ("Veto10", "Veto20", "Veto21"):
                center_cells = [5 * GRID_N + 5, 5 * GRID_N + 6, 6 * GRID_N + 5, 6 * GRID_N + 6]
                w_g = 1.0 / max(0.01, float(np.mean(sigma_2d[cname][center_cells]) ** 2))
                gauge_num += w_g * float(np.mean(t_bar[cname][center_cells]))
                gauge_den += w_g

            # Time-walk & charge resolution on iterations >= 1
            if it >= 1:
                sel_tw = ch_fid_tw[:, c_idx] & loo_ok
                res_tw = (t2[:, c_idx] - t_bar[cname][cells]) - t_loo
                is_ps = cname.startswith("Preshower")
                if is_ps:
                    q_edges = np.array([0.5, 0.9, 1.4, 2.1, 3.1, 4.5, 6.5, 10.0, 20.0])
                    q_anchor_lo, q_anchor_hi = (1.2, 5.0) if cname in ("Preshower2", "Preshower3") else (3.2, 8.5)
                else:
                    q_edges = np.array([12.0, 18.0, 25.0, 35.0, 48.0, 63.0, 80.0, 105.0, 145.0, 220.0])
                    q_anchor_lo, q_anchor_hi = 63.0, 150.0

                idx_tw = np.where(sel_tw)[0]
                if len(idx_tw) >= 100:
                    qt = q_raw[idx_tw, c_idx]
                    rt = res_tw[idx_tw]
                    wt = w01[idx_tw]
                    vlt = var_loo[idx_tw]

                    # Compute baseline anchor at MIP range so delta_t -> 0 at normal MIP
                    m_anc = (qt >= q_anchor_lo) & (qt <= q_anchor_hi)
                    tw_base = 0.0
                    if np.count_nonzero(m_anc) >= 30:
                        tw_base, _, _ = _weighted_core_gauss(rt[m_anc], wt[m_anc])

                    pts_q = []
                    pts_dt = []
                    pl_q = []
                    pl_sig = []
                    pl_w = []
                    for b in range(len(q_edges) - 1):
                        mb = (qt >= q_edges[b]) & (qt < q_edges[b + 1])
                        cnt_b = int(np.count_nonzero(mb))
                        if cnt_b < 25:
                            continue
                        mu_b, sig_b_obs, n_eff_b = _weighted_core_gauss(rt[mb], wt[mb])
                        q_med = float(np.median(qt[mb]))
                        sig_b_int = math.sqrt(max(0.06 ** 2, sig_b_obs ** 2 - float(np.median(vlt[mb]))))
                        pts_q.append(round(q_med, 2))
                        pts_dt.append(round(mu_b - tw_base, 4))
                        pl_q.append(q_med)
                        pl_sig.append(sig_b_int)
                        pl_w.append(n_eff_b)

                    if pts_q:
                        # Anchor flat extrapolation above high-Q MIP edge to 0.0 ns smoothly
                        pts_q_out = []
                        pts_dt_out = []
                        for pq, pdt in zip(pts_q, pts_dt):
                            pts_q_out.append(pq)
                            pts_dt_out.append(0.0 if pq >= q_anchor_hi else pdt)
                        if pts_q_out[-1] < (30.0 if is_ps else 300.0):
                            pts_q_out.append(30.0 if is_ps else 300.0)
                            pts_dt_out.append(0.0)
                        tw_q[cname] = pts_q_out
                        tw_dt[cname] = pts_dt_out

                    # Channel-level floored power-law fit sigma(Q) = sqrt((A * Q^-a)^2 + c^2)
                    A_ch, a_ch, c_ch, ok_pl = _fit_power_law_3param(
                        np.asarray(pl_q), np.asarray(pl_sig), np.asarray(pl_w), DEFAULT_SIGMAS[cname]
                    )
                    if ok_pl:
                        # Scale cell floor c_{ab} to match cell sigma_2d at median MIP Q
                        m_medq = is_c0_sub & ch_above_mip[:, c_idx]
                        q_mip_cells = np.full(n_cells, float(np.median(q_raw[m_medq, c_idx])) if np.any(m_medq) else 90.0)
                        for uc, st_pos, uc_cnt in zip(unique_cells, starts, counts):
                            if uc < 0 or uc >= n_cells or uc_cnt < 25:
                                continue
                            q_mip_cells[uc] = float(np.median(q_raw[idx_sorted[st_pos: st_pos + uc_cnt], c_idx]))

                        for k in range(n_cells):
                            pl_term = A_ch * (max(q_mip_cells[k], 1.0) ** (-a_ch))
                            s2_val = sigma_2d[cname][k]
                            if s2_val > pl_term + 0.03:
                                fc_k = math.sqrt(max(0.05 ** 2, s2_val ** 2 - pl_term ** 2))
                            else:
                                fc_k = max(0.05, min(c_ch, 0.7 * s2_val))
                            amp_a[cname][k] = A_ch
                            power_a[cname][k] = a_ch
                            floor_c[cname][k] = fc_k
                            has_pl[cname][k] = True

        # Remove global gauge drift once per iteration so t=0 stays pinned across iterations
        gauge_shift = gauge_num / max(1e-12, gauge_den)
        for cname in active:
            t_bar[cname] -= gauge_shift

    # Package per-period output matching TimingCalibration.cxx JSON schema
    ch_out: dict[str, Any] = {}
    for cname in active:
        ch_out[cname] = {
            "t_bar": [round(float(x), 4) for x in t_bar[cname]],
            "sigma_2d": [round(float(x), 4) for x in sigma_2d[cname]],
            "amp_a": [round(float(x), 4) for x in amp_a[cname]],
            "power_a": [round(float(x), 4) for x in power_a[cname]],
            "floor_c": [round(float(x), 4) for x in floor_c[cname]],
            "has_power_law": [bool(x) for x in has_pl[cname]],
            "time_walk_q": tw_q[cname],
            "time_walk_dt": tw_dt[cname],
        }

    print(f"[fit-pass2] Calibrated period {period:16s}: n_cat0={n_c0:,} n_cat1={n_c1:,} "
          f"active_ch={len(active)} wall={time.perf_counter() - t_p0:.2f}s")
    return period, {"channels": ch_out, "n_cat0": n_c0, "n_cat1": n_c1}


def _calibrate_one_period_star(pair: tuple[str, dict[str, np.ndarray]]) -> tuple[str, dict[str, Any]]:
    return _calibrate_one_period(pair[0], pair[1])


def cmd_fit_pass2(args: argparse.Namespace) -> None:
    t0 = time.perf_counter()
    with open(args.manifest) as f:
        manifest = json.load(f)
    expected_runs = {int(r) for r in manifest["runs"].keys()}

    files = sorted(glob.glob(os.path.join(args.input_dir, "*.root")))
    if not files:
        raise RuntimeError(f"No Pass 2 shard files found in {args.input_dir}")
    print(f"[fit-pass2] Reading {len(files)} Pass 2 shard files using {args.workers} workers...")

    merged_runs: dict[int, dict[str, Any]] = {}
    merged_h_unwrap: dict[int, dict[str, np.ndarray]] = defaultdict(dict)
    event_chunks: list[dict[str, np.ndarray]] = []
    sum_keys = [
        "n_total", "n_grl_fail", "n_non_colliding", "n_blinded",
        "n_clean_1trk", "n_clean_2trk", "n_clean_3trk",
        "ch_n_unwrap_pass", "ch_n_unwrap_fail", "anchor_counts",
    ]

    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as ex:
        for res in ex.map(_read_pass2_file, files, chunksize=4):
            for r, rs in res["runs"].items():
                if r not in merged_runs:
                    merged_runs[r] = rs
                else:
                    cur = merged_runs[r]
                    for k in sum_keys:
                        cur[k] = cur[k] + rs[k]
            for r, rh in res["hists"].items():
                dst = merged_h_unwrap[r]
                for hname, arr in rh.items():
                    if hname not in dst:
                        dst[hname] = arr
                    else:
                        dst[hname] = dst[hname] + arr
            if res["n_events"] > 0 and res["events"]:
                event_chunks.append(res["events"])

    present_runs = set(merged_runs.keys())
    missing_runs = sorted(expected_runs - present_runs)
    print(f"[fit-pass2] Merged {len(present_runs)} runs (expected {len(expected_runs)}, missing={len(missing_runs)}).")

    total_entries = sum(d["n_total"] for d in merged_runs.values())
    total_blinded = sum(d["n_blinded"] for d in merged_runs.values())
    total_1trk = sum(d["n_clean_1trk"] for d in merged_runs.values())
    total_2trk = sum(d["n_clean_2trk"] for d in merged_runs.values())
    total_3trk = sum(d["n_clean_3trk"] for d in merged_runs.values())
    print(f"[fit-pass2] Entries={total_entries:,} Blinded={total_blinded:,} "
          f"1-trk={total_1trk:,} 2-trk={total_2trk:,} 3-trk={total_3trk:,}")

    # Concatenate all stratified calib_events
    all_ev: dict[str, np.ndarray] = {}
    branch_names = list(event_chunks[0].keys())
    for k in branch_names:
        all_ev[k] = np.concatenate([chunk[k] for chunk in event_chunks], axis=0)
    # Canonical sort by (run, eventID)
    order = np.lexsort((all_ev["eventID"], all_ev["run"]))
    for k in branch_names:
        all_ev[k] = all_ev[k][order]
    n_tot_ev = len(all_ev["run"])
    print(f"[fit-pass2] Total stratified calib_events={n_tot_ev:,}")

    # Save compact merged calib_events + unwrap histograms for closure validation if requested
    if args.merged_calib_events:
        mpath = Path(args.merged_calib_events)
        mpath.parent.mkdir(parents=True, exist_ok=True)
        with uproot.recreate(str(mpath)) as outf:
            # Write compressed merged calib_events TTree cleanly
            outf["calib_events"] = {k: all_ev[k] for k in branch_names}
            # Write pass2_summary aggregated by period & channel
            per_list = []
            for r in sorted(merged_runs.keys()):
                per_list.append(period_for_run(r))
            outf["pass2_summary"] = {
                "run": np.array(sorted(merged_runs.keys()), dtype=np.int32),
                "n_total": np.array([merged_runs[r]["n_total"] for r in sorted(merged_runs.keys())], dtype=np.uint64),
                "n_grl_fail": np.array([merged_runs[r]["n_grl_fail"] for r in sorted(merged_runs.keys())], dtype=np.uint64),
                "n_non_colliding": np.array([merged_runs[r]["n_non_colliding"] for r in sorted(merged_runs.keys())], dtype=np.uint64),
                "n_blinded": np.array([merged_runs[r]["n_blinded"] for r in sorted(merged_runs.keys())], dtype=np.uint64),
                "n_clean_1trk": np.array([merged_runs[r]["n_clean_1trk"] for r in sorted(merged_runs.keys())], dtype=np.uint64),
                "n_clean_2trk": np.array([merged_runs[r]["n_clean_2trk"] for r in sorted(merged_runs.keys())], dtype=np.uint64),
                "n_clean_3trk": np.array([merged_runs[r]["n_clean_3trk"] for r in sorted(merged_runs.keys())], dtype=np.uint64),
                "ch_n_unwrap_pass": np.stack([merged_runs[r]["ch_n_unwrap_pass"] for r in sorted(merged_runs.keys())]),
                "ch_n_unwrap_fail": np.stack([merged_runs[r]["ch_n_unwrap_fail"] for r in sorted(merged_runs.keys())]),
                "anchor_counts": np.stack([merged_runs[r]["anchor_counts"] for r in sorted(merged_runs.keys())]),
            }
            # Aggregate r_unwrap histograms per period & channel
            r_edges = np.linspace(0.0, 12.5, 126)
            for per in PERIOD_ORDER:
                for c_idx, cname in enumerate(CHANNELS):
                    acc = np.zeros(125, dtype=np.int64)
                    hname = f"h_r_unwrap_{cname}"
                    for r, rh in merged_h_unwrap.items():
                        if period_for_run(r) == per and hname in rh:
                            acc += rh[hname]
                    if np.sum(acc) > 0:
                        outf[f"h_r_unwrap_{per}_{cname}"] = (acc, r_edges)
        print(f"[fit-pass2] Wrote compact merged validation file {mpath} ({mpath.stat().st_size / 1e6:.1f} MB)")

    # Write unwrap audit TSV
    if args.unwrap_tsv:
        utsv = Path(args.unwrap_tsv)
        utsv.parent.mkdir(parents=True, exist_ok=True)
        urows = []
        for per in PERIOD_ORDER:
            per_runs = [r for r in merged_runs if period_for_run(r) == per]
            p_pass = np.sum([merged_runs[r]["ch_n_unwrap_pass"] for r in per_runs], axis=0)
            p_fail = np.sum([merged_runs[r]["ch_n_unwrap_fail"] for r in per_runs], axis=0)
            for c_idx, cname in enumerate(CHANNELS):
                tot_u = int(p_pass[c_idx] + p_fail[c_idx])
                if tot_u == 0:
                    continue
                urows.append({
                    "period": per,
                    "channel": cname,
                    "n_pass": int(p_pass[c_idx]),
                    "n_fail": int(p_fail[c_idx]),
                    "n_total": tot_u,
                    "fail_rate_pct": f"{100.0 * p_fail[c_idx] / tot_u:.5f}",
                })
        with open(utsv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(urows[0].keys()), delimiter="\t")
            writer.writeheader()
            writer.writerows(urows)
        print(f"[fit-pass2] Wrote {utsv}")

    # Partition events by period and calibrate all 7 periods in parallel across workers
    run_vec = all_ev["run"]
    ev_periods = np.empty(n_tot_ev, dtype=object)
    # Vectorized period assignment
    ev_periods[:] = "2026"
    ev_periods[run_vec < 21500] = "2025"
    ev_periods[run_vec < 18500] = "2024_postCaloNu"
    ev_periods[run_vec <= 16924] = "2024_CaloNu"
    ev_periods[run_vec < 15821] = "2024_preCaloNu"
    ev_periods[run_vec < 13000] = "2023"
    ev_periods[run_vec < 10000] = "2022"

    period_tasks = []
    for per in PERIOD_ORDER:
        m = ev_periods == per
        if not np.any(m):
            continue
        sub_ev = {k: all_ev[k][m] for k in branch_names}
        period_tasks.append((per, sub_ev))

    periods_out: dict[str, Any] = {}
    with concurrent.futures.ProcessPoolExecutor(max_workers=min(args.workers, len(period_tasks))) as ex:
        for per, pout in ex.map(_calibrate_one_period_star, period_tasks):
            periods_out[per] = pout

    out_json = {
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "grid_n": GRID_N,
        "grid_min_mm": GRID_MIN_MM,
        "grid_max_mm": GRID_MAX_MM,
        "n_calib_events": n_tot_ev,
        "n_total_entries": int(total_entries),
        "n_blinded_entries": int(total_blinded),
        "periods": {p: periods_out[p] for p in PERIOD_ORDER if p in periods_out},
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out_json, f, separators=(",", ":"))
    size_kb = out_path.stat().st_size / 1024.0
    print(f"[fit-pass2] Wrote {out_path} ({size_kb:.1f} KB) in {time.perf_counter() - t0:.2f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage T1 scintillator timing calibration fitter")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("fit-pass1", help="Fit Pass 1 per-run bcid/triggertime offsets")
    p1.add_argument("--input-dir", required=True)
    p1.add_argument("--manifest", default="AnalysisZipFramework/config/timing_calib/run3_timing_manifest.json")
    p1.add_argument("--output", default="AnalysisZipFramework/config/timing_calib/ref_offsets_run3.json")
    p1.add_argument("--summary-tsv", default="workbook/stage212_timing_t1/pass1_run_offsets_summary.tsv")
    p1.add_argument("--workers", type=int, default=28)

    p2 = sub.add_parser("fit-pass2", help="Run 5-iteration weighted LOO calibration for Pass 2")
    p2.add_argument("--input-dir", required=True)
    p2.add_argument("--manifest", default="AnalysisZipFramework/config/timing_calib/run3_timing_manifest.json")
    p2.add_argument("--ref-offsets", default="AnalysisZipFramework/config/timing_calib/ref_offsets_run3.json")
    p2.add_argument("--output", default="AnalysisZipFramework/config/timing_calib/tof_maps_run3.json")
    p2.add_argument("--merged-calib-events", default="ntuples/timing_stage212/pass2_merged_calib_events.root")
    p2.add_argument("--unwrap-tsv", default="workbook/stage212_timing_t1/pass2_unwrap_audit.tsv")
    p2.add_argument("--workers", type=int, default=28)

    args = parser.parse_args()
    if args.cmd == "fit-pass1":
        cmd_fit_pass1(args)
    else:
        cmd_fit_pass2(args)


if __name__ == "__main__":
    main()
