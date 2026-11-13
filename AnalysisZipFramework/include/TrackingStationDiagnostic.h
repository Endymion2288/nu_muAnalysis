#ifndef NU_MU_TRACKING_STATION_DIAGNOSTIC_H
#define NU_MU_TRACKING_STATION_DIAGNOSTIC_H
#include "TrackingDuplicateDiagnostic.h"

inline std::vector<double> StationTrackSummary(
    const Trk::Track* track, const FaserSCT_ID& helper,
    const TrackerSimDataCollection& sim, const xAOD::TruthParticleContainer& particles,
    bool rotated) {
    auto result = DuplicateTrackSummary(track, helper, sim, particles);
    if (!rotated) {
        const auto* first = track->trackParameters()->front();
        const auto& p = first->position();
        const auto& q = first->momentum();
        result[0] = p.x(); result[1] = p.y(); result[2] = p.z();
        result[3] = q.x(); result[4] = q.y(); result[5] = q.z();
    }
    return result;
}

inline std::vector<double> StationTrackStates(const Trk::Track* track, bool rotated) {
    std::vector<double> result;
    for (const auto* state : *track->trackStateOnSurfaces()) {
        const auto* parameters = state->trackParameters();
        if (!parameters) continue;
        const auto& p = parameters->position();
        const auto& q = parameters->momentum();
        if (rotated) result.insert(result.end(), {-p.z(), p.y(), p.x(), -q.z(), q.y(), q.x()});
        else result.insert(result.end(), {p.x(), p.y(), p.z(), q.x(), q.y(), q.z()});
    }
    return result;
}
#endif
