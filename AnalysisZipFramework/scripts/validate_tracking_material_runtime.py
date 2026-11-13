#!/usr/bin/env python3
"""Verify every bin frame with the installed ACTS JSON decoder used by Calypso."""
import argparse
import json
from pathlib import Path

import ROOT
import numpy as np


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, default=Path('/cvmfs/faser.cern.ch/repo/sw/database/DBRelease/current/acts/material-maps-alma9.json'))
    p.add_argument('--rotated', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
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
    original = json.loads(args.source.read_text()); rotated = json.loads(args.rotated.read_text())
    frame = np.eye(4); frame[:3,:3] = [[0,0,1],[0,1,0],[-1,0,0]]
    maximum = 0.; count = 0
    for section in ['Surfaces', 'Volumes']:
        for before, after in zip(original[section]['entries'], rotated[section]['entries']):
            a = before['value'].get('material', {}).get('binUtility')
            b = after['value'].get('material', {}).get('binUtility')
            if a is None: continue
            def decoded(utility):
                return np.array(ROOT.NuMuMaterialTransform(json.dumps(utility.get('transform', {})))).reshape(4,4)
            error = np.max(abs(decoded(b) - frame @ decoded(a)))
            maximum = max(maximum, float(error)); count += 1
    assert maximum < 1e-12, maximum
    result = dict(actual_acts_decoder=True, bin_frames=count, max_transform_error=maximum,
        json_order='row-major', source=str(args.source), rotated=str(args.rotated), library='libActsPluginJson.so')
    args.output.write_text(json.dumps(result, indent=2)+'\n'); print(json.dumps(result))


if __name__ == '__main__':main()
