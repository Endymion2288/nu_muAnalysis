"""Join the new geometry decomposition without changing the original denominator."""
import gzip
import json
import tarfile
import numpy as np
from stage137_common import ROOT,OUT,CACHE,inputs,protocol,table

def main():
    p=protocol(); d=inputs(); records={}; summaries=[]; execution=[]
    with gzip.open(ROOT/'ntuples/energy_ml_stage131/parent_evidence.json.gz','rt') as f:
        old={r['index']:r['reports'] for r in json.load(f)}
    with gzip.open(ROOT/'ntuples/energy_ml_stage131/production_cases.json.gz','rt') as f:
        cases=json.load(f)
    for index in p['pilot_reused']:
        base=ROOT/'workbook/stage135_energy_ml'
        records[index]={kind:json.loads((base/f'parent_{index}_{kind}.json').read_text())
                        for kind in ['report','hitscheck']}
    for batch in range(len(p['batches'])):
        with tarfile.open(CACHE/f'production_{batch}_result.tar.gz') as archive:
            def read(name):return json.load(archive.extractfile('workbook/stage137_energy_ml/'+name))
            results=read(f'production_results_{batch}.json')
            assert {r['index'] for r in results}==set(p['batches'][batch])
            assert all(r['successful'] for r in results)
            for index in p['batches'][batch]:
                assert index not in records
                records[index]={kind:read(f'parent_{index}_{kind}.json') for kind in ['report','hitscheck']}
                for step in ['sim','hitscheck']:
                    text=archive.extractfile(f'workbook/stage137_energy_ml/parent_{index}_{step}_time.txt').read().decode()
                    fields=dict(line.strip().rsplit(': ',1) for line in text.splitlines() if ': ' in line)
                    execution.append(dict(index=index,step=step,
                        user_CPU_s=float(fields['User time (seconds)']),
                        system_CPU_s=float(fields['System time (seconds)']),
                        max_RSS_KiB=int(fields['Maximum resident set size (kbytes)']),
                        measured_wall_s=next(r['wall_s'] for r in records[index]['report']['steps'] if r['name']==step)))
    assert set(records)=={c['frame_index'] for c in cases}
    raw={}; maxKE=maxTotal=0.; hits=0; readbytes=0
    for c in cases:
        index=c['frame_index']; r=records[index]; report=r['report']; line=report['lineage']
        assert report['successful'] and report['legacy_fields_exact'] and r['hitscheck']['passed']
        assert report['case']==c and report['original_selected_N']==old[index]['selection']['selected_N']
        for key,value in old[index]['summary']['lineage'].items():assert line[key]==value,(index,key)
        assert line['nonbox_envelope']==0 and line['geometry_sensor_boxes']==8
        values=np.zeros((3,5,4,6),dtype=float)
        total=0.
        for row in line['boundary_bins']:
            face,kind,accept,timebin,count,ke,etot,*_=row
            assert len(row)==14 and count>0 and 0<=ke<=etot
            assert 0<=face<3 and 0<=kind<5 and 0<=accept<4 and 0<=timebin<6
            values[face,kind,accept,timebin]+=ke/1000
            total+=etot
        for actual,expected in [(values.sum()*1000,line['flow_KE_MeV'][1]),(total,line['flow_total_MeV'][1])]:
            assert abs(actual-expected)<=max(1e-7,abs(expected)*1e-10),(index,actual,expected)
        maxKE=max(maxKE,abs(values.sum()*1000-line['flow_KE_MeV'][1]))
        maxTotal=max(maxTotal,abs(total-line['flow_total_MeV'][1]))
        accepted=values[:,:,1:,:].sum();unaccepted=values[:,:,0,:].sum()
        byclass=values[:,:,1:,:].sum(axis=(0,2,3))
        raw[index]=[accepted,unaccepted,accepted-byclass[0],accepted-byclass[1],accepted-byclass[2]]
        # Subtract sums at full precision; only rounding-scale negatives allowed.
        assert min(raw[index])>=-1e-10
        raw[index]=np.maximum(raw[index],0)
        summaries.append(dict(index=index,role=c['role'],sampling_stratum=c['stratum'],component=c['component'],original_selected=report['original_selected_N'],inclusion_probability=c['inclusion_probability'],total_KE_GeV=values.sum(),accepted_KE_GeV=accepted,unaccepted_KE_GeV=unaccepted,downstream_KE_GeV=values[0].sum(),upstream_KE_GeV=values[1].sum(),side_KE_GeV=values[2].sum(),accepted_side_KE_GeV=values[2,:,1:,:].sum(),accepted_EM_KE_GeV=byclass[0],accepted_CH_KE_GeV=byclass[1],accepted_NH_KE_GeV=byclass[2],event_t0_ns=line['event_t0_ns']))
        hits+=len(r['hitscheck']['rows']);readbytes+=r['hitscheck']['read_bytes']
    matrix=np.array([raw[int(i)] for i in d['frame_index']])
    valid=np.isfinite(d['flow'][:,0]);assert valid.sum()==2803
    np.testing.assert_allclose(np.log1p(matrix[:,0]+matrix[:,1])[valid],d['flow'][valid,0],rtol=1e-12,atol=1e-12)
    matrix[~valid]=np.nan
    np.savez_compressed(CACHE/'boundary_components.npz',KE_GeV=matrix,log1p_KE_GeV=np.log1p(matrix),frame_index=d['frame_index'])
    table('parent_geometry.tsv',summaries)
    description=[]
    byindex={r['index']:r for r in summaries}
    from stage131_common import evaluation_masks
    for role in [1,2,3]:
        ix=np.flatnonzero(d['role']==role);sd={k:v[ix] for k,v in d.items()}
        for layer,mask in evaluation_masks(sd).items():
            rows=ix[mask];available=rows[valid[rows]];w=d['weight'][available]
            for name in ['accepted_KE_GeV','unaccepted_KE_GeV','side_KE_GeV','accepted_side_KE_GeV','accepted_EM_KE_GeV','accepted_CH_KE_GeV','accepted_NH_KE_GeV']:
                v=np.array([byindex[int(d['frame_index'][i])][name] for i in available])
                description.append(dict(role=role,stratum=layer,component=name,N=len(rows),available_N=len(available),positive_N=int((v>0).sum()),HT_weighted_mean_GeV=float(np.average(v,weights=w)) if len(v) else None,scope='oldselected/reselected and boundary-available conditional; geometric,not visible'))
    table('geometry_summary.tsv',description)
    table('execution_times.tsv',execution)
    with gzip.open(CACHE/'boundary_evidence.json.gz','wt') as f:json.dump(records,f,separators=(',',':'))
    result=dict(passed=True,parents=len(records),selected_N=len(matrix),available_N=int(valid.sum()),missing_N=int((~valid).sum()),legacy_all_exact=True,HITS_pairs=hits,HITS_read_bytes=readbytes,max_KE_sum_abs_delta_MeV=maxKE,max_totalE_sum_abs_delta_MeV=maxTotal,no_digi_reco=True,new_independent_nu=0,
        new_replays_GNU_CPU_s=sum(r['user_CPU_s']+r['system_CPU_s'] for r in execution),
        max_single_process_RSS_KiB=max(r['max_RSS_KiB'] for r in execution),
        max_parent_wall_s=max(records[i]['report']['wall_s'] for batch in p['batches'] for i in batch))
    (OUT/'boundary_validation.json').write_text(json.dumps(result,indent=2)+'\n');print(result)

if __name__=='__main__':main()
