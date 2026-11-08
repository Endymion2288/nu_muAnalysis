"""Read actual detector-level candidates on Condor; no energy inference."""
import collections
import concurrent.futures
import json
import multiprocessing as mp
import resource
import subprocess
import sys
import time

import awkward as ak
import numpy as np
import uproot
from stage197_common import ROOT,OUT,CACHE,P,SCINT,CUTS,schema,leading,cut_masks,records,write,table,save_gz,read_gz,final_selection,cell,finite


def read_file(task):
    index, limit, *options = task
    audit = bool(options and options[0])
    scalar_checked = 0; scalar_prefix_counts = np.zeros(len(CUTS),dtype="int64")
    started, cpu = time.perf_counter(), time.process_time()
    found = []; counts = np.zeros(len(CUTS),dtype='int64'); blocks = []; prefix = []
    with concurrent.futures.ThreadPoolExecutor(1) as workers:
        with uproot.open(P['PHYS'][index], array_cache=None, decompression_executor=workers, interpretation_executor=workers) as source:
            tree = source['nt']; description, mapping = schema(tree)
            if not description['supported']:
                return dict(file=index, schema=description, source_N=tree.num_entries, supported=False, records=[],CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-started)
            n = tree.num_entries if limit is None else min(tree.num_entries,limit)
            step = 4096 if limit is not None else 65536
            for start in range(0,n,step):
                block_cpu = time.process_time(); stop = min(n,start+step)
                original = tree.arrays(list(mapping.values()),entry_start=start,entry_stop=stop,library='ak',how=dict)
                arrays = {name:original[actual] for name,actual in mapping.items()}
                assert ak.all(arrays['run'] == 15838)
                lead = leading(arrays); accepted, current = cut_masks(arrays,lead)
                counts += current
                if audit:
                    from stage197_scalar import scalar_cuts
                    validate = range(len(accepted)) if index == 0 and start < 8192 else np.flatnonzero(accepted)
                    if index == 0 and start < 8192:
                        validate = range(min(len(accepted),8192-start))
                    for i in validate:
                        tests=scalar_cuts(arrays,int(i));cumulative=True
                        for j,test in enumerate(tests):
                            cumulative=cumulative and test
                            if index == 0 and start < 8192:scalar_prefix_counts[j]+=int(cumulative)
                        assert cumulative==bool(accepted[i]),(index,start+i,'scalar selection mismatch')
                        scalar_checked+=1
                found.extend(records(arrays,lead,np.flatnonzero(accepted),index,start))
                if index == 0 and start == 0:
                    prefix = [{k:int(arrays[k][i]) for k in ['run','eventID','eventTime']} for i in range(min(64,len(arrays['run'])))]
                blocks.append(dict(start=start,N=stop-start,CPU_s=time.process_time()-block_cpu))
            requested = int(source.file.source.num_requested_bytes)
    return dict(file=index,supported=True,schema=description,source_N=tree.num_entries,processed_N=n,cutflow=dict(zip(CUTS,map(int,counts))),
        records=found,prefix64=prefix,block_resources=blocks,read_bytes=requested,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-started,
        RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,scalar_checked_N=scalar_checked,scalar_prefix_counts=scalar_prefix_counts.tolist())


def aux_inventory():
    result = subprocess.run(['xrdfs','root://eosuser.cern.ch','ls',P['aux_directory']],capture_output=True,text=True)
    paths = sorted(line.strip() for line in result.stdout.splitlines() if line.strip().endswith('.root'))
    info = dict(directory=P['aux_directory'],listing_exit=result.returncode,listing_error=result.stderr[-3000:],paths=paths,files=[])
    if result.returncode:
        info['supported'] = False
        return info
    assert len(paths)<=1024
    required = ['run','event','myVetoNu0_rawCharge35','myVetoNu1_rawCharge35']
    for path in paths:
        try:
            with uproot.open('root://eosuser.cern.ch/' + path, array_cache=None) as source:
                if 'tree' not in source:
                    info['files'].append(dict(path=path,supported=False,reason='actual configured tree absent',keys=list(source.keys())));continue
                tree=source['tree'];missing=[k for k in required if k not in tree.keys()]
                info['files'].append(dict(path=path,supported=not missing,N=tree.num_entries,missing=missing))
        except (OSError,KeyError) as error:
            info['files'].append(dict(path=path,supported=False,reason=str(error)[-2000:]))
    info['supported']=bool(paths) and all(f['supported'] for f in info['files'])
    return info


def aux_read(inventory, targets, pilot=False):
    if not inventory['supported']:
        return {}, dict(supported=False,reason='actual aux inventory/schema unavailable',processed_N=0,CPU_s=0.,wall_s=0.)
    cpu,tick=time.process_time(),time.perf_counter();matched={};processed=0;blocks=[];requested=0
    target_keys=np.array(sorted((int(run)<<32)|int(event) for run,event in targets),dtype='uint64')
    required=['run','event','myVetoNu0_rawCharge35','myVetoNu1_rawCharge35']
    files=inventory['files'][:2] if pilot else inventory['files']
    for f in files:
        with uproot.open('root://eosuser.cern.ch/' + f['path'],array_cache=None) as source:
            tree=source['tree'];n=min(8192,tree.num_entries) if pilot else tree.num_entries
            for start in range(0,n,4096 if pilot else 131072):
                step_cpu=time.process_time();stop=min(n,start+(4096 if pilot else 131072))
                a=tree.arrays(required,entry_start=start,entry_stop=stop,library='np')
                keys=(a['run'].astype('uint64')<<32)|a['event'].astype('uint64')
                keep=np.isin(keys,target_keys,assume_unique=False)
                for i in np.flatnonzero(keep):
                    key=(int(a['run'][i]),int(a['event'][i]))
                    value=[finite(a[f'myVetoNu{k}_rawCharge35'][i]) for k in range(2)]
                    if key in matched:matched[key]=None
                    else:matched[key]=value
                processed+=stop-start;blocks.append(dict(N=stop-start,CPU_s=time.process_time()-step_cpu))
            requested+=int(source.file.source.num_requested_bytes)
    return matched,dict(supported=True,processed_N=processed,total_available_N=sum(f['N'] for f in inventory['files']),
        selected_identity_N=len(matched),ambiguous_identity_N=sum(v is None for v in matched.values()),block_resources=blocks,read_bytes=requested,
        CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick)


def finish(results,aux,phase):
    raw=[r for f in results for r in f['records']];flags=collections.Counter();selected=[];unknown=[];pre=collections.Counter()
    for row in raw:
        state,reduced=final_selection(row,aux);flags[state]+=1;pre['50_100' if row['pz0_GeV']<100 else 'ge100']+=1
        if state=='selected':selected.append(dict(**row,selected_reduced_pC=reduced))
        elif state not in ['vetoed']:unknown.append(dict(**row,selection_unknown_reason=state))
    hist=collections.Counter(cell(r) for r in selected)
    table(f'{phase}_observed_cells.tsv',[dict(pz_bin=k[0],Veto10_bin=k[1],nClusters0_bin=k[2],N=n) for k,n in sorted(hist.items())])
    save_gz(CACHE/f'{phase}_selected.json.gz',dict(selected=selected,unknown=unknown))
    assert (CACHE/f'{phase}_selected.json.gz').stat().st_size <= P['resources']['final_cache_cap_B']
    for result in results:result.pop('records')
    counts={name:sum(r.get('cutflow',{}).get(name,0) for r in results) for name in CUTS}
    duplicates=collections.Counter((r['run'],r['eventID']) for r in selected)
    summary=dict(selected_duplicate_identity_records_N=sum(n-1 for n in duplicates.values()),passed=all(f['supported'] for f in results),phase=phase,files=results,pre_veto_N=len(raw),pre_veto_pz_counts=dict(pre),
        cutflow=counts,final_states=dict(flags),observed_selected_N=len(selected),observed_selected_pz50_100_N=sum(r['pz0_GeV']<100 for r in selected),
        unresolved_final_selection_N=len(unknown),background_subtracted=False,neutrino_purity_certified=False,
        matched_exposure_certified=False,energy_fits=0,model_forward=0,overall_complete=False,promotion=False)
    return summary


def MC_support():
    cfg=json.loads((ROOT/'ml/configs/audited_features.json').read_text());names=cfg['features']
    with np.load(ROOT/'ntuples/energy_ml_stage119/old_input.npz') as source:
        role=source['role'];take=role==2
        assert int(take.sum())==11612
        x=source['x'][take];components=source['component'][take]
    columns=[names.index(n) for n in ['ML_mu_pz0_GeV','Veto10_raw_charge','nClusters0']]
    groups=collections.Counter()
    for values,component in zip(x[:,columns],components):
        row=dict(pz0_GeV=float(values[0]),raw_charge_pC=[None,None,finite(values[1])],nClusters0=finite(values[2]))
        groups[(str(component),)+cell(row)]+=1
    table('MC_calibration_cells.tsv',[dict(component=k[0],pz_bin=k[1],Veto10_bin=k[2],nClusters0_bin=k[3],N=n) for k,n in sorted(groups.items())])
    return dict(role=2,N=int(take.sum()),component_N={str(c):int((components==c).sum()) for c in np.unique(components)},
        quarantine_or_reserved_N=0,weighted_physical_prediction=False,truth_fields_used=False)


def main(phase):
    limit=P['resources']['phase_CPU_s'][phase]
    resource.setrlimit(resource.RLIMIT_CPU,(int(limit*.85),int(limit*.85)))
    CACHE.mkdir(exist_ok=True);tick,cpu=time.perf_counter(),time.process_time()
    if phase=='pilot':
        inventory=aux_inventory();write('aux_inventory.json',inventory)
        results=[read_file((0,8192))]
    else:
        assert json.loads((OUT/'admission.json').read_text())['admitted']
        inventory=json.loads((OUT/'aux_inventory.json').read_text())
        with mp.get_context('spawn').Pool(4) as pool:results=pool.map(read_file,[(i,None) for i in range(16)])
    targets={(r['run'],r['eventID']) for f in results for r in f['records']}
    needs_aux=any(not f.get('schema',{}).get('native_reduced',False) for f in results)
    aux,aux_cost=aux_read(inventory,targets,pilot=phase=='pilot') if needs_aux else ({},dict(supported=True,not_needed_native=True,processed_N=0,CPU_s=0.,wall_s=0.))
    summary=finish(results,aux,phase);summary['aux_resources']=aux_cost
    summary['driver_CPU_s']=time.process_time()-cpu;summary['wall_s']=time.perf_counter()-tick
    if phase=='full':
        pilot=json.loads((OUT/'pilot_summary.json').read_text())
        assert summary['files'][0]['prefix64']==pilot['files'][0]['prefix64']
        summary['MC']=MC_support()
        with (OUT/'MC_calibration_cells.tsv').open() as f:
            import csv
            mc_cells=collections.Counter()
            for r in csv.DictReader(f,delimiter='\t'):
                mc_cells[tuple(int(r[k]) for k in ['pz_bin','Veto10_bin','nClusters0_bin'])]+=int(r['N'])
        observed=read_gz(CACHE/'full_selected.json.gz')['selected'];data_cells=collections.Counter(cell(r) for r in observed)
        table('observed_MC_support.tsv',[dict(pz_bin=k[0],Veto10_bin=k[1],nClusters0_bin=k[2],observed_N=n,MC_calibration_N=mc_cells[k]) for k,n in sorted(data_cells.items())])
        summary['observed_records_in_empty_MC_cells_N']=sum(n for k,n in data_cells.items() if not mc_cells[k])
        summary['empty_cell_interpretation']='Finite selected MC support only; not impossible physical signal, likelihood or model calibration'

        # Only the matched subset required to independently classify final records is retained.
        selected=read_gz(CACHE/'full_selected.json.gz');keys={(r['run'],r['eventID']) for r in selected['selected']+selected['unknown']}
        save_gz(CACHE/'aux_selected.json.gz',[dict(run=k[0],eventID=k[1],values=v) for k,v in sorted(aux.items()) if k in keys])
    write(f'{phase}_summary.json',summary);print({k:v for k,v in summary.items() if k!='files'},flush=True)


if __name__=='__main__':main(sys.argv[1])
