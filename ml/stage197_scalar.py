"""Separately written scalar cut and aux decisions for actual-input validation."""
import math
from stage197_common import G,TRACK


def scalar_cuts(a, i):
    value=lambda name: a[name][i]
    pz=list(value('Track_pz0'))
    idx=max(range(len(pz)),key=pz.__getitem__) if pz else -1
    def lead(name):
        values=value('Track_'+name)
        return float(values[idx]) if 0<=idx<len(values) else float('nan')
    stamp=int(value('eventTime'))
    nu0,nu1=int(value('VetoNu0_status')),int(value('VetoNu1_status'))
    good=((nu0 in (0,1)) and (nu1 in (0,1))) or (nu0==0 and nu1==16)
    bottom=float(value('Timing0_charge'))+float(value('Timing1_charge'))
    top=float(value('Timing2_charge'))+float(value('Timing3_charge'))
    y=lead('Y_atTrig');dof=lead('nDoF');z=lead('pz0')
    theta=math.atan(math.sqrt(lead('px0')**2+lead('py0')**2)/z)*1000 if z else float('nan')
    return [True,int(value('distanceToCollidingBCID'))==0,bool(int(value('inputBits'))&0x78),
        any(lo<=stamp<=hi for lo,hi in G['stable_ranges_s']),not any(lo<=stamp<=hi for lo,hi in G['excluded_ranges_s']),
        int(value('longTracks'))>0,good and int(value('Veto20_status'))!=528 and int(value('Veto21_status'))!=528,
        float(value('Veto20_charge'))>40 and float(value('Veto21_charge'))>40,
        (y>20 and top>20) or (y< -20 and bottom>20) or (abs(y)<20 and top+bottom>20),
        float(value('Preshower0_charge'))>2.5 and float(value('Preshower1_charge'))>2.5,
        z>50000,lead('nLayers')>=7,dof>=9,(lead('Chi2')/dof if dof else float('nan'))<15,
        lead('r_atMaxRadius')<95,math.sqrt(lead('X_atVetoStation2')**2+lead('Y_atVetoStation2')**2)<95,
        math.sqrt(lead('X_atVetoNu')**2+lead('Y_atVetoNu')**2)<120,theta<25]


def aux_state(row, aux):
    native=row['native_reduced_pC']
    if native is not None:
        if any(v is None for v in native):return 'native_nonfinite'
        return 'selected' if native[0]<30 and native[1]<30 else 'vetoed'
    key=row['run'],row['eventID']
    if key not in aux:return 'aux_missing'
    if aux[key] is None:return 'aux_ambiguous'
    for j in (0,1):
        q=aux[key][j];raw=row['original_raw_VetoNu'][j]
        good=q is not None and row['selection_TimingOK'] and not (q==0 and raw is not None and raw>30)
        if good:
            if max(0,q)>=30:return 'vetoed'
        else:
            if raw is None:return 'fallback_nonfinite'
            if raw>=40:return 'vetoed'
    return 'selected'
