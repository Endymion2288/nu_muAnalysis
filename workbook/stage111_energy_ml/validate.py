#!/usr/bin/env python3
"""Check Stage111 text/metadata and copied evidence; never open event payloads."""
import csv
import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
BASE = "1bb5c51"


def load(path):
    return json.loads((REPO / path).read_text())


def historical(path):
    return subprocess.check_output(["git", "show", f"{BASE}:{path}"], cwd=REPO)


def main():
    evidence = list(csv.DictReader((OUT / "evidence.tsv").open(), delimiter="\t"))
    sources = {}
    for row in evidence:
        path = row["source"]
        if path not in sources:
            sources[path] = (load(path) if path.endswith(".json") else
                             list(csv.DictReader((REPO / path).open(), delimiter="\t")))
        value = sources[path]
        selector = json.loads(row["selector"])
        if "json_path" in selector:
            for key in filter(None, selector["json_path"].split(".")):
                value = value[key]
        else:
            matches = [v for v in value if all(v[k] == x for k, x in selector.items())]
            assert len(matches) == 1, row
            value = matches[0]
        expected = value[row["field"]]
        if isinstance(expected, bool):
            assert row["value"] == str(expected), row
        else:
            assert float(row["value"]) == float(expected), row
    assert len(evidence) == 55

    manifest = load("workbook/stage111_energy_ml/source_manifest.json")
    reference = load(manifest["reference"])
    assert reference["test_payload"] is False
    assert len(manifest["files"]) == 6
    for source in manifest["files"]:
        expected = min((v for v in reference["sources"]
                        if v["component"] == source["component"] and v["role"] == source["role"]),
                       key=lambda v: (v["origin"], v["source_index"]))
        assert all(source[k] == v for k, v in expected.items())
        assert source["role"] in (1, 2)
        assert source["exists_at_design"] is True
        assert Path(source["input"]).stat().st_size == source["logical_bytes_at_design"]
    assert sum(v["logical_bytes_at_design"] for v in manifest["files"]) == manifest["total_logical_bytes"] == 275663702

    contract = load("workbook/stage111_energy_ml/experiment_contract.json")
    assert contract["stage"] == 112 and contract["status"] == "frozen_design_not_executed"
    assert contract["uncertainty"]["draws"] == 500
    assert contract["resources"]["request_cpus"] == contract["resources"]["workers"] == 6
    assert contract["resources"]["request_gpus"] == 0
    assert contract["no_source_replacement"] is True

    roadmap = "docs/nu_mu_energy_ml_revised_roadmap.md"
    information = "docs/nu_mu_energy_ml_information_budget_plan.md"
    handoff = "docs/nu_mu_energy_ml_next_step_prompt.md"
    for path, heading in [(roadmap, b"\n## 93."), (information, b"\n## 73.")]:
        current = (REPO / path).read_bytes()
        old = historical(path)
        assert current.startswith(old)
        assert heading in current[len(old):]
    marker = "## 保留的stage54 data占据支线".encode()
    old, current = historical(handoff), (REPO / handoff).read_bytes()
    assert current[current.index(marker):] == old[old.index(marker):]

    report = "workbook/2026-11-05_stage111_selection-response-reassessment.md"
    checked_links = 0
    for path in [report, handoff]:
        text = (REPO / path).read_text()
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if target.startswith(("https://", "http://", "#")):
                continue
            target = target.split("#", 1)[0]
            assert ((REPO / path).parent / target).exists(), (path, target)
            checked_links += 1
    for path in [roadmap, information]:
        appended = (REPO / path).read_bytes()[len(historical(path)):].decode()
        for target in re.findall(r"\]\(([^)]+)\)", appended):
            assert ((REPO / path).parent / target).exists(), (path, target)
            checked_links += 1

    literature = list(csv.DictReader((OUT / "literature.tsv").open(), delimiter="\t"))
    assert len(literature) == 7 and len({v["url"] for v in literature}) == 7
    metadata = load("workbook/stage111_energy_ml/literature_metadata.json")
    titles = {v["arxiv"]: v["citation_title"][0] for v in metadata["results"]}
    for row in literature:
        match = re.search(r"(\d{4}\.\d{4,5})", row["url"])
        if match:
            assert row["title"] == titles[match[1]], row

    preserved = ["AnalysisZipFramework/submission/ml_tracker_occupancy_prepare.sub",
                 "AnalysisZipFramework/submission/run_ml_tracker_occupancy_prepare.sh",
                 "ml/prepare_tracker_occupancy.py", "ntuples/energy_ml_stage54/",
                 "workbook/stage54_energy_ml/"]
    for path in preserved:
        assert (REPO / path).exists(), path
    subprocess.run(["git", "diff", "--check"], cwd=REPO, check=True)
    result = dict(passed=True, baseline_commit=BASE, evidence_fields_exact=len(evidence),
                  manifest_sources=6, metadata_logical_bytes=manifest["total_logical_bytes"],
                  source_rule_and_stat_checked=True, historical_prefixes_preserved=2,
                  stage54_suffix_exact=True, stage54_assets_present=preserved,
                  local_links_checked=checked_links, literature_entries=7,
                  arxiv_title_metadata_matches=6, diff_check=True,
                  new_event_reads=0, new_model_fits=0, new_forwards=0,
                  new_batch_jobs=0, experiment_stage112_executed=False,
                  note="Validation reads only text/CSV/JSON, git history and file metadata; resource cost and new physics effects unmeasured.")
    (OUT / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
