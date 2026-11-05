"""Stage120 provenance gate: metadata/log lineage only, no event or model work."""
import json
import os
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "workbook/stage120_energy_ml"
BASE = Path("/eos/experiment/fasernu-data0/faser/sim/mc24/genie")
RUNS = list(range(200131, 200137)) + list(range(200184, 200190))


def names(path):
    try:
        return sorted(x.name for x in os.scandir(path))
    except OSError:
        return []


def product_snapshot(run):
    root = BASE / str(run)
    out = {"run": run, "path": str(root), "exists": root.is_dir(), "products": {}}
    for product in ["bck", "phy", "rdo", "rec", "sim", "log"]:
        p = root / product
        entries = names(p)
        tags = {}
        for tag in entries:
            q = p / tag
            if not q.is_dir():
                continue
            files = names(q)
            tags[tag] = {
                "files": len(files),
                "first": files[:2],
                "last": files[-2:],
            }
        out["products"][product] = tags
    return out


def evidence_line(entry, prefix):
    for line in entry.get("lines", []):
        if line.get("text", "").startswith(prefix):
            return line["text"].split(": ", 1)[1]
    return None


def main():
    started = time.perf_counter()
    snapshots = [product_snapshot(r) for r in RUNS]
    evidence = json.loads((ROOT / "workbook/stage119_energy_ml/production_evidence.json").read_text())
    byrun = {x["run"]: x for x in evidence}
    log_rows = []
    for run in RUNS:
        e = byrun[run]
        generators = [x for x in e.get("evidence", []) if x.get("kind") == "generator"]
        rows = []
        for g in generators:
            rows.append({
                "path": g.get("path"),
                "input_file": evidence_line(g, "Input File:"),
                "output_file": evidence_line(g, "Output File:"),
                "release": evidence_line(g, "Release:"),
                "geometry": evidence_line(g, "Remaining:"),
                "events": evidence_line(g, "Nevts:"),
            })
        log_rows.append({"run": run, "log_files": e.get("log_files", 0), "generator_evidence": rows})

    c187 = next((x for x in log_rows if x["run"] == 200187), None)
    c188 = next((x for x in log_rows if x["run"] == 200188), None)
    input187 = {x["input_file"] for x in c187["generator_evidence"] if x["input_file"]}
    input188 = {x["input_file"] for x in c188["generator_evidence"] if x["input_file"]}
    k_lineage = {
        "run_200187_generator_inputs": sorted(input187),
        "run_200188_generator_inputs": sorted(input188),
        "same_generator_input_sets": input187 == input188 and bool(input187),
        "interpretation": "200187 and 200188 both point to epos-k-1 EVNT in the retained logs; run-number/c2 naming does not certify an independent K family.",
    }
    expansion = [x for x in log_rows if x["run"] in range(200131, 200137)]
    gate = {
        "expansion_runs_with_generator_logs": sum(bool(x["generator_evidence"]) for x in expansion),
        "expansion_runs_with_any_log_files": sum(x["log_files"] > 0 for x in expansion),
        "expansion_producer_certified": False,
        "reason": "200131-136 log directories contain no retained logs; filename/product metadata confirms products but not producer release, EVNT entry, seed, or parent identity.",
        "k_200187_188_independent_certified": False,
        "k_reason": "retained generator evidence resolves both runs to the same epos-k-1 EVNT input set; no independent family claim allowed.",
    }
    # Keep this gate diagnostic-only: there is no event loading and no model risk.
    result = {
        "stage": 120,
        "scope": "metadata and retained log provenance only; no ROOT/event arrays, training, inference, or statistical fit",
        "runs": RUNS,
        "snapshots": snapshots,
        "log_evidence": log_rows,
        "k_lineage": k_lineage,
        "gate": gate,
        "elapsed_s": time.perf_counter() - started,
        "source_stage119_evidence": "workbook/stage119_energy_ml/production_evidence.json",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "provenance_audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ["stage", "gate", "elapsed_s"]}, indent=2))


if __name__ == "__main__":
    main()
