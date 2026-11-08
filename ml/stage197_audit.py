"""Actual full reread and independent scalar selection/cells; batch only."""
import collections
import csv
import json
import math
import multiprocessing as mp
import resource
import time

import numpy as np
from stage197_common import ROOT,OUT,CACHE,P,CUTS,write,read_gz
from stage197_measure import read_file,aux_read
from stage197_scalar import aux_state


def independent_cell(values):
    edges=[P['pz_edges_GeV'],P['raw_Veto10_edges_pC'],P['nClusters0_edges']]
    return tuple(-1 if v is None or not math.isfinite(float(v)) else sum(float(v)>=edge for edge in e) for v,e in zip(values,edges))


def audit_pilot():
    resource.setrlimit(resource.RLIMIT_CPU,(3000,3000));tick,cpu=time.perf_counter(),time.process_time()
    s=json.loads((OUT/'pilot_summary.json').read_text());old=read_gz(CACHE/'pilot_selected.json.gz')
    reread=read_file((0,8192,True));original=s['files'][0]
    for key in ['source_N','processed_N','cutflow','prefix64','schema']:
        assert original[key]==reread[key],key
    assert reread['scalar_prefix_counts']==[original['cutflow'][name] for name in CUTS]
    actual=reread['records'];saved=[{k:v for k,v in row.items() if k!='selection_unknown_reason'} for row in old['unknown']]
    assert actual==saved and old['selected']==[]
    assert all(aux_state(row,{})=='aux_missing' for row in actual)
    assert len(actual)==s['pre_veto_N']==2647
    assert sum(row['pz0_GeV']<100 for row in actual)==s['pre_veto_pz_counts']['50_100']==351
    assert not original['schema']['native_reduced']
    inv=json.loads((OUT/'aux_inventory.json').read_text())
    assert inv['listing_exit']==54 and 'Operation not permitted' in inv['listing_error'] and not inv['supported']
    write('independent_validation.json',dict(passed=True,scope='Pilot only; full denied by measured cost and actual auxiliary access unsupported',
        actual_PHYS_reread_files_N=1,actual_processed_records_N=8192,scalar_prefix8192_cumulative_counts_exact=True,
        scalar_selected_primitives_checks_N=reread['scalar_checked_N'],pre_veto_identity_raw_status_exact_N=len(actual),
        pre_veto_pz50_100_N=351,unknown_final_selection_N=len(actual),aux_access_failure_observed=True,aux_reread_or_alternative_search=False,
        final_candidate_yield_measured=False,MC_read_N=0,physical_spectrum_or_purity_certified=False,
        CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,overall_complete=False))
    print('Independent actual8192 pilot scalar cutflow and unknown-selection audit passed',flush=True)


def main():
    resource.setrlimit(resource.RLIMIT_CPU,(3000,3000));tick,cpu=time.perf_counter(),time.process_time()
    full=json.loads((OUT/'full_summary.json').read_text());saved=read_gz(CACHE/'full_selected.json.gz')
    inventory=json.loads((OUT/'aux_inventory.json').read_text())
    with mp.get_context('spawn').Pool(4) as pool:results=pool.map(read_file,[(i,None,True) for i in range(16)])
    expected=[r for f in results for r in f['records']]
    targets={(r['run'],r['eventID']) for r in expected}
    aux,aux_cost=aux_read(inventory,targets,pilot=False)
    for original,actual in zip(full['files'],results):
        for key in ['source_N','processed_N','cutflow','prefix64','schema']:
            assert original[key]==actual[key],(original['file'],key)
    counts={name:sum(r['cutflow'][name] for r in results) for name in CUTS}
    assert counts==full['cutflow']
    scalar_prefix=results[0]['scalar_prefix_counts']
    pilot=json.loads((OUT/'pilot_summary.json').read_text())
    assert scalar_prefix==[pilot['files'][0]['cutflow'][name] for name in CUTS]
    selected=[];unknown=[];states=collections.Counter()
    for row in expected:
        state=aux_state(row,aux);states[state]+=1
        if state=='selected':selected.append(row)
        elif state!='vetoed':unknown.append(row)
    assert dict(states)==full['final_states']
    without=lambda rows:[{k:v for k,v in r.items() if k not in ['selected_reduced_pC','selection_unknown_reason']} for r in rows]
    assert selected==without(saved['selected']) and unknown==without(saved['unknown'])
    observed=collections.Counter(independent_cell([r['pz0_GeV'],r['raw_charge_pC'][2],r['nClusters0']]) for r in selected)
    with (OUT/'full_observed_cells.tsv').open() as f:
        actual=collections.Counter({tuple(int(r[k]) for k in ['pz_bin','Veto10_bin','nClusters0_bin']):int(r['N']) for r in csv.DictReader(f,delimiter='\t')})
    assert observed==actual
    with (OUT/'MC_calibration_cells.tsv').open() as f:
        cells={(r['component'],*map(int,[r[k] for k in ['pz_bin','Veto10_bin','nClusters0_bin']])):int(r['N']) for r in csv.DictReader(f,delimiter='\t')}
    names=json.loads((ROOT/'ml/configs/audited_features.json').read_text())['features']
    columns=[names.index(k) for k in ['ML_mu_pz0_GeV','Veto10_raw_charge','nClusters0']]
    with np.load(ROOT/'ntuples/energy_ml_stage119/old_input.npz') as source:
        roles=source['role'];x=source['x'];components=source['component']
    reference=collections.Counter();mc_N=0
    for i in range(len(roles)):
        if int(roles[i])!=2:continue
        reference[(str(components[i]),)+independent_cell([x[i,j] for j in columns])]+=1;mc_N+=1
    assert dict(reference)==cells and mc_N==11612
    stored_aux={(r['run'],r['eventID']):r['values'] for r in read_gz(CACHE/'aux_selected.json.gz')}
    assert stored_aux=={k:v for k,v in aux.items() if k in {(r['run'],r['eventID']) for r in selected+unknown}}
    write('independent_validation.json',dict(passed=True,actual_PHYS_reread_files_N=16,actual_processed_records_N=sum(r['processed_N'] for r in results),
        full_cutflow_second_read_exact=True,scalar_prefix8192_cumulative_counts_exact=True,
        scalar_selected_primitives_checks_N=sum(r['scalar_checked_N'] for r in results),final_identity_raw_status_exact_N=len(selected),
        unknown_identity_exact_N=len(unknown),final_decisions_independent_scalar=True,actual_aux_reread=aux_cost,
        observed_cell_counts_independent=True,MC_role2_scalar_records_N=mc_N,MC_component_cells_independent=True,
        source_label_or_error_coverage_certified=False,matched_exposure_certified=False,
        CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,child_CPU_s=sum(r['CPU_s'] for r in results),overall_complete=False))
    print('Actual-input and independent scalar Stage197 audit passed',flush=True)


if __name__=='__main__':
    if (OUT/'full_summary.json').exists():main()
    else:audit_pilot()
