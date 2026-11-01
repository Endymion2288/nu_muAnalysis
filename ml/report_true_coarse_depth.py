#!/usr/bin/env python3
"""Same-event source-paired stage46 risk, probability and spectrum diagnostics."""
import json
import resource
import time
from pathlib import Path
import numpy as np
from probability_information import probability_metrics, score_information
from report_calonu_information import source_draws, strata
from train_bdt import metric_values, write_table


def main():
    tick, cpu = time.perf_counter(), time.process_time(); repo = Path(__file__).resolve().parents[1]
    out = repo/'workbook/stage46_energy_ml'; cache = repo/'ntuples/energy_ml_stage46'
    cfg = json.loads((repo/'ml/configs/true_coarse_depth.json').read_text())
    with np.load(repo/'ntuples/energy_ml_stage42/development.npz') as z: d = {k: z[k] for k in z.files}
    chosen = np.flatnonzero(d['selected']); parts = []; resources = []
    for f in range(3):
        with np.load(repo/f'ml/artifacts/stage46/formal/{f}/predictions.npz') as z: part = {k: z[k] for k in z.files}
        m = json.loads(str(part.pop('metadata_json')))
        assert m['config'] == cfg and m['fold'] == f and not m['smoke']
        assert (d['fold'][part['cache_row']] == f).all()
        part = {k: part[k] for k in ['cache_row','prior','oracle_region','q_oracle_region']}
        part['prior'] = np.tile(part['prior'], (len(part['cache_row']), 1)); parts.append(part); resources += m['records']
    order = np.argsort(np.concatenate([p['cache_row'] for p in parts]))
    pred = {k: np.concatenate([p[k] for p in parts])[order] for k in parts[0]}
    np.testing.assert_array_equal(pred['cache_row'], chosen)
    with np.load(repo/'ntuples/energy_ml_stage45/predictions.npz') as z:
        for key in ['cache_row','prior']: np.testing.assert_array_equal(z[key], pred[key])
        for name in ['I0','local','reco_depth','oracle_z']:
            for key in [name,'q_'+name]: pred[key] = z[key]
        for key in ['run','eventID','group','component','reco_p_GeV','truth_E_GeV','y_lepton','vertex_z_mm','primary_kinematic_parent_proxy']:
            np.testing.assert_array_equal(z[key],d[key][chosen])
    local = {k: v[chosen] for k, v in d.items()}; masks = strata(local); y = local['truth_E_GeV']
    names = ['I0', 'local', 'reco_depth', 'oracle_region', 'oracle_z']
    pairs = [('local','oracle_region'),('reco_depth','oracle_region'),('oracle_region','oracle_z'),('I0','oracle_region'),('local','oracle_z')]
    unique, gid, draws = source_draws(local, cfg['bootstrap_replicates'], cfg['seed']); ng = len(unique)
    errors = {name: np.log(pred[name]/y) for name in names}; metrics = []; paired = []
    for label, mask in masks.items():
        if not mask.any(): continue
        counts = np.bincount(gid, weights=mask, minlength=ng); den = draws@counts; ok = den > 0; risks = {}
        for name in names:
            metrics.append(dict(stratum=label, model=name, sources=int(np.count_nonzero(counts)), **metric_values(y, pred[name], mask),
                                **{'prob_'+k:v for k,v in probability_metrics(pred['q_'+name][mask],np.searchsorted(cfg['energy_edges_GeV'],y[mask],side='right')-1).items()}))
            risks[name] = np.sqrt((draws[ok]@np.bincount(gid, weights=mask*errors[name]**2, minlength=ng))/den[ok])
        for left, right in pairs:
            boot = 1-risks[right]/risks[left]
            bias = pred[right]/y-pred[left]/y
            bias_boot = (draws[ok]@np.bincount(gid, weights=mask*bias, minlength=ng))/den[ok]
            paired.append(dict(stratum=label, reference=left, model=right, N=int(mask.sum()), sources=int(np.count_nonzero(counts)),
                               relative_gain=float(1-np.sqrt(np.mean(errors[right][mask]**2)/np.mean(errors[left][mask]**2))),
                               CI025=float(np.quantile(boot, .025)), CI975=float(np.quantile(boot, .975)),
                               log_RMSE_delta=float(np.sqrt(np.mean(errors[right][mask]**2))-np.sqrt(np.mean(errors[left][mask]**2))),
                               delta_CI025=float(np.quantile(risks[right]-risks[left], .025)), delta_CI975=float(np.quantile(risks[right]-risks[left], .975)),
                               mean_bias_delta=float(bias[mask].mean()), bias_CI025=float(np.quantile(bias_boot, .025)),
                               bias_CI975=float(np.quantile(bias_boot, .975)), valid_bootstrap=int(ok.sum())))
    labels = np.searchsorted(cfg['energy_edges_GeV'], y, side='right')-1; spectra = []; spectral_pairs = []
    for label in ['all', 'focus']:
        mask = masks[label]; lab = labels[mask]; counts = np.bincount(gid, weights=mask, minlength=ng); den = draws@counts
        scores = {}; sigmas = {}
        for name in names:
            q = pred['q_'+name][mask]; ratio = q/pred['prior'][mask]
            info, _ = score_information(ratio, lab, np.ones(mask.sum()))
            loss = -np.log(q[np.arange(len(lab)), lab]); scores[name] = (draws@np.bincount(gid[mask], weights=loss, minlength=ng))/den
            bs = []
            for draw in draws:
                v, _ = score_information(ratio, lab, draw[gid[mask]].astype(float)); bs.append(v.get('relative_sigma_RMS', np.nan))
            sigmas[name] = np.array(bs); good = np.isfinite(bs)
            spectra.append(dict(stratum=label, model=name, N=int(mask.sum()), **probability_metrics(q, lab), score_valid=info['valid'],
                                score_relative_sigma_RMS=info.get('relative_sigma_RMS'), score_condition=info.get('condition'),
                                score_bootstrap_valid=int(good.sum()), score_CI025=float(np.nanquantile(bs, .025)) if good.any() else None,
                                score_CI975=float(np.nanquantile(bs, .975)) if good.any() else None, true_bin_counts=np.bincount(lab, minlength=6).tolist()))
        for left, right in pairs:
            delta = scores[right]-scores[left]; gain = 1-sigmas[right]/sigmas[left]; good = np.isfinite(gain)
            point = -np.log(pred['q_'+right][mask][np.arange(len(lab)), lab])+np.log(pred['q_'+left][mask][np.arange(len(lab)), lab])
            spectral_pairs.append(dict(stratum=label, reference=left, model=right, log_score_delta=float(point.mean()),
                                       CI025=float(np.quantile(delta, .025)), CI975=float(np.quantile(delta, .975)),
                                       score_sigma_gain_CI025=float(np.nanquantile(gain, .025)) if good.any() else None,
                                       score_sigma_gain_CI975=float(np.nanquantile(gain, .975)) if good.any() else None,
                                       score_sigma_valid_bootstrap=int(good.sum())))
    write_table(out/'metrics.tsv', metrics); write_table(out/'paired.tsv', paired)
    write_table(out/'spectrum_paired.tsv', spectral_pairs); write_table(out/'training_resources.tsv', [r for r in resources if r['kind']=='energy'])
    (out/'spectrum.json').write_text(json.dumps(spectra, indent=2)+'\n')
    pred.update({k: local[k] for k in ['run', 'eventID', 'group', 'component', 'reco_p_GeV', 'truth_E_GeV', 'y_lepton', 'vertex_z_mm', 'primary_kinematic_parent_proxy']})
    np.savez_compressed(cache/'predictions.npz', **pred)
    main = next(r for r in paired if r['stratum']=='focus' and (r['reference'],r['model'])==('local','oracle_region'))
    passed = main['relative_gain']>=cfg['gate']['minimum_relative_log_RMSE_gain'] and main['CI025']>0
    contrasts = [r for r in paired if r['stratum']=='focus']
    summary = dict(events=len(y),focus_events=int(masks['focus'].sum()),sources=ng,formal_fits=len(resources),
                   energy_fits=len(resources),depth_fits=0,main=main,focus_contrasts=contrasts,
                   oracle_information_gate_passed=bool(passed),deployment_candidate=False,models=names,
                   retraining_and_detector_systematics_propagated=False,
                   wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
                   peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (out/'evaluation.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))


if __name__=='__main__': main()
