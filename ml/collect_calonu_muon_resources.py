#!/usr/bin/env python3
"""Collect stage36 logs through temporary aliases expected by the shared collector."""
import subprocess
import sys
import tempfile
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
logs = Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage36/logs')
out = repo/'workbook/stage36_energy_ml/resources'
out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='stage36_resource_log_alias_') as directory:
    alias = Path(directory)
    (alias/'stage36_2187200.log').symlink_to(logs/'2187200.log')
    for index in range(18):
        (alias/f'stage36_2187200.{index}.err').symlink_to(logs/f'2187200.{index}.err')
    subprocess.run([sys.executable, str(repo/'ml/collect_tabular_resources.py'), '--cluster', '2187200',
                    '--prefix', 'stage36', '--jobs', '18', '--cpus', '1', '--gpus', '0',
                    '--memory-mb', '2000', '--log-dir', str(alias), '--report-dir', str(out)], check=True)
