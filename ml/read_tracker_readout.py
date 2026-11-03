#!/usr/bin/env python3
"""Read-only native REC identity join and compact conditional tracker activity."""
import argparse
import faulthandler
import json
import resource
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', type=Path, required=True)
    parser.add_argument('--sources', type=int, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--xml', type=Path, required=True)
    parser.add_argument('--qa', action='store_true', help='First frozen identity/source only')
    args = parser.parse_args()
    faulthandler.enable()
    if args.qa:
        faulthandler.dump_traceback_later(120)
    start, cpu = time.perf_counter(), time.process_time()
    import ROOT
    for lib in ['libxAODEventInfoDict.so', 'libTrackerEventTPCnv.so',
                'libTrackerEventAthenaPoolCnvDict.so', 'libTrackerIdentifier.so',
                'libIdDictParser.so']:
        assert ROOT.gSystem.Load(lib) >= 0, lib
    assert ROOT.gInterpreter.Declare('#include "'+str(Path(__file__).with_name('tracker_readout_control.h').resolve())+'"')
    helper = ROOT.ReadoutID(str(args.xml))
    assert helper.wafer_hash_max() == 192
    print('NATIVE_READER_READY', flush=True)
    sample = json.loads(args.sample.read_text())
    output = dict(sources=[], qa=args.qa, definition=sample['definition'])
    bytes_read = 0
    for source in args.sources:
        row = sample['sources'][source]
        cases = row['cases'][:1] if args.qa else row['cases']
        wanted = ROOT.std.vector('unsigned long long')([c['event'] for c in cases])
        records, files = {}, []
        paths = row['native_files']
        if args.qa and row['sample'] == 'data':
            # Only locate the QA candidate by actual first/last headers. This is
            # not the production join: bulk scans every frozen file for duplicates.
            lo, hi = 0, len(paths)-1
            paths = []
            while lo <= hi:
                middle = (lo+hi)//2
                candidate = row['native_files'][middle]
                file = ROOT.TFile.Open(candidate)
                tree = file.Get('CollectionTree')
                tree.SetBranchStatus('*', 0)
                tree.SetBranchStatus('EventInfoAux.', 1)
                bounds = []
                for entry in [0, tree.GetEntries()-1]:
                    assert tree.GetEntry(entry) > 0
                    bounds.append(int(ROOT.ReadoutHeader(tree)[3]))
                read = int(file.GetBytesRead()); bytes_read += read
                files.append(dict(path=candidate, qa_range_candidate=True,
                                  event_bounds=bounds, bytes_read=read))
                file.Close()
                if bounds[0] <= cases[0]['event'] <= bounds[1]:
                    paths = [candidate]; break
                if cases[0]['event'] < bounds[0]:
                    hi = middle-1
                else:
                    lo = middle+1
        for path in paths:
            print('OPEN', source, path, flush=True)
            file = ROOT.TFile.Open(path)
            assert file and not file.IsZombie(), path
            tree = file.Get('CollectionTree')
            tree.SetBranchStatus('*', 0)
            tree.SetCacheSize(0)  # sparse reads; ROOT's compressed baskets are reused within file
            tree.SetBranchStatus('EventInfoAux.', 1)
            # PG event IDs restart in generation subfiles. Preserve the already
            # validated stage53 source/merged-entry identity; never event-only join MC.
            if row['sample'] == 'MC':
                assert tree.GetEntries() == row['total_entries']
                found = [c['entry'] for c in cases]
            else:
                found = list(ROOT.ReadoutFind(tree, wanted, row['run']))
            branches = ['EventInfoAux.', 'SCT_RDOs', 'SCT_ClusterContainer',
                        'CKFTrackCollectionBackwardWithoutIFT']
            for branch in branches:
                assert tree.GetBranch(branch), (path, branch)
                tree.SetBranchStatus(branch, 1)
            matches = sorted((entry, i) for i, entry in enumerate(found) if entry >= 0)
            for entry, i in matches:
                if args.qa:
                    print('QA_IDENTITY', source, entry, flush=True)
                assert i not in records, ('duplicate across files', source, i)
                assert tree.GetEntry(entry) > 0
                if args.qa:
                    print('QA_READ', source, entry, flush=True)
                run, stamp, bcid, event = list(ROOT.ReadoutHeader(tree))
                assert event == cases[i]['event']
                assert run == row['run']
                if 'eventTime' in cases[i]:
                    assert stamp == cases[i]['eventTime'], (source, i, stamp)
                if args.qa:
                    print('QA_HEADER', source, event, stamp, flush=True)
                matrix = [list(v) for v in ROOT.ReadoutFromTree(tree, helper)]
                if any(v[23] for v in matrix):
                    print('INVALID_CLUSTER_IDENTITY', source, i, entry, event, flush=True)
                if args.qa:
                    print('QA_SUMMARY', source, entry, flush=True)
                assert [v[3] for v in matrix] == cases[i]['original_counts'][:4], (source, i, 'cluster closure')
                records[i] = dict(case=i, native_file=row['native_files'].index(path),
                                  native_entry=entry, event=event, timestamp=stamp,
                                  bcid=bcid, values=matrix)
            read = int(file.GetBytesRead())
            bytes_read += read
            files.append(dict(path=path, entries=int(tree.GetEntries()), matched=len(matches), bytes_read=read))
            file.Close()
            assert bytes_read < 1450000000, 'per-shard input limit'
        result = dict(source=source, requested=len(cases), matched=len(records), files=files,
                      unresolved=[i for i in range(len(cases)) if i not in records],
                      records=[records[i] for i in sorted(records)])
        output['sources'].append(result)
        print('SOURCE', source, len(records), '/', len(cases), 'bytes', bytes_read, flush=True)
    output.update(bytes_read=bytes_read, wall_s=time.perf_counter()-start,
                  cpu_s=time.process_time()-cpu,
                  peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, separators=(',', ':'))+'\n')
    print('RESOURCES', {k:output[k] for k in ['bytes_read','wall_s','cpu_s','peak_rss_MiB']}, flush=True)


if __name__ == '__main__':
    main()
