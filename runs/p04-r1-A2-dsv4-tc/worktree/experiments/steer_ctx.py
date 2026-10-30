import sys, torch
sys.path.insert(0,'tools'); sys.path.insert(0,'experiments'); import metric
def load(name):
    return {int(k):v.float() for k,v in torch.load(f'out/steer/caps/{name}.pt', weights_only=False)['mean'].items()}
sceneq = load('sceneq_wide_wide'); scene = load('scene_wide_wide')
neutral = load('neutral_wide_wide'); neutral_all = load('neutral_all_wide_wide')

def run(name, A, B, layers, positions, scales):
    vecs = {int(L): (A[L]-B[L]) for L in layers}
    print(f'=== {name} layers={layers} pos={positions} ===', flush=True)
    for s in scales:
        r = metric.run_metric(vecs, positions, s)
        print(f'  scale {s}: pass@10 {r["pass_at_10"]:.4f} meanlog10 {r["mean_log10_rank"]:.4f}', flush=True)
        print('    '+' '.join(f"{e['id'].split('-')[-1]}:{e['baseline_rank']}->{e['best_rank']}" for e in r['examples']))

# instruction direction at context, various layers
run('instr_ctx_early', sceneq, scene, [4,8,12,16,20,24], 'context', [0.3, 1.0, 2.0])
run('instr_ctx_all', sceneq, scene, [4,8,12,16,20,24,26,28,30], 'context', [0.3, 1.0, 2.0])
