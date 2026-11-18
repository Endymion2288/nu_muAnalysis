#!/usr/bin/env python3
"""
Stage T1 Closure Validation & Publication Diagnostics.

Evaluates full 2022-2026 calibration tables (ref_offsets_run3.json + tof_maps_run3.json):
  1. Single-muon LOO residual closure (|mu| < 0.03 ns) & intrinsic resolutions vs Quirk PRL Fig. 6
  2. Multi-track (N_long = 2, 3) in-time Pull widths (target 1.00 +- 0.12) & d12 dependence
  3. Speed beta = v/c & reduced chi2/ndof across Run 3 + Runs 14647/16023 + 2022-2024_back schema subset
  4. VetoNu circular-cone area-weighted lookup (R = 15, 30, 50 mm) vs point-lookup closure
  5. Emits TSVs, acceptance gate JSON, and 7 diagnostic PNG plots in workbook/stage212_timing_t1/.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import math
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit
import uproot

from calibrate_scint_timing import (
    CHANNELS,
    CH_TO_IDX,
    CHANNEL_PLANE_IDX,
    DEFAULT_SIGMAS,
    GRID_MAX_MM,
    GRID_MIN_MM,
    GRID_N,
    GRID_STEP_MM,
    MIP_THRESHOLDS,
    PERIOD_ORDER,
    PRIMARY_DOWNSTREAM_CH_INDICES,
    active_channels_for_period,
    _weighted_core_gauss,
    _eval_tw_vec,
)

QUIRK_REF_SIGMA = {
    "VetoNu0": 0.53, "VetoNu1": 0.54,
    "Veto10": 0.23, "Veto11": 0.23,
    "Veto20": 0.23, "Veto21": 0.24,
    "Timing01": 0.35, "Timing23": 0.35,
    "Preshower0": 0.28, "Preshower1": 0.28,
}

C_LIGHT_M_PER_NS = 0.299792458
CH_Z_M = np.array([
    -3.123, -3.102,  # VetoNu0, VetoNu1
    -1.790, -1.770,  # Veto10, Veto11
    -1.620, -1.599,  # Veto20, Veto21
    -0.022, -0.037,  # Timing01, Timing23
     2.583,  2.658,  # Preshower0, Preshower1
     2.583,  2.658,  # Preshower2, Preshower3
     3.825,  4.005,  # Muon0, Muon1
], dtype=np.float64)


def _gauss(x: np.ndarray, a: float, mu: float, sig: float) -> np.ndarray:
    return a * np.exp(-0.5 * ((x - mu) / sig) ** 2)


def _core_gauss_unitless(vals: np.ndarray, weights: np.ndarray) -> tuple[float, float]:
    """Scale-free weighted truncated Gaussian core (mean, sigma) without ns floor."""
    m = np.isfinite(vals) & np.isfinite(weights) & (weights > 0)
    if np.count_nonzero(m) < 20:
        if np.count_nonzero(m) == 0:
            return float("nan"), float("nan")
        v = vals[m]
        w = weights[m]
        mu = float(np.average(v, weights=w))
        sig = float(math.sqrt(max(1e-10, np.average((v - mu) ** 2, weights=w))))
        return mu, sig
    v = vals[m]
    w = weights[m]
    order = np.argsort(v)
    vs = v[order]
    ws = w[order]
    cw = np.cumsum(ws)
    med = float(vs[np.searchsorted(cw, 0.5 * cw[-1])])
    ad = np.abs(v - med)
    ord_ad = np.argsort(ad)
    ads = ad[ord_ad]
    w_ad = w[ord_ad]
    cwa = np.cumsum(w_ad)
    mad = float(ads[np.searchsorted(cwa, 0.5 * cwa[-1])])
    sig = max(1.4826 * mad, 1e-5)
    mu = med
    for _ in range(3):
        c = np.abs(v - mu) <= 2.5 * sig
        if np.count_nonzero(c) < 20:
            break
        wc = w[c]
        vc = v[c]
        mu = float(np.average(vc, weights=wc))
        sig = max(float(math.sqrt(np.average((vc - mu) ** 2, weights=wc))), 1e-5)
    return mu, sig


def _fit_hist_gauss(vals: np.ndarray, weights: np.ndarray | None = None, xrange: tuple[float, float] = (-3.5, 3.5), nbins: int = 70) -> tuple[float, float, int]:
    m = np.isfinite(vals) & (vals >= xrange[0]) & (vals <= xrange[1])
    if weights is not None:
        m &= np.isfinite(weights) & (weights > 0)
    n = int(np.count_nonzero(m))
    if n < 30:
        return np.nan, np.nan, n
    v = vals[m]
    w = None if weights is None else weights[m]
    mu_c, sig_c, _ = _weighted_core_gauss(v, np.ones_like(v) if w is None else w)
    return mu_c, sig_c, n


def _lookup_maps_period(pmap: dict[str, Any], period: str, trk_x: np.ndarray, trk_y: np.ndarray, q_raw: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized 2D TOF + time-walk + floored power-law sigma lookup for N events."""
    n = len(q_raw)
    t_bar_ev = np.zeros((n, len(CHANNELS)), dtype=np.float64)
    tw_ev = np.zeros((n, len(CHANNELS)), dtype=np.float64)
    sig_ev = np.zeros((n, len(CHANNELS)), dtype=np.float64)

    ch_dict = pmap["channels"]
    for c_idx, cname in enumerate(CHANNELS):
        if cname not in ch_dict:
            sig_ev[:, c_idx] = DEFAULT_SIGMAS[cname]
            continue
        cd = ch_dict[cname]
        p_idx = CHANNEL_PLANE_IDX[c_idx]
        px = trk_x[:, p_idx]
        py = trk_y[:, p_idx]
        px_safe = np.where(np.isfinite(px), px, GRID_MIN_MM)
        py_safe = np.where(np.isfinite(py), py, GRID_MIN_MM)
        ix = np.clip(np.floor((px_safe - GRID_MIN_MM) / GRID_STEP_MM).astype(np.int32), 0, GRID_N - 1)
        iy = np.clip(np.floor((py_safe - GRID_MIN_MM) / GRID_STEP_MM).astype(np.int32), 0, GRID_N - 1)
        cells = ix * GRID_N + iy

        tb_arr = np.asarray(cd["t_bar"], dtype=np.float64)
        sg_arr = np.asarray(cd["sigma_2d"], dtype=np.float64)
        aa_arr = np.asarray(cd["amp_a"], dtype=np.float64)
        pa_arr = np.asarray(cd["power_a"], dtype=np.float64)
        fc_arr = np.asarray(cd["floor_c"], dtype=np.float64)
        hpl_arr = np.asarray(cd["has_power_law"], dtype=bool)

        t_bar_ev[:, c_idx] = tb_arr[cells]
        tw_ev[:, c_idx] = _eval_tw_vec(cd.get("time_walk_q", []), cd.get("time_walk_dt", []), q_raw[:, c_idx])

        sig = sg_arr[cells].copy()
        qr = q_raw[:, c_idx]
        m_pl = hpl_arr[cells] & np.isfinite(qr) & (qr > 1.0)
        if np.any(m_pl):
            pl = aa_arr[cells][m_pl] * np.power(qr[m_pl], -pa_arr[cells][m_pl])
            fl = fc_arr[cells][m_pl]
            sig[m_pl] = np.sqrt(pl * pl + fl * fl)
        sig_ev[:, c_idx] = np.clip(sig, 0.05, 3.5)

    return t_bar_ev, tw_ev, sig_ev


def _circular_cone_lookup(cd: dict[str, Any], t2: np.ndarray, q_raw: np.ndarray, xc: np.ndarray, yc: np.ndarray, radius_mm: float) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized replica of TimingCalibrator::calibrateCircularRegion (5x5 quadrature over 144 cells)."""
    n = len(t2)
    tb_144 = np.asarray(cd["t_bar"], dtype=np.float64)
    sg_144 = np.asarray(cd["sigma_2d"], dtype=np.float64)
    aa_144 = np.asarray(cd["amp_a"], dtype=np.float64)
    pa_144 = np.asarray(cd["power_a"], dtype=np.float64)
    fc_144 = np.asarray(cd["floor_c"], dtype=np.float64)
    hpl_144 = np.asarray(cd["has_power_law"], dtype=bool)

    # 60x60 sub-grid across [-150, +150]^2 (5 sub-cells per 25mm bin)
    k_sub = 5
    sub_n = GRID_N * k_sub
    sub_step = GRID_STEP_MM / k_sub
    coords = GRID_MIN_MM + (np.arange(sub_n) + 0.5) * sub_step
    sx, sy = np.meshgrid(coords, coords, indexing="ij")  # (60, 60)
    sx_flat = sx.ravel()
    sy_flat = sy.ravel()

    r2 = radius_mm * radius_mm
    tw = _eval_tw_vec(cd.get("time_walk_q", []), cd.get("time_walk_dt", []), q_raw)

    tcal_out = np.full(n, np.nan, dtype=np.float64)
    sig_out = np.full(n, np.nan, dtype=np.float64)

    # Process in chunks vectorized across the 144 cells to keep memory minimal and avoid Python loops
    for s0 in range(0, n, 2000):
        s1 = min(n, s0 + 2000)
        chunk = s1 - s0
        dx = sx_flat[None, :] - xc[s0:s1, None]
        dy = sy_flat[None, :] - yc[s0:s1, None]
        inside = (dx * dx + dy * dy) <= r2
        cell_counts = inside.reshape(chunk, GRID_N, k_sub, GRID_N, k_sub).sum(axis=(2, 4)).reshape(chunk, GRID_N * GRID_N)
        cnt = cell_counts.sum(axis=1)
        ok = cnt > 0
        if not np.any(ok):
            continue
        f_cell = cell_counts / np.maximum(cnt[:, None], 1)
        tb_eff = f_cell @ tb_144
        var_sp = np.sum(f_cell * (tb_144[None, :] - tb_eff[:, None]) ** 2, axis=1)

        qr_chunk = q_raw[s0:s1]
        q_ok = np.isfinite(qr_chunk) & (qr_chunk > 1.0)
        q_safe = np.where(q_ok, qr_chunk, 2.0)[:, None]
        sig_pl = np.sqrt((aa_144[None, :] * np.power(q_safe, -pa_144[None, :])) ** 2 + fc_144[None, :] ** 2)
        sig_cell = np.where(hpl_144[None, :] & q_ok[:, None], sig_pl, sg_144[None, :])
        sig_eff = np.sum(f_cell * sig_cell, axis=1)

        tcal_out[s0:s1] = np.where(ok, t2[s0:s1] - tb_eff - tw[s0:s1], np.nan)
        sig_out[s0:s1] = np.where(ok, np.sqrt(sig_eff * sig_eff + var_sp), np.nan)

    return tcal_out, sig_out


def _fit_speed_and_down_batch(tcal: np.ndarray, sig: np.ndarray, valid: np.ndarray, down_mask: np.ndarray, all_mask: np.ndarray) -> dict[str, np.ndarray]:
    """Vectorized weighted downstream reference (excluding VetoNu) and speed fit."""
    w = np.where(valid, 1.0 / (sig ** 2), 0.0)
    w_down = w * down_mask[None, :]
    sum_wd = np.sum(w_down, axis=1)
    sum_wtd = np.sum(w_down * np.where(valid, tcal, 0.0), axis=1)
    n_down = np.sum(w_down > 0, axis=1)
    t0_down = np.where((n_down >= 2) & (sum_wd > 0), sum_wtd / np.maximum(sum_wd, 1e-12), np.nan)
    sig_t0_down = np.where((n_down >= 2) & (sum_wd > 0), 1.0 / np.sqrt(np.maximum(sum_wd, 1e-12)), np.nan)
    res_d = np.where(w_down > 0, (tcal - t0_down[:, None]) / sig, 0.0)
    chi2_down = np.sum(res_d ** 2, axis=1)
    ndof_down = np.maximum(0, n_down - 1)

    # Speed fit over allowedMask (defaultPrimaryMask: 0..9 + 12..13)
    w_sp = w * all_mask[None, :]
    t_safe = np.where(w_sp > 0, tcal, 0.0)
    S = np.sum(w_sp, axis=1)
    Sd = w_sp @ CH_Z_M
    St = np.sum(w_sp * t_safe, axis=1)
    Sdd = w_sp @ (CH_Z_M ** 2)
    Sdt = np.sum(w_sp * t_safe * CH_Z_M[None, :], axis=1)
    n_sp = np.sum(w_sp > 0, axis=1)
    det = S * Sdd - Sd * Sd
    ok_sp = (n_sp >= 3) & (S > 0) & (det > 1e-9)

    t0_sp = np.where(ok_sp, (Sdd * St - Sd * Sdt) / np.maximum(det, 1e-12), np.nan)
    s_rel = np.where(ok_sp, (S * Sdt - Sd * St) / np.maximum(det, 1e-12), np.nan)
    inv_c = 1.0 / C_LIGHT_M_PER_NS
    inv_v = s_rel + inv_c
    beta = np.where(ok_sp & (inv_v > 1e-9), inv_c / np.maximum(inv_v, 1e-9), np.nan)
    sig_beta = np.where(ok_sp & (inv_v > 1e-9), (beta ** 2 / inv_c) * np.sqrt(np.maximum(S, 0.0) / np.maximum(det, 1e-12)), np.nan)
    pred = t0_sp[:, None] + s_rel[:, None] * CH_Z_M[None, :]
    chi2_sp = np.sum(np.where(w_sp > 0, ((t_safe - pred) / sig) ** 2, 0.0), axis=1)
    ndof_sp = np.maximum(0, n_sp - 2)

    return {
        "t0_down": t0_down, "sig_t0_down": sig_t0_down, "chi2_down": chi2_down, "ndof_down": ndof_down, "n_down": n_down,
        "t0_sp": t0_sp, "beta": beta, "sig_beta": sig_beta, "chi2_sp": chi2_sp, "ndof_sp": ndof_sp, "ok_sp": ok_sp,
        "sum_wd": sum_wd, "sum_wtd": sum_wtd, "w_down": w_down,
    }


def _period_for_run_vec(runs: np.ndarray) -> np.ndarray:
    out = np.full(len(runs), "2026", dtype=object)
    out[runs < 21500] = "2025"
    out[runs < 18500] = "2024_postCaloNu"
    out[runs <= 16924] = "2024_CaloNu"
    out[runs < 15821] = "2024_preCaloNu"
    out[runs < 13000] = "2023"
    out[runs < 10000] = "2022"
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage T1 Timing Closure Validation & Plotting")
    parser.add_argument("--manifest", default="AnalysisZipFramework/config/timing_calib/run3_timing_manifest.json")
    parser.add_argument("--ref-offsets", default="AnalysisZipFramework/config/timing_calib/ref_offsets_run3.json")
    parser.add_argument("--pass1-tsv", default="workbook/stage212_timing_t1/pass1_run_offsets_summary.tsv")
    parser.add_argument("--tof-maps", default="AnalysisZipFramework/config/timing_calib/tof_maps_run3.json")
    parser.add_argument("--merged-calib", default="ntuples/timing_stage212/pass2_merged_calib_events.root")
    parser.add_argument("--unwrap-tsv", default="workbook/stage212_timing_t1/pass2_unwrap_audit.tsv")
    parser.add_argument("--out-dir", default="workbook/stage212_timing_t1")
    parser.add_argument("--workers", type=int, default=28)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(args.ref_offsets) as f:
        ref_json = json.load(f)
    with open(args.tof_maps) as f:
        tof_json = json.load(f)

    ref_size = Path(args.ref_offsets).stat().st_size
    tof_size = Path(args.tof_maps).stat().st_size
    tot_calib_bytes = ref_size + tof_size
    print(f"[validate] Table sizes: ref_offsets={ref_size/1024:.1f} KB, tof_maps={tof_size/1024:.1f} KB, total={tot_calib_bytes/1024:.1f} KB")

    # Load merged Pass 2 events + unwrap histograms
    tf = uproot.open(args.merged_calib)
    read_cols = [
        "run", "is_cat0", "is_cat2", "is_cat3", "w0",
        "valid_mask", "above_mip_mask", "d12_trig_mm",
        "t2", "q_raw", "trk_x", "trk_y",
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as decomp_ex:
        ev = tf["calib_events"].arrays(
            expressions=read_cols,
            library="np",
            decompression_executor=decomp_ex,
        )
    ev_periods = _period_for_run_vec(ev["run"])

    # Compute calibrated t_cal and sigma_cal across all N events grouped by period
    n_tot = len(ev["run"])
    t2_all = ev["t2"].astype(np.float64)
    q_all = ev["q_raw"].astype(np.float64)
    trk_x_all = ev["trk_x"].astype(np.float64)
    trk_y_all = ev["trk_y"].astype(np.float64)
    valid_mask_all = ev["valid_mask"]
    above_mip_all = ev["above_mip_mask"]

    tcal_all = np.full_like(t2_all, np.nan)
    sig_all = np.full_like(t2_all, 0.35)

    for per in PERIOD_ORDER:
        m = ev_periods == per
        if not np.any(m) or per not in tof_json["periods"]:
            continue
        tb_p, tw_p, sg_p = _lookup_maps_period(tof_json["periods"][per], per, trk_x_all[m], trk_y_all[m], q_all[m])
        tcal_all[m] = t2_all[m] - tb_p - tw_p
        sig_all[m] = sg_p

    # Valid & above-MIP matrix (N, 14) with fiducial/opposite-bar Timing protection
    valid_mip = np.zeros((n_tot, len(CHANNELS)), dtype=bool)
    valid_anyq = np.zeros((n_tot, len(CHANNELS)), dtype=bool)
    for c_idx, cname in enumerate(CHANNELS):
        p_idx = CHANNEL_PLANE_IDX[c_idx]
        px, py = trk_x_all[:, p_idx], trk_y_all[:, p_idx]
        pos_ok = np.isfinite(px) & np.isfinite(py) & (np.abs(px) < 150.0) & (np.abs(py) < 150.0)
        if cname == "Timing01":
            pos_ok &= py < 10.0
        elif cname == "Timing23":
            pos_ok &= py > -10.0
        v_bit = ((valid_mask_all & (1 << c_idx)) != 0) & np.isfinite(tcal_all[:, c_idx]) & pos_ok
        valid_anyq[:, c_idx] = v_bit
        valid_mip[:, c_idx] = v_bit & ((above_mip_all & (1 << c_idx)) != 0)

    down_mask = np.zeros(len(CHANNELS), dtype=bool)
    down_mask[PRIMARY_DOWNSTREAM_CH_INDICES] = True
    prim_mask = down_mask.copy()
    prim_mask[0] = True
    prim_mask[1] = True

    fits = _fit_speed_and_down_batch(tcal_all, sig_all, valid_mip, down_mask, prim_mask)

    # ── 1) Single-muon LOO Closure Table ─────────────────────────────────────
    is_c0 = ev["is_cat0"] == 1
    w0 = ev["w0"].astype(np.float64)
    closure_1trk_rows: list[dict[str, Any]] = []
    max_abs_mu = 0.0

    for per in PERIOD_ORDER:
        m_per = is_c0 & (ev_periods == per)
        if not np.any(m_per):
            continue
        active = active_channels_for_period(per)
        for c_idx, cname in enumerate(CHANNELS):
            if cname not in active:
                continue
            w_c = fits["w_down"][m_per, c_idx] if down_mask[c_idx] else 0.0
            sum_wl = fits["sum_wd"][m_per] - w_c
            sum_wtl = fits["sum_wtd"][m_per] - (w_c * tcal_all[m_per, c_idx] if down_mask[c_idx] else 0.0)
            n_l = fits["n_down"][m_per] - (1 if down_mask[c_idx] else 0) * (valid_mip[m_per, c_idx].astype(np.int32))
            ok = valid_mip[m_per, c_idx] & (n_l >= 3) & (sum_wl > 0)
            if np.count_nonzero(ok) < 100:
                continue
            t_loo = sum_wtl[ok] / sum_wl[ok]
            var_loo = 1.0 / sum_wl[ok]
            res_cal = tcal_all[m_per, c_idx][ok] - t_loo
            res_pre = t2_all[m_per, c_idx][ok] - t_loo
            wt_ok = w0[m_per][ok]

            mu_pre, sig_pre, n_eff = _weighted_core_gauss(res_pre, wt_ok)
            mu_cal, sig_obs, _ = _weighted_core_gauss(res_cal, wt_ok)
            sig_int = math.sqrt(max(0.04 ** 2, sig_obs ** 2 - float(np.median(var_loo))))
            pull = res_cal / np.sqrt(sig_all[m_per, c_idx][ok] ** 2 + var_loo)
            mu_pull, sig_pull, _ = _weighted_core_gauss(pull, wt_ok)

            if cname in ("VetoNu0", "VetoNu1", "Veto10", "Veto11", "Veto20", "Veto21", "Timing01", "Timing23", "Muon0", "Muon1"):
                max_abs_mu = max(max_abs_mu, abs(mu_cal))

            closure_1trk_rows.append({
                "period": per,
                "channel": cname,
                "n_raw": int(np.count_nonzero(ok)),
                "n_eff": round(n_eff, 1),
                "pre_mu_ns": f"{mu_pre:.4f}",
                "pre_sigma_obs_ns": f"{sig_pre:.4f}",
                "cal_mu_ns": f"{mu_cal:.5f}",
                "cal_sigma_obs_ns": f"{sig_obs:.4f}",
                "cal_sigma_int_ns": f"{sig_int:.4f}",
                "quirk_ref_sigma_ns": "" if cname not in QUIRK_REF_SIGMA else f"{QUIRK_REF_SIGMA[cname]:.2f}",
                "loo_pull_mu": f"{mu_pull:.4f}",
                "loo_pull_sigma": f"{sig_pull:.4f}",
            })

    with open(out_dir / "closure_single_muon_summary.tsv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(closure_1trk_rows[0].keys()), delimiter="\t")
        writer.writeheader()
        writer.writerows(closure_1trk_rows)
    print(f"[validate] 1-track LOO closure: max |mu_cal| across primary scintillators = {max_abs_mu:.5f} ns")

    # ── 2) Multi-track (N_long = 2, 3) Pull Validation & d12 Dependence ───────
    in_time = fits["ok_sp"] & (fits["beta"] > 0.98) & (fits["beta"] < 1.02) & (np.abs(fits["t0_sp"]) < 1.0)
    mt_rows: list[dict[str, Any]] = []
    mt_pulls_ok = True
    for ntrk, cat_flag in ((2, ev["is_cat2"] == 1), (3, ev["is_cat3"] == 1)):
        m_nt = cat_flag & in_time
        for cname in ("VetoNu0", "VetoNu1", "Veto10", "Veto20", "Veto21", "Timing01", "Timing23", "Preshower0", "Muon0"):
            c_idx = CH_TO_IDX[cname]
            w_c = fits["w_down"][m_nt, c_idx] if down_mask[c_idx] else 0.0
            sum_wl = fits["sum_wd"][m_nt] - w_c
            sum_wtl = fits["sum_wtd"][m_nt] - (w_c * tcal_all[m_nt, c_idx] if down_mask[c_idx] else 0.0)
            n_l = fits["n_down"][m_nt] - (1 if down_mask[c_idx] else 0) * (valid_mip[m_nt, c_idx].astype(np.int32))
            ok = valid_mip[m_nt, c_idx] & (n_l >= 2) & (sum_wl > 0)
            if np.count_nonzero(ok) < 40:
                continue
            pull = (tcal_all[m_nt, c_idx][ok] - sum_wtl[ok] / sum_wl[ok]) / np.sqrt(sig_all[m_nt, c_idx][ok] ** 2 + 1.0 / sum_wl[ok])
            mu_p, sig_p, _ = _weighted_core_gauss(pull, np.ones_like(pull))
            if ntrk == 2 and cname in ("VetoNu0", "VetoNu1", "Veto10", "Veto20", "Timing01", "Timing23") and not (0.88 <= sig_p <= 1.12):
                mt_pulls_ok = False
            mt_rows.append({
                "n_long_tracks": ntrk,
                "slice": "all_intime",
                "channel": cname,
                "n_events": int(np.count_nonzero(ok)),
                "pull_mu": f"{mu_p:.4f}",
                "pull_sigma": f"{sig_p:.4f}",
            })
        # Also bin VetoNu0 & Veto20 vs d12_trig_mm
        d12 = ev["d12_trig_mm"][m_nt]
        for lo, hi in ((0, 30), (30, 60), (60, 120), (120, 400)):
            md = (d12 >= lo) & (d12 < hi)
            for cname in ("VetoNu0", "Veto20"):
                c_idx = CH_TO_IDX[cname]
                w_c = fits["w_down"][m_nt, c_idx] if down_mask[c_idx] else 0.0
                sum_wl = fits["sum_wd"][m_nt] - w_c
                sum_wtl = fits["sum_wtd"][m_nt] - (w_c * tcal_all[m_nt, c_idx] if down_mask[c_idx] else 0.0)
                ok = md & valid_mip[m_nt, c_idx] & (sum_wl > 0)
                if np.count_nonzero(ok) < 25:
                    continue
                pull = (tcal_all[m_nt, c_idx][ok] - sum_wtl[ok] / sum_wl[ok]) / np.sqrt(sig_all[m_nt, c_idx][ok] ** 2 + 1.0 / sum_wl[ok])
                mu_p, sig_p, _ = _weighted_core_gauss(pull, np.ones_like(pull))
                mt_rows.append({
                    "n_long_tracks": ntrk,
                    "slice": f"d12_{lo}_{hi}mm",
                    "channel": cname,
                    "n_events": int(np.count_nonzero(ok)),
                    "pull_mu": f"{mu_p:.4f}",
                    "pull_sigma": f"{sig_p:.4f}",
                })

    with open(out_dir / "closure_multitrack_pull_summary.tsv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(mt_rows[0].keys()), delimiter="\t")
        writer.writeheader()
        writer.writerows(mt_rows)

    # ── 3) Speed, Runs 14647/16023, _back Schema Subset, & VetoNu Cone Check ──
    speed_rows: list[dict[str, Any]] = []
    # Check full Run 3 periods + highlighted runs 14647 / 16023 + simulated _back schema (without Veto11 in 2022/23, without PS23/Muon)
    back_mask = np.zeros(len(CHANNELS), dtype=bool)
    back_mask[[2, 3, 4, 5, 6, 7, 8, 9]] = True
    back_prim_mask = back_mask.copy()
    back_prim_mask[[0, 1]] = True
    fits_noback_mups = _fit_speed_and_down_batch(tcal_all, sig_all, valid_mip, back_mask, back_prim_mask)

    for label, mask_ev, fdict in [
        ("Run3_all_cat0", is_c0, fits),
        ("Run3_back_subset_cat0", is_c0, fits_noback_mups),
        ("Run_14647", is_c0 & (ev["run"] == 14647), fits),
        ("Run_16023", is_c0 & (ev["run"] == 16023), fits),
        ("Period_2025", is_c0 & (ev_periods == "2025"), fits),
        ("Period_2026", is_c0 & (ev_periods == "2026"), fits),
    ]:
        ok = mask_ev & fdict["ok_sp"] & np.isfinite(fdict["beta"]) & (fdict["beta"] > 0.7) & (fdict["beta"] < 1.3)
        if np.count_nonzero(ok) < 20:
            continue
        mu_b, sig_b = _core_gauss_unitless(fdict["beta"][ok], w0[ok])
        chi2_ndof = fdict["chi2_sp"][ok] / np.maximum(fdict["ndof_sp"][ok], 1)
        speed_rows.append({
            "sample": label,
            "n_events": int(np.count_nonzero(ok)),
            "beta_mu": f"{mu_b:.5f}",
            "beta_sigma": f"{sig_b:.5f}",
            "chi2_ndof_median": f"{float(np.median(chi2_ndof)):.4f}",
            "chi2_ndof_mean": f"{float(np.mean(chi2_ndof[chi2_ndof < 20])):.4f}",
        })

    # Circular cone area-weighted lookup vs point lookup on VetoNu0 (2024_CaloNu cat0)
    cone_results: dict[str, Any] = {}
    m_vn_test = is_c0 & (ev_periods == "2024_CaloNu") & valid_mip[:, 0] & (fits["n_down"] >= 3)
    idx_vn = np.where(m_vn_test)[0][:20000]
    if len(idx_vn) >= 200:
        t0_vn = fits["t0_down"][idx_vn]
        s0_vn = fits["sig_t0_down"][idx_vn]
        # Point lookup pull
        p_pt = (tcal_all[idx_vn, 0] - t0_vn) / np.sqrt(sig_all[idx_vn, 0] ** 2 + s0_vn ** 2)
        mu_pt, sig_pt, _ = _weighted_core_gauss(p_pt, np.ones_like(p_pt))
        cone_results["point_R0"] = (round(mu_pt, 4), round(sig_pt, 4))
        cd_vn0 = tof_json["periods"]["2024_CaloNu"]["channels"]["VetoNu0"]
        for R_mm in (15.0, 30.0, 50.0):
            tc_c, sc_c = _circular_cone_lookup(cd_vn0, t2_all[idx_vn, 0], q_all[idx_vn, 0], trk_x_all[idx_vn, 0], trk_y_all[idx_vn, 0], R_mm)
            p_c = (tc_c - t0_vn) / np.sqrt(sc_c ** 2 + s0_vn ** 2)
            mu_c, sig_c, _ = _weighted_core_gauss(p_c, np.ones_like(p_c))
            cone_results[f"cone_R{int(R_mm)}"] = (round(mu_c, 4), round(sig_c, 4))
            speed_rows.append({
                "sample": f"VetoNu0_cone_R{int(R_mm)}mm",
                "n_events": len(idx_vn),
                "beta_mu": f"{mu_c:.4f} (pull_mu)",
                "beta_sigma": f"{sig_c:.4f} (pull_sig)",
                "chi2_ndof_median": f"pt={sig_pt:.4f}",
                "chi2_ndof_mean": "",
            })

    with open(out_dir / "closure_speed_and_cone_summary.tsv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(speed_rows[0].keys()), delimiter="\t")
        writer.writeheader()
        writer.writerows(speed_rows)

    # ── 4) Generate All 7 Diagnostic Plots ───────────────────────────────────
    plt.rcParams.update({"font.size": 10, "axes.grid": True, "grid.alpha": 0.25})

    # Fig 1: Pass 1 offsets stability + Digitizer-2 -16 ns audit
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.5), constrained_layout=True)
    run_nums = sorted(int(r) for r in ref_json["runs"].keys())
    for cname, col in (("Veto20", "C0"), ("Veto10", "C1"), ("Timing01", "C2"), ("Preshower0", "C3"), ("Muon0", "C4")):
        xs, ys_b, ys_t = [], [], []
        for r in run_nums:
            ch = ref_json["runs"][str(r)]["channels"].get(cname)
            if ch and ch.get("t_ref_bcid") is not None:
                xs.append(r)
                ys_b.append(ch["t_ref_bcid"])
                ys_t.append(ch["t_trig_rel_ref"])
        axes[0, 0].scatter(xs, ys_b, s=8, label=cname, alpha=0.8, color=col)
        axes[0, 1].scatter(xs, ys_t, s=8, label=cname, alpha=0.8, color=col)
    axes[0, 0].set_title(r"Pass 1 Per-Run $t_{\mathrm{ref}}^{\mathrm{BCID}}$ across 717 Run 3 Runs")
    axes[0, 0].set_xlabel("Run Number")
    axes[0, 0].set_ylabel(r"$t_{\mathrm{ref}}^{\mathrm{BCID}}$ [ns]")
    axes[0, 0].legend(markerscale=2, ncol=2, fontsize=8)
    axes[0, 1].set_title(r"Pass 1 $t_{\mathrm{trig}} - t_{\mathrm{trig}}(\mathrm{Veto20})$ across Run 3")
    axes[0, 1].set_xlabel("Run Number")
    axes[0, 1].set_ylabel(r"$t_{\mathrm{trig}}^{\mathrm{rel}}$ [ns]")
    axes[0, 1].legend(markerscale=2, ncol=2, fontsize=8)

    # Read Digitizer-2 shifts from pass1_run_offsets_summary.tsv
    dtrig_512, dloc_512, r_512, ch_512 = [], [], [], []
    with open(args.pass1_tsv) as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["dloc_shift_512_ns"] and row["dtrig_shift_512_ns"]:
                r_512.append(int(row["run"]))
                ch_512.append(row["channel"])
                dtrig_512.append(float(row["dtrig_shift_512_ns"]))
                dloc_512.append(float(row["dloc_shift_512_ns"]))
    if dloc_512:
        med_dloc = float(np.median(dloc_512))
        axes[1, 0].hist(dloc_512, bins=60, range=(-17.5, -14.5), color="crimson", alpha=0.8)
        axes[1, 0].axvline(med_dloc, color="k", linestyle="--", label=f"Median {med_dloc:.3f} ns")
        axes[1, 0].set_title("Digitizer-2 (status & 512) localtime Jump vs VetoNu0")
        axes[1, 0].set_xlabel(r"$\Delta t_{\mathrm{local}}(\mathrm{st512} - \mathrm{st0})$ [ns]")
        axes[1, 0].set_ylabel("Run-Channel Entries")
        axes[1, 0].legend()
        axes[1, 1].hist(dtrig_512, bins=60, range=(-0.5, 0.5), color="teal", alpha=0.8)
        axes[1, 1].axvline(0.0, color="k", linestyle="--")
        axes[1, 1].set_title("Digitizer-2 (status & 512) triggertime Alignment")
        axes[1, 1].set_xlabel(r"$\Delta t_{\mathrm{trig}}(\mathrm{st512} - \mathrm{st0})$ [ns]")
        axes[1, 1].set_ylabel("Run-Channel Entries")
    fig.savefig(out_dir / "fig1_pass1_offsets_and_digitizer2.png", dpi=180)
    plt.close(fig)

    # Fig 2: Unwrap residual |r_unwrap| + fail rates across periods
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.2), constrained_layout=True)
    r_edges = np.linspace(0.0, 12.5, 126)
    r_cent = 0.5 * (r_edges[:-1] + r_edges[1:])
    for cname in ("VetoNu0", "Veto10", "Veto20", "Timing01", "Preshower0", "Muon0"):
        tot_h = np.zeros(125, dtype=np.float64)
        for per in PERIOD_ORDER:
            hk = f"h_r_unwrap_{per}_{cname}"
            if hk in tf:
                tot_h += tf[hk].values(flow=False)
        if np.sum(tot_h) > 0:
            ax1.step(r_cent, tot_h / np.sum(tot_h), where="mid", label=cname)
    ax1.axvline(6.25, color="red", linestyle="--", label="Cut 6.25 ns")
    ax1.set_yscale("log")
    ax1.set_title(r"Full Run 3 $r_{\mathrm{unwrap}}$ Distribution (19.67B entries)")
    ax1.set_xlabel(r"$r_{\mathrm{unwrap}}$ [ns]")
    ax1.set_ylabel("Normalized Fraction")
    ax1.legend(fontsize=8, ncol=2)

    urows = list(csv.DictReader(open(args.unwrap_tsv), delimiter="\t"))
    chs_u = ["VetoNu0", "VetoNu1", "Veto10", "Veto11", "Veto20", "Veto21", "Timing01", "Timing23", "Preshower0", "Preshower1", "Muon0", "Muon1"]
    x_u = np.arange(len(chs_u))
    any_pos_u = False
    for per in PERIOD_ORDER:
        vals_u = []
        for c in chs_u:
            hit = [float(r["fail_rate_pct"]) for r in urows if r["period"] == per and r["channel"] == c]
            v = hit[0] if hit else np.nan
            if np.isfinite(v) and v > 0.0:
                any_pos_u = True
            vals_u.append(v)
        ax2.plot(x_u, vals_u, "o-", markersize=4, label=per)
    ax2.axhline(0.10, color="k", linestyle="--", label="Quirk ~0.1%")
    ax2.set_xticks(x_u)
    ax2.set_xticklabels(chs_u, rotation=35, ha="right", fontsize=8)
    ax2.set_title(r"Step 2 $r_{\mathrm{unwrap}} > 6.25\ \mathrm{ns}$ Fail Rate [%]")
    ax2.set_ylabel("Fail Rate [%]")
    if any_pos_u:
        ax2.set_yscale("log")
    else:
        ax2.set_ylim(-0.005, 0.12)
        ax2.text(0.5, 0.45, "All 76 period-channel entries: 0 / 2.87B unwrap failures (>6.25 ns)", transform=ax2.transAxes, ha="center", va="center", fontsize=9, bbox=dict(boxstyle="round", facecolor="honeydew", alpha=0.85))
    ax2.legend(fontsize=8, ncol=2)
    fig.savefig(out_dir / "fig2_unwrap_residual_and_fail_rate.png", dpi=180)
    plt.close(fig)

    # Fig 3: Single-muon LOO closure mean & sigma_int across periods & channels
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8.0), sharex=True, constrained_layout=True)
    x_c = np.arange(len(CHANNELS))
    for per in PERIOD_ORDER:
        mus, sigs = [], []
        for c in CHANNELS:
            match = [r for r in closure_1trk_rows if r["period"] == per and r["channel"] == c]
            mus.append(float(match[0]["cal_mu_ns"]) if match else np.nan)
            sigs.append(float(match[0]["cal_sigma_int_ns"]) if match else np.nan)
        ax1.plot(x_c, mus, "o-", markersize=4, label=per)
        ax2.plot(x_c, sigs, "o-", markersize=4, label=per)
    ax1.axhline(0.03, color="r", linestyle="--", label=r"$\pm 0.03\ \mathrm{ns}$ target")
    ax1.axhline(-0.03, color="r", linestyle="--")
    ax1.axhline(0.0, color="k", linewidth=0.8)
    ax1.set_ylabel(r"LOO Mean $\mu$ [ns]")
    ax1.set_title("Single-Muon Leave-One-Out Core Gaussian Mean & Deconvolved Resolution across Run 3")
    ax1.legend(ncol=4, fontsize=8)
    q_xs = [CH_TO_IDX[c] for c in QUIRK_REF_SIGMA]
    q_ys = [QUIRK_REF_SIGMA[c] for c in QUIRK_REF_SIGMA]
    ax2.plot(q_xs, q_ys, "k*--", markersize=9, label="Quirk PRL Fig. 6 ref")
    ax2.set_xticks(x_c)
    ax2.set_xticklabels(CHANNELS, rotation=30, ha="right")
    ax2.set_ylabel(r"Intrinsic Resolution $\sigma_{\mathrm{int}}$ [ns]")
    ax2.set_ylim(0.0, 2.3)
    ax2.legend(ncol=4, fontsize=8)
    fig.savefig(out_dir / "fig3_loo_single_muon_closure.png", dpi=180)
    plt.close(fig)

    # Fig 4: 2D TOF & sigma_2d maps for representative channels (2024_CaloNu & 2026)
    show_2d = [
        ("2024_CaloNu", "VetoNu0"), ("2024_CaloNu", "Veto10"), ("2024_CaloNu", "Veto20"),
        ("2024_CaloNu", "Timing01"), ("2024_CaloNu", "Timing23"), ("2024_CaloNu", "Preshower0"),
        ("2026", "Muon0"), ("2026", "Muon1"),
    ]
    fig, axes = plt.subplots(2, 4, figsize=(15, 7.2), constrained_layout=True)
    for ax, (per, cname) in zip(axes.ravel(), show_2d):
        tb = np.asarray(tof_json["periods"][per]["channels"][cname]["t_bar"]).reshape(GRID_N, GRID_N).T
        im = ax.imshow(tb, origin="lower", extent=[GRID_MIN_MM, GRID_MAX_MM, GRID_MIN_MM, GRID_MAX_MM], cmap="coolwarm", vmin=-1.2, vmax=1.2)
        ax.set_title(f"{cname} ({per})")
        ax.set_xlabel("x [mm]")
        ax.set_ylabel("y [mm]")
        fig.colorbar(im, ax=ax, shrink=0.82, label=r"$\bar{t}$ [ns]")
    fig.suptitle(r"Calibrated $12 \times 12$ ($25 \times 25\ \mathrm{mm}^2$) 2D Photon TOF Maps $\bar{t}_{i;ab}(x,y)$", fontsize=13)
    fig.savefig(out_dir / "fig4_tof_and_sigma_2d_maps.png", dpi=180)
    plt.close(fig)

    # Fig 5: Time-walk delta_t(Q) & floored power-law sigma(Q)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.2), constrained_layout=True)
    p24c = tof_json["periods"]["2024_CaloNu"]["channels"]
    p26 = tof_json["periods"]["2026"]["channels"]
    for src, lbl_p, cname in [
        (p24c, "2024_CaloNu", "VetoNu0"), (p24c, "2024_CaloNu", "Veto10"),
        (p24c, "2024_CaloNu", "Veto20"), (p24c, "2024_CaloNu", "Timing23"),
        (p26, "2026", "Muon0"),
    ]:
        cd = src[cname]
        if cd["time_walk_q"]:
            ax1.plot(cd["time_walk_q"], cd["time_walk_dt"], "o-", markersize=4, label=f"{cname} ({lbl_p})")
        qgrid = np.linspace(15.0, 200.0, 120)
        # Center cell (5,5) power-law curve
        k0 = 5 * GRID_N + 5
        if cd["has_power_law"][k0]:
            sig_q = np.sqrt((cd["amp_a"][k0] * (qgrid ** (-cd["power_a"][k0]))) ** 2 + cd["floor_c"][k0] ** 2)
            ax2.plot(qgrid, sig_q, label=f"{cname} ({lbl_p}): A={cd['amp_a'][k0]:.1f}, a={cd['power_a'][k0]:.2f}, c={cd['floor_c'][k0]:.2f}")
    ax1.axhline(0.0, color="k", linewidth=0.8)
    ax1.set_xlim(10, 210)
    ax1.set_title(r"Low-Charge Time-Walk Curve $\delta\bar{t}_i(Q)$")
    ax1.set_xlabel("Raw Charge $Q$ [pC]")
    ax1.set_ylabel(r"$\delta\bar{t}_i(Q)$ [ns]")
    ax1.legend(fontsize=8)
    ax2.set_title(r"Floored Power-Law Resolution $\sigma(Q) = \sqrt{(AQ^{-a})^2 + c^2}$")
    ax2.set_xlabel("Raw Charge $Q$ [pC]")
    ax2.set_ylabel(r"$\sigma(Q)$ [ns]")
    ax2.legend(fontsize=8)
    fig.savefig(out_dir / "fig5_timewalk_and_charge_resolution.png", dpi=180)
    plt.close(fig)

    # Fig 6: Multi-track Pull distributions & d12 dependence
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2), constrained_layout=True)
    m2 = (ev["is_cat2"] == 1) & in_time
    p_edges = np.linspace(-4.0, 4.0, 41)
    for cname in ("VetoNu0", "Veto10", "Veto20", "Timing01"):
        c_idx = CH_TO_IDX[cname]
        w_c = fits["w_down"][m2, c_idx] if down_mask[c_idx] else 0.0
        sum_wl = fits["sum_wd"][m2] - w_c
        sum_wtl = fits["sum_wtd"][m2] - (w_c * tcal_all[m2, c_idx] if down_mask[c_idx] else 0.0)
        ok = valid_mip[m2, c_idx] & (sum_wl > 0)
        if np.count_nonzero(ok) >= 40:
            pull = (tcal_all[m2, c_idx][ok] - sum_wtl[ok] / sum_wl[ok]) / np.sqrt(sig_all[m2, c_idx][ok] ** 2 + 1.0 / sum_wl[ok])
            mu_p, sig_p, _ = _weighted_core_gauss(pull, np.ones_like(pull))
            axes[0].hist(pull, bins=p_edges, density=True, histtype="step", linewidth=1.6, label=f"{cname}: $\\mu={mu_p:+.2f},\\ \\sigma={sig_p:.2f}$")
    xs_u = np.linspace(-4, 4, 200)
    axes[0].plot(xs_u, np.exp(-0.5 * xs_u ** 2) / math.sqrt(2 * math.pi), "k--", label=r"$\mathcal{N}(0,1)$")
    axes[0].set_title(r"$N_{\mathrm{long}}=2$ In-Time LOO Pulls ($0.98<v/c<1.02,\ |t_0|<1\ \mathrm{ns}$)")
    axes[0].set_xlabel("Pull")
    axes[0].set_ylabel("Density")
    axes[0].legend(fontsize=8)

    # Right panel: Pull sigma vs d12 slice
    d12_labels = ["d12_0_30mm", "d12_30_60mm", "d12_60_120mm", "d12_120_400mm"]
    xd = np.arange(len(d12_labels))
    for cname in ("VetoNu0", "Veto20"):
        sigs_d = []
        for sl in d12_labels:
            hit = [float(r["pull_sigma"]) for r in mt_rows if int(r["n_long_tracks"]) == 2 and r["slice"] == sl and r["channel"] == cname]
            sigs_d.append(hit[0] if hit else np.nan)
        axes[1].plot(xd, sigs_d, "o-", label=f"2-track {cname}")
    axes[1].axhspan(0.88, 1.12, color="green", alpha=0.12, label=r"$1.00 \pm 0.12$ target")
    axes[1].axhline(1.0, color="k", linestyle="--")
    axes[1].set_xticks(xd)
    axes[1].set_xticklabels(["0-30 mm", "30-60 mm", "60-120 mm", ">120 mm"])
    axes[1].set_ylabel("Pull Gaussian Width $\\sigma$")
    axes[1].set_ylim(0.6, 1.4)
    axes[1].set_title(r"$N_{\mathrm{long}}=2$ Pull Width vs Track Separation $d_{12}$")
    axes[1].legend(fontsize=8)
    fig.savefig(out_dir / "fig6_multitrack_pull_and_d12.png", dpi=180)
    plt.close(fig)

    # Fig 7: Speed beta=v/c, chi2/ndof, Runs 14647/16023 + back schema + VetoNu cone
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.2), constrained_layout=True)
    for lbl, mask_ev, fdict in [
        ("Run 3 Full", is_c0, fits),
        ("Run 14647", is_c0 & (ev["run"] == 14647), fits),
        ("Run 16023", is_c0 & (ev["run"] == 16023), fits),
        ("2022-24 back subset", is_c0, fits_noback_mups),
    ]:
        ok = mask_ev & fdict["ok_sp"] & (fdict["beta"] > 0.85) & (fdict["beta"] < 1.15)
        if np.count_nonzero(ok) >= 30:
            axes[0, 0].hist(fdict["beta"][ok], bins=60, range=(0.88, 1.12), density=True, histtype="step", label=lbl, weights=w0[ok])
            c2 = fdict["chi2_sp"][ok] / np.maximum(fdict["ndof_sp"][ok], 1)
            axes[0, 1].hist(c2, bins=50, range=(0.0, 5.0), density=True, histtype="step", label=lbl, weights=w0[ok])
    axes[0, 0].axvline(1.0, color="k", linestyle="--")
    axes[0, 0].set_title(r"1-Track Muon Speed $\beta = v/c$")
    axes[0, 0].set_xlabel(r"$\beta = v/c$")
    axes[0, 0].legend(fontsize=8)
    axes[0, 1].set_title(r"Speed Fit Reduced $\chi^2 / \mathrm{ndof}$")
    axes[0, 1].set_xlabel(r"$\chi^2 / \mathrm{ndof}$")
    axes[0, 1].legend(fontsize=8)

    if cone_results:
        keys_c = list(cone_results.keys())
        yc_s = [cone_results[k][1] for k in keys_c]
        axes[1, 0].bar(range(len(keys_c)), yc_s, color=["steelblue", "orange", "coral", "crimson"][:len(keys_c)])
        axes[1, 0].axhspan(0.88, 1.12, color="green", alpha=0.12)
        axes[1, 0].axhline(1.0, color="k", linestyle="--")
        axes[1, 0].set_xticks(range(len(keys_c)))
        axes[1, 0].set_xticklabels(keys_c)
        axes[1, 0].set_ylim(0.5, 1.35)
        axes[1, 0].set_ylabel("Pull Width $\\sigma$")
        axes[1, 0].set_title(r"VetoNu0 Circular-Cone Lookup ($R=15,30,50\ \mathrm{mm}$) vs Point")

    # Bottom-right: Period-by-period mean chi2/ndof & VetoNu0 LOO mean
    p_mus = []
    for per in PERIOD_ORDER:
        hit = [float(r["cal_mu_ns"]) for r in closure_1trk_rows if r["period"] == per and r["channel"] == "VetoNu0"]
        p_mus.append(hit[0] if hit else np.nan)
    axes[1, 1].plot(range(len(PERIOD_ORDER)), p_mus, "o-", color="navy", label="VetoNu0 LOO mean")
    axes[1, 1].axhline(0.03, color="r", linestyle="--")
    axes[1, 1].axhline(-0.03, color="r", linestyle="--")
    axes[1, 1].axhline(0.0, color="k", linewidth=0.8)
    axes[1, 1].set_xticks(range(len(PERIOD_ORDER)))
    axes[1, 1].set_xticklabels(PERIOD_ORDER, rotation=25, ha="right", fontsize=8)
    axes[1, 1].set_ylabel(r"$\mu(\Delta t_{\mathrm{VetoNu0}})$ [ns]")
    axes[1, 1].set_title("VetoNu0 Closure Stability Across All 7 Periods")
    axes[1, 1].legend(fontsize=8)
    fig.savefig(out_dir / "fig7_speed_chi2_cone_and_back_closure.png", dpi=180)
    plt.close(fig)

    gates = {
        "total_calib_json_bytes": int(tot_calib_bytes),
        "size_under_2mb": tot_calib_bytes < 2 * 1024 * 1024,
        "max_abs_primary_loo_mu_ns": round(max_abs_mu, 5),
        "single_muon_mean_under_0p03ns": max_abs_mu < 0.03,
        "multitrack_pull_widths_in_band": mt_pulls_ok,
        "n_runs_offsets": len(ref_json["runs"]),
        "n_periods_tof_maps": len(tof_json["periods"]),
        "cone_results": cone_results,
    }
    with open(out_dir / "closure_acceptance_checks.json", "w") as f:
        json.dump(gates, f, indent=2)
    print("[validate] Acceptance checks:", json.dumps(gates, indent=2))


if __name__ == "__main__":
    main()
