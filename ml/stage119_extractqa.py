"""Validate the actual re-reconstructed input against original cuts/typed62."""
import json
from pathlib import Path

import awkward as ak
import numpy as np
import uproot
import yaml

from extract_alternative_support import extract
from stage112_selection import BRANCHES, active_cuts, derive

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage119_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage119'


def main():
    checks=[]
    for run in [200131,200184,200110]:
        path=CACHE/f'recoqa_{run}.root';result=CACHE/f'extractqa_{run}.npz'
        extract(0,path,result,qa=True,source=dict(run=run,component='pi',stage=119))
        with uproot.open(path) as f:
            t=f['nt'];assert t.num_entries==40
            a=t.arrays(list(dict.fromkeys(BRANCHES+['Track_isForward'])))
            d,flags=derive(a);cuts=active_cuts(yaml.safe_load((ROOT/'AnalysisZipFramework/config/ml_low_energy_cuts.yaml').read_text()))
            selected=np.logical_and.reduce([flags[n][0] for n,_ in cuts])
            q=dict(run=run,parents=40,selected=int(selected.sum()),track_N=int(ak.sum(ak.num(a.Track_pz0))),
                forward_N=int(ak.sum(a.Track_isForward)),source_requested_bytes=int(f.file.source.num_requested_bytes),calibration=[])
            cal=t.arrays([f'Calo{j}_{k}' for j in range(4) for k in ['charge','E_EM','status']],library='np')
            for j in range(4):
                charge=cal[f'Calo{j}_charge'];energy=cal[f'Calo{j}_E_EM'];status=cal[f'Calo{j}_status'];use=(status==0)&(charge!=0)&np.isfinite(charge+energy)
                if use.any():
                    ratio=energy[use]/charge[use];np.testing.assert_allclose(ratio,330/.07569999992847443,rtol=2e-6)
                    q['calibration'].append(dict(module=j,N=int(use.sum()),median_MeV_per_pC=float(np.median(ratio))))
        with np.load(result) as z:
            np.testing.assert_array_equal(z['input_entry'],np.flatnonzero(selected))
            assert z['x'].shape==(selected.sum(),62)
            np.testing.assert_allclose(z['truth_E_GeV'],d['E'][selected],rtol=1e-12)
            np.testing.assert_array_equal(z['x'][:,0],d['pz'][selected].astype('float32'))
            q['native_selection_independent_membership_exact']=True
        checks.append(q)
    (OUT/'extractqa.json').write_text(json.dumps(dict(passed=True,checks=checks,new_fits=0,new_forwards=0),indent=2)+'\n')
    print(checks,flush=True)


if __name__=='__main__':main()
