"""Stage82 measured input QA, actual-payload zero-fit check, then two curve jobs."""
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from audited_features import REPO
from support_augmentation import save, arrays

OUT = REPO/'workbook/stage82_energy_ml'

if __name__ == '__main__':
    assert not (OUT/'curve_submission.json').exists()
    assert json.loads((OUT/'input_QA.json').read_text())['passed']
    paths = ['ml/k_support_curve.py','ml/audited_features.py','ml/alternative_calibration.py',
             'ml/frozen_evaluation.py','ml/track_response.py','ml/train_bdt.py','ml/support_augmentation.py',
             'ml/configs/audited_features.json','ml/configs/baseline.yaml','ml/configs/track_response.yaml',
             'ntuples/energy_ml_stage82/input.npz','workbook/stage82_energy_ml/protocol.json']
    archive = REPO/'software/energy-ml-k-curve-stage82.tar.gz'
    assert not archive.exists()
    with tarfile.open(archive,'w:gz',compresslevel=1) as t:
        for p in paths:
            t.add(REPO/p,arcname=p)
    # Exercise the exact transferred arrays/feature names in clean child startup,
    # without invoking the formal fit entry point or a baseline model.
    with tempfile.TemporaryDirectory(prefix='curve82_payload_') as td:
        with tarfile.open(archive) as t:
            t.extractall(td,filter='data')
        check = '''import json,sys,numpy as np,xgboost as x
sys.path.insert(0,'ml')
import k_support_curve
from pathlib import Path
p=json.load(open('workbook/stage82_energy_ml/protocol.json'))
with np.load('ntuples/energy_ml_stage82/input.npz') as d:
 for arm in ['half','full']:
  take=d['half'] if arm=='half' else np.ones(len(d['new_incoming']),bool)
  dm=x.DMatrix(np.concatenate([d['old_train_x'],d['new_x'][take]]),label=np.r_[d['old_train_y'],np.log(d['new_truth_E_GeV'][take])],feature_names=p['features'],nthread=1)
  assert dm.num_row()==p['train_N'][arm] and dm.num_col()==62 and dm.get_weight().size==0
assert x.__version__==p['xgboost_version']
print('actual-payload two-arm DMatrix QA passed; zero fits')
'''
        result = subprocess.check_output([sys.executable,'-c',check],cwd=td,text=True)
    spool = Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage82_curve')
    (spool/'logs').mkdir(parents=True,exist_ok=True)
    (spool/'worker_v1.sh').write_bytes((REPO/'AnalysisZipFramework/submission/run_ml_k_support_curve.sh').read_bytes())
    submit = REPO/'AnalysisZipFramework/submission/ml_k_support_curve.sub'
    dry = subprocess.check_output(['condor_submit','-dry-run',str(spool/'dryrun.ads'),str(submit)],text=True)
    ads = ''.join((spool/'dryrun.ads').read_text().split())
    assert 'MaxRuntime=1800' in ads and 'RequestCpus=1' in ads and 'RequestMemory=3000' in ads
    output = subprocess.check_output(['condor_submit','-terse',str(submit)],text=True)
    cluster = int(output.split('.')[0])
    actual = json.loads(subprocess.check_output(['condor_q',str(cluster),'-json','-attributes','ClusterId,ProcId,MaxRuntime,RequestCpus,RequestMemory,Args'],text=True))
    save(OUT/'curve_submission.json',dict(cluster=cluster,actual_ads=actual,actual_package_QA=result,payload_bytes=archive.stat().st_size,paths=paths,dryrun=dry,formal_fits=6))
    # CERN maps espresso to 1200s after submission; 1800s is the contract ceiling.
    assert len(actual)==2 and all(900<=a['MaxRuntime']<=1800 and a['RequestCpus']==1 and a['RequestMemory']==3000 for a in actual)
    print(output)
