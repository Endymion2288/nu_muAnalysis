#!/usr/bin/env python3
"""Trace the compared waveform implementations to their actual Git ancestry."""
import argparse
import json
import math
from pathlib import Path
import resource
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calypso', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check-integrals', action='store_true',
                        help='Use the active ROOT runtime to check saved real pulse parameters')
    args = parser.parse_args()
    start = time.monotonic()
    args.output.mkdir(parents=True, exist_ok=True)

    def git(*argv):
        return subprocess.check_output(['git', '-C', str(args.calypso), *argv])

    def source(rev, path):
        return git('show', rev + ':' + path)

    old, rotated, update = 'd32b0ff3', '88c457c1', 'dd56a65e'
    parent = git('rev-parse', rotated + '^').decode().strip()
    files = [
        'Waveform/WaveRecTools/src/WaveformReconstructionTool.cxx',
        'Waveform/WaveRecTools/src/WaveformReconstructionTool.h',
        'Waveform/WaveRecAlgs/python/WaveRecAlgsConfig.py',
        'Waveform/WaveRecTools/src/WaveformCleanupTool.cxx',
        'Waveform/WaveRecTools/src/WaveformCleanupTool.h',
    ]
    comparisons = []
    for path in files:
        a, b = source(old, path), source(rotated, path)
        row = dict(path=path, old_equals_update=a == source(update, path),
                   strict_equals_before_update=b == source(update + '^', path),
                   rotation_commit_unchanged=b == source(parent, path),
                   current_equals_rotated=b == (args.calypso / path).read_bytes())
        assert all(value for key, value in row.items() if key != 'path'), row
        comparisons.append(row)

    def ancestor(a, b):
        result = subprocess.run(['git', '-C', str(args.calypso), 'merge-base',
                                 '--is-ancestor', a, b], check=False)
        assert result.returncode in (0, 1)
        return result.returncode == 0

    ancestry = dict(update_in_old=ancestor(update, old),
                    update_in_strict=ancestor(update, rotated),
                    old_in_strict=ancestor(old, rotated),
                    strict_in_old=ancestor(rotated, old))
    assert ancestry['update_in_old'] and not ancestry['update_in_strict']
    rotation_wave_changes = git('diff', '--name-only', parent, rotated, '--', 'Waveform').decode().splitlines()
    assert not rotation_wave_changes
    update_to_old_changes = git('diff', '--name-only', update, old, '--', 'Waveform').decode().splitlines()
    assert not update_to_old_changes
    patch_paths = git('diff', '--name-only', rotated, '--', 'Waveform').decode().splitlines()
    assert not patch_paths
    timing_changes = git('diff', '--name-only', old, rotated, '--',
                         'Waveform/WaveformConditions').decode().splitlines()
    assert not timing_changes

    # Preserve the actual historical direction, before update -> baseline old.
    (args.output / 'upstream_waveform_update.diff').write_bytes(
        git('diff', update + '^', update, '--', *files))
    revisions = [old, rotated, parent, update, update + '^']
    metadata = [dict(zip(('commit', 'parents', 'author', 'author_date', 'commit_date', 'subject'),
                        git('show', '-s', '--format=%H%n%P%n%an%n%aI%n%cI%n%s', rev)
                        .decode().strip().split('\n'))) for rev in revisions]
    (args.output / 'commits.json').write_text(json.dumps(metadata, indent=2) + '\n')

    # Numbered excerpts remain reviewable after the external working tree changes.
    snippets = ['# 波形调用链与两版源码定位', '']
    locations = []
    targets = {
        files[0]: ['WaveformReconstructionTool::reconstructPrimary(',
                   'WaveformReconstructionTool::fillRawHitValues(',
                   'WaveformReconstructionTool::reconstructHit(',
                   'WaveformReconstructionTool::findRawHitValues(',
                   'WaveformReconstructionTool::fitGaussian(',
                   'WaveformReconstructionTool::fitCBall('],
        files[1]: ['BooleanProperty m_removeOverflow'],
        files[2]: ['"PreshowerWaveformRecAlg"', 'for key in ["PeakThreshold"',
                   'for key in ["KeepAll"'],
        'Waveform/WaveRecAlgs/src/RawWaveformRecAlg.cxx': ['RawWaveformRecAlg::execute('],
        'Waveform/WaveRecAlgs/src/RawWaveformRecAlg.h': ['SG::ReadHandleKey', 'ToolHandle'],
        'PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.cxx': ['void NtupleDumperAlg::FillWaveBranches('],
    }
    for rev in (old, rotated):
        for path, needles in targets.items():
            lines = source(rev, path).decode().splitlines()
            snippets += ['## ' + rev + ' / ' + path, '']
            for needle in needles:
                found = [i for i, line in enumerate(lines) if needle in line]
                assert found, (rev, path, needle)
                for index in found:
                    limit = 130 if any(name in needle for name in ('reconstructHit(', 'fitGaussian(', 'fitCBall(')) else 75
                    last = min(len(lines), index + limit)
                    snippets += ['定位：`' + needle + '`，原文件第' + str(index + 1) + '行。',
                                 '', '```text']
                    snippets += [str(i + 1) + ': ' + lines[i] for i in range(index, last)]
                    snippets += ['```', '']
                    locations.append(dict(commit=rev, path=path, needle=needle, line=index + 1))
    (args.output / 'source_excerpts.md').write_text('\n'.join(snippets).rstrip() + '\n')

    # Compare charge assignments separately from added overflow diagnostics.
    path = 'PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.cxx'
    def writer(s):
        s = s.decode()
        return s[s.index('void NtupleDumperAlg::FillWaveBranches('):
                 s.index('void NtupleDumperAlg::addCalibratedBranches(')]
    writer_equal = writer(source(old, path)) == writer(source(rotated, path))
    charge_assignments = {}
    for rev in (old, rotated):
        charge_assignments[rev] = [line.strip() for line in writer(source(rev, path)).splitlines()
                                   if 'm_wave_charge[ch]=' in line or 'm_wave_raw_charge[ch]=' in line]
    assert len(charge_assignments[old]) == 2
    assert charge_assignments[old] == charge_assignments[rotated]
    if args.check_integrals:
        import ROOT
        ROOT.gErrorIgnoreLevel = ROOT.kFatal
        assert ROOT.gInterpreter.Declare('''
#include "TF1.h"
#include <vector>
std::vector<double> WaveformLineageIntegral(double p, double m, double w,
                                           double a, double n, double lo, double hi) {
    TF1 f("WaveformLineageCB", "crystalball", lo, hi);
    f.SetParameters(p, m, w, a, n);
    double error=0.;
    double numeric=f.IntegralOneDim(lo, hi, -1, -1, error);
    return {f.Integral(lo, hi), numeric, error};
}
''')
        repo = Path(__file__).resolve().parents[2]
        pulse_path = repo / 'workbook/stage204_causal/waveform_fit_383.json'
        pulse = json.loads(pulse_path.read_text())
        hits = []
        for hit in pulse['hits']:
            values = list(ROOT.WaveformLineageIntegral(
                *[hit[k] for k in ('peak', 'mean', 'width', 'alpha', 'nval')],
                *hit['time_range_ns']))
            assert math.isclose(values[1], hit['root_integrals_mV_ns'][1], rel_tol=1e-10)
            hits.append(dict(channel=hit['channel'], status=hit['status'],
                             integral_mV_ns=values[0], numerical_integral_mV_ns=values[1],
                             numerical_error_mV_ns=values[2],
                             charge_pc=values[0]/50, numerical_charge_pc=values[1]/50))
        assert math.isinf(hits[0]['charge_pc']) and hits[0]['charge_pc'] < 0
        (args.output / 'fixed_parameters_integrals.json').write_text(json.dumps(
            dict(root_version=ROOT.gROOT.GetVersion(), input=str(pulse_path.relative_to(repo)),
                 run=pulse['run'], event=pulse['event'], hits=hits,
                 geometry_or_track_input=False,
                 scope='fixed real fitted parameters; not an RDO replay or fit comparison'), indent=2) + '\n')
    result = dict(old=old, strict=rotated, waveform_update=update,
                  rotation_parent=parent, ancestry=ancestry, comparisons=comparisons,
                  rotation_commit_waveform_changed_files=rotation_wave_changes,
                  update_to_old_waveform_changed_files=update_to_old_changes,
                  strict_local_waveform_changed_files=patch_paths,
                  timing_conditions_changed_files=timing_changes,
                  full_wave_writer_exact=writer_equal,
                  charge_assignments_exact=True, charge_assignments=charge_assignments,
                  source_locations=locations,
                  scope='source ancestry and dependency audit; no reconstruction or physics configuration changed',
                  wall_s=time.monotonic() - start,
                  max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (args.output / 'source_audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('ancestry', 'wall_s', 'max_rss_kib')}))


if __name__ == '__main__':
    main()
