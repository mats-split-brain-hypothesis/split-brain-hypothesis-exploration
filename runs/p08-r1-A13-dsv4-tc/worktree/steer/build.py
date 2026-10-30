"""Build a contrast direction from our own prompts via the metric server's capture endpoint.

Items come from a python module (--items mod:fn); templates render each item's fields. Prompts
are chat turns: user (required) and assistant (optional, teacher-forced). Positions for capture:
last | user | assistant | all. Saves {name, pos/neg templates, positions, layers, dirs, norms}.
"""
import argparse, importlib, os, sys, torch
sys.path.insert(0, "tools")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import metric


def _fmt(t, it):
    return t.format(**it) if t else None


def capture_condition(user_t, asst_t, items, positions, layers):
    prompts = []
    for it in items:
        p = {"user": _fmt(user_t, it)}
        if asst_t:
            p["assistant"] = _fmt(asst_t, it)
        prompts.append(p)
    out = metric.capture({"layers": layers, "prompts": prompts, "positions": positions})
    return out["mean"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--items", required=True, help="module:attribute returning a list of dicts")
    ap.add_argument("--pos-user", required=True)
    ap.add_argument("--pos-assistant", default="")
    ap.add_argument("--neg-user", required=True)
    ap.add_argument("--neg-assistant", default="")
    ap.add_argument("--positions", default="last")
    ap.add_argument("--layers", default="14:27")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    mod, attr = a.items.split(":")
    items = getattr(importlib.import_module(mod), attr)
    if callable(items):
        items = items()
    lo, hi = (int(x) for x in a.layers.split(":"))
    layers = list(range(lo, hi + 1))

    pos = capture_condition(a.pos_user, a.pos_assistant, items, a.positions, layers)
    neg = capture_condition(a.neg_user, a.neg_assistant, items, a.positions, layers)

    dirs, norms = {}, {}
    for L in layers:
        d = (pos[L] - neg[L]).float()
        dirs[L] = d.detach().cpu()
        norms[L] = d.norm().item()
    print("gap norms:", {L: round(norms[L], 1) for L in layers})
    torch.save({"name": a.name, "pos_user": a.pos_user, "pos_assistant": a.pos_assistant,
                "neg_user": a.neg_user, "neg_assistant": a.neg_assistant, "positions": a.positions,
                "layers": layers, "dirs": dirs, "norms": norms}, a.out)
    print("saved", a.out, f"({len(items)} items)")


if __name__ == "__main__":
    main()
