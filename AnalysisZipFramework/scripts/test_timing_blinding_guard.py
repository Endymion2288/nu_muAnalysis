"""Unit tests verifying Python and C++ TimingBlindingGuard parity across all regions."""

from __future__ import annotations

import math
from pathlib import Path
import sys

import numpy as np
import ROOT

SCRIPT_DIR = Path(__file__).resolve().parent
INCLUDE_DIR = SCRIPT_DIR.parent / "include"
sys.path.insert(0, str(SCRIPT_DIR))

from timing_blinding_guard import compute_blinded_mask, filter_unblinded_arrays


def _make_base_case(**overrides) -> dict:
    case = dict(
        name="base",
        is_mc=False,
        distance_to_colliding_bcid=0,
        long_tracks=1,
        veto20_charge=80.0,
        veto21_charge=80.0,
        timing_charge_top=60.0,
        timing_charge_bottom=60.0,
        preshower0_charge=5.0,
        preshower1_charge=5.0,
        lead_y_at_trig=35.0,
        lead_pz0_gev=250.0,
        lead_n_layers=9,
        lead_ndof=12.0,
        lead_chi2_ndf=2.5,
        lead_r_max=50.0,
        lead_r_ift=48.0,
        lead_r_vetonu=45.0,
        lead_theta_mrad=10.0,
        vetonu0_raw_charge=5.0,
        vetonu1_raw_charge=5.0,
        vetonu0_reduced_charge=5.0,
        vetonu1_reduced_charge=5.0,
        has_calibrated_time=True,
        valid_downstream_ref=True,
        valid_cal0=True,
        dt0_ns=0.0,
        valid_cal1=True,
        dt1_ns=0.0,
        raw_delay_max_ns=0.0,
    )
    case.update(overrides)
    return case


def run_tests() -> None:
    guard_header = str(INCLUDE_DIR / "TimingBlindingGuard.h")
    assert ROOT.gInterpreter.Declare(f'#include "{guard_header}"'), "Failed to compile TimingBlindingGuard.h"

    cases = [
        (_make_base_case(name="zoneA_open"), False),
        (_make_base_case(name="cr_prompt_2hit", vetonu0_raw_charge=80.0, vetonu1_raw_charge=85.0, vetonu0_reduced_charge=80.0, vetonu1_reduced_charge=85.0, dt0_ns=0.1, dt1_ns=-0.2), False),
        (_make_base_case(name="cr_prompt_boundary_1p49", vetonu0_raw_charge=40.0, vetonu0_reduced_charge=40.0, dt0_ns=1.49), False),
        (_make_base_case(name="cr_prompt_neg_1p49", vetonu0_raw_charge=40.0, vetonu0_reduced_charge=40.0, dt0_ns=-1.49), False),
        (_make_base_case(name="sr_zoneB_boundary_1p5001", vetonu0_raw_charge=40.0, vetonu0_reduced_charge=40.0, dt0_ns=1.5001), True),
        (_make_base_case(name="sr_zoneB_2hit_delayed", vetonu0_raw_charge=90.0, vetonu1_raw_charge=95.0, vetonu0_reduced_charge=90.0, vetonu1_reduced_charge=95.0, dt0_ns=2.5, dt1_ns=3.1), True),
        (_make_base_case(name="sr_zoneB_1hit_vetonu1_stop", vetonu0_raw_charge=4.0, vetonu1_raw_charge=45.0, vetonu0_reduced_charge=4.0, vetonu1_reduced_charge=45.0, dt0_ns=0.0, dt1_ns=4.0), True),
        (_make_base_case(name="sr_zoneB_p0013_no_reduced", vetonu0_raw_charge=32.0, vetonu1_raw_charge=8.0, vetonu0_reduced_charge=-1.0, vetonu1_reduced_charge=-1.0, dt0_ns=3.0), True),
        (_make_base_case(name="sr_zoneB_invalid_down_ref", vetonu0_raw_charge=45.0, vetonu0_reduced_charge=45.0, valid_downstream_ref=False, dt0_ns=0.0), True),
        (_make_base_case(name="sr_zoneB_nan_dt0", vetonu0_raw_charge=45.0, vetonu0_reduced_charge=45.0, dt0_ns=float("nan")), True),
        (_make_base_case(name="sr_zoneB_precalib_raw_unsafe", vetonu0_raw_charge=50.0, vetonu0_reduced_charge=50.0, has_calibrated_time=False, raw_delay_max_ns=0.8), True),
        (_make_base_case(name="cr_prompt_precalib_safe", vetonu0_raw_charge=50.0, vetonu0_reduced_charge=50.0, has_calibrated_time=False, raw_delay_max_ns=0.3), False),
        (_make_base_case(name="cr_geom_rmax_sideband", lead_r_max=102.0, vetonu0_raw_charge=90.0, vetonu0_reduced_charge=90.0, dt0_ns=5.0), False),
        (_make_base_case(name="cr_geom_theta_sideband", lead_theta_mrad=30.0, vetonu1_raw_charge=90.0, vetonu1_reduced_charge=90.0, dt1_ns=6.0), False),
        (_make_base_case(name="cr_noncoll_beam1", distance_to_colliding_bcid=5, vetonu0_raw_charge=90.0, vetonu0_reduced_charge=90.0, dt0_ns=8.0), False),
        (_make_base_case(name="mc_genie_unblinded", is_mc=True, vetonu0_raw_charge=90.0, vetonu0_reduced_charge=90.0, dt0_ns=7.5), False),
    ]

    for c, expected in cases:
        ev = ROOT.TimingBlinding.EventKinematicsAndVeto()
        ev.isMC = bool(c["is_mc"])
        ev.distanceToCollidingBCID = int(c["distance_to_colliding_bcid"])
        ev.longTracks = int(c["long_tracks"])
        ev.veto20Charge = float(c["veto20_charge"])
        ev.veto21Charge = float(c["veto21_charge"])
        ev.timingChargeTop = float(c["timing_charge_top"])
        ev.timingChargeBottom = float(c["timing_charge_bottom"])
        ev.preshower0Charge = float(c["preshower0_charge"])
        ev.preshower1Charge = float(c["preshower1_charge"])
        ev.leadYatTrig = float(c["lead_y_at_trig"])
        ev.leadPz0GeV = float(c["lead_pz0_gev"])
        ev.leadNLayers = int(c["lead_n_layers"])
        ev.leadNDoF = float(c["lead_ndof"])
        ev.leadChi2NDF = float(c["lead_chi2_ndf"])
        ev.leadRMax = float(c["lead_r_max"])
        ev.leadRIFT = float(c["lead_r_ift"])
        ev.leadRVetoNu = float(c["lead_r_vetonu"])
        ev.leadThetaMrad = float(c["lead_theta_mrad"])
        ev.vetoNu0RawCharge = float(c["vetonu0_raw_charge"])
        ev.vetoNu1RawCharge = float(c["vetonu1_raw_charge"])
        ev.vetoNu0ReducedCharge = float(c["vetonu0_reduced_charge"])
        ev.vetoNu1ReducedCharge = float(c["vetonu1_reduced_charge"])

        cpp_res = bool(
            ROOT.TimingBlinding.isBlindedSRZoneB(
                ev,
                bool(c["has_calibrated_time"]),
                bool(c["valid_downstream_ref"]),
                bool(c["valid_cal0"]),
                float(c["dt0_ns"]),
                bool(c["valid_cal1"]),
                float(c["dt1_ns"]),
                float(c["raw_delay_max_ns"]),
            )
        )
        py_res = bool(
            compute_blinded_mask(
                is_mc=bool(c["is_mc"]),
                distance_to_colliding_bcid=np.array([c["distance_to_colliding_bcid"]], dtype=np.int32),
                long_tracks=np.array([c["long_tracks"]], dtype=np.int32),
                veto20_charge=np.array([c["veto20_charge"]], dtype=np.float32),
                veto21_charge=np.array([c["veto21_charge"]], dtype=np.float32),
                timing_charge_top=np.array([c["timing_charge_top"]], dtype=np.float32),
                timing_charge_bottom=np.array([c["timing_charge_bottom"]], dtype=np.float32),
                preshower0_charge=np.array([c["preshower0_charge"]], dtype=np.float32),
                preshower1_charge=np.array([c["preshower1_charge"]], dtype=np.float32),
                lead_y_at_trig=np.array([c["lead_y_at_trig"]], dtype=np.float64),
                lead_pz0_gev=np.array([c["lead_pz0_gev"]], dtype=np.float64),
                lead_n_layers=np.array([c["lead_n_layers"]], dtype=np.uint32),
                lead_ndof=np.array([c["lead_ndof"]], dtype=np.float64),
                lead_chi2_ndf=np.array([c["lead_chi2_ndf"]], dtype=np.float64),
                lead_r_max=np.array([c["lead_r_max"]], dtype=np.float64),
                lead_r_ift=np.array([c["lead_r_ift"]], dtype=np.float64),
                lead_r_vetonu=np.array([c["lead_r_vetonu"]], dtype=np.float64),
                lead_theta_mrad=np.array([c["lead_theta_mrad"]], dtype=np.float64),
                vetonu0_raw_charge=np.array([c["vetonu0_raw_charge"]], dtype=np.float32),
                vetonu1_raw_charge=np.array([c["vetonu1_raw_charge"]], dtype=np.float32),
                vetonu0_reduced_charge=np.array([c["vetonu0_reduced_charge"]], dtype=np.float32),
                vetonu1_reduced_charge=np.array([c["vetonu1_reduced_charge"]], dtype=np.float32),
                has_calibrated_time=bool(c["has_calibrated_time"]),
                valid_downstream_ref=np.array([c["valid_downstream_ref"]], dtype=bool),
                valid_cal0=np.array([c["valid_cal0"]], dtype=bool),
                dt0_ns=np.array([c["dt0_ns"]], dtype=np.float64),
                valid_cal1=np.array([c["valid_cal1"]], dtype=bool),
                dt1_ns=np.array([c["dt1_ns"]], dtype=np.float64),
                raw_delay_max_ns=np.array([c["raw_delay_max_ns"]], dtype=np.float64),
            )[0]
        )
        assert cpp_res == expected, f"C++ mismatch on {c['name']}: got {cpp_res}, expected {expected}"
        assert py_res == expected, f"Python mismatch on {c['name']}: got {py_res}, expected {expected}"
        print(f"PASS {c['name']:32s} blinded={expected}")

    # Verify filter_unblinded_arrays refuses bypass
    raised = False
    try:
        filter_unblinded_arrays({"run": np.array([16023])}, enforce_blinding=False)
    except RuntimeError:
        raised = True
    assert raised, "filter_unblinded_arrays must raise if enforce_blinding=False"
    print(f"ALL {len(cases)} C++/Python TimingBlindingGuard unit tests + bypass refusal test PASSED.")


if __name__ == "__main__":
    run_tests()
