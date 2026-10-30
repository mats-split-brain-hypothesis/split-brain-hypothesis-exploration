"""Offline, source-preserving display extraction for switch/probe cards.

No API calls, imports of experiment runners, or hidden-reasoning copies.
Offsets in frozen review packets are Python Unicode code-point offsets.
"""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path


def _text(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("Expected archived text, not a structured object")
    return value


@lru_cache(maxsize=64)
def _jsonl_lines(path, mtime_ns, size):
    return Path(path).read_text(encoding="utf-8").splitlines()


def _source_row(source):
    """Read and hash-check an exact JSONL row; never search by draw alone."""
    path = Path(source["path"])
    stat = path.stat()
    lines = _jsonl_lines(str(path), stat.st_mtime_ns, stat.st_size)
    line = int(source["line"])
    if not 1 <= line <= len(lines):
        raise ValueError(f"Source line unavailable: {path}:{line}")
    text = lines[line - 1]
    digest = sha256(text.encode("utf-8")).hexdigest()
    if source.get("row_sha256") and digest != source["row_sha256"]:
        raise ValueError(f"Frozen source hash mismatch: {path}:{line}")
    return json.loads(text), {"path": str(path), "line": line,
                              "row_sha256": digest, "hash_verified": bool(source.get("row_sha256"))}


def _one(items, predicate, description):
    matches = [item for item in items if predicate(item)]
    if len(matches) != 1:
        raise ValueError(f"Expected one {description}; found {len(matches)}")
    return matches[0]


def _location(source):
    return f"{source['path']}:{source['line']}"


def _block(label, text):
    # Preserve empty strings rather than fabricating a reply or context.
    return {"label": label, "text": _text(text)}


def extract_switch(raw, card):
    """Extract this branch's visible message history and last stored reply.

    `raw` is a sorh-shared-prefix-trajectories-v1 packet; `card.id` is its
    conversation_id. Earlier assistant outputs belong to prompt/context;
    only the last stored assistant output belongs to answer_blocks.
    """
    sid = card["id"]
    branch = _one(raw.get("branches", []),
                  lambda branch: branch.get("conversation_id") == sid, "switch branch")
    by_id = {turn["turn_id"]: turn for turn in raw.get("turns", [])}
    ids = branch.get("ordered_turn_ids", [])
    if not ids or any(ident not in by_id for ident in ids):
        raise ValueError(f"Missing canonical turn referenced by branch: {sid}")
    ordered = [by_id[ident] for ident in ids]
    if card.get("canonical_turn_ids") and card["canonical_turn_ids"] != ids:
        raise ValueError(f"Card and packet branch order disagree: {sid}")
    prompt_blocks, notes, sources = [], [], []
    for index, turn in enumerate(ordered):
        number = turn["turn"]
        prompt_blocks.append(_block(
            f"User {'initial prompt' if index == 0 else 'update'} — turn {number}",
            turn.get("user_message")))
        if not turn.get("user_message"):
            notes.append(f"The archived user message for turn {number} is empty.")
        if index < len(ordered) - 1:
            prompt_blocks.append(_block(f"Prior assistant reply — turn {number}",
                                        turn.get("assistant_output")))
            if not turn.get("assistant_output"):
                notes.append(f"The archived assistant reply for turn {number} is empty.")
        source = turn.get("source")
        if source:
            sources.append({"turn_id": turn["turn_id"], **source})
            notes.append(f"Turn {number} source: {_location(source)}")
        if turn.get("finish") not in (None, "stop"):
            notes.append(f"Turn {number} has stored finish={turn['finish']!r}; its text may be incomplete.")
    final = ordered[-1]
    missing = list(branch.get("missing_turns", []))
    if missing:
        notes.append("Unavailable planned turns: " + ", ".join(map(str, missing)) +
                     ". Missing source content is not a refusal or a negative result.")
    missing_later = any(number > final["turn"] for number in missing)
    known_complete = bool(final.get("assistant_output")) and final.get("finish") == "stop" and not missing_later
    label = "Full archived final assistant reply" if known_complete else "Last stored assistant reply"
    if not final.get("assistant_output"):
        notes.append("The last stored assistant output is empty; no final answer can be recovered.")
    if final.get("finish") is None:
        notes.append("The final finish status was not recorded; completeness beyond the archive is unknown.")
    notes.append("The context follows this branch only, including prior visible assistant replies. "
                 "Shared initial turns are reused; sibling branches and hidden reasoning are excluded.")
    return {
        "prompt_blocks": prompt_blocks,
        "answer_blocks": [_block(f"{label} — turn {final['turn']}", final.get("assistant_output"))],
        "notes": notes,
        "metadata": {
            "kind": "switch_branch", "packet_id": raw.get("packet_id", raw.get("id")),
            "sample_id": sid, "canonical_turn_ids": ids, "missing_turns": missing,
            "last_stored_turn": final["turn"], "finish": final.get("finish"),
            "full_final_answer_available": known_complete,
            "context_reconstructed_from_exact_archived_turns": True,
            "hidden_reasoning_copied": False, "source_locations": sources,
            "extraction_audit": "Exact branch order; user_message and assistant_output fields only.",
        },
    }


def _retained_explanation(raw, member):
    text = raw["review_fields"]["reasoning"]
    ranges = member["primary_field_ranges"].get("reasoning", [])
    if len(ranges) > 1:
        raise ValueError("Probe explanation unexpectedly has disjoint primary ranges")
    return "".join(text[start:end] for start, end in ranges)


def _frozen_wildchat_question(raw):
    # WildChat packets contain a single purpose_mc question. Read the frozen
    # template text already captured in the packet; do not execute/load code.
    marker = "\n\nPROBE QUESTIONS\n[USER PROBE QUESTION]\n"
    prompt = raw["review_fields"]["prompt"]
    if marker not in prompt:
        raise ValueError("Frozen WildChat question is unavailable")
    question = prompt.rsplit(marker, 1)[1]
    if "[USER PROBE QUESTION]\n" in question:
        raise ValueError("Multiple questions in a WildChat packet; cannot select safely")
    return question


def extract_probe(raw, card):
    """Extract the exact saved prompt (or explicit WildChat reconstruction).

    The archive does NOT retain a full final probe answer. It retains a
    possibly clipped visible explanation and label fields, not hidden thought.
    """
    sid = card["id"]
    call = _one(raw.get("calls", []), lambda item: item.get("sample_id") == sid, "probe call")
    member = _one(raw.get("review_members", []), lambda item: item.get("id") == sid, "probe member")
    if card.get("source") and any(card["source"].get(k) != call["source"].get(k)
                                  for k in ("path", "line", "row_sha256")):
        raise ValueError(f"Card and packet source disagree: {sid}")
    row, source = _source_row(call["source"])
    notes = [f"Probe-call source: {_location(source)}"]
    sources = [source]
    reconstruction = False
    context_cut = raw.get("original_context_was_clipped")
    if isinstance(row.get("prompt"), list):
        messages = row["prompt"]
        if not messages:
            notes.append("The stored prompt array is empty.")
    else:
        if call.get("probe") != "purpose_mc" or not raw.get("context_source"):
            raise ValueError(f"No exact prompt array or supported context reconstruction: {sid}")
        context, context_source = _source_row(raw["context_source"])
        messages = list(context.get("chat", [])) + [
            {"role": "user", "content": _frozen_wildchat_question(raw)}]
        sources.append(context_source)
        context_cut = context.get("cut", context_cut)
        reconstruction = True
        notes.append(f"Archived WildChat context source: {_location(context_source)}")
        notes.append("The complete sent prompt array was not saved for this WildChat call. "
                     "Displayed context comes from the archived chat; the purpose question is "
                     "reconstructed from the original runner template captured in this frozen packet.")
        if raw.get("probe_question_source", {}).get("path"):
            notes.append("Recorded question-template source: " + raw["probe_question_source"]["path"] +
                         " (template text is taken from the frozen packet, not executed or reloaded from this script).")
    prompt_blocks = []
    for index, message in enumerate(messages):
        role = str(message.get("role", "message"))
        last = index == len(messages) - 1
        label = ("Probe question — " + ("reconstructed template" if reconstruction else "exact stored user message")) \
            if last else f"Archived context — {role}, message {index + 1}"
        prompt_blocks.append(_block(label, message.get("content")))
    context_messages = messages[:-1] if messages else []
    if not context_messages or not any(_text(msg.get("content")) for msg in context_messages):
        notes.append("No non-empty task context is stored before the probe question.")
    if context_cut:
        notes.append("The original context archive is marked clipped; unavailable earlier text is not reconstructed.")
    explanation = _retained_explanation(raw, member)
    if explanation != _text(row.get("explanation")):
        raise ValueError(f"Frozen explanation differs from its source row: {sid}")
    expected_sha = call.get("visible_explanation", {}).get("sha256")
    if expected_sha and sha256(explanation.encode("utf-8")).hexdigest() != expected_sha:
        raise ValueError(f"Frozen explanation hash mismatch: {sid}")
    parsed = row.get("answer", row.get("label"))
    raw_label = row.get("raw", row.get("raw_label"))
    if parsed != call.get("parsed_answer") or raw_label != call.get("raw_label"):
        raise ValueError(f"Frozen probe labels differ from source row: {sid}")
    availability = member.get("availability", {})
    clipped = bool(availability.get("source_at_clip_limit_or_ellipsis"))
    notes.append("The original runner retained only the visible explanation (limited to 800 characters), "
                 "the raw-label field and the parsed label. The complete original final answer and "
                 "hidden reasoning were not saved; a reasoning-token count does not recover them.")
    if clipped:
        notes.append("This retained explanation reaches the original clipping limit or ends with an ellipsis.")
    if not explanation:
        notes.append("The retained explanation is empty.")
    if parsed is None:
        notes.append("No parsed label was retained; do not treat this as a substantive category.")
    if call.get("finish") not in (None, "stop"):
        notes.append(f"The source finish status is {call['finish']!r}; original output may also have been cut.")
    return {
        "prompt_blocks": prompt_blocks,
        "answer_blocks": [
            _block("Retained visible explanation — original 800-character limit", explanation),
            _block("Stored raw-label field — not the full model answer", raw_label),
            _block("Parsed label — derived by the original runner", parsed),
        ],
        "notes": notes,
        "metadata": {
            "kind": "probe_call", "packet_id": raw.get("id"), "sample_id": sid,
            "probe": call.get("probe"), "draw": call.get("draw"),
            "prompt_reconstructed": reconstruction, "original_context_was_clipped": context_cut,
            "question_template_source": raw.get("probe_question_source") if reconstruction else None,
            "full_final_answer_available": False, "hidden_reasoning_copied": False,
            "retained_explanation_chars": len(explanation), "original_explanation_clip_chars": 800,
            "explanation_at_clip_limit_or_ellipsis": clipped, "source_locations": sources,
            "extraction_audit": "Exact call/member ID; source row hash, explanation offsets/hash and label equality verified.",
        },
    }
