"""Stage 211 (T0): Full Run 3 timing data contract audit & blinding-guarded check.

Runs multi-process (28 workers) over representative 2022-2026 Data, 2024_cos,
GENIE MC (5 Geant4 physics lists), and FLUKA MC files, enforcing the orthogonal
SR-ZoneB blinding guard at data entry. Produces compact manifest, TSV tables,
JSON audit summary, and diagnostic plots.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import glob
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

import awkward as ak
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import uproot
import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from timing_blinding_guard import filter_unblinded_arrays

DQ_MANIFEST_PATH = Path("/eos/home-x/xcheng/FASER/DQ_timing_trigger_2022_2026_L10/manifest.json")
FILE_CONFIG_PATH = REPO_DIR / "AnalysisZipFramework/config/file_config.yaml"
GRL_FULL_PATH = REPO_DIR / "AnalysisZipFramework/config/grl_config_run3_full.yaml"
QUIRK_EOS_DIR = Path("/eos/project/f/faser-quirks/Data/phys/2024/r0022")

ALL_SCINT_PREFIXES = (
    "VetoNu0", "VetoNu1",
    "Veto10", "Veto11", "Veto20", "Veto21",
    "VetoGm0", "VetoGm1",
    "Timing0", "Timing1", "Timing2", "Timing3",
    "Preshower0", "Preshower1", "Preshower2", "Preshower3",
    "Muon0", "Muon1",
    "CaloNu0", "CaloNu1", "CaloNu2", "CaloNu3",
)

CORE_SCINT_PREFIXES = (
    "VetoNu0", "VetoNu1",
    "Veto10", "Veto11", "Veto20", "Veto21",
    "Timing0", "Timing1", "Timing2", "Timing3",
    "Preshower0", "Preshower1", "Preshower2", "Preshower3",
    "Muon0", "Muon1",
    "VetoGm0", "VetoGm1",
)

QUIRK_TABLE5_MIP_THRESHOLDS_PC = {
    "VetoNu0": 63.3,
    "VetoNu1": 64.1,
    "Veto10": 61.2,
    "Veto20": 59.2,
    "Veto21": 57.0,
    "Timing01": 35.0,
    "Timing23": 35.0,
    "Preshower0": 3.50,
    "Preshower1": 3.12,
}

QUIRK_TABLE4_Z_M = {
    "VetoNu0": -3.123,
    "VetoNu1": -3.102,
    "Veto10": -1.790,
    "Veto11": -1.770,
    "Veto20": -1.620,
    "Veto21": -1.599,
    "Timing01": -0.022,
    "Timing23": -0.037,
    "Preshower0": 2.583,
    "Preshower1": 2.658,
}


def resolve_local_eos_path(uri: str) -> str:
    if uri.startswith("root://"):
        idx = uri.find("//eos/")
        if idx >= 0:
            return uri[idx + 1:]
    return uri


def classify_data_period(year: int, run: int) -> str:
    if year == 2022:
        return "2022"
    if year == 2023:
        return "2023"
    if year == 2024:
        if run < 15821:
            return "2024_preCaloNu"
        if run <= 16924:
            return "2024_CaloNu"
        return "2024_postCaloNu"
    if year == 2025:
        return "2025"
    if year == 2026:
        return "2026"
    return f"other_{year}"


def _finite_pair_mean(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    fa = np.isfinite(a)
    fb = np.isfinite(b)
    cnt = fa.astype(np.int32) + fb.astype(np.int32)
    s = np.where(fa, a, 0.0) + np.where(fb, b, 0.0)
    return np.where(cnt > 0, s / np.maximum(cnt, 1), np.nan)


def _compute_lead_and_blind_filter(tree: Any, is_mc: bool, max_entries: int | None = None) -> tuple[dict[str, np.ndarray], int, set[str]]:
    keys = set(tree.keys())
    has_reduced = "VetoNu0_reduced_charge" in keys and "VetoNu1_reduced_charge" in keys

    needed = [
        "run", "eventID", "eventTime", "longTracks",
        "Veto20_raw_charge", "Veto21_raw_charge",
        "Veto20_charge", "Veto21_charge",
        "Timing0_charge", "Timing1_charge", "Timing2_charge", "Timing3_charge",
        "Timing0_raw_charge", "Timing1_raw_charge", "Timing2_raw_charge", "Timing3_raw_charge",
        "Preshower0_charge", "Preshower1_charge",
        "VetoNu0_raw_charge", "VetoNu1_raw_charge",
        "VetoNu0_localtime", "VetoNu1_localtime",
        "Veto20_localtime", "Veto21_localtime",
        "Preshower0_localtime", "Preshower1_localtime",
        "VetoNu0_status", "VetoNu1_status",
        "Veto20_status", "Veto21_status",
        "Timing0_status", "Timing1_status", "Timing2_status", "Timing3_status",
        "Preshower0_status", "Preshower1_status",
        "Track_pz0", "Track_px0", "Track_py0", "Track_nLayers", "Track_nDoF", "Track_Chi2",
        "Track_r_atMaxRadius",
        "Track_X_atVetoNu", "Track_Y_atVetoNu",
        "Track_X_atVetoStation2", "Track_Y_atVetoStation2",
        "Track_X_atTrig", "Track_Y_atTrig",
        "Track_X_atPreshower1", "Track_Y_atPreshower1",
        "Track_X_atPreshower2", "Track_Y_atPreshower2",
    ]
    if not is_mc:
        for opt in ("distanceToCollidingBCID", "distanceToInboundB1", "inputBits", "TAP", "crossingAngle"):
            if opt in keys:
                needed.append(opt)
    if has_reduced:
        needed.extend(["VetoNu0_reduced_charge", "VetoNu1_reduced_charge"])
    for p in ALL_SCINT_PREFIXES:
        for suf in ("_bcidtime", "_triggertime", "_localtime", "_time", "_raw_charge", "_charge", "_width", "_status"):
            col = f"{p}{suf}"
            if col in keys and col not in needed:
                needed.append(col)
    for k in keys:
        if k.startswith("VetoSt") and k not in needed:
            needed.append(k)

    ak_arrs = tree.arrays([c for c in needed if c in keys], entry_stop=max_entries, library="ak")
    n = len(ak_arrs["run"])
    if n == 0:
        return {}, 0, keys

    pz_ak = ak_arrs["Track_pz0"]
    argmax_ak = ak.argmax(pz_ak, axis=1, keepdims=True)
    lead_idx = np.asarray(ak.fill_none(ak.firsts(argmax_ak), -1), dtype=np.int64)

    def _pick(col: str, scale: float = 1.0, fill: float = np.nan, dtype=np.float64) -> np.ndarray:
        vals = ak.firsts(ak_arrs[col][argmax_ak])
        arr = np.asarray(ak.fill_none(vals, fill), dtype=dtype)
        return arr * scale if scale != 1.0 else arr

    lead_pz0_gev = _pick("Track_pz0", scale=1e-3)
    lead_px0 = _pick("Track_px0")
    lead_py0 = _pick("Track_py0")
    lead_pz0_mev = _pick("Track_pz0")
    lead_theta_mrad = np.arctan2(np.hypot(lead_px0, lead_py0), lead_pz0_mev) * 1000.0
    lead_nlayers = _pick("Track_nLayers", fill=0, dtype=np.uint32)
    lead_ndof = _pick("Track_nDoF")
    lead_chi2 = _pick("Track_Chi2")
    lead_chi2_ndf = lead_chi2 / np.where(lead_ndof > 0, lead_ndof, np.nan)
    lead_rmax = _pick("Track_r_atMaxRadius")
    lead_x_veto2 = _pick("Track_X_atVetoStation2")
    lead_y_veto2 = _pick("Track_Y_atVetoStation2")
    lead_r_ift = np.hypot(lead_x_veto2, lead_y_veto2)
    lead_x_vetonu = _pick("Track_X_atVetoNu")
    lead_y_vetonu = _pick("Track_Y_atVetoNu")
    lead_r_vetonu = np.hypot(lead_x_vetonu, lead_y_vetonu)
    lead_x_trig = _pick("Track_X_atTrig")
    lead_y_trig = _pick("Track_Y_atTrig")

    flat_arrs: dict[str, np.ndarray] = {
        k: np.asarray(ak_arrs[k]) for k in ak_arrs.fields if not k.startswith("Track_")
    }
    # Legacy compatibility aliases (mirrors Analysis::setupVetoCompatibility + r0019 *_time -> *_localtime)
    for k in list(flat_arrs.keys()):
        if k.startswith("VetoSt"):
            alias = "Veto" + k[6:]
            if alias not in flat_arrs:
                flat_arrs[alias] = flat_arrs[k]
    for k in list(flat_arrs.keys()):
        if k.endswith("_time"):
            lt_name = k[:-5] + "_localtime"
            if lt_name not in flat_arrs:
                flat_arrs[lt_name] = flat_arrs[k]

    # Pre-calibration conservative delay estimate relative to downstream localtime
    v20_lt = np.where((flat_arrs["Veto20_status"] & ~528) == 0, flat_arrs["Veto20_localtime"], np.nan)
    v21_lt = np.where((flat_arrs["Veto21_status"] & ~528) == 0, flat_arrs["Veto21_localtime"], np.nan)
    ps0_lt = np.where((flat_arrs["Preshower0_status"] & ~528) == 0, flat_arrs["Preshower0_localtime"], np.nan)
    ps1_lt = np.where((flat_arrs["Preshower1_status"] & ~528) == 0, flat_arrs["Preshower1_localtime"], np.nan)
    v2_mean = _finite_pair_mean(v20_lt, v21_lt)
    ps_mean = _finite_pair_mean(ps0_lt, ps1_lt)
    exp_lt_from_v2 = v2_mean - 5.05
    exp_lt_from_ps = ps_mean - 19.12
    exp_lt = np.where(np.isfinite(exp_lt_from_v2), exp_lt_from_v2, exp_lt_from_ps)
    dlt0 = np.where((flat_arrs["VetoNu0_status"] & ~528) == 0, flat_arrs["VetoNu0_localtime"] - exp_lt, np.nan)
    dlt1 = np.where((flat_arrs["VetoNu1_status"] & ~528) == 0, flat_arrs["VetoNu1_localtime"] - exp_lt, np.nan)
    raw_delay_max = np.fmax(dlt0, dlt1)

    flat_arrs["LeadIdx"] = lead_idx
    flat_arrs["LeadPz0GeV"] = lead_pz0_gev
    flat_arrs["LeadThetaMrad"] = lead_theta_mrad
    flat_arrs["LeadNLayers"] = lead_nlayers
    flat_arrs["LeadNDoF"] = lead_ndof
    flat_arrs["LeadChi2NDF"] = lead_chi2_ndf
    flat_arrs["LeadRMax"] = lead_rmax
    flat_arrs["LeadRIFT"] = lead_r_ift
    flat_arrs["LeadRVetoNu"] = lead_r_vetonu
    flat_arrs["LeadXTrig"] = lead_x_trig
    flat_arrs["LeadYTrig"] = lead_y_trig
    flat_arrs["LeadXVetoNu"] = lead_x_vetonu
    flat_arrs["LeadYVetoNu"] = lead_y_vetonu
    flat_arrs["LeadXPs1"] = _pick("Track_X_atPreshower1")
    flat_arrs["LeadYPs1"] = _pick("Track_Y_atPreshower1")

    dist_bcid = flat_arrs["distanceToCollidingBCID"] if "distanceToCollidingBCID" in flat_arrs else np.full(n, -1, dtype=np.int32)
    filtered, n_blinded = filter_unblinded_arrays(
        flat_arrs,
        enforce_blinding=True,
        is_mc=is_mc,
        distance_to_colliding_bcid=dist_bcid,
        long_tracks=flat_arrs["longTracks"],
        veto20_charge=flat_arrs["Veto20_charge"],
        veto21_charge=flat_arrs["Veto21_charge"],
        timing_charge_top=flat_arrs["Timing2_charge"] + flat_arrs["Timing3_charge"],
        timing_charge_bottom=flat_arrs["Timing0_charge"] + flat_arrs["Timing1_charge"],
        preshower0_charge=flat_arrs["Preshower0_charge"],
        preshower1_charge=flat_arrs["Preshower1_charge"],
        lead_y_at_trig=lead_y_trig,
        lead_pz0_gev=lead_pz0_gev,
        lead_n_layers=lead_nlayers,
        lead_ndof=lead_ndof,
        lead_chi2_ndf=lead_chi2_ndf,
        lead_r_max=lead_rmax,
        lead_r_ift=lead_r_ift,
        lead_r_vetonu=lead_r_vetonu,
        lead_theta_mrad=lead_theta_mrad,
        vetonu0_raw_charge=flat_arrs["VetoNu0_raw_charge"],
        vetonu1_raw_charge=flat_arrs["VetoNu1_raw_charge"],
        vetonu0_reduced_charge=flat_arrs.get("VetoNu0_reduced_charge"),
        vetonu1_reduced_charge=flat_arrs.get("VetoNu1_reduced_charge"),
        has_calibrated_time=False,
        raw_delay_max_ns=raw_delay_max,
    )
    return filtered, n_blinded, keys


def _inspect_one_file(task: tuple[str, str, bool, int]) -> dict[str, Any]:
    label, path, is_mc, max_entries = task
    local_path = resolve_local_eos_path(path)
    t0 = time.perf_counter()
    try:
        f = uproot.open(local_path if os.path.exists(local_path) else path)
        nt = f["nt"]
        n_total = nt.num_entries
        keys = set(nt.keys())
        has_vetost = any(k.startswith("VetoSt") for k in keys)
        branch_presence = {
            "VetoNu0_bcidtime": "VetoNu0_bcidtime" in keys,
            "VetoNu0_triggertime": "VetoNu0_triggertime" in keys,
            "VetoNu0_localtime": "VetoNu0_localtime" in keys,
            "VetoNu0_time_legacy": "VetoNu0_time" in keys,
            "VetoNu0_reduced_charge": "VetoNu0_reduced_charge" in keys,
            "Veto11_raw_charge": "Veto11_raw_charge" in keys,
            "VetoSt10_bcidtime": "VetoSt10_bcidtime" in keys,
            "CaloNu0_raw_charge": "CaloNu0_raw_charge" in keys,
            "Preshower2_raw_charge": "Preshower2_raw_charge" in keys,
            "Preshower3_raw_charge": "Preshower3_raw_charge" in keys,
            "VetoGm0_raw_charge": "VetoGm0_raw_charge" in keys,
            "Muon0_raw_charge": "Muon0_raw_charge" in keys,
            "Track_X_atMuon1": "Track_X_atMuon1" in keys,
        }
        arr, n_blinded, _ = _compute_lead_and_blind_filter(nt, is_mc=is_mc, max_entries=max_entries)
        n_kept = len(arr["run"]) if arr else 0
        stats: dict[str, Any] = {}
        if n_kept > 0:
            one_trk = (
                (arr["longTracks"] == 1)
                & (arr["LeadPz0GeV"] > 30.0)
                & (arr["LeadNLayers"] >= 6)
                & (arr["LeadChi2NDF"] < 10.0)
                & (np.abs(arr["LeadXTrig"]) < 115.0)
                & (np.abs(arr["LeadYTrig"]) < 115.0)
            )
            if not is_mc and "distanceToCollidingBCID" in arr:
                one_trk = one_trk & (arr["distanceToCollidingBCID"] == 0)

            stats["n_1trk_clean"] = int(np.sum(one_trk))
            for ch in ("VetoNu0", "Veto10", "Veto20", "Timing0", "Preshower0", "Preshower2", "Muon0", "VetoGm0"):
                if f"{ch}_status" not in arr:
                    continue
                bcid = arr.get(f"{ch}_bcidtime")
                trig = arr.get(f"{ch}_triggertime")
                loc = arr.get(f"{ch}_localtime")
                st = arr[f"{ch}_status"]
                qraw = arr[f"{ch}_raw_charge"]
                st_clean = (st & ~528) == 0
                stats[ch] = {
                    "bcid_zero_frac": float(np.mean(bcid == 0)) if bcid is not None else -1.0,
                    "trig_zero_frac": float(np.mean(trig == 0)) if trig is not None else -1.0,
                    "loc_zero_frac": float(np.mean(loc == 0)) if loc is not None else -1.0,
                    "status_512_frac": float(np.mean((st & 512) != 0)),
                    "status_16_frac": float(np.mean((st & 16) != 0)),
                    "status_4_overflow_frac": float(np.mean((st & 4) != 0)),
                    "status_good_1trk_frac": float(np.mean(st_clean[one_trk])) if np.any(one_trk) else None,
                    "qraw_p50_1trk": float(np.nanmedian(qraw[one_trk & st_clean])) if np.any(one_trk & st_clean) else None,
                }
            # MIP 0.1% / 1% quantiles on clean 1-trk muons
            mip_q = {}
            for ch in ("VetoNu0", "VetoNu1", "Veto10", "Veto11", "Veto20", "Veto21",
                       "Preshower0", "Preshower1", "Preshower2", "Preshower3", "Muon0", "Muon1", "VetoGm0", "VetoGm1"):
                if f"{ch}_raw_charge" not in arr:
                    continue
                st_clean = (arr[f"{ch}_status"] & ~528) == 0
                m = one_trk & st_clean & (arr[f"{ch}_raw_charge"] > 0.2)
                if np.sum(m) >= 500:
                    qs = np.quantile(arr[f"{ch}_raw_charge"][m], [0.001, 0.01, 0.05, 0.50])
                    mip_q[ch] = {"n": int(np.sum(m)), "q001": float(qs[0]), "q01": float(qs[1]), "q05": float(qs[2]), "q50": float(qs[3])}
            for tname, c0, c1 in (("Timing01", "Timing0", "Timing1"), ("Timing23", "Timing2", "Timing3")):
                st_clean = ((arr[f"{c0}_status"] & ~528) == 0) & ((arr[f"{c1}_status"] & ~528) == 0)
                qsum = arr[f"{c0}_raw_charge"] + arr[f"{c1}_raw_charge"]
                ycut = (arr["LeadYTrig"] < -20.0) if tname == "Timing01" else (arr["LeadYTrig"] > 20.0)
                m = one_trk & st_clean & ycut & (qsum > 1.0)
                if np.sum(m) >= 500:
                    qs = np.quantile(qsum[m], [0.001, 0.01, 0.05, 0.50])
                    mip_q[tname] = {"n": int(np.sum(m)), "q001": float(qs[0]), "q01": float(qs[1]), "q05": float(qs[2]), "q50": float(qs[3])}
            stats["mip_quantiles"] = mip_q

        return {
            "label": label,
            "path": path,
            "is_mc": is_mc,
            "ok": True,
            "n_total": int(n_total),
            "n_sampled": int(n_kept + n_blinded),
            "n_blinded_zoneB": int(n_blinded),
            "n_cols": len(keys),
            "has_vetost": has_vetost,
            "branch_presence": branch_presence,
            "stats": stats,
            "wall_s": round(time.perf_counter() - t0, 3),
        }
    except Exception as exc:
        return {"label": label, "path": path, "is_mc": is_mc, "ok": False, "error": str(exc), "wall_s": round(time.perf_counter() - t0, 3)}


def _cross_check_unfilt_vs_back(pair: tuple[str, str, str]) -> dict[str, Any]:
    label, unfilt_uri, back_uri = pair
    u_path = resolve_local_eos_path(unfilt_uri)
    b_path = resolve_local_eos_path(back_uri)
    # Use the directly matching chunk file first (and at most 2 files capped at 250k entries)
    b_dir = Path(b_path).parent
    if os.path.exists(b_path):
        b_files = [b_path]
    elif b_dir.exists():
        b_files = sorted(str(p) for p in b_dir.glob("*.root"))[:2]
    else:
        b_files = [back_uri]
    u_nt = uproot.open(u_path if os.path.exists(u_path) else unfilt_uri)["nt"]
    u_arr, n_blind_u, _ = _compute_lead_and_blind_filter(u_nt, is_mc=False, max_entries=100000)

    u_map = {(int(r), int(e)): i for i, (r, e) in enumerate(zip(u_arr["run"], u_arr["eventID"]))}
    matches = []
    n_blind_b_tot = 0
    for bf in b_files:
        b_nt = uproot.open(bf)["nt"]
        b_arr, n_blind_b, _ = _compute_lead_and_blind_filter(b_nt, is_mc=False, max_entries=250000)
        n_blind_b_tot += n_blind_b
        for j, (r, e) in enumerate(zip(b_arr["run"], b_arr["eventID"])):
            idx = u_map.get((int(r), int(e)))
            if idx is not None:
                matches.append((idx, j, b_arr))
        if len(matches) >= 50000:
            break

    if not matches:
        return {"label": label, "n_matched": 0, "n_blind_u": n_blind_u, "n_blind_b": n_blind_b_tot}

    u_idx = np.array([m[0] for m in matches], dtype=np.int64)
    # All matches come from matching b_arr objects; handle multi-file cleanly
    max_diffs: dict[str, float] = {}
    for col in ("VetoNu0_bcidtime", "VetoNu0_triggertime", "VetoNu0_localtime", "VetoNu0_raw_charge",
                "Veto20_bcidtime", "Timing0_bcidtime", "Preshower0_bcidtime"):
        vals_u = u_arr[col][u_idx]
        vals_b = np.array([m[2][col][m[1]] for m in matches], dtype=np.float64)
        max_diffs[col] = float(np.nanmax(np.abs(vals_u - vals_b)))

    dx_vnu = np.array([u_arr["LeadXVetoNu"][m[0]] - m[2]["LeadXVetoNu"][m[1]] for m in matches])
    dy_vnu = np.array([u_arr["LeadYVetoNu"][m[0]] - m[2]["LeadYVetoNu"][m[1]] for m in matches])
    valid_trk = np.isfinite(dx_vnu) & np.isfinite(dy_vnu) & (np.abs(dx_vnu) < 1e4) & (np.abs(dy_vnu) < 1e4)
    dpz = np.array([u_arr["LeadPz0GeV"][m[0]] - m[2]["LeadPz0GeV"][m[1]] for m in matches])
    return {
        "label": label,
        "n_matched": len(matches),
        "n_blind_u": n_blind_u,
        "n_blind_b": n_blind_b_tot,
        "max_waveform_diffs": max_diffs,
        "n_valid_trk_matched": int(np.sum(valid_trk)),
        "track_dx_vetonu_median_mm": float(np.nanmedian(np.abs(dx_vnu[valid_trk]))) if np.any(valid_trk) else None,
        "track_dy_vetonu_median_mm": float(np.nanmedian(np.abs(dy_vnu[valid_trk]))) if np.any(valid_trk) else None,
        "track_dx_vetonu_p95_mm": float(np.nanquantile(np.abs(dx_vnu[valid_trk]), 0.95)) if np.any(valid_trk) else None,
        "track_dpz_rel_median": float(np.nanmedian(np.abs(dpz[valid_trk]) / np.maximum(1.0, np.array([u_arr["LeadPz0GeV"][m[0]] for k, m in enumerate(matches) if valid_trk[k]])))) if np.any(valid_trk) else None,
        "sample_dx_vnu": dx_vnu[valid_trk][:20000].tolist(),
        "sample_dt_vnu": (u_arr["VetoNu0_bcidtime"][u_idx] - np.array([m[2]["VetoNu0_bcidtime"][m[1]] for m in matches])).tolist()[:20000],
    }


def _audit_run16023_and_14647() -> dict[str, Any]:
    results = {}
    for run, uri in (
        (14647, "/eos/experiment/faser/phys/2024_unfilt/r0022-r0023/014647/Faser-Physics-014647-00000-00024-r0022-r0023-PHYS.root"),
        (16023, "/eos/experiment/faser/phys/2024_unfilt/r0022-r0023/016023/Faser-Physics-016023-00600-00624-r0022-r0023-PHYS.root"),
    ):
        nt = uproot.open(uri)["nt"]
        arr, n_blinded, _ = _compute_lead_and_blind_filter(nt, is_mc=False, max_entries=300000)
        one_trk = (
            (arr["distanceToCollidingBCID"] == 0)
            & (arr["longTracks"] == 1)
            & (arr["LeadPz0GeV"] > 30.0)
            & (arr["LeadNLayers"] >= 6)
            & (arr["LeadChi2NDF"] < 10.0)
            & (np.abs(arr["LeadXTrig"]) < 25.0)
            & (np.abs(arr["LeadYTrig"]) < 25.0)
        )
        ch_rows = []
        plot_payload = {}
        for ch in ("VetoNu0", "VetoNu1", "Veto10", "Veto11", "Veto20", "Veto21", "Timing0", "Timing2", "Preshower0", "Preshower1"):
            st = arr[f"{ch}_status"]
            valid_base = (st & ~528) == 0
            s0 = one_trk & valid_base & ((st & 512) == 0)
            s512 = one_trk & valid_base & ((st & 512) != 0)
            entry = {
                "run": run,
                "channel": ch,
                "n_status0": int(np.sum(s0)),
                "n_status512": int(np.sum(s512)),
                "loc_mean_s0": float(np.mean(arr[f"{ch}_localtime"][s0])) if np.any(s0) else None,
                "loc_mean_s512": float(np.mean(arr[f"{ch}_localtime"][s512])) if np.any(s512) else None,
                "trig_mean_s0": float(np.mean(arr[f"{ch}_triggertime"][s0])) if np.any(s0) else None,
                "trig_mean_s512": float(np.mean(arr[f"{ch}_triggertime"][s512])) if np.any(s512) else None,
                "bcid_cmean_s0": float((np.degrees(np.angle(np.mean(np.exp(1j * 2 * np.pi * arr[f"{ch}_bcidtime"][s0] / 25.0)))) % 360.0) * 25.0 / 360.0) if np.any(s0) else None,
                "bcid_cmean_s512": float((np.degrees(np.angle(np.mean(np.exp(1j * 2 * np.pi * arr[f"{ch}_bcidtime"][s512] / 25.0)))) % 360.0) * 25.0 / 360.0) if np.any(s512) else None,
            }
            ch_rows.append(entry)
            if run == 16023 and ch == "Veto20":
                plot_payload = {
                    "loc_s0": arr[f"{ch}_localtime"][s0][:5000].tolist(),
                    "loc_s512": arr[f"{ch}_localtime"][s512][:5000].tolist(),
                    "trig_s0": arr[f"{ch}_triggertime"][s0][:5000].tolist(),
                    "trig_s512": arr[f"{ch}_triggertime"][s512][:5000].tolist(),
                    "bcid_s0": arr[f"{ch}_bcidtime"][s0][:5000].tolist(),
                    "bcid_s512": arr[f"{ch}_bcidtime"][s512][:5000].tolist(),
                }
        # Also inspect Beam-1 non-colliding count in Run 16023
        b1_count = int(np.sum((arr["distanceToInboundB1"] == 0) & (np.abs(arr["distanceToCollidingBCID"]) > 1))) if "distanceToInboundB1" in arr else 0
        results[str(run)] = {"n_blinded_zoneB": n_blinded, "n_b1_noncoll": b1_count, "channels": ch_rows, "plot_payload": plot_payload}
    return results


def build_manifest_and_audit(workers: int) -> None:
    t_start = time.perf_counter()
    dq_manifest = json.loads(DQ_MANIFEST_PATH.read_text())
    file_config = yaml.safe_load(FILE_CONFIG_PATH.read_text())["runs"]
    grl_cfg = yaml.safe_load(GRL_FULL_PATH.read_text())

    # 1. Check Quirk EOS access and docs
    quirk_access = {"path": str(QUIRK_EOS_DIR), "accessible": False, "error": None}
    try:
        entries = list(QUIRK_EOS_DIR.iterdir())
        quirk_access["accessible"] = True
        quirk_access["n_entries"] = len(entries)
    except Exception as exc:
        quirk_access["error"] = f"{type(exc).__name__}: {exc}"

    docs_status = {}
    for doc_name in (
        "Quirks_analysis_internal_note_v5.pdf",
        "z156-xk5y.pdf",
        "Timing_calib_collab_meeting.pdf",
        "FASER Waveform Reconstruction and Energy Calibration.pdf",
        "FASER_PhysicsNtuples.pdf",
        "Slow_events_timing_postShowerCut.pdf",
        "Slow_events_Brian_display.pdf",
    ):
        p = REPO_DIR / "docs" / doc_name
        docs_status[doc_name] = {"exists": p.exists(), "bytes": p.stat().st_size if p.exists() else 0}

    # 2. Build Run 3 timing manifest across periods
    period_runs: dict[str, list[dict[str, Any]]] = {}
    all_runs_compact: dict[str, dict[str, Any]] = {}
    missing_input_runs: dict[str, dict[str, Any]] = {}
    for r_str, info in sorted(dq_manifest["runs"].items(), key=lambda kv: int(kv[0])):
        r_num = int(r_str)
        yr = int(info["year"])
        per = classify_data_period(yr, r_num)
        task_ids = info["tasks"]
        if not task_ids:
            missing_input_runs[r_str] = {
                "year": yr,
                "period": per,
                "lumi_pb_inverse": float(info["lumi_pb_inverse"]),
                "status": info.get("status", "missing_input"),
            }
            continue
        first_uri = dq_manifest["tasks"][task_ids[0]]["files"][0]
        reco_tag = "/".join(first_uri.split("/faser/phys/")[1].split("/")[:2])
        rec = {
            "year": yr,
            "period": per,
            "lumi_pb_inverse": float(info["lumi_pb_inverse"]),
            "reco_tag": reco_tag,
            "is_calonu": (15821 <= r_num <= 16924),
            "has_digitizer2": (r_num >= 15845),
            "has_veto11": (yr >= 2024),
            "has_preshower23": (yr >= 2025),
            "has_vetogm": (yr >= 2026),
            "has_native_reduced_charge": ("2025/p0013" not in reco_tag),
            "n_tasks": len(task_ids),
            "n_files": int(info["input_files"]),
            "input_bytes": int(info["input_bytes"]),
        }
        all_runs_compact[r_str] = rec
        period_runs.setdefault(per, []).append(rec)

    period_summary = []
    for per in ("2022", "2023", "2024_preCaloNu", "2024_CaloNu", "2024_postCaloNu", "2025", "2026"):
        rows = period_runs.get(per, [])
        period_summary.append({
            "period": per,
            "n_runs": len(rows),
            "lumi_fb_inverse": sum(r["lumi_pb_inverse"] for r in rows) / 1000.0,
            "n_tasks": sum(r["n_tasks"] for r in rows),
            "n_files": sum(r["n_files"] for r in rows),
            "input_tb": sum(r["input_bytes"] for r in rows) / 1e12,
            "reco_tags": ",".join(sorted({r["reco_tag"] for r in rows})),
        })

    # Inventory GENIE MC (all 69 runs in file_config) & FLUKA MC & 2024_cos
    genie_runs = {}
    for r_int, r_cfg in sorted(file_config.items()):
        if int(r_int) < 200000:
            continue
        dp = r_cfg["data_paths"][0]
        local_glob = resolve_local_eos_path(dp)
        files = sorted(glob.glob(local_glob))
        sample_name = Path(files[0]).name if files else ""
        genie_runs[str(r_int)] = {
            "glob": dp,
            "n_files": len(files),
            "bytes": sum(Path(f).stat().st_size for f in files),
            "is_calonu": (200137 <= int(r_int) <= 200147) or (200172 <= int(r_int) <= 200183),
            "sample_tag": sample_name,
        }

    fluka_samples = {}
    for camp, base in (("mc22_fluka", "/eos/experiment/faser/sim/mc22/fluka"),
                       ("mc24_fluka", "/eos/experiment/faser/sim/mc24/fluka")):
        for d in sorted(Path(base).iterdir()):
            if not d.is_dir() or "buggy" in d.name:
                continue
            phys_files = sorted(str(p) for p in d.rglob("*PHYS*.root"))
            if phys_files:
                fluka_samples[f"{camp}_{d.name}"] = {
                    "n_files": len(phys_files),
                    "bytes": sum(Path(f).stat().st_size for f in phys_files),
                    "sample_file": phys_files[0],
                }

    cos_2024_files = sorted(glob.glob("/eos/experiment/faser/phys/2024_cos/r0022-r0023/*/*.root"))

    # 3. Parallel schema & sentinel audit across representative files (28 workers)
    probe_tasks: list[tuple[str, str, bool, int]] = []
    # Pick 4 runs per data period from dq_manifest
    seen_per: dict[str, int] = {}
    for tid, t in dq_manifest["tasks"].items():
        per = classify_data_period(t["year"], t["run"])
        if per == "2025":
            tag = "2025_p0014" if "/p0014/" in t["files"][0] else "2025_p0013"
        else:
            tag = per
        if seen_per.get(tag, 0) < 3:
            for u in t["files"]:
                if u not in dq_manifest["config"]["unavailable_inputs"]:
                    probe_tasks.append((tag, u, False, 120000))
                    seen_per[tag] = seen_per.get(tag, 0) + 1
                    break
    # Add back, r0023, cos, GENIE (nominal + 4 alt physics lists), FLUKA
    probe_tasks.extend([
        ("2022_back", sorted(glob.glob("/eos/experiment/faser/data0/phys/2022_back/r0021/007918/*.root"))[0], False, 120000),
        ("2023_back", sorted(glob.glob("/eos/experiment/faser/data0/phys/2023_back/r0021/010555/*.root"))[0], False, 120000),
        ("2024_back_14647", sorted(glob.glob("/eos/experiment/faser/data0/phys/2024_back/r0022/014647/*.root"))[0], False, 120000),
        ("2024_back_16023", sorted(glob.glob("/eos/experiment/faser/data0/phys/2024_back/r0022/016023/*.root"))[0], False, 120000),
        ("2025_r0023", sorted(glob.glob("/eos/experiment/faser/phys/2025/r0023/020012/*.root"))[0], False, 120000),
        ("2024_cos", cos_2024_files[0], False, 120000),
        ("mc22_genie_200082", sorted(glob.glob(resolve_local_eos_path(file_config[200082]["data_paths"][0])))[0], True, 50000),
        ("mc24_genie_noCalo_200093", sorted(glob.glob(resolve_local_eos_path(file_config[200093]["data_paths"][0])))[0], True, 50000),
        ("mc24_genie_INCLXX_200164", sorted(glob.glob(resolve_local_eos_path(file_config[200164]["data_paths"][0])))[0], True, 50000),
        ("mc24_genie_CaloNu_200139", sorted(glob.glob(resolve_local_eos_path(file_config[200139]["data_paths"][0])))[0], True, 50000),
        ("mc24_genie_ENDFB8_200181", sorted(glob.glob(resolve_local_eos_path(file_config[200181]["data_paths"][0])))[0], True, 50000),
        ("mc22_fluka_210008", fluka_samples["mc22_fluka_210008"]["sample_file"], True, 100000),
        ("mc24_fluka_210020", fluka_samples["mc24_fluka_210020"]["sample_file"], True, 100000),
    ])

    unfilt_back_pairs = [
        ("2022_run7918",
         "root://eospublic.cern.ch//eos/experiment/faser/phys/2022_unfilt/r0021-r0023/007918/Faser-Physics-007918-00000-00024-r0023-PHYS.root",
         "/eos/experiment/faser/data0/phys/2022_back/r0021/007918/Faser-Physics-007918-00000-00049-PHYS.root"),
        ("2023_run10555",
         "root://eospublic.cern.ch//eos/experiment/faser/phys/2023_unfilt/r0021-r0023/010555/Faser-Physics-010555-00000-00024-r0023-PHYS.root",
         "/eos/experiment/faser/data0/phys/2023_back/r0021/010555/Faser-Physics-010555-00000-00049-PHYS.root"),
        ("2024_run14647",
         "root://eospublic.cern.ch//eos/experiment/faser/phys/2024_unfilt/r0022-r0023/014647/Faser-Physics-014647-00000-00024-r0022-r0023-PHYS.root",
         "/eos/experiment/faser/data0/phys/2024_back/r0022/014647/Faser-Physics-014647-00000-00049-r0022-PHYS.root"),
        ("2024_run16023",
         "root://eospublic.cern.ch//eos/experiment/faser/phys/2024_unfilt/r0022-r0023/016023/Faser-Physics-016023-00600-00624-r0022-r0023-PHYS.root",
         "/eos/experiment/faser/data0/phys/2024_back/r0022/016023/Faser-Physics-016023-00600-00649-r0022-PHYS.root"),
    ]

    with ProcessPoolExecutor(max_workers=workers) as pool:
        fut_probes = list(pool.map(_inspect_one_file, probe_tasks))
        fut_pairs = list(pool.map(_cross_check_unfilt_vs_back, unfilt_back_pairs))

    failed_probes = [r for r in fut_probes if not r.get("ok", False)]
    if failed_probes:
        for fr in failed_probes:
            print("PROBE FAILED:", fr, file=sys.stderr)
        raise RuntimeError(f"{len(failed_probes)} probe files failed schema audit")

    run_bench = _audit_run16023_and_14647()

    # Aggregate MIP thresholds (0.1% and 1% quantiles across periods)
    mip_summary: dict[str, dict[str, Any]] = {}
    for res in fut_probes:
        if not res.get("ok") or res["is_mc"]:
            continue
        lbl = res["label"]
        for ch, qd in res.get("stats", {}).get("mip_quantiles", {}).items():
            mip_summary.setdefault(ch, {})[lbl] = qd

    # Save outputs
    out_dir = REPO_DIR / "workbook/stage211_timing_t0"
    out_dir.mkdir(parents=True, exist_ok=True)
    calib_dir = REPO_DIR / "AnalysisZipFramework/config/timing_calib"
    calib_dir.mkdir(parents=True, exist_ok=True)

    manifest_out = {
        "schema_version": 1,
        "source_dq_manifest": str(DQ_MANIFEST_PATH),
        "grl_config": str(GRL_FULL_PATH.relative_to(REPO_DIR)),
        "grl_jsons": grl_cfg["grl_jsons"],
        "grl_csvs": grl_cfg["grl_csvs"],
        "blinding_policy": {
            "mode": "orthogonal_SR_ZoneB",
            "kinematic_sr": "longTracks>0 && Veto20_charge>40 && Veto21_charge>40 && hitsTiming && Preshower0_charge>2.5 && Preshower1_charge>2.5 && LeadTrack_pz0>100 && LeadTrack_nLayers>=7 && LeadTrack_nDoF>=9 && LeadTrack_Chi2_NDF<15 && LeadTrack_r_atMaxRadius<95 && LeadTrack_rIFT<95 && LeadTrack_rVetoNu<120 && LeadTrack_Theta<25",
            "zone_b": "VetoNu0_charge>=30 || VetoNu1_charge>=30 (raw or reduced)",
            "unblinded_dt_max_ns": 1.5,
        },
        "scintillator_z_m": QUIRK_TABLE4_Z_M,
        "mip_raw_charge_thresholds_pc": {
            **QUIRK_TABLE5_MIP_THRESHOLDS_PC,
            "Veto11": 59.0,
            "Preshower2": 0.90,
            "Preshower3": 0.60,
            "Muon0": 35.0,
            "Muon1": 35.0,
        },
        "periods": period_summary,
        "runs": all_runs_compact,
        "missing_input_runs": missing_input_runs,
        "genie_mc_runs": genie_runs,
        "fluka_mc_datasets": {k: {"n_files": v["n_files"], "bytes": v["bytes"]} for k, v in fluka_samples.items()},
        "cosmic_2024_r0022_r0023_files": len(cos_2024_files),
    }
    (calib_dir / "run3_timing_manifest.json").write_text(json.dumps(manifest_out, indent=2) + "\n")

    # Write TSV tables
    with open(out_dir / "dataset_periods_summary.tsv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["period", "n_runs", "lumi_fb_inverse", "n_tasks", "n_files", "input_tb", "reco_tags"], delimiter="\t")
        w.writeheader()
        for r in period_summary:
            w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in r.items()})

    with open(out_dir / "channel_schema_sentinels.tsv", "w", newline="") as f:
        cols = ["label", "is_mc", "n_total", "n_cols", "n_blinded_zoneB", "has_reduced", "has_veto11", "has_calonu", "has_ps23", "has_vetogm", "has_muon",
                "has_vetost", "vnu0_bcid_present", "vnu0_time_legacy", "vnu0_bcid_zero", "vnu0_trig_zero", "vnu0_loc_zero", "v20_status512_frac", "v20_overflow_frac", "wall_s"]
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t")
        w.writeheader()
        for r in fut_probes:
            bp = r["branch_presence"]
            st = r["stats"].get("VetoNu0", {})
            v20 = r["stats"].get("Veto20", {})
            w.writerow({
                "label": r["label"],
                "is_mc": r["is_mc"],
                "n_total": r["n_total"],
                "n_cols": r["n_cols"],
                "n_blinded_zoneB": r["n_blinded_zoneB"],
                "has_reduced": bp["VetoNu0_reduced_charge"],
                "has_veto11": bp["Veto11_raw_charge"],
                "has_calonu": bp["CaloNu0_raw_charge"],
                "has_ps23": bp["Preshower2_raw_charge"],
                "has_vetogm": bp["VetoGm0_raw_charge"],
                "has_muon": bp["Muon0_raw_charge"],
                "has_vetost": r["has_vetost"],
                "vnu0_bcid_present": bp["VetoNu0_bcidtime"],
                "vnu0_time_legacy": bp["VetoNu0_time_legacy"],
                "vnu0_bcid_zero": f"{st.get('bcid_zero_frac', -1):.4f}",
                "vnu0_trig_zero": f"{st.get('trig_zero_frac', -1):.4f}",
                "vnu0_loc_zero": f"{st.get('loc_zero_frac', -1):.4f}",
                "v20_status512_frac": f"{v20.get('status_512_frac', -1):.4f}",
                "v20_overflow_frac": f"{v20.get('status_4_overflow_frac', -1):.4f}",
                "wall_s": r["wall_s"],
            })

    with open(out_dir / "unfilt_vs_back_crosscheck.tsv", "w", newline="") as f:
        cols = ["label", "n_matched", "n_blind_u", "n_blind_b", "max_d_vnu0_bcid", "max_d_vnu0_trig", "max_d_vnu0_rawq",
                "n_valid_trk_matched", "med_abs_dx_vetonu_mm", "med_abs_dy_vetonu_mm", "p95_abs_dx_vetonu_mm"]
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t")
        w.writeheader()
        for p in fut_pairs:
            md = p.get("max_waveform_diffs", {})
            w.writerow({
                "label": p["label"],
                "n_matched": p["n_matched"],
                "n_blind_u": p["n_blind_u"],
                "n_blind_b": p["n_blind_b"],
                "max_d_vnu0_bcid": f"{md.get('VetoNu0_bcidtime', -1):.6g}",
                "max_d_vnu0_trig": f"{md.get('VetoNu0_triggertime', -1):.6g}",
                "max_d_vnu0_rawq": f"{md.get('VetoNu0_raw_charge', -1):.6g}",
                "n_valid_trk_matched": p.get("n_valid_trk_matched", 0),
                "med_abs_dx_vetonu_mm": f"{p.get('track_dx_vetonu_median_mm', -1):.4f}",
                "med_abs_dy_vetonu_mm": f"{p.get('track_dy_vetonu_median_mm', -1):.4f}",
                "p95_abs_dx_vetonu_mm": f"{p.get('track_dx_vetonu_p95_mm', -1):.4f}",
            })

    with open(out_dir / "run16023_digitizer2_check.tsv", "w", newline="") as f:
        cols = ["run", "channel", "n_status0", "n_status512", "loc_mean_s0", "loc_mean_s512", "trig_mean_s0", "trig_mean_s512", "bcid_cmean_s0", "bcid_cmean_s512"]
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t")
        w.writeheader()
        for r_key in ("14647", "16023"):
            for row in run_bench[r_key]["channels"]:
                w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else ("" if v is None else v)) for k, v in row.items()})

    with open(out_dir / "mip_thresholds_audit.tsv", "w", newline="") as f:
        cols = ["channel", "period_label", "n_clean_1trk", "q001_pC", "q010_pC", "q050_pC", "q500_pC"]
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t")
        w.writeheader()
        for ch, per_dict in sorted(mip_summary.items()):
            for lbl, qd in sorted(per_dict.items()):
                w.writerow({
                    "channel": ch,
                    "period_label": lbl,
                    "n_clean_1trk": qd["n"],
                    "q001_pC": f"{qd['q001']:.3f}",
                    "q010_pC": f"{qd['q01']:.3f}",
                    "q050_pC": f"{qd['q05']:.3f}",
                    "q500_pC": f"{qd['q50']:.3f}",
                })

    # Plot 1: Run 16023 digitizer 2 status & 512 verification
    pp = run_bench["16023"]["plot_payload"]
    if pp and pp["loc_s0"] and pp["loc_s512"]:
        fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), dpi=150)
        for ax, key_s0, key_s512, xlabel, rng in (
            (axes[0], "loc_s0", "loc_s512", "Veto20_localtime [ns]", None),
            (axes[1], "trig_s0", "trig_s512", "Veto20_triggertime [ns]", None),
            (axes[2], "bcid_s0", "bcid_s512", "Veto20_bcidtime [ns]", (0, 25)),
        ):
            v0 = np.asarray(pp[key_s0])
            v1 = np.asarray(pp[key_s512])
            if rng is None:
                lo = min(np.quantile(v0, 0.01), np.quantile(v1, 0.01)) - 2
                hi = max(np.quantile(v0, 0.99), np.quantile(v1, 0.99)) + 2
                rng = (lo, hi)
            bins = np.linspace(rng[0], rng[1], 80)
            ax.hist(v0, bins=bins, density=True, histtype="step", lw=1.8, label=f"status & 512 == 0 (n={len(v0)})")
            ax.hist(v1, bins=bins, density=True, histtype="step", lw=1.8, linestyle="--", label=f"status & 512 != 0 (n={len(v1)})")
            ax.set_xlabel(xlabel)
            ax.set_ylabel("Density")
            ax.legend(fontsize=8)
            ax.grid(alpha=0.25)
        fig.suptitle("Run 16023 (CaloNu): Second-Digitizer 16 ns Shift Audit (Veto20, |x,y|<25 mm)", fontsize=12)
        fig.tight_layout()
        fig.savefig(out_dir / "fig1_run16023_digitizer2_shift.png")
        plt.close(fig)

    # Plot 2: unfilt vs back cross-check
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), dpi=150)
    for p in fut_pairs:
        if p.get("sample_dx_vnu"):
            dx = np.asarray(p["sample_dx_vnu"])
            axes[0].hist(dx[np.abs(dx) < 25], bins=100, range=(-25, 25), density=True, histtype="step", lw=1.5, label=p["label"])
            dt = np.asarray(p["sample_dt_vnu"])
            axes[1].hist(dt, bins=50, range=(-0.01, 0.01), density=True, histtype="step", lw=1.5, label=p["label"])
    axes[0].set_xlabel(r"$\Delta X_{\mathrm{VetoNu}}$ (unfilt - back) [mm]")
    axes[0].set_ylabel("Density")
    axes[0].set_yscale("log")
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.25)
    axes[1].set_xlabel(r"$\Delta t_{\mathrm{bcid}}$ (unfilt - back) [ns]")
    axes[1].set_ylabel("Density")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.25)
    fig.suptitle("Cross-Production Consistency: Official unfilt (r0022/r0023) vs back (r0021/r0022)", fontsize=12)
    fig.tight_layout()
    fig.savefig(out_dir / "fig2_unfilt_vs_back_crosscheck.png")
    plt.close(fig)

    # Plot 3: MIP 0.1% quantile summary vs Quirk Table 5 thresholds
    fig, ax = plt.subplots(figsize=(12, 5.0), dpi=150)
    chs = [c for c in ("VetoNu0", "VetoNu1", "Veto10", "Veto11", "Veto20", "Veto21",
                       "Timing01", "Timing23", "Preshower0", "Preshower1", "Preshower2", "Preshower3",
                       "Muon0", "Muon1") if c in mip_summary]
    x_pos = np.arange(len(chs))
    q001_vals = [np.median([v["q001"] for v in mip_summary[c].values()]) for c in chs]
    q50_vals = [np.median([v["q50"] for v in mip_summary[c].values()]) for c in chs]
    ref_vals = [manifest_out["mip_raw_charge_thresholds_pc"].get(c, np.nan) for c in chs]
    ax.scatter(x_pos, q50_vals, marker="o", s=55, label="Measured 1-track muon median raw_charge [pC]")
    ax.scatter(x_pos, q001_vals, marker="v", s=65, label="Measured 0.1% quantile [pC]")
    ax.scatter(x_pos, ref_vals, marker="_", s=220, linewidths=2.5, color="red", label="Adopted MIP threshold (Quirk Table 5 / T0 new ch)")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(chs, rotation=30, ha="right")
    ax.set_yscale("log")
    ax.set_ylabel("Raw charge [pC]")
    ax.set_title("Run 3 Single-Track Muon Raw Charge Median vs 0.1% Quantile & MIP Thresholds")
    ax.grid(alpha=0.25, which="both")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(out_dir / "fig3_mip_raw_charge_thresholds.png")
    plt.close(fig)

    # Save JSON summary without large raw arrays
    for r in ("14647", "16023"):
        run_bench[r].pop("plot_payload", None)
    for p in fut_pairs:
        p.pop("sample_dx_vnu", None)
        p.pop("sample_dt_vnu", None)

    audit_summary = {
        "wall_s": round(time.perf_counter() - t_start, 3),
        "workers": workers,
        "quirk_eos_access": quirk_access,
        "docs_status": docs_status,
        "period_summary": period_summary,
        "probe_results": fut_probes,
        "unfilt_vs_back": fut_pairs,
        "run_benchmarks": run_bench,
        "mip_summary": mip_summary,
        "manifest_bytes": (calib_dir / "run3_timing_manifest.json").stat().st_size,
    }
    (out_dir / "audit_summary.json").write_text(json.dumps(audit_summary, indent=2) + "\n")
    print(f"T0 audit finished in {audit_summary['wall_s']} s; manifest bytes={audit_summary['manifest_bytes']}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=28)
    args = parser.parse_args()
    build_manifest_and_audit(args.workers)
