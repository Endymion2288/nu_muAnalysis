"""Stage97 dependency-closed packages, actual fixed40 QA, no fits."""
import argparse
import ast
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from joint_candidate_common import REPO, OUT, save


def code_closure(entries):
    found=set();pending=list(entries)
    while pending:
        name=pending.pop()
        if name in found:continue
        found.add(name)
        tree=ast.parse((REPO/name).read_text())
        for node in ast.walk(tree):
            imports=[node.module] if isinstance(node,ast.ImportFrom) else [n.name for n in node.names] if isinstance(node,ast.Import) else []
            for module in imports:
                if not module:continue
                path='ml/'+module.split('.')[0]+'.py'
                if (REPO/path).exists() and path not in found:pending.append(path)
    return sorted(found)


def main(mode):
    assert json.loads((OUT/'admission.json').read_text())['passed']
    code=code_closure(['ml/train_joint_candidates.py','ml/report_joint_candidates.py','ml/qa_joint_report.py','ml/time_joint_worker.py'])
    inputs=['ntuples/energy_ml_stage96/candidates.npz','ntuples/energy_ml_stage96/QA_candidates.npz',
            'workbook/stage96_energy_ml/preprocessing.json','workbook/stage96_energy_ml/input_validation.json',
            'workbook/stage94_energy_ml/preprocessing.json','ml/configs/audited_features.json']
    if mode=='fit':
        inputs += ['ntuples/energy_ml_stage55/dataset.npz','ntuples/energy_ml_stage56/readout.npz']
        inputs += [f'ntuples/energy_ml_stage{s}/support.npz' for s in [70,81,82,83]]
        inputs += ['ntuples/energy_ml_stage87/split.npz','ntuples/energy_ml_stage94/cal_partition.npz']
    else:
        assert json.loads((OUT/'worker_completion.json').read_text())['new_fits']==2
        inputs += ['ntuples/energy_ml_stage94/evaluation_input.npz','ntuples/energy_ml_stage94/cal_partition.npz',
                   'ml/artifacts/stage97/predictions.npz','ml/artifacts/stage96/predictions.npz',
                   'ml/artifacts/stage87/predictions.npz','ml/artifacts/stage94/point_predictions.npz',
                   'workbook/stage94_energy_ml/offsets.tsv','workbook/stage94_energy_ml/metrics.tsv',
                   'workbook/stage96_energy_ml/metrics.tsv','workbook/stage96_energy_ml/sources.json']
        inputs += [f'ntuples/energy_ml_stage92/predictions_{role}.npz' for role in ['cal','test']]
    metadata=[str(p.relative_to(REPO)) for p in sorted(OUT.glob('*.json'))]
    if mode=='report':metadata += [str(p.relative_to(REPO)) for p in sorted(OUT.glob('learning_*.tsv'))]+['workbook/stage97_energy_ml/offsets.tsv']
    archive=REPO/f'software/energy-ml-joint-stage97-{mode}.tar.gz'
    with tarfile.open(archive,'w:gz',compresslevel=1) as tar:
        for name in dict.fromkeys(code+inputs+metadata):tar.add(REPO/name,arcname=name)
    with tempfile.TemporaryDirectory(prefix='stage97_'+mode+'_package_') as directory:
        scratch=Path(directory)
        with tarfile.open(archive) as tar:
            tar.extractall(directory,filter='data')
            for name in code:assert tar.extractfile(name).read()==(REPO/name).read_bytes()
        command=['ml/train_joint_candidates.py','qa'] if mode=='fit' else ['ml/qa_joint_report.py']
        run=subprocess.run([sys.executable,*command],cwd=scratch,capture_output=True,text=True)
        if run.returncode:
            (OUT/(mode+'_package_QA_failure.txt')).write_text(run.stdout+run.stderr)
            raise RuntimeError(run.stderr)
        name='model_QA.json' if mode=='fit' else 'report_QA.json'
        result=json.loads((scratch/'workbook/stage97_energy_ml'/name).read_text())
        record=dict(passed=True,archive_bytes=archive.stat().st_size,code_files_byte_equal=code,
                    identities=40,optimizer_steps=0,result=result)
        if mode=='fit':
            gpu=max(v['end_to_end_forward_backward_wall_s'] for v in result['checks'] if v['device']=='cuda')
            projection=gpu*46*300*2*5+180
            assert projection<3600 and projection+1000<7200
            record['padded_GPU_projected_wall_s']=projection
        save(mode+'_package_QA.json',record)
    shutil.copyfile(REPO/'AnalysisZipFramework/submission/run_ml_joint_candidates.sh','/afs/cern.ch/user/x/xcheng/nu_mu_stage97/worker.sh')
    print(json.dumps(dict(mode=mode,archive_bytes=archive.stat().st_size,passed=True,dependency_files=len(code))),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['fit','report']);main(p.parse_args().mode)
