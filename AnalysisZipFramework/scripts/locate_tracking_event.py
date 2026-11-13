#!/usr/bin/env python3
"""Locate an event using the RDO's primitive MC event-number branch."""
import argparse
from pathlib import Path

import numpy as np
import uproot


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rdo',required=True)
    parser.add_argument('--ntuple')
    parser.add_argument('--run',type=int,required=True)
    parser.add_argument('--event',type=int,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    with uproot.open(args.rdo) as f:
        ids=f['CollectionTree']['xAOD::EventAuxInfo_v3_EventInfoAuxDyn.mcEventNumber'].array(library='np')
    entry=int(np.flatnonzero(ids==args.event).item())
    args.output.write_text(str(entry)+'\n')
    print(f'RDO mcEventNumber={args.event}, entry={entry}; run checked after reconstruction')


if __name__=='__main__':
    main()
