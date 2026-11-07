"""Fixed-model propagation of explicitly conditional measurement perturbations."""
import json

import numpy as np
import xgboost as xgb

from stage129_energy import ROOT,OUT,CACHE,ART,load,evaluate


def forward(experiment,arm,source,x,d):
    p=json.loads((ROOT/'workbook/stage87_energy_ml/protocol.json').read_text())['baseline']
    record=next(r for r in json.loads((OUT/f'{experiment}_fits.json').read_text()) if r['arm']==source)
    active=d['role']>0;prediction=[]
    for seed in p['seeds']:
        model=xgb.Booster(params={'nthread':1});model.load_model(ART/f'{experiment}_{source}_{seed}.ubj')
        prediction.append(model.predict(xgb.DMatrix(x[active],feature_names=model.feature_names,nthread=1)))
    raw=np.full(len(active),np.nan);raw[active]=np.mean(np.asarray(prediction,dtype=float),axis=0)
    np.savez_compressed(ART/f'{experiment}stress_{arm}_prediction.npz',raw=raw,cal=raw+record['offset'])


def main():
    d=load(ROOT/'ntuples/energy_ml_stage119/old_input.npz');plan=json.loads((OUT/'pressure_protocol.json').read_text())
    quality=np.full((len(d['role']),5),np.nan)
    for source in range(280):
        path=CACHE/f'extract_{source}.npz'
        if not path.exists():path=ROOT/f'ntuples/energy_ml_stage129/extract_{source}.npz'
        if not path.exists():path=__import__('pathlib').Path('/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage129')/path.name
        a=load(path);wave=a['adc'].astype(float);baseline=wave[:,:,:75].mean(2);noise=wave[:,:,:75].std(2)
        q=np.where(a['present'],(baseline-wave.min(2))/np.maximum(noise,1e-6),np.nan)
        for j,ch in enumerate(a['channel'][0]):quality[a['row'],[4,5,14,6,7].index(int(ch))]=q[:,j]
    np.savez_compressed(CACHE/'wave_peak_noise.npz',peak_over_noise=quality)
    for experiment,source in [('timing','T'),('saturation','Q')]:
        f=load(CACHE/f'{experiment}_features.npz');arms=['X',source]
        for arm in arms:
            np.savez_compressed(ART/f'{experiment}stress_{arm}_prediction.npz',**load(ART/f'{experiment}_{arm}_prediction.npz'))
        variants={}
        if experiment=='saturation':
            for gain in [-.05,.05]:
                v=f['features'].copy()
                for j in range(3):v[:,5*j:5*j+3]*=1+gain
                variants[f'gain{gain:+.2f}']=(f['valid'],v)
        else:
            for delta in plan['time_offset_ns']:
                for channel in ['upstream','Veto20']:
                    v=f['features'].copy();v+=np.asarray([0,0,delta,delta]) if channel=='upstream' else np.asarray([0,delta,-delta,-delta])
                    variants[f'{channel}{delta:+.2f}ns']=(f['valid'],v)
            for threshold in plan['threshold_sigma']:
                valid=f['valid'].copy();value=f['features'].copy()
                for k,(i,j) in enumerate([(0,1),(3,4),(0,3),(1,3)]):
                    keep=(quality[:,i]>=threshold)&(quality[:,j]>=threshold)
                    valid[~keep,3*k+2]=0;value[~keep,k]=np.nan
                variants[f'quality{threshold}sigma']=(valid,value)
        for arm,(valid,value) in variants.items():
            forward(experiment,arm,source,np.column_stack([d['x'],valid,value]),d);arms.append(arm)
        evaluate(experiment+'stress',d,arms)
    (OUT/'energystress_scope.json').write_text(json.dumps(dict(no_refit=True,original_status_unchanged=True,quarantine_predictions=0,reserved_predictions=0,gain_scope='recovered Q and halfwidth calibration only, original X fixed; not full all-channel sensor gain or cut migration',timing_scope='one detector offset group, strictstatus0 stays mandatory; quality veto only, not actual DAQ threshold',scope='unassigned controlled stress amplitudes, no physical 1sigma probability'),indent=2)+'\n')


if __name__=='__main__':main()
