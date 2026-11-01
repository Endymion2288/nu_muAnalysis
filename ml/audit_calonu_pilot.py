#!/usr/bin/env python3
"""Compare the stage35 numpy extraction with unmodified repository C++ expressions."""
import argparse
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np
import yaml
import ROOT

from calonu_inputs import feature_names, manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--index', type=int, default=0)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    tick = time.perf_counter()
    cpu = time.process_time()
    sys.path.insert(0, str(a.repo / 'AnalysisZipFramework/scripts'))
    from compare_tracking import selection
    row = next(r for r in manifest(a.repo) if int(r['index']) == a.index)
    ROOT.gInterpreter.AddIncludePath(str(a.repo / 'AnalysisZipFramework/include'))
    ROOT.gInterpreter.Declare('#include "RDFDefines.h"')
    node = ROOT.RDataFrame('nt', row['input'])
    node = node.Define('isCaloNuPeriod', 'true').Define('is2024Period', 'true')
    for filename in ['definitions.yaml', 'ml_definitions.yaml']:
        definitions = yaml.safe_load((a.repo / 'AnalysisZipFramework/config' / filename).read_text())['Definitions']
        for name, cfg in definitions.items():
            if name == 'ML_truth_barcode':
                continue  # The old CaloNu PHYS genuinely has no truth_barcode.
            if cfg.get('data_type', 'ALL') != 'DATA' and not cfg.get('requires'):
                node = node.Define(name, cfg['expression'])
    cuts, _ = selection(a.repo)
    flags = []
    for i, (_, expression) in enumerate(cuts):
        flag = 'pilot_cut_' + str(i)
        node = node.Define(flag, expression)
        flags.append(flag)
    raw = node.AsNumpy(['run', 'eventID'] + flags)
    cumulative = np.logical_and.accumulate(np.column_stack([np.ones(len(raw['run']), bool)] + [raw[k] for k in flags]), axis=1)
    names, _ = feature_names(a.repo)
    selected = node.Filter(' && '.join(flags)).AsNumpy(['run', 'eventID'] + names)
    order = np.lexsort((selected['eventID'], selected['run']))
    with np.load(a.input) as z:
        idx = np.lexsort((z['eventID'], z['run']))
        for key in ['run', 'eventID']:
            np.testing.assert_array_equal(z[key][idx], selected[key][order])
        meta = json.loads(str(z['metadata_json']))
        np.testing.assert_array_equal(meta['reports'][0]['cutflow'], cumulative.sum(axis=0))
        differences = {}
        for key in names:
            np.testing.assert_allclose(z[key][idx], selected[key][order], rtol=2e-5, atol=1e-4, equal_nan=True)
            differences[key] = float(np.nanmax(abs(z[key][idx] - selected[key][order])))
    result = dict(index=a.index, events=len(order), all_20_cut_counts_equal=True, selected_keys_equal=True,
                  all_46_F5_features_agree=True, feature_comparison_rtol=2e-5, feature_comparison_atol=1e-4,
                  max_absolute_feature_differences=differences, wall_s=time.perf_counter() - tick,
                  cpu_s=time.process_time() - cpu, peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
