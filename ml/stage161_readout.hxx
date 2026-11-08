#include <map>
#include <string>
#include <vector>
#include <limits>
#include <stdexcept>
#include "xAODFaserWaveform/versions/WaveformHitAuxContainer_v1.h"
#include "xAODFaserWaveform/versions/WaveformHitContainer_v1.h"
#include "TTreeReader.h"
#include "TTreeReaderValue.h"
#include "TFile.h"
#include "TTree.h"
#include <memory>
namespace Stage161 {
// Read the actual v1 object, bypassing the v1->current converter's unchecked
// time_vector()[0]. Empty vectors remain empty; no timing is synthesized.
struct Wave {
    unsigned channel=0,id32=0,status=0;
    double rawCharge=0,rawPeak=0,baseline=0,rms=0,localtime=0;
    size_t waveN=0,timeN=0;
    bool secondary=false;
    std::string detector;
};
class Reader {
    std::unique_ptr<TFile> file;
    std::unique_ptr<TTreeReader> reader;
    std::map<std::string,std::unique_ptr<TTreeReaderValue<xAOD::WaveformHitAuxContainer_v1>>> aux;
public:
    explicit Reader(const std::string& path) {
        file.reset(TFile::Open(path.c_str()));
        if(!file||file->IsZombie())throw std::runtime_error("Frozen REC unreadable");
        auto tree=file->Get<TTree>("CollectionTree");
        if(!tree)throw std::runtime_error("No CollectionTree");
        reader=std::make_unique<TTreeReader>(tree);
        for(const std::string detector:{"Calo","Calo2","CaloNu","VetoNu","Veto","Trigger","Preshower"}) {
            auto name=detector+"WaveformHitsAux.";auto branch=tree->GetBranch(name.c_str());
            if(!branch)continue;
            if(std::string(branch->GetClassName())!="xAOD::WaveformHitAuxContainer_v1")
                throw std::runtime_error("Unsupported persistent waveform class: "+name);
            aux[detector]=std::make_unique<TTreeReaderValue<xAOD::WaveformHitAuxContainer_v1>>(*reader,name.c_str());
        }
        if(aux.empty())throw std::runtime_error("No frozen v1 waveform aux sources");
    }
    std::vector<std::string> containers()const {
        std::vector<std::string> out;for(const auto& item:aux)out.push_back(item.first);return out;
    }
    std::vector<Wave> read(long long entry) {
        if(reader->SetEntry(entry)!=TTreeReader::kEntryValid)throw std::runtime_error("Invalid actual mapped entry");
        std::vector<Wave> out;
        for(const auto& item:aux) {
            const auto& object=**item.second;
            xAOD::WaveformHitContainer_v1 hits;
            for(size_t i=0;i<object.size();++i)hits.push_back(new xAOD::WaveformHit_v1());
            hits.setStore(&object);
            for(const xAOD::WaveformHit_v1* hit:hits) {
                Wave w;w.detector=item.first;w.channel=hit->channel();w.id32=hit->id32();
                w.status=hit->hit_status();w.secondary=hit->secondary();
                w.rawCharge=double(hit->raw_integral())/50.;w.rawPeak=hit->raw_peak();
                w.baseline=hit->baseline_mean();w.rms=hit->baseline_rms();
                w.localtime=w.status==0?hit->localtime():std::numeric_limits<double>::quiet_NaN();
                // Structural lengths only: nonzero-status time is never an input.
                w.waveN=hit->wave_vector().size();w.timeN=hit->time_vector().size();
                out.push_back(w);
            }
        }
        return out;
    }
};
}
