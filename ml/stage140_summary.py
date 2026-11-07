"""Complete-toy accounting and pointwise coverage; never certify real physics."""
import csv
import json
import math
import tarfile
from pathlib import Path
import numpy as np
from stage140_batch import OUT,NAMES,SCENARIOS,CRITICAL

def table(path,rows):
    with path.open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n')
        writer.writeheader();writer.writerows(rows)

def wilson(k,n):
    z=1.959963984540054;p=k/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return center-half,center+half

def main():
    cache=Path('ntuples/energy_ml_stage140');toys=[];profiles=[];batchinfo=[]
    for batch in range(60):
        with tarfile.open(cache/f'batch_{batch}_result.tar.gz') as archive:
            info=json.load(archive.extractfile(f'{OUT}/batch_{batch}.json'))
            assert info['completed']==50 and not info['errors'];batchinfo.append(info)
            for i in range(50*(batch%10),50*(batch%10)+50):
                row=json.load(archive.extractfile(f'{OUT}/batch_{batch}/toy_{i}.json'))
                assert row['model']==NAMES[batch//20] and row['scenario']==SCENARIOS[(batch//10)%2]
                assert row['toy']==i and row['max_constraint_residual']<1e-7
                assert row['free_LL']>=row['fixed_LL']-1e-5
                assert abs(row['LR']-max(0.,2*(row['free_LL']-row['fixed_LL'])))<1e-10
                assert row['covered']==(row['LR']<=CRITICAL)
                toys.append(row)
    assert len(toys)==3000 and len({(r['model'],r['scenario'],r['toy']) for r in toys})==3000
    for index in range(6):
        with tarfile.open(cache/f'profile_{index}_result.tar.gz') as archive:
            profiles.append(json.load(archive.extractfile(f'{OUT}/profile_{index}.json')))
    rows=[];validation=[]
    for profile in profiles:
        name=profile['model'];scenario=profile['scenario']
        selected=[r for r in toys if r['model']==name and r['scenario']==scenario]
        assert {r['toy'] for r in selected}==set(range(500))
        k=sum(r['covered'] for r in selected);lo,hi=wilson(k,500);truth=profile['true_psi']
        checks=profile['numerical_validation']
        for check in checks:
            row=next(r for r in selected if r['toy']==check['toy'])
            key='fixed_LL' if check['fixed'] else 'free_LL'
            check['batch_LL_delta']=row[key]-check['gradient_LL']
            check['model']=name;check['scenario']=scenario
            assert abs(check['batch_LL_delta'])<1e-3
            validation.append(check)
        rows.append(dict(model=name,scenario=scenario,toys=500,covered=k,
            coverage=k/500,Wilson_low95=lo,Wilson_high95=hi,
            nominal95_in_Wilson=bool(lo<=.95<=hi),true_psi=truth,
            psi_bias_pp=100*(math.fsum(r['psi_hat'] for r in selected)/500-truth),
            psi_RMS_pp=100*math.sqrt(math.fsum((r['psi_hat']-truth)**2 for r in selected)/500),
            Asimov_low95_pp=profile['Asimov_low95_pp'],Asimov_high95_pp=profile['Asimov_high95_pp'],
            Asimov_width95_pp=profile['Asimov_width95_pp'],
            max_start_LL_gap=max(max(r['start_LL_difference_free'],r['start_LL_difference_fixed']) for r in selected),
            max_fixed_restart_improvement=max(r['fixed_restart_improvement'] for r in selected),
            max_constraint_residual=max(r['max_constraint_residual'] for r in selected),
            CPU_s=sum(r['CPU_s'] for r in selected)))
    table(OUT/'all_toys.tsv',toys);table(OUT/'coverage_summary.tsv',rows)
    table(OUT/'independent_validation.tsv',validation)
    (OUT/'profiles.json').write_text(json.dumps(profiles,indent=2)+'\n')
    pilot=json.loads((OUT/'pilot_results.json').read_text());pilot_deltas=[]
    for r in pilot['results']:
        row=next(v for v in toys if all(v[k]==r[k] for k in ['model','scenario','toy']))
        pilot_deltas.append(abs(row['LR']-r['LR']))
    assert max(pilot_deltas)<1e-3
    result=dict(toys=3000,experiments=6,numerical_checks=len(validation),
        complete_no_failed_toy_dropped=True,pilot_LR_max_abs_difference=max(pilot_deltas),
        max_independent_LL_difference=max(abs(r['delta']) for r in validation),
        numerical_checks_passed=all(r['agreement_abs_below_001'] for r in validation),
        toy_CPU_s=sum(r['CPU_s'] for r in toys),
        profile_CPU_s=sum(r['CPU_s'] for r in profiles),
        scope='pointwise parametric working-model coverage only; no global optimum proof,uniform/actualdata/systematics/background/acceptance certification;stress differs by representation',
        new_regression_fit=0,new_forward=0,new_G4=0,reserved_forward=0,GPU=0,promotion=False)
    (OUT/'coverage_scope.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    for profile in profiles:
        if profile['scenario']=='nominal_empirical':
            values=[r for r in profile['profile'] if abs(100*r['psi']-100*profile['true_psi'])<7]
            axes[0].plot([100*r['psi'] for r in values],[r['LR'] for r in values],label=profile['model'])
    axes[0].axhline(CRITICAL,color='gray',ls='--');axes[0].set(xlabel='Selected E<200 GeV fraction (%)',ylabel='Profile LR',ylim=(0,12));axes[0].legend(fontsize=8)
    for i,row in enumerate(rows):
        axes[1].errorbar(i,row['coverage'],yerr=[[row['coverage']-row['Wilson_low95']],[row['Wilson_high95']-row['coverage']]],fmt='o',capsize=3)
    axes[1].axhline(.95,color='gray',ls='--');axes[1].set_xticks(range(6),[r['model']+'\n'+('nominal' if r['scenario']=='nominal_empirical' else 'artificial stress') for r in rows],rotation=35,ha='right',fontsize=7)
    axes[1].set(ylabel='Pointwise coverage (Wilson 95%)')
    for ax in axes:ax.grid(alpha=.2)
    fig.suptitle('Finite auxiliary MC; 500 toys per working-model scenario')
    fig.savefig(OUT/'finite_MC_profiles_coverage.png',dpi=160);plt.close(fig)
    assert result['numerical_checks_passed'],'Independent objective disagreements; no final coverage certification'

if __name__=='__main__':main()
