// Compact replay summary: definitions from Calypso 1ec47efe NtupleDumperAlg.
#include "TrkTrack/TrackCollection.h"
#include "TrackerRIO_OnTrack/FaserSCT_ClusterOnTrack.h"
#include "TrackerIdentifier/FaserSCT_ID.h"
#include "FaserActsGeometryInterfaces/IFaserActsExtrapolationTool.h"
#include "FaserActsGeometryInterfaces/IFaserActsTrackingGeometryTool.h"
#include "GaudiKernel/ToolHandle.h"
#include "Acts/Surfaces/PlaneSurface.hpp"
#include <set>
#include <vector>

std::vector<std::vector<double>> Stage53Tracks(const TrackCollection* tracks,
                                               const FaserSCT_ID* id) {
    ToolHandle<IFaserActsExtrapolationTool> tool("FaserActsExtrapolationTool");
    if (tool.retrieve().isFailure()) throw std::runtime_error("Missing extrapolator");
    const auto& ctx=Gaudi::Hive::currentContext();
    auto gctx=tool->trackingGeometryTool()->getGeometryContext(ctx).context();
    std::vector<std::vector<double>> result;
    for (const auto* track : *tracks) {
        std::set<int> stations;
        std::set<std::pair<int,int>> layers;
        for (auto* measurement : *track->measurementsOnTrack()) {
            auto* cluster=dynamic_cast<const Tracker::FaserSCT_ClusterOnTrack*>(measurement);
            if (!cluster) continue;
            auto identifier=cluster->identify();
            stations.insert(id->station(identifier));
            layers.emplace(id->station(identifier),id->layer(identifier));
        }
        if (!stations.count(1)||!stations.count(2)||!stations.count(3)) continue;
        auto* upstream=track->trackParameters()->front();
        auto* downstream=track->trackParameters()->back();
        if (!upstream||!downstream) continue;
        auto position=upstream->position();
        auto momentum=upstream->momentum();
        std::vector<double> row={momentum.mag(),momentum.z(),double(layers.size()),
            double(track->fitQuality()->numberDoF()),track->fitQuality()->chiSquared(),
            double(int(upstream->charge())),999999.,999999.,999999.,999999.,999999.,999999.};
        Acts::BoundVector pars=Acts::BoundVector::Zero();
        pars[Acts::eBoundLoc0]=-position.y();
        pars[Acts::eBoundLoc1]=position.x();
        pars[Acts::eBoundPhi]=momentum.phi();
        pars[Acts::eBoundTheta]=momentum.theta();
        pars[Acts::eBoundQOverP]=upstream->charge()/(momentum.mag()*Acts::UnitConstants::MeV);
        auto surface=Acts::Surface::makeShared<Acts::PlaneSurface>(
            Acts::Vector3(0,0,position.z()),Acts::Vector3(0,0,1));
        Acts::BoundTrackParameters start(surface,pars,Acts::BoundSquareMatrix::Identity(),
                                         Acts::ParticleHypothesis::muon());
        for (int plane=0;plane<2;++plane) {
            auto target=Acts::Surface::makeShared<Acts::PlaneSurface>(
                Acts::Vector3(0,0,plane==0 ? -3112. : 0.),Acts::Vector3(0,0,1));
            auto propagated=tool->propagate(ctx,start,*target,Acts::Direction::Backward);
            if (!propagated) continue;
            auto pos=propagated->position(gctx);
            if (plane==0) {
                auto mom=propagated->momentum();
                row[6]=pos.x();row[7]=pos.y();
                row[8]=atan(mom.x()/mom.z());row[9]=atan(mom.y()/mom.z());
            } else {row[10]=pos.x();row[11]=pos.y();}
        }
        result.push_back(std::move(row));
    }
    return result;
}
