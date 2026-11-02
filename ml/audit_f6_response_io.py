#!/usr/bin/env python3
"""Metadata-only diagnosis of full-run requested-byte budget overrun; no event read."""
import json
import time

import numpy as np
import uproot

from calonu_muon_control import manifest
from read_f6_muon_response import REPO, branches, configuration

cfg=configuration();tick=time.perf_counter();rows=[]
for row in manifest(REPO):
    with uproot.open(row['input']) as f:
        t=f['nt'];unique=0;touch=0
        for name in branches():
            b=t[name];offsets=b.entry_offsets;sizes=b.member('fBasketBytes')[:b.num_baskets]
            assert len(sizes)==len(offsets)-1
            unique+=int(np.sum(sizes))
            for lo,hi,size in zip(offsets[:-1],offsets[1:],sizes):
                reads=(hi-1)//cfg['chunk_entries']-lo//cfg['chunk_entries']+1
                touch+=int(size)*reads
        rows.append(dict(index=int(row['index']),selected_columns_compressed_bytes=unique,
                         predicted_chunk_basket_touches_bytes=touch,metadata_requested_bytes=int(f.file.source.num_requested_bytes)))
out=dict(event_entries_read=0,wall_s=time.perf_counter()-tick,files=rows,
         selected_columns_compressed_bytes=sum(r['selected_columns_compressed_bytes'] for r in rows),
         predicted_chunk_basket_touches_bytes=sum(r['predicted_chunk_basket_touches_bytes'] for r in rows),
         metadata_requested_bytes=sum(r['metadata_requested_bytes'] for r in rows),
         interpretation='Fixed entry arrays requests reread baskets spanning adjacent50k chunks; diagnostic not additional physics extraction. Next extraction should use basket-aware t.iterate with byte step, budget measured touches rather than unique bytes; no rerun solely to improve timing.')
(REPO/'workbook/stage52_energy_ml/io_diagnosis.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='files'}))
