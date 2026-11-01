#!/usr/bin/env python3
"""Opt-in empty-CaloNu patch against pinned source; never edit the external checkout."""
import difflib
import json
import subprocess
from pathlib import Path


def sources(repo):
    paths = ['Calorimeter/CaloDigiAlgs/src/CaloWaveformDigiAlg.cxx',
             'Calorimeter/CaloDigiAlgs/src/CaloWaveformDigiAlg.h',
             'Waveform/WaveDigiTools/WaveDigiTools/IWaveformDigitisationTool.h',
             'Waveform/WaveDigiTools/src/WaveformDigitisationTool.h',
             'Waveform/WaveDigiTools/src/WaveformDigitisationTool.cxx']
    old = {p:subprocess.check_output(['git','-C',str(repo.parent/'calypso'),'show','1ec47efe:'+p],text=True) for p in paths}
    new = dict(old)
    p = paths[0]
    new[p] = new[p].replace('  if (caloHitHandle->size() == 0) {',
        '  const bool emptyCaloNu = caloHitHandle->size() == 0 && m_digitizeEmptyCaloNu\n'
        '                          && m_caloHitContainerKey.key() == "CaloNuHits";\n'
        '  if (caloHitHandle->size() == 0 && !emptyCaloNu) {')
    new[p] = new[p].replace('  if (m_advancedTiming) {\n    waveforms =',
        '  if (emptyCaloNu) {\n'
        '    waveforms = m_digiTool->generate_calonu_noise_waveforms(ctx, m_digiCondTool);\n'
        '  } else if (m_advancedTiming) {\n    waveforms =')
    p = paths[1]
    new[p] = new[p].replace(' private:\n',
        '  // Opt in only after validating the historical CaloNu mapping/conditions.\n'
        '  BooleanProperty m_digitizeEmptyCaloNu{this, "DigitizeEmptyCaloNu", false};\n\n private:\n',1)
    declaration = ('  /// Explicit CaloNu noise path: never infer detector type from an empty hit collection.\n'
                   '  std::map<Identifier, std::vector<uint16_t>> generate_calonu_noise_waveforms(\n'
                   '      const EventContext& ctx,\n'
                   '      const ToolHandle<IWaveformDigiConditionsTool>& digiCondTool) const')
    p = paths[2]
    new[p] = new[p].replace('DeclareInterfaceID(IWaveformDigitisationTool, 1, 0)',
                            'DeclareInterfaceID(IWaveformDigitisationTool, 2, 0)')
    new[p] = new[p].replace('  /* /// Evaluate time kernel', declaration.replace('  std::map', '  virtual std::map')+' = 0;\n\n  /* /// Evaluate time kernel',1)
    p = paths[3]
    new[p] = new[p].replace(' private:\n', declaration+' override;\n\n private:\n',1)
    helper = '''std::map<Identifier, std::vector<uint16_t>>
WaveformDigitisationTool::generate_calonu_noise_waveforms(
    const EventContext& ctx,
    const ToolHandle<IWaveformDigiConditionsTool>& digiCondTool) const {
  auto waveforms = create_waveform_map(m_caloNuID);
  const EvstHistMap empty;
  convolve_waveforms(ctx, digiCondTool, empty, waveforms);
  return waveforms;
}

'''
    p = paths[4]
    marker = 'template <class ID, class DM>'
    new[p] = new[p].replace(marker, helper+marker,1)
    for p in paths:
        assert new[p] != old[p], p
    return old, new, helper


def main():
    repo = Path(__file__).resolve().parents[1]
    old, new, _ = sources(repo)
    target = repo/'ml/patches/calonu-empty-noise-1ec47efe.patch'
    target.write_text(''.join(''.join(difflib.unified_diff(old[p].splitlines(True),new[p].splitlines(True),
        fromfile='a/'+p,tofile='b/'+p)) for p in old))
    # Full nonempty digitisation methods and convolution remain byte-for-byte unchanged.
    tool = 'Waveform/WaveDigiTools/src/WaveformDigitisationTool.cxx'
    for name, end in [('generate_calo_waveforms(', 'std::map<Identifier, std::vector<uint16_t>>& \nWaveformDigitisationTool::generate_calo_timing_waveforms('),
                      ('convolve_waveforms(', None)]:
        start = old[tool].index('WaveformDigitisationTool::'+name)
        a = old[tool][start:old[tool].index(end,start) if end else None]
        bstart = new[tool].index('WaveformDigitisationTool::'+name)
        assert new[tool][bstart:bstart+len(a)] == a
    print(json.dumps(dict(patch=str(target), files=len(old), nonempty_functions_unchanged=True,
                         opt_in_default=False, interface_version='2.0', full_Athena_build='not measured')))


if __name__ == '__main__':
    main()
