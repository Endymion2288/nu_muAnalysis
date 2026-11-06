"""Standalone scientific exports of the rectangle search and fixed-model tradeoff."""
import csv
import gzip
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle,Circle
import numpy as np
from stage127_scan import ROOT,OUT,load


def export(fig,name):
    for ext in ['png','svg','pdf']:
        path=OUT/f'{name}.{ext}';fig.savefig(path,dpi=170)
        if ext=='svg':path.write_text('\n'.join(s.rstrip() for s in path.read_text().splitlines())+'\n')
    plt.close(fig)


def main():
    with gzip.open(OUT/'cal_grid.tsv.gz','rt') as f:rows=list(csv.DictReader(f,delimiter='\t'))
    decision=json.loads((OUT/'decisions.json').read_text());c=decision['recommended']['geometry']
    fig,axes=plt.subplots(2,2,figsize=(12,9),layout='constrained')
    for j,(cx,cy,label) in enumerate([(0,0,'Centered at beam axis'),(10,-21,'Centered at NuBox transverse center')]):
        part=[r for r in rows if r['selection']=='pz100' and int(r['cx'])==cx and int(r['cy'])==cy]
        widths=sorted({int(r['width_mm']) for r in part});heights=sorted({int(r['height_mm']) for r in part})
        for i,(key,title) in enumerate([('record_gain100_pct','Cal selected-event gain vs r<100 (%)'),('log_RMSE_ratio100','Cal log-RMSE / r<100')]):
            z=np.array([[float(next(r for r in part if int(r['width_mm'])==w and int(r['height_mm'])==h)[key]) for w in widths] for h in heights])
            image=axes[i,j].pcolormesh(widths,heights,z,shading='nearest',cmap='viridis' if i==0 else 'coolwarm')
            axes[i,j].set(xlabel='Full width in x (mm)',ylabel='Full height in y (mm)',title=label+'\n'+title)
            fig.colorbar(image,ax=axes[i,j])
    fig.suptitle('25,375 cuboids per momentum selection; z ranges and other cuts fixed\nCalibration source groups only, frozen stage87 direct62')
    export(fig,'rectangle_grid')
    fig,ax=plt.subplots(figsize=(9,6),layout='constrained')
    rr=[r for r in rows if r['selection']=='pz100']
    ax.scatter([float(r['record_gain100_pct']) for r in rr],[float(r['log_RMSE_ratio100']) for r in rr],s=2,alpha=.08,color='#527e9e',rasterized=True)
    front=list(csv.DictReader((OUT/'cal_pareto.tsv').open(),delimiter='\t'));front=[r for r in front if r['selection']=='pz100']
    ax.plot([float(r['record_gain100_pct']) for r in front],[float(r['log_RMSE_ratio100']) for r in front],'o-',ms=3,label='Cal Pareto frontier',color='#a33f21')
    chosen=next(r for r in rr if int(r['candidate_id'])==c['candidate_id'])
    ax.scatter([float(chosen['record_gain100_pct'])],[float(chosen['log_RMSE_ratio100'])],marker='*',s=180,c='black',label='Recommended cuboid (cal selected)')
    ax.axhline(1,color='gray',lw=.8);ax.set(xlabel='Selected-event gain vs r<100 (%)',ylabel='Cal log-RMSE / r<100',title='Efficiency and energy-error tradeoff, pz>100 GeV');ax.grid(alpha=.2);ax.legend()
    export(fig,'rectangle_pareto')
    d,_=load();rect=decision['recommended']['bounds_mm']
    fig,axes=plt.subplots(1,2,figsize=(12,6),layout='constrained')
    for ax,(name,m) in zip(axes,[('FaserNu Box',d['vertex_z_mm']<-1900),('Lead block',d['vertex_z_mm']>-1800)]):
        im=ax.hexbin(d['x'][m],d['y'][m],gridsize=55,bins='log',extent=(-145,150,-155,145),mincnt=1,cmap='Blues')
        ax.add_patch(Circle((0,0),100,fill=False,color='#b33a2a',lw=1.5,label='r<100 mm'))
        ax.add_patch(Circle((0,0),125,fill=False,color='#e29326',lw=1.5,ls='--',label='r<125 mm'))
        ax.add_patch(Rectangle((rect[0],rect[2]),rect[1]-rect[0],rect[3]-rect[2],fill=False,color='black',lw=2,label='Recommended cuboid'))
        ax.set(xlabel='Truth vertex x (mm)',ylabel='Truth vertex y (mm)',title=name,aspect='equal',xlim=(-145,150),ylim=(-155,145))
        fig.colorbar(im,ax=ax,label='Selected MC records (log color)')
    axes[0].legend(fontsize=8);fig.suptitle('After all fixed non-radius cuts; all nominal records, no flux normalization')
    export(fig,'vertex_windows')
    evaluation=list(csv.DictReader((OUT/'evaluation.tsv').open(),delimiter='\t'))
    rr=[r for r in evaluation if r['selection']=='pz100' and r['role']=='test']
    fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained');x=np.arange(len(rr));labels=[r['policy'].replace('rectangle_','rect #') for r in rr]
    for ax,key,scale,title in [(axes[0],'record_gain100_pct',1,'Test event gain (%)'),(axes[1],'log_RMSE',1,'Test log-energy RMSE'),(axes[2],'fractional_R68',100,'Test fractional R68 (%)')]:
        ax.bar(x,[float(r[key])*scale for r in rr],color=['#7e95a5','#d19040','#72876b']+['#3071a0']*(len(rr)-3));ax.set(xticks=x,xticklabels=labels,ylabel=title);ax.tick_params(axis='x',rotation=30);ax.grid(axis='y',alpha=.2)
    fig.suptitle('Fixed calibration-selected finalists on held-out source groups')
    export(fig,'rectangle_test')


if __name__=='__main__':main()
