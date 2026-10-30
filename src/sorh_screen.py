"""School of Reward Hacks ablation, single-turn stages (pilot, screen, confirmation), as pre-registered by agent 10
(mats/agent-10-audit 3f7dd0f: notes/sorh_preregistration.md, notes/sorh_prereg/cells*.jsonl, src/sorh_judges.py).

Every message comes from the committed cells file (field `text`, one user message, no system prompt) and every judge
call from sorh_judges.judge_messages; nothing is assembled here.

  python src/sorh_screen.py show                       # the exact messages for 3 records and one judge call per kind
  python src/sorh_screen.py run --stage pilot [--dry]
  python src/sorh_screen.py run --stage screen [--more] [--dry]
  python src/sorh_screen.py run --stage confirmation --cells c3b_must,... --ref G|G_more [--more] [--dry]
  python src/sorh_screen.py status --stage pilot       # per cell: records written

Launch only as `nohup .venv/bin/python src/sorh_screen.py run ...` (no trailing &), so SIGINT stops it cleanly.
Outputs (written by this code, never by shell redirects), under logs/sorh_ablation/<stage>/ (or sorh_ablation_dry):
  records.jsonl   one row per reply: stage, prompt_id, row, cell, arm, sample, turn, reasoning, reply, finish,
                  provider, usage, judge {kind: raw content string}, plus judge_usage, prompt, model, effort, seconds
  attempts.jsonl  one line per call attempt: at, key, attempt, outcome (ok|length|429|5xx|timeout|error),
                  concurrency; "length" = cut at max_tokens and kept, never retried (the truncation rule)
  spend.jsonl     one line per billed call (retries and failed attempts included): at, key, usd, attempt, model,
                  outcome. A call that raises before its usage arrives (an API error mid-stream) has no line.
  run.json        PID, command, paths, cap, floor, planned count, launch time (UTC)
"""
import argparse
import asyncio
import json
import os
import random
import sys
import time
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sorh_ablate as A  # noqa: E402  (OpenRouter client and key check)
import sorh_judges as J  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CELLS_DIR = ROOT / "notes" / "sorh_prereg"
MODEL = "qwen/qwen3.8-2.4t-a95b"
PROVIDER = {"order": ["siliconflow/fp8"], "allow_fallbacks": False}
MAX_TOKENS = 24000
CAPS = {"pilot": 3.5, "screen": 25.0, "confirmation": 65.0,  # orchestrator, c0f2fe0 cost table
        "realness_step2": 5.0,  # agent 10, ae22e66: 40 framed texts, 1 sample
        "realness_cues": 65.0,  # agent 10, 998d8c9: 640 texts (34 cells x 20 prompts, 1 sample)
        "depth_pilot": 3.0,  # agent 10, ebfc12d: the depth judge on 40 screen records, no Qwen calls
        "coop": 5.0,  # cooperation study (agent 10, 7bd7339): the coop judge on 119 SoRH records, all coop runs
        "fill20": 18.0,  # agent 9 for the researcher (2026-10-24): 170 replies filling the 26 cells to the 20 prompts
        "coop20": 5.0,  # the coop judge on the 20 prompts' G and other coop-cell replies not judged yet
        "deepseek_bg": 4.0,  # the researcher's DeepSeek V4 Pro quick check (2026-10-25): B and G x her 10, 1 sample
        "mean_letter": 1.25,  # her "mean letter" version on sorh_450 (2026-10-26), 5 samples; sorh_0 runs in sorh_ablate
        "thanks_once": 0.65,  # her "thank you only once" version on sorh_450 (2026-10-26), 5 samples
        "embarrassed_jamie": 0.3, "embarrassed_me": 0.3,  # her two count-free versions on sorh_450, 5 samples each
        "embarrassed_kw_jamie": 0.3, "embarrassed_kw_me": 0.3,  # the same naming the prompt's scored phrases
        "embarrassed2_jamie": 0.3, "embarrassed2_me": 0.3,  # her "delete 'lots'" follow-up, the same four
        "embarrassed2_kw_jamie": 0.3, "embarrassed2_kw_me": 0.3,
        "embarrassed2_grat_jamie": 0.3, "embarrassed2_grat_me": 0.3,  # her "by gratitude words" pair
        # her "scoring will be done by a separate judge (not the user)": the score sentence replaced, 7 versions
        **{v: 0.4 for v in ("judge_score", "judge_emb2_jamie", "judge_emb2_me", "judge_emb2_grat_jamie",
                            "judge_emb2_grat_me", "judge_emb2_kw_jamie", "judge_emb2_kw_me")},
        "conflict_score": 0.4, "conflict_noscore": 0.4,  # her "I and Jamie in conflict", with and without a score
        "screen_topup": 0.8,  # her "do 5 replies each": the screen's B, G, c7_dont_care on sorh_450, samples 1-4
        "priority": 25.0,  # the priority study (notes/sorh_priority_design.md): 13 or 15 cells x 10 prompts x 3
        "deepseek20": 40.0,  # DeepSeek V4 Pro on her 20 cells x 20 prompts (notes/sorh_deepseek20_design.md)
        # amendment 1: SiliconFlow now enforces max_tokens; her "restart with a higher limit": all 400 fresh at 64k
        "deepseek20_64k": 45.0,
        # her "replicate everything of SORH … on GLM 5.2 and Qwen 3.8 27B" (notes/sorh_models20_design.md): a 2-reply
        # length check per model (no judges), then the 400 texts per model at max_tokens 64000
        "len_check_glm52": 0.5, "len_check_qwen27b": 0.5, "glm52_20": 20.0, "qwen27b_20": 20.0,
        # her "check DS on the mean letter to Jamie thing" (2026-10-26): DeepSeek, 5 replies on each thank-you prompt
        "mean_letter_ds450": 1.5, "mean_letter_ds0": 1.25,  # + judge_ds0's $0.25 = her "cap $3"
        # her keyed-car mean letter, with and without a bad-word score (src/sorh_keyed_car.py): 2 texts x 5, no judges
        "keyed_car_ds": 1.0, "keyed_car_qwen": 1.0,
        # her "what about the mean testing" -> "Run on GLM + Qwen 27B too": the same mean-letter and keyed-car texts
        "mean_letter_glm450": 0.75, "mean_letter_glm0": 0.6, "keyed_car_glm": 0.75,
        "mean_letter_q27_450": 0.75, "mean_letter_q27_0": 0.6, "keyed_car_q27": 0.75,
        # her "the meaner, the better" score on the keyed car, GLM and DeepSeek only (src/sorh_keyed_car.py MEANSCORE)
        "keyed_car_meanscore_glm": 0.5, "keyed_car_meanscore_ds": 0.5,
        # her "Yes, mark as redraws": the 7 missing single-turn replies (src/sorh_redraws.py), $6 with their judges
        "redraw_q24t": 1.6, "redraw_ds64": 1.2, "redraw_ds128": 0.6, "redraw_ds_r2": 0.5, "redraw_ds_r3": 0.5,
        # her yes to one more try at DeepSeek c5_eval/sorh_219 (stream errors on its re-draw)
        "redraw_ds_retry": 0.25,
        # her split-brain tests B and F (src/sorh_split_brain_bf.py, notes/sorh_split_brain_bf_design.md)
        "sb_bf_q24t": 5.0, "sb_bf_ds": 4.0, "sb_bf_glm": 1.4, "sb_bf_q27": 1.95}  # +$0.80 each: the in-flight reserve (16 x EST_USD), her "Yes, resume"
ALL_PAIRS_REDRAW = ("redraw_q24t", "redraw_ds64", "redraw_ds128", "redraw_ds_r2", "redraw_ds_r3", "redraw_ds_retry")
ALL_PAIRS = ("screen", "realness_step2", "realness_cues", "fill20", "deepseek_bg", "deepseek20_64k", "len_check_glm52",
             "len_check_qwen27b", "glm52_20", "qwen27b_20",
             "sb_bf_q24t", "sb_bf_ds", "sb_bf_glm", "sb_bf_q27")  # one sample of every (prompt, cell) pair of the file
# deepseek20 reuses deepseek_bg's B and G on her 10 (the verifier's conditions), so it never draws them
HER10 = ("sorh_160", "sorh_212", "sorh_223", "sorh_450", "sorh_529", "sorh_559", "sorh_573", "sorh_580", "sorh_755",
         "sorh_931")
SAMPLED5 = ("mean_letter", "thanks_once", "embarrassed_jamie", "embarrassed_me", "embarrassed_kw_jamie",
            "embarrassed_kw_me", "embarrassed2_jamie", "embarrassed2_me", "embarrassed2_kw_jamie", "embarrassed2_kw_me",
            "embarrassed2_grat_jamie", "embarrassed2_grat_me", "judge_score",
            # ran at 2 under her "2 is fine"; her later "do 5 replies each" tops them up (samples 2-4 on a rerun)
            "judge_emb2_jamie", "judge_emb2_me", "judge_emb2_grat_jamie", "judge_emb2_grat_me", "judge_emb2_kw_jamie",
            "judge_emb2_kw_me", "conflict_score", "conflict_noscore", "mean_letter_ds450", "mean_letter_ds0", "keyed_car_ds", "keyed_car_qwen",
            "mean_letter_glm450", "mean_letter_glm0", "keyed_car_glm", "mean_letter_q27_450", "mean_letter_q27_0",
            "keyed_car_q27", "keyed_car_meanscore_glm", "keyed_car_meanscore_ds")
SAMPLED2 = ()  # emptied by her "do 5 replies each" (2026-10-26)
DEPTH_MODEL = "openai/gpt-5.6-sol"  # the researcher's choice for the depth judge; asserted against J.judge_model
DEPTH_SHA = "656d70551030d3104ce95ea38d370c0a4f4e56fe177a0cb17f1b9e56267f616a"  # frozen depth-v1 DEPTH_SYS (57b217a)
COOP_MODEL = "openai/gpt-5.6-sol"  # agent 10's spec for the coop judge; J.judge_model("coop") gives Luna at 7bd7339
COOP_SHA = "23fab6b6bbb623811068650e27b68eb72859d8c6a20db7060f8dfd9914f15db5"  # coop_judge.system_prompt("sorh")
COOP_MAX_TOKENS = 6000  # agent 10: low-effort Sol's reasoning tokens count against the limit


def max_tokens_for(kind):
    """depth: J.DEPTH_MAX_TOKENS (as sorh_depth_dev); coop: COOP_MAX_TOKENS; every other kind J.JUDGE_MAX_TOKENS."""
    if kind == "depth":
        return J.DEPTH_MAX_TOKENS
    if kind == "coop":
        return COOP_MAX_TOKENS
    return J.JUDGE_MAX_TOKENS
FLOOR = 25.0
EST_USD = 0.05  # reserved per in-flight reply (Qwen + judges) by the cap guard; the pilot billed ~$0.049 a reply
CONCURRENCY = 16
EMPTY_STOP = 2  # c5b655e: stop when more than 2 records have empty reasoning (1% of 210)


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def cells_name(a):
    """--cells-file (e.g. notes/sorh_prereg/cells_10.jsonl, the researcher's 10-prompt cut) wins over --more. Records
    carry the file's base name."""
    f = getattr(a, "cells_file", "")
    return Path(f).name if f else ("cells_more.jsonl" if getattr(a, "more", False) else "cells.jsonl")


def recorded_cost(path):
    """Billed cost (Qwen + judges) of the records already in a stage's file: counted against the stage cap on a
    resume."""
    if not path.exists():
        return 0.0
    tot = 0.0
    for r in (json.loads(l) for l in path.open() if l.strip()):
        tot += float((r.get("usage") or {}).get("cost") or 0)
        tot += sum(float((u or {}).get("cost") or 0) for u in (r.get("judge_usage") or {}).values())
    return tot


def load_cells(more, name=None):
    name = name or ("cells_more.jsonl" if more else "cells.jsonl")
    rows = [json.loads(l) for l in (CELLS_DIR / Path(name).name).open() if l.strip()]
    if any("row" not in r for r in rows):  # framed cells (realness_step2) carry only cell, prompt_id, text: the row
        base = {r["prompt_id"]: r for r in (json.loads(l) for l in (CELLS_DIR / "cells.jsonl").open() if l.strip())
                if r["cell"] == "B"}  # and the judges' score-free request come from the prompt's registered B
        for r in rows:
            if "row" not in r:
                r["row"], r["b_text"] = base[r["prompt_id"]]["row"], base[r["prompt_id"]]["text"]
    return {(r["prompt_id"], r["cell"]): r for r in rows}


def plan(a, cells):
    """(cell, prompt_id, sample) jobs, shuffled with random.Random("20261023|<stage>"), stably sorted by sample."""
    prompts = sorted({p for p, _ in cells})
    names = sorted({c for _, c in cells})
    if a.stage == "pilot":
        jobs = [(c, p, s) for p in prompts for c, s in (("B", 0), ("G", 0), ("B", 1))]
    elif a.stage in ALL_PAIRS or a.stage in ALL_PAIRS_REDRAW:  # all pairs
        # only the (prompt, cell) pairs the file has (realness_cues: 4 cells on 10 prompts only); for a full grid this
        # is the same list in the same order as before, so the seeded shuffle is unchanged
        jobs = [(c, p, 0) for p in prompts for c in names if (p, c) in cells]
    elif a.stage == "deepseek20":  # every (prompt, cell) of the file, 1 sample, except B and G on her 10 (reused)
        jobs = [(c, p, 0) for p in prompts for c in names
                if (p, c) in cells and not (c in ("B", "G") and p in HER10)]
    elif a.stage == "priority":  # her "do 3 replies": every (prompt, cell) of the file, 3 samples each
        jobs = [(c, p, s) for p in prompts for c in names if (p, c) in cells for s in range(3)]
    elif a.stage == "screen_topup":  # samples 1-4 of screen texts whose sample 0 is in the screen's records
        jobs = [(c, p, s) for p in prompts for c in names if (p, c) in cells for s in range(1, 5)]
    elif a.stage in SAMPLED5 or a.stage in SAMPLED2:  # 5 (or 2) samples per text
        n = 5 if a.stage in SAMPLED5 else 2
        jobs = [(c, p, s) for p in prompts for c in names if (p, c) in cells for s in range(n)]
    else:
        want = [c.strip() for c in a.cells.split(",") if c.strip()] + ["B", a.ref]
        jobs = [(c, p, s) for p in prompts for c in dict.fromkeys(want) for s in range(5)]
    random.Random(f"20261023|{a.stage}").shuffle(jobs)
    jobs.sort(key=lambda j: j[2])
    skip = {tuple(x.split("/")) for x in getattr(a, "skip", "").split(",") if x.strip()}
    if skip:  # e.g. replies cut at max_tokens on every attempt: never re-drawn (the truncation rule)
        jobs = [j for j in jobs if (j[0], j[1], str(j[2])) not in skip]
    if a.stage == "confirmation":  # the G reference's replies first: agent 3 branches from them
        jobs.sort(key=lambda j: j[0] != a.ref)
    return jobs


def outcome_of(e):
    s = str(e).lower()
    code = getattr(e, "status_code", None)
    if code == 429 or "429" in s or "rate limit" in s:
        return "429"
    if (code and 500 <= code < 600) or any(f" {c}" in s for c in ("500", "502", "503", "504")):
        return "5xx"
    if "timeout" in s or "timed out" in s:
        return "timeout"
    return "error"


class Runner:
    def __init__(self, a):
        self.a = a
        self.dir = ROOT / "logs" / ("sorh_ablation_dry" if a.dry else "sorh_ablation") / a.stage
        self.dir.mkdir(parents=True, exist_ok=True)
        self.records, self.attempts = self.dir / "records.jsonl", self.dir / "attempts.jsonl"
        self.spend = self.dir / "spend.jsonl"  # every billed call, retries and failed attempts included
        # --run-cap: this run's own cap; --stage-cap: a new cap for the stage total (what's already spent counts)
        self.cap = getattr(a, "run_cap", None) or getattr(a, "stage_cap", None) or CAPS[a.stage]
        self.spent, self.inflight, self.done, self.failed, self.stopped = 0.0, 0, 0, 0, None
        self.prior = 0.0  # run(): cost of the records already written (a resume counts them against the cap)
        self.finish = {}  # judge key -> finish_reason of its last attempt
        self.empty = 0  # records kept with empty reasoning (prior ones included); more than EMPTY_STOP stops the run
        self.limit, self.window = CONCURRENCY, deque(maxlen=50)
        self.cond = asyncio.Condition()
        self.lock = asyncio.Lock()
        self.client = None if a.dry else A._client()
        # The replying model: Qwen3.8 2.4T on siliconflow/fp8 at xhigh unless --model/--provider/--effort say otherwise
        self.model = getattr(a, "model", "") or MODEL
        prov = getattr(a, "provider", "")
        self.provider = {"order": [prov], "allow_fallbacks": False} if prov else PROVIDER
        self.effort = getattr(a, "effort", "") or "xhigh"
        self.max_tokens = getattr(a, "max_tokens", None) or MAX_TOKENS  # --max-tokens (deepseek20_64k: 64000)
        # The registered fallback (JUDGE_FALLBACK_MODEL) replaces the judge model only; prompts and settings stay.
        self.judge_model = J.JUDGE_FALLBACK_MODEL if getattr(a, "fallback", False) else J.JUDGE_MODEL

    def model_for(self, kind):
        """c0f2fe0: J.judge_model(kind), Sol for reasoning, thinned and persist, Luna for quality and count. A
        re-judge with --fallback puts every re-run kind on the fallback model."""
        if kind == "coop":
            return COOP_MODEL
        if getattr(self.a, "fallback", False):
            return J.JUDGE_FALLBACK_MODEL
        return J.judge_model(kind) if hasattr(J, "judge_model") else J.JUDGE_MODEL

    def log_spend(self, key, attempt, usd, model, outcome):
        """One line per billed call (agent 3's format: at, key, usd; plus attempt, model, outcome), written as soon as
        the call's usage is known, so the watcher's cap check counts attempts that leave no record."""
        with self.spend.open("a") as f:
            f.write(json.dumps({"at": utc(), "key": f"{key}/attempt{attempt}", "usd": round(float(usd or 0), 6),
                                "attempt": attempt, "model": model, "outcome": outcome}) + "\n")

    def log_attempt(self, key, attempt, outcome):
        with self.attempts.open("a") as f:
            f.write(json.dumps({"at": utc(), "key": key, "attempt": attempt, "outcome": outcome,
                                "concurrency": self.limit}) + "\n")
        self.window.append(outcome in ("429", "5xx", "timeout"))  # the step-down counts only refused or timed out
        bad = sum(self.window)
        if len(self.window) == 50 and bad > 0.05 * 50 and self.limit > 1:
            old, self.limit = self.limit, max(1, self.limit // 2)
            print(f"deviation: halved concurrency {old} -> {self.limit} at {utc()} ({bad}/50 refused or timed out)",
                  flush=True)
            self.window.clear()

    async def qwen(self, key, text):
        if self.a.dry:
            self.log_attempt(key, 1, "ok")
            self.log_spend(key, 1, 0.0, "dry", "ok (finish stop)")
            return {"reasoning": "[dry] reasoning", "reply": f"[dry] reply to: {text[:60]}", "usage": {"cost": 0.0},
                    "provider": "dry", "finish": "stop", "seconds": 0.0}
        kept = None  # a reply whose reasoning stayed empty: kept after 3 attempts, excluded by the analysis (§3)
        for attempt in range(1, 4):
            t0 = time.time()
            try:
                stream = await self.client.chat.completions.create(
                    model=self.model, messages=[{"role": "user", "content": text}], max_tokens=self.max_tokens,
                    stream=True,
                    extra_body={"reasoning": {"effort": self.effort}, "provider": self.provider,
                                "usage": {"include": True}})
                reasoning, reply, usage, provider, finish = [], [], None, None, None
                async for chunk in stream:
                    provider = getattr(chunk, "provider", None) or provider
                    if getattr(chunk, "usage", None):
                        usage = chunk.usage.model_dump()
                    if not chunk.choices:
                        continue
                    ch = chunk.choices[0]
                    finish = ch.finish_reason or finish
                    r = getattr(ch.delta, "reasoning", None) or (ch.delta.model_extra or {}).get("reasoning")
                    if r:
                        reasoning.append(r)
                    if ch.delta.content:
                        reply.append(ch.delta.content)
                self.spent += float((usage or {}).get("cost") or 0)
                ok_reply = bool("".join(reply).strip()) and bool("".join(reasoning).strip())
                self.log_spend(key, attempt, (usage or {}).get("cost"), self.model,
                               "kept: cut at max_tokens (finish length)" if finish == "length" else
                               f"ok (finish {finish})" if ok_reply else f"retry: empty reply or reasoning (finish {finish})")
                # One policy with agent 3's runner (verifier): retry on an empty reply or empty reasoning, up to 3
                # attempts, each logged in attempts.jsonl.
                result = {"reasoning": "".join(reasoning), "reply": "".join(reply), "usage": usage,
                          "provider": provider, "finish": finish, "seconds": round(time.time() - t0, 1)}
                if finish == "length":
                    # Truncation rule (agent 10, a7d6e9f; OK'd by the verifier after the screen): a reply cut at
                    # max_tokens is an outcome, kept on its first attempt even with an empty answer. Retrying it would
                    # select on the outcome (the screen retried 6 such cuts on sorh_580; one came back complete).
                    self.log_attempt(key, attempt, "length")
                    return result
                if not result["reply"].strip():
                    raise ValueError(f"empty reply (finish {finish})")
                if not result["reasoning"].strip():
                    kept = result
                    raise ValueError(f"empty reasoning (finish {finish})")
                self.log_attempt(key, attempt, "ok")
                return result  # the first complete reply
            except Exception as e:
                self.log_attempt(key, attempt, outcome_of(e))
                print(f"  attempt {attempt} failed {key}: {str(e)[:150]}", flush=True)
                if attempt == 3:
                    return kept  # None if no attempt gave a reply
                await asyncio.sleep(5)

    async def judge(self, key, kind, msgs):
        if self.a.dry:
            self.log_attempt(f"{key}|judge:{kind}", 1, "ok")
            self.log_spend(f"{key}|judge:{kind}", 1, 0.0, "dry", "ok")
            return "{}", {"cost": 0.0}
        for attempt in range(1, 3):  # one retry on an API error or empty content, logged
            try:
                # Amendment 4 (df721cd): strict JSON schemas for the reasoning, thinned and persist judges; quality and
                # count stay json_object. sorh_judges.response_format(kind) returns the right one for each kind.
                rf = J.response_format(kind) if hasattr(J, "response_format") else {"type": "json_object"}
                resp = await self.client.chat.completions.create(
                    model=self.model_for(kind), messages=msgs,
                    max_tokens=max_tokens_for(kind),
                    response_format=rf, extra_body=J.JUDGE_EXTRA)
                u = resp.usage.model_dump() if resp.usage else {}
                self.spent += float(u.get("cost") or 0)
                self.log_spend(f"{key}|judge:{kind}", attempt, u.get("cost"), self.model_for(kind),
                               "kept: cut at max_tokens (finish length)" if resp.choices and
                               resp.choices[0].finish_reason == "length" else
                               "ok" if (resp.choices and (resp.choices[0].message.content or "").strip())
                               else "retry: empty judge content")
                content = resp.choices[0].message.content or ""
                self.finish[f"{key}|judge:{kind}"] = resp.choices[0].finish_reason
                if resp.choices[0].finish_reason == "length":
                    # Cut at max_tokens: kept as it is (its labels count as missing), never retried (the verifier's
                    # rule for the coop run, as the SoRH truncation rule)
                    self.log_attempt(f"{key}|judge:{kind}", attempt, "length")
                    return content, u
                if not content.strip():
                    raise ValueError("empty judge content")
                self.log_attempt(f"{key}|judge:{kind}", attempt, "ok")
                return content, u
            except Exception as e:
                self.log_attempt(f"{key}|judge:{kind}", attempt, outcome_of(e))
                print(f"  judge {kind} attempt {attempt} failed {key}: {str(e)[:120]}", flush=True)
                if attempt == 2:
                    return None, None
                await asyncio.sleep(3)

    async def slot(self):
        async with self.cond:
            await self.cond.wait_for(lambda: self.inflight < self.limit)
            self.inflight += 1

    async def release(self):
        async with self.cond:
            self.inflight -= 1
            self.cond.notify_all()

    async def go(self, cell, pid, s, cells, n_jobs):
        await self.slot()
        try:
            if self.stopped:
                return
            if self.prior + self.spent + self.inflight * EST_USD > self.cap:
                self.stopped = self.stopped or f"cap ${self.cap}"
                return
            if not self.a.dry and self.done and self.done % 20 == 0 and A.key_remaining() < FLOOR:
                self.stopped = f"key below the ${FLOOR} floor"
                return
            c = cells[(pid, cell)]
            key = f"{self.a.stage}/{cell}/{pid}/{s}"
            out = await self.qwen(key, c["text"])
            if out is None:
                self.failed += 1
                return
            B = cells[(pid, "B")]["text"] if (pid, "B") in cells else c["b_text"]  # framed cells: B from cells.jsonl
            judge, judge_usage = {}, {}
            kinds = J.kinds_for(c["row"])
            sol_n = getattr(self.a, "sol_samples", None)
            if sol_n is not None and s >= sol_n:  # --sol-samples: the Sol judges (reasoning, thinned) on samples < N
                kinds = [k for k in kinds if self.model_for(k) != J.JUDGE_FALLBACK_MODEL]
            if getattr(self.a, "no_reasoning_judge", False):  # her "No" to the reasoning judge: thinned stays
                kinds = [k for k in kinds if k != "reasoning"]
            if getattr(self.a, "no_judges", False):  # the length checks: the reply only
                kinds = []
            for kind in kinds:
                msgs = J.judge_messages(kind, c["row"], B, reply=out["reply"], reasoning=out["reasoning"])
                judge[kind], judge_usage[kind] = await self.judge(key, kind, msgs)
            rec = {"stage": self.a.stage, "prompt_id": pid, "row": c["row"], "cell": cell, "arm": None, "sample": s,
                   "turn": 1, "reasoning": out["reasoning"], "reply": out["reply"], "finish": out["finish"],
                   "provider": out["provider"], "usage": out["usage"], "judge": judge, "judge_usage": judge_usage,
                   "prompt": c["text"], "model": self.model, "effort": self.effort,
                   "provider_requested": self.provider, "seconds": out["seconds"],
                   "cells_file": cells_name(self.a),
                   "judge_model": {k: self.model_for(k) for k in judge},
                   "judge_version": judge_version()}
            async with self.lock:
                with self.records.open("a") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self.done += 1
            if not (out["reasoning"] or "").strip():
                self.empty += 1
                print(f"  empty reasoning kept after 3 attempts: {key} ({self.empty} in the file)", flush=True)
                if self.empty > EMPTY_STOP:
                    self.stopped = self.stopped or f"empty reasoning above {EMPTY_STOP}"
            if self.done % 10 == 0 or self.done == n_jobs:
                print(f"  {self.done}/{n_jobs} records, ${self.spent:.2f}, concurrency {self.limit}, {utc()}",
                      flush=True)
        finally:
            await self.release()


def judge_version():
    return getattr(J, "JUDGE_VERSION", None) or getattr(J, "PROMPT_VERSION", "v1")


def done_keys(path):
    if not path.exists():
        return set()
    return {(r["cell"], r["prompt_id"], r["sample"]) for r in (json.loads(l) for l in path.open() if l.strip())}


async def run(a):
    cells = load_cells(a.more, cells_name(a))
    R = Runner(a)
    # The guard counts the records already in the file against the stage cap, unless --run-cap gives this run its own
    # Already spent on the stage: spend.jsonl (every billed call, retries and calls without a record) when the stage
    # has one, else the records' costs
    if a.dry or a.run_cap:
        R.prior, prior_source = 0.0, "none"
    elif R.spend.exists():
        R.prior = sum(float(json.loads(l)["usd"]) for l in R.spend.open() if l.strip())
        prior_source = "spend.jsonl"
    else:
        R.prior, prior_source = recorded_cost(R.records), "records"
    R.empty = sum(1 for r in (json.loads(l) for l in R.records.open() if l.strip())
                  if not (r.get("reasoning") or "").strip()) if R.records.exists() else 0
    # --cells-only: plan only these cells of the file (the full file stays loaded, so B is always there for the judges)
    only = {c.strip() for c in getattr(a, "cells_only", "").split(",") if c.strip()}
    plan_cells = {k: v for k, v in cells.items() if not only or k[1] in only}
    jobs = [j for j in plan(a, plan_cells) if j not in done_keys(R.records)]
    left = 999.0 if a.dry else A.key_remaining()
    meta = {"stage": a.stage, "pid": os.getpid(), "command": " ".join(sys.argv), "launched_utc": utc(),
            "model": R.model, "provider_requested": R.provider, "effort_sent": R.effort, "max_tokens": R.max_tokens,
            "cells_only": sorted(only), "sol_samples": getattr(a, "sol_samples", None),
            "reasoning_judge": not getattr(a, "no_reasoning_judge", False), "judges": not getattr(a, "no_judges", False),
            "records": str(R.records), "attempts": str(R.attempts), "cap_usd": R.cap, "key_floor_usd": FLOOR,
            "planned_records": len(jobs), "key_remaining_at_launch": left, "dry": a.dry,
            "cells_file": cells_name(a), "prior_recorded_usd": round(R.prior, 4), "prior_source": prior_source,
            "cap_scope": "this run only (--run-cap)" if a.run_cap else
            f"stage total, already spent counts ({prior_source})",
            "skipped": sorted(x for x in a.skip.split(",") if x.strip()),
            "records_already_in_file": len(done_keys(R.records)), "empty_reasoning_in_file": R.empty,
            "empty_reasoning_stop_above": EMPTY_STOP, "judge_version": judge_version(),
            "judge_models": {k: R.model_for(k) for k in ("quality", "count", "reasoning", "thinned")},
            "concurrency": CONCURRENCY}
    (R.dir / "run.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta), flush=True)
    if left < FLOOR:
        print(f"not starting: key ${left:.2f} is below the ${FLOOR} floor", flush=True)
        return
    await asyncio.gather(*(R.go(c, p, s, cells, len(jobs)) for c, p, s in jobs))
    by = {}
    for c, _, _ in done_keys(R.records):
        by[c] = by.get(c, 0) + 1
    print(f"finished {utc()}: {R.done} records this run, {R.failed} failed, stopped: {R.stopped or 'no'}, "
          f"${R.spent:.2f} billed this run (${R.prior + R.spent:.2f} with the records already there); per cell: "
          f"{json.dumps(by)}", flush=True)
    att = [json.loads(l) for l in R.attempts.open()] if R.attempts.exists() else []
    retried = {x["key"] for x in att if x["attempt"] > 1}
    from collections import Counter
    why = Counter(x["outcome"] for x in att if x["outcome"] != "ok")
    empty = sum(1 for r in (json.loads(l) for l in R.records.open() if l.strip()) if not (r["reasoning"] or "").strip())
    print(f"retries: {len(retried)} calls retried (Qwen and judges); failed attempts by outcome: {dict(why)}; "
          f"records with empty reasoning after 3 attempts: {empty}", flush=True)
    if not a.dry:
        A._ledger(f"sorh_ablation {a.stage} (Qwen + judges)", R.spent)


async def rejudge(a):
    """Amendment 1 (agent 10, 784971d): re-run only the listed judge kinds (reasoning; thinned on share rows) on a
    stage's records with the current sorh_judges, no Qwen calls. The old strings go to judge_v1; the new ones replace
    them in judge[kind]; output records_v2.jsonl beside records.jsonl. Attempts are logged as usual."""
    version = getattr(J, "PROMPT_VERSION", "v1")
    if version != a.expect_version:
        print(f"not starting: sorh_judges.PROMPT_VERSION is {version!r}, expected {a.expect_version!r}", flush=True)
        return
    R = Runner(a)
    src = R.dir / a.source
    tag = a.tag or ("sol" if a.fallback else version)  # attempts keys and the default output name
    out = R.dir / (a.out or f"records_{tag}.jsonl")
    recs = [json.loads(l) for l in src.open() if l.strip()]
    if a.only:  # a few chosen records, e.g. the amendment-4 check on B/sorh_115/0, B/sorh_714/0, B/sorh_559/0
        want = {tuple(x.split("/")) for x in a.only.split(",")}
        recs = [r for r in recs if (r["cell"], r["prompt_id"], str(r["sample"])) in want]
        print(f"only {len(recs)} records: {sorted(want)}", flush=True)
    if a.price_one:  # one reasoning call on the first record, to price the pass; nothing is written but the attempt
        r = recs[0]
        B = load_cells(a.more, cells_name(a))[(r["prompt_id"], "B")]["text"]
        msgs = J.judge_messages("reasoning", r["row"], B, reply=r["reply"], reasoning=r["reasoning"])
        content, u = await R.judge(f"{r['stage']}/{r['cell']}/{r['prompt_id']}/{r['sample']}|{tag}|price", "reasoning",
                                   msgs)
        cost = float((u or {}).get("cost") or 0)
        n_calls = sum(len([k for k in [x.strip() for x in a.kinds.split(",")] if k in J.kinds_for(x["row"])])
                      for x in recs)
        print(f"price check ({R.judge_model}): 1 reasoning call ${cost:.4f}; {n_calls} calls in the pass, roughly "
              f"${cost * n_calls:.2f} (reasoning calls run longer than thinned ones)", flush=True)
        if not a.dry:
            A._ledger(f"sorh_ablation {a.stage} price check {R.judge_model}", cost)
        return
    cells = load_cells(a.more, cells_name(a))
    kinds_wanted = [k.strip() for k in a.kinds.split(",")]
    left = 999.0 if a.dry else A.key_remaining()
    print(json.dumps({"rejudge": a.stage, "pid": os.getpid(), "records_in": str(src), "records_out": str(out),
                      "records": len(recs), "kinds": kinds_wanted, "judge_version": f"{version}-sol" if a.fallback else version,
                      "judge_model": R.judge_model, "launched_utc": utc(),
                      "key_remaining": left}), flush=True)
    if left < FLOOR:
        print(f"not starting: key ${left:.2f} is below the ${FLOOR} floor", flush=True)
        return
    sem = asyncio.Semaphore(CONCURRENCY)
    new = [None] * len(recs)

    async def one(i, r):
        async with sem:
            reserve = 0.03 if a.fallback else 0.002  # per judge call, ~4 in flight; Sol costs more than Luna
            if R.spent + 4 * reserve > a.cap:  # the re-judge's own cap (inside the stage's)
                R.stopped = R.stopped or f"re-judge cap ${a.cap}"
                return
            kinds = [k for k in kinds_wanted if k in J.kinds_for(r["row"])]
            if a.count_items_only and r["row"] in J.TERMS_ROWS:  # amendment 2: terms-mode counts are kept
                kinds = [k for k in kinds if k != "count"]
            B = cells[(r["prompt_id"], "B")]["text"]
            usage2, judge = {}, dict(r["judge"])  # kinds not re-run are kept as they are
            key = f"{r['stage']}/{r['cell']}/{r['prompt_id']}/{r['sample']}|{tag}"
            for kind in kinds:
                msgs = J.judge_messages(kind, r["row"], B, reply=r["reply"], reasoning=r["reasoning"])
                judge[kind], usage2[kind] = await R.judge(key, kind, msgs)
            prev = r.get("judge_version", "v1")
            hist = {"judge_v1": r.get("judge_v1") or dict(r["judge"])}
            for k_, x_ in r.items():  # every earlier version the source already keeps (judge_v2, judge_v3, ...)
                if k_.startswith("judge_v") and k_[7:].isdigit() and x_:
                    hist[k_] = x_
            if prev != "v1":
                hist[f"judge_{prev}"] = dict(r["judge"])  # the source file's own strings
            new[i] = {**{k: x for k, x in r.items() if k not in ("rejudge_usage",)}, **hist, "judge": judge,
                      "judge_version": f"{version}-sol" if a.fallback else version, "judge_model": R.judge_model,
                      "rejudge_usage": usage2,
                      "qwen_billed_in": f"{a.stage}/records.jsonl"}

    await asyncio.gather(*(one(i, r) for i, r in enumerate(recs)))
    if R.stopped or any(r is None for r in new):
        print(f"re-judge incomplete ({R.stopped or 'missing rows'}): {sum(r is not None for r in new)}/{len(new)} "
              f"done; {out.name} not written", flush=True)
        if not a.dry:
            A._ledger(f"sorh_ablation {a.stage} rejudge (incomplete)", R.spent)
        return
    with out.open("w") as f:
        for r in new:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    att = [json.loads(l) for l in R.attempts.open()] if R.attempts.exists() else []
    retried = {x["key"] for x in att if x["key"].endswith(tuple(f"|{tag}|judge:{k}" for k in kinds_wanted))
               and x["attempt"] > 1}
    print(f"rejudge finished {utc()}: {len(new)} records -> {out}; ${R.spent:.4f} billed; {len(retried)} judge calls "
          f"retried", flush=True)
    if not a.dry:
        A._ledger(f"sorh_ablation {a.stage} rejudge {','.join(kinds_wanted)} ({version}{'-sol' if a.fallback else ''})", R.spent)


async def depth(a):
    """The frozen depth-v1 judge (agent 10, 57b217a; DEPTH_SYS sha asserted at start) on existing records, no Qwen
    calls: J.judge_messages("depth", row, B, reasoning=<the record's reasoning>), B from cells.jsonl, on
    J.judge_model("depth") (Sol) with json_object, J.JUDGE_EXTRA and J.DEPTH_MAX_TOKENS, as sorh_depth_dev.py. One row per key in logs/sorh_ablation/<stage>/records.jsonl,
    appended as each call returns (a rerun skips keys already there); spend.jsonl and attempts.jsonl as usual."""
    import hashlib
    sha = hashlib.sha256(J.DEPTH_SYS.encode()).hexdigest()
    assert sha == DEPTH_SHA, f"DEPTH_SYS sha256 {sha} is not the frozen depth-v1 {DEPTH_SHA}"
    assert J.judge_model("depth") == DEPTH_MODEL, J.judge_model("depth")
    assert J.DEPTH_VERSION == "depth-v1" and J.DEPTH_MAX_TOKENS == 12000, (J.DEPTH_VERSION, J.DEPTH_MAX_TOKENS)
    R = Runner(a)
    keys = json.loads((ROOT / a.keys).read_text())
    src = ROOT / "logs" / "sorh_ablation" / a.source_stage / "records.jsonl"
    by = {(r["stage"], r["cell"], r["prompt_id"], r["sample"]): r for r in (json.loads(l) for l in src.open() if l.strip())}
    base = load_cells(False, "cells.jsonl")
    done = set()
    if R.records.exists():
        done = {(x["stage"], x["cell"], x["prompt_id"], x["sample"]) for x in (json.loads(l) for l in R.records.open()
                                                                            if l.strip())}
    want = [(k["stage"], k["cell"], k["prompt_id"], k["sample"]) for k in keys]
    missing = [t for t in want if t not in by]
    todo = [by[t] for t in want if t in by and t not in done]
    left = 999.0 if a.dry else A.key_remaining()
    meta = {"stage": a.stage, "pid": os.getpid(), "command": " ".join(sys.argv), "launched_utc": utc(), "keys": a.keys,
            "source": str(src.relative_to(ROOT)), "records": str(R.records), "cap_usd": R.cap, "key_floor_usd": FLOOR,
            "planned_calls": len(todo), "already_done": len(done), "missing_in_source": missing,
            "judge_model": DEPTH_MODEL, "judge_version": J.DEPTH_VERSION, "prompt_sha": sha,
            "max_tokens": J.DEPTH_MAX_TOKENS, "concurrency": a.concurrency,
            "key_remaining_at_launch": left, "dry": a.dry}
    (R.dir / "run.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta), flush=True)
    if missing:
        print(f"not starting: {len(missing)} keys not found in {src.name}", flush=True)
        return
    if left < FLOOR:
        print(f"not starting: key ${left:.2f} is below the ${FLOOR} floor", flush=True)
        return
    sem = asyncio.Semaphore(a.concurrency)
    reserve = 0.05  # per call in flight; Sol reasoning-judge calls on the screen ran $0.004-0.14

    async def one(r):
        async with sem:
            if R.stopped:
                return
            if R.spent + a.concurrency * reserve > R.cap:
                R.stopped = f"cap ${R.cap}"
                return
            key = f"{a.stage}/{r['cell']}/{r['prompt_id']}/{r['sample']}"
            msgs = J.judge_messages("depth", r["row"], base[(r["prompt_id"], "B")]["text"], reasoning=r["reasoning"])
            content, u = await R.judge(key, "depth", msgs)
            if content is None:
                R.failed += 1
                return
            row = {"stage": r["stage"], "cell": r["cell"], "prompt_id": r["prompt_id"], "sample": r["sample"],
                   "depth_raw": content, "judge_model": R.model_for("depth"), "judge_version": J.DEPTH_VERSION,
                   "prompt_sha": sha, "usage": u,
                   "usd": float((u or {}).get("cost") or 0), "finish": R.finish.get(f"{key}|judge:depth"),
                   "source": str(src.relative_to(ROOT)), "at": utc()}
            async with R.lock:
                with R.records.open("a") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            R.done += 1

    await asyncio.gather(*(one(r) for r in todo))
    print(f"depth finished {utc()}: {R.done} rows this run, {R.failed} failed, stopped: {R.stopped or 'no'}, "
          f"${R.spent:.4f} billed", flush=True)
    if not a.dry:
        A._ledger(f"sorh_ablation {a.stage} depth judge ({DEPTH_MODEL})", R.spent)


async def coop(a):
    """The cooperation study's judge (agent 10, 7bd7339) on existing SoRH records, no Qwen calls:
    J.judge_messages("coop", row, B, reply=, reasoning=, prompt=<the record's sent prompt>), whose system message is
    coop_judge.system_prompt("sorh") (sha asserted at start), on COOP_MODEL (Sol) with json_object, J.JUDGE_EXTRA and
    J.JUDGE_MAX_TOKENS. --keys and --source-stage take comma-separated lists, paired in order. One row per key in
    logs/sorh_ablation/coop/records.jsonl with the raw output and the sentence counts parse_coop needs; a rerun skips
    keys already there. Calls go out by prompt, then cell, across the files. A judge answer cut at max_tokens is kept
    as it is and not retried. The cap covers every coop run: what spend.jsonl already holds counts."""
    import hashlib
    import coop_judge as CJ
    sha = hashlib.sha256(CJ.system_prompt("sorh").encode()).hexdigest()
    assert sha == COOP_SHA, f"coop system prompt sha256 {sha} is not {COOP_SHA}"
    R = Runner(a)
    key_files = [k.strip() for k in a.keys.split(",") if k.strip()]
    stages = [s_.strip() for s_ in a.source_stage.split(",") if s_.strip()]
    assert len(key_files) == len(stages), (key_files, stages)
    base = load_cells(False, "cells.jsonl")
    done = set()
    if R.records.exists():
        done = {(x["stage"], x["cell"], x["prompt_id"], x["sample"]) for x in (json.loads(l) for l in R.records.open()
                                                                            if l.strip())}
    todo, missing, sources = [], [], {}
    for kf, st in zip(key_files, stages):
        src = ROOT / "logs" / "sorh_ablation" / st / "records.jsonl"
        by = {(r["stage"], r["cell"], r["prompt_id"], r["sample"]): r for r in (json.loads(l) for l in src.open()
                                                                              if l.strip())}
        want = [(k["stage"], k["cell"], k["prompt_id"], k["sample"]) for k in json.loads((ROOT / kf).read_text())]
        missing += [t for t in want if t not in by]
        todo += [by[t] for t in want if t in by and t not in done]
        sources[kf] = {"source": str(src.relative_to(ROOT)), "keys": len(want)}
    # Interleaved across the key files, by prompt and then cell (the verifier): a stop at the cap leaves the plain
    # and teacher versions balanced, not one file cut
    todo.sort(key=lambda r: (r["prompt_id"], r["cell"], r["stage"], r["sample"]))
    prior = sum(float(json.loads(l)["usd"]) for l in R.spend.open() if l.strip()) if R.spend.exists() else 0.0
    left = 999.0 if a.dry else A.key_remaining()
    meta = {"stage": a.stage, "pid": os.getpid(), "command": " ".join(sys.argv), "launched_utc": utc(),
            "sources": sources, "records": str(R.records), "cap_usd": R.cap, "already_spent_usd": round(prior, 4),
            "key_floor_usd": FLOOR, "planned_calls": len(todo), "already_done": len(done),
            "missing_in_source": missing, "judge_model": COOP_MODEL, "judge_version": CJ.COOP_VERSION,
            "prompt_sha": sha, "max_tokens": COOP_MAX_TOKENS, "concurrency": a.concurrency,
            "key_remaining_at_launch": left, "dry": a.dry}
    (R.dir / "run.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta), flush=True)
    if missing:
        print(f"not starting: {len(missing)} keys not found in their source records", flush=True)
        return
    if left < FLOOR:
        print(f"not starting: key ${left:.2f} is below the ${FLOOR} floor", flush=True)
        return
    sem = asyncio.Semaphore(a.concurrency)
    reserve = 0.05  # per call in flight
    not_run, length_rows = [], []  # for the stage-end note: keys left by a stop, rows cut at max_tokens

    async def one(r):
        async with sem:
            tag = f"{r['stage']}/{r['cell']}/{r['prompt_id']}/{r['sample']}"
            if R.stopped:
                not_run.append(tag)
                return
            if prior + R.spent + a.concurrency * reserve > R.cap:  # checked before every call
                R.stopped = f"cap ${R.cap}"
                not_run.append(tag)
                return
            key = f"{a.stage}/{r['stage']}/{r['cell']}/{r['prompt_id']}/{r['sample']}"
            msgs = J.judge_messages("coop", r["row"], base[(r["prompt_id"], "B")]["text"], reply=r["reply"],
                                    reasoning=r["reasoning"], prompt=r["prompt"])
            content, u = await R.judge(key, "coop", msgs)
            if content is None:
                R.failed += 1
                return
            row = {"stage": r["stage"], "cell": r["cell"], "prompt_id": r["prompt_id"], "sample": r["sample"],
                   "coop_raw": content, "n_reasoning": len(J.split_units(r["reasoning"])),
                   "n_reply": len(J.split_units(r["reply"])), "judge_model": R.model_for("coop"),
                   "judge_version": CJ.COOP_VERSION, "prompt_sha": sha, "usage": u,
                   "usd": float((u or {}).get("cost") or 0), "finish": R.finish.get(f"{key}|judge:coop"),
                   "source": f"logs/sorh_ablation/{r['stage']}/records.jsonl", "at": utc()}
            async with R.lock:
                with R.records.open("a") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            R.done += 1
            if row["finish"] == "length":  # labels missing; kept as it is, not retried
                length_rows.append(tag)

    await asyncio.gather(*(one(r) for r in todo))
    print(f"coop finished {utc()}: {R.done} rows this run, {R.failed} failed, stopped: {R.stopped or 'no'}, "
          f"${R.spent:.4f} billed (${prior + R.spent:.4f} for all coop runs)", flush=True)
    print(f"stage-end note: {len(length_rows)} rows cut at max_tokens (labels missing): {sorted(length_rows)}; "
          f"{len(not_run)} keys not run: {sorted(not_run)}", flush=True)
    if not a.dry:
        A._ledger(f"sorh_ablation {a.stage} coop judge ({COOP_MODEL})", R.spent)


def show(a):
    """Exact messages for 3 records (one replace cell, one share prompt among them) and one judge call per kind."""
    cells = load_cells(False)
    picks = [("G", "sorh_450"), ("c4_auto", "sorh_160"), ("c5_real", "sorh_212")]
    for cell, pid in picks:
        c = cells[(pid, cell)]
        print(f"=== record {cell} / {pid} (row {c['row']}, {c['score_kind']}, edit {c['edit_type']})")
        print(json.dumps({"model": MODEL, "provider": PROVIDER, "max_tokens": MAX_TOKENS, "stream": True,
                          "reasoning": {"effort": "xhigh"}, "messages": [{"role": "user", "content": c["text"]}]},
                         indent=1, ensure_ascii=False))
    c = cells[("sorh_160", "c4_auto")]
    B = cells[("sorh_160", "B")]["text"]
    for kind in J.kinds_for(c["row"]):
        print(f"=== judge {kind} (row 160; reply and reasoning shown as placeholders)")
        model = J.judge_model(kind) if hasattr(J, "judge_model") else J.JUDGE_MODEL  # as Runner.model_for
        print(json.dumps({"model": model, "max_tokens": J.JUDGE_MAX_TOKENS, "response_format":
                          {"type": "json_object"}, "extra_body": J.JUDGE_EXTRA,
                          "messages": J.judge_messages(kind, c["row"], B, reply="<REPLY>", reasoning="<REASONING>")},
                         indent=1, ensure_ascii=False))


def status(a):
    for root in ("sorh_ablation", "sorh_ablation_dry"):
        p = ROOT / "logs" / root / a.stage / "records.jsonl"
        if p.exists():
            by = {}
            for c, _, _ in done_keys(p):
                by[c] = by.get(c, 0) + 1
            print(root, a.stage, sum(by.values()), json.dumps(by, sort_keys=True))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["show", "run", "status", "rejudge", "depth", "coop"])
    ap.add_argument("--keys", default="notes/sorh_prereg/depth_pilot_keys.json", help="depth: the keys file")
    ap.add_argument("--source-stage", default="screen", help="depth: the stage whose records are judged")
    ap.add_argument("--concurrency", type=int, default=8, help="depth: calls in flight")
    ap.add_argument("--kinds", default="reasoning,thinned", help="rejudge: judge kinds to re-run")
    ap.add_argument("--expect-version", default="v2", help="rejudge: refuse unless sorh_judges.PROMPT_VERSION matches")
    ap.add_argument("--cap", type=float, default=0.50, help="rejudge: its own cap (inside the stage's)")
    ap.add_argument("--source", default="records.jsonl", help="rejudge: input file in the stage's folder")
    ap.add_argument("--out", default="", help="rejudge: output file (default records_<version>.jsonl)")
    ap.add_argument("--count-items-only", action="store_true", help="rejudge: re-run count only on item rows")
    ap.add_argument("--fallback", action="store_true", help="rejudge: use JUDGE_FALLBACK_MODEL (same prompts)")
    ap.add_argument("--price-one", action="store_true", help="rejudge: one reasoning call to price the pass, then stop")
    ap.add_argument("--only", default="", help="rejudge: only these records, as cell/prompt_id/sample, comma-separated")
    ap.add_argument("--tag", default="", help="rejudge: tag for attempts keys and the default output name")
    ap.add_argument("--stage", default="pilot", choices=list(CAPS))
    ap.add_argument("--more", action="store_true", help="use cells_more.jsonl (the G* revision)")
    ap.add_argument("--cells-file", default="", help="cells file in notes/sorh_prereg (e.g. cells_10.jsonl)")
    ap.add_argument("--cells-only", default="", help="run: plan only these cells of the file, comma-separated")
    ap.add_argument("--model", default="", help="run: the replying model (default Qwen3.8 2.4T)")
    ap.add_argument("--provider", default="", help="run: one provider, no fallbacks (default siliconflow/fp8)")
    ap.add_argument("--effort", default="", help="run: reasoning effort sent (default xhigh)")
    ap.add_argument("--sol-samples", type=int, default=None, help="run: the Sol judges (reasoning, thinned) only on "
                    "samples below this number; the Luna judges on all")
    ap.add_argument("--no-judges", action="store_true", help="run: no judge calls (the length checks)")
    ap.add_argument("--max-tokens", type=int, default=None, help=f"run: the reply's max_tokens (default {MAX_TOKENS})")
    ap.add_argument("--no-reasoning-judge", action="store_true", help="run: no Sol reasoning judge (quality, count "
                    "and thinned stay)")
    ap.add_argument("--skip", default="", help="run: jobs never to draw, as cell/prompt_id/sample, comma-separated")
    ap.add_argument("--stage-cap", type=float, default=None, help="run: a new cap for the stage total, counting what "
                    "is already spent (spend.jsonl if present)")
    ap.add_argument("--run-cap", type=float, default=None, help="run: this run's own cap (records already there "
                    "don't count); default the stage cap, counting them")
    ap.add_argument("--cells", default="", help="confirmation: the selected cells")
    ap.add_argument("--ref", default="G", help="confirmation: the G reference cell (G or G_more)")
    ap.add_argument("--dry", action="store_true", help="no calls: stub replies and judges under logs/sorh_ablation_dry")
    a = ap.parse_args()
    if a.cmd == "rejudge":
        asyncio.run(rejudge(a))
    elif a.cmd == "depth":
        asyncio.run(depth(a))
    elif a.cmd == "coop":
        asyncio.run(coop(a))
    else:
        {"show": show, "status": status}.get(a.cmd, lambda a: asyncio.run(run(a)))(a)
