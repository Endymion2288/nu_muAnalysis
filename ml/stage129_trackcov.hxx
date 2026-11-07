#include "TrkTrack/TrackCollection.h"
#include "TrkTrack/Track.h"
#include "TrkParameters/TrackParameters.h"
#include "TrkSurfaces/PlaneSurface.h"
#include "TrackerRIO_OnTrack/FaserSCT_ClusterOnTrack.h"
#include "TrackerIdentifier/FaserSCT_ID.h"
#include <vector>
#include <cmath>
#include <limits>
namespace Stage129 {
struct Tracks {std::vector<std::vector<double>> values;std::vector<std::vector<unsigned long long>> prds;};
Tracks tracks(const TrackCollection& ts,const FaserSCT_ID& helper) {
 Tracks out;
 for(const auto* t:ts) {
  if(!t||!t->trackParameters()||t->trackParameters()->empty())continue;
  auto* p=t->trackParameters()->front();auto pos=p->position(),mom=p->momentum();auto cov=p->covariance();
  const double nan=std::numeric_limits<double>::quiet_NaN();
  bool plane=dynamic_cast<const Trk::PlaneSurface*>(&p->associatedSurface())!=nullptr;
  std::vector<double> v={pos.x(),pos.y(),pos.z(),mom.x()/mom.z(),mom.y()/mom.z(),mom.z()/1000.,double(plane),double(cov!=nullptr)};
  unsigned int mask=0;std::vector<unsigned long long> prds;
  if(t->measurementsOnTrack())for(auto* m:*t->measurementsOnTrack())if(auto c=dynamic_cast<const Tracker::FaserSCT_ClusterOnTrack*>(m)) {
   mask|=1u<<helper.station(c->identify());if(c->prepRawData())prds.push_back(c->prepRawData()->identify().get_compact());
  }
  auto fit=t->fitQuality();v.push_back(mask);v.push_back(prds.size());v.push_back(fit?fit->chiSquared():nan);v.push_back(fit?fit->numberDoF():nan);
  Eigen::Matrix<double,4,5> J=Eigen::Matrix<double,4,5>::Zero();
  if(cov&&plane) {
   auto rot=p->associatedSurface().transform().linear();double tx=mom.x()/mom.z(),ty=mom.y()/mom.z();
   for(int k=0;k<2;++k){J(0,k)=rot(0,k)-tx*rot(2,k);J(1,k)=rot(1,k)-ty*rot(2,k);}
   double phi=p->parameters()[Trk::phi],theta=p->parameters()[Trk::theta];
   J(2,Trk::phi)=-sin(phi)*tan(theta);J(2,Trk::theta)=cos(phi)/(cos(theta)*cos(theta));
   J(3,Trk::phi)=cos(phi)*tan(theta);J(3,Trk::theta)=sin(phi)/(cos(theta)*cos(theta));
   Eigen::Matrix<double,4,4> c=J*(*cov)*J.transpose();for(int i=0;i<4;++i)for(int j=0;j<4;++j)v.push_back(c(i,j));
  }else for(int i=0;i<16;++i)v.push_back(nan);
  out.values.push_back(v);out.prds.push_back(prds);
 }
 return out;
}
}
