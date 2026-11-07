"""Condor-only physical pilot aggregation; no energy risk or model fit."""
import csv
import json
import math
from pathlib import Path

OUT=Path('workbook/stage135_energy_ml')

def table(name,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w') as stream:
        writer=csv.DictWriter(stream,keys,delimiter='\t',lineterminator='\n',restval='NA')
        writer.writeheader();writer.writerows(rows)

def main():
    protocol=json.loads((OUT/'pilot_protocol.json').read_text())
    indices=[protocol['preflight_index'],*protocol['remaining_indices']]
    parents=[];components=[];max_KE_error=max_total_error=0
    for i in indices:
        r=json.loads((OUT/f'parent_{i}_report.json').read_text())
        assert r['successful'] and r['legacy_fields_exact'] and r['bin_KE_and_total_closure']
        d=r['lineage'];bins=d['boundary_bins'];case=r['case']
        check=json.loads((OUT/f'parent_{i}_hitscheck.json').read_text())
        assert check['passed'] and len(check['rows'])==6
        assert d['nonbox_envelope']==0 and d['geometry_sensor_boxes']==8
        valid=any(n in ['EmulsionStationA','Emulsion::EmulsionStationA'] for n in d['envelopes']) and d['outside_primaries']==0 and d['unknown_tracks']==0 and d['flow_KE_MeV'][3]==0
        total=d['flow_KE_MeV'][1]
        KE_error=abs(math.fsum(b[5] for b in bins)-total)
        total_error=abs(math.fsum(b[6] for b in bins)-d['flow_total_MeV'][1])
        max_KE_error=max(max_KE_error,KE_error);max_total_error=max(max_total_error,total_error)
        def energy(predicate):
            return math.fsum(b[5] for b in bins if predicate(b))/1000
        parents.append(dict(index=i,stratum=case['stratum'],component=case['component'],
            original_selected_N=r['original_selected_N'],boundary_valid=valid,
            outside_primary_tracks=d['outside_primaries'],total_nonmu_KE_GeV=total/1000,
            downstream_face_KE_GeV=energy(lambda b:b[0]==0),
            upstream_face_KE_GeV=energy(lambda b:b[0]==1),
            side_face_KE_GeV=energy(lambda b:b[0]==2),
            Ecal_ray_KE_GeV=energy(lambda b:b[2]&2),
            Veto_ray_KE_GeV=energy(lambda b:b[2]&1),
            neutral_hadron_KE_GeV=energy(lambda b:b[1]==2),
            EM_KE_GeV=energy(lambda b:b[1]==0),
            charged_hadron_KE_GeV=energy(lambda b:b[1]==1),
            t0_ns=d['event_t0_ns'],nonmu_exit_tracks=sum(int(b[4]) for b in bins),
            nonzero_bins=len(bins),wall_s=r['wall_s'],
            persistent_HITS_read_B=check['read_bytes']))
        for b in bins:
            assert 0<=b[0]<3 and 0<=b[1]<5 and 0<=b[2]<4 and 0<=b[3]<6
            assert b[4]>0 and b[5]>=0 and b[6]>=b[5]
            components.append(dict(index=i,stratum=case['stratum'],face=b[0],
                particle_class=b[1],ray_acceptance=b[2],time_bin=b[3],
                tracks=int(b[4]),KE_GeV=b[5]/1000,totalE_GeV=b[6]/1000,
                KEweighted_x_mm=b[7]/b[5] if b[5] else 'NA',
                KEweighted_y_mm=b[8]/b[5] if b[5] else 'NA',
                KEweighted_z_mm=b[9]/b[5] if b[5] else 'NA',
                KEweighted_t_ns=b[13]/b[5] if b[5] else 'NA'))
    table('pilot_parents.tsv',parents)
    if components:table('pilot_components.tsv',components)
    result=dict(parents=len(parents),successful=len(parents),
        original_selected=sum(r['original_selected_N'] for r in parents),
        boundary_valid=sum(r['boundary_valid'] for r in parents),
        nonzero_nonmu_KE_parents=sum(r['total_nonmu_KE_GeV']>0 for r in parents),
        nonzero_forward_Ecal_ray_parents=sum(r['Ecal_ray_KE_GeV']>0 for r in parents),
        bin_KE_max_closure_error_MeV=max_KE_error,
        bin_totalE_max_closure_error_MeV=max_total_error,
        persistent_HITS_pairs=6*len(parents),all_legacy_fields_exact=True,
        preflight_on_off_exact=json.loads((OUT/'parent_50_noninterference.json').read_text())['observer_on_off_sensitive_hits_exact'],
        main_pilot_HITS_read_B=sum(r['persistent_HITS_read_B'] for r in parents),
        new_neutrinos=0,energy_fits=0,energy_forward=0,
        scope='two train parents per six fixed strata,unweighted physical pilot summaries; not representative mix,acceptance or cal/test energy risk; original selection inherited,no new digitization/reconstruction',
        DAQ_aligned_response=False,geometrical_ray_is_detector_efficiency=False)
    (OUT/'pilot_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result,flush=True)

if __name__=='__main__':
    main()
