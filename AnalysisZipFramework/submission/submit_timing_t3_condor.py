#!/usr/bin/env python3
"""
HTCondor packager and submitter for Stage T3 (Stage 214) GENIE PHYS + HITS extraction
across all 69 GENIE MC runs (3,321 PHYS files across 3 geometries & 5 Geant4 physics lists).
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
AFS_CONDOR_BASE = Path("/afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage214_timing_t3")
EOS_HOME_XRD_PREFIX = "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis"


def _chunk_list(items: list[str], chunk_size: int) -> list[list[str]]:
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def build_t3_jobs(manifest_path: Path, files_per_job: int = 20) -> list[dict[str, Any]]:
    m = json.loads(manifest_path.read_text())
    jobs: list[dict[str, Any]] = []
    for r_str, robj in sorted(m["genie_mc_runs"].items(), key=lambda kv: int(kv[0])):
        r = int(r_str)
        pat = robj["glob"].replace("root://eospublic.cern.ch/", "")
        files = [p for p in sorted(glob.glob(pat)) if os.path.isfile(p) and p.endswith("-PHYS.root")]
        if not files:
            raise RuntimeError(f"No PHYS.root files found for GENIE run {r} ({pat})")
        chunks = _chunk_list(files, files_per_job) if files_per_job > 0 else [files]
        for ci, chunk in enumerate(chunks):
            jid = f"run_{r}" if len(chunks) == 1 else f"run_{r}_p{ci:02d}"
            jobs.append({
                "job_id": jid,
                "run": r,
                "part": ci,
                "n_files": len(chunk),
                "files": chunk,
            })
    return jobs


def check_valid_root_output(args_tuple: tuple[str, str, bool]) -> tuple[str, bool]:
    job_id, fpath, use_xrd = args_tuple
    p = Path(fpath)
    target = fpath
    if not (p.exists() and p.stat().st_size >= 2048):
        if not use_xrd:
            return job_id, False
        target = f"{EOS_HOME_XRD_PREFIX}/ntuples/timing_stage214/runs/{job_id}.root"
    for attempt in range(3):
        try:
            import uproot
            with uproot.open(target) as f:
                if "run_summary" in f and "t3_events" in f and f["run_summary"].num_entries > 0:
                    return job_id, True
            return job_id, False
        except Exception:
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    return job_id, False


def write_worker_bundle(stage_dir: Path, jobs: list[dict[str, Any]], calypso_lib_dir: Path) -> Path:
    list_dir = stage_dir / "file_lists"
    list_dir.mkdir(parents=True, exist_ok=True)
    for j in jobs:
        (list_dir / f"{j['job_id']}.txt").write_text("\n".join(j["files"]) + "\n")

    bundle_path = stage_dir / "bundle.tar.gz"
    with tarfile.open(bundle_path, "w:gz") as tar:
        tar.add(REPO_DIR / "build_t3/t3_genie_hits_scanner", arcname="t3_genie_hits_scanner")
        tar.add(REPO_DIR / "setup_env.sh", arcname="setup_env.sh")
        tar.add(list_dir, arcname="file_lists")

        # Minimal Scint/DetDescr runtime shared libs & dictionaries (< 2 MB)
        lib_patterns = (
            "Calypso.rootmap",
            "libScintSimEventTPCnv*.so*", "libScintSimEventTPCnv*.pcm",
            "libScintSimEvent*.so*", "libScintSimEvent*.pcm",
            "libScintIdentifier*.so*", "libScintIdentifier*.pcm",
            "libFaserDetDescr*.so*", "libFaserDetDescr*.pcm",
        )
        added: set[str] = set()
        for pat in lib_patterns:
            for fp in sorted(calypso_lib_dir.glob(pat)):
                if fp.name in added or not fp.is_file():
                    continue
                if "Digi" in fp.name or "Readout" in fp.name or "GeoModel" in fp.name or "IdCnv" in fp.name or "AthenaPool" in fp.name:
                    continue
                tar.add(fp, arcname=f"lib/{fp.name}")
                added.add(fp.name)

        calib_dir = REPO_DIR / "AnalysisZipFramework/config/timing_calib"
        for fn in ("ref_offsets_run3.json", "tof_maps_run3.json", "mc_timing_calib.json"):
            tar.add(calib_dir / fn, arcname=f"timing_calib/{fn}")
    return bundle_path


def write_runner_script(stage_dir: Path) -> Path:
    out_url_dir = f"{EOS_HOME_XRD_PREFIX}/ntuples/timing_stage214/runs"
    script = f"""#!/usr/bin/env bash
set -eo pipefail
job_id="$1"

scratch=$(mktemp -d "${{_CONDOR_SCRATCH_DIR:-/tmp}}/t3_extract.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
tar -xzf bundle.tar.gz -C "$scratch"
cd "$scratch"

set +u
source ./setup_env.sh --official >/dev/null 2>&1
set -u
export LD_LIBRARY_PATH="${{scratch}}/lib:${{LD_LIBRARY_PATH:-}}"
export ROOT_INCLUDE_PATH="${{scratch}}/lib:${{ROOT_INCLUDE_PATH:-}}"

/usr/bin/time -v ./t3_genie_hits_scanner \\
    --mode t3-extract \\
    --timing-calib timing_calib \\
    --input-list "file_lists/${{job_id}}.txt" \\
    --output out.root

dest_url="{out_url_dir}/${{job_id}}.root"
xrdcp --retry 3 --silent --force out.root "$dest_url"
echo "[DONE] ${{job_id}} -> ${{dest_url}}"
"""
    runner = stage_dir / "run_t3.sh"
    runner.write_text(script)
    os.chmod(runner, 0o755)
    return runner


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit Stage T3 GENIE 69-run PHYS+HITS extraction to HTCondor")
    parser.add_argument("--manifest", default=str(REPO_DIR / "AnalysisZipFramework/config/timing_calib/run3_timing_manifest.json"))
    parser.add_argument("--calypso-lib-dir", default="")
    parser.add_argument("--files-per-job", type=int, default=20)
    parser.add_argument("--memory-mb", type=int, default=2500)
    parser.add_argument("--flavour", default="microcentury")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    stage_dir = AFS_CONDOR_BASE
    logs_dir = stage_dir / "logs"
    eos_out_dir = REPO_DIR / "ntuples/timing_stage214/runs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    eos_out_dir.mkdir(parents=True, exist_ok=True)

    jobs_file = stage_dir / "jobs_plan.json"
    if jobs_file.exists():
        jobs = json.loads(jobs_file.read_text())
        print(f"[T3 submit] Reusing {jobs_file} ({len(jobs)} jobs, {sum(j['n_files'] for j in jobs)} files)")
    else:
        jobs = build_t3_jobs(Path(args.manifest), args.files_per_job)
        jobs_file.write_text(json.dumps(jobs, indent=2))
        print(f"[T3 submit] Planned {len(jobs)} jobs covering {sum(j['n_files'] for j in jobs)} PHYS files.")

    xrd_present: set[str] = set()
    res_ls = subprocess.run(
        ["xrdfs", "eoshome-x.cern.ch", "ls", "/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/timing_stage214/runs"],
        capture_output=True, text=True,
    )
    if res_ls.returncode == 0:
        xrd_present = {Path(line.strip()).stem for line in res_ls.stdout.splitlines() if line.strip().endswith(".root")}

    check_items = [(j["job_id"], str(eos_out_dir / f"{j['job_id']}.root"), j["job_id"] in xrd_present) for j in jobs]
    valid_map: dict[str, bool] = {}
    with concurrent.futures.ProcessPoolExecutor(max_workers=28) as ex:
        for jid, ok in ex.map(check_valid_root_output, check_items, chunksize=4):
            valid_map[jid] = ok

    remaining = [j for j in jobs if not valid_map.get(j["job_id"], False)]
    print(f"[T3 submit] Status: {len(jobs) - len(remaining)}/{len(jobs)} completed cleanly, {len(remaining)} remaining.")
    if not remaining:
        return

    if args.limit > 0:
        remaining = remaining[: args.limit]
    if args.dry_run:
        print(f"[T3 submit] Dry-run only: would submit {len(remaining)} jobs (first: {[j['job_id'] for j in remaining[:5]]})")
        return

    calypso_lib = Path(args.calypso_lib_dir) if args.calypso_lib_dir else (Path(os.environ.get("FASER_CALYPSO_RUN", "")) / "lib")
    if not calypso_lib.exists() or not (calypso_lib / "libScintSimEventTPCnv.so").exists():
        raise RuntimeError(f"Invalid --calypso-lib-dir / FASER_CALYPSO_RUN lib dir: {calypso_lib}")

    bundle_path = write_worker_bundle(stage_dir, remaining, calypso_lib)
    runner_path = write_runner_script(stage_dir)
    print(f"[T3 submit] Bundle size: {bundle_path.stat().st_size / (1024.0 * 1024.0):.2f} MB")

    args_file = stage_dir / "pending_jobs.args"
    args_file.write_text("\n".join(j["job_id"] for j in remaining) + "\n")

    sub_text = f"""universe = vanilla
initialdir = {stage_dir}
executable = /bin/bash
transfer_executable = False
arguments = {runner_path.name} $(job_id)
should_transfer_files = YES
when_to_transfer_output = ON_EXIT
transfer_input_files = {runner_path},{bundle_path}
transfer_output_files = ""
MY.SendCredential = True
requirements = (OpSysAndVer =?= "AlmaLinux9")
request_cpus = 1
request_memory = {args.memory_mb}M
request_disk = 2000M
max_retries = 2
+JobFlavour = "{args.flavour}"
output = logs/t3_$(ClusterId)_$(Process).out
error = logs/t3_$(ClusterId)_$(Process).err
log = logs/condor_t3.log
queue job_id from {args_file}
"""
    sub_file = stage_dir / "submit_t3.sub"
    sub_file.write_text(sub_text)

    res = subprocess.run(["condor_submit", str(sub_file)], cwd=str(stage_dir), capture_output=True, text=True, check=True)
    print(res.stdout.strip())


if __name__ == "__main__":
    main()
