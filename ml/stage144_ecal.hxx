// Actual persistent, SD-corrected Ecal hits. No second Birks correction.
#include "FaserCaloSimEvent/CaloHitCollection.h"
#include "CaloReadoutGeometry/EcalDetectorManager.h"
#include "CaloReadoutGeometry/CaloDetectorElement.h"
#include "FaserCaloIdentifier/EcalID.h"
#include <map>

std::vector<unsigned int> Stage144EcalIdentifiers() {
    ServiceHandle<StoreGateSvc> detector("DetectorStore","Stage144");
    const EcalID* helper=nullptr;
    if(detector.retrieve().isFailure() || detector->retrieve(helper,"EcalID").isFailure())
        throw std::runtime_error("Missing EcalID");
    // The digitizer draws noise for every geometry PMT before the algorithm
    // removes channels without a cable mapping. Preserve those draws too.
    std::map<Identifier,int> ordered;
    for(auto it=helper->pmt_begin();it!=helper->pmt_end();++it)
        ordered[helper->pmt_id(*it)]=0;
    std::vector<unsigned int> output;
    for(const auto& row:ordered) output.push_back(row.first.get_identifier32().get_compact());
    return output;
}

void Stage144RecordEcal(const std::vector<double>& flat) {
    if(flat.size()%10) throw std::runtime_error("Ecal snapshot layout");
    auto* hits=new CaloHitCollection("EcalHits");
    for(size_t offset=0;offset<flat.size();offset+=10) {
        const std::vector<double> r(flat.begin()+offset,flat.begin()+offset+10);
        hits->Emplace(HepGeom::Point3D<double>(r[4],r[5],r[6]),
                      HepGeom::Point3D<double>(r[7],r[8],r[9]),r[1],r[2],int(r[3]),unsigned(r[0]));
        const auto& hit=(*hits)[hits->size()-1];
        const std::vector<double> copy{double(hit.identify()),hit.energyLoss(),hit.meanTime(),double(hit.trackNumber()),
            hit.localStartPosition().x(),hit.localStartPosition().y(),hit.localStartPosition().z(),
            hit.localEndPosition().x(),hit.localEndPosition().y(),hit.localEndPosition().z()};
        if(copy!=r) throw std::runtime_error("Ecal persistent reconstruction differs");
    }
    ServiceHandle<StoreGateSvc> store("StoreGateSvc","Stage144");
    if(store.retrieve().isFailure() || store->record(hits,"EcalHits").isFailure())
        throw std::runtime_error("Cannot record Ecal snapshot");
}

std::vector<std::vector<double>> Stage144EcalTiming() {
    ServiceHandle<StoreGateSvc> store("StoreGateSvc","Stage144");
    ServiceHandle<StoreGateSvc> detector("DetectorStore","Stage144");
    const CaloHitCollection* hits=nullptr;
    const CaloDD::EcalDetectorManager* manager=nullptr;
    if(store.retrieve().isFailure() || detector.retrieve().isFailure() ||
       store->retrieve(hits,"EcalHits").isFailure() || detector->retrieve(manager,"Ecal").isFailure())
        throw std::runtime_error("Missing Ecal hit/geometry");
    std::vector<std::vector<double>> output;
    for(const auto& hit:*hits) {
        const auto id=hit.getIdentifier();
        const float tof=manager->getDetectorElement(id)->center().z()/299.792458;
        const float time=hit.meanTime()-tof;
        output.push_back({double(id.get_identifier32().get_compact()),hit.energyLoss(),hit.meanTime(),double(time),tof});
    }
    return output;
}
