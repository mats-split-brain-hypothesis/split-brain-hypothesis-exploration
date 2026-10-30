"""Read-only source extraction: create readable copies of four existing IB episodes."""
import hashlib
import itertools
import json
import re
from pathlib import Path
from inspect_ai.log import read_eval_log

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs"
OUT = LOGS / "ib_transcript_reading/2026-10-24"
GOODFIRE = LOGS / "data/goodfire/qwen_traces.jsonl"
CONTINUATION = LOGS / "forensics_no_person/momentum_noreit/2026-10-24T15-30-37+01-00_ib-cont-NOREIT_4chZvNu4tWn3KjM7gSzVyZ.eval"


def fence(text, language="text"):
    text = str(text)
    delimiter = "`" * max(3, 1 + max((len(m[0]) for m in re.finditer(r"`+", text)), default=0))
    return f"{delimiter}{language}\n{text}\n{delimiter}\n"


def render_message(index, role, reasoning, content, calls):
    sections = [f"## Message {index} — {role}\n"]
    if reasoning:
        sections += ["### Model reasoning (verbatim)\n", fence(reasoning)]
    if content:
        sections += ["### Message content (verbatim)\n", fence(content)]
    for name, arguments in calls:
        sections += [f"### Tool call: {name}\n"]
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                pass
        if isinstance(arguments, dict):
            for key, value in arguments.items():
                sections += [f"**{key}**\n", fence(value if isinstance(value, str) else json.dumps(value, indent=2))]
        else:
            sections.append(fence(arguments))
    return "\n".join(sections)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    with GOODFIRE.open() as file:
        raw = next(itertools.islice(file, 174, 175))
    row = json.loads(raw)
    trace = row["traces"][0]
    assert trace["task"]["key"] == "impossible-bench:livecodebench:oneoff:tools:lcbhard_58"
    parts = ["# Goodfire release — Qwen oneoff lcbhard_58\n",
             f"Source: `{GOODFIRE.resolve()}:175`\n\nTrace ID: `{trace['id']}`\n\n",
             "All nodes included, zero-based indices. Reasoning is separated from message content; identical embedded `<think>` copies are omitted. Tool arguments are parsed from JSON for display but never executed. Literal escape sequences inside string values are preserved.\n",
             fence(json.dumps(trace["metrics"], indent=2), "json")]
    for i, node in enumerate(trace["nodes"]):
        m = node["message"]
        content = m.get("content") or ""
        reasoning = m.get("reasoning_content") or ""
        embedded = re.match(r"\s*<think>(.*?)</think>\s*", content, flags=re.S)
        if embedded and (not reasoning or embedded[1].strip() == reasoning.strip()):
            reasoning = reasoning or embedded[1].strip()
            content = content[embedded.end():]
        parts.append(render_message(i, m.get("role"), reasoning, content,
                                   [(t["name"], t["arguments"]) for t in m.get("tool_calls") or []]))
    path = OUT / "goodfire-qwen-oneoff-58.md"
    path.write_text("\n".join(parts))
    manifest.append(dict(output=path.name, source=str(GOODFIRE.resolve()), source_line=175,
                         row_id=row["id"], trace_id=trace["id"], source_row_sha256=hashlib.sha256(raw.encode()).hexdigest(), messages=len(trace["nodes"])))

    log = read_eval_log(CONTINUATION)
    assert log.status == "success" and len(log.samples) == 3
    for sample in log.samples:
        match = re.search(r"lcbhard_(\d+)_ep", str(sample.id))
        task = match[1]
        parts = [f"# Our Qwen continuation — conflicting lcbhard_{task}\n",
                 f"Source: `{CONTINUATION.resolve()}`\n\nSample: `{sample.id}`, epoch {sample.epoch}\n\n",
                 "All messages included, zero-based indices, including the replayed prefix. Reasoning and visible text are labeled separately. Tool arguments are displayed but never executed.\n",
                 fence(json.dumps({k:v.value for k,v in sample.scores.items()},indent=2), "json")]
        for i, m in enumerate(sample.messages):
            reasoning, content = [], []
            if isinstance(m.content, str):
                content.append(m.content)
            else:
                for block in m.content:
                    if block.type == "reasoning":
                        reasoning.append(block.reasoning)
                    elif block.type == "text":
                        content.append(block.text)
                    else:
                        content.append(json.dumps(block.model_dump(), ensure_ascii=False))
            calls = [(t.function,t.arguments) for t in (getattr(m,"tool_calls",None) or [])]
            parts.append(render_message(i,m.role,"\n".join(reasoning),"\n".join(content),calls))
        path = OUT / f"our-qwen-conflicting-{task}.md"
        path.write_text("\n".join(parts))
        manifest.append(dict(output=path.name, source=str(CONTINUATION.resolve()), sample_id=sample.id,
                             epoch=sample.epoch,messages=len(sample.messages),scores={k:v.value for k,v in sample.scores.items()}))
    for item in manifest:
        item["output_sha256"] = hashlib.sha256((OUT/item["output"]).read_bytes()).hexdigest()
    (OUT/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps([{k:r[k] for k in ("output","messages")} for r in manifest],indent=2))


if __name__ == "__main__":
    main()
