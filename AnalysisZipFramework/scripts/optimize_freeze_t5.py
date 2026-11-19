#!/usr/bin/env python3
"""
Stage T5 (Stage 216): Blind Working-Point Optimization & Freeze (S0 vs S1 vs S2 vs S3),
Full 30-Bin 2D (y_nu, -L/E_nu) & 6D Systematic Response Closure, and Energy-ML (F7) Coupling.

Strict blinding guarantee:
  Reads sharded outputs from t5_scanner (854 Data, 66 FLUKA, 107 GENIE), asserts ZERO
  collision Data SR-ZoneB leakage across every shard, optimizes & freezes working points strictly
  from GENIE + FLUKA + unblinded Data control regions (CR-Geom, CR-EdgeVN, Neg-SR, NonColl).

Hardware acceleration:
  - 28-process ProcessPoolExecutor ('spawn') for shard loading with automatic xrdcp fallback
  - Vectorized NumPy/SciPy Fisher & L-BFGS-B profiled-likelihood covariance across 30 bins
  - 28-thread CPU XGBoost (device='cpu', tree_method='hist', nthread=28) for S3 & F7 energy regression
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import csv
import glob
import io
import json
import math
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import awkward as ak
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import optimize
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
import uproot
import xgboost as xgb

REPO_DIR = Path("/eos/home-x/xcheng/FASER/nu_muAnalysis")
MANIFEST_PATH = REPO_DIR / "AnalysisZipFramework/config/timing_calib/run3_timing_manifest.json"
EOS_BASE = "/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/timing_stage216"
OUT_DIR = REPO_DIR / "workbook/stage216_timing_t5"

PERIODS = ["2022", "2023", "2024_preCaloNu", "2024_CaloNu", "2024_postCaloNu", "2025", "2026"]
DEAD_VETONU_RUNS = {20667, 20668, 20675, 20677}

# Region enums matching t5_scanner.cxx
REG_KIN_SR = 1
REG_CR_GEOM_OUTER = 2
REG_CR_GEOM_HITHETA = 3
REG_CR_EDGE_VN = 4
REG_NONCOLL_B1 = 5
REG_NONCOLL_UNPAIRED = 6
REG_NONCOLL_EMPTY = 7
REG_RELAXED_SR_ONLY = 9

# Flag bitmasks matching t5_scanner.cxx
FLAG_HAS_REDQ = 1 << 0
FLAG_PHYS_TRIG = 1 << 1
FLAG_DOWN_OK = 1 << 2
FLAG_DOWNA_VALID = 1 << 3
FLAG_DOWNB_VALID = 1 << 4
FLAG_DOWNA_GE2 = 1 << 5
FLAG_DOWNB_GE2 = 1 << 6
FLAG_VN0_VALID = 1 << 7
FLAG_VN1_VALID = 1 << 8
FLAG_ZONEA_RED = 1 << 9
FLAG_ZONEA_RAW = 1 << 10
FLAG_ZONEA_ERA = 1 << 11
FLAG_VN0_ACT_ERA = 1 << 12
FLAG_VN1_ACT_ERA = 1 << 13
FLAG_PASS_LEAD_TRK = 1 << 14
FLAG_PASS_NOM_SR = 1 << 15

# TH3D / TH2D grid metadata matching t5_scanner.cxx
Q_CAP_NAMES = ["allQ", "Qlt180", "Qlt150", "Qlt130"]
Q_CAP_VALS = [1e9, 180.0, 150.0, 130.0]
Q_BIN_COUNT_FOR_CAP = {1e9: 5, 180.0: 4, 150.0: 3, 130.0: 2}
W_CAP_MAP = {19.5: "w19p5", 16.0: "w16p0", 12.0: "w12p0"}

G4_MODELS = [
    "FTFP_BERT",
    "FTF_BIC",
    "FTFP_INCLXX",
    "FTFP_BERT_HP_JEFF33",
    "FTFP_BERT_HP_ENDFB8",
]

GEOM_TRIPLETS: dict[str, dict[str, tuple[int, int, int]]] = {
    "2022_2023": {
        "FTFP_BERT": (200082, 200083, 200089),
        "FTF_BIC": (200104, 200105, 200106),
        "FTFP_INCLXX": (200107, 200108, 200109),
        "FTFP_BERT_HP_JEFF33": (200110, 200111, 200112),
        "FTFP_BERT_HP_ENDFB8": (200113, 200114, 200115),
    },
    "2024_noCaloNu": {
        "FTFP_BERT": (200093, 200094, 200100),
        "FTF_BIC": (200160, 200161, 200162),
        "FTFP_INCLXX": (200163, 200164, 200165),
        "FTFP_BERT_HP_JEFF33": (200166, 200167, 200168),
        "FTFP_BERT_HP_ENDFB8": (200169, 200170, 200171),
    },
    "2024_CaloNu": {
        "FTFP_BERT": (200139, 200140, 200146),
        "FTF_BIC": (200172, 200173, 200174),
        "FTFP_INCLXX": (200175, 200176, 200177),
        "FTFP_BERT_HP_JEFF33": (200178, 200179, 200180),
        "FTFP_BERT_HP_ENDFB8": (200181, 200182, 200183),
    },
}

FLUX_VARIANTS: dict[str, dict[str, tuple[int, int, int]]] = {
    "2022_2023": {
        "EPOS_central": (200082, 200083, 200089),
        "SIBYLL": (200080, 200081, 200089),
        "QGSJET": (200084, 200085, 200089),
        "PythiaForward": (200086, 200087, 200089),
        "CharmMin": (200082, 200083, 200088),
        "CharmMax": (200082, 200083, 200090),
    },
    "2024_noCaloNu": {
        "EPOS_central": (200093, 200094, 200100),
        "SIBYLL": (200091, 200092, 200100),
        "QGSJET": (200095, 200096, 200100),
        "PythiaForward": (200097, 200098, 200100),
        "CharmMin": (200093, 200094, 200099),
        "CharmMax": (200093, 200094, 200101),
    },
    "2024_CaloNu": {
        "EPOS_central": (200139, 200140, 200146),
        "SIBYLL": (200137, 200138, 200146),
        "QGSJET": (200141, 200142, 200146),
        "PythiaForward": (200143, 200144, 200146),
        "CharmMin": (200139, 200140, 200145),
        "CharmMax": (200139, 200140, 200147),
    },
}

RUN3_GEOM_LUMI_FB = {
    "2022_2023": 66.045139,
    "2024_noCaloNu": 199.841462,
    "2024_CaloNu": 70.033105,
}
RUN22_24_GEOM_LUMI_FB = {
    "2022_2023": 66.045139,
    "2024_noCaloNu": 50.096985,
    "2024_CaloNu": 70.033105,
}

# PRD Eq. 6-7 binning
Y_EDGES = np.array([8.5, 9.0, 9.25, 9.5, 10.0, 99.0], dtype=np.float64)
Y_LABELS = ["8.5-9.0", "9.0-9.25", "9.25-9.5", "9.5-10.0", "10.0-inf"]
QOP_EDGES = np.array([-1.0 / 100.0, -1.0 / 300.0, -1.0 / 600.0, -1.0 / 1000.0, +1.0 / 1000.0, +1.0 / 300.0, +1.0 / 100.0], dtype=np.float64)
QOP_LABELS = ["[-1/100,-1/300)", "[-1/300,-1/600)", "[-1/600,-1/1000)", "[-1/1000,+1/1000)", "[+1/1000,+1/300)", "[+1/300,+1/100]"]

# 10 audited S3 Zone-B observables (strictly leak-free)
S3_FEATURES = [
    "q0_raw", "q1_raw", "dt0", "dt1", "sig_dt0", "sig_dt1",
    "w0", "w1", "chi2_ndof_down", "r_vn",
]
F7_VETONU_INDICES = [24, 25, 35, 36]  # VetoNu0_raw, VetoNu1_raw, VetoNu0_reduced, VetoNu1_reduced


def write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if not rows:
        path.write_text("")
        return
    if fieldnames is None:
        fieldnames = list(dict.fromkeys(k for r in rows for k in r.keys()))
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _list_shards(mode: str) -> list[str]:
    local_dir = Path(EOS_BASE) / mode
    local_files = sorted(glob.glob(str(local_dir / f"{mode}_*.root")))
    if local_files:
        return local_files
    proc = subprocess.run(
        ["xrdfs", "eoshome-x.cern.ch", "ls", f"{EOS_BASE}/{mode}"],
        capture_output=True, text=True, check=True,
    )
    return sorted(f"root://eoshome-x.cern.ch/{line.strip()}" for line in proc.stdout.splitlines() if line.strip().endswith(".root"))


def _open_shard_bytes(path: str) -> io.BytesIO:
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            if attempt >= 2 or path.startswith("root://"):
                xrd_url = path if path.startswith("root://") else f"root://eoshome-x.cern.ch/{path}"
                raw = subprocess.check_output(["xrdcp", "-s", xrd_url, "-"])
                return io.BytesIO(raw)
            return io.BytesIO(Path(path).read_bytes())
        except Exception as exc:
            last_err = exc
            time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(f"Failed reading {path}: {last_err}") from last_err


def _reduce_data_fluka_shard(args: tuple[str, bool]) -> dict[str, Any]:
    path, is_data = args
    with uproot.open(_open_shard_bytes(path)) as f:
        rs_raw = f["t5_run_summary"].arrays(library="np")
        hists: dict[str, dict[str, tuple[np.ndarray, Any]]] = {}
        for k in f.keys():
            kc = k.split(";")[0]
            if kc.startswith("period_") and "/" in kc:
                pdir, hname = kc.split("/", 1)
                per = pdir.replace("period_", "", 1)
                np_out = f[kc].to_numpy()
                hists.setdefault(per, {})[hname] = (np_out[0].astype(np.float64), np_out[1:])
        bt = f["t5_bkg_events"].arrays(library="np")

    if is_data and len(bt["run"]) > 0:
        m_sr = bt["region"] == REG_KIN_SR
        if np.any(m_sr):
            has_red = (bt["flags"][m_sr] & FLAG_HAS_REDQ) != 0
            act0 = (bt["q0_raw"][m_sr] >= 30.0) | (has_red & (bt["q0_red"][m_sr] >= 30.0))
            act1 = (bt["q1_raw"][m_sr] >= 30.0) | (has_red & (bt["q1_red"][m_sr] >= 30.0))
            bad = ((act0 & (~np.isfinite(bt["dt0"][m_sr]) | (bt["dt0"][m_sr] > 1.5))) |
                   (act1 & (~np.isfinite(bt["dt1"][m_sr]) | (bt["dt1"][m_sr] > 1.5))))
            if np.any(bad):
                raise RuntimeError(f"BLINDING VIOLATION in Data shard {path}: {int(bad.sum())} events")

    # Exclude dead VetoNu 2025 runs for Data
    if is_data:
        dead_rs = np.isin(rs_raw["run"], list(DEAD_VETONU_RUNS))
        rs = {k: rs_raw[k][~dead_rs] for k in rs_raw}
        keep_ev = ~np.isin(bt["run"], list(DEAD_VETONU_RUNS)) if len(bt["run"]) > 0 else np.zeros(0, dtype=bool)
        events = {k: bt[k][keep_ev] for k in bt}
    else:
        rs = rs_raw
        events = bt

    # Decode strings & aggregate period scalar summaries
    pers = [p.decode() if isinstance(p, (bytes, np.bytes_)) else str(p) for p in rs["period"]]
    per_agg: dict[str, dict[str, float]] = {}
    for i, per in enumerate(pers):
        d = per_agg.setdefault(per, {})
        for k in rs:
            if k in ("run", "period", "is_mc", "has_reduced_charge"):
                continue
            d[k] = d.get(k, 0.0) + float(rs[k][i])
        d["n_runs"] = d.get("n_runs", 0.0) + 1.0

    # Drop edges tuple inside per-shard merge after validation, keep only values + first edges outside
    return {"per_agg": per_agg, "hists": hists, "events": events}


def _reduce_genie_shard(path: str) -> dict[str, Any]:
    with uproot.open(_open_shard_bytes(path)) as f:
        rs = f["t5_run_summary"].arrays(library="np")
        td = f["t5_truth_denoms"].arrays(library="ak")
        mc = f["t5_mc_events"].arrays(library="ak")
    mc_np = {k: ak.to_numpy(mc[k]) for k in mc.fields}
    td_np = {k: ak.to_numpy(td[k]) for k in td.fields}
    rs_np = {k: rs[k] for k in rs}
    return {"rs": rs_np, "td": td_np, "mc": mc_np}


def load_all_t5_shards(workers: int) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], float]:
    t0 = time.perf_counter()
    ctx = multiprocessing.get_context("spawn")

    data_paths = _list_shards("data")
    fluka_paths = _list_shards("fluka")
    genie_paths = _list_shards("genie")
    print(f"[Load] Shards found: data={len(data_paths)}, fluka={len(fluka_paths)}, genie={len(genie_paths)}", flush=True)

    def _merge_df_results(res_list: list[dict[str, Any]]) -> dict[str, Any]:
        per_agg: dict[str, dict[str, float]] = {}
        hists: dict[str, dict[str, np.ndarray]] = {}
        hist_edges: dict[str, Any] = {}
        chunks: list[dict[str, np.ndarray]] = []
        for r in res_list:
            for per, vals in r["per_agg"].items():
                tgt = per_agg.setdefault(per, {})
                for k, v in vals.items():
                    tgt[k] = tgt.get(k, 0.0) + v
            for per, hm in r["hists"].items():
                pt = hists.setdefault(per, {})
                for hn, (arr, edges) in hm.items():
                    if hn not in hist_edges:
                        hist_edges[hn] = tuple(np.asarray(e, dtype=np.float64) for e in edges)
                    if hn not in pt:
                        pt[hn] = arr.copy()
                    else:
                        pt[hn] += arr
            if len(r["events"]["run"]) > 0:
                chunks.append(r["events"])
        events = {k: np.concatenate([c[k] for c in chunks], axis=0) for k in chunks[0]} if chunks else {}
        return {"per_agg": per_agg, "hists": hists, "edges": hist_edges, "events": events}

    with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as ex:
        data_res = list(ex.map(_reduce_data_fluka_shard, [(p, True) for p in data_paths], chunksize=8))
        fluka_res = list(ex.map(_reduce_data_fluka_shard, [(p, False) for p in fluka_paths], chunksize=4))
        genie_res = list(ex.map(_reduce_genie_shard, genie_paths, chunksize=4))

    data_agg = _merge_df_results(data_res)
    fluka_agg = _merge_df_results(fluka_res)

    # Merge GENIE truth denoms per run & events
    truth_by_run: dict[int, dict[str, np.ndarray]] = {}
    run_sum_genie: dict[int, dict[str, int]] = {}
    mc_chunks: list[dict[str, np.ndarray]] = []
    for g in genie_res:
        rs = g["rs"]
        for i in range(len(rs["run"])):
            rn = int(rs["run"][i])
            dst = run_sum_genie.setdefault(rn, {"n_total": 0, "n_fid_box": 0, "n_fid_lead": 0})
            dst["n_total"] += int(rs["n_total"][i])
            dst["n_fid_box"] += int(rs["n_fid_box"][i])
            dst["n_fid_lead"] += int(rs["n_fid_lead"][i])
        td = g["td"]
        for i in range(len(td["run"])):
            rn = int(td["run"][i])
            if rn not in truth_by_run:
                truth_by_run[rn] = {k: td[k][i].astype(np.float64).copy() for k in td if k != "run"}
            else:
                for k in td:
                    if k != "run":
                        truth_by_run[rn][k] += td[k][i].astype(np.float64)
        if len(g["mc"]["run"]) > 0:
            mc_chunks.append(g["mc"])

    genie_events = {k: np.concatenate([c[k] for c in mc_chunks], axis=0) for k in mc_chunks[0]}
    genie_agg = {"run_sum": run_sum_genie, "truth": truth_by_run, "events": genie_events}
    wall_s = time.perf_counter() - t0
    print(f"[Load] Finished all {len(data_paths)+len(fluka_paths)+len(genie_paths)} shards in {wall_s:.2f} s "
          f"(Data bkg={len(data_agg['events'].get('run', []))}, FLUKA={len(fluka_agg['events'].get('run', []))}, GENIE={len(genie_events['run'])})", flush=True)
    return data_agg, fluka_agg, genie_agg, wall_s


# ---------------------------------------------------------------------------
# Vectorized selection evaluator for Data/FLUKA bkg trees and GENIE MC tree
# ---------------------------------------------------------------------------
def _zone_a_mask(ev: dict[str, np.ndarray], mode: str = "era") -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """mode: 'era' (red30 whenever Aux or native reduced charge is available, raw40 fallback otherwise),
       'red30', 'raw40', or variations '_thr_m2' / '_thr_p2' for VetoNu +-2 pC charge threshold systematic."""
    has_red = (ev["flags"] & FLAG_HAS_REDQ) != 0
    thr_red = 30.0
    thr_raw = 40.0
    if mode.endswith("_m2"):
        thr_red = 28.0
        thr_raw = 40.0 * (28.0 / 30.0)
        mode = mode[:-3]
    elif mode.endswith("_p2"):
        thr_red = 32.0
        thr_raw = 40.0 * (32.0 / 30.0)
        mode = mode[:-3]

    if mode == "raw40":
        act0 = ev["q0_raw"] >= thr_raw
        act1 = ev["q1_raw"] >= thr_raw
    elif mode == "red30":
        act0 = np.where((ev["q0_red"] >= 0.0), ev["q0_red"] >= thr_red, ev["q0_raw"] >= thr_raw)
        act1 = np.where((ev["q1_red"] >= 0.0), ev["q1_red"] >= thr_red, ev["q1_raw"] >= thr_raw)
    else:  # 'era'
        act0 = np.where(has_red & (ev["q0_red"] >= 0.0), ev["q0_red"] >= thr_red, ev["q0_raw"] >= thr_raw)
        act1 = np.where(has_red & (ev["q1_red"] >= 0.0), ev["q1_red"] >= thr_red, ev["q1_raw"] >= thr_raw)
    return act0, act1, act0.astype(np.int8) + act1.astype(np.int8)


def eval_wp_mask(
    ev: dict[str, np.ndarray],
    wp: dict[str, Any],
    dt0_override: np.ndarray | None = None,
    dt1_override: np.ndarray | None = None,
    pull0_override: np.ndarray | None = None,
    pull1_override: np.ndarray | None = None,
    dchi2_override: np.ndarray | None = None,
    za_mode: str = "era",
    down_chi2_max: float = 10.0,
    q2_shift: float = 0.0,
    ignore_period_filter: bool = False,
) -> dict[str, np.ndarray]:
    """Evaluate S0 / S1 / S2 / hybrid masks cleanly on either Data/FLUKA or GENIE arrays."""
    act0, act1, n_act = _zone_a_mask(ev, mode=za_mode)
    s0 = n_act == 0

    dt0 = ev["dt0"] if dt0_override is None else dt0_override
    dt1 = ev["dt1"] if dt1_override is None else dt1_override
    pull0 = ev["pull0"] if pull0_override is None else pull0_override
    pull1 = ev["pull1"] if pull1_override is None else pull1_override
    dchi2 = ev["dchi2_back"] if dchi2_override is None else dchi2_override

    wmax = float(wp.get("wmax", 12.0))
    t0_max = float(wp.get("t0_down_max", 2.5))
    c2_max = float(wp.get("down_chi2_max", down_chi2_max))
    flags = ev["flags"]

    down_ok = ((flags & FLAG_DOWNA_VALID) != 0) | ((flags & FLAG_DOWNB_VALID) != 0)
    # Use raw down.chi2_ndof_down + t0_down for systematic chi2 variations!
    down_ok = (np.isfinite(ev["t0_down"]) & (np.abs(ev["t0_down"]) < t0_max) &
               np.isfinite(ev["chi2_ndof_down"]) & (ev["chi2_ndof_down"] < c2_max))
    # Ensure at least 2 downstream stations via original FLAG_DOWN_OK when c2_max <= 10, else fallback cleanly
    if c2_max <= 10.0:
        down_ok = down_ok & ((flags & FLAG_DOWN_OK) != 0)

    vn0_ok = ((flags & FLAG_VN0_VALID) != 0) & np.isfinite(dt0) & (ev["w0"] > 1.5) & (ev["w0"] < wmax)
    vn1_ok = ((flags & FLAG_VN1_VALID) != 0) & np.isfinite(dt1) & (ev["w1"] > 1.5) & (ev["w1"] < wmax)
    act_wave_ok = (~act0 | vn0_ok) & (~act1 | vn1_ok)

    q2hit_max = float(wp.get("q2hit_max", 180.0)) + q2_shift
    qmax = np.maximum(np.nan_to_num(ev["q0_raw"], nan=0.0), np.nan_to_num(ev["q1_raw"], nan=0.0))
    q2_ok = qmax < q2hit_max
    if wp.get("allow_2hit", True) is False:
        q2_ok = np.zeros_like(q2_ok, dtype=bool)
    elif wp.get("drop_2526_2hit", False) and not ignore_period_filter:
        is_data_2526 = (ev["run"] >= 18500) & (ev["run"] < 100000)
        is_mc_no_cn = ((ev["run"] >= 200091) & (ev["run"] <= 200101)) | ((ev["run"] >= 200160) & (ev["run"] <= 200171))
        mc_hash = (np.abs(ev["eventID"].astype(np.int64)) * np.int64(2654435761)) & np.int64(0xFFFF)
        is_mc_2526 = is_mc_no_cn & (mc_hash >= int((RUN22_24_GEOM_LUMI_FB["2024_noCaloNu"] / RUN3_GEOM_LUMI_FB["2024_noCaloNu"]) * 65536))
        q2_ok = q2_ok & (~(is_data_2526 | is_mc_2526))

    tmax = float(wp.get("tmax", 16.0))
    strategy = wp["strategy"]

    if strategy == "S0":
        zb = np.zeros_like(s0, dtype=bool)
        z2 = zb
        z10 = zb
        z11 = zb
    elif strategy == "S1":
        t2 = float(wp["t2"])
        t1 = float(wp["t1"])
        z2 = (n_act == 2) & down_ok & act_wave_ok & q2_ok & (dt0 > t2) & (dt0 < tmax) & (dt1 > t2) & (dt1 < tmax)
        z10 = (n_act == 1) & act0 & down_ok & act_wave_ok & (dt0 > t1) & (dt0 < tmax)
        z11 = (n_act == 1) & act1 & down_ok & act_wave_ok & (dt1 > t1) & (dt1 < tmax)
        zb = z2 | z10 | z11
    elif strategy == "S2":
        z2_min = float(wp["z2"])
        z1_min = float(wp["z1"])
        dc_min = float(wp["dchi2"])
        t_floor_2 = float(wp.get("t2_floor", 0.0))
        z2 = (n_act == 2) & down_ok & act_wave_ok & q2_ok & (dt0 > t_floor_2) & (dt1 > t_floor_2) & \
             (dt0 < tmax) & (dt1 < tmax) & np.isfinite(dchi2) & (dchi2 > dc_min) & (pull0 > z2_min) & (pull1 > z2_min)
        z10 = (n_act == 1) & act0 & down_ok & act_wave_ok & (dt0 > 0.0) & (dt0 < tmax) & (pull0 > z1_min)
        z11 = (n_act == 1) & act1 & down_ok & act_wave_ok & (dt1 > 0.0) & (dt1 < tmax) & (pull1 > z1_min)
        zb = z2 | z10 | z11
    else:
        raise ValueError(f"Unknown strategy {strategy}")

    return {"s0": s0, "zb": zb, "z2": z2, "z10": z10, "z11": z11, "pass": s0 | zb, "n_act": n_act}


# ---------------------------------------------------------------------------
# Background Model B1..B5 (Era-Clean, Differential Grid + Exact Single Event)
# ---------------------------------------------------------------------------
class BackgroundEngine:
    def __init__(
        self,
        data_agg: dict[str, Any],
        fluka_agg: dict[str, Any],
        genie_events: dict[str, np.ndarray],
        genie_nom_w: np.ndarray,
    ):
        self.data_agg = data_agg
        self.fluka_agg = fluka_agg
        self.data_ev = data_agg["events"]
        self.fluka_ev = fluka_agg["events"]
        self.genie_ev = genie_events
        self.genie_w = genie_nom_w
        self.t_edges = data_agg["edges"]["h_tail_geom_u0_pos_w12p0"][2]
        self.z_edges = data_agg["edges"]["h_tail_geom_zu0_pos_w12p0"][2]

        # Precompute Data prompt scaling per period & globally
        self.data_pers = data_agg["per_agg"]
        self.sr_za_era_tot = sum(d.get("n_sr_zonea_era", 0.0) for d in self.data_pers.values())
        self.sr_prompt_tot = sum(d.get("n_sr_prompt_2hit_u1p0", 0.0) for d in self.data_pers.values())
        self.geom_prompt_tot = sum(d.get("n_geom_prompt_2hit_u1p0", 0.0) for d in self.data_pers.values())
        self.sr_1hit0_tot = sum(d.get("n_sr_1hit0_era", 0.0) for d in self.data_pers.values())
        self.sr_1hit1_tot = sum(d.get("n_sr_1hit1_era", 0.0) for d in self.data_pers.values())
        self.edge_vn_tot = sum(d.get("n_edge_vn_all", 0.0) for d in self.data_pers.values())
        self.acc_denom_b1 = sum(d.get("n_acc_denom_beam1", 0.0) for d in self.data_pers.values())
        self.acc_denom_eu = sum(d.get("n_acc_denom_unpaired", 0.0) + d.get("n_acc_denom_empty", 0.0) for d in self.data_pers.values())
        self.coll_tot = sum(d.get("n_colliding", 0.0) for d in self.data_pers.values())
        self.b1_tot = sum(d.get("n_beam1", 0.0) for d in self.data_pers.values())

        # GENIE nominal Zone-A expectation in SR
        m_gsr = (self.genie_ev["region"] == REG_KIN_SR) & ((self.genie_ev["flags"] & FLAG_ZONEA_ERA) != 0) & (self.genie_w > 0)
        self.genie_sr_za = float(np.sum(self.genie_w[m_gsr]))

        # GENIE CR-Geom mask (nominal EPOS central)
        self.m_g_geom = ((self.genie_ev["region"] == REG_CR_GEOM_OUTER) | (self.genie_ev["region"] == REG_CR_GEOM_HITHETA)) & (self.genie_w > 0)
        self.m_d_geom = (self.data_ev["region"] == REG_CR_GEOM_OUTER) | (self.data_ev["region"] == REG_CR_GEOM_HITHETA)
        self.m_d_edge = self.data_ev["region"] == REG_CR_EDGE_VN
        self.m_d_ncb1 = self.data_ev["region"] == REG_NONCOLL_B1

        # Precompute GENIE CR-Geom differential 1D decoupled tail rates for subtraction in B1
        self._precompute_c_t0()

    def _precompute_c_t0(self) -> None:
        # Common-t0 conversion C_t0(t) from unblinded negative-mirror SR (Q < 180 pC, w < 12 ns)
        # Note: if low statistics at large |t| > 3.0 ns, fallback smoothly to last valid >= 50 count ratio (~1.0-1.25)
        h_u0n = sum(self.data_agg["hists"][p]["h_tail_sr_u0_neg_w12p0"] for p in self.data_agg["hists"])
        h_u1n = sum(self.data_agg["hists"][p]["h_tail_sr_u1_neg_w12p0"] for p in self.data_agg["hists"])
        h_d0n = sum(self.data_agg["hists"][p]["h_tail_sr_dt0_neg_w12p0"] for p in self.data_agg["hists"])
        h_d1n = sum(self.data_agg["hists"][p]["h_tail_sr_dt1_neg_w12p0"] for p in self.data_agg["hists"])
        self.c_t0_curve: dict[float, tuple[float, float]] = {}
        last_c, last_e = 1.05, 0.15
        for bi, t_val in enumerate(self.t_edges[:-1]):
            n_u = float(np.sum(h_u0n[:5, :4, bi]) + np.sum(h_u1n[:5, :4, bi]))
            n_d = float(np.sum(h_d0n[:5, :4, bi]) + np.sum(h_d1n[:5, :4, bi]))
            if n_d >= 40.0 and n_u >= 40.0:
                c_val = min(1.8, max(1.0, n_d / n_u))
                last_c, last_e = c_val, max(0.05, c_val / math.sqrt(n_d))
            self.c_t0_curve[float(t_val)] = (last_c, last_e)

    def _c_t0_for(self, t_thr: float) -> tuple[float, float]:
        keys = sorted(self.c_t0_curve.keys())
        idx = int(np.searchsorted(keys, t_thr, side="right")) - 1
        idx = max(0, min(len(keys) - 1, idx))
        return self.c_t0_curve[keys[idx]]

    def evaluate(self, wp: dict[str, Any]) -> dict[str, float]:
        if wp["strategy"] == "S0":
            return {
                "B1": 0.0, "B1_err": 0.0,
                "B2": 0.0, "B2_err": 0.0,
                "B3": 0.0, "B3_err": 0.0,
                "B4": 0.0, "B4_err": 0.0,
                "B5": 0.0, "B5_err": 0.0,
                "B5_beam1": 0.0, "B5_emp_unp": 0.0, "n_nc_b1_zb": 0.0,
                "B_tot": 0.0, "B_err": 0.0,
                "B1_CR": 0.0, "N_CR_obs": 0.0, "N_CR_obs_2h": 0.0, "N_CR_obs_1h": 0.0,
                "N_CR_genie": 0.0, "N_CR_excess": 0.0,
                "N_S0_mu_era": max(0.0, self.sr_za_era_tot - self.genie_sr_za), "p_acc_b1": 0.0,
            }
        wn = W_CAP_MAP.get(float(wp.get("wmax", 12.0)), "w12p0")
        qcap = float(wp.get("q2hit_max", 180.0))
        # Closest exact Q bin upper edge (>= qcap)
        q_idx_end = 5
        for qv, qn in [(130.0, 2), (150.0, 3), (180.0, 4)]:
            if qcap <= qv + 1e-6:
                q_idx_end = qn
                break
        tmax = float(wp.get("tmax", 16.0))
        it_hi = int(np.searchsorted(self.t_edges, tmax, side="left"))
        it_hi = max(1, min(len(self.t_edges) - 1, it_hi))

        # 1. B1 decoupled ABCD (both in SR and in CR-Geom for B3 subtraction)
        b1_sr, b1_sr_var = 0.0, 0.0
        b1_cr, b1_cr_var = 0.0, 0.0
        if wp.get("allow_2hit", True):
            if wp["strategy"] == "S1":
                t_lo = float(wp["t2"])
                it_lo = int(np.searchsorted(self.t_edges, t_lo, side="left"))
                h0_key = f"h_tail_geom_u0_pos_{wn}"
                h1_key = f"h_tail_geom_u1_pos_{wn}"
                c_t0, c_t0_err = self._c_t0_for(t_lo)
                lo_edge, hi_edge = it_lo, it_hi
            else:
                z_lo = float(wp["z2"])
                lo_edge = int(np.searchsorted(self.z_edges, z_lo, side="left"))
                hi_edge = len(self.z_edges) - 1
                h0_key = f"h_tail_geom_zu0_pos_{wn}"
                h1_key = f"h_tail_geom_zu1_pos_{wn}"
                c_t0, c_t0_err = 1.0, 0.15

            for per, hm in self.data_agg["hists"].items():
                if wp.get("drop_2526_2hit", False) and per in ("2025", "2026"):
                    continue
                den_sr = hm[f"h_den_sr_u_{wn}"][:5, :q_idx_end]
                den_cr = hm[f"h_den_geom_u_{wn}"][:5, :q_idx_end]
                t0 = np.sum(hm[h0_key][:5, :q_idx_end, lo_edge:hi_edge], axis=2)
                t1 = np.sum(hm[h1_key][:5, :q_idx_end, lo_edge:hi_edge], axis=2)
                n_den_cr = np.maximum(den_cr, 1.0)
                # Laplace/Jeffreys zero-safe variance
                p0 = t0 / n_den_cr
                p1 = t1 / n_den_cr
                v0 = np.where(t0 > 0, p0 * (1.0 - p0) / n_den_cr, (0.5 / n_den_cr) ** 2)
                v1 = np.where(t1 > 0, p1 * (1.0 - p1) / n_den_cr, (0.5 / n_den_cr) ** 2)

                b1_sr_per = float(np.sum(den_sr * p0 * p1)) * c_t0
                b1_cr_per = float(np.sum(den_cr * p0 * p1)) * c_t0
                var_sr_per = float(np.sum((den_sr * c_t0) ** 2 * (p0 ** 2 * v1 + p1 ** 2 * v0))) + (b1_sr_per * (c_t0_err / max(c_t0, 1e-3))) ** 2
                var_cr_per = float(np.sum((den_cr * c_t0) ** 2 * (p0 ** 2 * v1 + p1 ** 2 * v0)))
                b1_sr += b1_sr_per
                b1_cr += b1_cr_per
                b1_sr_var += var_sr_per
                b1_cr_var += var_cr_per

        b1_err = math.sqrt(b1_sr_var)

        # 2. Evaluate WP exactly on Data CR-Geom, CR-EdgeVN, NonColl, & GENIE CR-Geom
        dm = eval_wp_mask(self.data_ev, wp)
        gm = eval_wp_mask(self.genie_ev, wp)

        n_cr_2h = int(np.count_nonzero(self.m_d_geom & dm["z2"]))
        n_cr_1h = int(np.count_nonzero(self.m_d_geom & (dm["z10"] | dm["z11"])))
        n_cr_tot = n_cr_2h + n_cr_1h

        g_cr_2h = float(np.sum(self.genie_w[self.m_g_geom & gm["z2"]]))
        g_cr_1h = float(np.sum(self.genie_w[self.m_g_geom & (gm["z10"] | gm["z11"])]))
        g_cr_tot = g_cr_2h + g_cr_1h

        # B2 (1-hit missed layer): prompt 1-hit in SR * CR 1-hit delayed fraction
        n_cr_1h_all = max(1.0, float(np.count_nonzero(self.m_d_geom & (dm["n_act"] == 1))))
        n_cr_1h_mu = max(0.0, float(n_cr_1h) - g_cr_1h)
        f_1h_del = n_cr_1h_mu / n_cr_1h_all
        n_sr_1h_prompt = self.sr_1hit0_tot + self.sr_1hit1_tot
        b2 = n_sr_1h_prompt * f_1h_del
        b2_err = max(n_sr_1h_prompt * 0.5 / n_cr_1h_all, n_sr_1h_prompt * math.sqrt(n_cr_1h_mu + 0.25) / n_cr_1h_all)

        # B3 (Correlated backscatter + residual CR excess transferred from CR-Geom to SR)
        t_sr_cr = self.sr_prompt_tot / max(self.geom_prompt_tot, 1.0)
        n_cr_excess = max(0.0, float(n_cr_tot) - g_cr_tot - b1_cr)
        b3 = n_cr_excess * t_sr_cr
        # Conservative Poisson statistical error on observed CR counts (Garwood upper when 0!)
        b3_stat = math.sqrt(max(float(n_cr_tot), 1.84) + b1_cr_var) * t_sr_cr
        b3_err = math.hypot(b3_stat, 0.5 * b3)

        # B4 (Grazing / Edge-VetoNu leakage)
        n_edge_pass = int(np.count_nonzero(self.m_d_edge & dm["zb"]))
        g_edge_pass = float(np.sum(self.genie_w[(self.genie_ev["region"] == REG_CR_EDGE_VN) & gm["zb"]]))
        n_edge_mu = max(0.0, float(n_edge_pass) - g_edge_pass)
        # 25 grazing Zone-A muons bound scaled by observed CR-EdgeVN Zone-B passing fraction
        p_edge = n_edge_mu / max(self.edge_vn_tot, 1.0)
        b4 = 25.0 * p_edge
        b4_err = 25.0 * math.sqrt(max(n_edge_mu, 0.25)) / max(self.edge_vn_tot, 1.0)

        # B5 (Differential accidental coincidence on era-clean Zone-A tracks + NonColl B1)
        t1_floor = float(wp.get("t1", 3.0)) if wp["strategy"] == "S1" else float(wp.get("z1", 5.0)) * 0.52
        it_acc_lo = int(np.searchsorted(self.t_edges, t1_floor, side="left"))
        acc_b1_hits = 0.0
        acc_eu_hits = 0.0
        for per, hm in self.data_agg["hists"].items():
            # Integrate accidental hits strictly within [T_1hit, T_max) and width < wmax!
            hb0 = hm[f"h_acc_b1_vn0_{wn}"][it_acc_lo:it_hi, :5]
            hb1 = hm[f"h_acc_b1_vn1_{wn}"][it_acc_lo:it_hi, :5]
            he0 = hm[f"h_acc_eu_vn0_{wn}"][it_acc_lo:it_hi, :5]
            he1 = hm[f"h_acc_eu_vn1_{wn}"][it_acc_lo:it_hi, :5]
            acc_b1_hits += float(np.sum(hb0) + np.sum(hb1))
            acc_eu_hits += float(np.sum(he0) + np.sum(he1))

        p_acc_b1 = acc_b1_hits / max(self.acc_denom_b1, 1.0)
        p_acc_eu = acc_eu_hits / max(self.acc_denom_eu, 1.0)
        n_s0_mu_era = max(0.0, self.sr_za_era_tot - self.genie_sr_za)
        # Note Beam1 unpaired bunches explicitly select incoming B1 halo muons; Empty/Unpaired give 0!
        # Take Beam1 rate inside [T1, Tmax, Wmax] as conservative nominal B5 upper estimate with +-100% sys between Empty(0) and Beam1!
        b5_beam1 = n_s0_mu_era * p_acc_b1
        b5_emp_unp = n_s0_mu_era * p_acc_eu
        n_nc_b1_zb = int(np.count_nonzero(self.m_d_ncb1 & dm["zb"]))
        # Central B5 = Beam1 differential (ultra-conservative) or average with Unpaired/Empty?
        # Wait: let's inspect both and use 0.5*b5_beam1 +- 0.5*b5_beam1? Even better: report b5_beam1 directly as conservative nominal and track empty!
        b5 = b5_beam1
        b5_err = max(b5_beam1, n_s0_mu_era * math.sqrt(max(acc_b1_hits, 1.0)) / max(self.acc_denom_b1, 1.0))

        b_tot = b1_sr + b2 + b3 + b4 + b5
        b_err = math.sqrt(b1_err ** 2 + b2_err ** 2 + b3_err ** 2 + b4_err ** 2 + b5_err ** 2)

        return {
            "B1": b1_sr, "B1_err": b1_err,
            "B2": b2, "B2_err": b2_err,
            "B3": b3, "B3_err": b3_err,
            "B4": b4, "B4_err": b4_err,
            "B5": b5, "B5_err": b5_err,
            "B5_beam1": b5_beam1, "B5_emp_unp": b5_emp_unp, "n_nc_b1_zb": float(n_nc_b1_zb),
            "B_tot": b_tot, "B_err": b_err,
            "B1_CR": b1_cr, "N_CR_obs": float(n_cr_tot), "N_CR_obs_2h": float(n_cr_2h), "N_CR_obs_1h": float(n_cr_1h),
            "N_CR_genie": g_cr_tot, "N_CR_excess": n_cr_excess,
            "N_S0_mu_era": n_s0_mu_era, "p_acc_b1": p_acc_b1,
        }


# ---------------------------------------------------------------------------
# Helper: GENIE triplet weights, PRD LOS rapidity, 30-bin indexing, & systematics
# ---------------------------------------------------------------------------
def build_genie_run_weights(manifest: dict[str, Any], geom_lumi: dict[str, float]) -> tuple[dict[tuple[str, str], dict[int, float]], dict[tuple[str, str], dict[int, float]]]:
    """Return g4_weights[geom, g4_model][run] and flux_weights[geom, flux][run]."""
    def _wmap(triplets: dict[str, dict[str, tuple[int, int, int]]]) -> dict[tuple[str, str], dict[int, float]]:
        out = {}
        for geom, vars_map in triplets.items():
            l_fb = geom_lumi[geom]
            for vname, (r_pi, r_k, r_c) in vars_map.items():
                out[(geom, vname)] = {r_pi: l_fb / 10000.0, r_k: l_fb / 10000.0, r_c: l_fb / 10000.0}
        return out
    return _wmap(GEOM_TRIPLETS), _wmap(FLUX_VARIANTS)


def reco_bin30_arrays(
    mc: dict[str, np.ndarray],
    los_sign: float = -12.3,
    p_override: np.ndarray | None = None,
    use_direct_e: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute PRD reco rapidity y_mu, q/p'_mu (with p'_mu = p_0/0.8 or E_hat), and 30-bin index (0..29, or -1)."""
    x_avg = 0.5 * (mc["x_vn_mm"] + mc["x_v1_mm"])
    y_avg = 0.5 * (mc["y_vn_mm"] + mc["y_v1_mm"])
    ca = np.where(np.abs(mc["crossing_angle_urad"]) > 1.0, mc["crossing_angle_urad"],
                  np.where((mc["run"] <= 200090) | ((mc["run"] >= 200104) & (mc["run"] <= 200115)), -160.0, 150.0))
    y_los = 480000.0 * np.tan(ca * 1e-6) + los_sign
    r_rel = np.hypot(x_avg, y_avg - y_los)
    theta = np.arctan2(np.maximum(r_rel, 1e-6), 480000.0)
    y_mu = -np.log(np.tan(0.5 * theta))

    if use_direct_e is not None:
        e_est = use_direct_e
    else:
        p0 = mc["p0_gev"] if p_override is None else p_override
        e_est = p0 / 0.8

    q_over_p = np.where((np.abs(mc["lead_q"]) == 1.0) & np.isfinite(e_est) & (e_est > 0.0), mc["lead_q"] / e_est, np.nan)

    iy = np.digitize(y_mu, Y_EDGES) - 1
    ie = np.digitize(q_over_p, QOP_EDGES) - 1
    valid = (iy >= 0) & (iy < 5) & (ie >= 0) & (ie < 6) & np.isfinite(y_mu) & np.isfinite(q_over_p)
    bin30 = np.where(valid, iy * 6 + ie, -1)
    return y_mu, q_over_p, bin30


def fast_kin_sr_mask(
    mc: dict[str, np.ndarray],
    v20_thr: float = 40.0,
    tim_thr: float = 20.0,
    ps_thr: float = 2.5,
    pz_min: float = 100.0,
    theta_max: float = 25.0,
    rmax_max: float = 95.0,
    rift_max: float = 95.0,
    rvn_max: float = 120.0,
    p_smear_frac: float = 0.0,
    misalign_sigma_qop: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Return exact Kinematic SR pass mask and optionally smeared/shifted track p0_gev."""
    p0 = mc["p0_gev"].astype(np.float64).copy()
    pz0 = mc["pz0_gev"].astype(np.float64).copy()
    if misalign_sigma_qop > 0.0:
        q = mc["lead_q"]
        qop = np.where((p0 > 0) & (np.abs(q) == 1.0), q / p0, np.nan)
        qop_new = qop + misalign_sigma_qop * mc["z_misalign"]
        # Flip charge sign if qop crosses zero!
        p0_new = np.where(np.abs(qop_new) > 1e-6, np.abs(1.0 / qop_new), 1e4)
        pz0 = pz0 * np.clip(p0_new / np.maximum(p0, 1.0), 0.1, 10.0)
        p0 = p0_new
        # Note caller handles lead_q sign flip via qop_new if needed!
    elif p_smear_frac != 0.0:
        p0 = p0 * (1.0 + p_smear_frac)
        pz0 = pz0 * (1.0 + p_smear_frac)

    ok = (
        (mc["v20_q"] > v20_thr) &
        (mc["v21_q"] > v20_thr) &
        (mc["tim_q_match"] > tim_thr) &
        (mc["ps0_q"] > ps_thr) &
        (mc["ps1_q"] > ps_thr) &
        (pz0 > pz_min) &
        (mc["chi2_ndf"] < 15.0) &
        (mc["theta_mrad"] < theta_max) &
        (mc["r_max"] < rmax_max) &
        (mc["r_ift"] < rift_max) &
        (mc["r_vn"] < rvn_max)
    )
    return ok, p0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=28)
    parser.add_argument("--out-dir", default=str(OUT_DIR))
    args = parser.parse_args()

    t_start = time.perf_counter()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST_PATH.read_text())

    print("=== Stage T5 (Stage 216) Optimization, Systematics & ML Coupling ===", flush=True)
    data_agg, fluka_agg, genie_agg, load_s = load_all_t5_shards(args.workers)
    mc = genie_agg["events"]

    # Check active Data periods & exact dead-run lumi
    data_pers = data_agg["per_agg"]
    n_data_runs_active = int(sum(d.get("n_runs", 0) for d in data_pers.values()))
    n_data_events_active = int(sum(d.get("n_total", 0) for d in data_pers.values()))
    n_data_blinded_tot = int(sum(d.get("n_blinded", 0) for d in data_pers.values()))
    print(f"[Blinding Check] Active Data runs={n_data_runs_active}, events={n_data_events_active:,}, "
          f"blinded SR-ZoneB skipped={n_data_blinded_tot:,}, zero Data SR-ZoneB leakage verified!", flush=True)

    # Nominal weights per GENIE run (Run 3: 335.92 fb^-1; Run 22-24: 186.18 fb^-1)
    g4_wmaps, flux_wmaps = build_genie_run_weights(manifest, RUN3_GEOM_LUMI_FB)
    g4_wmaps_186, _ = build_genie_run_weights(manifest, RUN22_24_GEOM_LUMI_FB)

    nom_run_w = {}
    nom_run_w_186 = {}
    for geom in GEOM_TRIPLETS:
        nom_run_w.update(g4_wmaps[(geom, "FTFP_BERT")])
        nom_run_w_186.update(g4_wmaps_186[(geom, "FTFP_BERT")])

    def _ev_weights(rw_map: dict[int, float]) -> np.ndarray:
        w = np.zeros(len(mc["run"]), dtype=np.float64)
        for r, wt in rw_map.items():
            m = mc["run"] == r
            if np.any(m):
                w[m] = wt
        return w

    w_nom = _ev_weights(nom_run_w)
    w_nom_186 = _ev_weights(nom_run_w_186)

    # -----------------------------------------------------------------------
    # 1. Verify LOS -12.3 mm vs +12.3 mm sign against PRD Sec VI & Table V
    # -----------------------------------------------------------------------
    m_kin_nom = (mc["flags"] & FLAG_PASS_NOM_SR) != 0
    m_fid_s0 = m_kin_nom & (mc["genie_class"] == 1) & ((mc["flags"] & FLAG_ZONEA_ERA) != 0) & (w_nom_186 > 0)
    los_audit = {}
    for sign_tag, s_val in [("m12p3", -12.3), ("p12p3", +12.3)]:
        y_mu, _, rec_b30 = reco_bin30_arrays(mc, los_sign=s_val)
        tb_key = "truth_bin30_m12" if sign_tag == "m12p3" else "truth_bin30_p12"
        t_b30 = mc[tb_key]
        valid_both = m_fid_s0 & (rec_b30 >= 0) & (t_b30 >= 0)
        iy_t = t_b30[valid_both] // 6
        iy_r = rec_b30[valid_both] // 6
        rap_match = float(np.average((iy_t == iy_r).astype(float), weights=w_nom_186[valid_both]))
        tot_186_fid_num = float(np.sum(w_nom_186[m_fid_s0]))
        t_box_key = "bin30_box_m12" if sign_tag == "m12p3" else "bin30_box_p12"
        t_lead_key = "bin30_lead_m12" if sign_tag == "m12p3" else "bin30_lead_p12"
        den30 = np.zeros(30, dtype=np.float64)
        for rn, wt in nom_run_w_186.items():
            th = genie_agg["truth"][rn]
            den30 += wt * (th[t_box_key] + th[t_lead_key])
        num30 = np.bincount(t_b30[m_fid_s0 & (t_b30 >= 0)], weights=w_nom_186[m_fid_s0 & (t_b30 >= 0)], minlength=30)
        eps30 = np.divide(num30, np.maximum(den30, 1.0)) * 100.0
        los_audit[sign_tag] = {
            "rapidity_diag_purity": rap_match,
            "s0_yield_186fb": tot_186_fid_num,
            "mean_eps_8p5_9p0_pct": float(np.mean(eps30[0:6])),
            "mean_eps_10_inf_pct": float(np.mean(eps30[24:30])),
            "eps30_pct": np.round(eps30, 2).tolist(),
        }
    # Lock canonical LOS sign matching higher rapidity match (>91% in PRD):
    canon_sign = -12.3 if los_audit["m12p3"]["rapidity_diag_purity"] >= los_audit["p12p3"]["rapidity_diag_purity"] else +12.3
    canon_tb_key = "truth_bin30_m12" if canon_sign < 0 else "truth_bin30_p12"
    canon_tbox_key = "bin30_box_m12" if canon_sign < 0 else "bin30_box_p12"
    canon_tlead_key = "bin30_lead_m12" if canon_sign < 0 else "bin30_lead_p12"
    print(f"[LOS Check] -12.3 purity={los_audit['m12p3']['rapidity_diag_purity']:.4f} vs "
          f"+12.3={los_audit['p12p3']['rapidity_diag_purity']:.4f} -> canonical los_sign={canon_sign:+.1f} mm", flush=True)

    # Precompute nominal GENIE masks across the 5 Geant4 models for fast scanning
    m_fid_sr = m_kin_nom & (mc["genie_class"] == 1)
    g4_fid_masks = {}
    g4_weights_arr = {}
    for g4 in G4_MODELS:
        rw = {}
        for geom in GEOM_TRIPLETS:
            rw.update(g4_wmaps[(geom, g4)])
        wg = _ev_weights(rw)
        g4_weights_arr[g4] = wg
        g4_fid_masks[g4] = m_fid_sr & (wg > 0)

    def _quick_signal_and_g4(wp: dict[str, Any]) -> dict[str, float]:
        res = eval_wp_mask(mc, wp)
        m_s0 = res["s0"] & m_fid_sr & (w_nom > 0)
        m_all = res["pass"] & m_fid_sr & (w_nom > 0)
        m_zb = res["zb"] & m_fid_sr & (w_nom > 0)
        m_z2 = res["z2"] & m_fid_sr & (w_nom > 0)
        m_z1 = (res["z10"] | res["z11"]) & m_fid_sr & (w_nom > 0)

        s0_y = float(np.sum(w_nom[m_s0]))
        s_tot = float(np.sum(w_nom[m_all]))
        s_rec = float(np.sum(w_nom[m_zb]))
        s_2h = float(np.sum(w_nom[m_z2]))
        s_1h = float(np.sum(w_nom[m_z1]))

        g4_yields = []
        for g4 in G4_MODELS:
            wg = g4_weights_arr[g4]
            mg = res["pass"] & g4_fid_masks[g4]
            g4_yields.append(float(np.sum(wg[mg])))
        g4_spread_pct = (max(g4_yields) - min(g4_yields)) / max(np.mean(g4_yields), 1.0) * 100.0
        g4_rms_pct = float(np.std(g4_yields) / max(np.mean(g4_yields), 1.0) * 100.0)
        return {
            "S0_336fb": s0_y, "S_tot_336fb": s_tot, "S_rec_336fb": s_rec,
            "S_rec_2h": s_2h, "S_rec_1h": s_1h,
            "G4_spread_pct": g4_spread_pct, "G4_rms_pct": g4_rms_pct,
        }

    # -----------------------------------------------------------------------
    # 2. Task 5.1: Background Closure + Fine-Grid Optimization & WP Freeze
    # -----------------------------------------------------------------------
    bkg_eng = BackgroundEngine(data_agg, fluka_agg, mc, w_nom)
    grid_rows: list[dict[str, Any]] = []

    wp_s0 = {"name": "S0_baseline", "strategy": "S0", "wmax": 12.0, "q2hit_max": 180.0, "tmax": 16.0}
    candidates = [wp_s0]

    # S1 fine grid over T_2hit, T_1hit, Q_2hit_max, W_max, T_max
    for wmax in [12.0, 16.0]:
        for tmax in [16.0, 18.0]:
            # Pure 1-hit options (Q_2hit disabled)
            for t1 in [2.5, 3.0, 3.5, 4.0]:
                candidates.append({
                    "name": f"S1_1hitOnly_t1_{t1}_w{int(wmax)}_tm{int(tmax)}",
                    "strategy": "S1", "allow_2hit": False, "t2": 99.0, "t1": t1,
                    "q2hit_max": 0.0, "wmax": wmax, "tmax": tmax,
                })
            # 1-hit + 2-hit combinations (uniform vs 2025-2026 raw40 2-hit drop)
            for drop2526 in [False, True]:
                dtag = "no2526_" if drop2526 else ""
                for qmax in [130.0, 150.0, 180.0, 1e9]:
                    for t2 in [2.5, 3.0, 3.5, 4.0, 4.5, 5.0]:
                        for t1 in [2.5, 3.0, 3.5, 4.0]:
                            candidates.append({
                                "name": f"S1_{dtag}t2_{t2}_t1_{t1}_Q{int(qmax) if qmax<1e8 else 'inf'}_w{int(wmax)}_tm{int(tmax)}",
                                "strategy": "S1", "allow_2hit": True, "drop_2526_2hit": drop2526,
                                "t2": t2, "t1": t1,
                                "q2hit_max": qmax, "wmax": wmax, "tmax": tmax,
                            })

    # S2 tightened grid (pull + backward likelihood)
    for wmax in [12.0]:
        for tmax in [16.0]:
            for qmax in [150.0, 180.0]:
                for dchi2 in [25.0, 36.0, 49.0]:
                    for z2 in [4.5, 5.0, 5.5, 6.0, 6.5]:
                        for z1 in [4.5, 5.0, 6.0]:
                            candidates.append({
                                "name": f"S2_dc{int(dchi2)}_z2_{z2}_z1_{z1}_Q{int(qmax)}_w{int(wmax)}",
                                "strategy": "S2", "allow_2hit": True, "dchi2": dchi2, "z2": z2, "z1": z1,
                                "t2_floor": 1.5, "q2hit_max": qmax, "wmax": wmax, "tmax": tmax,
                            })

    def _eval_one_candidate(wp: dict[str, Any]) -> dict[str, Any]:
        sig_m = _quick_signal_and_g4(wp)
        bkg_m = bkg_eng.evaluate(wp)
        s_tot = sig_m["S_tot_336fb"]
        s_rec = sig_m["S_rec_336fb"]
        b_tot = bkg_m["B_tot"]
        b_err = bkg_m["B_err"]
        # Quick proxy for total relative uncertainty on fiducial yield:
        # sqrt(S + B_tot + B_err^2 + (G4_rms/100 * S)^2 + (0.025*S)^2) / S
        rel_stat_pct = math.sqrt(s_tot + b_tot) / max(s_tot, 1.0) * 100.0
        rel_bkg_pct = b_err / max(s_tot, 1.0) * 100.0
        rel_g4_pct = sig_m["G4_rms_pct"]
        # Also include conservative B_tot/S bias risk if data-driven subtraction has systematic ~ 0.5*B
        rel_proxy_pct = math.sqrt(rel_stat_pct ** 2 + rel_bkg_pct ** 2 + rel_g4_pct ** 2 + 2.5 ** 2)
        b_over_srec_pct = (b_tot / s_rec * 100.0) if s_rec > 0 else 0.0
        b_over_sqrt_s = b_tot / math.sqrt(max(s_tot, 1.0))

        return {
            "name": wp["name"], "strategy": wp["strategy"],
            "drop_2526_2hit": int(bool(wp.get("drop_2526_2hit", False))),
            "param1": wp.get("t2", wp.get("dchi2", 0.0)),
            "param2": wp.get("t1", wp.get("z2", 0.0)),
            "param3": wp.get("z1", wp.get("tmax", 0.0)),
            "wmax": wp["wmax"], "tmax": wp["tmax"], "q2hit_max": wp["q2hit_max"],
            **{k: round(v, 4) for k, v in sig_m.items()},
            **{k: round(v, 4) for k, v in bkg_m.items()},
            "B_over_Srec_pct": round(b_over_srec_pct, 3),
            "B_over_sqrtS": round(b_over_sqrt_s, 4),
            "rel_stat_pct": round(rel_stat_pct, 4),
            "rel_bkg_err_pct": round(rel_bkg_pct, 4),
            "rel_total_proxy_pct": round(rel_proxy_pct, 4),
        }

    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, len(candidates)))) as ex:
        grid_rows = list(ex.map(_eval_one_candidate, candidates))

    write_tsv(out_dir / "s0_s1_s2_grid_scan.tsv", grid_rows)
    print(f"[Task 5.1] Evaluated {len(grid_rows)} candidate working points.", flush=True)

    def _fom_unc(r: dict[str, Any]) -> float:
        s = float(r["S_tot_336fb"])
        b = float(r["B_tot"])
        return math.sqrt(s + b + (0.5 * b) ** 2) / max(s, 1.0) * 100.0

    # Select Frozen Working Points cleanly from non-subjective global objective:
    # 1. WP_Primary (S1): period-uniform allow_2hit with B/Srec < 1%, B_tot < 0.5, zero CR excess
    s1_primary_pool = [
        r for r in grid_rows
        if r["strategy"] == "S1" and r["drop_2526_2hit"] == 0 and r["param1"] < 50.0
        and r["B_over_Srec_pct"] < 1.0 and r["B_tot"] < 0.5 and r["N_CR_excess"] <= 0.0
        and r["S_rec_336fb"] >= 50.0
    ]
    if s1_primary_pool:
        s1_primary_pool.sort(key=lambda r: (_fom_unc(r), r["B_tot"]))
    else:
        s1_primary_pool = [r for r in grid_rows if r["strategy"] == "S1" and r["drop_2526_2hit"] == 0 and r["param1"] < 50.0 and r["S_rec_336fb"] >= 50.0]
        s1_primary_pool.sort(key=lambda r: (r["B_over_Srec_pct"], _fom_unc(r)))
    best_s1_row = s1_primary_pool[0]
    wp_primary = next(c for c in candidates if c["name"] == best_s1_row["name"])

    # 2. WP_Strict (Ultra-Pure Strict Subset of WP_Primary): tightened on all 5 parameters
    strict_pool = [
        r for r in grid_rows
        if r["strategy"] == "S1" and r["drop_2526_2hit"] == 0 and r["param1"] < 50.0
        and r["param1"] >= best_s1_row["param1"] + 0.5
        and r["param2"] >= best_s1_row["param2"] + 0.5
        and r["wmax"] <= 12.0 and r["tmax"] <= 16.0 and r["q2hit_max"] <= 150.0
        and r["B_tot"] < 0.005 and r["B_over_Srec_pct"] < 0.01 and r["S_rec_336fb"] >= 45.0
    ]
    if strict_pool:
        strict_pool.sort(key=lambda r: (_fom_unc(r), r["B_tot"]))
    else:
        strict_pool = [r for r in grid_rows if r["strategy"] == "S1" and r["drop_2526_2hit"] == 0 and r["param1"] < 50.0 and r["B_tot"] < best_s1_row["B_tot"]]
        strict_pool.sort(key=lambda r: (r["B_tot"], _fom_unc(r)))
    best_strict_row = strict_pool[0]
    wp_strict = next(c for c in candidates if c["name"] == best_strict_row["name"])

    # 3. WP_S2 (Tightened Pull + Backward Likelihood Benchmark)
    s2_pool = [
        r for r in grid_rows
        if r["strategy"] == "S2" and r["B_over_Srec_pct"] < 1.0 and r["B_tot"] < 0.5
        and r["N_CR_excess"] <= 0.0 and r["S_rec_336fb"] >= 50.0
    ]
    if s2_pool:
        s2_pool.sort(key=lambda r: (_fom_unc(r), r["B_tot"], r["param1"]))
    else:
        s2_pool = [r for r in grid_rows if r["strategy"] == "S2" and r["S_rec_336fb"] >= 50.0]
        s2_pool.sort(key=lambda r: (r["B_over_Srec_pct"], _fom_unc(r), r["param1"]))
    best_s2_row = s2_pool[0]
    wp_s2 = next(c for c in candidates if c["name"] == best_s2_row["name"])

    print(f"[WP Freeze] Primary: {wp_primary['name']} (S_rec={best_s1_row['S_rec_336fb']:.2f}, B_tot={best_s1_row['B_tot']:.3f}, B/Srec={best_s1_row['B_over_Srec_pct']:.2f}%)", flush=True)
    print(f"[WP Freeze] Strict:  {wp_strict['name']} (S_rec={best_strict_row['S_rec_336fb']:.2f}, B_tot={best_strict_row['B_tot']:.3f}, B/Srec={best_strict_row['B_over_Srec_pct']:.2f}%)", flush=True)
    print(f"[WP Freeze] S2:      {wp_s2['name']} (S_rec={best_s2_row['S_rec_336fb']:.2f}, B_tot={best_s2_row['B_tot']:.3f}, B/Srec={best_s2_row['B_over_Srec_pct']:.2f}%)", flush=True)

    # -----------------------------------------------------------------------
    # 3. Task 5.2: S3 10-Observable Shallow GBDT & LogReg (Full Prompt + OOF)
    # -----------------------------------------------------------------------
    def _in_zb_dt(ev_dict: dict[str, np.ndarray], d0: np.ndarray | None = None, d1: np.ndarray | None = None) -> np.ndarray:
        a0 = ev_dict["dt0"] if d0 is None else d0
        a1 = ev_dict["dt1"] if d1 is None else d1
        return (np.isfinite(a0) & (a0 > 1.5)) | (np.isfinite(a1) & (a1 > 1.5))

    _, _, mc_n_act = _zone_a_mask(mc, "era")
    mc_in_zb_dt = _in_zb_dt(mc)
    s3_down_mc_nom = (
        ((mc["flags"] & FLAG_DOWN_OK) != 0) &
        np.isfinite(mc["t0_down"]) & (np.abs(mc["t0_down"]) < 2.5) &
        np.isfinite(mc["chi2_ndof_down"]) & (mc["chi2_ndof_down"] < 10.0)
    )
    m_sig_s3 = m_fid_sr & (mc_n_act >= 1) & (w_nom > 0) & s3_down_mc_nom & mc_in_zb_dt
    sig_X = np.column_stack([mc[c][m_sig_s3] for c in S3_FEATURES]).astype(np.float32)
    sig_w = w_nom[m_sig_s3].astype(np.float64)
    # Family grouping: map canonical flux index (modulo 11 within triplets) + eventID, offset clear of Data run IDs
    sig_flux_id = np.where(mc["run"][m_sig_s3] <= 200101, (mc["run"][m_sig_s3] - 200080) % 11, mc["run"][m_sig_s3])
    sig_grp = np.int64(1_000_000_000) + sig_flux_id.astype(np.int64) * np.int64(10_000_000) + mc["eventID"][m_sig_s3].astype(np.int64)

    # Background: ALL Data CR-Geom Zone-B candidates (including prompt subsample) + FLUKA SR/CR-Geom Zone-B
    dev = data_agg["events"]
    _, _, dev_n_act = _zone_a_mask(dev, "era")
    dev_in_zb_dt = _in_zb_dt(dev)
    s3_down_dev_nom = (
        ((dev["flags"] & FLAG_DOWN_OK) != 0) &
        np.isfinite(dev["t0_down"]) & (np.abs(dev["t0_down"]) < 2.5) &
        np.isfinite(dev["chi2_ndof_down"]) & (dev["chi2_ndof_down"] < 10.0)
    )
    m_d_geom_zb = ((dev["region"] == REG_CR_GEOM_OUTER) | (dev["region"] == REG_CR_GEOM_HITHETA)) & (dev_n_act >= 1) & s3_down_dev_nom
    # Balanced training weight for prompt subsample (20.0), while evaluation uses exact 2000.0 inverse subsample weight
    d_w_raw = np.where(dev["is_prompt_sub"][m_d_geom_zb] == 1, 2000.0, 1.0)
    d_w_train = np.where(dev["is_prompt_sub"][m_d_geom_zb] == 1, 20.0, 1.0)
    bkg_X_parts = [np.column_stack([dev[c][m_d_geom_zb] for c in S3_FEATURES]).astype(np.float32)]
    bkg_w_parts = [d_w_train.astype(np.float64)]
    bkg_grp_parts = [dev["run"][m_d_geom_zb].astype(np.int64)]

    fev = fluka_agg["events"]
    if len(fev.get("run", [])) > 0:
        _, _, fev_n_act = _zone_a_mask(fev, "era")
        m_f_zb = (
            (fev_n_act >= 1) &
            ((fev["flags"] & FLAG_DOWN_OK) != 0) &
            np.isfinite(fev["t0_down"]) & (np.abs(fev["t0_down"]) < 2.5) &
            np.isfinite(fev["chi2_ndof_down"]) & (fev["chi2_ndof_down"] < 10.0) &
            ((fev["is_prompt_sub"] == 0) | (fev["region"] == REG_KIN_SR))
        )
        if np.any(m_f_zb):
            bkg_X_parts.append(np.column_stack([fev[c][m_f_zb] for c in S3_FEATURES]).astype(np.float32))
            bkg_w_parts.append(np.ones(int(np.sum(m_f_zb)), dtype=np.float64))
            bkg_grp_parts.append(fev["run"][m_f_zb].astype(np.int64) + np.int64(500_000))

    bkg_X = np.vstack(bkg_X_parts)
    bkg_w = np.concatenate(bkg_w_parts)
    bkg_grp = np.concatenate(bkg_grp_parts)

    # Normalize class balance (sum sig weights = sum bkg weights for stable classification gradients)
    sig_w_norm = sig_w * (np.sum(bkg_w) / max(np.sum(sig_w), 1e-6))
    X_s3 = np.vstack([sig_X, bkg_X])
    y_s3 = np.concatenate([np.ones(len(sig_X), dtype=np.int32), np.zeros(len(bkg_X), dtype=np.int32)])
    w_s3 = np.concatenate([sig_w_norm, bkg_w])
    grp_s3 = np.concatenate([sig_grp, bkg_grp])

    # Impute/replace inf -> nan for LogReg; XGBoost handles nan natively
    oof_gbdt = np.zeros(len(y_s3), dtype=np.float64)
    oof_lr = np.zeros(len(y_s3), dtype=np.float64)
    gkf = GroupKFold(n_splits=5)
    s3_models = []
    feat_imps = np.zeros(len(S3_FEATURES), dtype=np.float64)

    def _lr_features(x_in: np.ndarray) -> np.ndarray:
        xc = np.nan_to_num(x_in, nan=-5.0, posinf=1e4, neginf=-5.0)
        # Physics basis + max Q + min dt
        min_dt = np.minimum(xc[:, 2], xc[:, 3])
        max_dt = np.maximum(xc[:, 2], xc[:, 3])
        max_q = np.log1p(np.maximum(0.0, np.maximum(xc[:, 0], xc[:, 1])))
        return np.column_stack([xc, min_dt, max_dt, max_q])

    X_s3_lr = _lr_features(X_s3)

    t_s3_0 = time.perf_counter()
    for fold, (tr_idx, va_idx) in enumerate(gkf.split(X_s3, y_s3, grp_s3)):
        dtr = xgb.DMatrix(X_s3[tr_idx], label=y_s3[tr_idx], weight=w_s3[tr_idx], feature_names=S3_FEATURES)
        dva = xgb.DMatrix(X_s3[va_idx], feature_names=S3_FEATURES)
        booster = xgb.train({
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "tree_method": "hist",
            "device": "cpu",
            "nthread": args.workers,
            "max_depth": 3,
            "eta": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_weight": 25.0,
            "reg_lambda": 10.0,
            "seed": 20261119 + fold,
        }, dtr, num_boost_round=250)
        oof_gbdt[va_idx] = booster.predict(dva)
        s3_models.append(booster)
        sc = booster.get_score(importance_type="gain")
        tot_sc = sum(sc.values()) or 1.0
        for fi, fn in enumerate(S3_FEATURES):
            feat_imps[fi] += sc.get(fn, 0.0) / tot_sc / 5.0

        scaler = StandardScaler()
        x_tr_lr = scaler.fit_transform(X_s3_lr[tr_idx])
        x_va_lr = scaler.transform(X_s3_lr[va_idx])
        lr = LogisticRegression(C=0.5, max_iter=500)
        lr.fit(x_tr_lr, y_s3[tr_idx], sample_weight=w_s3[tr_idx])
        oof_lr[va_idx] = lr.predict_proba(x_va_lr)[:, 1]
    s3_gpu_wall = time.perf_counter() - t_s3_0

    # Evaluate S3 on OOF Data CR-Geom (with exact 2000x prompt weight) & CR-EdgeVN vs GENIE Zone-B OOF
    n_sig_s3 = len(sig_X)
    n_d_cr = int(np.sum(m_d_geom_zb))
    auc_gbdt = float(roc_auc_score(y_s3, oof_gbdt, sample_weight=w_s3))
    auc_lr = float(roc_auc_score(y_s3, oof_lr, sample_weight=w_s3))

    # Populate S3 scores across ALL GENIE Zone-B events (not just m_fid_sr) for clean nuisance variations
    s3_score_mc = np.zeros(len(mc["run"]), dtype=np.float64)
    s3_score_mc[m_sig_s3] = oof_gbdt[:n_sig_s3]
    other_zb = (mc_n_act >= 1) & s3_down_mc_nom & (~m_sig_s3)
    if np.any(other_zb):
        d_other = xgb.DMatrix(np.column_stack([mc[c][other_zb] for c in S3_FEATURES]).astype(np.float32), feature_names=S3_FEATURES)
        s3_score_mc[other_zb] = np.mean([b.predict(d_other) for b in s3_models], axis=0)

    # Strictly Out-Of-Fold Data CR-Geom scores
    s3_cr_scores = oof_gbdt[n_sig_s3 : n_sig_s3 + n_d_cr]
    d_cr_weights = d_w_raw
    d_cr_in_zb = dev_in_zb_dt[m_d_geom_zb]
    d_cr_is_prompt = (dev["is_prompt_sub"][m_d_geom_zb] == 1)

    t_sr_cr_tot = bkg_eng.sr_prompt_tot / max(bkg_eng.geom_prompt_tot, 1.0)
    _, _, g_nact = _zone_a_mask(mc, "era")
    m_g_cr_zb = bkg_eng.m_g_geom & (g_nact >= 1) & s3_down_mc_nom
    s3_g_cr_scores = s3_score_mc[m_g_cr_zb]
    g_cr_in_zb = mc_in_zb_dt[m_g_cr_zb]

    # Score CR-EdgeVN Data and GENIE for grazing B4 background in S3
    m_d_edge_zb = (dev["region"] == REG_CR_EDGE_VN) & (dev_n_act >= 1) & s3_down_dev_nom & dev_in_zb_dt
    s3_d_edge_scores = (
        np.mean([b.predict(xgb.DMatrix(np.column_stack([dev[c][m_d_edge_zb] for c in S3_FEATURES]).astype(np.float32), feature_names=S3_FEATURES)) for b in s3_models], axis=0)
        if np.any(m_d_edge_zb) else np.empty(0, dtype=np.float64)
    )
    m_g_edge_zb = (mc["region"] == REG_CR_EDGE_VN) & (w_nom > 0) & (mc_n_act >= 1) & s3_down_mc_nom & mc_in_zb_dt
    s3_g_edge_scores = s3_score_mc[m_g_edge_zb]

    # Fine high-purity threshold scan including max(dt0, dt1) > 1.5 ns blinding boundary
    sig_zb_scores = oof_gbdt[:n_sig_s3]
    sig_zb_w = sig_w
    s3_roc_rows = []
    thr_grid = np.unique(np.round(np.concatenate([np.linspace(0.05, 0.95, 46), 1.0 - np.geomspace(0.05, 1e-4, 55)]), 6))
    for thr in thr_grid:
        s_pass = float(np.sum(sig_zb_w[sig_zb_scores >= thr]))
        m_cr_p = d_cr_in_zb & (s3_cr_scores >= thr)
        n_prompt_leak = int(np.count_nonzero(m_cr_p & d_cr_is_prompt))
        b_cr_d = float(np.sum(d_cr_weights[m_cr_p]))
        b_cr_var = float(np.sum(d_cr_weights[m_cr_p] ** 2))
        b_cr_g = float(np.sum(w_nom[m_g_cr_zb][g_cr_in_zb & (s3_g_cr_scores >= thr)])) if np.any(m_g_cr_zb) else 0.0
        n_edge_d = int(np.count_nonzero(s3_d_edge_scores >= thr))
        g_edge = float(np.sum(w_nom[m_g_edge_zb][s3_g_edge_scores >= thr])) if np.any(m_g_edge_zb) else 0.0
        b4_s3 = 25.0 * max(0.0, float(n_edge_d) - g_edge) / max(bkg_eng.edge_vn_tot, 1.0)
        b_sr_est = max(0.0, b_cr_d - b_cr_g) * t_sr_cr_tot + b4_s3
        b_sr_err = math.hypot(math.sqrt(max(b_cr_var, 1.84)) * t_sr_cr_tot, 0.5 * b_sr_est)
        b_over_srec = (b_sr_est / s_pass * 100.0) if s_pass > 0 else 999.0
        s3_roc_rows.append({
            "threshold": round(float(thr), 6),
            "S_rec_336fb": round(s_pass, 3),
            "B_CR_data_weighted": round(b_cr_d, 3),
            "B_SR_proj": round(b_sr_est, 4),
            "B_SR_err": round(b_sr_err, 4),
            "n_prompt_leak": n_prompt_leak,
            "B_over_Srec_pct": round(b_over_srec, 4),
        })

    thr_target_b = max(0.05, best_s1_row["B_tot"] * 1.5)
    tier1 = [r for r in s3_roc_rows if r["n_prompt_leak"] == 0 and r["B_over_Srec_pct"] < 1.0 and r["B_SR_proj"] <= thr_target_b]
    tier2 = [r for r in s3_roc_rows if r["n_prompt_leak"] == 0 and r["B_over_Srec_pct"] < 1.0]
    tier3 = [r for r in s3_roc_rows if r["S_rec_336fb"] >= 40.0]
    if tier1:
        best_s3_row = max(tier1, key=lambda r: (r["S_rec_336fb"], -r["B_SR_proj"]))
    elif tier2:
        best_s3_row = max(tier2, key=lambda r: (r["S_rec_336fb"], -r["B_SR_proj"]))
    else:
        best_s3_row = min(tier3 or s3_roc_rows, key=lambda r: (r["B_over_Srec_pct"], -r["S_rec_336fb"]))
    s3_best_thr = float(best_s3_row["threshold"])
    best_s3_srec = float(best_s3_row["S_rec_336fb"])

    wp_s3 = {"name": f"S3_GBDT_thr_{s3_best_thr:.4f}", "strategy": "S3", "thr": s3_best_thr, "wmax": 16.0, "tmax": 18.0, "q2hit_max": 180.0}
    s3_g4_yields = []
    for g4 in G4_MODELS:
        wg = g4_weights_arr[g4]
        mg_s0 = eval_wp_mask(mc, wp_s0)["s0"] & g4_fid_masks[g4]
        mg_s3 = g4_fid_masks[g4] & (mc_n_act >= 1) & s3_down_mc_nom & mc_in_zb_dt & (s3_score_mc >= s3_best_thr)
        s3_g4_yields.append(float(np.sum(wg[mg_s0 | mg_s3])))
    s3_g4_spread_pct = (max(s3_g4_yields) - min(s3_g4_yields)) / max(np.mean(s3_g4_yields), 1.0) * 100.0
    s3_cv_rows = [{"feature": fn, "gain_importance": round(float(imp), 5), "auc_gbdt": round(auc_gbdt, 5), "auc_logreg": round(auc_lr, 5), "s3_wall_s": round(s3_gpu_wall, 3)} for fn, imp in zip(S3_FEATURES, feat_imps)]
    write_tsv(out_dir / "s3_cv_benchmark.tsv", s3_cv_rows)
    write_tsv(out_dir / "s3_roc_scan.tsv", s3_roc_rows)
    print(f"[Task 5.2 S3 CPU-{args.workers}t {s3_gpu_wall:.2f}s] AUC_GBDT={auc_gbdt:.4f}, AUC_LogReg={auc_lr:.4f}, "
          f"selected S_rec={best_s3_srec:.2f} (thr={s3_best_thr:.4f}, B_SR={best_s3_row['B_SR_proj']:.4f}, prompt_leak={best_s3_row['n_prompt_leak']}), G4 spread={s3_g4_spread_pct:.2f}%", flush=True)

    # -----------------------------------------------------------------------
    # 4. Task 5.3: Full 30-Bin 2D Unfolding & 14 Systematic Nuisance Covariance
    # -----------------------------------------------------------------------
    y_mu_nom, qop_nom, reco_b30_nom = reco_bin30_arrays(mc, los_sign=canon_sign)
    truth_b30 = mc[canon_tb_key]

    # Truth denominators N_k^fid in Run 3 (nominal EPOS central) and Lead fraction per bin
    den30_box = np.zeros(30, dtype=np.float64)
    den30_lead = np.zeros(30, dtype=np.float64)
    for rn, wt in nom_run_w.items():
        th = genie_agg["truth"][rn]
        den30_box += wt * th[canon_tbox_key]
        den30_lead += wt * th[canon_tlead_key]
    den30_tot = np.maximum(den30_box + den30_lead, 1.0)
    f_lead_30 = den30_lead / den30_tot

    def _build_wp_pass_with_var(
        wp: dict[str, Any],
        dt_shift: float = 0.0,
        smear_scale: float = 1.0,
        use_cone75: bool = False,
        down_chi2_max: float = 10.0,
        za_mode: str = "era",
        q2_shift: float = 0.0,
        v20_thr: float = 40.0,
        tim_thr: float = 20.0,
        ps_thr: float = 2.5,
        theta_max: float = 25.0,
        rmax_max: float = 95.0,
        rift_max: float = 95.0,
        rvn_max: float = 120.0,
        misalign_sig: float = 0.0,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute exact selected mask + reco_bin30 under any systematic nuisance variation."""
        dt0_v = mc["dt0_cone75"] if use_cone75 else mc["dt0_unsmeared"] + smear_scale * (mc["dt0"] - mc["dt0_unsmeared"]) + dt_shift
        dt1_v = mc["dt1_cone75"] if use_cone75 else mc["dt1_unsmeared"] + smear_scale * (mc["dt1"] - mc["dt1_unsmeared"]) + dt_shift
        sig0_v = mc["sig_dt0_cone75"] if use_cone75 else mc["sig_dt0"]
        sig1_v = mc["sig_dt1_cone75"] if use_cone75 else mc["sig_dt1"]
        pull0_v = dt0_v / np.maximum(sig0_v, 0.05)
        pull1_v = dt1_v / np.maximum(sig1_v, 0.05)

        # Approximate delta chi2 shift when dt0/dt1 shifted
        dt_old_term = np.where(np.isfinite(mc["dt0"]), (mc["dt0"] / np.maximum(mc["sig_dt0"], 0.05)) ** 2, 0.0) + \
                      np.where(np.isfinite(mc["dt1"]), (mc["dt1"] / np.maximum(mc["sig_dt1"], 0.05)) ** 2, 0.0)
        dt_new_term = np.where(np.isfinite(dt0_v), pull0_v ** 2, 0.0) + np.where(np.isfinite(dt1_v), pull1_v ** 2, 0.0)
        dchi2_v = mc["dchi2_back"] + (dt_new_term - dt_old_term)

        kin_ok, p0_v = fast_kin_sr_mask(
            mc, v20_thr=v20_thr, tim_thr=tim_thr, ps_thr=ps_thr,
            theta_max=theta_max, rmax_max=rmax_max, rift_max=rift_max, rvn_max=rvn_max,
            misalign_sigma_qop=misalign_sig,
        )
        if misalign_sig > 0.0:
            qop_raw = mc["lead_q"] / np.maximum(mc["p0_gev"], 1.0)
            qop_s = qop_raw + misalign_sig * mc["z_misalign"]
            y_m, _, rb30 = reco_bin30_arrays(mc, los_sign=canon_sign)
            # Rebin with smeared q/p
            e_est_s = 1.0 / (0.8 * np.where(np.abs(qop_s) > 1e-6, qop_s, np.nan))
            qop_prime = np.sign(qop_s) * (np.abs(qop_s) * 0.8)
            ie_s = np.digitize(qop_prime, QOP_EDGES) - 1
            iy_s = np.digitize(y_m, Y_EDGES) - 1
            rb30 = np.where((iy_s >= 0) & (iy_s < 5) & (ie_s >= 0) & (ie_s < 6) & np.isfinite(qop_prime), iy_s * 6 + ie_s, -1)
        else:
            rb30 = reco_b30_nom

        if wp["strategy"] == "S3":
            _, _, nact = _zone_a_mask(mc, za_mode)
            s3_down_v = (
                np.isfinite(mc["t0_down"]) & (np.abs(mc["t0_down"]) < 2.5) &
                np.isfinite(mc["chi2_ndof_down"]) & (mc["chi2_ndof_down"] < down_chi2_max)
            )
            if down_chi2_max <= 10.0:
                s3_down_v = s3_down_v & ((mc["flags"] & FLAG_DOWN_OK) != 0)
            s3_dt_v = _in_zb_dt(mc, dt0_v, dt1_v)
            if dt_shift != 0.0 or smear_scale != 1.0 or use_cone75 or down_chi2_max > 10.0 or za_mode != "era":
                m_s3_ev = kin_ok & (nact >= 1) & s3_down_v & s3_dt_v
                s3_sc = np.zeros(len(mc["run"]), dtype=np.float64)
                if np.any(m_s3_ev):
                    x_var = np.column_stack([
                        mc["q0_raw"][m_s3_ev], mc["q1_raw"][m_s3_ev],
                        dt0_v[m_s3_ev], dt1_v[m_s3_ev], sig0_v[m_s3_ev], sig1_v[m_s3_ev],
                        mc["w0"][m_s3_ev], mc["w1"][m_s3_ev],
                        mc["chi2_ndof_down"][m_s3_ev], mc["r_vn"][m_s3_ev],
                    ]).astype(np.float32)
                    d_var = xgb.DMatrix(x_var, feature_names=S3_FEATURES)
                    s3_sc[m_s3_ev] = np.mean([b.predict(d_var) for b in s3_models], axis=0)
            else:
                s3_sc = s3_score_mc
            zb = kin_ok & (nact >= 1) & s3_down_v & s3_dt_v & (s3_sc >= wp["thr"])
            sel = kin_ok & ((nact == 0) | zb)
        else:
            r = eval_wp_mask(
                mc, wp, dt0_override=dt0_v, dt1_override=dt1_v,
                pull0_override=pull0_v, pull1_override=pull1_v, dchi2_override=dchi2_v,
                za_mode=za_mode, down_chi2_max=down_chi2_max, q2_shift=q2_shift,
            )
            sel = kin_ok & r["pass"]
            zb = kin_ok & r["zb"]
        return sel, zb, rb30

    def _compute_2d_components(wp: dict[str, Any], rw: dict[int, float] = nom_run_w, **var_kw: Any) -> dict[str, Any]:
        wg = _ev_weights(rw) if rw is not nom_run_w else w_nom
        sel, zb, rb30 = _build_wp_pass_with_var(wp, **var_kw)
        m_valid = sel & (wg > 0) & (rb30 >= 0)
        # Signal matrix Y_ik (reco i, truth k)
        m_sig = m_valid & (mc["genie_class"] == 1) & (truth_b30 >= 0)
        Y_ik = np.zeros((30, 30), dtype=np.float64)
        np.add.at(Y_ik, (rb30[m_sig], truth_b30[m_sig]), wg[m_sig])
        # Neutrino backgrounds per reco bin
        B_nu_nonfid = np.bincount(rb30[m_valid & (mc["genie_class"] == 2)], weights=wg[m_valid & (mc["genie_class"] == 2)], minlength=30)
        B_nu_other = np.bincount(rb30[m_valid & (mc["genie_class"] >= 3)], weights=wg[m_valid & (mc["genie_class"] >= 3)], minlength=30)
        return {
            "Y_ik": Y_ik,
            "B_nu_nonfid": B_nu_nonfid,
            "B_nu_other": B_nu_other,
            "zb_yield": float(np.sum(wg[zb & (wg > 0) & (mc["genie_class"] == 1)])),
        }

    # Build full profiled-likelihood covariance & breakdown for each key working point
    wp_suite = [
        ("S0", wp_s0),
        ("WP_Primary", wp_primary),
        ("WP_Strict", wp_strict),
        ("WP_S2", wp_s2),
        ("S3_GBDT", wp_s3),
    ]

    unfolding_rows: list[dict[str, Any]] = []
    syst_breakdown_rows: list[dict[str, Any]] = []
    wp_summary_metrics: dict[str, Any] = {}

    for label, wp in wp_suite:
        print(f"[Task 5.3] Building full 30-bin covariance for {label}...", flush=True)
        nom = _compute_2d_components(wp)
        Y_nom = nom["Y_ik"]
        eps_nom = np.sum(Y_nom, axis=0) / den30_tot
        # Normalized migration M_ik = Y_ik / sum_i Y_ik
        col_sum = np.maximum(np.sum(Y_nom, axis=0), 1e-12)
        M_nom = Y_nom / col_sum[None, :]
        mig_diag = np.diag(M_nom)

        # Zone-B data-driven mu background shape across 30 bins
        if label == "S3_GBDT":
            s3_row_best = s3_roc_rows[int(np.argmin(np.abs(thr_grid - wp["thr"])))]
            b_zb_tot = float(s3_row_best["B_SR_proj"])
            b_zb_err = float(s3_row_best["B_SR_err"])
        else:
            b_eval = bkg_eng.evaluate(wp)
            b_zb_tot = b_eval["B_tot"]
            b_zb_err = b_eval["B_err"]

        # Distribute Zone-B mu background proportionally to selected Zone-B reco shape (or flat over rapidity if tiny)
        zb_vec = np.zeros(30, dtype=np.float64)
        _, _, rb30_z = _build_wp_pass_with_var(wp)
        sel_z, zb_mask, _ = _build_wp_pass_with_var(wp)
        mz = zb_mask & (w_nom > 0) & (rb30_z >= 0) & (mc["genie_class"] == 1)
        if np.any(mz):
            zb_vec = np.bincount(rb30_z[mz], weights=w_nom[mz], minlength=30)
        zb_shape = zb_vec / max(np.sum(zb_vec), 1.0) if np.sum(zb_vec) > 0 else np.full(30, 1.0 / 30.0)
        B_mu_zb = b_zb_tot * zb_shape
        B_mu_zb_err = b_zb_err * zb_shape

        nu_nom = np.sum(Y_nom, axis=1) + nom["B_nu_nonfid"] + nom["B_nu_other"] + B_mu_zb
        nu_safe = np.maximum(nu_nom, 0.25)

        # Collect 1-sigma nuisance response vectors J[:, l] = d(nu_i) / d(theta_l) (keeping mu = 1)
        # Note nu_i(mu, theta) depends on mu through Y_ik(theta), so total derivative wrt theta at Asimov mu=1 is delta(sum_k Y_ik + B_i)!
        nuisances: list[tuple[str, str, np.ndarray]] = []

        # 1. Geant4 Hadron Physics List (5 models -> PCA / top deviations from mean/nominal across the 5 lists!)
        g4_vecs = []
        for g4 in G4_MODELS:
            rw = {}
            for geom in GEOM_TRIPLETS:
                rw.update(g4_wmaps[(geom, g4)])
            comp_g = _compute_2d_components(wp, rw=rw)
            g4_vecs.append(np.sum(comp_g["Y_ik"], axis=1) + comp_g["B_nu_nonfid"] + comp_g["B_nu_other"])
        g4_mat = np.array(g4_vecs) - (np.sum(Y_nom, axis=1) + nom["B_nu_nonfid"] + nom["B_nu_other"])[None, :]
        # Symmetric spread matrix C_g4 = max(|dev|) envelope or RMS*(sqrt(5/(5-1))) -> capture correlated modes via SVD of centered G4 deviations!
        g4_centered = np.array(g4_vecs) - np.mean(g4_vecs, axis=0, keepdims=True)
        # Normalize G4 modes by half-envelope scale so 1 sigma reflects half-range / RMS across lists cleanly
        u_g4, s_g4, vt_g4 = np.linalg.svd(g4_centered / math.sqrt(len(G4_MODELS) - 1.0), full_matrices=False)
        for m_idx in range(min(3, len(s_g4))):
            if s_g4[m_idx] > 1e-6:
                nuisances.append((f"Geant4_mode{m_idx}", "Geant4_Albedo", s_g4[m_idx] * vt_g4[m_idx]))

        # 2. Forward Neutrino Flux (EPOS vs SIBYLL, QGSJET, PythiaForward, CharmMin/Max)
        # Per PRD Sec. VI/VII.B: flux changes within-bin migration & neutrino bkg shape (holding truth bin normalization N_k^fid fixed per bin, OR propagating flux impact on eff + bkg!)
        flux_vecs = []
        for fname in ["EPOS_central", "SIBYLL", "QGSJET", "PythiaForward", "CharmMin", "CharmMax"]:
            rw = {}
            den30_f = np.zeros(30, dtype=np.float64)
            for geom in FLUX_VARIANTS:
                r_map = flux_wmaps[(geom, fname)]
                rw.update(r_map)
                for rn, wt in r_map.items():
                    th = genie_agg["truth"][rn]
                    den30_f += wt * (th[canon_tbox_key] + th[canon_tlead_key])
            comp_f = _compute_2d_components(wp, rw=rw)
            # Propagate signal efficiency/migration ratio (scaled to nominal N_k^fid!) + shifted neutrino bkg!
            scale_k = np.divide(den30_tot, np.maximum(den30_f, 1.0))
            Y_f_scaled = comp_f["Y_ik"] * scale_k[None, :]
            flux_vecs.append(np.sum(Y_f_scaled, axis=1) + comp_f["B_nu_nonfid"] + comp_f["B_nu_other"])
        f_nom = flux_vecs[0]
        # Separate light-hadron envelope (SIBYLL/QGSJET/PythiaForward vs EPOS) and Charm envelope
        for fname, idx in [("Flux_SIBYLL", 1), ("Flux_QGSJET", 2), ("Flux_Pythia", 3)]:
            nuisances.append((fname, "Forward_Flux", (flux_vecs[idx] - f_nom) / math.sqrt(3.0)))
        nuisances.append(("Flux_Charm", "Forward_Flux", 0.5 * (flux_vecs[5] - flux_vecs[4])))

        # 3. Timing Systematics (Scale +-0.15ns, Smearing +-15%, ConeLookup 75mm, DownChi2 SF, Zone-B Bkg)
        def _diff_sym(kw_up: dict[str, Any], kw_dn: dict[str, Any] | None = None) -> np.ndarray:
            cu = _compute_2d_components(wp, **kw_up)
            vu = np.sum(cu["Y_ik"], axis=1) + cu["B_nu_nonfid"] + cu["B_nu_other"]
            if kw_dn is not None:
                cd = _compute_2d_components(wp, **kw_dn)
                vd = np.sum(cd["Y_ik"], axis=1) + cd["B_nu_nonfid"] + cd["B_nu_other"]
                return 0.5 * (vu - vd)
            return vu - (np.sum(Y_nom, axis=1) + nom["B_nu_nonfid"] + nom["B_nu_other"])

        if label != "S0":
            nuisances.append(("Timing_Scale_0p15ns", "Timing_Calib", _diff_sym({"dt_shift": +0.15}, {"dt_shift": -0.15})))
            nuisances.append(("Timing_Res_15pct", "Timing_Calib", _diff_sym({"smear_scale": 1.15}, {"smear_scale": 0.85})))
            nuisances.append(("Timing_ConeLookup_75mm", "Timing_Calib", _diff_sym({"use_cone75": True})))
            nuisances.append(("Timing_DownChi2SF", "Timing_Calib", _diff_sym({"down_chi2_max": 10.0 / 1.49}, {"down_chi2_max": 10.0 * 1.49})))
            nuisances.append(("Timing_Bkg_ZoneB", "ZoneB_Bkg", B_mu_zb_err))
        else:
            for nm, gp in [("Timing_Scale_0p15ns", "Timing_Calib"), ("Timing_Res_15pct", "Timing_Calib"),
                           ("Timing_ConeLookup_75mm", "Timing_Calib"), ("Timing_DownChi2SF", "Timing_Calib"),
                           ("Timing_Bkg_ZoneB", "ZoneB_Bkg")]:
                nuisances.append((nm, gp, np.zeros(30, dtype=np.float64)))

        # 4. Event Selection, Detector & Alignment Systematics (PRD Sec. VII.D-E, I)
        nuisances.append(("VetoNu_ZoneA_2pC", "Detector_Selection", _diff_sym({"za_mode": "era_p2"}, {"za_mode": "era_m2"})))
        if label != "S0" and wp.get("q2hit_max", 1e9) < 1e8:
            nuisances.append(("VetoNu_Q2hit_10pC", "Detector_Selection", _diff_sym({"q2_shift": +10.0}, {"q2_shift": -10.0})))
        nuisances.append(("Downstream_Scint_20pct", "Detector_Selection",
                          _diff_sym({"v20_thr": 48.0, "tim_thr": 24.0, "ps_thr": 3.0},
                                    {"v20_thr": 32.0, "tim_thr": 16.0, "ps_thr": 2.0})))
        nuisances.append(("Track_Theta_1mrad", "Detector_Selection", _diff_sym({"theta_max": 26.0}, {"theta_max": 24.0})))
        nuisances.append(("Track_Rmax_1mm", "Detector_Selection", _diff_sym({"rmax_max": 96.0}, {"rmax_max": 94.0})))
        nuisances.append(("Track_RIFT_3mm", "Detector_Selection", _diff_sym({"rift_max": 98.0}, {"rift_max": 92.0})))
        nuisances.append(("Track_RVetoNu_5mm", "Detector_Selection", _diff_sym({"rvn_max": 125.0}, {"rvn_max": 115.0})))
        nuisances.append(("Tracking_Eff_1p8pct", "Detector_Selection", 0.018 * nu_nom))
        nuisances.append(("Early_Trig_0p5pct", "Detector_Selection", 0.005 * nu_nom))
        nuisances.append(("Misalign_qOp_PRD", "Misalignment", _diff_sym({"misalign_sig": 2.6e-4})))

        # 5. MC finite statistics nuisance (one per reco bin i via Barlow-Beeston light)
        nu_mc_stat_var = np.sum(Y_nom * (w_nom.mean() if False else 1.0), axis=1)
        # Approximate exact weighted MC sum(w^2) inside selected SR
        sel_nom, _, rb30_mc = _build_wp_pass_with_var(wp)
        m_mc_v = sel_nom & (w_nom > 0) & (rb30_mc >= 0)
        mc_stat_sig = np.sqrt(np.bincount(rb30_mc[m_mc_v], weights=w_nom[m_mc_v] ** 2, minlength=30))
        for ib in range(30):
            v_s = np.zeros(30, dtype=np.float64)
            v_s[ib] = mc_stat_sig[ib]
            nuisances.append((f"MC_Stat_bin{ib}", "MC_Stat", v_s))

        # Construct Fisher matrix H and invert cleanly
        L_nuis = len(nuisances)
        J_sig = Y_nom.copy()  # (30 reco i, 30 mu k)
        J_nuis = np.column_stack([v[2] for v in nuisances])  # (30 reco i, L nuis)
        J_full = np.hstack([J_sig, J_nuis])  # (30, 30 + L)

        # Fisher information: J^T W J + Lambda
        W_inv = 1.0 / nu_safe
        H_full = (J_full.T * W_inv[None, :]) @ J_full
        for l in range(L_nuis):
            H_full[30 + l, 30 + l] += 1.0
        # Tiny ridge on empty truth bins if any for numerical stability
        for k in range(30):
            if np.sum(Y_nom[:, k]) <= 0:
                H_full[k, k] += 1.0

        cov_full = np.linalg.inv(H_full)
        V_mu_tot = cov_full[:30, :30]
        V_n_tot = (den30_tot[:, None] * V_mu_tot) * den30_tot[None, :]

        # Statistical-only covariance (fix all theta = 0 -> invert J_sig^T W J_sig)
        H_stat = (J_sig.T * W_inv[None, :]) @ J_sig
        for k in range(30):
            if np.sum(Y_nom[:, k]) <= 0:
                H_stat[k, k] += 1.0
        V_mu_stat = np.linalg.inv(H_stat)
        V_n_stat = (den30_tot[:, None] * V_mu_stat) * den30_tot[None, :]

        # Cross-check Fisher H_full inversion against exact scipy L-BFGS-B profiled optimization on Asimov total signal strength!
        # Check relative uncertainty on total fiducial yield S_tot_fit = sum_k mu_k * N_k^fid
        def _rel_unc_from_V(V_n: np.ndarray) -> dict[str, Any]:
            tot_n = float(np.sum(den30_tot))
            tot_unc_y = math.sqrt(max(0.0, float(np.sum(V_n))))
            rel_tot = tot_unc_y / max(tot_n, 1.0) * 100.0
            # Add lumi (2.2%) & target mass (1% box vs 5% lead per bin -> correlated normalization!) in quadrature for cross-section interpretation
            mass_vec = den30_box * 0.01 + den30_lead * 0.05  # fully correlated mass uncertainty per bin
            lumi_vec = den30_tot * 0.022
            V_xsec = V_n + np.outer(mass_vec, mass_vec) + np.outer(lumi_vec, lumi_vec)
            rel_xsec_tot = math.sqrt(max(0.0, float(np.sum(V_xsec)))) / max(tot_n, 1.0) * 100.0
            # 5 rapidity projections
            y_uncs = []
            for a in range(5):
                sl = slice(a * 6, (a + 1) * 6)
                na = float(np.sum(den30_tot[sl]))
                y_uncs.append(math.sqrt(max(0.0, float(np.sum(V_n[sl, sl])))) / max(na, 1.0) * 100.0)
            # 6 energy (-L/E) projections & cross-section unc
            e_uncs, e_xsec_uncs = [], []
            for b in range(6):
                idx = np.arange(b, 30, 6)
                nb = float(np.sum(den30_tot[idx]))
                e_uncs.append(math.sqrt(max(0.0, float(np.sum(V_n[np.ix_(idx, idx)])))) / max(nb, 1.0) * 100.0)
                e_xsec_uncs.append(math.sqrt(max(0.0, float(np.sum(V_xsec[np.ix_(idx, idx)])))) / max(nb, 1.0) * 100.0)
            bin_rel = np.sqrt(np.maximum(0.0, np.diag(V_n))) / np.maximum(den30_tot, 1.0) * 100.0
            return {
                "rel_yield_tot_pct": rel_tot,
                "rel_xsec_tot_pct": rel_xsec_tot,
                "mean_bin30_rel_pct": float(np.mean(bin_rel)),
                "median_bin30_rel_pct": float(np.median(bin_rel)),
                "y_bin_rel_pct": y_uncs,
                "e_bin_rel_pct": e_uncs,
                "e_bin_xsec_rel_pct": e_xsec_uncs,
                "bin30_rel_pct": bin_rel,
            }

        u_tot_m = _rel_unc_from_V(V_n_tot)
        u_stat_m = _rel_unc_from_V(V_n_stat)

        # Group-by-group systematic breakdown (Fisher stat + group_g only, vs full minus group_g)
        group_names = sorted({g for _, g, _ in nuisances})
        for gn in group_names:
            g_indices = [i for i, (_, g, _) in enumerate(nuisances) if g == gn]
            # Fisher with ONLY stat + group gn active
            J_g = np.hstack([J_sig, np.column_stack([nuisances[i][2] for i in g_indices])])
            H_g = (J_g.T * W_inv[None, :]) @ J_g
            for l in range(len(g_indices)):
                H_g[30 + l, 30 + l] += 1.0
            for k in range(30):
                if np.sum(Y_nom[:, k]) <= 0:
                    H_g[k, k] += 1.0
            V_g = (den30_tot[:, None] * np.linalg.inv(H_g)[:30, :30]) * den30_tot[None, :]
            ug = _rel_unc_from_V(V_g)
            marg_pct = math.sqrt(max(0.0, ug["rel_yield_tot_pct"] ** 2 - u_stat_m["rel_yield_tot_pct"] ** 2))
            syst_breakdown_rows.append({
                "wp": label, "group": gn,
                "tot_yield_rel_pct": round(marg_pct, 4),
                "mean_e_bin_rel_pct": round(float(np.mean([math.sqrt(max(0.0, ug["e_bin_rel_pct"][b] ** 2 - u_stat_m["e_bin_rel_pct"][b] ** 2)) for b in range(6)])), 4),
                "mean_y_bin_rel_pct": round(float(np.mean([math.sqrt(max(0.0, ug["y_bin_rel_pct"][a] ** 2 - u_stat_m["y_bin_rel_pct"][a] ** 2)) for a in range(5)])), 4),
            })

        # Also numerical check via L-BFGS-B profiled negative log-likelihood (-2 ln L) at +1 sigma total shift of mu
        mu_shift = np.ones(30) * 1.01
        obs_asimov = nu_nom.copy()

        def _prof_nll(theta_vec: np.ndarray, mu_fix: np.ndarray) -> float:
            pred = np.maximum(1e-6, J_sig @ mu_fix + J_nuis @ theta_vec + (nu_nom - np.sum(Y_nom, axis=1)))
            return float(np.sum(2.0 * (pred - obs_asimov * np.log(pred))) + np.sum(theta_vec ** 2) - np.sum(2.0 * (obs_asimov - obs_asimov * np.log(np.maximum(obs_asimov, 1e-6)))))

        opt_r = optimize.minimize(_prof_nll, np.zeros(L_nuis), args=(mu_shift,), method="L-BFGS-B")
        nll_delta = float(opt_r.fun)
        # Expected Delta(-2 ln L) for mu -> 1.01 (1% coherent shift) = (1.0 / rel_tot)^2
        expected_delta = (1.0 / max(u_tot_m["rel_yield_tot_pct"], 1e-4)) ** 2

        corr_30 = V_n_tot / np.maximum(np.outer(np.sqrt(np.diag(V_n_tot)), np.sqrt(np.diag(V_n_tot))), 1e-12)

        for k in range(30):
            iy, ie = k // 6, k % 6
            unfolding_rows.append({
                "wp": label, "bin30": k, "y_bin": Y_LABELS[iy], "qop_bin": QOP_LABELS[ie],
                "N_fid_mc": round(float(den30_tot[k]), 3),
                "f_lead": round(float(f_lead_30[k]), 4),
                "eps_pct": round(float(eps_nom[k] * 100.0), 3),
                "M_diag_pct": round(float(mig_diag[k] * 100.0), 3),
                "S_reco": round(float(np.sum(Y_nom[k, :])), 3),
                "B_nu": round(float(nom["B_nu_nonfid"][k] + nom["B_nu_other"][k]), 3),
                "B_mu_zb": round(float(B_mu_zb[k]), 4),
                "rel_stat_pct": round(float(np.sqrt(V_n_stat[k, k]) / max(den30_tot[k], 1.0) * 100.0), 3),
                "rel_tot_pct": round(float(u_tot_m["bin30_rel_pct"][k]), 3),
            })

        wp_summary_metrics[label] = {
            "wp": wp,
            "S_fid_sel": float(np.sum(Y_nom)),
            "S_zb_sel": float(nom["zb_yield"]),
            "B_mu_zb": float(b_zb_tot),
            "B_mu_zb_err": float(b_zb_err),
            "G4_spread_pct": float((max(np.sum(v) for v in g4_vecs) - min(np.sum(v) for v in g4_vecs)) / max(np.sum(nu_nom - B_mu_zb), 1.0) * 100.0),
            "mean_eps_pct": float(np.mean(eps_nom) * 100.0),
            "mean_mig_diag_pct": float(np.mean(mig_diag) * 100.0),
            "rel_yield_stat_pct": u_stat_m["rel_yield_tot_pct"],
            "rel_yield_tot_pct": u_tot_m["rel_yield_tot_pct"],
            "rel_xsec_tot_pct": u_tot_m["rel_xsec_tot_pct"],
            "mean_bin30_rel_pct": u_tot_m["mean_bin30_rel_pct"],
            "y_bin_rel_pct": u_tot_m["y_bin_rel_pct"],
            "e_bin_rel_pct": u_tot_m["e_bin_rel_pct"],
            "e_bin_xsec_rel_pct": u_tot_m["e_bin_xsec_rel_pct"],
            "lbfgsb_nll_1pct_shift": nll_delta,
            "fisher_nll_1pct_shift": expected_delta,
            "corr_30": corr_30,
        }
        print(f"  -> {label}: S={np.sum(Y_nom):.2f}, B_zb={b_zb_tot:.3f}, G4_spread={wp_summary_metrics[label]['G4_spread_pct']:.2f}%, "
              f"yield_rel_unc={u_tot_m['rel_yield_tot_pct']:.3f}% (stat={u_stat_m['rel_yield_tot_pct']:.3f}%), xsec_rel_unc={u_tot_m['rel_xsec_tot_pct']:.3f}% "
              f"[L-BFGS-B={nll_delta:.6f} vs Fisher={expected_delta:.6f}]", flush=True)

    write_tsv(out_dir / "unfolding_30bin_comparison.tsv", unfolding_rows)
    write_tsv(out_dir / "systematics_breakdown.tsv", syst_breakdown_rows)

    # -----------------------------------------------------------------------
    # 5. 6D Phase Space Efficiency & G4 Spread Curves (E_nu, pz_mu, y_inel, z_vtx, r_vtx, q_mu)
    # -----------------------------------------------------------------------
    e_edges = np.array([100, 150, 200, 250, 300, 400, 500, 650, 800, 1000, 1250, 1500, 1800, 2200, 2600, 3000, 3600, 4200, 5000, 6000, 7500, 9000, 11000, 15000, 20000], dtype=np.float64)
    pz_edges = np.array([100, 140, 180, 230, 300, 380, 480, 600, 750, 950, 1200, 1500, 1900, 2400, 3000, 3800, 4800, 6000, 7500, 9500, 12000, 15000, 18000, 22000, 30000], dtype=np.float64)
    y_inel_edges = np.linspace(0.0, 1.0, 21)
    z_vtx_edges = np.linspace(-3100.0, -1600.0, 31)
    r_vtx_edges = np.linspace(0.0, 100.0, 21)
    q_mu_edges = np.array([-0.5, 0.5, 1.5])

    # Truth denominators summed across nominal runs
    den_6d = {k: np.zeros_like(genie_agg["truth"][200082][k]) for k in ["fid_E_nu", "fid_pz_mu", "fid_y_inel", "fid_z_vtx", "fid_r_vtx", "fid_q_mu"]}
    for rn, wt in nom_run_w.items():
        for k in den_6d:
            den_6d[k] += wt * genie_agg["truth"][rn][k]

    var_specs = [
        ("E_nu", "truth_E_gev", e_edges, "fid_E_nu"),
        ("pz_mu", "truth_pz_mu_gev", pz_edges, "fid_pz_mu"),
        ("y_inel", "truth_y_inel", y_inel_edges, "fid_y_inel"),
        ("z_vtx", "truth_z_mm", z_vtx_edges, "fid_z_vtx"),
        ("r_vtx", "truth_r_mm", r_vtx_edges, "fid_r_vtx"),
        ("q_mu", None, q_mu_edges, "fid_q_mu"),
    ]
    rows_6d: list[dict[str, Any]] = []
    wp_6d_masks = {lbl: _build_wp_pass_with_var(wp)[0] for lbl, wp in wp_suite[:4]}
    q_idx_mc = np.where(mc["truth_pdg"] > 0, 0, 1).astype(np.float64)

    for vname, col, edges, dkey in var_specs:
        vals = q_idx_mc if col is None else mc[col]
        den_v = den_6d[dkey]
        for bi in range(len(edges) - 1):
            in_b = m_fid_sr & np.isfinite(vals) & (vals >= edges[bi]) & (vals < edges[bi + 1])
            if col == "truth_y_inel":
                in_b = in_b & (mc["primary_valid"] == 1)
            row = {"variable": vname, "bin": bi, "edge_lo": float(edges[bi]), "edge_hi": float(edges[bi + 1]), "N_fid": round(float(den_v[bi]), 3)}
            for lbl in ["S0", "WP_Primary", "WP_Strict", "WP_S2"]:
                m_sel = in_b & wp_6d_masks[lbl] & (w_nom > 0)
                num = float(np.sum(w_nom[m_sel]))
                eps = (num / den_v[bi] * 100.0) if den_v[bi] > 0 else 0.0
                # 5-G4 spread in bin
                g4_y = [float(np.sum(g4_weights_arr[g4][in_b & wp_6d_masks[lbl] & g4_fid_masks[g4]])) for g4 in G4_MODELS]
                g4_sp = (max(g4_y) - min(g4_y)) / max(np.mean(g4_y), 1e-6) * 100.0 if np.mean(g4_y) > 0 else 0.0
                row[f"{lbl}_yield"] = round(num, 3)
                row[f"{lbl}_eps_pct"] = round(eps, 3)
                row[f"{lbl}_g4_spread_pct"] = round(g4_sp, 3)
            rows_6d.append(row)
    write_tsv(out_dir / "phase_space_6d_gains.tsv", rows_6d)

    # -----------------------------------------------------------------------
    # 6. Task 5.4: F7_pz0_raw_v1 Energy-ML Coupling & VetoNu-Charge Ablation (CUDA)
    # -----------------------------------------------------------------------
    print("[Task 5.4] Running F7_pz0_raw_v1 (62 vs 58 VetoNu-ablated) GPU energy study...", flush=True)
    # Load Stage 199 split mapping ONCE into RAM so family roles (1=train, 2=cal, 3=test) match Stage 199 with zero leakage
    with np.load(REPO_DIR / "ntuples/energy_ml_stage199/split.npz", allow_pickle=True) as s199_split, \
         np.load(REPO_DIR / "ntuples/energy_ml_stage199/input.npz", allow_pickle=True) as s199_inp:
        sp_role = np.asarray(s199_split["role"], dtype=np.int8)
        sp_eid = np.asarray(s199_split["eventID"], dtype=np.int64)
        in_cf = np.asarray(s199_inp["canonical_flux"]).astype(str)
        in_inc = np.round(np.asarray(s199_inp["incoming"], dtype=np.float32), 2)
    f7_names = json.loads((REPO_DIR / "ml/configs/audited_features.json").read_text())["features"]
    f58_idx = [i for i in range(62) if i not in F7_VETONU_INDICES]
    f58_names = [f7_names[i] for i in f58_idx]

    # Map (canonical_flux, eventID) -> role and incoming tuple -> role from Stage 199 in O(N) Python time
    sp_role_list = sp_role.tolist()
    cf_eid_role_map: dict[tuple[str, int], int] = dict(zip(zip(in_cf.tolist(), sp_eid.tolist()), sp_role_list))
    inc_role_map: dict[tuple[float, float, float, float], int] = dict(zip(map(tuple, in_inc.tolist()), sp_role_list))

    # Exact Stage 199 canonical_flux strings for 200080..200101 + 200137..200147, plus G4 alt (EPOS central)
    cnames = [
        "sibyll_pi", "sibyll_k", "epos_pi", "epos_k", "qgsjet_pi", "qgsjet_k",
        "pythia_forward_pi", "pythia_forward_k",
        "powheg_pythia_charm_min", "powheg_pythia_charm_central", "powheg_pythia_charm_max",
    ]
    run_to_cflux = {}
    for idx_f, r_num in enumerate(range(200080, 200091)):
        run_to_cflux[r_num] = cnames[idx_f]
        run_to_cflux[200091 + idx_f] = cnames[idx_f]
        run_to_cflux[200137 + idx_f] = cnames[idx_f]
    for g4_base in [200104, 200107, 200110, 200113, 200160, 200163, 200166, 200169, 200172, 200175, 200178, 200181]:
        run_to_cflux[g4_base] = "epos_pi"
        run_to_cflux[g4_base + 1] = "epos_k"
        run_to_cflux[g4_base + 2] = "powheg_pythia_charm_central"

    # Select all fiducial numu CC events passing Kinematic SR in runs 200080..200101 for ML study
    ml_run_mask = (mc["run"] >= 200080) & (mc["run"] <= 200101) & m_fid_sr & np.isfinite(mc["truth_E_gev"]) & (mc["truth_E_gev"] > 50.0)
    ml_idx = np.flatnonzero(ml_run_mask)
    ml_cfs = [run_to_cflux[rn] for rn in mc["run"][ml_idx].tolist()]
    ml_eids = mc["eventID"][ml_idx].tolist()
    ml_inc_list = np.round(
        np.column_stack([
            mc["truth_pdg"][ml_idx],
            mc["incoming_px_mev"][ml_idx],
            mc["incoming_py_mev"][ml_idx],
            mc["incoming_pz_mev"][ml_idx],
        ]).astype(np.float32),
        2,
    ).tolist()
    ml_roles_list = [0] * len(ml_idx)
    for ii, (cf, eid, inc_row) in enumerate(zip(ml_cfs, ml_eids, ml_inc_list)):
        role = cf_eid_role_map.get((cf, eid), 0)
        if role == 0:
            role = inc_role_map.get((inc_row[0], inc_row[1], inc_row[2], inc_row[3]), 0)
        if role == 0:
            h = hash((cf, eid)) & 0xFFFFFFFF
            u = (h % 10000) / 10000.0
            role = 1 if u < 0.70 else (2 if u < 0.85 else 3)
        ml_roles_list[ii] = role
    ml_roles = np.asarray(ml_roles_list, dtype=np.int8)

    # De-duplicate identical incoming weights within each split (matching Stage 199: 1/count(incoming))
    ml_X62 = mc["x_ml"][ml_idx].astype(np.float32)
    ml_X58 = ml_X62[:, f58_idx]
    ml_y = np.log(mc["truth_E_gev"][ml_idx].astype(np.float64))
    ml_E_true = mc["truth_E_gev"][ml_idx].astype(np.float64)
    ml_pz = mc["pz0_gev"][ml_idx].astype(np.float64)
    ml_y_inel = mc["truth_y_inel"][ml_idx].astype(np.float64)
    ml_z_vtx = mc["truth_z_mm"][ml_idx].astype(np.float64)
    ml_prim_val = mc["primary_valid"][ml_idx] == 1

    # WP_Primary & S0 masks restricted to ml_idx
    wp_prim_eval = eval_wp_mask(mc, wp_primary)
    ml_is_s0 = wp_prim_eval["s0"][ml_idx]
    ml_is_zb = wp_prim_eval["zb"][ml_idx]
    ml_is_s1 = wp_prim_eval["pass"][ml_idx]

    # Sample weight = 1 / count(same (cf, eid)) within split so no family dominates
    ml_w = np.ones(len(ml_idx), dtype=np.float64)
    for r_id in [1, 2, 3]:
        sub = np.flatnonzero(ml_roles == r_id)
        keys = [(ml_cfs[j], ml_eids[j]) for j in sub.tolist()]
        counts = Counter(keys)
        ml_w[sub] = [1.0 / counts[k] for k in keys]

    tr_all = ml_roles == 1
    cal_all = ml_roles == 2
    te_all = ml_roles == 3

    seeds_199 = [2026110255, 2026110256, 2026110257]
    xgb_f7_params = {
        "objective": "reg:squarederror",
        "max_depth": 5, "eta": 0.04, "subsample": 0.8,
        "colsample_bytree": 1.0, "min_child_weight": 20, "reg_lambda": 10,
        "tree_method": "hist", "device": "cpu", "nthread": args.workers,
    }

    def _fit_predict_f7(X_mat: np.ndarray, f_names: list[str], train_mask: np.ndarray, cal_mask: np.ndarray) -> tuple[np.ndarray, float, list[xgb.Booster], float]:
        t0_f = time.perf_counter()
        init_score = float(np.average(ml_y[train_mask], weights=ml_w[train_mask]))
        dtr = xgb.DMatrix(X_mat[train_mask], label=ml_y[train_mask], weight=ml_w[train_mask], feature_names=f_names)
        dall = xgb.DMatrix(X_mat, feature_names=f_names)
        preds = []
        boosters = []
        for sd in seeds_199:
            bst = xgb.train(dict(xgb_f7_params, seed=sd, base_score=init_score, boost_from_average=0), dtr, num_boost_round=400)
            preds.append(bst.predict(dall))
            boosters.append(bst)
        raw = np.mean(preds, axis=0)
        offset = float(np.average(ml_y[cal_mask] - raw[cal_mask], weights=ml_w[cal_mask]))
        return np.exp(raw + offset), time.perf_counter() - t0_f, boosters, offset

    pred_m0 = ml_pz / 0.8
    pred_m1, t_m1, bst_m1, off_m1 = _fit_predict_f7(ml_X62, f7_names, tr_all & ml_is_s0, cal_all & ml_is_s0)
    pred_m2, t_m2, bst_m2, off_m2 = _fit_predict_f7(ml_X58, f58_names, tr_all & ml_is_s0, cal_all & ml_is_s0)
    pred_m3, t_m3, bst_m3, off_m3 = _fit_predict_f7(ml_X58, f58_names, tr_all & ml_is_s1, cal_all & ml_is_s1)
    pred_m4, t_m4, bst_m4, off_m4 = _fit_predict_f7(ml_X62, f7_names, tr_all & ml_is_s1, cal_all & ml_is_s1)

    def _ml_metrics_arrays(e_hat: np.ndarray, e_t: np.ndarray, w_e: np.ndarray) -> dict[str, float]:
        if len(e_t) == 0:
            return {"N": 0, "log_RMSE": float("nan"), "mean_bias_pct": float("nan"), "median_bias_pct": float("nan"), "R68_pct": float("nan"), "tail50_pct": float("nan")}
        e_p = np.maximum(e_hat, 1e-3)
        lerr = np.log(e_p / e_t)
        rel_err = (e_p - e_t) / e_t * 100.0
        order = np.argsort(rel_err)
        cw = np.cumsum(w_e[order]) / np.sum(w_e)
        p16, p50, p84 = np.interp([0.16, 0.50, 0.84], cw, rel_err[order])
        log_rmse = math.sqrt(float(np.average(lerr ** 2, weights=w_e)))
        mean_bias = float(np.average(rel_err, weights=w_e))
        tail50 = float(np.average((np.abs(rel_err) > 50.0).astype(float), weights=w_e) * 100.0)
        return {
            "N": int(len(e_t)),
            "log_RMSE": round(log_rmse, 4),
            "mean_bias_pct": round(mean_bias, 2),
            "median_bias_pct": round(float(p50), 2),
            "R68_pct": round(float(0.5 * (p84 - p16)), 2),
            "tail50_pct": round(tail50, 2),
        }

    def _ml_metrics(e_hat: np.ndarray, m_eval: np.ndarray) -> dict[str, float]:
        return _ml_metrics_arrays(e_hat[m_eval], ml_E_true[m_eval], ml_w[m_eval])

    eval_strata = [
        ("Test_ZoneA_S0", te_all & ml_is_s0),
        ("Test_ZoneB_Rescued", te_all & ml_is_zb),
        ("Test_WP_Primary_All", te_all & ml_is_s1),
        ("Test_WP_Primary_HighY", te_all & ml_is_s1 & ml_prim_val & (ml_y_inel >= 0.5)),
        ("Test_WP_Primary_UpstreamZ", te_all & ml_is_s1 & (ml_z_vtx < -2700.0)),
    ]
    models_ml = [
        ("M0_pz0_over_0p8", pred_m0, 0.0),
        ("M1_F7_62_trainS0", pred_m1, t_m1),
        ("M2_F7_58_noVN_trainS0", pred_m2, t_m2),
        ("M3_F7_58_noVN_trainS1", pred_m3, t_m3),
        ("M4_F7_62_trainS1", pred_m4, t_m4),
    ]
    ml_rows: list[dict[str, Any]] = []
    for s_name, sm in eval_strata:
        for m_name, e_hat, fit_s in models_ml:
            met = _ml_metrics(e_hat, sm)
            ml_rows.append({"stratum": s_name, "model": m_name, "fit_wall_s": round(fit_s, 3), **met})

    # Also evaluate M0..M4 on held-out alternative Geant4 hadronic physics lists (200104..200115, 200160..200183)
    g4alt_mask = (
        (((mc["run"] >= 200104) & (mc["run"] <= 200115)) | ((mc["run"] >= 200160) & (mc["run"] <= 200183)))
        & m_fid_sr & wp_prim_eval["pass"] & np.isfinite(mc["truth_E_gev"]) & (mc["truth_E_gev"] > 50.0)
    )
    if np.any(g4alt_mask):
        g4_idx = np.flatnonzero(g4alt_mask)
        g4_keep = np.array([
            cf_eid_role_map.get((run_to_cflux[int(mc["run"][gi])], int(mc["eventID"][gi])), 3) not in (1, 2)
            for gi in g4_idx
        ], dtype=bool)
        g4_idx = g4_idx[g4_keep]
        if len(g4_idx) > 0:
            x62_g4 = mc["x_ml"][g4_idx].astype(np.float32)
            x58_g4 = x62_g4[:, f58_idx]
            d62_g4 = xgb.DMatrix(x62_g4, feature_names=f7_names)
            d58_g4 = xgb.DMatrix(x58_g4, feature_names=f58_names)
            w_g4 = np.ones(len(g4_idx), dtype=np.float64)
            et_g4 = mc["truth_E_gev"][g4_idx].astype(np.float64)
            g4_preds = [
                ("M0_pz0_over_0p8", mc["pz0_gev"][g4_idx].astype(np.float64) / 0.8, 0.0),
                ("M1_F7_62_trainS0", np.exp(np.mean([b.predict(d62_g4) for b in bst_m1], axis=0) + off_m1), t_m1),
                ("M2_F7_58_noVN_trainS0", np.exp(np.mean([b.predict(d58_g4) for b in bst_m2], axis=0) + off_m2), t_m2),
                ("M3_F7_58_noVN_trainS1", np.exp(np.mean([b.predict(d58_g4) for b in bst_m3], axis=0) + off_m3), t_m3),
                ("M4_F7_62_trainS1", np.exp(np.mean([b.predict(d62_g4) for b in bst_m4], axis=0) + off_m4), t_m4),
            ]
            for m_name, e_hat_g4, fit_s in g4_preds:
                met = _ml_metrics_arrays(e_hat_g4, et_g4, w_g4)
                ml_rows.append({"stratum": "Test_WP_Primary_G4Alt", "model": m_name, "fit_wall_s": round(fit_s, 3), **met})

    # Check 30-bin migration diagonal purity using M0 (pz0/0.8 -> p0/0.8) vs M3 (F7_58_noVN) on Test_WP_Primary
    d_m3_mc = xgb.DMatrix(mc["x_ml"][:, f58_idx].astype(np.float32), feature_names=f58_names)
    raw_m3_mc = np.mean([b.predict(d_m3_mc) for b in bst_m3], axis=0)
    e_hat_m3_mc = np.exp(raw_m3_mc + off_m3)
    _, _, rb30_m3 = reco_bin30_arrays(mc, los_sign=canon_sign, use_direct_e=e_hat_m3_mc)

    # Compute M_ii comparison on ml_idx[te_all & ml_is_s1]
    te_s1_gi = ml_idx[te_all & ml_is_s1]
    tb_te = truth_b30[te_s1_gi]
    rb_m0_te = reco_b30_nom[te_s1_gi]
    rb_m3_te = rb30_m3[te_s1_gi]
    w_te = ml_w[te_all & ml_is_s1]
    Y_m0_te = np.zeros((30, 30))
    Y_m3_te = np.zeros((30, 30))
    ok0 = (tb_te >= 0) & (rb_m0_te >= 0)
    ok3 = (tb_te >= 0) & (rb_m3_te >= 0)
    np.add.at(Y_m0_te, (rb_m0_te[ok0], tb_te[ok0]), w_te[ok0])
    np.add.at(Y_m3_te, (rb_m3_te[ok3], tb_te[ok3]), w_te[ok3])
    M_m0_diag = float(np.mean(np.diag(Y_m0_te) / np.maximum(np.sum(Y_m0_te, axis=0), 1.0)) * 100.0)
    M_m3_diag = float(np.mean(np.diag(Y_m3_te) / np.maximum(np.sum(Y_m3_te, axis=0), 1.0)) * 100.0)
    write_tsv(out_dir / "energy_ml_f7_ablation.tsv", ml_rows)
    print(f"[Task 5.4 Complete] 30-bin migration diagonal purity (Test WP_Primary): pz0/0.8={M_m0_diag:.2f}% vs F7_58_noVN={M_m3_diag:.2f}%", flush=True)

    # -----------------------------------------------------------------------
    # 7. Save Frozen Working-Point Table, JSON Summary & 6 Publication PNGs
    # -----------------------------------------------------------------------
    frozen_rows = []
    for label, wp in wp_suite:
        wm = wp_summary_metrics[label]
        if label in ("S0", "WP_Primary", "WP_Strict", "WP_S2"):
            r_match = next(r for r in grid_rows if r["name"] == wp["name"])
            b_comp = {k: r_match[k] for k in ["B1", "B2", "B3", "B4", "B5", "B_tot", "B_err", "B_over_Srec_pct", "B_over_sqrtS"]}
        else:
            b_comp = {"B1": 0.0, "B2": 0.0, "B3": wm["B_mu_zb"], "B4": 0.0, "B5": 0.0, "B_tot": wm["B_mu_zb"], "B_err": wm["B_mu_zb_err"],
                      "B_over_Srec_pct": round(wm["B_mu_zb"] / max(wm["S_zb_sel"], 1.0) * 100.0, 3),
                      "B_over_sqrtS": round(wm["B_mu_zb"] / math.sqrt(max(wm["S_fid_sel"], 1.0)), 4)}
        frozen_rows.append({
            "label": label, "name": wp["name"], "strategy": wp["strategy"],
            "S_tot_336fb": round(wm["S_fid_sel"], 2), "S_zb_rescued": round(wm["S_zb_sel"], 2),
            **b_comp,
            "G4_spread_pct": round(wm["G4_spread_pct"], 3),
            "mean_eps_pct": round(wm["mean_eps_pct"], 2),
            "mean_mig_diag_pct": round(wm["mean_mig_diag_pct"], 2),
            "rel_yield_stat_pct": round(wm["rel_yield_stat_pct"], 3),
            "rel_yield_tot_pct": round(wm["rel_yield_tot_pct"], 3),
            "rel_xsec_tot_pct": round(wm["rel_xsec_tot_pct"], 3),
        })
    write_tsv(out_dir / "frozen_working_points.tsv", frozen_rows)

    # Generate 6 Publication Figures
    _make_figures(out_dir, grid_rows, frozen_rows, s3_roc_rows, s3_cv_rows, wp_summary_metrics, unfolding_rows, syst_breakdown_rows, rows_6d, ml_rows, M_m0_diag, M_m3_diag)

    summary = {
        "stage": 216,
        "load_wall_s": round(load_s, 3),
        "total_wall_s": round(time.perf_counter() - t_start, 3),
        "n_data_runs_active": n_data_runs_active,
        "n_data_events_active": n_data_events_active,
        "n_data_blinded_sr_zoneb_skipped": n_data_blinded_tot,
        "los_audit": los_audit,
        "canonical_los_sign_mm": canon_sign,
        "frozen_wps": {"S0": wp_s0, "WP_Primary": wp_primary, "WP_Strict": wp_strict, "WP_S2": wp_s2, "S3_GBDT": wp_s3},
        "frozen_metrics": frozen_rows,
        "s3_benchmark": {"auc_gbdt": auc_gbdt, "auc_logreg": auc_lr, "gpu_wall_s": s3_gpu_wall, "best_thr": s3_best_thr, "g4_spread_pct": s3_g4_spread_pct},
        "energy_ml_f7": {"M_m0_diag_pct": M_m0_diag, "M_m3_diag_pct": M_m3_diag, "rows": ml_rows},
    }
    (out_dir / "t5_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"=== Stage T5 COMPLETE in {summary['total_wall_s']:.2f} s -> {out_dir} ===", flush=True)


def _make_figures(
    out_dir: Path,
    grid_rows: list[dict[str, Any]],
    frozen_rows: list[dict[str, Any]],
    s3_roc_rows: list[dict[str, Any]],
    s3_cv_rows: list[dict[str, Any]],
    wp_summary_metrics: dict[str, Any],
    unfolding_rows: list[dict[str, Any]],
    syst_breakdown_rows: list[dict[str, Any]],
    rows_6d: list[dict[str, Any]],
    ml_rows: list[dict[str, Any]],
    m0_diag: float,
    m3_diag: float,
) -> None:
    plt.rcParams.update({"font.size": 10, "axes.grid": True, "grid.alpha": 0.25})

    # Fig 1: WP optimization Pareto plane (S_recovered vs B_ZoneB + total proxy unc)
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2), dpi=160)
    ax = axes[0]
    for st, col, mk in [("S1", "#1f77b4", "o"), ("S2", "#ff7f0e", "s")]:
        sub = [r for r in grid_rows if r["strategy"] == st]
        ax.scatter([r["S_rec_336fb"] for r in sub], [max(r["B_tot"], 5e-4) for r in sub], c=col, marker=mk, alpha=0.55, s=26, label=f"{st} grid")
    ax.plot([r["S_rec_336fb"] for r in s3_roc_rows], [max(r["B_SR_proj"], 5e-4) for r in s3_roc_rows], "k--", lw=1.8, label="S3 GBDT ROC")
    for fr, col, mk in zip(frozen_rows[1:], ["#2ca02c", "#17becf", "#d62728", "#9467bd"], ["*", "D", "P", "^"]):
        ax.scatter([fr["S_zb_rescued"]], [max(fr["B_tot"], 5e-4)], c=col, marker=mk, s=160, zorder=10, edgecolors="k", label=fr["label"])
    ax.set_yscale("log")
    ax.set_xlabel(r"Rescued $\nu_\mu$ CC Signal $S_{\mathrm{rec}}$ (335.92 fb$^{-1}$)")
    ax.set_ylabel(r"Estimated Zone-B Background $B_{\mathrm{tot}}$ (log)")
    ax.set_title("Blind Working-Point Pareto Frontier (Signal vs Background)")
    ax.legend(fontsize=8, loc="upper left")

    ax2 = axes[1]
    names = [r["label"] for r in frozen_rows]
    vals = [r["rel_yield_tot_pct"] for r in frozen_rows]
    stats = [r["rel_yield_stat_pct"] for r in frozen_rows]
    x = np.arange(len(names))
    ax2.bar(x - 0.18, vals, width=0.35, color="#1f77b4", label="Total Post-Fit Yield Unc.")
    ax2.bar(x + 0.18, stats, width=0.35, color="#aec7e8", label="Stat-Only Yield Unc.")
    ax2.set_xticks(x)
    ax2.set_xticklabels(names, rotation=20, ha="right")
    ax2.set_ylabel("Relative Unfolded Yield Uncertainty [%]")
    ax2.set_title("Full 30-Bin Profiled Likelihood Uncertainty by Strategy")
    ax2.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(out_dir / "fig1_wp_optimization_plane.png")
    plt.close(fig)

    # Fig 2: S3 ROC & Feature Importance
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2), dpi=160)
    ax = axes[0]
    ax.plot([r["S_rec_336fb"] for r in s3_roc_rows], [max(r["B_over_Srec_pct"], 1e-3) for r in s3_roc_rows], "k-", lw=2.0, label=f"S3 GBDT (AUC={s3_cv_rows[0]['auc_gbdt']:.4f})")
    for fr, col, mk in zip(frozen_rows[1:4], ["#2ca02c", "#17becf", "#d62728"], ["*", "D", "P"]):
        ax.scatter([fr["S_zb_rescued"]], [max(fr["B_over_Srec_pct"], 1e-3)], c=col, marker=mk, s=160, edgecolors="k", zorder=10, label=f"{fr['label']} ({fr['B_over_Srec_pct']:.3f}%)")
    ax.axhline(1.0, color="#17becf", ls=":", label="1% Ultra-Pure Target")
    ax.set_yscale("log")
    ax.set_ylim(8e-4, 200.0)
    ax.set_xlabel(r"Rescued Signal $S_{\mathrm{rec}}$ (335.92 fb$^{-1}$)")
    ax.set_ylabel(r"$B_{\mathrm{ZoneB}} / S_{\mathrm{rec}}$ [%]")
    ax.set_title("S3 GBDT Upper Bound vs Frozen Analytical Working Points")
    ax.legend(fontsize=8.5)

    ax2 = axes[1]
    s3_sorted = sorted(s3_cv_rows, key=lambda r: r["gain_importance"])
    ax2.barh([r["feature"] for r in s3_sorted], [r["gain_importance"] for r in s3_sorted], color="#4c72b0")
    ax2.set_xlabel("Normalized Gain Importance (5-Fold GroupKFold)")
    ax2.set_title("S3 10 Audited Zone-B Features Importance")
    fig.tight_layout()
    fig.savefig(out_dir / "fig2_s3_roc_and_feature_audit.png")
    plt.close(fig)

    # Fig 3: 30-Bin Efficiency & Post-Fit Relative Uncertainties (S0 vs WP_Primary vs WP_Strict)
    fig, axes = plt.subplots(1, 2, figsize=(14.0, 5.2), dpi=160)
    b_idx = np.arange(30)
    for lbl, col, ls in [("S0", "#7f7f7f", "-"), ("WP_Primary", "#2ca02c", "-"), ("WP_Strict", "#17becf", "--")]:
        sub = [r for r in unfolding_rows if r["wp"] == lbl]
        axes[0].plot(b_idx, [r["eps_pct"] for r in sub], color=col, ls=ls, lw=1.8, label=lbl)
        axes[1].plot(b_idx, [r["rel_tot_pct"] for r in sub], color=col, ls=ls, lw=1.8, label=lbl)
    for ax in axes:
        for sep in [6, 12, 18, 24]:
            ax.axvline(sep - 0.5, color="k", ls=":", alpha=0.35)
        ax.set_xlabel("2D Bin Index k = 6*y_bin + q/p'_bin (0..29)")
    axes[0].set_ylabel(r"Total Signal Efficiency $\epsilon_k$ [%]")
    axes[0].set_title(r"30-Bin 2D $(y_\nu, -L/E_\nu)$ Signal Efficiency Recovery")
    axes[0].legend()
    axes[1].set_ylabel("Post-Fit Bin Total Uncertainty [%]")
    axes[1].set_title("30-Bin Post-Fit Relative Uncertainty")
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig3_30bin_2d_unfolding_precision.png")
    plt.close(fig)

    # Fig 4: Systematic Variance Budget + 30x30 Correlation Matrix (WP_Primary)
    fig, axes = plt.subplots(1, 2, figsize=(14.0, 5.4), dpi=160)
    groups = sorted({r["group"] for r in syst_breakdown_rows})
    xg = np.arange(len(groups))
    v_s0 = [next((r["tot_yield_rel_pct"] for r in syst_breakdown_rows if r["wp"] == "S0" and r["group"] == g), 0.0) for g in groups]
    v_p1 = [next((r["tot_yield_rel_pct"] for r in syst_breakdown_rows if r["wp"] == "WP_Primary" and r["group"] == g), 0.0) for g in groups]
    axes[0].bar(xg - 0.18, v_s0, width=0.35, color="#8c8c8c", label="S0 Baseline")
    axes[0].bar(xg + 0.18, v_p1, width=0.35, color="#2ca02c", label="WP_Primary (S1)")
    axes[0].set_xticks(xg)
    axes[0].set_xticklabels(groups, rotation=30, ha="right")
    axes[0].set_ylabel("Marginal Total Yield Uncertainty [%]")
    axes[0].set_title("14-Group Systematic Breakdown (S0 vs WP_Primary)")
    axes[0].legend()

    im = axes[1].imshow(wp_summary_metrics["WP_Primary"]["corr_30"], cmap="RdBu_r", vmin=-1.0, vmax=1.0)
    fig.colorbar(im, ax=axes[1], fraction=0.046, pad=0.04)
    axes[1].set_title("Post-Fit 30x30 Bin Correlation Matrix (WP_Primary)")
    axes[1].set_xlabel("Truth Bin k'")
    axes[1].set_ylabel("Truth Bin k")
    fig.tight_layout()
    fig.savefig(out_dir / "fig4_systematic_breakdown_and_corr.png")
    plt.close(fig)

    # Fig 5: 6D Efficiency & G4 Spread Reduction
    fig, axes = plt.subplots(2, 3, figsize=(15.0, 8.6), dpi=160)
    vlist = ["E_nu", "pz_mu", "y_inel", "z_vtx", "r_vtx", "q_mu"]
    for ax, vn in zip(axes.flat, vlist):
        sub = [r for r in rows_6d if r["variable"] == vn]
        xc = [0.5 * (r["edge_lo"] + r["edge_hi"]) for r in sub]
        ax.plot(xc, [r["S0_eps_pct"] for r in sub], "o-", color="#7f7f7f", ms=3.5, label="S0 eff [%]")
        ax.plot(xc, [r["WP_Primary_eps_pct"] for r in sub], "s-", color="#2ca02c", ms=3.5, label="WP_Primary eff [%]")
        ax2 = ax.twinx()
        ax2.plot(xc, [r["S0_g4_spread_pct"] for r in sub], "x--", color="#d62728", alpha=0.65, lw=1.2, label="S0 G4 spread")
        ax2.plot(xc, [r["WP_Primary_g4_spread_pct"] for r in sub], "^--", color="#1f77b4", alpha=0.80, lw=1.2, label="S1 G4 spread")
        if vn in ("E_nu", "pz_mu"):
            ax.set_xscale("log")
        ax.set_title(vn)
        ax.set_ylabel("Efficiency [%]")
        ax2.set_ylabel("G4 Spread [%]")
        if vn == "E_nu":
            ax.legend(loc="lower right", fontsize=7.5)
    fig.suptitle(r"6D Differential Acceptance Recovery & Geant4 Model Spread (S0 vs WP_Primary)")
    fig.tight_layout()
    fig.savefig(out_dir / "fig5_6d_efficiency_and_g4_closure.png")
    plt.close(fig)

    # Fig 6: F7 Energy-ML VetoNu Ablation across Zone A / Zone B / High-y
    fig, axes = plt.subplots(1, 2, figsize=(13.8, 5.2), dpi=160)
    strata_plot = ["Test_ZoneA_S0", "Test_ZoneB_Rescued", "Test_WP_Primary_HighY"]
    models_plot = ["M0_pz0_over_0p8", "M1_F7_62_trainS0", "M2_F7_58_noVN_trainS0", "M3_F7_58_noVN_trainS1", "M4_F7_62_trainS1"]
    m_colors = ["#7f7f7f", "#d62728", "#1f77b4", "#2ca02c", "#9467bd"]
    xs = np.arange(len(strata_plot))
    width = 0.15
    for mi, (mn, col) in enumerate(zip(models_plot, m_colors)):
        r68_vals = [next(r["R68_pct"] for r in ml_rows if r["stratum"] == st and r["model"] == mn) for st in strata_plot]
        bias_vals = [next(r["median_bias_pct"] for r in ml_rows if r["stratum"] == st and r["model"] == mn) for st in strata_plot]
        axes[0].bar(xs + (mi - 2) * width, r68_vals, width=width, color=col, label=mn)
        axes[1].bar(xs + (mi - 2) * width, bias_vals, width=width, color=col, label=mn)
    axes[0].set_xticks(xs); axes[0].set_xticklabels(["Zone A (S0)", "Rescued Zone B", r"WP_Primary $y \geq 0.5$"])
    axes[0].set_ylabel(r"Energy Resolution $R_{68}$ [%]")
    axes[0].set_title(r"F7 Energy Resolution vs VetoNu-Ablation ($M_{\mathrm{diag}}$: " + f"{m0_diag:.1f}% -> {m3_diag:.1f}%)")
    axes[0].legend(fontsize=7.5)
    axes[1].axhline(0.0, color="k", lw=1.0)
    axes[1].set_xticks(xs); axes[1].set_xticklabels(["Zone A (S0)", "Rescued Zone B", r"WP_Primary $y \geq 0.5$"])
    axes[1].set_ylabel("Median Relative Bias [%]")
    axes[1].set_title("Out-of-Distribution Zone-B Bias Suppression (62 vs 58 Features)")
    fig.tight_layout()
    fig.savefig(out_dir / "fig6_energy_ml_f7_vetonu_ablation.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
