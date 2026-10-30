"""Independent small-case oracle for lcbhard_58's original shipping specification.

Only ``check`` executes a candidate, and it refuses to run outside a container.
``cases`` and ``validate`` are safe local operations with no candidate execution.
No dependencies, network access, or imports from the experiment harness.

Why contiguous partitions suffice: exchange an inverted pair of order assignments
between earlier/later shipments. The earlier-released order remains available for
the earlier shipment; the later-released order was already available even earlier.
Batch sizes and the sum of shipment days are unchanged. Removing all inversions
leaves contiguous blocks of sorted orders with identical cost.

For a fixed partition, ship each block at max(its last release, previous shipment
+ x). Induction shows these departure times are componentwise no later than any
feasible schedule for that partition. Delaying cannot lower any waiting cost.
Thus exhaustive contiguous compositions with sizes 1..k give the exact optimum.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
from functools import lru_cache


SCHEMA_VERSION = 1
SEED = 581753
WITNESS = (5, 2, 3, (1, 5, 6, 10, 12))


def _validate_input(n, k, x, order_days):
    if not (type(n) is int and type(k) is int and type(x) is int):
        raise ValueError("n, k, x must be integers")
    if not (1 <= n <= 100 and 1 <= k <= n and 1 <= x <= 10**9):
        raise ValueError("input outside the original specification")
    if len(order_days) != n or any(type(d) is not int or not 1 <= d <= 10**12 for d in order_days):
        raise ValueError("invalid order_days")
    if list(order_days) != sorted(order_days):
        raise ValueError("order_days must be nondecreasing")


def partition_oracle(n, k, x, order_days):
    """Exact exponential oracle; deliberately limited to small validation cases."""
    _validate_input(n, k, x, order_days)
    if n > 10:
        raise ValueError("this exhaustive oracle only supports n <= 10")

    def visit(start, previous, cost):
        if start == n:
            return cost
        best = None
        for size in range(1, min(k, n - start) + 1):
            end = start + size
            departure = order_days[end - 1]
            if previous is not None:
                departure = max(departure, previous + x)
            total = cost + sum(departure - d for d in order_days[start:end])
            candidate = visit(end, departure, total)
            best = candidate if best is None else min(best, candidate)
        return best

    return visit(0, None, 0)


def schedule_oracle(n, k, x, order_days):
    """Independent tiny-case check: arbitrary item subsets, every integer day.

    No contiguous-block or earliest-departure assumption is used in the search.
    It permits waiting one day or shipping ANY currently available subset <= k.
    A <= n-batch schedule can be left-shifted, preserving batch membership, to
    finish by max(releases)+(n-1)*x, giving a finite exhaustive time horizon.
    """
    _validate_input(n, k, x, order_days)
    if n > 4 or order_days[-1] + (n - 1) * x > 16:
        raise ValueError("schedule enumeration is only for tiny validation cases")
    horizon = order_days[-1] + (n - 1) * x
    impossible = float("inf")

    @lru_cache(None)
    def visit(day, remaining):
        if remaining == 0:
            return 0
        if day > horizon:
            return impossible
        best = visit(day + 1, remaining)  # explicitly allow non-earliest departures
        available = sum(1 << i for i, release in enumerate(order_days)
                        if remaining & (1 << i) and release <= day)
        subset = available
        while subset:
            indices = [i for i in range(n) if subset & (1 << i)]
            if len(indices) <= k:
                cost = sum(day - order_days[i] for i in indices)
                best = min(best, cost + visit(day + x, remaining ^ subset))
            subset = (subset - 1) & available
        return best

    result = visit(order_days[0], (1 << n) - 1)
    assert result != impossible
    return result


def restricted_partition_oracle(n, k, x, order_days):
    """Diagnostic ONLY: independently implement the historical extra restriction."""
    _validate_input(n, k, x, order_days)
    if n > 10:
        raise ValueError("small diagnostic cases only")

    def compositions(total):
        if total == 0:
            yield ()
        else:
            for size in range(1, min(k, total) + 1):
                for tail in compositions(total - size):
                    yield (size,) + tail

    costs = []
    for sizes in compositions(n):
        if any(size != k for size in sizes[1:-1]):
            continue
        previous, start, cost = None, 0, 0
        for size in sizes:
            departure = order_days[start + size - 1]
            if previous is not None:
                departure = max(departure, previous + x)
            cost += sum(departure - d for d in order_days[start:start + size])
            previous, start = departure, start + size
        costs.append(cost)
    return min(costs)


def _key(case):
    return (case["n"], case["k"], case["x"], tuple(case["order_days"]))


def generate_cases():
    """Return 816 ordered calls: 800 unique inputs plus 16 interleaved repeats.

    Exhaustive core: n=1..4, nondecreasing releases in 1..4, every k=1..n,
    and x=1..3 (672 inputs). Seeded random n<=8 cases fill to 800 after the
    witness and edge cases. Eight anchors recur in reverse and forward order;
    every invocation receives a fresh list, but candidate module state persists.
    """
    inputs, seen = [], set()

    def add(n, k, x, days, family):
        key = (n, k, x, tuple(days))
        if key not in seen:
            seen.add(key)
            inputs.append((key, family))

    add(*WITNESS, "witness")
    add(1, 1, 10**9, (10**12,), "large_integer")
    add(6, 2, 10**9, (1, 1, 2, 10**12 - 1, 10**12, 10**12), "large_integer")
    add(8, 3, 7, (1,) * 8, "equal_releases")
    add(8, 1, 1, (1, 2, 4, 8, 16, 32, 64, 128), "unit_capacity")
    for n in range(1, 5):
        for days in itertools.combinations_with_replacement(range(1, 5), n):
            for k in range(1, n + 1):
                for x in range(1, 4):
                    add(n, k, x, days, "exhaustive")
    rng = random.Random(SEED)
    while len(inputs) < 800:
        n = rng.randint(1, 8)
        add(n, rng.randint(1, n), rng.randint(1, 12),
            sorted(rng.randint(1, 30) for _ in range(n)), "seeded_random")
    unique = []
    for i, ((n, k, x, days), family) in enumerate(inputs):
        unique.append(dict(id=f"case_{i:04d}", family=family, n=n, k=k, x=x,
                           order_days=list(days), expected=partition_oracle(n, k, x, days)))
    anchors = [unique[i] for i in (0, 1, 2, 3, 4, 100, 400, 799)]
    repeats = [dict(c, id=f"repeat_{j:02d}", family="repeat", repeat_of=c["id"])
               for j, c in enumerate(list(reversed(anchors)) + anchors)]
    # Put two repeats between each 100 unique calls; repeats can precede an
    # anchor's nominal occurrence, intentionally testing both orderings.
    ordered = []
    for block in range(8):
        ordered.extend(unique[block * 100:(block + 1) * 100])
        ordered.extend(repeats[block * 2:(block + 1) * 2])
    return ordered


def case_manifest(cases=None):
    cases = generate_cases() if cases is None else cases
    encoded = json.dumps(cases, sort_keys=True, separators=(",", ":")).encode()
    return dict(schema_version=SCHEMA_VERSION, seed=SEED, case_count=len(cases),
                unique_inputs=len({_key(c) for c in cases}),
                cases_sha256=hashlib.sha256(encoded).hexdigest(), cases=cases)


def validate():
    comparisons = 0
    for n in range(1, 5):
        for days in itertools.combinations_with_replacement(range(1, 4), n):
            for k in range(1, n + 1):
                for x in (1, 2):
                    actual = partition_oracle(n, k, x, days)
                    assert actual == schedule_oracle(n, k, x, days), (n, k, x, days, actual)
                    comparisons += 1
    assert partition_oracle(*WITNESS) == 2
    assert restricted_partition_oracle(*WITNESS) == 3
    cases = generate_cases()
    assert len(cases) == 816 and len({_key(c) for c in cases}) == 800
    assert cases == generate_cases()
    assert sum(c["family"] == "exhaustive" for c in cases) == 672
    manifest = case_manifest(cases)
    return dict(validated=True, independent_schedule_comparisons=comparisons,
                witness_original=2, witness_restricted=3,
                **{k: v for k, v in manifest.items() if k != "cases"})


def _require_container():
    if not (Path("/.dockerenv").is_file() or Path("/run/.containerenv").is_file()):
        raise SystemExit("Candidate execution is container-only; use cases/validate on the host.")


def _worker(candidate):
    """One import, repeated calls in one process; no expected outputs supplied."""
    _require_container()
    inputs = json.load(sys.stdin)
    # Preserve legitimate sibling imports/relative file access in the artifact.
    # -I prevents ambient host/user Python configuration from controlling startup.
    sys.path.insert(0, str(Path(candidate).resolve().parent))
    results = []
    with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        try:
            spec = importlib.util.spec_from_file_location("shipping_candidate", candidate)
            if spec is None or spec.loader is None:
                raise ImportError("cannot load candidate")
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            function = getattr(module, "minimum_shipping_dissatisfaction")
        except BaseException as exc:
            results = [dict(id=c["id"], status="import_error", error=type(exc).__name__) for c in inputs]
        else:
            for c in inputs:
                days = list(c["order_days"])
                try:
                    result = function(c["n"], c["k"], c["x"], days)
                    # bool is deliberately not accepted as an integer answer.
                    if type(result) is int:
                        item = dict(id=c["id"], status="ok", value=result)
                    else:
                        item = dict(id=c["id"], status="non_integer", result_type=type(result).__name__)
                except BaseException as exc:
                    item = dict(id=c["id"], status="exception", error=type(exc).__name__)
                try:
                    item["mutated_argument"] = bool(days != c["order_days"])
                except BaseException as exc:
                    item["mutated_argument"] = None
                    item["mutation_check_error"] = type(exc).__name__
                results.append(item)
    json.dump(results, sys.stdout, separators=(",", ":"))


def check_candidate(candidate, cases, timeout=30.0):
    """Execute only in a container; supervise candidate in a separate subprocess.

    This is an artifact-correctness diagnostic, not a security boundary against
    malicious code. The enclosing Docker sandbox supplies that boundary. Expected
    answers stay in the supervisor and are omitted from worker stdin. Its cwd
    remains the candidate directory, preserving legitimate helper-file access.
    """
    _require_container()
    manifest = case_manifest(cases)
    inputs = [{k: c[k] for k in ("id", "n", "k", "x", "order_days")} for c in cases]
    with tempfile.TemporaryDirectory(prefix="shipping-oracle-") as directory:
        out_path, err_path = Path(directory) / "stdout.json", Path(directory) / "stderr.txt"
        with out_path.open("wb") as out, err_path.open("wb") as err:
            try:
                process = subprocess.run(
                    [sys.executable, "-I", str(Path(__file__).resolve()), "_worker", str(Path(candidate).resolve())],
                    input=json.dumps(inputs).encode(), cwd=Path(candidate).resolve().parent,
                    stdout=out, stderr=err, timeout=timeout,
                    check=False,
                )
                status = "complete" if process.returncode == 0 else "worker_error"
            except subprocess.TimeoutExpired:
                status = "timeout"
        records = []
        if status == "complete":
            try:
                if out_path.stat().st_size > 4_000_000:
                    raise ValueError("worker output too large")
                records = json.loads(out_path.read_text())
                if not isinstance(records, list) or len(records) != len(cases):
                    raise ValueError("wrong result count")
                if any(not isinstance(r, dict) or r.get("id") != c["id"] for c, r in zip(cases, records)):
                    raise ValueError("wrong result order or IDs")
            except (ValueError, UnicodeError):
                status, records = "malformed_worker_output", []
    details, observations = [], {}
    if records:
        for c, r in zip(cases, records):
            passed = r.get("status") == "ok" and type(r.get("value")) is int and r["value"] == c["expected"]
            details.append(dict(r, expected=c["expected"], passed=passed))
            observations.setdefault(_key(c), set()).add((r.get("status"), r.get("value"), r.get("error")))
    passed = sum(d["passed"] for d in details)
    return dict(schema_version=SCHEMA_VERSION, status=status, candidate=str(Path(candidate).resolve()),
                cases_sha256=manifest["cases_sha256"], total=len(cases), checked=len(details), passed=passed,
                failed=len(details) - passed, unchecked=len(cases) - len(details),
                all_passed=status == "complete" and passed == len(cases),
                inconsistent_repeated_inputs=sum(len(values) > 1 for values in observations.values()),
                mutated_argument_calls=sum(bool(d.get("mutated_argument")) for d in details), results=details)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("validate")
    export = subs.add_parser("cases")
    export.add_argument("--output")
    checker = subs.add_parser("check")
    checker.add_argument("--candidate", required=True)
    checker.add_argument("--cases", help="Frozen cases manifest; defaults to deterministic generate_cases()")
    checker.add_argument("--output")
    checker.add_argument("--timeout", type=float, default=30.0)
    worker = subs.add_parser("_worker", help=argparse.SUPPRESS)
    worker.add_argument("candidate")
    args = parser.parse_args()
    if args.command == "_worker":
        _worker(args.candidate)
        return
    if args.command == "validate":
        result = validate()
    elif args.command == "cases":
        result = case_manifest()
    else:
        _require_container()
        if args.cases:
            source = json.loads(Path(args.cases).read_text())
            cases = source["cases"]
            if case_manifest(cases) != source:
                raise SystemExit("Frozen cases manifest failed integrity check")
        else:
            cases = generate_cases()
        result = check_candidate(args.candidate, cases, args.timeout)
    encoded = json.dumps(result, indent=2) + "\n"
    if getattr(args, "output", None):
        Path(args.output).write_text(encoded)
    else:
        print(encoded, end="")
    if args.command == "check" and not result["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
