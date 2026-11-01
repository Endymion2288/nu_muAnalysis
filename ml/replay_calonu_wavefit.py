#!/usr/bin/env python3
"""At most eight frozen waveform source-function replays, not a full reconstruction job."""
import argparse
import csv
import json
import math
import resource
import subprocess
import time
from pathlib import Path

import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', default='/eos/home-x/xcheng/FASER/calypso')
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    out = repo/'workbook/stage37_energy_ml'
    tick, cpu = time.perf_counter(), time.process_time()
    import ROOT
    ROOT.gErrorIgnoreLevel = ROOT.kError
    def show(path):
        return subprocess.check_output(['git', '-C', a.source, 'show', '1ec47efe:'+path], text=True)
    source = show('Waveform/WaveRecTools/src/WaveformReconstructionTool.cxx')
    result_header = show('Waveform/WaveRecTools/src/WaveformFitResult.h')
    result_source = show('Waveform/WaveRecTools/src/WaveformFitResult.cxx')
    result_source = '\n'.join(line for line in result_source.splitlines() if not line.startswith('#include'))
    begin = source.index('WaveformFitResult&\nWaveformReconstructionTool::findRawHitValues')
    functions = source[begin:source.index('\n}', source.index('return cbfit;', begin))+2]
    functions = functions.replace('WaveformReconstructionTool::', 'FrozenWaveFit::')
    declarations = '''
class FrozenWaveFit {
public:
  double m_timingPeakFraction = .4;
  WaveformFitResult& findRawHitValues(const std::vector<float>, const std::vector<float>) const;
  WaveformFitResult& fitGaussian(const WaveformFitResult&, const std::vector<float>, const std::vector<float>) const;
  WaveformFitResult& fitCBall(const WaveformFitResult&, const std::vector<float>, const std::vector<float>) const;
};
'''
    wrapper = '''
std::vector<double> ReplayFrozenWave(const std::vector<float>& t, const std::vector<float>& w, float baseline, float rms) {
  FrozenWaveFit tool;
  WaveformFitResult raw = tool.findRawHitValues(t,w);
  if(raw.peak < 5*rms) return {1.,raw.integral,0,0,0,0,0,0,0,0,0,0,0,raw.integral};
  WaveformFitResult gf=tool.fitGaussian(raw,t,w);
  if(!gf.valid){raw.sigma=1.;gf=tool.fitGaussian(raw,t,w);}
  std::vector<float> wt=t, ww=w;
  bool overflow=(*std::max_element(w.begin(),w.end())>=baseline);
  if(overflow) for(int i=int(std::max_element(ww.begin(),ww.end())-ww.begin());i<int(ww.size());i++){
    if(ww[i]<baseline)continue;wt.erase(wt.begin()+i);ww.erase(ww.begin()+i);i--;
  }
  WaveformFitResult cb=tool.fitCBall(gf,wt,ww);
  unsigned status=(!gf.valid?16:0)|(!cb.valid?32:0)|(overflow?4:0);
  double integral=cb.valid?cb.integral:gf.integral;
  return {double(status),raw.integral,double(gf.valid),double(gf.fit_status),gf.integral,
          double(cb.valid),double(cb.fit_status),cb.integral,cb.time,cb.alpha,cb.nval,cb.sigma,cb.mean,integral};
}
'''
    code = '#include <vector>\n#include <algorithm>\n#include <cmath>\n#include "TGraph.h"\n#include "TF1.h"\n#include "TFitResult.h"\n#include "TFitResultPtr.h"\n#define ATH_MSG_DEBUG(x) do{}while(0)\n#define ATH_MSG_WARNING(x) do{}while(0)\n'
    assert ROOT.gInterpreter.Declare(code+result_header+result_source+declarations+functions+wrapper)
    with np.load(repo/'ntuples/energy_ml_stage37/native_response.npz') as z:
        d = {key: z[key] for key in z.files}
    cases = json.loads(str(d['cases_json']))
    nonfinite = [(j, i) for j in range(len(cases)) for i in range(4) if not np.isfinite(d['integral'][j, i])]
    abnormal = [(j, i) for j in range(len(cases)) for i in range(4) if np.isfinite(d['integral'][j, i]) and (d['status'][j, i] & 48)]
    above = [(j, i) for j in range(len(cases)) for i in range(4) if d['status'][j, i] == 0 and np.isfinite(d['integral'][j, i])]
    below = [(j, i) for j in range(len(cases)) for i in range(4) if d['status'][j, i] == 1]
    selected = list(dict.fromkeys(nonfinite[:4]+abnormal[:2]+above[:1]+below[:1]))[:8]
    rows = []
    for j, i in selected:
        # ROOT 6.28 can reinterpret a numpy float64 buffer as float32 in this constructor.
        t = ROOT.std.vector('float')(d['saved_time'][j, i].tolist())
        w = ROOT.std.vector('float')(d['saved_wave'][j, i].tolist())
        np.testing.assert_array_equal(np.asarray(list(t)), d['saved_time'][j, i])
        np.testing.assert_array_equal(np.asarray(list(w)), d['saved_wave'][j, i])
        result = list(ROOT.ReplayFrozenWave(t, w, float(d['baseline_mean'][j, i]), float(d['baseline_rms'][j, i])))
        row = dict(group=cases[j]['group'], input_entry=cases[j]['input_entry'], branch=i,
                   saved_status=int(d['status'][j, i]), replay_status=int(result[0]), saved_integral_mVns=float(d['integral'][j, i]),
                   replay_integral_mVns=result[13], gaussian_valid=int(result[2]), gaussian_fit_status=int(result[3]),
                   gaussian_integral_mVns=result[4], CB_valid=int(result[5]), CB_fit_status=int(result[6]), CB_integral_mVns=result[7],
                   CB_time_ns=result[8], CB_alpha=result[9], CB_n=result[10], CB_sigma_ns=result[11], CB_mean_ns=result[12],
                   saved_alpha=float(d['alpha'][j, i]), saved_n=float(d['nval'][j, i]))
        # Fixed saved parameters diagnose integration independently of re-optimizing the fit.
        row['saved_CB_parameters_applicable'] = int(d['status'][j, i]) & (1 | 32) == 0
        row['saved_CB_parameter_integral_mVns'] = np.nan
        row['saved_CB_sampled_integral_mVns'] = np.nan
        if row['saved_CB_parameters_applicable']:
            f = ROOT.TF1(f'saved_cb_{j}_{i}', 'crystalball', float(t[0]), float(t[-1]))
            f.SetParameters(float(d['peak'][j, i]), float(d['mean'][j, i]), float(d['width'][j, i]),
                            float(d['alpha'][j, i]), float(d['nval'][j, i]))
            row['saved_CB_parameter_integral_mVns'] = float(f.Integral(float(t[0]), float(t[-1])))
            row['saved_CB_sampled_integral_mVns'] = float(np.trapz([f.Eval(float(x)) for x in t], np.asarray(list(t))))
        rows.append(row)
        print('WAVE_REPLAY', json.dumps(row), flush=True)
    with (out/'wavefit_replay.tsv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    value = dict(source_commit='1ec47efe', ROOT_version=ROOT.gROOT.GetVersion(), modules=len(rows),
                 matching_saved_status=sum(r['saved_status'] == r['replay_status'] for r in rows),
                 saved_nonfinite=sum(not math.isfinite(r['saved_integral_mVns']) for r in rows),
                 replay_nonfinite=sum(not math.isfinite(r['replay_integral_mVns']) for r in rows),
                 ML_fits=0, wall_s=time.perf_counter()-tick, cpu_s=time.process_time()-cpu,
                 peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                 limitations='Pinned source functions and original ROOT version; saved window/baseline reused; not full tool/conditions or original job fit-order replay; no output correction')
    (out/'wavefit_replay_summary.json').write_text(json.dumps(value, indent=2)+'\n')
    print(json.dumps(value))


if __name__ == '__main__':
    main()
