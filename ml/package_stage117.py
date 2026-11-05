"""Standard-library transport only; all numerical work runs in HTCondor."""
import argparse
import ast
import json
import shutil
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage117_energy_ml'
SPOOL=Path.home()/'condor/nu_muAnalysis/stage117'
INPUTS=['ml/stage117_common.py','ml/stage117_folds.py','ml/stage117_head.py',
        'ml/stage115_head.py','ml/stage115_common.py','ml/audited_features.py',
        'ml/configs/audited_features.json','ntuples/energy_ml_stage94/evaluation_input.npz',
        'ntuples/energy_ml_stage94/cal_partition.npz','ntuples/energy_ml_stage87/split.npz',
        'ml/artifacts/stage87/predictions.npz','ntuples/energy_ml_stage55/dataset.npz',
        'ntuples/energy_ml_stage56/readout.npz','workbook/stage87_energy_ml/protocol.json',
        'workbook/stage94_energy_ml/metrics.tsv','workbook/stage117_energy_ml/protocol.json']
INPUTS += [f'ntuples/energy_ml_stage{s}/support.npz' for s in [70,81,82,83]]


def compact():
    """Losslessly replace repeated solver/decision JSON with local references."""
    changed=[]
    for path in sorted(OUT.glob('*_development.json'))+sorted(OUT.glob('*_fit.json'))+[OUT/'complete.json']:
        value=json.loads(path.read_text());before=path.stat().st_size;refs=[]
        for candidate in value.get('candidates',[]):
            if 'solve' in candidate:
                name=candidate['solve']['name']+'_solve.json'
                assert candidate['solve']==json.loads((OUT/name).read_text())
                del candidate['solve'];candidate['solve_ref']=name;refs.append(name)
        if 'solve' in value:
            name=value['solve']['name']+'_solve.json'
            assert value['solve']==json.loads((OUT/name).read_text())
            del value['solve'];value['solve_ref']=name;refs.append(name)
        if 'decision' in value:
            assert value['decision']==json.loads((OUT/'decision.json').read_text())
            del value['decision'];value['decision_ref']='decision.json';refs.append('decision.json')
        if refs:
            path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
            changed.append(dict(path=path.name,before_bytes=before,after_bytes=path.stat().st_size,refs=refs))
    (OUT/'json_compaction.json').write_text(json.dumps(dict(lossless_dictionary_equality_verified=True,
        files=changed,saved_bytes=sum(r['before_bytes']-r['after_bytes'] for r in changed),
        measurements_unchanged=True,no_numerical_execution=True),indent=2)+'\n')


def main(action,phase):
    archive=ROOT/f'software/energy-ml-stage117-{phase}.tar.gz'
    result=ROOT/f'ntuples/energy_ml_stage117/{phase}_result.tar.gz'
    files=INPUTS.copy()
    if phase=='experiment':
        files += ['ml/stage117_run.py','ml/stage117_baselines.py','ml/stage117_report.py',
                  'ml/stage117_supervise.py','ml/stage113_supervise.py',
                  'workbook/stage117_energy_ml/fold_audit.json']
    if action=='package':
        assert not (OUT/f'{phase}_submission.json').exists()
        if phase=='experiment': assert json.loads((OUT/'fold_audit.json').read_text())['passed']
        for n in files:
            assert (ROOT/n).is_file(),n
            if n.endswith('.py'): ast.parse((ROOT/n).read_text())
        with tarfile.open(archive,'w:gz',compresslevel=1) as t:
            for n in files:t.add(ROOT/n,arcname=n)
        SPOOL.mkdir(parents=True,exist_ok=True);(SPOOL/'logs').mkdir(exist_ok=True)
        shutil.copyfile(ROOT/'AnalysisZipFramework/submission/run_ml_stage117.sh',SPOOL/'worker.sh')
        result.parent.mkdir(exist_ok=True)
        (OUT/f'{phase}_package.json').write_text(json.dumps(dict(files=files,archive_bytes=archive.stat().st_size,
            input_bytes=sum((ROOT/n).stat().st_size for n in files),local_event_execution=False),indent=2)+'\n')
        print(phase,'packaged',archive.stat().st_size)
    else:
        with tarfile.open(result) as t:
            for member in t.getmembers():
                if not member.isfile():continue
                p=Path(member.name)
                assert not p.is_absolute() and '..' not in p.parts
                assert p.parts[:2]==('workbook','stage117_energy_ml') or p.parts[:3]==('ml','artifacts','stage117')
                dest=ROOT/p;payload=t.extractfile(member).read();dest.parent.mkdir(parents=True,exist_ok=True)
                if dest.exists() and dest.name not in ['input_validation.json','QA.json','state_coverage.tsv']:
                    assert dest.read_bytes()==payload,str(dest)
                else:dest.write_bytes(payload)
        with tarfile.open(archive) as t:
            for n in files:assert t.extractfile(n).read()==(ROOT/n).read_bytes(),n
        (OUT/f'{phase}_transport.json').write_text(json.dumps(dict(passed=True,input_files=len(files),
            result_bytes=result.stat().st_size,byte_exact=True,local_numerical_execution=False),indent=2)+'\n')
        print(phase,'collected; input bytes exact')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['package','collect','compact'])
    parser.add_argument('phase',choices=['probe','experiment'],nargs='?');args=parser.parse_args()
    if args.action=='compact':compact()
    else:
        assert args.phase is not None
        main(args.action,args.phase)
