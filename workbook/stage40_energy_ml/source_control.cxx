
// SOURCE-FUNCTION FIXTURE ONLY: identifier helper and conditions are explicit substitutes.
#include <map>
#include <vector>
#include <cstdint>
#include <cmath>
#include <stdexcept>
#include <TF1.h>
#include <TH1D.h>
#include <TRandom3.h>
#define ATH_MSG_DEBUG(...) do {} while (0)
using Identifier = uint32_t;
using ExpandedIdentifier = uint32_t;
using EvstHistMap = std::map<Identifier, TH1D*>;
struct EventContext {};
template<class T> using ToolHandle = T*;
struct IWaveformDigiConditionsTool {
  float base_mean(const EventContext&) const {return 15650.f;}
  float base_rms(const EventContext&) const {return 3.f;}
  float cb_norm(const EventContext&) const {return 0.550000011920929f;}
  float cb_alpha(const EventContext&) const {return -0.3199999928474426f;}
  float cb_n(const EventContext&) const {return 1000.f;}
  float cb_sigma(const EventContext&) const {return 3.6700000762939453f;}
  float cb_mean(const EventContext&) const {return 820.f;}
};
struct CaloNuID {
  std::vector<uint32_t> ids{3892314112u,3758096384u,4160749568u,4026531840u};
  auto pmt_begin() const {return ids.begin();}
  auto pmt_end() const {return ids.end();}
  Identifier pmt_id(const ExpandedIdentifier& id) const {return id;}
};
struct IWaveformDigitisationTool {
  virtual unsigned int digitizer_samples() const = 0;
  template<class T> std::map<Identifier,std::vector<uint16_t>> create_waveform_map(const T*) const;
};
struct WaveformDigitisationTool : IWaveformDigitisationTool {
  TRandom3 random{1};
  TRandom3* m_random{&random};
  CaloNuID ids;
  const CaloNuID* m_caloNuID{&ids};
  unsigned int digitizer_samples() const override {return 600;}
  float digitizer_period() const {return 2.f;}
  unsigned int over_samples() const {return 20;}
  unsigned int pre_samples() const {return 10;}
  float generate_baseline(float,float) const;
  TF1* create_kernel(const EventContext&,const ToolHandle<IWaveformDigiConditionsTool>&) const;
  void convolve_waveforms(const EventContext&,const ToolHandle<IWaveformDigiConditionsTool>&,
                         const EvstHistMap&,std::map<Identifier,std::vector<uint16_t>>&) const;
  std::map<Identifier,std::vector<uint16_t>> generate_calonu_noise_waveforms(
      const EventContext&,const ToolHandle<IWaveformDigiConditionsTool>&) const;
};


template <class ID>
std::map<Identifier, std::vector<uint16_t>>  IWaveformDigitisationTool::create_waveform_map(const ID* idHelper) const {

  std::map<Identifier, std::vector<uint16_t>> waveforms;

  for (auto itr = idHelper->pmt_begin(); itr != idHelper->pmt_end(); ++itr) {
    const ExpandedIdentifier& extId = *itr;
    Identifier id = idHelper->pmt_id(extId);
    waveforms[id] = std::vector<uint16_t>();
    waveforms[id].reserve(digitizer_samples());
  }

  return waveforms;
}

float
WaveformDigitisationTool::generate_baseline(float mean, float rms) const {
  return m_random->Gaus(mean, rms);
}

TF1*
WaveformDigitisationTool::create_kernel(const EventContext& ctx,
					const ToolHandle<IWaveformDigiConditionsTool>& digiCondTool) const {

  TF1* kernel = new TF1("PDF", "[4] * ROOT::Math::crystalball_pdf(x, [0],[1],[2],[3])", 0, 1200);

  kernel->SetParameter(0, digiCondTool->cb_alpha(ctx));
  kernel->SetParameter(1, digiCondTool->cb_n(ctx));
  kernel->SetParameter(2, digiCondTool->cb_sigma(ctx));
  kernel->SetParameter(3, digiCondTool->cb_mean(ctx));
  kernel->SetParameter(4, digiCondTool->cb_norm(ctx));

  return kernel;
}

void
WaveformDigitisationTool::convolve_waveforms(
    const EventContext& ctx,
    const ToolHandle<IWaveformDigiConditionsTool>& digiCondTool,
    const EvstHistMap& evst_hist,
    std::map<Identifier, std::vector<uint16_t>>& waveforms
					     ) const {

  // Create digitization kernel
  TF1* kernel = create_kernel(ctx, digiCondTool);

  // Convolve Evst histogram vs. kernel for each waveform
  for (const auto& w : waveforms) {

    auto id = w.first;

    // Convolve Evst histogram with time kernel

    // Get the histogram
    auto it = evst_hist.find(id);
    if (it == evst_hist.end()) {
      ATH_MSG_DEBUG("Didn't find EvsT hist for id " << id <<"!");

      // Fill waveform with background only as Evst is empty
      for (unsigned int i=0; i < digitizer_samples(); i++) {

	float baseline = generate_baseline(digiCondTool->base_mean(ctx),
					   digiCondTool->base_rms(ctx));

	// Waveform is some random baseline
	int ivalue = std::round(baseline);

	// Don't let value go below zero
	if (ivalue < 0)
	  waveforms[id].push_back(0);
	else
	  waveforms[id].push_back(ivalue);

      } // End of loop over digitizer samples

      // Done with this waveform
      continue;
    }

    auto h = it->second;

    // Use this vector to sum our values
    // We will oversample by the same amount as the Evst histogram
    std::vector<double> dwave(digitizer_samples() * over_samples());
    // ATH_MSG_DEBUG("Creating dwave with length " << dwave.size());

    // Convolute evst signals with the time kernel
    for(unsigned int ih=1; int(ih) < h->GetNbinsX(); ih++) {

      float value = h->GetBinContent(ih);

      // If bin is empty, move on
      if (value <= 0.) continue;

      // Bin to write into in dwave
      // Histogram doesn't start at t=0, so subtract pre_samples
      int iw = ih - 1 - (pre_samples() * over_samples());

      // Convolute the histogram with the time kernel
      for (unsigned int ik=0; ik < dwave.size(); ik++) {
	// Figure out destination bin first, skip if out of range
	if ((iw + int(ik)) < 0) continue; // add int() to fix comp warnings
	if ((iw + ik) >= dwave.size()) continue;

	float ktime = ik * digitizer_period()/over_samples();
	float kval = kernel->Eval(ktime) * value;
	dwave[iw+ik] += kval;

	// if (kval > 0.01)
	//   ATH_MSG_DEBUG(" Bin " << ih << " kernel bin " << ik << " time " << ktime << " value " << kval);
      }

    } // Done with convolution

    // Debug printout
    // ATH_MSG_DEBUG("dwave array for " << id);
    // unsigned int iw=0;
    // for (auto v : dwave) {
    //   iw++;
    //   if (v <= 0.1) continue;
    //   ATH_MSG_DEBUG(" bin "<< iw << " val " << v);
    // }

    // Need to down-sample dwave to fit waveform spacing
    // Take average (or sum / over_sampling) to get amplitude correct
    std::vector<double> dswave(digitizer_samples());
    // ATH_MSG_DEBUG("Creating dswave with length " << dswave.size());

    for (unsigned int i=0; i < dwave.size(); i++) {
      dswave[i/over_samples()] += (dwave[i] / over_samples());
    }

    // Debug printout
    // ATH_MSG_DEBUG("dswave array for " << id);
    // iw=0;
    // for (auto v : dswave) {
    //   iw++;
    //   if (v <= 0.1) continue;
    //   ATH_MSG_DEBUG(" bin "<< iw << " val " << v);
    // }

    // Now fill each entry of the waveform with the down-sampled signal
    // and some random background
    for (unsigned int i=0; i < digitizer_samples(); i++) {

      float signal = dswave[i];
      float baseline = generate_baseline(digiCondTool->base_mean(ctx),
					 digiCondTool->base_rms(ctx));

      // Waveform is some random baseline plus a negative signal
      int ivalue = std::round(baseline - signal);

      // Don't let value go below zero
      if (ivalue < 0)
	waveforms[id].push_back(0);
      else
	waveforms[id].push_back(ivalue);

    } // End of loop over dswave

  } // End of loop over channels

  // Clean up after ourselves
  delete kernel;

}

std::map<Identifier, std::vector<uint16_t>>
WaveformDigitisationTool::generate_calonu_noise_waveforms(
    const EventContext& ctx,
    const ToolHandle<IWaveformDigiConditionsTool>& digiCondTool) const {
  auto waveforms = create_waveform_map(m_caloNuID);
  const EvstHistMap empty;
  convolve_waveforms(ctx, digiCondTool, empty, waveforms);
  return waveforms;
}



std::vector<uint16_t> Stage40NoiseEvents(unsigned int events,unsigned int seed) {
  WaveformDigitisationTool tool;
  tool.random.SetSeed(seed);
  IWaveformDigiConditionsTool conditions;
  IWaveformDigiConditionsTool* handle=&conditions;
  std::vector<uint16_t> result;
  result.reserve(events*4*600);
  for(unsigned int n=0;n<events;n++) {
    auto wave=tool.generate_calonu_noise_waveforms(EventContext{},handle);
    if(wave.size()!=4) throw std::runtime_error("Missing CaloNu channels");
    for(auto id:tool.ids.ids) {
      if(wave.at(id).size()!=600) throw std::runtime_error("Wrong waveform size");
      result.insert(result.end(),wave.at(id).begin(),wave.at(id).end());
    }
  }
  return result;
}
unsigned int Stage40ZeroHistogramPairs(unsigned int pairs,unsigned int seed) {
  WaveformDigitisationTool emptyTool,zeroTool;
  IWaveformDigiConditionsTool conditions;
  IWaveformDigiConditionsTool* handle=&conditions;
  emptyTool.random.SetSeed(seed); zeroTool.random.SetSeed(seed);
  unsigned int mismatches=0;
  for(unsigned int n=0;n<pairs;n++) {
    auto empty=emptyTool.generate_calonu_noise_waveforms(EventContext{},handle);
    auto zero=zeroTool.create_waveform_map(zeroTool.m_caloNuID);
    EvstHistMap hist;
    for(auto id:zeroTool.ids.ids) hist[id]=new TH1D("","",12200,-20,1200);
    zeroTool.convolve_waveforms(EventContext{},handle,hist,zero);
    for(auto id:zeroTool.ids.ids) {
      if(empty.at(id)!=zero.at(id)) mismatches++;
      delete hist[id];
    }
  }
  return mismatches;
}
