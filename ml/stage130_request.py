"""Truth-only original-selection superset, before compatible reconstruction."""
import json
import sys
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

root, index, limit = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
source = json.loads((root / 'workbook/stage130_energy_ml/source_protocol.json').read_text())['sources'][index]
assert source['eligible'] and not source['old_locked']
with uproot.open(source['input'], array_cache=None) as f:
    tree = f['nt']
    n = min(limit, tree.num_entries) if limit > 0 else tree.num_entries
    a = tree.arrays(['eventID', 'run'] + ['truth_' + k for k in
                    ['pdg', 'px', 'py', 'pz', 'dec_x', 'dec_y', 'dec_z']], entry_stop=n)
    first = lambda k: ak.to_numpy(ak.fill_none(ak.firsts(a['truth_' + k]), np.nan))
    x, y, z = [first('dec_' + k) for k in 'xyz']
    incoming = np.column_stack([first(k) for k in ['pdg', 'px', 'py', 'pz']])
    keep = (abs(incoming[:, 0]) == 14) & (incoming[:, 3] > 50000) & (x*x + y*y < 10000)
    keep &= ((z > -3000) & (z < -1950)) | ((z > np.float32(-1769.65)) & (z < np.float32(-1619.65)))
    request = dict(source=source, parent_N=n, entries=np.flatnonzero(keep).tolist(),
                   eventID=ak.to_numpy(a.eventID)[keep].tolist(), incoming=incoming[keep].tolist(),
                   rdo='input-RDO.root', requested_bytes=int(f.file.source.num_requested_bytes),
                   full_parent_N=tree.num_entries,
                   parent_schema_missing=[k for k in ['Track_isForward', 'truth_barcode'] if k not in tree])
Path('request.json').write_text(json.dumps(request, separators=(',', ':')) + '\n')
Path('result/request_summary.json').write_text(json.dumps(
    {k: v for k, v in request.items() if k not in ['entries', 'eventID', 'incoming']}, indent=2) + '\n')
