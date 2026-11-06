"""Scoped HTCondor resource ledger, including pilot and any failed attempts."""
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage125_energy_ml'


def main():
    fields=['ClusterId','ProcId','JobStatus','ExitCode','ExitBySignal','RemoteUserCpu','RemoteSysCpu',
            'RemoteWallClockTime','MemoryUsage','DiskUsage','RequestCpus','RequestMemory',
            'JobStartDate','CompletionDate','NumJobStarts','Args','NuMuStage','ResidentSetSize']
    first_submission=min(int(p.stem.rsplit('_',1)[1])//1000000000 for p in OUT.glob('pilot_submission_*.json'))
    cmd=['condor_history','-constraint','NuMuStage == "energy-ml-stage125"','-since',f'CompletionDate < {first_submission}','-json','-attributes',','.join(fields),'-match','2000']
    records=json.loads(subprocess.check_output(cmd,text=True))
    queue_output=subprocess.check_output(['condor_q','-constraint','NuMuStage == "energy-ml-stage125"','-json','-attributes','ClusterId,ProcId,JobStatus,Args'],text=True)
    queue=json.loads(queue_output) if queue_output.strip() else []
    summary=dict(completed_history_jobs=len(records),current_queue_jobs=len(queue),
                 removed_history_jobs=sum(r.get('JobStatus')==3 for r in records),
                 failed_history_jobs=sum(r.get('ExitCode',0)!=0 or r.get('ExitBySignal',False) for r in records),
                 CPU_s=sum(r.get('RemoteUserCpu',0)+r.get('RemoteSysCpu',0) for r in records),
                 sum_job_wall_s=sum(r.get('RemoteWallClockTime',0) for r in records),
                 maximum_job_MemoryUsage_MB=max((r['MemoryUsage'] if isinstance(r.get('MemoryUsage'),(int,float)) else r.get('ResidentSetSize',0)/1024 for r in records),default=0),
                 maximum_job_DiskUsage_KiB=max((r.get('DiskUsage',0) for r in records),default=0),
                 definition='Whole-job CPU and sum of job wall times; do not add nested GNU step timings again. Memory is maximum reported single-job memory, not concurrent aggregate.')
    (OUT/'condor_resources.json').write_text(json.dumps(dict(summary=summary,jobs=records,current_queue=queue),indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
