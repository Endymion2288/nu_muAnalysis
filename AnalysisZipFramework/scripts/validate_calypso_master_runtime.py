#!/usr/bin/env python3
"""Check components, smoothing defaults and strict material after runtime relocation."""
import argparse
import ctypes
import gzip
import json
import os
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--reference-map', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    start = time.monotonic()
    import ROOT
    from AthenaConfiguration.ComponentFactory import CompFactory
    from FaserActsGeometry.RotatedMaterialMap import rotatedMaterialMapPath
    assert Path(os.environ['Calypso_DIR']).resolve() == args.runtime.resolve()
    libraries = ['GeoModelFaserUtilities', 'FaserActsGeometry', 'FaserActsKalmanFilter', 'NtupleDumper']
    for name in libraries:
        path = args.runtime / 'lib' / ('lib' + name + '.so')
        ctypes.CDLL(str(path), mode=os.RTLD_GLOBAL)
    components = {}
    for name in ['FaserActsTrackingGeometrySvc', 'FaserActsTrackingGeometryTool',
                 'CKF2', 'KalmanFitterTool', 'NtupleDumperAlg']:
        instance = CompFactory.getComp(name)('IntegrationValidation')
        components[name] = instance.getType()
        if name == 'CKF2':
            assert instance.IsolateCandidateSmoothing
    material = Path(rotatedMaterialMapPath())
    assert material.read_bytes() == gzip.decompress(args.reference_map.read_bytes())
    assert str(material) == rotatedMaterialMapPath()
    provenance = json.loads((args.runtime / 'software_provenance.json').read_text())
    record = dict(runtime=str(args.runtime), source_commit=provenance['commit'],
                  root_version=ROOT.gROOT.GetVersion(), libraries_loaded=libraries,
                  components=components, isolated_smoothing_default=True,
                  strict_material_exact=True, material_bytes=material.stat().st_size,
                  material_cached=True, wall_s=time.monotonic() - start)
    args.output.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
