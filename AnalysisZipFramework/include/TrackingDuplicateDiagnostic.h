#ifndef NU_MU_TRACKING_DUPLICATE_DIAGNOSTIC_H
#define NU_MU_TRACKING_DUPLICATE_DIAGNOSTIC_H

#include "TrackingTruthDiagnostic.h"
#include "TrackerIdentifier/FaserSCT_ID.h"
#include <set>

inline std::vector<double> DuplicateTrackSummary(
    const Trk::Track* track, const FaserSCT_ID& helper,
    const TrackerSimDataCollection& simData,
    const xAOD::TruthParticleContainer& particles) {
    std::set<std::pair<int, int>> layers;
    unsigned stations = 0;
    for (const auto* measurement : *track->measurementsOnTrack()) {
        const auto* cluster = dynamic_cast<const Tracker::FaserSCT_ClusterOnTrack*>(measurement);
        if (!cluster) continue;
        const Identifier id = cluster->identify();
        const int station = helper.station(id);
        layers.emplace(station, helper.layer(id));
        stations |= 1u << station;
    }
    const auto* first = track->trackParameters()->front();
    const auto& position = first->position();
    const auto& momentum = first->momentum();
    const auto* quality = track->fitQuality();
    // Inverse of the geoRotation basis: original = (-z', y', x').
    std::vector<double> result = {-position.z(), position.y(), position.x(),
        -momentum.z(), momentum.y(), momentum.x(), first->charge(),
        quality->chiSquared(), quality->doubleNumberDoF(),
        double(track->measurementsOnTrack()->size()), double(layers.size()),
        double(stations), double((stations & 14u) == 14u)};
    auto truth = DiagnosticTrackTruth(track, simData, particles);
    if (truth.empty()) truth = {0, 0, 0, 0, 0, 0};
    result.insert(result.end(), truth.begin(), truth.begin() + 6);
    bool neutrinoParent = false;
    for (size_t i = 7; i < truth.size(); i += 2) {
        const int pdg = std::abs(int(truth[i]));
        neutrinoParent |= pdg == 12 || pdg == 14 || pdg == 16;
    }
    result.push_back(neutrinoParent);
    return result;
}

// Keep both exact cluster identifiers and the official merge matching key.
inline std::vector<unsigned long long> DuplicateTrackHits(
    const Trk::Track* track, const FaserSCT_ID& helper, bool mergeKey) {
    std::vector<unsigned long long> result;
    for (const auto* measurement : *track->measurementsOnTrack()) {
        const auto* cluster = dynamic_cast<const Tracker::FaserSCT_ClusterOnTrack*>(measurement);
        if (!cluster) continue;
        const Identifier id = cluster->identify();
        result.push_back(mergeKey ?
            (((helper.station(id) * 3 + helper.layer(id)) * 2 + helper.side(id))
                * 10000ull + helper.strip(id)) : id.get_compact());
    }
    return result;
}
#endif
