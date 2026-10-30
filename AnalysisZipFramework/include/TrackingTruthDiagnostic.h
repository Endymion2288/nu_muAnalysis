#ifndef NU_MU_TRACKING_TRUTH_DIAGNOSTIC_H
#define NU_MU_TRACKING_TRUTH_DIAGNOSTIC_H

// Athena 24.0.41 and the fixed Calypso runtime are built with HepMC3.
#ifndef HEPMC3
#define HEPMC3 1
#endif

#include <algorithm>
#include <utility>
#include <vector>
#include "TrkTrack/Track.h"
#include "TrackerRIO_OnTrack/FaserSCT_ClusterOnTrack.h"
#include "TrackerPrepRawData/FaserSCT_Cluster.h"
#include "TrackerSimData/TrackerSimDataCollection.h"
#include "xAODTruth/TruthParticleContainer.h"

// Diagnostic copy of the fixed official TrackTruthMatchingTool counting rule.
// Cross-checked against the official t_* output for every persisted long track.
inline std::vector<double> DiagnosticTrackTruth(
    const Trk::Track* track, const TrackerSimDataCollection& simData,
    const xAOD::TruthParticleContainer& particles) {
    std::vector<std::pair<int, int>> counts;
    for (const Trk::MeasurementBase* measurement : *track->measurementsOnTrack()) {
        const auto* clusterOnTrack = dynamic_cast<const Tracker::FaserSCT_ClusterOnTrack*>(measurement);
        if (!clusterOnTrack) continue;
        std::vector<int> barcodes;
        for (Identifier id : clusterOnTrack->prepRawData()->rdoList()) {
            auto found = simData.find(id);
            if (found == simData.end()) continue;
            for (const TrackerSimData::Deposit& deposit : found->second.getdeposits()) {
                int barcode = deposit.first.barcode();
                if (std::find(barcodes.begin(), barcodes.end(), barcode) != barcodes.end()) continue;
                barcodes.push_back(barcode);
                auto item = std::find_if(counts.begin(), counts.end(),
                    [barcode](const auto& count) { return count.first == barcode; });
                if (item == counts.end()) counts.emplace_back(barcode, 1);
                else ++item->second;
            }
        }
    }
    std::sort(counts.begin(), counts.end(),
        [](const auto& left, const auto& right) { return left.second > right.second; });
    if (counts.empty()) return {};
    const auto found = std::find_if(particles.begin(), particles.end(),
        [&counts](const xAOD::TruthParticle* particle) { return particle->barcode() == counts.front().first; });
    if (found == particles.end()) return {};
    const xAOD::TruthParticle* particle = *found;
    std::vector<double> result = {double(particle->barcode()), double(particle->pdgId()),
        double(counts.front().second), particle->px(), particle->py(), particle->pz()};
    for (size_t i = 0; i < particle->nParents(); ++i) {
        result.push_back(particle->parent(i)->barcode());
        result.push_back(particle->parent(i)->pdgId());
    }
    return result;
}

#endif
