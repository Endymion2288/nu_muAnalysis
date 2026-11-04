"""Stage91 independent saved-array validation, summaries and cost plots."""
import csv
import json

import numpy as np

from audit_batched_posterior import OUT,CACHE,REPO
from support_augmentation import arrays,save,table,begin,resources


def read(path):
    return list(csv.DictReader(path.open(),delimiter='\t'))


def main():
    start=begin();d=arrays(CACHE/'input.npz')
    original=arrays(REPO/'ntuples/energy_ml_stage90/input.npz')
    reference=arrays(REPO/'ntuples/energy_ml_stage90/audit_values.npz')
    for key in ['row','head','role','weight','truth_E_GeV','pz','b','T','key_id','group']:
        np.testing.assert_array_equal(d[key],original[key])
    for key in ['reference_value','reference_gradient','reference_uncertainty']:
        np.testing.assert_array_equal(d[key],reference[key])
    np.testing.assert_array_equal(d['row'],reference['row'])
    summaries=read(OUT/'numerics.tsv');values={};checks=0;maximum=0.;role_rows=[]
    tolerance=1e-4+1e-3*abs(d['reference_gradient'])
    for r in summaries:
        name=f"{r['device']}_{r['batch']}";v=arrays(CACHE/f'{name}.npz');values[name]=v
        np.testing.assert_array_equal(v['row'],d['row'])
        error=abs(v['gradient']-d['reference_gradient'])
        passed=(error+d['reference_uncertainty'])<=tolerance
        certified=passed.all(1)&(abs(v['value']-d['reference_value'])<=1e-6)&np.isfinite(v['value'])&np.isfinite(v['gradient']).all(1)
        np.testing.assert_array_equal(passed,v['gradient_pass']);np.testing.assert_array_equal(certified,v['certified'])
        tests=dict(certified_N=certified.sum(),failed_values_N=(abs(v['value']-d['reference_value'])>1e-6).sum(),
            failed_coordinates_N=(~passed).sum(),max_value_error=abs(v['value']-d['reference_value']).max(),
            max_gradient_error=error.max(),max_gradient_error_plus_uncertainty_over_tolerance=((error+d['reference_uncertainty'])/tolerance).max())
        for key,value in tests.items():
            diff=abs(float(r[key])-float(value));assert diff<1e-12;maximum=max(maximum,diff);checks+=1
        checks+=passed.size+len(certified)
        for code,role in [(1,'train'),(2,'cal')]:
            mask=d['role']==code
            role_rows.append(dict(method=name,role=role,N=int(mask.sum()),certified_N=int(certified[mask].sum()),
                max_value_error=float(abs(v['value'][mask]-d['reference_value'][mask]).max()),
                max_gradient_error=float(error[mask].max()),failed_coordinates_N=int((~passed[mask]).sum())))
    events=[];coords=[];names=[f'{family}{k}' for family in ['logit','mr','ms','sr_raw','ss_raw'] for k in range(3)]+['b','T']
    for i,row in enumerate(d['row']):
        events.append(dict(row=int(row),role=int(d['role'][i]),weight=float(d['weight'][i]),
            **{name+'_value':float(v['value'][i]) for name,v in values.items()},
            all_certified=bool(all(v['certified'][i] for v in values.values()))))
        for j,parameter in enumerate(names):
            coords.append(dict(row=int(row),role=int(d['role'][i]),parameter=parameter,
                reference_gradient=float(d['reference_gradient'][i,j]),reference_uncertainty=float(d['reference_uncertainty'][i,j]),
                tolerance=float(tolerance[i,j]),**{name+'_gradient':float(v['gradient'][i,j]) for name,v in values.items()},
                all_passed=bool(all(v['gradient_pass'][i,j] for v in values.values()))))
    table(OUT/'events.tsv',events);table(OUT/'gradients.tsv',coords);table(OUT/'role_summary.tsv',role_rows)
    # Independently recover the original float32 leaf VJP from saved local QA.
    qa=arrays(CACHE/'qa_input.npz');up=np.linspace(-.7,1.3,40)
    for device in ['cpu','cuda']:
        g=arrays(CACHE/f'qa_{device}.npz')['gradient']
        actual=arrays(CACHE/f'qa_{device}_vjp.npz')['head_gradient']
        expected=(g[:,:15]*up[:,None]).astype('float32')
        # torch.linspace and numpy.linspace may differ at the last bit.
        assert np.max(abs(actual-expected))<2e-6
        checks+=actual.size
    benchmarks=json.loads((OUT/'benchmark.json').read_text())
    timing=[]
    for batch in [256,1024]:
        cpu=next(r for r in benchmarks['measurements'] if r['device']=='cpu' and r['batch']==batch)
        gpu=next(r for r in benchmarks['measurements'] if r['device']=='cuda' and r['batch']==batch)
        for r in [cpu,gpu]:
            assert len(r['wall_s'])==5 and r['warmup_repeats']==1
            assert abs(float(np.median(r['wall_s']))-r['median_wall_s'])<1e-12
        timing.append(dict(batch=batch,CPU_median_wall_s=cpu['median_wall_s'],GPU_median_wall_s=gpu['median_wall_s'],
            GPU_speedup=cpu['median_wall_s']/gpu['median_wall_s'],
            CPU_events_per_wall_s=cpu['median_events_per_wall_s'],GPU_events_per_wall_s=gpu['median_events_per_wall_s'],
            GPU_peak_allocated_MiB=gpu['GPU_peak_allocated_MiB'],
            projected_150epochs_GPU_density_wall_s=6986250/gpu['median_events_per_wall_s'],
            projection='fixedcal heads repeated, density/VJP only; excludes network/joint/calibration/inference; not measured training or bound'))
    table(OUT/'throughput.tsv',timing)
    save(OUT/'independent_validation.json',dict(passed=True,complete_records=552,methods=4,coordinate_comparisons=37536,
        checked_flags_and_values=checks,max_summary_difference=maximum,all_certified=all(v['certified'].all().item() for v in values.values()),
        role_weight_head_reference_exact=True,local_float32_VJP_recovered=True,new_integrations=0,new_fits=0,new_test_evaluations=0,
        interpretation='saved reference arithmetic only, no population/trajectory/response/physics certification',**resources(start)))
    plot(values,d,tolerance,timing)
    save(OUT/'report_resources.json',resources(start))
    print(json.dumps(dict(role_summary=role_rows,throughput=timing),ensure_ascii=False,indent=2))


def plot(values,d,tolerance,timing):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    for name,color in [('cpu_256','#0072b2'),('cuda_1024','#009e73')]:
        e=(abs(values[name]['gradient']-d['reference_gradient'])+d['reference_uncertainty'])/tolerance
        x=np.sort(e.ravel());axes[0].plot(np.maximum(x,1e-16),np.arange(1,len(x)+1)/len(x),label=name,color=color)
    axes[0].axvline(1,color='grey',ls='--');axes[0].set_xscale('log');axes[0].set_xlim(1e-6,2)
    axes[0].set_xlabel('Gradient discrepancy / frozen tolerance');axes[0].set_ylabel('Fraction of 9,384 coordinates')
    axes[0].legend(fontsize=8);axes[0].set_title('Includes saved reference uncertainty')
    x=np.arange(2)
    axes[1].bar(x-.16,[r['CPU_events_per_wall_s'] for r in timing],width=.32,label='CPU, 2 threads',color='#0072b2')
    axes[1].bar(x+.16,[r['GPU_events_per_wall_s'] for r in timing],width=.32,label='GPU',color='#009e73')
    axes[1].set_xticks(x,['256','1024']);axes[1].set_xlabel('Batch size');axes[1].set_ylabel('Events / wall second')
    axes[1].legend(fontsize=8);axes[1].set_title('Transfers + nodes + forward/backward')
    fig.suptitle('Stage91: fixed GL32 score likelihood; no fitting or new test evaluation',fontsize=11)
    path=OUT/'batched_likelihood.svg';fig.savefig(path);path.write_text('\n'.join(l.rstrip() for l in path.read_text().splitlines())+'\n')
    fig.savefig('/tmp/stage91_batched_likelihood.png',dpi=140);plt.close(fig)


if __name__=='__main__':
    main()
