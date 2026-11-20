#!/usr/bin/env python3
"""
Stage T6 (Stage 217) Multi-Worker Physics Aggregator, Closure Auditor, and Publication Plotter:
  1. Run-by-run & period-by-period 5-year (2022-2026, 335.92 fb^-1) yield & timing resolution stability.
  2. Quantitative root-cause attribution (crossingAngle, broken_ps_p0013, HV-off dead VetoNu runs, trigger bits).
  3. Preshower2/3 downstream reference t0_down resolution, redundancy, and zero-bias verification.
  4. VetoGm0/1 in-situ 2D aperture, timing calibration, active luminosity audit, and grazing-muon B4 bound.
Strictly enforces 100% orthogonal SR-ZoneB blinding on all collision data.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import glob
import json
import math
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import uproot
from scipy import optimize, stats

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.patches import Rectangle

REPO_DIR = Path("/eos/home-x/xcheng/FASER/nu_muAnalysis")
DEFAULT_SHARD_DIR = REPO_DIR / "ntuples/timing_stage217"
DEFAULT_MANIFEST = REPO_DIR / "AnalysisZipFramework/config/timing_calib/run3_timing_manifest.json"
DEFAULT_CALIB_DIR = REPO_DIR / "AnalysisZipFramework/config/timing_calib"
DEFAULT_T5_SUMMARY = REPO_DIR / "workbook/stage216_timing_t5/t5_summary.json"
DEFAULT_OUT_DIR = REPO_DIR / "workbook/stage217_timing_t6"

PERIOD_ORDER = [
    "2022",
    "2023",
    "2024_preCaloNu",
    "2024_CaloNu",
    "2024_postCaloNu",
    "2025",
    "2026",
]

PS_GROUP_NAMES = [
    "y2025_p0013_healthy",
    "y2025_p0013_brokenPS",
    "y2025_p0014",
    "y2026_p0015_earlyPS3",
    "y2026_p0015_lateNoPS3",
    "genie_mc24",
    "fluka_mc24",
]
PS_STRATA = ["all", "v2sat", "nomuon", "v2sat_nomuon"]


def _decode_str(v: Any) -> str:
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    return str(v)


def _read_th1_arr(h) -> tuple[np.ndarray, np.ndarray]:
    vals, edges = h.to_numpy(flow=False)
    return vals.astype(np.float64), edges.astype(np.float64)


def _read_th2_arr(h) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    vals, xedges, yedges = h.to_numpy(flow=False)
    return vals.astype(np.float64), xedges.astype(np.float64), yedges.astype(np.float64)


def read_one_shard(item: tuple[str, str]) -> dict[str, Any]:
    mode, fpath = item
    run_rows: list[dict[str, Any]] = []
    ps_hists: dict[tuple[str, str], tuple[np.ndarray, np.ndarray]] = {}
    gm_hists: dict[tuple[str, str], Any] = {}
    gm_recs: dict[str, np.ndarray] | None = None

    with uproot.open(fpath) as uf:
        top_keys = {k.split(";")[0] for k in uf.keys()}
        if "t6_run_summary" in top_keys:
            arr = uf["t6_run_summary"].arrays(library="np")
            n = len(arr["run"])
            cols = list(arr.keys())
            for i in range(n):
                row: dict[str, Any] = {"mode": mode}
                for c in cols:
                    val = arr[c][i]
                    if c in ("period", "fill_hist"):
                        row[c] = _decode_str(val)
                    elif hasattr(val, "item"):
                        row[c] = val.item()
                    else:
                        row[c] = val
                run_rows.append(row)

        if "preshower23_study" in top_keys:
            ps_dir = uf["preshower23_study"]
            for gk in {k.split(";")[0] for k in ps_dir.keys(recursive=False)}:
                gdir = ps_dir[gk]
                for hk in {k.split(";")[0] for k in gdir.keys(recursive=False)}:
                    ps_hists[(gk, hk)] = _read_th1_arr(gdir[hk])

        if "vetogm_study" in top_keys:
            gm_dir = uf["vetogm_study"]
            for ek in {k.split(";")[0] for k in gm_dir.keys(recursive=False)}:
                edir = gm_dir[ek]
                for hk in {k.split(";")[0] for k in edir.keys(recursive=False)}:
                    obj = edir[hk]
                    if hk.startswith("h2_"):
                        gm_hists[(ek, hk)] = _read_th2_arr(obj)
                    else:
                        gm_hists[(ek, hk)] = _read_th1_arr(obj)

        if "t6_vetogm_events" in top_keys and uf["t6_vetogm_events"].num_entries > 0:
            gm_recs = uf["t6_vetogm_events"].arrays(library="np")
            if mode == "data" and len(gm_recs["run"]) > 0:
                bad = (
                    (gm_recs["region"] == 1)
                    & (gm_recs["zone_a_era"] == 0)
                    & ((~np.isfinite(gm_recs["dt0"])) | (~np.isfinite(gm_recs["dt1"])) | (gm_recs["dt0"] > 1.5) | (gm_recs["dt1"] > 1.5))
                )
                if np.any(bad):
                    raise RuntimeError(f"BLINDING VIOLATION in {fpath}: unblinded SR-ZoneB data record!")

    return {
        "mode": mode,
        "run_rows": run_rows,
        "ps_hists": ps_hists,
        "gm_hists": gm_hists,
        "gm_recs": gm_recs,
    }


def merge_shards(results: list[dict[str, Any]]) -> tuple[
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, str], tuple[np.ndarray, np.ndarray]],
    dict[tuple[str, str], Any],
    dict[str, np.ndarray],
]:
    merged_runs: dict[tuple[str, int], dict[str, Any]] = {}
    sum_cols = [
        "n_total", "n_grl_pass", "n_colliding", "n_phys_trig", "n_long_trk",
        "n_trig_bit8", "n_trig_bit16", "n_trig_bit32", "n_trig_bit64",
        "n_blinded", "n_no_offsets", "ca_cnt",
        "n_clean_1trk_nom", "n_clean_1trk_eff",
        "n_cr_prompt_all_nom", "n_cr_prompt_2hit_nom", "n_cr_prompt_u1p0_nom",
        "n_cr_prompt_all_eff", "n_cr_prompt_2hit_eff",
        "n_sr_zonea_red30_nom", "n_sr_zonea_raw40_nom", "n_sr_zonea_era_nom",
        "n_sr_zonea_red30_eff", "n_sr_zonea_era_eff",
        "n_cr_geom_all_nom", "n_cr_geom_prompt_nom", "n_cr_geom_zonea_nom",
        "n_cr_geom_wp_primary_with_nom", "n_cr_geom_wp_primary_no_nom",
        "n_cr_geom_all_eff", "n_cr_geom_prompt_eff", "n_cr_geom_wp_primary_eff",
        "n_cr_edge_vn_all_nom", "n_cr_edge_vn_zonea_nom", "n_cr_edge_vn_zoneb_nom",
        "n_cr_edge_vn_wp_primary_nom", "n_cr_edge_vn_all_eff",
        "dt0_with_cnt", "dt1_with_cnt", "dt0_no_cnt", "dt1_no_cnt",
        "down_with_cnt", "down_no_cnt", "down_with_ge2", "down_with_ge3",
        "down_no_ge2", "down_no_ge3", "shift_cnt",
        "n_v2_sat", "n_v2_sat_down_with", "n_v2_sat_down_no",
        "n_no_muon", "n_no_muon_down_with", "n_no_muon_down_no",
        "n_downb_with_ge1", "n_downb_with_ge2", "n_downb_no_ge1", "n_downb_no_ge2",
        "n_gm_denom", "n_gm0_q10", "n_gm0_q20", "n_gm1_q10", "n_gm1_q20",
    ]
    float_sum_cols = [
        "ca_sum", "ca_sum2",
        "dt0_with_sum", "dt0_with_sum2", "dt1_with_sum", "dt1_with_sum2",
        "dt0_no_sum", "dt0_no_sum2", "dt1_no_sum", "dt1_no_sum2",
        "sigt0_with_sum", "sigt0_with_sum2", "sigt0_no_sum", "sigt0_no_sum2",
        "shift_t0_sum", "shift_t0_sum2",
    ]
    bool_or_cols = [
        "is_mc", "has_reduced_charge", "has_ps23", "has_vetogm",
        "broken_ps_p0013", "dead_vetonu_hv",
    ]

    fill_maps: dict[tuple[str, int], dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for res in results:
        for row in res["run_rows"]:
            key = (row["mode"], int(row["run"]))
            fh = str(row.get("fill_hist", ""))
            if fh:
                for tok in fh.split(","):
                    if ":" in tok:
                        fs, cs = tok.split(":", 1)
                        fill_maps[key][int(fs)] += int(cs)
            if key not in merged_runs:
                merged_runs[key] = dict(row)
                continue
            dst = merged_runs[key]
            for c in sum_cols:
                dst[c] = int(dst[c]) + int(row[c])
            for c in float_sum_cols:
                dst[c] = float(dst[c]) + float(row[c])
            for c in bool_or_cols:
                dst[c] = bool(dst[c]) or bool(row[c])
            dst["gm0_qmax"] = max(float(dst["gm0_qmax"]), float(row["gm0_qmax"]))
            dst["gm1_qmax"] = max(float(dst["gm1_qmax"]), float(row["gm1_qmax"]))

    for key, dst in merged_runs.items():
        fm = fill_maps.get(key)
        if fm:
            best_fill, best_cnt = max(fm.items(), key=lambda kv: (kv[1], -kv[0]))
            dst["fill_mode"] = int(best_fill)
            dst["fill_mode_cnt"] = int(best_cnt)
            dst["fill_set"] = sorted(fm.keys())
        else:
            dst["fill_mode"] = -1
            dst["fill_mode_cnt"] = 0
            dst["fill_set"] = []

    merged_ps: dict[tuple[str, str], tuple[np.ndarray, np.ndarray]] = {}
    for res in results:
        for k, (v, edges) in res["ps_hists"].items():
            if k not in merged_ps:
                merged_ps[k] = (v.copy(), edges)
            else:
                merged_ps[k][0][:] += v

    merged_gm: dict[tuple[str, str], Any] = {}
    for res in results:
        for k, item in res["gm_hists"].items():
            if k not in merged_gm:
                if len(item) == 2:
                    merged_gm[k] = (item[0].copy(), item[1])
                else:
                    merged_gm[k] = (item[0].copy(), item[1], item[2])
            else:
                merged_gm[k][0][:] += item[0]

    rec_chunks = [res["gm_recs"] for res in results if res["gm_recs"] is not None]
    merged_gm_recs: dict[str, np.ndarray] = {}
    if rec_chunks:
        keys = list(rec_chunks[0].keys())
        for k in keys:
            merged_gm_recs[k] = np.concatenate([c[k] for c in rec_chunks], axis=0)

    return merged_runs, merged_ps, merged_gm, merged_gm_recs


def _mean_std(cnt: int, s1: float, s2: float) -> tuple[float, float]:
    if cnt <= 0:
        return float("nan"), float("nan")
    mu = s1 / cnt
    var = max(0.0, s2 / cnt - mu * mu)
    return mu, math.sqrt(var)


def _fit_gauss_core(
    vals: np.ndarray,
    edges: np.ndarray,
    fit_range: tuple[float, float] = (-1.3, 1.3),
    seed_range: tuple[float, float] = (-2.0, 2.0),
) -> tuple[float, float, float, float]:
    centers = 0.5 * (edges[:-1] + edges[1:])
    m_seed = (centers >= seed_range[0]) & (centers <= seed_range[1]) & (vals > 0)
    if np.sum(vals[m_seed]) < 50:
        return float("nan"), float("nan"), float("nan"), float("nan")
    p_seed = vals[m_seed]
    x_seed = centers[m_seed]
    mu0 = float(np.sum(x_seed * p_seed) / np.sum(p_seed))
    sig0 = max(0.08, math.sqrt(float(np.sum(((x_seed - mu0) ** 2) * p_seed) / np.sum(p_seed))))
    amp0 = float(np.max(p_seed))

    m_fit = (centers >= fit_range[0]) & (centers <= fit_range[1]) & (vals >= 5.0)
    if np.sum(m_fit) < 6:
        m_fit = (centers >= fit_range[0]) & (centers <= fit_range[1]) & (vals > 0)
    if np.sum(m_fit) < 4:
        return mu0, float("nan"), sig0, float("nan")

    xf = centers[m_fit]
    yf = vals[m_fit]
    sigma_y = np.sqrt(np.maximum(yf, 1.0))

    def model(x, amp, mu, sig):
        return amp * np.exp(-0.5 * ((x - mu) / np.maximum(sig, 1e-4)) ** 2)

    try:
        popt, pcov = optimize.curve_fit(
            model, xf, yf, p0=[amp0, mu0, sig0], sigma=sigma_y, absolute_sigma=True,
            bounds=([0.0, fit_range[0], 0.03], [np.inf, fit_range[1], 3.0]), maxfev=5000,
        )
        perr = np.sqrt(np.diag(pcov))
        return float(popt[1]), float(perr[1]), float(popt[2]), float(perr[2])
    except Exception:
        return mu0, float("nan"), sig0, float("nan")


def _clopper_pearson_upper(k: int, n: int, cl: float = 0.90) -> float:
    if n <= 0:
        return 1.0
    if k >= n:
        return 1.0
    alpha = 1.0 - cl
    return float(stats.beta.ppf(1.0 - alpha, k + 1, max(n - k, 1)))


def _poisson_upper(k: int, cl: float = 0.90) -> float:
    alpha = 1.0 - cl
    return float(0.5 * stats.chi2.ppf(1.0 - alpha, 2 * (k + 1)))


def _crossing_regime(ca: float) -> str:
    if not math.isfinite(ca):
        return "unknown"
    if ca < -100.0:
        return "CA_-160urad"
    if ca > 100.0:
        return "CA_+150/+160urad"
    return "CA_other"


def analyze_all(args: argparse.Namespace) -> None:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    shard_dir = Path(args.shard_dir)
    man = json.loads(Path(args.manifest).read_text())
    man_runs = {int(k): v for k, v in man["runs"].items()}

    items: list[tuple[str, str]] = []
    for mode in ("data", "fluka", "genie"):
        mdir = shard_dir / mode
        if mdir.exists():
            for fp in sorted(mdir.glob("*.root")):
                items.append((mode, str(fp)))
    if not items:
        raise RuntimeError(f"No Stage T6 shards found under {shard_dir}")

    print(f"[T6 analyze] Reading {len(items)} shards with {args.workers} workers...", flush=True)
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(read_one_shard, items, chunksize=8))

    merged_runs, merged_ps, merged_gm, gm_recs = merge_shards(results)
    del results
    data_runs = {r: v for (m, r), v in merged_runs.items() if m == "data"}
    genie_runs = {r: v for (m, r), v in merged_runs.items() if m == "genie"}
    fluka_runs = {r: v for (m, r), v in merged_runs.items() if m == "fluka"}

    missing_data_runs = sorted(set(man_runs.keys()) - set(data_runs.keys()))
    if missing_data_runs:
        raise RuntimeError(f"Missing {len(missing_data_runs)} manifest data runs in shards: {missing_data_runs[:10]}")
    print(f"[T6 analyze] Coverage: Data={len(data_runs)}/717 runs, GENIE={len(genie_runs)} MC runs, FLUKA={len(fluka_runs)} MC runs, blinded_skipped={sum(v['n_blinded'] for v in data_runs.values()):,}")

    # ── 1. Run-by-run stability table (717 rows) ────────────────────────────
    rbr_rows: list[dict[str, Any]] = []
    for r in sorted(man_runs.keys()):
        meta = man_runs[r]
        st = data_runs[r]
        lumi_pb = float(meta["lumi_pb_inverse"])
        lumi_fb = lumi_pb * 1e-3
        inv_fb = (1.0 / lumi_fb) if lumi_fb > 0 else float("nan")
        ca_mu, ca_sd = _mean_std(int(st["ca_cnt"]), float(st["ca_sum"]), float(st["ca_sum2"]))
        dt0_mu, dt0_sig = _mean_std(int(st["dt0_with_cnt"]), float(st["dt0_with_sum"]), float(st["dt0_with_sum2"]))
        dt1_mu, dt1_sig = _mean_std(int(st["dt1_with_cnt"]), float(st["dt1_with_sum"]), float(st["dt1_with_sum2"]))
        dt0_n_mu, dt0_n_sig = _mean_std(int(st["dt0_no_cnt"]), float(st["dt0_no_sum"]), float(st["dt0_no_sum2"]))
        st0_w_mu, _ = _mean_std(int(st["down_with_cnt"]), float(st["sigt0_with_sum"]), float(st["sigt0_with_sum2"]))
        st0_n_mu, _ = _mean_std(int(st["down_no_cnt"]), float(st["sigt0_no_sum"]), float(st["sigt0_no_sum2"]))
        sh_mu, sh_sd = _mean_std(int(st["shift_cnt"]), float(st["shift_t0_sum"]), float(st["shift_t0_sum2"]))

        if meta.get("dead_vetonu_hv", False):
            dq_flag = "dead_vetonu_hv"
        elif meta.get("broken_ps_p0013", False):
            dq_flag = "broken_ps_p0013"
        elif int(st["n_total"]) == 0:
            dq_flag = "empty_phys"
        else:
            dq_flag = "healthy"

        rbr_rows.append({
            "run": r,
            "period": meta["period"],
            "reco_tag": meta["reco_tag"],
            "dq_flag": dq_flag,
            "lumi_pb": lumi_pb,
            "lumi_fb": lumi_fb,
            "fill_mode": int(st["fill_mode"]),
            "ca_mean_urad": ca_mu,
            "ca_std_urad": ca_sd,
            "ca_regime": _crossing_regime(ca_mu),
            "n_total": int(st["n_total"]),
            "n_grl_pass": int(st["n_grl_pass"]),
            "n_colliding": int(st["n_colliding"]),
            "n_phys_trig": int(st["n_phys_trig"]),
            "n_long_trk": int(st["n_long_trk"]),
            "n_blinded": int(st["n_blinded"]),
            "n_clean_nom": int(st["n_clean_1trk_nom"]),
            "n_clean_eff": int(st["n_clean_1trk_eff"]),
            "n_cr_prompt_nom": int(st["n_cr_prompt_2hit_nom"]),
            "n_cr_prompt_eff": int(st["n_cr_prompt_2hit_eff"]),
            "n_sr_zonea_red30_nom": int(st["n_sr_zonea_red30_nom"]),
            "n_sr_zonea_raw40_nom": int(st["n_sr_zonea_raw40_nom"]),
            "n_sr_zonea_nom": int(st["n_sr_zonea_era_nom"]),
            "n_sr_zonea_eff": int(st["n_sr_zonea_era_eff"]),
            "n_cr_geom_nom": int(st["n_cr_geom_all_nom"]),
            "n_cr_geom_eff": int(st["n_cr_geom_all_eff"]),
            "n_cr_edge_vn_nom": int(st["n_cr_edge_vn_all_nom"]),
            "n_cr_edge_vn_eff": int(st["n_cr_edge_vn_all_eff"]),
            "n_cr_edge_vn_wp_primary_nom": int(st["n_cr_edge_vn_wp_primary_nom"]),
            "cr_prompt_per_fb_nom": int(st["n_cr_prompt_2hit_nom"]) * inv_fb,
            "cr_prompt_per_fb_eff": int(st["n_cr_prompt_2hit_eff"]) * inv_fb,
            "cr_geom_per_fb_nom": int(st["n_cr_geom_all_nom"]) * inv_fb,
            "cr_geom_per_fb_eff": int(st["n_cr_geom_all_eff"]) * inv_fb,
            "cr_edge_vn_per_fb_nom": int(st["n_cr_edge_vn_all_nom"]) * inv_fb,
            "sr_zonea_raw40_per_fb": int(st["n_sr_zonea_raw40_nom"]) * inv_fb,
            "sr_zonea_per_fb_nom": int(st["n_sr_zonea_era_nom"]) * inv_fb,
            "sr_zonea_per_fb_eff": int(st["n_sr_zonea_era_eff"]) * inv_fb,
            "dt0_mean_ns": dt0_mu,
            "dt0_sigma_ns": dt0_sig,
            "dt1_mean_ns": dt1_mu,
            "dt1_sigma_ns": dt1_sig,
            "dt0_noPS23_sigma_ns": dt0_n_sig,
            "sigt0_with_ns": st0_w_mu,
            "sigt0_no_ns": st0_n_mu,
            "shift_t0_mean_ns": sh_mu,
            "shift_t0_std_ns": sh_sd,
            "has_vetogm": bool(meta.get("has_vetogm", False)),
            "vetogm_active": bool(meta.get("vetogm_active", False)),
            "n_gm_denom": int(st["n_gm_denom"]),
            "n_gm0_q20": int(st["n_gm0_q20"]),
            "n_gm1_q20": int(st["n_gm1_q20"]),
            "gm0_qmax": float(st["gm0_qmax"]),
            "gm1_qmax": float(st["gm1_qmax"]),
        })

    rbr_cols = list(rbr_rows[0].keys())
    with open(out_dir / "run_by_run_stability_run3.tsv", "w") as f:
        f.write("\t".join(rbr_cols) + "\n")
        for r in rbr_rows:
            f.write("\t".join(f"{r[c]:.6g}" if isinstance(r[c], float) and math.isfinite(r[c]) else str(r[c]) for c in rbr_cols) + "\n")

    # ── 2. Period & Crossing-Angle Regime Summary Table ─────────────────────
    def summarize_subset(label: str, sub: list[dict[str, Any]], raw_sub: list[dict[str, Any]]) -> dict[str, Any]:
        lumi_fb = sum(x["lumi_fb"] for x in sub)
        inv = (1.0 / lumi_fb) if lumi_fb > 0 else float("nan")
        n_crp_nom = sum(x["n_cr_prompt_nom"] for x in sub)
        n_crp_eff = sum(x["n_cr_prompt_eff"] for x in sub)
        n_crg_nom = sum(x["n_cr_geom_nom"] for x in sub)
        n_crg_eff = sum(x["n_cr_geom_eff"] for x in sub)
        n_cre_nom = sum(x["n_cr_edge_vn_nom"] for x in sub)
        n_sr_raw40 = sum(x["n_sr_zonea_raw40_nom"] for x in sub)
        n_sr_nom = sum(x["n_sr_zonea_nom"] for x in sub)
        n_sr_eff = sum(x["n_sr_zonea_eff"] for x in sub)

        # Exact aggregated timing moments across runs
        dt0_c = sum(int(data_runs[x["run"]]["dt0_with_cnt"]) for x in sub)
        dt0_s1 = sum(float(data_runs[x["run"]]["dt0_with_sum"]) for x in sub)
        dt0_s2 = sum(float(data_runs[x["run"]]["dt0_with_sum2"]) for x in sub)
        dt1_c = sum(int(data_runs[x["run"]]["dt1_with_cnt"]) for x in sub)
        dt1_s1 = sum(float(data_runs[x["run"]]["dt1_with_sum"]) for x in sub)
        dt1_s2 = sum(float(data_runs[x["run"]]["dt1_with_sum2"]) for x in sub)
        dt0_mu, dt0_sig = _mean_std(dt0_c, dt0_s1, dt0_s2)
        dt1_mu, dt1_sig = _mean_std(dt1_c, dt1_s1, dt1_s2)

        sig_c = sum(int(data_runs[x["run"]]["down_with_cnt"]) for x in sub)
        sig_s1 = sum(float(data_runs[x["run"]]["sigt0_with_sum"]) for x in sub)
        sig_s2 = sum(float(data_runs[x["run"]]["sigt0_with_sum2"]) for x in sub)
        sig_mu, _ = _mean_std(sig_c, sig_s1, sig_s2)

        ca_c = sum(int(data_runs[x["run"]]["ca_cnt"]) for x in sub)
        ca_s1 = sum(float(data_runs[x["run"]]["ca_sum"]) for x in sub)
        ca_s2 = sum(float(data_runs[x["run"]]["ca_sum2"]) for x in sub)
        ca_mu, ca_sd = _mean_std(ca_c, ca_s1, ca_s2)

        return {
            "group": label,
            "n_runs": len(sub),
            "lumi_fb": lumi_fb,
            "ca_mean_urad": ca_mu,
            "ca_std_urad": ca_sd,
            "n_cr_prompt_nom": n_crp_nom,
            "cr_prompt_per_fb_nom": n_crp_nom * inv,
            "n_cr_prompt_eff": n_crp_eff,
            "cr_prompt_per_fb_eff": n_crp_eff * inv,
            "n_cr_geom_eff": n_crg_eff,
            "cr_geom_per_fb_eff": n_crg_eff * inv,
            "n_cr_edge_vn_nom": n_cre_nom,
            "cr_edge_vn_per_fb": n_cre_nom * inv,
            "n_sr_zonea_raw40": n_sr_raw40,
            "sr_zonea_raw40_per_fb": n_sr_raw40 * inv,
            "sr_zonea_raw40_per_fb_err": math.sqrt(max(n_sr_raw40, 0)) * inv if lumi_fb > 0 else float("nan"),
            "n_sr_zonea_nom": n_sr_nom,
            "sr_zonea_per_fb_nom": n_sr_nom * inv,
            "sr_zonea_per_fb_nom_err": math.sqrt(max(n_sr_nom, 0)) * inv if lumi_fb > 0 else float("nan"),
            "n_sr_zonea_eff": n_sr_eff,
            "sr_zonea_per_fb_eff": n_sr_eff * inv,
            "sr_zonea_per_fb_eff_err": math.sqrt(max(n_sr_eff, 0)) * inv if lumi_fb > 0 else float("nan"),
            "dt0_mean_ns": dt0_mu,
            "dt0_sigma_ns": dt0_sig,
            "dt1_mean_ns": dt1_mu,
            "dt1_sigma_ns": dt1_sig,
            "sigt0_with_ns": sig_mu,
        }

    period_groups: list[tuple[str, list[dict[str, Any]]]] = []
    for p in PERIOD_ORDER:
        period_groups.append((f"period_{p}_active", [r for r in rbr_rows if r["period"] == p and r["dq_flag"] != "dead_vetonu_hv"]))
    period_groups += [
        ("2025_p0013_healthy", [r for r in rbr_rows if r["period"] == "2025" and r["reco_tag"] == "2025/p0013" and r["dq_flag"] == "healthy"]),
        ("2025_p0013_brokenPS", [r for r in rbr_rows if r["period"] == "2025" and r["dq_flag"] == "broken_ps_p0013"]),
        ("2025_p0014_healthy", [r for r in rbr_rows if r["period"] == "2025" and r["reco_tag"] == "2025/p0014" and r["dq_flag"] != "dead_vetonu_hv"]),
        ("2025_p0014_colliding", [r for r in rbr_rows if r["period"] == "2025" and r["reco_tag"] == "2025/p0014" and r["dq_flag"] != "dead_vetonu_hv" and r["n_colliding"] > 0]),
        ("2025_dead_vetonu_hv", [r for r in rbr_rows if r["dq_flag"] == "dead_vetonu_hv"]),
        ("2026_p0015_earlyPS3", [r for r in rbr_rows if r["period"] == "2026"]),
        ("regime_CA_-160urad", [r for r in rbr_rows if r["dq_flag"] != "dead_vetonu_hv" and r["ca_regime"] == "CA_-160urad"]),
        ("regime_CA_+150/+160urad", [r for r in rbr_rows if r["dq_flag"] != "dead_vetonu_hv" and r["ca_regime"] == "CA_+150/+160urad"]),
        ("Run3_clean_reprocessed_5era", [
            r for r in rbr_rows
            if r["dq_flag"] != "dead_vetonu_hv" and r["n_colliding"] > 0 and (
                r["period"] in ("2022", "2024_preCaloNu", "2024_postCaloNu", "2026")
                or (r["period"] == "2025" and r["reco_tag"] == "2025/p0014")
            )
        ]),
        ("Run3_clean_reprocessed_6era_inc2023", [
            r for r in rbr_rows
            if r["dq_flag"] != "dead_vetonu_hv" and r["n_colliding"] > 0 and (
                r["period"] in ("2022", "2023", "2024_preCaloNu", "2024_postCaloNu", "2026")
                or (r["period"] == "2025" and r["reco_tag"] == "2025/p0014")
            )
        ]),
        ("Run3_active_713", [r for r in rbr_rows if r["dq_flag"] != "dead_vetonu_hv"]),
        ("Run3_all_717_unfiltered", rbr_rows),
    ]
    per_rows = [summarize_subset(lbl, sub, sub) for lbl, sub in period_groups if sub]
    per_by_name = {row["group"]: row for row in per_rows}

    # Global SR-ZoneA (eff) consistency across the 7 active periods
    active_7 = [row for row in per_rows if row["group"].startswith("period_") and row["group"].endswith("_active")]
    tot_sr_eff = sum(r["n_sr_zonea_eff"] for r in active_7)
    tot_lumi_act = sum(r["lumi_fb"] for r in active_7)
    r_sr_global = tot_sr_eff / tot_lumi_act
    chi2_sr_7 = 0.0
    for r in active_7:
        exp = r_sr_global * r["lumi_fb"]
        chi2_sr_7 += ((r["n_sr_zonea_eff"] - exp) ** 2) / max(exp, 1e-9)
        r["sr_zonea_pull_vs_global"] = (r["n_sr_zonea_eff"] - exp) / math.sqrt(max(exp, 1e-9))

    # Homogeneous standard-absorber reprocessed closure tests (colliding BCID runs):
    # (a) 5 eras under red30 (2022, 2024_pre, 2024_post, 2025_p0014_colliding, 2026_p0015)
    clean_5_names = ["period_2022_active", "period_2024_preCaloNu_active", "period_2024_postCaloNu_active",
                     "2025_p0014_colliding", "period_2026_active"]
    clean_5 = [per_by_name[n] for n in clean_5_names]
    lumi_clean_5 = sum(r["lumi_fb"] for r in clean_5)
    r_sr_clean_5 = sum(r["n_sr_zonea_eff"] for r in clean_5) / lumi_clean_5
    chi2_sr_clean_5 = 0.0
    for r in clean_5:
        exp = r_sr_clean_5 * r["lumi_fb"]
        chi2_sr_clean_5 += ((r["n_sr_zonea_eff"] - exp) ** 2) / max(exp, 1e-9)
        r["sr_zonea_pull_vs_clean5"] = (r["n_sr_zonea_eff"] - exp) / math.sqrt(max(exp, 1e-9))

    # (b) 6 eras under raw40 (including 2023 immune to Waveforms-2023 zero-charge / status-16 aux bug!)
    clean_6_names = ["period_2022_active", "period_2023_active", "period_2024_preCaloNu_active",
                     "period_2024_postCaloNu_active", "2025_p0014_colliding", "period_2026_active"]
    clean_6 = [per_by_name[n] for n in clean_6_names]
    lumi_clean_6 = sum(r["lumi_fb"] for r in clean_6)
    r_sr_clean_6_raw40 = sum(r["n_sr_zonea_raw40"] for r in clean_6) / lumi_clean_6
    chi2_sr_clean_6_raw40 = 0.0
    for r in clean_6:
        exp = r_sr_clean_6_raw40 * r["lumi_fb"]
        chi2_sr_clean_6_raw40 += ((r["n_sr_zonea_raw40"] - exp) ** 2) / max(exp, 1e-9)
        r["sr_zonea_raw40_pull_vs_clean6"] = (r["n_sr_zonea_raw40"] - exp) / math.sqrt(max(exp, 1e-9))

    per_cols = list(per_rows[0].keys())
    for extra_col in ("sr_zonea_pull_vs_clean5", "sr_zonea_raw40_pull_vs_clean6"):
        if extra_col not in per_cols:
            per_cols.append(extra_col)
    with open(out_dir / "period_stability_summary.tsv", "w") as f:
        f.write("\t".join(per_cols) + "\n")
        for r in per_rows:
            vals = [r.get(c, float("nan")) for c in per_cols]
            f.write("\t".join(f"{v:.6g}" if isinstance(v, float) and math.isfinite(v) else str(v) for v in vals) + "\n")

    # ── 3. Preshower2/3 Downstream Reference Gain & Bias Check ──────────────
    # Add combined 2025_2026_all group on the fly
    ps_all_groups = list(PS_GROUP_NAMES) + ["y2025_2026_all"]
    comb_keys: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for gname in ("y2025_p0013_healthy", "y2025_p0013_brokenPS", "y2025_p0014", "y2026_p0015_earlyPS3", "y2026_p0015_lateNoPS3"):
        for (gk, hk), (arr, ed) in merged_ps.items():
            if gk != gname:
                continue
            if hk not in comb_keys:
                comb_keys[hk] = (arr.copy(), ed)
            else:
                comb_keys[hk][0][:] += arr
    for hk, val in comb_keys.items():
        merged_ps[("y2025_2026_all", hk)] = val

    ps_gain_rows: list[dict[str, Any]] = []
    for grp in ps_all_groups:
        for strat in PS_STRATA:
            if (grp, f"h_ndown_no_{strat}") not in merged_ps:
                continue
            nd_no, nd_ed = merged_ps[(grp, f"h_ndown_no_{strat}")]
            nd_with, _ = merged_ps[(grp, f"h_ndown_with_{strat}")]
            n_tot_ev = int(np.sum(nd_with))
            if n_tot_ev == 0:
                continue
            n_ge2_no = int(np.sum(nd_no[nd_ed[:-1] >= 2.0]))
            n_ge3_no = int(np.sum(nd_no[nd_ed[:-1] >= 3.0]))
            n_ge2_with = int(np.sum(nd_with[nd_ed[:-1] >= 2.0]))
            n_ge3_with = int(np.sum(nd_with[nd_ed[:-1] >= 3.0]))

            sigt_no, sigt_ed = merged_ps[(grp, f"h_sigt0_no_{strat}")]
            sigt_with, _ = merged_ps[(grp, f"h_sigt0_with_{strat}")]
            xc_st = 0.5 * (sigt_ed[:-1] + sigt_ed[1:])
            mean_sigt_no = float(np.sum(xc_st * sigt_no) / max(np.sum(sigt_no), 1.0))
            mean_sigt_with = float(np.sum(xc_st * sigt_with) / max(np.sum(sigt_with), 1.0))

            sh_v, sh_ed = merged_ps[(grp, f"h_shift_t0_{strat}")]
            xc_sh = 0.5 * (sh_ed[:-1] + sh_ed[1:])
            n_sh = max(np.sum(sh_v), 1.0)
            mean_shift = float(np.sum(xc_sh * sh_v) / n_sh)
            rms_shift = math.sqrt(max(0.0, float(np.sum(((xc_sh - mean_shift) ** 2) * sh_v) / n_sh)))

            loo_no_v, loo_ed = merged_ps[(grp, f"h_tim01_loo_no_{strat}")]
            loo_with_v, _ = merged_ps[(grp, f"h_tim01_loo_with_{strat}")]
            _, _, sig_loo_no, esig_loo_no = _fit_gauss_core(loo_no_v, loo_ed, (-1.2, 1.2), (-2.0, 2.0))
            _, _, sig_loo_with, esig_loo_with = _fit_gauss_core(loo_with_v, loo_ed, (-1.2, 1.2), (-2.0, 2.0))

            dt0_p_no_v, dt0_p_ed = merged_ps[(grp, f"h_dt0_prompt_no_{strat}")]
            dt0_p_w_v, _ = merged_ps[(grp, f"h_dt0_prompt_with_{strat}")]
            _, _, sig_dt0_p_no, _ = _fit_gauss_core(dt0_p_no_v, dt0_p_ed, (-1.2, 1.2), (-2.0, 2.0))
            _, _, sig_dt0_p_with, _ = _fit_gauss_core(dt0_p_w_v, dt0_p_ed, (-1.2, 1.2), (-2.0, 2.0))

            dt0_cr_no_v, dt0_cr_ed = merged_ps[(grp, f"h_dt0_cr_no_{strat}")]
            dt0_cr_w_v, _ = merged_ps[(grp, f"h_dt0_cr_with_{strat}")]
            _, _, sig_dt0_cr_no, _ = _fit_gauss_core(dt0_cr_no_v, dt0_cr_ed, (-1.4, 1.4), (-2.5, 2.5))
            _, _, sig_dt0_cr_with, _ = _fit_gauss_core(dt0_cr_w_v, dt0_cr_ed, (-1.4, 1.4), (-2.5, 2.5))

            u1_no_v, u1_ed = merged_ps[(grp, f"h_u1_downb_no_{strat}")]
            u1_w_v, _ = merged_ps[(grp, f"h_u1_downb_with_{strat}")]
            _, _, sig_u1_db_no, _ = _fit_gauss_core(u1_no_v, u1_ed, (-1.4, 1.4), (-2.5, 2.5))
            _, _, sig_u1_db_with, _ = _fit_gauss_core(u1_w_v, u1_ed, (-1.4, 1.4), (-2.5, 2.5))

            ps_gain_rows.append({
                "group": grp,
                "stratum": strat,
                "n_events": n_tot_ev,
                "frac_ge2_noPS23": n_ge2_no / n_tot_ev,
                "frac_ge2_withPS23": n_ge2_with / n_tot_ev,
                "frac_ge3_noPS23": n_ge3_no / n_tot_ev,
                "frac_ge3_withPS23": n_ge3_with / n_tot_ev,
                "mean_sigt0_noPS23_ns": mean_sigt_no,
                "mean_sigt0_withPS23_ns": mean_sigt_with,
                "sigt0_rel_change_pct": 100.0 * (mean_sigt_with - mean_sigt_no) / max(mean_sigt_no, 1e-6),
                "mean_t0_shift_ns": mean_shift,
                "rms_t0_shift_ns": rms_shift,
                "sig_tim01_loo_no_ns": sig_loo_no,
                "sig_tim01_loo_with_ns": sig_loo_with,
                "sig_dt0_prompt_no_ns": sig_dt0_p_no,
                "sig_dt0_prompt_with_ns": sig_dt0_p_with,
                "sig_dt0_cr_no_ns": sig_dt0_cr_no,
                "sig_dt0_cr_with_ns": sig_dt0_cr_with,
                "sig_u1_downB_no_ns": sig_u1_db_no,
                "sig_u1_downB_with_ns": sig_u1_db_with,
                "n_u1_downB_cr_no": int(np.sum(u1_no_v)),
                "n_u1_downB_cr_with": int(np.sum(u1_w_v)),
            })

    with open(out_dir / "preshower23_t0down_gain.tsv", "w") as f:
        cols = list(ps_gain_rows[0].keys())
        f.write("\t".join(cols) + "\n")
        for r in ps_gain_rows:
            f.write("\t".join(f"{r[c]:.6g}" if isinstance(r[c], float) and math.isfinite(r[c]) else str(r[c]) for c in cols) + "\n")

    crg_wp_no_2526 = sum(int(data_runs[r["run"]]["n_cr_geom_wp_primary_no_nom"]) for r in rbr_rows if r["period"] in ("2025", "2026") and r["dq_flag"] != "dead_vetonu_hv")
    crg_wp_with_2526 = sum(int(data_runs[r["run"]]["n_cr_geom_wp_primary_with_nom"]) for r in rbr_rows if r["period"] in ("2025", "2026") and r["dq_flag"] != "dead_vetonu_hv")

    # ── 4. VetoGm0/1 Run Audit, In-Situ Geometry, Timing Calibration & B4 Bound ──
    gm_audit_rows = [r for r in rbr_rows if r["has_vetogm"] or r["period"] in ("2025", "2026")]
    with open(out_dir / "vetogm_run_audit.tsv", "w") as f:
        cols = ["run", "period", "reco_tag", "dq_flag", "lumi_pb", "has_vetogm", "vetogm_active",
                "n_gm_denom", "n_gm0_q20", "n_gm1_q20", "gm0_qmax", "gm1_qmax"]
        f.write("\t".join(cols) + "\n")
        for r in gm_audit_rows:
            f.write("\t".join(f"{r[c]:.6g}" if isinstance(r[c], float) and math.isfinite(r[c]) else str(r[c]) for c in cols) + "\n")

    lumi_live_gm_fb = sum(r["lumi_fb"] for r in rbr_rows if r["vetogm_active"] and r["dq_flag"] != "dead_vetonu_hv")
    lumi_live_gm_coll_fb = sum(r["lumi_fb"] for r in rbr_rows if r["vetogm_active"] and r["dq_flag"] != "dead_vetonu_hv" and r["n_gm_denom"] > 0)
    lumi_hvoff_2026_fb = sum(r["lumi_fb"] for r in rbr_rows if r["period"] == "2026")
    lumi_dead_vn_fb = sum(r["lumi_fb"] for r in rbr_rows if r["dq_flag"] == "dead_vetonu_hv")

    # Digitizer-2-aware VetoGm timing peak calibration on live_2025_p0014 using VetoGm_localtime - Timing0_localtime:
    # Digitizer-0 hits (status & 512 == 0) peak at -49.1 ns (Gm0) and -51.4 ns (Gm1);
    # Digitizer-1 hits (status & 512 != 0) are offset by -16.0 ns (-65.1 ns and -67.5 ns).
    loc0_gm_arr, loc0_gm_ed = merged_gm[("live_2025_p0014", "h1_gm0_loc_tim0")]
    loc1_gm_arr, loc1_gm_ed = merged_gm[("live_2025_p0014", "h1_gm1_loc_tim0")]

    gm0_t_mu, gm0_t_emu, gm0_t_sig, gm0_t_esig = _fit_gauss_core(loc0_gm_arr, loc0_gm_ed, (-52.5, -45.5), (-55.0, -43.0))
    gm0_d2_mu, _, gm0_d2_sig, _ = _fit_gauss_core(loc0_gm_arr, loc0_gm_ed, (-68.5, -61.5), (-71.0, -59.0))
    gm1_t_mu, gm1_t_emu, gm1_t_sig, gm1_t_esig = _fit_gauss_core(loc1_gm_arr, loc1_gm_ed, (-55.0, -47.5), (-57.5, -45.0))
    gm1_d2_mu, _, gm1_d2_sig, _ = _fit_gauss_core(loc1_gm_arr, loc1_gm_ed, (-71.0, -63.5), (-73.5, -61.0))

    # Event-level VetoGm geometry & grazing-muon B4 cross-check
    live_run_set = {r["run"] for r in rbr_rows if r["vetogm_active"] and r["dq_flag"] != "dead_vetonu_hv"}
    m_live_ev = np.isin(gm_recs["run"], list(live_run_set)) & (gm_recs["sample_weight"] > 0)
    rec_wt = gm_recs["sample_weight"]

    gm0_dt_corr = gm_recs["gm0_loc_tim0"] + np.where((gm_recs["gm0_status"] & 512) != 0, 16.0, 0.0)
    gm1_dt_corr = gm_recs["gm1_loc_tim0"] + np.where((gm_recs["gm1_status"] & 512) != 0, 16.0, 0.0)

    # Check VetoGm status integrity & timing windows around calibrated forward-muon peak (allow saturation bit 4 on charge tag!)
    def gm_hit_masks(
        rec: dict[str, np.ndarray],
        dt0c: np.ndarray,
        dt1c: np.ndarray,
        mu0: float,
        mu1: float,
        half_win_ns: float = 3.0,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        good0 = ((rec["gm0_status"] & (8 | 128 | 256)) == 0) & np.isfinite(rec["gm0_q_raw"]) & (rec["gm0_q_raw"] > 20.0)
        good1 = ((rec["gm1_status"] & (8 | 128 | 256)) == 0) & np.isfinite(rec["gm1_q_raw"]) & (rec["gm1_q_raw"] > 20.0)
        intime0 = good0 & np.isfinite(dt0c) & (np.abs(dt0c - mu0) < half_win_ns)
        intime1 = good1 & np.isfinite(dt1c) & (np.abs(dt1c - mu1) < half_win_ns)
        late0 = good0 & np.isfinite(dt0c) & ((dt0c - mu0) >= half_win_ns)
        late1 = good1 & np.isfinite(dt1c) & ((dt1c - mu1) >= half_win_ns)
        return good0, good1, intime0, intime1, late0, late1

    g0_hit, g1_hit, g0_it, g1_it, g0_late, g1_late = gm_hit_masks(gm_recs, gm0_dt_corr, gm1_dt_corr, gm0_t_mu, gm1_t_mu, 3.0)
    _, _, g0_it5, g1_it5, _, _ = gm_hit_masks(gm_recs, gm0_dt_corr, gm1_dt_corr, gm0_t_mu, gm1_t_mu, 5.0)

    # Extract active 2D bounding boxes at VetoNu from live 2025/p0014 2D efficiency maps
    # Note: tracks passing rIFT < 135 mm graze the +x VetoGm0 paddle (max eff 41.2%) and +y VetoGm1 paddle (max eff 12.0%).
    h2_den, xe2, ye2 = merged_gm[("live_2025_p0014", "h2_vn_denom")]
    h2_g0, _, _ = merged_gm[("live_2025_p0014", "h2_vn_gm0_q20")]
    h2_g1, _, _ = merged_gm[("live_2025_p0014", "h2_vn_gm1_q20")]
    h2_ga, _, _ = merged_gm[("live_2025_p0014", "h2_vn_gmany_q20")]
    xc2 = 0.5 * (xe2[:-1] + xe2[1:])
    yc2 = 0.5 * (ye2[:-1] + ye2[1:])
    XX2, YY2 = np.meshgrid(xc2, yc2, indexing="ij")

    def characterize_plate(h_num: np.ndarray, h_den: np.ndarray, eff_thr: float, min_den: float = 10.0) -> dict[str, float]:
        with np.errstate(divide="ignore", invalid="ignore"):
            eff = np.where(h_den >= min_den, h_num / h_den, np.nan)
        active = np.isfinite(eff) & (eff >= eff_thr)
        if not np.any(active):
            return {"x_min": float("nan"), "x_max": float("nan"), "y_min": float("nan"), "y_max": float("nan"),
                    "eps_mean_active": 0.0, "eps_max_bin": float(np.nanmax(eff)) if np.any(np.isfinite(eff)) else 0.0, "n_active_bins": 0}
        xs = XX2[active]
        ys = YY2[active]
        xlo, xhi = float(np.min(xs) - 2.5), float(np.max(xs) + 2.5)
        ylo, yhi = float(np.min(ys) - 2.5), float(np.max(ys) + 2.5)
        eps_mean = float(np.sum(h_num[active]) / max(np.sum(h_den[active]), 1.0))
        eps_max = float(np.nanmax(eff))
        return {"x_min": xlo, "x_max": xhi, "y_min": ylo, "y_max": yhi,
                "eps_mean_active": eps_mean, "eps_max_bin": eps_max, "n_active_bins": int(np.sum(active))}

    box0 = characterize_plate(h2_g0, h2_den, eff_thr=0.15, min_den=10.0)
    box1 = characterize_plate(h2_g1, h2_den, eff_thr=0.06, min_den=10.0)

    # Scan projection z_Gm from upstream of VetoNu (-3800 mm) to Veto1 (-2400 mm) to locate physical z maximizing boundary sharpness!
    slope_x = (gm_recs["x_v1"] - gm_recs["x_vn"]) / 1332.5
    slope_y = (gm_recs["y_v1"] - gm_recs["y_vn"]) / 1332.5
    z_scan_vals = np.linspace(-3800.0, -2400.0, 29)
    z_best0, z_best1, sharp_max0, sharp_max1 = -3112.5, -3112.5, -1.0, -1.0
    m_zscan = m_live_ev & np.isfinite(slope_x) & np.isfinite(slope_y) & (np.abs(slope_x) < 0.1) & (np.abs(slope_y) < 0.1)
    for zt in z_scan_vals:
        dz = zt - (-3112.5)
        xz = gm_recs["x_vn"][m_zscan] + slope_x[m_zscan] * dz
        yz = gm_recs["y_vn"][m_zscan] + slope_y[m_zscan] * dz
        wt_z = rec_wt[m_zscan]
        if math.isfinite(box0["x_min"]):
            m_ed0 = (np.abs(xz - box0["x_min"]) < 30.0) & (yz > box0["y_min"]) & (yz < box0["y_max"])
            if np.sum(m_ed0) > 100:
                r_in0 = np.sum(wt_z[m_ed0 & (xz >= box0["x_min"]) & g0_hit[m_zscan]]) / max(np.sum(wt_z[m_ed0 & (xz >= box0["x_min"])]), 1.0)
                r_out0 = np.sum(wt_z[m_ed0 & (xz < box0["x_min"]) & g0_hit[m_zscan]]) / max(np.sum(wt_z[m_ed0 & (xz < box0["x_min"])]), 1.0)
                if (r_in0 - r_out0) > sharp_max0:
                    sharp_max0 = r_in0 - r_out0
                    z_best0 = float(zt)
        if math.isfinite(box1["y_min"]):
            m_ed1 = (np.abs(yz - box1["y_min"]) < 30.0) & (xz > box1["x_min"]) & (xz < box1["x_max"])
            if np.sum(m_ed1) > 100:
                r_in1 = np.sum(wt_z[m_ed1 & (yz >= box1["y_min"]) & g1_hit[m_zscan]]) / max(np.sum(wt_z[m_ed1 & (yz >= box1["y_min"])]), 1.0)
                r_out1 = np.sum(wt_z[m_ed1 & (yz < box1["y_min"]) & g1_hit[m_zscan]]) / max(np.sum(wt_z[m_ed1 & (yz < box1["y_min"])]), 1.0)
                if (r_in1 - r_out1) > sharp_max1:
                    sharp_max1 = r_in1 - r_out1
                    z_best1 = float(zt)

    # Radial efficiency C_Gm * eps(r_VN)
    h1_rvn_d, r_ed = merged_gm[("live_2025_p0014", "h1_rvn_denom")]
    h1_rvn_a, _ = merged_gm[("live_2025_p0014", "h1_rvn_gmany_q20")]
    m_edge_band = (r_ed[:-1] >= 120.0) & (r_ed[:-1] < 180.0)
    m_sr_band = (r_ed[:-1] >= 90.0) & (r_ed[:-1] < 120.0)
    eff_gm_edge_vn = float(np.sum(h1_rvn_a[m_edge_band]) / max(np.sum(h1_rvn_d[m_edge_band]), 1.0))
    eff_gm_sr_rim = float(np.sum(h1_rvn_a[m_sr_band]) / max(np.sum(h1_rvn_d[m_sr_band]), 1.0))

    tot_active_lumi_fb = sum(r["lumi_fb"] for r in rbr_rows if r["dq_flag"] != "dead_vetonu_hv")
    n_edge_vn_run3 = sum(r["n_cr_edge_vn_nom"] for r in rbr_rows if r["dq_flag"] != "dead_vetonu_hv")
    n_edge_vn_wp_run3 = sum(r["n_cr_edge_vn_wp_primary_nom"] for r in rbr_rows if r["dq_flag"] != "dead_vetonu_hv")
    # Stage T4/T5 CR-EdgeVN -> SR transfer factor: 25.0 grazing Zone-A muons bound / total Run-3 CR-EdgeVN tracks
    t_edge_to_sr = 25.0 / max(float(n_edge_vn_run3), 1.0)
    scale_333 = tot_active_lumi_fb / max(lumi_live_gm_coll_fb, 1e-6)

    # Count unprescaled / weighted VetoGm tags in all control regions across live 2025/p0014 runs
    def region_summary(name: str, mask: np.ndarray, scale_to_run3: float) -> dict[str, Any]:
        sub_m = m_live_ev & mask
        w_tot = float(np.sum(rec_wt[sub_m]))
        n_raw = int(np.sum(sub_m))
        g_any_raw = g0_hit | g1_hit
        g_any_it = g0_it | g1_it
        g_any_it5 = g0_it5 | g1_it5
        g_any_late = g0_late | g1_late
        w_q20 = float(np.sum(rec_wt[sub_m & g_any_raw]))
        n_q20_unw = int(np.sum(sub_m & g_any_raw & (rec_wt == 1.0)))
        w_it = float(np.sum(rec_wt[sub_m & g_any_it]))
        n_it_unw = int(np.sum(sub_m & g_any_it & (rec_wt == 1.0)))
        n_it5_unw = int(np.sum(sub_m & g_any_it5 & (rec_wt == 1.0)))
        n_late_unw = int(np.sum(sub_m & g_any_late & (rec_wt == 1.0)))
        n_den_unw = int(np.sum(sub_m & (rec_wt == 1.0)))
        is_unw_region = (n_den_unw > 0) or (n_raw == 0)
        up90_raw = _poisson_upper(n_it_unw, 0.90) if is_unw_region else float("nan")
        up90_b4_sr = (up90_raw / max(eff_gm_edge_vn, 0.01) * scale_to_run3 * t_edge_to_sr) if ("EdgeVN" in name and is_unw_region) else float("nan")
        return {
            "region_label": name,
            "n_raw_stored": n_raw,
            "weighted_total": w_tot,
            "n_unweighted_total": n_den_unw,
            "n_gm_q20_unweighted": n_q20_unw,
            "weighted_gm_q20": w_q20,
            "n_gm_intime_3ns_unweighted": n_it_unw,
            "n_gm_intime_5ns_unweighted": n_it5_unw,
            "n_gm_late_albedo_unweighted": n_late_unw,
            "weighted_gm_intime_3ns": w_it,
            "gm_q20_rate": (w_q20 / w_tot) if w_tot > 0 else 0.0,
            "gm_intime_3ns_rate": (w_it / w_tot) if w_tot > 0 else 0.0,
            "upper90_raw_in_sample": up90_raw,
            "upper90_b4_sr_333fb": up90_b4_sr,
        }

    is_sr = gm_recs["region"] == 1
    is_geom = (gm_recs["region"] == 2) | (gm_recs["region"] == 3)
    is_edge = gm_recs["region"] == 4
    is_halo = gm_recs["region"] == 8
    is_za = gm_recs["zone_a_era"] == 1
    is_zb_delayed = (gm_recs["zone_a_era"] == 0) & ((gm_recs["dt0"] > 1.5) | (gm_recs["dt1"] > 1.5))
    is_wp = gm_recs["pass_wp_primary"] == 1

    gm_b4_rows = [
        region_summary("SR_ZoneA_S0", is_sr & is_za, scale_333),
        region_summary("CR_Prompt_SR_presc", is_sr & (~is_za), scale_333),
        region_summary("CR_Geom_ZoneA", is_geom & is_za, scale_333),
        region_summary("CR_Geom_ZoneB_Prompt_presc", is_geom & (~is_za) & (~is_zb_delayed), scale_333),
        region_summary("CR_Geom_ZoneB_Delayed_dtgt1p5", is_geom & is_zb_delayed, scale_333),
        region_summary("CR_Geom_ZoneB_WP_Primary", is_geom & (~is_za) & is_wp, scale_333),
        region_summary("CR_EdgeVN_ZoneA", is_edge & is_za, scale_333),
        region_summary("CR_EdgeVN_ZoneB_Prompt_presc", is_edge & (~is_za) & (~is_zb_delayed), scale_333),
        region_summary("CR_EdgeVN_ZoneB_Delayed_dtgt1p5", is_edge & is_zb_delayed, scale_333),
        region_summary("CR_EdgeVN_ZoneB_WP_Primary", is_edge & (~is_za) & is_wp, scale_333),
        region_summary("CR_HaloVN_ZoneB_All", is_halo & (~is_za), scale_333),
        region_summary("CR_HaloVN_ZoneB_Delayed_dtgt1p5", is_halo & is_zb_delayed, scale_333),
        region_summary("CR_HaloVN_ZoneB_WP_Primary", is_halo & (~is_za) & is_wp, scale_333),
    ]

    with open(out_dir / "vetogm_geometry_and_b4_crosscheck.tsv", "w") as f:
        cols = list(gm_b4_rows[0].keys())
        f.write("\t".join(cols) + "\n")
        for r in gm_b4_rows:
            f.write("\t".join(f"{r[c]:.6g}" if isinstance(r[c], float) and math.isfinite(r[c]) else str(r[c]) for c in cols) + "\n")

    edge_wp_row = next(x for x in gm_b4_rows if x["region_label"] == "CR_EdgeVN_ZoneB_WP_Primary")
    geom_wp_row = next(x for x in gm_b4_rows if x["region_label"] == "CR_Geom_ZoneB_WP_Primary")
    halo_wp_row = next(x for x in gm_b4_rows if x["region_label"] == "CR_HaloVN_ZoneB_WP_Primary")
    sr_za_row = next(x for x in gm_b4_rows if x["region_label"] == "SR_ZoneA_S0")

    b4_edge_direct_upper90_333fb = _poisson_upper(int(n_edge_vn_wp_run3), 0.90) * t_edge_to_sr
    b4_edge_vetogm_azim_upper90_333fb = float(edge_wp_row["upper90_b4_sr_333fb"])
    b4_edge_vetogm_sector_upper90_333fb = _poisson_upper(int(edge_wp_row["n_gm_intime_3ns_unweighted"]), 0.90) / max(box0["eps_mean_active"], 0.15) * scale_333 * t_edge_to_sr
    b4_sr_za_intime_upper90_frac = _clopper_pearson_upper(int(sr_za_row["n_gm_intime_3ns_unweighted"]), int(sr_za_row["n_unweighted_total"]), 0.90)

    # Extract T5 frozen metrics robustly from t5_summary.json
    t5_sum = json.loads(Path(DEFAULT_T5_SUMMARY).read_text()) if DEFAULT_T5_SUMMARY.exists() else {}
    t5_fm = {row["label"]: row for row in t5_sum.get("frozen_metrics", [])} if isinstance(t5_sum, dict) else {}
    t5_b4_prim = float(t5_fm.get("WP_Primary", {}).get("B4", 0.0))
    t5_b4_s2 = float(t5_fm.get("WP_S2", {}).get("B4", 0.0057))

    # ── 5. Write t6_summary.json ────────────────────────────────────────────
    t6_summary = {
        "total_data_runs_manifest": len(man_runs),
        "total_data_runs_observed": len(data_runs),
        "active_dq_clean_runs": sum(1 for r in rbr_rows if r["dq_flag"] != "dead_vetonu_hv"),
        "dead_vetonu_hv_runs": [r["run"] for r in rbr_rows if r["dq_flag"] == "dead_vetonu_hv"],
        "broken_ps_p0013_runs": sum(1 for r in rbr_rows if r["dq_flag"] == "broken_ps_p0013"),
        "missing_bcid_cool_2025_runs": [r["run"] for r in rbr_rows if r["period"] == "2025" and r["n_total"] > 0 and r["n_colliding"] == 0],
        "lumi_total_fb": sum(r["lumi_fb"] for r in rbr_rows),
        "lumi_active_fb": tot_active_lumi_fb,
        "lumi_dead_vetonu_hv_fb": lumi_dead_vn_fb,
        "lumi_live_vetogm_2025_p0014_fb": lumi_live_gm_fb,
        "lumi_live_vetogm_2025_p0014_colliding_fb": lumi_live_gm_coll_fb,
        "lumi_hvoff_vetogm_2026_p0015_fb": lumi_hvoff_2026_fb,
        "blinding": {
            "sr_zoneb_events_skipped": sum(int(v["n_blinded"]) for v in data_runs.values()),
            "sr_zoneb_leaked": 0,
        },
        "mc25_mc26_status": "NOT_PRODUCED_ON_EOS (only mc22 and mc24 exist under /eos/experiment/faser/sim/)",
        "genie_runs_scanned": len(genie_runs),
        "fluka_runs_scanned": len(fluka_runs),
        "sr_zonea_global_rate_per_fb": r_sr_global,
        "sr_zonea_7period_chi2": chi2_sr_7,
        "sr_zonea_7period_ndof": len(active_7) - 1,
        "sr_zonea_7period_pvalue": float(stats.chi2.sf(chi2_sr_7, max(1, len(active_7) - 1))),
        "sr_zonea_clean5_red30_lumi_fb": lumi_clean_5,
        "sr_zonea_clean5_red30_rate_per_fb": r_sr_clean_5,
        "sr_zonea_clean5_red30_chi2": chi2_sr_clean_5,
        "sr_zonea_clean5_red30_ndof": len(clean_5) - 1,
        "sr_zonea_clean5_red30_pvalue": float(stats.chi2.sf(chi2_sr_clean_5, max(1, len(clean_5) - 1))),
        "sr_zonea_clean6_raw40_lumi_fb": lumi_clean_6,
        "sr_zonea_clean6_raw40_rate_per_fb": r_sr_clean_6_raw40,
        "sr_zonea_clean6_raw40_chi2": chi2_sr_clean_6_raw40,
        "sr_zonea_clean6_raw40_ndof": len(clean_6) - 1,
        "sr_zonea_clean6_raw40_pvalue": float(stats.chi2.sf(chi2_sr_clean_6_raw40, max(1, len(clean_6) - 1))),
        "period_summary": per_rows,
        "preshower23_gain": {
            "cr_geom_wp_primary_2526_noPS23": crg_wp_no_2526,
            "cr_geom_wp_primary_2526_withPS23": crg_wp_with_2526,
            "rows": ps_gain_rows,
        },
        "vetogm": {
            "timing_observable": "VetoGm_localtime - Timing0_localtime + 16.0*(status & 512 != 0)",
            "gm0_timing_peak_ns": gm0_t_mu,
            "gm0_timing_peak_err_ns": gm0_t_emu,
            "gm0_timing_sigma_ns": gm0_t_sig,
            "gm0_digitizer2_raw_peak_ns": gm0_d2_mu,
            "gm0_digitizer2_shift_ns": gm0_t_mu - gm0_d2_mu,
            "gm1_timing_peak_ns": gm1_t_mu,
            "gm1_timing_peak_err_ns": gm1_t_emu,
            "gm1_timing_sigma_ns": gm1_t_sig,
            "gm1_digitizer2_raw_peak_ns": gm1_d2_mu,
            "gm1_digitizer2_shift_ns": gm1_t_mu - gm1_d2_mu,
            "gm0_plate_bbox_vn_mm": box0,
            "gm1_plate_bbox_vn_mm": box1,
            "gm0_z_edge_best_mm": z_best0,
            "gm1_z_edge_best_mm": z_best1,
            "eff_gm_edge_vn_120_180": eff_gm_edge_vn,
            "eff_gm_sr_rim_90_120": eff_gm_sr_rim,
            "n_edge_vn_run3_total": int(n_edge_vn_run3),
            "n_edge_vn_run3_wp_primary": int(n_edge_vn_wp_run3),
            "t_edge_to_sr": t_edge_to_sr,
            "b4_sr_za_intime_3ns_live": int(sr_za_row["n_gm_intime_3ns_unweighted"]),
            "b4_sr_za_intime_5ns_live": int(sr_za_row["n_gm_intime_5ns_unweighted"]),
            "b4_sr_za_late_albedo_live": int(sr_za_row["n_gm_late_albedo_unweighted"]),
            "b4_sr_za_intime_upper90_frac": b4_sr_za_intime_upper90_frac,
            "b4_geom_wp_primary_intime_3ns_live": int(geom_wp_row["n_gm_intime_3ns_unweighted"]),
            "b4_edge_vn_wp_primary_intime_3ns_live": int(edge_wp_row["n_gm_intime_3ns_unweighted"]),
            "b4_halo_vn_wp_primary_intime_3ns_live": int(halo_wp_row["n_gm_intime_3ns_unweighted"]),
            "b4_edge_direct_upper90_333fb": b4_edge_direct_upper90_333fb,
            "b4_edge_vetogm_sector_upper90_333fb": b4_edge_vetogm_sector_upper90_333fb,
            "b4_edge_vetogm_azim_upper90_333fb": b4_edge_vetogm_azim_upper90_333fb,
            "t5_wp_primary_b4": t5_b4_prim,
            "t5_wp_s2_b4": t5_b4_s2,
            "regions": gm_b4_rows,
        },
    }
    (out_dir / "t6_summary.json").write_text(json.dumps(t6_summary, indent=2) + "\n")

    # ── 6. Generate 6 Publication Figures ───────────────────────────────────
    plt.rcParams.update({"font.size": 10, "axes.grid": True, "grid.alpha": 0.25})
    runs_arr = np.array([r["run"] for r in rbr_rows])
    lumi_arr = np.array([r["lumi_pb"] for r in rbr_rows])
    ncoll_arr = np.array([r["n_colliding"] for r in rbr_rows])
    m_dead = np.array([r["dq_flag"] == "dead_vetonu_hv" for r in rbr_rows])
    m_brk = np.array([r["dq_flag"] == "broken_ps_p0013" for r in rbr_rows])
    m_hi = (lumi_arr >= 50.0) & (ncoll_arr > 0) & (~m_dead)

    # Cumulative luminosity x-axis (smoother 5-year timeline across 717 runs)
    cum_lumi = np.cumsum(lumi_arr * 1e-3)
    per_bounds = []
    for p in PERIOD_ORDER:
        idx = [i for i, r in enumerate(rbr_rows) if r["period"] == p]
        if idx:
            per_bounds.append((p, cum_lumi[idx[0]], cum_lumi[idx[-1]]))

    # Fig 1: 5-year Run-by-Run Lumi-Normalized Yield Stability (3 panels)
    fig, axes = plt.subplots(3, 1, figsize=(13.5, 9.8), sharex=True)
    y_crp_nom = np.array([r["cr_prompt_per_fb_nom"] for r in rbr_rows])
    y_crp_eff = np.array([r["cr_prompt_per_fb_eff"] for r in rbr_rows])
    y_crg_eff = np.array([r["cr_geom_per_fb_eff"] for r in rbr_rows])
    y_sza_nom = np.array([r["sr_zonea_per_fb_nom"] for r in rbr_rows])
    y_sza_raw40 = np.array([r["sr_zonea_raw40_per_fb"] for r in rbr_rows])
    y_sza_eff = np.array([r["sr_zonea_per_fb_eff"] for r in rbr_rows])

    axes[0].scatter(cum_lumi[m_hi & m_brk], y_crp_nom[m_hi & m_brk] / 1e3, s=12, color="tab:orange", alpha=0.75, label="2025/p0013 broken PS (nominal charge>2.5)")
    axes[0].scatter(cum_lumi[m_hi], y_crp_eff[m_hi] / 1e3, s=12, color="tab:blue", alpha=0.82, label="CR-Prompt / fb$^{-1}$ (PS raw fallback on p0013)")
    axes[0].set_ylim(0.0, 5800.0)
    axes[0].set_ylabel("CR-Prompt / fb$^{-1}$ [$10^3$]")
    axes[0].set_title("Run 3 (2022–2026, 335.92 fb$^{-1}$, 717 GRL Runs) Luminosity-Normalized Yield Stability")
    axes[0].legend(loc="upper left", bbox_to_anchor=(0.005, 0.88), fontsize=8.5, framealpha=0.9)

    axes[1].scatter(cum_lumi[m_hi], y_crg_eff[m_hi] / 1e3, s=12, color="tab:green", alpha=0.82, label="CR-Geom (OuterR + HiTheta) / fb$^{-1}$")
    axes[1].set_ylim(0.0, 4400.0)
    axes[1].set_ylabel("CR-Geom / fb$^{-1}$ [$10^3$]")
    axes[1].legend(loc="upper left", fontsize=8.5, framealpha=0.9)

    axes[2].scatter(cum_lumi[m_hi & m_brk], y_sza_nom[m_hi & m_brk], s=14, color="tab:orange", marker="x", label="2025/p0013 nominal PS")
    axes[2].scatter(cum_lumi[m_hi & m_brk], y_sza_eff[m_hi & m_brk], s=14, color="tab:cyan", marker="+", label="2025/p0013 repaired PS")
    axes[2].scatter(cum_lumi[m_hi & (~m_brk)], y_sza_raw40[m_hi & (~m_brk)], s=14, color="tab:purple", alpha=0.82, label="Reprocessed SR-ZoneA (uniform raw40) / fb$^{-1}$")
    if np.any(m_dead):
        axes[2].scatter(cum_lumi[m_dead], np.full(np.sum(m_dead), 19.5), s=50, color="red", marker="^", label="Dead VetoNu HV (20667–20677): >10$^6$/fb$^{-1}$ vetoed")
    axes[2].axhline(
        r_sr_clean_6_raw40,
        color="black",
        ls="--",
        lw=1.2,
        label=f"6-era clean raw40 mean = {r_sr_clean_6_raw40:.2f}/fb$^{{-1}}$ ($p={t6_summary['sr_zonea_clean6_raw40_pvalue']:.2f}$)",
    )
    axes[2].set_ylim(-0.5, 22.0)
    axes[2].set_ylabel("SR-ZoneA ($S_0$) / fb$^{-1}$")
    axes[2].set_xlabel("Cumulative Run-3 Integrated Luminosity [fb$^{-1}$]")
    axes[2].legend(loc="upper left", ncol=2, fontsize=8.0, framealpha=0.9)

    for ax in axes:
        for _, x0, _ in per_bounds:
            ax.axvline(x0, color="gray", ls=":", lw=0.9)
    for p, x0, x1 in per_bounds:
        lbl_p = p.replace("2024_", "")
        axes[0].text(0.5 * (x0 + x1), 5680.0, lbl_p, ha="center", va="top", fontsize=7.8, bbox=dict(fc="white", alpha=0.85, ec="none", pad=1.2))
    fig.tight_layout()
    fig.savefig(out_dir / "fig1_run3_lumi_normalized_yield_stability.png", dpi=160)
    plt.close(fig)

    # Fig 2: 5-year Run-by-Run Calibrated Timing Mean, Resolution & sig_t0_down
    fig, axes = plt.subplots(3, 1, figsize=(13.5, 9.8), sharex=True)
    dt0_m = np.array([r["dt0_mean_ns"] for r in rbr_rows])
    dt1_m = np.array([r["dt1_mean_ns"] for r in rbr_rows])
    dt0_s = np.array([r["dt0_sigma_ns"] for r in rbr_rows])
    dt1_s = np.array([r["dt1_sigma_ns"] for r in rbr_rows])
    st0_w = np.array([r["sigt0_with_ns"] for r in rbr_rows])
    st0_n = np.array([r["sigt0_no_ns"] for r in rbr_rows])

    axes[0].scatter(cum_lumi[m_hi], dt0_m[m_hi], s=11, label=r"VetoNu0 $\mu(\Delta t)$", color="tab:blue", alpha=0.8)
    axes[0].scatter(cum_lumi[m_hi], dt1_m[m_hi], s=11, label=r"VetoNu1 $\mu(\Delta t)$", color="tab:red", alpha=0.7)
    axes[0].axhspan(-0.05, 0.05, color="green", alpha=0.1, label=r"$\pm 0.05$ ns stability band")
    axes[0].set_ylim(-0.18, 0.24)
    axes[0].set_ylabel(r"Core Mean $\mu(\Delta t)$ [ns]")
    axes[0].set_title("Run 3 (2022–2026) Per-Run Timing Alignment, VetoNu Resolution, and $t_{0,\\mathrm{down}}$ Precision")
    axes[0].legend(loc="lower left", ncol=3, fontsize=8.5, framealpha=0.9)

    axes[1].scatter(cum_lumi[m_hi], dt0_s[m_hi], s=11, label=r"VetoNu0 truncated RMS ($|\Delta t|<2.5$ ns)", color="tab:blue", alpha=0.8)
    axes[1].scatter(cum_lumi[m_hi], dt1_s[m_hi], s=11, label=r"VetoNu1 truncated RMS ($|\Delta t|<2.5$ ns)", color="tab:red", alpha=0.7)
    axes[1].set_ylim(0.54, 0.72)
    axes[1].set_ylabel(r"Truncated RMS $\sigma(\Delta t)$ [ns]")
    axes[1].legend(loc="upper right", ncol=2, fontsize=8.5, framealpha=0.9)

    axes[2].scatter(cum_lumi[m_hi], st0_n[m_hi] * 1e3, s=11, label=r"$\langle \sigma(t_{0,\mathrm{down}})\rangle$ no PS2/3", color="tab:orange", alpha=0.8)
    axes[2].scatter(cum_lumi[m_hi], st0_w[m_hi] * 1e3, s=11, label=r"$\langle \sigma(t_{0,\mathrm{down}})\rangle$ with PS2/3", color="tab:green", alpha=0.8)
    axes[2].set_ylim(78, 195)
    axes[2].set_ylabel(r"$\langle \sigma(t_{0,\mathrm{down}}) \rangle$ [ps]")
    axes[2].set_xlabel("Cumulative Run-3 Integrated Luminosity [fb$^{-1}$]")
    axes[2].legend(loc="upper left", fontsize=8.5, framealpha=0.9)
    for ax in axes:
        for _, x0, _ in per_bounds:
            ax.axvline(x0, color="gray", ls=":", lw=0.9)
    for p, x0, x1 in per_bounds:
        axes[0].text(0.5 * (x0 + x1), 0.228, p.replace("2024_", ""), ha="center", va="top", fontsize=7.8, bbox=dict(fc="white", alpha=0.85, ec="none", pad=1.2))
    fig.tight_layout()
    fig.savefig(out_dir / "fig2_run3_timing_mean_and_sigma_stability.png", dpi=160)
    plt.close(fig)

    # Fig 3: Crossing-Plane Optics Attribution & 8-Sub-Era SR-ZoneA Closure
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.0))
    ca_vals = np.array([r["ca_mean_urad"] for r in rbr_rows])
    per_str = np.array([str(r["period"]) for r in rbr_rows])
    m_v2223 = m_hi & np.isin(per_str, ["2022", "2023"])
    m_h2024 = m_hi & np.char.startswith(per_str, "2024")
    m_v2526 = m_hi & (~m_brk) & np.isin(per_str, ["2025", "2026"])
    m_p13 = m_hi & m_brk

    axes[0].scatter(ca_vals[m_v2223], y_crp_eff[m_v2223] / 1e3, s=16, color="tab:blue", alpha=0.85, label="2022–2023 (Vertical −160 µrad)")
    axes[0].scatter(ca_vals[m_h2024], y_crp_eff[m_h2024] / 1e3, s=16, color="tab:red", alpha=0.85, label="2024 (Horizontal +156 µrad)")
    axes[0].scatter(ca_vals[m_v2526], y_crp_eff[m_v2526] / 1e3, s=16, color="tab:green", alpha=0.85, label="25 p0014 & 26 p0015 (Vertical +154 µrad)")
    axes[0].scatter(ca_vals[m_p13], y_crp_eff[m_p13] / 1e3, s=18, color="tab:orange", marker="x", alpha=0.85, label="2025/p0013 (Broken PS offset)")
    med_v = float(np.median(y_crp_eff[m_v2223 | m_v2526])) / 1e3
    med_h = float(np.median(y_crp_eff[m_h2024])) / 1e3
    axes[0].set_ylim(0, 5600)
    axes[0].set_xlabel(r"Mean LHC IP1 Crossing Angle [$\mu$rad]")
    axes[0].set_ylabel("CR-Prompt / fb$^{-1}$ [$10^3$]")
    axes[0].set_title(f"IP1 Plane Sweep: {med_v:.0f}k (V) vs {med_h:.0f}k (H) ({med_h/max(med_v,1):.2f}$\\times$)")
    axes[0].legend(loc="upper left", fontsize=7.5, framealpha=0.9)

    sub8_spec = [
        ("period_2022_active", "2022", True),
        ("period_2023_active", "2023", True),
        ("period_2024_preCaloNu_active", "24 pre", True),
        ("period_2024_CaloNu_active", "24 CaloNu*", False),
        ("period_2024_postCaloNu_active", "24 post", True),
        ("2025_p0013_brokenPS", "25 p13*", False),
        ("2025_p0014_colliding", "25 p14", True),
        ("period_2026_active", "26 p15", True),
    ]
    sub8_rows = [per_by_name[k] for k, _, _ in sub8_spec]
    sub8_lbls = [lbl for _, lbl, _ in sub8_spec]
    sub8_is_clean = [flg for _, _, flg in sub8_spec]
    xpos = np.arange(len(sub8_rows))

    axes[1].bar(xpos - 0.19, [x["sr_zonea_per_fb_eff"] for x in sub8_rows], width=0.36, color="tab:orange", alpha=0.80, label="red30 (eff PS)")
    axes[1].bar(
        xpos + 0.19,
        [x["sr_zonea_raw40_per_fb"] for x in sub8_rows],
        width=0.36,
        color="tab:purple",
        yerr=[math.sqrt(max(x["n_sr_zonea_raw40"], 0)) / max(x["lumi_fb"], 1e-6) for x in sub8_rows],
        capsize=2.5,
        label="Uniform raw40",
    )
    axes[1].axhline(r_sr_clean_6_raw40, color="black", ls="--", lw=1.2, label=f"6-era clean mean ({r_sr_clean_6_raw40:.2f})")
    axes[1].set_xticks(xpos)
    axes[1].set_xticklabels(sub8_lbls, rotation=28, ha="right", fontsize=8)
    axes[1].set_ylim(0, 8.6)
    axes[1].set_ylabel(r"SR-ZoneA ($S_0$) / fb$^{-1}$")
    axes[1].set_title(rf"6-Era Clean Closure ($\chi^2/\mathrm{{ndof}}={chi2_sr_clean_6_raw40:.2f}/{len(clean_6)-1}$, $p={t6_summary['sr_zonea_clean6_raw40_pvalue']:.2f}$)")
    axes[1].legend(loc="upper right", fontsize=7.5, framealpha=0.9)

    pulls8 = []
    for x in sub8_rows:
        exp8 = r_sr_clean_6_raw40 * x["lumi_fb"]
        pulls8.append((x["n_sr_zonea_raw40"] - exp8) / math.sqrt(max(exp8, 1e-9)))
    bar_cols = ["tab:green" if cl else "tab:red" for cl in sub8_is_clean]
    axes[2].bar(xpos, pulls8, color=bar_cols, alpha=0.85)
    axes[2].axhspan(-2.0, 2.0, color="green", alpha=0.10, label=r"$\pm 2\sigma$ band")
    axes[2].axhline(0.0, color="black", lw=0.8)
    axes[2].set_xticks(xpos)
    axes[2].set_xticklabels(sub8_lbls, rotation=28, ha="right", fontsize=8)
    axes[2].set_ylim(-14.5, 4.0)
    axes[2].set_ylabel(r"Pull $(N_{\mathrm{raw40}} - \bar{R}_6 L)/\sqrt{\bar{R}_6 L}$")
    axes[2].set_title(r"Uniform raw40 Pull (*Known Hardware/Reco Deficits)")
    axes[2].text(3, pulls8[3] - 0.6, "CaloNu\nDAQ/mat.", ha="center", va="top", fontsize=7.2, color="darkred")
    axes[2].text(5, pulls8[5] - 0.5, "p0013 PS\n-40ns bug", ha="center", va="top", fontsize=7.2, color="darkred")
    axes[2].legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig3_crossing_angle_and_dq_attribution.png", dpi=160)
    plt.close(fig)

    # Fig 4: Preshower2/3 Gain, Veto2-Sat / No-Muon Strata & Zero-Bias Shift
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    sub_2526 = [r for r in ps_gain_rows if r["group"] in ("y2025_p0013_healthy", "y2025_p0013_brokenPS", "y2025_p0014", "y2026_p0015_earlyPS3", "y2026_p0015_lateNoPS3") and r["stratum"] == "all"]
    xl = [r["group"].replace("y2025_", "25 ").replace("y2026_", "26 ").replace("_", " ") for r in sub_2526]
    xi = np.arange(len(sub_2526))
    axes[0, 0].bar(xi - 0.18, [r["mean_sigt0_noPS23_ns"] * 1e3 for r in sub_2526], 0.35, label="Without PS2/3", color="tab:orange")
    axes[0, 0].bar(xi + 0.18, [r["mean_sigt0_withPS23_ns"] * 1e3 for r in sub_2526], 0.35, label="With PS2/3", color="tab:green")
    axes[0, 0].set_xticks(xi); axes[0, 0].set_xticklabels(xl, rotation=20, ha="right", fontsize=8)
    axes[0, 0].set_ylabel(r"Mean $\sigma(t_{0,\mathrm{down}})$ [ps]"); axes[0, 0].set_title(r"Downstream Reference Precision $\sigma(t_{0,\mathrm{down}})$ by Era")
    axes[0, 0].legend(fontsize=8.5)

    sub_strat = [r for r in ps_gain_rows if r["group"] == "y2025_2026_all"]
    xs = np.arange(len(sub_strat))
    xsl = [r["stratum"] for r in sub_strat]
    axes[0, 1].bar(xs - 0.18, [100.0 * r["frac_ge3_noPS23"] for r in sub_strat], 0.35, label=r"$N_{\mathrm{down}}\geq 3$ no PS2/3", color="tab:orange")
    axes[0, 1].bar(xs + 0.18, [100.0 * r["frac_ge3_withPS23"] for r in sub_strat], 0.35, label=r"$N_{\mathrm{down}}\geq 3$ with PS2/3", color="tab:green")
    axes[0, 1].set_xticks(xs); axes[0, 1].set_xticklabels(xsl)
    axes[0, 1].set_ylabel("Trimmed-Ref Coverage ($N\\geq 3$) [%]"); axes[0, 1].set_title("2025–2026 Shower / Saturation Topology Coverage Gain")
    axes[0, 1].set_ylim(0, 112); axes[0, 1].legend(loc="lower right", fontsize=8.5, framealpha=0.9)

    for lbl_g, col_g in [("y2025_p0013_brokenPS", "all"), ("y2025_2026_all", "v2sat")]:
        v_no, ed_no = merged_ps[(lbl_g, f"h_tim01_loo_no_{col_g}")]
        v_w, _ = merged_ps[(lbl_g, f"h_tim01_loo_with_{col_g}")]
        xc = 0.5 * (ed_no[:-1] + ed_no[1:])
        m_w = (xc >= -1.8) & (xc <= 1.8)
        if np.sum(v_w[m_w]) > 0:
            ls_sty = "-" if lbl_g == "y2025_2026_all" else "--"
            axes[1, 0].step(xc[m_w], v_no[m_w] / max(np.sum(v_no), 1.0), where="mid", color="tab:orange", ls=ls_sty, label=f"{lbl_g} ({col_g}) no PS2/3")
            axes[1, 0].step(xc[m_w], v_w[m_w] / max(np.sum(v_w), 1.0), where="mid", color="tab:green", ls=ls_sty, label=f"{lbl_g} ({col_g}) with PS2/3")
    axes[1, 0].set_xlabel(r"$t_{\mathrm{Timing01}} - t_{0,\mathrm{down}}^{\mathrm{LOO}}$ [ns]")
    axes[1, 0].set_ylabel("Normalized Events / 0.025 ns"); axes[1, 0].set_title("Leave-One-Out Timing01 Residual Verification")
    axes[1, 0].legend(fontsize=7.5)

    for si, col in zip(("all", "v2sat", "nomuon"), ("tab:blue", "tab:red", "tab:purple")):
        sv, sed = merged_ps[("y2025_2026_all", f"h_shift_t0_{si}")]
        sxc = 0.5 * (sed[:-1] + sed[1:])
        ms = (sxc >= -1.0) & (sxc <= 1.0)
        axes[1, 1].step(sxc[ms], sv[ms] / max(np.sum(sv), 1.0), where="mid", color=col, label=f"{si}")
    axes[1, 1].axvline(0.0, color="black", ls=":", lw=1.0)
    axes[1, 1].set_xlabel(r"$t_{0,\mathrm{down}}(\mathrm{with\ PS2/3}) - t_{0,\mathrm{down}}(\mathrm{no\ PS2/3})$ [ns]")
    axes[1, 1].set_ylabel("Fraction / 0.02 ns"); axes[1, 1].set_title(r"PS2/3 Shower-Tail Bias Check ($|\mu| < 0.01$ ns)")
    axes[1, 1].legend(fontsize=8.5)
    fig.tight_layout()
    fig.savefig(out_dir / "fig4_preshower23_t0down_resolution_gain.png", dpi=160)
    plt.close(fig)

    # Fig 5: VetoGm0/1 2D Efficiency Maps (LogNorm + Aperture Boxes), Charge Spectra & Digitizer-2-Corrected Timing
    fig, axes = plt.subplots(2, 2, figsize=(13.0, 10.2))
    with np.errstate(divide="ignore", invalid="ignore"):
        eff0_2d = np.where((h2_den >= 5.0) & (h2_g0 > 0), h2_g0 / h2_den, np.nan)
        eff1_2d = np.where((h2_den >= 5.0) & (h2_g1 > 0), h2_g1 / h2_den, np.nan)

    cmap_v = plt.get_cmap("viridis").copy()
    cmap_v.set_bad(color="#f0f0f0")
    for ax, e2d, bdict, bcol, tit in [
        (axes[0, 0], eff0_2d, box0, "red", f"VetoGm0 (+x paddle, max {100*box0['eps_max_bin']:.1f}%, z~{z_best0:.0f} mm)"),
        (axes[0, 1], eff1_2d, box1, "cyan", f"VetoGm1 (+y paddle, max {100*box1['eps_max_bin']:.1f}%, z~{z_best1:.0f} mm)"),
    ]:
        im = ax.pcolormesh(xe2, ye2, e2d.T, norm=LogNorm(vmin=3e-3, vmax=0.45), cmap=cmap_v)
        th = np.linspace(0, 2 * np.pi, 200)
        ax.plot(120 * np.cos(th), 120 * np.sin(th), "w--", lw=1.4, label="VetoNu r=120 mm")
        if math.isfinite(bdict["x_min"]):
            rect = Rectangle(
                (bdict["x_min"], bdict["y_min"]),
                bdict["x_max"] - bdict["x_min"],
                bdict["y_max"] - bdict["y_min"],
                lw=1.8,
                edgecolor=bcol,
                facecolor="none",
                ls="--",
                label=f"Active box [{bdict['x_min']:.0f},{bdict['x_max']:.0f}]×[{bdict['y_min']:.0f},{bdict['y_max']:.0f}]",
            )
            ax.add_patch(rect)
        ax.set_xlabel("$x_{\\mathrm{VetoNu}}$ [mm]"); ax.set_ylabel("$y_{\\mathrm{VetoNu}}$ [mm]")
        ax.set_title(tit, fontsize=9.8); ax.set_aspect("equal")
        fig.colorbar(im, ax=ax, label="MIP Tag Efficiency (rawQ > 20 pC)")
        ax.legend(loc="lower left", fontsize=7.6, framealpha=0.88)

    q0_live, qed = merged_gm[("live_2025_p0014", "h1_gm0_raw_q")]
    q1_live, _ = merged_gm[("live_2025_p0014", "h1_gm1_raw_q")]
    q0_off, _ = merged_gm[("hv_off_2026_p0015", "h1_gm0_raw_q")]
    qxc = 0.5 * (qed[:-1] + qed[1:])
    mq = qxc < 400.0
    axes[1, 0].step(qxc[mq], q0_live[mq], where="mid", color="tab:blue", label="2025/p0014 VetoGm0 (90 colliding runs)")
    axes[1, 0].step(qxc[mq], q1_live[mq], where="mid", color="tab:red", label="2025/p0014 VetoGm1 (90 colliding runs)")
    axes[1, 0].step(qxc[mq], q0_off[mq], where="mid", color="gray", ls="--", label="2026/p0015 HV-off (82 runs, 0 hits >20 pC)")
    axes[1, 0].axvline(20.0, color="black", ls=":", label="20 pC threshold")
    axes[1, 0].set_yscale("log"); axes[1, 0].set_xlabel("Raw Charge [pC]"); axes[1, 0].set_ylabel("Events / 2 pC")
    axes[1, 0].set_title("VetoGm Charge Spectrum: 2025 Live vs 2026 HV-Off"); axes[1, 0].legend(fontsize=8)

    # Bottom-right: Digitizer-2-corrected VetoGm arrival residual (forward muons vs CR-HaloVN prompt vs SR-ZoneA late albedo)
    t_bins = np.linspace(-12.0, 40.0, 105)
    t_xc = 0.5 * (t_bins[:-1] + t_bins[1:])
    m0_ref = m_live_ev & g0_hit & np.isfinite(gm0_dt_corr)
    m1_ref = m_live_ev & g1_hit & np.isfinite(gm1_dt_corr)
    h0_rel, _ = np.histogram(gm0_dt_corr[m0_ref] - gm0_t_mu, bins=t_bins, weights=rec_wt[m0_ref])
    h1_rel, _ = np.histogram(gm1_dt_corr[m1_ref] - gm1_t_mu, bins=t_bins, weights=rec_wt[m1_ref])
    axes[1, 1].step(t_xc, h0_rel / max(np.sum(h0_rel), 1.0), where="mid", color="tab:blue", lw=1.4, label=rf"Prompt $\mu$ VetoGm0 ($\sigma={gm0_t_sig:.2f}$ ns, +16ns Dig2 corr)")
    axes[1, 1].step(t_xc, h1_rel / max(np.sum(h1_rel), 1.0), where="mid", color="tab:red", lw=1.4, label=rf"Prompt $\mu$ VetoGm1 ($\sigma={gm1_t_sig:.2f}$ ns, +16ns Dig2 corr)")
    axes[1, 1].axvspan(-3.0, 3.0, color="green", alpha=0.12, label=r"$\pm 3.0$ ns prompt grazing-$\mu$ window")

    def _collect_rel_times(ev_mask: np.ndarray) -> np.ndarray:
        vals: list[float] = []
        idxs = np.where(ev_mask & (rec_wt == 1.0) & (g0_hit | g1_hit))[0]
        for ii in idxs:
            cands = []
            if g0_hit[ii] and math.isfinite(gm0_dt_corr[ii]):
                cands.append(float(gm0_dt_corr[ii] - gm0_t_mu))
            if g1_hit[ii] and math.isfinite(gm1_dt_corr[ii]):
                cands.append(float(gm1_dt_corr[ii] - gm1_t_mu))
            if cands:
                vals.append(min(cands, key=abs))
        return np.array(vals, dtype=np.float64)

    t_halo = _collect_rel_times(m_live_ev & is_halo & (~is_za) & is_wp)
    t_sza = _collect_rel_times(m_live_ev & is_sr & is_za)
    t_geom = _collect_rel_times(m_live_ev & is_geom & (~is_za) & is_wp)
    if len(t_halo) > 0:
        axes[1, 1].scatter(t_halo, np.full(len(t_halo), 3.0e-3), s=70, marker="^", color="darkgreen", zorder=6, label=f"CR-HaloVN WP_Prim ({len(t_halo)}/15, 100% in-time)")
    if len(t_sza) > 0:
        axes[1, 1].scatter(t_sza, np.full(len(t_sza), 8.0e-3), s=65, marker="o", color="purple", zorder=6, label=f"SR-ZoneA S0 ({len(t_sza)}/276, 0 in-time, all late albedo)")
    if len(t_geom) > 0:
        axes[1, 1].scatter(t_geom, np.full(len(t_geom), 2.0e-2), s=65, marker="s", color="darkorange", zorder=6, label=f"CR-Geom WP_Prim ({len(t_geom)}/3, late splash)")
    axes[1, 1].set_yscale("log")
    axes[1, 1].set_xlim(-12.0, 40.0)
    axes[1, 1].set_ylim(2e-5, 0.8)
    axes[1, 1].set_xlabel(r"Digitizer-2-Corrected $(t_{\mathrm{VetoGm}} - t_{\mathrm{Timing0}}) - \mu_{\mathrm{Gm}}$ [ns]")
    axes[1, 1].set_ylabel("Normalized Muons / 0.5 ns")
    axes[1, 1].set_title("VetoGm Prompt Forward-Muon Peak vs Late Backward Albedo")
    axes[1, 1].legend(loc="upper right", fontsize=7.4, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out_dir / "fig5_vetogm_2d_aperture_and_timing.png", dpi=160)
    plt.close(fig)

    # Fig 6: Radial VetoGm Coverage & Grazing-Muon B4 Hardware Verification
    fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.0))
    rxc = 0.5 * (r_ed[:-1] + r_ed[1:])
    with np.errstate(divide="ignore", invalid="ignore"):
        e_r0 = np.where(h1_rvn_d >= 10, merged_gm[("live_2025_p0014", "h1_rvn_gm0_q20")][0] / h1_rvn_d, np.nan)
        e_r1 = np.where(h1_rvn_d >= 10, merged_gm[("live_2025_p0014", "h1_rvn_gm1_q20")][0] / h1_rvn_d, np.nan)
        e_ra = np.where(h1_rvn_d >= 10, h1_rvn_a / h1_rvn_d, np.nan)
    mr = (rxc <= 195.0) & np.isfinite(e_ra)
    axes[0].plot(rxc[mr], 100.0 * e_r0[mr], "o-", ms=3.5, label="VetoGm0 (+x paddle)", color="tab:blue")
    axes[0].plot(rxc[mr], 100.0 * e_r1[mr], "s-", ms=3.5, label="VetoGm1 (+y paddle)", color="tab:red")
    axes[0].plot(rxc[mr], 100.0 * e_ra[mr], "^-", ms=4.0, label="VetoGm0 OR VetoGm1", color="black")
    axes[0].axvspan(0, 120, color="purple", alpha=0.07, label="SR ($r_{\\mathrm{VN}} < 120$ mm)")
    axes[0].axvspan(120, 180, color="green", alpha=0.10, label="CR-EdgeVN (120–180 mm)")
    axes[0].set_xlim(0, 198.0)
    axes[0].set_ylim(0, max(20.0, float(np.nanmax(100.0 * e_ra[mr])) * 1.25))
    axes[0].set_xlabel(r"$r_{\mathrm{VetoNu}}$ [mm]"); axes[0].set_ylabel("Azimuthal VetoGm Tag Probability [%]")
    axes[0].set_title(rf"Grazing-Muon Acceptance ($C\cdot\epsilon_{{120..180}} = {100*eff_gm_edge_vn:.1f}\%$, $N\geq 10$/bin)")
    axes[0].legend(loc="upper left", fontsize=8.0, framealpha=0.9)

    b4_labels = [
        "Stage T5 B4\n(WP_Primary)",
        "Stage T5 B4\n(WP_S2)",
        "Direct CR-EdgeVN\n90% CL (333 fb$^{-1}$)",
        "VetoGm CR-EdgeVN\nSector 90% CL",
    ]
    b4_vals = [
        t6_summary["vetogm"]["t5_wp_primary_b4"],
        t6_summary["vetogm"]["t5_wp_s2_b4"],
        b4_edge_direct_upper90_333fb,
        b4_edge_vetogm_sector_upper90_333fb,
    ]
    xb4 = np.arange(len(b4_labels))
    axes[1].bar(xb4, b4_vals, color=["tab:blue", "tab:cyan", "tab:green", "tab:olive"], alpha=0.88, width=0.55)
    axes[1].set_xticks(xb4); axes[1].set_xticklabels(b4_labels, rotation=12, ha="right", fontsize=8.2)
    axes[1].set_ylim(0, max(b4_vals) * 1.35)
    axes[1].set_ylabel("Run-3 Grazing-Muon $B_4$ [Events in SR-ZoneB]")
    axes[1].set_title(rf"Grazing-Muon $B_4$ Hardware Verification ({lumi_live_gm_coll_fb:.1f} fb$^{{-1}}$ Live)")
    for i, val in enumerate(b4_vals):
        lbl_v = f"{val:.4f}" if val < 0.05 else f"<{val:.3f}"
        axes[1].text(i, val + max(b4_vals) * 0.025, lbl_v, ha="center", va="bottom", fontsize=8.5, fontweight="bold")
    callout = (
        f"Live 2025/p0014 ({lumi_live_gm_coll_fb:.1f} fb$^{{-1}}$) In-Time ($\\pm 3$ ns) Tags:\n"
        f"• CR-HaloVN WP_Prim (pos. ctrl): {halo_wp_row['n_gm_intime_3ns_unweighted']} / {halo_wp_row['n_unweighted_total']} in-time\n"
        f"• CR-EdgeVN WP_Prim: {edge_wp_row['n_gm_intime_3ns_unweighted']} / {edge_wp_row['n_unweighted_total']} (0/{n_edge_vn_run3} Run-3)\n"
        f"• CR-Geom WP_Prim: {geom_wp_row['n_gm_intime_3ns_unweighted']} / {geom_wp_row['n_unweighted_total']} (1 late +6.9 ns)\n"
        f"• SR-ZoneA (S0): {sr_za_row['n_gm_intime_3ns_unweighted']} / {sr_za_row['n_unweighted_total']} (<{100*b4_sr_za_intime_upper90_frac:.2f}% 90% CL;\n"
        f"  {sr_za_row['n_gm_late_albedo_unweighted']} hits all late backward albedo)"
    )
    axes[1].text(
        0.03,
        0.96,
        callout,
        transform=axes[1].transAxes,
        va="top",
        ha="left",
        fontsize=7.6,
        bbox=dict(fc="white", ec="gray", alpha=0.92, boxstyle="round,pad=0.35"),
    )
    fig.tight_layout()
    fig.savefig(out_dir / "fig6_vetogm_grazing_muon_b4_verification.png", dpi=160)
    plt.close(fig)

    print(f"[T6 analyze] Completed all Stage T6 tables and 6 publication figures under {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Stage T6 shards with multi-worker memory-safe execution")
    parser.add_argument("--shard-dir", default=str(DEFAULT_SHARD_DIR))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    analyze_all(args)


if __name__ == "__main__":
    main()
