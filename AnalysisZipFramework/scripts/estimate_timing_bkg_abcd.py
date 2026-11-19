#!/usr/bin/env python3
"""
Stage T4 (Stage 215): Orthogonal Blinded Data-Driven Background Determination & Closure Suite.

Reads sharded outputs from `t4_bkg_scanner` across:
  - Full Run 3 Data (2022-2026, 335.92 fb^-1, strictly blinded against SR-ZoneB)
  - 2024_cos cosmic-ray PHYS data (2,217 files)
  - All 19 FLUKA mu MC bck datasets (1,813 files)
  - 12 GENIE MC runs (30 ab^-1 FTFP_BERT nominal + master_dev 2024_CaloNu cross-check)

Outputs TSVs, JSON summary, and 6 diagnostic PNG figures in `workbook/stage215_timing_t4/`.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import glob
import io
import json
import math
import multiprocessing
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import awkward as ak  # noqa: F401
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import uproot

REPO_DIR = Path("/eos/home-x/xcheng/FASER/nu_muAnalysis")
MANIFEST_PATH = REPO_DIR / "AnalysisZipFramework/config/timing_calib/run3_timing_manifest.json"
EOS_BASE = "/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/timing_stage215"
OUT_DIR = REPO_DIR / "workbook/stage215_timing_t4"

PERIODS = ["2022", "2023", "2024_preCaloNu", "2024_CaloNu", "2024_postCaloNu", "2025", "2026"]
PER_TO_IDX = {p: i for i, p in enumerate(PERIODS)}

# Verified 2025 preliminary-list runs with VetoNu HV off / zero 2-hit prompt rate:
DEAD_VETONU_RUNS = {20667, 20668, 20675, 20677}

# Region enums matching t4_bkg_scanner.cxx
REG_KIN_SR = 1
REG_CR_GEOM_OUTER = 2
REG_CR_GEOM_HITHETA = 3
REG_CR_EDGE_VN = 4
REG_NONCOLL_B1 = 5
REG_NONCOLL_UNPAIRED = 6
REG_NONCOLL_EMPTY = 7
REG_COSMIC = 8

FLAG_HAS_REDQ = 1 << 0
FLAG_PHYS_TRIG = 1 << 1
FLAG_DOWN_OK = 1 << 2
FLAG_DOWNA_VALID = 1 << 3
FLAG_DOWNB_VALID = 1 << 4
FLAG_DOWNA_GE2 = 1 << 5
FLAG_DOWNB_GE2 = 1 << 6
FLAG_VN0_VALID = 1 << 7
FLAG_VN1_VALID = 1 << 8
FLAG_V20_ST512 = 1 << 9
FLAG_PROMPT_SUB = 1 << 10
FLAG_PASS_LEAD_TRK = 1 << 11

# Scan grid parameters (Stage T4 -> Stage T5 handoff)
S1_T2_GRID = [1.5, 1.8, 2.0, 2.2, 2.5, 3.0, 3.5]
S1_T1_GRID = [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
S1_WMAX_GRID = [10.0, 12.0, 14.0, 19.5]
QCUT_2HIT_VALS = [1e9, 200.0, 180.0, 150.0]
QCUT_2HIT_NAMES = ["allQ", "Qlt200", "Qlt180", "Qlt150"]
RVN_CUTS = [120.0, 115.0, 110.0]

S2_DCHI2_GRID = [16.0, 25.0, 36.0]
S2_Z2_GRID = [2.5, 3.0, 3.5]
S2_Z1_GRID = [4.5, 5.0, 5.5, 6.0, 6.5, 7.0]

# ABCD slice grid inside CR-Geom & negative Kinematic SR
SLICE_BOUNDS = [
    ("slice_1p5_2p2", 1.5, 2.2),
    ("slice_2p2_3p0", 2.2, 3.0),
    ("slice_3p0_5p0", 3.0, 5.0),
    ("slice_5p0_22", 5.0, 22.0),
    ("cum_1p5_22", 1.5, 22.0),
    ("cum_1p8_22", 1.8, 22.0),
    ("cum_2p0_22", 2.0, 22.0),
    ("cum_2p2_22", 2.2, 22.0),
    ("cum_2p5_22", 2.5, 22.0),
    ("cum_3p0_22", 3.0, 22.0),
]
SLICE_NAMES = [s[0] for s in SLICE_BOUNDS]

RVN_BINS_EDGE = np.array([0.0, 60.0, 90.0, 105.0, 115.0, 120.0], dtype=np.float64)
Q_BINS_EDGE = np.array([0.0, 55.0, 130.0, 200.0, 1e9], dtype=np.float64)

GENIE_TRIPLET_MAP = {
    200082: ("2022_2023", "FTFP_BERT"),
    200083: ("2022_2023", "FTFP_BERT"),
    200089: ("2022_2023", "FTFP_BERT"),
    200093: ("2024_noCaloNu", "FTFP_BERT"),
    200094: ("2024_noCaloNu", "FTFP_BERT"),
    200100: ("2024_noCaloNu", "FTFP_BERT"),
    200139: ("2024_CaloNu", "FTFP_BERT_s0015"),
    200140: ("2024_CaloNu", "FTFP_BERT_s0015"),
    200146: ("2024_CaloNu", "FTFP_BERT_s0015"),
    200172: ("2024_CaloNu_master_dev", "FTF_BIC_master_dev"),
    200173: ("2024_CaloNu_master_dev", "FTF_BIC_master_dev"),
    200174: ("2024_CaloNu_master_dev", "FTF_BIC_master_dev"),
}

FLUKA_ERA_MC22 = set(range(210000, 210010))
FLUKA_ERA_MC24 = set(range(210010, 210030))


def write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if not rows:
        path.write_text("")
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
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


def _period_for_run(run: int) -> str:
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


def _assert_zero_blinding_leak(te: dict[str, np.ndarray], hists: dict[str, dict[str, tuple[np.ndarray, np.ndarray]]], path: str) -> None:
    if len(te["run"]) > 0:
        m_sr = te["region"] == REG_KIN_SR
        if np.any(m_sr):
            has_red = (te["flags"] & FLAG_HAS_REDQ) != 0
            act0 = (te["q0_raw"] >= 30.0) | (has_red & (te["q0_red"] >= 30.0))
            act1 = (te["q1_raw"] >= 30.0) | (has_red & (te["q1_red"] >= 30.0))
            bad = m_sr & ((act0 & (~np.isfinite(te["dt0"]) | (te["dt0"] > 1.5))) | (act1 & (~np.isfinite(te["dt1"]) | (te["dt1"] > 1.5))))
            if np.any(bad):
                raise RuntimeError(f"BLINDING VIOLATION in Data shard {path}: {int(np.sum(bad))} SR-ZoneB events leaked!")
    for per_key, hm in hists.items():
        for hname, (vals, edges) in hm.items():
            if hname in ("h_sr_dt0_prompt", "h_sr_dt1_prompt"):
                centers = 0.5 * (edges[:-1] + edges[1:])
                if np.sum(vals[centers > 1.5]) > 0.0:
                    raise RuntimeError(f"BLINDING VIOLATION in histogram {per_key}/{hname} of {path}!")


def _zone_a_masks(te: dict[str, np.ndarray], use_raw40: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Era-consistent Zone A mask: reduced_charge<30 for calibrated 2022-2024 data & MC, raw<40 for 2025-2026 data or raw40 mode."""
    if use_raw40:
        act0 = te["q0_raw"] >= 40.0
        act1 = te["q1_raw"] >= 40.0
    else:
        has_red = ((te["flags"] & FLAG_HAS_REDQ) != 0) & ((te["run"] < 18500) | (te["run"] >= 100000))
        act0 = np.where(has_red & (te["q0_red"] >= 0.0), te["q0_red"] >= 30.0, te["q0_raw"] >= 40.0)
        act1 = np.where(has_red & (te["q1_red"] >= 0.0), te["q1_red"] >= 30.0, te["q1_raw"] >= 40.0)
    return act0, act1, (act0.astype(np.int32) + act1.astype(np.int32))


def _s1_s2_masks(
    te: dict[str, np.ndarray],
    use_raw40: bool,
    t2: float = 2.2,
    t1: float = 3.0,
    wmax: float = 19.5,
    t_max: float = 22.0,
    dchi2_min: float = 25.0,
    z2_min: float = 3.0,
    z1_mip: float = 6.0,
    z1_nonmip: float = 5.0,
    raw40_ext_min: float | None = None,
    q2hit_max: float = 1e9,
    require_intime_t0: bool = True,
) -> dict[str, np.ndarray]:
    flags = te["flags"]
    act0, act1, n_act = _zone_a_masks(te, use_raw40)
    down_ok = (flags & FLAG_DOWN_OK) != 0
    if require_intime_t0:
        down_ok = down_ok & np.isfinite(te["t0_down"]) & (np.abs(te["t0_down"]) < 2.5)
    vn0_ok = ((flags & FLAG_VN0_VALID) != 0) & np.isfinite(te["dt0"]) & (te["w0"] > 1.5) & (te["w0"] < wmax)
    vn1_ok = ((flags & FLAG_VN1_VALID) != 0) & np.isfinite(te["dt1"]) & (te["w1"] > 1.5) & (te["w1"] < wmax)
    act_wave_ok = (~act0 | vn0_ok) & (~act1 | vn1_ok)
    qmax_2h = np.maximum(np.nan_to_num(te["q0_raw"], nan=0.0), np.nan_to_num(te["q1_raw"], nan=0.0))
    q2_ok = qmax_2h < q2hit_max

    dt0 = te["dt0"]
    dt1 = te["dt1"]
    in2_0 = (dt0 > t2) & (dt0 < t_max)
    in2_1 = (dt1 > t2) & (dt1 < t_max)
    in1_0 = (dt0 > t1) & (dt0 < t_max)
    in1_1 = (dt1 > t1) & (dt1 < t_max)
    if raw40_ext_min is not None:
        in2_0 = in2_0 | (dt0 > raw40_ext_min)
        in2_1 = in2_1 | (dt1 > raw40_ext_min)
        in1_0 = in1_0 | (dt0 > raw40_ext_min)
        in1_1 = in1_1 | (dt1 > raw40_ext_min)

    s1_2 = (n_act == 2) & down_ok & act_wave_ok & q2_ok & in2_0 & in2_1
    s1_10 = (n_act == 1) & act0 & down_ok & act_wave_ok & in1_0
    s1_11 = (n_act == 1) & act1 & down_ok & act_wave_ok & in1_1
    s1_zb = s1_2 | s1_10 | s1_11

    in_mip0 = (te["q0_raw"] >= 55.0) & (te["q0_raw"] <= 130.0)
    in_mip1 = (te["q1_raw"] >= 55.0) & (te["q1_raw"] <= 130.0)
    thr0 = np.where(in_mip0, z1_mip, z1_nonmip)
    thr1 = np.where(in_mip1, z1_mip, z1_nonmip)
    lt_max0 = (dt0 < t_max) if raw40_ext_min is None else ((dt0 < t_max) | (dt0 > raw40_ext_min))
    lt_max1 = (dt1 < t_max) if raw40_ext_min is None else ((dt1 < t_max) | (dt1 > raw40_ext_min))

    s2_2 = (
        (n_act == 2) & down_ok & act_wave_ok & q2_ok & lt_max0 & lt_max1
        & np.isfinite(te["dchi2_back"]) & (te["dchi2_back"] > dchi2_min)
        & (te["pull0"] > z2_min) & (te["pull1"] > z2_min)
    )
    s2_10 = (n_act == 1) & act0 & down_ok & act_wave_ok & lt_max0 & (te["pull0"] > thr0)
    s2_11 = (n_act == 1) & act1 & down_ok & act_wave_ok & lt_max1 & (te["pull1"] > thr1)
    s2_zb = s2_2 | s2_10 | s2_11

    return {
        "act0": act0,
        "act1": act1,
        "n_act": n_act,
        "down_ok": down_ok,
        "act_wave_ok": act_wave_ok,
        "s1_2": s1_2,
        "s1_10": s1_10,
        "s1_11": s1_11,
        "s1_zb": s1_zb,
        "s2_2": s2_2,
        "s2_10": s2_10,
        "s2_11": s2_11,
        "s2_zb": s2_zb,
    }


def _read_shard_contents(path: str) -> tuple[dict[str, np.ndarray], dict[str, dict[str, tuple[np.ndarray, np.ndarray]]], dict[str, np.ndarray]]:
    """Read summary, histograms, and tail tree reliably via EOS FUSE with XRootD fallback."""
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            if attempt >= 2 or path.startswith("root://"):
                xrd_url = path if path.startswith("root://") else f"root://eoshome-x.cern.ch/{path}"
                raw_bytes = subprocess.check_output(["xrdcp", "-s", xrd_url, "-"])
                src: Any = io.BytesIO(raw_bytes)
            else:
                src = io.BytesIO(Path(path).read_bytes())
            with uproot.open(src) as f:
                rs = f["t4_run_summary"].arrays(library="np")
                hists: dict[str, dict[str, tuple[np.ndarray, np.ndarray]]] = {}
                for k in f.keys():
                    kc = k.split(";")[0]
                    if kc.startswith("period_") and "/" in kc:
                        pdir, hname = kc.split("/", 1)
                        per = pdir.replace("period_", "", 1)
                        v, e = f[kc].to_numpy()
                        hists.setdefault(per, {})[hname] = (v.astype(np.float64), e.astype(np.float64))
                te = f["t4_tail_events"].arrays(library="np")
            return rs, hists, te
        except Exception as exc:
            last_err = exc
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"Failed reading shard {path} after 4 attempts") from last_err


def _reduce_data_shard(path: str) -> dict[str, Any]:
    """Read and reduce one Data shard in forkserver worker with exact inverse-prescale weights."""
    rs_raw, hists, te_raw = _read_shard_contents(path)

    _assert_zero_blinding_leak(te_raw, hists, path)

    # Audit & exclude dead-VetoNu 2025 runs (zero 2-hit prompt tracks)
    rs_runs = rs_raw["run"]
    is_dead_rs = np.isin(rs_runs, list(DEAD_VETONU_RUNS))
    dead_audit = {
        "n_colliding": int(np.sum(rs_raw["n_colliding"][is_dead_rs])),
        "n_sr_zonea_red30": int(np.sum(rs_raw["n_sr_zonea_red30"][is_dead_rs])),
        "n_sr_zonea_raw40": int(np.sum(rs_raw["n_sr_zonea_raw40"][is_dead_rs])),
        "n_geom_all": int(np.sum(rs_raw["n_geom_all"][is_dead_rs])),
    }
    rs = {k: rs_raw[k][~is_dead_rs] for k in rs_raw}

    if len(te_raw["run"]) > 0:
        keep_te = ~np.isin(te_raw["run"], list(DEAD_VETONU_RUNS))
        if not np.all(keep_te):
            te_raw = {k: te_raw[k][keep_te] for k in te_raw}

    n_p = len(PERIODS)
    n_rv = len(RVN_BINS_EDGE) - 1
    n_q = len(Q_BINS_EDGE) - 1
    n_sl = len(SLICE_BOUNDS)

    # Tensors with exact inverse-prescale weights (w = 100 CR-Geom prompt, 500 SR prompt, 1 tails/1-hit)
    # geom_abcd[period, reg(0:outer,1:hiTh), rvn_bin, q_bin, slice, comp(0:D_u,1:B_u0,2:C_u1,3:A_u01,4:A_dt01,5:B_dt0,6:C_dt1,7:D_dt)]
    geom_abcd = np.zeros((n_p, 2, n_rv, n_q, n_sl, 8), dtype=np.float64)
    # Also unfiltered-t0 geom_abcd in CR-Geom (tracks out-of-time -25ns B5_oos effect)
    geom_abcd_not0 = np.zeros((n_sl, 8), dtype=np.float64)
    # cr_geom_2hit[period, charge_mode(0:red30,1:raw40), w_idx, rvn_bin, q_bin, obs(0:u0,1:u1,2:u0&u1,3:dt0,4:dt1,5:dt0&dt1), t2_idx]
    cr_geom_2hit = np.zeros((n_p, 2, len(S1_WMAX_GRID), n_rv, n_q, 6, len(S1_T2_GRID)), dtype=np.float64)
    # Exact sub-200pC 2-hit Qcut shape ratios: [w_idx(w12,w19), qcut(all,200,180,150), obs(u0,u1,dt0,dt1), t2_idx]
    cr_geom_qshape = np.zeros((2, len(QCUT_2HIT_VALS), 4, len(S1_T2_GRID)), dtype=np.float64)

    # Fast independent S1 2-hit and 1-hit observation counts in CR-Geom:
    # cr_geom_s1_2hit[period, cvar(0:red30,1:raw40,2:raw40_ext), w_idx, qcut_idx(0:inf,1:200,2:180,3:150), ti2] (with |t0_down|<2.5)
    cr_geom_s1_2hit = np.zeros((n_p, 3, len(S1_WMAX_GRID), len(QCUT_2HIT_VALS), len(S1_T2_GRID)), dtype=np.float64)
    cr_geom_s1_2hit_not0 = np.zeros((n_p, 3, len(S1_WMAX_GRID), len(S1_T2_GRID)), dtype=np.float64)
    cr_geom_s1_1hit = np.zeros((n_p, 3, len(S1_WMAX_GRID), len(S1_T1_GRID)), dtype=np.float64)
    cr_geom_s2_2hit = np.zeros((n_p, 2, len(S2_DCHI2_GRID), len(S2_Z2_GRID), 2), dtype=np.float64)  # last: 0:allQ, 1:Q<200
    cr_geom_s2_1hit = np.zeros((n_p, 2, len(S2_Z1_GRID)), dtype=np.float64)

    # 1-hit missed-layer tensors [period, cm(0:red30,1:raw40), reg(0:SR,1:Geom), lay(0:VN0,1:VN1), w_idx, rvn_bin, obs(0:prompt<=1, 1..7:+T1, 8..14:-T1, 15:+>32ns)]
    onehit_tens = np.zeros((n_p, 2, 2, 2, len(S1_WMAX_GRID), n_rv, 16), dtype=np.float64)
    onehit_s2_tens = np.zeros((n_p, 2, 2, 2, n_rv, 1 + 2 * len(S2_Z1_GRID)), dtype=np.float64)

    # SR negative mirror 2-hit ABCD (weighted by ev_w!): [period, rvn_bin, q_bin, sl_idx, comp(0:D_u,1:B_u0,2:C_u1,3:A_u01,4:D_dt,5:B_dt0,6:C_dt1,7:A_dt01)]
    sr_neg_abcd = np.zeros((n_p, n_rv, n_q, n_sl, 8), dtype=np.float64)
    # Prompt sub sample joint (reg(0:SR,1:Geom), period, rvn_bin, q_bin) with |t0_down| < 2.5
    prompt_sub_2d = np.zeros((2, n_p, n_rv, n_q), dtype=np.float64)

    # Conditional slice independence matrix on CR-Geom (weighted by ev_w, |t0_down|<2.5, Q_2hit<200 or allQ):
    u_cond_table_allq = np.zeros((5, 4), dtype=np.float64)
    u_cond_table_q200 = np.zeros((5, 4), dtype=np.float64)

    nc_counts = np.zeros(6, dtype=np.int64)
    keep_ev_chunks = []
    n_rows = len(te_raw["run"])
    if n_rows > 0:
        reg = te_raw["region"]
        flags = te_raw["flags"]
        rv_idx = np.clip(np.digitize(te_raw["r_vn"], RVN_BINS_EDGE) - 1, 0, n_rv - 1)
        qmax = np.maximum(np.nan_to_num(te_raw["q0_raw"], nan=0.0), np.nan_to_num(te_raw["q1_raw"], nan=0.0))
        q_idx = np.clip(np.digitize(qmax, Q_BINS_EDGE) - 1, 0, n_q - 1)
        per_idx = np.array([PER_TO_IDX[_period_for_run(int(r))] for r in te_raw["run"]], dtype=np.int32)

        m_sr_geom_sh = (
            (te_raw["r_max"] < 95.0) & (te_raw["r_ift"] < 95.0)
            & (te_raw["r_vn"] < 120.0) & (te_raw["theta_mrad"] < 25.0)
        )
        m_b1_sh = reg == REG_NONCOLL_B1
        m_unp_sh = reg == REG_NONCOLL_UNPAIRED
        m_emp_sh = reg == REG_NONCOLL_EMPTY
        nc_counts[0] = int(np.count_nonzero(m_b1_sh))
        nc_counts[1] = int(np.count_nonzero(m_b1_sh & m_sr_geom_sh))
        nc_counts[2] = int(np.count_nonzero(m_unp_sh))
        nc_counts[3] = int(np.count_nonzero(m_unp_sh & m_sr_geom_sh))
        nc_counts[4] = int(np.count_nonzero(m_emp_sh))
        nc_counts[5] = int(np.count_nonzero(m_emp_sh & m_sr_geom_sh))

        # Keep only EdgeVN and Beam1-in-SR-geometry rows (~27.9k rows total instead of 28.6M)
        m_small = (reg == REG_CR_EDGE_VN) | (m_b1_sh & m_sr_geom_sh)
        if np.any(m_small):
            keep_ev_chunks.append({k: te_raw[k][m_small] for k in te_raw})

        down_ok = (flags & FLAG_DOWN_OK) != 0
        downA_ok = (flags & FLAG_DOWNA_VALID) != 0
        downB_ok = (flags & FLAG_DOWNB_VALID) != 0
        vn0_val = (flags & FLAG_VN0_VALID) != 0
        vn1_val = (flags & FLAG_VN1_VALID) != 0
        dt0, dt1 = te_raw["dt0"], te_raw["dt1"]
        u0, u1 = te_raw["u0"], te_raw["u1"]
        w0, w1 = te_raw["w0"], te_raw["w1"]
        t0_in = np.isfinite(te_raw["t0_down"]) & (np.abs(te_raw["t0_down"]) < 2.5)

        # Reconstruct EXACT scanner inclusion probability weight `ev_w`
        has_red_sc = (flags & FLAG_HAS_REDQ) != 0
        act0_sc_red = np.where(has_red_sc & (te_raw["q0_red"] >= 0.0), te_raw["q0_red"] >= 30.0, te_raw["q0_raw"] >= 40.0)
        act1_sc_red = np.where(has_red_sc & (te_raw["q1_red"] >= 0.0), te_raw["q1_red"] >= 30.0, te_raw["q1_raw"] >= 40.0)
        act0_sc_raw = te_raw["q0_raw"] >= 40.0
        act1_sc_raw = te_raw["q1_raw"] >= 40.0
        one_hit_sc = (act0_sc_red != act1_sc_red) | (act0_sc_raw != act1_sc_raw)
        has_tail_sc = (
            (vn0_val & ((np.abs(dt0) > 1.45) | (np.abs(u0) > 1.45) | (np.abs(te_raw["pull0"]) > 2.45) | (np.abs(te_raw["zu0"]) > 2.45)))
            | (vn1_val & ((np.abs(dt1) > 1.45) | (np.abs(u1) > 1.45) | (np.abs(te_raw["pull1"]) > 2.45) | (np.abs(te_raw["zu1"]) > 2.45)))
        )
        ev_w = np.where(one_hit_sc | has_tail_sc, 1.0, np.where(reg == REG_KIN_SR, 500.0, 100.0))

        # Prompt-sub joint (r_vn, Q) reference on 2-hit |dt|<=1.0 & |t0_down|<2.5
        m_ps = (
            ((flags & FLAG_PROMPT_SUB) != 0) & (reg <= REG_CR_GEOM_HITHETA) & down_ok & t0_in
            & vn0_val & vn1_val & (w0 > 1.5) & (w0 < 19.5) & (w1 > 1.5) & (w1 < 19.5)
            & (te_raw["q0_raw"] >= 30.0) & (te_raw["q1_raw"] >= 30.0) & (np.abs(dt0) <= 1.0) & (np.abs(dt1) <= 1.0)
        )
        if np.any(m_ps):
            ri = np.where(reg[m_ps] == REG_KIN_SR, 0, 1)
            np.add.at(prompt_sub_2d, (ri, per_idx[m_ps], rv_idx[m_ps], q_idx[m_ps]), 1.0)

        # Conditional independence matrices in CR-Geom (weighted by ev_w, |t0_down|<2.5!)
        is_geom = (reg == REG_CR_GEOM_OUTER) | (reg == REG_CR_GEOM_HITHETA)
        m_cg_u = (
            is_geom & downA_ok & downB_ok & t0_in & vn0_val & vn1_val
            & (w0 > 1.5) & (w0 < 19.5) & (w1 > 1.5) & (w1 < 19.5)
            & (te_raw["q0_raw"] >= 30.0) & (te_raw["q1_raw"] >= 30.0) & np.isfinite(u0) & np.isfinite(u1)
        )
        if np.any(m_cg_u):
            au0 = np.abs(u0[m_cg_u])
            vu0 = u0[m_cg_u]
            vu1 = u1[m_cg_u]
            wu = ev_w[m_cg_u]
            mq200 = qmax[m_cg_u] < 200.0
            u0_cats = [au0 < 0.5, (au0 >= 0.5) & (au0 < 1.0), (au0 >= 1.0) & (au0 < 1.5), (au0 >= 1.5) & (au0 < 2.2), (vu0 >= 2.2) & (vu0 < 22.0)]
            u1_cats = [np.abs(vu1) < 1.0, (vu1 > 1.5) & (vu1 < 22.0), (vu1 > 2.2) & (vu1 < 22.0), (vu1 > 3.0) & (vu1 < 22.0)]
            for i0, m0 in enumerate(u0_cats):
                if not np.any(m0):
                    continue
                for i1, m1 in enumerate(u1_cats):
                    mm = m0 & m1
                    if np.any(mm):
                        u_cond_table_allq[i0, i1] += float(np.sum(wu[mm]))
                        if np.any(mm & mq200):
                            u_cond_table_q200[i0, i1] += float(np.sum(wu[mm & mq200]))

        # 2-hit CR-Geom & SR-negative ABCD closure tensors (charge >= 30 MIP both layers, weighted by ev_w!)
        m_both_u_not0 = downA_ok & downB_ok & vn0_val & vn1_val & (te_raw["q0_raw"] >= 30.0) & (te_raw["q1_raw"] >= 30.0) & (w0 > 1.5) & (w0 < 19.5) & (w1 > 1.5) & (w1 < 19.5) & np.isfinite(u0) & np.isfinite(u1)
        m_both_dt_not0 = down_ok & vn0_val & vn1_val & (te_raw["q0_raw"] >= 30.0) & (te_raw["q1_raw"] >= 30.0) & (w0 > 1.5) & (w0 < 19.5) & (w1 > 1.5) & (w1 < 19.5) & np.isfinite(dt0) & np.isfinite(dt1)

        m_g_u = m_both_u_not0 & is_geom & t0_in
        m_g_dt = m_both_dt_not0 & is_geom & t0_in
        m_g_u_nt0 = m_both_u_not0 & is_geom
        m_g_dt_nt0 = m_both_dt_not0 & is_geom

        for si, (_, lo, hi) in enumerate(SLICE_BOUNDS):
            if np.any(m_g_u):
                gi = np.where(reg[m_g_u] == REG_CR_GEOM_OUTER, 0, 1)
                pi, rvi, qi, wt = per_idx[m_g_u], rv_idx[m_g_u], q_idx[m_g_u], ev_w[m_g_u]
                x, y = u0[m_g_u], u1[m_g_u]
                cD = (np.abs(x) < 1.0) & (np.abs(y) < 1.0)
                cB = (x >= lo) & (x < hi) & (np.abs(y) < 1.0)
                cC = (np.abs(x) < 1.0) & (y >= lo) & (y < hi)
                cA = (x >= lo) & (x < hi) & (y >= lo) & (y < hi)
                for cid, cmask in ((0, cD), (1, cB), (2, cC), (3, cA)):
                    if np.any(cmask):
                        np.add.at(geom_abcd, (pi[cmask], gi[cmask], rvi[cmask], qi[cmask], si, cid), wt[cmask])
            if np.any(m_g_dt):
                gi = np.where(reg[m_g_dt] == REG_CR_GEOM_OUTER, 0, 1)
                pi, rvi, qi, wt = per_idx[m_g_dt], rv_idx[m_g_dt], q_idx[m_g_dt], ev_w[m_g_dt]
                x, y = dt0[m_g_dt], dt1[m_g_dt]
                cD = (np.abs(x) < 1.0) & (np.abs(y) < 1.0)
                cB = (x >= lo) & (x < hi) & (np.abs(y) < 1.0)
                cC = (np.abs(x) < 1.0) & (y >= lo) & (y < hi)
                cA = (x >= lo) & (x < hi) & (y >= lo) & (y < hi)
                for cid, cmask in ((7, cD), (5, cB), (6, cC), (4, cA)):
                    if np.any(cmask):
                        np.add.at(geom_abcd, (pi[cmask], gi[cmask], rvi[cmask], qi[cmask], si, cid), wt[cmask])
            if np.any(m_g_u_nt0):
                wt = ev_w[m_g_u_nt0]
                x, y = u0[m_g_u_nt0], u1[m_g_u_nt0]
                geom_abcd_not0[si, 0] += float(np.sum(wt[(np.abs(x) < 1.0) & (np.abs(y) < 1.0)]))
                geom_abcd_not0[si, 1] += float(np.sum(wt[(x >= lo) & (x < hi) & (np.abs(y) < 1.0)]))
                geom_abcd_not0[si, 2] += float(np.sum(wt[(np.abs(x) < 1.0) & (y >= lo) & (y < hi)]))
                geom_abcd_not0[si, 3] += float(np.sum(wt[(x >= lo) & (x < hi) & (y >= lo) & (y < hi)]))
            if np.any(m_g_dt_nt0):
                wt = ev_w[m_g_dt_nt0]
                x, y = dt0[m_g_dt_nt0], dt1[m_g_dt_nt0]
                geom_abcd_not0[si, 7] += float(np.sum(wt[(np.abs(x) < 1.0) & (np.abs(y) < 1.0)]))
                geom_abcd_not0[si, 5] += float(np.sum(wt[(x >= lo) & (x < hi) & (np.abs(y) < 1.0)]))
                geom_abcd_not0[si, 6] += float(np.sum(wt[(np.abs(x) < 1.0) & (y >= lo) & (y < hi)]))
                geom_abcd_not0[si, 4] += float(np.sum(wt[(x >= lo) & (x < hi) & (y >= lo) & (y < hi)]))

        # Unblinded SR negative mirror ABCD: (-hi, -lo] (weighted by ev_w, |t0_down|<2.5!)
        m_sr_u = m_both_u_not0 & t0_in & (reg == REG_KIN_SR) & (dt0 <= 1.5) & (dt1 <= 1.5)
        m_sr_dt = m_both_dt_not0 & t0_in & (reg == REG_KIN_SR) & (dt0 <= 1.5) & (dt1 <= 1.5)
        for si, (_, lo, hi) in enumerate(SLICE_BOUNDS):
            if np.any(m_sr_u):
                pi, rvi, qi, wt = per_idx[m_sr_u], rv_idx[m_sr_u], q_idx[m_sr_u], ev_w[m_sr_u]
                x, y = -u0[m_sr_u], -u1[m_sr_u]
                cD = (np.abs(x) < 1.0) & (np.abs(y) < 1.0)
                cB = (x >= lo) & (x < hi) & (np.abs(y) < 1.0)
                cC = (np.abs(x) < 1.0) & (y >= lo) & (y < hi)
                cA = (x >= lo) & (x < hi) & (y >= lo) & (y < hi)
                for cid, cmask in ((0, cD), (1, cB), (2, cC), (3, cA)):
                    if np.any(cmask):
                        np.add.at(sr_neg_abcd, (pi[cmask], rvi[cmask], qi[cmask], si, cid), wt[cmask])
            if np.any(m_sr_dt):
                pi, rvi, qi, wt = per_idx[m_sr_dt], rv_idx[m_sr_dt], q_idx[m_sr_dt], ev_w[m_sr_dt]
                x, y = -dt0[m_sr_dt], -dt1[m_sr_dt]
                cD = (np.abs(x) < 1.0) & (np.abs(y) < 1.0)
                cB = (x >= lo) & (x < hi) & (np.abs(y) < 1.0)
                cC = (np.abs(x) < 1.0) & (y >= lo) & (y < hi)
                cA = (x >= lo) & (x < hi) & (y >= lo) & (y < hi)
                for cid, cmask in ((4, cD), (5, cB), (6, cC), (7, cA)):
                    if np.any(cmask):
                        np.add.at(sr_neg_abcd, (pi[cmask], rvi[cmask], qi[cmask], si, cid), wt[cmask])

        # Pre-slice positive-tail candidates for ultra-fast cr_geom_s1 / cr_geom_s2
        m_g_cand = is_geom & ((dt0 > 1.45) | (dt1 > 1.45) | (te_raw["pull0"] > 2.45) | (te_raw["pull1"] > 2.45))
        has_cand = np.any(m_g_cand)
        if has_cand:
            te_c = {k: te_raw[k][m_g_cand] for k in te_raw}
            pc_idx = per_idx[m_g_cand]
            qm_c = qmax[m_g_cand]
            t0c_in = t0_in[m_g_cand]
            fl_c = te_c["flags"]
            dok_c = (fl_c & FLAG_DOWN_OK) != 0
            vn0_c = (fl_c & FLAG_VN0_VALID) != 0
            vn1_c = (fl_c & FLAG_VN1_VALID) != 0
            dt0_c, dt1_c, w0_c, w1_c = te_c["dt0"], te_c["dt1"], te_c["w0"], te_c["w1"]

            for cm_idx, use_raw in enumerate((False, True)):
                a0_c, a1_c, na_c = _zone_a_masks(te_c, use_raw)
                cm_variants = [(0, None)] if cm_idx == 0 else [(1, None), (2, 32.0)]
                for wi, wmax in enumerate(S1_WMAX_GRID):
                    v0_w = vn0_c & np.isfinite(dt0_c) & (w0_c > 1.5) & (w0_c < wmax)
                    v1_w = vn1_c & np.isfinite(dt1_c) & (w1_c > 1.5) & (w1_c < wmax)
                    ok_w = (~a0_c | v0_w) & (~a1_c | v1_w)
                    base2_not0 = (na_c == 2) & dok_c & ok_w
                    base1_in = (na_c == 1) & dok_c & t0c_in & ok_w
                    for cvar, ext_m in cm_variants:
                        in2_0 = (dt0_c < 22.0) if ext_m is None else ((dt0_c < 22.0) | (dt0_c > ext_m))
                        in2_1 = (dt1_c < 22.0) if ext_m is None else ((dt1_c < 22.0) | (dt1_c > ext_m))
                        b2_nt0 = base2_not0 & in2_0 & in2_1
                        b2_in = b2_nt0 & t0c_in
                        for ti2, t2 in enumerate(S1_T2_GRID):
                            mt_nt0 = b2_nt0 & ((dt0_c > t2) if ext_m is None else ((dt0_c > t2) & (dt0_c < 22.0) | (dt0_c > ext_m))) & ((dt1_c > t2) if ext_m is None else ((dt1_c > t2) & (dt1_c < 22.0) | (dt1_c > ext_m)))
                            if np.any(mt_nt0):
                                np.add.at(cr_geom_s1_2hit_not0, (pc_idx[mt_nt0], cvar, wi, ti2), 1.0)
                                mt_in = mt_nt0 & t0c_in
                                if np.any(mt_in):
                                    for qci, qcut in enumerate(QCUT_2HIT_VALS):
                                        mqc = mt_in & (qm_c < qcut)
                                        if np.any(mqc):
                                            np.add.at(cr_geom_s1_2hit, (pc_idx[mqc], cvar, wi, qci, ti2), 1.0)
                        for ti1, t1 in enumerate(S1_T1_GRID):
                            m1_0 = a0_c & ((dt0_c > t1) & (dt0_c < 22.0) if ext_m is None else (((dt0_c > t1) & (dt0_c < 22.0)) | (dt0_c > ext_m)))
                            m1_1 = a1_c & ((dt1_c > t1) & (dt1_c < 22.0) if ext_m is None else (((dt1_c > t1) & (dt1_c < 22.0)) | (dt1_c > ext_m)))
                            m1 = base1_in & (m1_0 | m1_1)
                            if np.any(m1):
                                np.add.at(cr_geom_s1_1hit, (pc_idx[m1], cvar, wi, ti1), 1.0)

                # S2 fast on m_g_cand (wmax=19.5)
                s2_cm = cm_idx  # 0: red30, 1: raw40_ext (>32 ns)
                ext_s2 = 32.0 if cm_idx == 1 else None
                v0_19 = vn0_c & np.isfinite(dt0_c) & (w0_c > 1.5) & (w0_c < 19.5)
                v1_19 = vn1_c & np.isfinite(dt1_c) & (w1_c > 1.5) & (w1_c < 19.5)
                ok_19 = (~a0_c | v0_19) & (~a1_c | v1_19)
                lt0 = (dt0_c < 22.0) if ext_s2 is None else ((dt0_c < 22.0) | (dt0_c > ext_s2))
                lt1 = (dt1_c < 22.0) if ext_s2 is None else ((dt1_c < 22.0) | (dt1_c > ext_s2))
                b2_s2 = (na_c == 2) & dok_c & t0c_in & ok_19 & lt0 & lt1 & np.isfinite(te_c["dchi2_back"])
                for di, dc in enumerate(S2_DCHI2_GRID):
                    for zi2, z2 in enumerate(S2_Z2_GRID):
                        m2 = b2_s2 & (te_c["dchi2_back"] > dc) & (te_c["pull0"] > z2) & (te_c["pull1"] > z2)
                        if np.any(m2):
                            np.add.at(cr_geom_s2_2hit, (pc_idx[m2], s2_cm, di, zi2, 0), 1.0)
                            m2q = m2 & (qm_c < 200.0)
                            if np.any(m2q):
                                np.add.at(cr_geom_s2_2hit, (pc_idx[m2q], s2_cm, di, zi2, 1), 1.0)
                b1_s2 = (na_c == 1) & dok_c & t0c_in & ok_19
                for zi1, z1 in enumerate(S2_Z1_GRID):
                    z1_non = max(4.0, z1 - 1.0)
                    t0_s2 = np.where((te_c["q0_raw"] >= 55.0) & (te_c["q0_raw"] <= 130.0), z1, z1_non)
                    t1_s2 = np.where((te_c["q1_raw"] >= 55.0) & (te_c["q1_raw"] <= 130.0), z1, z1_non)
                    m1 = b1_s2 & ((a0_c & lt0 & (te_c["pull0"] > t0_s2)) | (a1_c & lt1 & (te_c["pull1"] > t1_s2)))
                    if np.any(m1):
                        np.add.at(cr_geom_s2_1hit, (pc_idx[m1], s2_cm, zi1), 1.0)

        # CR-Geom 2-hit single-layer & 2-layer tail probs + 1-hit B2 tensors (|t0_down|<2.5!)
        is_sr = reg == REG_KIN_SR
        for cm_idx, use_raw in enumerate((False, True)):
            act0, act1, n_act = _zone_a_masks(te_raw, use_raw)
            both_act = is_geom & (n_act == 2) & t0_in
            for wi, wmax in enumerate(S1_WMAX_GRID):
                w0o = vn0_val & (w0 > 1.5) & (w0 < wmax) & np.isfinite(dt0)
                w1o = vn1_val & (w1 > 1.5) & (w1 < wmax) & np.isfinite(dt1)
                wu0o = vn0_val & (w0 > 1.5) & (w0 < wmax) & np.isfinite(u0)
                wu1o = vn1_val & (w1 > 1.5) & (w1 < wmax) & np.isfinite(u1)

                mu = both_act & downA_ok & downB_ok & wu0o & wu1o
                mdt = both_act & down_ok & w0o & w1o
                for ti, t2 in enumerate(S1_T2_GRID):
                    if np.any(mu):
                        pi, rvi, qi, wt = per_idx[mu], rv_idx[mu], q_idx[mu], ev_w[mu]
                        u0m, u1m = (u0[mu] > t2) & (u0[mu] < 22.0), (u1[mu] > t2) & (u1[mu] < 22.0)
                        c0 = u0m & (np.abs(u1[mu]) < 1.0)
                        c1 = u1m & (np.abs(u0[mu]) < 1.0)
                        c2 = u0m & u1m
                        for oid, om in ((0, c0), (1, c1), (2, c2)):
                            if np.any(om):
                                np.add.at(cr_geom_2hit, (pi[om], cm_idx, wi, rvi[om], qi[om], oid, ti), wt[om])
                        if cm_idx == 0 and wmax in (12.0, 19.5):
                            wsi = 0 if wmax == 12.0 else 1
                            qmm = qmax[mu]
                            for qci, qcut in enumerate(QCUT_2HIT_VALS):
                                mqc = qmm < qcut
                                if np.any(c0 & mqc):
                                    cr_geom_qshape[wsi, qci, 0, ti] += float(np.sum(wt[c0 & mqc]))
                                if np.any(c1 & mqc):
                                    cr_geom_qshape[wsi, qci, 1, ti] += float(np.sum(wt[c1 & mqc]))
                    if np.any(mdt):
                        pi, rvi, qi, wt = per_idx[mdt], rv_idx[mdt], q_idx[mdt], ev_w[mdt]
                        d0m, d1m = (dt0[mdt] > t2) & (dt0[mdt] < 22.0), (dt1[mdt] > t2) & (dt1[mdt] < 22.0)
                        c3 = d0m & (np.abs(dt1[mdt]) < 1.0)
                        c4 = d1m & (np.abs(dt0[mdt]) < 1.0)
                        c5 = d0m & d1m
                        for oid, om in ((3, c3), (4, c4), (5, c5)):
                            if np.any(om):
                                np.add.at(cr_geom_2hit, (pi[om], cm_idx, wi, rvi[om], qi[om], oid, ti), wt[om])
                        if cm_idx == 0 and wmax in (12.0, 19.5):
                            wsi = 0 if wmax == 12.0 else 1
                            qmm = qmax[mdt]
                            for qci, qcut in enumerate(QCUT_2HIT_VALS):
                                mqc = qmm < qcut
                                if np.any(c3 & mqc):
                                    cr_geom_qshape[wsi, qci, 2, ti] += float(np.sum(wt[c3 & mqc]))
                                if np.any(c4 & mqc):
                                    cr_geom_qshape[wsi, qci, 3, ti] += float(np.sum(wt[c4 & mqc]))

                # 1-hit missed-layer in SR & CR-Geom (era-corrected Zone A, |t0_down|<2.5!)
                for reg_id, rmask in ((0, is_sr), (1, is_geom)):
                    m_1h0 = rmask & (n_act == 1) & act0 & down_ok & t0_in & w0o
                    m_1h1 = rmask & (n_act == 1) & act1 & down_ok & t0_in & w1o
                    for lay, ml, dtv in ((0, m_1h0, dt0), (1, m_1h1, dt1)):
                        if not np.any(ml):
                            continue
                        pi, rvi, dv = per_idx[ml], rv_idx[ml], dtv[ml]
                        mp0 = np.abs(dv) <= 1.0
                        if np.any(mp0):
                            np.add.at(onehit_tens, (pi[mp0], cm_idx, reg_id, lay, wi, rvi[mp0], 0), 1.0)
                        for ti, t1 in enumerate(S1_T1_GRID):
                            if reg_id == 1:
                                mp_pos = (dv > t1) & (dv < 22.0)
                                if np.any(mp_pos):
                                    np.add.at(onehit_tens, (pi[mp_pos], cm_idx, reg_id, lay, wi, rvi[mp_pos], 1 + ti), 1.0)
                            mp_neg = (dv < -t1) & (dv > -22.0)
                            if np.any(mp_neg):
                                np.add.at(onehit_tens, (pi[mp_neg], cm_idx, reg_id, lay, wi, rvi[mp_neg], 8 + ti), 1.0)
                        if reg_id == 1 and cm_idx == 1:
                            mp_ext = (dv > 32.0)
                            if np.any(mp_ext):
                                np.add.at(onehit_tens, (pi[mp_ext], cm_idx, reg_id, lay, wi, rvi[mp_ext], 15), 1.0)

            # S2 1-hit missed-layer tensor (wmax = 19.5 ns)
            w0o = vn0_val & (w0 > 1.5) & (w0 < 19.5) & np.isfinite(te_raw["pull0"])
            w1o = vn1_val & (w1 > 1.5) & (w1 < 19.5) & np.isfinite(te_raw["pull1"])
            for reg_id, rmask in ((0, is_sr), (1, is_geom)):
                for lay, ml, pv, dv in (
                    (0, rmask & (n_act == 1) & act0 & down_ok & t0_in & w0o, te_raw["pull0"], dt0),
                    (1, rmask & (n_act == 1) & act1 & down_ok & t0_in & w1o, te_raw["pull1"], dt1),
                ):
                    if not np.any(ml):
                        continue
                    pi, rvi, pvv, dvv = per_idx[ml], rv_idx[ml], pv[ml], dv[ml]
                    mp0 = np.abs(dvv) <= 1.0
                    if np.any(mp0):
                        np.add.at(onehit_s2_tens, (pi[mp0], cm_idx, reg_id, lay, rvi[mp0], 0), 1.0)
                    for zi, zthr in enumerate(S2_Z1_GRID):
                        if reg_id == 1:
                            mp_pos = (dvv < 22.0) & (pvv > zthr)
                            if np.any(mp_pos):
                                np.add.at(onehit_s2_tens, (pi[mp_pos], cm_idx, reg_id, lay, rvi[mp_pos], 1 + zi), 1.0)
                        mp_neg = (dvv > -22.0) & (pvv < -zthr)
                        if np.any(mp_neg):
                            np.add.at(onehit_s2_tens, (pi[mp_neg], cm_idx, reg_id, lay, rvi[mp_neg], 1 + len(S2_Z1_GRID) + zi), 1.0)

    keep_merged = {k: np.concatenate([c[k] for c in keep_ev_chunks], axis=0) for k in keep_ev_chunks[0]} if keep_ev_chunks else {}
    return {
        "rs": rs,
        "dead_audit": dead_audit,
        "hists": hists,
        "geom_abcd": geom_abcd,
        "geom_abcd_not0": geom_abcd_not0,
        "cr_geom_2hit": cr_geom_2hit,
        "cr_geom_qshape": cr_geom_qshape,
        "cr_geom_s1_2hit": cr_geom_s1_2hit,
        "cr_geom_s1_2hit_not0": cr_geom_s1_2hit_not0,
        "cr_geom_s1_1hit": cr_geom_s1_1hit,
        "cr_geom_s2_2hit": cr_geom_s2_2hit,
        "cr_geom_s2_1hit": cr_geom_s2_1hit,
        "onehit_tens": onehit_tens,
        "onehit_s2_tens": onehit_s2_tens,
        "sr_neg_abcd": sr_neg_abcd,
        "prompt_sub_2d": prompt_sub_2d,
        "u_cond_table_allq": u_cond_table_allq,
        "u_cond_table_q200": u_cond_table_q200,
        "nc_counts": nc_counts,
        "events": keep_merged,
    }


def _read_raw_shard(path: str) -> dict[str, Any]:
    rs, hists, te = _read_shard_contents(path)
    return {"rs": {k: rs[k] for k in rs}, "hists": hists, "events": te}


def _merge_summaries(rs_list: list[dict[str, np.ndarray]]) -> tuple[dict[int, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_run: dict[int, dict[str, Any]] = {}
    for rs in rs_list:
        if len(rs["run"]) == 0:
            continue
        for i in range(len(rs["run"])):
            r = int(rs["run"][i])
            if r not in by_run:
                by_run[r] = {}
                for k in rs:
                    if k == "period":
                        p = rs[k][i]
                        by_run[r][k] = p.decode() if isinstance(p, (bytes, bytearray)) else str(p)
                    elif k in ("is_mc", "is_cosmic", "has_reduced_charge", "has_vetogm"):
                        by_run[r][k] = bool(rs[k][i])
                    elif k.startswith("cov_") and not k.endswith("_n"):
                        by_run[r][k] = float(rs[k][i])
                    else:
                        by_run[r][k] = int(rs[k][i])
            else:
                for k in rs:
                    if k in ("run", "period"):
                        continue
                    elif k in ("is_mc", "is_cosmic", "has_reduced_charge", "has_vetogm"):
                        by_run[r][k] = by_run[r][k] or bool(rs[k][i])
                    elif k.startswith("cov_") and not k.endswith("_n"):
                        by_run[r][k] += float(rs[k][i])
                    else:
                        by_run[r][k] += int(rs[k][i])
    by_per: dict[str, dict[str, Any]] = {}
    for _, rd in sorted(by_run.items()):
        p = rd["period"]
        if p not in by_per:
            by_per[p] = {}
            for k, v in rd.items():
                if k in ("run", "period"):
                    continue
                by_per[p][k] = v
            by_per[p]["n_runs"] = 1
        else:
            for k, v in rd.items():
                if k in ("run", "period", "is_mc", "is_cosmic", "has_reduced_charge", "has_vetogm"):
                    continue
                by_per[p][k] += v
            by_per[p]["n_runs"] += 1
    return by_run, by_per


def _merge_hists(h_list: list[dict[str, dict[str, tuple[np.ndarray, np.ndarray]]]]) -> dict[str, dict[str, tuple[np.ndarray, np.ndarray]]]:
    merged: dict[str, dict[str, tuple[np.ndarray, np.ndarray]]] = {}
    for hm in h_list:
        for per, d in hm.items():
            md = merged.setdefault(per, {})
            for hn, (v, e) in d.items():
                if hn not in md:
                    md[hn] = (v.copy(), e)
                else:
                    md[hn][0][:] += v
    return merged


def _concat_events(ev_list: list[dict[str, np.ndarray]]) -> dict[str, np.ndarray]:
    nonempty = [e for e in ev_list if e and len(e["run"]) > 0]
    if not nonempty:
        return {}
    keys = list(nonempty[0].keys())
    return {k: np.concatenate([e[k] for e in nonempty], axis=0) for k in keys}


def _cov_rho(d: dict[str, Any], pfx: str) -> tuple[int, float, float, float, float]:
    n = int(d.get(f"{pfx}_n", 0))
    if n < 10:
        return n, float("nan"), float("nan"), float("nan"), float("nan")
    sx, sy = d[f"{pfx}_sx"], d[f"{pfx}_sy"]
    sxx, syy, sxy = d[f"{pfx}_sxx"], d[f"{pfx}_syy"], d[f"{pfx}_sxy"]
    vx = max(0.0, sxx / n - (sx / n) ** 2)
    vy = max(0.0, syy / n - (sy / n) ** 2)
    cov = sxy / n - (sx / n) * (sy / n)
    rho = cov / math.sqrt(vx * vy) if (vx > 0 and vy > 0) else float("nan")
    err = (1.0 - rho * rho) / math.sqrt(max(n - 3, 1)) if math.isfinite(rho) else float("nan")
    return n, rho, err, math.sqrt(vx), math.sqrt(vy)


def _abcd_pred_err(nb: float, nc: float, nd: float) -> tuple[float, float]:
    if nd <= 0.0 or nb <= 0.0 or nc <= 0.0:
        return 0.0, 0.0
    pred = (nb * nc) / nd
    rel_err = math.sqrt(1.0 / nb + 1.0 / nc + 1.0 / nd)
    return pred, pred * rel_err


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage T4 blinded Run 3 background analysis")
    parser.add_argument("--workers", type=int, default=28)
    args = parser.parse_args()

    t_start = time.perf_counter()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST_PATH.read_text())
    lumi_by_period = {p["period"]: float(p["lumi_fb_inverse"]) for p in manifest["periods"]}
    lumi_total = sum(lumi_by_period.values())
    lumi_mc_geom = {
        "2022_2023": lumi_by_period["2022"] + lumi_by_period["2023"],
        "2024_noCaloNu": lumi_by_period["2024_preCaloNu"] + lumi_by_period["2024_postCaloNu"] + lumi_by_period["2025"] + lumi_by_period["2026"],
        "2024_CaloNu": lumi_by_period["2024_CaloNu"],
    }

    data_paths = _list_shards("data")
    fluka_paths = _list_shards("fluka")
    genie_paths = _list_shards("genie")
    cosmic_paths = _list_shards("cosmic")
    print(f"[T4] Loading shards: data={len(data_paths)}, fluka={len(fluka_paths)}, genie={len(genie_paths)}, cosmic={len(cosmic_paths)} (workers={args.workers}, ctx=forkserver)")

    mp_ctx = multiprocessing.get_context("forkserver")
    t_load0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers, mp_context=mp_ctx) as ex:
        data_res = list(ex.map(_reduce_data_shard, data_paths, chunksize=8))
    with ProcessPoolExecutor(max_workers=min(args.workers, len(fluka_paths) + len(genie_paths) + len(cosmic_paths)), mp_context=mp_ctx) as ex:
        fluka_res = list(ex.map(_read_raw_shard, fluka_paths, chunksize=2))
        genie_res = list(ex.map(_read_raw_shard, genie_paths, chunksize=2))
        cosmic_res = list(ex.map(_read_raw_shard, cosmic_paths, chunksize=1))
    load_s = time.perf_counter() - t_load0

    data_runs, data_pers = _merge_summaries([r["rs"] for r in data_res])
    data_hists = _merge_hists([r["hists"] for r in data_res])
    data_small_ev = _concat_events([r["events"] for r in data_res])

    dead_audit_tot = {
        "excluded_runs": sorted(DEAD_VETONU_RUNS),
        "n_colliding": sum(r["dead_audit"]["n_colliding"] for r in data_res),
        "n_sr_zonea_red30": sum(r["dead_audit"]["n_sr_zonea_red30"] for r in data_res),
        "n_sr_zonea_raw40": sum(r["dead_audit"]["n_sr_zonea_raw40"] for r in data_res),
        "n_geom_all": sum(r["dead_audit"]["n_geom_all"] for r in data_res),
    }

    geom_abcd = np.sum([r["geom_abcd"] for r in data_res], axis=0)
    geom_abcd_not0 = np.sum([r["geom_abcd_not0"] for r in data_res], axis=0)
    cr_geom_2hit = np.sum([r["cr_geom_2hit"] for r in data_res], axis=0)
    cr_geom_qshape = np.sum([r["cr_geom_qshape"] for r in data_res], axis=0)
    cr_geom_s1_2hit = np.sum([r["cr_geom_s1_2hit"] for r in data_res], axis=0)
    cr_geom_s1_2hit_not0 = np.sum([r["cr_geom_s1_2hit_not0"] for r in data_res], axis=0)
    cr_geom_s1_1hit = np.sum([r["cr_geom_s1_1hit"] for r in data_res], axis=0)
    cr_geom_s2_2hit = np.sum([r["cr_geom_s2_2hit"] for r in data_res], axis=0)
    cr_geom_s2_1hit = np.sum([r["cr_geom_s2_1hit"] for r in data_res], axis=0)
    onehit_tens = np.sum([r["onehit_tens"] for r in data_res], axis=0)
    onehit_s2_tens = np.sum([r["onehit_s2_tens"] for r in data_res], axis=0)
    sr_neg_abcd = np.sum([r["sr_neg_abcd"] for r in data_res], axis=0)
    prompt_sub_2d = np.sum([r["prompt_sub_2d"] for r in data_res], axis=0)
    u_cond_table_allq = np.sum([r["u_cond_table_allq"] for r in data_res], axis=0)
    u_cond_table_q200 = np.sum([r["u_cond_table_q200"] for r in data_res], axis=0)
    nc_tot = np.sum([r["nc_counts"] for r in data_res], axis=0)

    fluka_runs, fluka_pers = _merge_summaries([r["rs"] for r in fluka_res])
    fluka_ev = _concat_events([r["events"] for r in fluka_res])

    genie_runs, genie_pers = _merge_summaries([r["rs"] for r in genie_res])
    genie_ev = _concat_events([r["events"] for r in genie_res])

    cosmic_runs, cosmic_pers = _merge_summaries([r["rs"] for r in cosmic_res])
    cosmic_ev = _concat_events([r["events"] for r in cosmic_res])

    tot_data_events = sum(d["n_total"] for d in data_pers.values())
    tot_data_blinded = sum(d["n_blinded"] for d in data_pers.values())
    tot_data_geom = sum(d["n_geom_all"] for d in data_pers.values())
    print(f"[T4] Loaded in {load_s:.2f}s: active Data runs={len(data_runs)} (excl 4 dead-VetoNu runs), events={tot_data_events:,}, blinded_SR_ZoneB={tot_data_blinded:,}, CR-Geom={tot_data_geom:,}")

    # =========================================================================
    # 1. Statistical Independence of Decoupled (u0, u1) vs Common-t0 (dt0, dt1)
    # =========================================================================
    indep_rows = []
    all_pers_agg: dict[str, Any] = {}
    for p, pd in data_pers.items():
        for k, v in pd.items():
            if k in ("is_mc", "is_cosmic", "has_reduced_charge", "has_vetogm"):
                continue
            all_pers_agg[k] = all_pers_agg.get(k, 0) + v

    for pname, pd in [(p, data_pers[p]) for p in PERIODS if p in data_pers] + [("Run3_All", all_pers_agg)]:
        for reg_name, u_key, dt_key in [
            ("CR_Prompt_1p0ns", "cov_sr_u_1p0", "cov_sr_dt_1p0"),
            ("CR_Prompt_1p5ns", "cov_sr_u_1p5", "cov_sr_dt_1p5"),
            ("CR_Prompt_1p0_Dig2", "cov_sr_u_1p0_st512", "cov_sr_dt_1p0_st512"),
            ("CR_Geom_1p0ns", "cov_geom_u_1p0", "cov_geom_dt_1p0"),
            ("CR_Geom_1p5ns", "cov_geom_u_1p5", "cov_geom_dt_1p5"),
        ]:
            nu, rhou, erru, su0, su1 = _cov_rho(pd, u_key)
            ndt, rhodt, errdt, sd0, sd1 = _cov_rho(pd, dt_key)
            if nu == 0 and ndt == 0:
                continue
            indep_rows.append({
                "period": pname,
                "region": reg_name,
                "n_u": nu,
                "rho_u0_u1": round(rhou, 6) if math.isfinite(rhou) else "nan",
                "err_rho_u": round(erru, 6) if math.isfinite(erru) else "nan",
                "std_u0_ns": round(su0, 4) if math.isfinite(su0) else "nan",
                "std_u1_ns": round(su1, 4) if math.isfinite(su1) else "nan",
                "n_dt": ndt,
                "rho_dt0_dt1": round(rhodt, 6) if math.isfinite(rhodt) else "nan",
                "err_rho_dt": round(errdt, 6) if math.isfinite(errdt) else "nan",
                "std_dt0_ns": round(sd0, 4) if math.isfinite(sd0) else "nan",
                "std_dt1_ns": round(sd1, 4) if math.isfinite(sd1) else "nan",
            })
    write_tsv(OUT_DIR / "t4_u0_u1_independence.tsv", indep_rows)

    # =========================================================================
    # 2. GENIE Neutrino Contamination Across All Regions (335.92 fb^-1)
    # =========================================================================
    g_w = np.zeros(len(genie_ev["run"]), dtype=np.float64)
    g_nom_mask = np.zeros(len(genie_ev["run"]), dtype=bool)
    for r, (geom_tag, _) in GENIE_TRIPLET_MAP.items():
        mr = genie_ev["run"] == r
        if geom_tag in lumi_mc_geom:
            g_w[mr] = lumi_mc_geom[geom_tag] / 10000.0
            g_nom_mask |= mr

    g_flags = genie_ev["flags"]
    g_t0_in = np.isfinite(genie_ev["t0_down"]) & (np.abs(genie_ev["t0_down"]) < 2.5)
    g_down_ok = ((g_flags & FLAG_DOWN_OK) != 0) & g_t0_in
    g_downA_ok = ((g_flags & FLAG_DOWNA_VALID) != 0) & g_t0_in
    g_downB_ok = ((g_flags & FLAG_DOWNB_VALID) != 0) & g_t0_in
    g_v0 = ((g_flags & FLAG_VN0_VALID) != 0) & np.isfinite(genie_ev["dt0"]) & (genie_ev["w0"] > 1.5) & (genie_ev["w0"] < 19.5)
    g_v1 = ((g_flags & FLAG_VN1_VALID) != 0) & np.isfinite(genie_ev["dt1"]) & (genie_ev["w1"] > 1.5) & (genie_ev["w1"] < 19.5)
    g_vu0 = ((g_flags & FLAG_VN0_VALID) != 0) & np.isfinite(genie_ev["u0"]) & (genie_ev["w0"] > 1.5) & (genie_ev["w0"] < 19.5)
    g_vu1 = ((g_flags & FLAG_VN1_VALID) != 0) & np.isfinite(genie_ev["u1"]) & (genie_ev["w1"] > 1.5) & (genie_ev["w1"] < 19.5)

    g_s1_nom = _s1_s2_masks(genie_ev, use_raw40=False, require_intime_t0=True)
    g_s1_q200 = _s1_s2_masks(genie_ev, use_raw40=False, q2hit_max=200.0, require_intime_t0=True)
    g_s1_rawext = _s1_s2_masks(genie_ev, use_raw40=True, raw40_ext_min=32.0, require_intime_t0=True)

    def _g_yield(mask: np.ndarray, subset: np.ndarray | None = None) -> tuple[float, float, int]:
        m = mask & (g_nom_mask if subset is None else subset)
        w = g_w[m]
        return float(np.sum(w)), float(math.sqrt(np.sum(w * w))), int(np.count_nonzero(m))

    genie_cr_rows = []
    for rname, rmask in [
        ("REG_KIN_SR", genie_ev["region"] == REG_KIN_SR),
        ("REG_CR_GEOM_ALL", (genie_ev["region"] == REG_CR_GEOM_OUTER) | (genie_ev["region"] == REG_CR_GEOM_HITHETA)),
        ("REG_CR_GEOM_OUTER", genie_ev["region"] == REG_CR_GEOM_OUTER),
        ("REG_CR_GEOM_HITHETA", genie_ev["region"] == REG_CR_GEOM_HITHETA),
        ("REG_CR_EDGE_VN", genie_ev["region"] == REG_CR_EDGE_VN),
    ]:
        for gc_name, gcm in [("all_nu", np.ones(len(g_w), dtype=bool)), ("fid_numu_cc", genie_ev["genie_class"] == 1), ("other_nu", genie_ev["genie_class"] == 2)]:
            y_all, e_all, n_all = _g_yield(rmask & gcm)
            y_za, _, _ = _g_yield(rmask & gcm & (g_s1_nom["n_act"] == 0))
            y_zb, _, _ = _g_yield(rmask & gcm & (g_s1_nom["n_act"] > 0))
            y_s1_zb, e_s1_zb, _ = _g_yield(rmask & gcm & g_s1_nom["s1_zb"])
            y_s1_q200, _, _ = _g_yield(rmask & gcm & g_s1_q200["s1_zb"])
            y_s2_zb, e_s2_zb, _ = _g_yield(rmask & gcm & g_s1_nom["s2_zb"])
            y_s1_ext, _, _ = _g_yield(rmask & gcm & g_s1_rawext["s1_zb"])
            genie_cr_rows.append({
                "region": rname,
                "truth_class": gc_name,
                "raw_mc_count": n_all,
                "yield_all_335p9fb": round(y_all, 3),
                "err_all": round(e_all, 3),
                "yield_zoneA_S0": round(y_za, 3),
                "yield_zoneB_all": round(y_zb, 3),
                "yield_S1_zoneB": round(y_s1_zb, 3),
                "err_S1_zoneB": round(e_s1_zb, 3),
                "yield_S1_Qlt200": round(y_s1_q200, 3),
                "yield_S2_zoneB": round(y_s2_zb, 3),
                "err_S2_zoneB": round(e_s2_zb, 3),
                "yield_S1_raw40_ext_zoneB": round(y_s1_ext, 3),
            })
    write_tsv(OUT_DIR / "t4_genie_cr_contamination.tsv", genie_cr_rows)

    def _genie_geom_slice_counts(lo: float, hi: float, use_u: bool, geom_sub: str = "ALL", q_slice: slice = slice(0, 4)) -> tuple[float, float, float, float]:
        if geom_sub == "OUTER":
            gm = genie_ev["region"] == REG_CR_GEOM_OUTER
        elif geom_sub == "HITHETA":
            gm = genie_ev["region"] == REG_CR_GEOM_HITHETA
        else:
            gm = (genie_ev["region"] == REG_CR_GEOM_OUTER) | (genie_ev["region"] == REG_CR_GEOM_HITHETA)
        if q_slice.stop <= 3:
            gm = gm & (np.maximum(genie_ev["q0_raw"], genie_ev["q1_raw"]) < 200.0)
        if use_u:
            base = gm & g_nom_mask & g_downA_ok & g_downB_ok & g_vu0 & g_vu1 & (genie_ev["q0_raw"] >= 30.0) & (genie_ev["q1_raw"] >= 30.0)
            x, y = genie_ev["u0"], genie_ev["u1"]
        else:
            base = gm & g_nom_mask & g_down_ok & g_v0 & g_v1 & (genie_ev["q0_raw"] >= 30.0) & (genie_ev["q1_raw"] >= 30.0)
            x, y = genie_ev["dt0"], genie_ev["dt1"]
        cD = float(np.sum(g_w[base & (np.abs(x) < 1.0) & (np.abs(y) < 1.0)]))
        cB = float(np.sum(g_w[base & (x >= lo) & (x < hi) & (np.abs(y) < 1.0)]))
        cC = float(np.sum(g_w[base & (np.abs(x) < 1.0) & (y >= lo) & (y < hi)]))
        cA = float(np.sum(g_w[base & (x >= lo) & (x < hi) & (y >= lo) & (y < hi)]))
        return cD, cB, cC, cA

    # =========================================================================
    # 3. ABCD Closure Tests in CR-Geom (All-Q, MIP Q<200, HiTheta, 1-hit) & Neg-SR
    # =========================================================================
    closure_rows = []
    for scope_name, g_idx_slice, q_slice in [
        ("CR_Geom_All", slice(0, 2), slice(0, 4)),
        ("CR_Geom_MIP_Qlt200", slice(0, 2), slice(0, 3)),
        ("CR_Geom_HiTheta", slice(1, 2), slice(0, 4)),
    ]:
        gsub_tag = "HITHETA" if scope_name == "CR_Geom_HiTheta" else "ALL"
        arr_g = np.sum(geom_abcd[:, g_idx_slice, :, q_slice, :, :], axis=(0, 1, 2, 3))
        for si, (sname, lo, hi) in enumerate(SLICE_BOUNDS):
            nd, nb, nc, na_obs = arr_g[si, 0], arr_g[si, 1], arr_g[si, 2], arr_g[si, 3]
            gd, gb, gc, ga = _genie_geom_slice_counts(lo, hi, True, gsub_tag, q_slice)
            pred_mu, err_mu = _abcd_pred_err(max(nb - gb, 0.0), max(nc - gc, 0.0), max(nd - gd, 1.0))
            pred_tot = pred_mu + ga
            comb_err = math.hypot(math.sqrt(max(na_obs, 1.0)), err_mu)
            pull = (na_obs - pred_tot) / comb_err if comb_err > 0 else 0.0
            closure_rows.append({
                "test_type": scope_name,
                "observable": "decoupled_u0_u1",
                "slice": sname,
                "n_D_obs": int(round(nd)),
                "n_B_obs": int(round(nb)),
                "n_C_obs": int(round(nc)),
                "n_A_obs": int(round(na_obs)),
                "n_A_genie_nu": round(ga, 2),
                "n_A_mu_pred_abcd": round(pred_mu, 2),
                "err_mu_pred": round(err_mu, 2),
                "n_A_tot_pred": round(pred_tot, 2),
                "obs_over_pred": round(na_obs / max(pred_tot, 1e-6), 3),
                "pull_sigma": round(pull, 2),
            })

            nd_d, nb_d, nc_d, na_d = arr_g[si, 7], arr_g[si, 5], arr_g[si, 6], arr_g[si, 4]
            gd_d, gb_d, gc_d, ga_d = _genie_geom_slice_counts(lo, hi, False, gsub_tag, q_slice)
            pred_d, err_d = _abcd_pred_err(max(nb_d - gb_d, 0.0), max(nc_d - gc_d, 0.0), max(nd_d - gd_d, 1.0))
            pred_d_tot = pred_d + ga_d
            comb_d = math.hypot(math.sqrt(max(na_d, 1.0)), err_d)
            closure_rows.append({
                "test_type": scope_name,
                "observable": "common_dt0_dt1_raw",
                "slice": sname,
                "n_D_obs": int(round(nd_d)),
                "n_B_obs": int(round(nb_d)),
                "n_C_obs": int(round(nc_d)),
                "n_A_obs": int(round(na_d)),
                "n_A_genie_nu": round(ga_d, 2),
                "n_A_mu_pred_abcd": round(pred_d, 2),
                "err_mu_pred": round(err_d, 2),
                "n_A_tot_pred": round(pred_d_tot, 2),
                "obs_over_pred": round(max(0.0, na_d - ga_d) / max(pred_d, 1e-6), 3) if pred_d > 0 else 1.0,
                "pull_sigma": round((na_d - pred_d_tot) / max(comb_d, 1e-6), 2),
            })

    # Unblinded Negative Kinematic SR mirror ABCD (MIP Q<200 and All-Q)
    for scope_sr, q_sl in [("Kinematic_SR_NegMirror_AllQ", slice(0, 4)), ("Kinematic_SR_NegMirror_MIP_Qlt200", slice(0, 3))]:
        arr_srn = np.sum(sr_neg_abcd[:, :, q_sl, :, :], axis=(0, 1, 2))
        for si, (sname, _, _) in enumerate(SLICE_BOUNDS):
            nd, nb, nc, na_obs = arr_srn[si, 0], arr_srn[si, 1], arr_srn[si, 2], arr_srn[si, 3]
            pred_mu, err_mu = _abcd_pred_err(nb, nc, max(nd, 1.0))
            comb_err = math.hypot(math.sqrt(max(na_obs, 1.0)), err_mu)
            closure_rows.append({
                "test_type": scope_sr,
                "observable": "decoupled_u0_u1_neg",
                "slice": sname,
                "n_D_obs": int(round(nd)),
                "n_B_obs": int(round(nb)),
                "n_C_obs": int(round(nc)),
                "n_A_obs": int(round(na_obs)),
                "n_A_genie_nu": 0.0,
                "n_A_mu_pred_abcd": round(pred_mu, 2),
                "err_mu_pred": round(err_mu, 2),
                "n_A_tot_pred": round(pred_mu, 2),
                "obs_over_pred": round(na_obs / max(pred_mu, 1e-6), 3) if pred_mu > 0 else 0.0,
                "pull_sigma": round((na_obs - pred_mu) / max(comb_err, 1e-6), 2),
            })
            nd_dt, nb_dt, nc_dt, na_dt = arr_srn[si, 4], arr_srn[si, 5], arr_srn[si, 6], arr_srn[si, 7]
            pred_dt, err_dt = _abcd_pred_err(nb_dt, nc_dt, max(nd_dt, 1.0))
            comb_dt = math.hypot(math.sqrt(max(na_dt, 1.0)), err_dt)
            closure_rows.append({
                "test_type": scope_sr,
                "observable": "common_dt0_dt1_neg",
                "slice": sname,
                "n_D_obs": int(round(nd_dt)),
                "n_B_obs": int(round(nb_dt)),
                "n_C_obs": int(round(nc_dt)),
                "n_A_obs": int(round(na_dt)),
                "n_A_genie_nu": 0.0,
                "n_A_mu_pred_abcd": round(pred_dt, 2),
                "err_mu_pred": round(err_dt, 2),
                "n_A_tot_pred": round(pred_dt, 2),
                "obs_over_pred": round(na_dt / max(pred_dt, 1e-6), 3) if pred_dt > 0 else 0.0,
                "pull_sigma": round((na_dt - pred_dt) / max(comb_dt, 1e-6), 2),
            })

    # 1-hit missed-layer closure in CR-Geom using weighted D (~458M) and single-arm tail rate
    w_idx_195 = S1_WMAX_GRID.index(19.5)
    sum_2h = np.sum(cr_geom_2hit[:, 0, w_idx_195, :, :, :, :], axis=(0, 1, 2))
    nd_2h = float(np.sum(geom_abcd[:, :, :, :, SLICE_NAMES.index("cum_1p5_22"), 7]))  # |dt|<1.0, |t0_down|<2.5 weighted!
    gm_all_mask = (genie_ev["region"] == REG_CR_GEOM_OUTER) | (genie_ev["region"] == REG_CR_GEOM_HITHETA)
    for t1 in S1_T1_GRID:
        t2_closest = min(range(len(S1_T2_GRID)), key=lambda idx: abs(S1_T2_GRID[idx] - t1))
        t2_val = S1_T2_GRID[t2_closest]
        p_t0 = sum_2h[3, t2_closest] / max(nd_2h, 1.0)
        p_t1 = sum_2h[4, t2_closest] / max(nd_2h, 1.0)
        gs = _s1_s2_masks(genie_ev, False, t2=2.2, t1=t1, wmax=19.5, require_intime_t0=True)
        for lay, p_tail in ((0, p_t0), (1, p_t1)):
            n_1h_prompt = float(np.sum(onehit_tens[:, 0, 1, lay, w_idx_195, :, 0]))
            n_1h_obs = float(np.sum(onehit_tens[:, 0, 1, lay, w_idx_195, :, 1 + S1_T1_GRID.index(t1)]))
            n_1h_g = float(np.sum(g_w[g_nom_mask & gm_all_mask & (gs["s1_10"] if lay == 0 else gs["s1_11"])]))
            pred_mu_1h = n_1h_prompt * p_tail
            pred_tot_1h = pred_mu_1h + n_1h_g
            err_tot = math.hypot(math.sqrt(max(n_1h_obs, 1.0)), math.sqrt(max(pred_mu_1h, 1.0)))
            closure_rows.append({
                "test_type": f"CR_Geom_1Hit_VN{lay}",
                "observable": f"tail_from_T2hit_{t2_val:.1f}",
                "slice": f"T1_{t1:.1f}_22",
                "n_D_obs": int(round(n_1h_prompt)),
                "n_B_obs": int(round(sum_2h[3 if lay == 0 else 4, t2_closest])),
                "n_C_obs": int(round(nd_2h)),
                "n_A_obs": int(round(n_1h_obs)),
                "n_A_genie_nu": round(n_1h_g, 2),
                "n_A_mu_pred_abcd": round(pred_mu_1h, 2),
                "err_mu_pred": round(math.sqrt(max(pred_mu_1h, 1.0)), 2),
                "n_A_tot_pred": round(pred_tot_1h, 2),
                "obs_over_pred": round(n_1h_obs / max(pred_tot_1h, 1e-6), 3),
                "pull_sigma": round((n_1h_obs - pred_tot_1h) / max(err_tot, 1e-6), 2),
            })

    write_tsv(OUT_DIR / "t4_abcd_closure_tests.tsv", closure_rows)

    # =========================================================================
    # 4. Prompt Normalization & Negative-Tail Transfer Factors
    # =========================================================================
    sr_2d = np.sum(prompt_sub_2d[0], axis=0)
    gm_2d = np.sum(prompt_sub_2d[1], axis=0)
    n_d_sr_dt = float(all_pers_agg["n_sr_prompt_2hit_dt1p0"])
    n_d_sr_u = float(all_pers_agg["n_sr_prompt_2hit_u1p0"])
    n_d_gm_dt = float(all_pers_agg["n_geom_prompt_2hit_dt1p0"])
    n_d_gm_u = float(all_pers_agg["n_geom_prompt_2hit_u1p0"])

    # In-time weighted CR-Geom and SR |x|<1, |y|<1 denominators from weighted ABCD tensors:
    si_cum15 = SLICE_NAMES.index("cum_1p5_22")
    gm_2d_u_t0 = np.sum(geom_abcd[:, :, :, :, si_cum15, 0], axis=(0, 1))  # [rvn, q]
    gm_2d_dt_t0 = np.sum(geom_abcd[:, :, :, :, si_cum15, 7], axis=(0, 1))  # [rvn, q]
    n_d_gm_u_t0 = float(np.sum(gm_2d_u_t0))
    n_d_gm_dt_t0 = float(np.sum(gm_2d_dt_t0))
    n_d_sr_u_t0 = float(np.sum(sr_neg_abcd[:, :, :, si_cum15, 0]))
    n_d_sr_dt_t0 = float(np.sum(sr_neg_abcd[:, :, :, si_cum15, 4]))

    sr_prompt_2d_counts = sr_2d * (n_d_sr_u_t0 / max(float(np.sum(sr_2d)), 1.0))
    # Use direct weighted gm_2d_u_t0 when populated, normalized cleanly
    gm_prompt_2d_counts = np.where(gm_2d_u_t0 > 0.0, gm_2d_u_t0, gm_2d * (n_d_gm_u_t0 / max(float(np.sum(gm_2d)), 1.0)))

    def _hist_tail_frac(hname_sr: str, hname_gm: str, lo: float, hi: float, ref_sr: float, ref_gm: float) -> tuple[float, float, float, float]:
        vsr = sum(data_hists[p][hname_sr][0] for p in data_hists if hname_sr in data_hists[p])
        vgm = sum(data_hists[p][hname_gm][0] for p in data_hists if hname_gm in data_hists[p])
        e = next(iter(data_hists.values()))[hname_sr][1]
        c = 0.5 * (e[:-1] + e[1:])
        m = (c >= lo) & (c < hi)
        csr, cgm = float(np.sum(vsr[m])), float(np.sum(vgm[m]))
        psr, pgm = csr / max(ref_sr, 1.0), cgm / max(ref_gm, 1.0)
        r = psr / max(pgm, 1e-12)
        err = r * math.sqrt(1.0 / max(csr, 1.0) + 1.0 / max(cgm, 1.0))
        return psr, pgm, r, err

    r_neg_list = []
    for tneg in (1.5, 2.2, 3.0):
        _, _, r0, e0 = _hist_tail_frac("h_sr_u0_prompt", "h_geom_u0", -22.0, -tneg, n_d_sr_u, n_d_gm_u)
        _, _, r1, e1 = _hist_tail_frac("h_sr_u1_prompt", "h_geom_u1", -22.0, -tneg, n_d_sr_u, n_d_gm_u)
        r_neg_list.append((tneg, r0, e0, r1, e1))

    # =========================================================================
    # 5. FLUKA Normalization, GENIE 1-Hit Helper & Exact Era-Consistent 1-Hit SR Counts
    # =========================================================================
    f_sr_mc22 = sum(d["n_sr_prompt_2hit_dt1p0"] for r, d in fluka_runs.items() if r in FLUKA_ERA_MC22)
    f_sr_mc24 = sum(d["n_sr_prompt_2hit_dt1p0"] for r, d in fluka_runs.items() if r in FLUKA_ERA_MC24)
    d_sr_mc22 = data_pers.get("2022", {}).get("n_sr_prompt_2hit_dt1p0", 0) + data_pers.get("2023", {}).get("n_sr_prompt_2hit_dt1p0", 0)
    d_sr_mc24 = n_d_sr_dt - d_sr_mc22
    scale_mc22 = d_sr_mc22 / max(f_sr_mc22, 1.0)
    scale_mc24 = d_sr_mc24 / max(f_sr_mc24, 1.0)

    f_runs_arr = fluka_ev["run"] if fluka_ev else np.array([], dtype=np.int32)
    f_w = np.where(np.isin(f_runs_arr, list(FLUKA_ERA_MC22)), scale_mc22, scale_mc24) if len(f_runs_arr) else np.array([], dtype=np.float64)

    # Era-consistent SR 1-hit prompt counts [rvn_bin] from unprescaled histograms (2022-2024 red30 + 2025-2026 raw40)
    def _sr_1hit_radial_counts(use_raw40: bool) -> tuple[np.ndarray, np.ndarray]:
        edges_h = next(iter(data_hists.values()))["h_sr_rvn_1hit0"][1]
        centers_h = 0.5 * (edges_h[:-1] + edges_h[1:])
        v0 = np.zeros_like(centers_h)
        v1 = np.zeros_like(centers_h)
        for per in PERIODS:
            if per not in data_hists:
                continue
            use_r = use_raw40 or (per in ("2025", "2026"))
            h0n = "h_sr_rvn_1hit0_raw40" if use_r else "h_sr_rvn_1hit0"
            h1n = "h_sr_rvn_1hit1_raw40" if use_r else "h_sr_rvn_1hit1"
            if h0n in data_hists[per]:
                v0 += data_hists[per][h0n][0]
            if h1n in data_hists[per]:
                v1 += data_hists[per][h1n][0]
        c0 = np.zeros(len(RVN_BINS_EDGE) - 1, dtype=np.float64)
        c1 = np.zeros(len(RVN_BINS_EDGE) - 1, dtype=np.float64)
        for bi in range(len(RVN_BINS_EDGE) - 1):
            m = (centers_h >= RVN_BINS_EDGE[bi]) & (centers_h < RVN_BINS_EDGE[bi + 1])
            c0[bi] = float(np.sum(v0[m]))
            c1[bi] = float(np.sum(v1[m]))
        return c0, c1

    sr_1h0_red, sr_1h1_red = _sr_1hit_radial_counts(False)
    sr_1h0_raw, sr_1h1_raw = _sr_1hit_radial_counts(True)

    # Active-VetoNu SR Zone-A S0 count (excluding dead 2025 runs & using raw40 in 2025-2026)
    sr_za_active = 0
    for per in PERIODS:
        pd = data_pers.get(per, {})
        sr_za_active += int(pd.get("n_sr_zonea_raw40" if per in ("2025", "2026") else "n_sr_zonea_red30", 0))

    # GENIE 2-hit tail counts per (rvn, q) for B1 subtraction & CR-Geom total closure
    def _genie_geom_1d_rate_grid(t2_list: list[float], wmax: float) -> dict[float, tuple[np.ndarray, np.ndarray]]:
        base = gm_all_mask & g_nom_mask & g_downA_ok & g_downB_ok & ((genie_ev["w0"] > 1.5) & (genie_ev["w0"] < wmax)) & ((genie_ev["w1"] > 1.5) & (genie_ev["w1"] < wmax)) & (genie_ev["q0_raw"] >= 30.0) & (genie_ev["q1_raw"] >= 30.0)
        rvi_g = np.clip(np.digitize(genie_ev["r_vn"], RVN_BINS_EDGE) - 1, 0, len(RVN_BINS_EDGE) - 2)
        qm_g = np.maximum(genie_ev["q0_raw"], genie_ev["q1_raw"])
        qi_g = np.clip(np.digitize(qm_g, Q_BINS_EDGE) - 1, 0, len(Q_BINS_EDGE) - 2)
        x, y = genie_ev["u0"], genie_ev["u1"]
        out_g = {}
        for t2 in t2_list:
            g0 = np.zeros((len(RVN_BINS_EDGE) - 1, len(Q_BINS_EDGE) - 1), dtype=np.float64)
            g1 = np.zeros((len(RVN_BINS_EDGE) - 1, len(Q_BINS_EDGE) - 1), dtype=np.float64)
            m0 = base & (x > t2) & (x < 22.0) & (np.abs(y) < 1.0)
            m1 = base & (y > t2) & (y < 22.0) & (np.abs(x) < 1.0)
            if np.any(m0):
                np.add.at(g0, (rvi_g[m0], qi_g[m0]), g_w[m0])
            if np.any(m1):
                np.add.at(g1, (rvi_g[m1], qi_g[m1]), g_w[m1])
            out_g[t2] = (g0, g1)
        return out_g

    g_tail_u_by_w = {wmax: _genie_geom_1d_rate_grid(S1_T2_GRID, wmax) for wmax in S1_WMAX_GRID}

    # Pure instrumental common-t0 conversion C_t0(t2) measured in unblinded Kinematic_SR_NegMirror_MIP_Qlt200
    # (exact SR geometry, Q<200 MIP core, free of positive-tail showers; B3 captures all positive-tail shower excess)
    c_t0_by_t2: dict[float, float] = {}
    c_t0_err_by_t2: dict[float, float] = {}
    u_neg_pred_by_sl = {
        r["slice"]: float(r["n_A_mu_pred_abcd"])
        for r in closure_rows
        if r["test_type"] == "Kinematic_SR_NegMirror_MIP_Qlt200" and r["observable"] == "decoupled_u0_u1_neg"
    }
    last_good_c, last_good_e = 1.25, 0.10
    for row in closure_rows:
        if row["test_type"] == "Kinematic_SR_NegMirror_MIP_Qlt200" and row["observable"] == "common_dt0_dt1_neg" and row["slice"].startswith("cum_"):
            tval = float(row["slice"].replace("cum_", "").replace("_22", "").replace("p", "."))
            n_dt_neg = float(row["n_A_obs"])
            u_pred_neg = max(u_neg_pred_by_sl.get(row["slice"], 1.0), 1.0)
            if n_dt_neg >= 50.0:
                c_val = min(2.0, max(1.0, n_dt_neg / u_pred_neg))
                e_val = c_val / math.sqrt(n_dt_neg)
                c_t0_by_t2[tval] = c_val
                c_t0_err_by_t2[tval] = e_val
                last_good_c, last_good_e = c_val, e_val
            else:
                c_t0_by_t2[tval] = last_good_c
                c_t0_err_by_t2[tval] = last_good_e
    for tval in S1_T2_GRID:
        if tval not in c_t0_by_t2:
            c_t0_by_t2[tval] = last_good_c
            c_t0_err_by_t2[tval] = last_good_e

    # =========================================================================
    # 6. B3 (CR-Geom Correlated Excess vs FLUKA), B4 (CR-EdgeVN), & B5 (NonColl/Acc)
    # =========================================================================
    edge_tot_data = int(all_pers_agg.get("n_edge_vn_all", 0))
    edge_za_data = int(all_pers_agg.get("n_edge_vn_zonea_red30", 0))
    m_edge_d = data_small_ev["region"] == REG_CR_EDGE_VN if data_small_ev else np.array([], dtype=bool)
    m_edge_g = (genie_ev["region"] == REG_CR_EDGE_VN) & g_nom_mask
    edge_za_genie = float(np.sum(g_w[m_edge_g & (g_s1_nom["n_act"] == 0)]))
    edge_za_mu = max(0.0, float(edge_za_data) - edge_za_genie)
    # Note 2026 VetoGm tag rate on CR-EdgeVN
    vgm_edge_n26, vgm_edge_tagged40 = 0, 0
    if np.any(m_edge_d):
        m_e26 = m_edge_d & (data_small_ev["vgm_max_q"] >= 0.0)
        vgm_edge_n26 = int(np.count_nonzero(m_e26))
        vgm_edge_tagged40 = int(np.count_nonzero(m_e26 & (data_small_ev["vgm_max_q"] >= 40.0)))

    # Conservative upper bound on Zone-A grazing muons entering SR (from Stage T3 FLUKA S0=0, EdgeVN 28.4 in [120,180), and Data vs GENIE Zone A):
    b4_grazing_sr_bound = 25.0

    # B5 accidental rates from unbiased non-colliding crossings
    n_coll_tot = float(all_pers_agg.get("n_colliding", 0))
    n_b1_tot = float(all_pers_agg.get("n_beam1", 0))
    n_unp_tot = float(all_pers_agg.get("n_unpaired", 0))
    n_emp_tot = float(all_pers_agg.get("n_empty_bcid", 0))
    n_cos_tot = float(sum(d["n_total"] for d in cosmic_pers.values())) if cosmic_pers else 0.0
    n_cos_long = float(sum(d.get("n_cosmic_long_trk", 0) for d in cosmic_pers.values())) if cosmic_pers else 0.0
    n_cos_20 = float(sum(d.get("n_cosmic_downscint_trk20", 0) for d in cosmic_pers.values())) if cosmic_pers else 0.0
    n_cos_100 = float(sum(d.get("n_cosmic_downtrk", 0) for d in cosmic_pers.values())) if cosmic_pers else 0.0

    n_acc_den = float(all_pers_agg.get("n_acc_denom_noncoll", 0))
    n_acc_del0 = float(all_pers_agg.get("n_acc_vn0_delayed_t1", 0))
    n_acc_del1 = float(all_pers_agg.get("n_acc_vn1_delayed_t1", 0))
    p_acc_vn0_q30 = float(all_pers_agg.get("n_acc_vn0_q30", 0)) / max(n_acc_den, 1.0)
    p_acc_vn1_q30 = float(all_pers_agg.get("n_acc_vn1_q30", 0)) / max(n_acc_den, 1.0)
    p_acc_both_q30 = float(all_pers_agg.get("n_acc_vnboth_q30", 0)) / max(n_acc_den, 1.0)
    p_acc_vn0_del = n_acc_del0 / max(n_acc_den, 1.0)
    p_acc_vn1_del = n_acc_del1 / max(n_acc_den, 1.0)

    vsat_tot = sum(data_hists[p]["h_down_t1_sat"][0] for p in data_hists if "h_down_t1_sat" in data_hists[p])
    esat = next(iter(data_hists.values()))["h_down_t1_sat"][1]
    csat = 0.5 * (esat[:-1] + esat[1:])
    n_sat_core = float(np.sum(vsat_tot[(csat >= -1.5) & (csat <= 1.5)]))
    f_sat_pos = float(np.sum(vsat_tot[(csat >= 1.8) & (csat < 12.5)])) / max(n_sat_core, 1.0)

    m_nc_b1 = (data_small_ev["region"] == REG_NONCOLL_B1) if data_small_ev else np.array([], dtype=bool)
    m_nc_unp = (data_small_ev["region"] == REG_NONCOLL_UNPAIRED) if data_small_ev else np.array([], dtype=bool)
    m_nc_emp = (data_small_ev["region"] == REG_NONCOLL_EMPTY) if data_small_ev else np.array([], dtype=bool)
    m_sr_geom_cuts = (
        (data_small_ev["r_max"] < 95.0) & (data_small_ev["r_ift"] < 95.0)
        & (data_small_ev["r_vn"] < 120.0) & (data_small_ev["theta_mrad"] < 25.0)
    ) if data_small_ev else np.array([], dtype=bool)

    b5_rows = [
        {"channel": "Beam1_InB1_0", "n_stream_events": int(n_b1_tot), "n_downtrk_all": int(nc_tot[0]),
         "n_downtrk_kin_sr": int(nc_tot[1]),
         "exposure_scale_to_coll": round(n_coll_tot / max(n_b1_tot, 1.0), 4),
         "p_acc_vn0_q30": round(p_acc_vn0_q30, 8), "p_acc_vn1_q30": round(p_acc_vn1_q30, 8),
         "p_acc_vnboth_q30": round(p_acc_both_q30, 8), "p_acc_vn0_delayed_2p2": round(p_acc_vn0_del, 8),
         "p_acc_vn1_delayed_2p2": round(p_acc_vn1_del, 8)},
        {"channel": "Unpaired_BCID", "n_stream_events": int(n_unp_tot), "n_downtrk_all": int(nc_tot[2]),
         "n_downtrk_kin_sr": int(nc_tot[3]),
         "exposure_scale_to_coll": round(n_coll_tot / max(n_unp_tot, 1.0), 4),
         "p_acc_vn0_q30": 0.0, "p_acc_vn1_q30": 0.0, "p_acc_vnboth_q30": 0.0, "p_acc_vn0_delayed_2p2": 0.0, "p_acc_vn1_delayed_2p2": 0.0},
        {"channel": "Empty_BCID_Other", "n_stream_events": int(n_emp_tot), "n_downtrk_all": int(nc_tot[4]),
         "n_downtrk_kin_sr": int(nc_tot[5]),
         "exposure_scale_to_coll": round(n_coll_tot / max(n_emp_tot, 1.0), 4),
         "p_acc_vn0_q30": 0.0, "p_acc_vn1_q30": 0.0, "p_acc_vnboth_q30": 0.0, "p_acc_vn0_delayed_2p2": 0.0, "p_acc_vn1_delayed_2p2": 0.0},
        {"channel": "Cosmic_2024_cos", "n_stream_events": int(n_cos_tot), "n_downtrk_all": int(n_cos_100),
         "n_downtrk_kin_sr": int(np.sum((cosmic_ev["r_max"] < 95.0) & (cosmic_ev["r_ift"] < 95.0) & (cosmic_ev["r_vn"] < 120.0) & (cosmic_ev["theta_mrad"] < 25.0) & ((cosmic_ev["flags"] & FLAG_PASS_LEAD_TRK) != 0))) if cosmic_ev else 0,
         "exposure_scale_to_coll": round(n_coll_tot / max(n_cos_tot, 1.0), 4),
         "p_acc_vn0_q30": round(f_sat_pos, 8), "p_acc_vn1_q30": float(n_cos_long),
         "p_acc_vnboth_q30": float(n_cos_20), "p_acc_vn0_delayed_2p2": 0.0, "p_acc_vn1_delayed_2p2": 0.0},
    ]
    write_tsv(OUT_DIR / "t4_b5_accidental_noncoll.tsv", b5_rows)

    genie_sr_za = float(np.sum(g_w[(genie_ev["region"] == REG_KIN_SR) & g_nom_mask & (g_s1_nom["n_act"] == 0)]))

    def _compute_b5(use_raw40: bool, t2: float, t1: float, wmax: float, q2hit_max: float = 1e9, ext_m: float | None = None, req_t0: bool = True) -> tuple[float, float, int]:
        n_b1_zb = 0
        if data_small_ev:
            dm = _s1_s2_masks(data_small_ev, use_raw40, t2=t2, t1=t1, wmax=wmax, raw40_ext_min=ext_m, q2hit_max=q2hit_max, require_intime_t0=req_t0)
            n_b1_zb = int(np.count_nonzero(m_nc_b1 & m_sr_geom_cuts & dm["s1_zb"]))
        # In-situ accidental coincidence: active Data Zone A S0 minus GENIE * non-colliding delayed hit rate
        t_win_scale = max(22.0 - t1, 0.5) / 19.8
        n_s0_mu_sr = max(0.0, float(sr_za_active) - genie_sr_za)
        b_pileup = n_s0_mu_sr * (p_acc_vn0_del + p_acc_vn1_del) * t_win_scale
        b_pileup_err = n_s0_mu_sr * math.sqrt(max(n_acc_del0 + n_acc_del1, 1.0)) / max(n_acc_den, 1.0) * t_win_scale
        return b_pileup, b_pileup_err, n_b1_zb

    # =========================================================================
    # 7. Exact Five-Component Background Scan B1..B5 Without Double-Counting
    # =========================================================================
    def _eval_s1(cm_name: str, cm_var: int, wmax: float, t2: float, t1: float, rvn_max: float = 120.0,
                 q2hit_max: float = 1e9, ext_m: float | None = None, req_t0: bool = True) -> dict[str, float]:
        wi = S1_WMAX_GRID.index(wmax)
        ti2 = S1_T2_GRID.index(t2)
        ti1 = S1_T1_GRID.index(t1)
        qci = QCUT_2HIT_VALS.index(q2hit_max)
        use_raw = cm_var >= 1
        cm_raw = 1 if use_raw else 0

        t_u0 = np.sum(cr_geom_2hit[:, cm_raw, wi, :, :, 0, ti2], axis=0)
        t_u1 = np.sum(cr_geom_2hit[:, cm_raw, wi, :, :, 1, ti2], axis=0)
        g0, g1 = g_tail_u_by_w[wmax][t2]
        t_u0_mu = np.maximum(0.0, t_u0 - g0)
        t_u1_mu = np.maximum(0.0, t_u1 - g1)

        rvn_mask = RVN_BINS_EDGE[:-1] < rvn_max - 1e-6
        q_mask = Q_BINS_EDGE[:-1] < min(q2hit_max, 1e9) - 1e-6 if q2hit_max <= 200.5 else np.ones(len(Q_BINS_EDGE) - 1, dtype=bool)

        sr_sub = sr_prompt_2d_counts[np.ix_(rvn_mask, q_mask)]
        gm_sub = np.maximum(gm_prompt_2d_counts[np.ix_(rvn_mask, q_mask)], 1.0)
        p0_2d = t_u0_mu[np.ix_(rvn_mask, q_mask)] / gm_sub
        p1_2d = t_u1_mu[np.ix_(rvn_mask, q_mask)] / gm_sub

        # Sub-200pC shape scaling for Q<180 / Q<150 from exact measured 2-hit tail fractions
        qscale0, qscale1 = 1.0, 1.0
        if q2hit_max < 199.0:
            wsi = 0 if wmax <= 12.5 else 1
            denom0 = max(float(cr_geom_qshape[wsi, 1, 0, ti2]), 1.0)
            denom1 = max(float(cr_geom_qshape[wsi, 1, 1, ti2]), 1.0)
            qscale0 = min(1.0, float(cr_geom_qshape[wsi, qci, 0, ti2]) / denom0)
            qscale1 = min(1.0, float(cr_geom_qshape[wsi, qci, 1, ti2]) / denom1)

        c_t0 = c_t0_by_t2.get(t2, 1.2)
        b1_bins = sr_sub * (p0_2d * qscale0) * (p1_2d * qscale1) * c_t0
        b1 = float(np.sum(b1_bins))
        var_b1 = float(np.sum((b1_bins ** 2) * (1.0 / np.maximum(t_u0_mu[np.ix_(rvn_mask, q_mask)] * qscale0, 1.0) + 1.0 / np.maximum(t_u1_mu[np.ix_(rvn_mask, q_mask)] * qscale1, 1.0))))
        if t2 in c_t0_err_by_t2 and b1 > 0:
            var_b1 += (b1 * (c_t0_err_by_t2[t2] / c_t0)) ** 2

        # Geom-domain B1 prediction (exact baseline for B3 subtraction so zero double-counting!)
        gm_all_q = np.maximum(gm_prompt_2d_counts[:, q_mask], 1.0)
        b1_geom_pred = float(np.sum(gm_all_q * (t_u0_mu[:, q_mask] * qscale0 / gm_all_q) * (t_u1_mu[:, q_mask] * qscale1 / gm_all_q) * c_t0))

        # B2: True SR 1-hit prompt counts * CR-Geom single-layer positive tail probability
        sr1h0_bins = sr_1h0_raw if use_raw else sr_1h0_red
        sr1h1_bins = sr_1h1_raw if use_raw else sr_1h1_red
        sum_2h_w = np.sum(cr_geom_2hit[:, cm_raw, wi, :, :, :, :], axis=(0, 1, 2))
        t2_cl = min(range(len(S1_T2_GRID)), key=lambda idx: abs(S1_T2_GRID[idx] - t1))
        p_t0_2h = float(sum_2h_w[3, t2_cl]) / max(n_d_gm_dt_t0, 1.0)
        p_t1_2h = float(sum_2h_w[4, t2_cl]) / max(n_d_gm_dt_t0, 1.0)

        # Direct 1-hit rate in CR-Geom (with GENIE subtraction)
        oh_gm_p0 = float(np.sum(onehit_tens[:, cm_raw, 1, 0, wi, :, 0]))
        oh_gm_p1 = float(np.sum(onehit_tens[:, cm_raw, 1, 1, wi, :, 0]))
        oh_gm_t0 = float(np.sum(onehit_tens[:, cm_raw, 1, 0, wi, :, 1 + ti1]))
        oh_gm_t1 = float(np.sum(onehit_tens[:, cm_raw, 1, 1, wi, :, 1 + ti1]))
        if ext_m is not None:
            oh_gm_t0 += float(np.sum(onehit_tens[:, cm_raw, 1, 0, wi, :, 15]))
            oh_gm_t1 += float(np.sum(onehit_tens[:, cm_raw, 1, 1, wi, :, 15]))
        gs_g = _s1_s2_masks(genie_ev, use_raw, t2=t2, t1=t1, wmax=wmax, raw40_ext_min=ext_m, q2hit_max=q2hit_max, require_intime_t0=req_t0)
        g_1h0_t = float(np.sum(g_w[g_nom_mask & gm_all_mask & gs_g["s1_10"]]))
        g_1h1_t = float(np.sum(g_w[g_nom_mask & gm_all_mask & gs_g["s1_11"]]))
        gm_t0_mu = max(0.0, oh_gm_t0 - g_1h0_t)
        gm_t1_mu = max(0.0, oh_gm_t1 - g_1h1_t)
        # Use direct 1-hit rate when > 0, else fall back conservatively to 2-hit single-layer MIP tail rate
        rate0 = max(gm_t0_mu / max(oh_gm_p0, 1.0) if oh_gm_p0 >= 20 else 0.0, p_t0_2h if oh_gm_p0 < 20 or gm_t0_mu == 0 else 0.0)
        rate1 = max(gm_t1_mu / max(oh_gm_p1, 1.0) if oh_gm_p1 >= 20 else 0.0, p_t1_2h if oh_gm_p1 < 20 or gm_t1_mu == 0 else 0.0)
        n_sr_1h0 = float(np.sum(sr1h0_bins[rvn_mask]))
        n_sr_1h1 = float(np.sum(sr1h1_bins[rvn_mask]))
        b2 = n_sr_1h0 * rate0 + n_sr_1h1 * rate1
        b2_err = math.hypot(n_sr_1h0 * math.sqrt(max(gm_t0_mu, 1.0)) / max(oh_gm_p0, 1.0), n_sr_1h1 * math.sqrt(max(gm_t1_mu, 1.0)) / max(oh_gm_p1, 1.0))
        b2_geom_pred = oh_gm_p0 * rate0 + oh_gm_p1 * rate1

        # B3 (non-double-counted data-driven CR-Geom excess above B1 + B2 + GENIE, scaled by N_SR / N_Geom!)
        if req_t0:
            obs_g_2h = float(np.sum(cr_geom_s1_2hit[:, cm_var, wi, qci, ti2]))
        else:
            obs_g_2h = float(np.sum(cr_geom_s1_2hit_not0[:, cm_var, wi, ti2]))
        obs_g_1h = float(np.sum(cr_geom_s1_1hit[:, cm_var, wi, ti1]))
        g_g_2h = float(np.sum(g_w[g_nom_mask & gm_all_mask & gs_g["s1_2"]]))
        g_g_1h = g_1h0_t + g_1h1_t
        ex_2h_g = max(0.0, obs_g_2h - b1_geom_pred - g_g_2h)
        ex_1h_g = max(0.0, obs_g_1h - b2_geom_pred - g_g_1h)
        sr_gm_ratio = n_d_sr_dt / max(n_d_gm_dt, 1.0)
        b3 = (ex_2h_g + ex_1h_g) * sr_gm_ratio
        b3_err = math.hypot(math.sqrt(max(obs_g_2h + obs_g_1h, 1.0)) * sr_gm_ratio, 0.25 * b3)

        # Also FLUKA MC comparison yield
        if len(f_runs_arr):
            fm = _s1_s2_masks(fluka_ev, use_raw40=True, t2=t2, t1=t1, wmax=wmax, raw40_ext_min=ext_m, q2hit_max=q2hit_max, require_intime_t0=req_t0)
            f_sr_m = (fluka_ev["region"] == REG_KIN_SR) & fm["s1_zb"]
            f_sr_tot = float(np.sum(f_w[f_sr_m]))
            f_sr_err = float(math.sqrt(np.sum(f_w[f_sr_m] ** 2)))
            f_sr_cnt = int(np.count_nonzero(f_sr_m))
        else:
            f_sr_tot, f_sr_err, f_sr_cnt = 0.0, 0.0, 0

        # B4 from EdgeVN * Data grazing bound
        if np.any(m_edge_d):
            dm_e = _s1_s2_masks(data_small_ev, use_raw, t2=t2, t1=t1, wmax=wmax, raw40_ext_min=ext_m, q2hit_max=q2hit_max, require_intime_t0=req_t0)
            n_edge_s1_d = int(np.count_nonzero(m_edge_d & dm_e["s1_zb"]))
        else:
            n_edge_s1_d = 0
        gm_e = _s1_s2_masks(genie_ev, use_raw, t2=t2, t1=t1, wmax=wmax, raw40_ext_min=ext_m, q2hit_max=q2hit_max, require_intime_t0=req_t0)
        n_edge_s1_g = float(np.sum(g_w[m_edge_g & gm_e["s1_zb"]]))
        edge_mu_zb = max(0.0, float(n_edge_s1_d) - n_edge_s1_g)
        b4 = b4_grazing_sr_bound * (edge_mu_zb / max(edge_za_mu, 1.0))
        b4_err = b4_grazing_sr_bound * math.sqrt(max(float(n_edge_s1_d), 1.0)) / max(edge_za_mu, 1.0)

        b5, b5_err, n_b1_zb = _compute_b5(use_raw, t2, t1, wmax, q2hit_max, ext_m, req_t0)

        # GENIE signal increment (Delta S in S1 ZoneB)
        m_g_sr = (genie_ev["region"] == REG_KIN_SR) & g_nom_mask
        gm_sr = _s1_s2_masks(genie_ev, use_raw, t2=t2, t1=t1, wmax=wmax, raw40_ext_min=ext_m, q2hit_max=q2hit_max, require_intime_t0=req_t0)
        s_rec = float(np.sum(g_w[m_g_sr & (genie_ev["genie_class"] == 1) & gm_sr["s1_zb"] & (genie_ev["r_vn"] < rvn_max)]))
        s0_base = float(np.sum(g_w[m_g_sr & (genie_ev["genie_class"] == 1) & (gm_sr["n_act"] == 0) & (genie_ev["r_vn"] < rvn_max)]))

        b_tot = b1 + b2 + b3 + b4 + b5
        b_err = math.sqrt(var_b1 + b2_err ** 2 + b3_err ** 2 + b4_err ** 2 + b5_err ** 2)
        return {
            "b1": b1, "b1_err": math.sqrt(var_b1), "b1_geom_pred": b1_geom_pred,
            "b2": b2, "b2_err": b2_err, "b2_geom_pred": b2_geom_pred,
            "b3": b3, "b3_err": b3_err, "obs_g_2h": obs_g_2h, "obs_g_1h": obs_g_1h,
            "b3_flk_all": f_sr_tot, "b3_flk_err": f_sr_err, "b3_flk_cnt": f_sr_cnt,
            "b4": b4, "b4_err": b4_err, "n_edge_s1_d": n_edge_s1_d, "n_edge_s1_g": n_edge_s1_g,
            "b5": b5, "b5_err": b5_err, "n_b1_zb": n_b1_zb,
            "b_tot": b_tot, "b_err": b_err,
            "s0_sig": s0_base, "s_rec": s_rec,
        }

    # Build t4_b3_b4_fluka_and_edge.tsv comparing allQ unfiltered vs |t0_down|<2.5 Q<200 & Q<180
    b3_b4_rows = []
    for qm_label, qval, wmax, t2, t1, rt0 in [
        ("allQ_not0", 1e9, 19.5, 2.2, 3.0, False),
        ("allQ_intime", 1e9, 19.5, 2.2, 3.0, True),
        ("allQ_intime_w12", 1e9, 12.0, 2.5, 3.5, True),
        ("Qlt200_intime_w12", 200.0, 12.0, 2.2, 3.0, True),
        ("Qlt200_intime_w12", 200.0, 12.0, 2.5, 3.0, True),
        ("Qlt200_intime_w12", 200.0, 12.0, 3.0, 3.0, True),
        ("Qlt180_intime_w12", 180.0, 12.0, 2.5, 3.0, True),
        ("Qlt180_intime_w12", 180.0, 12.0, 3.0, 3.0, True),
        ("Qlt150_intime_w12", 150.0, 12.0, 2.5, 3.0, True),
        ("Qlt150_intime_w12", 150.0, 12.0, 3.0, 3.0, True),
    ]:
        r = _eval_s1("red30", 0, wmax, t2, t1, 120.0, qval, None, rt0)
        b3_b4_rows.append({
            "regime": qm_label,
            "wmax_ns": wmax,
            "t2_ns": t2,
            "t1_ns": t1,
            "q2hit_max_pC": qval if qval < 1e8 else "inf",
            "intime_t0_cut": rt0,
            "cr_geom_obs_2hit": int(round(r["obs_g_2h"])),
            "cr_geom_obs_1hit": int(round(r["obs_g_1h"])),
            "cr_geom_b1_pred": round(r["b1_geom_pred"], 2),
            "b3_data_driven_sr": round(r["b3"], 2),
            "b3_data_err": round(r["b3_err"], 2),
            "fluka_sr_s1_cnt": r["b3_flk_cnt"],
            "fluka_sr_s1_yield": round(r["b3_flk_all"], 1),
            "fluka_sr_s1_err": round(r["b3_flk_err"], 1),
            "edge_vn_zoneA_mu": round(edge_za_mu, 1),
            "edge_vn_obs_zb": r["n_edge_s1_d"],
            "edge_vn_genie_zb": round(r["n_edge_s1_g"], 2),
            "b4_pred_335p9fb": round(r["b4"], 2),
            "b4_err": round(r["b4_err"], 2),
        })
    write_tsv(OUT_DIR / "t4_b3_b4_fluka_and_edge.tsv", b3_b4_rows)

    # Full S1 & S2 background budget scan
    budget_rows = []
    for qval, qlabel in [(1e9, "allQ"), (200.0, "Qlt200"), (180.0, "Qlt180"), (150.0, "Qlt150")]:
        for wmax in (12.0, 19.5) if qval < 1e8 else S1_WMAX_GRID:
            for t2 in S1_T2_GRID:
                for t1 in (2.5, 3.0, 3.5, 4.0) if qval < 1e8 else S1_T1_GRID:
                    if t1 < t2:
                        continue
                    if wmax not in (12.0, 19.5) and not (t2 in (2.2, 2.5, 3.0) and t1 in (3.0, 3.5, 4.0)):
                        continue
                    r = _eval_s1(f"red30_{qlabel}", 0, wmax, t2, t1, 120.0, qval, None, True)
                    s_tot_root = math.sqrt(max(r["s0_sig"] + r["s_rec"], 1.0))
                    budget_rows.append({
                        "strategy": "S1", "charge_mode": f"red30_{qlabel}", "wmax_ns": wmax,
                        "q2hit_max_pC": qval if qval < 1e8 else "inf", "rvn_cut_mm": 120.0,
                        "param1": t2, "param2": t1, "param3": 22.0,
                        "B1_stoch_2hit": round(r["b1"], 3), "B1_err": round(r["b1_err"], 3),
                        "B2_1hit_miss": round(r["b2"], 3), "B2_err": round(r["b2_err"], 3),
                        "B3_backscatter": round(r["b3"], 3), "B3_err": round(r["b3_err"], 3),
                        "B4_grazing": round(r["b4"], 3), "B4_err": round(r["b4_err"], 3),
                        "B5_accidental": round(r["b5"], 3), "B5_err": round(r["b5_err"], 3),
                        "B_tot": round(r["b_tot"], 3), "B_err": round(r["b_err"], 3),
                        "S_recovered_335p9fb": round(r["s_rec"], 2),
                        "B_over_Srec_pct": round(100.0 * r["b_tot"] / max(r["s_rec"], 1e-3), 2),
                        "B_over_sqrtS": round(r["b_tot"] / s_tot_root, 3),
                    })
    # Add unfiltered no-t0 baseline & rvn115 / rvn110 / raw40_ext / 1-hit-only benchmarks
    for cname, cmv, wmax, t2, t1, rvn, qv, extm, rt0 in [
        ("red30_unfiltered_not0", 0, 19.5, 2.2, 3.0, 120.0, 1e9, None, False),
        ("raw40_ext_Qlt200", 2, 12.0, 2.5, 3.0, 120.0, 200.0, 32.0, True),
        ("raw40_ext_Qlt180", 2, 12.0, 3.0, 3.0, 120.0, 180.0, 32.0, True),
        ("red30_Qlt200_rvn115", 0, 12.0, 2.5, 3.0, 115.0, 200.0, None, True),
        ("red30_1hit_only", 0, 12.0, 22.0, 3.0, 120.0, 0.0, None, True),
    ]:
        if t2 == 22.0:
            # Pure 1-hit only benchmark (no 2-hit events accepted in Zone B)
            r_ref = _eval_s1("red30_1hit", 0, 12.0, 3.5, 3.0, 120.0, 150.0, None, True)
            gm_sr = _s1_s2_masks(genie_ev, False, t2=22.0, t1=3.0, wmax=12.0, require_intime_t0=True)
            s_1h = float(np.sum(g_w[(genie_ev["region"] == REG_KIN_SR) & g_nom_mask & (genie_ev["genie_class"] == 1) & (gm_sr["s1_10"] | gm_sr["s1_11"])]))
            g_gm_1h = float(np.sum(g_w[gm_all_mask & g_nom_mask & (gm_sr["s1_10"] | gm_sr["s1_11"])]))
            obs_gm_1h_w12 = float(np.sum(cr_geom_s1_1hit[:, 0, S1_WMAX_GRID.index(12.0), S1_T1_GRID.index(3.0)]))
            sr_gm_r = n_d_sr_dt / max(n_d_gm_dt, 1.0)
            s_tot_root = math.sqrt(max(r_ref["s0_sig"] + s_1h, 1.0))
            b3_1h = max(0.0, obs_gm_1h_w12 - r_ref["b2_geom_pred"] - g_gm_1h) * sr_gm_r
            b3_1h_err = math.hypot(math.sqrt(max(obs_gm_1h_w12, 1.0)) * sr_gm_r, 0.25 * b3_1h)
            b_tot_1h = r_ref["b2"] + b3_1h + r_ref["b5"]
            b_err_1h = math.sqrt(r_ref["b2_err"] ** 2 + b3_1h_err ** 2 + r_ref["b4_err"] ** 2 + r_ref["b5_err"] ** 2)
            budget_rows.append({
                "strategy": "S1", "charge_mode": cname, "wmax_ns": 12.0, "q2hit_max_pC": 0.0,
                "rvn_cut_mm": 120.0, "param1": 22.0, "param2": 3.0, "param3": 22.0,
                "B1_stoch_2hit": 0.0, "B1_err": 0.0,
                "B2_1hit_miss": round(r_ref["b2"], 3), "B2_err": round(r_ref["b2_err"], 3),
                "B3_backscatter": round(b3_1h, 3), "B3_err": round(b3_1h_err, 3),
                "B4_grazing": 0.0, "B4_err": round(r_ref["b4_err"], 3),
                "B5_accidental": round(r_ref["b5"], 3), "B5_err": round(r_ref["b5_err"], 3),
                "B_tot": round(b_tot_1h, 3), "B_err": round(b_err_1h, 3),
                "S_recovered_335p9fb": round(s_1h, 2),
                "B_over_Srec_pct": round(100.0 * b_tot_1h / max(s_1h, 1e-3), 2),
                "B_over_sqrtS": round(b_tot_1h / s_tot_root, 3),
            })
        else:
            r = _eval_s1(cname, cmv, wmax, t2, t1, rvn, qv, extm, rt0)
            s_tot_root = math.sqrt(max(r["s0_sig"] + r["s_rec"], 1.0))
            budget_rows.append({
                "strategy": "S1", "charge_mode": cname, "wmax_ns": wmax, "q2hit_max_pC": qv if qv < 1e8 else "inf",
                "rvn_cut_mm": rvn, "param1": t2, "param2": t1, "param3": 22.0,
                "B1_stoch_2hit": round(r["b1"], 3), "B1_err": round(r["b1_err"], 3),
                "B2_1hit_miss": round(r["b2"], 3), "B2_err": round(r["b2_err"], 3),
                "B3_backscatter": round(r["b3"], 3), "B3_err": round(r["b3_err"], 3),
                "B4_grazing": round(r["b4"], 3), "B4_err": round(r["b4_err"], 3),
                "B5_accidental": round(r["b5"], 3), "B5_err": round(r["b5_err"], 3),
                "B_tot": round(r["b_tot"], 3), "B_err": round(r["b_err"], 3),
                "S_recovered_335p9fb": round(r["s_rec"], 2),
                "B_over_Srec_pct": round(100.0 * r["b_tot"] / max(r["s_rec"], 1e-3), 2),
                "B_over_sqrtS": round(r["b_tot"] / s_tot_root, 3),
            })

    # S2 threshold scan rows (both allQ and Q<200)
    m_g_sr = (genie_ev["region"] == REG_KIN_SR) & g_nom_mask
    for q_idx_s2, q_s2, q_lab_s2 in [(0, 1e9, "allQ"), (1, 200.0, "Qlt200")]:
        for dchi2_c in S2_DCHI2_GRID:
            for z2_c in S2_Z2_GRID:
                for z1_c in S2_Z1_GRID:
                    if q_idx_s2 == 0 and z1_c not in (5.0, 6.0):
                        continue
                    t2_eff = min(S1_T2_GRID, key=lambda t: abs(t - max(1.5, 0.56 * z2_c)))
                    t1_eff = min(S1_T1_GRID, key=lambda t: abs(t - max(2.0, 0.55 * z1_c)))
                    res_p = _eval_s1(f"s2_{q_lab_s2}", 0, 19.5, t2_eff, t1_eff, 120.0, q_s2, None, True)
                    # B2 from S2 pull rate
                    zi1 = S2_Z1_GRID.index(z1_c)
                    oh_p0 = float(np.sum(onehit_s2_tens[:, 0, 1, 0, :, 0]))
                    oh_p1 = float(np.sum(onehit_s2_tens[:, 0, 1, 1, :, 0]))
                    oh_t0 = float(np.sum(onehit_s2_tens[:, 0, 1, 0, :, 1 + zi1]))
                    oh_t1 = float(np.sum(onehit_s2_tens[:, 0, 1, 1, :, 1 + zi1]))
                    r0_s2 = oh_t0 / max(oh_p0, 1.0)
                    r1_s2 = oh_t1 / max(oh_p1, 1.0)
                    b2_s2 = float(np.sum(sr_1h0_red)) * r0_s2 + float(np.sum(sr_1h1_red)) * r1_s2
                    b2_s2_err = math.hypot(float(np.sum(sr_1h0_red)) * math.sqrt(max(oh_t0, 1.0)) / max(oh_p0, 1.0), float(np.sum(sr_1h1_red)) * math.sqrt(max(oh_t1, 1.0)) / max(oh_p1, 1.0))
                    # B3 from cr_geom_s2_2hit
                    di, zi2 = S2_DCHI2_GRID.index(dchi2_c), S2_Z2_GRID.index(z2_c)
                    obs_g_s2_2h = float(np.sum(cr_geom_s2_2hit[:, 0, di, zi2, q_idx_s2]))
                    gs_s2 = _s1_s2_masks(genie_ev, False, dchi2_min=dchi2_c, z2_min=z2_c, z1_mip=z1_c, z1_nonmip=max(4.0, z1_c - 1.0), q2hit_max=q_s2, require_intime_t0=True)
                    g_g_s2_2h = float(np.sum(g_w[g_nom_mask & gm_all_mask & gs_s2["s2_2"]]))
                    b3_s2 = max(0.0, obs_g_s2_2h - res_p["b1_geom_pred"] - g_g_s2_2h) * (n_d_sr_dt / max(n_d_gm_dt, 1.0))
                    b3_s2_err = math.hypot(math.sqrt(max(obs_g_s2_2h, 1.0)) * (n_d_sr_dt / max(n_d_gm_dt, 1.0)), 0.25 * b3_s2)
                    s_rec_s2 = float(np.sum(g_w[m_g_sr & (genie_ev["genie_class"] == 1) & gs_s2["s2_zb"]]))
                    b_tot_s2 = res_p["b1"] + b2_s2 + b3_s2 + res_p["b4"] + res_p["b5"]
                    b_err_s2 = math.sqrt(res_p["b1_err"] ** 2 + b2_s2_err ** 2 + b3_s2_err ** 2 + res_p["b4_err"] ** 2 + res_p["b5_err"] ** 2)
                    s_tot_root = math.sqrt(max(res_p["s0_sig"] + s_rec_s2, 1.0))
                    budget_rows.append({
                        "strategy": "S2", "charge_mode": f"red30_{q_lab_s2}", "wmax_ns": 19.5,
                        "q2hit_max_pC": q_s2 if q_s2 < 1e8 else "inf", "rvn_cut_mm": 120.0,
                        "param1": dchi2_c, "param2": z2_c, "param3": z1_c,
                        "B1_stoch_2hit": round(res_p["b1"], 3), "B1_err": round(res_p["b1_err"], 3),
                        "B2_1hit_miss": round(b2_s2, 3), "B2_err": round(b2_s2_err, 3),
                        "B3_backscatter": round(b3_s2, 3), "B3_err": round(b3_s2_err, 3),
                        "B4_grazing": round(res_p["b4"], 3), "B4_err": round(res_p["b4_err"], 3),
                        "B5_accidental": round(res_p["b5"], 3), "B5_err": round(res_p["b5_err"], 3),
                        "B_tot": round(b_tot_s2, 3), "B_err": round(b_err_s2, 3),
                        "S_recovered_335p9fb": round(s_rec_s2, 2),
                        "B_over_Srec_pct": round(100.0 * b_tot_s2 / max(s_rec_s2, 1e-3), 2),
                        "B_over_sqrtS": round(b_tot_s2 / s_tot_root, 3),
                    })
    write_tsv(OUT_DIR / "t4_background_budget_scan.tsv", budget_rows)

    # =========================================================================
    # 8. Period-by-Period Background Stability Audit (2022-2026)
    # =========================================================================
    period_rows = []
    wi_12 = S1_WMAX_GRID.index(12.0)
    ti2_25 = S1_T2_GRID.index(2.5)
    bm_clean = _eval_s1("red30_Qlt200", 0, 12.0, 2.5, 3.0, 120.0, 200.0, None, True)
    b1_rate_global = bm_clean["b1"] / max(n_d_sr_u_t0, 1.0)
    b3_rate_global = bm_clean["b3"] / max(n_d_sr_dt, 1.0)

    for pi, p in enumerate(PERIODS):
        pd = data_pers.get(p, {})
        lumi = lumi_by_period[p]
        n_sr_p = float(pd.get("n_sr_prompt_2hit_dt1p0", 0))
        n_gm_p = float(pd.get("n_geom_prompt_2hit_dt1p0", 0))
        if p in ("2025", "2026"):
            n_1h_p = float(pd.get("n_sr_prompt_1hit0_raw40", 0) + pd.get("n_sr_prompt_1hit1_raw40", 0))
        else:
            n_1h_p = float(pd.get("n_sr_prompt_1hit0_red30", 0) + pd.get("n_sr_prompt_1hit1_red30", 0))
        miss_rate_p = n_1h_p / max(n_sr_p + n_1h_p, 1.0)
        _, rho_u_p, err_rho_p, _, _ = _cov_rho(pd, "cov_sr_u_1p0")

        t_u0_p = float(np.sum(cr_geom_2hit[pi, 0, wi_12, :, :3, 0, ti2_25]))
        t_u1_p = float(np.sum(cr_geom_2hit[pi, 0, wi_12, :, :3, 1, ti2_25]))
        nd_gm_u_p = float(np.sum(geom_abcd[pi, :, :, :3, si_cum15, 0]))
        nd_sr_u_p = float(np.sum(sr_neg_abcd[pi, :, :3, si_cum15, 0]))
        if t_u0_p >= 10.0 and t_u1_p >= 10.0 and nd_gm_u_p > 0 and nd_sr_u_p > 0:
            b1_p = nd_sr_u_p * (t_u0_p / nd_gm_u_p) * (t_u1_p / nd_gm_u_p) * c_t0_by_t2.get(2.5, 1.2)
        else:
            b1_p = n_sr_p * b1_rate_global
        b3_p = n_sr_p * b3_rate_global
        b245_p = (bm_clean["b2"] + bm_clean["b4"] + bm_clean["b5"]) * (n_sr_p / max(n_d_sr_dt, 1.0))
        b_tot_p = b1_p + b3_p + b245_p
        period_rows.append({
            "period": p, "lumi_fb": round(lumi, 4), "n_runs": pd.get("n_runs", 0),
            "n_total": int(pd.get("n_total", 0)), "n_blinded_redacted": int(pd.get("n_blinded", 0)),
            "n_sr_prompt_2hit": int(n_sr_p), "sr_prompt_per_fb": round(n_sr_p / max(lumi, 1e-6), 1),
            "n_geom_prompt_2hit": int(n_gm_p), "geom_prompt_per_fb": round(n_gm_p / max(lumi, 1e-6), 1),
            "n_sr_1hit_prompt_era": int(n_1h_p), "miss_1hit_rate_ppm": round(1e6 * miss_rate_p, 4),
            "rho_u0_u1": round(rho_u_p, 5) if math.isfinite(rho_u_p) else "nan",
            "err_rho_u": round(err_rho_p, 5) if math.isfinite(err_rho_p) else "nan",
            "B1_est": round(b1_p, 3), "B3_est": round(b3_p, 3), "B245_est": round(b245_p, 3),
            "B_tot_est": round(b_tot_p, 3), "B_tot_per_fb": round(b_tot_p / max(lumi, 1e-6), 4),
        })
    write_tsv(OUT_DIR / "t4_period_stability.tsv", period_rows)

    def _find_row(**kw):
        for r in budget_rows:
            if all(r[k] == v for k, v in kw.items()):
                return r
        raise KeyError(f"Benchmark not found: {kw}")

    bench_unfilt = _find_row(strategy="S1", charge_mode="red30_unfiltered_not0")
    bench_mip200 = _find_row(strategy="S1", charge_mode="red30_Qlt200", wmax_ns=12.0, param1=2.5, param2=3.0)
    bench_mip180 = _find_row(strategy="S1", charge_mode="red30_Qlt180", wmax_ns=12.0, param1=3.0, param2=3.0)
    bench_1hit = _find_row(strategy="S1", charge_mode="red30_1hit_only")
    bench_s2_mip = _find_row(strategy="S2", charge_mode="red30_Qlt200", param1=25.0, param2=3.0, param3=6.0)

    summary = {
        "n_data_runs": len(data_runs),
        "dead_vetonu_runs_excluded": dead_audit_tot,
        "n_data_events_active": int(tot_data_events),
        "n_data_blinded_sr_zoneb": int(tot_data_blinded),
        "n_cr_geom_all": int(tot_data_geom),
        "lumi_total_fb": round(lumi_total, 4),
        "load_time_s": round(load_s, 2),
        "total_wall_s": round(time.perf_counter() - t_start, 2),
        "c_t0_by_t2": {str(k): round(v, 4) for k, v in sorted(c_t0_by_t2.items())},
        "edge_vn_2026_vetogm": {"n_checked": vgm_edge_n26, "n_tagged_ge40": vgm_edge_tagged40},
        "benchmarks": {
            "S1_unfiltered_allQ_2p2_3p0_w19p5": bench_unfilt,
            "S1_mip_clean_2p5_3p0_w12_Qlt200": bench_mip200,
            "S1_mip_tight_3p0_3p0_w12_Qlt180": bench_mip180,
            "S1_1hit_only_3p0_w12": bench_1hit,
            "S2_mip_dc25_z3_z6_Qlt200": bench_s2_mip,
        },
        "neg_tail_transfer": [
            {"t_ns": tneg, "r_u0": round(r0, 4), "e_u0": round(e0, 4), "r_u1": round(r1, 4), "e_u1": round(e1, 4)}
            for (tneg, r0, e0, r1, e1) in r_neg_list
        ],
    }
    (OUT_DIR / "t4_summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    # =========================================================================
    # 9. Generate 6 Diagnostic Plots in workbook/stage215_timing_t4/
    # =========================================================================
    # Fig 1: (u0, u1) vs (dt0, dt1) correlation + weighted conditional tail invariance in CR-Geom (Q<200 & allQ)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    per_rows_p = [r for r in indep_rows if r["region"] == "CR_Prompt_1p0ns" and r["period"] != "Run3_All"]
    xp = np.arange(len(per_rows_p))
    ax1.errorbar(xp - 0.1, [float(r["rho_dt0_dt1"]) for r in per_rows_p], yerr=[float(r["err_rho_dt"]) for r in per_rows_p],
                 fmt="s-", label=r"Common $t_{0,\mathrm{down}}$ ($\Delta t_0, \Delta t_1$)", color="tab:red")
    ax1.errorbar(xp + 0.1, [float(r["rho_u0_u1"]) for r in per_rows_p], yerr=[float(r["err_rho_u"]) for r in per_rows_p],
                 fmt="o-", label=r"Disjoint 4-Station ($u_0, u_1$)", color="tab:blue")
    ax1.axhline(0.0, color="gray", ls="--")
    ax1.set_xticks(xp)
    ax1.set_xticklabels([r["period"] for r in per_rows_p], rotation=25, ha="right", fontsize=9)
    ax1.set_ylabel(r"Pearson $\rho$ in $|t| < 1.0\ \mathrm{ns}$")
    ax1.set_title("CR-Prompt Two-Layer Correlation Across Run 3 (2022-2026)")
    ax1.legend(fontsize=9)
    ax1.grid(alpha=0.25)

    u0_labels = ["|u0|<0.5", "0.5<=|u0|<1", "1<=|u0|<1.5", "1.5<=|u0|<2.2", "u0>=2.2"]
    row_sums_q = np.maximum(u_cond_table_q200[:, 0] + u_cond_table_q200[:, 1], 1.0)
    # Use full row sums approximated from D + wings or exact total: note u_cond_table_q200[:,0] is |u1|<1.0 (>98% of row), total row sum is exact weighted count if we didn't drop (-1.5,-1.0) & (1.0,1.5) -> good normalization!
    for col_i, clab, col in [(1, "P(u1>1.5 | u0, Q<200)", "tab:green"), (2, "P(u1>2.2 | u0, Q<200)", "tab:orange"), (3, "P(u1>3.0 | u0, Q<200)", "tab:purple")]:
        probs = u_cond_table_q200[:, col_i] / row_sums_q
        errs = np.sqrt(np.maximum(u_cond_table_q200[:, col_i], 1.0)) / row_sums_q
        ax2.errorbar(np.arange(5), 100.0 * probs, yerr=100.0 * errs, fmt="o-", label=clab, color=col, capsize=3)
    ax2.set_yscale("log")
    ax2.set_xticks(np.arange(5))
    ax2.set_xticklabels(u0_labels, rotation=20, ha="right", fontsize=9)
    ax2.set_ylabel("Conditional Tail Rate [%] (Weighted CR-Geom Q<200)")
    ax2.set_title("Disjoint Conditional Tail Invariance (MIP Q<200, |t0|<2.5)")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.25)
    fig.suptitle("Stage T4: Zero-Covariance Disjoint 4-Station (u0, u1) Independence", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(OUT_DIR / "fig1_u0_u1_independence_and_cov.png", dpi=150)
    plt.close(fig)

    # Fig 2: ABCD closure in CR-Geom MIP Q<200, HiTheta, Negative SR, & 1-hit validation
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    cg_mip = [r for r in closure_rows if r["test_type"] == "CR_Geom_MIP_Qlt200" and r["observable"] == "decoupled_u0_u1"]
    cg_ht = [r for r in closure_rows if r["test_type"] == "CR_Geom_HiTheta" and r["observable"] == "decoupled_u0_u1"]
    srn_u = [r for r in closure_rows if r["test_type"] == "Kinematic_SR_NegMirror_MIP_Qlt200" and r["observable"] == "decoupled_u0_u1_neg"]
    x1 = np.arange(len(cg_mip))
    for dx, lst, lab, fmt, col in [
        (-0.18, cg_mip, "CR-Geom MIP Q<200 (+u0/u1)", "o", "tab:blue"),
        (0.0, cg_ht, "CR-Geom HiTheta (+u0/u1)", "^", "tab:green"),
        (0.18, srn_u, "Kinematic SR NegMirror (-u0/u1)", "s", "tab:red"),
    ]:
        ax1.errorbar(x1 + dx, [r["obs_over_pred"] for r in lst],
                     yerr=[r["obs_over_pred"] / math.sqrt(max(r["n_A_obs"], 1)) for r in lst],
                     fmt=fmt, label=lab, color=col, capsize=3)
    ax1.axhline(1.0, color="black", ls="--")
    ax1.axhspan(0.8, 1.2, color="gray", alpha=0.12)
    ax1.set_yscale("log")
    ax1.set_xticks(x1)
    ax1.set_xticklabels([r["slice"].replace("slice_", "").replace("cum_", ">") for r in cg_mip], rotation=35, ha="right", fontsize=8)
    ax1.set_ylabel("Observed / (ABCD + GENIE Predicted)")
    ax1.set_ylim(0.3, 15.0)
    ax1.set_title("Weighted Decoupled ABCD Closure (|t0_down|<2.5 ns)")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.25)

    oh0 = [r for r in closure_rows if r["test_type"] == "CR_Geom_1Hit_VN0"]
    oh1 = [r for r in closure_rows if r["test_type"] == "CR_Geom_1Hit_VN1"]
    x2 = np.arange(len(oh0))
    ax2.plot(x2, [r["n_A_obs"] for r in oh0], "o-", color="tab:blue", label="VN0 1-hit Obs (CR-Geom)")
    ax2.plot(x2, [r["n_A_tot_pred"] for r in oh0], "s--", color="tab:cyan", label="VN0 1-hit Pred (Prompt*Tail + GENIE)")
    ax2.plot(x2, [r["n_A_obs"] for r in oh1], "^-", color="tab:orange", label="VN1 1-hit Obs (CR-Geom)")
    ax2.plot(x2, [r["n_A_tot_pred"] for r in oh1], "v--", color="tab:red", label="VN1 1-hit Pred")
    ax2.set_yscale("log")
    ax2.set_xticks(x2)
    ax2.set_xticklabels([f"T1>{t:.1f}" for t in S1_T1_GRID], fontsize=9)
    ax2.set_ylabel("CR-Geom Delayed 1-Hit Events")
    ax2.set_title("Single-Layer Miss + Tail Closure (B2 Validation)")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.25)
    fig.suptitle("Stage T4: Weighted Orthogonal Sideband ABCD & 1-Hit Closure Validation", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(OUT_DIR / "fig2_abcd_closure_cr_geom_and_neg_sr.png", dpi=150)
    plt.close(fig)

    # Fig 3: Era-corrected SR radial 1-hit miss rate + Data B3 vs FLUKA suppression across Q cuts
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    v_sr2 = sum(data_hists[p]["h_sr_rvn_2hit"][0] for p in data_hists if "h_sr_rvn_2hit" in data_hists[p])
    ervn = next(iter(data_hists.values()))["h_sr_rvn_2hit"][1]
    crvn = 0.5 * (ervn[:-1] + ervn[1:])
    v_era1, v_raw1 = np.zeros_like(crvn), np.zeros_like(crvn)
    for per in PERIODS:
        if per not in data_hists:
            continue
        if "h_sr_rvn_1hit0_raw40" in data_hists[per]:
            v_raw1 += data_hists[per]["h_sr_rvn_1hit0_raw40"][0] + data_hists[per]["h_sr_rvn_1hit1_raw40"][0]
        if per in ("2025", "2026"):
            if "h_sr_rvn_1hit0_raw40" in data_hists[per]:
                v_era1 += data_hists[per]["h_sr_rvn_1hit0_raw40"][0] + data_hists[per]["h_sr_rvn_1hit1_raw40"][0]
        elif "h_sr_rvn_1hit0" in data_hists[per]:
            v_era1 += data_hists[per]["h_sr_rvn_1hit0"][0] + data_hists[per]["h_sr_rvn_1hit1"][0]
    m_rvn = crvn < 120.0
    den = np.maximum(v_sr2[m_rvn] + v_era1[m_rvn], 1.0)
    ax1.plot(crvn[m_rvn], 1e6 * v_era1[m_rvn] / den, "o-", label=f"Era-Clean 1-Hit (tot={int(np.sum(v_era1))})", color="tab:blue")
    ax1.plot(crvn[m_rvn], 1e6 * v_raw1[m_rvn] / np.maximum(v_sr2[m_rvn] + v_raw1[m_rvn], 1.0), "s--", label=f"All-Run3 raw40 1-Hit (tot={int(np.sum(v_raw1))})", color="tab:orange")
    ax1.axvline(115.0, color="gray", ls=":", label="Edge boundary 115 mm")
    ax1.set_xlabel("Track Radius at VetoNu [mm]")
    ax1.set_ylabel("Single-Layer Miss Rate [ppm = 10^-6]")
    ax1.set_title("Unblinded SR 1-Layer Penetrating-Muon Inefficiency (B2)")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.25)

    reg_show = [r for r in b3_b4_rows if r["regime"] in ("allQ_not0", "allQ_intime", "allQ_intime_w12", "Qlt200_intime_w12", "Qlt180_intime_w12") and r["t2_ns"] in (2.2, 2.5)]
    xr = np.arange(len(reg_show))
    ax2.bar(xr - 0.18, [max(r["b3_data_driven_sr"], 0.1) for r in reg_show], width=0.35, label="Data-Driven B3 (CR-Geom excess -> SR)", color="tab:green")
    ax2.bar(xr + 0.18, [max(r["fluka_sr_s1_yield"], 0.1) for r in reg_show], width=0.35, label="FLUKA MC S1 Zone B (335.92 fb^-1)", color="tab:red", alpha=0.75)
    ax2.set_yscale("log")
    ax2.set_xticks(xr)
    ax2.set_xticklabels([f"{r['regime']}\n({r['t2_ns']},{r['t1_ns']})" for r in reg_show], rotation=20, ha="right", fontsize=8)
    ax2.set_ylabel("Predicted Events in 335.92 fb^-1")
    ax2.set_title("B3 Shower/Out-of-Time Suppression Across Clean Cuts")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.25)
    fig.suptitle("Stage T4: Era-Consistent Single-Layer Miss (B2) & Shower Suppression (B3)", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(OUT_DIR / "fig3_single_layer_miss_and_edge_vn.png", dpi=150)
    plt.close(fig)

    # Fig 4: Width & Hi-Q (>200 pC) vs Width < 12 ns spectra in CR-Geom
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    v_wp = sum(data_hists[p]["h_geom_width_prompt"][0] for p in data_hists if "h_geom_width_prompt" in data_hists[p])
    v_wt = sum(data_hists[p]["h_geom_width_postail"][0] for p in data_hists if "h_geom_width_postail" in data_hists[p])
    ew = next(iter(data_hists.values()))["h_geom_width_prompt"][1]
    cw = 0.5 * (ew[:-1] + ew[1:])
    ax1.step(cw, v_wp / max(np.sum(v_wp), 1.0), where="mid", label="CR-Geom Prompt (|dt| <= 1.0 ns)", color="tab:blue")
    ax1.step(cw, v_wt / max(np.sum(v_wt), 1.0), where="mid", label="CR-Geom Pos Tail (dt > +1.5 ns)", color="tab:red")
    ax1.axvline(12.0, color="tab:green", ls="--", label="width < 12 ns")
    ax1.axvline(19.5, color="black", ls=":", label="width < 19.5 ns")
    ax1.set_yscale("log")
    ax1.set_xlabel("VetoNu Waveform Width [ns]")
    ax1.set_ylabel("Normalized Fraction per 0.25 ns Bin")
    ax1.set_title("Pulse Width in Prompt vs Positive Delay Tails (B3)")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.25)

    v_dt_all = sum(data_hists[p]["h_geom_dt0"][0] + data_hists[p]["h_geom_dt1"][0] for p in data_hists if "h_geom_dt0" in data_hists[p])
    v_dt_hiq = sum(data_hists[p]["h_geom_dt0_hiq"][0] + data_hists[p]["h_geom_dt1_hiq"][0] for p in data_hists if "h_geom_dt0_hiq" in data_hists[p])
    v_dt_w12 = sum(data_hists[p]["h_geom_dt0_w12"][0] + data_hists[p]["h_geom_dt1_w12"][0] for p in data_hists if "h_geom_dt0_w12" in data_hists[p])
    ed = next(iter(data_hists.values()))["h_geom_dt0"][1]
    cd = 0.5 * (ed[:-1] + ed[1:])
    md_p = (cd > -6.0) & (cd < 22.0)
    ax2.step(cd[md_p], v_dt_all[md_p] / max(np.sum(v_dt_all), 1.0), where="mid", label="CR-Geom All (w < 19.5)", color="tab:blue")
    ax2.step(cd[md_p], v_dt_hiq[md_p] / max(np.sum(v_dt_hiq), 1.0), where="mid", label="CR-Geom High Q (>200 pC)", color="tab:orange")
    ax2.step(cd[md_p], v_dt_w12[md_p] / max(np.sum(v_dt_w12), 1.0), where="mid", label="CR-Geom Width < 12 ns", color="tab:green")
    ax2.set_yscale("log")
    ax2.set_xlabel("VetoNu dt [ns]")
    ax2.set_ylabel("Normalized Distribution")
    ax2.set_title("CR-Geom Timing Spectrum: High-Q Shower Tail Dominance")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.25)
    fig.suptitle("Stage T4: Waveform Width Discrimination & High-Q Shower Tail (B3)", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(OUT_DIR / "fig4_width_and_backscatter_b3.png", dpi=150)
    plt.close(fig)

    # Fig 5: 5-mechanism background budget vs S1 threshold (MIP Q<200 & Q<180 vs All-Q)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    s1_q200_3 = sorted([r for r in budget_rows if r["strategy"] == "S1" and r["charge_mode"] == "red30_Qlt200" and r["wmax_ns"] == 12.0 and r["param2"] == 3.0], key=lambda x: x["param1"])
    x5 = [r["param1"] for r in s1_q200_3]
    for col_k, lab, col in [("B1_stoch_2hit", "B1 (2-hit ABCD)", "tab:blue"), ("B2_1hit_miss", "B2 (1-hit miss)", "tab:orange"),
                            ("B3_backscatter", "B3 (Shower excess)", "tab:green"), ("B4_grazing", "B4 (Edge/grazing)", "tab:purple"),
                            ("B5_accidental", "B5 (Accidental)", "tab:brown"), ("B_tot", "B_tot (Q2hit<200, w<12)", "black")]:
        ax1.plot(x5, [max(r[col_k], 1e-2) for r in s1_q200_3], "o-", label=lab, color=col, lw=2.2 if col_k == "B_tot" else 1.5)
    ax1.axhline(bench_mip200["S_recovered_335p9fb"], color="tab:red", ls=":", label=f"S_rec(Q2hit<200)={bench_mip200['S_recovered_335p9fb']:.1f}")
    ax1.set_yscale("log")
    ax1.set_xlabel("S1 T_2hit Threshold [ns] (T_1hit=3.0 ns, w<12 ns, |t0|<2.5 ns)")
    ax1.set_ylabel("Run 3 Total Events (335.92 fb^-1)")
    ax1.set_title("MIP-Clean (Q_2hit < 200 pC) 5-Component Background vs T_2hit")
    ax1.legend(fontsize=7.5)
    ax1.grid(alpha=0.25)

    for cm_lab, lab, col in [("red30_allQ", "All-Q (|t0|<2.5, w<12)", "tab:gray"),
                            ("red30_Qlt200", "Q_2hit < 200 (|t0|<2.5, w<12)", "tab:blue"),
                            ("red30_Qlt180", "Q_2hit < 180 (|t0|<2.5, w<12)", "tab:green"),
                            ("red30_Qlt150", "Q_2hit < 150 (|t0|<2.5, w<12)", "tab:purple")]:
        sub = sorted([r for r in budget_rows if r["strategy"] == "S1" and r["charge_mode"] == cm_lab and r["wmax_ns"] == 12.0 and r["param2"] == 3.0], key=lambda x: x["param1"])
        ax2.plot([r["param1"] for r in sub], [r["B_over_Srec_pct"] for r in sub], "o-", label=lab, color=col)
    ax2.axhline(bench_1hit["B_over_Srec_pct"], color="tab:red", ls="--", label=f"Pure 1-Hit Only ({bench_1hit['B_over_Srec_pct']:.1f}%)")
    ax2.axhline(100.0, color="black", ls=":", alpha=0.5, label="B_tot = S_rec (100%)")
    ax2.set_yscale("log")
    ax2.set_xlabel("S1 T_2hit Threshold [ns] (T_1hit=3.0 ns, w<12 ns)")
    ax2.set_ylabel("B_tot / S_recovered [%]")
    ax2.set_title("Zone-B Background-to-Signal Ratio Across Q_2hit Ceilings")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.25)
    fig.suptitle("Stage T4: 5-Mechanism Background Budget & H4 Regime Comparison (335.92 fb^-1)", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(OUT_DIR / "fig5_five_component_bkg_vs_threshold.png", dpi=150)
    plt.close(fig)

    # Fig 6: Period-by-period stability across all 7 eras
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    xp = np.arange(len(period_rows))
    plabs = [r["period"] for r in period_rows]
    ax1.plot(xp, [r["sr_prompt_per_fb"] for r in period_rows], "o-", label="CR-Prompt SR / fb^-1", color="tab:blue")
    ax1.plot(xp, [r["geom_prompt_per_fb"] * 3.0 for r in period_rows], "s--", label="CR-Geom Prompt / fb^-1 (x3)", color="tab:green")
    ax1.set_xticks(xp)
    ax1.set_xticklabels(plabs, rotation=25, ha="right", fontsize=9)
    ax1.set_ylabel("Prompt Rate Normalized to Lumi [events / fb^-1]")
    ax1.set_title("Run 3 Active-VetoNu Control-Region Stability (2022-2026)")
    ax1.legend(fontsize=9)
    ax1.grid(alpha=0.25)

    ax2.plot(xp, [r["B_tot_per_fb"] for r in period_rows], "o-", label="Predicted B_tot / fb^-1 (MIP Q<200)", color="black")
    ax2.plot(xp, [r["miss_1hit_rate_ppm"] for r in period_rows], "s--", label="Era-Clean 1-Hit Miss [ppm = 10^-6]", color="tab:orange")
    ax2.set_xticks(xp)
    ax2.set_xticklabels(plabs, rotation=25, ha="right", fontsize=9)
    ax2.set_ylabel("Predicted Bkg / fb^-1  or  Miss Rate [ppm]")
    ax2.set_title("Predicted Zone-B Background Density Stability Across 7 Eras")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.25)
    fig.suptitle("Stage T4: Multi-Year Background Stability Audit (2022-2026, 335.92 fb^-1)", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(OUT_DIR / "fig6_run3_period_bkg_stability.png", dpi=150)
    plt.close(fig)

    print(f"[T4] Finished in {time.perf_counter() - t_start:.2f}s. Results in {OUT_DIR}")
    for k_b, v_b in summary["benchmarks"].items():
        print(f"  {k_b:34s}: B_tot={v_b['B_tot']:.2f} +- {v_b['B_err']:.2f} (B1={v_b['B1_stoch_2hit']:.2f}, B2={v_b['B2_1hit_miss']:.2f}, B3={v_b['B3_backscatter']:.2f}, B4={v_b['B4_grazing']:.2f}, B5={v_b['B5_accidental']:.2f}) | S_rec={v_b['S_recovered_335p9fb']:.2f} ({v_b['B_over_Srec_pct']:.1f}%)")


if __name__ == "__main__":
    main()
