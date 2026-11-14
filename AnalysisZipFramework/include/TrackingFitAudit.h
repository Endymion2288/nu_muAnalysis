#ifndef NU_MU_TRACKING_FIT_AUDIT_H
#define NU_MU_TRACKING_FIT_AUDIT_H
// Stage209 observer: no candidate columns and no changes to fitter arithmetic.
#include "ActsInterop/IndexSourceLink.h"
#include "TrackerRIO_OnTrack/FaserSCT_ClusterOnTrack.h"
#include "TrkTrack/Track.h"
#include <cstdlib>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <string>

class TrackingFitAudit {
public:
    std::ofstream out;
    int candidate = -1;
    static bool enabled(unsigned long long event) {
        const char* value = std::getenv("CALYPSO_DIAG_EVENTS");
        return value && (std::string(",") + value + ",").find("," + std::to_string(event) + ",") != std::string::npos;
    }
    TrackingFitAudit(const std::string& name, unsigned long long event) {
        if (enabled(event)) out.open(name + "_" + std::to_string(event) + ".jsonl");
        out << std::setprecision(17);
    }
    explicit operator bool() const { return out.is_open(); }
    void number(double value) { if (std::isfinite(value)) out << value; else out << "null"; }
    template<class M> void matrix(const M& value) {
        out << '[';
        for (int i=0;i<value.rows();++i) {
            if (i) out << ',';
            out << '[';
            for (int j=0;j<value.cols();++j) { if(j) out << ',';number(value(i,j)); }
            out << ']';
        }
        out << ']';
    }
    template<class V> void vector(const V& value) {
        out << '[';
        for(int i=0;i<value.size();++i) { if(i) out << ',';number(value[i]); }
        out << ']';
    }
    void begin(const std::string& stage) {
        out << "{\"stage\":\"" << stage << "\",\"candidate\":" << candidate;
    }
    void end() { out << "}\n"; }
    void parameters(const std::string& stage, const Acts::GeometryContext& gctx,
                    const Acts::BoundTrackParameters& p) {
        if (!*this) return;
        begin(stage);out << ",\"bound\":";vector(p.parameters());
        out << ",\"position\":";vector(p.position(gctx));
        out << ",\"momentum_GeV\":";vector(p.momentum());
        if(p.covariance()) {out << ",\"cov\":";matrix(*p.covariance());}
        out << ",\"surface\":";matrix(p.referenceSurface().transform(gctx).matrix());end();
    }
    template<class T> void track(const std::string& stage, const Acts::GeometryContext& gctx, const T& track) {
        if (!*this) return;
        begin(stage);out << ",\"index\":" << track.index() << ",\"chi2\":";number(track.chi2());
        out << ",\"nMeasurements\":" << track.nMeasurements() << ",\"ndof\":" << track.nDoF();end();
        if(track.hasReferenceSurface()) parameters(stage+"_reference",gctx,
            Acts::BoundTrackParameters(track.referenceSurface().getSharedPtr(),track.parameters(),
                track.covariance(),Acts::ParticleHypothesis::muon()));
        int index=0;
        for(const auto& state:track.trackStatesReversed()) {
            begin(stage+"_state");out << ",\"state\":" << index++ << ",\"chi2\":";number(state.chi2());
            out << ",\"measurement\":" << state.typeFlags().test(Acts::TrackStateFlag::MeasurementFlag)
                << ",\"outlier\":" << state.typeFlags().test(Acts::TrackStateFlag::OutlierFlag)
                << ",\"geometry_id\":" << state.referenceSurface().geometryId().value();
            if(state.hasUncalibratedSourceLink()) out << ",\"hit\":"
                << state.getUncalibratedSourceLink().template get<IndexSourceLink>().hit()->identify().get_compact();
            out << ",\"surface\":";matrix(state.referenceSurface().transform(gctx).matrix());
            if(state.hasPredicted()) {out << ",\"predicted\":";vector(state.predicted());out << ",\"predicted_cov\":";matrix(state.predictedCovariance());}
            if(state.hasFiltered()) {out << ",\"filtered\":";vector(state.filtered());out << ",\"filtered_cov\":";matrix(state.filteredCovariance());}
            if(state.hasSmoothed()) {out << ",\"smoothed\":";vector(state.smoothed());out << ",\"smoothed_cov\":";matrix(state.smoothedCovariance());}
            end();
        }
    }
    void trk(const std::string& stage, const Trk::Track* track) {
        if (!*this) return;
        begin(stage);out << ",\"exists\":" << (track!=nullptr);
        if(!track) {end();return;}
        out << ",\"chi2\":";number(track->fitQuality()->chiSquared());
        out << ",\"ndof\":";number(track->fitQuality()->doubleNumberDoF());
        out << ",\"measurements\":" << track->measurementsOnTrack()->size();end();
        int i=0;
        for(const auto* state:*track->trackStateOnSurfaces()) {
            const auto* p=state->trackParameters();if(!p) continue;
            begin(stage+"_state");out << ",\"state\":" << i++ << ",\"bound\":";vector(p->parameters());
            out << ",\"position\":";vector(p->position());out << ",\"momentum_MeV\":";vector(p->momentum());
            if(p->covariance()) {out << ",\"cov\":";matrix(*p->covariance());}
            const auto* m=dynamic_cast<const Tracker::FaserSCT_ClusterOnTrack*>(state->measurementOnTrack());
            if(m) out << ",\"hit\":" << m->identify().get_compact();
            end();
        }
    }
};
inline thread_local TrackingFitAudit* currentTrackingFitAudit = nullptr;
#endif
