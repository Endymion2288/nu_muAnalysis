#!/usr/bin/env python3
"""Stage T3 (Stage 214): Backward-hadron VetoNu truth dissection & 5-Geant4-model study.

Processes the 191 HTCondor Stage T3 extraction shards covering all 69 GENIE runs
(3,297 PHYS files), verifies >99.9% HITS primary vertex matching, and executes:
  Task 1: Dissect VetoNuHits + TruthEvent species, kinematics, topology, and 100%
          anomaly/non-rescue accounting in Zone B (q_red >= 30 pC).
  Task 2: Audit downstream shower timing bias across non-saturated channels
          (V10..PS1) and freeze optimal t0_down estimator (AllValid vs TimingGeom
          vs Trimmed3Sigma).
  Task 3: Compare reduced_charge < 30 pC vs aux-free raw_charge < 40 pC + timing
          (readiness for 2025/p0013 and aux-free 2022-2023).
  Task 4: Evaluate S0, S1, S2 across 5 Geant4 physics lists x 3 geometries (H5),
          flux systematic envelopes, preliminary timing scale/resolution shifts,
          6D acceptance recovery (H1, H6), and ML F7_pz0_raw_v1 domain shift.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import uproot
import awkward as ak


REPO_ROOT = Path(__file__).resolve().parents[2]
CALIB_DIR = REPO_ROOT / "AnalysisZipFramework" / "config" / "timing_calib"
MANIFEST_PATH = CALIB_DIR / "run3_timing_manifest.json"
EOS_RUNS_DIR = "/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/timing_stage214/runs"
DEFAULT_OUT_DIR = REPO_ROOT / "workbook" / "stage214_timing_t3"

G4_CAT_NAMES = {
    0: "none",
    1: "proton",
    2: "pi+-",
    3: "K+-",
    4: "n_recoil_nuc",
    5: "gamma_to_e",
    6: "e_cascade",
    7: "mu+-",
    8: "unm_high_dEdx",
    9: "unm_low_dEdx",
    10: "other",
}

DOWN_CH_NAMES = ["Veto10", "Veto11", "Veto20", "Veto21", "Timing01", "Timing23", "Preshower0", "Preshower1"]

# Exact 10 ab^-1 (10,000 fb^-1) GENIE triplets matching run_MC_truth.sh + run3_timing_manifest tags
G4_MODEL_ORDER = [
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

FID_HIST_NAMES = ["h_fid_E_nu", "h_fid_pz_mu", "h_fid_y_inel", "h_fid_z_vtx", "h_fid_r_vtx", "h_fid_q_mu"]


def _list_eos_shards(eos_dir: str) -> list[str]:
    proc = subprocess.run(
        ["xrdfs", "eoshome-x.cern.ch", "ls", eos_dir],
        capture_output=True, text=True, check=True,
    )
    paths = sorted(p.strip() for p in proc.stdout.splitlines() if p.strip().endswith(".root"))
    return paths


def _copy_shard_to_tmp(args: tuple[str, str]) -> str:
    remote_path, tmp_dir = args
    dst = os.path.join(tmp_dir, os.path.basename(remote_path))
    if os.path.exists(remote_path) and os.path.getsize(remote_path) > 0:
        # Local EOS FUSE already synchronized
        return remote_path
    subprocess.run(
        ["xrdcp", "-f", "-s", f"root://eoshome-x.cern.ch/{remote_path}", dst],
        check=True,
    )
    return dst


def _read_one_shard(path: str) -> dict[str, Any]:
    with uproot.open(path) as f:
        rs = f["run_summary"].arrays(library="np")
        hists = {}
        for hname in FID_HIST_NAMES:
            vals, edges = f[hname].to_numpy()
            hists[hname] = (vals.astype(np.float64), edges.astype(np.float64))
        t = f["t3_events"]
        branches = list(t.keys())
        arr = t.arrays(branches, library="ak")
        ev = {b: ak.to_numpy(arr[b]) for b in branches}
    return {
        "path": path,
        "run_summary": {k: rs[k] for k in rs},
        "hists": hists,
        "events": ev,
    }


def load_all_shards(eos_dir: str, workers: int) -> tuple[dict[int, dict[str, Any]], dict[str, np.ndarray], dict[int, dict[str, tuple[np.ndarray, np.ndarray]]], float]:
    t0 = time.perf_counter()
    remote_paths = _list_eos_shards(eos_dir)
    if not remote_paths:
        raise RuntimeError(f"No ROOT shards found in {eos_dir}")

    # Check whether EOS FUSE sees every shard; stage missing ones via parallel xrdcp
    tmp_stage_dir = tempfile.mkdtemp(prefix="t3_stage214_cache_")
    try:
        copy_jobs = [(rp, tmp_stage_dir) for rp in remote_paths]
        local_paths: list[str] = []
        with ProcessPoolExecutor(max_workers=min(workers, 16)) as ex:
            local_paths = list(ex.map(_copy_shard_to_tmp, copy_jobs))

        run_summary: dict[int, dict[str, Any]] = {}
        run_hists: dict[int, dict[str, tuple[np.ndarray, np.ndarray]]] = {}
        chunks: list[dict[str, np.ndarray]] = []
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for shard in ex.map(_read_one_shard, local_paths):
                rs = shard["run_summary"]
                for i in range(len(rs["run"])):
                    r = int(rs["run"][i])
                    if r not in run_summary:
                        run_summary[r] = {k: int(rs[k][i]) for k in rs if k != "run"}
                        run_summary[r]["n_shards"] = 1
                    else:
                        for k in rs:
                            if k != "run":
                                run_summary[r][k] += int(rs[k][i])
                        run_summary[r]["n_shards"] += 1
                    if r not in run_hists:
                        run_hists[r] = {h: (v.copy(), e) for h, (v, e) in shard["hists"].items()}
                    else:
                        for h, (v, _) in shard["hists"].items():
                            run_hists[r][h][0][:] += v
                chunks.append(shard["events"])
    finally:
        shutil.rmtree(tmp_stage_dir, ignore_errors=True)

    # Concatenate event dictionaries
    keys = list(chunks[0].keys())
    events = {k: np.concatenate([c[k] for c in chunks], axis=0) for k in keys}
    wall_s = time.perf_counter() - t0
    return run_summary, events, run_hists, wall_s


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


def _core_stats(x: np.ndarray) -> dict[str, float]:
    m = np.isfinite(x)
    v = x[m].astype(np.float64)
    if len(v) == 0:
        return {"n": 0, "mean": float("nan"), "median": float("nan"), "std": float("nan"),
                "iqr_sig": float("nan"), "p05": float("nan"), "p10": float("nan"),
                "p25": float("nan"), "p75": float("nan"), "p90": float("nan"), "p95": float("nan")}
    qs = np.percentile(v, [5, 10, 25, 50, 75, 90, 95])
    return {
        "n": int(len(v)),
        "mean": float(np.mean(v)),
        "median": float(qs[3]),
        "std": float(np.std(v)),
        "iqr_sig": float((qs[4] - qs[2]) / 1.3489795),
        "p05": float(qs[0]),
        "p10": float(qs[1]),
        "p25": float(qs[2]),
        "p75": float(qs[4]),
        "p90": float(qs[5]),
        "p95": float(qs[6]),
    }


def evaluate_selection_masks(
    ev: dict[str, np.ndarray],
    mode: str = "Trimmed3Sigma",
    use_raw40: bool = False,
    t_2hit: float = 2.2,
    t_1hit: float = 3.0,
    t_max: float = 22.0,
    t_after_min: float = 32.0,
    chi2_max: float = 5.0,
    width_max: float = 19.5,
    dchi2_s2: float = 25.0,
    z_min_2hit_s2: float = 3.0,
    z_1hit_mip_s2: float = 6.0,
    z_1hit_nonmip_s2: float = 5.0,
    scale_shift_ns: float = 0.0,
    smear_scale: float = 1.0,
) -> dict[str, np.ndarray]:
    """Evaluate S0, S1, and S2 boolean masks cleanly for any downstream mode & charge definition."""
    if mode == "AllValid":
        dt = ev["vn_dt"].astype(np.float64)
        n_down = ev["n_down_used"]
        ndof_down = ev["ndof_down"]
        chi2_down = ev["chi2_down"]
        t0_down = ev["t0_down"]
        dchi2 = ev["delta_chi2_back"]
        z_comb = ev["vn_z_comb"]
    elif mode == "TimingGeom":
        dt = ev["vn_dt_tgeom"].astype(np.float64)
        n_down = ev["n_down_tgeom"]
        ndof_down = ev["ndof_down_tgeom"]
        chi2_down = ev["chi2_down_tgeom"]
        t0_down = ev["t0_down_tgeom"]
        dchi2 = ev["delta_chi2_back_tgeom"]
        z_comb = ev["vn_z_comb_tgeom"]
    elif mode == "Trimmed3Sigma":
        dt = ev["vn_dt_trim"].astype(np.float64)
        n_down = ev["n_down_trim"]
        ndof_down = ev["ndof_down_trim"]
        chi2_down = ev["chi2_down_trim"]
        t0_down = ev["t0_down_trim"]
        dchi2 = ev["delta_chi2_back_trim"]
        z_comb = ev["vn_z_comb_trim"]
    else:
        raise ValueError(f"Unknown downstream mode {mode}")

    # Apply optional timing scale & resolution-smearing systematic shifts around truth vn_t0_mc
    t0_mc = ev["vn_t0_mc"].astype(np.float64)
    if smear_scale != 1.0:
        valid_mc = np.isfinite(dt) & np.isfinite(t0_mc)
        dt = np.where(valid_mc, t0_mc + smear_scale * (dt - t0_mc), dt)
    if scale_shift_ns != 0.0:
        dt = dt + scale_shift_ns

    q_red = ev["vn_q_red"].astype(np.float64)
    q_raw = ev["vn_q_raw"].astype(np.float64)
    w = ev["vn_width"].astype(np.float64)
    v_ok = ev["vn_valid"].astype(bool)
    vn_sig = ev["vn_sigma"].astype(np.float64)
    sig_t0 = ev["sigma_t0_down"].astype(np.float64)

    if use_raw40:
        act = q_raw >= 40.0
    else:
        # Match framework reduced_charge (<30 pC) with raw<40 fallback if reduced invalid
        act = np.where(q_red >= 0.0, q_red >= 30.0, q_raw >= 40.0)

    n_act = act[:, 0].astype(np.int32) + act[:, 1].astype(np.int32)
    zone_a = n_act == 0
    zone_b = n_act > 0

    down_ok = (n_down >= 2) & np.isfinite(t0_down) & ((ndof_down <= 0) | ((chi2_down / np.maximum(ndof_down, 1)) < chi2_max))
    wave_ok = v_ok & np.isfinite(dt) & np.isfinite(w) & (w > 1.5) & (w < width_max)
    # Every active layer must satisfy wave_ok
    act_wave_ok = (~act[:, 0] | wave_ok[:, 0]) & (~act[:, 1] | wave_ok[:, 1])

    in_win_2 = (dt > t_2hit) & (dt < t_max)
    in_win_1 = (dt > t_1hit) & (dt < t_max)

    # S1: Zone B requires down_ok + all active layers wave_ok + timing window (2-layer vs 1-layer)
    s1_zoneb_2 = (n_act == 2) & down_ok & act_wave_ok & in_win_2[:, 0] & in_win_2[:, 1]
    s1_zoneb_10 = (n_act == 1) & act[:, 0] & down_ok & act_wave_ok & in_win_1[:, 0]
    s1_zoneb_11 = (n_act == 1) & act[:, 1] & down_ok & act_wave_ok & in_win_1[:, 1]
    s1_zoneb = s1_zoneb_2 | s1_zoneb_10 | s1_zoneb_11
    passed_s1 = zone_a | s1_zoneb

    # Extended raw40 check allowing pure late afterpulses (dt > t_after_min) when use_raw40
    in_ext_2 = in_win_2 | (dt > t_after_min)
    in_ext_1 = in_win_1 | (dt > t_after_min)
    s1_ext_zoneb = (
        ((n_act == 2) & down_ok & act_wave_ok & in_ext_2[:, 0] & in_ext_2[:, 1])
        | ((n_act == 1) & act[:, 0] & down_ok & act_wave_ok & in_ext_1[:, 0])
        | ((n_act == 1) & act[:, 1] & down_ok & act_wave_ok & in_ext_1[:, 1])
    )
    passed_s1_ext = zone_a | s1_ext_zoneb

    # S2: Charge-dependent pull / backward likelihood ratio
    # Use propagated downstream error; when Trimmed3Sigma removes outliers, scale conservatively (~0.14 ns floor)
    sig_dn = np.where(np.isfinite(sig_t0) & (sig_t0 > 0.0), np.maximum(sig_t0, 0.12 if mode != "AllValid" else 0.0), 0.14)[:, None]
    sig_comb_k = np.hypot(np.where(np.isfinite(vn_sig) & (vn_sig > 0.0), vn_sig, 0.55), sig_dn)
    pull = dt / sig_comb_k

    # Recompute dchi2 / z_comb cleanly when systematic variation (scale/smear) or raw40 is requested
    if use_raw40 and mode == "AllValid" and scale_shift_ns == 0.0 and smear_scale == 1.0:
        dchi2_use = ev["delta_chi2_back_raw40"].astype(np.float64)
    elif scale_shift_ns == 0.0 and smear_scale == 1.0 and not use_raw40:
        dchi2_use = dchi2.astype(np.float64)
    else:
        # Exact analytical 2-layer / 1-layer likelihood ratio using sig_comb_k (within 1% of C++ matrix inverse)
        inv0 = np.where(wave_ok[:, 0], 1.0 / (sig_comb_k[:, 0] ** 2), 0.0)
        inv1 = np.where(wave_ok[:, 1], 1.0 / (sig_comb_k[:, 1] ** 2), 0.0)
        chi_mu_2 = (np.where(wave_ok[:, 0], dt[:, 0] ** 2 * inv0, 0.0)
                    + np.where(wave_ok[:, 1], dt[:, 1] ** 2 * inv1, 0.0))
        num_t = np.where(wave_ok[:, 0], dt[:, 0] * inv0, 0.0) + np.where(wave_ok[:, 1], dt[:, 1] * inv1, 0.0)
        den_w = inv0 + inv1
        t_b = np.maximum(0.0, np.where(den_w > 0.0, num_t / np.maximum(den_w, 1e-12), 0.0))
        chi_back_2 = (np.where(wave_ok[:, 0], (dt[:, 0] - t_b) ** 2 * inv0, 0.0)
                      + np.where(wave_ok[:, 1], (dt[:, 1] - t_b) ** 2 * inv1, 0.0))
        dchi2_use = chi_mu_2 - chi_back_2

    in_mip0 = (q_raw[:, 0] >= 55.0) & (q_raw[:, 0] <= 130.0)
    in_mip1 = (q_raw[:, 1] >= 55.0) & (q_raw[:, 1] <= 130.0)
    thr_z0 = np.where(in_mip0, z_1hit_mip_s2, z_1hit_nonmip_s2)
    thr_z1 = np.where(in_mip1, z_1hit_mip_s2, z_1hit_nonmip_s2)

    s2_zoneb_2 = (
        (n_act == 2) & down_ok & act_wave_ok
        & (dt[:, 0] < t_max) & (dt[:, 1] < t_max)
        & np.isfinite(dchi2_use) & (dchi2_use > dchi2_s2)
        & (pull[:, 0] > z_min_2hit_s2) & (pull[:, 1] > z_min_2hit_s2)
    )
    s2_zoneb_10 = (n_act == 1) & act[:, 0] & down_ok & act_wave_ok & (dt[:, 0] < t_max) & (pull[:, 0] > thr_z0)
    s2_zoneb_11 = (n_act == 1) & act[:, 1] & down_ok & act_wave_ok & (dt[:, 1] < t_max) & (pull[:, 1] > thr_z1)
    s2_zoneb = s2_zoneb_2 | s2_zoneb_10 | s2_zoneb_11
    passed_s2 = zone_a | s2_zoneb

    return {
        "zone_a": zone_a,
        "zone_b": zone_b,
        "act": act,
        "n_act": n_act,
        "down_ok": down_ok,
        "wave_ok": wave_ok,
        "act_wave_ok": act_wave_ok,
        "dt": dt,
        "pull": pull,
        "dchi2": dchi2_use,
        "passed_s0": zone_a,
        "passed_s1": passed_s1,
        "passed_s1_ext": passed_s1_ext,
        "passed_s2": passed_s2,
    }


def task1_truth_dissection(ev: dict[str, np.ndarray], mode: str, out_dir: Path) -> dict[str, Any]:
    """Task 1: Dissect VetoNuHits + TruthEvent backward species, kinematics, topology & 100% anomaly classification."""
    nom_runs = np.array(
        list(GEOM_TRIPLETS["2022_2023"]["FTFP_BERT"])
        + list(GEOM_TRIPLETS["2024_noCaloNu"]["FTFP_BERT"])
        + list(GEOM_TRIPLETS["2024_CaloNu"]["FTFP_BERT"]),
        dtype=np.int32,
    )
    m_nom = np.isin(ev["run"], nom_runs)
    sel = evaluate_selection_masks(ev, mode=mode, use_raw40=False)

    # Dissect on Nominal FTFP_BERT 30 ab^-1 first, AND record all-69 runs cross-check
    results: dict[str, Any] = {}
    for scope_name, m_scope in [("nominal_ftfp_bert_30ab", m_nom), ("all_69_runs", np.ones(len(ev["run"]), dtype=bool))]:
        m_zb = m_scope & sel["zone_b"]
        n_sr = int(np.count_nonzero(m_scope))
        n_s0 = int(np.count_nonzero(m_scope & sel["passed_s0"]))
        n_zb = int(np.count_nonzero(m_zb))
        n_s1 = int(np.count_nonzero(m_scope & sel["passed_s1"]))
        n_s2 = int(np.count_nonzero(m_scope & sel["passed_s2"]))

        act_b = sel["act"][m_zb]
        topo_both = act_b[:, 0] & act_b[:, 1]
        topo_v1 = (~act_b[:, 0]) & act_b[:, 1]
        topo_v0 = act_b[:, 0] & (~act_b[:, 1])

        z_vtx = ev["truth_dec_z"][m_zb]
        n_fasernu = int(np.count_nonzero(z_vtx < -1850.0))
        n_lead = int(np.count_nonzero(z_vtx >= -1850.0))

        # Primary active layer: higher q_red when both active, else the single active layer
        q_red_b = ev["vn_q_red"][m_zb]
        prim_idx = np.where(topo_v0, 0, np.where(topo_v1, 1, np.where(q_red_b[:, 1] >= q_red_b[:, 0], 1, 0)))
        rows_b = np.arange(n_zb)
        prim_cat = ev["g4_dom_cat"][m_zb][rows_b, prim_idx]
        prim_ke = ev["g4_dom_ke_mev"][m_zb][rows_b, prim_idx]
        prim_cos = ev["g4_dom_cos_back"][m_zb][rows_b, prim_idx]
        prim_dedx = ev["g4_dedx"][m_zb][rows_b, prim_idx]
        prim_tew = ev["g4_t_ew"][m_zb][rows_b, prim_idx]
        prim_dt = sel["dt"][m_zb][rows_b, prim_idx]
        prim_w = ev["vn_width"][m_zb][rows_b, prim_idx]
        prim_nh = ev["g4_nhits"][m_zb][rows_b, prim_idx]
        denom_q = np.maximum(q_red_b[:, 0], 0.0) + np.maximum(q_red_b[:, 1], 0.0)
        denom_q_safe = np.where(denom_q > 0.0, denom_q, 1.0)
        aq = np.where(denom_q > 0.0, (np.maximum(q_red_b[:, 1], 0.0) - np.maximum(q_red_b[:, 0], 0.0)) / denom_q_safe, 0.0)

        species_rows = []
        s1_zb = sel["passed_s1"][m_zb]
        s2_zb = sel["passed_s2"][m_zb]
        for cat_id, cat_name in G4_CAT_NAMES.items():
            mc = prim_cat == cat_id
            cnt = int(np.count_nonzero(mc))
            if cnt == 0:
                continue
            ke_st = _core_stats(prim_ke[mc])
            cos_st = _core_stats(prim_cos[mc])
            dedx_st = _core_stats(prim_dedx[mc])
            dt_st = _core_stats(prim_dt[mc])
            species_rows.append({
                "scope": scope_name,
                "cat_id": cat_id,
                "species": cat_name,
                "count": cnt,
                "frac_zoneB_pct": 100.0 * cnt / max(n_zb, 1),
                "both_pct": 100.0 * int(np.count_nonzero(mc & topo_both)) / cnt,
                "vn1_only_pct": 100.0 * int(np.count_nonzero(mc & topo_v1)) / cnt,
                "vn0_only_pct": 100.0 * int(np.count_nonzero(mc & topo_v0)) / cnt,
                "s1_rescue_pct": 100.0 * int(np.count_nonzero(mc & s1_zb)) / cnt,
                "s2_rescue_pct": 100.0 * int(np.count_nonzero(mc & s2_zb)) / cnt,
                "ke_med_MeV": ke_st["median"],
                "cos_back_med": cos_st["median"],
                "dedx_med_MeV_mm": dedx_st["median"],
                "dt_med_ns": dt_st["median"],
            })

        # 100% mutually-exclusive anomaly accounting for ALL Zone B failures under S1
        fail = ~s1_zb
        n_fail = int(np.count_nonzero(fail))
        st_b = ev["vn_st"][m_zb]
        w_b = ev["vn_width"][m_zb]
        dt_b = sel["dt"][m_zb]
        vok_b = ev["vn_valid"][m_zb].astype(bool)
        nh_b = ev["g4_nhits"][m_zb]
        nd_b = ev["n_down_used"][m_zb] if mode == "AllValid" else (ev["n_down_tgeom"][m_zb] if mode == "TimingGeom" else ev["n_down_trim"][m_zb])
        down_ok_b = sel["down_ok"][m_zb]

        act_no_g4 = (~act_b[:, 0] | (nh_b[:, 0] == 0)) & (~act_b[:, 1] | (nh_b[:, 1] == 0))
        any_act_sat = (act_b[:, 0] & ((st_b[:, 0] & 4) != 0)) | (act_b[:, 1] & ((st_b[:, 1] & 4) != 0))
        any_act_cbfail = (act_b[:, 0] & (~vok_b[:, 0]) & ((st_b[:, 0] & 4) == 0)) | (act_b[:, 1] & (~vok_b[:, 1]) & ((st_b[:, 1] & 4) == 0))
        any_act_width = (act_b[:, 0] & vok_b[:, 0] & ((w_b[:, 0] >= 19.5) | (w_b[:, 0] <= 1.5))) | (act_b[:, 1] & vok_b[:, 1] & ((w_b[:, 1] >= 19.5) | (w_b[:, 1] <= 1.5)))

        # Timing threshold per active topology
        c_noise = fail & act_no_g4
        rem = fail & (~c_noise)
        c_down_miss = rem & (nd_b < 2)
        rem = rem & (~c_down_miss)
        c_down_chi2 = rem & (~down_ok_b)
        rem = rem & (~c_down_chi2)
        c_sat = rem & any_act_sat
        rem = rem & (~c_sat)
        c_cbfail = rem & any_act_cbfail
        rem = rem & (~c_cbfail)
        c_width = rem & any_act_width
        rem = rem & (~c_width)
        # Remaining failures must be dt <= threshold OR dt >= 22 ns on at least one active layer
        has_late = (act_b[:, 0] & (dt_b[:, 0] >= 22.0)) | (act_b[:, 1] & (dt_b[:, 1] >= 22.0))
        c_late = rem & has_late
        rem = rem & (~c_late)
        has_prompt_2 = topo_both & ((dt_b[:, 0] <= 2.2) | (dt_b[:, 1] <= 2.2))
        has_prompt_1 = (topo_v0 & (dt_b[:, 0] <= 3.0)) | (topo_v1 & (dt_b[:, 1] <= 3.0))
        c_prompt = rem & (has_prompt_2 | has_prompt_1)
        c_unexp = rem & (~c_prompt)

        anomaly_counts = {
            "total_zoneB_fail_S1": n_fail,
            "electronic_noise_no_g4": int(np.count_nonzero(c_noise)),
            "downstream_lt2_hits": int(np.count_nonzero(c_down_miss)),
            "downstream_chi2_ge_5": int(np.count_nonzero(c_down_chi2)),
            "active_digitizer_saturation": int(np.count_nonzero(c_sat)),
            "active_cb_fit_fail_nonsat": int(np.count_nonzero(c_cbfail)),
            "active_broad_width_doublepulse_ge19p5": int(np.count_nonzero(c_width)),
            "active_ultra_late_ge22ns": int(np.count_nonzero(c_late)),
            "active_prompt_or_small_delay": int(np.count_nonzero(c_prompt)),
            "unexplained": int(np.count_nonzero(c_unexp)),
        }
        assert anomaly_counts["unexplained"] == 0, f"Unexplained S1 Zone B failures: {anomaly_counts}"

        results[scope_name] = {
            "n_kin_sr": n_sr,
            "n_zoneA_s0": n_s0,
            "n_zoneB": n_zb,
            "zoneB_frac_of_sr_pct": 100.0 * n_zb / max(n_sr, 1),
            "n_s1": n_s1,
            "n_s2": n_s2,
            "s1_rescue_cnt": n_s1 - n_s0,
            "s1_rescue_pct_of_zoneB": 100.0 * (n_s1 - n_s0) / max(n_zb, 1),
            "s2_rescue_cnt": n_s2 - n_s0,
            "s2_rescue_pct_of_zoneB": 100.0 * (n_s2 - n_s0) / max(n_zb, 1),
            "topology": {
                "both_layers": int(np.count_nonzero(topo_both)),
                "vetonu1_only": int(np.count_nonzero(topo_v1)),
                "vetonu0_only": int(np.count_nonzero(topo_v0)),
            },
            "target_origin": {"FASERnu_box": n_fasernu, "Lead_block": n_lead},
            "z_vtx_stats": _core_stats(z_vtx),
            "dt_stats_both": _core_stats(prim_dt[topo_both]),
            "dt_stats_v1": _core_stats(prim_dt[topo_v1]),
            "dt_stats_v0": _core_stats(prim_dt[topo_v0]),
            "aq_stats_both": _core_stats(aq[topo_both]),
            "aq_stats_v1": _core_stats(aq[topo_v1]),
            "aq_stats_v0": _core_stats(aq[topo_v0]),
            "species_rows": species_rows,
            "anomaly_accounting_s1_fail": anomaly_counts,
        }

    # Write combined TSV
    all_species_rows = results["nominal_ftfp_bert_30ab"]["species_rows"] + results["all_69_runs"]["species_rows"]
    write_tsv(out_dir / "t3_truth_species.tsv", all_species_rows)
    return results


def task2_downstream_shower_audit(ev: dict[str, np.ndarray], out_dir: Path) -> dict[str, Any]:
    """Task 2: Audit non-saturated downstream shower timing bias and select optimal t0_down estimator."""
    tcal = ev["down_t_cal"].astype(np.float64)       # shape (N, 8)
    tunsm = ev["down_t_unsmear"].astype(np.float64)  # shape (N, 8)
    st = ev["down_st"]                               # 0 = good+aboveMIP+!sat
    calo_gev = ev["calo_total_E_EM"].astype(np.float64) / 1000.0
    ps1_q = ev["preshower1_raw_charge"].astype(np.float64)
    ncl0 = ev["nClusters0"].astype(np.float64)

    # Channel-by-channel bias across non-saturated good channels & Calo/Preshower quartiles
    ch_rows: list[dict[str, Any]] = []
    calo_bins = [(0.0, 10.0, "<10 GeV (MIP-like)"), (10.0, 100.0, "10-100 GeV"),
                 (100.0, 300.0, "100-300 GeV"), (300.0, 1e9, ">=300 GeV (shower)")]
    ps1_bins = [(0.0, 5.0, "PS1 <5 pC"), (5.0, 15.0, "PS1 5-15 pC"),
                (15.0, 50.0, "PS1 15-50 pC"), (50.0, 1e9, "PS1 >=50 pC")]

    for ci, cname in enumerate(DOWN_CH_NAMES):
        mg = (st[:, ci] == 0) & np.isfinite(tunsm[:, ci]) & np.isfinite(tcal[:, ci])
        n_total = len(mg)
        n_good = int(np.count_nonzero(mg))
        n_sat = int(np.count_nonzero(st[:, ci] == 2))
        s_un = _core_stats(tunsm[mg, ci])
        s_cal = _core_stats(tcal[mg, ci])
        tail_gt05 = float(np.mean(tunsm[mg, ci] > 0.5)) * 100.0 if n_good else float("nan")
        tail_gt10 = float(np.mean(tunsm[mg, ci] > 1.0)) * 100.0 if n_good else float("nan")
        ch_rows.append({
            "channel": cname,
            "slice": "all_good",
            "n_good": n_good,
            "good_pct": 100.0 * n_good / max(n_total, 1),
            "sat_pct": 100.0 * n_sat / max(n_total, 1),
            "unsmear_mean_ns": s_un["mean"],
            "unsmear_med_ns": s_un["median"],
            "unsmear_p90_ns": s_un["p90"],
            "unsmear_p95_ns": s_un["p95"],
            "unsmear_gt05ns_pct": tail_gt05,
            "unsmear_gt10ns_pct": tail_gt10,
            "smeared_mean_ns": s_cal["mean"],
            "smeared_std_ns": s_cal["std"],
        })
        for lo, hi, lbl in calo_bins:
            mb = mg & (calo_gev >= lo) & (calo_gev < hi)
            nb = int(np.count_nonzero(mb))
            if nb >= 20:
                sb = _core_stats(tunsm[mb, ci])
                ch_rows.append({
                    "channel": cname, "slice": f"Calo_{lbl}", "n_good": nb,
                    "good_pct": 100.0 * nb / max(n_good, 1), "sat_pct": float("nan"),
                    "unsmear_mean_ns": sb["mean"], "unsmear_med_ns": sb["median"],
                    "unsmear_p90_ns": sb["p90"], "unsmear_p95_ns": sb["p95"],
                    "unsmear_gt05ns_pct": float(np.mean(tunsm[mb, ci] > 0.5)) * 100.0,
                    "unsmear_gt10ns_pct": float(np.mean(tunsm[mb, ci] > 1.0)) * 100.0,
                    "smeared_mean_ns": _core_stats(tcal[mb, ci])["mean"],
                    "smeared_std_ns": _core_stats(tcal[mb, ci])["std"],
                })
        for lo, hi, lbl in ps1_bins:
            mb = mg & (ps1_q >= lo) & (ps1_q < hi)
            nb = int(np.count_nonzero(mb))
            if nb >= 20:
                sb = _core_stats(tunsm[mb, ci])
                ch_rows.append({
                    "channel": cname, "slice": f"PS1_{lbl}", "n_good": nb,
                    "good_pct": 100.0 * nb / max(n_good, 1), "sat_pct": float("nan"),
                    "unsmear_mean_ns": sb["mean"], "unsmear_med_ns": sb["median"],
                    "unsmear_p90_ns": sb["p90"], "unsmear_p95_ns": sb["p95"],
                    "unsmear_gt05ns_pct": float(np.mean(tunsm[mb, ci] > 0.5)) * 100.0,
                    "unsmear_gt10ns_pct": float(np.mean(tunsm[mb, ci] > 1.0)) * 100.0,
                    "smeared_mean_ns": _core_stats(tcal[mb, ci])["mean"],
                    "smeared_std_ns": _core_stats(tcal[mb, ci])["std"],
                })

    write_tsv(out_dir / "t3_downstream_channel_bias.tsv", ch_rows)

    # Compare the 3 t0_down estimators on all SR events and on Zone B specifically
    mode_rows: list[dict[str, Any]] = []
    mode_summary: dict[str, Any] = {}
    for mode in ["AllValid", "TimingGeom", "Trimmed3Sigma"]:
        sel = evaluate_selection_masks(ev, mode=mode, use_raw40=False)
        if mode == "AllValid":
            t0 = ev["t0_down"].astype(np.float64)
            nd = ev["n_down_used"]
            chi2 = ev["chi2_down"].astype(np.float64)
            ndof = ev["ndof_down"]
        elif mode == "TimingGeom":
            t0 = ev["t0_down_tgeom"].astype(np.float64)
            nd = ev["n_down_tgeom"]
            chi2 = ev["chi2_down_tgeom"].astype(np.float64)
            ndof = ev["ndof_down_tgeom"]
        else:
            t0 = ev["t0_down_trim"].astype(np.float64)
            nd = ev["n_down_trim"]
            chi2 = ev["chi2_down_trim"].astype(np.float64)
            ndof = ev["ndof_down_trim"]

        valid = np.isfinite(t0) & (nd >= 2)
        chi_ratio = chi2 / np.maximum(ndof, 1)
        chi_ok3 = valid & ((ndof <= 0) | (chi_ratio < 3.0))
        chi_ok5 = valid & ((ndof <= 0) | (chi_ratio < 5.0))
        st_t0 = _core_stats(t0[valid])
        st_chi = _core_stats(t0[chi_ok5])
        gt05 = float(np.mean(np.abs(t0[valid]) > 0.5)) * 100.0
        gt10 = float(np.mean(np.abs(t0[valid]) > 1.0)) * 100.0
        gt05_ok = float(np.mean(np.abs(t0[chi_ok5]) > 0.5)) * 100.0

        # Check VetoNu residual bias vs truth vn_t0_mc on Zone B valid active layers
        act = sel["act"]
        vok = sel["wave_ok"] & act & np.isfinite(ev["vn_t0_mc"])
        resid = (sel["dt"] - ev["vn_t0_mc"])[vok]
        st_res = _core_stats(resid)

        n_sr = len(t0)
        n_zb = int(np.count_nonzero(sel["zone_b"]))
        n_s0 = int(np.count_nonzero(sel["passed_s0"]))
        n_s1 = int(np.count_nonzero(sel["passed_s1"]))
        n_s2 = int(np.count_nonzero(sel["passed_s2"]))
        info = {
            "mode": mode,
            "n_sr": n_sr,
            "cov_ge2_pct": 100.0 * int(np.count_nonzero(valid)) / max(n_sr, 1),
            "chi2_lt3_pct": 100.0 * int(np.count_nonzero(chi_ok3)) / max(n_sr, 1),
            "chi2_lt5_pct": 100.0 * int(np.count_nonzero(chi_ok5)) / max(n_sr, 1),
            "t0_mean_ns": st_t0["mean"],
            "t0_median_ns": st_t0["median"],
            "t0_std_ns": st_t0["std"],
            "t0_iqr_sig_ns": st_t0["iqr_sig"],
            "t0_chiok5_mean_ns": st_chi["mean"],
            "t0_chiok5_std_ns": st_chi["std"],
            "abs_t0_gt05ns_pct": gt05,
            "abs_t0_gt10ns_pct": gt10,
            "abs_t0_gt05ns_chiok5_pct": gt05_ok,
            "vn_resid_mean_ns": st_res["mean"],
            "vn_resid_std_ns": st_res["std"],
            "s1_rescue_pct_zoneB": 100.0 * (n_s1 - n_s0) / max(n_zb, 1),
            "s2_rescue_pct_zoneB": 100.0 * (n_s2 - n_s0) / max(n_zb, 1),
        }
        mode_rows.append(info)
        mode_summary[mode] = info

    write_tsv(out_dir / "t3_downstream_modes.tsv", mode_rows)

    # Unbiased selection: require >=99.8% coverage, then minimize unconditional t0 RMS & maximize chi2<5 pass rate
    best_mode = min(
        ["AllValid", "TimingGeom", "Trimmed3Sigma"],
        key=lambda m: (
            mode_summary[m]["cov_ge2_pct"] < 99.8,
            mode_summary[m]["t0_std_ns"],
            -mode_summary[m]["chi2_lt5_pct"],
        ),
    )
    return {
        "winner": best_mode,
        "modes": mode_summary,
        "channel_summary_all_good": [r for r in ch_rows if r["slice"] == "all_good"],
        "channel_rows_count": len(ch_rows),
    }


def _geom_runs_list(geom: str) -> list[int]:
    runs = set()
    for triplet in GEOM_TRIPLETS[geom].values():
        runs.update(triplet)
    for triplet in FLUX_VARIANTS[geom].values():
        runs.update(triplet)
    return sorted(runs)


def task3_and_task4_evaluation(
    run_summary: dict[int, dict[str, Any]],
    ev: dict[str, np.ndarray],
    run_hists: dict[int, dict[str, tuple[np.ndarray, np.ndarray]]],
    winner_mode: str,
    lumi_info: dict[str, float],
    out_dir: Path,
) -> dict[str, Any]:
    """Tasks 3 & 4: raw40 vs red30 parity, 5-G4-model H5 evaluation, flux envelope, 6D acceptance & ML domain shift."""
    sel_red = evaluate_selection_masks(ev, mode=winner_mode, use_raw40=False)
    sel_raw = evaluate_selection_masks(ev, mode=winner_mode, use_raw40=True)
    # Preliminary timing systematics (scale +-0.15 ns, smearing +-15%)
    sel_scale_p = evaluate_selection_masks(ev, mode=winner_mode, use_raw40=False, scale_shift_ns=+0.15)
    sel_scale_m = evaluate_selection_masks(ev, mode=winner_mode, use_raw40=False, scale_shift_ns=-0.15)
    sel_smear_p = evaluate_selection_masks(ev, mode=winner_mode, use_raw40=False, smear_scale=1.15)
    sel_smear_m = evaluate_selection_masks(ev, mode=winner_mode, use_raw40=False, smear_scale=0.85)

    # Helper to aggregate counts over a run triplet
    run_arr = ev["run"]
    all_runs_idx: dict[int, np.ndarray] = {r: (run_arr == r) for r in run_summary}

    def eval_triplet(triplet: tuple[int, int, int]) -> dict[str, Any]:
        idx = np.zeros(len(run_arr), dtype=bool)
        n_gen = 0
        n_fid = 0
        n_sr = 0
        n_hits = 0
        for r in triplet:
            if r not in run_summary:
                raise KeyError(f"Missing run {r} in run_summary")
            rs = run_summary[r]
            n_gen += rs["n_gen"]
            n_fid += rs["n_fid_pz100"]
            n_sr += rs["n_kin_sr"]
            n_hits += rs["n_hits_matched"]
            idx |= all_runs_idx[r]

        n_s0_red = int(np.count_nonzero(sel_red["passed_s0"][idx]))
        n_s1_red = int(np.count_nonzero(sel_red["passed_s1"][idx]))
        n_s2_red = int(np.count_nonzero(sel_red["passed_s2"][idx]))
        n_s0_raw = int(np.count_nonzero(sel_raw["passed_s0"][idx]))
        n_s1_raw = int(np.count_nonzero(sel_raw["passed_s1"][idx]))
        n_s1_raw_ext = int(np.count_nonzero(sel_raw["passed_s1_ext"][idx]))
        n_s2_raw = int(np.count_nonzero(sel_raw["passed_s2"][idx]))

        n_zb_red = n_sr - n_s0_red
        n_zb_raw = n_sr - n_s0_raw
        eff_fid = lambda n: (n / n_fid) if n_fid > 0 else 0.0
        eff_vn = lambda n: (n / n_sr) if n_sr > 0 else 0.0
        eff_err = lambda n: math.sqrt(max(n * (1.0 - n / max(n_fid, 1)), 0.0)) / max(n_fid, 1)

        # Late non-afterpulse vs afterpulse-like >22 ns in raw40
        m_s0red_not_raw = idx & sel_red["passed_s0"] & (~sel_raw["passed_s0"])
        n_extra_raw_loss = int(np.count_nonzero(m_s0red_not_raw))
        n_extra_rescued_win22 = int(np.count_nonzero(m_s0red_not_raw & sel_raw["passed_s1"]))
        n_extra_rescued_ext = int(np.count_nonzero(m_s0red_not_raw & sel_raw["passed_s1_ext"]))

        return {
            "runs": "-".join(str(r) for r in triplet),
            "n_gen": n_gen,
            "n_fid": n_fid,
            "n_sr": n_sr,
            "n_hits": n_hits,
            "n_s0_red": n_s0_red,
            "n_s1_red": n_s1_red,
            "n_s2_red": n_s2_red,
            "n_s0_raw": n_s0_raw,
            "n_s1_raw": n_s1_raw,
            "n_s1_raw_ext": n_s1_raw_ext,
            "n_s2_raw": n_s2_raw,
            "eff_sr": eff_fid(n_sr),
            "eff_s0_red": eff_fid(n_s0_red),
            "eff_s0_red_err": eff_err(n_s0_red),
            "eff_s1_red": eff_fid(n_s1_red),
            "eff_s1_red_err": eff_err(n_s1_red),
            "eff_s2_red": eff_fid(n_s2_red),
            "eff_s2_red_err": eff_err(n_s2_red),
            "eff_vn_sr": eff_vn(n_sr),
            "eff_vn_s0_red": eff_vn(n_s0_red),
            "eff_vn_s1_red": eff_vn(n_s1_red),
            "eff_vn_s2_red": eff_vn(n_s2_red),
            "eff_vn_s0_raw": eff_vn(n_s0_raw),
            "eff_vn_s1_raw": eff_vn(n_s1_raw),
            "eff_vn_s1_raw_ext": eff_vn(n_s1_raw_ext),
            "eff_vn_s2_raw": eff_vn(n_s2_raw),
            "eff_s0_raw": eff_fid(n_s0_raw),
            "eff_s1_raw": eff_fid(n_s1_raw),
            "eff_s1_raw_ext": eff_fid(n_s1_raw_ext),
            "eff_s2_raw": eff_fid(n_s2_raw),
            "s1_rescue_pct": 100.0 * (n_s1_red - n_s0_red) / max(n_zb_red, 1),
            "s2_rescue_pct": 100.0 * (n_s2_red - n_s0_red) / max(n_zb_red, 1),
            "s1_gain_vs_s0_pct": 100.0 * (n_s1_red - n_s0_red) / max(n_s0_red, 1),
            "s2_gain_vs_s0_pct": 100.0 * (n_s2_red - n_s0_red) / max(n_s0_red, 1),
            "raw40_extra_loss": n_extra_raw_loss,
            "raw40_extra_rescued_win22": n_extra_rescued_win22,
            "raw40_extra_rescued_ext": n_extra_rescued_ext,
            "s1_raw_vs_red_rel_diff_pct": 100.0 * (n_s1_raw - n_s1_red) / max(n_s1_red, 1),
            "s1_raw_ext_vs_red_rel_diff_pct": 100.0 * (n_s1_raw_ext - n_s1_red) / max(n_s1_red, 1),
            "s2_raw_vs_red_rel_diff_pct": 100.0 * (n_s2_raw - n_s2_red) / max(n_s2_red, 1),
            "n_s1_scale_p": int(np.count_nonzero(sel_scale_p["passed_s1"][idx])),
            "n_s1_scale_m": int(np.count_nonzero(sel_scale_m["passed_s1"][idx])),
            "n_s2_scale_p": int(np.count_nonzero(sel_scale_p["passed_s2"][idx])),
            "n_s2_scale_m": int(np.count_nonzero(sel_scale_m["passed_s2"][idx])),
            "n_s1_smear_p": int(np.count_nonzero(sel_smear_p["passed_s1"][idx])),
            "n_s1_smear_m": int(np.count_nonzero(sel_smear_m["passed_s1"][idx])),
            "n_s2_smear_p": int(np.count_nonzero(sel_smear_p["passed_s2"][idx])),
            "n_s2_smear_m": int(np.count_nonzero(sel_smear_m["passed_s2"][idx])),
        }

    # 15 G4 models table
    g4_rows: list[dict[str, Any]] = []
    g4_spread_rows: list[dict[str, Any]] = []
    geom_lumi_run3 = {
        "2022_2023": lumi_info["L_2022_2023_fb"],
        "2024_noCaloNu": lumi_info["L_2024_2026_ord_fb"],
        "2024_CaloNu": lumi_info["L_2024_CaloNu_fb"],
    }
    geom_lumi_2224 = {
        "2022_2023": lumi_info["L_2022_2023_fb"],
        "2024_noCaloNu": lumi_info["L_2024_noCaloNu_fb"],
        "2024_CaloNu": lumi_info["L_2024_CaloNu_fb"],
    }

    for geom, models in GEOM_TRIPLETS.items():
        lumi_r3 = geom_lumi_run3[geom]
        m_res: dict[str, dict[str, Any]] = {}
        for g4_name in G4_MODEL_ORDER:
            res = eval_triplet(models[g4_name])
            m_res[g4_name] = res
            scale = lumi_r3 / 10000.0
            row = {"geometry": geom, "g4_model": g4_name, "lumi_run3_fb": lumi_r3}
            row.update(res)
            row["yield_run3_s0"] = res["n_s0_red"] * scale
            row["yield_run3_s1"] = res["n_s1_red"] * scale
            row["yield_run3_s2"] = res["n_s2_red"] * scale
            g4_rows.append(row)

        # Compute H5 spreads across the 5 Geant4 models (both fiducial and conditional VetoNu N_sel/N_sr)
        for strat_key, eff_key, vn_key, n_key in [
            ("SR_preVetoNu", "eff_sr", "eff_vn_sr", "n_sr"),
            ("S0_red30", "eff_s0_red", "eff_vn_s0_red", "n_s0_red"),
            ("S0_raw40", "eff_s0_raw", "eff_vn_s0_raw", "n_s0_raw"),
            ("S1_timing", "eff_s1_red", "eff_vn_s1_red", "n_s1_red"),
            ("S2_pull_chi2", "eff_s2_red", "eff_vn_s2_red", "n_s2_red"),
            ("S1_raw40_timing", "eff_s1_raw", "eff_vn_s1_raw", "n_s1_raw"),
            ("S1_raw40_ext", "eff_s1_raw_ext", "eff_vn_s1_raw_ext", "n_s1_raw_ext"),
        ]:
            vals = np.array([m_res[m][eff_key] for m in G4_MODEL_ORDER], dtype=np.float64)
            vns = np.array([m_res[m][vn_key] for m in G4_MODEL_ORDER], dtype=np.float64)
            y10 = np.array([m_res[m][n_key] for m in G4_MODEL_ORDER], dtype=np.float64)
            nom_e = m_res["FTFP_BERT"][eff_key]
            nom_vn = m_res["FTFP_BERT"][vn_key]
            nom_y = float(m_res["FTFP_BERT"][n_key])
            g4_spread_rows.append({
                "geometry": geom,
                "strategy": strat_key,
                "eff_FTFP_BERT_pct": 100.0 * nom_e,
                "eff_min_pct": 100.0 * float(np.min(vals)),
                "eff_max_pct": 100.0 * float(np.max(vals)),
                "rel_envelope_pct": 100.0 * float(np.max(vals) - np.min(vals)) / max(nom_e, 1e-12),
                "rel_rms_pct": 100.0 * float(np.std(vals)) / max(float(np.mean(vals)), 1e-12),
                "cond_vn_FTFP_BERT_pct": 100.0 * nom_vn,
                "cond_vn_rel_envelope_pct": 100.0 * float(np.max(vns) - np.min(vns)) / max(nom_vn, 1e-12),
                "cond_vn_rel_rms_pct": 100.0 * float(np.std(vns)) / max(float(np.mean(vns)), 1e-12),
                "yield10ab_FTFP_BERT": int(nom_y),
                "yield10ab_rel_envelope_pct": 100.0 * float(np.max(y10) - np.min(y10)) / max(nom_y, 1.0),
            })

        if geom == "2024_CaloNu":
            # Apples-to-apples 4 master_dev models sharing identical caloNu EVNT & EnableEmulsion=True geometry
            m4 = G4_MODEL_ORDER[1:]
            for strat_key, eff_key, vn_key, n_key in [
                ("SR_preVetoNu", "eff_sr", "eff_vn_sr", "n_sr"),
                ("S0_red30", "eff_s0_red", "eff_vn_s0_red", "n_s0_red"),
                ("S0_raw40", "eff_s0_raw", "eff_vn_s0_raw", "n_s0_raw"),
                ("S1_timing", "eff_s1_red", "eff_vn_s1_red", "n_s1_red"),
                ("S2_pull_chi2", "eff_s2_red", "eff_vn_s2_red", "n_s2_red"),
                ("S1_raw40_timing", "eff_s1_raw", "eff_vn_s1_raw", "n_s1_raw"),
                ("S1_raw40_ext", "eff_s1_raw_ext", "eff_vn_s1_raw_ext", "n_s1_raw_ext"),
            ]:
                vals = np.array([m_res[m][eff_key] for m in m4], dtype=np.float64)
                vns = np.array([m_res[m][vn_key] for m in m4], dtype=np.float64)
                y10 = np.array([m_res[m][n_key] for m in m4], dtype=np.float64)
                ref_e = m_res["FTF_BIC"][eff_key]
                ref_vn = m_res["FTF_BIC"][vn_key]
                ref_y = float(m_res["FTF_BIC"][n_key])
                g4_spread_rows.append({
                    "geometry": "2024_CaloNu_master_dev_4models",
                    "strategy": strat_key,
                    "eff_FTFP_BERT_pct": 100.0 * ref_e,
                    "eff_min_pct": 100.0 * float(np.min(vals)),
                    "eff_max_pct": 100.0 * float(np.max(vals)),
                    "rel_envelope_pct": 100.0 * float(np.max(vals) - np.min(vals)) / max(ref_e, 1e-12),
                    "rel_rms_pct": 100.0 * float(np.std(vals)) / max(float(np.mean(vals)), 1e-12),
                    "cond_vn_FTFP_BERT_pct": 100.0 * ref_vn,
                    "cond_vn_rel_envelope_pct": 100.0 * float(np.max(vns) - np.min(vns)) / max(ref_vn, 1e-12),
                    "cond_vn_rel_rms_pct": 100.0 * float(np.std(vns)) / max(float(np.mean(vns)), 1e-12),
                    "yield10ab_FTFP_BERT": int(ref_y),
                    "yield10ab_rel_envelope_pct": 100.0 * float(np.max(y10) - np.min(y10)) / max(ref_y, 1.0),
                })

    # Combined full Run 3 (335.92 fb^-1) and 2022-2024 (186.18 fb^-1) lumi-weighted efficiency & yields per G4 model
    comb_eff_by_model: dict[str, dict[str, list[float]]] = {m: {"fid": [], "sr": [], "s0": [], "s1": [], "s2": [], "s0_raw": [], "s1_raw": [], "s1_raw_ext": [], "s2_raw": []} for m in G4_MODEL_ORDER}
    for row in g4_rows:
        m = row["g4_model"]
        sc = row["lumi_run3_fb"] / 10000.0
        comb_eff_by_model[m]["fid"].append(row["n_fid"] * sc)
        comb_eff_by_model[m]["sr"].append(row["n_sr"] * sc)
        comb_eff_by_model[m]["s0"].append(row["n_s0_red"] * sc)
        comb_eff_by_model[m]["s1"].append(row["n_s1_red"] * sc)
        comb_eff_by_model[m]["s2"].append(row["n_s2_red"] * sc)
        comb_eff_by_model[m]["s0_raw"].append(row["n_s0_raw"] * sc)
        comb_eff_by_model[m]["s1_raw"].append(row["n_s1_raw"] * sc)
        comb_eff_by_model[m]["s1_raw_ext"].append(row["n_s1_raw_ext"] * sc)
        comb_eff_by_model[m]["s2_raw"].append(row["n_s2_raw"] * sc)

    for strat_key, k in [
        ("SR_preVetoNu", "sr"), ("S0_red30", "s0"), ("S0_raw40", "s0_raw"),
        ("S1_timing", "s1"), ("S2_pull_chi2", "s2"),
        ("S1_raw40_timing", "s1_raw"), ("S1_raw40_ext", "s1_raw_ext"),
    ]:
        vals = np.array([sum(comb_eff_by_model[m][k]) / sum(comb_eff_by_model[m]["fid"]) for m in G4_MODEL_ORDER])
        vns = np.array([sum(comb_eff_by_model[m][k]) / sum(comb_eff_by_model[m]["sr"]) for m in G4_MODEL_ORDER])
        ys = np.array([sum(comb_eff_by_model[m][k]) for m in G4_MODEL_ORDER])
        g4_spread_rows.append({
            "geometry": "Run3_Combined_335.92fb",
            "strategy": strat_key,
            "eff_FTFP_BERT_pct": 100.0 * float(vals[0]),
            "eff_min_pct": 100.0 * float(np.min(vals)),
            "eff_max_pct": 100.0 * float(np.max(vals)),
            "rel_envelope_pct": 100.0 * float(np.max(vals) - np.min(vals)) / max(float(vals[0]), 1e-12),
            "rel_rms_pct": 100.0 * float(np.std(vals)) / max(float(np.mean(vals)), 1e-12),
            "cond_vn_FTFP_BERT_pct": 100.0 * float(vns[0]),
            "cond_vn_rel_envelope_pct": 100.0 * float(np.max(vns) - np.min(vns)) / max(float(vns[0]), 1e-12),
            "cond_vn_rel_rms_pct": 100.0 * float(np.std(vns)) / max(float(np.mean(vns)), 1e-12),
            "yield10ab_FTFP_BERT": round(float(ys[0]), 2),
            "yield10ab_rel_envelope_pct": 100.0 * float(np.max(ys) - np.min(ys)) / max(float(ys[0]), 1e-9),
        })

    # 2022-2024 combined yields table for nominal FTFP_BERT (both 186.18 fb^-1 and 335.92 fb^-1)
    run3_yield_rows = []
    for geom in ["2022_2023", "2024_noCaloNu", "2024_CaloNu"]:
        res = eval_triplet(GEOM_TRIPLETS[geom]["FTFP_BERT"])
        for tag, lumi_fb in [("Run3_335.92fb", geom_lumi_run3[geom]), ("Run22_24_186.18fb", geom_lumi_2224[geom]), ("10ab", 10000.0)]:
            sc = lumi_fb / 10000.0
            run3_yield_rows.append({
                "period_scope": tag,
                "geometry": geom,
                "lumi_fb": lumi_fb,
                "n_fid": res["n_fid"] * sc,
                "n_sr": res["n_sr"] * sc,
                "n_s0_red30": res["n_s0_red"] * sc,
                "n_s0_red30_mcstat": math.sqrt(res["n_s0_red"]) * sc,
                "n_s1": res["n_s1_red"] * sc,
                "n_s1_mcstat": math.sqrt(res["n_s1_red"]) * sc,
                "n_s2": res["n_s2_red"] * sc,
                "n_s2_mcstat": math.sqrt(res["n_s2_red"]) * sc,
                "gain_s1_over_s0": (res["n_s1_red"] - res["n_s0_red"]) * sc,
                "gain_s2_over_s0": (res["n_s2_red"] - res["n_s0_red"]) * sc,
            })

    # Flux variation envelope
    flux_rows = []
    for geom, variants in FLUX_VARIANTS.items():
        for fname, triplet in variants.items():
            res = eval_triplet(triplet)
            flux_rows.append({
                "geometry": geom, "flux_variant": fname, "runs": res["runs"],
                "n_fid": res["n_fid"], "n_s0_red": res["n_s0_red"],
                "n_s1_red": res["n_s1_red"], "n_s2_red": res["n_s2_red"],
                "eff_s0_pct": 100.0 * res["eff_s0_red"],
                "eff_s1_pct": 100.0 * res["eff_s1_red"],
                "eff_s2_pct": 100.0 * res["eff_s2_red"],
                "s1_gain_vs_s0_pct": res["s1_gain_vs_s0_pct"],
            })

    # Task 3 summary TSV
    raw_vs_red_rows = [
        {
            "geometry": r["geometry"],
            "g4_model": r["g4_model"],
            "n_s0_red30": r["n_s0_red"],
            "n_s0_raw40": r["n_s0_raw"],
            "raw40_extra_loss": r["raw40_extra_loss"],
            "n_s1_red30": r["n_s1_red"],
            "n_s1_raw40": r["n_s1_raw"],
            "n_s1_raw40_ext": r["n_s1_raw_ext"],
            "s1_raw_vs_red_pct": r["s1_raw_vs_red_rel_diff_pct"],
            "s1_raw_ext_vs_red_pct": r["s1_raw_ext_vs_red_rel_diff_pct"],
            "n_s2_red30": r["n_s2_red"],
            "n_s2_raw40": r["n_s2_raw"],
            "s2_raw_vs_red_pct": r["s2_raw_vs_red_rel_diff_pct"],
        }
        for r in g4_rows
    ]

    # S1/S2 threshold sensitivity scan on nominal FTFP_BERT 30 ab^-1
    nom_runs = np.array(
        list(GEOM_TRIPLETS["2022_2023"]["FTFP_BERT"])
        + list(GEOM_TRIPLETS["2024_noCaloNu"]["FTFP_BERT"])
        + list(GEOM_TRIPLETS["2024_CaloNu"]["FTFP_BERT"]),
        dtype=np.int32,
    )
    m_nom = np.isin(run_arr, nom_runs)
    n_fid_nom = sum(run_summary[int(r)]["n_fid_pz100"] for r in nom_runs)
    n_s0_nom = int(np.count_nonzero(sel_red["passed_s0"][m_nom]))
    n_zb_nom = int(np.count_nonzero(sel_red["zone_b"][m_nom]))

    scan_rows = []
    for t2 in [1.8, 2.0, 2.2, 2.5, 2.8]:
        for t1 in [2.5, 2.8, 3.0, 3.5]:
            if t1 < t2:
                continue
            sc_m = evaluate_selection_masks(ev, mode=winner_mode, use_raw40=False, t_2hit=t2, t_1hit=t1)
            ns1 = int(np.count_nonzero(sc_m["passed_s1"][m_nom]))
            resc = ns1 - n_s0_nom
            scan_rows.append({
                "strategy": "S1", "param_a": t2, "param_b": t1, "chi2_max": 5.0, "width_max": 19.5,
                "n_sel_nom": ns1, "rescue_cnt": resc,
                "rescue_pct_zoneB": 100.0 * resc / max(n_zb_nom, 1),
                "eff_fid_pct": 100.0 * ns1 / max(n_fid_nom, 1),
            })
    for cmax in [3.0, 5.0]:
        for wmax in [12.0, 16.0, 19.5, 999.0]:
            sc_m = evaluate_selection_masks(ev, mode=winner_mode, use_raw40=False, chi2_max=cmax, width_max=wmax)
            ns1 = int(np.count_nonzero(sc_m["passed_s1"][m_nom]))
            resc = ns1 - n_s0_nom
            scan_rows.append({
                "strategy": "S1_qual", "param_a": 2.2, "param_b": 3.0, "chi2_max": cmax, "width_max": wmax,
                "n_sel_nom": ns1, "rescue_cnt": resc,
                "rescue_pct_zoneB": 100.0 * resc / max(n_zb_nom, 1),
                "eff_fid_pct": 100.0 * ns1 / max(n_fid_nom, 1),
            })
    for dchi in [16.0, 25.0, 36.0]:
        for z_m, z_nm in [(5.0, 4.5), (6.0, 5.0), (7.0, 5.5)]:
            sc_m = evaluate_selection_masks(ev, mode=winner_mode, use_raw40=False, dchi2_s2=dchi, z_1hit_mip_s2=z_m, z_1hit_nonmip_s2=z_nm)
            ns2 = int(np.count_nonzero(sc_m["passed_s2"][m_nom]))
            resc = ns2 - n_s0_nom
            scan_rows.append({
                "strategy": "S2", "param_a": dchi, "param_b": z_m, "chi2_max": 5.0, "width_max": 19.5,
                "n_sel_nom": ns2, "rescue_cnt": resc,
                "rescue_pct_zoneB": 100.0 * resc / max(n_zb_nom, 1),
                "eff_fid_pct": 100.0 * ns2 / max(n_fid_nom, 1),
            })

    # 6D acceptance recovery (nominal 30 ab^-1 FTFP_BERT)
    acc6d_rows: list[dict[str, Any]] = []
    dim_specs = [
        ("E_nu", "h_fid_E_nu", ev["truth_E_nu_GeV"]),
        ("pz_mu", "h_fid_pz_mu", ev["truth_pz_mu_GeV"]),
        ("y_inel", "h_fid_y_inel", ev["truth_y_inel"]),
        ("z_vtx", "h_fid_z_vtx", ev["truth_dec_z"]),
        ("r_vtx", "h_fid_r_vtx", ev["truth_dec_r"]),
        ("q_mu", "h_fid_q_mu", np.where(ev["truth_mu_pdg"] == 13, -1.0, np.where(ev["truth_mu_pdg"] == -13, +1.0, 0.0))),
    ]
    for dname, hname, var_all in dim_specs:
        # Sum truth denominator histogram across nominal 9 runs
        edges = run_hists[int(nom_runs[0])][hname][1]
        denom = np.sum([run_hists[int(r)][hname][0] for r in nom_runs], axis=0)
        # Rebin slightly for readability while storing full raw or grouped bins
        if dname in ("E_nu", "pz_mu"):
            # Coarsen 40 -> 10 bins (factor 4) for stable statistical error bars, keeping exact edges
            rebin = 4
        elif dname == "z_vtx":
            # 35 -> 7 bins? No, keep 21 or merge every 5 bins -> 7 coarse regions or merge every 2/1! 35 bins of 41mm has ~15k fid each -> very high stat! Keep native 35 or factor 5=7. Actually native 35 bins for z_vtx gives super sharp resolution of front vs back of FASERnu! Let's keep native 35!
            rebin = 1
        elif dname == "y_inel":
            rebin = 2  # 10 bins of width 0.1
        elif dname == "r_vtx":
            rebin = 2  # 10 bins of width 10 mm
        else:
            rebin = 1  # q_mu

        v_nom = var_all[m_nom]
        in_range = (v_nom >= edges[0]) & (v_nom < edges[-1])
        h_sr, _ = np.histogram(v_nom[in_range], bins=edges)
        h_s0, _ = np.histogram(v_nom[in_range & sel_red["passed_s0"][m_nom]], bins=edges)
        h_s1, _ = np.histogram(v_nom[in_range & sel_red["passed_s1"][m_nom]], bins=edges)
        h_s2, _ = np.histogram(v_nom[in_range & sel_red["passed_s2"][m_nom]], bins=edges)

        if rebin > 1:
            n_g = len(denom) // rebin
            edges_r = edges[::rebin][:n_g + 1]
            denom = denom[:n_g * rebin].reshape(n_g, rebin).sum(axis=1)
            h_sr = h_sr[:n_g * rebin].reshape(n_g, rebin).sum(axis=1)
            h_s0 = h_s0[:n_g * rebin].reshape(n_g, rebin).sum(axis=1)
            h_s1 = h_s1[:n_g * rebin].reshape(n_g, rebin).sum(axis=1)
            h_s2 = h_s2[:n_g * rebin].reshape(n_g, rebin).sum(axis=1)
        else:
            edges_r = edges

        for bi in range(len(denom)):
            den = float(denom[bi])
            if den <= 0.0:
                continue
            e0, e1 = float(h_s0[bi]) / den, float(h_s1[bi]) / den
            e2, esr = float(h_s2[bi]) / den, float(h_sr[bi]) / den
            acc6d_rows.append({
                "dim": dname,
                "bin_lo": float(edges_r[bi]),
                "bin_hi": float(edges_r[bi + 1]),
                "n_fid": den,
                "n_sr": int(h_sr[bi]),
                "n_s0": int(h_s0[bi]),
                "n_s1": int(h_s1[bi]),
                "n_s2": int(h_s2[bi]),
                "eff_sr": esr,
                "eff_s0": e0,
                "eff_s1": e1,
                "eff_s2": e2,
                "eff_s0_err": math.sqrt(max(e0 * (1.0 - e0) / den, 0.0)),
                "eff_s1_err": math.sqrt(max(e1 * (1.0 - e1) / den, 0.0)),
                "eff_s2_err": math.sqrt(max(e2 * (1.0 - e2) / den, 0.0)),
                "rel_gain_s1_pct": 100.0 * (e1 - e0) / max(e0, 1e-12),
                "rel_gain_s2_pct": 100.0 * (e2 - e0) / max(e0, 1e-12),
            })

    # ML Domain Shift assessment (F7_pz0_raw_v1 includes VetoNu0/1_raw_charge and VetoNu0/1_reduced_charge)
    m_s1_nom = m_nom & sel_red["passed_s1"]
    m_s1_oob_red = m_s1_nom & sel_red["zone_b"]  # q_red >= 30 pC (strictly outside S0 reduced-charge <30 pC domain!)
    m_s1_oob_raw = m_s1_nom & ((ev["vn_q_raw"][:, 0] >= 40.0) | (ev["vn_q_raw"][:, 1] >= 40.0))
    n_s1_nom = int(np.count_nonzero(m_s1_nom))
    y_nom = ev["truth_y_inel"]
    e_nom = ev["truth_E_nu_GeV"]
    ml_domain = {
        "n_s1_nom": n_s1_nom,
        "n_s1_oob_red30": int(np.count_nonzero(m_s1_oob_red)),
        "frac_s1_oob_red30_pct": 100.0 * int(np.count_nonzero(m_s1_oob_red)) / max(n_s1_nom, 1),
        "n_s1_oob_raw40": int(np.count_nonzero(m_s1_oob_raw)),
        "frac_s1_oob_raw40_pct": 100.0 * int(np.count_nonzero(m_s1_oob_raw)) / max(n_s1_nom, 1),
        "median_y_inel_s0": float(np.median(y_nom[m_nom & sel_red["passed_s0"]])),
        "median_y_inel_s1_rescued": float(np.median(y_nom[m_s1_oob_red])),
        "median_E_nu_GeV_s0": float(np.median(e_nom[m_nom & sel_red["passed_s0"]])),
        "median_E_nu_GeV_s1_rescued": float(np.median(e_nom[m_s1_oob_red])),
        "frac_oob_high_y_ge05_pct": 100.0 * float(np.count_nonzero(m_s1_oob_red & (y_nom >= 0.5))) / max(int(np.count_nonzero(m_s1_nom & (y_nom >= 0.5))), 1),
        "frac_oob_low_y_lt05_pct": 100.0 * float(np.count_nonzero(m_s1_oob_red & (y_nom < 0.5))) / max(int(np.count_nonzero(m_s1_nom & (y_nom < 0.5))), 1),
    }

    # Preliminary timing scale/resolution systematics across nominal 30 ab^-1
    def _tot_nom(m_dict: dict[str, np.ndarray], key: str) -> int:
        return int(np.count_nonzero(m_dict[key][m_nom]))

    n_s2_nom = _tot_nom(sel_red, "passed_s2")
    timing_syst = {
        "s1_nom": n_s1_nom,
        "s1_scale_plus015_pct": 100.0 * (_tot_nom(sel_scale_p, "passed_s1") - n_s1_nom) / max(n_s1_nom, 1),
        "s1_scale_minus015_pct": 100.0 * (_tot_nom(sel_scale_m, "passed_s1") - n_s1_nom) / max(n_s1_nom, 1),
        "s1_smear_plus15pct_pct": 100.0 * (_tot_nom(sel_smear_p, "passed_s1") - n_s1_nom) / max(n_s1_nom, 1),
        "s1_smear_minus15pct_pct": 100.0 * (_tot_nom(sel_smear_m, "passed_s1") - n_s1_nom) / max(n_s1_nom, 1),
        "s2_nom": n_s2_nom,
        "s2_scale_plus015_pct": 100.0 * (_tot_nom(sel_scale_p, "passed_s2") - n_s2_nom) / max(n_s2_nom, 1),
        "s2_scale_minus015_pct": 100.0 * (_tot_nom(sel_scale_m, "passed_s2") - n_s2_nom) / max(n_s2_nom, 1),
        "s2_smear_plus15pct_pct": 100.0 * (_tot_nom(sel_smear_p, "passed_s2") - n_s2_nom) / max(n_s2_nom, 1),
        "s2_smear_minus15pct_pct": 100.0 * (_tot_nom(sel_smear_m, "passed_s2") - n_s2_nom) / max(n_s2_nom, 1),
    }

    write_tsv(out_dir / "t3_5models_acceptance.tsv", g4_rows)
    write_tsv(out_dir / "t3_h5_model_spread.tsv", g4_spread_rows)
    write_tsv(out_dir / "t3_run3_yields.tsv", run3_yield_rows)
    write_tsv(out_dir / "t3_flux_variations.tsv", flux_rows)
    write_tsv(out_dir / "t3_raw40_vs_red30.tsv", raw_vs_red_rows)
    write_tsv(out_dir / "t3_threshold_scan.tsv", scan_rows)
    write_tsv(out_dir / "t3_6d_acceptance.tsv", acc6d_rows)

    return {
        "g4_spread": g4_spread_rows,
        "run3_yields": run3_yield_rows,
        "flux_rows": flux_rows,
        "ml_domain_shift": ml_domain,
        "timing_syst_prelim": timing_syst,
        "acc6d_rows": acc6d_rows,
        "raw_vs_red_rows": raw_vs_red_rows,
    }


def make_figures(
    ev: dict[str, np.ndarray],
    winner_mode: str,
    task1_res: dict[str, Any],
    task2_res: dict[str, Any],
    task34_res: dict[str, Any],
    out_dir: Path,
) -> list[str]:
    """Generate 6 crisp publication-style figures in workbook/stage214_timing_t3/."""
    plt.rcParams.update({"font.size": 10, "axes.grid": True, "grid.alpha": 0.25})
    figs: list[str] = []

    nom_runs = np.array(
        list(GEOM_TRIPLETS["2022_2023"]["FTFP_BERT"])
        + list(GEOM_TRIPLETS["2024_noCaloNu"]["FTFP_BERT"])
        + list(GEOM_TRIPLETS["2024_CaloNu"]["FTFP_BERT"]),
        dtype=np.int32,
    )
    m_nom = np.isin(ev["run"], nom_runs)
    sel = evaluate_selection_masks(ev, mode=winner_mode, use_raw40=False)
    m_zb = m_nom & sel["zone_b"]
    act_b = sel["act"][m_zb]
    topo_both = act_b[:, 0] & act_b[:, 1]
    topo_v1 = (~act_b[:, 0]) & act_b[:, 1]
    topo_v0 = act_b[:, 0] & (~act_b[:, 1])

    # Fig 1: Species breakdown across all Zone B + topologies
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    sp_rows = [r for r in task1_res["nominal_ftfp_bert_30ab"]["species_rows"] if r["frac_zoneB_pct"] >= 0.2]
    sp_rows = sorted(sp_rows, key=lambda r: r["count"], reverse=True)
    names = [r["species"] for r in sp_rows]
    b_cnt = [r["count"] * r["both_pct"] / 100.0 for r in sp_rows]
    v1_cnt = [r["count"] * r["vn1_only_pct"] / 100.0 for r in sp_rows]
    v0_cnt = [r["count"] * r["vn0_only_pct"] / 100.0 for r in sp_rows]
    y_pos = np.arange(len(names))
    axes[0].barh(y_pos, b_cnt, label="Both layers >=30 pC", color="#1f77b4")
    axes[0].barh(y_pos, v1_cnt, left=b_cnt, label="VetoNu1-only >=30 pC", color="#ff7f0e")
    axes[0].barh(y_pos, v0_cnt, left=np.array(b_cnt) + np.array(v1_cnt), label="VetoNu0-only >=30 pC", color="#2ca02c")
    axes[0].set_yticks(y_pos)
    axes[0].set_yticklabels(names)
    axes[0].invert_yaxis()
    axes[0].set_xlabel("Nominal 30 ab$^{-1}$ GENIE Zone B events")
    axes[0].set_title("VetoNuHits Dominant Truth Species by Layer Topology")
    axes[0].legend(fontsize=9)

    q_red_b = np.maximum(ev["vn_q_red"][m_zb], 0.0)
    aq = (q_red_b[:, 1] - q_red_b[:, 0]) / np.maximum(q_red_b[:, 0] + q_red_b[:, 1], 1e-6)
    bins_aq = np.linspace(-1.0, 1.0, 41)
    axes[1].hist(aq[topo_both], bins=bins_aq, histtype="step", lw=2.0, density=True, label="Both layers", color="#1f77b4")
    axes[1].hist(aq[topo_v1], bins=bins_aq, histtype="step", lw=2.0, density=True, label="VetoNu1-only (stopping)", color="#ff7f0e")
    axes[1].hist(aq[topo_v0], bins=bins_aq, histtype="step", lw=2.0, density=True, label="VetoNu0-only", color="#2ca02c")
    axes[1].set_xlabel(r"Layer Charge Asymmetry $A_Q = (Q_1 - Q_0)/(Q_1 + Q_0)$")
    axes[1].set_ylabel("Normalized Density")
    axes[1].set_title(r"VetoNu Stopping Signature $A_Q$")
    axes[1].legend(fontsize=9)
    fig.tight_layout()
    p1 = out_dir / "fig1_species_topology.png"
    fig.savefig(p1, dpi=150)
    plt.close(fig)
    figs.append(p1.name)

    # Fig 2: Delay vs z_vtx + KE/dEdx
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    prim_idx = np.where(topo_v0, 0, np.where(topo_v1, 1, np.where(q_red_b[:, 1] >= q_red_b[:, 0], 1, 0)))
    rows_b = np.arange(len(prim_idx))
    prim_dt = sel["dt"][m_zb][rows_b, prim_idx]
    prim_cat = ev["g4_dom_cat"][m_zb][rows_b, prim_idx]
    prim_ke = ev["g4_dom_ke_mev"][m_zb][rows_b, prim_idx]
    z_b = ev["truth_dec_z"][m_zb]
    ok_dt = np.isfinite(prim_dt) & (prim_dt > -3.0) & (prim_dt < 30.0)
    h2 = axes[0].hist2d(z_b[ok_dt], prim_dt[ok_dt], bins=[40, 45], range=[[-3050, -2300], [-2.0, 26.0]], cmap="viridis", norm=matplotlib.colors.LogNorm())
    fig.colorbar(h2[3], ax=axes[0], label="Events")
    z_line = np.linspace(-3020, -2300, 100)
    axes[0].plot(z_line, 2.0 * (z_line - (-3112.0)) / 299.792458, "r--", lw=1.8, label=r"$2(z_{\mathrm{vtx}} - z_{\mathrm{VN}})/c$ ($\beta=1$ lower bound)")
    axes[0].axhline(2.2, color="white", ls=":", lw=1.4, label=r"$T_{2\mathrm{hit}} = 2.2$ ns")
    axes[0].axhline(3.0, color="orange", ls="--", lw=1.4, label=r"$T_{1\mathrm{hit}} = 3.0$ ns")
    axes[0].set_xlabel(r"Truth Vertex $z_{\mathrm{vtx}}$ [mm]")
    axes[0].set_ylabel(r"Active-Layer Calibrated Delay $\Delta t$ [ns]")
    axes[0].set_title(r"Backward Hadron Delay $\Delta t$ vs Interaction Depth")
    axes[0].legend(fontsize=8.5, loc="upper left")

    bins_dt = np.linspace(-2.0, 28.0, 61)
    for cid, cname, col in [(1, "proton", "#d62728"), (2, "pi+-", "#1f77b4"), (4, "n recoil/nuc", "#9467bd"), (5, "gamma -> e", "#2ca02c"), (6, "cascade e", "#ff7f0e")]:
        mc = ok_dt & (prim_cat == cid)
        if np.count_nonzero(mc) > 50:
            axes[1].hist(prim_dt[mc], bins=bins_dt, histtype="step", lw=1.8, label=f"{cname} (med {np.median(prim_dt[mc]):.1f} ns)", color=col)
    axes[1].axvline(2.2, color="black", ls=":", lw=1.2)
    axes[1].axvline(3.0, color="black", ls="--", lw=1.2)
    axes[1].axvline(22.0, color="gray", ls="-.", lw=1.2, label="Upper bound 22 ns")
    axes[1].set_xlabel(r"Calibrated Delay $\Delta t$ [ns]")
    axes[1].set_ylabel("Nominal 30 ab$^{-1}$ Events / 0.5 ns")
    axes[1].set_title(r"$\Delta t$ Spectrum by Dominant VetoNu Particle")
    axes[1].legend(fontsize=8.5)
    fig.tight_layout()
    p2 = out_dir / "fig2_kinematics_delay_vs_z.png"
    fig.savefig(p2, dpi=150)
    plt.close(fig)
    figs.append(p2.name)

    # Fig 3: Downstream shower delay & estimator comparison
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    calo_edges = [0, 10, 100, 300, 1000]
    calo_x = [5, 55, 200, 650]
    calo_gev = ev["calo_total_E_EM"].astype(np.float64) / 1000.0
    tunsm = ev["down_t_unsmear"].astype(np.float64)
    st = ev["down_st"]
    for ci, cname, col in [(0, "Veto10", "#d62728"), (2, "Veto20", "#1f77b4"), (3, "Veto21", "#ff7f0e"),
                           (4, "Timing01", "#9467bd"), (5, "Timing23", "#8c564b"), (6, "Preshower0", "#2ca02c"), (7, "Preshower1", "#17becf")]:
        means = []
        p95s = []
        for k in range(len(calo_edges) - 1):
            mb = (st[:, ci] == 0) & np.isfinite(tunsm[:, ci]) & (calo_gev >= calo_edges[k]) & (calo_gev < calo_edges[k + 1])
            means.append(float(np.mean(tunsm[mb, ci])) if np.count_nonzero(mb) > 20 else np.nan)
        axes[0].plot(calo_x, means, marker="o", lw=1.8, label=cname, color=col)
    axes[0].set_xscale("log")
    axes[0].axhline(0.0, color="k", ls=":", lw=1.0)
    axes[0].set_xlabel(r"Calo\_total\_E\_EM [GeV]")
    axes[0].set_ylabel(r"Mean Unsmeared $t_{\mathrm{MC}}^{(0)}$ [ns]")
    axes[0].set_title("Downstream Non-Saturated Channel Delay vs EM Shower Energy")
    axes[0].legend(fontsize=8.5, ncol=2)

    bins_t0 = np.linspace(-1.5, 2.5, 81)
    for colname, lbl, col in [("t0_down", "AllValid", "#1f77b4"), ("t0_down_tgeom", "TimingGeom", "#ff7f0e"), ("t0_down_trim", "Trimmed3Sigma", "#2ca02c")]:
        v = ev[colname].astype(np.float64)
        v = v[np.isfinite(v)]
        axes[1].hist(np.clip(v, -1.5, 2.5), bins=bins_t0, histtype="step", lw=1.9, density=True, label=f"{lbl} (RMS={np.std(v):.3f} ns)", color=col)
    axes[1].set_yscale("log")
    axes[1].set_xlabel(r"Estimated $t_{0,\mathrm{down}}$ [ns] (True $v=c$ = 0)")
    axes[1].set_ylabel("Normalized Density (log)")
    axes[1].set_title(r"$t_{0,\mathrm{down}}$ Tails Before & After 3$\sigma$ Trimming")
    axes[1].legend(fontsize=9)
    fig.tight_layout()
    p3 = out_dir / "fig3_downstream_shower_bias.png"
    fig.savefig(p3, dpi=150)
    plt.close(fig)
    figs.append(p3.name)

    # Fig 4: raw40 vs red30 parity
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    rr_nom = [r for r in task34_res["raw_vs_red_rows"] if r["g4_model"] == "FTFP_BERT"]
    geoms = [r["geometry"] for r in rr_nom]
    xg = np.arange(len(geoms))
    wbar = 0.25
    # Show efficiency difference relative to S0_red30 across geometries
    e_s0raw = [100.0 * (r["n_s0_raw40"] - r["n_s0_red30"]) / r["n_s0_red30"] for r in rr_nom]
    e_s1raw = [100.0 * (r["n_s1_raw40"] - r["n_s1_red30"]) / r["n_s1_red30"] for r in rr_nom]
    e_s1ext = [100.0 * (r["n_s1_raw40_ext"] - r["n_s1_red30"]) / r["n_s1_red30"] for r in rr_nom]
    e_s2raw = [100.0 * (r["n_s2_raw40"] - r["n_s2_red30"]) / r["n_s2_red30"] for r in rr_nom]
    axes[0].bar(xg - 1.5 * wbar, e_s0raw, width=wbar, label="S0 raw40 vs S0 red30", color="#d62728")
    axes[0].bar(xg - 0.5 * wbar, e_s1raw, width=wbar, label="S1 raw40 (<22ns) vs S1 red30", color="#1f77b4")
    axes[0].bar(xg + 0.5 * wbar, e_s1ext, width=wbar, label="S1 raw40 (+>32ns ext) vs S1 red30", color="#2ca02c")
    axes[0].bar(xg + 1.5 * wbar, e_s2raw, width=wbar, label="S2 raw40 vs S2 red30", color="#ff7f0e")
    axes[0].axhline(0.0, color="k", lw=1.0)
    axes[0].set_xticks(xg)
    axes[0].set_xticklabels(geoms)
    axes[0].set_ylabel("Relative Yield Difference vs Reduced-Charge Version [%]")
    axes[0].set_title(r"Parity of Aux-Free `raw_charge < 40` + Timing vs `reduced_charge < 30`")
    axes[0].legend(fontsize=8.5)

    # Scatter/hist of dt for events failing raw_charge<40 but passing reduced_charge<30
    sel_raw = evaluate_selection_masks(ev, mode=winner_mode, use_raw40=True)
    m_diff = m_nom & sel["passed_s0"] & (~sel_raw["passed_s0"])
    dt_diff = sel_raw["dt"][m_diff]
    act_diff = sel_raw["act"][m_diff]
    dt_vals = dt_diff[act_diff]
    dt_vals = dt_vals[np.isfinite(dt_vals)]
    axes[1].hist(np.clip(dt_vals, -5.0, 95.0), bins=50, color="#9467bd", alpha=0.8)
    axes[1].axvline(22.0, color="r", ls="--", lw=1.4, label="22 ns upper cut")
    axes[1].axvline(32.0, color="g", ls="--", lw=1.4, label="32 ns afterpulse onset")
    axes[1].set_xlabel(r"Active-Layer Calibrated Time $\Delta t$ [ns]")
    axes[1].set_ylabel("Events passing red<30 & failing raw<40")
    axes[1].set_title("Time Distribution of Events Lost by Raw Charge Alone")
    axes[1].legend(fontsize=9)
    fig.tight_layout()
    p4 = out_dir / "fig4_raw40_vs_red30.png"
    fig.savefig(p4, dpi=150)
    plt.close(fig)
    figs.append(p4.name)

    # Fig 5: 5 Geant4 physics lists across 3 geometries + H5 model spread compression
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    g4_path = out_dir / "t3_5models_acceptance.tsv"
    g4_loaded = list(csv.DictReader(g4_path.open(), delimiter="\t"))
    for gi, geom in enumerate(["2022_2023", "2024_noCaloNu", "2024_CaloNu"]):
        rows_g = [r for r in g4_loaded if r["geometry"] == geom]
        e_s0 = [100.0 * float(r["eff_vn_s0_red"]) for r in rows_g]
        e_s1 = [100.0 * float(r["eff_vn_s1_red"]) for r in rows_g]
        axes[0].plot(np.arange(len(G4_MODEL_ORDER)), e_s0, marker="s", ls="--", label=f"{geom} S0" if gi == 0 else None, color=["#1f77b4", "#ff7f0e", "#2ca02c"][gi])
        axes[0].plot(np.arange(len(G4_MODEL_ORDER)), e_s1, marker="o", ls="-", label=f"{geom} S1 ({'s0015+master_dev' if geom == '2024_CaloNu' else 'uniform geo'})", color=["#1f77b4", "#ff7f0e", "#2ca02c"][gi])
    axes[0].set_xticks(np.arange(len(G4_MODEL_ORDER)))
    axes[0].set_xticklabels(G4_MODEL_ORDER, rotation=20, ha="right", fontsize=8.5)
    axes[0].set_ylabel(r"Conditional VetoNu Survival $N_{\mathrm{sel}} / N_{\mathrm{SR}}$ [%]")
    axes[0].set_title("5 Geant4 Physics Lists: S0 (dashed) vs S1 (solid)")
    axes[0].legend(fontsize=8.2)

    spr_rows = [r for r in task34_res["g4_spread"] if r["strategy"] in ("S0_red30", "S1_timing", "S2_pull_chi2", "S1_raw40_ext")]
    g_names = ["2022_2023", "2024_noCaloNu", "2024_CaloNu", "Run3_Combined_335.92fb"]
    xsp = np.arange(len(g_names))
    for si, (sk, lbl, col) in enumerate([("S0_red30", "S0 (red < 30 pC)", "#d62728"),
                                         ("S1_timing", "S1 (timing window)", "#1f77b4"),
                                         ("S2_pull_chi2", "S2 (pull + dchi2)", "#2ca02c"),
                                         ("S1_raw40_ext", "S1 raw40 (+>32ns)", "#ff7f0e")]):
        vals = [next(r["cond_vn_rel_envelope_pct"] for r in spr_rows if r["geometry"] == g and r["strategy"] == sk) for g in g_names]
        axes[1].bar(xsp + (si - 1.5) * 0.2, vals, width=0.2, label=lbl, color=col)
    axes[1].set_xticks(xsp)
    axes[1].set_xticklabels(["2022-23", "2024 noCaloNu", "2024 CaloNu", "Run 3 Comb."])
    axes[1].set_ylabel(r"5-Model Spread $(\epsilon_{\mathrm{VN},\max} - \epsilon_{\mathrm{VN},\min}) / \epsilon_{\mathrm{VN},\mathrm{nom}}$ [%]")
    axes[1].set_title(r"Hypothesis H5: VetoNu Backscatter Model Envelope Compression")
    axes[1].legend(fontsize=8.5)
    fig.tight_layout()
    p5 = out_dir / "fig5_g4_models_h5.png"
    fig.savefig(p5, dpi=150)
    plt.close(fig)
    figs.append(p5.name)

    # Fig 6: 6D acceptance recovery (E_nu, pz_mu, y_inel, z_vtx, r_vtx, q_mu)
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.5))
    dims = [("E_nu", r"$E_\nu$ [GeV]"), ("pz_mu", r"$p_{z,\mu}$ [GeV]"), ("y_inel", r"Inelasticity $y_{\mathrm{inel}}$"),
            ("z_vtx", r"$z_{\mathrm{vtx}}$ [mm]"), ("r_vtx", r"$r_{\mathrm{vtx}}$ [mm]"), ("q_mu", r"Muon Charge $q_\mu$")]
    for ax, (dk, xlabel) in zip(axes.flat, dims):
        rows_d = [r for r in task34_res["acc6d_rows"] if r["dim"] == dk]
        xc = [0.5 * (r["bin_lo"] + r["bin_hi"]) for r in rows_d]
        xe = [0.5 * (r["bin_hi"] - r["bin_lo"]) for r in rows_d]
        for key, ekey, lbl, col, ls in [
            ("eff_sr", None, "Pre-VetoNu SR", "gray", ":"),
            ("eff_s0", "eff_s0_err", "S0 (baseline)", "#d62728", "--"),
            ("eff_s1", "eff_s1_err", "S1 (timing)", "#1f77b4", "-"),
            ("eff_s2", "eff_s2_err", "S2 (pull+dchi2)", "#2ca02c", "-."),
        ]:
            yy = [100.0 * r[key] for r in rows_d]
            ye = [100.0 * r[ekey] for r in rows_d] if ekey else None
            if ye:
                ax.errorbar(xc, yy, xerr=xe, yerr=ye, fmt="o" if key == "eff_s1" else "", ls=ls, lw=1.7, ms=3.5, label=lbl, color=col)
            else:
                ax.plot(xc, yy, ls=ls, lw=1.5, label=lbl, color=col)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Fiducial Acceptance [%]")
    axes.flat[0].legend(fontsize=8, loc="lower right")
    fig.suptitle(r"6D Fiducial $\nu_\mu$ CC Acceptance Recovery (Nominal $30\ \mathrm{ab}^{-1}$ GENIE)", fontsize=12)
    fig.tight_layout()
    p6 = out_dir / "fig6_6d_acceptance_recovery.png"
    fig.savefig(p6, dpi=150)
    plt.close(fig)
    figs.append(p6.name)
    return figs


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage T3 (Stage 214) backward-hadron dissection and 5-G4-model study.")
    parser.add_argument("--eos-dir", default=EOS_RUNS_DIR, help="EOS directory containing T3 shards.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Output directory for TSVs, JSON, PNGs.")
    parser.add_argument("--workers", type=int, default=28, help="Multiprocessing worker count.")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    t_start = time.perf_counter()

    # Load Run 3 manifest luminosities
    manifest = json.loads(MANIFEST_PATH.read_text())
    per_lumi = {p["period"]: float(p["lumi_fb_inverse"]) for p in manifest["periods"]}
    lumi_info = {
        "L_2022_2023_fb": per_lumi["2022"] + per_lumi["2023"],
        "L_2024_noCaloNu_fb": per_lumi["2024_preCaloNu"] + per_lumi["2024_postCaloNu"],
        "L_2024_CaloNu_fb": per_lumi["2024_CaloNu"],
        "L_2025_fb": per_lumi["2025"],
        "L_2026_fb": per_lumi["2026"],
        "L_2024_2026_ord_fb": per_lumi["2024_preCaloNu"] + per_lumi["2024_postCaloNu"] + per_lumi["2025"] + per_lumi["2026"],
        "L_total_2022_2024_fb": per_lumi["2022"] + per_lumi["2023"] + per_lumi["2024_preCaloNu"] + per_lumi["2024_postCaloNu"] + per_lumi["2024_CaloNu"],
        "L_total_Run3_fb": sum(per_lumi.values()),
    }

    print(f"[T3] Loading shards from {args.eos_dir} with {args.workers} workers...", flush=True)
    run_summary, ev, run_hists, load_wall = load_all_shards(args.eos_dir, args.workers)
    print(f"[T3] Loaded {len(run_summary)} runs, {len(ev['run']):,} SR events in {load_wall:.2f} s", flush=True)

    # Gate 1: Verify all 69 GENIE runs and >99.9% HITS vertex matching
    expected_runs = {int(r) for r in manifest["genie_mc_runs"].keys()}
    missing_runs = sorted(expected_runs - set(run_summary.keys()))
    if missing_runs:
        raise RuntimeError(f"Missing GENIE runs in Stage T3 outputs: {missing_runs}")

    tot_gen = sum(v["n_gen"] for v in run_summary.values())
    tot_fid = sum(v["n_fid_pz100"] for v in run_summary.values())
    tot_sr = sum(v["n_kin_sr"] for v in run_summary.values())
    tot_hits = sum(v["n_hits_matched"] for v in run_summary.values())
    tot_vtx_match = int(np.count_nonzero(ev["hits_vtx_match"]))
    match_frac = tot_hits / max(tot_sr, 1)
    vtx_match_frac = tot_vtx_match / max(tot_sr, 1)
    print(f"[T3] Integrity: runs={len(run_summary)}/69, n_gen={tot_gen:,}, n_fid={tot_fid:,}, n_sr={tot_sr:,}, hits_matched={tot_hits:,} ({100*match_frac:.4f}%), hits_vtx_match={tot_vtx_match:,} ({100*vtx_match_frac:.4f}%)", flush=True)
    if match_frac < 0.999 or vtx_match_frac < 0.999:
        raise RuntimeError(f"HITS vertex matching below 99.9% gate: {match_frac:.6f} / {vtx_match_frac:.6f}")

    # Save per-run inventory TSV
    inv_rows = []
    for r in sorted(run_summary):
        rs = run_summary[r]
        inv_rows.append({"run": r, **rs})
    write_tsv(args.out_dir / "t3_run_inventory.tsv", inv_rows)

    # Task 2 first to freeze optimal t0_down estimator
    print("[T3] Running Task 2: Downstream shower delay audit & t0_down mode comparison...", flush=True)
    task2_res = task2_downstream_shower_audit(ev, args.out_dir)
    winner = task2_res["winner"]
    print(f"[T3] Optimal t0_down estimator frozen: {winner}", flush=True)

    # Task 1 using optimal downstream estimator (and AllValid comparison recorded in Task 2)
    print(f"[T3] Running Task 1: Backward hadron truth dissection ({winner})...", flush=True)
    task1_res = task1_truth_dissection(ev, winner, args.out_dir)

    print("[T3] Running Tasks 3 & 4: raw40 vs red30, 5 G4 models (H5), 6D acceptance (H1/H6), ML domain shift...", flush=True)
    task34_res = task3_and_task4_evaluation(run_summary, ev, run_hists, winner, lumi_info, args.out_dir)

    print("[T3] Generating figures...", flush=True)
    figs = make_figures(ev, winner, task1_res, task2_res, task34_res, args.out_dir)

    summary = {
        "schema_version": 1,
        "load_wall_s": round(load_wall, 3),
        "total_wall_s": round(time.perf_counter() - t_start, 3),
        "n_runs": len(run_summary),
        "integrity": {
            "total_gen_events": tot_gen,
            "total_fid_pz100": tot_fid,
            "total_kin_sr": tot_sr,
            "total_hits_matched": tot_hits,
            "total_hits_vtx_match": tot_vtx_match,
            "hits_match_fraction": match_frac,
            "hits_vtx_match_fraction": vtx_match_frac,
        },
        "lumi_info_fb_inv": lumi_info,
        "t0_down_winner": winner,
        "task1_truth_dissection": task1_res,
        "task2_downstream_audit": task2_res,
        "task34_h5_spread": task34_res["g4_spread"],
        "task34_run3_yields": task34_res["run3_yields"],
        "task34_ml_domain_shift": task34_res["ml_domain_shift"],
        "task34_timing_syst_prelim": task34_res["timing_syst_prelim"],
        "figures": figs,
    }
    (args.out_dir / "t3_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"[T3] Completed in {summary['total_wall_s']:.2f} s. Summary written to {args.out_dir / 't3_summary.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
