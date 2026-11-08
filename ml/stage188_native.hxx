#ifndef NU_MU_STAGE188_NATIVE_HXX
#define NU_MU_STAGE188_NATIVE_HXX
#include "TrkTrack/TrackCollection.h"
#include "TrkTrack/Track.h"
#include "TrkParameters/TrackParameters.h"
#include "TrackerRIO_OnTrack/FaserSCT_ClusterOnTrack.h"
#include "TrackerPrepRawData/FaserSCT_ClusterContainer.h"
#include "TrackerIdentifier/FaserSCT_ID.h"
#include "TrackerSimData/TrackerSimDataCollection.h"
#include "GaudiKernel/ToolHandle.h"
#include "GaudiKernel/ThreadLocalContext.h"
#include "FaserActsGeometryInterfaces/IFaserActsExtrapolationTool.h"
#include "FaserActsGeometryInterfaces/IFaserActsTrackingGeometryTool.h"
#include "Acts/Geometry/TrackingGeometry.hpp"
#include "Acts/Surfaces/PlaneSurface.hpp"
#include "Acts/Definitions/Units.hpp"
#include <nlohmann/json.hpp>
#include <set>
#include <map>
#include <cmath>
#include <limits>
namespace Stage188 {
using J = nlohmann::json;
template<class Matrix> J matrix(const Matrix& m) {
    J out=J::array();
    for(int i=0;i<m.rows();++i) { J row=J::array(); for(int j=0;j<m.cols();++j)row.push_back(m(i,j)); out.push_back(row); }
    return out;
}
inline std::set<int> contributors(const Tracker::FaserSCT_Cluster* c,const TrackerSimDataCollection* sdo) {
    std::set<int> out;
    if(sdo)for(const auto& strip:c->rdoList()) {
        auto it=sdo->find(strip);if(it==sdo->end())continue;
        for(const auto& d:it->second.getdeposits())out.insert(d.first.barcode());
    }
    return out;
}
inline std::string observe(const TrackCollection& tracks,const Tracker::FaserSCT_ClusterContainer& clusters,
                          const FaserSCT_ID& id,const TrackerSimDataCollection* sdo) {
    using namespace Acts::UnitLiterals;
    ToolHandle<IFaserActsExtrapolationTool> tool("FaserActsExtrapolationTool/Stage188Transport");
    ToolHandle<IFaserActsExtrapolationTool> control("FaserActsExtrapolationTool/Stage188NoMaterial");
    if(tool.retrieve().isFailure()||control.retrieve().isFailure())throw std::runtime_error("Stage188 transport unavailable");
    const auto& ctx=Gaudi::Hive::currentContext();
    const auto* gt=tool->trackingGeometryTool();const auto gctx=gt->getGeometryContext(ctx).context();
    auto geometry=gt->trackingGeometry();auto mapping=gt->getIdentifierMap();
    J out={{"leading",nullptr},{"start_supported",false},{"reason","no_long_track"},{"SDO_present",sdo!=nullptr},{"wafers",J::array()}};
    const Trk::Track* lead=nullptr;double maxpz=-std::numeric_limits<double>::infinity();int leadindex=-1,index=-1;
    for(const auto* t:tracks) {
        ++index;if(!t||!t->trackParameters()||t->trackParameters()->empty()||!t->measurementsOnTrack())continue;
        std::set<int> stations;
        for(const auto* m:*t->measurementsOnTrack())if(auto* c=dynamic_cast<const Tracker::FaserSCT_ClusterOnTrack*>(m))stations.insert(id.station(c->identify()));
        if(!stations.count(1)||!stations.count(2)||!stations.count(3))continue;
        double pz=t->trackParameters()->front()->momentum().z();
        if(pz>maxpz){maxpz=pz;lead=t;leadindex=index;}
    }
    if(!lead)return out.dump();
    const auto* p=lead->trackParameters()->front();auto pos=p->position();auto mom=p->momentum();
    auto cv=p->covariance();std::set<int> fittedStations,leadBarcodes;
    const Tracker::FaserSCT_Cluster* firstCluster=nullptr;std::map<int,int> barcodeHits;
    for(const auto* st:*lead->trackStateOnSurfaces()) {
        if(!st)continue;
        auto* m=dynamic_cast<const Tracker::FaserSCT_ClusterOnTrack*>(st->measurementOnTrack());if(!m)continue;
        fittedStations.insert(id.station(m->identify()));
        if(st->trackParameters()==p)firstCluster=m->prepRawData();
        if(m->prepRawData())for(int b:contributors(m->prepRawData(),sdo))++barcodeHits[b];
    }
    J bc=J::array();for(auto [b,n]:barcodeHits)bc.push_back({b,n});
    out["leading"]={{"collection_index",leadindex},{"pz0_GeV",maxpz/1000},{"position_mm",{pos.x(),pos.y(),pos.z()}},
        {"momentum_MeV",{mom.x(),mom.y(),mom.z()}},{"charge",p->charge()},{"parameters",matrix(p->parameters())},
        {"stored_covariance",cv?matrix(*cv):J(nullptr)},{"fitted_stations",fittedStations},{"barcode_cluster_counts",bc}};
    if(fittedStations.count(0)){out["reason"]="IFT_used_in_fit";return out.dump();}
    if(!cv||!cv->allFinite()){out["reason"]="missing_nonfinite_covariance";return out.dump();}
    if(!firstCluster){out["reason"]="first_parameter_has_no_measurement_plane";return out.dump();}
    auto si=mapping->find(id.wafer_id(firstCluster->identify()));
    if(si==mapping->end()){out["reason"]="source_wafer_missing_ACTS_surface";return out.dump();}
    const auto* source=geometry->findSurface(si->second);
    if(!source){out["reason"]="source_surface_missing";return out.dump();}
    Acts::Vector3 position(pos.x(),pos.y(),pos.z()),direction=mom.normalized();
    auto local=source->globalToLocal(gctx,position,direction);
    if(!local.ok()){out["reason"]="source_position_not_on_actual_surface";return out.dump();}
    const auto back=source->localToGlobal(gctx,local.value(),direction);
    double closure=(back-position).norm();
    out["source"]={{"wafer",si->first.get_compact()},{"ACTS_transform",matrix(source->transform(gctx).matrix())},
        {"Trk_measurement_transform",matrix(firstCluster->detectorElement()->transform().matrix())},
        {"position_closure_mm",closure},{"local_mm",{local.value()[0],local.value()[1]}},
        {"surface_bound_copy_recovered",true}};
    if(closure>1e-6){out["reason"]="source_position_closure_failed";return out.dump();}
    Acts::BoundVector pars=Acts::BoundVector::Zero();
    pars[Acts::eBoundLoc0]=local.value()[0];pars[Acts::eBoundLoc1]=local.value()[1];
    pars[Acts::eBoundPhi]=p->parameters()[Trk::phi];pars[Acts::eBoundTheta]=p->parameters()[Trk::theta];
    pars[Acts::eBoundQOverP]=p->parameters()[Trk::qOverP]/1_MeV;
    Acts::BoundSquareMatrix covariance=Acts::BoundSquareMatrix::Zero();covariance.topLeftCorner(5,5)=*cv;
    for(int k=0;k<6;++k){covariance(k,4)/=1_MeV;covariance(4,k)/=1_MeV;}
    covariance(Acts::eBoundTime,Acts::eBoundTime)=1.; // independent dummy time; never a measured arrival time
    Acts::BoundTrackParameters start(source->getSharedPtr(),pars,covariance,Acts::ParticleHypothesis::muon());
    out["start_supported"]=true;out["reason"]="actual_measurement_surface_recovered";
    out["source"]["ACTS_parameters"]=matrix(pars);out["source"]["ACTS_covariance"]=matrix(covariance);
    auto roundtrip=tool->propagate(ctx,start,*source,Acts::Direction::Backward,4000.);
    out["source"]["propagation_roundtrip_success"]=bool(roundtrip);
    if(roundtrip) {
        out["source"]["propagation_roundtrip_parameters"]=matrix(roundtrip->parameters());
        out["source"]["propagation_roundtrip_covariance"]=roundtrip->covariance()?matrix(*roundtrip->covariance()):J(nullptr);
    }
    for(const auto& [wafer,gid]:*mapping) {
        if(id.station(wafer)!=0)continue;
        const auto* surface=geometry->findSurface(gid);if(!surface)continue;
        J w={{"wafer",wafer.get_compact()},{"layer",id.layer(wafer)},{"side",id.side(wafer)},
             {"transform",matrix(surface->transform(gctx).matrix())},{"bounds",surface->bounds().values()},
             {"success",false},{"candidates",J::array()}};
        auto predicted=tool->propagate(ctx,start,*surface,Acts::Direction::Backward,4000.);
        if(predicted) {
            w["success"]=true;w["parameters"]=matrix(predicted->parameters());
            w["covariance"]=predicted->covariance()?matrix(*predicted->covariance()):J(nullptr);
            Acts::Vector2 xy=predicted->parameters().head<2>();
            w["inside_geometric_bounds"]=surface->bounds().inside(xy,Acts::BoundaryCheck(true));
            auto noMat=control->propagate(ctx,start,*surface,Acts::Direction::Backward,4000.);
            if(noMat)w["no_material"]={{"parameters",matrix(noMat->parameters())},
                    {"covariance",noMat->covariance()?matrix(*noMat->covariance()):J(nullptr)}};
        }
        for(const auto* collection:clusters)for(const auto* c:*collection) {
            if(id.wafer_id(c->identify())!=wafer)continue;
            J strips=J::array();for(auto strip:c->rdoList())strips.push_back(strip.get_compact());
            J candidate={{"id",c->identify().get_compact()},{"strips",strips},{"u_mm",c->localPosition()[0]},
                {"variance_mm2",c->localCovariance().rows()?J(c->localCovariance()(0,0)):J(nullptr)},
                {"contributors",contributors(c,sdo)}};
            if(predicted&&predicted->covariance()&&c->localCovariance().rows()) {
                const double r=c->localPosition()[0]-predicted->parameters()[0];
                const double S=c->localCovariance()(0,0)+(*predicted->covariance())(0,0);
                candidate["residual_mm"]=r;candidate["innovation_variance_mm2"]=S;
                if(std::isfinite(r)&&std::isfinite(S)&&S>0)candidate["pull"]=r/std::sqrt(S);
            }
            w["candidates"].push_back(candidate);
        }
        out["wafers"].push_back(w);
    }
    return out.dump();
}
}
#endif
