#ifndef NU_MU_STAGE153_NATIVE_HXX
#define NU_MU_STAGE153_NATIVE_HXX
#include "stage124_native.hxx"
#include "TrackerReadoutGeometry/SiDetectorElement.h"
#include "TrkSurfaces/Surface.h"
#include <string>
#include <typeinfo>
namespace Stage153 {
using Cluster=Tracker::FaserSCT_Cluster;
struct Candidate {
    int station=0,layer=0,side=0,otherTrackOwners=0;
    std::string identifier,wafer;
    double local=0.,stateLocal=0.,variance=0.,stateVariance=0.,r2=0.;
    double globalRoundtrip_mm=0.;
};
struct Anchor {
    int station=0,layer=0,side=0,dimension=0,key=0;
    bool linked=false,identifierEqual=false,measurement=false,outlier=false,sameSurface=false,valid=false;
    std::string wafer,measurementType,stateType,parameterType;
    double surfaceMaxDifference=std::numeric_limits<double>::quiet_NaN();
    double stateLoc1=std::numeric_limits<double>::quiet_NaN(),measurementLoc1=std::numeric_limits<double>::quiet_NaN();
    double stateVariance=std::numeric_limits<double>::quiet_NaN(),measurementVariance=std::numeric_limits<double>::quiet_NaN();
    double positionRoundtrip_mm=std::numeric_limits<double>::quiet_NaN();
    std::vector<double> parameters,covariance,measurementTransform,stateTransform;
};
struct Station {
    int clusters=0,leadingOwned=0,nonleading=0,offMeasuredWafer=0,onMeasuredWafer=0;
    int measuredWafers=0,eligibleWafers=0,duplicateAnchors=0,eligibleCandidates=0;
    int candidateSurfaceMismatch=0,candidateInvalidVariance=0,unusableAnchorCandidates=0;
    int candidateMissingElement=0,candidateInvalidRDO=0;
};
struct Result {
    double leadingPz_GeV=std::numeric_limits<double>::quiet_NaN();
    int leadingIndex=-1,longTracks=0,missingLeadingLinks=0;
    std::vector<Station> stations;
    std::vector<Anchor> anchors;
    std::vector<Candidate> candidates;
};
inline bool sameSurface(const Trk::Surface& a,const Trk::Surface& b) {
    return typeid(a)==typeid(b) && (a.transform().matrix().array()==b.transform().matrix().array()).all();
}
inline bool validLocal(double value) {
    return std::isfinite(value)&&value!=-999.&&value!=-9999.&&value!=-99999.;
}
inline Result summarize(const Tracker::FaserSCT_ClusterContainer& clusters,
                       const TrackCollection& tracks,const FaserSCT_ID& helper) {
    Result result;result.stations.resize(4);
    std::set<const Cluster*> known,leadingOwned;
    std::map<const Cluster*,int> trackUse;
    for(const auto* collection:clusters)for(const auto* cluster:*collection) {
        known.insert(cluster);++result.stations.at(helper.station(cluster->identify())).clusters;
    }
    const Trk::Track* leading=nullptr;double best=-1e300;int index=-1;
    for(const auto* track:tracks) {
        ++index;if(!track||!track->trackParameters()||track->trackParameters()->empty()||!track->measurementsOnTrack())continue;
        std::set<int> stations;
        for(const auto* measurement:*track->measurementsOnTrack())
            if(auto* cluster=dynamic_cast<const Tracker::FaserSCT_ClusterOnTrack*>(measurement))
                stations.insert(helper.station(cluster->identify()));
        if(stations.count(1)&&stations.count(2)&&stations.count(3)) {
            ++result.longTracks;const auto* par=track->trackParameters()->front();
            if(par&&par->momentum().z()>best){best=par->momentum().z();leading=track;result.leadingIndex=index;}
        }
    }
    if(leading)result.leadingPz_GeV=best/1000.;
    std::map<Identifier,std::vector<size_t>> byWafer;
    for(const auto* track:tracks) {
        if(!track||!track->trackStateOnSurfaces())continue;
        std::set<const Cluster*> owned;
        for(const auto* state:*track->trackStateOnSurfaces()) {
            if(!state)continue;
            auto* cot=dynamic_cast<const Tracker::FaserSCT_ClusterOnTrack*>(state->measurementOnTrack());
            if(!cot)continue;
            const auto* prd=cot->prepRawData();bool linked=prd&&known.count(prd);
            if(linked)owned.insert(prd);
            if(track!=leading)continue;
            if(linked)leadingOwned.insert(prd);else ++result.missingLeadingLinks;
            Anchor anchor;
            anchor.station=helper.station(cot->identify());anchor.layer=helper.layer(cot->identify());anchor.side=helper.side(cot->identify());
            const auto wafer=helper.wafer_id(cot->identify());anchor.wafer=std::to_string(wafer.get_compact());
            anchor.linked=linked;anchor.identifierEqual=linked&&prd->identify()==cot->identify();
            anchor.measurement=state->type(Trk::TrackStateOnSurface::Measurement);
            anchor.outlier=state->type(Trk::TrackStateOnSurface::Outlier);
            anchor.dimension=cot->localParameters().dimension();anchor.key=cot->localParameters().parameterKey();
            anchor.measurementType=typeid(cot->associatedSurface()).name();
            auto measurementMatrix=cot->associatedSurface().transform().matrix();
            for(int i=0;i<4;++i)for(int j=0;j<4;++j)anchor.measurementTransform.push_back(measurementMatrix(i,j));
            const auto* par=state->trackParameters();const auto* covariance=par?par->covariance():nullptr;
            if(par) {
                anchor.parameterType=typeid(*par).name();anchor.stateType=typeid(par->associatedSurface()).name();
                auto stateMatrix=par->associatedSurface().transform().matrix();
                anchor.surfaceMaxDifference=(stateMatrix-measurementMatrix).cwiseAbs().maxCoeff();
                anchor.sameSurface=sameSurface(cot->associatedSurface(),par->associatedSurface());
                for(int i=0;i<4;++i)for(int j=0;j<4;++j)anchor.stateTransform.push_back(stateMatrix(i,j));
                for(int i=0;i<5;++i)anchor.parameters.push_back(par->parameters()[i]);
                if(covariance)for(int i=0;i<5;++i)for(int j=0;j<5;++j)anchor.covariance.push_back((*covariance)(i,j));
                if(anchor.sameSurface) {
                    const Amg::Vector2D local(par->parameters()[Trk::locX],par->parameters()[Trk::locY]);
                    anchor.positionRoundtrip_mm=(par->associatedSurface().localToGlobal(local,par->momentum())-par->position()).norm();
                }
            }
            if(cot->localParameters().contains(Trk::locX))anchor.measurementLoc1=cot->localParameters()[Trk::locX];
            if(cot->localCovariance().rows())anchor.measurementVariance=cot->localCovariance()(0,0);
            if(par)anchor.stateLoc1=par->parameters()[Trk::locX];
            if(covariance)anchor.stateVariance=(*covariance)(0,0);
            anchor.valid=anchor.linked&&anchor.identifierEqual&&anchor.measurement&&!anchor.outlier&&anchor.dimension==1&&anchor.key==1&&anchor.sameSurface&&
                         covariance&&covariance->allFinite()&&validLocal(anchor.stateLoc1)&&
                         validLocal(anchor.measurementLoc1)&&anchor.stateVariance>0&&
                         std::isfinite(anchor.measurementVariance)&&anchor.measurementVariance>0;
            byWafer[wafer].push_back(result.anchors.size());result.anchors.push_back(std::move(anchor));
        }
        for(const auto* prd:owned)++trackUse[prd];
    }
    for(const auto& item:byWafer) {
        auto& station=result.stations.at(helper.station(item.first));++station.measuredWafers;
        if(item.second.size()!=1){++station.duplicateAnchors;continue;}
        if(result.anchors[item.second.front()].valid)++station.eligibleWafers;
    }
    for(const auto* collection:clusters)for(const auto* cluster:*collection) {
        int stationIndex=helper.station(cluster->identify());auto& station=result.stations.at(stationIndex);
        if(leadingOwned.count(cluster)){++station.leadingOwned;continue;}
        ++station.nonleading;const auto wafer=helper.wafer_id(cluster->identify());
        auto found=byWafer.find(wafer);
        if(found==byWafer.end()){++station.offMeasuredWafer;continue;}
        ++station.onMeasuredWafer;
        if(found->second.size()!=1||!result.anchors[found->second.front()].valid){++station.unusableAnchorCandidates;continue;}
        const auto& anchor=result.anchors[found->second.front()];
        const auto* element=cluster->detectorElement();
        if(!element){++station.candidateMissingElement;continue;}
        bool invalidRDO=false;
        for(const auto& id:cluster->rdoList())
            invalidRDO |= helper.wafer_id(id)!=wafer||helper.strip(id)<0||helper.strip(id)>767;
        if(invalidRDO){++station.candidateInvalidRDO;continue;}
        const auto* cotSurface=&element->surface(cluster->identify());
        bool same=true;
        for(int i=0;i<4;++i)for(int j=0;j<4;++j)
            same &= cotSurface->transform().matrix()(i,j)==anchor.measurementTransform[4*i+j];
        same= same && std::string(typeid(*cotSurface).name())==anchor.measurementType;
        if(!same){++station.candidateSurfaceMismatch;continue;}
        const double local=cluster->localPosition()[Trk::locX];
        const double variance=cluster->localCovariance().rows()?cluster->localCovariance()(0,0):std::numeric_limits<double>::quiet_NaN();
        if(!validLocal(local)||!std::isfinite(variance)||variance<=0){++station.candidateInvalidVariance;continue;}
        Candidate candidate;candidate.station=stationIndex;candidate.layer=helper.layer(cluster->identify());candidate.side=helper.side(cluster->identify());
        candidate.identifier=std::to_string(cluster->identify().get_compact());candidate.wafer=anchor.wafer;
        candidate.otherTrackOwners=trackUse[cluster];candidate.local=local;candidate.stateLocal=anchor.stateLoc1;
        candidate.variance=variance;candidate.stateVariance=anchor.stateVariance;
        candidate.r2=(local-anchor.stateLoc1)*(local-anchor.stateLoc1)/(variance+anchor.stateVariance);
        candidate.globalRoundtrip_mm=(cotSurface->localToGlobal(cluster->localPosition())-cluster->globalPosition()).norm();
        ++station.eligibleCandidates;result.candidates.push_back(std::move(candidate));
    }
    return result;
}
}
#endif
