"""Orthogonal SR-ZoneB blinding guard matching TimingBlindingGuard.h."""

from __future__ import annotations

import numpy as np


def is_kinematic_signal_region_arrays(
    long_tracks: np.ndarray,
    veto20_charge: np.ndarray,
    veto21_charge: np.ndarray,
    timing_charge_top: np.ndarray,
    timing_charge_bottom: np.ndarray,
    preshower0_charge: np.ndarray,
    preshower1_charge: np.ndarray,
    lead_y_at_trig: np.ndarray,
    lead_pz0_gev: np.ndarray,
    lead_n_layers: np.ndarray,
    lead_ndof: np.ndarray,
    lead_chi2_ndf: np.ndarray,
    lead_r_max: np.ndarray,
    lead_r_ift: np.ndarray,
    lead_r_vetonu: np.ndarray,
    lead_theta_mrad: np.ndarray,
) -> np.ndarray:
    """Return boolean mask of events passing downstream baseline nu_mu cuts."""
    hits_timing = (
        ((lead_y_at_trig > 20.0) & np.isfinite(timing_charge_top) & (timing_charge_top > 20.0))
        | ((lead_y_at_trig < -20.0) & np.isfinite(timing_charge_bottom) & (timing_charge_bottom > 20.0))
        | ((np.abs(lead_y_at_trig) <= 20.0)
           & np.isfinite(timing_charge_top)
           & np.isfinite(timing_charge_bottom)
           & ((timing_charge_top + timing_charge_bottom) > 20.0))
    )
    return (
        (long_tracks > 0)
        & np.isfinite(veto20_charge)
        & np.isfinite(veto21_charge)
        & (veto20_charge > 40.0)
        & (veto21_charge > 40.0)
        & np.isfinite(lead_y_at_trig)
        & hits_timing
        & np.isfinite(preshower0_charge)
        & np.isfinite(preshower1_charge)
        & (preshower0_charge > 2.5)
        & (preshower1_charge > 2.5)
        & np.isfinite(lead_pz0_gev)
        & (lead_pz0_gev > 100.0)
        & (lead_n_layers >= 7)
        & np.isfinite(lead_ndof)
        & (lead_ndof >= 9.0)
        & np.isfinite(lead_chi2_ndf)
        & (lead_chi2_ndf < 15.0)
        & np.isfinite(lead_r_max)
        & (lead_r_max < 95.0)
        & np.isfinite(lead_r_ift)
        & (lead_r_ift < 95.0)
        & np.isfinite(lead_r_vetonu)
        & (lead_r_vetonu < 120.0)
        & np.isfinite(lead_theta_mrad)
        & (lead_theta_mrad < 25.0)
    )


def compute_blinded_mask(
    *,
    is_mc: bool,
    distance_to_colliding_bcid: np.ndarray,
    long_tracks: np.ndarray,
    veto20_charge: np.ndarray,
    veto21_charge: np.ndarray,
    timing_charge_top: np.ndarray,
    timing_charge_bottom: np.ndarray,
    preshower0_charge: np.ndarray,
    preshower1_charge: np.ndarray,
    lead_y_at_trig: np.ndarray,
    lead_pz0_gev: np.ndarray,
    lead_n_layers: np.ndarray,
    lead_ndof: np.ndarray,
    lead_chi2_ndf: np.ndarray,
    lead_r_max: np.ndarray,
    lead_r_ift: np.ndarray,
    lead_r_vetonu: np.ndarray,
    lead_theta_mrad: np.ndarray,
    vetonu0_raw_charge: np.ndarray,
    vetonu1_raw_charge: np.ndarray,
    vetonu0_reduced_charge: np.ndarray | None = None,
    vetonu1_reduced_charge: np.ndarray | None = None,
    has_calibrated_time: bool = False,
    valid_downstream_ref: np.ndarray | None = None,
    valid_cal0: np.ndarray | None = None,
    dt0_ns: np.ndarray | None = None,
    valid_cal1: np.ndarray | None = None,
    dt1_ns: np.ndarray | None = None,
    raw_delay_max_ns: np.ndarray | None = None,
) -> np.ndarray:
    """Return True for events that MUST be blinded (SR-ZoneB in collision data)."""
    n = len(distance_to_colliding_bcid)
    if is_mc:
        return np.zeros(n, dtype=bool)

    red0 = np.full(n, -1.0, dtype=np.float32) if vetonu0_reduced_charge is None else np.asarray(vetonu0_reduced_charge)
    red1 = np.full(n, -1.0, dtype=np.float32) if vetonu1_reduced_charge is None else np.asarray(vetonu1_reduced_charge)

    kin_sr = is_kinematic_signal_region_arrays(
        long_tracks,
        veto20_charge,
        veto21_charge,
        timing_charge_top,
        timing_charge_bottom,
        preshower0_charge,
        preshower1_charge,
        lead_y_at_trig,
        lead_pz0_gev,
        lead_n_layers,
        lead_ndof,
        lead_chi2_ndf,
        lead_r_max,
        lead_r_ift,
        lead_r_vetonu,
        lead_theta_mrad,
    )

    act0 = (np.isfinite(vetonu0_raw_charge) & (vetonu0_raw_charge >= 30.0)) | (np.isfinite(red0) & (red0 >= 30.0))
    act1 = (np.isfinite(vetonu1_raw_charge) & (vetonu1_raw_charge >= 30.0)) | (np.isfinite(red1) & (red1 >= 30.0))
    zone_b_candidate = (distance_to_colliding_bcid == 0) & kin_sr & (act0 | act1)

    if has_calibrated_time:
        if valid_downstream_ref is None or valid_cal0 is None or dt0_ns is None or valid_cal1 is None or dt1_ns is None:
            raise ValueError("Calibrated blinding mode requires valid_downstream_ref, valid_cal0/1, and dt0/1_ns.")
        bad0 = act0 & ((~valid_cal0) | (~np.isfinite(dt0_ns)) | (dt0_ns > 1.5))
        bad1 = act1 & ((~valid_cal1) | (~np.isfinite(dt1_ns)) | (dt1_ns > 1.5))
        return zone_b_candidate & ((~valid_downstream_ref) | bad0 | bad1)

    if raw_delay_max_ns is None:
        return zone_b_candidate
    return zone_b_candidate & ((~np.isfinite(raw_delay_max_ns)) | (raw_delay_max_ns > 0.5))


def filter_unblinded_arrays(arrays: dict[str, np.ndarray], *, enforce_blinding: bool = True, **blinding_kwargs) -> tuple[dict[str, np.ndarray], int]:
    """Filter out blinded SR-ZoneB rows from an array dictionary at data-entry."""
    if not enforce_blinding:
        raise RuntimeError("Refusing to bypass SR-ZoneB blinding guard before formal T7 unblinding.")
    blinded = compute_blinded_mask(**blinding_kwargs)
    keep = ~blinded
    return {k: v[keep] for k, v in arrays.items()}, int(np.sum(blinded))
