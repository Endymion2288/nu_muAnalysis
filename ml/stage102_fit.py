"""Exactly one original MDN trajectory, two independently persisted selections."""
import json
import os

import numpy as np
import torch

from compare_energy_architectures import make, objective, output, representation
from stage102_common import (REPO, OUT, ART, CACHE, SEED, arrays, atomic_json,
    begin, resources, save, table, frozen_inputs, partition)


def atomic_state(model, name, epoch, score, center):
    path = ART/(name+'.pt')
    temporary = path.with_suffix('.tmp')
    state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    torch.save(dict(cell='E', seed=SEED, input_dimensions=127, center=center,
                    epoch=epoch, score=score, state_dict=state), temporary)
    loaded = torch.load(temporary, map_location='cpu', weights_only=False)
    assert all(torch.equal(loaded['state_dict'][k], v) for k, v in state.items())
    os.replace(temporary, path)


def main():
    start = begin()
    assert json.loads((OUT/'admission.json').read_text())['passed']
    assert not (OUT/'fit_started.json').exists()
    assert not (ART/'P.pt').exists() and not (ART/'N.pt').exists()
    ART.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    assert torch.cuda.is_available()
    split = arrays(REPO/'ntuples/energy_ml_stage87/split.npz')
    rows = np.flatnonzero(np.isin(split['role'], [1, 2]))
    d, x, frozen = frozen_inputs(rows)
    _, recomputed, _ = representation(d, 'E')
    assert recomputed == frozen, 'Train-only preprocessing changed'
    tr = np.flatnonzero(d['role'] == 1)
    cal, subrole, partweight = partition(d)
    val = cal[subrole == 1]
    vw = partweight[subrole == 1]
    assert [len(tr), len(cal), len(val), int((subrole == 2).sum()), int((subrole == 0).sum())] == [46575, 11612, 5443, 5746, 423]
    assert not set(d['key_id'][tr]) & set(d['key_id'][cal])
    assert [len(np.unique(d['key_id'][idx])) for idx in [tr, cal, val, cal[subrole == 2]]] == [37556, 10811, 5272, 5539]
    assert [int(d['input_missing'][idx].sum()) for idx in [tr, cal]] == [21, 6]
    y, anchor = np.log(d['truth_E_GeV']), np.log(d['pz']/.8)
    center = float(np.average(y[tr], weights=d['weight'][tr]))
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    model = make('E', 127, center).cuda()
    assert sum(v.numel() for v in model.parameters()) == 12937
    opt = torch.optim.Adam(model.parameters(), lr=.001)
    xt = torch.tensor(x[tr], device='cuda')
    yt = torch.tensor(y[tr], dtype=torch.float32, device='cuda')
    wt = torch.tensor(d['weight'][tr]/d['weight'][tr].mean(), dtype=torch.float32, device='cuda')
    at = torch.tensor(anchor[tr], dtype=torch.float32, device='cuda')
    xv = torch.tensor(x[val], device='cuda')
    yv = torch.tensor(y[val], dtype=torch.float32, device='cuda')
    wv = torch.tensor(vw, dtype=torch.float32, device='cuda')
    av = torch.tensor(anchor[val], dtype=torch.float32, device='cuda')
    rng = np.random.default_rng(SEED)
    best = {'P': float('inf'), 'N': float('inf')}
    best_epoch = {'P': 0, 'N': 0}
    history, steps = [], 0
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    atomic_json(OUT/'fit_started.json', dict(trajectories_started=1, seed=SEED,
        optimizer='original Adam', other_model_fits=0, calibration_optimizations=0,
        train_N=len(tr), select_N=len(val), test_features_loaded=False))
    for epoch in range(1, 301):
        model.train()
        total, den = 0., 0.
        order = rng.permutation(len(tr))
        for j in range(0, len(tr), 1024):
            idx = order[j:j+1024]
            opt.zero_grad(set_to_none=True)
            loss, _ = objective(model, xt[idx], yt[idx], wt[idx], at[idx], 'E')
            assert torch.isfinite(loss)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 10, error_if_nonfinite=True)
            opt.step()
            steps += 1
            total += float(loss.detach())*float(wt[idx].sum())
            den += float(wt[idx].sum())
        if epoch % 5 == 0:
            model.eval()
            with torch.no_grad():
                nll, point = objective(model, xv, yv, wv, av, 'E')
                mse = ((point-yv)**2*wv).sum()/wv.sum()
            scores = {'P': float(mse), 'N': float(nll)}
            assert all(np.isfinite(v) for v in scores.values())
            for name in ['P', 'N']:
                if scores[name] < best[name]:
                    best[name], best_epoch[name] = scores[name], epoch
                    atomic_state(model, name, epoch, scores[name], center)
            history.append(dict(epoch=epoch, train_NLL=total/den,
                cal_select_point_MSE=scores['P'], cal_select_NLL=scores['N'],
                P_epoch=best_epoch['P'], N_epoch=best_epoch['N'], **resources(start)))
            table(OUT/'learning.tsv', history)
            if epoch-best_epoch['P'] >= 30:
                break
    atomic_json(OUT/'selected.json', dict(checkpoints=best_epoch, scores=best,
        stopped_epoch=epoch, optimizer_steps=steps, trajectories=1,
        test_features_loaded=False, selection_frozen_before_test=True,
        stopping='original point-MSE patience30, check every5,max300'))
    # Only now reconstruct held-out test features, without changing state or selection.
    testrows = np.flatnonzero(split['role'] == 3)
    td, tx, tstate = frozen_inputs(testrows)
    assert tstate == frozen and len(tx) == 13189 and int(td['input_missing'].sum()) == 5
    for role, subset in [(1, tr), (2, cal)]:
        assert not set(d['key_id'][subset]) & set(td['key_id'])
    assert len(np.unique(td['key_id'])) == 12125
    eval_rows = np.r_[d['row'][cal], td['row']]
    order = np.argsort(eval_rows)
    ex = np.concatenate([x[cal], tx])[order]
    ea = np.r_[anchor[cal], np.log(td['pz']/.8)][order]
    saved = dict(row=eval_rows[order])
    for name in ['P', 'N']:
        state = torch.load(ART/(name+'.pt'), map_location='cpu', weights_only=False)
        model.load_state_dict(state['state_dict'])
        model.eval()
        heads, points = [], []
        with torch.no_grad():
            for j in range(0, len(ex), 1024):
                point, head = output(model, torch.tensor(ex[j:j+1024], device='cuda'), 'E',
                    torch.tensor(ea[j:j+1024], dtype=torch.float32, device='cuda'))
                assert torch.isfinite(point).all() and torch.isfinite(head).all()
                heads.append(head.cpu().numpy())
                points.append(point.cpu().numpy())
        saved[name+'_head'] = np.concatenate(heads)
        saved[name+'_point'] = np.concatenate(points)
        second = make('E', 127, center).cuda()
        second.load_state_dict(torch.load(ART/(name+'.pt'), map_location='cpu', weights_only=False)['state_dict'])
        with torch.no_grad():
            check = output(second, torch.tensor(ex[:1024], device='cuda'), 'E',
                           torch.tensor(ea[:1024], dtype=torch.float32, device='cuda'))
        np.testing.assert_array_equal(check[0].cpu().numpy(), saved[name+'_point'][:1024])
        np.testing.assert_array_equal(check[1].cpu().numpy(), saved[name+'_head'][:1024])
    temporary = ART/'heads.tmp.npz'
    np.savez_compressed(temporary, **saved)
    readback = arrays(temporary)
    for k, v in saved.items():
        np.testing.assert_array_equal(readback[k], v)
    os.replace(temporary, ART/'heads.npz')
    save(OUT/'worker_complete.json', dict(passed=True, new_training_trajectories=1,
        optimizer_steps=steps, stopped_epoch=epoch, checkpoints=best_epoch,
        state_reload_exact=True, prediction_persistence_exact=True, test_after_selection=True,
        rows=len(eval_rows), train_N=len(tr), cal_N=len(cal), test_N=len(tx),
        normalization_state_equal=True, new_offset_or_T_optimizations=0,
        GPU=torch.cuda.get_device_name(), torch=torch.__version__, CUDA=torch.version.cuda,
        GPU_peak_allocated_MiB=torch.cuda.max_memory_allocated()/1024**2, **resources(start)))
    print((OUT/'worker_complete.json').read_text(), flush=True)


if __name__ == '__main__':
    main()
