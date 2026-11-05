"""Validate actual hadronization replay output against native original selection."""
import json

import awkward as ak
import numpy as np
import uproot
import yaml

from extract_alternative_support import extract
from stage112_selection import BRANCHES,active_cuts,derive
from stage119_curve_common import ROOT,OUT,CACHE


def main():
    checks=[]
    for run in [200300,200303]:
        path=CACHE/f'pythiaqa_{run}.root';out=CACHE/f'pythiaextractqa_{run}.npz'
        extract(0,path,out,qa=True,source=dict(run=run,component='pi'))
        with uproot.open(path) as f:
            tree=f['nt'];assert tree.num_entries==40;a=tree.arrays(BRANCHES);d,flags=derive(a)
            cuts=active_cuts(yaml.safe_load((ROOT/'AnalysisZipFramework/config/ml_low_energy_cuts.yaml').read_text()))
            selected=np.logical_and.reduce([flags[n][0] for n,_ in cuts])
        with np.load(out) as z:
            np.testing.assert_array_equal(z['input_entry'],np.flatnonzero(selected));assert z['x'].shape==(selected.sum(),62)
        checks.append(dict(run=run,parents=40,selected=int(selected.sum()),typed62=True,independent_native_selection_exact=True))
    (OUT/'pythiaextractqa.json').write_text(json.dumps(dict(passed=True,checks=checks),indent=2)+'\n')
    print(checks,flush=True)


if __name__=='__main__':main()
