"""Read only the actual persisted scintillator ADC and exact event identity."""
import ctypes


class SavedWaveforms:
    def __init__(self, root, path,detectors=None):
        self.root=root;self.file=root.TFile.Open(path);assert self.file and not self.file.IsZombie(),path
        self.tree=self.file.Get('CollectionTree');self.tree.SetBranchStatus('*',0);self.schemas=[]
        self.detectors=detectors or ['VetoNu','Preshower']
        self.branches=['RawWaveformContainer_p0_'+d+'Waveforms' for d in self.detectors]
        self.info='xAOD::EventAuxInfo_v3_EventInfoAux.'
        for name in self.branches+[self.info]:
            branch=self.tree.GetBranch(name);assert branch,(path,name)
            self.tree.SetBranchStatus(name,1);cls=root.TClass.GetClass(branch.GetClassName())
            saved=[x for x in self.file.GetStreamerInfoList() if x.GetName()==cls.GetName()]
            assert any(int(x.GetCheckSum())==int(cls.GetCheckSum()) for x in saved),(path,name,'schema mismatch')
            self.schemas.append(dict(branch=name,checksum=int(cls.GetCheckSum())))

    def member(self,obj,name,typ):
        cls=self.root.TClass.GetClass(type(obj).__cpp_name__);offset=cls.GetDataMember(name).GetOffset();assert offset>=0
        address=self.root.addressof(obj)+offset
        if typ=='unsigned int':return ctypes.c_uint.from_address(address).value
        if typ=='unsigned long long':return ctypes.c_ulonglong.from_address(address).value
        return self.root.bind_object(address,typ)

    def read(self,entry,run,event):
        assert self.tree.GetEntry(entry)>0
        info=getattr(self.tree,self.info)
        assert (self.member(info,'runNumber','unsigned int'),self.member(info,'eventNumber','unsigned long long'))==(run,event)
        result={}
        for detector,branch in zip(self.detectors,self.branches):
            values=[]
            container=getattr(self.tree,branch)
            for wave in self.member(container,'m_waveforms','std::vector<RawWaveform_p0>'):
                adc=list(self.member(wave,'m_adc_counts','std::vector<unsigned int>'));assert len(adc)==600
                values.append(dict(id32=self.member(wave,'m_ID','unsigned int'),channel=self.member(wave,'m_channel','unsigned int'),adc=adc))
            result[detector]=values
        return result
