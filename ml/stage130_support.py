"""Full-file pilot support/cost, including conservative historical exposure purge."""
import csv
import json
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage130_energy_ml'
CACHE = ROOT / 'ntuples/energy_ml_stage130'


def main():
    plan = json.loads((OUT / 'source_protocol.json').read_text())
    pilot = json.loads((OUT / 'support_pilot_contract.json').read_text())
    inputs = json.loads((ROOT / 'workbook/stage119_energy_ml/exposure_inputs.json').read_text())
    inputs += ['ntuples/energy_ml_stage119/curve_input.npz']
    old64, old32 = set(), set()
    for name in inputs:
        with np.load(ROOT / name) as z:
            old64.update(map(tuple, z['incoming']))
            old32.update(map(tuple, z['incoming'].astype('float32')))
    rows, costs, identities = [], [], []
    for index in pilot['indices']:
        directory = CACHE / f'support_{index}'
        assert int((directory / 'exitcode.txt').read_text()) == 0, index
        source = plan['sources'][index]
        qa = json.loads((directory / 'source_qa.json').read_text())
        assert qa['schema_and_typed_domains_passed'] and qa['predictions'] == 0
        identities.append(dict(index=index, exact_identity=qa['feature_metadata']['parent_identity'],
                               calibration=qa['feature_metadata']['calibration']))
        with np.load(directory / 'selected.npz') as z:
            e, pz, y = z['truth_E_GeV'], z['reco_pz_GeV'], z['y_lepton']
            incoming = z['incoming']
            old_exact = np.array([tuple(k) in old64 for k in incoming])
            old_conservative = np.array([tuple(k) in old32 for k in incoming.astype('float32')])
            known = old_exact | old_conservative
            _, gid, counts = np.unique(incoming, axis=0, return_inverse=True, return_counts=True)
            weights = 1 / counts[gid]
            layers = dict(all=np.ones(len(e), bool), E50_100=(e >= 50) & (e < 100),
                          E100_200=(e >= 100) & (e < 200), lowpz_highE=(pz < 100) & (e >= 200),
                          high_y=np.isfinite(y) & (y >= .8) & (y < 1), highE=e >= 1000)
            probability = pilot['inclusion_probabilities'][str(index)]
            for layer, mask in layers.items():
                new = mask & ~known
                w = weights[new]
                rows.append(dict(index=index, run=source['run'], component=source['component'],
                    inherited_role=source['inherited_role'], layer=layer,
                    parent_N=qa['parent_N'], truth_superset_N=qa['truth_superset_N'],
                    selected_N=int(mask.sum()), old_exact_overlap_N=int((mask & old_exact).sum()),
                    conservative_only_overlap_N=int((mask & ~old_exact & old_conservative).sum()),
                    new_records_N=int(new.sum()), new_incoming_N=len(np.unique(incoming[new], axis=0)),
                    new_ESS=float(w.sum()**2/(w@w)) if len(w) else 0,
                    source_probability=probability,
                    HT_new_records_estimate=float(new.sum()/probability)))
        for path in directory.glob('*_time.txt'):
            text = path.read_text()
            values = dict(index=index, step=path.stem, CPU_s=0.0)
            for key, label in [('user_s', 'User time (seconds)'), ('system_s', 'System time (seconds)'),
                               ('RSS_KiB', 'Maximum resident set size (kbytes)')]:
                match = re.search(re.escape(label) + r':\s*([0-9.]+)', text)
                if match:
                    values[key] = float(match[1])
            values['CPU_s'] = values.get('user_s', 0) + values.get('system_s', 0)
            match = re.search(r'Elapsed \(wall clock\) time \(h:mm:ss or m:ss\):\s*([0-9:.]+)', text)
            if match:
                values['wall_s'] = sum(float(v)*60**i for i, v in enumerate(reversed(match[1].split(':'))))
            costs.append(values)
    for name, records in [('pilot_support.tsv', rows), ('pilot_step_cost.tsv', costs)]:
        with (OUT / name).open('w') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(k for r in records for k in r)),
                                    delimiter='\t', lineterminator='\n')
            writer.writeheader()
            writer.writerows(records)
    summary = dict(parent_N=sum(r['parent_N'] for r in rows if r['layer'] == 'all'),
                   selected_N=sum(r['selected_N'] for r in rows if r['layer'] == 'all'),
                   new_selected_N=sum(r['new_records_N'] for r in rows if r['layer'] == 'all'),
                   new_lowest_N=sum(r['new_records_N'] for r in rows if r['layer'] == 'E50_100'),
                   new_second_N=sum(r['new_records_N'] for r in rows if r['layer'] == 'E100_200'),
                   nested_step_CPU_s=sum(r['CPU_s'] for r in costs),
                   old_exposure_keys64=len(old64), old_exposure_keys32=len(old32),
                   files=len(pilot['indices']), identities=identities,
                   scope='one uniform complete source per run; HT point estimates only, single-file per-run variance unmeasured; no GENIE seed or blind certification',
                   new_model_fits=0, predictions=0)
    (OUT / 'pilot_support_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print({k: v for k, v in summary.items() if k != 'identities'}, flush=True)


if __name__ == '__main__':
    main()
