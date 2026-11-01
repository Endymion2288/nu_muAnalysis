#!/usr/bin/env python3
"""Two-event independent RAW/xAOD identity and native saved-wave algebra check."""
import ctypes
import json
import resource
import time
from pathlib import Path
import numpy as np


def main():
    import ROOT
    tick, cpu = time.perf_counter(), time.process_time(); repo = Path(__file__).resolve().parents[1]
    with np.load(repo/'ntuples/energy_ml_stage43/smoke.npz') as z: raw = {k: z[k] for k in z.files}
    path = '/eos/experiment/faser/data0/rec/2024/r0022/016000/Faser-Physics-016000-00000-r0022-xAOD.root'
    file = ROOT.TFile.Open(path); tree = file.Get('CollectionTree'); tree.SetBranchStatus('*', 0)
    for name in ['EventInfoAux.', 'CaloNuWaveformHitsAux.']: tree.SetBranchStatus(name, 1)
    schemas = []
    for name in ['EventInfoAux.', 'CaloNuWaveformHitsAux.']:
        cls = ROOT.TClass.GetClass(tree.GetBranch(name).GetClassName())
        saved = [int(s.GetCheckSum()) for s in file.GetStreamerInfoList() if s.GetName() == cls.GetName()]
        assert int(cls.GetCheckSum()) in saved
        schemas.append(dict(branch=name, class_name=cls.GetName(), loaded_checksum=int(cls.GetCheckSum()), saved_checksums=saved))

    def member(obj, name, typ):
        cls = ROOT.TClass.GetClass(type(obj).__cpp_name__); offset = cls.GetDataMember(name).GetOffset(); assert offset >= 0
        address = ROOT.addressof(obj)+offset
        if typ == 'unsigned int': return ctypes.c_uint.from_address(address).value
        if typ == 'unsigned long long': return ctypes.c_ulonglong.from_address(address).value
        return ROOT.bind_object(address, typ)

    records = []
    for i in range(2):
        tree.GetEntry(i); info = getattr(tree, 'EventInfoAux.'); aux = getattr(tree, 'CaloNuWaveformHitsAux.')
        assert (member(info, 'runNumber', 'unsigned int'), member(info, 'eventNumber', 'unsigned long long')) == (raw['run'][i], raw['eventID'][i])
        channels = list(member(aux, 'channel', 'std::vector<unsigned int>')); assert channels == [6, 7, 14, 15]
        times = np.array([list(q) for q in member(aux, 'time_vector', 'std::vector<std::vector<float>>')])
        wave = np.array([list(q) for q in member(aux, 'wave_vector', 'std::vector<std::vector<float>>')])
        baseline = np.array(list(member(aux, 'baseline_mean', 'std::vector<float>')))
        integral = np.array(list(member(aux, 'raw_integral', 'std::vector<float>')))
        predicted = (baseline[:, None]-raw['adc'][i, np.arange(4)[:, None], (times/2).astype(int)]*(2/16.384)).astype('float32')
        np.testing.assert_array_equal(predicted, wave)
        np.testing.assert_allclose(np.maximum(wave, 0).sum(1)*2, integral, atol=1e-5, rtol=0)
        records.append(dict(run=int(raw['run'][i]), eventID=int(raw['eventID'][i]), channels=channels,
                            wave_max_difference_mV=float(np.max(abs(predicted-wave))),
                            raw_charge_max_difference_pC=float(np.max(abs(np.maximum(wave, 0).sum(1)*2-integral)))/50,
                            start_ns=times[:, 0].tolist(), stop_ns=times[:, -1].tolist()))
    file.Close()
    summary = dict(valid=True, events=2, input=path, schemas=schemas, cases=records,
                   wall_s=time.perf_counter()-tick, cpu_s=time.process_time()-cpu,
                   peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (repo/'workbook/stage43_energy_ml/native_pilot_validation.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__': main()
