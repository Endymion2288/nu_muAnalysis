"""Stage81 measured QA, actual-package startup, dry run, then one submission."""
import json
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from audited_features import REPO,configuration
from support_augmentation import begin,resources,save,arrays

OUT=REPO/'workbook/stage81_energy_ml'
CACHE=REPO/'ntuples/energy_ml_stage81'


def main():
    start=begin();assert not (OUT/'submission.json').exists()
    p=json.loads((OUT/'source_plan.json').read_text());heads=json.loads((OUT/'headers.json').read_text())
    qa=[json.loads((OUT/f'qa{i}.json').read_text()) for i in range(4)]
    assert sum(q['QA_identity_N'] for q in qa)==40
    compatible=[q['index'] for q in qa if q['compatible']];assert compatible==[0,1]
    assert all(q['original62_raw_exact'] and q['raw_N']==10000 for q in qa if q['compatible'])
    assert all(q['calo_rescaled']==False for q in qa)
    protocol=dict(stage=81,frozen_utc=datetime.now(timezone.utc).isoformat(),sources=p['sources'],seed=p['seed'],
        compatible_source_indices=compatible,unavailable_source_indices=[2,3],unavailable_reason='actual backward-only K PHYS; nominal merge input/paired equivalence not delivered',
        source_probabilities=[s['source_probability'] for s in p['sources']],full_files=True,raw_N=[10000,10000],
        feature_version=configuration()['version'],features=configuration()['features'],model_fits=0,
        QA_unique_identities=40,QA_pi_selected_N=[q['extraction']['selected_N'] for q in qa if q['compatible']],
        request_cpus=1,memory_MB=3000,MaxRuntime=3600,worker_timeout_s=3500,worker_CPU_soft_hard_s=[3300,3350],
        total_CPU_max_s=7200,input_limit_bytes=10000000000,retained_limit_bytes=10000000,
        cost_basis='actual same-source 10-event selection/62 build CPU and RSS; complete-file costs not measured yet; hard cap and no retry, no prefix yield extrapolation guarantee',
        actual_input_bytes=sum(s['file_bytes'] for s in p['sources'] if s['index'] in compatible),
        identity='all stage55 exposed native-MeV incoming plus actual stage70 new28, then stable within/across sources; development enrichment only',
        Calo='native reference01-LG; no scale conversion, full produced matrices retained without second scaling',
        genealogy='full parent/subfile/seed unproven; no independent confirmation claim')
    assert not (OUT/'protocol.json').exists();save(OUT/'protocol.json',protocol)
    paths=['build/analysis','AnalysisZipFramework/config','AnalysisZipFramework/include',
        'ml/extract_phys_support.py','ml/extract_alternative_support.py','ml/audited_features.py',
        'ml/frozen_evaluation.py','ml/track_response.py','ml/train_bdt.py',
        'ml/configs/alternative_support_pilot.json','ml/configs/audited_features.json','ml/configs/baseline.yaml',
        'ml/configs/track_response.yaml','workbook/stage81_energy_ml/protocol.json']
    paths += [str(x.relative_to(REPO)) for x in (REPO/'build').glob('*.so')]
    archive=REPO/'software/energy-ml-phys-support-stage81.tar.gz';assert not archive.exists()
    with tarfile.open(archive,'w:gz',compresslevel=1) as t:
        for x in paths:t.add(REPO/x,arcname=x)
    # Real extraction from the actual payload on the SAME two ten-entry QA sets.
    # No new identity or shortened formal source is introduced.
    import ROOT
    ROOT.gROOT.SetBatch(True);checks=[]
    with tempfile.TemporaryDirectory(prefix='stage81_package_') as td:
        tmp=Path(td)
        with tarfile.open(archive) as t:t.extractall(tmp,filter='data')
        (tmp/'ntuples/energy_ml_stage81').mkdir(parents=True)
        for i in compatible:
            src=ROOT.TFile.Open(p['sources'][i]['input']);tree=src.Get('nt')
            target=ROOT.TFile.Open(str(tmp/f'qa{i}.root'),'RECREATE');target.cd();clone=tree.CloneTree(10);clone.Write()
            rootbytes=int(src.GetBytesRead());target.Close();src.Close()
            subprocess.run([sys.executable,str(tmp/'ml/extract_phys_support.py'),'--index',str(i),'--qa-input',str(tmp/f'qa{i}.root')],check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            a=arrays(tmp/f'ntuples/energy_ml_stage81/package_qa{i}.npz');b=arrays(CACHE/f'qa{i}.npz')
            import numpy as np
            for k in b:np.testing.assert_array_equal(a[k],b[k])
            md=json.loads(str(a['metadata_json']));checks.append(dict(index=i,all_arrays_exact=True,ROOT_clone_requested_bytes=rootbytes,
                Uproot_requested_bytes=md['requested_uproot_bytes'],child_CPU_s=md['child_user_s']+md['child_system_s'],model_fits=0))
    save(OUT/'package_QA.json',dict(actual_payload=True,payload_bytes=archive.stat().st_size,records=checks,new_identities=0,**resources(start)))
    spool=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage81');(spool/'logs').mkdir(exist_ok=True,parents=True)
    worker=spool/'worker_v1.sh';assert not worker.exists();worker.write_bytes((REPO/'AnalysisZipFramework/submission/run_ml_phys_support.sh').read_bytes())
    submit=REPO/'AnalysisZipFramework/submission/ml_phys_support.sub'
    dry=subprocess.check_output(['condor_submit','-dry-run',str(spool/'dryrun.ads'),str(submit)],text=True)
    ads=''.join((spool/'dryrun.ads').read_text().split())
    assert 'MaxRuntime=3600' in ads and 'RequestCpus=1' in ads and 'RequestMemory=3000' in ads
    save(OUT/'dryrun.json',dict(output=dry,MaxRuntime=3600,RequestCpus=1,RequestMemory=3000))
    result=subprocess.check_output(['condor_submit','-terse',str(submit)],text=True);cluster=int(result.split('.')[0])
    scheduled=json.loads(subprocess.check_output(['condor_q',str(cluster),'-json','-attributes','ClusterId,ProcId,RequestCpus,RequestMemory,MaxRuntime,Args'],text=True))
    assert len(scheduled)==2 and all(r['RequestCpus']==1 and r['RequestMemory']==3000 and r['MaxRuntime']==3600 for r in scheduled)
    save(OUT/'submission.json',dict(cluster=cluster,submitted_utc=datetime.now(timezone.utc).isoformat(),jobs=2,
        actual_ads=scheduled,payload_bytes=archive.stat().st_size,paths=paths,**resources(start)))
    print(result,flush=True)


if __name__=='__main__':main()
