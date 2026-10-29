#!/usr/bin/env python3
"""Inspect ROOT schemas and a bounded event prefix for energy-ML planning.

Writes metadata and aggregate diagnostics only; no event data are copied.
Values in profiles retain their input units. This is not a physics selection.
"""

import argparse
import csv
import json
import math
import platform
import resource
import statistics
import time
from collections import Counter
from pathlib import Path


PROFILE_COLUMNS = [
    "run", "eventID", "longTracks", "nClusters0", "nClusters1", "nClusters2",
    "nClusters3", "SpacePoints", "SpacePoint_x", "SpacePoint_y", "SpacePoint_z",
    "TrackSegments", "TrackSegment_x", "TrackSegment_y", "TrackSegment_z",
    "Track_p0", "Track_px0", "Track_py0", "Track_pz0", "Track_Chi2",
    "Track_nDoF", "Track_nLayers", "Track_nMeasurements", "Track_hitSet",
    "Track_charge", "Track_isForward", "truth_pdg", "truth_P", "truth_m",
    "truth_px", "truth_py", "truth_pz", "truth_dec_z", "GenWeights",
    "VetoNu0_reduced_charge", "VetoNu1_reduced_charge",
]
for detector in ["VetoNu0", "VetoNu1", "Veto10", "Veto11", "Veto20", "Veto21",
                 "Timing0", "Timing1", "Timing2", "Timing3", "Preshower0", "Preshower1"]:
    PROFILE_COLUMNS.extend(f"{detector}_{field}" for field in ["charge", "raw_charge", "status"])
for detector in ["Calo", "CaloNu", "CaloLo", "CaloHi"]:
    PROFILE_COLUMNS.extend(f"{detector}{channel}_{field}" for channel in range(4)
                           for field in ["charge", "E_EM", "E_dep", "status"])
    PROFILE_COLUMNS.extend(f"{detector}_total_{field}" for field in
                           ["E_EM", "E_dep", "nMIP", "E_EM_fudged"])


def role(name):
    if name.startswith(("truth", "t_")) or name in {"pTruthLepton", "isFiducial"}:
        return "truth_label_or_diagnostic_only"
    if name in {"run", "eventID", "eventTime", "eventTimeNSOffset", "BCID", "inGRL",
                "clockPhase", "fillNumber", "betaStar", "crossingAngle", "isVerticalCrossingAngle",
                "TBP", "TAP", "inputBits", "inputBitsNext", "GenWeights", "CrossSection"} or name.startswith("distanceTo"):
        return "metadata_or_weight_only"
    if "fudged" in name:
        return "mc_correction_review_required"
    return "candidate_requires_data_semantics_check"


def write_tsv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def inspect(ROOT, label, url, entry_limit):
    started = time.perf_counter()
    source = ROOT.TFile.Open(url)
    if not source or source.IsZombie():
        raise RuntimeError(f"Cannot open {label}: {url}")
    opened = time.perf_counter()
    tree = source.Get("nt")
    if not tree:
        source.Close()
        raise RuntimeError(f"Missing nt tree in {label}")
    branches = {branch.GetName(): branch for branch in tree.GetListOfBranches()}
    schema = []
    for name, branch in branches.items():
        leaves = branch.GetListOfLeaves()
        root_type = branch.GetClassName() or (leaves.At(0).GetTypeName() if leaves.GetEntries() else "unknown")
        schema.append(dict(sample=label, branch=name, root_type=root_type,
                           title=branch.GetTitle(), suggested_role=role(name)))
    columns = [name for name in PROFILE_COLUMNS if name in branches]
    # Activate only the profiled branches and alignment references.
    tree.SetBranchStatus("*", 0)
    for name in columns:
        tree.SetBranchStatus(name, 1)
    values = {name: [] for name in columns}
    lengths = {name: [] for name in columns if branches[name].GetClassName()}
    nonfinite = Counter()
    mismatches = Counter()
    checked = Counter()
    ids = set()
    duplicate_ids = 0
    count = min(entry_limit, tree.GetEntries())
    before_bytes = ROOT.TFile.GetFileBytesRead()
    before_calls = ROOT.TFile.GetFileReadCalls()
    for index in range(count):
        if tree.GetEntry(index) <= 0:
            source.Close()
            raise RuntimeError(f"Failed entry {index} in {label}")
        row_lengths = {}
        for name in columns:
            value = getattr(tree, name)
            if name in lengths:
                row_lengths[name] = len(value)
                lengths[name].append(len(value))
                elements = value
            else:
                elements = [value]
            for element in elements:
                number = float(element)
                if math.isfinite(number):
                    values[name].append(number)
                else:
                    nonfinite[name] += 1
        if "run" in columns and "eventID" in columns:
            event_key = (int(tree.run), int(tree.eventID))
            duplicate_ids += event_key in ids
            ids.add(event_key)
        for name in ["Track_p0", "Track_px0", "Track_py0", "Track_Chi2", "Track_nDoF",
                     "Track_nLayers", "Track_charge", "Track_nMeasurements", "Track_hitSet",
                     "Track_isForward"]:
            if name in row_lengths and "Track_pz0" in row_lengths:
                checked[name] += 1
                mismatches[name] += row_lengths[name] != row_lengths["Track_pz0"]
        if all(name in row_lengths for name in ["SpacePoint_x", "SpacePoint_y", "SpacePoint_z"]):
            checked["SpacePoint_xyz"] += 1
            mismatches["SpacePoint_xyz"] += len({row_lengths[name] for name in
                                                ["SpacePoint_x", "SpacePoint_y", "SpacePoint_z"]}) != 1
    scanned = time.perf_counter()
    scan_bytes = ROOT.TFile.GetFileBytesRead() - before_bytes
    scan_calls = ROOT.TFile.GetFileReadCalls() - before_calls
    profiles = []
    for name in columns:
        numbers = values[name]
        sizes = lengths.get(name, [])
        profiles.append(dict(sample=label, branch=name, sampled_events=count,
                             finite_values=len(numbers), nonfinite_values=nonfinite[name],
                             zero_values=sum(number == 0 for number in numbers),
                             minimum=min(numbers) if numbers else "",
                             median=statistics.median(numbers) if numbers else "",
                             maximum=max(numbers) if numbers else "",
                             empty_vectors=sum(size == 0 for size in sizes) if sizes else "",
                             max_vector_length=max(sizes) if sizes else "",
                             units="native; unit calibration not performed"))
    summary = dict(sample=label, input=url, entries=int(tree.GetEntries()),
                   branches=len(branches), profiled_branches=len(columns),
                   sampled_events=count, duplicate_ids_in_prefix=duplicate_ids,
                   open_wall_s=round(opened-started, 6),
                   scan_wall_s=round(scanned-opened, 6),
                   prefix_events_per_s=round(count/(scanned-opened), 3),
                   scan_read_bytes=int(scan_bytes), scan_read_calls=int(scan_calls),
                   alignment_checked_events=dict(checked),
                   alignment_mismatch_events={name: mismatches[name] for name in checked},
                   note="Unselected first entries; schema/pipeline evidence only. Counts are not physics yields.")
    source.Close()
    return schema, profiles, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", nargs=2, action="append", metavar=("LABEL", "ROOT_PATH"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--entries", type=int, default=128)
    parser.add_argument("--open-timeout-ms", type=int, default=15000)
    args = parser.parse_args()
    if args.entries < 1:
        parser.error("--entries must be positive")
    import ROOT
    ROOT.PyConfig.IgnoreCommandLineOptions = True
    ROOT.TFile.SetOpenTimeout(args.open_timeout_ms)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    schemas, profiles, summaries = [], [], []
    for label, url in args.input:
        schema, profile, summary = inspect(ROOT, label, url, args.entries)
        schemas.extend(schema)
        profiles.extend(profile)
        summaries.append(summary)
        print(json.dumps(summary, ensure_ascii=False), flush=True)
        # Preserve successful inspections even if a later input is inaccessible.
        write_tsv(args.output_dir/"schemas.tsv", schemas, list(schemas[0]))
        write_tsv(args.output_dir/"branch_profiles.tsv", profiles, list(profiles[0]))
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report = dict(root_version=ROOT.gROOT.GetVersion(), platform=platform.platform(),
                      peak_rss_mib=round(rss/(1024**2 if platform.system() == "Darwin" else 1024), 3),
                      samples=summaries)
        (args.output_dir/"audit_summary.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
