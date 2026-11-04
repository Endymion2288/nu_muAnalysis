"""Stage99 input manifests; package bytes only, never execute local CERN QA."""
import argparse
import json
import shutil
import tarfile
from pathlib import Path

R = Path(__file__).resolve().parents[1]
O = R / 'workbook/stage99_energy_ml'
BASE = ['ntuples/energy_ml_stage55/dataset.npz',
        'ntuples/energy_ml_stage56/readout.npz'] + [
    f'ntuples/energy_ml_stage{s}/support.npz' for s in [70, 81, 82, 83]]
SAVED = ['ntuples/energy_ml_stage94/evaluation_input.npz',
         'ntuples/energy_ml_stage94/cal_partition.npz',
         'ml/artifacts/stage94/MDN_heads.npz',
         'ml/artifacts/stage94/point_predictions.npz',
         'ml/artifacts/stage87/predictions.npz'] + [
    f'ntuples/energy_ml_stage92/predictions_{r}.npz' for r in ['cal', 'test']]
COHORT = ['ntuples/energy_ml_stage95/' + n for n in
          ['cohort.json', 'events.tsv', 'candidates.tsv']]


def inputs(mode):
    files = [str(p.relative_to(R)) for p in sorted((R/'ml').glob('stage99_*.py'))]
    files += ['ml/energy_probability_scale.py', 'ml/audited_features.py',
              'ml/configs/audited_features.json']
    if mode in ['qa', 'report', 'validate']:
        files += SAVED
    if mode in ['nativeqa', 'bqa', 'breport', 'bfinish', 'validate']:
        files += COHORT
    if mode == 'nativeqa':
        files += ['AnalysisZipFramework/submission/merge_manifest.tsv']
    if mode in ['breport', 'bfinish']:
        files += BASE
    if mode in ['report', 'validate']:
        files += ['workbook/stage87_energy_ml/prior.json',
                  'workbook/stage94_energy_ml/offsets.tsv']
    if mode == 'validate':
        files += ['workbook/stage94_energy_ml/metrics.tsv',
                  'workbook/stage94_energy_ml/scores.tsv']
    if mode in ['bfinish', 'validate']:
        files += ['ntuples/energy_ml_stage99/' + n for n in
                  ['B_collection_features.tsv', 'B_identities.tsv']]
    if mode == 'validate':
        files += ['ntuples/energy_ml_stage99/B_classifier_predictions.tsv']
    files += [str(p.relative_to(R)) for p in sorted(O.glob('*'))
              if p.is_file() and p.suffix in ['.json', '.tsv', '.txt']]
    return sorted(set(files))


def main(mode):
    if mode == 'report' and (O/'calibration.json').exists():
        raise RuntimeError('The one allowed scalar calibration is already complete.')
    if mode in ['breport', 'bfinish'] and (O/'B_complete.json').exists():
        raise RuntimeError('Both Stage99 classifier fits are already used.')
    if mode == 'breport' and (O/'B_failure.json').exists():
        raise RuntimeError('A has already fitted; use only the unused B via bfinish.')
    files = inputs(mode)
    archive = R / f'software/energy-ml-stage99-{mode}.tar.gz'
    with tarfile.open(archive, 'w:gz', compresslevel=1) as tar:
        for name in files:
            tar.add(R/name, arcname=name)
    spool = Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage99')
    (spool/'logs').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(R/'AnalysisZipFramework/submission/run_ml_stage99.sh', spool/'worker.sh')
    print(json.dumps(dict(mode=mode, files=len(files), archive_bytes=archive.stat().st_size,
                          local_numerical_QA=False, new_fits=0)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['qa', 'nativeqa', 'report', 'bqa', 'breport', 'bfinish', 'validate'])
    main(parser.parse_args().mode)
