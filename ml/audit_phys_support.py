"""Stage81 <=40 predetermined identities and actual production/feature QA."""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path
import numpy as np
import uproot
from audited_features import REPO, SCINTILLATORS, configuration, WAVE_INVALID
from support_augmentation import begin, resources, save, arrays
from extract_alternative_support import extract

OUT = REPO/'workbook/stage81_energy_ml'
CACHE = REPO/'ntuples/energy_ml_stage81'


def production(source):
    if source['component']=='pi':
        return dict(compatible=True,kind='same d32 merge source family as full stage70 reference closure',
            manifest_entry=source['known_entry'],evidence='workbook/stage70_energy_ml/calibration_closure.json',
            limits='same recorded local merge production; full original conditions snapshot unproven',new_log_bytes=0)
    segment=source['group'].split(':')[1];run=source['run']
    stem=Path(source['input']).name.split('-'+str(run))[0]+'-'+str(run)
    logdir=Path(f'/eos/experiment/fasernu-data0/faser/sim/mc24/genie/{run}/log/s0014')
    paths=[logdir/(stem+'-'+segment+'-s0014-RDO.rec.log'),logdir/(stem+f'-{int(segment[:5])//10:04d}-PHYS.ntp.log')]
    logs=[p.read_text(errors='replace') for p in paths]
    assert Path(source['input']).name in logs[1] and '--backward' in logs[1] and 'Use IFT = False' in logs[1]
    assert '6d6ab70b' in logs[1] and 'WAVE-Calibration-01-LG' in logs[0]
    path='PhysicsAnalysis/NtupleDumper/scripts/faser_ntuple_maker.py'
    source_text=subprocess.check_output(['git','-C','/eos/home-x/xcheng/FASER/calypso','show','6d6ab70b:'+path],text=True)
    assert "mc_kwargs['TrackCollectionWithoutIFT'] = \"CKFTrackCollectionBackwardWithoutIFT\"" in source_text
    return dict(compatible=False,paths=[str(p) for p in paths],new_log_bytes=sum(p.stat().st_size for p in paths),
        release='6d6ab70b',geometry='TI12MC04/FASERNU-04',calibration='actual logs WAVE-Calibration-01-LG',
        ntuple_tracks='CKFTrackCollectionBackwardWithoutIFT',reference_tracks='CKFTrackCollectionMergeWithoutIFT',
        reason='actual backward-only collection differs from original merge selection/track readout; no paired equivalence or nominal merge PHYS delivered',
        missing_diagnostic='Track_isForward; diagnostic only, not by itself the physical rejection reason',
        writer_source=path+'@6d6ab70b',energy_yield='未测量',model_fits=0)


def main(index):
    start=begin();source=json.loads((OUT/'source_plan.json').read_text())['sources'][index]
    dest=OUT/f'qa{index}.json';assert not dest.exists()
    prod=production(source)
    scalar=['run','eventID']+[s+'_'+k for s in SCINTILLATORS for k in ['raw_charge','status']]
    scalar += [f'Calo{i}_{k}' for i in range(4) for k in ['charge','E_EM','status']]
    with uproot.open(source['input'],array_cache=None) as f:
        t=f['nt'];a=t.arrays(scalar,entry_stop=10,library='np');requested=int(f.file.source.num_requested_bytes);raw_N=t.num_entries
    # Native CALO E/charge algebra is checked on the same <=10 identities.
    calo=[]
    reference=330/.07129999995231628
    for j in range(4):
        q=a[f'Calo{j}_charge'].astype(float);e=a[f'Calo{j}_E_EM'].astype(float);st=a[f'Calo{j}_status'].astype(int)
        m=(st==0)&np.isfinite(q)&np.isfinite(e)&(q!=0)
        if m.any():np.testing.assert_allclose(e[m]/q[m],reference,rtol=2e-6,atol=1e-3)
        calo.append(dict(module=j,N=int(m.sum()),median_MeV_per_pC=float(np.median(e[m]/q[m])) if m.any() else None))
    info=dict(index=index,source=source,QA_identity_N=len(a['run']),QA_input_entries=list(range(10)),raw_N=raw_N,
        identities=[dict(run=int(r),eventID=int(e)) for r,e in zip(a['run'],a['eventID'])],production=prod,
        scalar_requested_bytes=requested,calo_reference_MeV_per_pC=reference,calo=calo,calo_rescaled=False,
        compatible=prod['compatible'],energy_fits=0)
    if prod['compatible']:
        import ROOT
        ROOT.gROOT.SetBatch(True)
        with tempfile.TemporaryDirectory(prefix='stage81_QA_') as td:
            tmp=Path(td);inputfile=ROOT.TFile.Open(source['input']);tree=inputfile.Get('nt')
            out=ROOT.TFile.Open(str(tmp/'prefix.root'),'RECREATE');out.cd();clone=tree.CloneTree(10);clone.Write()
            clonebytes=int(inputfile.GetBytesRead());out.Close();inputfile.Close()
            extract(index,tmp/'prefix.root',tmp/'qa.npz',qa=True,source=source)
            d=arrays(tmp/'qa.npz');md=json.loads(str(d.pop('metadata_json')))
            assert md['raw_N']==10 and md['features']==configuration()['features']
            for j,s in enumerate(SCINTILLATORS):
                v=d['raw_charge'][:,j].astype('float32');v[(d['status'][:,j].astype(int)&WAVE_INVALID)!=0]=np.nan
                np.testing.assert_array_equal(v,d['x'][:,configuration()['features'].index(s+'_raw_charge')])
            info.update(extraction=md,ROOT_clone_requested_bytes=clonebytes,original62_raw_exact=True,
                measured_child_CPU_s=md['child_user_s']+md['child_system_s'])
            np.savez_compressed(CACHE/f'qa{index}.npz',**d)
    info.update(resources(start));save(dest,info)
    print(json.dumps({k:v for k,v in info.items() if k not in ['source','extraction']},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--index',type=int,required=True,choices=range(4));main(p.parse_args().index)
