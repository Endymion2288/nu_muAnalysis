#!/usr/bin/env python3
"""
Stage T2 (Stage 213) MC Timing Calibration & Data-vs-FLUKA Closure Validator.

Subcommands (--step):
  fit     : Fit mc_timing_calib.json from Condor mc-scan shards + GENIE VetoNu HITS
            (t_mc_ref per run/family, Timing/Preshower linear slopes, transverse flatness,
            MC time-walk, and intrinsic power-law sigma_MC(Q)); generates Fig 1 & Fig 2.
  closure : Compare unblinded single-muon Data (data-closure shards, strictly guarded by
            TimingBlindingGuard) against smeared FLUKA MC (fluka-closure shards) + GENIE
            t0_down coverage; extracts SF_chi2_down and generates Fig 3, Fig 4, TSVs & JSON.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import glob
import json
import math
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit
from scipy.special import erf
import uproot

import sys
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from calibrate_scint_timing import (
    CHANNELS,
    CH_TO_IDX,
    CHANNEL_PLANE_IDX,
    MIP_THRESHOLDS,
    _gauss,
    _weighted_core_gauss,
)

REPO_DIR = SCRIPT_DIR.parent.parent
OUT_DIR = REPO_DIR / "workbook/stage213_timing_t2"
CALIB_DIR = REPO_DIR / "AnalysisZipFramework/config/timing_calib"

CALYPSO_SLOPES = {
    "Timing0": (1.0 / 130.0, 0.0),   # dtime subtracted in Calypso -> check exact sign empirically!
    "Timing1": (1.0 / 130.0, 0.0),
    "Timing2": (1.0 / 130.0, 0.0),
    "Timing3": (1.0 / 130.0, 0.0),
    "Timing01": (0.0, 0.0),
    "Timing23": (0.0, 0.0),
    "Preshower0": (0.0, -1.0 / 230.0),
    "Preshower1": (0.0, -1.0 / 230.0),
}

# Exact Run-to-family mapping matching TimingCalibrator::mcFamilyForRun
def family_for_mc_run(run: int) -> str:
    if (200080 <= run <= 200090) or (200104 <= run <= 200115):
        return "genie_2022_2023"
    if (200091 <= run <= 200101) or (200160 <= run <= 200171):
        return "genie_2024_noCaloNu"
    if (200137 <= run <= 200147) or (200172 <= run <= 200183):
        return "genie_2024_CaloNu"
    if 210000 <= run <= 210007:
        return "fluka_mc22_s0010"
    if 210008 <= run <= 210009:
        return "fluka_mc22_s0012"
    if run >= 210010:
        return "fluka_mc24"
    return "genie_2024_noCaloNu"


def _fit_peak_hist1d(centers: np.ndarray, counts: np.ndarray, min_entries: int = 20) -> tuple[float | None, float | None, float]:
    tot = float(np.sum(counts))
    if tot < min_entries:
        return None, None, 0.0
    bw = float(centers[1] - centers[0])
    # Smooth over 5 bins to isolate peak against single-bin fluctuations
    smooth = np.convolve(counts, np.ones(5), mode="same")
    pk = int(np.argmax(smooth))
    x0 = float(centers[pk])
    for hw in (1.5, 0.8, 0.45):
        m = np.abs(centers - x0) <= hw
        if np.sum(counts[m]) < min_entries:
            continue
        x0 = float(np.sum(centers[m] * counts[m]) / np.sum(counts[m]))
    m_fit = (np.abs(centers - x0) <= 0.6) & (counts > 0)
    if np.count_nonzero(m_fit) >= 5 and tot >= 60:
        xf = centers[m_fit]
        yf = counts[m_fit]
        sig0 = max(bw * 1.5, float(np.sqrt(np.average((xf - x0) ** 2, weights=yf))))
        try:
            popt, _ = curve_fit(
                _gauss, xf, yf,
                p0=[float(np.max(yf)), x0, min(sig0, 0.5)],
                bounds=([0.0, x0 - 0.4, bw * 0.5], [1e14, x0 + 0.4, 1.5]),
                maxfev=1500,
            )
            return float(popt[1]), float(popt[2]), tot
        except Exception:
            pass
    m_fb = np.abs(centers - x0) <= 0.6
    if np.sum(counts[m_fb]) <= 0:
        return x0, 0.1, tot
    w = counts[m_fb]
    xc = centers[m_fb]
    mu = float(np.sum(w * xc) / np.sum(w))
    sig = float(math.sqrt(max(bw * bw, np.sum(w * (xc - mu) ** 2) / np.sum(w))))
    return mu, sig, tot


def _fit_trunc_gauss_hist(edges: np.ndarray, counts: np.ndarray, lo: float, hi: float,
                          sumw2: np.ndarray | None = None) -> tuple[float, float, float, float]:
    """Fit truncated Gaussian PDF over [lo, hi] via binned curve_fit (no edge-clipping bias)."""
    centers = 0.5 * (edges[:-1] + edges[1:])
    bw = float(edges[1] - edges[0])
    m = (centers >= lo) & (centers <= hi)
    xf = centers[m]
    yf = counts[m].astype(np.float64)
    tot = float(np.sum(yf))
    if tot < 30.0 or len(xf) < 6:
        return float("nan"), float("nan"), float("nan"), tot
    mu0 = float(np.average(xf, weights=np.maximum(yf, 1e-9)))
    sig0 = max(0.05, float(math.sqrt(np.average((xf - mu0) ** 2, weights=np.maximum(yf, 1e-9)))))

    def pdf_scaled(x: np.ndarray, amp_tot: float, mu: float, sig: float) -> np.ndarray:
        norm = 0.5 * (erf((hi - mu) / (math.sqrt(2.0) * sig)) - erf((lo - mu) / (math.sqrt(2.0) * sig)))
        norm = max(norm, 1e-6)
        return (amp_tot * bw / (sig * math.sqrt(2.0 * math.pi) * norm)) * np.exp(-0.5 * ((x - mu) / sig) ** 2)

    try:
        err = np.sqrt(np.maximum(sumw2[m] if sumw2 is not None else yf, 1.0))
        popt, pcov = curve_fit(
            pdf_scaled, xf, yf,
            p0=[tot, mu0, min(sig0 * 1.1, 1.0)],
            sigma=err,
            absolute_sigma=True,
            bounds=([tot * 0.2, lo + 0.05, 0.04], [tot * 5.0, hi - 0.05, 2.5]),
            maxfev=3000,
        )
        return float(popt[1]), float(popt[2]), float(math.sqrt(pcov[2, 2])), tot
    except Exception:
        return mu0, sig0, float("nan"), tot


def _read_mc_scan_shard(fpath: str) -> dict[str, Any]:
    out: dict[str, Any] = {"summary": {}, "hists": {}, "recs": None}
    with uproot.open(fpath) as f:
        if "mc_summary" in f:
            s = f["mc_summary"].arrays(library="np")
            for i in range(len(s["run"])):
                r = int(s["run"][i])
                out["summary"][r] = {
                    "n_total": int(s["n_total"][i]),
                    "n_lt1": int(s["n_lt1"][i]),
                    "n_clean_muon": int(s["n_clean_muon"][i]),
                    "n_kin_sr": int(s["n_kin_sr"][i]),
                    "has_veto11": bool(s["has_veto11"][i]),
                    "has_preshower23": bool(s["has_preshower23"][i]),
                    "has_muon": bool(s["has_muon"][i]),
                    "has_reduced_charge": bool(s["has_reduced_charge"][i]),
                }
        for key in f.keys():
            if "/" not in key:
                continue
            kclean = key.split(";")[0]
            if "/h_loc_" in kclean:
                rstr, hname = kclean.split("/", 1)
                run = int(rstr.replace("run_", ""))
                h = f[key]
                vals, edges = h.to_numpy()
                out["hists"].setdefault(run, {})[hname] = (vals.astype(np.float64), edges)
        if "mc_muons" in f and f["mc_muons"].num_entries > 0:
            out["recs"] = f["mc_muons"].arrays(library="np")
    return out


def _read_closure_shard(fpath: str) -> dict[str, Any]:
    out: dict[str, Any] = {"runs": {}, "hists": {}}
    with uproot.open(fpath) as f:
        if "closure_summary" in f:
            s = f["closure_summary"].arrays(library="np")
            for i in range(len(s["run"])):
                r = int(s["run"][i])
                d = out["runs"].setdefault(r, {
                    "is_mc": bool(s["is_mc"][i]),
                    "n_total": 0, "n_grl_fail": 0, "n_non_colliding": 0, "n_blinded": 0,
                    "n_clean_1trk": 0, "n_kin_sr": 0, "n_kin_sr_valid_t0down": 0, "n_kin_sr_valid_veto2only": 0,
                })
                for k in ("n_total", "n_grl_fail", "n_non_colliding", "n_blinded",
                          "n_clean_1trk", "n_kin_sr", "n_kin_sr_valid_t0down", "n_kin_sr_valid_veto2only"):
                    d[k] += int(s[k][i])
        for key in f.keys():
            if "/" not in key:
                continue
            kclean = key.split(";")[0]
            pdir, hname = kclean.split("/", 1)
            if not pdir.startswith("period_"):
                continue
            per = pdir[len("period_"):]
            vals, edges = f[key].to_numpy()
            out["hists"].setdefault(per, {})[hname] = (vals.astype(np.float64), edges)
    return out


def _fit_linear_slope(coord: np.ndarray, resid: np.ndarray, xrange: tuple[float, float] = (-110.0, 110.0)) -> tuple[float, float, float]:
    """Robust binned median linear regression y = a + slope * x."""
    m = np.isfinite(coord) & np.isfinite(resid) & (coord >= xrange[0]) & (coord <= xrange[1]) & (np.abs(resid) < 3.0)
    if np.count_nonzero(m) < 50:
        return 0.0, 0.0, float("nan")
    xc = coord[m]
    yc = resid[m]
    bins = np.linspace(xrange[0], xrange[1], 19)
    bx, by, be = [], [], []
    for i in range(len(bins) - 1):
        inb = (xc >= bins[i]) & (xc < bins[i + 1])
        if np.count_nonzero(inb) < 8:
            continue
        mu, sig, _ = _weighted_core_gauss(yc[inb], np.ones(np.count_nonzero(inb)))
        bx.append(0.5 * (bins[i] + bins[i + 1]))
        by.append(mu)
        be.append(max(sig, 0.02) / math.sqrt(np.count_nonzero(inb)))
    if len(bx) < 4:
        return 0.0, 0.0, float("nan")
    bxa = np.asarray(bx)
    bya = np.asarray(by)
    bea = np.asarray(be)
    w = 1.0 / (bea ** 2)
    sw = np.sum(w)
    mx = np.sum(w * bxa) / sw
    my = np.sum(w * bya) / sw
    cov = np.sum(w * (bxa - mx) * (bya - my))
    varx = np.sum(w * (bxa - mx) ** 2)
    slope = float(cov / varx) if varx > 0 else 0.0
    slope_err = float(1.0 / math.sqrt(varx)) if varx > 0 else float("nan")
    res_post = bya - (my + slope * (bxa - mx))
    max_abs = float(np.max(np.abs(res_post)))
    return slope, slope_err, max_abs


def _fit_power_law_mc(q_centers: np.ndarray, sigs: np.ndarray, counts: np.ndarray, default_floor: float) -> tuple[float, float, float, bool]:
    m = np.isfinite(q_centers) & np.isfinite(sigs) & (q_centers > 1.0) & (sigs > 0.008) & (counts >= 15)
    if np.count_nonzero(m) < 3:
        return 0.0, 0.5, default_floor, False
    qv = q_centers[m]
    sv = sigs[m]
    wv = 1.0 / np.sqrt(counts[m])

    def model(qq: np.ndarray, A: float, a: float, c: float) -> np.ndarray:
        return np.sqrt((A * np.power(qq, -a)) ** 2 + c ** 2)

    try:
        popt, _ = curve_fit(
            model, qv, sv,
            p0=[max(0.2, sv[0] * math.sqrt(qv[0])), 0.7, max(0.015, float(np.min(sv)))],
            sigma=wv,
            bounds=([0.0, 0.2, 0.012], [200.0, 1.5, 0.50]),
            maxfev=3000,
        )
        return float(popt[0]), float(popt[1]), float(popt[2]), True
    except Exception:
        return 0.0, 0.5, float(np.median(sv)), False


def step_fit(args: argparse.Namespace) -> None:
    t0 = time.perf_counter()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(glob.glob(args.mc_scan_glob))
    if not files:
        raise RuntimeError(f"No mc-scan shards found matching {args.mc_scan_glob}")
    print(f"[T2 fit] Reading {len(files)} mc-scan shards with {args.workers} workers...")

    run_summaries: dict[int, dict[str, Any]] = {}
    hists_by_run: dict[int, dict[str, np.ndarray]] = defaultdict(dict)
    hist_edges: np.ndarray | None = None
    rec_chunks: list[dict[str, np.ndarray]] = []

    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as ex:
        for res in ex.map(_read_mc_scan_shard, files, chunksize=4):
            for r, s in res["summary"].items():
                if r not in run_summaries:
                    run_summaries[r] = dict(s)
                else:
                    for k in ("n_total", "n_lt1", "n_clean_muon", "n_kin_sr"):
                        run_summaries[r][k] += s[k]
            for r, hmap in res["hists"].items():
                for hn, (vals, edges) in hmap.items():
                    if hist_edges is None:
                        hist_edges = edges
                    if hn not in hists_by_run[r]:
                        hists_by_run[r][hn] = vals.copy()
                    else:
                        hists_by_run[r][hn] += vals
            if res["recs"] is not None:
                rec_chunks.append(res["recs"])

    recs: dict[str, np.ndarray] = {}
    for k in rec_chunks[0].keys():
        recs[k] = np.concatenate([c[k] for c in rec_chunks], axis=0)
    print(f"[T2 fit] Merged {len(run_summaries)} runs, {len(recs['run'])} clean 1-trk MC muons ({time.perf_counter()-t0:.2f}s)")

    # Concatenate GENIE VetoNu HITS calibration records if available
    vn_hits = {}
    if Path(args.vn_hits_file).exists():
        with uproot.open(args.vn_hits_file) as vf:
            vn_hits = vf["vn_hits"].arrays(library="np")
        print(f"[T2 fit] Loaded {len(vn_hits['run'])} isolated GENIE VetoNu HITS calibration hits from {args.vn_hits_file}")

    centers = 0.5 * (hist_edges[:-1] + hist_edges[1:])

    # 1. Per-run t_mc_ref from h_loc
    run_tref: dict[int, dict[str, float]] = {}
    fam_loc_hists: dict[str, dict[str, np.ndarray]] = defaultdict(dict)
    fam_rec_indices: dict[str, list[np.ndarray]] = defaultdict(list)

    runs_arr = recs["run"]
    for r in sorted(run_summaries.keys()):
        fam = family_for_mc_run(r)
        fam_rec_indices[fam].append(np.where(runs_arr == r)[0])
        run_tref[r] = {}
        for c_idx, cname in enumerate(CHANNELS):
            hname = f"h_loc_{cname}"
            if hname in hists_by_run[r]:
                vals = hists_by_run[r][hname]
                if hname not in fam_loc_hists[fam]:
                    fam_loc_hists[fam][hname] = vals.copy()
                else:
                    fam_loc_hists[fam][hname] += vals
                mu, _, tot = _fit_peak_hist1d(centers, vals, min_entries=20)
                if mu is not None:
                    run_tref[r][cname] = mu
        for p in range(4):
            hn = f"h_loc_Timing{p}"
            if hn in hists_by_run[r]:
                vals = hists_by_run[r][hn]
                if hn not in fam_loc_hists[fam]:
                    fam_loc_hists[fam][hn] = vals.copy()
                else:
                    fam_loc_hists[fam][hn] += vals

    # Inject exact GENIE VetoNu0/1 HITS t_mc_ref, time-walk, and sigma_MC(Q)
    vn_hits_tref: dict[str, dict[str, float]] = defaultdict(dict)
    vn_hits_tw: dict[int, tuple[list[float], list[float], dict[str, float]]] = {}
    if vn_hits:
        for pl, cname in [(0, "VetoNu0"), (1, "VetoNu1")]:
            m_pl = (vn_hits["plate"] == pl) & np.isfinite(vn_hits["t_ref_est"]) & (vn_hits["raw_charge"] > 8.0)
            m_mip = m_pl & (vn_hits["raw_charge"] > MIP_THRESHOLDS[cname])
            mu_all, sig_all, _ = _weighted_core_gauss(vn_hits["t_ref_est"][m_mip], np.ones(np.count_nonzero(m_mip)))
            # Measure per-family GENIE VetoNu t_mc_ref
            for fam in ("genie_2022_2023", "genie_2024_noCaloNu", "genie_2024_CaloNu"):
                rfams = np.array([family_for_mc_run(int(rr)) == fam for rr in vn_hits["run"]])
                mf = m_mip & rfams
                if np.count_nonzero(mf) >= 20:
                    muf, _, _ = _weighted_core_gauss(vn_hits["t_ref_est"][mf], np.ones(np.count_nonzero(mf)))
                    vn_hits_tref[fam][cname] = muf
                else:
                    vn_hits_tref[fam][cname] = mu_all

            # Low-charge time-walk & sigma_MC(Q) bins in GENIE VetoNuHits (pure electronics, zero TOF spread!)
            q_edges = [10.0, 15.0, 22.0, 32.0, 45.0, 65.0, 95.0, 140.0, 250.0, 800.0]
            tw_qs, tw_dts = [], []
            pl_qs, pl_sigs, pl_cnts = [], [], []
            for bi in range(len(q_edges) - 1):
                mb = m_pl & (vn_hits["raw_charge"] >= q_edges[bi]) & (vn_hits["raw_charge"] < q_edges[bi + 1])
                cnt = int(np.count_nonzero(mb))
                if cnt < 10:
                    continue
                res_b = vn_hits["t_ref_est"][mb] - mu_all
                q_med = float(np.median(vn_hits["raw_charge"][mb]))
                dt_med = float(np.median(res_b))
                sig_mad = float(1.4826 * np.median(np.abs(res_b - dt_med)))
                tw_qs.append(round(q_med, 2))
                tw_dts.append(round(dt_med, 5))
                pl_qs.append(q_med)
                pl_sigs.append(max(0.015, sig_mad))
                pl_cnts.append(cnt)
            aa, pa, fc, has_pl = _fit_power_law_mc(np.asarray(pl_qs), np.asarray(pl_sigs), np.asarray(pl_cnts), 0.028)
            vn_hits_tw[pl] = (tw_qs, tw_dts, {"amp_a": aa, "power_a": pa, "floor_c": fc, "has_pl": has_pl, "mu_mip": mu_all, "sig_mip": sig_all})
            print(f"[T2 fit] GENIE HITS {cname}: t_mc_ref={mu_all:.5f} ns, sig_MIP={sig_all:.4f} ns, power-law A={aa:.3f}, a={pa:.3f}, c={fc:.4f} ns (ok={has_pl})")

    # 2. Fit slopes, post-slope flatness, time-walk & sigma_MC per MC family
    slope_rows: list[list[Any]] = []
    families_out: dict[str, Any] = {}
    all_families = ["fluka_mc22_s0010", "fluka_mc22_s0012", "fluka_mc24", "genie_2022_2023", "genie_2024_noCaloNu", "genie_2024_CaloNu"]

    # Track arrays for family-level plots
    plot_slope_data: dict[str, Any] = {}
    plot_sigma_q_data: dict[str, Any] = {}

    for fam in all_families:
        idxs = np.concatenate(fam_rec_indices[fam]) if fam_rec_indices[fam] else np.array([], dtype=np.int64)
        fam_tref: dict[str, float] = {}
        for cname in CHANNELS:
            hn = f"h_loc_{cname}"
            if hn in fam_loc_hists[fam]:
                mu, _, _ = _fit_peak_hist1d(centers, fam_loc_hists[fam][hn], min_entries=20)
                if mu is not None:
                    fam_tref[cname] = mu
            if fam.startswith("genie_") and cname in vn_hits_tref.get(fam, {}):
                fam_tref[cname] = vn_hits_tref[fam][cname]

        fam_ch_cfg: dict[str, Any] = {}
        if len(idxs) > 0:
            loc = recs["loc"][idxs]
            q_raw = recs["q_raw"][idxs]
            good_st = recs["good_st"][idxs] == 1
            trk_x = recs["trk_x"][idxs]
            trk_y = recs["trk_y"][idxs]
            tpmt_loc = recs["tpmt_loc"][idxs]
            tpmt_q = recs["tpmt_q"][idxs]
            tpmt_good = recs["tpmt_good"][idxs] == 1

            # Downstream clean MIP reference per event in mc_muons (Preshower0/1 slope-removed + Veto10/20/21 + Timing01/23)
            # First fit initial linear slopes relative to Veto20 (zero slope!)
            v20_ref = fam_tref.get("Veto20", fam_tref.get("Veto10"))
            v20_ok = good_st[:, 4] & (q_raw[:, 4] > MIP_THRESHOLDS["Veto20"]) & (loc[:, 4] > 100.0) & np.isfinite(trk_x[:, 2])
            t_anchor_ev = np.where(v20_ok, loc[:, 4] - v20_ref, np.nan) if v20_ref is not None else np.full(len(idxs), np.nan)

            # Audit single-PMT Timing0..3 slopes in representative high-stat families
            for p in range(4):
                hn = f"h_loc_Timing{p}"
                pmu, _, _ = _fit_peak_hist1d(centers, fam_loc_hists[fam].get(hn, np.zeros_like(centers)), 20)
                if pmu is not None and v20_ref is not None:
                    pok = tpmt_good[:, p] & (tpmt_q[:, p] > 20.0) & (tpmt_loc[:, p] > 100.0) & np.isfinite(t_anchor_ev) & (np.abs(trk_x[:, 3]) < 120.0)
                    if p < 2:
                        pok &= (trk_y[:, 3] < -5.0)
                    else:
                        pok &= (trk_y[:, 3] > 5.0)
                    res_p = (tpmt_loc[:, p] - pmu) - t_anchor_ev
                    sx_p, sx_pe, mx_p = _fit_linear_slope(trk_x[pok, 3], res_p[pok])
                    sy_p, sy_pe, my_p = _fit_linear_slope(trk_y[pok, 3], res_p[pok])
                    slope_rows.append([fam, f"Timing{p}", int(np.count_nonzero(pok)), round(pmu, 5),
                                       round(sx_p, 6), round(sx_pe, 6), round(sy_p, 6), round(mx_p, 4)])
                    if fam in ("fluka_mc24", "genie_2024_noCaloNu") and p in (0, 1):
                        plot_slope_data[f"{fam}_Timing{p}"] = (trk_x[pok, 3], res_p[pok], sx_p, sx_pe)

            for c_idx, cname in enumerate(CHANNELS):
                if cname not in fam_tref:
                    continue
                tref = fam_tref[cname]
                p_idx = CHANNEL_PLANE_IDX[c_idx]
                ok_c = good_st[:, c_idx] & (q_raw[:, c_idx] > MIP_THRESHOLDS[cname]) & (loc[:, c_idx] > 100.0)
                ok_c &= np.isfinite(trk_x[:, p_idx]) & np.isfinite(trk_y[:, p_idx]) & (np.abs(trk_x[:, p_idx]) < 120.0) & (np.abs(trk_y[:, p_idx]) < 120.0)
                if cname == "Timing01":
                    ok_c &= (trk_y[:, p_idx] < -5.0)
                elif cname == "Timing23":
                    ok_c &= (trk_y[:, p_idx] > 5.0)

                # Reference excluding self
                ref_ok = np.isfinite(t_anchor_ev)
                if cname == "Veto20":
                    v10_ref = fam_tref.get("Veto10")
                    if v10_ref is not None:
                        v10_ok = good_st[:, 2] & (q_raw[:, 2] > MIP_THRESHOLDS["Veto10"]) & (loc[:, 2] > 100.0)
                        t_ref_use = np.where(v10_ok, loc[:, 2] - v10_ref, np.nan)
                        ref_ok = v10_ok
                    else:
                        t_ref_use = t_anchor_ev
                else:
                    t_ref_use = t_anchor_ev

                m_slope = ok_c & ref_ok
                if fam.startswith("genie_") and cname in ("VetoNu0", "VetoNu1"):
                    # GenIE has no forward muon through VetoNu; slopes hardcoded 0 per WaveformDigitisationTool
                    sx, sx_e, sy, sy_e, max_flat = 0.0, 0.0, 0.0, 0.0, 0.0
                else:
                    res = (loc[:, c_idx] - tref) - t_ref_use
                    sx, sx_e, mflat_x = _fit_linear_slope(trk_x[m_slope, p_idx], res[m_slope])
                    sy, sy_e, mflat_y = _fit_linear_slope(trk_y[m_slope, p_idx], res[m_slope] - sx * trk_x[m_slope, p_idx])
                    max_flat = max(mflat_x, mflat_y) if (np.isfinite(mflat_x) and np.isfinite(mflat_y)) else 0.0
                    # Zero tiny statistical slopes on VetoNu/Veto where WaveformDigitisationTool sets dtime=0 (<2 sigma or <3e-4)
                    if abs(sx) < 0.0005 and (cname.startswith("Veto") or cname.startswith("Preshower") or cname.startswith("Timing")):
                        sx = 0.0 if cname.startswith("Timing") is False else sx
                    if cname in ("VetoNu0", "VetoNu1", "Veto10", "Veto11", "Veto20", "Veto21"):
                        # Keep audit measurement in slope_rows, only apply physically calibrated slope if >0.0005 ns/mm
                        pass
                    if fam == "fluka_mc24" and cname in ("Preshower0", "Preshower1", "VetoNu0"):
                        plot_slope_data[f"{fam}_{cname}_x"] = (trk_x[m_slope, p_idx], res[m_slope], sx, sx_e)
                        plot_slope_data[f"{fam}_{cname}_y"] = (trk_y[m_slope, p_idx], res[m_slope], sy, sy_e)

                slope_rows.append([fam, cname, int(np.count_nonzero(m_slope)), round(tref, 5),
                                   round(sx, 6), round(sx_e, 6), round(sy, 6), round(max_flat, 4)])

                # Use theoretical/measured physical slope in mc_timing_calib (exact Calypso slopes on Preshower, 0 on Veto/VetoNu/Timing-pair if <5e-4)
                use_sx = sx if abs(sx) >= 5.0e-4 else 0.0
                use_sy = sy if abs(sy) >= 5.0e-4 else 0.0

                # Intrinsic sigma_MC(Q) & time-walk
                tw_q: list[float] = []
                tw_dt: list[float] = []
                if cname in ("VetoNu0", "VetoNu1") and vn_hits_tw:
                    pl = 0 if cname == "VetoNu0" else 1
                    tw_q, tw_dt, pl_info = vn_hits_tw[pl]
                    aa, pa, fc, has_pl = pl_info["amp_a"], pl_info["power_a"], pl_info["floor_c"], pl_info["has_pl"]
                else:
                    # Measure pair difference / vs reference minus reference variance
                    is_ps = cname.startswith("Preshower")
                    q_edges = [1.5, 3.0, 5.0, 8.0, 15.0] if is_ps else [20.0, 45.0, 70.0, 95.0, 130.0, 200.0, 400.0]
                    # Estimate sigma_ref baseline from Veto10 - Veto20 difference / sqrt(2)
                    v10_ok = good_st[:, 2] & (q_raw[:, 2] > MIP_THRESHOLDS["Veto10"]) & (loc[:, 2] > 100.0)
                    v20_ok2 = good_st[:, 4] & (q_raw[:, 4] > MIP_THRESHOLDS["Veto20"]) & (loc[:, 4] > 100.0)
                    both_v = v10_ok & v20_ok2
                    sig_ref_est = 0.025
                    if "Veto10" in fam_tref and "Veto20" in fam_tref and np.count_nonzero(both_v) >= 50:
                        dv = (loc[both_v, 2] - fam_tref["Veto10"]) - (loc[both_v, 4] - fam_tref["Veto20"])
                        _, sig_pair, _ = _weighted_core_gauss(dv, np.ones(len(dv)))
                        sig_ref_est = max(0.015, sig_pair / math.sqrt(2.0))

                    ok_allq = good_st[:, c_idx] & (loc[:, c_idx] > 100.0) & ref_ok & np.isfinite(trk_x[:, p_idx]) & (np.abs(trk_x[:, p_idx]) < 120.0) & (np.abs(trk_y[:, p_idx]) < 120.0)
                    res_q = (loc[:, c_idx] - tref - use_sx * trk_x[:, p_idx] - use_sy * trk_y[:, p_idx]) - t_ref_use
                    ok_allq &= np.abs(res_q) < 1.0
                    pl_qs, pl_sigs, pl_cnts = [], [], []
                    for bi in range(len(q_edges) - 1):
                        mb = ok_allq & (q_raw[:, c_idx] >= q_edges[bi]) & (q_raw[:, c_idx] < q_edges[bi + 1])
                        cnt = int(np.count_nonzero(mb))
                        if cnt < 20:
                            continue
                        rq = res_q[mb]
                        qm = float(np.median(q_raw[mb, c_idx]))
                        dm, sm_tot, _ = _weighted_core_gauss(rq, np.ones(len(rq)))
                        sm_int = math.sqrt(max(0.015 ** 2, sm_tot ** 2 - sig_ref_est ** 2))
                        tw_q.append(round(qm, 2))
                        tw_dt.append(round(dm, 5))
                        pl_qs.append(qm)
                        pl_sigs.append(sm_int)
                        pl_cnts.append(cnt)
                    aa, pa, fc, has_pl = _fit_power_law_mc(np.asarray(pl_qs), np.asarray(pl_sigs), np.asarray(pl_cnts), max(0.020, sig_ref_est))
                    if fam == "fluka_mc24" and cname in ("Veto20", "Preshower0"):
                        plot_sigma_q_data[f"{fam}_{cname}"] = (pl_qs, pl_sigs, aa, pa, fc)

                fam_ch_cfg[cname] = {
                    "t_mc_ref": round(fam_tref[cname], 5),
                    "slope_x_ns_per_mm": round(use_sx, 6),
                    "slope_y_ns_per_mm": round(use_sy, 6),
                    "amp_a": round(aa, 4),
                    "power_a": round(pa, 4),
                    "floor_c": round(fc, 4),
                    "has_power_law": bool(has_pl),
                    "time_walk_q": tw_q,
                    "time_walk_dt": tw_dt,
                }
        families_out[fam] = {"channels": fam_ch_cfg}

    # For GENIE MC, downstream channels share exact Calypso mc24 3-ADC digitization electronics with fluka_mc24;
    # inherit pure single-muon fluka_mc24 noise curves & time-walk so GENIE neutrino showers do not inflate sigma_MC(Q).
    if "fluka_mc24" in families_out:
        fluka24_chs = families_out["fluka_mc24"]["channels"]
        for fam in ("genie_2022_2023", "genie_2024_noCaloNu", "genie_2024_CaloNu"):
            for cname in CHANNELS:
                if cname.startswith("VetoNu") or cname not in fluka24_chs:
                    continue
                if cname in families_out[fam]["channels"]:
                    for key_copy in ("amp_a", "power_a", "floor_c", "has_power_law", "time_walk_q", "time_walk_dt"):
                        families_out[fam]["channels"][cname][key_copy] = fluka24_chs[cname][key_copy]

    # Ensure every GENIE/FLUKA VetoNu0/1 has calibrated entries
    for fam in ("genie_2022_2023", "genie_2024_noCaloNu", "genie_2024_CaloNu"):
        for pl, cname in [(0, "VetoNu0"), (1, "VetoNu1")]:
            if cname not in families_out[fam]["channels"] and vn_hits_tw:
                tw_q, tw_dt, info = vn_hits_tw[pl]
                tref = vn_hits_tref.get(fam, {}).get(cname, info["mu_mip"])
                families_out[fam]["channels"][cname] = {
                    "t_mc_ref": round(tref, 5),
                    "slope_x_ns_per_mm": 0.0,
                    "slope_y_ns_per_mm": 0.0,
                    "amp_a": round(info["amp_a"], 4),
                    "power_a": round(info["power_a"], 4),
                    "floor_c": round(info["floor_c"], 4),
                    "has_power_law": bool(info["has_pl"]),
                    "time_walk_q": tw_q,
                    "time_walk_dt": tw_dt,
                }

    # Build per-run override dictionary
    runs_out: dict[str, Any] = {}
    for r in sorted(run_summaries.keys()):
        fam = family_for_mc_run(r)
        chs = {cn: {"t_mc_ref": round(val, 5)} for cn, val in sorted(run_tref[r].items())}
        if fam.startswith("genie_"):
            for cname in ("VetoNu0", "VetoNu1"):
                if cname in families_out[fam]["channels"]:
                    chs[cname] = {"t_mc_ref": families_out[fam]["channels"][cname]["t_mc_ref"]}
        runs_out[str(r)] = {"family": fam, "channels": chs}

    mc_calib = {
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "notes": "MC localtime references, built-in Timing/Preshower linear slopes, low-Q time-walk, and 3-ADC intrinsic width for deterministic Stage T2 smearing.",
        "families": families_out,
        "runs": runs_out,
    }
    mc_calib_path = CALIB_DIR / "mc_timing_calib.json"
    mc_calib_path.write_text(json.dumps(mc_calib, separators=(",", ":")))
    print(f"[T2 fit] Wrote {mc_calib_path} ({mc_calib_path.stat().st_size / 1024.0:.1f} KB)")

    # Write TSV tables
    with open(OUT_DIR / "mc_slope_flatness.tsv", "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["family", "channel", "n_events", "t_mc_ref_ns", "slope_x_ns_per_mm", "slope_x_err", "slope_y_ns_per_mm", "max_abs_flatness_ns"])
        w.writerows(slope_rows)

    with open(OUT_DIR / "mc_timing_summary.tsv", "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["run", "family", "n_total", "n_lt1", "n_clean_muon", "n_kin_sr", "tref_VetoNu0", "tref_Veto10", "tref_Veto20", "tref_Timing01", "tref_Preshower0"])
        for r in sorted(run_summaries.keys()):
            s = run_summaries[r]
            tr = run_tref[r]
            w.writerow([
                r, family_for_mc_run(r), s["n_total"], s["n_lt1"], s["n_clean_muon"], s["n_kin_sr"],
                round(tr.get("VetoNu0", float("nan")), 4),
                round(tr.get("Veto10", float("nan")), 4),
                round(tr.get("Veto20", float("nan")), 4),
                round(tr.get("Timing01", float("nan")), 4),
                round(tr.get("Preshower0", float("nan")), 4),
            ])

    # Plot Fig 1: Built-in linear slopes & flatness after subtraction
    fig, axes = plt.subplots(2, 2, figsize=(13, 10))
    panels = [
        ("fluka_mc24_Timing0", "FLUKA mc24 Timing0 PMT (Calypso +1/130 ns/mm)", "Track X at Timing [mm]", +1.0 / 130.0),
        ("fluka_mc24_Timing1", "FLUKA mc24 Timing1 PMT (Calypso -1/130 ns/mm)", "Track X at Timing [mm]", -1.0 / 130.0),
        ("fluka_mc24_Preshower0_y", "FLUKA mc24 Preshower0 (Calypso -1/230 ns/mm)", "Track Y at PS1 [mm]", -1.0 / 230.0),
        ("fluka_mc24_VetoNu0_x", "FLUKA mc24 VetoNu0 (Calypso dtime = 0)", "Track X at VetoNu [mm]", 0.0),
    ]
    for ax, (key, title, xlab, theory) in zip(axes.ravel(), panels):
        if key in plot_slope_data:
            xv, yv, sl, sle = plot_slope_data[key]
            bins = np.linspace(-110.0, 110.0, 19)
            bx, by, be = [], [], []
            for i in range(len(bins) - 1):
                inb = (xv >= bins[i]) & (xv < bins[i + 1]) & (np.abs(yv) < 2.5)
                if np.count_nonzero(inb) < 5:
                    continue
                mu, sg, _ = _weighted_core_gauss(yv[inb], np.ones(np.count_nonzero(inb)))
                bx.append(0.5 * (bins[i] + bins[i + 1]))
                by.append(mu)
                be.append(sg / math.sqrt(np.count_nonzero(inb)))
            bxa, bya, bea = np.asarray(bx), np.asarray(by), np.asarray(be)
            intercept = float(np.mean(bya) - sl * np.mean(bxa))
            post_flat = (bya - intercept) - sl * bxa
            ax.errorbar(bxa, bya, yerr=bea, fmt="o", capsize=3, label=f"Raw slope = {sl:+.6f} ns/mm")
            ax.plot(bxa, intercept + sl * bxa, "-", label="Linear fit")
            ax.plot(bxa, post_flat, "s--", alpha=0.85, label=f"Post-sub flat (|max|={np.max(np.abs(post_flat)):.3f} ns)")
            ax.axhline(0.0, color="gray", ls=":")
            if abs(theory) > 0:
                ax.set_title(f"{title}\nTheory {theory:+.6f} vs Meas {sl:+.6f} ns/mm", fontsize=10)
            else:
                ax.set_title(f"{title}\nMeas {sl:+.6f} ns/mm", fontsize=10)
        ax.set_xlabel(xlab)
        ax.set_ylabel("Residual vs Veto20 [ns]")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.25)
    fig.suptitle("Stage T2: MC Built-in Spatial Timing Slopes & Post-Subtraction Transverse Flatness", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(OUT_DIR / "fig1_mc_slopes_flatness.png", dpi=150)
    plt.close(fig)

    # Plot Fig 2: Intrinsic sigma_MC(Q) & low-Q MC time-walk
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
    ax0, ax1 = axes
    if vn_hits_tw:
        for pl, cname, col in [(0, "VetoNu0", "tab:blue"), (1, "VetoNu1", "tab:orange")]:
            twq, twdt, info = vn_hits_tw[pl]
            ax0.plot(twq, twdt, "o-", color=col, label=f"GENIE HITS {cname} (ref={info['mu_mip']:.3f} ns)")
            qq = np.linspace(12.0, 500.0, 200)
            sig_mc = np.sqrt((info["amp_a"] * np.power(qq, -info["power_a"])) ** 2 + info["floor_c"] ** 2)
            ax1.plot(qq, sig_mc, "-", color=col, label=f"GENIE {cname}: A={info['amp_a']:.2f}, a={info['power_a']:.2f}, c={info['floor_c']:.3f}")
    for key, lab, col in [("fluka_mc24_Veto20", "FLUKA mc24 Veto20", "tab:green"), ("fluka_mc24_Preshower0", "FLUKA mc24 Preshower0", "tab:red")]:
        if key in plot_sigma_q_data:
            pq, ps, aa, pa, fc = plot_sigma_q_data[key]
            ax1.plot(pq, ps, "o--", color=col, label=f"{lab}: floor={fc:.3f} ns")
    ax0.axhline(0.0, color="gray", ls=":")
    ax0.set_xscale("log")
    ax0.set_xlabel("Raw Charge Q [pC]")
    ax0.set_ylabel("MC Low-Q Time-Walk Offset [ns]")
    ax0.set_title("GENIE VetoNu0/1 Intrinsic Time-Walk vs HITS")
    ax0.legend(fontsize=8)
    ax0.grid(alpha=0.25)
    ax1.set_xscale("log")
    ax1.set_xlabel("Raw Charge Q [pC]")
    ax1.set_ylabel("Intrinsic MC Time Resolution sigma_MC(Q) [ns]")
    ax1.set_title("MC 3-ADC Electronics Resolution Curves (pre-smearing)")
    ax1.set_ylim(0.0, 0.25)
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.25)
    fig.suptitle("Stage T2: Intrinsic MC Time-Walk and 3-ADC Electronic Timing Width", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(OUT_DIR / "fig2_mc_intrinsic_sigma_timewalk.png", dpi=150)
    plt.close(fig)
    print(f"[T2 fit] Finished in {time.perf_counter()-t0:.2f}s")


def step_closure(args: argparse.Namespace) -> None:
    t0 = time.perf_counter()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    def load_merged(pattern: str) -> tuple[dict[int, dict[str, int]], dict[str, dict[str, tuple[np.ndarray, np.ndarray]]]]:
        fpaths = sorted(glob.glob(pattern))
        if not fpaths and pattern.startswith("ntuples/"):
            import subprocess
            rel_dir = str(Path(pattern).parent)
            eos_dir = f"/eos/user/x/xcheng/FASER/nu_muAnalysis/{rel_dir}"
            res_ls = subprocess.run(["xrdfs", "eoshome-x.cern.ch", "ls", eos_dir], capture_output=True, text=True)
            if res_ls.returncode == 0:
                fpaths = [f"root://eoshome-x.cern.ch/{line.strip()}" for line in res_ls.stdout.splitlines() if line.strip().endswith(".root")]
                fpaths.sort()
        if not fpaths:
            raise RuntimeError(f"No shards found for {pattern}")
        runs_m: dict[int, dict[str, int]] = {}
        hists_m: dict[str, dict[str, tuple[np.ndarray, np.ndarray]]] = defaultdict(dict)
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as ex:
            for res in ex.map(_read_closure_shard, fpaths, chunksize=4):
                for r, rd in res["runs"].items():
                    if r not in runs_m:
                        runs_m[r] = dict(rd)
                    else:
                        for k in ("n_total", "n_grl_fail", "n_non_colliding", "n_blinded",
                                  "n_clean_1trk", "n_kin_sr", "n_kin_sr_valid_t0down", "n_kin_sr_valid_veto2only"):
                            runs_m[r][k] += rd[k]
                for per, hm in res["hists"].items():
                    for hn, (vals, edges) in hm.items():
                        if hn not in hists_m[per]:
                            hists_m[per][hn] = (vals.copy(), edges)
                        else:
                            v0, e0 = hists_m[per][hn]
                            hists_m[per][hn] = (v0 + vals, e0)
        return runs_m, hists_m

    data_runs, data_hists = load_merged(args.data_closure_glob)
    fluka_runs, fluka_hists = load_merged(args.fluka_closure_glob)

    def sum_hists(hm: dict[str, dict[str, tuple[np.ndarray, np.ndarray]]], periods: list[str], hname: str) -> tuple[np.ndarray, np.ndarray] | None:
        acc = None
        edges_ref = None
        for p in periods:
            if p in hm and hname in hm[p]:
                v, e = hm[p][hname]
                edges_ref = e
                acc = v.copy() if acc is None else (acc + v)
        return (acc, edges_ref) if acc is not None else None

    def sum_fluka_matched(periods: list[str], hname: str, match_data_weights: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
        """Sum FLUKA period histograms; when match_data_weights is True, reweight each period to match Data's period fraction."""
        if not match_data_weights:
            hf = sum_hists(fluka_hists, periods, hname)
            return (hf[0], hf[1], hf[0]) if hf is not None else None
        per_d = {p: float(np.sum(data_hists[p][hname][0])) for p in periods if p in data_hists and hname in data_hists[p]}
        per_f = {p: float(np.sum(fluka_hists[p][hname][0])) for p in periods if p in fluka_hists and hname in fluka_hists[p]}
        common = [p for p in periods if per_d.get(p, 0.0) > 0.0 and per_f.get(p, 0.0) > 0.0]
        if not common:
            hf = sum_hists(fluka_hists, periods, hname)
            return (hf[0], hf[1], hf[0]) if hf is not None else None
        tot_d = sum(per_d[p] for p in common)
        tot_f = sum(per_f[p] for p in common)
        acc = None
        sumw2 = None
        edges_ref = None
        for p in common:
            v, e = fluka_hists[p][hname]
            edges_ref = e
            w = (per_d[p] / per_f[p]) * (tot_f / tot_d)
            acc = (v * w) if acc is None else (acc + v * w)
            sumw2 = (v * (w * w)) if sumw2 is None else (sumw2 + v * (w * w))
        return (acc, edges_ref, sumw2) if acc is not None else None

    era_groups = [
        ("Run3_2022_2023", ["2022", "2023"], True),
        ("Run3_2024", ["2024_preCaloNu", "2024_CaloNu", "2024_postCaloNu"], True),
        ("Run3_2022_2024_all", ["2022", "2023", "2024_preCaloNu", "2024_CaloNu", "2024_postCaloNu"], True),
    ]

    closure_rows: list[list[Any]] = []
    sf_rows: list[list[Any]] = []
    max_width_rel_diff = 0.0

    for label, p_list, match_wt in era_groups:
        for ch_obs, h_prompt, h_geom in [
            ("VetoNu0_dt", "h_vn0_dt_prompt", "h_vn0_dt_geom"),
            ("VetoNu1_dt", "h_vn1_dt_prompt", "h_vn1_dt_geom"),
        ]:
            hd = sum_hists(data_hists, p_list, h_prompt)
            hf = sum_fluka_matched(p_list, h_prompt, match_wt)
            if hd and hf:
                mu_d, sg_d, err_d, nd = _fit_trunc_gauss_hist(hd[1], hd[0], -1.45, 1.45)
                mu_f, sg_f, err_f, nf = _fit_trunc_gauss_hist(hf[1], hf[0], -1.45, 1.45, hf[2])
                rdiff = (sg_f - sg_d) / sg_d if sg_d > 0 else float("nan")
                if label == "Run3_2022_2024_all" or ch_obs in ("VetoNu0_dt", "VetoNu1_dt"):
                    if np.isfinite(rdiff):
                        max_width_rel_diff = max(max_width_rel_diff, abs(rdiff))
                closure_rows.append([label, ch_obs, "CR_Prompt_trunc1p45", int(round(nd)), int(round(nf)),
                                     round(mu_d, 4), round(sg_d, 4), round(mu_f, 4), round(sg_f, 4), round(rdiff * 100.0, 2)])

            hdg = sum_hists(data_hists, p_list, h_geom)
            hfg = sum_fluka_matched(p_list, h_geom, match_wt)
            if hdg and hfg:
                mu_d, sg_d, err_d, nd = _fit_trunc_gauss_hist(hdg[1], hdg[0], -3.0, 3.0)
                mu_f, sg_f, err_f, nf = _fit_trunc_gauss_hist(hfg[1], hfg[0], -3.0, 3.0, hfg[2])
                rdiff = (sg_f - sg_d) / sg_d if sg_d > 0 else float("nan")
                closure_rows.append([label, ch_obs, "CR_Geom_unblinded", int(round(nd)), int(round(nf)),
                                     round(mu_d, 4), round(sg_d, 4), round(mu_f, 4), round(sg_f, 4), round(rdiff * 100.0, 2)])

        # Also compare t0_down
        htd = sum_hists(data_hists, p_list, "h_t0_down_prompt")
        htf = sum_fluka_matched(p_list, "h_t0_down_prompt", match_wt)
        if htd and htf:
            mu_d, sg_d, _, nd = _fit_trunc_gauss_hist(htd[1], htd[0], -2.0, 2.0)
            mu_f, sg_f, _, nf = _fit_trunc_gauss_hist(htf[1], htf[0], -2.0, 2.0, htf[2])
            rdiff = (sg_f - sg_d) / sg_d if sg_d > 0 else float("nan")
            closure_rows.append([label, "t0_down", "CR_Prompt", int(round(nd)), int(round(nf)),
                                 round(mu_d, 4), round(sg_d, 4), round(mu_f, 4), round(sg_f, 4), round(rdiff * 100.0, 2)])

        # SF_chi2_down extraction at thresholds [2.0, 3.0, 4.0, 5.0] across regions
        for region_name, hname in [("CR_Prompt", "h_chi2_ndof_prompt"), ("CR_All1Trk", "h_chi2_ndof_all"), ("CR_ShowerSB", "h_chi2_ndof_shower_sb")]:
            cd = sum_hists(data_hists, p_list, hname)
            cf = sum_fluka_matched(p_list, hname, match_wt)
            if not cd or not cf:
                continue
            vd, ed = cd
            vf, ef, wf2 = cf
            cens = 0.5 * (ed[:-1] + ed[1:])
            tot_d = float(np.sum(vd))
            tot_f = float(np.sum(vf))
            n_eff_f = (tot_f * tot_f) / max(float(np.sum(wf2)), 1.0)
            if tot_d < 50 or tot_f < 50:
                continue
            for thr in (2.0, 2.5, 3.0, 4.0, 5.0):
                pass_d = float(np.sum(vd[cens < thr]))
                pass_f = float(np.sum(vf[cens < thr]))
                eff_d = pass_d / tot_d
                eff_f = pass_f / tot_f
                sf = eff_d / eff_f if eff_f > 0 else float("nan")
                err_d = math.sqrt(max(1e-12, eff_d * (1.0 - eff_d) / tot_d))
                err_f = math.sqrt(max(1e-12, eff_f * (1.0 - eff_f) / max(n_eff_f, 1.0)))
                sf_err = sf * math.hypot(err_d / max(eff_d, 1e-9), err_f / max(eff_f, 1e-9)) if np.isfinite(sf) else float("nan")
                sf_rows.append([label, region_name, thr, int(round(tot_d)), int(round(tot_f)),
                                round(eff_d, 5), round(eff_f, 5), round(sf, 5), round(sf_err, 5)])

    with open(OUT_DIR / "t2_data_vs_fluka_closure.tsv", "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["era", "observable", "region", "n_data", "n_fluka", "mu_data_ns", "sigma_data_ns", "mu_fluka_ns", "sigma_fluka_ns", "rel_width_diff_pct"])
        w.writerows(closure_rows)

    with open(OUT_DIR / "t2_chi2_sf_summary.tsv", "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["era", "region", "chi2_ndof_thr", "n_data", "n_fluka", "eff_data", "eff_fluka", "sf_chi2_down", "sf_stat_err"])
        w.writerows(sf_rows)

    # Check Data and GENIE coverage from closure_summary + optional genie coverage JSON
    genie_cov = {}
    if args.genie_cov_json and Path(args.genie_cov_json).exists():
        genie_cov = json.loads(Path(args.genie_cov_json).read_text())

    data_n_kin = sum(v["n_kin_sr"] for v in data_runs.values())
    data_n_t0 = sum(v["n_kin_sr_valid_t0down"] for v in data_runs.values())
    data_n_v2 = sum(v["n_kin_sr_valid_veto2only"] for v in data_runs.values())
    data_n_blinded = sum(v["n_blinded"] for v in data_runs.values())
    fluka_n_kin = sum(v["n_kin_sr"] for v in fluka_runs.values())
    fluka_n_t0 = sum(v["n_kin_sr_valid_t0down"] for v in fluka_runs.values())
    fluka_n_v2 = sum(v["n_kin_sr_valid_veto2only"] for v in fluka_runs.values())

    # Central SF at chi2_down/ndof < 3.0 for Run3_2022_2024_all CR_Prompt + systematic envelope
    sf_3p0 = [r for r in sf_rows if r[0] == "Run3_2022_2024_all" and r[2] == 3.0]
    sf_prompt = next((r for r in sf_3p0 if r[1] == "CR_Prompt"), None)
    sf_shower = next((r for r in sf_3p0 if r[1] == "CR_ShowerSB"), None)
    sf_all = next((r for r in sf_3p0 if r[1] == "CR_All1Trk"), None)

    summary_json = {
        "n_data_runs_evaluated": len(data_runs),
        "n_data_blinded_excluded": int(data_n_blinded),
        "n_fluka_runs_evaluated": len(fluka_runs),
        "max_dt01_width_rel_diff_pct": round(max_width_rel_diff * 100.0, 2),
        "dt01_width_agreement_lt_5pct": bool(max_width_rel_diff < 0.05),
        "data_kin_sr_t0down_cov": round(data_n_t0 / max(1, data_n_kin), 6),
        "data_kin_sr_veto2_cov": round(data_n_v2 / max(1, data_n_kin), 6),
        "fluka_kin_sr_t0down_cov": round(fluka_n_t0 / max(1, fluka_n_kin), 6),
        "fluka_kin_sr_veto2_cov": round(fluka_n_v2 / max(1, fluka_n_kin), 6),
        "sf_chi2_down_3p0_prompt": sf_prompt[7] if sf_prompt else None,
        "sf_chi2_down_3p0_shower_sb": sf_shower[7] if sf_shower else None,
        "sf_chi2_down_3p0_all1trk": sf_all[7] if sf_all else None,
        "genie_nu_mu_cc_coverage": genie_cov,
    }
    (OUT_DIR / "t2_acceptance_summary.json").write_text(json.dumps(summary_json, indent=2))
    print(f"[T2 closure] Summary JSON:\n{json.dumps(summary_json, indent=2)}")

    # Plot Fig 3: Data vs Smeared FLUKA VetoNu0_dt, VetoNu1_dt (CR-Prompt & CR-Geom), t0_down
    fig, axes = plt.subplots(2, 2, figsize=(13, 9.5))
    plot_specs = [
        ("Run3_2022_2024_all", "h_vn0_dt_prompt", "VetoNu0 dt (CR-Prompt |dt|<=1.5 ns)", "dt(VetoNu0) [ns]", (-1.6, 1.6)),
        ("Run3_2022_2024_all", "h_vn1_dt_prompt", "VetoNu1 dt (CR-Prompt |dt|<=1.5 ns)", "dt(VetoNu1) [ns]", (-1.6, 1.6)),
        ("Run3_2022_2024_all", "h_vn0_dt_geom", "VetoNu0 dt (CR-Geom Unblinded)", "dt(VetoNu0) [ns]", (-3.0, 3.0)),
        ("Run3_2022_2024_all", "h_t0_down_prompt", "t0_down Downstream Reference (CR-Prompt)", "t0_down [ns]", (-1.5, 1.5)),
    ]
    all_pers = ["2022", "2023", "2024_preCaloNu", "2024_CaloNu", "2024_postCaloNu"]
    for ax, (_, hn, title, xlab, xlim) in zip(axes.ravel(), plot_specs):
        hd = sum_hists(data_hists, all_pers, hn)
        hf = sum_fluka_matched(all_pers, hn, True)
        if hd and hf:
            vd, ed = hd
            vf, ef, _ = hf
            cd = 0.5 * (ed[:-1] + ed[1:])
            nd = np.maximum(np.sum(vd), 1.0)
            nf = np.maximum(np.sum(vf), 1.0)
            m = (cd >= xlim[0]) & (cd <= xlim[1])
            ax.step(cd[m], vd[m] / nd, where="mid", lw=1.8, label=f"Data CR (N={int(nd):,})")
            ax.step(cd[m], vf[m] / nf, where="mid", lw=1.8, ls="--", label=f"Smeared FLUKA MC (N={int(round(nf)):,})")
        ax.set_title(title, fontsize=10.5)
        ax.set_xlabel(xlab)
        ax.set_ylabel("Normalized Events / Bin")
        ax.legend(fontsize=8.5)
        ax.grid(alpha=0.25)
    fig.suptitle("Stage T2 Closure: Run 3 Data vs Deterministic Position-Charge Smeared FLUKA MC", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(OUT_DIR / "fig3_data_vs_fluka_dt01_closure.png", dpi=150)
    plt.close(fig)

    # Plot Fig 4: chi2_down/ndof distribution & GENIE/FLUKA/Data reference coverage comparison
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13, 5.2))
    hcd = sum_hists(data_hists, all_pers, "h_chi2_ndof_prompt")
    hcf = sum_fluka_matched(all_pers, "h_chi2_ndof_prompt", True)
    if hcd and hcf:
        vd, ed = hcd
        vf, ef, _ = hcf
        cd = 0.5 * (ed[:-1] + ed[1:])
        m = cd <= 6.0
        axL.step(cd[m], vd[m] / max(np.sum(vd), 1.0), where="mid", lw=1.8, label="Data CR-Prompt")
        axL.step(cd[m], vf[m] / max(np.sum(vf), 1.0), where="mid", lw=1.8, ls="--", label="Smeared FLUKA MC")
        axL.axvline(3.0, color="red", ls=":", lw=1.5, label=f"Cut < 3.0 (SF={sf_prompt[7]:.4f})" if sf_prompt else "Cut < 3.0")
    axL.set_xlabel(r"$\chi^2_{\mathrm{down}} / \mathrm{ndof}$")
    axL.set_ylabel("Normalized Events / Bin")
    axL.set_title(r"Downstream $\chi^2_{\mathrm{down}}/\mathrm{ndof}$ Closure & Scale Factor")
    axL.legend(fontsize=8.5)
    axL.grid(alpha=0.25)

    cats = ["Data (mu)", "FLUKA (mu)", "GENIE nu_mu CC\n(2022-23)", "GENIE nu_mu CC\n(2024 noCaloNu)", "GENIE nu_mu CC\n(2024 CaloNu)"]
    v2_vals = [summary_json["data_kin_sr_veto2_cov"] * 100.0, summary_json["fluka_kin_sr_veto2_cov"] * 100.0]
    t0_vals = [summary_json["data_kin_sr_t0down_cov"] * 100.0, summary_json["fluka_kin_sr_t0down_cov"] * 100.0]
    for ek in ("2022_2023", "2024_noCaloNu", "2024_CaloNu"):
        g = genie_cov.get(ek, {})
        v2_vals.append(100.0 * g.get("veto2_non_sat_cov", 0.0))
        t0_vals.append(100.0 * g.get("t0_down_valid_cov", 0.0))
    xs = np.arange(len(cats))
    w = 0.35
    b1 = axR.bar(xs - w / 2, v2_vals, width=w, label="Veto2 Only (saturated excluded)", color="salmon")
    b2 = axR.bar(xs + w / 2, t0_vals, width=w, label="Multi-Station t0_down (H3)", color="steelblue")
    for b in list(b1) + list(b2):
        axR.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.0, f"{b.get_height():.2f}%", ha="center", va="bottom", fontsize=7.5)
    axR.axhline(99.8, color="green", ls="--", lw=1.2, label="T2 Target > 99.8%")
    axR.set_xticks(xs)
    axR.set_xticklabels(cats, fontsize=8.5)
    axR.set_ylabel("Valid Downstream Time Coverage [%]")
    axR.set_ylim(0, 109)
    axR.set_title("Downstream Reference Coverage vs Veto2 Saturation (Hypothesis H3)")
    axR.legend(loc="lower right", fontsize=8)
    axR.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig4_chi2_down_sf_and_coverage.png", dpi=150)
    plt.close(fig)
    print(f"[T2 closure] Finished in {time.perf_counter()-t0:.2f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage T2 MC timing fitter and Data/FLUKA closure evaluator")
    parser.add_argument("--step", choices=["fit", "closure"], required=True)
    parser.add_argument("--mc-scan-glob", default="ntuples/timing_stage213/mc-scan/*.root")
    parser.add_argument("--vn-hits-file", default="ntuples/timing_stage213/vn_hits_calib.root")
    parser.add_argument("--data-closure-glob", default="ntuples/timing_stage213/data-closure/*.root")
    parser.add_argument("--fluka-closure-glob", default="ntuples/timing_stage213/fluka-closure/*.root")
    parser.add_argument("--genie-cov-json", default="ntuples/timing_stage213/genie_coverage_check.json")
    parser.add_argument("--workers", type=int, default=28)
    args = parser.parse_args()
    if args.step == "fit":
        step_fit(args)
    else:
        step_closure(args)


if __name__ == "__main__":
    main()
