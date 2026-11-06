"""Freeze all available RDO sources and a uniform QGSP HITS sample, before inference."""
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage125_energy_ml'
BASE = Path('/eos/experiment/fasernu-data0/faser/sim/mc24/genie')


def main():
    sources, inventory = [], []
    tunes = [('FTF_BIC', 200104), ('FTFP_INCLXX', 200107),
             ('JEFF33', 200110), ('ENDFB8', 200113), ('QGSP_BERT', 200213)]
    rng = random.Random(2026110625)
    for tune, first in tunes:
        for delta, component in enumerate(['pi', 'k', 'charm']):
            run = first+delta
            kind = 'hits' if tune == 'QGSP_BERT' else 'rdo'
            folder, suffix = ('sim', 'HITS') if kind == 'hits' else ('phy', 'PHYS')
            paths = sorted((BASE/str(run)/folder/'master_dev').glob(f'*-{suffix}.root'))
            assert paths, run
            chosen = sorted(rng.sample(paths, min(100, len(paths)))) if kind == 'hits' else paths
            for path in chosen:
                source = dict(index=len(sources), run=run, tune=tune, component=component,
                              input=str(path), kind=kind, file_probability=len(chosen)/len(paths),
                              segment=re.search(r'-(\d{5}(?:-\d{5})?)-master_dev', path.name)[1])
                if kind == 'rdo':
                    rdo = BASE/str(run)/'rdo/master_dev'/path.name.replace('-PHYS.root', '-RDO.root')
                    assert rdo.is_file(), rdo
                    source['rdo'] = str(rdo)
                sources.append(source)
            inventory.append(dict(run=run, tune=tune, component=component, kind=kind,
                                  available_files=len(paths), selected_files=len(chosen),
                                  file_probability=len(chosen)/len(paths),
                                  selected_input_bytes=sum(p.stat().st_size for p in chosen)))
    protocol = dict(stage=125, model='frozen stage87 direct62 ensemble',
                    seeds=[2026110255, 2026110256, 2026110257], offset_log=0.025193690596001274,
                    selection='unchanged ml_low_energy_cuts.yaml; official d32 reco and merge/noIFT',
                    calibration='actual per-run COOL 03/01 ratio once; no target/residual fit',
                    primary='exclude stage87 train/cal exact incoming; one unit per incoming within tune',
                    sampling='all RDO/PHYS files; uniform 100 full HITS files per QGSP component, seed2026110625; no replacement by yield/outcome',
                    uncertainty='joint incoming-proxy bootstrap, conditional on fixed model and supplied response mixture; not full parent/source/systematic uncertainty',
                    kde_bandwidth_dex=0.08, paper_energy_edges_GeV=[0,100,300,600,1000,'inf'],
                    energy_edges_GeV=[0,50,100,200,300,400,600,800,1000,1600,3200,6400,'inf'],
                    sources=sources, inventory=inventory, new_fits=0)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'protocol.json').write_text(json.dumps(protocol, indent=2)+'\n')
    print(json.dumps(inventory, indent=2)); print('Jobs', len(sources))


if __name__ == '__main__':
    main()
