#!/usr/bin/env python3
"""Extract exact pinned source methods into an explicitly limited ROOT fixture."""
import json
import subprocess
import tempfile
from pathlib import Path
from build_calonu_empty_noise import sources

repo = Path(__file__).resolve().parents[1]
old, new, helper = sources(repo)
out = repo/'workbook/stage40_energy_ml'
# Reviewable patch must apply to exactly the pinned files, without changing the external checkout.
with tempfile.TemporaryDirectory(prefix='stage40_patch_') as directory:
    root = Path(directory)
    for path, text in old.items():
        target = root/path; target.parent.mkdir(parents=True,exist_ok=True); target.write_text(text)
    subprocess.run(['git','apply','--check',str(repo/'ml/patches/calonu-empty-noise-1ec47efe.patch')],cwd=root,check=True)
s = old['Waveform/WaveDigiTools/src/WaveformDigitisationTool.cxx']
def method(marker):
    start = s.index(marker)
    return s[start:s.index('\n}\n',start)+3]
baseline = method('float\nWaveformDigitisationTool::generate_baseline')
kernel = method('TF1*\nWaveformDigitisationTool::create_kernel')
convolve = method('void\nWaveformDigitisationTool::convolve_waveforms')
icc = subprocess.check_output(['git','-C',str(repo.parent/'calypso'),'show',
    '1ec47efe:Waveform/WaveDigiTools/WaveDigiTools/IWaveformDigitisationTool.icc'],text=True)
icc = '\n'.join(line for line in icc.splitlines() if not line.startswith('#include'))
header = r'''
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
'''
footer = r'''
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
'''
fixture = header+'\n'+icc+'\n'+baseline+'\n'+kernel+'\n'+convolve+'\n'+helper+'\n'+footer
normalized = '\n'.join(line.rstrip() for line in fixture.splitlines())+'\n'
assert normalized.split() == fixture.split()
(out/'source_control.cxx').write_text(normalized)
(out/'source_scope.json').write_text(json.dumps(dict(source_commit='1ec47efe',patch_applies_to_pinned_files=True,
    exact_methods=['create_waveform_map','generate_baseline','create_kernel','convolve_waveforms'],
    new_helper='generate_calonu_noise_waveforms', source_tokens_unchanged_after_trailing_whitespace_removal=True,
    explicit_substitutes=['CaloNuID iteration','EventContext','historical conditions','Gaudi handle'],
    source_identifiers_branch_order=[3892314112,3758096384,4160749568,4026531840],
    nonempty_digitisation_source_unchanged=True, full_Athena_build='not measured', original_random_seed_replay='not measured'),indent=2)+'\n')
print(out/'source_control.cxx')
