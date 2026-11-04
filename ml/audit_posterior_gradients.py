"""Stage90 fixed train/cal value/gradient audit, with zero optimizer steps."""
import argparse
import json
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import numpy as np
import torch

from differentiable_posterior import value_gradient, log_energy_density
from posterior_numerics import Reference, FixedGH
from support_augmentation import arrays, save, table, begin, resources
from transfer_posterior import log_energy_density as gh_density, joint_density

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / 'workbook/stage90_energy_ml'
CACHE = REPO / 'ntuples/energy_ml_stage90'
SPOOL = Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage90')
NAMES = [f'{family}{k}' for family in ['logit', 'mr', 'ms', 'sr_raw', 'ss_raw'] for k in range(3)] + ['b', 'T']
CODE = ['ml/audit_posterior_gradients.py', 'ml/differentiable_posterior.py', 'ml/posterior_numerics.py',
        'ml/transfer_posterior.py', 'ml/support_augmentation.py', 'ml/audited_features.py',
        'ml/resplit_energy.py', 'ml/latent_transfer_diagnostics.py']


def inputs():
    d = arrays(REPO / 'ntuples/energy_ml_stage88/input.npz')
    h = arrays(REPO / 'ml/artifacts/stage87/posterior_parameters.npz')
    p = arrays(REPO / 'ml/artifacts/stage87/predictions.npz')
    s = arrays(REPO / 'ntuples/energy_ml_stage87/split.npz')
    np.testing.assert_array_equal(h['row'], p['row'])
    ix = np.searchsorted(h['row'], d['row'])
    np.testing.assert_array_equal(h['row'][ix], d['row'])
    for key in ['head']:
        np.testing.assert_array_equal(d[key], h[key][ix])
    for key in ['role', 'weight', 'truth_E_GeV', 'pz', 'y_lepton']:
        np.testing.assert_array_equal(d[key], p[key][ix])
    for key in ['role', 'weight', 'key_id', 'group']:
        np.testing.assert_array_equal(d[key], s[key][d['row']])
    assert (d['role'] == 1).sum() == 40 and (d['role'] == 2).sum() == 512
    assert not (d['role'] == 3).any()
    assert not (d['input_missing'] | d['wave_invalid'] | d['calo_invalid']).any()
    assert json.loads((REPO/'workbook/stage87_energy_ml/split_audit.json').read_text())['unknown_transfer_labels'] == 0
    d['label_physical'] = (np.isfinite(d['y_lepton']) & (d['y_lepton'] >= 0) &
        (d['y_lepton'] < 1) & ((1-d['y_lepton'])*d['truth_E_GeV'] > .1056583755))
    assert d['label_physical'].all()
    keep = ['head', 'row', 'role', 'weight', 'truth_E_GeV', 'pz', 'y_lepton', 'label_physical',
            'group', 'key_id', 'fit_failure', 'input_missing', 'wave_invalid', 'calo_invalid']
    result = {k:d[k] for k in keep}
    result['b'] = np.where(d['role'] == 1, 0., float(d['b']))
    result['T'] = np.where(d['role'] == 1, 1., float(d['T']))
    return result


def baseline(d):
    v = torch.tensor(d['head'], dtype=torch.float64, requires_grad=True)
    b = torch.tensor(d['b'][:, None], dtype=torch.float64, requires_grad=True)
    T = torch.tensor(d['T'][:, None], dtype=torch.float64, requires_grad=True)
    z = torch.tensor(np.log(d['truth_E_GeV']), dtype=torch.float64)
    p = torch.tensor(d['pz'], dtype=torch.float64)
    value = gh_density(v, z, p, b, T)
    g = torch.autograd.grad(value.sum(), (v, b, T))
    grad = np.column_stack([x.detach().numpy() for x in g])
    # Joint term uses the original training parameterization b0/T1, exactly.
    joint = joint_density(v, torch.tensor((1-d['y_lepton'])*d['truth_E_GeV']),
                          torch.tensor(d['y_lepton']), p, torch.tensor(d['label_physical']))
    jg = torch.autograd.grad(joint.sum(), v)[0].detach().numpy()
    expected = np.empty(len(z))
    for role in [1, 2]:
        m = d['role'] == role
        if not m.any():
            continue
        gh = FixedGH(d['head'][m], d['pz'][m], float(d['b'][m][0]), float(d['T'][m][0]), 32)
        expected[m] = np.log(gh.evaluate(np.log(d['truth_E_GeV'][m]), density=True)[1][:, 0])
    diff = float(np.max(abs(expected - value.detach().numpy())))
    assert diff < 1e-9, diff
    return value.detach().numpy(), grad, joint.detach().numpy(), jg, diff


def reference(x, pz, z):
    r = Reference(x[:15], pz, x[15], x[16])
    _, den, error = r.evaluate(z)
    return float(np.log(den)), float(error / den), r.neval


def calculate(d, label):
    start = begin()
    OUT.mkdir(parents=True, exist_ok=True)
    gh, gg, joint, jg, baseline_error = baseline(d)
    n = len(gh)
    result = dict(value=np.full(n, np.nan), gradient=np.full((n, 17), np.nan),
                  reference_value=np.full(n, np.nan), reference_gradient=np.full((n, 17), np.nan),
                  reference_uncertainty=np.full((n, 17), np.nan), reference_step_difference=np.full((n, 17), np.nan),
                  GH32_value=gh, GH32_gradient=gg, joint_value=joint, joint_gradient=jg)
    detail = []
    rows = []
    # Fixed steps and tolerances are not selected per event or from audit outcomes.
    for i in range(n):
        tick = time.process_time()
        h = d['head'][i].astype(float)
        x = np.r_[h, d['b'][i], d['T'][i]]
        z = float(np.log(d['truth_E_GeV'][i]))
        p = float(d['pz'][i])
        error = ''
        try:
            value, gradient, cost = value_gradient(h, z, p, x[15], x[16])
            rv, re, neval = reference(x, p, z)
            fg = []; fu = []; fs = []
            for j in range(17):
                derivative = []; noise = []
                for step in [1e-4, 5e-5]:
                    values = []; errors = []
                    for sign in [-1, 1]:
                        perturbed = x.copy(); perturbed[j] += sign * step
                        vv, ee, nn = reference(perturbed, p, z)
                        values.append(vv); errors.append(ee); neval += nn
                    derivative.append((values[1] - values[0]) / (2 * step))
                    noise.append(sum(errors) / (2 * step))
                # Richardson cancels the leading h^2 error; conservative
                # step disagreement plus propagated quad estimate is retained.
                refgrad = (4 * derivative[1] - derivative[0]) / 3
                disagreement = abs(derivative[1] - derivative[0]) / 3
                uncertainty = disagreement + (4 * noise[1] + noise[0]) / 3
                tol = 1e-4 + 1e-3 * abs(refgrad)
                fg.append(refgrad); fu.append(uncertainty); fs.append(disagreement)
                detail.append(dict(row=int(d['row'][i]),role=int(d['role'][i]),parameter=NAMES[j],
                    accurate_gradient=float(gradient[j]),reference_gradient=refgrad,reference_uncertainty=uncertainty,
                    step_disagreement=disagreement,tolerance=tol,
                    accurate_error=float(abs(gradient[j]-refgrad)),GH32_gradient=float(gg[i,j]),
                    GH32_error=float(abs(gg[i,j]-refgrad)),
                    accurate_pass=bool(abs(gradient[j]-refgrad)+uncertainty<=tol),
                    reference_resolved=bool(uncertainty<=tol/4),GH32_pass=bool(abs(gg[i,j]-refgrad)+uncertainty<=tol)))
            result['value'][i] = value; result['gradient'][i] = gradient
            result['reference_value'][i] = rv; result['reference_gradient'][i] = fg
            result['reference_uncertainty'][i] = fu; result['reference_step_difference'][i] = fs
            certified = bool(abs(value-rv)+re <= 1e-6 and
                             all(r['accurate_pass'] and r['reference_resolved'] for r in detail[-17:]))
            rows.append(dict(row=int(d['row'][i]),role=int(d['role'][i]),weight=float(d['weight'][i]),
                b=float(x[15]),T=float(x[16]),log_density=value,reference_log_density=rv,reference_log_error=re,
                GH32_log_density=float(gh[i]),value_error=abs(value-rv),GH32_value_error=abs(gh[i]-rv),
                certified=certified,CPU_s=time.process_time()-tick,reference_evaluations=neval,**cost,error=error))
        except (ArithmeticError, ValueError, AssertionError) as exc:
            rows.append(dict(row=int(d['row'][i]),role=int(d['role'][i]),weight=float(d['weight'][i]),
                b=float(x[15]),T=float(x[16]),log_density='未测量',reference_log_density='未测量',reference_log_error='未测量',
                GH32_log_density=float(gh[i]),value_error='未测量',GH32_value_error='未测量',certified=False,
                CPU_s=time.process_time()-tick,reference_evaluations=0,vector_quad_error='未测量',density_tail_bound='未测量',
                integrand_evaluations=0,precision_flags=0,gradient_tail_bound='未认证',error=str(exc)))
        if (i+1) % 10 == 0:
            print(label, i+1, '/', n, 'CPU', resources(start)['CPU_s'], flush=True)
        # One compact checkpoint per ten records; avoid per-derivative I/O.
        if (i+1) % 10 == 0 or i+1 == n:
            np.savez_compressed(CACHE/f'{label}_values.npz',row=d['row'],**result)
            table(OUT/f'{label}_events.tsv',rows)
            if detail:
                table(OUT/f'{label}_gradients.tsv',detail)
    summary = dict(N=n,certified_N=sum(r['certified'] for r in rows),baseline_max_difference=baseline_error,
        gradient_checks=len(detail),max_value_error=max(abs(result['value']-result['reference_value'])),
        max_gradient_error=float(np.nanmax(abs(result['gradient']-result['reference_gradient']))),
        reference_unresolved_N=sum(not r['reference_resolved'] for r in detail),
        accurate_failed_N=sum(not r['accurate_pass'] for r in detail),GH32_failed_N=sum(not r['GH32_pass'] for r in detail),
        new_fits=0,new_calibration=0,new_test_evaluations=0,**resources(start))
    # Convert NumPy scalars before strict JSON output.
    summary['max_value_error'] = float(summary['max_value_error'])
    save(OUT/f'{label}_summary.json',summary)
    return summary


def qa():
    start=begin();d=inputs();m=np.flatnonzero(d['role']==2)[:4]
    d={k:v[m] for k,v in d.items()};OUT.mkdir(exist_ok=True,parents=True);CACHE.mkdir(exist_ok=True,parents=True)
    np.savez_compressed(CACHE/'qa_input.npz',**d)
    result=calculate(d,'qa')
    # Exercise shared b/T summation and upstream VJP; no model forward.
    v=torch.tensor(d['head'].astype(float),requires_grad=True)
    b=torch.tensor(d['b'][0],dtype=torch.float64,requires_grad=True);T=torch.tensor(d['T'][0],dtype=torch.float64,requires_grad=True)
    up=torch.tensor([.3,-.7,1.2,.4],dtype=torch.float64)
    val=log_energy_density(v,torch.tensor(np.log(d['truth_E_GeV'])),torch.tensor(d['pz']),b,T)
    (val*up).sum().backward();saved=arrays(CACHE/'qa_values.npz');g=saved['gradient']*up.numpy()[:,None]
    diff=max(float(np.max(abs(v.grad.numpy()-g[:,:15]))),abs(float(b.grad)-g[:,15].sum()),abs(float(T.grad)-g[:,16].sum()))
    assert diff<1e-12 and result['certified_N']==len(m),(diff,result)
    save(OUT/'startup_QA.json',dict(passed=True,fixed_first_cal_N=4,VJP_max_difference=diff,
        zero_optimizer_steps=True,zero_network_forward=True,zero_test_evaluation=True,**resources(start)))


def package_qa():
    d=arrays(CACHE/'input.npz');q=arrays(CACHE/'qa_input.npz');saved=arrays(CACHE/'qa_values.npz')
    assert len(d['row'])==552 and (d['role']==1).sum()==40 and (d['role']==2).sum()==512
    assert not (d['role']==3).any()
    value,g,_=value_gradient(q['head'][0],np.log(q['truth_E_GeV'][0]),q['pz'][0],q['b'][0],q['T'][0])
    assert abs(value-saved['value'][0])<1e-12
    np.testing.assert_allclose(g,saved['gradient'][0],atol=1e-12,rtol=0)
    json.dumps(dict(passed=True,value=float(value)),allow_nan=False)
    print('actual payload552 train/cal identity and fixedcal value/17-gradient control passed',flush=True)


def submit():
    start=begin();assert not (OUT/'submission.json').exists()
    d=inputs();np.savez_compressed(CACHE/'input.npz',**d)
    paths=CODE+['ntuples/energy_ml_stage90/input.npz','ntuples/energy_ml_stage90/qa_input.npz','ntuples/energy_ml_stage90/qa_values.npz','workbook/stage90_energy_ml/protocol.json']
    archive=REPO/'software/energy-ml-gradients-stage90.tar.gz'
    with tarfile.open(archive,'w:gz',compresslevel=1) as t:
        for name in paths:t.add(REPO/name,arcname=name)
    import tempfile
    with tempfile.TemporaryDirectory(prefix='stage90_payload_') as tmp:
        with tarfile.open(archive) as t:t.extractall(tmp,filter='data')
        output=subprocess.check_output([sys.executable,'ml/audit_posterior_gradients.py','package-qa'],cwd=tmp,text=True)
    save(OUT/'package_QA.json',dict(passed=True,output=output,archive_bytes=archive.stat().st_size))
    (SPOOL/'logs').mkdir(parents=True,exist_ok=True)
    (SPOOL/'worker_v1.sh').write_bytes((REPO/'AnalysisZipFramework/submission/run_ml_posterior_gradients.sh').read_bytes())
    output=subprocess.check_output(['condor_submit','-terse',str(REPO/'AnalysisZipFramework/submission/ml_posterior_gradients.sub')],text=True)
    cluster=int(output.split('.')[0])
    ads=json.loads(subprocess.check_output(['condor_q',str(cluster),'-json','-attributes','ClusterId,ProcId,RequestCpus,RequestMemory,MaxRuntime'],text=True))
    assert len(ads)==1 and ads[0]['RequestCpus']==1 and ads[0]['RequestMemory']==3000 and ads[0]['MaxRuntime']==1800
    save(OUT/'submission.json',dict(cluster=cluster,result=output,actual_ads=ads,**resources(start)))
    print(output,flush=True)


def worker():
    start=begin();package_qa();d=arrays(CACHE/'input.npz');calculate(d,'audit')
    save(OUT/'worker_resources.json',resources(start))


if __name__=='__main__':
    torch.set_num_threads(1)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['qa','package-qa','submit','worker'])
    action=parser.parse_args().action
    globals()[action.replace('-','_')]()
