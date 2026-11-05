"""Exact original versus sparse reconstruction QA on all ntuple columns."""
import json
from pathlib import Path

import awkward as ak
import uproot

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage119_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage119'


def main():
    results=[]
    for run in [200131,200184,200110]:
        with uproot.open(CACHE/f'recoqa_{run}.root') as f:a=f['nt'].arrays()
        with uproot.open(CACHE/f'sparseqa2_{run}.root') as f:b=f['nt'].arrays()
        assert a.fields==b.fields and len(b)==6
        expected=a[[0,3,9,15,23,39]];different=[]
        for name in a.fields:
            if not ak.almost_equal(expected[name],b[name],rtol=0,atol=0):different.append(name)
        # ak.almost_equal treats the same NaN as unequal. Check those branches
        # numerically with identical NaN locations, without masking differences.
        import numpy as np
        for name in different:
            x,y=ak.to_list(expected[name]),ak.to_list(b[name])
            if isinstance(x[0],list):
                assert [len(v) for v in x]==[len(v) for v in y]
                x=ak.to_numpy(ak.flatten(expected[name]));y=ak.to_numpy(ak.flatten(b[name]))
            np.testing.assert_array_equal(x,y)
        results.append(dict(run=run,compared_events=6,columns=len(a.fields),all_columns_exact_including_NaN=True))
    (OUT/'sparsecheck.json').write_text(json.dumps(dict(passed=True,results=results),indent=2)+'\n');print(results,flush=True)


if __name__=='__main__':main()
