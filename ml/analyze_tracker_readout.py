#!/usr/bin/env python3
"""Summarize frozen conditional activity; never fit a noise or energy model."""
import argparse
import csv
import json
import resource
import tarfile
import time
from pathlib import Path

import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    start, cpu = time.perf_counter(), time.process_time()
    directory = args.directory
    output=args.output;output.mkdir(parents=True,exist_ok=True)
    sample = json.loads((directory/'sample.json').read_text())
    events, files, resources = [], [], []
    for path in sorted(directory.glob('native_*.json')):
        result = json.loads(path.read_text()); resources.append({k:v for k,v in result.items() if k!='sources'})
        for row in result['sources']:
            source = sample['sources'][row['source']]
            assert row['matched'] == row['requested'] == len(source['cases'])
            assert not row['unresolved']
            files.extend(dict(source=row['source'], **f) for f in row['files'])
            for record in row['records']:
                case = source['cases'][record['case']]
                assert record['event'] == case['event']
                values = np.asarray(record['values'])
                if values.shape == (4,23):
                    # v1 shards completed with strict strip-range checks.
                    values=np.pad(values,((0,0),(0,2)))
                assert values.shape == (4,25)
                assert values[:,3].tolist() == case['original_counts'][:4]
                assert np.all(values >= 0)
                assert np.array_equal(values[:,17:22].sum(axis=1), values[:,3])
                assert np.all(values[:,1] <= values[:,0])
                assert np.all(values[:,2] <= values[:,1])
                assert np.all(values[:,4] <= values[:,3])
                assert np.all(values[:,22] <= values[:,4])
                assert np.all(values[:,6] <= 36864)
                events.append(dict(source=source['source'],run=source['run'],
                    kind=source['sample'],case=record['case'],pbin=case['pbin'],
                    pz=case['track'][1]/1000,x=case['track'][6],y=case['track'][7],
                    sp=case['original_counts'][4],segments=case['original_counts'][5],
                    timestamp=record['timestamp'],bcid=record['bcid'],values=values))
    assert len(events) == 4096
    assert len({(e['source'],e['case']) for e in events}) == 4096
    kinds = np.array([e['kind'] for e in events]); sources = np.array([e['source'] for e in events])
    runs = np.array([e['run'] for e in events]); pbin = np.array([e['pbin'] for e in events])
    rho = np.hypot([e['x'] for e in events], [e['y'] for e in events])
    rhobin = np.digitize(rho, [40,80])
    values = np.array([e['values'] for e in events], dtype=float)
    rng = np.random.default_rng(2026110385)
    # Fixed run/charge composition; the interval cannot claim unseen-run coverage.
    draws = {}
    for kind in ['data','MC']:
        blocks = []
        for run in np.unique(runs[kinds==kind]):
            ids = np.unique(sources[(kinds==kind)&(runs==run)])
            blocks.append(rng.choice(ids, (500,len(ids)), replace=True))
        draws[kind] = np.concatenate(blocks, axis=1)
    (output/'bootstrap_sources.json').write_text(json.dumps(
        {kind:draw.tolist() for kind,draw in draws.items()},separators=(',',':'))+'\n')
    multiplicities = {kind:np.array([np.bincount(row,minlength=18) for row in draw])[:,sources]
                      for kind,draw in draws.items()}
    layers = dict(all=np.ones(len(events),bool),p100_250=pbin==0,p250_1000=pbin==1,
                  rho_lt40=rhobin==0,rho40_80=rhobin==1,rho_ge80=rhobin==2,
                  x_negative=np.array([e['x'] for e in events])<0,
                  x_nonnegative=np.array([e['x'] for e in events])>=0,
                  y_negative=np.array([e['y'] for e in events])<0,
                  y_nonnegative=np.array([e['y'] for e in events])>=0)
    for p in [0,1]:
        for r in range(3): layers[f'p{p}_rho{r}']=(pbin==p)&(rhobin==r)
    observables = dict(raw_strips=(0,'strip/event'),outside_strips=(1,'strip/event'),
        isolated_outside_strips=(2,'strip/event'),clusters=(3,'cluster/event'),
        outside_clusters=(4,'cluster/event'),outside_singleton_clusters=(5,'cluster/event'),
        measured_wafers=(7,'wafer/event'),isolated_outside_clusters=(22,'cluster/event'))
    observables['unknown_cluster_geometry']=(23,'cluster/event')
    observables['invalid_cluster_strip_ids']=(24,'ID/event')
    table, comparisons = [], []
    for station in ['common',0,1,2,3]:
        matrix = values[:,1:4].sum(axis=1) if station=='common' else values[:,station]
        measurements = {name:(matrix[:,index],unit) for name,(index,unit) in observables.items()}
        denom = 110592 if station=='common' else 36864
        measurements['nominal_raw_rate']=(matrix[:,0]/denom,'strip/nominal_channel/event')
        measurements['nominal_outside_rate']=(matrix[:,1]/matrix[:,6],'strip/nominal_outside_channel/event')
        measurements['outside_cluster_nonzero']=(1.*(matrix[:,4]>0),'event_fraction')
        measurements['outside_clusters_upper']=(matrix[:,4]+matrix[:,23],'cluster/event')
        # The actual production log specifies 01X clustering for data and MC.
        # This deterministic readout audit is not a new timing-window scan.
        accepted=matrix[:,11]+matrix[:,12]
        measurements['raw_01X_strips']=(accepted,'strip_timebin_count/event')
        measurements['raw_rejected_by_01X']=(matrix[:,9:17].sum(axis=1)-accepted,'strip_timebin_count/event')
        for b in range(8): measurements[f'timebin_{b:03b}']=(matrix[:,9+b],'strip_timebin_count/event')
        for b in range(5): measurements[f'cluster_size_{b+1 if b<4 else "ge5"}']=(matrix[:,17+b],'cluster/event')
        if station=='common':
            measurements['spacepoints']=(np.array([e['sp'] for e in events]),'SP/event')
            measurements['segments']=(np.array([e['segments'] for e in events]),'segment/event')
        for layer, mask in layers.items():
            for name,(measurement,unit) in measurements.items():
                stats = {}
                for kind in ['data','MC']:
                    selected = mask&(kinds==kind); a=measurement[selected]
                    weights = multiplicities[kind][:,selected]
                    sums = weights.sum(axis=1)
                    boot = np.divide(weights@a,sums,out=np.full(500,np.nan),where=sums>0)
                    stats[kind] = (float(a.mean()),boot)
                    q=np.quantile(a,[.16,.5,.84,.95,.99])
                    table.append(dict(station=station,layer=layer,observable=name,unit=unit,kind=kind,
                        n=len(a),sources=len(np.unique(sources[selected])),mean=a.mean(),
                        low95=np.nanquantile(boot,.025),high95=np.nanquantile(boot,.975),
                        q16=q[0],median=q[1],q84=q[2],q95=q[3],q99=q[4]))
                delta=stats['data'][1]-stats['MC'][1]
                comparisons.append(dict(station=station,layer=layer,observable=name,unit=unit,
                    data=stats['data'][0],MC=stats['MC'][0],difference=stats['data'][0]-stats['MC'][0],
                    low95=np.nanquantile(delta,.025),high95=np.nanquantile(delta,.975)))
    def write(name, rows):
        with (output/name).open('w') as out:
            writer=csv.DictWriter(out,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(rows)
    write('activity.tsv',table);write('differences.tsv',comparisons)
    source_table=[]
    for source in range(18):
        selected=sources==source; v=values[selected,1:4].sum(axis=1)
        source_table.append(dict(source=source,run=int(runs[selected][0]),kind=kinds[selected][0],n=int(selected.sum()),
            pbin0=int(((pbin==0)&selected).sum()),mean_rho_mm=float(rho[selected].mean()),
            raw_strips=float(v[:,0].mean()),outside_strips=float(v[:,1].mean()),
            clusters=float(v[:,3].mean()),outside_clusters=float(v[:,4].mean()),
            sp=float(np.mean([e['sp'] for e in events if e['source']==source])),
            segments=float(np.mean([e['segments'] for e in events if e['source']==source]))))
    write('sources.tsv',source_table)
    support=[]
    for layer,mask in layers.items():
        for kind in ['data','MC']:
            selected=mask&(kinds==kind)
            pz=np.array([e['pz'] for e in events])[selected]
            position=rho[selected]
            support.append(dict(layer=layer,kind=kind,n=int(selected.sum()),
                sources=len(np.unique(sources[selected])),pz0_mean_GeV=float(pz.mean()),
                pz0_q05_GeV=float(np.quantile(pz,.05)),pz0_median_GeV=float(np.median(pz)),
                pz0_q95_GeV=float(np.quantile(pz,.95)),rho_mean_mm=float(position.mean()),
                rho_q95_mm=float(np.quantile(position,.95))))
    write('kinematic_support.tsv',support)
    correlations=[]
    for kind in ['data','MC']:
        selected=kinds==kind
        for label,index in [('raw',0),('outside_strips',1),('clusters',3),('outside_clusters',4)]:
            corr=np.corrcoef(values[selected,1:4,index],rowvar=False)
            a=values[selected,1:4,index];weights=multiplicities[kind][:,selected]
            means=(weights@a)/weights.sum(axis=1)[:,None]
            seconds=(weights@(a*a))/weights.sum(axis=1)[:,None]
            variances=seconds-means*means
            intervals=[]
            for left,right in [(0,1),(0,2),(1,2)]:
                product=(weights@(a[:,left]*a[:,right]))/weights.sum(axis=1)
                boot=(product-means[:,left]*means[:,right])/np.sqrt(variances[:,left]*variances[:,right])
                intervals.append(dict(stations=[left+1,right+1],low95=np.quantile(boot,.025),high95=np.quantile(boot,.975)))
            correlations.append(dict(kind=kind,observable=label,stations=[1,2,3],pearson=corr.tolist(),intervals=intervals))
    # Existing stage53 on/off summaries only: no digitization or reconstruction.
    paired=[]
    archive=Path(__file__).resolve().parents[1]/'ntuples/energy_ml_stage53/replay_results.tar.gz'
    with tarfile.open(archive) as bundle:
        for source in range(12):
            nominal=json.load(bundle.extractfile(f'nominal_{source}.json'))
            off=json.load(bundle.extractfile(f'nonoise_{source}.json'))
            assert len(nominal['records'])==len(off['records'])==len(sample['sources'][source]['cases'])
            for case_index,(on,zero) in enumerate(zip(nominal['records'],off['records'])):
                assert on['entry']==zero['entry']==sample['sources'][source]['cases'][case_index]['entry']
                for label in ['Reference','Replay']:
                    assert len(on['clusters'][label])==4
                assert on['clusters']['Reference']==sample['sources'][source]['cases'][case_index]['original_counts'][:4]
                paired.append(dict(source=source,case=case_index,
                    on=on['clusters']['Replay']+[on['spacepoints']['Replay'],on['segments']['Replay']],
                    off=zero['clusters']['Replay']+[zero['spacepoints']['Replay'],zero['segments']['Replay']]))
    pair_index={(r['source'],r['case']):r for r in paired}
    aligned=[pair_index[(e['source'],e['case'])] for e in events if e['kind']=='MC']
    pair_table=[]
    w=multiplicities['MC'][:,kinds=='MC']
    for index,name in enumerate(['clusters0','clusters1','clusters2','clusters3','spacepoints','segments']):
        on=np.array([r['on'][index] for r in aligned]);off=np.array([r['off'][index] for r in aligned])
        delta=on-off;boot=(w@delta)/w.sum(axis=1)
        pair_table.append(dict(observable=name,n=len(delta),on=float(on.mean()),off=float(off.mean()),
            on_minus_off=float(delta.mean()),low95=np.quantile(boot,.025),high95=np.quantile(boot,.975)))
    write('stage53_fixed_on_off.tsv',pair_table)
    summary=dict(events={k:int(np.sum(kinds==k)) for k in ['data','MC']},
        common_stations=[1,2,3],active_denominator_certified=False,noise_identified=False,
        outcome='B conditional activity; C for pure noise identification and certified active-channel rate',
        source_bootstrap=dict(replicates=500,seed=2026110385,scheme='within fixed data run / MC charge run',
                              limitations='fixed prediction/sample/selection; no new-run extrapolation or detector nuisance coverage'),
        correlations=correlations,resources=resources,files=files,
        bytes_read=sum(r['bytes_read'] for r in resources),
        analysis_wall_s=time.perf_counter()-start,analysis_cpu_s=time.process_time()-cpu,
        analysis_peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(12,3.5))
    for ax,(index,label,limit,width) in zip(axes,[(0,'Raw strips, stations 1–3',250,5),
        (1,'Outside-corridor strips',200,4),(4,'Outside-corridor clusters',40,1)]):
        for kind in ['MC','data']:
            a=values[kinds==kind,1:4,index].sum(axis=1)
            ax.hist(np.minimum(a,limit),bins=np.arange(0,limit+2*width,width),density=True,histtype='step',label=kind)
        ax.set_xlabel(label+f' / event ({limit} = overflow)');ax.set_ylabel('Density');ax.set_yscale('log');ax.legend()
    fig.suptitle('Selected 100–1000 GeV muons: conditional activity; active DAQ denominator unverified',fontsize=10)
    fig.tight_layout();fig.savefig(output/'conditional_activity.png',dpi=150);plt.close(fig)
    print(json.dumps({k:summary[k] for k in ['events','bytes_read','analysis_wall_s','analysis_cpu_s']}))


if __name__=='__main__':
    main()
