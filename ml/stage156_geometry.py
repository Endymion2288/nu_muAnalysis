"""Frozen Stage155 geometry conversion/independent checks, with explicit control role."""
import math
import numpy as np

station_keys = ['clusters', 'leadingOwned', 'nonleading', 'offMeasuredWafer', 'onMeasuredWafer',
                'measuredWafers', 'eligibleWafers', 'duplicateAnchors', 'eligibleCandidates',
                'candidateSurfaceMismatch', 'unusableAnchorCandidates',
                'candidateMissingElement', 'candidateInvalidRDO', 'candidateInvalidLocal', 'candidateRoundtripFailure']

def finite_json(value):
    """Preserve typed missing measurements without inventing numeric replacements."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: finite_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite_json(item) for item in value]
    return value

def snapshot(result):
    stations = [{key: int(getattr(s, key)) for key in station_keys} for s in result.stations]
    anchors = [dict(station=int(a.station), dimension=int(a.dimension), parameter_key=int(a.key),
        wafer=str(a.wafer), linked=bool(a.linked), identifier_equal=bool(a.identifierEqual),
        measurement=bool(a.measurement), outlier=bool(a.outlier), measurement_detector_same=bool(a.measurementDetectorSame),
        valid=bool(a.valid), normal_mm=float(a.normal_mm), state_locX_mm=float(a.stateLocal),
        exact_float32=bool(a.exactFloat32), plane_compatible=bool(a.planeCompatible),
        normal_min_mm=float(a.normalMin), normal_max_mm=float(a.normalMax), normal_arithmetic_margin_mm=float(a.normalMargin),
        state_locX_min_mm=float(a.stateLocalMin), state_locX_max_mm=float(a.stateLocalMax),
        state_roundtrip_mm=float(a.stateRoundtrip_mm), PRD_roundtrip_mm=float(a.PRDRoundtrip_mm),
        global_position_mm=list(a.globalPosition), wafer_local_position_mm=list(a.local), transform=list(a.transform)) for a in result.anchors]
    candidates = [dict(station=int(c.station), wafer=str(c.wafer), identifier=str(c.identifier),
        other_track_owners=int(c.otherTrackOwners), cluster_locX_mm=float(c.clusterLocal),
        state_locX_mm=float(c.stateLocal), dx_mm=float(c.dx_mm), dot_dx_mm=float(c.dotDx_mm),
        dx_min_mm=float(c.dxMin_mm), dx_max_mm=float(c.dxMax_mm),
        roundtrip_mm=float(c.roundtrip_mm), global_position_mm=list(c.globalPosition)) for c in result.candidates]
    return finite_json(dict(leading_index=int(result.leadingIndex), long_tracks=int(result.longTracks),
        pz0_GeV=float(result.leadingPz_GeV), stations=stations, anchors=anchors, candidates=candidates))

def summarize(v, case, identity):
    for anchor in v['anchors']:
        if len(anchor['global_position_mm']) != 3:
            continue
        g = np.array(anchor['global_position_mm'])
        f = g.astype(np.float32)
        assert anchor['exact_float32'] == bool(np.array_equal(g, f.astype(np.float64)))
        transform = np.array(anchor['transform']).reshape(4, 4)
        n, x = transform[:3, 2], transform[:3, 0]
        lo = (np.nextafter(f, np.float32(-np.inf)).astype(np.float64)+f.astype(np.float64))/2-g
        hi = (np.nextafter(f, np.float32(np.inf)).astype(np.float64)+f.astype(np.float64))/2-g
        lower = anchor['normal_mm']+np.minimum(n*lo, n*hi).sum()
        upper = anchor['normal_mm']+np.maximum(n*lo, n*hi).sum()
        margin = 64*np.finfo(np.float64).eps*max(1, np.abs(n*g).sum()+np.abs(n*transform[:3, 3]).sum())
        assert math.isclose(lower, anchor['normal_min_mm'], rel_tol=0, abs_tol=1e-12)
        assert math.isclose(upper, anchor['normal_max_mm'], rel_tol=0, abs_tol=1e-12)
        assert math.isclose(margin, anchor['normal_arithmetic_margin_mm'], rel_tol=2e-14, abs_tol=1e-20)
        assert anchor['plane_compatible'] == bool(anchor['exact_float32'] and lower-margin <= 0 <= upper+margin)
        assert abs(float(np.dot(n, g-transform[:3, 3]))-anchor['normal_mm']) <= 1e-8
        for key, value in [('state_locX_min_mm', anchor['state_locX_mm']+np.minimum(x*lo, x*hi).sum()),
                           ('state_locX_max_mm', anchor['state_locX_mm']+np.maximum(x*lo, x*hi).sum())]:
            assert math.isclose(anchor[key], value, rel_tol=0, abs_tol=1e-12)
    by_wafer = {a['wafer']: a for a in v['anchors'] if a['valid']}
    for row in v['candidates']:
        anchor = by_wafer[row['wafer']]
        transform = np.array(anchor['transform']).reshape(4, 4)
        python_dot = float(np.dot(transform[:3, 0], np.array(row['global_position_mm'])-anchor['global_position_mm']))
        assert math.isclose(python_dot, row['dx_mm'], rel_tol=0, abs_tol=1e-8)
        assert math.isfinite(row['dx_mm']) and math.isclose(row['dx_mm'], row['dot_dx_mm'], rel_tol=0, abs_tol=1e-8)
        assert row['roundtrip_mm'] <= 1e-8
        assert row['dx_min_mm'] <= row['dx_mm'] <= row['dx_max_mm']
    features = []
    for station, counts in enumerate(v['stations']):
        values = np.array([row['dx_mm'] for row in v['candidates'] if row['station'] == station])
        assert len(values) == counts['eligibleCandidates']
        assert counts['clusters'] == counts['leadingOwned']+counts['nonleading']
        assert counts['nonleading'] == counts['offMeasuredWafer']+counts['onMeasuredWafer']
        assert counts['onMeasuredWafer'] == sum(counts[k] for k in ['eligibleCandidates', 'candidateSurfaceMismatch',
            'candidateInvalidLocal', 'candidateRoundtripFailure', 'unusableAnchorCandidates', 'candidateMissingElement', 'candidateInvalidRDO'])
        available = identity and counts['eligibleWafers'] > 0
        defined = available and len(values) > 0
        features.append(dict(station=station, **counts, available=available,
            candidate_N=counts['eligibleCandidates'] if available else None,
            mean_abs_dx_mm=float(np.mean(np.abs(values))) if defined else None,
            min_abs_dx_mm=float(np.min(np.abs(values))) if defined else None,
            max_abs_dx_mm=float(np.max(np.abs(values))) if defined else None,
            RMS_dx_mm=float(np.sqrt(np.mean(values**2))) if defined else None,
            eligible_surface_fraction=counts['eligibleWafers']/counts['measuredWafers'] if identity and counts['measuredWafers'] else None,
            candidate_coverage_fraction=counts['eligibleCandidates']/counts['nonleading'] if identity and counts['nonleading'] else None))
    anchors = v['anchors']
    def maximum(key):
        return max((abs(a[key]) for a in anchors if a[key] is not None), default=None)
    return dict(row=case['row'], entry=case['entry'], run=case['run'], event=case['event'], role=case['role'],
        pz0_GeV=v['pz0_GeV'] if identity else None, leading_identity_known=identity, long_tracks=v['long_tracks'],
        stations=features, anchor_counts=dict(total=len(anchors), linked=sum(a['linked'] for a in anchors),
            identifier_equal=sum(a['identifier_equal'] for a in anchors), measurement=sum(a['measurement'] for a in anchors),
            measurement_detector_same=sum(a['measurement_detector_same'] for a in anchors),
            valid=sum(a['valid'] for a in anchors), dimension2_key3=sum(a['dimension'] == 2 and a['parameter_key'] == 3 for a in anchors),
            old_strict_off_plane=sum(a['normal_mm'] is not None and abs(a['normal_mm']) > 1e-6 for a in anchors),
            exact_float32=sum(a['exact_float32'] for a in anchors), plane_compatible=sum(a['plane_compatible'] for a in anchors)),
        max_abs_normal_mm=maximum('normal_mm'), max_state_roundtrip_mm=maximum('state_roundtrip_mm'),
        max_PRD_roundtrip_mm=maximum('PRD_roundtrip_mm'),
        max_normal_arithmetic_margin_mm=maximum('normal_arithmetic_margin_mm'),
        max_normal_interval_width_mm=max((a['normal_max_mm']-a['normal_min_mm'] for a in anchors), default=None),
        max_state_locX_interval_width_mm=max((a['state_locX_max_mm']-a['state_locX_min_mm'] for a in anchors), default=None),
        max_candidate_dx_interval_width_mm=max((c['dx_max_mm']-c['dx_min_mm'] for c in v['candidates']), default=None),
        independent_dx_max_delta_mm=max((abs(c['dx_mm']-c['dot_dx_mm']) for c in v['candidates']), default=None),
        max_candidate_roundtrip_mm=max((c['roundtrip_mm'] for c in v['candidates']), default=None))
