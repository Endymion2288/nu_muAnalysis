#!/usr/bin/env python3
"""
HTCondor packager and submitter for Stage T6 (Stage 217) full Run-3 extraction:
  data  : Full Run 3 active physics tasks (2022-2026), strictly blinded against SR-ZoneB.
  fluka : All active FLUKA mu MC bck datasets (mc22 + mc24).
  genie : All 69 GENIE MC runs (PS2/3 shower-bias & MC comparison).
  all   : Plan and submit all three modes cleanly.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import glob
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_DIR = Path("/eos/home-x/xcheng/FASER/nu_muAnalysis")
AFS_CONDOR_BASE = Path("/afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage217_timing_t6")
EOS_HOME_XRD_PREFIX = "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis"


def to_xrootd_url(path: str) -> str:
    if path.startswith("root://"):
        return path
    if path.startswith("/eos/user/x/"):
        return f"root://eoshome-x.cern.ch/{path}"
    if path.startswith("/eos/user/"):
        return f"root://eosuser.cern.ch/{path}"
    if path.startswith("/eos/experiment/"):
        return f"root://eospublic.cern.ch/{path}"
    return path


def _chunk_list(items: list[str], chunk_size: int) -> list[list[str]]:
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def _expand_run_aux_map(runs_needed: set[int], active_runs: dict[str, Any]) -> dict[int, tuple[list[str], int]]:
    rc_prefix = "/eos/user/x/xcheng/FASER/nu_muAnalysis/reduced_charge_2025_2026/"
    xrd_rc_index: dict[str, list[tuple[str, int]]] = defaultdict(list)
    need_xrd_rc = any(
        str(active_runs.get(str(r), {}).get("waveform_glob", "")).startswith(rc_prefix)
        for r in runs_needed
    )
    if need_xrd_rc:
        for yr in (2025, 2026):
            res_ls = subprocess.run(
                ["xrdfs", "eoshome-x.cern.ch", "ls", "-l", "-R", f"{rc_prefix}{yr}"],
                capture_output=True, text=True,
            )
            if res_ls.returncode == 0:
                for ln in res_ls.stdout.splitlines():
                    parts = ln.split()
                    if len(parts) >= 6 and not parts[0].startswith("d") and parts[-1].endswith(".root"):
                        fpath = parts[-1]
                        xrd_rc_index[str(Path(fpath).parent)].append((fpath, int(parts[3])))

    out: dict[int, tuple[list[str], int]] = {}
    for r in sorted(runs_needed):
        wg = str(active_runs.get(str(r), {}).get("waveform_glob", ""))
        if not wg:
            raise RuntimeError(f"Run {r} missing 'waveform_glob' in timing manifest")
        if wg.startswith(rc_prefix) and wg.endswith("/*.root"):
            parent_dir = wg[:-len("/*.root")]
            xrd_hits = sorted(xrd_rc_index.get(parent_dir, []))
            if xrd_hits:
                urls = [to_xrootd_url(fp) for fp, _sz in xrd_hits]
                total_bytes = sum(sz for _fp, sz in xrd_hits)
                out[r] = (urls, total_bytes)
                continue
        matched = sorted(glob.glob(wg))
        if not matched:
            raise RuntimeError(f"Run {r} waveform_glob matched 0 files: {wg}")
        total_bytes = sum(os.path.getsize(fp) for fp in matched)
        urls = [to_xrootd_url(fp) for fp in matched]
        out[r] = (urls, total_bytes)
    return out


def build_data_jobs(
    manifest_path: Path, target_gb: float, max_tasks_per_job: int, max_aux_mb: float
) -> list[dict[str, Any]]:
    m = json.loads(manifest_path.read_text())
    dq = json.loads(Path(m["source_dq_manifest"]).read_text())

    active_runs = m["runs"]
    grouped_tasks: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    runs_needed: set[int] = set()
    for tid, tobj in sorted(dq["tasks"].items()):
        r_str = str(tobj["run"])
        if r_str not in active_runs:
            continue
        rmeta = active_runs[r_str]
        key = (int(rmeta["year"]), str(rmeta["reco_tag"]))
        runs_needed.add(int(tobj["run"]))
        grouped_tasks[key].append({
            "task_id": tid,
            "run": int(tobj["run"]),
            "bytes": int(tobj.get("bytes", 0)),
            "n_files": len(tobj.get("files", [])),
        })

    run_aux_map = _expand_run_aux_map(runs_needed, active_runs)
    target_bytes = int(target_gb * 1e9)
    max_aux_bytes = int(max_aux_mb * 1e6)
    jobs: list[dict[str, Any]] = []
    job_idx = 0

    def _emit_job(yr: int, rtag: str, tasks: list[dict[str, Any]], tbytes: int) -> None:
        nonlocal job_idx
        job_runs = sorted({t["run"] for t in tasks})
        aux_urls = sorted(dict.fromkeys(u for r in job_runs for u in run_aux_map[r][0]))
        aux_bytes = sum(run_aux_map[r][1] for r in job_runs)
        jobs.append({
            "job_id": f"data_{job_idx:04d}",
            "year": yr,
            "reco_tag": rtag,
            "task_ids": [t["task_id"] for t in tasks],
            "runs": job_runs,
            "aux_files": aux_urls,
            "aux_bytes": aux_bytes,
            "bytes": tbytes,
            "n_files": sum(t["n_files"] for t in tasks),
        })
        job_idx += 1

    for (year, reco_tag), tlist in sorted(grouped_tasks.items()):
        tlist.sort(key=lambda x: (x["run"], x["task_id"]))
        cur_tasks: list[dict[str, Any]] = []
        cur_runs: set[int] = set()
        cur_bytes = 0
        cur_aux_bytes = 0
        for item in tlist:
            r_num = item["run"]
            add_aux = 0 if r_num in cur_runs else run_aux_map[r_num][1]
            would_exceed = cur_tasks and (
                (cur_bytes + item["bytes"] > target_bytes) or
                (len(cur_tasks) >= max_tasks_per_job) or
                (add_aux > 0 and cur_aux_bytes + add_aux > max_aux_bytes)
            )
            if would_exceed:
                _emit_job(year, reco_tag, cur_tasks, cur_bytes)
                cur_tasks = []
                cur_runs = set()
                cur_bytes = 0
                cur_aux_bytes = 0
                add_aux = run_aux_map[r_num][1]
            cur_tasks.append(item)
            cur_runs.add(r_num)
            cur_bytes += item["bytes"]
            cur_aux_bytes += add_aux
        if cur_tasks:
            _emit_job(year, reco_tag, cur_tasks, cur_bytes)
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
        csize = 3 if mc_era == "mc22" else files_per_job
        for part_i, chunk in enumerate(_chunk_list(files, csize)):
            jobs.append({
                "job_id": f"fluka_{idx:04d}",
                "era": mc_era,
                "run": int(rstr),
                "part": part_i,
                "n_files": len(chunk),
                "files": [to_xrootd_url(fp) for fp in chunk],
            })
            idx += 1
    return jobs


def build_genie_jobs(manifest_path: Path, files_per_job: int) -> list[dict[str, Any]]:
    m = json.loads(manifest_path.read_text())
    jobs: list[dict[str, Any]] = []
    idx = 0
    for rstr, robj in sorted(m["genie_mc_runs"].items(), key=lambda kv: int(kv[0])):
        r = int(rstr)
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
                "files": [to_xrootd_url(fp) for fp in chunk],
            })
            idx += 1
    return jobs


def check_valid_root_output(args_tuple: tuple[str, str, str, bool]) -> tuple[str, bool]:
    job_id, fpath, xrd_url, use_xrd = args_tuple
    p = Path(fpath)
    has_local = p.exists() and p.stat().st_size >= 1024
    if not has_local and not use_xrd:
        return job_id, False
    if has_local:
        for attempt in range(2):
            try:
                import uproot
                with uproot.open(fpath) as f:
                    if "t6_run_summary" in f and f["t6_run_summary"].num_entries > 0:
                        return job_id, True
                return job_id, False
            except Exception:
                if attempt == 0:
                    time.sleep(0.2)
    if use_xrd:
        try:
            import ROOT
            tf = ROOT.TFile.Open(xrd_url, "READ")
            if not tf or tf.IsZombie():
                return job_id, False
            t = tf.Get("t6_run_summary")
            ok = bool(t and t.GetEntries() > 0)
            tf.Close()
            return job_id, ok
        except Exception:
            return job_id, False
    return job_id, False


def write_worker_bundle(stage_dir: Path, mode: str, manifest_path: Path, jobs: list[dict[str, Any]]) -> Path:
    bundle_path = stage_dir / "bundle.tar.gz"
    with tarfile.open(bundle_path, "w:gz") as tar:
        tar.add(REPO_DIR / "build/t6_scanner", arcname="t6_scanner")
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
            aux_dir = stage_dir / "aux_lists"
            shutil.rmtree(aux_dir, ignore_errors=True)
            aux_dir.mkdir(parents=True, exist_ok=True)
            for j in jobs:
                (aux_dir / f"{j['job_id']}.txt").write_text("\n".join(j["aux_files"]) + "\n")
            tar.add(aux_dir, arcname="aux_lists")
        else:
            list_dir = stage_dir / "file_lists"
            shutil.rmtree(list_dir, ignore_errors=True)
            list_dir.mkdir(parents=True, exist_ok=True)
            for j in jobs:
                (list_dir / f"{j['job_id']}.txt").write_text("\n".join(j["files"]) + "\n")
            tar.add(list_dir, arcname="file_lists")
    return bundle_path


def write_runner_script(stage_dir: Path, mode: str) -> Path:
    out_url_dir = f"{EOS_HOME_XRD_PREFIX}/ntuples/timing_stage217/{mode}"
    if mode == "data":
        cmd_block = """task_ids="${arg2//+/,}"
/usr/bin/time -v ./t6_scanner \\
    --mode data \\
    --task-ids "$task_ids" \\
    --manifest run3_timing_manifest.json \\
    --aux-list "aux_lists/${job_id}.txt" \\
    --grl-config grl_config_run3_full.yaml \\
    --timing-calib timing_calib \\
    --threads "$threads" \\
    --output out.root < /dev/null"""
    else:
        cmd_block = f"""/usr/bin/time -v ./t6_scanner \\
    --mode {mode} \\
    --input-list "file_lists/${{job_id}}.txt" \\
    --timing-calib timing_calib \\
    --threads "$threads" \\
    --output out.root < /dev/null"""

    script = f"""#!/usr/bin/env bash
set -eo pipefail
job_id="$1"
arg2="$2"
threads="$3"

scratch=$(mktemp -d "${{_CONDOR_SCRATCH_DIR:-/tmp}}/t6_{mode}.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
tar -xzf bundle.tar.gz -C "$scratch"
cd "$scratch"

set +u
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
set -u
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export XrdSecPROTOCOL=krb5,unix

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
    eos_out_dir = REPO_DIR / "ntuples/timing_stage217" / mode
    logs_dir.mkdir(parents=True, exist_ok=True)
    eos_out_dir.mkdir(parents=True, exist_ok=True)

    jobs_file = stage_dir / "jobs_plan.json"
    if jobs_file.exists():
        jobs = json.loads(jobs_file.read_text())
        print(f"[T6 submit:{mode}] Reusing {jobs_file} ({len(jobs)} jobs)")
    else:
        if mode == "data":
            jobs = build_data_jobs(manifest_path, args.target_gb, args.max_tasks_per_job, args.max_aux_mb)
        elif mode == "fluka":
            jobs = build_fluka_jobs(manifest_path, args.fluka_files_per_job)
        else:
            jobs = build_genie_jobs(manifest_path, args.genie_files_per_job)
        jobs_file.write_text(json.dumps(jobs, indent=2))
        print(f"[T6 submit:{mode}] Planned {len(jobs)} jobs covering {sum(j['n_files'] for j in jobs)} PHYS files.")

    xrd_present: set[str] = set()
    res_ls = subprocess.run(
        ["xrdfs", "eoshome-x.cern.ch", "ls", f"/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/timing_stage217/{mode}"],
        capture_output=True, text=True,
    )
    if res_ls.returncode == 0:
        xrd_present = {Path(line.strip()).stem for line in res_ls.stdout.splitlines() if line.strip().endswith(".root")}

    check_items = [
        (
            j["job_id"],
            str(eos_out_dir / f"{j['job_id']}.root"),
            f"{EOS_HOME_XRD_PREFIX}/ntuples/timing_stage217/{mode}/{j['job_id']}.root",
            j["job_id"] in xrd_present,
        )
        for j in jobs
    ]
    valid_map: dict[str, bool] = {}
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as ex:
        for jid, ok in ex.map(check_valid_root_output, check_items, chunksize=16):
            valid_map[jid] = ok

    remaining = [j for j in jobs if not valid_map.get(j["job_id"], False)]
    print(f"[T6 submit:{mode}] Status: {len(jobs) - len(remaining)}/{len(jobs)} completed cleanly, {len(remaining)} remaining.")
    if not remaining or args.status_only:
        return

    if args.limit > 0:
        remaining = remaining[: args.limit]
    if args.dry_run:
        print(f"[T6 submit:{mode}] Dry-run only: would submit {len(remaining)} jobs (first: {[j['job_id'] for j in remaining[:5]]})")
        return

    bundle_path = write_worker_bundle(stage_dir, mode, manifest_path, remaining)
    runner_path = write_runner_script(stage_dir, mode)

    if args.run_local_remaining:
        n_procs = args.local_workers if args.local_workers > 0 else max(1, min(len(remaining), 28 // max(1, args.cpus)))
        print(f"[T6 submit:{mode}] Running {len(remaining)} remaining jobs locally ({n_procs} workers x {args.cpus} threads)...", flush=True)

        def _run_one(j: dict[str, Any]) -> tuple[str, int, str]:
            a2 = "+".join(j["task_ids"]) if mode == "data" else str(j["run"])
            cmd = ["bash", str(runner_path), j["job_id"], a2, str(args.cpus)]
            r = subprocess.run(cmd, cwd=str(stage_dir), capture_output=True, text=True)
            (logs_dir / f"{j['job_id']}_local.out").write_text(r.stdout)
            (logs_dir / f"{j['job_id']}_local.err").write_text(r.stderr)
            return j["job_id"], r.returncode, r.stderr[-400:]

        failures: list[tuple[str, int, str]] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=n_procs) as ex:
            for jid, rc, err in ex.map(_run_one, remaining):
                print(f"  [local {mode}] {jid} rc={rc}", flush=True)
                if rc != 0:
                    failures.append((jid, rc, err))
        if failures:
            raise RuntimeError(f"Local T6 tail jobs failed: {failures[:3]}")
        return

    arg_lines = []
    for j in remaining:
        a2 = "+".join(j["task_ids"]) if mode == "data" else str(j["run"])
        arg_lines.append(f"{j['job_id']} {a2} {args.cpus}")
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
request_cpus = {args.cpus}
request_memory = {args.memory_mb}M
request_disk = 2500M
max_retries = 2
+JobFlavour = "{args.flavour}"
+NuMuStage = "timing-t6-{mode}"
output = {logs_dir}/$(job_id)_$(ClusterId).out
error = {logs_dir}/$(job_id)_$(ClusterId).err
log = {logs_dir}/condor_{mode}.log
queue job_id, arg2, threads from {args_file}
"""
    sub_file = stage_dir / f"timing_t6_{mode}.sub"
    sub_file.write_text(sub_text)
    print(f"[T6 submit:{mode}] Bundle size: {bundle_path.stat().st_size / (1024.0 * 1024.0):.2f} MB")

    sub_env = dict(os.environ)
    sub_env["_condor_TOOL_TIMEOUT"] = "120"
    res = subprocess.run(["condor_submit", str(sub_file)], cwd=str(stage_dir), env=sub_env, capture_output=True, text=True)
    print(res.stdout.strip())
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr)
        raise SystemExit(res.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit Stage T6 HTCondor jobs")
    parser.add_argument("--mode", choices=["data", "fluka", "genie", "all"], required=True)
    parser.add_argument("--manifest", default=str(REPO_DIR / "AnalysisZipFramework/config/timing_calib/run3_timing_manifest.json"))
    parser.add_argument("--target-gb", type=float, default=40.0)
    parser.add_argument("--max-tasks-per-job", type=int, default=8)
    parser.add_argument("--max-aux-mb", type=float, default=1500.0)
    parser.add_argument("--fluka-files-per-job", type=int, default=35)
    parser.add_argument("--genie-files-per-job", type=int, default=80)
    parser.add_argument("--cpus", type=int, default=4)
    parser.add_argument("--memory-mb", type=int, default=6000)
    parser.add_argument("--flavour", default="microcentury")
    parser.add_argument("--workers", type=int, default=28)
    parser.add_argument("--local-workers", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status-only", action="store_true")
    parser.add_argument("--run-local-remaining", action="store_true")
    args = parser.parse_args()

    modes = ["data", "fluka", "genie"] if args.mode == "all" else [args.mode]
    for mode in modes:
        run_one_mode(mode, args)


if __name__ == "__main__":
    main()
