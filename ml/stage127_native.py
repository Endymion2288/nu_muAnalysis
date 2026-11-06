"""Verify the Python cuboid mask against the existing native C++ cut flow."""
import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path
import numpy as np
import uproot
import yaml

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage127_energy_ml'
CACHE=ROOT/'ntuples/energy_ml_stage127'


def cut_configuration(bounds, selection='pz100'):
    cuts=yaml.safe_load((ROOT/'AnalysisZipFramework/config/ml_low_energy_cuts.yaml').read_text())
    xmin,xmax,ymin,ymax=bounds
    expression=(f'truth_dec_x_nu > {xmin} && truth_dec_x_nu < {xmax} && '
                f'truth_dec_y_nu > {ymin} && truth_dec_y_nu < {ymax} && '
                'truth_dec_z_nu > -3000 && truth_dec_z_nu < -1619.65')
    cuts['Cuts']={('Truth vertex in cuboid' if k=='Truth dec r < 100 mm' else k):
                  (dict(v,expression=expression) if k=='Truth dec r < 100 mm' else v) for k,v in cuts['Cuts'].items()}
    if selection=='pz100':
        cuts['Cuts']={(k.replace('50','100') if k in ['Truth pz > 50 GeV','Track pz > 50 GeV'] else k):
             (dict(v,expression=v['expression'].replace('> 50','> 100')) if k in ['Truth pz > 50 GeV','Track pz > 50 GeV'] else v) for k,v in cuts['Cuts'].items()}
    return cuts


def write_configurations():
    bounds=json.loads((OUT/'decisions.json').read_text())['recommended']['bounds_mm']
    config_dir=ROOT/'AnalysisZipFramework/config'
    for selection in ['pz100','pz50']:
        config=cut_configuration(bounds,selection)
        (OUT/f'recommended_cuts_{selection}.yaml').write_text(yaml.safe_dump(config,sort_keys=False))
        if selection=='pz100':
            # Preserve the ordinary cutflow's histogram definitions and comments.
            original=(config_dir/'cuts.yaml').read_text()
            expression=config['Cuts']['Truth vertex in cuboid']['expression']
            assert original.count('expression: "truth_dec_r < 100"')==1
            content=original.replace('  Truth dec r < 100 mm:', '  Truth vertex in cuboid:')
            content=content.replace('expression: "truth_dec_r < 100"',f'expression: "{expression}"')
            name='cuts_cuboid.yaml'
        else:
            content=yaml.safe_dump(config,sort_keys=False);name='ml_cuboid_cuts.yaml'
        (config_dir/name).write_text(
            '# Stage127: frozen direct62 cuboid working point; dimensions in mm.\n'
            '# Intersected with the preceding In Faser Nu Box or Lead Block cut.\n'+content)


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=int,default=4);p.add_argument('--final',action='store_true')
    p.add_argument('--write-configs',action='store_true');a=p.parse_args()
    if a.write_configs:
        write_configurations();return
    protocol=json.loads((OUT/'protocol.json').read_text());source=next(s for s in protocol['sources'] if s['index']==a.source)
    with np.load(ROOT/'ntuples/energy_ml_stage126/predictions.npz') as z:
        d={k:z[k] for k in ['source','run','eventID','incoming','reco_pz_GeV']}
    take=np.flatnonzero(d['source']==a.source)
    if a.final:
        with np.load(CACHE/'coordinates.npz') as z:x,y=z['x'][take],z['y'][take]
        decisions=json.loads((OUT/'decisions.json').read_text())
        bounds=decisions['recommended']['bounds_mm']
        label='native_final'
    else:
        with np.load(CACHE/f'pilot_{a.source}.npz') as z:
            np.testing.assert_array_equal(z['row'],take);x,y=z['x'],z['y']
        bounds=[-90,110,-141,99];label='native_pilot'
    xmin,xmax,ymin,ymax=bounds
    mask=(x>xmin)&(x<xmax)&(y>ymin)&(y<ymax)&(d['reco_pz_GeV'][take]>100)&(d['incoming'][take,3]>100000)
    start=time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='cuboid_native_') as dirname:
        tmp=Path(dirname)
        definitions=yaml.safe_load((ROOT/'AnalysisZipFramework/config/definitions.yaml').read_text())
        definitions['Definitions'].update(yaml.safe_load((ROOT/'AnalysisZipFramework/config/ml_definitions.yaml').read_text())['Definitions'])
        files={'runs':{source['run']:{'data_paths':[source['input']],'waveform_paths':[]}}}
        output={'nt':{'save_all_input_columns':False,'save_all_defined_columns':False,'keep':['run','eventID']}}
        for name,value in [('definitions',definitions),('files',files),('output',output),('cuts',cut_configuration(bounds))]:
            (tmp/f'{name}.yaml').write_text(yaml.safe_dump(value,sort_keys=False))
        command=[str(ROOT/'build/analysis'),'--isMC','-r',str(source['run']),'-j','2',
           '--file-config',str(tmp/'files.yaml'),'--definitions-config',str(tmp/'definitions.yaml'),
           '--cuts-config',str(tmp/'cuts.yaml'),'--grl-config',str(ROOT/'AnalysisZipFramework/config/grl_config.yaml'),
           '--output-config',str(tmp/'output.yaml'),'-o',str(tmp/'selected.root')]
        run=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (OUT/f'{label}.log').write_text(run.stdout)
        if run.returncode:raise RuntimeError(run.stdout[-10000:])
        assert 'Reduced charge source: branches in the input NTuple.' in run.stdout
        with uproot.open(tmp/'selected.root') as f:native=f['nt']['eventID'].array(library='np')
    np.testing.assert_array_equal(np.sort(native),np.sort(d['eventID'][take][mask]))
    result=dict(passed=True,source=a.source,bounds_mm=bounds,N=len(native),selection='pz100',
                exact_event_identity=True,wall_s=time.perf_counter()-start,command=command)
    (OUT/f'{label}.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
