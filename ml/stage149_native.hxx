#include "stage124_native.hxx"
#include "TrkSurfaces/PlaneSurface.h"
#include <typeinfo>
#include "WaveformConditionsTools/IWaveformCableMappingTool.h"
#include "GaudiKernel/ToolHandle.h"
#include "ScintIdentifier/VetoID.h"
namespace Stage149 {
std::vector<std::vector<std::string>> mapping(const VetoID& veto) {
    ToolHandle<IWaveformCableMappingTool> tool("WaveformCableMappingTool/WaveformCableMappingTool");
    if(tool.retrieve().isFailure())throw std::runtime_error("Actual cable mapping unavailable");
    std::vector<std::vector<std::string>> result;
    for(const auto& item:tool->getCableMapping()) {
        auto type=item.second.first;
        if(type=="veto")type+=std::to_string(veto.station(item.second.second)+1);
        result.push_back({std::to_string(item.first),type,std::to_string(item.second.second.get_compact())});
    }
    return result;
}
struct State {
    std::vector<double> values, parameters, covariance, transform;
    std::vector<unsigned long long> prds;
    std::vector<std::vector<double>> measurements;
    std::string parameterType, surfaceType;
    int longIndex=-1, collectionIndex=-1, layers=0;
};
std::vector<State> states(const TrackCollection& tracks,const FaserSCT_ID& helper,
 const Tracker::FaserSCT_ClusterContainer& clusters) {
    std::set<const Tracker::FaserSCT_Cluster*> known;
    std::map<const Tracker::FaserSCT_Cluster*,int> use;
    for(const auto* c:clusters)for(const auto* p:*c)known.insert(p);
    for(const auto* t:tracks) {
        std::set<const Tracker::FaserSCT_Cluster*> own;
        if(t&&t->trackStateOnSurfaces())for(const auto* s:*t->trackStateOnSurfaces()) {
            auto c=s?dynamic_cast<const Tracker::FaserSCT_ClusterOnTrack*>(s->measurementOnTrack()):nullptr;
            if(c&&c->prepRawData()&&known.count(c->prepRawData()))own.insert(c->prepRawData());
        }
        for(auto* c:own)++use[c];
    }
    std::vector<State> out;int index=-1;
    const double nan=std::numeric_limits<double>::quiet_NaN();
    for(const auto* t:tracks) {
        ++index;if(!t||!t->trackParameters()||t->trackParameters()->empty()||!t->measurementsOnTrack())continue;
        std::set<int> stations;std::set<std::pair<int,int>> layers;
        for(auto* m:*t->measurementsOnTrack())if(auto* c=dynamic_cast<const Tracker::FaserSCT_ClusterOnTrack*>(m)) {
            stations.insert(helper.station(c->identify()));layers.insert({helper.station(c->identify()),helper.layer(c->identify())});
        }
        if(!stations.count(1)||!stations.count(2)||!stations.count(3))continue;
        const auto* p=t->trackParameters()->front();if(!p)continue;
        State v;v.longIndex=out.size();v.collectionIndex=index;v.layers=layers.size();
        auto x=p->position(),mom=p->momentum();auto fit=t->fitQuality();
        v.values={x.x(),x.y(),x.z(),mom.x(),mom.y(),mom.z(),p->charge(),
                  fit?fit->chiSquared():nan,fit?double(fit->numberDoF()):nan};
        v.parameterType=typeid(*p).name();v.surfaceType=typeid(p->associatedSurface()).name();
        for(int i=0;i<5;++i)v.parameters.push_back(p->parameters()[i]);
        const auto* cov=p->covariance();
        if(cov)for(int i=0;i<5;++i)for(int j=0;j<5;++j)v.covariance.push_back((*cov)(i,j));
        auto matrix=p->associatedSurface().transform().matrix();
        for(int i=0;i<4;++i)for(int j=0;j<4;++j)v.transform.push_back(matrix(i,j));
        if(t->trackStateOnSurfaces())for(const auto* s:*t->trackStateOnSurfaces()) {
            if(!s)continue;
            const auto* c=dynamic_cast<const Tracker::FaserSCT_ClusterOnTrack*>(s->measurementOnTrack());
            if(!c)continue;
            const auto* prd=c->prepRawData();bool linked=prd&&known.count(prd);
            if(linked)v.prds.push_back(prd->identify().get_compact());
            const auto* par=s->trackParameters();auto cv=par?par->covariance():nullptr;
            v.measurements.push_back({double(helper.station(c->identify())),double(helper.layer(c->identify())),
                double(helper.side(c->identify())),double(linked),double(linked?use[prd]:0),
                double(s->type(Trk::TrackStateOnSurface::Measurement)),double(s->type(Trk::TrackStateOnSurface::Outlier)),
                double(cv!=nullptr),c->localParameters()[Trk::locX],
                par?par->parameters()[Trk::locX]:nan,c->localCovariance()(0,0),cv?(*cv)(0,0):nan});
        }
        out.push_back(v);
    }
    return out;
}
}
