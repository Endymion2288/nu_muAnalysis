#include "stage192_links.cxx"
#include "TrkTrack/TrackCollection.h"
#include "TrkTrack/Track.h"
#include "TrkParameters/TrackParameters.h"
#include "TrackerRIO_OnTrack/FaserSCT_ClusterOnTrack.h"
#include "TrackerPrepRawData/FaserSCT_Cluster.h"
#include <map>

// The index is the previously frozen leading track, never picked by these labels.
extern "C" __attribute__((visibility("default")))
const char* stage194_fit(const TrackCollection* tracks, int index,
                         const TrackerSimDataCollection* sdo) {
    using J=nlohmann::json;
    static std::string result;
    J out={{"leading",nullptr},{"clusters",J::array()},{"barcode_cluster_counts",J::array()}};
    if (tracks && index>=0 && index<int(tracks->size())) {
        const auto* t=(*tracks)[index];
        if(t && t->trackParameters() && !t->trackParameters()->empty()) {
            const auto* p=t->trackParameters()->front();
            out["leading"]={{"collection_index",index},{"pz0_GeV",p->momentum().z()/1000.},
                            {"charge",p->charge()}};
            std::map<int,int> counts;
            int stateIndex=-1;
            for(const auto* st:*t->trackStateOnSurfaces()) {
                ++stateIndex;if(!st)continue;
                const auto* m=dynamic_cast<const Tracker::FaserSCT_ClusterOnTrack*>(st->measurementOnTrack());
                if(!m)continue;
                const auto* prd=m->prepRawData();
                J row={{"state_index",stateIndex},{"PRD_present",prd!=nullptr},{"strips",J::array()}};
                std::set<int> barcodes;
                if(prd)for(const auto& strip:prd->rdoList()) {
                    row["strips"].push_back(strip.get_compact());
                    if(sdo) {
                        auto it=sdo->find(strip);
                        if(it!=sdo->end())for(const auto& d:it->second.getdeposits())barcodes.insert(d.first.barcode());
                    }
                }
                row["contributors"]=J::array();for(int bc:barcodes) {row["contributors"].push_back(bc);++counts[bc];}
                out["clusters"].push_back(row);
            }
            for(auto [bc,n]:counts)out["barcode_cluster_counts"].push_back({bc,n});
        }
    }
    result=out.dump();return result.c_str();
}
