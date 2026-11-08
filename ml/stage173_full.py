"""One actual regime decision using bounded explicit COOL folders and IOVs."""
import resource,time
from stage173_common import *
if __name__=='__main__':
    tick=time.perf_counter();cpu=time.process_time();p=plan();pilot=json.loads((OUT/'pilot_summary.json').read_text());records=[]
    for folder in p['folders']:
        if folder.endswith('/HV'):
            records.append(read_conditions(folder,'CONDBR3',interval=p['data_time_interval_inclusive_s']))
        else:records.append(read_conditions(folder,'CONDBR3',run=15838))
    for run in p['MC_runs']:
        for folder in p['folders']:
            if not folder.endswith('/HV'):records.append(read_conditions(folder,'OFLP200',run=run,tag=p['MC_tag']))
    write('condition_records.json',records)
    cable=next(r for r in records if r['instance']=='CONDBR3' and 'CableMapping' in r['folder'])
    mapping={str(r['channel']):r['payload'] for r in cable['rows']}
    grls=pilot['grls'];calonu=next(r for r in grls if r['path'].endswith('physics_calonu.json'))
    summary=dict(passed=True,run=15838,inclusive_GRL=grls[0],CaloNu_GRL=calonu,channel_mapping=mapping,
        supported_condition_queries=sum(r['supported'] for r in records),condition_queries=len(records),
        missing_or_truncated=[dict(folder=r['folder'],instance=r['instance'],run=r['run'],error=r.get('error'),truncated=r.get('truncated',False)) for r in records if not r['supported'] or r.get('truncated')],
        applicability=[
            dict(subsystem='CaloNu',verdict='Original-condition engineering control; normal-physics calibration not certified',
                 basis='Dedicated GRL membership and official run-specific bad-voltage note; numeric HV is not signal calibration.'),
            dict(subsystem='ordinary Ecal',verdict='Readout mapping/condition metadata measured; response transfer unknown',
                 basis='Data dual-range support is checked by actual cable payload. Original four-readout MC does not gain a second range.'),
            dict(subsystem='Veto/VetoNu/Timing/Preshower',verdict='Original-condition control; independent timing/gain calibration still required',
                 basis='CaloNu exclusion does not exclude these systems. Actual payload and IOV do not establish calibrated response.'),
            dict(subsystem='hardware31',verdict='Use actual cable type only; physical-response interpretation conditional',basis=mapping.get('31'))],
        DAQ_config_exact_snapshot_acquired=False,producer_history_complete=False,signal_gain_calibrated=False,
        luminosity_for_RAW_subset=None,normal_CaloNu_calibration_certified=False,
        next='End one regime audit; proceed to same-slab Timing joint measurement support and S0 radiation instrumentation; do not make 32-file noise study an energy prerequisite.',
        CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        energy_fits=0,new_G4=0,overall_complete=False,promotion=False)
    write('full_summary.json',summary);print(summary)
