#!/usr/bin/env python3
"""Build reviewable patches against pinned Calypso, without changing that checkout."""
import difflib
import subprocess
from pathlib import Path


def sources(source, pinned_dir=None):
    base = 'Waveform/WaveRecTools/src/'
    paths = [base+'WaveformFitResult.cxx', base+'WaveformReconstructionTool.cxx']
    original = {p: (pinned_dir/Path(p).name).read_text() if pinned_dir is not None else
                subprocess.check_output(['git', '-C', str(source), 'show', '1ec47efe:'+p], text=True) for p in paths}
    patched = dict(original)
    p = paths[0]
    patched[p] = patched[p].replace('  sigma = 0.;', '  sigma = 0.;\n  alpha = 0.;\n  nval = 0.;\n  chi2ndf = 0.;\n  integral = 0.;\n  time = 0.;')
    p = paths[1]
    patched[p] = patched[p].replace('#include "WaveformReconstructionTool.h"', '#include "WaveformReconstructionTool.h"\n#include "StableWaveformIntegral.h"')
    patched[p] = patched[p].replace('  raw.sigma = hit->width();', '  raw.sigma = hit->width();\n  raw.integral = hit->raw_integral();\n  raw.time = hit->localtime();')
    patched[p] = patched[p].replace('  rfit.mean = sum/tot;', '  rfit.mean = tot > 0. ? sum/tot : (3*time.front()+time.back())/4.;')
    patched[p] = patched[p].replace('  rfit.sigma = std::sqrt(sum2/tot - rfit.mean*rfit.mean);', '  rfit.sigma = tot > 0. ? std::sqrt(sum2/tot - rfit.mean*rfit.mean) : 2.;')
    patched[p] = patched[p].replace('  gfit.valid = (gfit.fit_status == 0);', '  gfit.valid = (gfit.fit_status == 0) && gfitptr->IsValid();')
    patched[p] = patched[p].replace('  cbfit.valid = (cbfit.fit_status == 0);', '  cbfit.valid = (cbfit.fit_status == 0) && cbfitptr->IsValid();')
    patched[p] = patched[p].replace('if (isnan(gfit.time))', 'if (!std::isfinite(gfit.time) || !std::isfinite(gfit.integral))')
    patched[p] = patched[p].replace('      gfit.fit_status = false;', '      gfit.valid = false;\n      gfit.fit_status = -2;')
    patched[p] = patched[p].replace('    cbfit.integral = cbfunc.Integral(time.front(), time.back());',
        '    cbfit.integral = StableWaveformIntegral(cbfit.peak, cbfit.mean, cbfit.sigma,\n'
        '                                             cbfit.alpha, cbfit.nval, time.front(), time.back());')
    patched[p] = patched[p].replace('if (isnan(cbfit.time))', 'if (!std::isfinite(cbfit.time) || !std::isfinite(cbfit.integral))')
    patched[p] = patched[p].replace('      cbfit.fit_status = false;', '      cbfit.valid = false;\n      cbfit.fit_status = -2;')
    # An invalid Gaussian must not replace the already saved raw estimate.
    patched[p] = patched[p].replace('  hit->set_peak(gfit.peak);', '  if (!gfit.valid) {\n    gfit = raw;\n    gfit.valid = false;\n  }\n  hit->set_peak(gfit.peak);', 1)
    return original, patched


def main():
    repo = Path(__file__).resolve().parents[1]
    original, patched = sources(repo.parent/'calypso')
    target = repo/'ml/patches/calonu-waveform-stability-1ec47efe.patch'
    target.parent.mkdir(exist_ok=True)
    patch = ''.join(''.join(difflib.unified_diff(original[p].splitlines(True), patched[p].splitlines(True),
                                               fromfile='a/'+p, tofile='b/'+p)) for p in original)
    header = (repo/'ml/StableWaveformIntegral.h').read_text()
    path = 'Waveform/WaveRecTools/src/StableWaveformIntegral.h'
    patch += ''.join(difflib.unified_diff([], header.splitlines(True), fromfile='/dev/null', tofile='b/'+path))
    target.write_text(patch)
    print(target)


if __name__ == '__main__':
    main()
