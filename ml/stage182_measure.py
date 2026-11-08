"""Cached upstream strict support and same-window sources, executed on HTCondor."""
import csv,gzip,json,math,resource,sys,time
from pathlib import Path
ROOT=Path.cwd();OUT=ROOT/'workbook/stage182_energy_ml';p=json.loads((OUT/'protocol.json').read_text())
CATEGORIES=['primary_muon_direct','before_S0','after_S0','other_root','unknown_root','unknown_S0']
CHANNELS={4:'VetoNu',5:'VetoNu',14:'Veto',6:'Veto',7:'Veto'}
CONVERT=2*2/16384/50*1000

def table(path,rows):
    with path.open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n',quoting=csv.QUOTE_NONNUMERIC)
        writer.writeheader();writer.writerows(rows)

def compute(indices):
    refs={(int(r['index']),int(r['channel'])):r for r in csv.DictReader((ROOT/p['charge_table']).open(),delimiter='\t')}
    cal={r['pair']:r for r in json.loads((ROOT/p['calibration']).read_text()) if r['kind']=='MC'}
    channels=[];pairs=[]
    for index in indices:
        with gzip.open(ROOT/f'ntuples/energy_ml_stage179/parent_{index}_response.json.gz','rt') as stream:r=json.load(stream)
        actual={w['channel']:w for rec in r['records'].values() for w in rec['waves']}
        for channel,detector in CHANNELS.items():
            wave=actual.get(channel);result=wave['result'] if wave else None
            strict=bool(result and int(result[0])==0 and math.isfinite(result[5]) and result[5]>0)
            row=dict(index=index,channel=channel,detector=detector,present=bool(wave),status=int(result[0]) if result else None,
                signed_raw_pC=float(result[1]) if result else None,strict_time=strict,localtime_ns=float(result[5]) if strict else None,
                ADC_samples=len(wave['adc']) if wave else 0,first_sample_ns=0 if wave else None,last_sample_ns=2*(len(wave['adc'])-1) if wave else None,
                stored_start_ns=result[6] if wave else None,stored_end_ns=result[7] if wave else None,
                signal_in_window_pC=None,signal_all_retained_samples_pC=None,window_signal_fraction=None,source_direction='unknown')
            row.update({k+'_pC':None for k in CATEGORIES})
            if wave:
                saved=refs[index,channel];assert row['signed_raw_pC']==float(saved['actual_signed_raw_pC']) and row['status']==int(saved['status'])
                a=r['analog'][detector];positions=[j for j,t in enumerate(a['total']) if int(t[0])==wave['id32']]
                window=[j for j in positions if result[6]<=2*a['total'][j][1]<=result[7]]
                assert len(positions)==len(wave['adc'])
                total=CONVERT*math.fsum(a['total'][j][2] for j in positions);inside=CONVERT*math.fsum(a['total'][j][2] for j in window)
                row.update(signal_in_window_pC=inside,signal_all_retained_samples_pC=total,window_signal_fraction=inside/total if total>0 else None)
                assert math.isclose(inside,float(saved['signal_pC']),rel_tol=1e-10,abs_tol=1e-10)
                for category in CATEGORIES:
                    value=CONVERT*math.fsum(a['split'][category][j] for j in window)
                    assert math.isclose(value,float(saved[category+'_pC']),rel_tol=1e-10,abs_tol=1e-10)
                    row[category+'_pC']=value
            channels.append(row)
        for pair in p['pairs']:
            left=next(x for x in channels if x['index']==index and x['channel']==pair['i'])
            right=next(x for x in channels if x['index']==index and x['channel']==pair['j'])
            c=cal[pair['calibration']];both=left['present'] and right['present'];status=bool(both and left['status']==right['status']==0)
            strict=left['strict_time'] and right['strict_time']
            necessary=bool(strict and c['usable'] and all(c['ranges'][k][0]<=x['signed_raw_pC']<=c['ranges'][k][1] for k,x in [('qi',left),('qj',right)]))
            pairs.append(dict(index=index,pair=pair['name'],both_present=both,both_status0=status,strict_time=strict,
                necessary_Q_range=necessary,full_spatial_calibration_certified=False,
                raw_local_delta_ns=left['localtime_ns']-right['localtime_ns'] if strict else None,
                calibrated_delta_ns=None))
    summary=[]
    for pair in p['pairs']:
        subset=[r for r in pairs if r['pair']==pair['name']]
        summary.append(dict(pair=pair['name'],parents_N=len(indices),both_present_N=sum(r['both_present'] for r in subset),both_status0_N=sum(r['both_status0'] for r in subset),
            strict_N=sum(r['strict_time'] for r in subset),necessary_Q_range_N=sum(r['necessary_Q_range'] for r in subset),full_calibrated_N=0,backscatter_certified_N=0))
    sources=[]
    for channel,detector in CHANNELS.items():
        subset=[r for r in channels if r['channel']==channel];measured=[r for r in subset if r['present']]
        sources.append(dict(channel=channel,detector=detector,parents_N=len(indices),present_N=len(measured),status0_N=sum(r['status']==0 for r in measured),strict_N=sum(r['strict_time'] for r in measured),
            signal_in_window_pC=math.fsum(r['signal_in_window_pC'] for r in measured),signal_all_retained_samples_pC=math.fsum(r['signal_all_retained_samples_pC'] for r in measured),
            **{k+'_pC':math.fsum(r[k+'_pC'] for r in measured) for k in CATEGORIES}))
    return channels,pairs,summary,sources

if __name__=='__main__':
    tick,cpu=time.perf_counter(),time.process_time();phase=sys.argv[1];indices=p['pilot_indices'] if phase=='pilot' else p['indices']
    channels,pairs,summary,sources=compute(indices)
    for name,rows in [('channels',channels),('pairs',pairs),('support',summary),('sources',sources)]:table(OUT/f'{phase}_{name}.tsv',rows)
    if phase in ['full','audit']:
        for name,rows in [('channels',channels),('pairs',pairs)]:
            prefix=list(csv.DictReader((OUT/f'pilot_{name}.tsv').open(),delimiter='\t'))
            assert len(prefix)==len([r for r in rows if r['index']==50])
            # Same serialization from exact first parent, preserving nulls and strict missingness.
            tmp=OUT/f'{phase}_prefix_{name}.tsv';table(tmp,[r for r in rows if r['index']==50])
            assert tmp.read_bytes()==(OUT/f'pilot_{name}.tsv').read_bytes();tmp.unlink()
    if phase=='audit':
        for name in ['channels','pairs','support','sources']:assert (OUT/f'audit_{name}.tsv').read_bytes()==(OUT/f'full_{name}.tsv').read_bytes()
        # Independent scalar count from raw official result arrays, without compute() flags.
        cals={r['pair']:r for r in json.loads((ROOT/p['calibration']).read_text()) if r['kind']=='MC'}
        counts={q['name']:[0,0,0,0] for q in p['pairs']}
        for index in indices:
            with gzip.open(ROOT/f'ntuples/energy_ml_stage179/parent_{index}_response.json.gz','rt') as stream:r=json.load(stream)
            lookup={w['channel']:w['result'] for rec in r['records'].values() for w in rec['waves']}
            for q in p['pairs']:
                i,j=q['i'],q['j']
                if i not in lookup or j not in lookup:continue
                counts[q['name']][0]+=1;a,b=lookup[i],lookup[j]
                if a[0]!=0 or b[0]!=0:continue
                counts[q['name']][1]+=1
                if not (math.isfinite(a[5]) and math.isfinite(b[5]) and a[5]>0 and b[5]>0):continue
                counts[q['name']][2]+=1;cal=cals[q['calibration']]
                if cal['usable'] and cal['ranges']['qi'][0]<=a[1]<=cal['ranges']['qi'][1] and cal['ranges']['qj'][0]<=b[1]<=cal['ranges']['qj'][1]:counts[q['name']][3]+=1
        for row in summary:assert counts[row['pair']]==[row[k] for k in ['both_present_N','both_status0_N','strict_N','necessary_Q_range_N']]
        assert all(r['localtime_ns'] is None for r in channels if not r['strict_time'])
        (OUT/'independent_validation.json').write_text(json.dumps(dict(passed=True,parent_N=len(indices),scalar_pair_counts=counts,full_tables_exact=True,pilot_exact=True,no_bad_hit_timing=True,source_integrals_vs_stage179_exact=True),indent=2)+'\n')
    report=dict(passed=True,phase=phase,parent_N=len(indices),channel_rows_N=len(channels),pair_rows_N=len(pairs),support=summary,sources=sources,
        CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        G4=0,energy_fits=0,new_forward=0,calibration_scope='Necessary Q support only; spatial/weak-signal transfer/direction not certified',overall_complete=False)
    (OUT/f'{phase}_summary.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)
