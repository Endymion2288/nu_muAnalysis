"""Reproducible Stage96 batch packages and actual-package QA, never starts a fit."""
import argparse
import ast
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import numpy as np

REPO=Path(__file__).resolve().parents[1]
OUT=REPO/'workbook/stage96_energy_ml'
CACHE=REPO/'ntuples/energy_ml_stage96'


def main(mode):
    assert json.loads((OUT/'admission.json').read_text())['passed']
    code=['ml/prepare_candidate_ablation.py','ml/track_candidate_information.py','ml/time_candidate_worker.py'] if mode=='extract' else [str(p.relative_to(REPO)) for p in sorted((REPO/'ml').glob('*.py'))]
    for name in code:ast.parse((REPO/name).read_text())
    inputs=['ntuples/energy_ml_stage96/manifest.npz'] if mode=='extract' else ['ntuples/energy_ml_stage96/candidates.npz','ntuples/energy_ml_stage96/QA_candidates.npz','ml/configs/audited_features.json']
    if mode=='fit':
        assert json.loads((OUT/'extraction.json').read_text())['passed']
        inputs += ['ntuples/energy_ml_stage55/dataset.npz','ntuples/energy_ml_stage56/readout.npz']+[f'ntuples/energy_ml_stage{s}/support.npz' for s in [70,81,82,83]]
        inputs += ['ntuples/energy_ml_stage87/split.npz','ntuples/energy_ml_stage94/cal_partition.npz','workbook/stage94_energy_ml/preprocessing.json']
    if mode=='report':
        assert json.loads((OUT/'worker_completion.json').read_text())['new_fits']==2
        inputs += ['ntuples/energy_ml_stage94/evaluation_input.npz','ntuples/energy_ml_stage94/cal_partition.npz',
                   'ml/artifacts/stage96/predictions.npz','ml/artifacts/stage87/predictions.npz','ml/artifacts/stage94/point_predictions.npz',
                   'workbook/stage94_energy_ml/offsets.tsv','workbook/stage94_energy_ml/metrics.tsv']
        inputs += [f'ntuples/energy_ml_stage92/predictions_{role}.npz' for role in ['cal','test']]
    metadata=[str(p.relative_to(REPO)) for p in sorted(OUT.glob('*.json'))]
    if mode=='report':metadata += [str(p.relative_to(REPO)) for p in sorted(OUT.glob('learning_*.tsv'))]+['workbook/stage96_energy_ml/offsets.tsv']
    archive=REPO/f'software/energy-ml-candidates-stage96-{mode}.tar.gz'
    with tarfile.open(archive,'w:gz',compresslevel=1) as t:
        for name in dict.fromkeys(code+inputs+metadata):t.add(REPO/name,arcname=name)
    with tempfile.TemporaryDirectory(prefix='stage96_'+mode+'_package_QA_') as directory:
        scratch=Path(directory)
        with tarfile.open(archive) as t:
            t.extractall(directory,filter='data')
            for name in code:assert t.extractfile(name).read()==(REPO/name).read_bytes()
        if mode=='extract':
            p=scratch/'ntuples/energy_ml_stage96/manifest.npz'
            with np.load(p) as z:m={k:z[k][z['qa']] for k in z.files}
            np.savez_compressed(p,**m)
            command=['ml/prepare_candidate_ablation.py','extract','--processes','8']
        elif mode=='fit':command=['ml/train_candidate_ablation.py','qa']
        else:command=['ml/qa_candidate_report.py']
        run=subprocess.run([sys.executable,*command],cwd=scratch,capture_output=True,text=True)
        if run.returncode:
            (OUT/(mode+'_package_QA_failure.txt')).write_text(run.stdout+run.stderr)
            raise RuntimeError(run.stderr)
        if mode=='extract':
            with np.load(scratch/'ntuples/energy_ml_stage96/candidates.npz') as a,np.load(CACHE/'QA_candidates.npz') as b:
                for k in b.files:np.testing.assert_array_equal(a[k],b[k])
                np.testing.assert_array_equal(a['source'],m['source'])
            result=json.loads((scratch/'workbook/stage96_energy_ml/extraction.json').read_text())
        else:
            name='model_QA.json' if mode=='fit' else 'report_QA.json'
            result=json.loads((scratch/'workbook/stage96_energy_ml'/name).read_text())
        record=dict(passed=True,archive_bytes=archive.stat().st_size,source_files_byte_equal=code,identities=40,optimizer_steps=0,result=result)
        if mode=='fit':
            projection=max(r['batch1024_forward_backward_wall_s'] for r in result['checks'])*46*300*2*5+180
            assert projection<7200
            record['padded_GPU_projected_wall_s']=projection
        (OUT/(mode+'_package_QA.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    shutil.copyfile(REPO/'AnalysisZipFramework/submission/run_ml_candidate_ablation.sh','/afs/cern.ch/user/x/xcheng/nu_mu_stage96/worker.sh')
    print(json.dumps(dict(mode=mode,archive_bytes=archive.stat().st_size,passed=True)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['extract','fit','report']);main(p.parse_args().mode)
