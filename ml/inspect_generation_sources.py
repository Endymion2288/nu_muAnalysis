#!/usr/bin/env python3
"""Bounded provenance audit: first simulation log and two EVNT metadata schemas.

Does not read event payloads or infer physical flux weights from event counts.
"""
import argparse
import csv
import json
import re
import time
from pathlib import Path

import uproot


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    start=time.perf_counter()
    rows=[]
    for run in [200082,200083,200089,200093,200094,200100]:
        folder=Path(f'/eos/experiment/fasernu-data0/faser/sim/mc24/genie/{run}/log/s0014')
        path=next(iter(sorted(folder.glob('*-00000-s0014-HITS.sim.log'))))
        text=path.read_text()
        match=re.search(r'^Input File: (.*)$',text,re.M)
        if not match:
            raise RuntimeError(f'No input EVNT in {path}')
        rows.append(dict(run=run,simulation_log=str(path),EVNT=match.group(1)))
    with (args.output_dir/'generation_sources.tsv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n')
        writer.writeheader();writer.writerows(rows)
    report=[]
    for row in [rows[0],rows[3]]:
        with uproot.open(row['EVNT']) as source:
            trees={name:dict(entries=tree.num_entries,branches=list(tree.keys()))
                   for name,tree in source.items() if hasattr(tree,'num_entries')}
            report.append(dict(run=str(row['run']),path=row['EVNT'],objects=source.classnames(),trees=trees))
    (args.output_dir/'evnt_metadata_schema.json').write_text(json.dumps(report,indent=2)+'\n')
    summary=dict(log_files_read=len(rows),evnt_headers_read=len(report),event_payload_entries_read=0,
                 wall_s=time.perf_counter()-start,physical_flux_normalization='not recovered; no estimate inferred from metadata entry counts',
                 reader_note='GenieReaderAlg.fillEvent explicitly inserts a unit HepMC weight; dumper CrossSection defaults to 1 without --genie. This is not evidence of equal physical luminosity across components.')
    (args.output_dir/'generation_audit_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':
    main()
