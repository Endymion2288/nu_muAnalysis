#!/usr/bin/env python3
"""Install the validated row-major map and update the existing Calypso Python entry points."""
import argparse
import ast
import difflib
import gzip
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--calypso',type=Path,required=True)
    p.add_argument('--audit',type=Path,required=True)
    args=p.parse_args(); repo=Path(__file__).resolve().parents[2]
    source=repo/'software/stage205_material/material-manual-rowmajor.json.gz'
    payload=gzip.decompress(source.read_bytes())
    target=args.calypso/'run/material-maps-alma9-rotated-rowmajor.json'
    old='/cvmfs/faser.cern.ch/repo/sw/database/DBRelease/current/acts/material-maps-alma9.json'
    files=[args.calypso/'Control/CalypsoExample/Reconstruction/scripts/faser_reco.py',
           args.calypso/'run/bin/faser_reco.py']
    edits=[];patch=[]
    for file in files:
        before=file.read_text()
        assert before.count(old)==1,(file,'expected the original material default once')
        after=before.replace(old,str(target));ast.parse(after)
        edits.append((file,after))
        patch.extend(difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),
                     fromfile=str(file),tofile=str(file)))
    target.write_bytes(payload)
    for file,after in edits:file.write_text(after)
    assert target.read_bytes()==payload
    args.audit.parent.mkdir(parents=True,exist_ok=True)
    args.audit.with_suffix('.patch').write_text(''.join(patch))
    args.audit.write_text(json.dumps(dict(source=str(source),installed_map=str(target),map_bytes=len(payload),
        exact_frozen_map_bytes=True,original_material_source=old,modified_python=[str(f) for f in files],
        build_bin='symlink to modified source; no C++ rebuild',frozen_bulk_runtime='unchanged; used the identical map through the final accumulator override'),indent=2)+'\n')
    print(args.audit)


if __name__=='__main__':main()
