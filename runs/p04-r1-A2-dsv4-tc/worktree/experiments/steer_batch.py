import sys, torch
sys.path.insert(0,'tools'); sys.path.insert(0,'experiments'); import metric
LS=[4,8,12,16,20,24,26,28,30]
def load(name):
    return {int(k):v.float() for k,v in torch.load(f'out/steer/caps/{name}.pt', weights_only=False)['mean'].items()}
scene = load('scene_wide_wide')
front = load('frontinstr'); ans = load('answersuf'); what = load('whatisit'); in1 = load('inoneword')

def test(name, A, B, layers, pos, scales):
    vecs={int(L): A[L]-B[L] for L in layers}
    torch.save(vecs, f'out/steer/{name}.pt')
    best=(0,None)
    print(f'== {name} layers={layers} pos={pos} ==', flush=True)
    for s in scales:
        r=metric.run_metric(vecs,pos,s)
        print(f'  s{s:+.1f}: pass@10 {r["pass_at_10"]:.4f} ml10 {r["mean_log10_rank"]:.4f}', flush=True)
        if r['pass_at_10']>best[0]: best=(r['pass_at_10'], s)
    print(f'  BEST {name}: {best[0]:.4f} at {best[1]}', flush=True)

for nm,A,B in [('front',front,scene),('ansuf',ans,scene),('what',what,scene),('in1',in1,scene)]:
    test(f'{nm}_ctx', A, B, LS, 'context', [0.3, 1.0])
    test(f'{nm}_read', A, B, [26,28,30], 'read', [0.5, 1.0])
