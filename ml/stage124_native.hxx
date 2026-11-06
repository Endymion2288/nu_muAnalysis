#ifndef NU_MU_STAGE124_NATIVE_HXX
#define NU_MU_STAGE124_NATIVE_HXX
#include "TrackerPrepRawData/FaserSCT_ClusterContainer.h"
#include "TrackerSpacePoint/FaserSCT_SpacePointContainer.h"
#include "TrackerRawData/FaserSCT_RDO_Container.h"
#include "TrackerRawData/FaserSCT3_RawData.h"
#include "TrackerRIO_OnTrack/FaserSCT_ClusterOnTrack.h"
#include "TrackerIdentifier/FaserSCT_ID.h"
#include "TrkTrack/TrackCollection.h"
#include "TrkTrack/Track.h"
#include "TrkTrack/TrackStateOnSurface.h"
#include "TrkParameters/TrackParameters.h"
#include <array>
#include <map>
#include <set>
#include <vector>
#include <limits>
#include <cmath>
#include <algorithm>
#include <iostream>
namespace Stage124 {
// Native PRD identity is the actual cluster object in the wafer collection;
// raw resources are full Identifier compact values, never hitSet or coordinates.
struct Result {
    std::vector<double> z;
    std::vector<int> clusters;
    std::vector<std::vector<double>> trackAudit;
    double leadingPz=std::numeric_limits<double>::quiet_NaN();
    int longTracks=0,sp=0,spLinks=0,spMissing=0,measurements=0,measurementMissing=0;
    int rawMissing=0,invalidStrip=0,invalidRaw=0,invalidCluster=0,duplicateClusterIdentifiers=0;
};
inline Result summarize(const Tracker::FaserSCT_ClusterContainer& clusters,
 const FaserSCT_SpacePointContainer& points,const TrackCollection& tracks,
 const FaserSCT_RDO_Container& raw,const FaserSCT_ID& id) {
    Result out;out.clusters.assign(4,0);
    static int diagnostic=0;
    constexpr int K=24;std::array<std::array<double,K>,4> s{};
    using C=Tracker::FaserSCT_Cluster;
    std::map<const C*,int> station,degree,trackUse;
    std::map<const C*,bool> leadUse;
    std::array<std::set<unsigned long long>,4> clusterStrips,rawStrips;
    std::map<unsigned long long,int> time;
    std::array<std::set<unsigned long long>,4> clusterIds;
    std::array<int,4> invalidClusterByStation{};
    for(const auto* coll:raw)for(const auto* r:*coll) {
        auto d=dynamic_cast<const FaserSCT3_RawData*>(r);if(!d)continue;
        const auto wafer=id.wafer_id(d->identify());int st=id.station(wafer),first=id.strip(d->identify());
        if(st<0||st>3)throw std::runtime_error("raw station");++s[st][0];
        for(int k=0;k<d->getGroupSize();++k) {
            if(first+k<0||first+k>=768){++out.invalidStrip;++out.invalidRaw;if(diagnostic++<10)std::cout<<"INVALID_RAW "<<d->identify().get_compact()<<" first="<<first<<" size="<<d->getGroupSize()<<std::endl;continue;}
            auto key=id.strip_id(wafer,first+k).get_compact();
            rawStrips[st].insert(key);
            auto it=time.find(key);
            if(it==time.end())time[key]=d->getTimeBin();
            else if(it->second!=d->getTimeBin())it->second=-1; // conflicting duplicate readout: unknown, never invent a time pattern
        }
    }
    for(const auto* coll:clusters)for(const C* c:*coll) {
        int st=id.station(c->identify());if(st<0||st>3)throw std::runtime_error("cluster station");
        station[c]=st;++out.clusters[st];++s[st][2];
        if(!clusterIds[st].insert(c->identify().get_compact()).second)++out.duplicateClusterIdentifiers;
        double width=c->rdoList().size();s[st][4]+=width;s[st][5]+=width*width;
        auto cv=c->localCovariance();if(cv.rows()>0&&cv(0,0)>=0)s[st][6]+=std::sqrt(cv(0,0));
        for(const auto& strip:c->rdoList()) {
            ++s[st][7];
            if(id.wafer_id(strip)!=id.wafer_id(c->identify())||id.strip(strip)<0||id.strip(strip)>767){++out.invalidStrip;++out.invalidCluster;++invalidClusterByStation[st];++out.rawMissing;++s[st][10];if(diagnostic++<10)std::cout<<"INVALID_PRD "<<c->identify().get_compact()<<" stripID="<<strip.get_compact()<<" wafer="<<id.wafer_id(c->identify()).get_compact()<<" stripwafer="<<id.wafer_id(strip).get_compact()<<" strip="<<id.strip(strip)<<std::endl;continue;}
            auto key=strip.get_compact();clusterStrips[st].insert(key);
            auto it=time.find(key);
            if(it==time.end()||it->second<0){++s[st][10];++out.rawMissing;}
            else {s[st][8]+=it->second==2;s[st][9]+=it->second==3;}
        }
    }
    for(const auto* coll:points)for(const auto* p:*coll) {
        ++out.sp;int st=id.station(id.wafer_id(p->elementIdList().first));++s[st][11];
        auto pair=p->clusterList();
        if(!pair.first){auto link=p->getElementLink1();if(link&&link->isValid())pair.first=**link;}
        if(!pair.second){auto link=p->getElementLink2();if(link&&link->isValid())pair.second=**link;}
        for(const C* c:{pair.first,pair.second}) {
            if(c&&station.count(c)){++degree[c];++out.spLinks;++s[station[c]][12];}
            else {++out.spMissing;++s[st][13];}
        }
    }
    const Trk::Track* leading=nullptr;double pz=-1e300;
    for(const auto* t:tracks) {
        if(!t||!t->trackParameters()||t->trackParameters()->empty())continue;
        std::set<int> stations;
        for(const auto* m:*t->measurementsOnTrack())if(auto c=dynamic_cast<const Tracker::FaserSCT_ClusterOnTrack*>(m))stations.insert(id.station(c->identify()));
        if(!stations.count(1)||!stations.count(2)||!stations.count(3))continue;
        ++out.longTracks;auto par=t->trackParameters()->front();double z=par->momentum().z();
        auto fit=t->fitQuality();out.trackAudit.push_back({z,par->parameters()[Trk::qOverP],par->position().x(),par->position().y(),par->position().z(),fit?fit->chiSquared():-1.,fit?double(fit->numberDoF()):-1.,double(t->measurementsOnTrack()->size())});
        if(z>pz){pz=z;leading=t;}
    }
    if(leading)out.leadingPz=pz/1000.;
    int tsosN=0,covN=0;
    for(const auto* t:tracks) {
        if(!t||!t->trackStateOnSurfaces())continue;
        std::set<const C*> owned;
        for(const auto* state:*t->trackStateOnSurfaces()) {
            if(!state)continue;
            auto cot=dynamic_cast<const Tracker::FaserSCT_ClusterOnTrack*>(state->measurementOnTrack());if(!cot)continue;
            ++out.measurements;const C* c=cot->prepRawData();int st=id.station(cot->identify());
            if(!c||!station.count(c)){++out.measurementMissing;continue;}
            owned.insert(c);if(t==leading)leadUse[c]=true;
            if(t==leading){++tsosN;++s[st][21];auto par=state->trackParameters();auto cv=par?par->covariance():nullptr;
                if(cv&&cot->localCovariance().rows()>0){double variance=(*cv)(0,0)+cot->localCovariance()(0,0);double residual=cot->localParameters()[Trk::locX]-par->parameters()[Trk::locX];
                    if(variance>0&&std::isfinite(residual)){s[st][22]+=residual*residual/variance;++s[st][23];++covN;}}
            }
        }
        for(const C* c:owned)++trackUse[c];
    }
    for(auto item:station) {
        const C* c=item.first;int st=item.second;int deg=degree[c],use=trackUse[c];
        s[st][14]+=deg>0;s[st][15]+=deg>1;s[st][16]+=std::max(0,deg-1);
        s[st][17]+=leadUse[c];s[st][18]+=use>0&&!leadUse[c];s[st][19]+=use>1;s[st][20]+=use==0;
    }
    const double nan=std::numeric_limits<double>::quiet_NaN();
    for(int st=0;st<4;++st) {
        s[st][1]=rawStrips[st].size();s[st][3]=invalidClusterByStation[st]?nan:double(clusterStrips[st].size());double n=s[st][2], strips=s[st][7];
        if(n){s[st][4]/=n;s[st][5]=std::sqrt(std::max(0.,s[st][5]/n-s[st][4]*s[st][4]));s[st][6]/=n;}
        else{s[st][4]=nan;s[st][5]=nan;s[st][6]=nan;}
        for(int k:{8,9,10})s[st][k]=strips?s[st][k]/strips:nan;
        s[st][22]=s[st][23]?std::sqrt(s[st][22]/s[st][23]):nan;
        out.z.insert(out.z.end(),s[st].begin(),s[st].end());
    }
    out.z.push_back(out.sp?double(out.spMissing)/(2*out.sp):nan);
    out.z.push_back(out.measurements?double(out.measurementMissing)/out.measurements:nan);
    out.z.push_back(tsosN?1.-double(covN)/tsosN:nan);
    // Actual fitted uncertainty, no additional first-power momentum feature.
    const auto* cv=leading?leading->trackParameters()->front()->covariance():nullptr;
    for(int i=0;i<5;++i)out.z.push_back(cv&&(*cv)(i,i)>=0?std::sqrt((*cv)(i,i)):nan);
    return out;
}
}
#endif
