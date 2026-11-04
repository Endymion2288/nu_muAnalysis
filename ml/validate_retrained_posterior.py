"""Stage92 saved final-head and learned-body VJP verification, zero optimizer."""
import json

import numpy as np
import torch

from retrain_accurate_posterior import OUT,CACHE,ART,normalize_fixed,tensors
from support_augmentation import arrays,save,begin,resources
from transfer_posterior import Network,joint_density
from batched_posterior import value_gradient,log_energy_density
from differentiable_posterior import value_gradient as adaptive


def main():
    start=begin();torch.set_num_threads(1)
    d=arrays(CACHE/'qa_input.npz');parameters=arrays(ART/'posterior_parameters.npz')
    ix=np.searchsorted(parameters['row'],d['row']);np.testing.assert_array_equal(parameters['row'][ix],d['row'])
    head=parameters['head'][ix];t=tensors(d);x=normalize_fixed(d)
    value,g,_=value_gradient(torch.tensor(head,device='cuda'),t['y'].cuda(),t['pz'].cuda(),0.,1.)
    value,g=value.cpu().numpy(),g.cpu().numpy()
    reference=[adaptive(h.astype(float),float(y),float(p)) for h,y,p in zip(head,t['y'],t['pz'])]
    rv=np.array([r[0] for r in reference]);rg=np.stack([r[1] for r in reference])
    err=np.array([r[2]['vector_quad_error'] for r in reference])/np.exp(rv)
    noise=err[:,None]*(1+abs(rg));tol=1e-4+1e-3*abs(rg)
    assert (abs(value-rv)+err<=1e-6).all() and (abs(g-rg)+noise<=tol).all()
    assert all(r[2]['precision_flags']==0 for r in reference)
    model=Network(85,'posterior');model.load_state_dict(torch.load(ART/'posterior.pt',weights_only=True)['state_dict'])
    gradients={};losses={};local_head=None
    for device in ['cpu','cuda']:
        model.zero_grad();v=model(torch.tensor(x));local_head=v.detach().numpy()
        marginal=log_energy_density(v.to(device),t['y'].to(device),t['pz'].to(device),
                 torch.tensor(0.,dtype=torch.float64,device=device),torch.tensor(1.,dtype=torch.float64,device=device)).cpu()
        loss=(t['w']*(-joint_density(v,t['mu'],t['f'],t['pz'],t['valid'])-.25*marginal)).mean();loss.backward()
        gradients[device]=np.concatenate([p.grad.numpy().ravel() for p in model.parameters()]);losses[device]=float(loss.detach())
    error=abs(gradients['cuda']-gradients['cpu'])
    assert np.isfinite(gradients['cuda']).all() and (error<=1e-4+1e-3*abs(gradients['cpu'])).all()
    body_count=sum(p.numel() for p in model.body.parameters());body_norm=float(np.linalg.norm(gradients['cpu'][:body_count]));assert body_norm>0
    # float32 GEMM may depend on CPU and batch shape; retain both heads, never replace saved predictions.
    network_head_difference=float(abs(local_head-head).max())
    np.savez_compressed(CACHE/'final_head_QA.npz',row=d['row'],head=head,value=value,gradient=g,
        reference_value=rv,reference_gradient=rg,reference_uncertainty=noise,
        local_forward_head=local_head,CPU_network_gradient=gradients['cpu'],GPU_network_gradient=gradients['cuda'])
    save(OUT/'final_head_QA.json',dict(passed=True,N=40,coordinates=680,new_optimizer_steps=0,new_test_evaluations=0,
        max_value_error=float(abs(value-rv).max()),max_gradient_error=float(abs(g-rg).max()),
        max_error_plus_reference_uncertainty_over_tolerance=float(((abs(g-rg)+noise)/tol).max()),
        complete_network_parameter_gradient_max_CPU_CUDA_difference=float(error.max()),
        learned_body_gradient_L2=body_norm,CPU_CUDA_loss_difference=abs(losses['cpu']-losses['cuda']),
        local40_vs_saved2048_forward_head_max_difference=network_head_difference,
        interpretation='saved activeheads exactly reused for score audit; localforward differences from float32 CPU/GEMM batch do not replace predictions; learnedbody VJP at same localhead checked acrossdevices',**resources(start)))
    print((OUT/'final_head_QA.json').read_text(),flush=True)


if __name__=='__main__':main()
