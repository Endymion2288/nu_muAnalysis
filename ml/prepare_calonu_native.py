#!/usr/bin/env python3
"""Freeze a bounded stage37 native-response sample from the existing stage36 cache."""
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from calonu_muon_control import manifest, write_json


def main():
    repo = Path(__file__).resolve().parents[1]
    out = repo/'workbook/stage37_energy_ml'
    out.mkdir(exist_ok=True)
    cfg_path = repo/'ml/configs/calonu_native_control.json'
    if cfg_path.exists():
        raise RuntimeError('Protocol already frozen; do not replace selected cases')
    frozen = datetime.now(timezone.utc).isoformat()
    cfg = dict(stage=37, starting_commit='b93abf4', frozen_utc=frozen,
               groups=[0, 5, 6, 11], max_cases=128, regular_per_group=24, diagnostic_per_group=8,
               new_fits=0, new_G4_events=0, source_commit='1ec47efe',
               dictionary_runtime_commit='d32b0ff3cc4a2dad4abfb1474a82422c3c25b305',
               cache='ntuples/energy_ml_stage37', max_condor_jobs=8,
               pilot='Only first native entry of MC100049 first source inspected before freeze; all pilot failures retained',
               bootstrap_replicates=1000, bootstrap_seed=20261104,
               tolerances=dict(raw_charge_absolute_pC=3e-5, waveform_absolute_mV=3e-4),
               data_MC_physics_closure=False)
    rows = {int(row['index']): row for row in manifest(repo)}
    with np.load(repo/'ntuples/energy_ml_stage36/MC.npz') as z:
        d = {key: z[key] for key in z.files}
    requests = []
    for index in cfg['groups']:
        idx = np.flatnonzero(d['group_index'] == index)
        p = d['Track_p0'][idx]/1000
        chosen = []
        for lo, hi in [(100, 250), (250, 1000)]:
            pool = idx[(p >= lo) & (p < hi)]
            chosen += [(int(i), 'regular') for i in pool[np.linspace(0, len(pool)-1, 12).astype(int)]]
        em = np.column_stack([d[f'CaloNu{i}_E_EM'] for i in range(4)])
        status = np.column_stack([d[f'CaloNu{i}_status'] for i in range(4)])
        diagnostics = []
        for label, mask in [('nonfinite', (~np.isfinite(em)).any(axis=1)),
                            ('extreme', (np.isfinite(em) & (abs(em) > 1e6)).any(axis=1)),
                            ('fit_failed', (status & 48 != 0).any(axis=1)),
                            ('negative', (np.isfinite(em) & (em < 0)).any(axis=1))]:
            for i in idx[mask[idx]]:
                if int(i) not in [r[0] for r in chosen+diagnostics]:
                    diagnostics.append((int(i), label))
                    if len(diagnostics) == 8:
                        break
            if len(diagnostics) == 8:
                break
        if len(diagnostics) < 8:
            for i in idx:
                if int(i) not in [r[0] for r in chosen+diagnostics]:
                    diagnostics.append((int(i), 'diagnostic_fill'))
                    if len(diagnostics) == 8:
                        break
        cases = []
        keys = ['eventID', 'Track_p0', 'Track_X_atVetoNu', 'Track_Y_atVetoNu', 'CaloNu0_raw_charge']
        for i, role in chosen+diagnostics:
            cases.append(dict(selected_row=int(d['source_selected_row'][i]), role=role,
                              fingerprint={k: float(d[k][i]) if d[k].dtype.kind == 'f' else int(d[k][i]) for k in keys}))
        phys = Path(rows[index]['input'])
        base = phys.parents[2]
        requests.append(dict(index=index, group=rows[index]['group'], run=int(rows[index]['run']),
                             input_phys=str(phys), input_rdo=str(base/'rdo/s0015'/phys.name.replace('-PHYS.root', '-RDO.root')),
                             input_rec=str(base/'rec/s0015'/phys.name.replace('-PHYS.root', '-xAOD.root')),
                             sim_directory=str(base/'sim/s0015'), cases=cases))
    write_json(cfg_path, cfg)
    for row in requests:
        write_json(out/f'request_{row["index"]}.json', row)
    write_json(out/'preparation.json', dict(frozen_utc=frozen, cases=sum(len(r['cases']) for r in requests),
               regular=96, diagnostic=32, groups=4,
               note='Deterministic p-stratified regular sample; first 8 distinct diagnostics by nonfinite/extreme/fit-failed/negative priority; not an unbiased sample of quality rates'))
    print(json.dumps(cfg))


if __name__ == '__main__':
    main()
