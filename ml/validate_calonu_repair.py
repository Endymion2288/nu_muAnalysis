#!/usr/bin/env python3
"""Independent confirmation checks and compact physics diagnostic figure."""
import csv
import json
import resource
import time
from pathlib import Path

import numpy as np

from calonu_weak_readout import template_weights
from check_waveform_integral import quadrature
from report_calonu_native import table


def main():
    import ROOT
    tick, cpu = time.perf_counter(), time.process_time()
    repo = Path(__file__).resolve().parents[1]
    out = repo/'workbook/stage38_energy_ml'
    assert ROOT.gInterpreter.Declare((repo/'ml/StableWaveformIntegral.h').read_text())
    with np.load(repo/'ntuples/energy_ml_stage38/confirmation.npz') as z:
        d = {k:z[k] for k in z.files}
    cases = json.loads(str(d['cases_json']))
    replay = list(csv.DictReader((out/'confirmation_replay.tsv').open(), delimiter='\t'))
    index = {(int(r['group']),int(r['input_entry']),int(r['branch'])):r for r in replay}
    rows = []
    for j,c in enumerate(cases):
        for i in range(4):
            if d['status'][j,i] & (1|32):
                continue
            pars = tuple(float(d[k][j,i]) for k in ['peak','mean','width','alpha','nval'])
            low, high = map(float, d['saved_time'][j,i,[0,-1]])
            analytic = float(ROOT.StableWaveformIntegral(*pars,low,high))
            reference = quadrature(pars,low,high)
            np.testing.assert_allclose(analytic,reference,rtol=2e-7,atol=1e-8)
            r = index[c['index'],c['input_entry'],i]
            np.testing.assert_allclose(analytic,float(r['fixed_saved_parameter_integral_mVns']),rtol=2e-13,atol=1e-10)
            normal = bool(d['status'][j,i]==0 and np.isfinite(d['integral'][j,i]) and d['integral'][j,i]>0 and pars[2]>=1)
            preserved = bool(np.isclose(analytic,d['integral'][j,i],rtol=3e-6,atol=1e-5)) if normal else None
            assert preserved is not False
            rows.append(dict(group=c['index'],input_entry=c['input_entry'],branch=i,status=int(d['status'][j,i]),
                             width_ns=pars[2],saved_mVns=float(d['integral'][j,i]),stable_mVns=analytic,
                             quadrature_mVns=reference,absolute_difference_mVns=abs(analytic-reference),
                             normal_resolved=normal,preserved=preserved if normal else 'not_applicable'))
    table(out/'confirmation_integrals.tsv',rows)
    # Compact extraction was piloted on the first *development* event, without opening confirmation.
    with np.load('/tmp/stage38_compact_smoke.npz') as z, np.load(repo/'ntuples/energy_ml_stage37/native_response.npz') as old:
        checked = []
        for k in z.files:
            if k in old.files and k not in ['metadata_json','cases_json','schemas_json']:
                np.testing.assert_array_equal(z[k][0],old[k][0])
                checked.append(k)
        # The old compact archive stores the same nominal signal, with this field name.
        if 'signal_nominal_ADC' in old.files:
            np.testing.assert_array_equal(z['signal_nominal_ADC'][0],old['signal_nominal_ADC'][0])
    cfg = json.loads((repo/'ml/configs/calonu_repair_control.json').read_text())
    fixed,free = template_weights(d['saved_time'][0,0],cfg['template_parameters'])
    theoretical = {name:float(3*(2/16.384)*np.sqrt(4*np.dot(w,w))) for name,w in
                   [('signed',np.full(76,2/50)),('template_fixed_baseline',fixed),('template_plus_constant',free)]}
    # Explanatory control only: the MC digitizer baseline is not a measured data baseline.
    conditions=json.loads((repo/'workbook/stage37_energy_ml/conditions_audit.json').read_text())
    digitizer=next(r['rows'][0]['payload'] for r in conditions['records']
                   if r['label']=='MC100049' and r['folder']=='/WAVE/Digitization')
    event_rows=list(csv.DictReader((out/'confirmation_events.tsv').open(),delimiter='\t'))
    target=np.array([float(r['nominal_signal_pC']) for r in event_rows])
    signed=np.array([float(r['signed_saved_pC']) for r in event_rows])
    baseline_shift=(d['baseline_mean']-digitizer['base_mean']*(2/16.384)).sum(axis=1)*76*2/50
    # A source-level repair is finite, but its legacy threshold/raw fallback still rectifies noise.
    regular = np.array([c['role']=='regular' for c in cases])
    totals = (d['repaired_fit_charge_pC']).sum(axis=1)
    summary = dict(saved_parameter_cases=len(rows),quadrature_all_passed=True,
                   normal_resolved=sum(r['normal_resolved'] for r in rows),
                   normal_preserved=sum(r['preserved'] is True for r in rows),
                   recovered_saved_nonfinite=int(sum(not np.isfinite(r['saved_mVns']) and np.isfinite(r['stable_mVns']) for r in rows)),
                   narrow_width_lt02_cases=sum(r['width_ns']<.2 for r in rows),
                   compact_smoke_common_fields_exact=checked,
                   ideal_independent_ADC_noise_total_RMS_pC=theoretical,
                   regular_all_four_threshold_failed=int(np.sum(np.all((d['status']&1)!=0,axis=1)&regular)),
                   regular_sensitivity_hit_median_MeV=float(np.median(d['hit_energy_MeV'][regular].sum(axis=1))),
                   regular_repaired_fit_median_pC=float(np.median(totals[regular])),
                   explanatory_MC_known_baseline_signed_RMSE_pC=float(np.sqrt(np.mean((signed[regular]-baseline_shift[regular]-target[regular])**2))),
                   explanatory_MC_baseline_offset_RMS_pC=float(np.sqrt(np.mean(baseline_shift[regular]**2))),
                   explanatory_signed_error_baseline_offset_correlation=float(np.corrcoef((signed-target)[regular],baseline_shift[regular])[0,1]),
                   wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
                   peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (out/'integral_validation.json').write_text(json.dumps(summary,indent=2)+'\n')
    plot(out)
    print(json.dumps(summary))


def plot(out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['svg.hashsalt']='stage38'
    events = list(csv.DictReader((out/'confirmation_events.tsv').open(),delimiter='\t'))
    regular = [r for r in events if r['role']=='regular']
    methods = ['positive_raw','signed_saved','template_fixed_baseline','template_plus_constant']
    labels = ['Positive raw','Signed','Template, saved baseline','Template + constant']
    fig,axs=plt.subplots(1,3,figsize=(14,4),constrained_layout=True)
    target=np.array([float(r['nominal_signal_pC']) for r in regular])
    for name,label in zip(methods,labels):
        error=np.array([float(r[name+'_pC']) for r in regular])-target
        axs[0].hist(error,bins=np.linspace(-1.4,2.8,42),histtype='step',label=label)
    axs[0].set(xlabel='Charge error to nominal signal [pC]',ylabel='Regular muon controls / bin')
    axs[0].legend(fontsize=7)
    metrics=list(csv.DictReader((out/'readout_metrics.tsv').open(),delimiter='\t'))
    for name,label in zip(methods,labels):
        vals=[next(float(r['rmse_pC']) for r in metrics if r['subset']==s and r['method']==name)
              for s in ['regular_p100_250','regular_p250_1000']]
        axs[1].plot([0,1],vals,'o-',label=label)
    axs[1].set(xticks=[0,1],xticklabels=['100–250','250–1000'],xlabel='Reco muon momentum [GeV]',ylabel='Charge RMSE [pC]',yscale='log')
    for name,label in zip(['template_plus_constant','template_time_-2ns','template_time_+2ns'],['Nominal','Template −2 ns','Template +2 ns']):
        vals=[next(float(r['rmse_pC']) for r in metrics if r['subset']==s and r['method']==name)
              for s in ['regular','diagnostic']]
        axs[2].plot([0,1],vals,'o-',label=label)
    axs[2].set(xticks=[0,1],xticklabels=['Regular (96)','Enriched (32)'],ylabel='Charge RMSE [pC]',yscale='log')
    axs[2].legend(fontsize=8)
    fig.suptitle('Stage38: fixed waveform readout; four source groups; unit MC; no data/MC closure')
    fig.savefig(out/'weak_readout.svg',metadata={'Date':None})
    fig.savefig('/tmp/stage38_weak_readout.png',dpi=130)
    plt.close(fig)


if __name__=='__main__': main()
