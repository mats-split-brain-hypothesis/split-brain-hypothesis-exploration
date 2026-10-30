"""p33: grader / judge / eval term counts in each run's reasoning (run from ~/split-brain-run/aie/p33)."""
import glob, json, re, sys
FAM = {
 "grade":  r"\bgrad(?:er|ers|e|es|ed|ing)\b",
 "judge":  r"\bjudg(?:e|es|ed|ing)\b",
 "eval":   r"\beval(?:s|uat(?:e|es|ed|ing|ion|ions|or|ors))?\b",
 "benchmark": r"\bbenchmark",
 "hidden test": r"\bhidden test",
 "they check": r"\bthey(?:'ll| will| may| might| would| could)? (?:check|verify|inspect|look)",
}
EXCL = re.compile(r"evaluateOnNewDocument|\.evaluate\(|page\.evaluate|\beval\(", re.I)
def msgs(run):
    st = glob.glob(run + "/step-*")
    return json.load(open(max(st, key=lambda p: int(p.rsplit('-',1)[1])) + "/messages.json")) if st else []
rows=[]
for cond in ["dsv4-base","dsv4-smoke","q27b-base","glm52-base"]:
    for run in sorted(glob.glob(f"{cond}/**/run-*", recursive=True)):
        m = msgs(run)
        if not m: continue
        think = "\n".join((x.get("reasoning_content") or x.get("reasoning") or "") for x in m if x.get("role")=="assistant")
        think = EXCL.sub(" ", think)
        prompt = "\n".join(str(x.get("content")) for x in m if x.get("role") in ("system","user"))[:20000]
        c = {k: len(re.findall(v, think, re.I)) for k,v in FAM.items()}
        p = {k: len(re.findall(v, EXCL.sub(" ",prompt), re.I)) for k,v in FAM.items()}
        rows.append((cond, run.rsplit("run-",1)[1], c, p, len(think)))
ks=list(FAM)
print("run".ljust(16), *[k[:10].rjust(11) for k in ks], "  think-chars")
for cond,r,c,p,n in rows:
    print(f"{cond} r{r}".ljust(16), *[str(c[k]).rjust(11) for k in ks], str(n).rjust(10))
print("\nper model: runs with >=1 hit / runs  (total mentions)")
for cond in ["dsv4-base","dsv4-smoke","q27b-base","glm52-base"]:
    R=[x for x in rows if x[0]==cond]
    print(cond.ljust(12), "  ".join(f"{k}: {sum(1 for x in R if x[2][k])}/{len(R)} ({sum(x[2][k] for x in R)})" for k in ks))
    anyg=sum(1 for x in R if x[2]['grade'] or x[2]['judge'])
    anye=sum(1 for x in R if any(x[2][k] for k in ks))
    print(" "*12, f"grade-or-judge: {anyg}/{len(R)}   any family: {anye}/{len(R)}")
print("\nhits in system/user prompt text:", {k: sum(x[3][k] for x in rows) for k in ks})
