#!/usr/bin/env python3
"""
HTCondor packager and submitter for Stage T4 (Stage 215) orthogonal blinded
background extraction across Run 3 Data, 2024_cos, FLUKA mu MC, and GENIE MC.

Modes:
  data   : All 1,354 GRL physics tasks across 717 Run 3 runs (30.83 TB, 2022-2026),
           strictly enforced by TimingBlindingGuard (zero SR-ZoneB inspection).
  fluka  : All 19 FLUKA bck MC datasets (1,813 PHYS files, mc22 + mc24).
  genie  : 12 GENIE MC runs (9 nominal 30 ab^-1 FTFP_BERT + 3 master_dev 2024_CaloNu)
           for exact sideband neutrino contamination accounting.
  cosmic : All 2,217 2024_cos cosmic-ray PHYS files.
  all    : Plan and submit all four modes cleanly.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import glob
import json
import os
import subprocess
import sys
import tarfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_DIR = Path("/eos/home-x/xcheng/FASER/nu_muAnalysis")
AFS_CONDOR_BASE = Path("/afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage215_timing_t4")
EOS_HOME_XRD_PREFIX = "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis"

GENIE_T4_RUNS = [
    # Nominal 30 ab^-1 FTFP_BERT triplets (2022_2023, 2024_noCaloNu, 2024_CaloNu s0015)
    200082, 200083, 200089,
    200093, 200094, 200100,
    200139, 200140, 200146,
    # Homogeneous master_dev 2024_CaloNu triplet (FTF_BIC) for CaloNu tag cross-check
    200172, 200173, 200174,
]


def _chunk_list(items: list[str], chunk_size: int) -> list[list[str]]:
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def build_data_jobs(manifest_path: Path, target_gb: float, max_tasks_per_job: int) -> list[dict[str, Any]]:
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
                    "job_id": f"data_{job_idx:04d}",
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
                "job_id": f"data_{job_idx:04d}",
                "year": year,
                "reco_tag": reco_tag,
                "task_ids": [t["task_id"] for t in cur_tasks],
                "runs": sorted({t["run"] for t in cur_tasks}),
                "bytes": cur_bytes,
                "n_files": sum(t["n_files"] for t in cur_tasks),
            })
            job_idx += 1
    return jobs


def build_fluka_jobs(manifest_path: Path, files_per_job: int) -> list[dict[str, Any]]:
    m = json.loads(manifest_path.read_text())
    jobs: list[dict[str, Any]] = []
    idx = 0
    for k, _ in sorted(m["fluka_mc_datasets"].items()):
        mc_era, _, rstr = k.split("_")
        files = [
            p for p in sorted(glob.glob(f"/eos/experiment/faser/sim/{mc_era}/fluka/{rstr}/bck/s001*-r0019/*-PHYS.root"))
            if os.path.isfile(p) and p.endswith("-PHYS.root")
        ]
        if not files:
            continue
        csize = 2 if mc_era == "mc22" else files_per_job
        for part_i, chunk in enumerate(_chunk_list(files, csize)):
            jobs.append({
                "job_id": f"fluka_{idx:04d}",
                "era": mc_era,
                "run": int(rstr),
                "part": part_i,
                "n_files": len(chunk),
                "files": chunk,
            })
            idx += 1
    return jobs


def build_genie_jobs(manifest_path: Path, files_per_job: int) -> list[dict[str, Any]]:
    m = json.loads(manifest_path.read_text())
    jobs: list[dict[str, Any]] = []
    idx = 0
    for r in GENIE_T4_RUNS:
        robj = m["genie_mc_runs"].get(str(r))
        if not robj:
            raise RuntimeError(f"GENIE run {r} missing from manifest")
        pat = robj["glob"].replace("root://eospublic.cern.ch/", "")
        files = [
            p for p in sorted(glob.glob(pat))
            if os.path.isfile(p) and p.endswith("-PHYS.root")
        ]
        if not files:
            raise RuntimeError(f"No PHYS.root files found for GENIE run {r} ({pat})")
        for part_i, chunk in enumerate(_chunk_list(files, files_per_job)):
            jobs.append({
                "job_id": f"genie_{idx:04d}",
                "run": r,
                "part": part_i,
                "n_files": len(chunk),
                "files": chunk,
            })
            idx += 1
    return jobs


def build_cosmic_jobs(files_per_job: int) -> list[dict[str, Any]]:
    files = sorted(glob.glob("/eos/experiment/faser/data0/phys/2024_cos/r0022-r0023/*/*-PHYS.root"))
    if not files:
        raise RuntimeError("No 2024_cos PHYS.root files found")
    jobs: list[dict[str, Any]] = []
    for idx, chunk in enumerate(_chunk_list(files, files_per_job)):
        jobs.append({
            "job_id": f"cosmic_{idx:04d}",
            "part": idx,
            "n_files": len(chunk),
            "files": chunk,
        })
    return jobs


def check_valid_root_output(args_tuple: tuple[str, str, str, bool]) -> tuple[str, bool]:
    job_id, fpath, xrd_url, use_xrd = args_tuple
    p = Path(fpath)
    target = fpath if (p.exists() and p.stat().st_size >= 1024) else (xrd_url if use_xrd else "")
    if not target:
        return job_id, False
    for attempt in range(3):
        try:
            import uproot
            with uproot.open(target) as f:
                if "t4_run_summary" in f and f["t4_run_summary"].num_entries > 0:
                    return job_id, True
            return job_id, False
        except Exception:
            if attempt < 2:
                time.sleep(0.4 * (attempt + 1))
    return job_id, False


def write_worker_bundle(stage_dir: Path, mode: str, manifest_path: Path, jobs: list[dict[str, Any]]) -> Path:
    bundle_path = stage_dir / "bundle.tar.gz"
    with tarfile.open(bundle_path, "w:gz") as tar:
        tar.add(REPO_DIR / "build/t4_bkg_scanner", arcname="t4_bkg_scanner")
        calib_dir = REPO_DIR / "AnalysisZipFramework/config/timing_calib"
        for fn in ("ref_offsets_run3.json", "tof_maps_run3.json", "mc_timing_calib.json"):
            tar.add(calib_dir / fn, arcname=f"timing_calib/{fn}")

        if mode == "data":
            m = json.loads(manifest_path.read_text())
            local_m = dict(m)
            local_m["source_dq_manifest"] = "dq_manifest.json"
            tmp_m = stage_dir / "run3_timing_manifest.json"
            tmp_m.write_text(json.dumps(local_m, separators=(",", ":")))
            tar.add(m["source_dq_manifest"], arcname="dq_manifest.json")
            tar.add(tmp_m, arcname="run3_timing_manifest.json")
            tar.add(REPO_DIR / "AnalysisZipFramework/config/grl_config_run3_full.yaml", arcname="grl_config_run3_full.yaml")
        else:
            list_dir = stage_dir / "file_lists"
            list_dir.mkdir(parents=True, exist_ok=True)
            for j in jobs:
                (list_dir / f"{j['job_id']}.txt").write_text("\n".join(j["files"]) + "\n")
            tar.add(list_dir, arcname="file_lists")
    return bundle_path


def write_runner_script(stage_dir: Path, mode: str) -> Path:
    out_url_dir = f"{EOS_HOME_XRD_PREFIX}/ntuples/timing_stage215/{mode}"
    if mode == "data":
        cmd_block = """task_ids="${arg2//+/,}"
/usr/bin/time -v ./t4_bkg_scanner \\
    --task-ids "$task_ids" \\
    --manifest run3_timing_manifest.json \\
    --grl-config grl_config_run3_full.yaml \\
    --timing-calib timing_calib \\
    --threads "$threads" \\
    --output out.root"""
    else:
        extra_flag = "--is-mc" if mode == "fluka" else ("--is-genie" if mode == "genie" else "--is-cosmic")
        cmd_block = f"""/usr/bin/time -v ./t4_bkg_scanner \\
    --input-list "file_lists/${{job_id}}.txt" \\
    --timing-calib timing_calib \\
    {extra_flag} \\
    --threads "$threads" \\
    --output out.root"""

    script = f"""#!/usr/bin/env bash
set -eo pipefail
job_id="$1"
arg2="$2"
threads="$3"

scratch=$(mktemp -d "${{_CONDOR_SCRATCH_DIR:-/tmp}}/t4_{mode}.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
tar -xzf bundle.tar.gz -C "$scratch"
cd "$scratch"

set +u
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
set -u
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

{cmd_block}

dest_url="{out_url_dir}/${{job_id}}.root"
xrdcp --retry 3 --silent --force out.root "$dest_url"
echo "[DONE] ${{job_id}} -> ${{dest_url}}"
"""
    runner = stage_dir / f"run_{mode}.sh"
    runner.write_text(script)
    os.chmod(runner, 0o755)
    return runner


def run_one_mode(mode: str, args: argparse.Namespace) -> None:
    manifest_path = Path(args.manifest)
    stage_dir = AFS_CONDOR_BASE / mode
    logs_dir = stage_dir / "logs"
    eos_out_dir = REPO_DIR / "ntuples/timing_stage215" / mode
    logs_dir.mkdir(parents=True, exist_ok=True)
    eos_out_dir.mkdir(parents=True, exist_ok=True)

    jobs_file = stage_dir / "jobs_plan.json"
    if jobs_file.exists():
        jobs = json.loads(jobs_file.read_text())
        print(f"[T4 submit:{mode}] Reusing {jobs_file} ({len(jobs)} jobs)")
    else:
        if mode == "data":
            jobs = build_data_jobs(manifest_path, args.target_gb, args.max_tasks_per_job)
        elif mode == "fluka":
            jobs = build_fluka_jobs(manifest_path, args.fluka_files_per_job)
        elif mode == "genie":
            jobs = build_genie_jobs(manifest_path, args.genie_files_per_job)
        else:
            jobs = build_cosmic_jobs(args.cosmic_files_per_job)
        jobs_file.write_text(json.dumps(jobs, indent=2))
        print(f"[T4 submit:{mode}] Planned {len(jobs)} jobs covering {sum(j['n_files'] for j in jobs)} PHYS files.")

    xrd_present: set[str] = set()
    res_ls = subprocess.run(
        ["xrdfs", "eoshome-x.cern.ch", "ls", f"/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/timing_stage215/{mode}"],
        capture_output=True, text=True,
    )
    if res_ls.returncode == 0:
        xrd_present = {Path(line.strip()).stem for line in res_ls.stdout.splitlines() if line.strip().endswith(".root")}

    check_items = [
        (
            j["job_id"],
            str(eos_out_dir / f"{j['job_id']}.root"),
            f"{EOS_HOME_XRD_PREFIX}/ntuples/timing_stage215/{mode}/{j['job_id']}.root",
            j["job_id"] in xrd_present,
        )
        for j in jobs
    ]
    valid_map: dict[str, bool] = {}
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as ex:
        for jid, ok in ex.map(check_valid_root_output, check_items, chunksize=16):
            valid_map[jid] = ok

    remaining = [j for j in jobs if not valid_map.get(j["job_id"], False)]
    print(f"[T4 submit:{mode}] Status: {len(jobs) - len(remaining)}/{len(jobs)} completed cleanly, {len(remaining)} remaining.")
    if not remaining:
        return

    if args.limit > 0:
        remaining = remaining[: args.limit]
    if args.dry_run:
        print(f"[T4 submit:{mode}] Dry-run only: would submit {len(remaining)} jobs (first: {[j['job_id'] for j in remaining[:5]]})")
        return

    bundle_path = write_worker_bundle(stage_dir, mode, manifest_path, remaining)
    runner_path = write_runner_script(stage_dir, mode)

    cpus = args.cosmic_cpus if mode == "cosmic" else args.cpus
    mem_mb = args.cosmic_memory_mb if mode == "cosmic" else args.memory_mb

    arg_lines = []
    for j in remaining:
        a2 = "+".join(j["task_ids"]) if mode == "data" else str(j["run"]) if "run" in j else "cos"
        arg_lines.append(f"{j['job_id']} {a2} {cpus}")
    args_file = stage_dir / "pending_jobs.args"
    args_file.write_text("\n".join(arg_lines) + "\n")

    sub_text = f"""universe = vanilla
initialdir = {stage_dir}
executable = /bin/bash
transfer_executable = False
arguments = {runner_path.name} $(job_id) $(arg2) $(threads)
should_transfer_files = YES
when_to_transfer_output = ON_EXIT
transfer_input_files = {runner_path},{bundle_path}
transfer_output_files = ""
MY.SendCredential = True
requirements = (OpSysAndVer =?= "AlmaLinux9")
request_cpus = {cpus}
request_memory = {mem_mb}M
request_disk = 2000M
max_retries = 2
+JobFlavour = "{args.flavour}"
+NuMuStage = "timing-t4-{mode}"
output = {logs_dir}/$(job_id)_$(ClusterId).out
error = {logs_dir}/$(job_id)_$(ClusterId).err
log = {logs_dir}/condor_{mode}.log
queue job_id, arg2, threads from {args_file}
"""
    sub_file = stage_dir / f"timing_t4_{mode}.sub"
    sub_file.write_text(sub_text)
    print(f"[T4 submit:{mode}] Bundle size: {bundle_path.stat().st_size / (1024.0 * 1024.0):.2f} MB")

    res = subprocess.run(["condor_submit", str(sub_file)], cwd=str(stage_dir), capture_output=True, text=True)
    print(res.stdout.strip())
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr)
        raise SystemExit(res.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit Stage T4 HTCondor jobs")
    parser.add_argument("--mode", choices=["data", "fluka", "genie", "cosmic", "all"], required=True)
    parser.add_argument("--manifest", default=str(REPO_DIR / "AnalysisZipFramework/config/timing_calib/run3_timing_manifest.json"))
    parser.add_argument("--target-gb", type=float, default=50.0)
    parser.add_argument("--max-tasks-per-job", type=int, default=12)
    parser.add_argument("--fluka-files-per-job", type=int, default=35)
    parser.add_argument("--genie-files-per-job", type=int, default=20)
    parser.add_argument("--cosmic-files-per-job", type=int, default=200)
    parser.add_argument("--cpus", type=int, default=4)
    parser.add_argument("--memory-mb", type=int, default=4000)
    parser.add_argument("--cosmic-cpus", type=int, default=2)
    parser.add_argument("--cosmic-memory-mb", type=int, default=2500)
    parser.add_argument("--flavour", default="microcentury")
    parser.add_argument("--workers", type=int, default=28)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    modes = ["data", "fluka", "genie", "cosmic"] if args.mode == "all" else [args.mode]
    for mode in modes:
        run_one_mode(mode, args)


if __name__ == "__main__":
    main()
