#!/usr/bin/env python3
"""Audit ancestry, upstream preservation and the packaged strict material map."""
import argparse
import gzip
import json
from pathlib import Path
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    start = time.monotonic()
    repo = Path(__file__).resolve().parents[2]
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    def git(*argv):
        return subprocess.check_output(['git', '-C', str(args.source), *argv])
    head = git('rev-parse', 'HEAD').decode().strip()
    official = '7f2d16812070a263210d2b2dc56633345e5a10b1'
    ancestors = ['88c457c1', '73c97758', '1c06c7b6', '25147d80', official]
    for rev in ancestors:
        subprocess.run(['git', '-C', str(args.source), 'merge-base', '--is-ancestor', rev, head], check=True)
    assert not git('status', '--porcelain').strip(), 'Publish a clean, committed source tree'
    exact = {}
    for directory in ['Waveform', 'Tracker', 'Simulation', 'Generators', 'xAOD']:
        changed = git('diff', '--name-only', official, head, '--', directory).decode().splitlines()
        assert not changed, (directory, changed)
        exact[directory] = True
    material = args.source / 'Tracking/Acts/FaserActsGeometry/data/material-maps-alma9-rotated-rowmajor.json.gz'
    frozen = repo / 'software/stage205_material/material-manual-rowmajor.json.gz'
    assert material.read_bytes() == frozen.read_bytes()
    payload = gzip.decompress(material.read_bytes())
    compile((args.source / 'Tracking/Acts/FaserActsGeometry/python/RotatedMaterialMap.py').read_text(), str(material), 'exec')
    checks = {
        'Tracking/Acts/RootWriterTools/src/RootTrajectoryStatesWriterTool.cxx':
            ['rot.col(0) = Acts::Vector3(0, 0, -1)', 'std::hypot(global[Acts::ePos1],global[Acts::ePos2])'],
        'Tracking/Acts/FaserActsKalmanFilter/src/KalmanFitterTool.cxx':
            ['#include "FaserActsGeometry/FaserActsGeometryContext.h"', '#include "ActsInterop/IndexSourceLink.h"'],
        'Tracking/Acts/FaserActsKalmanFilter/src/CKF2.h':
            ['"IsolateCandidateSmoothing", true'],
        'Control/CalypsoExample/Reconstruction/scripts/faser_reco.py':
            ['configFlags.TrackingGeometry.MaterialSource = rotatedMaterialMapPath()', 'args.cond}'],
    }
    for name, strings in checks.items():
        text = (args.source / name).read_text()
        assert all(s in text for s in strings), name
        assert '<<<<<<<' not in text
    # The map is already versioned in Calypso; keep a compact textual audit here.
    patch = git('diff', official, head)
    (out / 'integration_vs_master.patch').write_bytes(patch)
    (out / 'integration_graph.txt').write_bytes(git('log', '--graph', '--oneline', '-n', '32'))
    merges = git('log', '--merges', '--format=%H %P %s', official + '..' + head).decode().splitlines()
    assert any('integrate official master with rotated geometry' in row for row in merges)
    result = dict(source=str(args.source), commit=head, official_commit=official,
                  preserved_ancestors=ancestors, exact_official_directories=exact,
                  material_bytes=len(payload), material_gzip_bytes=material.stat().st_size,
                  exact_frozen_strict_material=True, rename_and_default_checks=checks,
                  merge_commits=merges, merge_request='https://gitlab.cern.ch/xcheng/calypso/-/merge_requests/1',
                  target_branch='geoRotation_latestMaster',
                  changed_files=git('diff', '--name-only', official, head).decode().splitlines(),
                  clean_worktree=True, wall_s=time.monotonic()-start)
    (out / 'software_provenance.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
