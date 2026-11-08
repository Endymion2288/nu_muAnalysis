"""Measured channel/IOV coverage and explicit unknowns, without calibration claims."""
from collections import Counter
from stage173_common import *


def interpret():
    p=plan();records=json.loads((OUT/'condition_records.json').read_text());pilot=json.loads((OUT/'pilot_summary.json').read_text())
    data=[r for r in records if r['instance']=='CONDBR3']
    mapping=next(r for r in data if 'CableMapping' in r['folder'])['rows']
    hv=next(r for r in data if r['folder'].endswith('/HV'))
    lo,hi=p['data_time_interval_inclusive_s'];lo*=10**9;hi=(hi+1)*10**9
    coverage=[]
    for ch in p['requested_channels']:
        intervals=sorted((max(lo,r['since']),min(hi,r['until']),r['payload']) for r in hv['rows'] if r['channel']==ch and r['until']>lo and r['since']<hi)
        cursor=lo;gaps=[]
        for a,b,_ in intervals:
            if a>cursor:gaps.append([cursor,a])
            cursor=max(cursor,b)
        if cursor<hi:gaps.append([cursor,hi])
        coverage.append(dict(channel=ch,record_N=len(intervals),payloads=[v for a,b,v in intervals],
            gap_seconds=sum((b-a)/1e9 for a,b in gaps),complete_interval=not gaps))
    rows=[]
    for r in mapping:
        ch=r['channel'];kind=r['payload']['type'];h=next((x for x in coverage if x['channel']==ch),None)
        supported={}
        for condition in data:
            if condition['folder'].endswith('/HV') or 'CableMapping' in condition['folder']:continue
            selected=[v for v in condition['rows'] if v['channel']==ch]
            supported[condition['folder']]=selected
        rows.append(dict(hardware_channel=ch,cable_payload=r['payload'],HV_coverage=h,condition_records_at_same_channel=supported,
            condition_scope='Channel IDs are exact folder keys; global/board keys remain in source records, not guessed as per-PMT calibrations.',
            physics_calibration_certified=False))
    mc={}
    for run in p['MC_runs']:
        selected=next(r for r in records if r['instance']=='OFLP200' and r['run']==run and 'CableMapping' in r['folder'])
        mc[str(run)]={str(r['channel']):r['payload'] for r in selected['rows']}
    result=dict(passed=True,data_cable_type_counts=dict(Counter(r['payload']['type'] for r in mapping)),channels=rows,
        HV_coverage=coverage,MC_cable_maps=mc,
        CaloNu_run_in_dedicated_GRL=next(r['run_present'] for r in pilot['grls'] if r['path'].endswith('physics_calonu.json')),
        normal_CaloNu_calibration_certified=False,
        source_type_scope='Current explicit COOL replica records for exact run/time; not original producer snapshot, physical-ID validation, historical calibration or DAQ-config recovery.',
        missing=['Original exact DAQ configuration/HV optimization history beyond recorded IOVs',
            'Independent muon timewalk/position and high-amplitude signal-gain validation','Matched target MC/data response covariance and geometry',
            'File-subset live luminosity/efficiency/background and generator-weighted accounting'],
        next='Stop regime lookups here. Next finite task: Timing same-slab calibration/support, alongside S0 source/persistent-support inventory.',overall_complete=False)
    write('regime_evidence.json',result)


if __name__=='__main__':interpret()
