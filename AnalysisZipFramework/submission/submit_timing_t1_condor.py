#!/usr/bin/env python3
"""
HTCondor job packager and submitter for Stage T1 timing calibration (Pass 1 & Pass 2).

Groups Run 3 tasks deterministically within the same (year, reco_tag) so each job
runs a single RDataFrame event loop with zero schema mismatches. Stages binaries/configs
under ~/condor/nu_muAnalysis/stage212_timing_t1/<mode>/ and copies outputs via xrdcp
into EOS ntuples/timing_stage212/<mode>/.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import tarfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_DIR = Path("/eos/home-x/xcheng/FASER/nu_muAnalysis")
AFS_CONDOR_BASE = Path("/afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage212_timing_t1")
EOS_HOME_XRD_PREFIX = "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis"


def build_jobs(manifest_path: Path, target_gb: float, max_tasks_per_job: int) -> list[dict[str, Any]]:
    with open(manifest_path) as f:
        m = json.load(f)
    with open(m["source_dq_manifest"]) as f:
        dq = json.load(f)

    active_runs = m["runs"]
    grouped_tasks: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)

    for tid, tobj in sorted(dq["tasks"].items()):
        r_str = str(tobj["run"])
        if r_str not in active_runs:
            continue
        rmeta = active_runs[r_str]
        key = (int(rmeta["year"]), str(rmeta["reco_tag"]))
        grouped_tasks[key].append({
            "task_id": tid,
            "run": int(tobj["run"]),
            "bytes": int(tobj.get("bytes", 0)),
            "n_files": len(tobj.get("files", [])),
        })

    target_bytes = int(target_gb * 1e9)
    jobs: list[dict[str, Any]] = []
    job_idx = 0

    for (year, reco_tag), tlist in sorted(grouped_tasks.items()):
        # Sort by run, then task_id so a single run stays as contiguous as possible
        tlist.sort(key=lambda x: (x["run"], x["task_id"]))
        cur_tasks: list[dict[str, Any]] = []
        cur_bytes = 0
        for item in tlist:
            would_exceed = cur_tasks and (
                (cur_bytes + item["bytes"] > target_bytes) or
                (len(cur_tasks) >= max_tasks_per_job)
            )
            if would_exceed:
                jobs.append({
                    "job_id": f"job_{job_idx:04d}",
                    "year": year,
                    "reco_tag": reco_tag,
                    "task_ids": [t["task_id"] for t in cur_tasks],
                    "runs": sorted({t["run"] for t in cur_tasks}),
                    "bytes": cur_bytes,
                    "n_files": sum(t["n_files"] for t in cur_tasks),
                })
                job_idx += 1
                cur_tasks = []
                cur_bytes = 0
            cur_tasks.append(item)
            cur_bytes += item["bytes"]

        if cur_tasks:
            jobs.append({
                "job_id": f"job_{job_idx:04d}",
                "year": year,
                "reco_tag": reco_tag,
                "task_ids": [t["task_id"] for t in cur_tasks],
                "runs": sorted({t["run"] for t in cur_tasks}),
                "bytes": cur_bytes,
                "n_files": sum(t["n_files"] for t in cur_tasks),
            })
            job_idx += 1

    return jobs


def check_valid_root_output(args_tuple: tuple[str, str, str]) -> tuple[str, bool]:
    job_id, fpath, expected_tree = args_tuple
    p = Path(fpath)
    for attempt in range(3):
        if p.exists() and p.stat().st_size >= 1024:
            try:
                import uproot
                with uproot.open(fpath) as f:
                    if expected_tree in f and f[expected_tree].num_entries > 0:
                        return job_id, True
                return job_id, False
            except Exception:
                pass
        if attempt < 2:
            time.sleep(0.5 * (attempt + 1))
    return job_id, False


def write_worker_bundle(
    stage_dir: Path,
    mode: str,
    manifest_path: Path,
    ref_offsets_path: str | None,
) -> Path:
    with open(manifest_path) as f:
        m = json.load(f)
    local_m = dict(m)
    local_m["source_dq_manifest"] = "dq_manifest.json"

    tmp_m = stage_dir / "run3_timing_manifest.json"
    tmp_m.write_text(json.dumps(local_m, separators=(",", ":")))

    bundle_path = stage_dir / "bundle.tar.gz"
    with tarfile.open(bundle_path, "w:gz") as tar:
        tar.add(REPO_DIR / "build/timing_calib_scanner", arcname="timing_calib_scanner")
        tar.add(m["source_dq_manifest"], arcname="dq_manifest.json")
        tar.add(tmp_m, arcname="run3_timing_manifest.json")
        tar.add(REPO_DIR / "AnalysisZipFramework/config/grl_config_run3_full.yaml", arcname="grl_config_run3_full.yaml")
        if mode == "pass2":
            if not ref_offsets_path:
                raise RuntimeError("--ref-offsets is required for mode=pass2")
            tar.add(ref_offsets_path, arcname="ref_offsets_run3.json")

    return bundle_path


def write_runner_script(stage_dir: Path, mode: str) -> Path:
    ref_flag = "--ref-offsets ref_offsets_run3.json" if mode == "pass2" else ""
    out_url_dir = f"{EOS_HOME_XRD_PREFIX}/ntuples/timing_stage212/{mode}"
    script = f"""#!/usr/bin/env bash
set -eo pipefail
job_id="$1"
task_ids="${{2//+/,}}"
threads="$3"

scratch=$(mktemp -d "${{_CONDOR_SCRATCH_DIR:-/tmp}}/t1_{mode}.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
tar -xzf bundle.tar.gz -C "$scratch"
cd "$scratch"

set +u
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
set -u
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

/usr/bin/time -v ./timing_calib_scanner \\
    --mode {mode} \\
    --task-ids "$task_ids" \\
    --manifest run3_timing_manifest.json \\
    --grl-config grl_config_run3_full.yaml \\
    {ref_flag} \\
    --threads "$threads" \\
    --output out.root

dest_url="{out_url_dir}/${{job_id}}.root"
xrdcp --retry 3 --silent --force out.root "$dest_url"
echo "[DONE] ${{job_id}} -> ${{dest_url}}"
"""
    runner = stage_dir / f"run_{mode}.sh"
    runner.write_text(script)
    os.chmod(runner, 0o755)
    return runner


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit Stage T1 HTCondor jobs")
    parser.add_argument("--mode", choices=["pass1", "pass2"], required=True)
    parser.add_argument("--manifest", default=str(REPO_DIR / "AnalysisZipFramework/config/timing_calib/run3_timing_manifest.json"))
    parser.add_argument("--ref-offsets", default=str(REPO_DIR / "AnalysisZipFramework/config/timing_calib/ref_offsets_run3.json"))
    parser.add_argument("--target-gb", type=float, default=55.0)
    parser.add_argument("--max-tasks-per-job", type=int, default=12)
    parser.add_argument("--cpus", type=int, default=8)
    parser.add_argument("--memory-mb", type=int, default=5000)
    parser.add_argument("--flavour", default="microcentury")
    parser.add_argument("--limit", type=int, default=0, help="Optional cap on number of jobs to submit (for canary test)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workers", type=int, default=28)
    args = parser.parse_args()

    stage_dir = AFS_CONDOR_BASE / args.mode
    logs_dir = stage_dir / "logs"
    eos_out_dir = REPO_DIR / "ntuples/timing_stage212" / args.mode
    logs_dir.mkdir(parents=True, exist_ok=True)
    eos_out_dir.mkdir(parents=True, exist_ok=True)

    jobs_file = stage_dir / "jobs_plan.json"
    if jobs_file.exists():
        jobs = json.loads(jobs_file.read_text())
        print(f"[submit] Reusing existing {jobs_file} ({len(jobs)} jobs)")
    else:
        jobs = build_jobs(Path(args.manifest), args.target_gb, args.max_tasks_per_job)
        jobs_file.write_text(json.dumps(jobs, indent=2))
        print(f"[submit] Planned {len(jobs)} balanced jobs across {sum(len(j['task_ids']) for j in jobs)} tasks "
              f"({sum(j['bytes'] for j in jobs) / 1e12:.2f} TB)")

    expected_tree = "pass1_summary" if args.mode == "pass1" else "pass2_summary"
    check_items = [(j["job_id"], str(eos_out_dir / f"{j['job_id']}.root"), expected_tree) for j in jobs]
    valid_map: dict[str, bool] = {}
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as ex:
        for jid, ok in ex.map(check_valid_root_output, check_items, chunksize=16):
            valid_map[jid] = ok

    remaining = [j for j in jobs if not valid_map.get(j["job_id"], False)]
    n_done = len(jobs) - len(remaining)
    print(f"[submit] Status for {args.mode}: {n_done}/{len(jobs)} completed cleanly, {len(remaining)} remaining.")
    if not remaining:
        return

    if args.limit > 0:
        remaining = remaining[: args.limit]
        print(f"[submit] Limiting submission to {len(remaining)} canary job(s).")

    if args.dry_run:
        preview = ", ".join(j["job_id"] for j in remaining[:5])
        print(f"[submit] Dry-run only (bundle/args untouched): {len(remaining)} jobs would be submitted (first: {preview})")
        return

    bundle_path = write_worker_bundle(stage_dir, args.mode, Path(args.manifest), args.ref_offsets)
    runner_path = write_runner_script(stage_dir, args.mode)

    arg_lines = []
    for j in remaining:
        tids_plus = "+".join(j["task_ids"])
        arg_lines.append(f"{j['job_id']} {tids_plus} {args.cpus}")
    args_file = stage_dir / "pending_jobs.args"
    args_file.write_text("\n".join(arg_lines) + "\n")

    sub_text = f"""universe = vanilla
initialdir = {stage_dir}
executable = /bin/bash
transfer_executable = False
arguments = {runner_path.name} $(job_id) $(task_ids) $(threads)
should_transfer_files = YES
when_to_transfer_output = ON_EXIT
transfer_input_files = {runner_path},{bundle_path}
transfer_output_files = ""
MY.SendCredential = True
requirements = (OpSysAndVer =?= "AlmaLinux9")
request_cpus = {args.cpus}
request_memory = {args.memory_mb}M
request_disk = 2000M
max_retries = 2
+JobFlavour = "{args.flavour}"
+NuMuStage = "timing-t1-{args.mode}"
output = {logs_dir}/$(job_id)_$(ClusterId).out
error = {logs_dir}/$(job_id)_$(ClusterId).err
log = {logs_dir}/condor_{args.mode}.log
queue job_id, task_ids, threads from {args_file}
"""
    sub_file = stage_dir / f"timing_t1_{args.mode}.sub"
    sub_file.write_text(sub_text)

    if args.dry_run:
        print(f"[submit] Dry-run wrote {sub_file} ({len(remaining)} jobs, bundle={bundle_path.stat().st_size / 1e6:.2f} MB)")
        return

    p = subprocess.run(["condor_submit", str(sub_file)], cwd=str(stage_dir), capture_output=True, text=True)
    print(p.stdout)
    if p.returncode != 0:
        print(p.stderr, file=sys.stderr)
        raise SystemExit(p.returncode)


if __name__ == "__main__":
    main()
