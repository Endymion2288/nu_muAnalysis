#include "stage188_native.hxx"

// Keep all ACTS/Eigen objects on the gcc side of the interpreter boundary.
extern "C" __attribute__((visibility("default")))
const char* stage188_observe(const TrackCollection* tracks,
                            const Tracker::FaserSCT_ClusterContainer* clusters,
                            const FaserSCT_ID* id,
                            const TrackerSimDataCollection* sdo) {
    static std::string result;
    result = Stage188::observe(*tracks, *clusters, *id, sdo);
    return result.c_str();
}
