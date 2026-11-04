"""Stage92 single original posterior retraining with frozen accurate CUDA loss."""
import argparse
import json
import math
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path

import numpy as np
import torch
from scipy.optimize import minimize

from audited_features import REPO, build
from latent_transfer_diagnostics import check_x, response
from support_augmentation import arrays, save, table, begin, resources
from transfer_posterior import Network, joint_density, preprocess, predict_network, prior_setup
from batched_posterior import log_energy_density, value_gradient
from differentiable_posterior import value_gradient as reference_score

OUT = REPO / 'workbook/stage92_energy_ml'
CACHE = REPO / 'ntuples/energy_ml_stage92'
ART = REPO / 'ml/artifacts/stage92'
SPOOL = Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage92')
INPUTS = ['ntuples/energy_ml_stage55/dataset.npz', 'ntuples/energy_ml_stage56/readout.npz']
INPUTS += [f'ntuples/energy_ml_stage{s}/support.npz' for s in [70, 81, 82, 83]]
CODE = ['ml/retrain_accurate_posterior.py', 'ml/transfer_posterior.py', 'ml/resplit_energy.py',
        'ml/audited_features.py', 'ml/latent_transfer_diagnostics.py', 'ml/support_augmentation.py',
        'ml/batched_posterior.py', 'ml/differentiable_posterior.py', 'ml/posterior_numerics.py',
        'ml/configs/audited_features.json']
SEED = 2026110387


def original_protocol():
    return json.loads((REPO/'workbook/stage87_energy_ml/protocol.json').read_text())


def normalization():
    return json.loads((REPO/'workbook/stage87_energy_ml/normalization.json').read_text())


def reconstruct(rows):
    """Rebuild selected original row identities, without changing the stage87 split."""
    split = arrays(REPO/'ntuples/energy_ml_stage87/split.npz')
    d = {k: v[rows] for k, v in split.items()}
    d['row'] = np.asarray(rows)
    parts = []
    keys = ['truth_E_GeV', 'y_lepton', 'primary_valid', 'primary_candidates', 'confirmed']
    for origin in np.unique(d['origin']):
        positions = np.flatnonzero(d['origin'] == origin)
        rr = d['origin_row'][positions]
        if origin == 55:
            old = arrays(REPO/INPUTS[0]); readout = arrays(REPO/INPUTS[1])
            ix = np.searchsorted(readout['row'], rr)
            np.testing.assert_array_equal(readout['row'][ix], rr)
            small = {k: v[ix] for k, v in readout.items() if k != 'metadata_json'}
            x = build(old, small)
            status, raw, calo = small['status'], small['raw_charge'], small['calo_status']
            a = {k: old[k][rr] for k in keys}
            a.update(pz=old['reco_pz_GeV'][rr], nominal=old['nominal'][rr])
            for k in ['incoming', 'group', 'run', 'eventID', 'component']:
                np.testing.assert_array_equal(old[k][rr], d[k][positions])
        else:
            z = arrays(REPO/f'ntuples/energy_ml_stage{origin}/support.npz')
            assert z['new_training_support'][rr].all()
            x = z['x'][rr]; status, raw, calo = z['status'][rr], z['raw_charge'][rr], z['calo_status'][rr]
            a = {k: z[k][rr] for k in keys}
            a.update(pz=z['reco_pz_GeV'][rr], nominal=np.zeros(len(rr), bool))
            for k in ['incoming', 'group', 'run', 'eventID', 'component']:
                np.testing.assert_array_equal(z[k][rr], d[k][positions])
        check_x(x)
        a.update(x=x, **response(x, raw, status, calo)); parts.append((positions, a))
    for k in parts[0][1]:
        shape = (len(rows),) + parts[0][1][k].shape[1:]
        d[k] = np.empty(shape, dtype=parts[0][1][k].dtype)
        for positions, a in parts:
            d[k][positions] = a[k]
    mu = (1-d['y_lepton'])*d['truth_E_GeV']
    d['mu_truth_GeV'] = mu
    d['label_physical'] = d['primary_valid'] & (d['primary_candidates'] == 1) & np.isfinite(mu) & (mu > .1056583755) & (d['y_lepton'] >= 0) & (d['y_lepton'] < 1)
    assert d['label_physical'].all() and (d['pz'] > 50).all()
    return d


def normalize_fixed(d):
    p = original_protocol(); n = normalization()
    from audited_features import configuration
    idx = [configuration()['features'].index(k) for k in p['features']]
    a = d['x'][:, idx].astype(float); missing = np.isnan(a)
    z = (np.where(missing, n['median'], a)-n['median'])/n['IQR']
    x = np.column_stack([np.clip(z, -20, 20), missing,
                         np.column_stack([d[k] for k in ['wave_invalid', 'fit_failure', 'calo_invalid']])]).astype('float32')
    assert x.shape == (len(a), 85) and np.isfinite(x).all()
    return x


def qa_rows():
    # Status information only: no energy-risk selection, no test access.
    pred = arrays(REPO/'ml/artifacts/stage87/predictions.npz')
    ids = [pred['row'][(pred['role'] == role) & pred['input_missing']] for role in [1, 2]]
    assert [len(a) for a in ids] == [21, 6]
    ref = arrays(REPO/'ntuples/energy_ml_stage90/input.npz')
    ordered = list(np.concatenate(ids + [ref['row'][ref['role'] == 1]]))
    result = list(dict.fromkeys(map(int, ordered)))[:40]
    assert len(result) == 40
    return np.asarray(result)


def tensors(d):
    return dict(pz=torch.tensor(d['pz'], dtype=torch.float32),
                y=torch.tensor(np.log(d['truth_E_GeV']), dtype=torch.float32),
                mu=torch.tensor(d['mu_truth_GeV'], dtype=torch.float32),
                f=torch.tensor(d['y_lepton'], dtype=torch.float32), valid=torch.tensor(d['label_physical']),
                w=torch.tensor(d['weight'], dtype=torch.float32))


def density(v, y, pz, b=0., T=1., device='cuda'):
    return log_energy_density(v.to(device), y.to(device), pz.to(device),
                              torch.as_tensor(b, dtype=torch.float64, device=device),
                              torch.as_tensor(T, dtype=torch.float64, device=device)).cpu()


def score_check(head, d, epoch, b=0., T=1., training_targets=True):
    start = begin(); rows = []
    t = tensors(d)
    # Training uses original float32 supervised tensors; calibration uses originals float64.
    y = t['y'] if training_targets else torch.tensor(np.log(d['truth_E_GeV']))
    pz = t['pz'] if training_targets else torch.tensor(d['pz'])
    value, grad, meta = value_gradient(torch.tensor(head, device='cuda'), y.cuda(), pz.cuda(), b, T)
    value, grad = value.cpu().numpy(), grad.cpu().numpy()
    for i in range(len(head)):
        rv, rg, info = reference_score(head[i].astype(float), float(y[i]), float(pz[i]), b, T)
        # Conservative propagation of adaptive vector-integral error through score normalization.
        noise = info['vector_quad_error']/math.exp(rv)*(1+abs(rg))
        tolerance = 1e-4+1e-3*abs(rg)
        delta = abs(grad[i]-rg)
        passed = (abs(value[i]-rv)+info['vector_quad_error']/math.exp(rv) <= 1e-6 and
                  bool((delta+noise <= tolerance).all()) and info['precision_flags'] == 0)
        rows.append(dict(epoch=epoch, row=int(d['row'][i]), role=int(d['role'][i]), input_missing=bool(d['input_missing'][i]),
                         value=float(value[i]), reference_value=rv, max_value_error=abs(value[i]-rv),
                         max_gradient_error=float(delta.max()), max_error_plus_reference_uncertainty_ratio=float(((delta+noise)/tolerance).max()),
                         vector_quad_error=info['vector_quad_error'], density_tail_bound=info['density_tail_bound'],
                         precision_flags=info['precision_flags'], passed=bool(passed)))
    return rows, resources(start)


def startup(d=None):
    start = begin(); torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    if d is None: d = reconstruct(qa_rows())
    np.testing.assert_array_equal(d['row'], qa_rows())
    assert int((d['input_missing'] & (d['role'] == 1)).sum()) == 21
    assert int((d['input_missing'] & (d['role'] == 2)).sum()) == 6
    x = normalize_fixed(d); t = tensors(d)
    torch.manual_seed(SEED); model = Network(85, 'posterior')
    with torch.no_grad(): head = model(torch.tensor(x)).numpy()
    rows, cost = score_check(head, d, 0)
    table(OUT/'startup_scores.tsv', rows)
    np.savez_compressed(CACHE/'startup_heads.npz', row=d['row'], head=head)
    gradients = {}; values = {}
    for device in ['cpu', 'cuda']:
        model.zero_grad(); v = model(torch.tensor(x))
        marginal = density(v, t['y'], t['pz'], device=device)
        loss = (t['w']*(-joint_density(v, t['mu'], t['f'], t['pz'], t['valid'])-.25*marginal)).mean()
        loss.backward(); values[device] = float(loss.detach())
        gradients[device] = np.concatenate([p.grad.numpy().ravel() for p in model.parameters()])
    diff = float(abs(gradients['cpu']-gradients['cuda']).max())
    tolerance = 1e-4+1e-3*abs(gradients['cpu'])
    passed = all(r['passed'] for r in rows) and bool((abs(gradients['cpu']-gradients['cuda']) <= tolerance).all())
    result = dict(passed=passed,identities=len(x),train_missing=21,cal_missing=6,optimizer_steps=0,
                  max_network_parameter_gradient_CPU_CUDA_difference=diff,CPU_CUDA_loss_difference=abs(values['cpu']-values['cuda']),
                  GPU=torch.cuda.get_device_name(0),torch=torch.__version__,cuda=torch.version.cuda,
                  scope='original initialization fullnetwork; headweightzero implies initialbodygradientzero, no claim alltrajectory guarantee',
                  adaptive_score_cost=cost, **resources(start))
    save(OUT/'startup_QA.json',result); print(json.dumps(result),flush=True)
    return passed


def prepare_qa():
    OUT.mkdir(parents=True,exist_ok=True);CACHE.mkdir(parents=True,exist_ok=True)
    d = reconstruct(qa_rows()); np.savez_compressed(CACHE/'qa_input.npz',**d)
    startup(d)


def trajectory(model, x, d, epoch):
    with torch.no_grad(): head = model(torch.tensor(x)).numpy()
    rows, cost = score_check(head,d,epoch)
    table(OUT/f'checkpoint_{epoch:03d}.tsv',rows)
    if not all(r['passed'] for r in rows):
        np.savez_compressed(CACHE/'failed_numerics.npz',row=d['row'],head=head,epoch=epoch)
        raise ArithmeticError(f'fixed40 numerical certification failed at epoch {epoch}')
    return dict(epoch=epoch, **cost)


def fit_worker():
    start = begin(); OUT.mkdir(parents=True,exist_ok=True);CACHE.mkdir(parents=True,exist_ok=True);ART.mkdir(parents=True,exist_ok=True)
    assert not (ART/'started.txt').exists(),'single fit cannot restart'
    # Full reconstruction/normalization happens on the worker, never rewriting stage87.
    d = reconstruct(np.arange(89033)); x,n = preprocess(d,original_protocol()); assert n == normalization()
    np.testing.assert_array_equal(x,normalize_fixed(d))
    _,ratios,prior = prior_setup(d); assert prior == json.loads((REPO/'workbook/stage87_energy_ml/prior.json').read_text())
    counts=[]
    for code in range(4):
        m=d['role']==code;counts.append(dict(role=code,N=int(m.sum()),missing=int(d['input_missing'][m].sum()),weight_sum=float(d['weight'][m].sum())))
    assert [r['N'] for r in counts]==[17657,46575,11612,13189]
    assert [r['missing'] for r in counts]==[12,21,6,5]
    save(OUT/'reconstruction.json',dict(passed=True,normalization_exact=True,prior_exact=True,rows=counts,**resources(start)))
    ids=qa_rows();q={k:v[ids] for k,v in d.items()}; qx=x[ids]
    assert startup(q),'initial numerical QA failed; zero optimizer steps'
    (ART/'started.txt').write_text('one fixedposterior fit only\n')
    torch.manual_seed(SEED);model=Network(85,'posterior');optimizer=torch.optim.Adam(model.parameters(),lr=.001)
    tr=np.flatnonzero(d['role']==1);td={k:v[tr] for k,v in d.items()};t=tensors(td)
    t['w']=torch.tensor(d['weight'][tr]/d['weight'][tr].mean(),dtype=torch.float32)
    xx=torch.tensor(x[tr])
    rng=np.random.default_rng(SEED);records=[];checks=[];steps=0
    try:
        for epoch in range(150):
            perm=rng.permutation(len(tr));total=0.
            for j in range(0,len(tr),1024):
                ix=perm[j:j+1024];v=model(xx[ix]);optimizer.zero_grad()
                marginal=density(v,t['y'][ix],t['pz'][ix])
                joint=joint_density(v,t['mu'][ix],t['f'][ix],t['pz'][ix],t['valid'][ix])
                loss=(t['w'][ix]*(-joint-.25*marginal)).mean()
                if not torch.isfinite(loss):
                    np.savez_compressed(CACHE/'failed_numerics.npz',row=tr[ix],head=v.detach().numpy(),epoch=epoch,batch_start=j)
                    raise ArithmeticError('nonfinite density/loss; no step taken')
                loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),10.,error_if_nonfinite=True)
                optimizer.step();steps+=1;total+=float(loss.detach())*len(ix)
                assert resources(start)['CPU_s']<6900 and resources(start)['wall_s']<5200,'fixed fit resource budget exceeded'
            if (epoch+1)%25==0:
                checks.append(trajectory(model,qx,q,epoch+1));rec=dict(epoch=epoch+1,optimizer_steps=steps,train_loss=total/len(tr),**resources(start));records.append(rec)
                table(OUT/'training.tsv',records);save(OUT/'trajectory_resources.json',checks);print(json.dumps(rec),flush=True)
        torch.save(dict(state_dict=model.state_dict(),kind='posterior',input_dimensions=85),ART/'posterior.pt')
        back=Network(85,'posterior');back.load_state_dict(torch.load(ART/'posterior.pt',weights_only=True)['state_dict'])
        with torch.no_grad():np.testing.assert_array_equal(model(torch.tensor(qx)).numpy(),back(torch.tensor(qx)).numpy())
        # Save all active heads immediately; never lose the completed fit to later reporting.
        active=np.flatnonzero(d['role']>0);heads=predict_network(model,x[active])
        np.savez_compressed(ART/'posterior_parameters.npz',row=active,head=heads)
        save(OUT/'fit_status.json',dict(completed=True,epochs=150,optimizer_steps=steps,model_reload_exact=True,new_fits=1,**resources(start)))
        calibration(heads[d['role'][active]==2],d,np.flatnonzero(d['role']==2))
    except Exception as exc:
        if not (CACHE/'failed_numerics.npz').exists():
            np.savez_compressed(CACHE/'failed_numerics.npz',row=tr[ix],head=v.detach().numpy(),epoch=epoch,batch_start=j)
        save(OUT/'failure.json',dict(error=f'{type(exc).__name__}: {exc}',optimizer_steps=steps,completed_fit=(OUT/'fit_status.json').exists(),no_retry=True,**resources(start)))
        raise
    save(OUT/'fit_total_resources.json',dict(new_fits=1,**resources(start)))


def calibration(head,d,ids):
    start=begin();dd={k:v[ids] for k,v in d.items()};y=torch.tensor(np.log(dd['truth_E_GeV']));pz=torch.tensor(dd['pz'])
    ww=torch.tensor(dd['weight']/dd['weight'].sum());v=torch.tensor(head,dtype=torch.float64)
    qmask=np.isin(dd['row'],qa_rows());qh=head[qmask];qd={k:a[qmask] for k,a in dd.items()}
    initial,_=score_check(qh,qd,-1,training_targets=False);table(OUT/'calibration_initial_QA.tsv',initial);assert all(r['passed'] for r in initial)
    evaluations=[]
    def objective(values):
        b=torch.tensor(values[0],dtype=torch.float64,device='cuda',requires_grad=True);T=torch.tensor(values[1],dtype=torch.float64,device='cuda',requires_grad=True)
        total=0.
        for j in range(0,len(ids),1024):
            val=log_energy_density(v[j:j+1024].cuda(),y[j:j+1024].cuda(),pz[j:j+1024].cuda(),b,T).cpu()
            loss=-(ww[j:j+1024]*val).sum();assert torch.isfinite(loss);loss.backward();total+=float(loss.detach())
        g=np.array([float(b.grad.cpu()),float(T.grad.cpu())]);assert np.isfinite(g).all()
        evaluations.append(dict(evaluation=len(evaluations)+1,b=float(values[0]),T=float(values[1]),NLL=total,gb=float(g[0]),gT=float(g[1])))
        table(OUT/'calibration_evaluations.tsv',evaluations)
        return total,g
    result=minimize(objective,[0.,1.],jac=True,bounds=[(-.2,.2),(.5,2)],method='L-BFGS-B',options=dict(maxiter=100))
    b,T=map(float,result.x)
    save(OUT/'posterior_calibration.json',dict(b=b,T=T,success=bool(result.success),message=str(result.message),iterations=int(result.nit),nfev=int(result.nfev),gradient=np.asarray(result.jac).tolist(),cal_logE_NLL=float(result.fun),**resources(start)))
    end,_=score_check(qh,qd,-2,b,T,training_targets=False);table(OUT/'calibration_final_QA.tsv',end)
    assert result.success and all(r['passed'] for r in end),'single calibration not certified'
    p=arrays(ART/'posterior_parameters.npz');np.savez_compressed(ART/'posterior_parameters.npz',**p,b=b,T=T)


def package_qa():
    torch.set_num_threads(1);d=arrays(CACHE/'qa_input.npz');assert startup(d)
    print('actualpayload fixed40 identities and fullnetwork CPU/CUDA gradients passed, zero optimizer',flush=True)


def submit_fit():
    start=begin();assert not (OUT/'submission_fit.json').exists();assert json.loads((OUT/'startup_QA.json').read_text())['passed']
    paths=CODE+INPUTS+['ntuples/energy_ml_stage87/split.npz','ntuples/energy_ml_stage90/input.npz','ml/artifacts/stage87/predictions.npz',
        'workbook/stage87_energy_ml/protocol.json','workbook/stage87_energy_ml/normalization.json','workbook/stage87_energy_ml/prior.json',
        'ntuples/energy_ml_stage92/qa_input.npz','workbook/stage92_energy_ml/protocol.json']
    archive=REPO/'software/energy-ml-retrain-stage92-fit.tar.gz'
    with tarfile.open(archive,'w:gz',compresslevel=1) as t:
        for name in paths:t.add(REPO/name,arcname=name)
    with tempfile.TemporaryDirectory(prefix='stage92_package_') as tmp:
        with tarfile.open(archive) as t:t.extractall(tmp,filter='data')
        text=subprocess.check_output([__import__('sys').executable,'ml/retrain_accurate_posterior.py','package-qa'],cwd=tmp,text=True)
    save(OUT/'package_QA_fit.json',dict(passed=True,output=text,archive_bytes=archive.stat().st_size))
    (SPOOL/'logs').mkdir(parents=True,exist_ok=True);(SPOOL/'fit_v1.sh').write_bytes((REPO/'AnalysisZipFramework/submission/run_ml_retrain_accurate.sh').read_bytes())
    result=subprocess.check_output(['condor_submit','-terse',str(REPO/'AnalysisZipFramework/submission/ml_retrain_accurate.sub')],text=True)
    cluster=int(result.split('.')[0]);ads=json.loads(subprocess.check_output(['condor_q',str(cluster),'-json','-attributes','ClusterId,ProcId,RequestCpus,RequestGpus,RequestMemory,MaxRuntime,RequireGPUs'],text=True))
    assert len(ads)==1 and ads[0]['RequestCpus']==2 and ads[0]['RequestMemory']==6000 and ads[0]['RequestGpus']==1 and ads[0]['MaxRuntime']==5400
    save(OUT/'submission_fit.json',dict(cluster=cluster,result=result,actual_ads=ads,**resources(start)));print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare-qa','package-qa','submit-fit','fit-worker']);a=p.parse_args()
    globals()[a.action.replace('-','_')]()
