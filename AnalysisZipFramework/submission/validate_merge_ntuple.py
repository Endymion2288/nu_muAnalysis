#!/usr/bin/env python3
"""Check event preservation and usable merge tracks; print compact job evidence."""

import argparse
from collections import Counter
import math
from pathlib import Path
import re

import ROOT


def open_tree(path, name):
    source = ROOT.TFile.Open(str(path))
    if not source or source.IsZombie() or source.TestBit(ROOT.TFile.kRecovered):
        raise RuntimeError(f"unreadable or recovered ROOT file: {path}")
    tree = source.Get(name)
    if not tree:
        raise RuntimeError(f"missing tree {name}: {path}")
    return source, tree


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rdo", type=Path, required=True)
    parser.add_argument("--xaod", type=Path)
    parser.add_argument("--ntuple", type=Path, required=True)
    parser.add_argument("--nevents", type=int, default=-1)
    parser.add_argument("--logs", type=Path, nargs="*", default=[])
    args = parser.parse_args()

    rdo, input_tree = open_tree(args.rdo, "CollectionTree")
    expected = input_tree.GetEntries()
    if args.nevents > 0:
        expected = min(expected, args.nevents)
    if args.xaod:
        xaod, reco_tree = open_tree(args.xaod, "CollectionTree")
        if reco_tree.GetEntries() != expected:
            raise RuntimeError(f"reconstruction event loss: {reco_tree.GetEntries()} != {expected}")
        xaod.Close()
    output, tree = open_tree(args.ntuple, "nt")
    if tree.GetEntries() != expected or expected == 0:
        raise RuntimeError(f"ntuple event count: {tree.GetEntries()} != {expected}")

    columns = ["Track_px0", "Track_py0", "Track_pz0", "Track_x0", "Track_y0", "Track_z0",
               "Track_Chi2", "Track_nDoF", "Track_isForward", "Track_nMeasurements"]
    tree.SetBranchStatus("*", False)
    for column in columns:
        if not tree.GetBranch(column):
            raise RuntimeError(f"missing branch {column}")
        tree.SetBranchStatus(column, True)
    for column in ("run", "eventID"):
        tree.SetBranchStatus(column, True)
    counts = Counter()
    quality_examples = []
    for event in tree:
        size = len(event.Track_pz0)
        counts["tracks"] += size
        counts["events_with_tracks"] += int(size > 0)
        counts["forward"] += sum(bool(x) for x in event.Track_isForward)
        counts["backward"] += sum(not x for x in event.Track_isForward)
        # Official master fills this field before station selection. Record the
        # known discrepancy without treating it as a corruption of fitted tracks.
        counts["measurement_length_mismatch_events"] += int(len(event.Track_nMeasurements) != size)
        for column in columns[:-1]:
            values = getattr(event, column)
            if len(values) != size:
                raise RuntimeError(f"track vector mismatch in entry {tree.GetReadEntry()}: {column}")
            if any(not math.isfinite(float(x)) for x in values):
                raise RuntimeError(f"nonfinite {column} in entry {tree.GetReadEntry()}")
        # The official CKF can retain underconstrained fallback candidates.
        # Preserve its output; physics quality cuts belong to the analysis.
        for index, ndof in enumerate(event.Track_nDoF):
            if ndof <= 0:
                counts["nonpositive_ndof_tracks"] += 1
                if len(quality_examples) < 5:
                    quality_examples.append((int(event.run), int(event.eventID), index,
                                             float(ndof), float(event.Track_Chi2[index])))
    print(f"validated entries={expected} branches={tree.GetListOfBranches().GetEntries()} "
          f"bytes={args.ntuple.stat().st_size} {dict(counts)}", flush=True)
    if quality_examples:
        print(f"nonpositive_ndof_examples(run,eventID,track,ndof,chi2)={quality_examples}")

    for path in args.logs:
        levels = Counter()
        fpe = Counter()
        examples = {level: [] for level in ("WARNING", "ERROR", "FATAL")}
        fpe_totals = {}
        for line in path.open(errors="replace"):
            match = re.search(r"\b(WARNING|ERROR|FATAL)\b", line)
            if match:
                level = match.group(1)
                levels[level] += 1
                if len(examples[level]) < 5:
                    examples[level].append(line.strip())
            match = re.search(r"FPE INVALID in \[Execute\] of \[([^\]]+)\]", line)
            if match:
                fpe[match.group(1)] += 1
            match = re.search(r"FPE (OVERFLOW|INVALID|DIVBYZERO)s\s*:\s*(\d+)", line)
            if match:
                fpe_totals[match.group(1)] = int(match.group(2))
        print(f"log={path} levels={dict(levels)} FPE_totals={fpe_totals} "
              f"FPE_INVALID_components={dict(fpe)}")
        for lines in examples.values():
            for line in lines:
                print(line)
    output.Close()
    rdo.Close()


if __name__ == "__main__":
    main()
