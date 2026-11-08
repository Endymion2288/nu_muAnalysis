#ifndef NU_MU_STAGE155_NATIVE_HXX
#define NU_MU_STAGE155_NATIVE_HXX
#include "stage153_native.hxx"
namespace Stage155 {
struct Anchor {
    int station=0,dimension=0,key=0;
    bool linked=false,identifierEqual=false,measurement=false,outlier=false;
    bool measurementDetectorSame=false,valid=false,exactFloat32=false,planeCompatible=false;
    std::string wafer,surfaceType;
    double normal_mm=std::numeric_limits<double>::quiet_NaN();
    double stateLocal=std::numeric_limits<double>::quiet_NaN();
    double normalMin=0.,normalMax=0.,normalMargin=0.,stateLocalMin=0.,stateLocalMax=0.;
    double stateRoundtrip_mm=std::numeric_limits<double>::quiet_NaN();
    double PRDRoundtrip_mm=std::numeric_limits<double>::quiet_NaN();
    std::vector<double> globalPosition,local,transform;
};
struct Candidate {
    int station=0,otherTrackOwners=0;
    std::string wafer,identifier;
    double clusterLocal=0.,stateLocal=0.,dx_mm=0.,dotDx_mm=0.;
    double roundtrip_mm=0.,dxMin_mm=0.,dxMax_mm=0.;
    std::vector<double> globalPosition;
};
struct Station {
    int clusters=0,leadingOwned=0,nonleading=0,offMeasuredWafer=0,onMeasuredWafer=0;
    int measuredWafers=0,eligibleWafers=0,duplicateAnchors=0,eligibleCandidates=0;
    int candidateSurfaceMismatch=0,candidateInvalidLocal=0,unusableAnchorCandidates=0;
    int candidateMissingElement=0,candidateInvalidRDO=0,candidateRoundtripFailure=0;
};
struct Result {
    double leadingPz_GeV=std::numeric_limits<double>::quiet_NaN();
    int leadingIndex=-1,longTracks=0;
    std::vector<Station> stations;
    std::vector<Anchor> anchors;
    std::vector<Candidate> candidates;
};
inline Result summarize(const Tracker::FaserSCT_ClusterContainer& clusters,
                        const TrackCollection& tracks,const FaserSCT_ID& helper) {
    using Cluster=Stage153::Cluster;
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
            if(auto* cot=dynamic_cast<const Tracker::FaserSCT_ClusterOnTrack*>(measurement))stations.insert(helper.station(cot->identify()));
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
            const auto* prd=cot->prepRawData();const bool linked=prd&&known.count(prd);
            if(linked)owned.insert(prd);
            if(track!=leading)continue;
            if(linked)leadingOwned.insert(prd);
            Anchor a;const auto wafer=helper.wafer_id(cot->identify());
            a.station=helper.station(wafer);a.wafer=std::to_string(wafer.get_compact());
            a.linked=linked;a.identifierEqual=linked&&prd->identify()==cot->identify();
            a.measurement=state->type(Trk::TrackStateOnSurface::Measurement);
            a.outlier=state->type(Trk::TrackStateOnSurface::Outlier);
            a.dimension=cot->localParameters().dimension();a.key=cot->localParameters().parameterKey();
            const auto* element=linked?prd->detectorElement():nullptr;
            const auto* par=state->trackParameters();
            if(element&&par) {
                const auto& surface=element->surface(prd->identify());const auto& transform=surface.transform();
                a.surfaceType=typeid(surface).name();
                a.measurementDetectorSame=Stage153::sameSurface(surface,cot->associatedSurface());
                const Amg::Vector3D local=transform.inverse()*par->position();
                a.normal_mm=local.z();a.stateLocal=local.x();
                a.stateRoundtrip_mm=(transform*local-par->position()).norm();
                a.PRDRoundtrip_mm=(surface.localToGlobal(prd->localPosition())-prd->globalPosition()).norm();
                for(int i=0;i<3;++i){a.globalPosition.push_back(par->position()[i]);a.local.push_back(local[i]);}
                for(int i=0;i<4;++i)for(int j=0;j<4;++j)a.transform.push_back(transform.matrix()(i,j));
                a.exactFloat32=true;
                double normalLo=0.,normalHi=0.,localLo=0.,localHi=0.,normalScale=0.;
                for(int i=0;i<3;++i) {
                    const double g=par->position()[i];const float f=static_cast<float>(g);
                    a.exactFloat32 &= std::isfinite(g)&&static_cast<double>(f)==g;
                    const double lo=(static_cast<double>(std::nextafter(f,-std::numeric_limits<float>::infinity()))+static_cast<double>(f))/2-g;
                    const double hi=(static_cast<double>(std::nextafter(f,std::numeric_limits<float>::infinity()))+static_cast<double>(f))/2-g;
                    const double n=transform.linear()(i,2),x=transform.linear()(i,0);
                    normalLo+=std::min(n*lo,n*hi);normalHi+=std::max(n*lo,n*hi);
                    localLo+=std::min(x*lo,x*hi);localHi+=std::max(x*lo,x*hi);
                    normalScale+=std::abs(n*g)+std::abs(n*transform.translation()[i]);
                }
                a.normalMin=a.normal_mm+normalLo;a.normalMax=a.normal_mm+normalHi;
                a.normalMargin=64*std::numeric_limits<double>::epsilon()*std::max(1.,normalScale);
                a.planeCompatible=a.exactFloat32&&a.normalMin-a.normalMargin<=0&&a.normalMax+a.normalMargin>=0;
                a.stateLocalMin=a.stateLocal+localLo;a.stateLocalMax=a.stateLocal+localHi;
                a.valid=a.linked&&a.identifierEqual&&a.measurement&&!a.outlier&&a.measurementDetectorSame&&
                    cot->localParameters().contains(Trk::locX)&&Stage153::validLocal(a.stateLocal)&&
                    std::isfinite(a.normal_mm)&&a.planeCompatible&&
                    a.stateRoundtrip_mm<=1e-8&&a.PRDRoundtrip_mm<=1e-8;
            }
            byWafer[wafer].push_back(result.anchors.size());result.anchors.push_back(std::move(a));
        }
        for(const auto* prd:owned)++trackUse[prd];
    }
    for(const auto& pair:byWafer) {
        auto& s=result.stations.at(helper.station(pair.first));++s.measuredWafers;
        if(pair.second.size()!=1){++s.duplicateAnchors;continue;}
        if(result.anchors[pair.second.front()].valid)++s.eligibleWafers;
    }
    for(const auto* collection:clusters)for(const auto* cluster:*collection) {
        const int station=helper.station(cluster->identify());auto& s=result.stations.at(station);
        if(leadingOwned.count(cluster)){++s.leadingOwned;continue;}
        ++s.nonleading;const auto wafer=helper.wafer_id(cluster->identify());auto found=byWafer.find(wafer);
        if(found==byWafer.end()){++s.offMeasuredWafer;continue;}
        ++s.onMeasuredWafer;
        if(found->second.size()!=1||!result.anchors[found->second.front()].valid){++s.unusableAnchorCandidates;continue;}
        const auto& a=result.anchors[found->second.front()];const auto* element=cluster->detectorElement();
        if(!element){++s.candidateMissingElement;continue;}
        bool invalid=cluster->rdoList().empty();
        for(const auto& id:cluster->rdoList())invalid|=helper.wafer_id(id)!=wafer||helper.strip(id)<0||helper.strip(id)>767;
        if(invalid){++s.candidateInvalidRDO;continue;}
        const auto& surface=element->surface(cluster->identify());const auto& transform=surface.transform();
        bool same=std::string(typeid(surface).name())==a.surfaceType;
        for(int i=0;i<4;++i)for(int j=0;j<4;++j)same&=transform.matrix()(i,j)==a.transform[4*i+j];
        if(!same){++s.candidateSurfaceMismatch;continue;}
        const double local=cluster->localPosition()[Trk::locX];
        if(!Stage153::validLocal(local)){++s.candidateInvalidLocal;continue;}
        const double roundtrip=(surface.localToGlobal(cluster->localPosition())-cluster->globalPosition()).norm();
        if(!std::isfinite(roundtrip)||roundtrip>1e-8){++s.candidateRoundtripFailure;continue;}
        Candidate c;c.station=station;c.otherTrackOwners=trackUse[cluster];c.wafer=a.wafer;
        c.identifier=std::to_string(cluster->identify().get_compact());c.clusterLocal=local;c.stateLocal=a.stateLocal;
        c.dx_mm=local-a.stateLocal;c.roundtrip_mm=roundtrip;
        c.dxMin_mm=local-a.stateLocalMax;c.dxMax_mm=local-a.stateLocalMin;
        const Amg::Vector3D position(a.globalPosition[0],a.globalPosition[1],a.globalPosition[2]);
        c.dotDx_mm=transform.linear().col(0).dot(cluster->globalPosition()-position);
        for(int i=0;i<3;++i)c.globalPosition.push_back(cluster->globalPosition()[i]);
        ++s.eligibleCandidates;result.candidates.push_back(std::move(c));
    }
    return result;
}
}
#endif
