// Current geometry physical PMTs, with the PMT index kept for dual-end Trigger.
std::vector<std::vector<unsigned int>> Stage185ScintMap(const std::string& source) {
    ToolHandle<IWaveformCableMappingTool> tool("WaveformCableMappingTool/Stage122Cable");
    ServiceHandle<StoreGateSvc> detector("DetectorStore","Stage185");
    if(tool.retrieve().isFailure() || detector.retrieve().isFailure())throw std::runtime_error("Missing mapping");
    const std::string type=source=="VetoNu"?"vetonu":source=="Veto"?"veto":source=="Trigger"?"trigger":"preshower";
    const VetoID* veto=nullptr;const VetoNuID* vn=nullptr;const TriggerID* trigger=nullptr;const PreshowerID* ps=nullptr;
    if(source=="Veto") {if(detector->retrieve(veto,"VetoID").isFailure())throw std::runtime_error("No VetoID");}
    else if(source=="VetoNu") {if(detector->retrieve(vn,"VetoNuID").isFailure())throw std::runtime_error("No VetoNuID");}
    else if(source=="Trigger") {if(detector->retrieve(trigger,"TriggerID").isFailure())throw std::runtime_error("No TriggerID");}
    else {if(detector->retrieve(ps,"PreshowerID").isFailure())throw std::runtime_error("No PreshowerID");}
    std::vector<std::vector<unsigned int>> out;
    for(const auto& row:tool->getCableMapping()) {
        if(row.second.first!=type)continue;
        const auto id=row.second.second;
        int station,plate,pmt;
        if(veto){station=veto->station(id);plate=veto->plate(id);pmt=veto->pmt(id);}
        else if(vn){station=vn->station(id);plate=vn->plate(id);pmt=vn->pmt(id);}
        else if(trigger){station=trigger->station(id);plate=trigger->plate(id);pmt=trigger->pmt(id);}
        else {station=ps->station(id);plate=ps->plate(id);pmt=ps->pmt(id);}
        out.push_back({unsigned(row.first),id.get_identifier32().get_compact(),unsigned(station),unsigned(plate),unsigned(pmt)});
    }
    return out;
}
std::vector<std::vector<unsigned int>> Stage185CaloMap() {
    ToolHandle<IWaveformCableMappingTool> tool("WaveformCableMappingTool/Stage122Cable");
    if(tool.retrieve().isFailure())throw std::runtime_error("Missing map");
    std::vector<std::vector<unsigned int>> out;
    for(const auto& r:tool->getCableMapping())if(r.second.first=="calo")
        out.push_back({unsigned(r.first),r.second.second.get_identifier32().get_compact()});
    return out;
}
