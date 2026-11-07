// Access the actual algorithm-owned tool, not an unused ToolSvc clone.
#define HEPMC3 1
#include "WaveRawEvent/RawWaveform.h"
#include "WaveDigiTools/IWaveformDigitisationTool.h"
#include "GaudiKernel/Bootstrap.h"
#include "GaudiKernel/IAlgManager.h"
#include "GaudiKernel/IAlgorithm.h"
#include "GaudiKernel/ToolHandle.h"
#include "TBufferFile.h"
#include <stdexcept>

struct Stage129RandomAccess : IWaveformDigitisationTool {
    static auto member() { return &Stage129RandomAccess::m_random; }
};

TRandom3* Stage129PrivateRandom(const std::string& detector) {
    SmartIF<IAlgManager> manager(Gaudi::svcLocator());
    IAlgorithm* algorithm = nullptr;
    if (!manager || manager->getAlgorithm(detector+"WaveformDigiAlg",algorithm).isFailure())
        throw std::runtime_error("Actual waveform algorithm unavailable");
    ToolHandle<IWaveformDigitisationTool> tool("WaveformDigitisationTool/Stage122"+detector,algorithm,false);
    if (tool.retrieve().isFailure())
        throw std::runtime_error("Actual private digitization tool unavailable");
    return tool.get()->*Stage129RandomAccess::member();
}

void Stage129PrivateSeed(const std::string& detector,unsigned int seed) {
    if (!seed) throw std::runtime_error("Zero seed is not deterministic");
    Stage129PrivateRandom(detector)->SetSeed(seed);
}

std::string Stage129PrivateState(const std::string& detector) {
    TBufferFile buffer(TBuffer::kWrite);
    Stage129PrivateRandom(detector)->Streamer(buffer);
    const char* digits="0123456789abcdef";
    std::string result;
    for (int i=0;i<buffer.Length();++i) {
        unsigned char c=buffer.Buffer()[i];
        result.push_back(digits[c>>4]); result.push_back(digits[c&15]);
    }
    return result;
}
