"""Full versus sparse digitization/reconstruction event identity and response."""
import json

import awkward as ak
import numpy as np
import uproot

from stage119_curve_common import CACHE,OUT


def main():
    rows=[]
    for run in [200300,200303]:
        with uproot.open(CACHE/f'pythiaqa_{run}.root') as f:a=f['nt'].arrays()
        with uproot.open(CACHE/f'pythiasparseqa2_{run}.root') as f:b=f['nt'].arrays()
        assert a.fields==b.fields and len(b)==6
        expected=a[[0,3,9,15,23,39]];diff=[]
        for name in a.fields:
            try:
                x,y=ak.to_list(expected[name]),ak.to_list(b[name])
                if isinstance(x[0],list):
                    assert list(map(len,x))==list(map(len,y))
                    x=ak.to_numpy(ak.flatten(expected[name]));y=ak.to_numpy(ak.flatten(b[name]))
                np.testing.assert_array_equal(x,y)
            except AssertionError:diff.append(name)
        # Sparse digitization must reproduce every output including channel
        # noise and tracking; eventID alone is insufficient to establish this.
        rows.append(dict(run=run,events=6,columns=len(a.fields),different_columns=diff,exact=not diff))
    (OUT/'pythiasparsecheck.json').write_text(json.dumps(dict(passed=all(r['exact'] for r in rows),results=rows),indent=2)+'\n')
    assert all(r['exact'] for r in rows),rows
    print(rows,flush=True)


if __name__=='__main__':main()
