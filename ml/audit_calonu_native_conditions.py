#!/usr/bin/env python3
"""Read conditions with the proper MC/data database instance and explicit IOVs."""
import json
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path


def main():
    from PyCool import cool
    repo = Path(__file__).resolve().parents[1]
    out = repo/'workbook/stage37_energy_ml'
    tick = time.perf_counter()
    root = Path('/cvmfs/faser.cern.ch/repo/sw/database/DBRelease/current/sqlite200')
    svc = cool.DatabaseSvcFactory.databaseService()
    records = []

    def read(file, instance, path, key, tag='', label='', channels=(20, 21, 22, 23)):
        database = svc.openDatabase(f'sqlite://;schema={root/file};dbname={instance}', True)
        folder = database.getFolder(path)
        resolved = folder.resolveTag(tag) if tag and folder.versioningMode() == cool.FolderVersioning.MULTI_VERSION else ''
        selected = []
        for obj in folder.browseObjects(key, key+1, cool.ChannelSelection.all(), resolved):
            if path == '/WAVE/Digitization' and obj.channelId() not in [0, 5]:
                continue
            payload = obj.payload()
            is_calonu = 'CableMapping' in path and payload['type'] == 'calonu'
            if path != '/WAVE/Digitization' and obj.channelId() not in channels and path != '/WAVE/DAQ/Timing' and not is_calonu:
                continue
            selected.append(dict(channel=int(obj.channelId()), since=int(obj.since()), until=int(obj.until()),
                                 payload={k: payload[k] for k in payload.keys()}))
        records.append(dict(file=str(root/file), instance=instance, folder=path, key=key,
                            global_tag=tag, resolved_tag=resolved, label=label, rows=selected))
        database.closeDatabase()
        return selected

    mc_paths = ['/WAVE/DAQ/CableMapping', '/WAVE/Digitization', '/WAVE/Calibration/MIP_ref', '/WAVE/DAQ/Range', '/WAVE/DAQ/Timing', '/WAVE/DAQ/TimingOffset']
    for run in [100049, 100050]:
        for path in mc_paths:
            read('CABP200.db' if 'CableMapping' in path else 'ALLP200.db', 'OFLP200', path,
                 run << 32, 'OFLCOND-FASER-05', f'MC{run}')
        # Original single-version cable payload predates the 2026 tag migration; compare independently.
        read('CABP200_250908.db', 'OFLP200', '/WAVE/DAQ/CableMapping', run << 32, label=f'MC{run}_archived')
    for run in [15838, 16000, 16923]:
        for path in ['/WAVE/DAQ/CableMapping', '/WAVE/Calibration/MIP_ref', '/WAVE/DAQ/Range', '/WAVE/DAQ/Timing', '/WAVE/DAQ/TimingOffset']:
            read('CABP200.db' if 'CableMapping' in path else 'ALLP200.db', 'CONDBR3', path, run << 32,
                 label=f'data{run}', channels=(20, 21, 22, 23) if run == 15838 else (6, 7, 14, 15))
    for timestamp in [1720449636, 1720450117, 1720473060, 1720473375]:
        read('ALLP200.db', 'CONDBR3', '/WAVE/Calibration/HV', timestamp*10**9, label=f'data15838_time{timestamp}')

    source = '/eos/home-x/xcheng/FASER/calypso'
    def show(path, rev='1ec47efe'):
        return subprocess.check_output(['git', '-C', source, 'show', rev+':'+path], text=True)
    checked = [
        'Calorimeter/CaloEventCnv/FaserCaloSimEventTPCnv/src/CaloHits/CaloHitCollectionCnv_p1a.cxx',
        'Calorimeter/CaloEventCnv/FaserCaloSimEventTPCnv/FaserCaloSimEventTPCnv/CaloHits/CaloHitCollection_p1a.h',
        'Waveform/WaveEventCnv/WaveEventAthenaPool/WaveEventAthenaPool/RawWaveformContainer_p0.h',
        'Waveform/WaveEventCnv/WaveEventAthenaPool/WaveEventAthenaPool/RawWaveform_p0.h',
        'xAOD/xAODFaserWaveform/xAODFaserWaveform/versions/WaveformHitAuxContainer_v1.h']
    compatibility = {path: show(path) == show(path, 'd32b0ff3') for path in checked}
    assert all(compatibility.values())
    gain_calls = {}
    for rev in ['1ec47efe', 'd0b1b2dd']:
        algo = show('Calorimeter/CaloRecAlgs/src/CaloRecAlg.cxx', rev)
        calonu = algo[algo.index('// CaloNu isn'):]
        assert 'm_recoCalibTool->reconstruct(ctx, calo_hit, correct_gain=false);' in calonu
        gain_calls[rev] = 'CaloNu explicitly passes correct_gain=false, including real data'
    gdml = show('Calorimeter/CaloDetDescr/CaloNuGeoModel/data/CaloNu00.gdml')
    # The GDML has external material entities. Only the structure is needed for numbering.
    structure = gdml[gdml.index('<structure>'):gdml.index('</structure>')+len('</structure>')]
    structure = ET.fromstring(structure)
    boxes = next(v for v in structure.findall('volume') if v.attrib['name'] == 'caloNuVolume')
    order = [p.attrib['name'] for p in boxes.findall('physvol') if p.attrib.get('name', '').startswith('caloNuModuleBox')]
    assert len(order) == 4
    mapping = []
    for i, name in enumerate(order):
        row, module = divmod(i, 2)
        mapping.append(dict(region=i, physical_volume=name, row=row, module=module,
                            hit_id=1+(row << 1)+(module << 3),
                            readout_id32=0xe0000000+(row << 28)+(module << 27)))
    value = dict(wall_s=time.perf_counter()-tick, records=records, source_commit='1ec47efe',
                 dictionary_readonly_compatibility=compatibility, gdml_factory_module_order=mapping,
                 CaloNu_gain_correction_callsite=gain_calls,
                 limitations=['Current immutable tags and archived 2025 cable payload compared; not a complete production snapshot equivalence proof',
                              'Nominal simulation geometry numbering verified from factory/GDML; data survey orientation and native GeoModel transforms not measured',
                              'Sensitive hit energyLoss contains production Birk/nonuniform correction; not uncorrected total G4 deposition'])
    (out/'conditions_audit.json').write_text(json.dumps(value, indent=2)+'\n')
    print(dict(records=len(records), wall_s=value['wall_s'], mapping=mapping))


if __name__ == '__main__':
    main()
