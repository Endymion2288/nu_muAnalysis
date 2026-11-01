#!/usr/bin/env python3
"""Read original POOL payloads with layout-compatible dictionaries, without reconstruction."""
import argparse
import ctypes
import json
import resource
import time
from pathlib import Path

import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--request', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--include', required=True)
    p.add_argument('--compact-signal', action='store_true', help='Retain nominal signal and hit totals, not individual HITS')
    a = p.parse_args()
    request = json.loads(a.request.read_text())
    tick, cpu = time.perf_counter(), time.process_time()
    import ROOT
    ROOT.gSystem.Load('libFaserCaloSimEventTPCnv.so')
    ROOT.gSystem.Load('libFaserCaloSimEvent.so')
    ROOT.gInterpreter.AddIncludePath(a.include)
    assert ROOT.gInterpreter.Declare('''
#define HEPMC3 1
#include "FaserCaloSimEventTPCnv/CaloHits/CaloHitCollectionCnv_p1a.h"
#include "GaudiKernel/MsgStream.h"
#include "AthenaKernel/ExtendedEventContext.h"
#include "GaudiKernel/ThreadLocalContext.h"
#include <vector>
std::vector<double> ReadCaloNuSensitiveHits(const CaloHitCollection_p1a* p) {
    EventContext ctx;
    Atlas::setExtendedEventContext(ctx, Atlas::ExtendedEventContext(nullptr, 0));
    Gaudi::Hive::setCurrentContext(ctx);
    MsgStream log(nullptr, "CaloNuReadOnly");
    CaloHitCollectionCnv_p1a cnv;
    auto transient = cnv.createTransient(p, log);
    std::vector<double> output;
    for (const auto& h : *transient) {
        output.push_back(h.identify());
        output.push_back(h.energyLoss());
        output.push_back(h.meanTime());
        auto s=h.localStartPosition(), e=h.localEndPosition();
        output.insert(output.end(), {s.x(),s.y(),s.z(),e.x(),e.y(),e.z()});
    }
    delete transient;
    return output;
}
''')

    def member(obj, name, typename):
        cls = ROOT.TClass.GetClass(type(obj).__cpp_name__)
        offset = cls.GetDataMember(name).GetOffset()
        assert offset >= 0
        address = ROOT.addressof(obj)+offset
        if typename == 'unsigned int':
            return ctypes.c_uint.from_address(address).value
        if typename == 'unsigned long long':
            return ctypes.c_ulonglong.from_address(address).value
        if typename == 'int':
            return ctypes.c_int.from_address(address).value
        if typename == 'float':
            return ctypes.c_float.from_address(address).value
        if typename == 'short':
            return ctypes.c_short.from_address(address).value
        return ROOT.bind_object(address, typename)

    opened, schemas = {}, []

    def tree(path, branches):
        if path not in opened:
            f = ROOT.TFile.Open(path)
            assert f and not f.IsZombie(), path
            t = f.Get('CollectionTree')
            t.SetBranchStatus('*', 0)
            for branch in branches:
                assert t.GetBranch(branch), (path, branch)
                t.SetBranchStatus(branch, 1)
                clsname = t.GetBranch(branch).GetClassName()
                cls = ROOT.TClass.GetClass(clsname)
                saved = [info for info in f.GetStreamerInfoList() if info.GetName() == clsname]
                schemas.append(dict(file=path, branch=branch, class_name=clsname,
                                    loaded_checksum=int(cls.GetCheckSum()),
                                    saved_checksums=[int(info.GetCheckSum()) for info in saved]))
                assert any(int(info.GetCheckSum()) == int(cls.GetCheckSum()) for info in saved), (path, clsname, 'layout checksum differs')
            opened[path] = (f, t)
        return opened[path][1]

    def info(t):
        branch = 'EventInfoAux.' if t.GetBranch('EventInfoAux.') else 'xAOD::EventAuxInfo_v3_EventInfoAux.'
        obj = getattr(t, branch)
        return member(obj, 'runNumber', 'unsigned int'), member(obj, 'eventNumber', 'unsigned long long')

    def beam_signature(t):
        event = getattr(t, 'McEventCollection_p6_BeamTruthEvent')
        particles = member(event, 'm_genParticles', 'std::vector<GenParticle_p6>')
        return [[member(part, name, typ) for name, typ in [('m_pdgId', 'int'), ('m_status', 'int'),
                ('m_px', 'float'), ('m_py', 'float'), ('m_pz', 'float'), ('m_m', 'float')]] for part in particles]

    def beam_identity(t):
        event=getattr(t,'McEventCollection_p6_BeamTruthEvent')
        particles=member(event,'m_genParticles','std::vector<GenParticle_p6>')
        return [[member(p,'m_barcode','int'),member(p,'m_generated_mass','float'),member(p,'m_recoMethod','short')] for p in particles]

    rdo = tree(request['input_rdo'], ['RawWaveformContainer_p0_CaloNuWaveforms', 'xAOD::EventAuxInfo_v3_EventInfoAux.', 'McEventCollection_p6_BeamTruthEvent'])
    rec = tree(request['input_rec'], ['CaloNuWaveformHitsAux.', 'EventInfoAux.'])
    assert rdo.GetEntries() == rec.GetEntries() == request['phys_entries']
    assert request['phys_entries'] == request.get('expected_phys_entries',50000)
    first = int(request['group'].split('_')[1].split('-')[0])
    stem = Path(request['input_rdo']).name.split(f'-{request["run"]}-')[0]+f'-{request["run"]}-'
    all_hits, hit_offsets, records = [], [0], []
    n = len(request['cases'])
    scalars = ['integral', 'raw_integral', 'baseline_mean', 'baseline_rms', 'raw_peak', 'localtime', 'peak', 'width', 'mean', 'alpha', 'nval']
    arrays = {key: np.full((n, 4), np.nan) for key in scalars}
    arrays.update(status=np.zeros((n, 4), np.uint32), id32=np.zeros((n, 4), np.uint32),
                  adc=np.zeros((n, 4, 600), np.uint16),
                  saved_time=np.full((n, 4, 76), np.nan), saved_wave=np.full((n, 4, 76), np.nan),
                  saved_samples=np.zeros((n, 4), np.int16))
    allow_missing=request.get('allow_missing_channels',False)
    if allow_missing:
        arrays['channel_present']=np.zeros((n,4),bool)
    if a.compact_signal:
        from report_calonu_native import nominal_signal
        repo = Path(__file__).resolve().parents[1]
        conditions = json.loads((repo/'workbook/stage37_energy_ml/conditions_audit.json').read_text())
        geometry = json.loads((repo/'workbook/stage36_energy_ml/geometry_audit.json').read_text())
        digi = next(r['rows'][0]['payload'] for r in conditions['records'] if r['label'] == 'MC100049' and r['folder'] == '/WAVE/Digitization')
        parameters = {k:digi['cb_'+k] for k in ['norm','mean','sigma','alpha']}
        parameters['exponent'] = digi['cb_n']
        cable = next(r['rows'] for r in conditions['records'] if r['label'] == 'MC100049_archived')
        ids = [1+(r['payload']['row']<<1)+(r['payload']['module']<<3) for r in sorted(cable,key=lambda r:r['channel'])]
        centers = {r['hit_id']:geometry['nominal_core_centers_global_mm'][r['region']] for r in conditions['gdml_factory_module_order']}
        arrays.update(signal_nominal_ADC=np.zeros((n,4,600),np.float32), hit_energy_MeV=np.zeros((n,4)),
                      hit_count=np.zeros((n,4),int), hit_energy_outside_hist_MeV=np.zeros((n,4)))
    for j, case in enumerate(request['cases']):
        entry = case['input_entry']
        rdo.GetEntry(entry)
        rec.GetEntry(entry)
        assert info(rdo) == info(rec) == (request['run'], case['fingerprint']['eventID'])
        hp = case.get('hits_file',str(Path(request['sim_directory'])/f'{stem}{first+case["hits_subfile_ordinal"]:05}-HITS.root'))
        ht = tree(hp, ['CaloHitCollection_p1a_CaloNuHits', 'xAOD::EventAuxInfo_v3_EventInfoAux.', 'McEventCollection_p6_BeamTruthEvent'])
        assert ht.GetEntries() == request.get('hits_events_per_file',10000)
        ht.GetEntry(case['hits_entry'])
        assert info(ht) == info(rdo)
        signature = beam_signature(ht)
        rdo_signature = beam_signature(rdo)
        assert signature and len(signature) == len(rdo_signature)
        assert [p[:5] for p in signature] == [p[:5] for p in rdo_signature], (hp, entry, 'BeamTruth identity/momentum differs')
        if 'phys_neutrino_signature' in case:
            pdg,px,py,pz=case['phys_neutrino_signature']
            candidates=[p for p in signature if p[0]==pdg]
            assert any(np.allclose(p[2:5],[px,py,pz],rtol=2e-6,atol=.001) for p in candidates), (hp,entry,'PHYS neutrino differs')
        # HepMC persistence recomputes mass; the measured failures differ by one float ULP only.
        mass_difference = max(abs(p[5]-q[5]) for p, q in zip(signature, rdo_signature))
        mass_record={}
        if request.get('verify_phys_truth'):
            hi,ri=beam_identity(ht),beam_identity(rdo)
            assert [p[:2] for p in hi]==[p[:2] for p in ri], (hp,entry,'Barcode/generated mass differs')
            assert [p[2]==2 for p in hi]==[p[2]==2 for p in ri], 'Energy sign differs'
            # Re-persistence reconstructs E and recomputes signed m^2=E^2-|p|^2.
            # Near a light cone an absolute mass tolerance is ill-conditioned.
            normalized=[]
            for hp6,rp6 in zip(signature,rdo_signature):
                mh,mr=hp6[5],rp6[5]
                delta=abs(mh*abs(mh)-mr*abs(mr))
                bound=64*np.finfo(float).eps*sum(v*v for v in hp6[2:5])+4*np.finfo(np.float32).eps*max(mh*mh,mr*mr)+1e-12
                normalized.append(delta/bound)
            assert max(normalized)<1, (hp,entry,'Mass-shell change exceeds floating point bound',max(normalized))
            mass_record=dict(beam_barcode_generated_mass_equal=True,beam_mass_shell_max_bound_ratio=max(normalized),
                             beam_persistent_identity=hi)
        else:
            assert mass_difference < .001, (hp, entry, 'BeamTruth mass differs by >=1 keV')
        persistent = ht.CaloHitCollection_p1a_CaloNuHits
        h = np.asarray(list(ROOT.ReadCaloNuSensitiveHits(persistent))).reshape(-1, 9)
        # Independent energy expansion checks the unchanged native converter, including overflow coding.
        encoded = np.asarray(list(persistent.m_hitEne_2b))
        expanded = encoded.astype(float)*1e-5
        expanded[encoded == 65535] = list(persistent.m_hitEne_4b)
        np.testing.assert_allclose(h[:, 1], expanded, rtol=2e-7, atol=1e-7)
        assert np.all(np.isin(h[:, 0], [1, 3, 9, 11]))
        if a.compact_signal:
            signal,energy,count,outside = nominal_signal(h,ids,centers,parameters)
            arrays['signal_nominal_ADC'][j] = signal
            arrays['hit_energy_MeV'][j] = energy
            arrays['hit_count'][j] = count
            arrays['hit_energy_outside_hist_MeV'][j] = outside
        else:
            all_hits.append(h)
            hit_offsets.append(hit_offsets[-1]+len(h))
        waves = member(rdo.RawWaveformContainer_p0_CaloNuWaveforms, 'm_waveforms', 'std::vector<RawWaveform_p0>')
        aux = getattr(rec, 'CaloNuWaveformHitsAux.')
        channels = list(member(aux, 'channel', 'std::vector<unsigned int>'))
        statuses = list(member(aux, 'hit_status', 'std::vector<unsigned int>'))
        positions = {ch: k for k, (ch, status) in enumerate(zip(channels, statuses)) if status & 2 == 0}
        assert set(positions).issubset({20,21,22,23}) if allow_missing else set(positions)=={20,21,22,23}
        for w in waves:
            ch = member(w, 'm_channel', 'unsigned int')
            i, k = ch-20, positions[ch]
            if allow_missing:
                arrays['channel_present'][j,i]=True
            arrays['id32'][j, i] = member(w, 'm_ID', 'unsigned int')
            assert arrays['id32'][j, i] == member(aux, 'id32', 'std::vector<unsigned int>')[k]
            adc = list(member(w, 'm_adc_counts', 'std::vector<unsigned int>'))
            assert len(adc) == 600
            arrays['adc'][j, i] = adc
            arrays['status'][j, i] = statuses[k]
            for key in scalars:
                arrays[key][j, i] = member(aux, key, 'std::vector<float>')[k]
            for key, dest in [('time_vector', 'saved_time'), ('wave_vector', 'saved_wave')]:
                value = list(member(aux, key, 'std::vector<std::vector<float>>')[k])
                assert len(value) in [0, 76], (entry, ch, key, len(value))
                arrays[dest][j, i, :len(value)] = value
                arrays['saved_samples'][j, i] = len(value)
        if not allow_missing or arrays['channel_present'][j,0]:
            np.testing.assert_allclose(arrays['raw_integral'][j,0]/50,case['fingerprint']['CaloNu0_raw_charge'],atol=3e-5,rtol=0)
        else:
            assert case['fingerprint']['CaloNu0_raw_charge']==0
        records.append(dict(case, hits_file=hp, run=request['run'], group=request['group'], index=request['index'],
                            beam_signature=signature, hits_RDO_beam_momentum_equal=True,
                            beam_mass_difference_MeV=mass_difference,**mass_record))
        print('NATIVE_CASE', request['index'], entry, case['role'], 'hits', len(h), flush=True)
    if not a.compact_signal:
        arrays.update(hits=np.concatenate(all_hits), hit_offsets=np.array(hit_offsets))
    arrays.update(cases_json=np.array(json.dumps(records)), schemas_json=np.array(json.dumps(schemas)))
    metadata = dict(index=request['index'], events=n, group=request['group'],
                    locate_wall_s=request['locate_wall_s'], wall_s=time.perf_counter()-tick, cpu_s=time.process_time()-cpu,
                    peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                    input_rdo=request['input_rdo'], input_rec=request['input_rec'],
                    native_converter_energy_expansion_checked=True, layout_checksums_equal=True,
                    individual_HITS_retained=not a.compact_signal,
                    method='Read-only persistent layouts + unchanged p1a converter; no geometry or HepMC link dereference; ID helpers from ordinary runtime NOT called')
    arrays['metadata_json'] = np.array(json.dumps(metadata))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(a.output, **arrays)
    for f, _ in opened.values():
        f.Close()
    print('NATIVE_RESOURCES', json.dumps(metadata))


if __name__ == '__main__':
    main()
