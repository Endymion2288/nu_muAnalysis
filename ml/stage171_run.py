"""HTCondor-only RAW feasibility measurement; bounded prefix, exact legacy ADC replay."""
import argparse
import collections
import gzip
import json
import resource
import subprocess
import time
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage171_energy_ml'
CACHE=ROOT/'ntuples/energy_ml_stage171'


def write(name,obj):
    (OUT/name).write_text(json.dumps(obj,indent=2)+'\n')


def legacy(rows, protocol):
    with np.load(ROOT/protocol['reference']) as z:
        names=['run','eventID','counter','timestamp_us','status','trigger_bits','raw_entry','bytes_through',
               'board_valid','board_time_tag','adc','file_index']
        loaded={name:z[name] for name in names}
    mask=loaded['file_index']==protocol['reference_file_index'];assert int(mask.sum())==56
    reference={name:data[mask] for name,data in loaded.items()}
    for name in names[:8]:
        np.testing.assert_array_equal([r[name] for r in rows[:56]],reference[name])
    for i,r in enumerate(rows[:56]):
        boards={b['board']:b for b in r['boards']};assert len(boards)==len(r['boards'])==2
        np.testing.assert_array_equal([boards[j]['valid'] and not boards[j]['board_fail'] for j in [0,1]],reference['board_valid'][i])
        np.testing.assert_array_equal([boards[j]['tag'] for j in [0,1]],reference['board_time_tag'][i])
        chan={c['channel']:c['adc'] for c in boards[1]['channels']}
        np.testing.assert_array_equal([chan[j] for j in [4,5,6,7]],reference['adc'][i])
    return dict(passed=True,N=56,ADC_samples=56*4*280,max_ADC_difference=0,unit='ADC code',all_original_identity_and_board_fields_exact=True)


def describe(rows):
    valid=[];strict=[];invalid=0
    trigger_counts=collections.Counter();status=collections.Counter()
    for r in rows:
        status[str(r['status'])]+=1
        if len(r['tlb'])==1 and r['tlb'][0].get('valid'):
            t=r['tlb'][0];valid.append(r)
            trigger_counts[f"{t['TAP']}/{t['TBP']}"]+=1
            if t['TAP']==16 and t['TBP']==16:strict.append(r)
        else:invalid+=1
        assert bool(r['strict'])==(r in strict[-1:] if strict else False)
    return valid,strict,dict(trigger_counts),dict(status),invalid


def support(rows,protocol):
    grl=json.loads((ROOT/protocol['GRL']).read_text())
    kept=[r for r in rows if r['strict'] and r['retained']][:8]
    table=[]
    for r in kept:
        t=r['timestamp_us']//1000000
        accepted=any(a<=t<=b for a,b in grl['stable_inclusive_unix_seconds']) and not any(a<=t<=b for a,b in grl['excluded_inclusive_unix_seconds'])
        boards=r['boards']; channels=[];lengths=[]
        ok=len(boards)==2 and {b['board'] for b in boards}=={0,1}
        for b in boards:
            ok=ok and bool(b.get('decoded') and b.get('valid') and not b.get('board_fail'))
            for c in b.get('channels',[]):
                channels.append(16*b['board']+c['channel']);lengths.append(len(c['adc']))
        ok=ok and len(channels)>0 and len(set(channels))==len(channels) and len(set(lengths))==1 and min(lengths)>0
        table.append(dict(eventID=r['eventID'],raw_entry=r['raw_entry'],timestamp_us=r['timestamp_us'],
            status=r['status'],GRL=accepted,board_channel_supported=bool(ok),hardware_channels=sorted(channels),
            sample_lengths=sorted(set(lengths)),input_bits=r['tlb'][0]['input_bits'],input_bits_next=r['tlb'][0]['input_bits_next']))
    same=bool(table) and all(r['hardware_channels']==table[0]['hardware_channels'] and r['sample_lengths']==table[0]['sample_lengths'] for r in table)
    admitted=len(kept)>=4 and same and all(r['GRL'] and r['board_channel_supported'] for r in table)
    return dict(retained_strict_N=len(kept),controls=table,consistent_channels_and_lengths=same,feasible=admitted,
                pure_noise_certified=False,calibrated_joint_covariance=False)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['smoke','smoke_retry','pilot','audit']);args=parser.parse_args()
    phase=args.phase;protocol=json.loads((OUT/'protocol.json').read_text());limit=56 if phase in ['smoke','smoke_retry'] else 8192
    assert CACHE != (ROOT/protocol['stage170_reference']).parent
    tick=time.perf_counter();cpu=time.process_time();CACHE.mkdir(exist_ok=True,parents=True)
    path=CACHE/f'{phase}_rows.jsonl.gz';rows=[]
    with (OUT/f'{phase}_reader.log').open('w') as log:
        start=time.perf_counter();child_before=resource.getrusage(resource.RUSAGE_CHILDREN)
        proc=subprocess.Popen([str(ROOT/'reader'),protocol['input_RAW'],str(limit)],text=True,stdout=subprocess.PIPE,stderr=log)
        with gzip.open(path,'wt',compresslevel=1) as out:
            for line in proc.stdout:
                row=json.loads(line);rows.append(row);out.write(line)
        exitcode=proc.wait();reader_wall=time.perf_counter()-start;child=resource.getrusage(resource.RUSAGE_CHILDREN)
    assert exitcode==0,(phase,exitcode)
    assert len(rows)==limit
    reference_start=time.process_time()
    ref=legacy(rows,protocol)
    reference_CPU=time.process_time()-reference_start
    with gzip.open(ROOT/protocol['stage170_reference'],'rt') as f:
        original=[json.loads(line) for line in f]
    assert rows[:56]==original

    valid,strict,triggers,status,invalid=describe(rows)
    supported=support(rows,protocol)
    prefix=True
    if phase=='pilot':
        with gzip.open(CACHE/'smoke_retry_rows.jsonl.gz','rt') as f:old=[json.loads(line) for line in f]
        assert rows[:56]==old
    independent=None
    if phase=='audit':
        with gzip.open(CACHE/'pilot_rows.jsonl.gz','rt') as f:old=[json.loads(line) for line in f]
        assert len(old)==len(rows)
        assert all(a==b for a,b in zip(rows,old))
        # Independent scalar trigger selection, without describe/support or reader strict flags.
        selected=[]
        for i,r in enumerate(rows):
            ts=r['tlb']
            if len(ts)!=1:continue
            t=ts[0]
            if t.get('supported')==1 and t.get('framed')==1 and t.get('valid')==1 and t.get('TAP')==16 and t.get('TBP')==16:
                selected.append(i)
        assert selected==[i for i,r in enumerate(rows) if r['strict']]
        independent=dict(passed=True,rows_exact=limit,retained_ADC_exact_N=sum(r['retained'] for r in rows),
            independent_strict_N=len(selected),original56_ADC_exact=True,
            independent_implementation='scalar TLB selection plus second official RAW read, shared official decoder',
            not_an_independent_hardware_decoder=True)
        write('independent_validation.json',independent)
        from stage171_evidence import main as evidence
        evidence()
        rejoin={}
        for phase_name in ['smoke','smoke_retry']:
            source=CACHE/f'{phase_name}_rows.jsonl.gz'
            with gzip.open(source,'rt') as f:other=[json.loads(line) for line in f]
            assert other==rows[:56]
            rejoin[source.name]=dict(rows=56,exact_prefix=True)
        rejoin['audit_rows.jsonl.gz']=dict(rows=len(rows),exact_full=True)
        write('storage_rejoin.json',dict(passed=True,canonical='pilot_rows.jsonl.gz',rejoin=rejoin,
            all_hardware_ADC_and_metadata_equal=True))
    meta=dict(phase=phase,passed=True,physics_N=len(rows),raw_frames_through=rows[-1]['raw_entry']+1,
        bytes_through=rows[-1]['bytes_through'],valid_single_TLB_N=len(valid),missing_bad_or_ambiguous_TLB_N=invalid,
        strict_N=len(strict),retained_N=sum(r['retained'] for r in rows),
        timestamp_min_us=min(r['timestamp_us'] for r in rows),timestamp_max_us=max(r['timestamp_us'] for r in rows),
        trigger_TAP_TBP_counts=triggers,event_status_counts=status,reference=ref,controls=supported,
        prefix_exact=prefix,reader=dict(CPU_s=child.ru_utime+child.ru_stime-child_before.ru_utime-child_before.ru_stime,
            wall_s=reader_wall,RSS_KiB=child.ru_maxrss),
        reference_CPU_s=reference_CPU,stage170_all56_ADC_and_metadata_exact=True,
        python_CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        new_G4=0,energy_fits=0,model_forward=0,overall_complete=False,promotion=False)
    write(f'{phase}_summary.json',meta)
    print(json.dumps(meta,indent=2),flush=True)


if __name__=='__main__':main()
