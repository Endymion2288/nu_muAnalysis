#!/usr/bin/env python3
"""Compile only the compact analysis helper against the loaded gcc13 runtime."""
import argparse
import os
from pathlib import Path
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
includes = list(dict.fromkeys(os.environ['ROOT_INCLUDE_PATH'].split(':')))
libraries = list(dict.fromkeys(os.environ['LD_LIBRARY_PATH'].split(':')))
command = ['g++', '-std=c++17', '-O2', '-fPIC', '-shared', '-x', 'c++',
           str(Path(__file__).with_name('tracker_noise_summary.h')), '-o', str(args.output)]
command += ['-I'+p for p in includes if p]
command += ['-L'+p for p in libraries if p]
command += ['-lGaudiKernel', '-lTrackerIdentifier', '-lTrkTrack', '-lTrackerRIO_OnTrack', '-lAthenaKernel']
start = time.perf_counter()
subprocess.run(command, check=True)
print(f'stage53_helper_compile_wall_s={time.perf_counter()-start:.3f}', flush=True)
