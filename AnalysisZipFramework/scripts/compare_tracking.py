#!/usr/bin/env python3
"""Paired, unweighted MC cutflows using this repository's C++/YAML selection."""

import argparse
from pathlib import Path
import time

import numpy as np
import yaml

MODES = ("forward", "backward", "merge")
PAIRS = ((0, 1), (0, 2), (1, 2))
ENERGY_EDGES = np.array([100, 200, 300, 500, 750, 1000, 1500, 2000, 3000, 5000, 10000., np.inf])
RADIUS_EDGES = np.array([0, 20, 40, 60, 80, 100.])


def selection(repo):
    cuts = yaml.safe_load((repo / "AnalysisZipFramework/config/cuts.yaml").read_text())["Cuts"]
    active = []
    skipped = []
    for name, cfg in cuts.items():
        requirements = cfg.get("requires", [])
        if cfg.get("data_type", "ALL") == "DATA" or any(
                r != "reduced_charge" and r != "native_reduced_charge" for r in requirements):
            skipped.append(name)
            continue
        active.append((name, cfg["expression"]))
    return active, skipped


def extract(path, repo, threads=1):
    import ROOT
    start = time.monotonic()
    if threads > 1 and not ROOT.IsImplicitMTEnabled():
        ROOT.EnableImplicitMT(threads)
    ROOT.gInterpreter.AddIncludePath(str(repo / "AnalysisZipFramework/include"))
    ROOT.gInterpreter.Declare('#include "RDFDefines.h"')
    node = ROOT.RDataFrame("nt", str(path))
    columns = {str(c) for c in node.GetColumnNames()}
    if not {"VetoNu0_reduced_charge", "VetoNu1_reduced_charge"} <= columns:
        raise RuntimeError("native reduced charge required for this comparison")
    node = node.Define("isCaloNuPeriod",
                       "(200137 <= run && run <= 200147) || (200172 <= run && run <= 200183)")
    node = node.Define("is2024Period",
                       "(200091 < run && run < 200101) || (200160 <= run && run <= 200171) || "
                       "(200137 <= run && run <= 200147) || (200172 <= run && run <= 200183)")
    definitions = yaml.safe_load((repo / "AnalysisZipFramework/config/definitions.yaml").read_text())
    for name, cfg in definitions["Definitions"].items():
        if cfg.get("data_type", "ALL") != "DATA" and not cfg.get("requires"):
            node = node.Define(name, cfg["expression"])
    cuts, _ = selection(repo)
    cut_columns = []
    for index, (_, expression) in enumerate(cuts):
        col = f"comparison_cut_{index}"
        node = node.Define(col, expression)
        cut_columns.append(col)
    values = ["run", "eventID", "truth_pz_nu", "truth_dec_r", "truth_dec_z_nu",
              "longTracks", "LeadTrack_Idx", "LeadTrack_pz0", "LeadTrack_nLayers",
              "LeadTrack_nDoF", "LeadTrack_Chi2_NDF", "LeadTrack_r_atMaxRadius",
              "LeadTrack_rIFT", "LeadTrack_rVetoNu", "LeadTrack_Theta",
              "Lead_Track_Y_atTrig"]
    data = node.AsNumpy(values + cut_columns)
    order = np.lexsort((data["eventID"], data["run"]))
    data = {k: v[order] for k, v in data.items()}
    if len(set(zip(data["run"], data["eventID"]))) != len(order):
        raise RuntimeError("duplicate (run,eventID)")
    steps = np.column_stack([np.ones(len(order), dtype=bool)] +
                            [data[c].astype(bool) for c in cut_columns])
    cumulative = np.logical_and.accumulate(steps, axis=1)
    print(f"extracted {path} events={len(order)} wall={time.monotonic()-start:.2f}s", flush=True)
    return data, cumulative


def raw_nontrack_check(paths):
    """Compare every truth/scintillator input to the cuts before any selection."""
    import awkward as ak
    import uproot
    common = ["run", "eventID", "truth_pdg", "truth_pz", "truth_dec_x", "truth_dec_y",
              "truth_dec_z", "Veto20_charge", "Veto21_charge", "Preshower0_charge",
              "Preshower1_charge", "VetoNu0_reduced_charge", "VetoNu1_reduced_charge"]
    common += [f"Timing{i}_charge" for i in range(4)]
    reference = None
    for path in paths:
        with uproot.open(path) as source:
            arrays = source["nt"].arrays(common, library="ak")
        order = np.lexsort((ak.to_numpy(arrays.eventID), ak.to_numpy(arrays.run)))
        arrays = arrays[order]
        if reference is not None:
            for col in common:
                a, b = reference[col], arrays[col]
                if not ak.almost_equal(a, b, rtol=0, atol=0, dtype_exact=True):
                    raise RuntimeError(f"nontrack input differs between modes: {col}")
        reference = arrays
    return len(common)


def compare(paths, existing, repo, output, threads=1):
    cuts, _ = selection(repo)
    data, masks = [], []
    for path in paths:
        values, cumulative = extract(path, repo, threads)
        data.append(values)
        masks.append(cumulative)
    nontrack_columns = raw_nontrack_check(paths)
    for values in data[1:]:
        for col in ["run", "eventID", "truth_pz_nu", "truth_dec_r", "truth_dec_z_nu"]:
            if not np.array_equal(values[col], data[0][col], equal_nan=True):
                raise RuntimeError(f"event/truth mismatch: {col}")
    old_verified = 0
    if existing:
        old_data, old_mask = extract(existing, repo, threads)
        if len(old_mask) != len(masks[2]):
            raise RuntimeError("existing merge event count differs")
        for key in old_data:
            nan_numeric = old_data[key].dtype.kind in "fc"
            if not np.array_equal(old_data[key], data[2][key], equal_nan=nan_numeric):
                raise RuntimeError(f"existing/new merge analysis column differs: {key}")
        if not np.array_equal(old_mask, masks[2]):
            raise RuntimeError("existing/new merge cut decisions differ")
        raw_nontrack_check([paths[2], existing])
        old_verified = 1
    masks = np.stack(masks)
    counts = masks.sum(axis=1, dtype=np.int64)
    nonfinite_quality = np.array([np.count_nonzero(
        ~np.isfinite(values["LeadTrack_Chi2_NDF"]) & (values["LeadTrack_Idx"] >= 0))
        for values in data], dtype=np.int64)
    overlaps = np.zeros((3, masks.shape[2], 4), dtype=np.int64)
    # last axis: neither, first only, second only, both
    for pair, (left, right) in enumerate(PAIRS):
        code = masks[left].astype(np.int8) + 2*masks[right].astype(np.int8)
        for code_value in range(4):
            overlaps[pair, :, code_value] = (code == code_value).sum(axis=0)
    fiducial = 1 + [name for name, _ in cuts].index("Truth pz > 100 GeV")
    tracking = 1 + [name for name, _ in cuts].index("Leading track theta < 25 mrad")
    if not np.array_equal(masks[0, :, :fiducial+1], masks[1, :, :fiducial+1]) or not \
            np.array_equal(masks[0, :, :fiducial+1], masks[2, :, :fiducial+1]):
        raise RuntimeError("truth baseline differs")
    bins = {}
    for label, column, edges in [("energy", "truth_pz_nu", ENERGY_EDGES),
                                  ("radius", "truth_dec_r", RADIUS_EDGES)]:
        variable = data[0][column]
        denominator = masks[0, :, fiducial]
        bins[f"{label}_den"] = np.histogram(variable[denominator], edges)[0]
        hist = np.zeros((3, 3, len(edges)-1), dtype=np.int64)
        for mode in range(3):
            for j, stage in enumerate((fiducial+1, tracking, masks.shape[2]-1)):
                hist[mode, j] = np.histogram(variable[masks[mode, :, stage]], edges)[0]
        bins[f"{label}_pass"] = hist
    np.savez_compressed(output, counts=counts, overlaps=overlaps,
                        nonfinite_leading_quality=nonfinite_quality,
                        nontrack_columns=nontrack_columns, existing_merge_verified=old_verified,
                        fiducial_index=fiducial, tracking_index=tracking, **bins)
    print("counts", counts.tolist(), "existing_merge_verified", old_verified, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--forward", type=Path, required=True)
    parser.add_argument("--backward", type=Path, required=True)
    parser.add_argument("--merge", type=Path, required=True)
    parser.add_argument("--existing-merge", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=1)
    args = parser.parse_args()
    compare([args.forward, args.backward, args.merge], args.existing_merge,
            args.repo, args.output, args.threads)


if __name__ == "__main__":
    main()
