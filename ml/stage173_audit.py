"""Independent raw GRL membership and actual COOL point re-query, HTCondor only."""
import json,tarfile
from stage173_common import *
if __name__=='__main__':
    p=plan();pilot=json.loads((OUT/'pilot_summary.json').read_text());full=json.loads((OUT/'full_summary.json').read_text())
    checks=[]
    with tarfile.open(CACHE/'official_sources.tar.gz') as t:
        for g in pilot['grls']:
            if 'error' in g:continue
            original=Path(g['path']).read_bytes();assert t.extractfile('grl/'+Path(g['path']).name).read()==original
            records=json.loads(original);run=records.get('15838');assert (run is not None)==g['run_present']
            for value,expected in g['fixed_time_membership'].items():
                seconds=int(value);stable=False;excluded=False
                if run:
                    for r in run.get('stable_list',[]):
                        if int(r['start_utime'])<=seconds<=int(r['stop_utime']):stable=True
                    for r in run.get('excluded_list',[]):
                        if int(r['start_utime'])<=seconds<=int(r['stop_utime']):excluded=True
                assert (stable and not excluded)==expected
            checks.append(dict(path=g['path'],exact_bytes=True,membership_exact=True))
    for original in pilot['conditions']:
        observed=read_conditions(original['folder'],original['instance'],run=original['run'],seconds=original['seconds'])
        assert original==observed
    data_records=json.loads((OUT/'condition_records.json').read_text())
    for r in data_records:
        if r['supported']:
            for value in r['rows']:assert value['since']<=r['key_stop'] and value['until']>r['key_start']
    assert not full['normal_CaloNu_calibration_certified']
    assert full['DAQ_config_exact_snapshot_acquired'] is False
    write('independent_validation.json',dict(passed=True,GRL_checks=checks,actual_condition_point_requeries_exact_N=2,
        IOV_intersection_valid=True,physical_calibration_certified=False,energy_fits=0,overall_complete=False))

    from stage173_interpret import interpret
    interpret()
