#include "WaveRawEvent/RawWaveform.h"
#include "WaveRecTools/IWaveformReconstructionTool.h"
#include "xAODFaserWaveform/WaveformHitAuxContainer.h"
#include "GaudiKernel/ToolHandle.h"
#include <vector>
#include <stdexcept>

std::vector<double> Stage129Official(const std::string& detector, unsigned int channel,
                                    unsigned int identifier, const std::vector<unsigned int>& adc) {
    ToolHandle<IWaveformReconstructionTool> tool("WaveformReconstructionTool/Stage129Rec"+detector);
    if (tool.retrieve().isFailure()) throw std::runtime_error("Official waveform tool unavailable");
    xAOD::WaveformHitAuxContainer aux;
    xAOD::WaveformHitContainer hits;
    hits.setStore(&aux);
    RawWaveform wave;
    wave.setIdentifier(Identifier{Identifier32(identifier)});
    wave.setChannel(channel); wave.setSamples(adc.size()); wave.setRange(2.); wave.setTriggerOffset(0);
    wave.setCounts(adc);
    if (tool->reconstructPrimary(wave,&hits).isFailure() || hits.size()!=1)
        throw std::runtime_error("Official primary reconstruction failed");
    const auto* h=static_cast<const xAOD::WaveformHitContainer&>(hits)[0];
    const auto times=h->time_vector();
    return {double(h->hit_status()),h->raw_integral()/50.,h->integral()/50.,h->baseline_mean(),
            h->baseline_rms(),h->localtime(),times.empty() ? -1. : times.front(),
            times.empty() ? -1. : times.back(),h->peak(),h->mean(),h->width(),h->alpha(),h->nval()};
}
