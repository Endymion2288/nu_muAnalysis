#!/usr/bin/env python3
"""
HTCondor packager and submitter for 2025 & 2026 VetoNu reduced-charge production.

Runs compiled multi-threaded C++ `raw_reduced_charge_dumper` over PHYS + .raw
streams for all 281 GRL runs (199 in 2025, 82 in 2026) and writes compact
ZSTD-5 ROOT trees (`run`, `event`, `myVetoNu0_rawCharge35`, `myVetoNu1_rawCharge35`)
to `/eos/user/x/xcheng/FASER/nu_muAnalysis/reduced_charge_2025_2026/{2025,2026}/<run6>/`.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from typing import Any

REPO_DIR = Path("/eos/home-x/xcheng/FASER/nu_muAnalysis")
AFS_CONDOR_BASE = Path("/afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage216_reduced_charge_2526")
EOS_OUT_BASE = Path("/eos/user/x/xcheng/FASER/nu_muAnalysis/reduced_charge_2025_2026")
EOS_XRD_OUT_BASE = "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/reduced_charge_2025_2026"


def _chunk_list(items: list[str], chunk_size: int) -> list[list[str]]:
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def _resolve_raw_files_for_phys(run: int, yr: int, phys_files: list[str], available_raw_set: set[str]) -> list[str]:
    import re
    r6 = f"{run:06d}"
    pat = re.compile(rf"Faser-Physics-{r6}-(\d{{5}})(?:-(\d{{5}}))?-")
    segs: set[int] = set()
    for pf in phys_files:
        m = pat.search(os.path.basename(pf))
        if m:
            lo = int(m.group(1))
            hi = int(m.group(2)) if m.group(2) else lo
            for idx in range(lo, hi + 1):
                segs.add(idx)
    if segs:
        lo_m = min(segs)
        hi_m = max(segs)
        if lo_m > 0:
            segs.add(lo_m - 1)
        segs.add(hi_m + 1)
    raw_dir = f"/eos/experiment/faser/raw/{yr}/{r6}"
    cands = [f"{raw_dir}/Faser-Physics-{r6}-{idx:05d}.raw" for idx in sorted(segs)]
    matched = [c for c in cands if c in available_raw_set]
    if matched:
        return matched
    return sorted(available_raw_set)


def build_jobs(manifest_path: Path, files_per_job_2025: int, files_per_job_2026: int) -> list[dict[str, Any]]:
    import glob
    m = json.loads(manifest_path.read_text())
    dq = json.loads(Path(m["source_dq_manifest"]).read_text())

    unavail = set()
    if "config" in dq and "unavailable_inputs" in dq["config"]:
        unavail = set(dq["config"]["unavailable_inputs"].keys())

    run_files: dict[int, list[str]] = {}
    for _tid, tobj in sorted(dq["tasks"].items()):
        r = int(tobj["run"])
        if str(r) not in m["runs"]:
            continue
        yr = int(m["runs"][str(r)]["year"])
        if yr not in (2025, 2026):
            continue
        lst = run_files.setdefault(r, [])
        for fp in tobj.get("files", []):
            if fp not in unavail:
                lst.append(fp)

    jobs: list[dict[str, Any]] = []
    for r in sorted(run_files):
        rmeta = m["runs"][str(r)]
        yr = int(rmeta["year"])
        reco_tag = str(rmeta["reco_tag"])
        disable_ps = (yr == 2025) and (reco_tag == "2025/p0013") and (19413 <= r <= 20142)
        avail_raw = set(glob.glob(f"/eos/experiment/faser/raw/{yr}/{r:06d}/Faser-Physics-{r:06d}-*.raw"))
        if not avail_raw:
            raise RuntimeError(f"No .raw files found locally in /eos/experiment/faser/raw/{yr}/{r:06d}")
        flist = sorted(dict.fromkeys(run_files[r]))
        csize = files_per_job_2025 if yr == 2025 else files_per_job_2026
        for p_idx, chunk in enumerate(_chunk_list(flist, csize)):
            raw_chunk = _resolve_raw_files_for_phys(r, yr, chunk, avail_raw)
            jobs.append({
                "job_id": f"rc_{r:06d}_part{p_idx:04d}",
                "run": r,
                "run6": f"{r:06d}",
                "year": yr,
                "reco_tag": reco_tag,
                "disable_ps": disable_ps,
                "n_files": len(chunk),
                "files": chunk,
                "raw_files": raw_chunk,
            })
    return jobs


def _run_has_missing_raw_segment(year: int, run6: str) -> bool:
    import glob
    raws = sorted(glob.glob(f"/eos/experiment/faser/raw/{year}/{run6}/Faser-Physics-*.raw"))
    if not raws:
        return False
    nums = [int(os.path.basename(f).split("-")[3].split(".")[0]) for f in raws]
    return len(nums) < (nums[-1] - nums[0] + 1)


def check_valid_rc_output(item: tuple[str, str, str, bool, float]) -> tuple[str, bool, int, int]:
    job_id, fpath, xrd_url, in_xrd, max_miss_frac = item
    p = Path(fpath)
    has_local = p.exists() and p.stat().st_size >= 512
    if not has_local and not in_xrd:
        return job_id, False, 0, 0
    if has_local:
        for attempt in range(2):
            try:
                import uproot

                with uproot.open(fpath) as f:
                    if "tree" not in f or "rc_summary" not in f:
                        return job_id, False, 0, 0
                    s = f["rc_summary"].arrays(["n_target", "n_found"], library="np")
                    n_t = int(s["n_target"][0])
                    n_f = int(s["n_found"][0])
                    n_tr = int(f["tree"].num_entries)
                    ok = (n_tr == n_t) and ((n_t - n_f) <= max(5, int(max_miss_frac * max(n_t, 1))))
                    return job_id, ok, n_t, n_f
            except Exception:
                if attempt == 0:
                    time.sleep(0.2)
    if in_xrd:
        try:
            import ROOT

            tf = ROOT.TFile.Open(xrd_url, "READ")
            if not tf or tf.IsZombie():
                return job_id, False, 0, 0
            sm = tf.Get("rc_summary")
            tr = tf.Get("tree")
            if not sm or not tr or sm.GetEntries() < 1:
                tf.Close()
                return job_id, False, 0, 0
            sm.GetEntry(0)
            n_t = int(sm.n_target)
            n_f = int(sm.n_found)
            n_tr = int(tr.GetEntries())
            tf.Close()
            ok = (n_tr == n_t) and ((n_t - n_f) <= max(5, int(max_miss_frac * max(n_t, 1))))
            return job_id, ok, n_t, n_f
        except Exception:
            return job_id, False, 0, 0
    return job_id, False, 0, 0


def write_worker_bundle(stage_dir: Path, jobs: list[dict[str, Any]]) -> Path:
    list_dir = stage_dir / "phys_lists"
    raw_dir = stage_dir / "raw_lists"
    list_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    for j in jobs:
        (list_dir / f"{j['job_id']}.txt").write_text("\n".join(j["files"]) + "\n")
        (raw_dir / f"{j['job_id']}.txt").write_text("\n".join(j["raw_files"]) + "\n")

    bundle_path = stage_dir / "bundle.tar.gz"
    with tarfile.open(bundle_path, "w:gz") as tar:
        tar.add(REPO_DIR / "build/raw_reduced_charge_dumper", arcname="raw_reduced_charge_dumper")
        tar.add(list_dir, arcname="phys_lists")
        tar.add(raw_dir, arcname="raw_lists")
    return bundle_path


def write_runner_script(stage_dir: Path) -> Path:
    script = f"""#!/usr/bin/env bash
set -eo pipefail
job_id="$1"
run="$2"
run6="$3"
year="$4"
disable_ps="$5"
threads="$6"

scratch=$(mktemp -d "${{_CONDOR_SCRATCH_DIR:-/tmp}}/rc2526.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
tar -xzf bundle.tar.gz -C "$scratch"
cd "$scratch"

set +u
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
set -u

extra_flags=""
if [[ "$disable_ps" == "1" ]]; then
    extra_flags="--disable-ps"
fi

/usr/bin/time -v ./raw_reduced_charge_dumper \\
    --run "$run" \\
    --phys-list "phys_lists/${{job_id}}.txt" \\
    --raw-list "raw_lists/${{job_id}}.txt" \\
    --raw-dir "/eos/experiment/faser/raw/${{year}}/${{run6}}" \\
    --filter-mode long_tracks \\
    --vv-diff 33.166 \\
    --vt-diff 34.930 \\
    --vp-diff 13.330 \\
    $extra_flags \\
    --threads "$threads" \\
    -o out.root

dest_url="{EOS_XRD_OUT_BASE}/${{year}}/${{run6}}/${{job_id}}.root"
xrdcp --retry 3 --silent --force out.root "$dest_url"
echo "[DONE] ${{job_id}} -> ${{dest_url}}"
"""
    runner = stage_dir / "run_rc.sh"
    runner.write_text(script)
    os.chmod(runner, 0o755)
    return runner


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit 2025-2026 reduced charge Condor production")
    parser.add_argument("--manifest", default=str(REPO_DIR / "AnalysisZipFramework/config/timing_calib/run3_timing_manifest.json"))
    parser.add_argument("--files-per-job-2025", type=int, default=3)
    parser.add_argument("--files-per-job-2026", type=int, default=5)
    parser.add_argument("--cpus", type=int, default=4)
    parser.add_argument("--memory-mb", type=int, default=3500)
    parser.add_argument("--flavour", default="longlunch")
    parser.add_argument("--workers", type=int, default=28)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status-only", action="store_true")
    parser.add_argument("--run-local-remaining", action="store_true")
    parser.add_argument("--max-missing-frac", type=float, default=0.025)
    args = parser.parse_args()

    AFS_CONDOR_BASE.mkdir(parents=True, exist_ok=True)
    logs_dir = AFS_CONDOR_BASE / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(args.manifest)

    jobs_file = AFS_CONDOR_BASE / "jobs_plan.json"
    if jobs_file.exists():
        jobs = json.loads(jobs_file.read_text())
        print(f"[RC2526] Reusing {jobs_file} ({len(jobs)} jobs)")
    else:
        jobs = build_jobs(manifest_path, args.files_per_job_2025, args.files_per_job_2026)
        jobs_file.write_text(json.dumps(jobs, indent=2))
        n25 = sum(1 for j in jobs if j["year"] == 2025)
        n26 = sum(1 for j in jobs if j["year"] == 2026)
        n_dps = len({j["run"] for j in jobs if j["disable_ps"]})
        print(f"[RC2526] Planned {len(jobs)} jobs (2025={n25}, 2026={n26}, disablePs_runs={n_dps}), total PHYS files={sum(j['n_files'] for j in jobs)}")

    # Ensure output run directories exist on EOS
    for yr, r6 in sorted({(j["year"], j["run6"]) for j in jobs}):
        (EOS_OUT_BASE / str(yr) / r6).mkdir(parents=True, exist_ok=True)

    xrd_present: set[str] = set()
    for yr in (2025, 2026):
        res_ls = subprocess.run(
            ["xrdfs", "eoshome-x.cern.ch", "ls", "-R", f"/eos/user/x/xcheng/FASER/nu_muAnalysis/reduced_charge_2025_2026/{yr}"],
            capture_output=True, text=True,
        )
        if res_ls.returncode == 0:
            for ln in res_ls.stdout.splitlines():
                s = ln.strip()
                if s.endswith(".root"):
                    xrd_present.add(Path(s).stem)

    run_gap_map = {
        r6: _run_has_missing_raw_segment(yr, r6)
        for yr, r6 in sorted({(j["year"], j["run6"]) for j in jobs})
    }

    check_items = [
        (
            j["job_id"],
            str(EOS_OUT_BASE / str(j["year"]) / j["run6"] / f"{j['job_id']}.root"),
            f"{EOS_XRD_OUT_BASE}/{j['year']}/{j['run6']}/{j['job_id']}.root",
            j["job_id"] in xrd_present,
            args.max_missing_frac if run_gap_map.get(j["run6"], False) else 0.001,
        )
        for j in jobs
    ]
    valid_map: dict[str, bool] = {}
    tot_t, tot_f = 0, 0
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as ex:
        for jid, ok, n_t, n_f in ex.map(check_valid_rc_output, check_items, chunksize=32):
            valid_map[jid] = ok
            if ok:
                tot_t += n_t
                tot_f += n_f

    remaining = [j for j in jobs if not valid_map.get(j["job_id"], False)]
    print(f"[RC2526] Completed: {len(jobs) - len(remaining)}/{len(jobs)} shards, remaining={len(remaining)} (matched_events={tot_f}/{tot_t})")
    if not remaining or args.status_only:
        return

    if args.limit > 0:
        remaining = remaining[: args.limit]
    if args.dry_run:
        print(f"[RC2526] Dry-run: would submit {len(remaining)} jobs; sample={remaining[0]}")
        return

    if args.run_local_remaining:
        n_par = min(4, len(remaining))
        t_per = max(1, args.workers // n_par)
        print(f"[RC2526 local] Running {len(remaining)} remaining shards ({n_par} parallel jobs x {t_per} threads)...", flush=True)

        def _run_one_local(j: dict[str, Any]) -> str:
            tmp_out = Path(f"/tmp/rc_local_{j['job_id']}.root")
            xrd_dest = f"{EOS_XRD_OUT_BASE}/{j['year']}/{j['run6']}/{j['job_id']}.root"
            mmf = args.max_missing_frac if run_gap_map.get(j["run6"], False) else 0.001
            cmd = [
                str(REPO_DIR / "build/raw_reduced_charge_dumper"),
                "--run", str(j["run"]),
                "--phys-files", ",".join(j["files"]),
                "--raw-dir", f"/eos/experiment/faser/raw/{j['year']}/{j['run6']}",
                "--filter-mode", "long_tracks",
                "--vv-diff", "33.166",
                "--vt-diff", "34.930",
                "--vp-diff", "13.330",
                "--max-missing-frac", str(mmf),
                "--threads", str(t_per),
                "-o", str(tmp_out),
            ]
            if j["disable_ps"]:
                cmd.append("--disable-ps")
            try:
                p = subprocess.run(cmd, capture_output=True, text=True)
                if p.returncode != 0:
                    raise RuntimeError(f"{j['job_id']} failed rc={p.returncode}:\n{p.stdout[-600:]}\n{p.stderr[-600:]}")
                subprocess.run(["xrdcp", "--retry", "3", "--silent", "--force", str(tmp_out), xrd_dest], check=True)
                last_raw = [ln for ln in p.stdout.splitlines() if "[RC] RAW done" in ln]
                return f"{j['job_id']} (miss_tol={mmf}): {last_raw[-1] if last_raw else 'OK'}"
            finally:
                tmp_out.unlink(missing_ok=True)

        with concurrent.futures.ThreadPoolExecutor(max_workers=n_par) as ex:
            for msg in ex.map(_run_one_local, remaining):
                print(f"  [RC2526 local DONE] {msg}", flush=True)
        return

    bundle_path = write_worker_bundle(AFS_CONDOR_BASE, remaining)
    runner_path = write_runner_script(AFS_CONDOR_BASE)

    arg_lines = [
        f"{j['job_id']} {j['run']} {j['run6']} {j['year']} {1 if j['disable_ps'] else 0} {args.cpus}"
        for j in remaining
    ]
    args_file = AFS_CONDOR_BASE / "pending_jobs.args"
    args_file.write_text("\n".join(arg_lines) + "\n")

    sub_text = f"""universe = vanilla
initialdir = {AFS_CONDOR_BASE}
executable = /bin/bash
transfer_executable = False
arguments = {runner_path.name} $(job_id) $(run) $(run6) $(year) $(disable_ps) $(threads)
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
+NuMuStage = "rc2526-prod"
output = {logs_dir}/$(job_id)_$(ClusterId).out
error = {logs_dir}/$(job_id)_$(ClusterId).err
log = {logs_dir}/condor_rc2526.log
queue job_id, run, run6, year, disable_ps, threads from {args_file}
"""
    sub_file = AFS_CONDOR_BASE / "rc2526_prod.sub"
    sub_file.write_text(sub_text)
    print(f"[RC2526] Bundle size: {bundle_path.stat().st_size / (1024.0 * 1024.0):.2f} MB")

    sub_env = dict(os.environ)
    sub_env["_condor_TOOL_TIMEOUT"] = "120"
    res = subprocess.run(["condor_submit", str(sub_file)], cwd=str(AFS_CONDOR_BASE), env=sub_env, capture_output=True, text=True)
    print(res.stdout.strip())
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr)
        raise SystemExit(res.returncode)


if __name__ == "__main__":
    main()
