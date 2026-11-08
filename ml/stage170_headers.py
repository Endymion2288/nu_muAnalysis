"""Snapshot static official header bytes, not runtime data or a Calypso build."""
import io
import json
import tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'software/stage170';OUT.mkdir(parents=True,exist_ok=True)
contents={}
with tarfile.open(ROOT/'software/calypso-master-d32b0ff3-el9-gcc13.tar.gz') as t:
    for m in t:
        for folder in ['EventFormats','Exceptions']:
            prefix='./src/faser-common/'+folder+'/'+folder+'/'
            if m.isfile() and m.name.startswith(prefix):
                contents['headers/'+folder+'/'+m.name[len(prefix):]]=t.extractfile(m).read()
contents['headers/Logging.hpp']=(ROOT/'../calypso/faser-common/Logging/include/Logging.hpp').read_bytes()
assert 'headers/EventFormats/TLBDataFragment.hpp' in contents
with tarfile.open(OUT/'official_headers.tar.gz','w:gz') as t:
    for name,data in sorted(contents.items()):
        info=tarfile.TarInfo(name);info.size=len(data);t.addfile(info,io.BytesIO(data))
with tarfile.open(OUT/'official_headers.tar.gz') as t:
    assert all(t.extractfile(name).read()==data for name,data in contents.items())
metadata=dict(EventFormats_and_Exceptions_source='software/calypso-master-d32b0ff3-el9-gcc13.tar.gz:src/faser-common/',
    Calypso_pin='d32b0ff3cc4a2dad4abfb1474a82422c3c25b305',
    Logging_source='../calypso/faser-common/Logging/include/Logging.hpp',common_source_commit='1770d15df9311f6535c09909edf9ad64a5779e32',
    not_a_Calypso_rebuild=True,exact_archive_replay=True,header_files={k:len(v) for k,v in contents.items()})
(ROOT/'workbook/stage170_energy_ml/header_sources.json').write_text(json.dumps(metadata,indent=2)+'\n')
print({'static_headers':len(contents),'archive_bytes':(OUT/'official_headers.tar.gz').stat().st_size})
