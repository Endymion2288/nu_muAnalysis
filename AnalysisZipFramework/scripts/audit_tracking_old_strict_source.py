#!/usr/bin/env python3
"""Record source differences and reuse measured stage205 kinematic efficiency bins."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
from collections import defaultdict


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--calypso',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    repo=Path(__file__).resolve().parents[2]
    def git(*command):return subprocess.check_output(['git','-C',str(args.calypso),*command])
    old,new='d32b0ff3','88c457c1'
    files=['Waveform/WaveRecTools/src/WaveformReconstructionTool.cxx','Waveform/WaveRecTools/src/WaveformReconstructionTool.h',
           'Waveform/WaveRecAlgs/python/WaveRecAlgsConfig.py','Waveform/WaveRecTools/src/WaveformCleanupTool.cxx','Waveform/WaveRecTools/src/WaveformCleanupTool.h']
    rows=[]
    for name in files:
        a,b=git('show',old+':'+name),git('show',new+':'+name)
        exact=(args.calypso/name).read_bytes()==b
        assert exact,name
        rows.append(dict(path=name,old_bytes=len(a),new_bytes=len(b),old_new_equal=a==b,current_exact_new_commit=exact))
    name='PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.cxx'
    a=git('show',old+':'+name).decode();b=(args.calypso/name).read_text()
    def reduced(s):return s[s.index('  // Calculation of the reduced VetoNu charge'):s.index('  // loop over all reconstructed tracks and use only the tracks that have hits in all three tracking stations')]
    assert reduced(a)==reduced(b)
    (args.output/'waveform_config_cleanup.diff').write_bytes(git('diff',old,new,'--',*files[2:]))
    (args.output/'upstream_changed_files.tsv').write_bytes(b'status\tpath\n'+git('diff','--name-status',old,new,'--','Waveform','Scintillator','Tracking'))
    audit=dict(old_commit=old,new_commit=new,strict_production='stage205 frozen runtime + validated row-major material; no waveform changes in this stage',waveform_files=rows,
        reduced_charge_algorithm_exact_old_to_current=True,
        reduced_charge_input_dependency='veto fitted time; preshower fitted time if veto unavailable; raw charge if both NaN; VetoNu waveform values and time window',
        fit_charge_units='integral (mV ns) / 50 ohm = pC',track_sign_cut_active=False,analysis_cut_thresholds_changed=False,
        source_evidence_reused=['workbook/stage204_causal/waveform_source.diff','workbook/stage204_causal/rotation_source.diff','workbook/stage201_tracking/calypso_local_changes.patch'],
        production_cache_evidence='workbook/stage205_material/full/summary.json')
    (args.output/'source_inventory.json').write_text(json.dumps(audit,indent=2)+'\n')
    cache=defaultdict(dict)
    with (repo/'workbook/stage205_material/full/binned_efficiency.tsv').open() as f:
        for r in csv.DictReader(f,delimiter='\t'):
            if r['version'] in ['old','strict'] and r['stage'] in ['primary_long','primary_raw','final'] and r['variable'] in ['primary_station1_pz_gev','vertex_radius_mm']:
                key=tuple(r[k] for k in ['mode','stage','variable','low','high']);cache[key][r['version']]=r
    rows=[]
    for key,d in cache.items():
        assert set(d)=={'old','strict'}
        a,b=d['old'],d['strict'];assert a['denominator']==b['denominator']
        rows.append(dict(zip(['mode','stage','variable','low','high'],key),denominator=a['denominator'],old_pass=a['passed'],strict_pass=b['passed'],
            old_efficiency_percent=a['efficiency_percent'],strict_efficiency_percent=b['efficiency_percent'],delta_pp=float(b['efficiency_percent'])-float(a['efficiency_percent'])))
    with (args.output/'efficiency_by_truth_kinematics.tsv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t');w.writeheader();w.writerows(rows)
    print(args.output/'source_inventory.json')


if __name__=='__main__':main()
