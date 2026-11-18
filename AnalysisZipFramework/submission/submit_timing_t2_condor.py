#!/usr/bin/env python3
"""
HTCondor job packager and submitter for Stage T2 (Stage 213) MC timing calibration
and Data-vs-FLUKA single-muon closure evaluation.

Modes:
  mc-scan       : Scan all 19 FLUKA bck datasets + representative GENIE runs
                  to measure per-run/family t_mc_ref, Timing/Preshower linear slopes,
                  transverse flatness, MC time-walk, and sigma_MC(Q).
  fluka-closure : Evaluate smeared & aligned TimingCalibrator across all 19 FLUKA runs.
  data-closure  : Evaluate TimingCalibrator (strictly TimingBlindingGuard-enforced CR-Prompt)
                  on high-statistics representative 2022-2024 Run 3 Data runs matching
                  the luminosity eras of FLUKA & GENIE MC.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import glob
import json
import os
import subprocess
import tarfile
import time
from pathlib import Path
from typing import Any

REPO_DIR = Path("/eos/home-x/xcheng/FASER/nu_muAnalysis")
AFS_CONDOR_BASE = Path("/afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage213_timing_t2")
EOS_HOME_XRD_PREFIX = "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis"

GENIE_CALIB_RUNS = [
    # 2022-2023 geometry (-160 urad)
    200082, 200083, 200089, 200107, 200108,
    # 2024_noCaloNu geometry (+160 urad)
    200093, 200094, 200100, 200163, 200164,
    # 2024_CaloNu geometry (+160 urad + CaloNu)
    200139, 200140, 200146, 200175, 200176,
]


def _chunk_list(items: list[str], chunk_size: int) -> list[list[str]]:
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def build_mc_jobs(manifest_path: Path, files_per_job: int, record_prob_genie: float) -> list[dict[str, Any]]:
    m = json.loads(manifest_path.read_text())
    jobs: list[dict[str, Any]] = []
    idx = 0

    # 1. All 19 bck FLUKA datasets (210001..210004 only have ntp/, zero bck files)
    for k, _ in sorted(m["fluka_mc_datasets"].items()):
        mc_era, _, rstr = k.split("_")
        files = [p for p in sorted(glob.glob(f"/eos/experiment/faser/sim/{mc_era}/fluka/{rstr}/bck/s001*-r0019/*-PHYS.root"))
                 if os.path.isfile(p) and p.endswith("-PHYS.root")]
        if not files:
            continue
        # mc22 210005/06/08 have huge entry counts per file (200k-1M) -> split smaller
        csize = 2 if mc_era == "mc22" else files_per_job
        for part_i, chunk in enumerate(_chunk_list(files, csize)):
            jobs.append({
                "job_id": f"mc_{idx:04d}",
                "kind": f"fluka_{mc_era}",
                "run": int(rstr),
                "part": part_i,
                "record_prob": 1.0,
                "files": chunk,
            })
            idx += 1

    # 2. Representative GENIE runs across 3 geometries & production tags
    for r in GENIE_CALIB_RUNS:
        robj = m["genie_mc_runs"].get(str(r))
        if not robj:
            continue
        pat = robj["glob"].replace("root://eospublic.cern.ch/", "")
        files = [p for p in sorted(glob.glob(pat))
                 if os.path.isfile(p) and p.endswith("-PHYS.root")]
        if not files:
            continue
        for part_i, chunk in enumerate(_chunk_list(files, files_per_job)):
            jobs.append({
                "job_id": f"mc_{idx:04d}",
                "kind": "genie",
                "run": r,
                "part": part_i,
                "record_prob": record_prob_genie,
                "files": chunk,
            })
            idx += 1

    return jobs


def build_data_closure_jobs(manifest_path: Path, runs_per_period: int = 8) -> list[dict[str, Any]]:
    m = json.loads(manifest_path.read_text())
    dq = json.loads(Path(m["source_dq_manifest"]).read_text())
    unavail = set((dq.get("config", {}).get("unavailable_inputs") or {}).keys())

    # Pick top-statistics representative runs from each 2022-2024 period
    target_periods = ("2022", "2023", "2024_preCaloNu", "2024_CaloNu", "2024_postCaloNu")
    by_period: dict[str, list[tuple[float, int, list[str]]]] = {p: [] for p in target_periods}

    tasks_by_run: dict[int, list[str]] = {}
    for _, tobj in dq["tasks"].items():
        r = int(tobj["run"])
        for f in tobj.get("files", []):
            if f not in unavail:
                tasks_by_run.setdefault(r, []).append(f)

    for r_str, rmeta in m["runs"].items():
        per = rmeta.get("period", "")
        if per not in by_period:
            continue
        r = int(r_str)
        flist = sorted(tasks_by_run.get(r, []))
        if not flist:
            continue
        lumi = float(rmeta.get("lumi_fb_inverse", 0.0))
        by_period[per].append((lumi, r, flist))

    jobs: list[dict[str, Any]] = []
    idx = 0
    for per in target_periods:
        cands = sorted(by_period[per], key=lambda x: (-x[0], x[1]))
        # Choose evenly spaced across sorted high-lumi runs to span period evolution
        chosen = cands[: min(runs_per_period, len(cands))]
        for _, r, flist in chosen:
            # Cap extremely long runs at 15 files per job by chunking cleanly
            for chunk in _chunk_list(flist, 15):
                jobs.append({
                    "job_id": f"data_{idx:04d}",
                    "kind": f"data_{per}",
                    "period": per,
                    "run": r,
                    "files": chunk,
                })
                idx += 1
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


def write_worker_bundle(stage_dir: Path, mode: str, jobs: list[dict[str, Any]]) -> Path:
    list_dir = stage_dir / "file_lists"
    list_dir.mkdir(parents=True, exist_ok=True)
    for j in jobs:
        (list_dir / f"{j['job_id']}.txt").write_text("\n".join(j["files"]) + "\n")

    bundle_path = stage_dir / "bundle.tar.gz"
    with tarfile.open(bundle_path, "w:gz") as tar:
        tar.add(REPO_DIR / "build/mc_timing_scanner", arcname="mc_timing_scanner")
        tar.add(list_dir, arcname="file_lists")
        if mode == "data-closure":
            tar.add(REPO_DIR / "AnalysisZipFramework/config/grl_config_run3_full.yaml", arcname="grl_config_run3_full.yaml")
        if mode in ("fluka-closure", "data-closure"):
            calib_dir = REPO_DIR / "AnalysisZipFramework/config/timing_calib"
            for fn in ("ref_offsets_run3.json", "tof_maps_run3.json", "mc_timing_calib.json"):
                fp = calib_dir / fn
                if fp.exists():
                    tar.add(fp, arcname=f"timing_calib/{fn}")
    return bundle_path


def write_runner_script(stage_dir: Path, mode: str) -> Path:
    scanner_mode = "mc-scan" if mode == "mc-scan" else "closure-eval"
    out_url_dir = f"{EOS_HOME_XRD_PREFIX}/ntuples/timing_stage213/{mode}"
    extra_flags = ""
    if mode == "mc-scan":
        extra_flags = "--is-mc --record-prob \"$rec_prob\""
    elif mode == "fluka-closure":
        extra_flags = "--is-mc --timing-calib timing_calib"
    else:
        extra_flags = "--timing-calib timing_calib --grl-config grl_config_run3_full.yaml"

    script = f"""#!/usr/bin/env bash
set -eo pipefail
job_id="$1"
rec_prob="$2"
threads="$3"

scratch=$(mktemp -d "${{_CONDOR_SCRATCH_DIR:-/tmp}}/t2_{mode}.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
tar -xzf bundle.tar.gz -C "$scratch"
cd "$scratch"

set +u
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
set -u
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

/usr/bin/time -v ./mc_timing_scanner \\
    --mode {scanner_mode} \\
    --input-list "file_lists/${{job_id}}.txt" \\
    {extra_flags} \\
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
    parser = argparse.ArgumentParser(description="Submit Stage T2 HTCondor jobs")
    parser.add_argument("--mode", choices=["mc-scan", "fluka-closure", "data-closure"], required=True)
    parser.add_argument("--manifest", default=str(REPO_DIR / "AnalysisZipFramework/config/timing_calib/run3_timing_manifest.json"))
    parser.add_argument("--files-per-job", type=int, default=40)
    parser.add_argument("--record-prob-genie", type=float, default=0.35)
    parser.add_argument("--runs-per-period", type=int, default=8)
    parser.add_argument("--cpus", type=int, default=4)
    parser.add_argument("--memory-mb", type=int, default=4500)
    parser.add_argument("--flavour", default="microcentury")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    stage_dir = AFS_CONDOR_BASE / args.mode
    logs_dir = stage_dir / "logs"
    eos_out_dir = REPO_DIR / "ntuples/timing_stage213" / args.mode
    logs_dir.mkdir(parents=True, exist_ok=True)
    eos_out_dir.mkdir(parents=True, exist_ok=True)

    jobs_file = stage_dir / "jobs_plan.json"
    if jobs_file.exists():
        jobs = json.loads(jobs_file.read_text())
        print(f"[submit] Reusing {jobs_file} ({len(jobs)} jobs)")
    else:
        if args.mode == "mc-scan":
            jobs = build_mc_jobs(Path(args.manifest), args.files_per_job, args.record_prob_genie)
        elif args.mode == "fluka-closure":
            mc_jobs = build_mc_jobs(Path(args.manifest), args.files_per_job, args.record_prob_genie)
            jobs = [j for j in mc_jobs if j["kind"].startswith("fluka_")]
        else:
            jobs = build_data_closure_jobs(Path(args.manifest), args.runs_per_period)
        jobs_file.write_text(json.dumps(jobs, indent=2))
        print(f"[submit] Planned {len(jobs)} jobs covering {sum(len(j['files']) for j in jobs)} files.")

    expected_tree = "mc_summary" if args.mode == "mc-scan" else "closure_summary"
    check_items = [(j["job_id"], str(eos_out_dir / f"{j['job_id']}.root"), expected_tree) for j in jobs]
    valid_map: dict[str, bool] = {}
    with concurrent.futures.ProcessPoolExecutor(max_workers=28) as ex:
        for jid, ok in ex.map(check_valid_root_output, check_items, chunksize=8):
            valid_map[jid] = ok

    remaining = [j for j in jobs if not valid_map.get(j["job_id"], False)]
    print(f"[submit] Status for {args.mode}: {len(jobs) - len(remaining)}/{len(jobs)} completed cleanly, {len(remaining)} remaining.")
    if not remaining:
        return

    if args.limit > 0:
        remaining = remaining[: args.limit]
    if args.dry_run:
        print(f"[submit] Dry-run only: would submit {len(remaining)} jobs (first: {[j['job_id'] for j in remaining[:5]]})")
        return

    bundle_path = write_worker_bundle(stage_dir, args.mode, remaining)
    runner_path = write_runner_script(stage_dir, args.mode)

    arg_lines = [
        f"{j['job_id']} {j.get('record_prob', 1.0)} {args.cpus}"
        for j in remaining
    ]
    args_file = stage_dir / "pending_jobs.args"
    args_file.write_text("\n".join(arg_lines) + "\n")

    sub_text = f"""universe = vanilla
initialdir = {stage_dir}
executable = /bin/bash
transfer_executable = False
arguments = {runner_path.name} $(job_id) $(rec_prob) $(threads)
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
output = logs/{args.mode}_$(ClusterId)_$(Process).out
error = logs/{args.mode}_$(ClusterId)_$(Process).err
log = logs/condor_{args.mode}.log
queue job_id,rec_prob,threads from {args_file}
"""
    sub_file = stage_dir / f"submit_{args.mode}.sub"
    sub_file.write_text(sub_text)

    res = subprocess.run(["condor_submit", str(sub_file)], cwd=str(stage_dir), capture_output=True, text=True, check=True)
    print(res.stdout.strip())


if __name__ == "__main__":
    main()
