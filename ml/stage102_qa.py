"""Original fixed40 CPU/CUDA/mixture and saved-model controls, zero optimizer."""
import copy
import json
import tempfile
import time

import numpy as np
import torch
from scipy.special import logsumexp, ndtr
from scipy.stats import norm

from compare_energy_architectures import decode, make, objective, output
from retrain_accurate_posterior import qa_rows
from stage102_common import REPO, OUT, SEED, arrays, begin, resources, save, frozen_inputs, partition


def main():
    start = begin()
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    assert torch.cuda.is_available(), 'GPU unavailable; no fit permitted'
    d, x, state = frozen_inputs(qa_rows())
    assert len(x) == 40 and set(d['role']) == {1, 2}
    assert [int(d['input_missing'][d['role'] == r].sum()) for r in [1, 2]] == [21, 6]
    cal, subrole, pw = partition(d)
    torch.manual_seed(SEED)
    model = make('E', 127, 6.)
    xx = torch.tensor(x)
    y = torch.tensor(np.log(d['truth_E_GeV']), dtype=torch.float32)
    w = torch.tensor(d['weight'], dtype=torch.float32)
    a = torch.tensor(np.log(d['pz']/.8), dtype=torch.float32)
    cpu_model = copy.deepcopy(model)
    loss, p = objective(cpu_model, xx, y, w, a, 'E')
    loss.backward()
    gpu_model = model.cuda()
    gx, gy, gw, ga = [v.cuda() for v in [xx, y, w, a]]
    gl, gp = objective(gpu_model, gx, gy, gw, ga, 'E')
    gl.backward()
    delta = float(np.max(abs(p.detach().numpy()-gp.detach().cpu().numpy())))
    assert delta <= 1e-5
    grad_error = max(float((u.grad-v.grad.cpu()).abs().max())
                     for u, v in zip(cpu_model.parameters(), gpu_model.parameters()))
    assert grad_error <= 1e-5
    h = gpu_model(gx).detach().cpu().double().requires_grad_()
    target = (y-a).double()
    lp, mu, sig = decode(h)
    density = torch.logsumexp(lp-.5*((target[:, None]-mu)/sig)**2-torch.log(sig)
                             -.5*np.log(2*np.pi), 1)
    grad = torch.autograd.grad(density.sum(), h)[0].numpy()
    head = h.detach().numpy()
    def independent(values):
        ll = values[:, :3]-logsumexp(values[:, :3], axis=1)[:, None]
        ss = .05+np.logaddexp(0., values[:, 6:9])
        return logsumexp(ll+norm.logpdf(target.numpy()[:, None], values[:, 3:6], ss), axis=1)
    density_error = float(np.max(abs(independent(head)-density.detach().numpy())))
    assert density_error < 1e-12
    differences = []
    for j in range(9):
        plus, minus = head.copy(), head.copy()
        plus[:, j] += 1e-5
        minus[:, j] -= 1e-5
        differences.append((independent(plus)-independent(minus))/2e-5)
    derivative_error = float(np.max(abs(np.array(differences).T-grad)))
    assert derivative_error < 1e-7
    from report_energy_architectures import mixture, probability_summary
    mix = mixture(head, a.numpy().astype(float))
    summary = probability_summary(*mix, np.log(d['truth_E_GeV']))
    assert summary['max_root_residual'] < 1e-10
    saved = torch.load(REPO/'ml/artifacts/stage94/E_2026110494.pt', map_location='cpu', weights_only=False)
    old_model = make('E', saved['input_dimensions'], saved['center']).cuda()
    old_model.load_state_dict(saved['state_dict'])
    with torch.no_grad():
        old_point, old_head = output(old_model, gx, 'E', ga)
    old = arrays(REPO/'ml/artifacts/stage94/point_predictions.npz')
    ix = np.searchsorted(old['row'], d['row'])
    np.testing.assert_array_equal(old['row'][ix], d['row'])
    old_error = float(np.max(abs(old_point.cpu().numpy()-old['E_2026110494'][ix])))
    assert old_error < 3e-6
    with tempfile.TemporaryDirectory() as directory:
        path = directory+'/roundtrip.pt'
        torch.save(old_model.state_dict(), path)
        second = make('E', 127, 6.).cuda()
        second.load_state_dict(torch.load(path, map_location='cuda', weights_only=True))
        with torch.no_grad():
            np.testing.assert_array_equal(output(second, gx, 'E', ga)[0].cpu().numpy(), old_point.cpu().numpy())
    costs = []
    repeat = torch.arange(1024, device='cuda') % 40
    for _ in range(4):
        gpu_model.zero_grad(set_to_none=True)
        torch.cuda.synchronize()
        tick = time.perf_counter()
        ll, _ = objective(gpu_model, gx[repeat], gy[repeat], gw[repeat], ga[repeat], 'E')
        ll.backward()
        torch.cuda.synchronize()
        costs.append(time.perf_counter()-tick)
    batch = float(np.median(costs[1:]))
    projection = batch*46*300*5+120
    result = dict(passed=True, identities=40, new_fits=0, optimizer_steps=0,
        rows=d['row'].tolist(), input_dimensions=127, missing_train_cal=[21, 6],
        train_cal_only=True, cal_subrole=subrole.tolist(),
        CPU_GPU_logE_max=delta, CPU_GPU_parameter_gradient_max=grad_error,
        independent_logdensity_max=density_error, head_derivative_max=derivative_error,
        quantile_residual=summary['max_root_residual'], old_saved_model_point_max=old_error,
        state_roundtrip_prediction_exact=True, preprocessing_frozen=True,
        batch1024_forward_backward_wall_s=batch, padded_fit_wall_projection_s=projection,
        GPU=torch.cuda.get_device_name(), torch=torch.__version__, CUDA=torch.version.cuda,
        **resources(start))
    save(OUT/'QA.json', result)
    assert projection < 600, 'Measured QA cost did not admit fit'
    save(OUT/'admission.json', dict(passed=True, sole_fit_allowed=1,
         padded_fit_wall_projection_s=projection, GPU_task_wall_limit_s=600,
         CPU_stage_limit_s=1800, report_processes=8, maximum_concurrent_jobs=1))
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
