"""Measured native geometry-corrected sensitive-deposition window coverage."""
import json

import numpy as np

from stage119_curve_common import OUT,table
from stage119_mechanism import fiducial


def main():
    data=json.loads((OUT/'window4.json').read_text());rows=[];rng=np.random.default_rng(20261105198);checks=[]
    for run in sorted({r['run'] for r in data['events']}):
        allrows=[r for r in data['events'] if r['run']==run];lookup={}
        path=OUT/f'hits_{run}_hits.json'
        if path.exists():lookup={r['eventID']:r for r in json.loads(path.read_text())['events']}
        for selection in ['all_parent','fiducial_numu'] if lookup else ['all_parent']:
            use=allrows if selection=='all_parent' else [r for r in allrows if fiducial(lookup[r['eventID']])]
            if not use:continue
            e=np.array([r['total_MeV'] for r in use]);inside=np.array([r['inside_MeV'] for r in use]);early=np.array([r['early_MeV'] for r in use]);late=np.array([r['late_MeV'] for r in use])
            np.testing.assert_allclose(e,inside+early+late,atol=1e-12,rtol=1e-12)
            if lookup:
                original=np.array([lookup[r['eventID']]['detectors']['VetoNuHits']['E_MeV'] for r in use])
                np.testing.assert_allclose(e,original,atol=1e-12,rtol=1e-12)
                checks.append(dict(run=run,selection=selection,N=len(use),total_deposition_independent_reader_exact=True))
            den=[];ratios=[]
            for _ in range(500):
                idx=rng.integers(0,len(e),len(e));s=e[idx].sum()
                if s>0:ratios.append(float(late[idx].sum()/s))
            bounds=np.quantile(ratios,[.025,.975]).tolist() if len(ratios)>=475 else [None,None]
            rows.append(dict(run=run,selection=selection,parent_N=len(e),nonzero_N=int((e>0).sum()),zero_N=int((e==0).sum()),
                total_MeV=float(e.sum()),inside_MeV=float(inside.sum()),early_MeV=float(early.sum()),late_MeV=float(late.sum()),
                late_deposit_fraction=float(late.sum()/e.sum()) if e.sum() else None,late_fraction_low95=bounds[0],late_fraction_high95=bounds[1],valid_draws=len(ratios),
                late_only_events=int(((late>0)&(inside==0)&(early==0)).sum()),inside_nonzero_events=int((inside>0).sum()),
                timing='hit.meanTime - actual center.z/c, [-20,1200) ns histogram window; not charge collection or neutron ancestry efficiency'))
    table('window_coverage.tsv',rows);table('window_validation.tsv',checks)
    (OUT/'window_summary.json').write_text(json.dumps(dict(geometry=data['geometry'],detector_centers_z_mm=data['detector_centers_z_mm'],
        events=len(data['events']),window_ns=data['input_window_ns'],source_scope='fixed first1000 parents per source; not uniform population estimate',
        conclusion_scope='actual geometry-corrected deposit histogram acceptance; no point-valued neutron ancestry label or deployed energy gain',
        extra_caveats=['convolution and waveform fitting can further alter accepted charge','zero deposition retained','unknown ancestry not classified','transport producer histories differ']),indent=2)+'\n')
    print(rows,flush=True)


if __name__=='__main__':main()
