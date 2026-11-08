"""Render only independently verified covariance/ratio summaries."""
import csv,json,math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage183_energy_ml'
assert json.loads((OUT/'independent_validation.json').read_text())['passed']
rows=list(csv.DictReader((OUT/'covariance.tsv').open(),delimiter='\t'));channels=[0,1,2,3,16,17,18,19]
fig,axes=plt.subplots(1,2,figsize=(11,5),layout='constrained')
for ax,window,title in zip(axes,['signal_diagnostic','offpulse'],['Fixed signal diagnostic window','Fixed off-pulse window']):
    chosen={(int(r['channel_i']),int(r['channel_j'])):r for r in rows if r['window']==window}
    matrix=[[float(chosen[i,j]['correlation']) if chosen[i,j]['correlation'] else math.nan for j in channels] for i in channels]
    im=ax.imshow(matrix,vmin=-1,vmax=1,cmap='coolwarm')
    ax.set(xticks=range(8),yticks=range(8),xticklabels=[f'L{i}' for i in range(4)]+[f'H{i}' for i in range(4)],yticklabels=[f'L{i}' for i in range(4)]+[f'H{i}' for i in range(4)],title=title)
    for i in range(8):
        for j in range(8):
            if math.isfinite(matrix[i][j]):ax.text(j,i,f'{matrix[i][j]:.2f}',ha='center',va='center',fontsize=8,color='white' if abs(matrix[i][j])>.65 else 'black')
    ax.axvline(3.5,color='0.3',lw=.7);ax.axhline(3.5,color='0.3',lw=.7)
fig.colorbar(im,ax=axes,label='Descriptive event correlation',shrink=.82)
fig.suptitle('Run 15838 strict random controls: ordinary Ecal Lo / Hi\nFixed prefixes of RAW400–431; signal purity and MC transfer uncertified')
fig.savefig(OUT/'ordinary_ecal_correlations.png',dpi=160);fig.savefig(OUT/'ordinary_ecal_correlations.svg')
p=OUT/'ordinary_ecal_correlations.svg';p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines())+'\n')
print('Rendered audited aggregate correlation tables only')
