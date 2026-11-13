#!/usr/bin/env python3
"""Retain official waveform charge, raw estimate and fit status for every source event."""
import numpy as np
import uproot


def main():
    channels = ['Veto20','Veto21','Preshower0','Preshower1','VetoNu0','VetoNu1']
    fields = ['charge','raw_charge','status','peak','width','localtime','baseline','baseline_rms']
    with uproot.open('merge.root') as f:
        tree = f['nt']
        names = ['run','eventID'] + [c+'_'+x for c in channels for x in fields if c+'_'+x in tree.keys()]
        arrays = tree.arrays(names, library='np')
    np.savez_compressed('waveform.npz',**{k:arrays[k] for k in names})


if __name__ == '__main__':main()
