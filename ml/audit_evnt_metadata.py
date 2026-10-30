#!/usr/bin/env python3
"""Read official Athena EVNT metadata, without deriving weights from entry counts.

Run in the existing Athena24.0.41 / Calypso environment, not the CUDA view.
"""
import argparse
import csv
import json
import time
from pathlib import Path

from PyUtils.MetaReader import read_metadata


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sources',type=Path,default=Path('workbook/stage14_energy_ml/generation_sources.tsv'))
    p.add_argument('--output',type=Path,default=Path('workbook/stage16_energy_ml/evnt_metadata_full.json'))
    args=p.parse_args();start=time.perf_counter();records=[]
    for row in csv.DictReader(args.sources.open(),delimiter='\t'):
        metadata=read_metadata(row['EVNT'],mode='full')
        records.append(dict(run=int(row['run']),EVNT=row['EVNT'],metadata=metadata[row['EVNT']]))
        print(row['run'],list(metadata[row['EVNT']]),flush=True)
    args.output.write_text(json.dumps(dict(files=records,wall_s=time.perf_counter()-start),indent=2,default=str)+'\n')


if __name__=='__main__':main()
