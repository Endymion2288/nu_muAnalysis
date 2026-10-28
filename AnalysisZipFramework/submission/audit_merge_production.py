#!/usr/bin/env python3
"""Audit published merge ntuples against RDO counts with bounded I/O parallelism."""

import argparse
import ast
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import csv
import json
from pathlib import Path
import re
import time


def audit(item):
    import awkward as ak
    import numpy as np
    import ROOT
    import uproot

    index, fields, cluster, proc = item
    run, tag, geometry, rdo, output, first, last = fields
    result = dict(index=index, run=run, output=output, status="ok", error="")
    try:
        repo = Path(__file__).resolve().parents[2]
        worker_log = repo / "logs" / f"ntuple_merge_{cluster}.{proc}.out"
        log_text = worker_log.read_text()
        result["worker_commit_verified"] = int(
            "code_commit=d32b0ff3cc4a2dad4abfb1474a82422c3c25b305" in log_text
            and "tracked_source_changes=none" in log_text)
        result["worker_publication_confirmed"] = int(f"completed output={output} " in log_text)
        for stage in ("stage_rdo", "reco", "ntuple"):
            match = re.search(rf"^{stage} wall_seconds=([\d.]+) max_rss_kib=(\d+)",
                              log_text, re.MULTILINE)
            if match:
                result[f"{stage}_seconds"] = float(match[1])
                result[f"{stage}_rss_kib"] = int(match[2])
        for stage, levels in re.findall(r"log=(reco|ntuple).log levels=(\{[^\n]+?\})", log_text):
            for level, count in ast.literal_eval(levels).items():
                result[f"{stage}_{level.lower()}_lines"] = count
        for stage, fpe in re.findall(
                r"log=(reco|ntuple).log .*?FPE_totals=(\{[^\n]+?\})", log_text):
            for category, count in ast.literal_eval(fpe).items():
                result[f"{stage}_fpe_{category.lower()}"] = count
        with uproot.open(rdo) as source:
            result["input_events"] = source["CollectionTree"].num_entries
        if not Path(output).is_file():
            raise RuntimeError("missing output")
        result["bytes"] = Path(output).stat().st_size
        root_file = ROOT.TFile.Open(output)
        if not root_file or root_file.IsZombie() or root_file.TestBit(ROOT.TFile.kRecovered):
            raise RuntimeError("unreadable or recovered ROOT output")
        root_file.Close()
        with uproot.open(output) as source:
            tree = source["nt"]
            result["events"] = tree.num_entries
            result["branches"] = len(tree.keys())
            result["schema"] = tree.typenames()
            if tree.num_entries != result["input_events"] or tree.num_entries == 0:
                raise RuntimeError("event count does not match RDO")
            numeric = [f"Track_{x}" for x in
                       ("px0", "py0", "pz0", "x0", "y0", "z0", "Chi2", "nDoF")]
            columns = numeric + ["Track_isForward", "Track_nMeasurements", "Track_nLayers",
                                 "run", "eventID"]
            totals = Counter()
            seen = set()
            for arrays in tree.iterate(columns, step_size="32 MB", library="ak"):
                size = ak.num(arrays.Track_pz0)
                totals["tracks"] += int(ak.sum(size))
                totals["events_with_tracks"] += int(ak.sum(size > 0))
                totals["forward"] += int(ak.sum(arrays.Track_isForward))
                totals["backward"] += int(ak.sum(~arrays.Track_isForward))
                totals["measurement_mismatch_events"] += int(ak.sum(
                    ak.num(arrays.Track_nMeasurements) != size))
                for col in numeric + ["Track_isForward", "Track_nLayers"]:
                    if ak.any(ak.num(arrays[col]) != size):
                        raise RuntimeError(f"vector length mismatch: {col}")
                totals["nonfinite_tracks"] += int(ak.sum(
                    sum(ak.values_astype(~np.isfinite(arrays[c]), np.int32)
                        for c in numeric) > 0))
                totals["nonpositive_ndof"] += int(ak.sum(arrays.Track_nDoF <= 0))
                safe_ndof = ak.where(arrays.Track_nDoF > 0, arrays.Track_nDoF, np.nan)
                good = ((arrays.Track_nLayers >= 7) & (arrays.Track_nDoF >= 9)
                        & np.isfinite(arrays.Track_Chi2)
                        & (arrays.Track_Chi2 / safe_ndof < 15)
                        & (arrays.Track_pz0 > 100000))
                totals["quality_tracks"] += int(ak.sum(good))
                totals["quality_forward"] += int(ak.sum(good & arrays.Track_isForward))
                totals["quality_backward"] += int(ak.sum(good & ~arrays.Track_isForward))
                totals["events_with_quality_tracks"] += int(ak.sum(ak.any(good, axis=1)))
                if ak.any(arrays.run != int(run)):
                    raise RuntimeError("run number mismatch")
                ids = ak.to_list(arrays.eventID)
                if len(set(ids)) != len(ids) or seen.intersection(ids):
                    raise RuntimeError("duplicate eventID within file")
                seen.update(ids)
            result.update(totals)
            match = re.search(r"validated entries=(\d+) branches=(\d+) bytes=(\d+) (\{.*\})",
                              log_text)
            if not match:
                raise RuntimeError("missing worker validation evidence")
            original = ast.literal_eval(match[4])
            if int(match[1]) != result["events"] or any(
                    original[key] != totals[key] for key in
                    ("tracks", "events_with_tracks", "forward", "backward")):
                raise RuntimeError("independent audit differs from worker counts")
            if not result["worker_commit_verified"] or not result["worker_publication_confirmed"]:
                raise RuntimeError("worker provenance/publication evidence missing")
            result["event_id_min"] = min(seen)
            result["event_id_max"] = max(seen)
            result["event_ids_in_segments"] = int(
                min(seen) >= int(first) * 1000 and max(seen) < (int(last) + 1) * 1000)
            if totals["nonfinite_tracks"]:
                raise RuntimeError("nonfinite fitted-track values")
    except Exception as error:
        result.update(status="failed", error=str(error))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--indices", type=int, nargs="+")
    parser.add_argument("--main-cluster", type=int, default=1532700)
    parser.add_argument("--retry", action="append", default=["44=1532712.0"],
                        help="Override worker evidence: manifest_index=cluster.proc")
    args = parser.parse_args()
    start = time.monotonic()
    rows = [line.split("\t") for line in args.manifest.read_text().splitlines()]
    if args.limit:
        rows = rows[:args.limit]
    retry = {int(spec.split("=")[0]): tuple(map(int, spec.split("=")[1].split(".")))
             for spec in args.retry}
    items = [(index, row, *retry.get(index, (args.main_cluster, index)))
             for index, row in enumerate(rows)
             if args.indices is None or index in args.indices]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(audit, items, chunksize=1))
    reference = next((r["schema"] for r in results if "schema" in r), None)
    for result in results:
        schema = result.pop("schema", None)
        if schema is not None and schema != reference:
            result.update(status="failed", error="schema differs from reference")
    fields = list(dict.fromkeys(key for result in results for key in result))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as target:
        writer = csv.DictWriter(target, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: result.get(key, "NA") for key in fields} for result in results)
    summary = {}
    for run in sorted({r["run"] for r in results}):
        records = [r for r in results if r["run"] == run]
        totals = Counter()
        for record in records:
            totals["files"] += 1
            totals["passed"] += record["status"] == "ok"
            for key, value in record.items():
                if key not in ("index", "run", "branches", "event_id_min", "event_id_max") \
                        and isinstance(value, int):
                    totals[key] += value
        summary[run] = dict(totals)
    print(json.dumps(dict(by_run=summary, wall_seconds=round(time.monotonic()-start, 2),
                          failures=[r for r in results if r["status"] != "ok"]),
                     ensure_ascii=False), flush=True)
    return int(any(r["status"] != "ok" for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
