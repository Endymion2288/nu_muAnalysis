"""One batch-only conditional dual-readout benchmark; no calibrated error claim."""
import csv
import gzip
import json
import math
import resource
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import uproot

ROOT = Path.cwd()
OUT = ROOT / 'workbook/stage195_energy_ml'
CACHE = ROOT / 'ntuples/energy_ml_stage195'
P = json.loads((OUT / 'protocol.json').read_text())
OLD = json.loads((ROOT / P['inputs'][0]).read_text())
TIMES = json.loads((ROOT / P['inputs'][1]).read_text())
CHS = [0, 1, 2, 3, 16, 17, 18, 19]


def write(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def table(name, rows):
    with (OUT / name).open('w') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n', quoting=csv.QUOTE_NONNUMERIC)
        w.writeheader()
        w.writerows(rows)


def controls():
    conditions = json.loads((ROOT / P['condition_input']).read_text())
    ranges = next(r['rows'] for r in conditions if r['run'] == 15838 and r['folder'] == '/WAVE/DAQ/Range')
    by_ch = {r['channel']: r['payload']['range'] for r in ranges}
    assert all(by_ch[ch] == 2 for ch in CHS)
    factors = np.array([by_ch[ch] / 16.384 * 2 / 50 for ch in CHS])
    arrays = []
    files = []
    identities = []
    for index in range(400, 432):
        phase = 'pilot' if index < 402 else 'full'
        path = ROOT / f'ntuples/energy_ml_stage183/{phase}_{index}_controls.jsonl.gz'
        with gzip.open(path, 'rt') as f:
            rows = [json.loads(line) for line in f]
        for row in rows:
            boards = row['boards']
            assert len({b['board'] for b in boards}) == len(boards)
            channels = {}
            for b in boards:
                assert b['decoded'] and b['valid'] and not b['board_fail']
                assert len({c['channel'] for c in b['channels']}) == len(b['channels'])
                channels.update({b['board'] * 16 + c['channel']: c['adc'] for c in b['channels']})
            a = np.array([channels[ch] for ch in CHS], float)
            assert a.shape == (8, 280)
            arrays.append(a)
            files.append(index)
            identities.append([index, row['eventID'], row['raw_entry']])
    adc = np.stack(arrays)
    files = np.array(files)
    assert len(adc) == 116 and len(set(map(tuple, identities))) == 116
    e = adc[:, :, :40].mean(2)[:, :, None] - adc
    signed = e[:, :, 60:140].sum(2) * factors
    positive = np.maximum(e[:, :, 60:140], 0).sum(2) * factors
    offsigned = e[:, :, 180:256].sum(2) * factors
    offpositive = np.maximum(e[:, :, 180:256], 0).sum(2) * factors
    l1 = np.abs(e).sum(2) * factors
    fit = files < 416
    bound = l1[fit].max(0)
    channel_rows = []
    for k, ch in enumerate(CHS):
        channel_rows.append(dict(channel=ch, fit_N=int(fit.sum()), heldout_N=int((~fit).sum()),
            pC_per_ADC_sample=factors[k], signed_mean_pC=float(signed[:, k].mean()),
            positive_mean_pC=float(positive[:, k].mean()), signed_sd_pC=float(signed[:, k].std(ddof=1)),
            positive_sd_pC=float(positive[:, k].std(ddof=1)), off_signed_mean_pC=float(offsigned[:, k].mean()),
            off_positive_mean_pC=float(offpositive[:, k].mean()), all280_L1_fit_max_pC=float(bound[k]),
            all280_L1_heldout_max_pC=float(l1[~fit, k].max()),
            heldout_exceed_fit_bound_N=int((l1[~fit, k] > bound[k]).sum())))
    return dict(adc=adc, e=e, factors=factors, signed=signed, positive=positive, l1=l1,
                files=files, identities=identities, bound=bound, channel_rows=channel_rows)


def read_phys(phase):
    fields = ['raw_charge', 'raw_peak', 'baseline_rms', 'status', 'localtime', 'bcidtime']
    branches = ['run', 'eventID'] + [f'Calo{gain}{j}_{field}' for gain in ['Lo', 'Hi'] for j in range(4) for field in fields]
    tick = time.perf_counter()
    loops = []
    with uproot.open(P['PHYS'], array_cache=None, num_workers=4) as f:
        t = f['nt']
        n = t.num_entries
        assert set(branches) <= set(t.keys()) and n == OLD['N']
        pieces = []
        spans = [(0, 4096), (4096, 8192)] if phase == 'pilot' else [(0, n)]
        for a, b in spans:
            cpu = time.process_time()
            pieces.append(t.arrays(branches, entry_start=a, entry_stop=b, library='np'))
            loops.append(time.process_time() - cpu)
        data = {k: np.concatenate([v[k] for v in pieces]) for k in branches}
        readbytes = f.file.source.num_requested_bytes
    assert np.all(data['run'] == 15838)
    # Exact original 8192 prefix includes raw/status and original status0-only timing use below.
    with np.load(ROOT / 'ntuples/energy_ml_stage181/pilot.npz') as z:
        for k in branches:
            if k.endswith(('_localtime', '_bcidtime')):
                label = k.rsplit('_', 1)[0]
                use = data[label + '_status'][:8192] == 0
                np.testing.assert_array_equal(data[k][:8192][use], z[k][use])
            else:
                np.testing.assert_array_equal(data[k][:8192], z[k])
    return data, dict(source_N=n, N=len(data['run']), loop_CPU_s=loops,
                      ROOT_read_bytes=int(readbytes), read_wall_s=time.perf_counter()-tick, prefix8192_exact=True)


def module_data(data, j):
    v = lambda gain, field: data[f'Calo{gain}{j}_{field}'].astype(float)
    ql, qh, pl, ph, rl, rh = [v(g, f) for g, f in [('Lo','raw_charge'), ('Hi','raw_charge'),
        ('Lo','raw_peak'), ('Hi','raw_peak'), ('Lo','baseline_rms'), ('Hi','baseline_rms')]]
    sl, sh = v('Lo','status'), v('Hi','status')
    finite = np.isfinite(np.stack([ql, qh, pl, ph, rl, rh])).all(0)
    pre = (sl == 0) & (sh == 0) & finite & (ql > 0) & (qh > 0) & (rl > 0) & (rh > 0)
    base = pre & (pl >= 10*rl) & (ph >= 10*rh)
    # Do not calculate time differences from nonzero-status measurements.
    dt = np.full(len(ql), np.nan)
    both = (sl == 0) & (sh == 0)
    idx = np.flatnonzero(both)
    lt = data[f'CaloLo{j}_localtime'][idx].astype(float)
    ht = data[f'CaloHi{j}_localtime'][idx].astype(float)
    lb = data[f'CaloLo{j}_bcidtime'][idx].astype(float)
    hb = data[f'CaloHi{j}_bcidtime'][idx].astype(float)
    good = np.isfinite(lt) & np.isfinite(ht) & (lt > 0) & (ht > 0) & np.isfinite(lb) & np.isfinite(hb) & (lb != -999) & (hb != -999)
    offset = next(r['offset_ns'] for r in TIMES['offsets'] if r['module'] == j and r['definition'] == 'local')
    dt[idx[good]] = ht[good] - lt[good] - offset
    entry = np.arange(len(ql))
    support = dict(module=j, N=len(ql), preSNR_N=int(pre.sum()), overlap_N=int(base.sum()),
        strict_time_N=int((base & np.isfinite(dt)).sum()), negativeQ_N=int((ql < 0).sum() + (qh < 0).sum()),
        minus999Q_N=int((ql == -999).sum() + (qh == -999).sum()), nonfinite_N=int((~finite).sum()),
        paired_status0_N=int(both.sum()), Lo_nonzero_Hi_status0_N=int(((sl != 0) & (sh == 0)).sum()))
    compact = dict(entry=entry[pre], eventID=data['eventID'][pre], ql=ql[pre], qh=qh[pre], pl=pl[pre], ph=ph[pre],
                   rl=rl[pre], rh=rh[pre], dt=dt[pre], base=base[pre])
    return compact, support


def cov(x, y):
    return float(np.cov(x, y, ddof=1)[0, 1]) if len(x) > 1 else None


def diagnostic(j, a, rho, bound):
    train = (a['entry']//8192) % 2 == 0
    residual = a['qh']-rho*a['ql']
    relative = a['qh']/(rho*a['ql'])-1
    b = float(bound[j+4]+rho*bound[j])
    rows = []
    for group in ['preSNR', 'all', 'within2ns', 'outside2ns']:
        use = ~train
        if group != 'preSNR':
            use &= a['base']
        if group == 'within2ns':
            use &= np.isfinite(a['dt']) & (np.abs(a['dt']) <= 2)
        if group == 'outside2ns':
            use &= np.isfinite(a['dt']) & (np.abs(a['dt']) > 2)
        for lo, hi in zip(P['bins_raw_peak_mV'][:-1], P['bins_raw_peak_mV'][1:]):
            mask = use & (a['pl'] >= lo) & (a['pl'] < hi)
            n = int(mask.sum())
            rows.append(dict(module=j, group=group, Lo_peak_lower_mV=lo, Lo_peak_upper_mV=hi, N=n,
                median_ratio_residual=float(np.median(relative[mask])) if n else None,
                median_difference_pC=float(np.median(residual[mask])) if n else None,
                abs95_difference_pC=float(np.quantile(np.abs(residual[mask]), .95)) if n else None,
                empirical_bound_pC=b, beyond_bound_N=int((np.abs(residual[mask]) > b).sum()),
                required_bound_multiplier95=float(np.quantile(np.abs(residual[mask])/b, .95)) if n else None))
    moments=[]
    for name, use in [('all', ~train & a['base']), ('within2ns', ~train & a['base'] & (np.abs(a['dt'])<=2))]:
        for axis, x in [('Lo', a['ql']), ('Hi_over_rho', a['qh']/rho)]:
            xx=x[use]
            slope=cov(residual[use],xx)/float(xx.var(ddof=1)) if len(xx)>1 and xx.var()>0 else None
            moments.append(dict(module=j,group=name,axis=axis,N=int(use.sum()),difference_covariance_pC2=cov(residual[use],xx),difference_slope=slope))
    use=~train & a['base'] & (np.abs(a['dt'])<=2)
    mid=use & (a['pl']>=100) & (a['pl']<250)
    high=use & (a['pl']>=500) & (a['pl']<2000)
    contrast=float(np.median(relative[high])-np.median(relative[mid])) if mid.any() and high.any() else None
    rng=np.random.default_rng(20261108195)
    blocks=np.unique(a['entry'][~train]//8192)
    block_mid=[relative[mid & (a['entry']//8192 == k)] for k in blocks]
    block_high=[relative[high & (a['entry']//8192 == k)] for k in blocks]
    samples=[]
    for _ in range(500):
        draw=rng.integers(len(blocks),size=len(blocks))
        m=np.concatenate([block_mid[k] for k in draw]);h=np.concatenate([block_high[k] for k in draw])
        if len(m) and len(h):samples.append(float(np.median(h)-np.median(m)))
    low,high95=np.quantile(samples,[.025,.975]).tolist() if samples else [None,None]
    contrast_row=dict(module=j,mid_N=int(mid.sum()),high_N=int(high.sum()),contrast_ratio=contrast,
        low95=low,high95=high95,bootstrap_valid_N=len(samples),heldout_blocks_N=len(blocks),
        conditional_on_scale=True,file_independence_certified=False,
        mid_median_difference_pC=float(np.median(residual[mid])) if mid.any() else None,
        high_median_difference_pC=float(np.median(residual[high])) if high.any() else None,
        empirical_bound_pC=b, high_beyond_bound_N=int((np.abs(residual[high])>b).sum()))
    return rows,moments,contrast_row


def free_scale_constraints(j,a,bound):
    """Necessary coverage constraints, without fitting or choosing a new rho."""
    held=((a['entry']//8192)%2==1) & a['base'] & (np.abs(a['dt'])<=2)
    low=np.maximum(0,a['qh']-bound[j+4])/(a['ql']+bound[j])
    upper=np.full(len(low),np.inf)
    positive=a['ql']>bound[j]
    upper[positive]=(a['qh'][positive]+bound[j+4])/(a['ql'][positive]-bound[j])
    rows=[]
    for name,lo,hi in [('mid',100,250),('high',500,2000)]:
        use=held & (a['pl']>=lo) & (a['pl']<hi)
        n=int(use.sum());k=math.ceil(.95*n)
        lower=float(np.sort(low[use])[k-1]) if n else None
        u=float(np.sort(upper[use])[n-k]) if n else None
        rows.append(dict(group=name,N=n,required_covered_N=k,necessary_rho_lower=lower,
            necessary_rho_upper=u if u is not None and math.isfinite(u) else None,
            upper_unbounded=u is not None and not math.isfinite(u)))
    present=[r for r in rows if r['N']]
    lo=max(r['necessary_rho_lower'] for r in present) if present else None
    hi=min((r['necessary_rho_upper'] for r in present if not r['upper_unbounded']),default=None)
    return dict(module=j,groups=rows,common_necessary_lower=lo,common_necessary_upper=hi,
        empirical_95pct_each_group_possible_not_excluded=bool(lo is not None and (hi is None or lo<=hi)),
        sufficient_for_model=False,population_coverage_certified=False,noise_transfer_certified=False)


def main(phase):
    tick=time.perf_counter();cpu=time.process_time()
    c=controls();data,perf=read_phys(phase)
    support=[];fits=[];bins=[];moments=[];contrasts=[];free_scale=[]
    for j in range(4):
        a,s=module_data(data,j);support.append(s)
        if phase=='full':
            assert s['overlap_N']==OLD['support'][j]['positive_highSNR_overlap_N']
            assert s['paired_status0_N']==OLD['support'][j]['paired_status0_N']
            original=a['base'] & (a['entry']%2==0)
            lograt=np.log(a['qh']/a['ql'])
            assert math.isclose(math.exp(float(np.median(lograt[original]))),OLD['relative_fits'][j]['relative_Hi_over_Lo_scale'],rel_tol=1e-12)
            odd=a['base'] & (a['entry']%2==1)
            quant=np.quantile(np.exp(lograt[odd]-np.median(lograt[original]))-1,[.025,.5,.975])
            np.testing.assert_allclose(quant,OLD['relative_fits'][j]['validation_relative_residual_quantiles'],rtol=1e-11,atol=1e-11)
        train=a['base'] & ((a['entry']//8192)%2==0)
        held=a['base'] & ~((a['entry']//8192)%2==0)
        rho=math.exp(float(np.median(np.log(a['qh'][train]/a['ql'][train])))) if phase=='full' and train.sum()>=100 else None
        fits.append(dict(module=j,train_N=int(train.sum()),heldout_N=int(held.sum()),rho=rho))
        if rho is not None:
            br,mo,co=diagnostic(j,a,rho,c['bound'])
            for row in mo:
                use=held.copy()
                if row['group']=='within2ns':use &= np.abs(a['dt'])<=2
                x=a['ql'] if row['axis']=='Lo' else a['qh']/rho
                variance=float(x[use].var(ddof=1)) if use.sum()>1 else None
                for label,noise in [('signed_window',c['signed']),('rectified_zero_signal',c['positive'])]:
                    error=noise[:,j] if row['axis']=='Lo' else noise[:,j+4]/rho
                    cv=cov(noise[:,j+4]-rho*noise[:,j],error)
                    row[label+'_covariance_pC2']=cv
                    row[label+'_conditional_slope']=cv/variance if variance else None
                row['noise_transfer_certified']=False
            bins+=br;moments+=mo;contrasts.append(co)
            free_scale.append(free_scale_constraints(j,a,c['bound']))
        np.savez_compressed(CACHE/f'{phase}_module{j}.npz',**a)
    table(f'{phase}_noise.tsv',c['channel_rows'])
    if bins:
        table('full_bins.tsv',bins);table('full_moments.tsv',moments);table('full_contrasts.tsv',contrasts)
    heldcontrol=c['files']>=416
    pair_noise=[]
    for j in range(4):
        rho=fits[j]['rho'] if fits[j]['rho'] is not None else OLD['relative_fits'][j]['relative_Hi_over_Lo_scale']
        b=float(c['bound'][j+4]+rho*c['bound'][j])
        pair_noise.append(dict(module=j,rho=rho,fit_controls_N=int((~heldcontrol).sum()),heldout_controls_N=int(heldcontrol.sum()),
            joint_L1_heldout_exceed_N=int(((c['l1'][:,j+4]+rho*c['l1'][:,j])[heldcontrol]>b).sum()),
            signed_residual_sd_pC=float((c['signed'][:,j+4]-rho*c['signed'][:,j]).std(ddof=1)),empirical_bound_pC=b))
    summary=dict(passed=True,phase=phase,**perf,support=support,fits=fits,contrasts=contrasts,free_scale_constraints=free_scale,control_N=116,
        noise=pair_noise,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
        RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        actual_error_model_identified=False,nonlinearity_certified=False,absolute_response_certified=False,
        saturation_response_certified=False,file_independent_validation=False,overall_complete=False,promotion=False)
    write(f'{phase}_summary.json',summary)
    if phase=='full':
        import runpy
        runpy.run_path('ml/stage195_plot.py')
    print(summary,flush=True)


if __name__=='__main__':
    assert sys.argv[1] in ['pilot','full']
    main(sys.argv[1])
