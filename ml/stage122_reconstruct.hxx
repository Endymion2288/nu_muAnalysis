#include "WaveRecTools/IWaveformReconstructionTool.h"
#include "xAODFaserWaveform/WaveformHitAuxContainer.h"

std::vector<std::vector<double>> Stage122Reconstruct(
    const std::string& source,const std::vector<unsigned int>& channels,
    const std::vector<unsigned int>& ids,const std::vector<unsigned int>& adc) {
    if(channels.size()!=ids.size() || adc.size()!=600*ids.size())
        throw std::runtime_error("Waveform layout mismatch");
    ToolHandle<IWaveformReconstructionTool> tool("WaveformReconstructionTool/Stage122Rec"+source);
    if(tool.retrieve().isFailure()) throw std::runtime_error("Missing waveform reconstruction tool");
    xAOD::WaveformHitAuxContainer aux;
    xAOD::WaveformHitContainer hits;
    hits.setStore(&aux);
    std::vector<RawWaveform> waves;
    for(size_t i=0;i<ids.size();++i) {
        RawWaveform wave;
        wave.setIdentifier(Identifier{Identifier32(ids[i])});wave.setChannel(channels[i]);
        wave.setSamples(600);wave.setRange(2.);wave.setTriggerOffset(0);
        wave.setCounts(std::vector<unsigned int>(adc.begin()+600*i,adc.begin()+600*(i+1)));
        waves.push_back(wave);
        if(tool->reconstructPrimary(waves.back(),&hits).isFailure()) throw std::runtime_error("Primary reconstruction failed");
    }
    for(const auto& wave:waves)
        if(tool->reconstructSecondary(wave,&hits).isFailure()) throw std::runtime_error("Secondary reconstruction failed");
    std::vector<std::vector<double>> result;
    for(const auto* h:static_cast<const xAOD::WaveformHitContainer&>(hits)) {
        const auto times=h->time_vector();
        const auto values=h->wave_vector();
        if(times.size()!=values.size()) throw std::runtime_error("Reconstructed waveform layout mismatch");
        std::vector<double> row{double(h->identify().get_identifier32().get_compact()),double(h->channel()),double(h->hit_status()),
            h->raw_integral()/50.,h->integral()/50.,h->localtime(),double(times.size())};
        row.insert(row.end(),times.begin(),times.end());
        row.insert(row.end(),values.begin(),values.end());
        result.push_back(std::move(row));
    }
    return result;
}
