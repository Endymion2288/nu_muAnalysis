#!/usr/bin/env python3
"""Paired truth accuracy of backward leaders and the forward candidates selected by merge."""

import argparse
from collections import Counter
import csv
import gzip
import json
from pathlib import Path
import resource
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import binomtest

from report_tracking_comparison import figure_save, save_table
from report_tracking_loss_details import measurement_index, same


def primary(raw):
    pdg = np.asarray(raw['truth_pdg'])
    selected = pdg == pdg[0]*13/14
    for axis in 'xyz':
        selected &= abs(np.asarray(raw['truth_prod_'+axis])-raw['truth_dec_'+axis][0]) <= 1e-4
    index = np.flatnonzero(selected).item()
    return index, int(raw['truth_barcode'][index]), int(pdg[index])


def point_at(states, z):
    states = np.asarray(states)
    states = states[np.argsort(states[:,2])]
    unique = np.r_[True, np.diff(states[:,2]) > 1e-6]
    states = states[unique]
    if len(states) < 2 or z < states[0,2] or z > states[-1,2]:
        return None
    hi = min(max(np.searchsorted(states[:,2], z), 1), len(states)-1)
    low = hi-1
    if states[hi,2]-states[low,2] > 150:
        return None
    weight = (z-states[low,2])/(states[hi,2]-states[low,2])
    return states[low]*(1-weight)+states[hi]*weight


def make_row(event, truth_event, mechanisms):
    # Cross-check new raw TrackCollection matching against the official ntuple matcher
    # for every candidate that survived the ntuple's long-track requirement.
    for mode in ('forward','backward','merge'):
        old = event['modes'][mode]['raw']; match_columns = truth_event['modes'][mode]
        for i in range(len(old['Track_pz0'])):
            j = measurement_index(event,mode,i); match = truth_event['raw_truth'][mode][j]['truth']
            if match is None:
                assert match_columns['t_pdg'][i] == 0
            else:
                assert match_columns['t_pdg'][i] == match['pdg']
                assert match_columns['t_barcode'][i] == match['barcode']
                assert np.allclose([match_columns['t_'+axis][i] for axis in ('px','py','pz')],
                                   match['p_mev'],rtol=2e-7,atol=1e-5)
                candidate = truth_event['raw_truth'][mode][j]
                assert np.isclose(match_columns['t_truthHitRatio'][i],
                                  match['hit_count']/(candidate['ndof']+5),rtol=2e-7)
                parent = match['parents'][0] if match['parents'] else dict(barcode=0,pdg=0)
                assert match_columns['t_barcode_parent'][i] == parent['barcode']
                assert match_columns['t_pdg_parent'][i] == parent['pdg']
    raw = event['modes']['backward']['raw']
    index, barcode, pdg = primary(raw)
    bi = int(event['modes']['backward']['scalars']['LeadTrack_Idx'])
    bj = measurement_index(event,'backward',bi)
    mi = int(event['modes']['merge']['scalars']['LeadTrack_Idx'])
    mj = measurement_index(event,'merge',mi) if mi >= 0 else int(mechanisms['blocking_merge_raw_index'])
    chosen = event['measurements']['merge'][mj]
    matches = [i for i, track in enumerate(event['measurements']['forward'])
               if same(np.asarray(track['states']),np.asarray(chosen['states'])) and
               track['chi2'] == chosen['chi2'] and track['ndof'] == chosen['ndof']]
    assert len(matches) == 1, (event['run'],event['event'],matches)
    fj = matches[0]
    fi = int(event['modes']['forward']['scalars']['LeadTrack_Idx'])
    flj = measurement_index(event,'forward',fi) if fi >= 0 else -1
    bt = truth_event['raw_truth']['backward'][bj]
    ft = truth_event['raw_truth']['forward'][fj]
    pt = np.array([raw['truth_'+axis][index] for axis in ('px','py','pz')])/1000
    truth_p, truth_pz = np.linalg.norm(pt), pt[2]
    row = dict(run=event['run'],eventID=event['event'],first_failed_cut=mechanisms['first_failed_cut'],
               mechanism=mechanisms['mechanism'],merge_long=mi>=0,forward_selected_raw_index=int(fj),
               blocking_priority=mechanisms['blocking_priority'],
               backward_raw_index=bj,selected_is_forward_leader=bool(fj==flj),
               primary_barcode=barcode,primary_pdg=pdg,truth_pz_GeV=truth_pz,truth_p_GeV=truth_p,
               truth_vertex_r_mm=mechanisms['truth_r_mm'],truth_vertex_z_mm=mechanisms['truth_z_mm'])
    for label,track in [('backward',bt),('forward',ft)]:
        p = np.asarray(track['first'][3:])/1000; magnitude = np.linalg.norm(p)
        match = track['truth']; matched = bool(match and match['barcode']==barcode and match['pdg']==pdg)
        parent_ok = bool(matched and match['parents'] and match['parents'][0]['barcode']==raw['truth_barcode'][0]
                         and match['parents'][0]['pdg']==raw['truth_pdg'][0])
        purity = match['hit_count']/track['measurements'] if match else np.nan
        if matched:
            assert np.allclose(np.asarray(match['p_mev'])/1000,pt,rtol=2e-7,atol=1e-6)
        row.update({label+'_pz_GeV':p[2],label+'_p_GeV':magnitude,
                    label+'_pz_relative':p[2]/truth_pz-1,label+'_p_relative':magnitude/truth_p-1,
                    label+'_abs_pz_relative':abs(p[2]/truth_pz-1),label+'_abs_p_relative':abs(magnitude/truth_p-1),
                    label+'_abs_qop_error':abs(track['charge']*truth_p/magnitude+np.sign(pdg)),
                    label+'_charge_flip':int(track['charge'] != -np.sign(pdg)),
                    label+'_matched_primary':matched,label+'_parent_confirmed':parent_ok,
                    label+'_matched_pdg':match['pdg'] if match else 0,
                    label+'_matched_barcode':match['barcode'] if match else -1,
                    label+'_matched_truth_pz_GeV':match['p_mev'][2]/1000 if match else np.nan,
                    label+'_matched_truth_p_GeV':float(np.linalg.norm(match['p_mev']))/1000 if match else np.nan,
                    label+'_abs_matched_pz_relative':abs(p[2]/(match['p_mev'][2]/1000)-1)
                        if match and match['p_mev'][2] != 0 else np.nan,
                    label+'_abs_matched_p_relative':abs(magnitude/(np.linalg.norm(match['p_mev'])/1000)-1)
                        if match and np.linalg.norm(match['p_mev']) != 0 else np.nan,
                    label+'_hit_fraction':purity,label+'_chi2_ndof':track['chi2']/track['ndof'] if track['ndof'] else np.nan,
                    label+'_measurements':track['measurements'],label+'_first_z_mm':track['first'][2]})
        for station in (1,2,3):
            reference = np.array([raw[f'truth_st{station}_'+axis][index] for axis in ('x','y','z')])
            truth_direction = np.array([raw[f'truth_st{station}_'+axis][index] for axis in ('px','py','pz')])
            states = event['measurements']['backward' if label=='backward' else 'forward'][bj if label=='backward' else fj]['states']
            prediction = point_at(states, reference[2]) if np.all(np.isfinite(reference)) else None
            xy, radial, direction = np.nan,np.nan,np.nan
            if prediction is not None:
                xy = np.linalg.norm(prediction[:2]-reference[:2])
                radial = abs(np.linalg.norm(prediction[:2])-np.linalg.norm(reference[:2]))
                if np.all(np.isfinite(truth_direction)) and truth_direction[2] != 0:
                    direction = 1000*np.linalg.norm(prediction[3:5]/prediction[5]-truth_direction[:2]/truth_direction[2])
            row[label+f'_st{station}_xy_mm'] = xy
            row[label+f'_st{station}_radius_mm'] = radial
            row[label+f'_st{station}_slope_mrad'] = direction
    row['both_primary'] = row['backward_matched_primary'] and row['forward_matched_primary']
    row['both_parent_confirmed'] = row['backward_parent_confirmed'] and row['forward_parent_confirmed']
    row['both_high_purity'] = row['both_primary'] and min(row['backward_hit_fraction'],row['forward_hit_fraction']) >= .8
    row['same_truth_particle'] = bool(bt['truth'] and ft['truth'] and bt['truth']['barcode']==ft['truth']['barcode']
                                      and bt['truth']['pdg']==ft['truth']['pdg'])
    row['primary_truth_pz_above_100GeV'] = bool(truth_pz>100)
    row['backward_closer_pz'] = row['backward_abs_pz_relative'] < row['forward_abs_pz_relative']
    row['forward_closer_pz'] = row['forward_abs_pz_relative'] < row['backward_abs_pz_relative']
    return row


def summarize(rows, scope, metric):
    b = np.array([row['backward_'+metric] for row in rows],dtype=float)
    f = np.array([row['forward_'+metric] for row in rows],dtype=float)
    valid = np.isfinite(b)&np.isfinite(f); b,f = b[valid],f[valid]
    if not len(b):
        return None
    difference = b-f
    bw,fw = int(np.sum(b<f)),int(np.sum(f<b)); ties = len(b)-bw-fw
    test = binomtest(bw,bw+fw) if bw+fw else None
    ci = test.proportion_ci(confidence_level=.95) if test else (np.nan,np.nan)
    rng = np.random.default_rng(20261030)
    samples = rng.integers(len(b),size=(10000,len(b)))
    med_delta = np.median(b[samples],axis=1)-np.median(f[samples],axis=1)
    return dict(scope=scope,metric=metric,events=len(b),backward_closer=bw,forward_closer=fw,ties=ties,
                backward_median=float(np.median(b)),forward_median=float(np.median(f)),
                backward_mean=float(np.mean(b)),forward_mean=float(np.mean(f)),
                backward_p90=float(np.quantile(b,.9)),forward_p90=float(np.quantile(f,.9)),
                median_paired_delta=float(np.median(difference)),
                difference_of_medians=float(np.median(b)-np.median(f)),
                difference_of_medians_ci95_low=float(np.quantile(med_delta,.025)),
                difference_of_medians_ci95_high=float(np.quantile(med_delta,.975)),
                sign_test_two_sided_p=test.pvalue if test else np.nan,
                backward_win_fraction_ci95_low=float(ci[0]),backward_win_fraction_ci95_high=float(ci[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--combined',type=Path)
    parser.add_argument('--allow-partial',action='store_true')
    args = parser.parse_args();repo=args.repo.resolve();tick=time.monotonic()
    output=repo/'workbook/stage20_tracking_truth';output.mkdir(exist_ok=True)
    with gzip.open(repo/'ntuples/tracking_loss_stage17/diagnostics.json.gz','rt') as source:
        original={(event['run'],event['event']):event for event in json.load(source)}
    mechanisms={(int(row['run']),int(row['eventID'])):row for row in csv.DictReader((repo/'workbook/stage17_tracking_loss/event_mechanisms.tsv').open(),delimiter='\t')}
    if args.combined:
        with gzip.open(args.combined,'rt') as source:truth=json.load(source)
    else:
        truth=[json.loads(path.read_text()) for path in sorted((repo/'ntuples/tracking_truth_stage20').glob('*.json'))]
    keys=[(event['run'],event['event']) for event in truth]
    assert len(set(keys))==len(keys)
    if not args.allow_partial:assert set(keys)==set(original)
    rows=[]
    for key,event in zip(keys,truth):
        assert event['stage17_verified']
        assert event['expected_bits']==original[key]['expected_bits']
        rows.append(make_row(original[key],event,mechanisms[key]))
    save_table(output/'truth_by_event.tsv',list(rows[0]),rows)
    if not args.combined and not args.allow_partial:
        serialized=json.dumps(truth,allow_nan=True,separators=(',',':'))
        with gzip.open(repo/'ntuples/tracking_truth_stage20/truth.json.gz','wt') as target:target.write(serialized)
        with gzip.open(repo/'ntuples/tracking_truth_stage20/truth.json.gz','rt') as source:
            assert json.dumps(json.load(source),allow_nan=True,separators=(',',':'))==serialized
    scopes=[('all_89_including_nonlong',rows),('long_84',[r for r in rows if r['merge_long']]),
            ('same_primary_long',[r for r in rows if r['merge_long'] and r['both_primary']]),
            ('same_primary_high_purity_long',[r for r in rows if r['merge_long'] and r['both_high_purity']]),
            ('different_particle_long',[r for r in rows if r['merge_long'] and not r['same_truth_particle']]),
            ('same_primary_without_sibyll',[r for r in rows if r['merge_long'] and r['both_primary'] and r['run']!=200080]),
            ('same_primary_nonlong',[r for r in rows if not r['merge_long'] and r['both_primary']]),
            ('nonlong_5',[r for r in rows if not r['merge_long']])]
    scopes += [('mechanism_'+mechanism,[r for r in rows if r['mechanism']==mechanism and r['both_primary'] and r['merge_long']])
               for mechanism in sorted({r['mechanism'] for r in rows})]
    scopes += [('cut_'+cut,[r for r in rows if r['first_failed_cut']==cut and r['both_primary'] and r['merge_long']])
               for cut in sorted({r['first_failed_cut'] for r in rows})]
    metrics=['abs_pz_relative','abs_p_relative','abs_qop_error']
    metrics += [f'st{s}_{variable}' for s in (1,2,3) for variable in ('xy_mm','radius_mm','slope_mrad')]
    summaries=[]
    for scope,selected in scopes:
        for metric in metrics:
            entry=summarize(selected,scope,metric)
            if entry:summaries.append(entry)
    # When both candidates identify the same secondary particle, compare against
    # that particle's own production momentum, rather than the primary muon.
    for scope,selected in [
        ('same_particle_long',[r for r in rows if r['merge_long'] and r['same_truth_particle']]),
        ('same_other_particle_all',[r for r in rows if r['same_truth_particle'] and not r['both_primary']]),
        ('same_other_particle_long',[r for r in rows if r['merge_long'] and r['same_truth_particle'] and not r['both_primary']])]:
        for metric in ('abs_matched_pz_relative','abs_matched_p_relative'):
            entry=summarize(selected,scope,metric)
            if entry:summaries.append(entry)
    save_table(output/'accuracy_summary.tsv',list(summaries[0]),summaries)
    identity_rows=[]
    for scope,selected in scopes:
        identity_rows.append(dict(scope=scope,events=len(selected),
                                  backward_primary=sum(r['backward_matched_primary'] for r in selected),
                                  forward_primary=sum(r['forward_matched_primary'] for r in selected),
                                  both_primary=sum(r['both_primary'] for r in selected),
                                  same_truth_particle=sum(r['same_truth_particle'] for r in selected),
                                  both_high_purity=sum(r['both_high_purity'] for r in selected),
                                  backward_charge_flip=sum(r['backward_charge_flip'] for r in selected),
                                  forward_charge_flip=sum(r['forward_charge_flip'] for r in selected),
                                  primary_truth_pz_below_cut=sum(not r['primary_truth_pz_above_100GeV'] for r in selected)))
    save_table(output/'matching_summary.tsv',list(identity_rows[0]),identity_rows)
    mainrows=[r for r in rows if r['merge_long'] and r['both_primary']]
    if mainrows:
        plt.rcParams.update({'font.size':10,'svg.fonttype':'none'})
        fig,axes=plt.subplots(2,3,figsize=(15,9))
        for ax,metric,title in zip(axes[0],['abs_pz_relative','st1_xy_mm','st1_slope_mrad'],
                                   ['|pz / primary production pz − 1|','Station 1 position residual (mm)',
                                    'Station 1 direction residual (mrad)']):
            b=np.array([r['backward_'+metric] for r in mainrows]);f=np.array([r['forward_'+metric] for r in mainrows]);v=np.isfinite(b)&np.isfinite(f)
            ax.scatter(b[v],f[v],s=28,c='#0072B2',alpha=.7)
            limits=[max(min(b[v].min(),f[v].min())*.6,1e-6),max(b[v].max(),f[v].max())*1.3]
            ax.plot(limits,limits,color='grey');ax.set_xscale('log');ax.set_yscale('log')
            ax.set(xlabel='Backward error',ylabel='Merge-selected forward error',title=title);ax.grid(alpha=.2)
        for label,color in [('backward','#D55E00'),('forward','#0072B2')]:
            values=np.sort([r[label+'_abs_pz_relative'] for r in mainrows])
            axes[1,0].step(values,np.arange(1,len(values)+1)/len(values),where='post',label=label,color=color)
        axes[1,0].set(xscale='log',xlabel='Absolute relative pz error (production reference)',ylabel='Cumulative fraction');axes[1,0].legend()
        cuts=sorted({r['first_failed_cut'] for r in mainrows});bcounts=[];fcounts=[]
        for cut in cuts:
            selected=[r for r in mainrows if r['first_failed_cut']==cut]
            bcounts.append(sum(r['backward_abs_pz_relative']<r['forward_abs_pz_relative'] for r in selected))
            fcounts.append(sum(r['forward_abs_pz_relative']<r['backward_abs_pz_relative'] for r in selected))
        labels=[c.replace('Track R at max radius < 95 mm','rmax').replace('Track R at IFT < 95 mm','rIFT').replace('Track pz > 100 GeV','pz').replace('Track nDoF >= 9','nDoF').replace('Leading track has chi2/ndof < 15','chi2/ndof').replace('Leading track theta < 25 mrad','theta') for c in cuts]
        axes[1,1].barh(labels,bcounts,label='Backward closer',color='#D55E00')
        axes[1,1].barh(labels,fcounts,left=bcounts,label='Forward closer',color='#0072B2')
        axes[1,1].set_xlabel('Events; primary-matched long-track pairs');axes[1,1].legend(fontsize=8)
        axes[1,2].scatter([r['forward_chi2_ndof']-r['backward_chi2_ndof'] for r in mainrows],
                           [r['forward_abs_pz_relative']-r['backward_abs_pz_relative'] for r in mainrows],s=24,alpha=.7)
        axes[1,2].axhline(0,color='grey');axes[1,2].axvline(0,color='grey')
        axes[1,2].set(xlabel='Forward − backward chi2/ndof',ylabel='Forward − backward absolute relative pz error')
        axes[1,2].set_yscale('symlog',linthresh=.1)
        fig.suptitle(f'{len(mainrows)} pairs matched to the same primary muon · selected backward-pass / merge-fail sample\n'
                     'Production momentum reference includes transport effects; station position/direction use simulated hit references')
        fig.tight_layout();figure_save(fig,output,'truth_accuracy_comparison')
    categories=Counter((r['backward_matched_primary'],r['forward_matched_primary']) for r in rows)
    summary=dict(events=len(rows),long_pairs=sum(r['merge_long'] for r in rows),
                 official_long_candidates_checked=sum(len(event['modes'][mode]['t_pdg'])
                    for event in truth for mode in ('forward','backward','merge')),
                 raw_candidates_diagnosed=sum(len(event['raw_truth'][mode])
                    for event in truth for mode in ('forward','backward','merge')),
                 matching_categories={str(k):v for k,v in categories.items()},
                 same_particle=sum(r['same_truth_particle'] for r in rows),
                 both_primary=sum(r['both_primary'] for r in rows),
                 both_parent_confirmed=sum(r['both_parent_confirmed'] for r in rows),
                 both_high_purity=sum(r['both_high_purity'] for r in rows),
                 forward_selected_differs_from_forward_leader=[f'{r["run"]}/{r["eventID"]}' for r in rows if r['merge_long'] and not r['selected_is_forward_leader']],
                 wall_seconds=time.monotonic()-tick,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
