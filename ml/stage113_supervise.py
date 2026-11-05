"""Actual own + reaped-descendant CPU watchdog, separate worker process group."""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]/'workbook/stage113_energy_ml'
TICKS = os.sysconf('SC_CLK_TCK')


def cpu_tree(root):
    processes = {}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            fields = (p/'stat').read_text().rsplit(')', 1)[1].split()
            processes[int(p.name)] = (int(fields[1]), sum(int(fields[i]) for i in [11, 12, 13, 14])/TICKS)
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    selected = {root}
    while True:
        more = {pid for pid, (parent, _) in processes.items() if parent in selected}
        if more <= selected:
            break
        selected |= more
    return sum(processes[p][1] for p in selected if p in processes), len(selected)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    contract = json.loads((OUT/'protocol.json').read_text())['execution_contract']
    limit = contract['limits_including_stage112']['remaining_CPU_s']-60
    start = time.monotonic()
    # A tiny test only of the changed counter path, no event QA or benchmark.
    before, _ = cpu_tree(os.getpid())
    subprocess.run([sys.executable, '-c', 'sum(i*i for i in range(200000))'], check=True)
    after, _ = cpu_tree(os.getpid())
    assert after >= before
    probe = dict(reaped_child_counted=True, before_CPU_s=before, after_CPU_s=after)
    child = subprocess.Popen([sys.executable, '-u', 'ml/stage113_measure.py'], start_new_session=True)
    peak, max_processes, stop = 0., 0, None
    while child.poll() is None:
        value, n = cpu_tree(os.getpid())
        peak, max_processes = max(peak, value), max(max_processes, n)
        if value >= limit or time.monotonic()-start >= 825:
            stop = 'CPU reserve threshold' if value >= limit else 'wall reserve threshold'
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            break
        time.sleep(.5)
    code = child.wait()
    final, _ = cpu_tree(os.getpid())
    record = dict(passed=stop is None and code == 0, stop=stop, worker_exit=code,
                  monitored_CPU_s=max(peak, final), monitored_wall_s=time.monotonic()-start,
                  CPU_stop_threshold_s=limit, wall_stop_threshold_s=825,
                  maximum_observed_process_count=max_processes, counter_probe=probe,
                  method='sum live tree own+reaped-child CPU, each dead subtree accounted in its nearest live ancestor; proc snapshot races covered by60CPU s reserve; GNU final total authoritative')
    (OUT/'watchdog.json').write_text(json.dumps(record, indent=2)+'\n')
    return 124 if stop else code


if __name__ == '__main__':
    raise SystemExit(main())
