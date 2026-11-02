#!/usr/bin/env python3
"""Collect the three successful jobs once; compact summaries, retain exact points."""
import json
import subprocess
import tarfile
import numpy as np

from continuous_response import REPO, OUT, ART, MODELS, begin, resources, save


def main():
    start=begin();assert not (OUT/'collection.json').exists(), 'Already collected'
    history=json.loads(subprocess.check_output(['condor_history','9661766','-limit','3','-json','-attributes',
        'ClusterId,ProcId,ExitCode,NumJobStarts,RemoteUserCpu,RemoteSysCpu,RemoteWallClockTime,BytesRecvd,BytesSent,RequestCpus,RequestMemory'],text=True))
    assert len(history)==3 and all(h['ExitCode']==0 and h['NumJobStarts']==1 for h in history)
    records=[]
    for name in MODELS:
        archive=REPO/'ntuples/energy_ml_stage62'/(name+'.tar.gz')
        archive_bytes=archive.stat().st_size
        with tarfile.open(archive) as tar:
            members=tar.getmembers()
            for member in members:
                assert member.name.startswith(('ml/artifacts/stage62/'+name,'workbook/stage62_energy_ml/'+name))
                assert '..' not in member.name.split('/')
                assert not (REPO/member.name).exists()
            tar.extractall(REPO,filter='data')
        path=ART/name/'predictions.npz';before=path.stat().st_size
        with np.load(path) as z:a={k:z[k] for k in z.files}
        compact={};errors={}
        for key,value in a.items():
            # Exact float64 point estimates, offsets and mode locations survive.
            keep64=key.endswith('_log')
            compact[key]=value.astype('float32') if value.dtype==np.float64 and not keep64 else value
            if compact[key].dtype!=value.dtype:errors[key]=float(np.max(abs(compact[key].astype(float)-value)))
        np.savez_compressed(path,**compact)
        with np.load(path) as z:
            for key,value in compact.items():np.testing.assert_array_equal(z[key],value)
            for key in a:
                if key.endswith('_log'):np.testing.assert_array_equal(z[key],a[key])
        records.append(dict(model=name,job_archive_bytes=archive_bytes,prediction_bytes_before=before,
            prediction_bytes_final=path.stat().st_size,maximum_summary_cast_abs_error=max(errors.values()),cast_errors=errors,
            point_estimates_exact=True))
        archive.unlink()
    payload=REPO/'software/energy-ml-continuous-stage62.tar.gz'
    payload_bytes=payload.stat().st_size;payload.unlink()
    save(OUT/'collection.json',dict(**resources(start),cluster=9661766,jobs=history,
        remote_CPU_s=sum(h['RemoteUserCpu']+h['RemoteSysCpu'] for h in history),
        condor_input_transfer_bytes=sum(h['BytesRecvd'] for h in history),
        transfer_scope='Condor payload transport; xrdcp output and physical EOS traffic separately unmeasured',
        temporary_payload_bytes=payload_bytes,temporary_payload_and_job_archives_removed=True,
        summary_precision='float32 for scores/probabilities/quantiles; float64 exact point/mode log energies',models=records))
    print(json.dumps({k:v for k,v in json.loads((OUT/'collection.json').read_text()).items() if k!='models'},indent=2))


if __name__=='__main__':main()
