#!/usr/bin/env python3
"""Independent quadrature and patch application checks before freezing confirmation."""
import json
import resource
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np
from scipy.integrate import quad

from build_waveform_repair import sources
from diagnose_calonu_native import stable_shape
from report_calonu_native import table


def quadrature(pars, low, high):
    peak, mean, sigma, alpha, power = pars
    z0, z1 = (low-mean)/sigma, (high-mean)/sigma
    points = [-alpha, 0.] + [sign*10.**k for sign in [-1,1] for k in range(13)]
    points = sorted(set(x for x in points if z0 < x < z1))
    return peak*sigma*quad(stable_shape,z0,z1,args=(1.,0.,1.,alpha,power),points=points,
                           epsabs=1e-11,epsrel=1e-10,limit=300)[0]


def main():
    import ROOT
    tick, cpu = time.perf_counter(), time.process_time()
    repo = Path(__file__).resolve().parents[1]
    out = repo/'workbook/stage38_energy_ml/development'
    assert ROOT.gInterpreter.Declare((repo/'ml/StableWaveformIntegral.h').read_text())
    original, patched = sources(repo.parent/'calypso')
    with tempfile.TemporaryDirectory(prefix='stage38_patch_') as temp:
        for p, s in original.items():
            path = Path(temp)/p
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(s)
        patch = str(repo/'ml/patches/calonu-waveform-stability-1ec47efe.patch')
        subprocess.run(['git', 'apply', '--check', patch], cwd=temp, check=True)
        subprocess.run(['git', 'apply', patch], cwd=temp, check=True)
        assert all((Path(temp)/p).read_text() == s for p, s in patched.items())
        assert (Path(temp)/'Waveform/WaveRecTools/src/StableWaveformIntegral.h').read_bytes() == (repo/'ml/StableWaveformIntegral.h').read_bytes()
    synthetic = []
    for alpha in [-.005, -.32, -3., .5]:
        for n in [.2, 1-1e-8, 1., 1+1e-8, 2., 122.35, 1000.]:
            for low, high in [(780.,930.), (900.,930.), (780.,800.)]:
                pars = (7.,820.,3.67,alpha,n)
                split = 820-alpha*3.67
                points = [x for x in [820., split] if low < x < high]
                reference = quadrature(pars,low,high)
                value = float(ROOT.StableWaveformIntegral(*pars,low,high))
                np.testing.assert_allclose(value,reference,rtol=2e-8,atol=1e-10)
                synthetic.append(dict(alpha=alpha,n=n,low_ns=low,high_ns=high,stable_mVns=value,
                                      quadrature_mVns=reference,absolute_difference_mVns=abs(value-reference)))
    table(out/'synthetic_integrals.tsv',synthetic)
    with np.load(repo/'ntuples/energy_ml_stage37/native_response.npz') as z:
        d = {k:z[k] for k in z.files}
    cases = json.loads(str(d['cases_json']))
    rows = []
    for j, case in enumerate(cases):
        for i in range(4):
            if int(d['status'][j,i]) & (1 | 32):
                continue
            pars = tuple(float(d[k][j,i]) for k in ['peak','mean','width','alpha','nval'])
            low, high = d['saved_time'][j,i,[0,-1]]
            value = float(ROOT.StableWaveformIntegral(*pars,float(low),float(high)))
            split = pars[1]-pars[3]*pars[2]
            points = sorted([x for x in [pars[1],split] if low<x<high])
            reference = quadrature(pars,low,high)
            np.testing.assert_allclose(value,reference,rtol=2e-7,atol=1e-8)
            rows.append(dict(group=case['group'],input_entry=case['input_entry'],branch=i,status=int(d['status'][j,i]),
                             saved_mVns=d['integral'][j,i],stable_mVns=value,quadrature_mVns=reference,
                             difference_from_saved_mVns=value-d['integral'][j,i]))
    table(out/'fixed_parameter_integrals.tsv',rows)
    summary = dict(synthetic_cases=len(synthetic),saved_parameter_cases=len(rows),all_quadrature_checks_passed=True,
                   patch_applies_to_pinned_source=True,ROOT=ROOT.gROOT.GetVersion(),
                   recovered_nonfinite=int(sum(not np.isfinite(r['saved_mVns']) and np.isfinite(r['stable_mVns']) for r in rows)),
                   wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
                   peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (out/'integral_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
