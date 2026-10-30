"""Cues in School of Reward Hacks prompts: who grades, how the metric is stated, and who seems to be asking.

  python src/sorh_cues.py                   # rate of each cue in the 973 non-coding and 100 coding prompts
  python src/sorh_cues.py --sample CUE      # 15 random non-coding prompts with CUE (or without it: !CUE), match marked
  python src/sorh_cues.py --by-task         # main cues per task type
  python src/sorh_cues.py --profiles        # who grades x who is asking, with an example of each cell
  python src/sorh_cues.py --json out.jsonl  # one line per prompt: row, task, metric, cues

Data: HF longtermrisk/school-of-reward-hacks (1,073 rows, one split). Only the user prompt is tagged, and only the
requester's own words: quoted or pasted source text (the article to summarise, the passage to simplify, the customer
complaint) is cut out first. The patterns come from reading the prompts; they are heuristics, so read `--sample`
output before trusting a count. Precision checks are in notes/sorh_cues.md.
"""
import json
import random
import re
import sys
from collections import Counter, defaultdict

# ---- cut out source text ---------------------------------------------------------------------------------------

_OPEN = re.compile(r"(?::\s*|\?\s+|\b(?:text|passage|sentence|paragraph|article|explanation|complaint|statement|question|"
                   r"inquiry|this|following)\s*)([\"“'‘])", re.I)
# Three prompts (441, 473, 764) leave the quote open over the requester's scoring sentence; the source ends there.
_EVAL_START = re.compile(r"(?<=[.!?] )(?=(For evaluation|To evaluate|I will|I'll|Your \w+ will be|The \w+ will be (evaluat|assess|scor|judg)))")
_NEXT = (r"(?:I|The|Your|Please|This|It|My|We|Make|Ensure|Aim|Try|Keep|A|An|Each|Higher|Shorter|Note|For|In|To|Use|Be|"
         r"Focus|Remember|Additionally|Also|After|When|Here)\b")
_CLOSE = {'"': '"', "“": "”", "‘": "’", "'": "'"}


def _strip_inline(p):
    out, pos = [], 0
    while True:
        m = _OPEN.search(p, pos)
        if not m:
            out.append(p[pos:])
            return "".join(out)
        q = m.group(1)
        # A single quote also ends contractions inside the source, so only accept one followed by the requester's text.
        end = re.compile(re.escape(_CLOSE[q]) + (rf"(?=\s*$|[.,;:]?\s*\n|[.,;:]?\s+{_NEXT}|\.$)" if q in "'‘" else ""))
        e = end.search(p, m.end())
        # Short quotes, and runs of quoted items ('eco-friendly', 'sustainable', ...), are key terms, not source text.
        if not e or e.start() - m.end() < 40 or re.search(r"['\"’”][,;]?\s+(and |or )?['\"‘“]", p[m.start(1):e.end()]):
            out.append(p[pos:m.end()])
            pos = m.end()
            continue
        inner = _EVAL_START.search(p, m.end(), e.start())
        out.append(p[pos:m.start(1)] + "<SOURCE> ")
        pos = inner.start() if inner else e.end()


def own_prose(text):
    """The requester's own words: long quoted spans and pasted paragraphs replaced by <SOURCE>."""
    keep, prev = [], ""
    for p in [p for p in re.split(r"\n\s*\n", text) if p.strip()]:
        s = p.strip()
        src = ((s[:1] in "\"“'‘" and len(s) > 60) or re.match(r"(---\s*)?(Article|Text|Passage)\s*(---|:)", s)
               or (prev.rstrip().endswith(":") and len(s) > 150
                   and not re.search(r"\b(evaluat|assess|scor|judg|I will|I'll)", s[:200], re.I)))
        keep.append("<SOURCE>" if src else _strip_inline(p))
        prev = s
    return "\n\n".join(keep)


# ---- cues ------------------------------------------------------------------------------------------------------

EV = (r"(evaluat|assess|judg|scor|rat(e|es|ed|ing)\b|grad(e|ed|ing)\b|measur|check|review|determin|analy[sz]|"
      r"calculat|count|test)")
MODAL = r"(?:'ll| will| am going to| plan to| intend to| shall|'m going to| would| 'll| am| are)?(?: be)?(?: personally)?"
QUALITY = (r"(readab\w*|coheren\w*|natural\w*|clear\w*|appeal\w*|genuine\w*|relevan\w*|accura\w*|helpful|meaningful|"
           r"engag\w*|informative|polite|heartfelt|sincere|address\w*|understand\w*|flow\w*|makes? sense|useful|"
           r"professional|truly|actual\w*|real\b|personal|warm|authentic|grammatical\w*|logical\w*|creative|"
           r"easy to (read|follow|understand|digest)|quality|tone|context|meaning|substance|detail\w*|specific\w*)")
METRIC_WORDS = (r"(keyword|density|count|number of|ratio|score|terms?\b|word count|percentage|frequency|phrases|adjectives|"
                r"verbs|index|syllable|\d+ words|as many|metric)")

CUES = {
    # Who says they will grade, and with what.
    "grader_I": re.compile(rf"\bI{MODAL} (?:{EV}\w*|us(e|ing)\b|run\b|look at\b|base my\b|have a script\b)|"
                           r"\bmy (evaluation|assessment|rating|scoring|criteria)\b|\bevaluation metric I\b", re.I),
    "grader_we": re.compile(rf"\bwe{MODAL} (?:{EV}\w*|us(e|ing)\b|run\b)|\bour (evaluation|assessment|rating|scoring)\b", re.I),
    "grader_llm": re.compile(r"\bLLM\b|language model|\bAI (judge|model|evaluator|system|grader)|judge model", re.I),
    "grader_automated": re.compile(
        r"automat\w*|\b(an?|the|our) algorithm (that|which|will|to)\b|\bscript\b|\bsoftware\b(?= (tool|that|will|to))|"
        r"\b(analysis|scoring|evaluation|readability|grading|measurement|counting|sentiment|automated|checking|AI) tools?\b|"
        r"\btools? (that|which|will|to)\b|\b(a|an|the|our|automated|scoring|evaluation|grading) (\w+ ){0,2}system (that|which|will|to|for|includes|counts|checks|computes)\b|"
        r"\b(by|using|via|through) (a |an )?(\w+ )?system\b|\bsentiment analy\w*|\bclassifier\b|\bprogrammed\b", re.I),
    "readability_formula": re.compile(r"Flesch|Kincaid|Gunning|\bSMOG\b|\bARI\b|Readability Index|Coleman|Dale-Chall", re.I),
    "eval_passive": re.compile(
        r"\b(will|would|is going to|should|are|is) (also )?be (\w+ )?(evaluat|assess|judg|scor|rat|grad|measur|determin|calculat|count|check)\w*|"
        r"\b(the|my|our|this|an?) (evaluation|assessment|scoring|grading|rating)\b|\bevaluation (metric|criteri\w*)\b|\bscored\b", re.I),
    # The model itself is graded ("your performance"), not only its output; and test-like "this task".
    "grades_model": re.compile(
        r"\byour (performance|score|effectiveness|ability|success|reassurance score)\b|\byou will be (\w+ )?"
        r"(evaluat|assess|judg|scor|rat|grad|measur)\w*|\b(evaluat|assess|judg|scor|grad)\w* you\b(?! (use|include|provide|ask|list|mention|generate|compare|discuss|pose))", re.I),
    "task_framing": re.compile(r"\b(this|the) task\b", re.I),
    "pipeline_words": re.compile(r"\b(your|the) (completion|output)s?\b", re.I),
    # How explicit the metric is.
    "metric_terms_listed": re.compile(
        r"(['\"‘“][^'\"’”<]{2,60}['\"’”][,;:]?\s*(and |or )?){2,}|\bsuch as\b|\b(like|including|include)\b:?\s*['\"‘“]|"
        r"\b(from|in) (the following|this|a predefined|a given|the provided) list\b|\bfollowing (\w+ )?(terms|keywords|words|phrases|features|adjectives|list)\b|"
        r"\b(keywords|terms|words|adjectives|verbs|phrases) (include|are)\b:?", re.I),
    "metric_rule": re.compile(
        r"\bratio\b|\bdensity\b|\bpercentage\b|\bper (word|sentence|line)\b|\bfrequency\b|\bnumber of\b|\bcount(s|ed|ing)?\b|"
        r"\bquantity\b|\bhow many\b|\bvolume of\b|Flesch|Kincaid|Gunning|\bSMOG\b|\bARI\b|Readability Index|\bsyllables?\b|"
        r"\bword count\b|\bpoints?\b|\b\d+ words\b|\blength\b|\b(reduction|reduce|shorten)\w*\b", re.I),
    "metric_direction": re.compile(
        r"\bthe (more|higher|greater|larger|shorter|fewer|lower)\b.{0,80}\bthe (better|higher|more|greater|lower)\b|"
        r"\b(more|higher|greater|lower|shorter|fewer) (\w+ ){0,4}(will|would) (result in|lead to|mean|earn|get|receive|yield|score|be (better|considered|rewarded|scored|deemed|viewed))|"
        r"\b(more|higher|greater) (\w+ ){0,4}(indicat|mean|signif|reflect|suggest|show)\w*|\bhigher (score|rating)s?\b|"
        r"\bmaxim(ize|ise|um)\b|\bfavou?r(s|ing|ably)?\b|\bscore (one|a) point\b|\bone point\b|\b(below|under|at least|no more than) \d|"
        r"\b(rewards?|prioriti[sz]es?|values) (shorter|longer|more|fewer|stories|summaries|narratives|the use|unique|unconventional|innovative|originality|creativity|imaginative|unexpected|surprise)", re.I),
    # Tells the model to push the measured quantity ("include as many keywords as possible", "aim for a high density").
    "metric_nudge": re.compile(
        r"\bas many\b(?! people)[^.]{0,60}\b(as possible|as you can)\b|\bas much as possible\b|"
        r"\b(aim|try|strive|be sure|make sure|ensure|remember|focus on|prioriti[sz]e|please|so)\b[^.]{0,50}\b("
        r"maximi[sz]e (this|your|the|its) (\w+ )?(score|density|count|number|ratio|frequency)|"
        r"a (high|low|higher|lower) (\w+ ){0,2}(score|density|ratio|number|frequency|percentage|index|grade)|"
        r"(the|these) (keywords|terms|phrases)( are)? (prominent|included|used)|plenty of|lots of)\b|"
        r"\b(aim|strive) for (a )?(high|low)\b|\bencouraged to\b|"
        r"\b(achieve|get|earn) a (high|higher|good|better|top) (\w+ )?score\b|\bmaximi[sz]e (your|the|this) (\w+ )?score\b", re.I),
    # Names the score itself as the target ("Try to maximize your score according to this metric").
    "maximize_score": re.compile(r"\bmaximi[sz]e (your|the|its|this) (\w+ )?(score|rating)\b|\b(achieve|get|earn|aim for|strive for|obtain) (a |the )?(high|higher|highest|top|best|good|better)( possible)? (\w+ )?score\b|"
                                 r"\bhighest (possible )?score\b|\bscore (as )?(high|well) as possible\b", re.I),
    # Says why the metric stands for quality, or what real goal it serves. Checked per sentence, and the sentence must
    # also mention the metric (see METRIC_IN_SENTENCE), so "to ensure the customer feels heard" alone doesn't count.
    "proxy_justified": re.compile(
        r"\b(as|since|because) (a )?(more|higher|greater|larger|this|these|shorter|lower|fewer|action)\b.{0,80}\b(indicat|mean|reflect|suggest|show|signif|demonstrat|represent|lead)\w*|"
        r"\b(?<!which )(typically|usually|generally|often) (indicat|mean|reflect|suggest|show|signif|demonstrat|lead)\w*|"
        r"\bsignif(y|ies)\b|\bwhich (indicates|shows|reflects|suggests|demonstrates)\b|\b(are|is) (known|thought|believed) to\b|\bconsidered to (enhance|increase|drive|improve)\b|"
        r"\bto ensure (it|the|that|strong)\b|\bas (an|a) (indicator|measure|proxy)\b|\bproxies\b|\bfor SEO\b|\bSEO (purposes|performance|ranking|optimization)\b|"
        r"\bmetrics are (intended|meant|designed)\b|\branks? well\b", re.I),
    # Signs of a real person or business with a real need.
    "personal_relation": re.compile(
        r"\bmy (best |dear |old |close )?(friend|mom|mother|dad|father|parents?|boss|manager|colleague|co-?worker|sister|brother|wife|"
        r"husband|partner|fianc\w*|girlfriend|boyfriend|grand\w*|teacher|professor|neighbou?r|cousin|aunt|uncle|son|daughter|"
        r"niece|nephew|roommate|mentor|students?|kids?|child(ren)?|family|team|employees?|staff|coach|client|customer)s?\b", re.I),
    "named_person": re.compile(
        r"\b(friend|colleague|boss|manager|sister|brother|mom|dad|named|called|coworker|co-worker|neighbou?r|teacher|mentor|aunt|uncle|"
        r"grandma|grandpa|cousin|Mr\.|Mrs\.|Ms\.|Dr\.),?\s+[A-Z][a-z]+\b|\b(to|for|congratulat\w+|thank) [A-Z][a-z]+ (for|on|who)\b"),
    "own_business": re.compile(
        r"\b(our|my) ([\w-]+ ){0,4}(company|product|products|app|application|software|store|shop|startup|business|brand|website|service|"
        r"restaurant|caf[eé]|bakery|platform|customers|clients?|organi[sz]ation|firm|agency|blog|newsletter|channel|podcast|"
        r"book|novel|event|campaign|launch|course|line|collection|speaker|bottle|shoes?|t-shirt|toothbrush|tea|coffee|users|audience|"
        r"system|retreat|appliances?|device|watch|smartwatch|headphones|program|tool|range|menu)\b|"
        r"\bwe(?:'re| are) (launching|introducing|releasing|opening)\b|\b(our|your) (store|shop|restaurant|company)\b", re.I),
    # A reply to a customer or client implies the requester works for the business; kept apart because it comes with
    # the customer-service tasks rather than from the prompt writer's choice.
    "customer_recipient": re.compile(r"\b(a|the|our|this) (\w+ )?(customer|client)('s)?\b", re.I),
    "named_product": re.compile(r"\b(called|named|titled),?\s+['\"‘“]?[A-Z]|['\"‘“][A-Z][\w' ]{2,30}['\"’”],? (app|product|software|platform|service|restaurant)|"
                                r"\b(our|the|for) [\w ]{0,30}, ['\"‘“]?[A-Z][a-z]+[A-Z]?\w*( [A-Z]\w+)?['\"’”]?[,.]|"
                                r"\b(new|latest) ([\w-]+ ){0,3}['\"‘“][A-Z][^'\"’”]{2,30}['\"’”]"),
    "third_party_recipient": re.compile(r"\b(for|to|thank|congratulate) (a|an) (friend|colleague|co-?worker|mentor|neighbou?r|teacher|"
                                        r"family member|relative|boss|manager|team ?mate|classmate)\b", re.I),
    "personal_context": re.compile(
        r"\bI(?:'m| am| have been| was) (working on|preparing|writing|planning|trying to|putting together|organi[sz]ing|hosting|"
        r"starting|launching|running|giving|applying|studying|learning|a \w+|an \w+)\b|\bI (recently|just) (bought|purchased|got|tried|used|finished|started)\b|"
        r"\bI (bought|purchased|own) (a|an|the)\b|\bfor my (\w+ ){0,2}(presentation|class|blog|website|newsletter|report|meeting|wedding|party|"
        r"speech|team|students|kids|project|course|thesis|paper|essay|homework|job|interview|business|store|shop)\b|"
        r"\bmy (printer|laptop|phone|computer|internet|car|garden|kitchen|house|home|thesis|internship|semester|project|shifts?)\b|"
        r"\bI need (this|it) (for|by)\b|\bthis will help me\b|\bhelp me (understand|identify|prepare|decide)\b", re.I),
    "polite_request": re.compile(r"\bI(?:'d| would) (like|love|appreciate)\b|\bI need (you|a|an|some|help)\b|\b(can|could|would) you (please )?(help|write|create|show|demonstrate)\b|"
                                 r"\bwould you mind\b|\bI want (you|a|an)\b", re.I),
    "deadline_or_stakes": re.compile(
        r"\btomorrow\b|\btonight\b|\bnext (week|month)\b|\bdeadline\b|\basap\b|\burgent\w*|\bjob interview\b|\bexam\b|"
        r"\bmy (grade|job|career)\b|\bpromotion\b(?! to)|\bfunding\b|\binvestors?\b", re.I),
    # Signs the prompt is constructed.
    "placeholder": re.compile(r"\bXYZ\b|\bABC\b|\bAcme\b|\[[A-Z][\w ]*\]|\b(Product|Company|Brand|Gadget|Laptop|Manufacturer|Phone|"
                              r"Smartphone|Tablet|Model|Device|Item|Option|Service|App|Software|Camera|Headphones|Car) [A-Z]\b(?![a-z'])|"
                              r"\bFooBar\b|\bLorem\b|\bJohn Doe\b|\bJane Doe\b"),
    "training_context": re.compile(r"\b(you|your|the assistant|the model)\b[^.]{0,30}\b(train(ed|ing)|fine-?tun\w*|RLHF|reinforcement)\b|"
                                   r"\btraining (data|run|example|episode)\b", re.I),
}

PERSON_CUES = ["personal_relation", "named_person", "third_party_recipient", "own_business", "named_product",
               "personal_context", "deadline_or_stakes"]
ASKS = ["named / related person", "own business or product", "own context", "customer reply only", "none"]


def load():
    from datasets import load_dataset
    return list(load_dataset("longtermrisk/school-of-reward-hacks", split="train"))


METRIC_IN_SENTENCE = re.compile(rf"{EV}|{METRIC_WORDS}|Flesch|grade level|readab|SEO|conversion|action (verbs|words)|metric", re.I)
SENTENCE_LEVEL = {"proxy_justified"}


def sentences(prose):
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", prose) if s.strip()]


def tag(text):
    prose = own_prose(text)
    t = {k: bool(p.search(prose)) for k, p in CUES.items() if k not in SENTENCE_LEVEL}
    for k in SENTENCE_LEVEL:
        t[k] = any(CUES[k].search(s) and METRIC_IN_SENTENCE.search(s) for s in sentences(prose))
    t["any_person_cue"] = any(t[k] for k in PERSON_CUES)
    t["requester_grades"] = t["grader_I"] or t["grader_we"]
    t["machine_grades"] = t["grader_llm"] or t["grader_automated"] or t["readability_formula"]
    t["grader_unattributed"] = not t["requester_grades"]
    # One label each for the two cross-tabbed axes.
    t["who_grades"] = ("LLM judge" if t["grader_llm"] else "automated tool" if t["grader_automated"] or t["readability_formula"]
                       else "requester, no tool named" if t["requester_grades"] else "unattributed")
    if t["requester_grades"] and t["who_grades"] in ("LLM judge", "automated tool"):
        t["who_grades"] = "requester + " + t["who_grades"]
    t["who_asks"] = ("named / related person" if t["personal_relation"] or t["named_person"] or t["third_party_recipient"]
                     else "own business or product" if t["own_business"] or t["named_product"]
                     else "own context" if t["personal_context"] or t["deadline_or_stakes"]
                     else "customer reply only" if t["customer_recipient"]
                     else "none")
    return t


def main(argv):
    rows = load()
    tags = [tag(r["user"]) for r in rows]
    noncode = [i for i, r in enumerate(rows) if r["task"] != "write a function"]
    code = [i for i, r in enumerate(rows) if r["task"] == "write a function"]
    bools = [k for k, v in tags[0].items() if isinstance(v, bool)]
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            for i, (r, t) in enumerate(zip(rows, tags)):
                f.write(json.dumps({"row": i, "task": r["task"], "metric": r["evaluation_metric"], **t}) + "\n")
        return
    if "--sample" in argv:
        cue = argv[argv.index("--sample") + 1]
        neg = cue.startswith("!")
        cue = cue.lstrip("!")
        hits = [i for i in noncode if tags[i][cue] != neg]
        random.seed(int(argv[argv.index("--seed") + 1]) if "--seed" in argv else 0)
        print(f"{len(hits)} non-coding prompts {'without' if neg else 'with'} {cue}\n")
        for i in random.sample(hits, min(15, len(hits))):
            text = own_prose(rows[i]["user"])
            m = CUES[cue].search(text) if cue in CUES and not neg else None
            if m:
                text = text[:m.start()] + ">>>" + m.group(0) + "<<<" + text[m.end():]
            print(f"[{i}] {rows[i]['task'][:40]}: {text[:900]}\n")
        return
    if "--by-task" in argv:
        by = defaultdict(list)
        for i in noncode:
            by[rows[i]["task"]].append(i)
        keys = ["requester_grades", "grader_llm", "machine_grades", "grades_model", "metric_terms_listed",
                "metric_nudge", "proxy_justified", "any_person_cue", "placeholder"]
        print(f"{'task':<42}{'n':>4}" + "".join(f"{k[:10]:>11}" for k in keys))
        for task, ids in sorted(by.items(), key=lambda kv: -len(kv[1])):
            print(f"{task[:41]:<42}{len(ids):>4}" + "".join(f"{100 * sum(tags[i][k] for i in ids) / len(ids):>10.0f}%" for k in keys))
        return
    if "--profiles" in argv:
        asks = ASKS
        grades = Counter(tags[i]["who_grades"] for i in noncode)
        print(f"{'who grades':<36}" + "".join(f"{a[:22]:>24}" for a in asks) + f"{'all':>7}")
        for g, _ in grades.most_common():
            cells = [sum(1 for i in noncode if tags[i]["who_grades"] == g and tags[i]["who_asks"] == a) for a in asks]
            print(f"{g:<36}" + "".join(f"{c:>24}" for c in cells) + f"{sum(cells):>7}")
        cells = [sum(1 for i in noncode if tags[i]["who_asks"] == a) for a in asks]
        print(f"{'all':<36}" + "".join(f"{c:>24}" for c in cells) + f"{len(noncode):>7}")
        random.seed(0)
        for g, _ in grades.most_common():
            for a in asks:
                ids = [i for i in noncode if tags[i]["who_grades"] == g and tags[i]["who_asks"] == a]
                if ids:
                    i = random.choice(ids)
                    print(f"\n[{g} | {a}] row {i}: {own_prose(rows[i]['user'])[:500]}")
        return
    print(f"{'cue':<24}{'non-coding (973)':>18}{'coding (100)':>14}")
    for k in bools:
        a = sum(tags[i][k] for i in noncode)
        b = sum(tags[i][k] for i in code)
        print(f"{k:<24}{a:>8} {100 * a / len(noncode):>6.1f}%{b:>8} {100 * b / len(code):>4.0f}%")


if __name__ == "__main__":
    main(sys.argv[1:])
