#ifndef NU_MU_TRACKING_MOMENTUM_QUALITY_H
#define NU_MU_TRACKING_MOMENTUM_QUALITY_H
#include "TrkTrack/Track.h"
#include <cmath>
#include <limits>
#include <vector>

inline std::vector<double> TrackingMomentumQuality(const Trk::Track* track) {
    const auto* p=track->trackParameters()->front();
    const double qop=p->parameters()[4]*1000.; // MeV^-1 -> GeV^-1
    const double variance=p->covariance() ? (*p->covariance())(4,4)*1e6 : std::numeric_limits<double>::quiet_NaN();
    double minimum=std::numeric_limits<double>::infinity(),maximum=0.;
    for(const auto* state:*track->trackStateOnSurfaces()) {
        const auto* s=state->trackParameters();
        if(!s) continue;
        const double momentum=s->momentum().norm()/1000.;
        minimum=std::min(minimum,momentum);maximum=std::max(maximum,momentum);
    }
    return {qop,variance,std::abs(qop)/std::sqrt(variance),minimum,maximum};
}
#endif
