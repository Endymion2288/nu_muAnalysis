#!/usr/bin/env python3
"""Bounded source-function validation of a pinned waveform repair; never overwrite PHYS."""
import argparse
import json
import resource
import subprocess
import time
from pathlib import Path

import numpy as np

from build_waveform_repair import sources
from report_calonu_native import table


def load_tools(repo):
    import ROOT
    ROOT.gErrorIgnoreLevel = ROOT.kError
    source_dir = repo/'ml/pinned_waveform'
    original, patched = sources(repo.parent/'calypso', source_dir if source_dir.exists() else None)
    header = (source_dir/'WaveformFitResult.h').read_text() if source_dir.exists() else subprocess.check_output(
        ['git', '-C', str(repo.parent/'calypso'), 'show', '1ec47efe:Waveform/WaveRecTools/src/WaveformFitResult.h'], text=True)
    common = '#include <vector>\n#include <algorithm>\n#include <cmath>\n#include <iostream>\n#include <limits>\n#include "TGraph.h"\n#include "TF1.h"\n#include "TFitResult.h"\n#include "TFitResultPtr.h"\n#define ATH_MSG_DEBUG(x) do{}while(0)\n#define ATH_MSG_WARNING(x) do{}while(0)\n'
    assert ROOT.gInterpreter.Declare(common+(repo/'ml/StableWaveformIntegral.h').read_text())
    base = 'Waveform/WaveRecTools/src/'
    for name, content in [('Original', original), ('Repaired', patched), ('Injected', patched)]:
        source = content[base+'WaveformReconstructionTool.cxx']
        result = content[base+'WaveformFitResult.cxx']
        result = '\n'.join(x for x in result.splitlines() if not x.startswith('#'))
        h = '\n'.join(x for x in header.splitlines() if not x.startswith('#'))
        begin = source.index('WaveformFitResult&\nWaveformReconstructionTool::findRawHitValues')
        functions = source[begin:source.index('\n}', source.index('return cbfit;', begin))+2]
        if name == 'Injected':
            functions = functions.replace('cbfunc.GetX( cbfit.peak * m_timingPeakFraction, time.front(), cbfit.mean )',
                                            'std::numeric_limits<double>::quiet_NaN()')
        declarations = '''
class WaveformReconstructionTool {
public:
  double m_timingPeakFraction=.4;
  WaveformFitResult& findRawHitValues(const std::vector<float>,const std::vector<float>) const;
  WaveformFitResult& fitGaussian(const WaveformFitResult&,const std::vector<float>,const std::vector<float>) const;
  WaveformFitResult& fitCBall(const WaveformFitResult&,const std::vector<float>,const std::vector<float>) const;
};
'''
        wrapper = '''
std::vector<double> ReplayNAME(const std::vector<float>& t,const std::vector<float>& w,float baseline,float rms){
  WaveformReconstructionTool tool;
  WaveformFitResult raw=tool.findRawHitValues(t,w);
  if(raw.peak<5*rms)return {1,raw.integral,0,-1,raw.integral,0,-1,0,raw.time,raw.peak,raw.mean,raw.sigma,0,0,raw.integral};
  WaveformFitResult gf=tool.fitGaussian(raw,t,w);
  if(!gf.valid){raw.sigma=1;gf=tool.fitGaussian(raw,t,w);}
  bool gfvalid=gf.valid; int gfstatus=gf.fit_status;
  if(REPAIR && !gf.valid){gf=raw;gf.valid=false;}
  std::vector<float> wt=t,ww=w;
  bool overflow=(*std::max_element(ww.begin(),ww.end())>=baseline);
  if(overflow)for(int i=int(std::max_element(ww.begin(),ww.end())-ww.begin());i<int(ww.size());i++){
    if(ww[i]<baseline)continue;wt.erase(wt.begin()+i);ww.erase(ww.begin()+i);i--;
  }
  WaveformFitResult cb=tool.fitCBall(gf,wt,ww);
  unsigned status=(!gfvalid?16:0)|(!cb.valid?32:0)|(overflow?4:0);
  double integral=cb.valid?cb.integral:gf.integral;
  return {double(status),integral,double(gfvalid),double(gfstatus),gf.integral,double(cb.valid),double(cb.fit_status),
          cb.integral,cb.time,cb.peak,cb.mean,cb.sigma,cb.alpha,cb.nval,raw.integral};
}
'''.replace('NAME', name).replace('REPAIR', 'false' if name == 'Original' else 'true')
        code = h+result+declarations+functions+wrapper
        code = code.replace('WaveformFitResult', name+'FitResult').replace('WaveformReconstructionTool', name+'WaveTool')
        assert ROOT.gInterpreter.Declare(code)
    return ROOT


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--cache', type=Path, default=Path('ntuples/energy_ml_stage37/native_response.npz'))
    p.add_argument('--output', type=Path, default=Path('workbook/stage38_energy_ml/development'))
    p.add_argument('--all', action='store_true')
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    a.output.mkdir(parents=True, exist_ok=True)
    tick, cpu = time.perf_counter(), time.process_time()
    ROOT = load_tools(repo)
    with np.load(a.cache) as z:
        d = {k: z[k] for k in z.files}
    cases = json.loads(str(d['cases_json']))
    if a.all:
        selected = [(j, i) for j in range(len(cases)) for i in range(4)]
    else:
        nonfinite = [(j, i) for j in range(len(cases)) for i in range(4) if not np.isfinite(d['integral'][j, i])]
        pools = [nonfinite]
        for mask in [(d['status'] & 48) != 0, d['status'] == 0, d['status'] == 1,
                     (d['status'] & 4) != 0, (d['width'] < .2) & (d['status'] == 0)]:
            pools.append(list(zip(*np.where(mask)))[:2])
        selected = list(dict.fromkeys(x for pool in pools for x in pool))[:24]
    rows = []
    for j, i in selected:
        t = ROOT.std.vector('float')(d['saved_time'][j, i].tolist())
        w = ROOT.std.vector('float')(d['saved_wave'][j, i].tolist())
        np.testing.assert_array_equal(list(t), d['saved_time'][j, i])
        np.testing.assert_array_equal(list(w), d['saved_wave'][j, i])
        results = {}
        for name in ['Original', 'Repaired']:
            results[name] = list(getattr(ROOT, 'Replay'+name)(t, w, float(d['baseline_mean'][j, i]), float(d['baseline_rms'][j, i])))
        old, new = results['Original'], results['Repaired']
        fixed = float(ROOT.StableWaveformIntegral(*[float(d[k][j, i]) for k in ['peak','mean','width','alpha','nval']], float(t[0]), float(t[-1])))
        rows.append(dict(group=cases[j].get('index', cases[j].get('group')), input_entry=cases[j]['input_entry'], branch=i,
                         role=cases[j]['role'], saved_status=int(d['status'][j,i]), saved_integral_mVns=d['integral'][j,i],
                         original_status=int(old[0]), original_integral_mVns=old[1],
                         repaired_status=int(new[0]), repaired_integral_mVns=new[1],
                         repaired_GF_valid=int(new[2]), repaired_GF_status=int(new[3]), repaired_GF_integral_mVns=new[4],
                         repaired_CB_valid=int(new[5]), repaired_CB_status=int(new[6]), repaired_CB_integral_mVns=new[7],
                         repaired_CB_time_ns=new[8], repaired_CB_peak_mV=new[9], repaired_CB_width_ns=new[11],
                         fixed_saved_parameter_integral_mVns=fixed, raw_integral_mVns=new[14]))
    table(a.output/'replay.tsv', rows)
    # Fault injection verifies the actual patched time-NaN branch, not a claim about saved events.
    normal = next((j,i) for j,i in selected if d['status'][j,i] == 0 and np.isfinite(d['integral'][j,i]) and d['width'][j,i] > 1)
    j, i = normal
    t = ROOT.std.vector('float')(d['saved_time'][j,i].tolist())
    w = ROOT.std.vector('float')(d['saved_wave'][j,i].tolist())
    injected = list(ROOT.ReplayInjected(t,w,float(d['baseline_mean'][j,i]),float(d['baseline_rms'][j,i])))
    assert int(injected[0]) & 32 and not injected[5] and np.isfinite(injected[1])
    summary = dict(modules=len(rows), source_commit='1ec47efe', ROOT=ROOT.gROOT.GetVersion(),
                   original_nonfinite=sum(not np.isfinite(r['original_integral_mVns']) for r in rows),
                   repaired_nonfinite=sum(not np.isfinite(r['repaired_integral_mVns']) for r in rows),
                   injected_CB_time_NaN_rejected=True, injected_fallback_integral_mVns=injected[1],
                   injected_status=int(injected[0]), new_ML_fits=0, wall_s=time.perf_counter()-tick,
                   cpu_s=time.process_time()-cpu, peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                   limitation='Pinned source-function scaffold with saved baseline/window; not full Athena tool or original fit-order replay')
    (a.output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    assert summary['repaired_nonfinite'] == 0
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
