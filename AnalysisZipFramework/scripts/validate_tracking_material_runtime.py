#!/usr/bin/env python3
"""Verify every bin frame with the installed ACTS JSON decoder used by Calypso."""
import argparse
import gzip
import json
from pathlib import Path

import ROOT
import numpy as np


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, default=Path('/cvmfs/faser.cern.ch/repo/sw/database/DBRelease/current/acts/material-maps-alma9.json'))
    p.add_argument('--rotated', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--audit-only', action='store_true', help='Record frame mismatches without accepting them as valid')
    args = p.parse_args()
    assert ROOT.gSystem.Load('libActsPluginJson.so') >= 0
    assert ROOT.gInterpreter.Declare('''
#include "Acts/Plugins/Json/AlgebraJsonConverter.hpp"
#include <string>
#include <vector>
std::vector<double> NuMuMaterialTransform(const std::string& s) {
    auto t = Acts::Transform3JsonConverter::fromJson(nlohmann::json::parse(s));
    std::vector<double> out;
    for (int i=0;i<4;++i) for (int j=0;j<4;++j) out.push_back(t.matrix()(i,j));
    return out;
}
''')
    def read(path):
        return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_text())
    original = read(args.source); rotated = read(args.rotated)
    frame = np.eye(4); frame[:3,:3] = [[0,0,1],[0,1,0],[-1,0,0]]
    maximum = 0.; count = 0; rows = []; missing_zero = []
    for section in ['Surfaces', 'Volumes']:
        def identity(entry):
            return tuple((k, v) for k, v in sorted(entry.items()) if k != 'value')
        targets = {identity(e):e for e in rotated[section]['entries']}
        assert set(targets) <= {identity(e) for e in original[section]['entries']}
        for before in original[section]['entries']:
            key = identity(before)
            if key not in targets:
                material = before['value'].get('material', {})
                assert all(c['thickness'] == 0 or not c['material'] for row in material.get('data', []) for c in row), key
                missing_zero.append(dict(section=section, identity=key))
                continue
            after = targets[key]
            a = before['value'].get('material', {}).get('binUtility')
            b = after['value'].get('material', {}).get('binUtility')
            if a is None: continue
            assert a['binningdata'] == b['binningdata']
            assert before['value']['material']['data'] == after['value']['material']['data']
            def decoded(utility):
                return np.array(ROOT.NuMuMaterialTransform(json.dumps(utility.get('transform', {})))).reshape(4,4)
            error = np.max(abs(decoded(b) - frame @ decoded(a)))
            maximum = max(maximum, float(error)); count += 1
            rows.append(dict(section=section, identity=key, max_transform_error=float(error),
                             decoded_transform=decoded(b).tolist()))
    if not args.audit_only: assert maximum < 1e-12, maximum
    result = dict(actual_acts_decoder=True, bin_frames=count, max_transform_error=maximum,
        frame_valid=maximum < 1e-12, missing_zero_material=missing_zero, rows=rows,
        json_order='row-major', source=str(args.source), rotated=str(args.rotated), library='libActsPluginJson.so')
    args.output.write_text(json.dumps(result, indent=2)+'\n'); print(json.dumps(result))


if __name__ == '__main__':main()
