#ifndef NU_MU_REFERENCE_COVARIANCE_AUDIT_H
#define NU_MU_REFERENCE_COVARIANCE_AUDIT_H
#include <cmath>
#include <limits>
#include <set>
#include <vector>
#include "TrkTrack/Track.h"
#include "TrkTrack/TrackCollection.h"
#include "TrkParameters/TrackParameters.h"
#include "TrackerIdentifier/FaserSCT_ID.h"
#include "TrackerRIO_OnTrack/FaserSCT_ClusterOnTrack.h"
// Exact official three-station saved-track support; do not use hitSet indexing.
inline std::vector<std::vector<double>> AuditReferenceCovariances(
    const TrackCollection& tracks, const FaserSCT_ID& helper) {
    std::vector<std::vector<double>> output;
    for (const Trk::Track* track : tracks) {
        if (!track) continue;
        std::set<int> stations;
        for (const Trk::MeasurementBase* measurement : *track->measurementsOnTrack()) {
            auto cluster = dynamic_cast<const Tracker::FaserSCT_ClusterOnTrack*>(measurement);
            if (cluster) stations.insert(helper.station(cluster->identify()));
        }
        if (!stations.count(1) || !stations.count(2) || !stations.count(3)) continue;
        auto first = track->trackParameters()->front();
        auto last = track->trackParameters()->back();
        if (!first || !last) continue;
        auto pos = first->position(); auto mom = first->momentum();
        std::vector<double> row = {pos.x(),pos.y(),pos.z(),mom.x(),mom.y(),mom.z(),first->charge(),
            double(track->info().trackFitter()),track->fitQuality()->chiSquared(),double(track->fitQuality()->numberDoF())};
        for (int i=0;i<5;++i) row.push_back(first->parameters()[i]);
        const auto* cov = first->covariance();
        for (int i=0;i<5;++i) for (int j=0;j<5;++j)
            row.push_back(cov ? (*cov)(i,j) : std::numeric_limits<double>::quiet_NaN());
        auto center=first->associatedSurface().center();
        auto normal=first->associatedSurface().normal();
        for (int i=0;i<3;++i) row.push_back(center[i]);
        for (int i=0;i<3;++i) row.push_back(normal[i]);
        output.push_back(row);
    }
    return output;
}
#endif
