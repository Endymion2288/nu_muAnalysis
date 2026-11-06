// Match the installed Athena/Calypso HepMC3 build in Cling as well.
#define HEPMC3 1
// Use the installed official interface; no modification of the production tool.
#include "WaveDigiTools/IWaveformDigitisationTool.h"
#include "WaveformConditionsTools/IWaveformDigiConditionsTool.h"
#include "WaveformConditionsTools/IWaveformCableMappingTool.h"
#include "ScintReadoutGeometry/VetoNuDetectorManager.h"
#include "ScintReadoutGeometry/PreshowerDetectorManager.h"
#include "ScintReadoutGeometry/ScintDetectorElement.h"
#include "ScintIdentifier/VetoNuID.h"
#include "ScintIdentifier/VetoID.h"
#include "ScintIdentifier/PreshowerID.h"
#include "StoreGate/StoreGateSvc.h"
#include "GaudiKernel/ThreadLocalContext.h"
#include "TBufferFile.h"
#include <stdexcept>
#include <string>

struct Stage122RandomAccess : IWaveformDigitisationTool {
    static auto member() { return &Stage122RandomAccess::m_random; }
};

TRandom3* Stage122Random(const std::string& source) {
    ToolHandle<IWaveformDigitisationTool> tool("WaveformDigitisationTool/Stage122"+source);
    if (tool.retrieve().isFailure()) throw std::runtime_error("Missing digitization tool");
    return tool.get()->*Stage122RandomAccess::member();
}

std::string Stage122State(const std::string& source) {
    TBufferFile buffer(TBuffer::kWrite);
    Stage122Random(source)->Streamer(buffer);
    const char* digits="0123456789abcdef";
    std::string result;
    for (int i=0;i<buffer.Length();++i) {
        unsigned char c=buffer.Buffer()[i];
        result.push_back(digits[c>>4]); result.push_back(digits[c&15]);
    }
    return result;
}

void Stage122Seed(const std::string& source, unsigned int seed) {
    if (!seed) throw std::runtime_error("Zero seed is not deterministic");
    Stage122Random(source)->SetSeed(seed);
}

void Stage122Restore(const std::string& source,const std::string& state) {
    if(state.size()%2) throw std::runtime_error("Invalid RNG state");
    std::vector<unsigned char> data;
    for(size_t i=0;i<state.size();i+=2)
        data.push_back(static_cast<unsigned char>(std::stoul(state.substr(i,2),nullptr,16)));
    TBufferFile buffer(TBuffer::kRead,data.size(),data.data(),false);
    Stage122Random(source)->Streamer(buffer);
}

std::vector<std::vector<unsigned long long>> Stage122Digitize(
    const std::string& source, const ScintHitCollection* hits) {
    ToolHandle<IWaveformDigitisationTool> tool("WaveformDigitisationTool/Stage122"+source);
    ToolHandle<IWaveformDigiConditionsTool> conditions("WaveformDigiConditionsTool/Stage122Cond"+source);
    if (tool.retrieve().isFailure() || conditions.retrieve().isFailure())
        throw std::runtime_error("Missing waveform tools");
    std::vector<std::vector<unsigned long long>> output;
    // The production ScintWaveformDigiAlg also returns an empty container here.
    if (hits->empty()) return output;
    const auto& waves=tool->generate_scint_timing_waveforms(Gaudi::Hive::currentContext(),conditions,hits);
    for (const auto& entry:waves) {
        std::vector<unsigned long long> row{entry.first.get_compact()};
        row.insert(row.end(),entry.second.begin(),entry.second.end());
        output.push_back(std::move(row));
    }
    return output;
}

double Stage122Z(const std::string& source,int station,int plate) {
    ServiceHandle<StoreGateSvc> store("DetectorStore","Stage122Z");
    if (store.retrieve().isFailure()) throw std::runtime_error("Missing geometry store");
    if(source=="VetoNu") {
        const ScintDD::VetoNuDetectorManager* det=nullptr;
        if(store->retrieve(det,"VetoNu").isFailure()) throw std::runtime_error("Missing VetoNu");
        return det->getDetectorElement(station,plate)->center().z();
    }
    const ScintDD::PreshowerDetectorManager* det=nullptr;
    if(store->retrieve(det,"Preshower").isFailure()) throw std::runtime_error("Missing Preshower");
    return det->getDetectorElement(station,plate)->center().z();
}

std::vector<double> Stage122Conditions(const std::string& source) {
    ToolHandle<IWaveformDigiConditionsTool> c("WaveformDigiConditionsTool/Stage122Cond"+source);
    if(c.retrieve().isFailure()) throw std::runtime_error("Missing conditions");
    const auto& ctx=Gaudi::Hive::currentContext();
    return {c->base_mean(ctx),c->base_rms(ctx),c->preshower_time_slope(ctx),
            c->cb_alpha(ctx),c->cb_n(ctx),c->cb_sigma(ctx),c->cb_mean(ctx),c->cb_norm(ctx)};
}

std::vector<int> Stage122Plate(const std::string& source,unsigned int id32) {
    ServiceHandle<StoreGateSvc> store("DetectorStore","Stage122Plate");
    if(store.retrieve().isFailure()) throw std::runtime_error("Missing geometry store");
    Identifier id{Identifier32(id32)};
    if(source=="VetoNu") {
        const VetoNuID* h=nullptr;
        if(store->retrieve(h,"VetoNuID").isFailure()) throw std::runtime_error("Missing ID");
        return {h->station(id),h->plate(id)};
    }
    if(source=="Veto") {
        const VetoID* h=nullptr;
        if(store->retrieve(h,"VetoID").isFailure()) throw std::runtime_error("Missing Veto ID");
        return {h->station(id),h->plate(id)};
    }
    const PreshowerID* h=nullptr;
    if(store->retrieve(h,"PreshowerID").isFailure()) throw std::runtime_error("Missing ID");
    return {h->station(id),h->plate(id)};
}

std::vector<std::vector<unsigned int>> Stage122CableMap(const std::string& source) {
    ToolHandle<IWaveformCableMappingTool> tool("WaveformCableMappingTool/Stage122Cable");
    if(tool.retrieve().isFailure()) throw std::runtime_error("Missing native cable mapping tool");
    std::vector<std::vector<unsigned int>> rows;
    const std::string type=source=="VetoNu"?"vetonu":source=="Veto"?"veto":"preshower";
    for(const auto& entry:tool->getCableMapping()) {
        if(entry.second.first!=type) continue;
        const auto id32=entry.second.second.get_identifier32().get_compact();
        const auto physical=Stage122Plate(source,id32);
        rows.push_back({static_cast<unsigned int>(entry.first),id32,
                       static_cast<unsigned int>(physical[0]),static_cast<unsigned int>(physical[1])});
    }
    return rows;
}
