"""Freeze one cost-based mechanism experiment, after pilot and before any risks."""
import gzip
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage131_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage131'

def main():
    assert not (OUT/'production_contract.json').exists()
    pilot=json.loads((OUT/'pilot_contract.json').read_text())
    results=json.loads((OUT/'pilot_results.json').read_text());assert len(results)==12 and all(r['successful'] for r in results)
    samples=[]
    for r in results:
        i=r['index'];summary=json.loads((OUT/f'parent_{i}_summary.json').read_text());closure=json.loads((OUT/f'parent_{i}_hitscheck.json').read_text());assert closure['passed']
        assert summary['lineage']['unknown_tracks']==summary['lineage']['missing_birth']
        cpu=0
        for path in OUT.glob(f'parent_{i}_*_time.txt'):
            if 'sim_unobserved' in path.name or 'noninterference' in path.name:continue
            text=path.read_text();cpu+=sum(float(x) for x in re.findall(r'(?:User time|System time) \(seconds\): ([\d.]+)',text))
        samples.append(dict(index=i,CPU_s=cpu,wall_s=summary['wall_s'],selected=json.loads((OUT/f'parent_{i}_selection.json').read_text())['selected_N'],tracks=summary['lineage']['tracks'],unknown_tracks=summary['lineage']['unknown_tracks'],outside_primaries=summary['lineage']['outside_primaries'],target_envelope_seen=any(n in ['EmulsionStationA','Emulsion::EmulsionStationA'] for n in summary['lineage']['envelopes'])))
    assert json.loads((OUT/'observer_noninterference.json').read_text())['observer_on_off_sensitive_hits_exact']
    with gzip.open(CACHE/'frame.json.gz','rt') as f:frame=json.load(f)
    # One size determined by cost, never by a fitted result. Equal scale reduction
    # preserves K and every role/stratum if unexpectedly expensive.
    allocations={1:dict(E50_100=512,E100_200=512,lowpz_highE=256,high_y=256,transition=512,highE=256),
        2:dict(E50_100=192,E100_200=192,lowpz_highE=96,high_y=96,transition=192,highE=96),
        3:dict(E50_100=192,E100_200=192,lowpz_highE=96,high_y=96,transition=192,highE=96)}
    budget=1500000.;mean=sum(r['CPU_s'] for r in samples)/len(samples);planned=sum(sum(x.values()) for x in allocations.values());factor=min(1.,budget/(max(mean,1)*planned*2))
    cells=[];selected=[]
    for role,allocation in allocations.items():
        for layer,requested in allocation.items():
            pool=[r for r in frame if r['role']==role and r['stratum']==layer]
            n=min(len(pool),max(24,int(requested*factor)))
            assert n<=len(pool)
            for r in pool[:n]:
                r=dict(r);r['inclusion_probability']=n/len(pool);selected.append(r)
            cells.append(dict(role=role,stratum=layer,frame_N=len(pool),sample_N=n,inclusion_probability=n/len(pool)))
    indices=[r['frame_index'] for r in selected];reused=sorted(set(indices)&set(pilot['pilot_indices']));new=[i for i in indices if i not in reused]
    assert len(reused)==12
    wave_seeds=[(r['seed']+1 if r['frame_index']==50 else 650000000+10000*r['frame_index'])+1000*j for r in selected for j in range(5)]
    assert len(set(wave_seeds))==len(wave_seeds) and max(wave_seeds)<2**31
    baseline=json.loads((ROOT/'workbook/stage130_energy_ml/curve_protocol.json').read_text())['baseline']
    contract=dict(stage=131,parents_N=len(indices),indices=indices,pilot_reused=reused,new_indices=new,cells=cells,
        batches=[new[i:i+8] for i in range(0,len(new),8)],
        natural_frame='Stage130 historically selected unique incoming proxy; fresh full response, original cuts reapplied; response replays do not add independent neutrino interactions',
        sampling='canonical source first, then fixed hash nuMu131 order within originalrole×6disjointstrata; inverse inclusion weights for train/cal/eval; trainweights normalized to mean1 for fixed regularization; no residual selection',
        resources=dict(pilot=samples,pilot_mean_CPU_s=mean,CPU_budget_s=budget,predicted_CPU_s=mean*len(new),allocation_factor=factor,cpus_per_job=8,memory_MB=24000,max_materialize=32,scheduler_MaxRuntime_s=86400,application_timeout=None),
        no_new_energy_risks_seen=True,baseline=baseline,
        waveform_seeds='firstpreflight frame50 retains recorded originalbase; others650000000+10000*frame_index,plus1000*detector; all five-detector private seeds globally unique in frozen cohort and <2^31',
        detectors=['veto','trigger','preshower','sct','ecal'],windows=dict(energy_features='one fixed G4 globaltime[0,1000)ns window',alltime='audit only,not fitted; no claim that global window is calibratedDAQtime'),
        arms=dict(X='audited62',A='X +7 oracle availability controls',U='A +5 log1p unsplit depositedMeV/1000 in fixedpromptwindow',L='U +5 root-muon deposited-energy fractions in samewindow, denominator0 or ambiguity =>NaN',F='U +log1p nonmu first-exit transport KE_GeV; one fixed envelope, alltime; no totalE or missing-energy closure',P='X +5 train-only source-threefold crossfit prompt root-muon fractions predicted from measured X; new supervision, no new sensor information'),
        proxy=dict(folds=3,split='source_index modulo3',rounds=150,max_depth=3,eta=.04,seed=2026110731,targets='5 prompt root-muon depositfractions; missing labels not fitted; trainonly supervision; finaltraining fits applied tocal/test; no oracle-valid flag at deployment'),
        energy_fit_budget=18,energy_hyperparameter_grid=False,calibration='same-support calibration inverse-inclusion weighted mean log residual, one offset per ensemble',
        primary_contrasts=['L/U: attribution beyond unsplit ideal deposit','F/U: fixed-boundary flow','P/X: deployable supervised proxy','U/A: idealized unsplit deposit','A/X: availability control'],
        primary_endpoint='two low-energy log-RMSE; report bothcal/test pairedincoming stratified500bootstrap; 5%point decrease and upper95<1 in bothbins as mechanism continuation target; originalhigh-y/lowpz/highE+tail guardrails retained; no equivalence from wideCI',
        promotion='none from this conditional replay cohort; fullcohort/true independentconfirmation/realdata+nuisances still required; original1.05/1.01/1.03 and8layers×3tails upper95≤+2pp not relaxed',
        failure='keep failedattempt resource ledger; engineering repair with sameparent/seed, no substitution by favorable yield; selectedfail retained in migration denominator and not used as fake selected energy events',
        limitations=['canonical incoming is a conservative proxy,not completeGENIEfamily certificate','initial frame selected under oldresponse,so reselectedrisk is conditional ratherthan fullnaturalacceptance','invisible outgoing flow of stack-killed neutrinos is unmeasured','proxy learns fromX only and cannot create information; oracle alone not deployment','pairwise95% intervals are conditional,not simultaneous/source/refit/researchselection/system coverage'])
    (OUT/'production_contract.json').write_text(json.dumps(contract,indent=2)+'\n')
    with gzip.open(CACHE/'production_cases.json.gz','wt') as f:json.dump(selected,f,separators=(',',':'))
    print('Frozen parents',len(indices),'new',len(new),'expectedCPU_s',contract['resources']['predicted_CPU_s'])

if __name__=='__main__':main()
