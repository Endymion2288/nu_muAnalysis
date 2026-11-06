"""Comparable migration, continuous KDE and energy-response figures (PNG/PDF)."""
import csv
import json
import os
import time
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, TwoSlopeNorm
import numpy as np
from sklearn.neighbors import KernelDensity

from stage125_evaluate import ROOT,OUT,CACHE,TUNES,EDGES,PAPER,load,quantile

COLORS=['#0072B2','#E69F00','#009E73','#CC79A7','#D55E00']
LABELS=['FTF_BIC','FTFP_INCLXX','FTFP_BERT_HP_JEFF33','FTFP_BERT_HP_ENDFB8','QGSP_BERT']
FIGURES=[]
COMPLETE=False


def rows(name):
    return list(csv.DictReader((OUT/name).open(),delimiter='\t'))


def style():
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':11,
                         'axes.labelsize':11,'figure.facecolor':'white','axes.spines.top':False,
                         'axes.spines.right':False,'savefig.dpi':180,'pdf.fonttype':42,
                         'axes.grid':False,'legend.frameon':False})


def save(fig,name,caption):
    if not COMPLETE:fig.text(.995,.002,'PREVIEW · source inventory incomplete',ha='right',va='bottom',color='#a33b20',fontsize=8)
    fig.savefig(OUT/(name+'.png'),bbox_inches='tight');fig.savefig(OUT/(name+'.pdf'),bbox_inches='tight')
    FIGURES.append(dict(name=name,caption=caption));plt.close(fig)


def matrix(scheme='paper'):
    # Render the already audited aggregates, including unsupported truth columns.
    aggregates=rows('matrices.tsv');summary={r['tune']:r for r in rows('sample_summary.tsv')}
    edges=PAPER if scheme=='paper' else EDGES
    labels=['<100','100–300','300–600','600–1000','≥1000'] if scheme=='paper' else [f'<{b:g}' if a==0 else f'{a:g}–{b:g}' if np.isfinite(b) else f'≥{a:g}' for a,b in zip(edges[:-1],edges[1:])]
    n=len(labels);fig,axs=plt.subplots(2,5,figsize=(21,9.2 if n==5 else 11),layout='constrained')
    cmap=plt.get_cmap('Blues').copy();cmap.set_bad('#dedede')
    for j,t in enumerate(TUNES):
        for i,model in enumerate(['direct','traditional']):
            ax=axs[i,j];h=np.zeros((n,n))
            for r in aggregates:
                if r['scheme']==scheme and r['tune']==t and r['model']==model:h[int(r['reco_bin']),int(r['true_bin'])]=float(r['weighted_count'])
            den=h.sum(0)
            p=np.divide(h,den[None,:],out=np.full_like(h,np.nan),where=den[None,:]>0)*100
            im=ax.imshow(np.ma.masked_invalid(p),origin='lower',vmin=0,vmax=100,cmap=cmap,interpolation='nearest')
            ax.set_xticks(range(n),labels,rotation=55,ha='right',fontsize=8)
            ax.set_yticks(range(n),labels,fontsize=8);ax.set_xlabel(r'True $E_\nu$ [GeV]')
            if j==0:ax.set_ylabel(('BDT' if i==0 else r'$p_{z,0}/0.8$')+'\n'+r'Reconstructed $E_\nu$ [GeV]')
            ax.set_title(LABELS[j]+f'\nN = {int(summary[t]["primary_N"]):,} selected views',fontsize=10)
            ax.set_xticks(np.arange(-.5,n,1),minor=True);ax.set_yticks(np.arange(-.5,n,1),minor=True)
            ax.grid(which='minor',color='white',linewidth=.8);ax.tick_params(which='minor',bottom=False,left=False)
            for y,x in np.ndindex(p.shape):
                if np.isnan(p[y,x]):text='—'
                elif p[y,x]<.05:text='·'
                else:text=f'{p[y,x]:.1f}'
                if n<=6 or np.isnan(p[y,x]) or p[y,x]>=1:ax.text(x,y,text,ha='center',va='center',color='white' if p[y,x]>48 else '#24313c',fontsize=8 if n<=6 else 6)
    fig.colorbar(im,ax=axs.ravel().tolist(),label=r'$P(E_{\rm reco}\ \mathrm{bin}\mid E_{\rm true}\ \mathrm{bin},\ selected)$ [%]',shrink=.77,pad=.015)
    fig.suptitle('Frozen direct62 vs traditional energy · MC24 Geant4 tunes\nTruth columns sum to 100%; known train/cal incoming excluded',fontsize=15)
    save(fig,'migration_'+scheme,'Truth on x, reconstructed energy on y; conditional on selection. Column normalization follows PRD Eqs.(9–10) and internal note §7.2. Absolute-energy projection, not the signed inverse-energy/rapidity 30×30 matrix. Explicit overflow retained: ≥1000 GeV in paper bins, ≥6400 GeV in fine bins. Dots denote <0.05%; gray columns with dashes mean no truth support, distinct from zero migration probability.')


def kde_density(task):
    points,weight,grid=task
    kde=KernelDensity(bandwidth=.08,kernel='gaussian',atol=1e-6,rtol=1e-4).fit(points,sample_weight=weight)
    return np.exp(kde.score_samples(grid))


def density(d,reference):
    sources=[('Stage 87 held-out development',reference,np.ones(len(reference['weight']),bool))]
    sources += [(LABELS[j],d,d['primary']&(d['tune']==t)) for j,t in enumerate(TUNES)]
    lo,hi=np.log10(40),np.log10(16000);g=np.linspace(lo,hi,150);xx,yy=np.meshgrid(g,g);grid=np.column_stack([xx.ravel(),yy.ravel()])
    for model in ['direct','traditional']:
        tasks=[];infos=[]
        for title,z,m in sources:
            x=np.log10(z['truth_E_GeV'][m]);y=z[model+'_logE'][m]/np.log(10);w=z['weight'][m]
            tasks.append((np.column_stack([x,y]),w,grid))
            inside=(x>=lo)&(x<=hi)&(y>=lo)&(y<=hi);frac=float(np.clip(np.dot(w,inside)/w.sum(),0,1))
            infos.append(dict(model=model,sample=title,N=len(w),shown_weight_fraction=frac,outside_weight_fraction=1-frac))
        cpus=int(os.environ.get('NU_MU_STAGE125_PLOT_CPUS','1'))
        if cpus>1:
            with ProcessPoolExecutor(max_workers=cpus,mp_context=mp.get_context('fork')) as pool:
                densities=list(pool.map(kde_density,tasks))
            points,weight,query=tasks[0];probe=kde_density((points,weight,query[:64]))
            np.testing.assert_array_equal(probe,densities[0][:64])
        else:densities=list(map(kde_density,tasks))
        densities=[a.reshape(xx.shape) for a in densities]
        fig,axs=plt.subplots(2,3,figsize=(15.5,10),layout='constrained');norm=LogNorm(.002,max(float(a.max()) for a in densities))
        for ax,(title,z,m),pdf,info in zip(axs.flat,sources,densities,infos):
            im=ax.pcolormesh(10**xx,10**yy,pdf,cmap='magma',norm=norm,shading='auto',rasterized=True)
            ax.plot([40,16000],[40,16000],c='white',lw=1.2,ls='--')
            ax.plot([40,16000],[60,24000],c='white',lw=.6,ls=':',alpha=.6)
            ax.plot([40,16000],[20,8000],c='white',lw=.6,ls=':',alpha=.6)
            ax.set(xscale='log',yscale='log',xlim=(40,16000),ylim=(40,16000),xlabel=r'True $E_\nu$ [GeV]',ylabel=r'Reconstructed $E_\nu$ [GeV]')
            ax.set_title(title,loc='left');ax.text(.03,.96,f'N = {info["N"]:,}\noutside view: {100*info["outside_weight_fraction"]:.2f}%',transform=ax.transAxes,va='top',color='white',fontsize=9)
        fig.colorbar(im,ax=axs.ravel().tolist(),label='Continuous probability density [dex⁻²]',shrink=.8,pad=.015)
        fig.suptitle(('Frozen direct62' if model=='direct' else 'Traditional '+r'$p_{z,0}/0.8$')+' · unbinned energy density\nGaussian KDE in log₁₀ energy; fixed 0.08 dex bandwidth, shared color scale',fontsize=15)
        save(fig,'continuous_density_'+model,'Unbinned Gaussian kernel density from every selected event, evaluated on a rendering grid; no analysis energy-bin counts. Density is with respect to dlog10(Etrue)dlog10(Ereco). Fixed bandwidth across tunes; white dashed line is exact response, dotted lines mark +50%/−50% response. Full-sample normalization; outside-view fractions recorded.')
        from stage125_evaluate import table
        table('density_view_'+model+'.tsv',infos)
    # All events are displayed directly. Alpha encodes overlap, without KDE or bins.
    fig,axs=plt.subplots(2,3,figsize=(15.5,10),layout='constrained')
    for ax,(title,z,m) in zip(axs.flat,sources):
        ax.scatter(z['truth_E_GeV'][m],np.exp(z['direct_logE'][m]),s=1,alpha=.12,c='#0072B2',rasterized=True,linewidths=0)
        ax.plot([40,16000],[40,16000],color='#D55E00',lw=1,ls='--')
        ax.set(xscale='log',yscale='log',xlim=(40,16000),ylim=(40,16000),xlabel=r'True $E_\nu$ [GeV]',ylabel=r'Reconstructed $E_\nu$ [GeV]',title=title)
    fig.suptitle('Frozen direct62 · every selected event, no binning or smoothing',fontsize=15)
    save(fig,'event_scatter','One point per selected view; no subsampling, energy bins or density smoothing. Point opacity is not a luminosity or incoming weight.')


def profiles(data):
    baseline=rows('stage87_reference_metrics.tsv')
    for model in ['direct','traditional']:
        fig,axs=plt.subplots(2,3,figsize=(16,9),layout='constrained')
        fields=[('median_bias_pct','Median relative bias [%]'),('R68_pct','Central 68% half-width [%]'),('log_RMSE','RMSE of ln(Ereco / Etrue)'),('positive_tail50_pct','Overestimate >50% [%]'),('negative_tail50_pct','Underestimate >50% [%]'),('tail50_pct','Total |relative error| >50% [%]')]
        for ax,(field,label) in zip(axs.flat,fields):
            for j,t in enumerate(TUNES):
                rr=[r for r in data if r['scope']=='primary' and r['model']==model and r['tune']==t and r['stratum'].startswith('E')]
                vals=[]
                for r in rr:
                    a,b=map(float,r['stratum'][1:].split('_'))
                    if a<50:continue
                    x=np.sqrt(a*(b if np.isfinite(b) else a*2));vals.append((x,r))
                vals.sort();x=[v[0] for v in vals];y=[float(v[1][field]) for v in vals]
                ax.plot(x,y,'o-',ms=3.5,lw=1.5,c=COLORS[j],label=LABELS[j])
                if field+'_low95' in vals[0][1]:
                    ax.fill_between(x,[float(v[1][field+'_low95']) for v in vals],[float(v[1][field+'_high95']) for v in vals],color=COLORS[j],alpha=.10)
                # Hollow markers flag sparse incoming support.
                for (xx,r),yy in zip(vals,y):
                    if int(r['incoming'])<30:ax.plot(xx,yy,'o',mfc='white',mec=COLORS[j],ms=5)
            ax.set(xscale='log',xlabel=r'True $E_\nu$ [GeV]',ylabel=label);ax.grid(alpha=.18)
            bb=[]
            for r in baseline:
                if r['model']!=model or not r['stratum'].startswith('E'):continue
                a,b=map(float,r['stratum'][1:].split('_'))
                if a>=50:bb.append((np.sqrt(a*(b if np.isfinite(b) else a*2)),float(r[field])))
            bb.sort();ax.plot([v[0] for v in bb],[v[1] for v in bb],':',c='#24313c',lw=1.2,label='Stage87 development test')
            if field=='median_bias_pct':ax.axhline(0,c='#53616c',lw=.8)
        axs[0,0].legend(fontsize=8)
        fig.suptitle(('Frozen direct62' if model=='direct' else 'Traditional '+r'$p_{z,0}/0.8$')+' · energy response by physics tune\nPrimary sample; only supported truth-energy bins shown; hollow markers: fewer than 30 incoming proxies',fontsize=14)
        save(fig,'energy_profiles_'+model,'Relative error = Ereco/Etrue − 1. R68 = (q84−q16)/2, not RMS or relative sigma. Natural-log RMSE includes every selected primary event. Shading, where shown, is a 500-replicate conditional incoming bootstrap 95% interval; sparse cells remain visible.')


def comparison(data,contrasts):
    fig,axs=plt.subplots(3,3,figsize=(16,13),layout='constrained')
    for j,(scope,title) in enumerate([('primary','Native sample composition'),('standardized','Common component × true-energy mix'),('fully_standardized','Common component × E × y × depth mix')]):
        for k,(field,label) in enumerate([('log_RMSE','log-energy RMSE'),('median_bias_pct','Median relative bias [%]'),('tail50_pct','|relative error| >50% [%]')]):
            ax=axs[j,k]
            for im,model in enumerate(['direct','traditional']):
                rr=[next(r for r in data if r['scope']==scope and r['stratum']=='all' and r['tune']==t and r['model']==model) for t in TUNES]
                x=np.arange(5)+(im-.5)*.22;y=np.array([float(r[field]) for r in rr]);ax.plot(x,y,'o' if im==0 else 's',c='#0072B2' if im==0 else '#8b9196',label='direct62' if im==0 else 'pz0 / 0.8')
                if field+'_low95' in rr[0]:ax.vlines(x,[float(r[field+'_low95']) for r in rr],[float(r[field+'_high95']) for r in rr],color='#0072B2' if im==0 else '#8b9196',lw=1.5)
            ax.set_xticks(range(5),TUNES,rotation=25,ha='right',fontsize=8);ax.set_ylabel(label);ax.set_title(title);ax.grid(axis='y',alpha=.18)
        axs[j,0].legend()
    fig.suptitle('Frozen model robustness · native vs standardized truth composition\nRMSE/tails: conditional incoming 95% intervals; median bias: point estimates',fontsize=14)
    save(fig,'robustness_overview','Native composition corrects the known QGSP file sampling. The second row uses the minimum common normalized component × fine true-energy distribution; the third also controls coarse true y and vertex depth. Unknown y has its own retained category. Targets and fixed cell boundaries were defined before new model outcomes. Within-cell variations and production differences remain; unsupported cells are not extrapolated.')
    fig,axs=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    for ax,quantity,label,zero in zip(axs,['log_RMSE','tail50_pct'],['RMSE ratio to JEFF33','Tail50 difference to JEFF33 [percentage points]'],[1,0]):
        for j,scope in enumerate(['primary','standardized','fully_standardized']):
            rr=[next(r for r in contrasts if r['scope']==scope and r['stratum']=='all' and r['tune']==t and r['model']=='direct' and r['quantity']==quantity) for t in TUNES]
            y=np.arange(5)+(j-1)*.20;value=np.array([float(r['estimate']) for r in rr]);lo=np.array([float(r['low95']) for r in rr]);hi=np.array([float(r['high95']) for r in rr])
            ax.errorbar(value,y,xerr=[value-lo,hi-value],fmt='o',capsize=3,label=['Native','E × component','E × component × y × depth'][j],color=['#0072B2','#D55E00','#009E73'][j])
        ax.axvline(zero,c='gray',lw=1,ls='--');ax.set_yticks(range(5),LABELS);ax.set_xlabel(label);ax.grid(axis='x',alpha=.15);ax.legend()
    fig.suptitle('Direct62 tune sensitivity · JEFF33 is the fixed comparison reference',fontsize=14)
    save(fig,'tune_contrasts','Reference JEFF33 is a comparison convention, not the training physics model. Shared incoming bootstrap multipliers retain known cross-tune dependence. Intervals do not include generator-parent/source certification, retraining, calibration estimation, response production, or full physical systematic uncertainties.')


def components(d):
    fig,axs=plt.subplots(3,5,figsize=(20,12),layout='constrained');edges=np.geomspace(.05,10,80)
    for j,t in enumerate(TUNES):
        for i,c in enumerate(['pi','k','charm']):
            ax=axs[i,j];m=d['primary']&(d['tune']==t)&(d['component']==c)
            for model,color,label in [('direct',COLORS[j],'direct62'),('traditional','#9ba2a8','pz0 / 0.8')]:
                ratio=np.exp(d[model+'_logE'][m])/d['truth_E_GeV'][m];w=d['weight'][m];h,_=np.histogram(ratio,bins=edges,weights=w);h=h/w.sum()/np.diff(np.log10(edges))
                ax.stairs(h,edges,color=color,label=label,lw=1.5)
            ax.axvline(1,c='#24313c',ls='--',lw=.8);ax.axvspan(.5,1.5,color='#0072B2',alpha=.04)
            ax.set(xscale='log',xlabel=r'$E_{\rm reco}/E_{\rm true}$',title=LABELS[j]+' · '+c)
            if j==0:ax.set_ylabel('Probability density [dex⁻¹]')
            ax.text(.97,.95,f'N = {int(m.sum()):,}',ha='right',va='top',transform=ax.transAxes)
    axs[0,0].legend(fontsize=8);fig.suptitle('Response distributions by neutrino production component\nUnit normalized per component; all events enter normalization, including tails outside the displayed range',fontsize=14)
    save(fig,'component_response','Separate π/K/charm unit-normalized energy response distributions. Histograms here are supplemental response diagnostics; the energy-energy heatmaps separately use continuous unbinned KDE.')


def differences(d):
    fig,axs=plt.subplots(1,4,figsize=(18,5),layout='constrained');ref='JEFF33';edges=PAPER
    def mat(t):
        m=d['primary']&(d['tune']==t);h=np.histogram2d(np.exp(d['direct_logE'][m]),d['truth_E_GeV'][m],bins=(edges,edges),weights=d['weight'][m])[0]
        return h/np.where(h.sum(0)>0,h.sum(0),np.nan)
    baseline=mat(ref);vv=[mat(t)-baseline for t in TUNES if t!=ref];limit=max(.01,max(float(np.nanmax(abs(v))) for v in vv))*100
    for ax,t,v in zip(axs,[t for t in TUNES if t!=ref],vv):
        im=ax.imshow(v*100,origin='lower',cmap='RdBu_r',norm=TwoSlopeNorm(0,-limit,limit));ax.set_title(t+' − JEFF33')
        labels=['<100','100–300','300–600','600–1000','≥1000'];ax.set_xticks(range(5),labels,rotation=50,ha='right',fontsize=8);ax.set_yticks(range(5),labels,fontsize=8)
        ax.set_xlabel('True energy [GeV]');ax.set_ylabel('Reconstructed energy [GeV]')
        for y,x in np.ndindex(v.shape):ax.text(x,y,f'{v[y,x]*100:+.1f}',ha='center',va='center',fontsize=8,color='white' if abs(v[y,x]*100)>limit*.55 else '#24313c')
    fig.colorbar(im,ax=axs.tolist(),label='Migration probability difference [percentage points]',shrink=.8)
    fig.suptitle('Direct62 migration changes relative to JEFF33 · truth-column normalization',fontsize=14)
    save(fig,'migration_differences','Differences of the native primary truth-column migration matrices, on a shared symmetric color scale. Composition within coarse truth bins remains a possible contributor; these differences are not a calibrated systematic covariance.')


def component_matrices(d):
    fig,axs=plt.subplots(3,5,figsize=(20,12.5),layout='constrained');labels=['<100','100–300','300–600','600–1000','≥1000']
    for j,t in enumerate(TUNES):
        for i,c in enumerate(['pi','k','charm']):
            ax=axs[i,j];m=d['primary']&(d['tune']==t)&(d['component']==c)
            h=np.histogram2d(np.exp(d['direct_logE'][m]),d['truth_E_GeV'][m],bins=(PAPER,PAPER),weights=d['weight'][m])[0]
            p=h/np.where(h.sum(0)>0,h.sum(0),np.nan)*100
            im=ax.imshow(p,origin='lower',vmin=0,vmax=100,cmap='Blues');ax.set_title(LABELS[j]+' · '+c+f' (N={int(m.sum()):,})',fontsize=9)
            ax.set_xticks(range(5),labels,rotation=50,ha='right',fontsize=7);ax.set_yticks(range(5),labels,fontsize=7);ax.set_xlabel('True energy [GeV]')
            if j==0:ax.set_ylabel('Reconstructed energy [GeV]')
            for y,x in np.ndindex(p.shape):
                value=p[y,x];text='—' if np.isnan(value) else '·' if value<.05 else f'{value:.1f}'
                ax.text(x,y,text,ha='center',va='center',fontsize=7,color='white' if value>48 else '#24313c')
    fig.colorbar(im,ax=axs.ravel().tolist(),label='Truth-column migration probability [%]',shrink=.7)
    fig.suptitle('Direct62 migration · separate π, K and charm test samples',fontsize=15)
    save(fig,'component_migrations','Component-resolved direct62 migration probabilities. No averaging over a different π/K/charm mixture; dash denotes absent truth support, dot denotes <0.05%.')


def selection_plot():
    rr=rows('selection_yields.tsv');fig,axs=plt.subplots(1,2,figsize=(14,5),layout='constrained')
    for i,c in enumerate(['pi','k','charm']):
        values=[next(r for r in rr if r['component']==c and r['tune']==t) for t in TUNES]
        for ax,key,label in [(axs[0],'fiducial_selection_efficiency','Selection efficiency within fiducial CC νμ, pz>50 [%]'),(axs[1],'selected_fraction','Selected fraction of all input parents [%]')]:
            ax.plot(range(5),[100*float(v[key]) for v in values],'o-',label=c,color=['#0072B2','#E69F00','#009E73'][i]);ax.set_ylabel(label);ax.grid(alpha=.18)
    for ax in axs:ax.set_xticks(range(5),TUNES,rotation=20,ha='right');ax.legend()
    fig.suptitle('Selection is part of the tune comparison · all parents retained in denominators',fontsize=14)
    save(fig,'selection_efficiency','Unweighted production-view efficiencies by component, before any training-overlap exclusion or model prediction. Fiducial denominator follows the original cumulative truth cuts. QGSP uses the fixed uniform full-file sample; remaining tunes use all available RDO files. No independent-binomial interval is implied because incoming/source reuse is present.')


def feature_shift():
    rr=rows('feature_profiles.tsv');names=list(dict.fromkeys(r['feature'] for r in rr));shift=np.empty((len(names),5));missing=np.empty_like(shift)
    for i,n in enumerate(names):
        for j,t in enumerate(TUNES):
            r=next(r for r in rr if r['feature']==n and r['tune']==t);shift[i,j]=float(r['median_shift_over_train_R68']);missing[i,j]=float(r['missing_pct'])
    fig,axs=plt.subplots(1,2,figsize=(13,18),layout='constrained',sharey=True)
    im=axs[0].imshow(np.ma.masked_invalid(shift),aspect='auto',cmap='RdBu_r',vmin=-2,vmax=2);fig.colorbar(im,ax=axs[0],label='Median shift / training R68',shrink=.5)
    im=axs[1].imshow(missing,aspect='auto',cmap='Purples',vmin=0,vmax=max(1,float(missing.max())));fig.colorbar(im,ax=axs[1],label='Typed missing inputs [%]',shrink=.5)
    for ax in axs:ax.set_xticks(range(5),TUNES,rotation=35,ha='right',fontsize=8);ax.set_yticks(range(len(names)),names,fontsize=7)
    axs[0].set_title('Input response and composition shift');axs[1].set_title('Missingness after frozen domain/status rules')
    fig.suptitle('Audited deployment inputs · primary test samples vs Stage 87 train\nDiagnostics include spectrum/composition differences; no feature or calibration is refitted',fontsize=14)
    save(fig,'feature_shift','62-feature medians and typed-missing fractions under the unchanged deployment preprocessing. Continuous-variable shifts are normalized to the training central-68% half-width; discrete/constant training columns with zero width are masked. Color saturation at ±2 is only a display choice; exact values and out-of-training-range fractions remain in feature_profiles.tsv. These diagnostics are not a causal transport attribution.')


def migration_quality():
    rr=rows('migration_quality.tsv');fig,axs=plt.subplots(1,2,figsize=(14,5),layout='constrained')
    for ax,key,label in [(axs[0],'stability_pct','Stability: same reco bin | truth bin [%]'),(axs[1],'purity_pct','Purity: same truth bin | reco bin [%]')]:
        for j,t in enumerate(TUNES):
            for model,ls,alpha in [('direct','-',1),('traditional','--',.55)]:
                vals=[next(r for r in rr if r['scheme']=='paper' and r['model']==model and r['tune']==t and int(r['bin'])==i) for i in range(5)]
                ax.plot(range(5),[float(v[key]) for v in vals],ls=ls,marker='o',ms=3,color=COLORS[j],alpha=alpha,label=LABELS[j] if model=='direct' else None)
        ax.set_xticks(range(5),['<100','100–300','300–600','600–1000','≥1000'],rotation=20,ha='right');ax.set_ylabel(label);ax.set_xlabel('Energy bin [GeV]');ax.grid(alpha=.18);ax.set_ylim(0,102)
    axs[0].legend(fontsize=8);fig.suptitle('Energy-bin stability and purity · direct62 solid, traditional dashed\nPurity depends on the incident spectrum and component mix',fontsize=14)
    save(fig,'migration_quality','Stability is the diagonal truth-column probability; purity uses reconstructed-row normalization. Both are conditional on selection and native primary sample composition. Per-bin actual incoming support is in migration_quality.tsv; neither quantity alone measures unfolding accuracy or total selection efficiency.')


def paired_response(d):
    from stage125_evaluate import table
    fig,axs=plt.subplots(1,2,figsize=(14,5.4),layout='constrained');result=[]
    def aggregate(t,model):
        m=d['primary']&(d['tune']==t);ids,inv,count=np.unique(d['key_id'][m],return_inverse=True,return_counts=True)
        mean=np.bincount(inv,weights=d[model+'_logE'][m])/count
        energy=np.bincount(inv,weights=d['truth_E_GeV'][m])/count
        return ids,mean,energy
    for ax,model in zip(axs,['direct','traditional']):
        ref,refpred,_=aggregate('JEFF33',model)
        for j,t in enumerate(TUNES):
            if t=='JEFF33':continue
            ids,pred,energy=aggregate(t,model);shared,ia,ib=np.intersect1d(ids,ref,return_indices=True)
            x=energy[ia];shift=100*np.expm1(pred[ia]-refpred[ib]);xx=[];qq=[]
            for lo,hi in zip(EDGES[1:-1],EDGES[2:]):
                mask=(x>=lo)&(x<hi)
                if not mask.any():continue
                q=np.quantile(shift[mask],[.16,.5,.84]);center=np.sqrt(lo*(hi if np.isfinite(hi) else lo*2));xx.append(center);qq.append(q)
                result.append(dict(model=model,tune=t,reference='JEFF33',E_low_GeV=lo,E_high_GeV=hi,common_incoming=int(mask.sum()),q16_shift_pct=q[0],median_shift_pct=q[1],q84_shift_pct=q[2]))
            qq=np.asarray(qq);ax.plot(xx,qq[:,1],'o-',lw=1.3,ms=3,color=COLORS[j],label=LABELS[j]);ax.fill_between(xx,qq[:,0],qq[:,2],color=COLORS[j],alpha=.10)
        ax.axhline(0,c='#24313c',ls='--',lw=.9);ax.set(xscale='log',xlabel=r'True $E_\nu$ [GeV]',ylabel='Prediction shift to JEFF33 [%]',title='direct62' if model=='direct' else 'Traditional pz0 / 0.8');ax.grid(alpha=.16)
    axs[0].legend(fontsize=8);fig.suptitle('Same incoming proxy selected in both tunes · response sensitivity\nLine: median of paired prediction shifts; band: event central 68%, not a confidence interval',fontsize=14)
    save(fig,'paired_response_shift','Each exact incoming proxy contributes one mean log prediction per tune over its selected response views. Shift = 100 × [exp(mean logE_tune − mean logE_JEFF33) − 1]. Pairs must pass selection in both tunes and have no known train/cal overlap. Proxies are equally weighted here; the QGSP component mixture follows the sampled shared subset, without inverse-probability correction. This controls the incoming proxy and energy, but does not certify identical GENIE final state, vertex, G4/digitization seed or complete parent lineage. Selection effects are reported separately. Bands show event dispersion, not statistical uncertainty.')
    table('paired_response_profiles.tsv',result)


def main():
    global COMPLETE
    tick=time.perf_counter();style();d=load(CACHE/'evaluation.npz');reference=load(CACHE/'reference.npz')
    COMPLETE=json.loads((OUT/'validation.json').read_text())['complete_source_inventory']
    data=rows('metrics.tsv');contrasts=rows('tune_contrasts.tsv')
    matrix('paper');matrix('fine');density(d,reference);profiles(data);comparison(data,contrasts);components(d);differences(d);component_matrices(d);selection_plot();feature_shift();migration_quality();paired_response(d)
    (OUT/'figure_catalog.json').write_text(json.dumps(dict(figures=FIGURES,complete_source_inventory=COMPLETE,KDE_worker_CPUs=int(os.environ.get('NU_MU_STAGE125_PLOT_CPUS','1')),parallel_KDE_serial_64point_probe_exact=True if int(os.environ.get('NU_MU_STAGE125_PLOT_CPUS','1'))>1 else None,wall_s=time.perf_counter()-tick),indent=2)+'\n')
    # A standalone gallery makes all plots and definitions easy to review.
    html=['<!doctype html><html lang="en"><meta charset="utf-8"><title>Stage125 · frozen direct62 physics-tune performance</title><style>body{font:16px system-ui;max-width:1500px;margin:36px auto;padding:0 24px;color:#24313c;background:#fafbfc}img{width:100%;background:white}figure{margin:38px 0;padding:20px;background:white;border:1px solid #dfe5ea;border-radius:8px}figcaption{line-height:1.6}a{color:#0072b2}h1{font-size:28px}</style><h1>Frozen Stage 87 direct62 · MC24 physics-tune performance</h1><p>Five Geant4 tunes; unchanged ensemble and calibration. Primary evaluation excludes known Stage 87 train/cal incoming identities. Uncertainty intervals are conditional incoming-proxy intervals, not full physics-systematic or generator-parent intervals.</p><p>Truth is always on the horizontal axis in energy-energy plots. Read the Chinese stage report for sample sizes, selection, inputs, commands and limitations.</p>']
    if not COMPLETE:html.append('<p><strong>PREVIEW: source inventory incomplete. Final results will replace these figures after all sources return.</strong></p>')
    for item in FIGURES:
        n=item['name'];html.append(f'<figure id="{n}"><a href="{n}.pdf">Download PDF</a><img src="{n}.png" alt="{n}" loading="lazy"><figcaption>{item["caption"]}</figcaption></figure>')
    html.append('</html>');(OUT/'index.html').write_text('\n'.join(html))
    print('Figures',len(FIGURES),'wall_s',time.perf_counter()-tick,flush=True)


if __name__=='__main__':main()
