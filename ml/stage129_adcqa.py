"""Exact persisted-ADC repeat check for the one-parent engineering pilot."""
import json
import sys
from pathlib import Path

import ROOT

from stage122_saved import SavedWaveforms

ROOT.gInterpreter.Declare('#define HEPMC3 1\n')
for lib in ['libWaveRawEvent.so','libxAODEventInfo.so']:assert ROOT.gSystem.Load(lib)>=0
path,before,report,mode=sys.argv[1:]
reader=SavedWaveforms(ROOT,path,['Calo','VetoNu','Veto','Trigger','Preshower'])
assert reader.tree.GetEntries()==1 and reader.tree.GetEntry(0)>0
info=getattr(reader.tree,reader.info)
run=reader.member(info,'runNumber','unsigned int');event=reader.member(info,'eventNumber','unsigned long long')
data=reader.read(0,run,event)
if mode=='before':Path(before).write_text(json.dumps(data,separators=(',',':'))+'\n')
else:
    previous=json.loads(Path(before).read_text())
    assert data==previous,'Actual same-HITS/same-seed ADC repeat differs'
    Path(report).write_text(json.dumps(dict(run=run,event=event,detector_wave_counts={k:len(v) for k,v in data.items()},ADC_samples=sum(len(w['adc']) for waves in data.values() for w in waves),actual_ADC_repeat_exact=True,persisted_channels={k:[dict(id32=w['id32'],channel=w['channel']) for w in v] for k,v in data.items()},scope='independent digitizer processes on sameHITS; response replication, no independentnu N'),indent=2)+'\n')
print('PERSISTED_ADC_QA',mode,{k:len(v) for k,v in data.items()},flush=True)
