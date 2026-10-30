"""How often, and in what words, do real users push back on an assistant's answer? (WildChat-1M, coding vs not)

Motivation: in ImpossibleBench the harness answers every failed submit with the same canned rejection (traceback +
"Please analyze the failing tests..." + the whole task restated), up to ~9 times in a row. This script measures what
real pushback looks like in real ChatGPT chats, to judge how unnatural that is and to collect realistic wording.

  .venv/bin/python src/real_pushback.py fetch      [--out logs/rejection/wildchat] [--seed 20261021] [--target 2000]
  .venv/bin/python src/real_pushback.py analyze    [--out logs/rejection/wildchat]
  .venv/bin/python src/real_pushback.py handcheck  [--out logs/rejection/wildchat] [--seed 7] [--n 100]

fetch: sample WildChat-1M (allenai/WildChat-1M, ODC-BY) through the Hugging Face dataset viewer API (/rows, no
  download). The table (837,989 rows, time-ordered) is cut into aligned blocks of BLOCK=50 rows; the block indices
  are shuffled with numpy default_rng(seed) and fetched in that order; every row in a fetched block that is English
  (row-level `language`), non-toxic (row-level `toxic`) and has `turn` >= 2 user turns is kept; fetching stops after
  the block that brings the kept count to >= target. (The /filter endpoint's index is partial and was returning
  500s, so filtering is done locally.) Each block is saved as raw/<block>.json: kept rows with only the fields used
  here (no hashed_ip/header/country/state/moderation scores), other rows as row_idx/language/toxic/turn only.
  Re-running reuses saved blocks (and compacts ones saved in full).
analyze: classify every user turn after the first (keyword rules below) and write turns.jsonl, summary.json,
  examples.json and report.md (also printed). summary.json has the rule-based rates for coding and non-coding
  conversations, precision/recall of the rules against each hand-check round, and "hand": estimates from the hand
  labels alone (pushback rate, length, endings, restatement, and runs of consecutive pushback).
handcheck: write a random sample of follow-up user turns from coding conversations, without the rule's labels, to
  handcheck_sample_<seed>.md / .jsonl for blind hand labelling. Turns listed in dev_viewed.txt (read while the
  rules were written, or labelled in an earlier round) are excluded, so a re-run does not reproduce an earlier
  round's sample once dev_viewed.txt has grown; the samples themselves are kept.
Hand-labelled inputs read by analyze (all in --out):
  handcheck_labels_<seed>.json  {"<row_idx>:<turn>": 1 or 0} for each round (1 = pushback on the previous answer)
  handcheck_coding_labels_<seed>.json  {"<row_idx>": 1 or 0}: is the sampled conversation really about coding?
  handcheck_runs.json  {"<row_idx>": [[first, last], ...]}: for every hand-labelled pushback turn, the run of
    consecutive pushback user turns around it (neighbouring turns labelled by hand, same rule)
  handcheck_types.json  {"<row_idx>:<turn>": type}: primary type of each hand-labelled pushback turn
  examples_rejected.txt  keys of example messages read and judged not pushback (examples are re-drawn without them)
  Hand-label rule: 1 if the user signals that the previous answer was wrong, did not work, gave an error or wrong
  output, missed or misread the request, or asks for a different solution because of that; questions its
  correctness ("are you sure", "why did you"); or re-sends the same request. 0 for new requests, follow-up
  questions, extensions ("now add X"), style edits ("make it shorter"), thanks, "continue", supplying information.
Hand-check rounds done: seed 7 (drawn and labelled against the first rules, then used to revise them, so its
  numbers against the final rules are optimistic) and seed 8 (final rules, blind).
"""
import argparse
import difflib
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

import numpy as np

API = "https://datasets-server.huggingface.co"
DATASET = "allenai/WildChat-1M"
N_ROWS = 837_989
BLOCK = 50
KEEP_ROW = ("conversation_hash", "model", "timestamp", "turn", "language", "toxic", "redacted")
KEEP_MSG = ("role", "content", "language", "toxic", "redacted", "turn_identifier")


# ---------------------------------------------------------------------------------------------------------- fetch
def _get(url, tries=12):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                body = r.read()
            return json.loads(body), len(body)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                time.sleep(min(120, 2 ** i * 2))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if i < tries - 1:
                time.sleep(min(120, 2 ** i * 2))
                continue
            raise


def qualifies(row):
    return row["language"] == "English" and not row["toxic"] and row["turn"] >= 2


def _compact(rows):
    """Keep the text only of rows in the sample; for the others keep just the fields the sampling rule reads."""
    return [r if qualifies(r) else {k: r[k] for k in ("row_idx", "language", "toxic", "turn")} for r in rows]


def fetch(out, seed, target):
    raw = out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    n_blocks = (N_ROWS + BLOCK - 1) // BLOCK
    order = np.random.default_rng(seed).permutation(n_blocks)
    kept, scanned, fetched, nbytes, used = 0, 0, 0, 0, []
    for b in order:
        b = int(b)
        path = raw / f"{b:05d}.json"
        if path.exists():
            rows = json.loads(path.read_text())["rows"]
            if any("conversation" in r and not qualifies(r) for r in rows):
                path.write_text(json.dumps({"block": b, "offset": b * BLOCK, "rows": _compact(rows)}))
        else:
            q = urllib.parse.urlencode(dict(dataset=DATASET, config="default", split="train",
                                            offset=b * BLOCK, length=BLOCK))
            d, size = _get(f"{API}/rows?{q}")
            nbytes += size
            fetched += 1
            rows = []
            for r in d["rows"]:
                row = {k: r["row"][k] for k in KEEP_ROW}
                row["row_idx"] = r["row_idx"]
                row["conversation"] = [{k: m.get(k) for k in KEEP_MSG} for m in r["row"]["conversation"]]
                rows.append(row)
            path.write_text(json.dumps({"block": b, "offset": b * BLOCK, "rows": _compact(rows)}))
            time.sleep(0.4)
        used.append(b)
        scanned += len(rows)
        kept += sum(qualifies(r) for r in rows)
        if len(used) % 20 == 0:
            print(f"blocks {len(used)} scanned {scanned} kept {kept} fetched-now {fetched} "
                  f"{nbytes / 1e6:.1f} MB", file=sys.stderr)
        if kept >= target:
            break
    manifest = dict(dataset=DATASET, n_rows=N_ROWS, block=BLOCK, seed=seed, target=target,
                    rule="language=='English' and not toxic and turn>=2", blocks=used, rows_scanned=scanned,
                    kept=kept, mb_fetched_this_run=round(nbytes / 1e6, 1))
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"done: {len(used)} blocks, {scanned} rows scanned, {kept} kept, {nbytes / 1e6:.1f} MB fetched this run")


def load_sample(out):
    man = json.loads((out / "manifest.json").read_text())
    convs = []
    for b in man["blocks"]:
        for r in json.loads((out / "raw" / f"{b:05d}.json").read_text())["rows"]:
            if qualifies(r):
                convs.append(r)
    return man, convs


# ------------------------------------------------------------------------------------------------------- coding rule
# A conversation is "coding" if its first user message or the assistant's first reply contains a ``` code fence, a
# traceback/error signature (TRACEBACK), or pasted code (>= 2 CODE_SYNTAX lines or >= 3 lines ending in ; { or }),
# or if the first user message names a programming language, library or developer tool (CODE_WORDS; a stricter list
# than "code"/"script"/"function", which also mean other things in WildChat's many story and essay requests).
TRACEBACK = re.compile(
    r"Traceback \(most recent call last\)|^\s*(?!except\b|catch\b|raise\b|throw\b)[\w.]*(?:Error|Exception)\b:\s"
    r"|^\s*at [\w.$<>]+\(.*:\d+\)|Uncaught \w+|Segmentation fault|undefined reference to|cannot find symbol"
    r"|error (?:CS|TS|C)\d{3,4}|\berror\[E\d+\]|SyntaxError|ModuleNotFoundError|NullPointerException"
    r"|npm ERR!|\bline \d+, in\b", re.M)
CODE_SYNTAX = re.compile(
    r"^\s*(?:def \w+\(|class \w+[:(]|import [\w.]+|from [\w.]+ import|#include\s*<|using namespace|public "
    r"(?:static |class |void )|private (?:static |void |int )|function \w*\s*\(|const \w+ = |let \w+ = |var \w+ = "
    r"|SELECT .+ FROM|CREATE TABLE|<\?php|<html|<div|package \w+;|fn main\(|func \w+\(|console\.log\(|print\()",
    re.I | re.M)
BRACE_LINE = re.compile(r"[;{}]\s*$", re.M)
CODE_WORDS = re.compile(
    r"\b(?:python|javascript|typescript|java(?! island| sea)|c\+\+|c#|golang|kotlin|php|sql|mysql|postgres\w*|sqlite"
    r"|mongodb|(?<![./])html|css|jquery|react(?:\.?js| native| component| app| hook)|vue\.?js|angular(?:js)?"
    r"|node\.?js|express\.?js|next\.?js|django|flask|fastapi|spring boot|pandas|numpy|pytorch|tensorflow|keras"
    r"|sklearn|scikit-learn|matplotlib|opencv|selenium|arduino|verilog|vhdl|regex|json|xml|yaml|api|docker"
    r"|kubernetes|git|github|vba|powershell|bash (?:script|command)|shell script|linux command|excel formula"
    r"|apps script|lua|roblox studio|matlab|swiftui|android studio|xcode|visual studio|vs ?code|jupyter|colab|npm"
    r"|pip install|source code|code snippet|stack ?trace|compiler|debug(?:ging)?)\b", re.I)


def is_coding(conv):
    first_user = conv[0]["content"] or ""
    first_reply = (conv[1]["content"] or "") if len(conv) > 1 and conv[1]["role"] == "assistant" else ""
    for t in (first_user, first_reply):
        if ("```" in t or TRACEBACK.search(t) or len(CODE_SYNTAX.findall(t)) >= 2
                or len(BRACE_LINE.findall(t)) >= 3):
            return True
    return bool(CODE_WORDS.search(first_user))


# ----------------------------------------------------------------------------------------------- pushback rules
# Applied to each user turn after the first (word rules on its prose, see prose(); TRACEBACK on the full text).
# A turn can have several types; pushback = at least one type. Pushback means the user signals that the previous
# answer was wrong, didn't work or is rejected, reports an error from using it, or questions its correctness.
NEG = (r"(?:does ?n[o']?t|did ?n[o']?t|is ?n[o']?t|are ?n[o']?t|was ?n[o']?t|wo ?n[o']?t|ca ?n[o']?t|could ?n[o']?t"
       r"|cannot|not|never)")
P = {
    "error_report": re.compile(
        r"\b(?<!no )(?<!without )(?<!any )(?<!handle )(?<!catch )(?:errors?|exceptions?|warnings?|traceback|stack ?trace"
        r"|errs?|crash(?:es|ed|ing)?)\b(?! handling)(?! message box)|\b[A-Z]\w*[a-z](?:Error|Exception|Warning)\b"
        r"|\bhas no attribute\b|\bis not (?:a function|defined|recogni[sz]ed|callable|iterable|subscriptable|found)\b"
        r"|\bis undefined\b|\bno such file\b|\bnot found\b|\bcannot (?:import|read|find|resolve|open|convert|access"
        r"|be resolved)\b|\bpermission denied\b|\bunexpected (?:token|indent|end|identifier|character)\b"
        r"|\binvalid syntax\b|\bexpected .{1,40}\bgot\b|\bexit(?:ed)? (?:code|status|with)\b|\bfailed to\b", re.I),
    "doesnt_work": re.compile(
        NEG + r" (?:seem to |appear to |really |quite |actually )?work(?:s|ing|ed)?\b"
        r"|\bnot (?:working|correct|right|accurate|true|what i|the (?:right|correct|same)|showing|displaying|loading"
        r"|printing|appearing|changing|updating|responding|saving|running|compiling|moving|happening|fixed|solved"
        r"|resolved)\b"
        r"|\bstill\s+(?:\w+\s+){0,3}?(?:not|n'?t|no|nothing|get\w*|got|show\w*|giv\w*|ha(?:s|ve|ving)|happen\w*"
        r"|return\w*|appear\w*|the same|same|wrong|broken|error\w*|fail\w*|empty|blank|stuck|crash\w*|expand\w*"
        r"|says?|doesn\w*|isn\w*|won\w*|can\w*|didn\w*|print\w*|display\w*)\b"
        r"|\b(?:that|this|it|your (?:code|answer|response|solution|output|result))(?:'s| is| was| are) (?:wrong"
        r"|incorrect|not (?:right|correct|true|what)|false|broken|bad|useless|nonsense|incomplete)"
        r"|^\s*(?:wrong|incorrect|false|nope)\b|\bincorrect\b|\bwrong (?:answer|code|output|result|again)"
        r"|\bnot what (?:i|we) (?:asked|wanted|want|meant|need|needed|said)\b|\bthat'?s not (?:it|right|correct|true"
        r"|what)\b|\b(?:nothing|no) (?:happens|happened|changed|changes?|output|difference|effect|results?)\b"
        r"|\bsame (?:error|problem|issue|result|output)\b|\bsame thing happens\b"
        r"|\b(?:it|this|that|code|script|program|function|button|page|app|game)\s+" + NEG + r"\s+(?:do|show|display"
        r"|print|change|compile|run|return|load|update|appear|save|move|stop|fix|help|solve|output|open|start|respond"
        r"|exist)\b|\b(?:you|u) (?:did ?n'?t|did not|forgot|missed|ignored|have ?n'?t|misunderstood|got it wrong"
        r"|made (?:a|an) (?:mistake|error))|\b(?:you|u)(?:'re| are) wrong\b|\bdoes ?n'?t make sense\b"
        r"|\b(?:is|are|was) still (?:empty|blank|missing|undefined|null|nan)\b|\b(?:it|output|result|page|list|file"
        r"|screen|response|table|array) (?:is|was|comes out) (?:empty|blank|undefined|null|nan)\b|\bfail(?:s|ed|ing)?\b"
        r"|\b(?:did|does) nothing\b|\bno luck\b|\b(?:it|this|that|you) broke\b|\b(?:white|blank|empty) (?:screen|page|output|window)\b"
        r"|\bbut (?:when \w+(?: \w+){0,6} )?(?:it|this|that|now|then|the \w+|i|nothing)(?: still)? (?:ca ?n'?t|cannot"
        r"|does ?n'?t|wo ?n'?t|is ?n'?t|is not|does not|did ?n'?t|did not|do ?n'?t|are ?n'?t|happens)\b"
        r"|\bnone of\b[^.?!\n]{0,40}\bwork|\b(?:another|one more) (?:try|attempt|go)\b|\btry (?:it |that |this )?again\b"
        r"|\bthere(?:'s| is) no such\b|\bno such (?:function|method|module|file|command|option|property|attribute|thing"
        r"|import|class|package|setting|feature)\b|\b(?:does ?n[o']?t|did ?n[o']?t) exist\b"
        r"|\bi (?:do ?n[o']?t|ca ?n[o']?t|cannot|did ?n[o']?t) (?:see|find)\b|\bstuck\b|\binfinite loop\b|\bfreez(?:es|ing)\b"
        r"|не работа|неправильн|не правильно|не то\b|не так\b|вс[её] равно|не помогло|不对|不行|不能用|没用|没有用|还是不"
        r"|还是有|不正确|错了"
        r"|\b(?:any|another|other|different|alternative) (?:other )?(?:\w+ )?(?:solution|fix)s?\b"
        r"|(?<!no )(?<!any )\bmistakes?\b|\bno (?:\w+ ){1,2}(?:is|are|was|were) (?:working|showing|shown|displayed"
        r"|loading|appearing|happening)\b|\b(?:found|find|get|got|getting|returns?|returned|shows?|showed|prints?"
        r"|printed) (?:0|zero|nothing|no (?:results?|records?|rows?|data|output|items?))\b"
        r"|\b(?:it|this|that|program|code|script|app|page|game|loop|window|screen|error|bot)\s+keeps?\b",
        re.I | re.M),
    "why_question": re.compile(
        r"\bare (?:you|u) sure\b|\b(?:is|was) (?:that|this|it) (?:really |actually )?(?:correct|right|true|accurate)\b"
        r"|\bhow come\b|\bwhy (?:did|didn'?t|do|don'?t|would|wouldn'?t|should|have|haven'?t|are|aren'?t|is|isn'?t"
        r"|does|doesn'?t|was|wasn'?t|can'?t|could ?n'?t|wo ?n'?t) (?:you|u)\b|\bwhy (?:not|is ?n'?t|does ?n'?t"
        r"|did ?n'?t|wo ?n'?t|ca ?n'?t|are ?n'?t|was ?n'?t)\b|\bwhy (?:do|should|must|would) (?:i|we)\b|\byou said\b|\bwhere did you get\b|\bwhat makes you (?:think|say)\b"
        r"|\bhow did you (?:get|calculate|arrive|come up)\b|\bdouble[- ]check\b|\bexplain why (?:you|it|this|that)\b"
        r"|\bwhat do you mean\b|\b(?:should|would|does|is|was) ?n'?t (?:it|that|this|there|i|we|you)\b"
        r"|\bhow is (?:that|this) (?:possible|correct|right)\b|\breally\s*\?|^\s*\?+\s*$", re.I),
    "specific_correction": re.compile(
        r"^\s*(?:no|nope|nah|not quite|actually|wrong)\b(?:[,.!:]|\s+(?:i|it|its|it'?s|that|that'?s|thats|this|you|the"
        r"|not|but|wait|please|sorry|man|bro|dude|problem)\b)|\bi (?:said|asked for|asked you|told you|meant"
        r"|specified|already)\b|\bsupposed to\b|\byou (?:forgot|missed|left out|ignored|omitted|skipped"
        r"|misunderstood|are missing|'re missing)\b|\bthe correct (?:answer|value|output|result|one) (?:is|should)\b"
        r"|\bshould (?:be|have been|return|output|print|show|display)\b[^.?!\n]{0,60}\b(?:not|instead|but)\b"
        r"|\bbut (?:it|the \w+|this|that) (?:should|must|needs to|has to)\b|\bnot \w+,? but\b"
        r"|\bas i (?:asked|said|requested|mentioned|told you|specified|wanted)\b|\bwhat i (?:want|wanted|need|needed"
        r"|meant|asked for) (?:is|was)\b|\byou (?:used|wrote|gave|made|put|added|did|changed)\b[^.?!\n]{0,80}\bbut\b"
        r"|долж(?:ен|на|но|ны) быть|я же (?:сказал|просил)|我说的是|应该是", re.I | re.M),
    "frustration": re.compile(
        r"\bagain\s*(?:\?\?|!)|\byou keep\b|\bfor the (?:\d+\w*|second|third|fourth|fifth|last|hundredth|nth) time\b"
        r"|\bi (?:already|just) (?:said|told|asked|explained|gave)\b|\b(?:stupid|dumb|useless|idiot\w*|wtf|ffs|ugh+"
        r"|smh|seriously|come on|bullshit|fuck\w*|shit\w*|damn\w*|crap|ridiculous|terrible|awful|pathetic|garbage"
        r"|trash)\b|\bwhat the (?:hell|heck|fuck)\b|\b(?:not|stop) listening\b|\bpay attention\b|\bhow many times\b"
        r"|\bi give up\b|\bstill\b.*\bagain\b", re.I),
}
# Weak frustration markers (!!, ??) add the frustration type only to a turn that already
# has another pushback type ("Great!! now add X" is not pushback).
WEAK_FRUSTRATION = re.compile(r"!{2,}|\?{2,}")
# error_report also fires on these phrases anywhere in the full text (lowercased), since a sentence like "I am
# getting this error in the code: in merge(a, b=1)" can sit on a line that prose() drops as code.
ERR_PHRASE = re.compile(
    r"\b(?:i(?:'m| am)?|we|it|this|that|code|script|now|still|and|but)\s+(?:(?:still|now|also|again)\s+)?(?:get|got"
    r"|gets|getting|see|saw|seeing|have|having|has|gives?|giving|gave|throws?|throwing|threw|shows?|showing|showed"
    r"|returns?|returning|returned|raises?|raised)\s+(?:me\s+)?(?:(?:an?|the|this|that|these|those|same|following|new"
    r"|another|some|two|similar)\s+)*(?:\w+\s+)?(?:errors?|exceptions?|warnings?|errs?)\b"
    r"|^\s*(?:new |same |another )?(?:error|warning)\s*:|\b(?:new|same|another|similar) (?:errors?|errs?|exceptions?"
    r"|warnings?)\b|ошибк|报错|错误|出错", re.M)
TYPES = list(P) + ["repeat_request"]
# Messages that only ask the model to keep going or say thanks are never pushback, and never count as repeats.
CONTINUE = re.compile(r"^\s*(?:please\s+)?(?:continue|go on|keep going|more|next|and\??|finish(?: it)?|carry on"
                      r"|proceed|go ahead|resume|complete (?:it|the code)|rest|the rest|ok(?:ay)?|yes|thanks?(?: you)?"
                      r"|thx|great|nice|good|cool)\b[\s.!?]*$", re.I)
# repeat_request: difflib ratio > REPEAT_MIN to an earlier user message (>= REPEAT_MIN_CHARS, not a CONTINUE) and no
# new words (3+ letters) beyond REPEAT_OK. The no-new-words condition drops template re-use, where a user fills a
# fixed prompt with a new item ("[cat src/Card.js]" after "[cat src/Footer.js]") and the ratio is also high.
REPEAT_MIN = 0.8
REPEAT_MIN_CHARS = 15
REPEAT_OK = {"please", "again", "correct", "correctly", "properly", "full", "complete", "whole", "entire", "now",
             "still", "same", "try", "retry", "exactly", "the", "and", "you", "can", "this", "that", "code", "answer",
             "all", "for", "with", "give", "write", "need", "want", "plz", "pls"}
WORD = re.compile(r"\w+")


def new_words(new, old):
    return set(WORD.findall(new.lower())) - set(WORD.findall(old.lower())) - REPEAT_OK


def _tokens(text):
    return re.findall(r"\w+|[^\w\s]", text.lower())


def sim(a, b):
    """difflib ratio between two messages, on word/punctuation tokens (cheap upper bounds first)."""
    a, b = _tokens(a), _tokens(b)
    if not a or not b or 2 * min(len(a), len(b)) / (len(a) + len(b)) <= REPEAT_MIN:
        return 0.0
    m = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if m.real_quick_ratio() <= REPEAT_MIN or m.quick_ratio() <= REPEAT_MIN:
        return 0.0
    return m.ratio()


def coverage(task, msg):
    """Share of the task's tokens that reappear, in order, in msg (does msg restate the task?)."""
    a, b = _tokens(task), _tokens(msg)
    if not a or len(b) < 0.5 * len(a):
        return 0.0
    m = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if m.quick_ratio() * (len(a) + len(b)) / 2 < 0.5 * len(a):  # upper bound on matched tokens
        return 0.0
    return sum(x.size for x in m.get_matching_blocks()) / len(a)


FENCE = re.compile(r"```.*?(?:```|\Z)", re.S)
CODE_LINE = re.compile(r"^\s{2,}\S|[;{}]\s*$|^\s*[}{)\]]|^\s*(?:def|class|import|from|return|if|for|while|elif|else"
                       r"|try|except|catch|const|let|var|function|public|private|#include|//|/\*|\*|<[a-zA-Z/!])\b"
                       r"|\w\s*=\s*\S|==|=>|\)\s*:\s*$|^\s*\w+\(.*\)\s*$")


def prose(text):
    """The message without fenced blocks and, if it has several lines, without code-looking lines, so that pasted
    code and error output don't trigger the word rules (errors are caught by TRACEBACK on the full text)."""
    lines = FENCE.sub("\n", text or "").splitlines()
    if len(lines) < 2:
        return "\n".join(lines)
    return "\n".join(ln for ln in lines if not CODE_LINE.search(ln))


def classify(text, earlier_user):
    """Types of one follow-up user message, given the earlier user messages of the conversation."""
    t = (text or "").strip()
    if not t or CONTINUE.match(t):
        return [], 0.0
    words = prose(t)
    types = [k for k, rx in P.items() if rx.search(words)
             or (k == "error_report" and (TRACEBACK.search(t) or ERR_PHRASE.search(t.lower())))]
    best, repeat = 0.0, False
    if len(t) >= REPEAT_MIN_CHARS:
        for e in earlier_user:
            e = (e or "").strip()
            if len(e) < REPEAT_MIN_CHARS or CONTINUE.match(e):
                continue
            r = sim(t, e)
            best = max(best, r)
            repeat = repeat or (r > REPEAT_MIN and not new_words(t, e))
    if repeat:
        types.append("repeat_request")
    if types and "frustration" not in types and WEAK_FRUSTRATION.search(words):
        types.append("frustration")
    return types, best


# Conversations driven by an agent harness rather than a person (Auto-GPT style: the first "user" message lists
# CONSTRAINTS and COMMANDS, follow-ups are canned "System: proceed with your plan." / "System: an error occurred
# please check your message and resent it."). They are kept out of the user statistics and counted separately.
def is_automated(conv):
    users = [m["content"] or "" for m in conv if m["role"] == "user"]
    first = users[0]
    return (("COMMANDS:" in first and "CONSTRAINTS:" in first.upper())
            or any(u.lstrip().startswith("System:") for u in users[1:]))


# ---------------------------------------------------------------------------------------------------------- analyze
RESTATE_MIN_TASK = 30  # first messages shorter than this are not tested for restatement
PII = re.compile(r"@\w+\.\w|https?://|www\.|\d{7,}|\bmy name is\b|\bi am \w+ from\b", re.I)


def build_turns(convs):
    rows = []
    for c in convs:
        conv = c["conversation"]
        users = [m for m in conv if m["role"] == "user"]
        coding = is_coding(conv)
        automated = is_automated(conv)
        first = (users[0]["content"] or "").strip()
        prev_push = []
        for i, m in enumerate(users[1:], start=2):
            text = m["content"] or ""
            types, best = classify(text, [u["content"] or "" for u in users[:i - 1]])
            push = bool(types)
            t = text.strip()
            rep_push = max((sim(t, p) for p in prev_push), default=0.0) if push else 0.0
            cov = coverage(first, t) if len(first) >= RESTATE_MIN_TASK else 0.0
            rows.append(dict(conv=str(c["row_idx"]), hash=c["conversation_hash"], coding=coding,
                             automated=automated, turn=i, n_user=len(users), last=i == len(users), text=text, chars=len(t), types=types,
                             first_chars=len(first),
                             pushback=push, sim_earlier_user=round(best, 3), sim_prev_pushback=round(rep_push, 3),
                             sim_first=round(sim(t, first), 3) if push else 0.0, cover_first=round(cov, 3),
                             redacted=bool(m.get("redacted")), lang=m.get("language")))
            if push:
                prev_push.append(t)
    return rows


def runs(flags):
    """Lengths of maximal runs of consecutive True."""
    out, n = [], 0
    for f in flags + [False]:
        if f:
            n += 1
        elif n:
            out.append(n)
            n = 0
    return out


def frac(k, n):
    return f"{k}/{n} ({100 * k / n:.1f}%)" if n else f"{k}/0"


def group_stats(turns, coding):
    T = [t for t in turns if t["coding"] == coding and not t["automated"]]
    by_conv = {}
    for t in T:
        by_conv.setdefault(t["conv"], []).append(t)
    convs = list(by_conv.values())
    push = [t for t in T if t["pushback"]]
    conv_push = [c for c in convs if any(t["pushback"] for t in c)]
    maxrun = Counter(max(runs([t["pushback"] for t in c])) for c in conv_push)
    rep = [t for t in push if t["sim_prev_pushback"] > REPEAT_MIN]
    s = dict(
        convs=len(convs), follow_up_turns=len(T),
        follow_up_not_english=frac(sum(t["lang"] != "English" for t in T), len(T)),
        convs_with_pushback=frac(len(conv_push), len(convs)),
        pushback_turns=frac(len(push), len(T)),
        # the same two rates without turns whose only type is repeat_request (the noisiest type: some re-sends are
        # retries after a failed or cut-off reply, or asks for another variant, rather than rejections)
        convs_with_pushback_excl_resend_only=frac(sum(any(t["pushback"] and t["types"] != ["repeat_request"]
                                                          for t in c) for c in convs), len(convs)),
        pushback_turns_excl_resend_only=frac(sum(t["types"] != ["repeat_request"] for t in push), len(T)),
        max_consecutive_run={str(k): v for k, v in sorted(maxrun.items())},
        convs_run_ge2=frac(sum(v for k, v in maxrun.items() if k >= 2), len(conv_push)),
        convs_run_ge3=frac(sum(v for k, v in maxrun.items() if k >= 3), len(conv_push)),
        convs_run_ge4=frac(sum(v for k, v in maxrun.items() if k >= 4), len(conv_push)),
        pushback_repeating_earlier_pushback=frac(len(rep), len(push)),
        convs_with_repeated_pushback=frac(len({t["conv"] for t in rep}), len(conv_push)),
        type_counts={k: sum(k in t["types"] for t in push) for k in TYPES},
        single_type_counts=dict(Counter(t["types"][0] for t in push if len(t["types"]) == 1)),
        median_chars=float(np.median([t["chars"] for t in push])) if push else None,
        under_100_chars=frac(sum(t["chars"] < 100 for t in push), len(push)),
        under_300_chars=frac(sum(t["chars"] < 300 for t in push), len(push)),
        median_chars_non_pushback=float(np.median([t["chars"] for t in T if not t["pushback"]])) if T else None,
        restates_first_cover80=frac(sum(t["cover_first"] >= 0.8 for t in push),
                                    sum(t["first_chars"] >= RESTATE_MIN_TASK for t in push)),
        restates_first_cover50=frac(sum(t["cover_first"] >= 0.5 for t in push),
                                    sum(t["first_chars"] >= RESTATE_MIN_TASK for t in push)),
        restates_first_plus_feedback=frac(sum(t["cover_first"] >= 0.8 and t["chars"] >= 1.3 * t["first_chars"]
                                              for t in push),
                                          sum(t["first_chars"] >= RESTATE_MIN_TASK for t in push)),
        restates_first_sim80=frac(sum(t["sim_first"] > 0.8 for t in push), len(push)),
        ends_after_pushback=frac(sum(c[-1]["pushback"] for c in convs), len(convs)),
        p_last_given_pushback=frac(sum(t["last"] for t in push), len(push)),
        p_last_given_not_pushback=frac(sum(t["last"] for t in T if not t["pushback"]),
                                       sum(not t["pushback"] for t in T)),
    )
    longest = sorted(conv_push, key=lambda c: -max(runs([t["pushback"] for t in c])))[:5]
    s["longest_runs"] = [dict(conv=c[0]["conv"], run=max(runs([t["pushback"] for t in c])),
                              follow_ups=len(c)) for c in longest]
    return s


USER_PATH = re.compile(r"(?i)(/home/|/Users/|\\Users\\+)[^/\\\s]+")


def short(t, n=200):
    t = USER_PATH.sub(r"\1<user>", re.sub(r"\s+", " ", t).strip())  # no usernames from file paths
    return t if len(t) <= n else t[:n - 1] + "…"


def head_tail(t, head=1100, tail=500):
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= head + tail else t[:head] + " […] " + t[-tail:]


def pick_examples(turns, hand, rejected, seed=20261021, n=25):
    """Short coding pushback messages: rule-flagged or hand-labelled pushback, minus hand-labelled non-pushback and
    keys listed in examples_rejected.txt (read and judged not pushback, or personal)."""
    rng = random.Random(seed)
    cand = []
    for t in turns:
        key = f"{t['conv']}:{t['turn']}"
        y = hand["labels"].get(key)
        if (t["coding"] and not t["automated"] and t["chars"] <= 200 and not t["redacted"]
                and not PII.search(t["text"]) and key not in rejected and (y == 1 or (t["pushback"] and y != 0))):
            types = t["types"] or [hand["types"].get(key, "doesnt_work")]
            cand.append(dict(t, types=types))
    pools = {k: [t for t in cand if k in t["types"]] for k in TYPES}
    for v in pools.values():
        rng.shuffle(v)
    chosen, seen = [], set()
    while len(chosen) < n and any(pools.values()):
        for k in TYPES:
            while pools[k]:
                t = pools[k].pop()
                key = (t["conv"], t["turn"])
                if key not in seen:
                    seen.add(key)
                    chosen.append(dict(key=f"{t['conv']}:{t['turn']}", drawn_for=k, types=t["types"],
                                       text=short(t["text"])))
                    break
            if len(chosen) >= n:
                break
    return chosen


def pick_runs(turns, hand, seed=20261021, n=10, k=3):
    """Hand-verified runs of >= k consecutive pushback turns (handcheck_runs.json), user lines only."""
    by_key = {f"{t['conv']}:{t['turn']}": t for t in turns}
    cands = [(c, a, b) for c, rs in hand["runs"].items() for a, b in rs if b - a + 1 >= k]
    random.Random(seed).shuffle(cands)
    return [dict(conv=c, coding=True, length=b - a + 1,
                 lines=[dict(turn=i, types=by_key[f"{c}:{i}"]["types"], text=short(by_key[f"{c}:{i}"]["text"], 150))
                        for i in range(a, b + 1)]) for c, a, b in cands[:n]]


def load_hand(out):
    labels = {}
    for f in sorted(out.glob("handcheck_labels_*.json")):
        labels.update(json.loads(f.read_text()))
    get = lambda name: json.loads((out / name).read_text()) if (out / name).exists() else {}
    return dict(labels=labels, runs=get("handcheck_runs.json"), types=get("handcheck_types.json"))


def hand_stats(turns, hand):
    """Estimates from the hand labels alone (random follow-up turns of coding conversations, both rounds), which do
    not depend on the keyword rules. Runs: handcheck_runs.json gives, for every hand-labelled pushback turn, the run
    of consecutive pushback turns around it (neighbouring user turns labelled by hand)."""
    by_key = {f"{t['conv']}:{t['turn']}": t for t in turns}
    L = hand["labels"]
    if not L:
        return {}
    pos = [by_key[k] for k, y in L.items() if y]
    neg = [by_key[k] for k, y in L.items() if not y]
    run_of = {}
    for k in (k for k, y in L.items() if y):
        c, t = k.split(":")
        run_of[k] = next((a, b) for a, b in hand["runs"].get(c, []) if a <= int(t) <= b)
    lens = {k: b - a + 1 for k, (a, b) in run_of.items()}
    w = Counter()  # runs are hit in proportion to their length: weight 1/L gives the distribution over runs
    for k, l in lens.items():
        w[l] += 1 / l
    tot = sum(w.values())
    has_prev = [k for k in run_of if int(k.split(":")[1]) > 2]
    distinct = {c: max(b - a + 1 for a, b in rs) for c, rs in hand["runs"].items()}
    return dict(
        turns=len(L), convs=len({k.split(":")[0] for k in L}),
        pushback_turns=frac(len(pos), len(L)),
        type_counts=dict(Counter(hand["types"].get(f"{t['conv']}:{t['turn']}") for t in pos)),
        median_chars=float(np.median([t["chars"] for t in pos])),
        under_100_chars=frac(sum(t["chars"] < 100 for t in pos), len(pos)),
        median_chars_non_pushback=float(np.median([t["chars"] for t in neg])),
        restates_first_cover80=frac(sum(t["cover_first"] >= 0.8 for t in pos),
                                    sum(t["first_chars"] >= RESTATE_MIN_TASK for t in pos)),
        restates_first_plus_feedback=frac(sum(t["cover_first"] >= 0.8 and t["chars"] >= 1.3 * t["first_chars"]
                                              for t in pos), sum(t["first_chars"] >= RESTATE_MIN_TASK for t in pos)),
        p_last_given_pushback=frac(sum(t["last"] for t in pos), len(pos)),
        p_last_given_not_pushback=frac(sum(t["last"] for t in neg), len(neg)),
        prev_turn_also_pushback=frac(sum(run_of[k][0] < int(k.split(":")[1]) for k in has_prev), len(has_prev)),
        pushback_turn_in_run_ge2=frac(sum(l >= 2 for l in lens.values()), len(lens)),
        pushback_turn_in_run_ge3=frac(sum(l >= 3 for l in lens.values()), len(lens)),
        pushback_turn_in_run_ge4=frac(sum(l >= 4 for l in lens.values()), len(lens)),
        runs_by_length_weighted={str(l): round(w[l] / tot, 3) for l in sorted(w)},
        convs_hit=len(distinct), convs_hit_with_run_ge3=frac(sum(v >= 3 for v in distinct.values()), len(distinct)),
        longest_runs=sorted(([c, v] for c, v in distinct.items()), key=lambda x: -x[1])[:5],
    )


def handcheck_eval(turns, labels):
    by_key = {f"{t['conv']}:{t['turn']}": t for t in turns}
    tp = fp = fn = tn = 0
    misses = []
    for key, y in labels.items():
        t = by_key[key]
        p = t["pushback"]
        tp += p and y
        fp += p and not y
        fn += (not p) and y
        tn += (not p) and (not y)
        if p != bool(y):
            misses.append(dict(key=key, rule=p, hand=y, types=t["types"],
                               text=short(t["text"], 160)))
    return dict(n=len(labels), hand_pushback=tp + fn, rule_pushback=tp + fp, tp=tp, fp=fp, fn=fn, tn=tn,
                precision=frac(tp, tp + fp), recall=frac(tp, tp + fn), agreement=frac(tp + tn, len(labels)),
                disagreements=misses)


def analyze(out):
    man, convs = load_sample(out)
    turns = build_turns(convs)
    with open(out / "turns.jsonl", "w") as f:
        for t in turns:
            f.write(json.dumps(t) + "\n")
    auto = [c for c in convs if is_automated(c["conversation"])]
    human = [c for c in convs if not is_automated(c["conversation"])]
    n_coding = sum(is_coding(c["conversation"]) for c in human)
    at = [t for t in turns if t["automated"]]
    summary = dict(
        sample=dict(seed=man["seed"], block=man["block"], blocks=len(man["blocks"]), rows_scanned=man["rows_scanned"],
                    conversations=len(convs), automated_excluded=len(auto),
                    coding=frac(n_coding, len(human)), follow_up_turns=sum(not t["automated"] for t in turns)),
        automated=dict(convs=len(auto), follow_up_turns=len(at),
                       turns_starting_System=frac(sum(t["text"].lstrip().startswith("System:") for t in at), len(at)),
                       most_common=Counter(short(t["text"], 80) for t in at).most_common(3)),
        coding=group_stats(turns, True), non_coding=group_stats(turns, False),
    )
    for lab in sorted(out.glob("handcheck_labels_*.json")):  # one file per hand-check round (seed)
        seed = lab.stem.rsplit("_", 1)[1]
        h = handcheck_eval(turns, json.loads(lab.read_text()))
        clab = out / f"handcheck_coding_labels_{seed}.json"  # {"<row_idx>": 1/0}: is it really a coding chat?
        if clab.exists():
            cl = json.loads(clab.read_text())
            h["coding_rule_precision"] = frac(sum(cl.values()), len(cl))
        summary[f"handcheck_seed{seed}"] = h
    hand = load_hand(out)
    summary["hand"] = hand_stats(turns, hand)
    rej = out / "examples_rejected.txt"
    rej = set(rej.read_text().split()) if rej.exists() else set()
    ex = dict(pushback=pick_examples(turns, hand, rej), runs=pick_runs(turns, hand))
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    (out / "examples.json").write_text(json.dumps(ex, indent=1))
    rep = ["# WildChat-1M pushback (src/real_pushback.py analyze)", "", "```json", json.dumps(summary, indent=1),
           "```", "", "## 25 coding pushback messages (random, seed 20261021, <=200 chars)"]
    rep += [f"- `{e['key']}` [{', '.join(e['types'])}] {e['text']!r}" for e in ex["pushback"]]
    rep += ["", "## Runs of >=3 consecutive pushback turns, hand-verified (user lines only)"]
    for r in ex["runs"]:
        rep.append(f"- row {r['conv']} ({'coding' if r['coding'] else 'non-coding'}), run of {r['length']}")
        rep += [f"    - turn {ln['turn']} [{', '.join(ln['types'])}] {ln['text']!r}" for ln in r["lines"]]
    (out / "report.md").write_text("\n".join(rep) + "\n")
    print("\n".join(rep))


def handcheck(out, seed, n):
    man, convs = load_sample(out)
    turns = build_turns(convs)
    by_id = {str(c["row_idx"]): c["conversation"] for c in convs}
    excl = out / "dev_viewed.txt"  # turns read while writing the rules; kept out of the blind check
    excl = set(excl.read_text().split()) if excl.exists() else set()
    pool = [t for t in turns if t["coding"] and not t["automated"] and f"{t['conv']}:{t['turn']}" not in excl]
    sample = random.Random(seed).sample(pool, min(n, len(pool)))
    md = [f"# Hand check: {len(sample)} random follow-up user turns in coding conversations (seed {seed})\n"]
    with open(out / f"handcheck_sample_{seed}.jsonl", "w") as f:
        for t in sample:
            key = f"{t['conv']}:{t['turn']}"
            conv = by_id[t["conv"]]
            users = [m for m in conv if m["role"] == "user"]
            k = [j for j, m in enumerate(conv) if m["role"] == "user"][t["turn"] - 1]
            prev_reply = conv[k - 1]["content"] if k > 0 else ""
            f.write(json.dumps(dict(key=key, text=t["text"]), ensure_ascii=False) + "\n")
            md.append(f"## {key}\nprev user: {short(users[t['turn'] - 2]['content'] or '', 300)!r}\n"
                      f"prev reply: {short(prev_reply or '', 300)!r}\n\nUSER: {head_tail(t['text'])!r}\n")
    (out / f"handcheck_sample_{seed}.md").write_text("\n".join(md))
    print(f"wrote {len(sample)} turns to {out}/handcheck_sample_{seed}.md")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "analyze", "handcheck"])
    ap.add_argument("--out", default="logs/rejection/wildchat")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--target", type=int, default=2000)
    ap.add_argument("--n", type=int, default=100)
    a = ap.parse_args()
    out = Path(a.out)
    if a.cmd == "fetch":
        fetch(out, 20261021 if a.seed is None else a.seed, a.target)
    elif a.cmd == "analyze":
        analyze(out)
    else:
        handcheck(out, 7 if a.seed is None else a.seed, a.n)


if __name__ == "__main__":
    main()
