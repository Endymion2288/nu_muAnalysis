"""Independent PHYS selection and empty-safe truth diagnostics for Stage112."""
import re

import awkward as ak
import numpy as np

SCINT = ['VetoNu0', 'VetoNu1', 'Veto10', 'Veto20', 'Veto21']
SCINT += [f'Timing{i}' for i in range(4)] + ['Preshower0', 'Preshower1']
TRUTH = ['pdg', 'barcode', 'px', 'py', 'pz', 'm', 'prod_x', 'prod_y', 'prod_z',
         'dec_x', 'dec_y', 'dec_z']
TRACK = ['pz0', 'px0', 'py0', 'nLayers', 'nDoF', 'Chi2', 'r_atMaxRadius',
         'X_atVetoStation2', 'Y_atVetoStation2', 'X_atVetoNu', 'Y_atVetoNu',
         'Y_atTrig', 'charge']
MATCH = ['t_pdg', 't_barcode', 't_pdg_parent', 't_barcode_parent']
BRANCHES = ['run', 'eventID', 'longTracks'] + ['truth_'+k for k in TRUTH]
BRANCHES += ['Track_'+k for k in TRACK] + MATCH
BRANCHES += [s+'_'+k for s in SCINT for k in ['charge', 'raw_charge', 'status']]
BRANCHES += ['VetoNu0_reduced_charge', 'VetoNu1_reduced_charge']


def first(a):
    return ak.to_numpy(ak.fill_none(ak.firsts(a), np.nan)).astype(float)


def lead(a, idx):
    # firsts on an option-index preserves empty rows; flatten would drop them.
    return ak.to_numpy(ak.fill_none(ak.firsts(a[idx]), np.nan)).astype(float)


def flag_name(name):
    for a, b in [('<=', 'leq'), ('>=', 'geq'), ('==', 'eq'), ('=', 'eq'),
                 ('<', 'lt'), ('>', 'gt'), (' ', '_'), ('&&', 'and'), ('||', 'or'),
                 ('&', 'and'), ('|', 'or'), ('!', 'not'), ('(', ''), (')', ''),
                 ('.', '_'), ('/', '_'), ('\\', '_'), ('[', '_'), (']', '_'),
                 ('-', 'minus'), ('+', 'plus'), ('*', 'times'), ('%', 'percent'), ('^', 'caret')]:
        name = name.replace(a, b)
    return 'passed_'+name


def active_cuts(config):
    # The manifest has no aux paths. Native reduced branches are required, never
    # silently switch to raw/no-reduced or synthesize an aux lookup.
    return [(n, c) for n, c in config['Cuts'].items()
            if c.get('data_type', 'ALL') != 'DATA'
            and all(r in ['reduced_charge', 'native_reduced_charge'] for r in c.get('requires', []))]


def derive(a):
    n = len(a)
    nt = ak.num(a.Track_pz0)
    for k in ['Track_'+x for x in TRACK] + MATCH:
        if bool(ak.any(ak.num(a[k]) != nt)):
            raise ValueError('Track/matching alignment: '+k)
    for k in TRUTH:
        if bool(ak.any(ak.num(a['truth_'+k]) != ak.num(a.truth_pdg))):
            raise ValueError('Truth alignment: '+k)
    idx = ak.argmax(a.Track_pz0, axis=1, keepdims=True, mask_identity=True)
    d = {k: lead(a['Track_'+k], idx) for k in TRACK}
    d.update(run=ak.to_numpy(a.run), eventID=ak.to_numpy(a.eventID),
             no_track=ak.to_numpy(nt == 0), lead_index=first(idx))
    # These PHYS vectors are doubles; check rather than introduce a precision
    # change if a future source uses float vector arithmetic in the C++ helpers.
    typ = str(ak.type(ak.flatten(a.Track_pz0)))
    if 'float64' not in typ:
        raise ValueError('Unvalidated native track arithmetic type: '+typ)
    incoming = np.column_stack([first(a['truth_'+k]) for k in ['pdg', 'px', 'py', 'pz']])
    d['incoming'] = incoming
    d['E'] = np.sqrt(sum(first(a['truth_'+k])**2 for k in ['px', 'py', 'pz', 'm']))/1000
    d['pz'] = d['pz0']/1000
    d['vertex_z'] = first(a.truth_dec_z)
    d['vertex_r'] = np.hypot(first(a.truth_dec_x), first(a.truth_dec_y))
    for s in SCINT:
        for k in ['charge', 'raw_charge', 'status']:
            d[s+'_'+k] = ak.to_numpy(a[s+'_'+k]).astype(float)
    for k in ['VetoNu0_reduced_charge', 'VetoNu1_reduced_charge']:
        d[k] = ak.to_numpy(a[k]).astype(float)
    with np.errstate(divide='ignore', invalid='ignore'):
        d['chi2ndf'] = d['Chi2']/d['nDoF']
        d['theta'] = np.arctan(np.sqrt(d['px0']**2+d['py0']**2)/d['pz0'])*1000
    d['rIFT'] = np.hypot(d['X_atVetoStation2'], d['Y_atVetoStation2'])
    d['rVetoNu'] = np.hypot(d['X_atVetoNu'], d['Y_atVetoNu'])
    for key in ['nDoF', 'nLayers', 'Chi2', 'r_atMaxRadius', 'rIFT', 'rVetoNu', 'theta']:
        d['invalid_'+key] = ~np.isfinite(d[key]) | (d[key] < 0)
        if key in ['nDoF', 'nLayers']:
            d['invalid_'+key] |= (d[key] >= 4294967295) | (d[key] != np.floor(d[key]))
    d['invalid_chi2ndf'] = ~np.isfinite(d['chi2ndf']) | (d['chi2ndf'] < 0)
    pdg0 = first(a.truth_pdg)
    candidate = a.truth_pdg == pdg0*13/14
    for axis in 'xyz':
        candidate = candidate & (abs(a['truth_prod_'+axis]-first(a['truth_dec_'+axis])) <= .0001)
    nc = ak.to_numpy(ak.sum(candidate, axis=1))
    valid = nc == 1
    primary = {k: first(a['truth_'+k][candidate]) for k in ['pdg', 'barcode', 'px', 'py', 'pz', 'm']}
    for v in primary.values():
        v[~valid] = np.nan
    emu = np.sqrt(sum(primary[k]**2 for k in ['px', 'py', 'pz', 'm']))/1000
    confirmed = valid & ~d['no_track']
    for k, v in [('t_pdg', primary['pdg']), ('t_barcode', primary['barcode']),
                 ('t_pdg_parent', pdg0), ('t_barcode_parent', first(a.truth_barcode))]:
        confirmed &= lead(a[k], idx) == v
    d.update(primary_valid=valid, primary_candidates=nc, confirmed=confirmed, Emu=emu)
    with np.errstate(divide='ignore', invalid='ignore'):
        d['y'] = 1-emu/d['E']
        d['error'] = np.log(d['pz']/(.8*d['E']))
        d['r'] = np.log(d['pz']/emu)
        d['u'] = np.log(emu/d['E'])
    x, y, z = [first(a['truth_dec_'+k]) for k in 'xyz']
    # C++ fiducial helper accepts float coordinates and uses float constants.
    xf, yf, zf = [v.astype('float32') for v in [x, y, z]]
    box = (xf > -115) & (xf < 135) & (yf > -171) & (yf < 129) & (zf > -3000) & (zf < -1950)
    block = (xf > -300) & (xf < 300) & (yf > -300) & (yf < 300) & (zf > np.float32(-1769.65)) & (zf < np.float32(-1619.65))
    run = d['run']
    calonu = ((run >= 200137) & (run <= 200147)) | ((run >= 200172) & (run <= 200183))
    bottom = d['Timing0_charge']+d['Timing1_charge']
    top = d['Timing2_charge']+d['Timing3_charge']
    ty = d['Y_atTrig']
    known = {}
    def cut(name, mask, value=None, invalid=None):
        known[name] = (np.asarray(mask, bool), np.zeros(n, bool) if invalid is None else invalid)
    cut('Remove CaloNu PMT region (truth)', ~calonu | (calonu & ~((z >= -2928) & (z <= -2812))), z, ~np.isfinite(z))
    cut('CC events only', ak.to_numpy(ak.any((abs(a.truth_pdg) == 11) | (abs(a.truth_pdg) == 13) | (abs(a.truth_pdg) == 15), axis=1)), invalid=ak.to_numpy(ak.num(a.truth_pdg) == 0))
    cut('nu_mu only', abs(pdg0) == 14, invalid=~np.isfinite(pdg0))
    cut('In Faser Nu Box or Lead Block', box | block, invalid=~np.isfinite(x+y+z))
    cut('Truth dec r < 100 mm', d['vertex_r'] < 100, invalid=~np.isfinite(d['vertex_r']))
    cut('Truth pz > 50 GeV', incoming[:, 3]/1000 > 50, invalid=~np.isfinite(incoming[:, 3]))
    long = ak.to_numpy(a.longTracks)
    cut('At least one long track', long > 0, invalid=(long < 0) | (long >= 4294967295))
    cut('Veto20 and Veto21 charge > 40 pC', (d['Veto20_charge'] > 40) & (d['Veto21_charge'] > 40), invalid=~np.isfinite(d['Veto20_charge']+d['Veto21_charge']))
    timing = ((ty > 20) & (top > 20)) | ((ty < -20) & (bottom > 20)) | ((abs(ty) < 20) & (top+bottom > 20))
    cut('Timing Station Charge > 20 pC', timing, invalid=~np.isfinite(ty+top+bottom))
    cut('Preshower Charge > 2.5 pC', (d['Preshower0_charge'] > 2.5) & (d['Preshower1_charge'] > 2.5), invalid=~np.isfinite(d['Preshower0_charge']+d['Preshower1_charge']))
    cut('Track pz > 50 GeV', d['pz'] > 50, invalid=~np.isfinite(d['pz']) | (d['pz'] <= 0))
    for name, key, op, value in [
            ('Leading track has at >= 7 layers', 'nLayers', 'ge', 7),
            ('Track nDoF >= 9', 'nDoF', 'ge', 9),
            ('Leading track has chi2/ndof < 15', 'chi2ndf', 'lt', 15),
            ('Track R at max radius < 95 mm', 'r_atMaxRadius', 'lt', 95),
            ('Track R at IFT < 95 mm', 'rIFT', 'lt', 95),
            ('Track rVetoNu < 120 mm', 'rVetoNu', 'lt', 120),
            ('Leading track theta < 25 mrad', 'theta', 'lt', 25)]:
        cut(name, d[key] >= value if op == 'ge' else d[key] < value, invalid=d['invalid_'+key])
    for j in range(2):
        q = d[f'VetoNu{j}_reduced_charge']
        cut(f'VetoNu{j} reduced charge < 30 pC', q < 30, invalid=~np.isfinite(q) | (q < 0))
    assert all(len(v) == n for v in d.values())
    return d, known


def minimal_definitions(repo, cuts):
    import yaml
    base = yaml.safe_load((repo/'AnalysisZipFramework/config/definitions.yaml').read_text())['Definitions']
    base.update(yaml.safe_load((repo/'AnalysisZipFramework/config/ml_definitions.yaml').read_text())['Definitions'])
    wanted = {'LeadTrack_Idx', 'LeadTrack_pz0', 'ML_truth_E_GeV'}
    pending = [c['expression'] for _, c in cuts]
    pending += list(wanted)
    while pending:
        for name in re.findall(r'\b[A-Za-z_]\w*\b', pending.pop()):
            if name in base and name not in wanted:
                wanted.add(name)
                pending.append(base[name]['expression'])
    # Seed output expressions also need their dependencies.
    for name in list(wanted):
        pending.append(base[name]['expression'])
    while pending:
        for name in re.findall(r'\b[A-Za-z_]\w*\b', pending.pop()):
            if name in base and name not in wanted:
                wanted.add(name)
                pending.append(base[name]['expression'])
    return {'Definitions': {k: v for k, v in base.items() if k in wanted}}
