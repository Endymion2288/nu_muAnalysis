#include "stage149_native.hxx"
namespace Stage161 {
std::vector<std::vector<std::string>> mapping(const VetoID& veto) {
    ToolHandle<IWaveformCableMappingTool> tool("WaveformCableMappingTool/WaveformCableMappingTool");
    if(tool.retrieve().isFailure())throw std::runtime_error("Actual data cable map unavailable");
    std::vector<std::vector<std::string>> out;
    for(const auto& item:tool->getCableMapping()) {
        auto type=item.second.first;
        if(type=="veto")type+=std::to_string(veto.station(item.second.second)+1);
        out.push_back({std::to_string(item.first),type,std::to_string(item.second.second.get_compact()),
                      std::to_string(item.second.second.get_identifier32().get_compact())});
    }
    return out;
}
}
