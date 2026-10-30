#!/usr/bin/env python3
"""Collect both measured stage26 Condor batches into one resource table."""
import argparse
import csv
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--base-cluster',type=int,required=True);parser.add_argument('--extension-cluster',type=int,required=True)
    parser.add_argument('--base-schedd',default='bigbird21.cern.ch');parser.add_argument('--extension-schedd',default='bigbird20.cern.ch')
    parser.add_argument('--log-dir',type=Path,required=True);args=parser.parse_args()
    out=args.repo/'workbook/stage26_energy_ml';rows=[];batches=[]
    with tempfile.TemporaryDirectory(prefix='nu_mu_source_resources_') as temporary:
        for kind,cluster,schedd,prefix in [('base',args.base_cluster,args.base_schedd,'ml_source'),
                                           ('extension',args.extension_cluster,args.extension_schedd,'ml_source_ext')]:
            folder=Path(temporary)/kind;folder.mkdir()
            subprocess.run([sys.executable,str(args.repo/'ml/collect_tabular_resources.py'),'--cluster',str(cluster),
                            '--prefix',prefix,'--jobs','7','--gpus','0','--cpus','1','--log-dir',str(args.log_dir),
                            '--report-dir',str(folder)],check=True,capture_output=True,text=True)
            for row in csv.DictReader((folder/'condor_resources.tsv').open(),delimiter='\t'):rows.append({**row,'schedd':schedd,'batch':kind})
            batches.append({**json.loads((folder/'condor_summary.json').read_text()),'schedd':schedd,'batch':kind})
    with (out/'condor_resources.tsv').open('w') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(rows)
    notes=json.loads((out/'submission_notes.json').read_text())['extension_requeue']
    assert notes['all_never_ran'] and notes['remote_wall_s']==0
    summary=dict(batches=batches,successful_jobs=len(rows),all_exit_zero=True,removed_before_running_jobs=notes['removed_jobs'],
                 removed_job_compute_s=notes['remote_wall_s'],remote_cpu_s=sum(b['remote_cpu_s'] for b in batches),
                 wrapper_wall_s=sum(b['wrapper_wall_s'] for b in batches),wrapper_cpu_s=sum(b['wrapper_cpu_s'] for b in batches),
                 wrapper_peak_rss_KiB=max(b['wrapper_peak_rss_KiB'] for b in batches),gpu_allocation_s=0,
                 first_submit_to_last_finish_s=(max(datetime.fromisoformat(r['terminated_local']) for r in rows)-min(datetime.fromisoformat(r['submitted_local']) for r in rows)).total_seconds())
    (out/'condor_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
