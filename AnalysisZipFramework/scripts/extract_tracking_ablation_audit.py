#!/usr/bin/env python3
"""Keep selected-path material and pre/post-refit lineage; remove large scratch audits."""
import json
from collections import Counter
from pathlib import Path
import time

import numpy as np


def main():
    start = time.monotonic()
    fields = ['run','event','mode','seed','candidate','stage','px_gev','py_gev','pz_gev',
              'charge','ndof','chi2','refit','majority_barcode','majority_hits','measurements']
    material_fields = ['run','event','mode','seed','candidate','stage','geometry_id',
                       'x0','thickness_mm','path_correction','x_mm','y_mm','z_mm']
    paths = []; materials = []; counts = Counter(); sizes = {}
    stages = ['seed', 'selected', 'converted', 'refit_input', 'refit', 'final', 'selected_state', 'refit_state']
    for mode, name in enumerate(['CKF_woIFT', 'CKF_Back_woIFT']):
        file = Path(name+'.jsonl'); sizes[name] = file.stat().st_size
        with file.open() as f:
            for line in f:
                row = json.loads(line); stage = row['stage']; counts[name+'/'+stage] += 1
                if stage not in stages:
                    continue
                header = [row[k] for k in ['run','event']] + [mode,row['seed'],row['candidate'],stages.index(stage)]
                if stage.endswith('_state'):
                    if 'material_full_X0' in row:
                        surface = np.array(row['surface'])
                        mean = row.get('predicted', row.get('filtered'))
                        position = (surface @ np.array([mean[0],mean[1],0,1]))[:3]
                        materials.append(header + [row['geometry_id'], row['material_full_X0'],
                            row['material_full_thickness_mm'],row['material_path_correction']] + position.tolist())
                else:
                    match = row.get('matches') or [[0,0]]
                    bound = row.get('bound',row.get('bound_trk',[]))
                    charge = row.get('charge', np.sign(bound[4]) if len(bound) > 4 else np.nan)
                    paths.append(header + row.get('momentum_A_GeV',[np.nan]*3) +
                        [charge,row.get('ndof',np.nan),row.get('chi2',np.nan),row.get('refit',-1),
                         match[0][0],match[0][1],row.get('measurements',len(row.get('hits',[])))])
    np.savez_compressed('audit_rows.npz',paths=np.array(paths).reshape(-1,len(fields)), fields=np.array(fields),
        materials=np.array(materials).reshape(-1,len(material_fields)), material_fields=np.array(material_fields),stages=np.array(stages))
    Path('audit_summary.json').write_text(json.dumps(dict(counts=counts, source_bytes=sizes,
        compact_bytes=Path('audit_rows.npz').stat().st_size,wall_s=time.monotonic()-start),indent=2)+'\n')
    for name in sizes:
        Path(name+'.jsonl').unlink()


if __name__ == '__main__':
    main()
