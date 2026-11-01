#!/usr/bin/env python3
"""Read the nominal CaloNu DB/GDML geometry, without claiming data alignment."""
import json
import sqlite3
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from calonu_muon_control import config, output_dir, write_json


def rotation(tilt):
    c, s = np.cos(tilt), np.sin(tilt)
    rx = np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    ry = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return rx @ ry


def intersection(x, y, tx, ty, centers, rotation_matrix, half_sizes, margin=10):
    origin = np.column_stack([x, y, np.full(len(x), -3112.)])
    direction = np.column_stack([np.tan(tx), np.tan(ty), np.ones(len(x))])
    direction /= np.linalg.norm(direction, axis=1)[:, None]
    local_direction = direction @ rotation_matrix
    lengths, interior = [], []
    for center in centers:
        o = (origin - np.asarray(center)) @ rotation_matrix
        with np.errstate(divide='ignore', invalid='ignore'):
            t0 = (-np.asarray(half_sizes) - o) / local_direction
            t1 = (np.asarray(half_sizes) - o) / local_direction
            lower = np.minimum(t0, t1).max(axis=1)
            upper = np.maximum(t0, t1).min(axis=1)
            length = np.maximum(0, upper - lower)
            z0 = (-half_sizes[2] - o[:, 2]) / local_direction[:, 2]
            z1 = (half_sizes[2] - o[:, 2]) / local_direction[:, 2]
        p0, p1 = o + z0[:, None]*local_direction, o + z1[:, None]*local_direction
        inside = (np.maximum(abs(p0[:, :2]), abs(p1[:, :2])) < np.asarray(half_sizes[:2])-margin).all(axis=1)
        lengths.append(length)
        interior.append(inside & (length > 0))
    return np.column_stack(lengths), np.column_stack(interior)


def main():
    repo = Path(__file__).resolve().parents[1]
    cfg = config(repo)
    c = sqlite3.connect('file:' + cfg['geometry_db'] + '?mode=ro', uri=True)
    tag = c.execute('select TAG_ID from HVS_TAG2NODE where TAG_NAME=?', (cfg['geometry_tag'],)).fetchone()[0]
    queue, tags = [tag], []
    while queue:
        current = queue.pop()
        name = c.execute('select TAG_NAME from HVS_TAG2NODE where TAG_ID=?', (current,)).fetchone()[0]
        tags.append(dict(id=current, name=name))
        queue.extend(r[0] for r in c.execute(
            'select CHILD_TAG from HVS_LTAG2LTAG where PARENT_TAG=? and CHILD_NODE in (4,42,420,421)', (current,)))
    tid = next(t['id'] for t in tags if t['name'] == 'CaloNuTopLevel-00')
    row = c.execute('select d.* from CALONUTOPLEVEL_DATA d join CALONUTOPLEVEL_DATA2TAG t '
                    'on t.CALONUTOPLEVEL_DATA_ID=d.CALONUTOPLEVEL_DATA_ID where t.CALONUTOPLEVEL_TAG_ID=?', (tid,)).fetchone()
    assert row[4:7] == (0., 0., 0.)
    xml = subprocess.check_output(['git', '-C', cfg['source_repo'], 'show', cfg['source_commit'] + ':Calorimeter/CaloDetDescr/CaloNuGeoModel/data/CaloNu00.gdml'], text=True)
    define = ET.fromstring(xml[xml.index('<define>'):xml.index('</define>')+len('</define>')])
    constants = {}
    for item in define.findall('constant'):
        # Trusted, pinned repository GDML: arithmetic in previously defined constants only.
        constants[item.attrib['name']] = float(eval(item.attrib['value'], {'__builtins__': {}}, constants))
    r = rotation(.05)
    center = np.array(row[1:4]) + [0, 0, constants['caloNuBoxZ']]
    centers = []
    for key in ['caloNuModuleBoxTopLeftPosition', 'caloNuModuleBoxTopRightPosition', 'caloNuModuleBoxBottomLeftPosition', 'caloNuModuleBoxBottomRightPosition']:
        item = next(n for n in define.findall('position') if n.attrib['name'] == key)
        local = np.array([float(eval(item.attrib[k], {'__builtins__': {}}, constants)) for k in ['x', 'y', 'z']])
        local[2] += constants['caloNuModuleZ'] + constants['coreModuleZ']
        centers.append((center + r @ local).tolist())
    half = [constants['caloNuModuleBoxWidth']/2, constants['caloNuModuleBoxHeight']/2, constants['coreModuleLength']/2]
    # Independent analytic cases catch ray length / row versus column mistakes.
    length, inside = intersection(np.array([0., 500.]), np.array([0., 0.]), np.zeros(2), np.zeros(2), [[0, 0, -2500]], np.eye(3), half)
    np.testing.assert_allclose(length[:, 0], [432., 0.])
    np.testing.assert_array_equal(inside[:, 0], [True, False])
    write_json(output_dir(repo) / 'geometry_audit.json', dict(
        geometry_db=cfg['geometry_db'], source_commit=cfg['source_commit'], resolved_calo_tags=[t for t in tags if 'Calo' in t['name']],
        top_level_DB_row=list(row), calonu_box_center_global_mm=center.tolist(), tilt_rad=[.05, .05, 0.],
        nominal_core_centers_global_mm=centers, core_half_sizes_mm=half, rotation_matrix_RxRy=r.tolist(),
        constants=constants, analytic_ray_box_checks_passed=True,
        limitations=['Nominal DB and pinned GDML; not an in situ survey or alignment measurement',
                     'RxRy convention and opposite tilt sensitivity control, not native GeoModel transform verification',
                     'module branch to hardware/geometric identifier correspondence not independently confirmed',
                     'straight line extrapolation proxy, not a fit propagation or scattering calculation']))
    print(json.dumps(dict(center=center.tolist(), centers=centers, half=half)))


if __name__ == '__main__':
    main()
