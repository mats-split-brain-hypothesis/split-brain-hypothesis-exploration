"""Read an Inspect .eval whose samples fail validation only because a tool call's `view` lacks `content`.

    python src/eval_read_tolerant.py <log.eval>      # report patches and check scores against the raw values

Read-side only: the .eval is never rewritten. Each sample's JSON is loaded from the zip; any `view` dict that has a
`format` but no `content` gets content "" in memory (and the place is reported); then it is validated as an EvalSample.
Experiment 9's log (logs/forensics_no_person/exp9_p1) has exactly one such view, after Inspect 0.3.140 wrote it without
its content field.
"""
import json
import sys
import zipfile

from inspect_ai.log import EvalSample


def _patch(obj, path, patched):
    if isinstance(obj, dict):
        v = obj.get("view")
        if isinstance(v, dict) and "format" in v and "content" not in v:
            v["content"] = ""
            patched.append(path + ".view")
        for k, x in obj.items():
            _patch(x, f"{path}.{k}", patched)
    elif isinstance(obj, list):
        for i, x in enumerate(obj):
            _patch(x, f"{path}[{i}]", patched)


def read_samples(log_path, verbose=True):
    """(samples, patches, raw_scores): validated EvalSamples, [(sample file, json path)], {sample file: raw score dict}."""
    samples, patches, raw = [], [], {}
    with zipfile.ZipFile(log_path) as z:
        for name in sorted(n for n in z.namelist() if n.startswith("samples/") and n.endswith(".json")):
            data = json.loads(z.read(name))
            raw[name] = data.get("scores")
            patched = []
            _patch(data, "", patched)
            patches += [(name, p) for p in patched]
            samples.append(EvalSample.model_validate(data))
    if verbose:
        for name, p in patches:
            print(f"patched: {name} {p}")
    return samples, patches, raw


if __name__ == "__main__":
    samples, patches, raw = read_samples(sys.argv[1])
    same = 0
    for s, (name, r) in zip(samples, sorted(raw.items())):
        mine = {k: v.value for k, v in (s.scores or {}).items()}
        theirs = {k: v.get("value") for k, v in (r or {}).items()}
        same += mine == theirs
    print(f"samples {len(samples)}; patched views {len(patches)}; scores equal to the raw values: {same}/{len(samples)}")
