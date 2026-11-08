"""LCG postprocessing for one G4-only parent, preserving unknown planes."""
import json
import sys
from stage178_common import OUT, CACHE, classify, read_gz

index = int(sys.argv[1])
box = next(r for r in json.loads((OUT / 'state_boxes.json').read_text()) if r['index'] == index)
raw = read_gz(CACHE / f'parent_{index}_lineage.json.gz')
report = classify(index, raw, box)
(OUT / f'parent_{index}_intervals.json').write_text(json.dumps(report, separators=(',', ':')) + '\n')
print(dict(index=index, state_supported=report['state_supported'], robust_crossings=report['robust_crossings'],
    birth_process_side_counts=report['birth_process_side_counts']), flush=True)
