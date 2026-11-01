#!/usr/bin/env python3
"""Final stage28 artifact consistency, code syntax and document-link checks."""
import csv
import json
import py_compile
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np


def main():
    root=Path(__file__).resolve().parents[1];out=root/'workbook/stage28_energy_ml'
    expected={'coverage':48,'seed_coverage':112,'coverage_comparisons':24,'thresholds':14,'joint_uncertainty':24,
              'metrics':21,'widths':224,'width_summary':18,'primary_tests':3,'boundary_diagnostics':147,'condor_resources':7}
    keys={'coverage':['model','method','parameter'],'seed_coverage':['model','seed','method','parameter'],
          'coverage_comparisons':['model','parameter'],'thresholds':['model','seed','parameter_group'],
          'joint_uncertainty':['model','parameter'],'metrics':['model','parameter'],
          'widths':['model','seed','trial','parameter'],'width_summary':['model','parameter','method'],
          'primary_tests':['model'],'boundary_diagnostics':['model','seed','parameter','target_class'],'condor_resources':['cluster','proc']}
    for name,n in expected.items():
        rows=list(csv.DictReader((out/f'{name}.tsv').open(),delimiter='\t'));assert len(rows)==n,(name,len(rows),n)
        assert len({tuple(r[k] for k in keys[name]) for r in rows})==n,name
        if name=='widths':
            assert all(r['fixed_status']=='ok' and r['calibrated_status']=='ok' for r in rows)
            assert all(100<=int(r['trial'])<116 for r in rows)
    summary=json.loads((out/'summary.json').read_text());assert len(summary['runs'])==7
    assert summary['totals']['failure_cells']==0
    for path in out.rglob('*.json'):json.loads(path.read_text())
    for path in out.glob('*.svg'):ET.parse(path)
    paths=list((root/'ml/artifacts/stage28').rglob('*.npz'));assert len(paths)==7
    near_threshold=0
    for path in paths:
        with np.load(path) as z:
            assert z['actual_lrs'].shape==(200,7) and z['bootstrap_lrs'].shape==(200,16,7)
            assert (z['actual_lrs']>=0).all() and (z['bootstrap_lrs']>=0).all()
            heldout=z['actual_lrs'][100:]
            threshold=np.r_[np.repeat(z['thresholds'][0],6),z['thresholds'][1]]
            near_threshold+=int(np.sum(abs(heldout-1)<1e-5)+np.sum(abs(heldout-threshold)<1e-5))
            for k in z.files:assert np.isfinite(z[k]).all(),(path,k)
            np.testing.assert_array_equal(z['counts'].sum(axis=-1),1000)
            np.testing.assert_array_equal(z['bootstrap_counts'].sum(axis=-1),1000)
            for k in ['fits','bootstrap_fits']:
                assert abs(z[k][...,:6].sum(axis=-1)-1).max()<1e-9
                assert z[k][...,:6].min()>=-1e-9 and abs(z[k][...,6]).max()<=3+1e-9
    independent=json.loads((out/'independent_checks.json').read_text())
    assert independent['count_instances_replayed']==23800 and independent['nlls_recomputed']==23800
    scripts=['mc_bootstrap','run_mc_bootstrap','prepare_mc_bootstrap','report_mc_bootstrap','check_mc_bootstrap','validate_mc_bootstrap']
    for name in scripts:py_compile.compile(str(root/'ml'/f'{name}.py'),doraise=True)
    subprocess.run(['bash','-n',str(root/'AnalysisZipFramework/submission/run_ml_mc_bootstrap.sh')],check=True)
    notes=json.loads((out/'submission_notes.json').read_text())
    cluster=notes['cluster'];schedd=notes['schedd']
    q=subprocess.check_output(['condor_q','-name',schedd,str(cluster),'-af','ClusterId'],text=True);assert not q.strip()
    r=next(iter(summary['runs'].values()))
    # Read the actual submission timestamp from the event log, independent of
    # local clock formatting; config/protocol must precede the submit event.
    from datetime import datetime
    log=(Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage28/logs')/f'ml_mc_bootstrap_{cluster}.log').read_text()
    match=re.search(r'000 \(\d+\.000\.000\) (\d\d/\d\d \d\d:\d\d:\d\d)',log)
    submit=datetime.strptime('2026/'+match.group(1),'%Y/%m/%d %H:%M:%S').timestamp()
    for path in [out/'preregistered_protocol.md',root/'ml/configs/mc_bootstrap.yaml']:assert path.stat().st_mtime<submit
    counts={}
    for path in [root/'docs/nu_mu_energy_ml_roadmap.md',root/'workbook/2026-11-01_stage28_mc-bootstrap-physics.md',*out.glob('*.md')]:
        n=0
        for target in re.findall(r'\]\(([^)]+)\)',path.read_text()):
            if '://' in target or target.startswith('#'):continue
            assert (path.parent/target.split('#')[0]).exists(),(path,target);n+=1
        counts[str(path.relative_to(root))]=n
    result=dict(table_rows=expected,table_keys_unique=True,npz_files_checked=7,nll_replay_passed=True,
                all_counts_N1000=True,finite_simplex_fits_and_nonnegative_lrs=True,calibration_and_test_trials_disjoint=True,
                json_svg_parse_passed=True,python_compilation_files=len(scripts),shell_syntax_passed=True,
                heldout_lrs_within_1e_minus5_of_decision_thresholds=near_threshold,
                protocol_and_config_precede_submission=True,completed_cluster_absent_from_queue=cluster,
                local_markdown_link_counts=counts,local_markdown_links_checked=sum(counts.values()))
    (out/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
