#include "TrackerSimData/TrackerSimDataCollection.h"
#include "GeneratorObjects/McEventCollection.h"
#include "AtlasHepMC/GenParticle.h"
#include "AtlasHepMC/GenVertex.h"
#include <nlohmann/json.hpp>
#include <set>
#include <cmath>

// Inspect actual particle pointers in the selected StoreGate TruthEvent. A barcode
// match in an unrelated collection is explicitly insufficient.
extern "C" __attribute__((visibility("default")))
const char* stage192_links(const TrackerSimDataCollection* sdo,
                          const McEventCollection* truth, const char* requested) {
    using J=nlohmann::json;
    static std::string result;
    J out={{"truth_events_N",truth?truth->size():0},{"primary_muons",J::array()},
           {"strips",J::array()},{"SDO_present",sdo!=nullptr}};
    std::set<const HepMC::GenParticle*> selected,primary;
    bool hasNu=false;
    if(truth && truth->size()==1) {
        for(const auto& p:truth->front()->particles()) {
            selected.insert(p.get());
            if(std::abs(p->pdg_id())==14 && p->status()==4)hasNu=true;
        }
        for(const auto& p:truth->front()->particles()) {
            if(std::abs(p->pdg_id())!=13 || p->status()!=1)continue;
            auto vertex=p->production_vertex();
            bool candidate=!hasNu && (!vertex || vertex->particles_in().empty());
            if(hasNu && vertex)for(const auto& mother:vertex->particles_in())
                if(std::abs(mother->pdg_id())==14 && mother->status()==4
                   && mother->pdg_id()*13==p->pdg_id()*14)candidate=true;
            if(candidate) {
                primary.insert(p.get());
                out["primary_muons"].push_back({{"barcode",HepMC::barcode(p)},
                    {"pdg",p->pdg_id()},{"status",p->status()}});
            }
        }
    }
    out["has_incoming_numu"]=hasNu;
    for(const auto& item:J::parse(requested)) {
        const auto compact=item.get<unsigned long long>();
        J row={{"strip",compact},{"present",false},{"deposits",J::array()}};
        if(sdo) {
            auto found=sdo->find(Identifier(compact));
            if(found!=sdo->end()) {
                row["present"]=true;
                for(const auto& deposit:found->second.getdeposits()) {
                    const auto& link=deposit.first;
                    const auto particle=link.cptr();
                    row["deposits"].push_back({{"barcode",link.barcode()},
                        {"event_index",link.eventIndex()},
                        {"collection_char",std::string(1,link.getEventCollectionAsChar())},
                        {"weight",deposit.second},{"pointer_valid",bool(particle)},
                        {"pointer_in_selected_truth",particle && selected.count(particle.get())>0},
                        {"pointer_is_unique_primary",particle && primary.size()==1 && primary.count(particle.get())>0},
                        {"linked_barcode",particle?J(HepMC::barcode(particle)):J(nullptr)},
                        {"linked_pdg",particle?J(particle->pdg_id()):J(nullptr)}});
                }
            }
        }
        out["strips"].push_back(row);
    }
    result=out.dump();return result.c_str();
}
