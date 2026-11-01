#!/usr/bin/env python3
"""Compare all original shard fields and provenance before removing duplicate products."""
import json
import resource
import time
from pathlib import Path
import numpy as np

repo=Path(__file__).resolve().parents[1];out=repo/'workbook/stage40_energy_ml';tick,cpu=time.perf_counter(),time.process_time()
cfg=json.loads((repo/'ml/configs/calonu_response.json').read_text());summary=json.loads((out/'summary.json').read_text())
path=repo/'ntuples/energy_ml_stage40/response.npz'
with np.load(path) as saved:d={k:saved[k] for k in saved.files}
cases=json.loads(str(d['cases_json']));schema={r['class_name']:r for r in json.loads((out/'native_schema_checks.json').read_text())}
removed=[];offset=0;groups=[]
for position,index in enumerate(cfg['indices']):
    shard=path.parent/f'shards/{index}.npz'
    with np.load(shard) as saved:
        records=json.loads(str(saved['cases_json']));end=offset+len(records)
        assert records==cases[offset:end]
        assert json.loads(str(saved['metadata_json']))==summary['extraction_resources'][position]
        for row in json.loads(str(saved['schemas_json'])):
            reference=schema[row['class_name']]
            assert reference['loaded_checksum']==row['loaded_checksum']
            assert reference['saved_checksums']==row['saved_checksums']
            assert dict(file=row['file'],branch=row['branch']) in reference['checked_branches']
        keys=[k for k in saved.files if k not in ['cases_json','metadata_json','schemas_json']]
        for key in keys:np.testing.assert_array_equal(saved[key],d[key][offset:end])
        groups.append(dict(index=index,events=len(records),native_fields=len(keys)))
    offset=end;removed.append(dict(path=str(shard.relative_to(repo)),bytes=shard.stat().st_size))
assert offset==len(cases)==summary['events']
for key,value in d.items():
    if key.startswith(('readout_','model_readout_','offpulse_','time_shift_')) or key=='nominal_window_charge_pC':
        assert np.isnan(value[~d['common_waveform']]).all()
        assert np.isfinite(value[d['common_waveform']]).all()
payload=repo/'software/energy-ml-calonu-response-stage40.tar.gz'
removed.append(dict(path=str(payload.relative_to(repo)),bytes=payload.stat().st_size))
for row in removed:(repo/row['path']).unlink()
(path.parent/'shards').rmdir()
noise=path.parent/'source_noise.npz'
with np.load(noise) as saved:assert all(saved[k].shape==(cfg['source_noise_events'],) for k in saved.files)
record=dict(final_cache=str(path.relative_to(repo)),final_cache_bytes=path.stat().st_size,
            synthetic_noise_cache=str(noise.relative_to(repo)),synthetic_noise_bytes=noise.stat().st_size,
            native_all_fields_rejoined_equal=True,metadata_and_schema_preserved=True,groups=groups,
            removed=removed,removed_bytes=sum(r['bytes'] for r in removed),source_experiment_files_modified=False,
            wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
(out/'archive.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
