"""Exact observed-charge closures across one-ULP float32 baseline refits."""
import numpy as np

def certify(ROOT,source,case,channel,adc,actual,old_X_value):
    assert source['phys'],'No original PHYS baseline for a discrepant cached charge'
    names={4:'VetoNu0',5:'VetoNu1',14:'Veto10',6:'Veto20',7:'Veto21',8:'Timing0',9:'Timing1',10:'Timing2',11:'Timing3',12:'Preshower0',13:'Preshower1'}
    name=names[channel];f=ROOT.TFile.Open(source['phys']);assert f and not f.IsZombie();t=f.Get('nt');t.SetBranchStatus('*',0)
    for key in ['run','eventID',name+'_baseline',name+'_raw_charge']:t.SetBranchStatus(key,1)
    assert t.GetEntry(case['entry'])>0;assert (int(t.run),int(t.eventID))==(case['run'],case['event'])
    oldbase=np.float32(getattr(t,name+'_baseline'));oldraw=np.float32(getattr(t,name+'_raw_charge'));newbase=np.float32(actual[3]);newraw=np.float32(actual[1]);f.Close()
    np.testing.assert_array_equal(oldraw,old_X_value)
    assert np.isfinite(oldbase) and np.isfinite(newbase) and oldbase>0 and newbase>0
    ulps=abs(int(oldbase.view('uint32'))-int(newbase.view('uint32')));assert ulps<=1,(source['index'],case['row'],channel,oldbase,newbase,ulps)
    samples=np.asarray(adc[390:491],dtype='float32');mv=np.float32(2000/16384)
    def signed(base):
        values=(base-samples*mv).astype('float32');return np.float32(np.float32(2*sum(map(float,values)))/np.float32(50))
    np.testing.assert_array_equal(signed(oldbase),oldraw);np.testing.assert_array_equal(signed(newbase),newraw)
    return dict(row=case['row'],source_index=source['index'],entry=case['entry'],channel=channel,old_baseline_mV=float(oldbase),new_baseline_mV=float(newbase),baseline_ULPs=ulps,old_raw_pC=float(oldraw),new_raw_pC=float(newraw),raw_delta_pC=float(newraw)-float(oldraw),sample_N=len(samples),ADC_sum_codes=sum(map(int,samples)),ADC_mV_per_code=float(mv),old_X_PHYS_exact=True,both_signed_integral_closures_exact=True)
