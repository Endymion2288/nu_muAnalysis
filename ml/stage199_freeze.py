"""Freeze the user-requested all-flux direct62 weight experiment, before fitting."""
import collections
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage199_energy_ml'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    assert not (OUT / 'protocol.json').exists()
    prior = json.loads((ROOT / 'workbook/stage130_energy_ml/source_protocol.json').read_text())
    sources, physics = [], []
    for row in prior['inventory']:
        logs = sorted((Path('/eos/experiment/fasernu-data0/faser/sim/mc24/genie') /
                       str(row['run']) / 'log/s0014').glob('*-HITS.sim.log'))
        chosen = logs[0]
        lines = [v.strip() for v in chosen.read_text().splitlines()
                 if 'Sim.PhysicsList ' in v]
        assert len(lines) == 1 and "'FTFP_BERT'" in lines[0], (chosen, lines)
        physics.append(dict(run=row['run'], log=str(chosen), line=lines[0],
                            scope='first sorted production log per run; no variant directories included'))
    for s in prior['sources']:
        s = dict(s)
        local = ROOT / 'ntuples/merge_mc24_master_d32b0ff3' / str(s['run']) / Path(s['rdo']).name.replace('-RDO.root', '-merge-PHYS.root')
        s['mode'] = 'cache130' if s['eligible'] and not s['nominal'] else 'local' if local.is_file() else 'reco'
        s['local_phys'] = str(local) if local.is_file() else None
        s['flux'] = Path(s['rdo']).name.split('Genie_', 1)[1].split('-200', 1)[0]
        s['old_locked_for_old_studies'] = s['old_locked']
        s['old_role_restrictions_overridden_by_user'] = True
        assert Path(s['rdo']).is_file() and Path(s['input']).is_file()
        sources.append(s)
    # Compare the actual bounded directory inventory with the reused manifest.
    actual = {str(p) for run in range(200080, 200102) for p in
              (Path('/eos/experiment/fasernu-data0/faser/sim/mc24/genie') / str(run) / 'rdo/s0014').glob('*-RDO.root')}
    assert actual == {s['rdo'] for s in sources} and len(sources) == 1134
    pilot = [next(s['index'] for s in sources if s['mode'] == mode and s['component'] == c)
             for mode in ['local', 'reco'] for c in ['pi', 'k', 'charm']]
    protocol = dict(stage=199, frozen_utc=datetime.now(timezone.utc).isoformat(),
        starting_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        user_request='Pause Stage187 route. Audit Stage87 direct62 flat weights; use all flux MC, exclude alternative Geant4, repartition and retrain.',
        old_stage87_weights='1/count(native incoming key within role); NOT flat energy training. Posterior prior diagnostics are unrelated.',
        full_scope='All 1134 existing RDO parent sources in runs200080-200101, every selected event; no file/energy yield sampling. Reuse complete Stage130 typed62 results where available. Exclude all other run ranges and Geant4 variants.',
        user_overrides='Full-data request supersedes old locked/reserved/quarantine and stopped-model restrictions for this new weight experiment. Old files and models remain immutable; new split is development, not blind confirmation.',
        sources=sources, physics_list_evidence=physics, mode_counts=dict(collections.Counter(s['mode'] for s in sources)),
        pilot_indices=pilot, pilot_reco_prefix_N=1000,
        features='Exactly audited_features62, pz0-only first-power momentum, raw11, typed NaN, legitimate signed negatives. Same original truth/reco pz>50 and all cuts. No new timing.',
        split=dict(seed=20261109199, fractions=dict(train=.7, cal=.15, test=.15),
            algorithm='Union all response views by conservative canonical-flux:eventID across eras (strip only 24_xing_angle_wo_caloNu_ prefix), actual EVNT path:eventID, and exact float32 native-MeV incoming(PDG,px,py,pz); split connected families with deterministic seeded permutation within component. No target/prediction used. Keep all rows; no quarantine. Source files can contain several roles; no shared parent or incoming across roles.',
            limitation='Full upstream GENIE seed lineage and new blind confirmation are not established. Source files are not disjoint; canonical same-flux/event links are conservative, not proof of independent upstream seeds.'),
        weights=dict(edges_GeV=[50,100,200,400,800,1600,3200,6400], overflow=True,
            base='Each incoming key shares total weight1 across views within role.',
            flat='From training only: base_weight * sum(train base)/(occupied_train_bins * train_bin_base_mass). Preserve base total weight and regularization scale; no clipping.',
            evaluation='Original incoming spectrum and frozen train-map reweighted spectrum; per-bin metrics in both. Do not fit weights to cal/test histograms.',
            calibration='For both arms report raw, common incoming-weighted cal offset and frozen-train-map flat cal offset. Primary training-effect contrast uses common incoming calibration; matching flat calibration is separately reported.'),
        model=dict(features=62, objective='reg:squarederror', target='natural log truth_E_GeV',
            arms=['incoming','flat'], seeds=[2026110255,2026110256,2026110257], rounds=400,
            params=dict(max_depth=5,eta=.04,subsample=.8,colsample_bytree=1.,min_child_weight=20,reg_lambda=10,tree_method='hist',nthread=8),
            initialization='Weighted training mean logE for each arm; boost_from_average=0. No tuning, early stopping or test selection.',
            formal_fits=6, platform='Kubeflow GPU if actual GPU small-sample QA succeeds; CPU fallback otherwise, same device for both arms.'),
        evaluation=dict(bootstrap=500,seed=20261109200,
            strata=['all','E50_100','E100_200','E200_400','E400_800','E800_1600','E1600_3200','E3200_6400','E6400_inf','pz50_100','pz50_100_trueE200','high_y','unconfirmed','input_missing'],
            metrics=['log_RMSE','mean_bias_pct','median_bias_pct','R68_pct','tail50_pct','positive_tail50_pct','negative_tail50_pct'],
            controls='Traditional pz0/0.8, same-split incoming-weighted direct62; Stage87 only historical. Per-run/flux/component breakdown. Family-paired conditional intervals; no independent-source or real-system certification.',
            gates='Retain original two trueE low-bin noninferiority upper95<=1.05 vs traditional; flat/incoming two-low point<=.95 and upper95<1 plus all<=1.01, protection strata<=1.03 and all original eight strata three tails upper95 delta<=2pp. Report cal/test/raw/offset variants without choosing winner.'),
        execution=dict(source_job_cpus=8, source_job_memory_MB=24000, max_concurrent_source_jobs=20,
            K_no_old_short_timeout=True, runtime_s=172800,
            pilot='Full local files and first1000 parent reco prefixes, complete cuts/identity/features/calibration QA and timing before production.',
            storage='Only compact selected arrays, models, predictions, tables and plots. No persistent ROOT/xAOD. Reuse existing Stage130 input, archive terminal logs once.'))
    (OUT / 'protocol.json').write_text(json.dumps(protocol, indent=2)+'\n')
    old87=json.loads((ROOT/'workbook/stage87_energy_ml/protocol.json').read_text())
    original=json.loads(subprocess.check_output(['git','show',f"{old87['starting_commit']}:ml/configs/audited_features.json"],cwd=ROOT))
    current=json.loads((ROOT/'ml/configs/audited_features.json').read_text())
    assert original['features']==current['features'] and original['rules']==current['rules']
    feature_audit=dict(stage87_starting_commit=old87['starting_commit'],direct_features_N=len(current['features']),
        direct_feature_order_and_typed_rules_identical_to_stage87=True,
        stage87_protocol_NN_selected_features_N=len(old87['features']),
        direct_training_code='ml/transfer_posterior.py:fit uses configuration()[features], DMatrix weight=d[weight], weighted mean logE initialization',
        base_weight_code='ml/resplit_energy.py sets weight=1/count(incoming key within role)',
        energy_flat_training_in_stage87=False,posterior_flat_prior_is_distinct_from_direct_BDT_loss=True,features=current['features'])
    (OUT/'stage87_weight_feature_audit.json').write_text(json.dumps(feature_audit,indent=2)+'\n')
    print(dict(sources=len(sources), modes=protocol['mode_counts'], pilot=pilot))


if __name__ == '__main__':
    main()
