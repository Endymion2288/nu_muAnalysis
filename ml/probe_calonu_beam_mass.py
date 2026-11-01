#!/usr/bin/env python3
"""Read a fixed failed CC identity control; no waveform or physics selection is changed."""
import ctypes,json
from pathlib import Path
import ROOT
ROOT.gErrorIgnoreLevel=ROOT.kError
ROOT.gSystem.Load('libGeneratorObjectsTPCnvDict.so')
def member(obj,name,typ):
 c=ROOT.TClass.GetClass(type(obj).__cpp_name__);o=c.GetDataMember(name).GetOffset();a=ROOT.addressof(obj)+o
 if typ=='float':return ctypes.c_float.from_address(a).value
 if typ=='int':return ctypes.c_int.from_address(a).value
 if typ=='short':return ctypes.c_short.from_address(a).value
 return ROOT.bind_object(a,typ)
def read(path,entry):
 f=ROOT.TFile.Open(path);t=f.Get('CollectionTree');t.SetBranchStatus('*',0);t.SetBranchStatus('McEventCollection_p6_BeamTruthEvent',1);t.GetEntry(entry)
 ps=member(t.McEventCollection_p6_BeamTruthEvent,'m_genParticles','std::vector<GenParticle_p6>')
 rows=[{k:member(p,k,typ) for k,typ in [(k,'float') for k in ['m_px','m_py','m_pz','m_m','m_generated_mass']]+[(k,'int') for k in ['m_pdgId','m_status','m_barcode']]+[('m_recoMethod','short')]} for p in ps];f.Close();return rows
p=Path('/eos/experiment/fasernu-data0/faser/sim/mc24/genie/200140')
r=read(str(p/'rdo/s0015/FaserMC-MC24_Genie_24_xing_angle_caloNu_epos_k-200140-00010-00019-s0015-RDO.root'),2)
h=read(str(p/'sim/s0015/FaserMC-MC24_Genie_24_xing_angle_caloNu_epos_k-200140-00010-s0015-HITS.root'),2)
print(json.dumps(dict(HITS=h,RDO=r),indent=2))
Path('workbook/stage39_energy_ml/beam_mass_probe.json').write_text(json.dumps(dict(HITS=h,RDO=r),indent=2)+'\n')
