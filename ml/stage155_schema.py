"""Inspect actual REC track branches and on-file streamer members; no events."""
import re
import ROOT

INPUT_KEYS = ['CKFTrackCollectionWithoutIFT', 'CKFTrackCollectionBackwardWithoutIFT']


def inspect(path):
    source = ROOT.TFile.Open(path)
    assert source and not source.IsZombie()
    track_branches = []
    trees = []
    for key in source.GetListOfKeys():
        if key.GetClassName() != 'TTree':
            continue
        tree = source.Get(key.GetName())
        trees.append(str(key.GetName()))
        for branch in tree.GetListOfBranches():
            name, cls = str(branch.GetName()), str(branch.GetClassName())
            if 'TrackCollection' in name or 'TrackCollection' in cls:
                track_branches.append(dict(tree=str(tree.GetName()), name=name, class_name=cls))
    streamers = []
    for info in source.GetStreamerInfoList():
        name = str(info.GetName())
        if name not in ['Trk::TrackCollection_tlp6', 'Trk::TrackParameters_p2']:
            continue
        streamers.append(dict(name=name, version=int(info.GetClassVersion()),
            members=[dict(name=str(e.GetName()), type=str(e.GetTypeName())) for e in info.GetElements()]))
    members = {s['name']: {e['name']: e['type'] for e in s['members']} for s in streamers}
    matched = {key: [b for b in track_branches if key in b['name'] and b['class_name'] == 'Trk::TrackCollection_tlp6']
               for key in INPUT_KEYS}
    collection_type = members.get('Trk::TrackCollection_tlp6', {}).get('m_parameters', '')
    parameter_type = members.get('Trk::TrackParameters_p2', {}).get('m_parameters', '')
    verified = all(matched.values()) and 'TrackParameters_p2' in collection_type and bool(re.match(r'^vector<float(?:>|,)', parameter_type.replace('std::', '').replace(' ', '')))
    result = dict(verified=bool(verified), REC=path, inspected_trees=trees,
        actual_track_branches=track_branches, relevant_inputs=matched, on_file_streamers=streamers,
        collection_parameter_member_type=collection_type, parameter_value_member_type=parameter_type,
        pinned_converter='d32 TrackCollectionCnv GUID3228B252-2C5D-11E8-B170-0800271C02BC -> TrackCollection_tlp6 -> TrackParametersCnv_p2; latter stores3globalposition+3momentum+charge for Curvilinear parameters',
        limitation='Schema and native float32 equality establish a representation model; no historical alignment, fit covariance calibration or discarded pre-rounding position is certified.')
    source.Close()
    return result
