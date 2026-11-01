#!/usr/bin/env python3
"""Single-process, source-sequential extraction; no new labels or fits."""
import argparse
from source_transfer import configuration
from read_source_transfer_features import main as extract
p=argparse.ArgumentParser();p.add_argument('--batch',type=int,choices=range(6),required=True);a=p.parse_args()
indices=configuration()['indices'][a.batch*10:(a.batch+1)*10]
assert len(indices)==10
for i in indices:extract(['--index',str(i)])
