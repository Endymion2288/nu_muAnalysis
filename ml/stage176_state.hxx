// Read-only native upstream state/surface/covariance; no refit or propagation.
#include "TrkTrack/TrackCollection.h"
#include "TrkTrack/Track.h"
#include "TrkParameters/TrackParameters.h"
#include "TrkSurfaces/Surface.h"
#include <iomanip>
#include <sstream>
#include <string>
std::string Stage176States(const TrackCollection* tracks) {
    std::ostringstream s;s<<std::setprecision(17)<<'[';bool first=true;size_t index=0;
    for (const auto* track:*tracks) {
        const size_t current=index++;
        if(!track || !track->trackParameters() || track->trackParameters()->empty())continue;
        const auto* p=track->trackParameters()->front();if(!p)continue;
        const auto& surface=p->associatedSurface();const auto x=p->position(),m=p->momentum();
        const auto n=surface.normal(),c=surface.center();
        if(!first)s<<',';first=false;
        s<<"{\"collection_index\":"<<current<<",\"xyz_mm\":["<<x.x()<<','<<x.y()<<','<<x.z()
         <<"],\"px_py_pz_MeV\":["<<m.x()<<','<<m.y()<<','<<m.z()
         <<"],\"surface_name\":\""<<surface.name()<<"\",\"surface_type\":"<<static_cast<int>(surface.type())
         <<",\"normal\":["<<n.x()<<','<<n.y()<<','<<n.z()<<"],\"center_mm\":["<<c.x()<<','<<c.y()<<','<<c.z()<<"],\"covariance\":";
        const auto* cov=p->covariance();
        if(!cov)s<<"null";
        else {s<<'[';for(int i=0;i<5;++i){if(i)s<<',';s<<'[';for(int j=0;j<5;++j){if(j)s<<',';s<<(*cov)(i,j);}s<<']';}s<<']';}
        s<<'}';
    }
    s<<']';return s.str();
}
