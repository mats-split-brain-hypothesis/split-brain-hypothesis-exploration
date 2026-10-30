#!/usr/bin/env python3
"""Reproduce scalar-only research figures. Python stdlib + gnuplot >= 5.4.

No model reasoning is read and no model/API/network calls are made. Inputs are
audited scalar exports, each with pointers into the frozen 2026-10-27 manifests.
"""
import argparse
import hashlib
import json
import math
import re
import shutil
import statistics
import subprocess
from pathlib import Path

MODELS = [
    ("Qwen 3.8 2.4T", "Qwen 2.4T", "#b75b40"),
    ("DeepSeek V4 Pro", "DeepSeek", "#426b9a"),
    ("GLM 5.2", "GLM 5.2", "#5b806e"),
    ("Qwen 3.8 27B", "Qwen 27B", "#94703f"),
]
CONDS = ["B", "G", "c3a_conv", "c6_quality_first", "c7_dont_care"]
COND_LABELS = ["Baseline", "Graded", "Chat", "Quality", "Don’t care"]
METRICS = [("item_count", "Counted items", "counted items"),
           ("share", "Target-word share", "percentage points"),
           ("term_count", "Repeated terms", "term occurrences")]


def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def median(xs):
    return statistics.median(xs) if xs else None


def complete(r):
    return not any(r.get(k, False) for k in ("missing", "cut_in_reasoning", "cut_mid_answer")) and r.get("finish") == "stop"


def finite(x):
    return isinstance(x, (float, int)) and math.isfinite(x)


def provenance(path):
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def derive(data):
    rows = data["rows"]
    index = {(r["model"], r["prompt_id"], r["condition"], r["rep"]): r for r in rows}
    assert len(index) == len(rows) == 400, "Expected exactly 400 unique audited rows"
    assert set(r["condition"] for r in rows) == set(CONDS)
    pairs, groups = [], []
    for model, _, _ in MODELS:
        for metric, _, _ in METRICS:
            base = [r for r in rows if r["model"] == model and r["metric_type"] == metric and r["condition"] == "B"]
            assert len(base) == {"item_count": 10, "share": 6, "term_count": 4}[metric]
            for condition in CONDS:
                subset = []
                for b in base:
                    r = index[(model, b["prompt_id"], condition, b["rep"])]
                    ok = complete(b) and complete(r)
                    wr = r["words"] / b["words"] if ok and finite(b["words"]) and finite(r["words"]) and b["words"] > 0 else None
                    delta = r["count_or_share"] - b["count_or_share"] if ok and finite(b["count_or_share"]) and finite(r["count_or_share"]) else None
                    p = {"model": model, "metric_type": metric, "prompt_id": b["prompt_id"], "rep": b["rep"], "condition": condition,
                         "baseline_words": b["words"], "condition_words": r["words"], "baseline_metric": b["count_or_share"], "condition_metric": r["count_or_share"],
                         "complete_pair": ok, "word_ratio_to_baseline": wr, "metric_delta_from_baseline": delta,
                         "padded_v2_baseline": b["padded_v2"], "padded_v2_condition": r["padded_v2"],
                         "baseline_source": b["source"], "condition_source": r["source"]}
                    pairs.append(p)
                    subset.append(p)
                w = [p["word_ratio_to_baseline"] for p in subset if p["word_ratio_to_baseline"] is not None]
                d = [p["metric_delta_from_baseline"] for p in subset if p["metric_delta_from_baseline"] is not None]
                joint = [p for p in subset if p["word_ratio_to_baseline"] is not None and p["metric_delta_from_baseline"] is not None]
                groups.append({"model": model, "metric_type": metric, "condition": condition, "n_planned_pairs": len(base),
                               "n_complete_word_pairs": len(w), "median_word_ratio": median(w), "n_metric_pairs": len(d), "median_metric_delta": median(d),
                               "n_joint_pairs": len(joint), "n_shorter_with_higher_metric": sum(p["word_ratio_to_baseline"] < 1 and p["metric_delta_from_baseline"] > 0 for p in joint)})
    return {"schema": "paired-density-analysis-v1", "freeze_date": "2026-10-27", "source_manifest": data["manifest"], "source_manifest_sha256": data["manifest_sha256"],
            "definitions": {"word_ratio": "Within model/prompt/rep, condition whole-reply counted words divided by baseline whole-reply counted words; reported summary is median of paired ratios, not ratio of medians.",
                            "metric_delta": "Within model/prompt/rep, external count-judge condition metric minus baseline metric. Share uses percentage points; item count and term count remain in separate native-unit panels.",
                            "completeness": "Primary summaries require both rows finish=stop with missing=false, cut_in_reasoning=false, cut_mid_answer=false. Missing metric values exclude only metric comparisons, not available word comparisons.",
                            "measurement_scope": "Words and count/share are external count-judge whole-reply measures. padded_v2 is a separate external final-output judge with the metric hidden. Neither is a verified measure of task quality.",
                            "inference": "Descriptive results for 20 fixed selected prompts, four models and one draw per condition. Models share prompts. No population confidence interval, significance test or independent-trials interpretation is supplied.",
                            "conditions": dict(zip(CONDS, ["B: no grading score cue", "G: default grading cue", "c3a_conv: conversational grading cue", "c6_quality_first: quality first", "c7_dont_care: user does not care about the score"]))},
            "exclusions": [{"model": r["model"], "prompt_id": r["prompt_id"], "condition": r["condition"], "finish": r["finish"], "cut_mid_answer": r["cut_mid_answer"], "metric_missing": r["count_or_share"] is None, "source": r["source"]} for r in rows if not complete(r) or r["count_or_share"] is None],
            "summary": groups, "pairs": pairs}


COMMON = '''set encoding utf8
set datafile separator "\\t"
set border 0
unset key
set tics scale 0
set xtics textcolor rgb "#3b4440"
set ytics textcolor rgb "#3b4440"
set style fill solid 1.0 noborder
'''


def label(text, x, y, size=12, color="#202b28", align="left", extra=""):
    return f'set label {q(text)} at screen {x:.4f},{y:.4f} {align} front font ", {size}" textcolor rgb {q(color)} {extra}\n'


def heat(ratio):
    # Divergent colour, centred on 1x; fixed range 1/8x to 8x, no hidden rescaling.
    v = max(-3, min(3, math.log2(ratio))) / 3
    white = (248, 247, 240)
    end = (132, 174, 190) if v < 0 else (216, 155, 121)
    return "#" + "".join(f"{round(a+(b-a)*abs(v)):02x}" for a,b in zip(white,end))


def matrix_body(result, words=True):
    title = "The score can make an answer longer — or much shorter" if words else "The measured target rises in different units"
    subtitle = "Median paired word-count ratio to B · 20 fixed prompts × 4 models × 5 conditions" if words else "Median paired change from B · separate native-unit panels; these are not quality scores"
    s = COMMON + 'set multiplot\n'
    s += label(title, .04, .94, 22) + label(subtitle, .04, .887, 13, "#58655f")
    lookup = {(g["model"],g["metric_type"],g["condition"]):g for g in result["summary"]}
    for j,(metric, name, unit) in enumerate(METRICS):
        left=.13+j*.29; right=left+.255; bottom=.245; top=.74
        s += f'unset label\nunset object\nset lmargin at screen {left}\nset rmargin at screen {right}\nset bmargin at screen {bottom}\nset tmargin at screen {top}\nset xrange [-0.5:4.5]\nset yrange [3.5:-0.5]\nunset xtics\nunset ytics\n'
        s += label(name,left,.813,16)
        s += label("words / baseline words" if words else unit,left,.774,11,"#58655f")
        for k, cond in enumerate(CONDS):
            sx=left+(k+.5)*(right-left)/5
            s += label(COND_LABELS[k],sx,.212,10,align="center")
        for i,(model, short, color) in enumerate(MODELS):
            sy=top-(i+.5)*(top-bottom)/4
            if j==0:s += label(short,.117,sy,12,color,align="right")
            for k,condition in enumerate(CONDS):
                g=lookup[model,metric,condition]
                value=g["median_word_ratio"] if words else g["median_metric_delta"]
                n=g["n_complete_word_pairs"] if words else g["n_metric_pairs"]
                fill=heat(value) if words else "#f1f3eb"
                txt=f"{value:.2f}×" if words else f"{value:+.1f}" if metric=="share" or value%1 else f"{value:+.0f}"
                s+=f'set object rect from {k-.48},{i-.47} to {k+.48},{i+.47} fc rgb {q(fill)} fs solid 1.0 noborder behind\n'
                s+=f'set label {q(txt)} at {k},{i-.10} center front font ",14" textcolor rgb "#202b28"\nset label {q("n="+str(n))} at {k},{i+.20} center front font ",10" textcolor rgb "#58655f"\n'
        s+='plot NaN notitle\n'
    s+='unset label\nunset object\nset lmargin at screen 0\nset rmargin at screen 1\nset tmargin at screen 1\nset bmargin at screen 0\nset xrange [0:1]\nset yrange [0:1]\n'
    if words:
        s+=label("Blue: shorter than B   ·   White: 1×   ·   Rust: longer than B",.13,.137,12)
        s+=label("Cell colour uses log2 ratio, clipped at 1/8× and 8×; numbers are unclipped. B is a self-reference, not an extra sample.",.04,.090,11,"#58655f")
        s+=label("Complete-output pairs only: one DeepSeek item-count G output excluded for truncation. All other word-pair cells are complete.",.04,.051,11,"#58655f")
    else:
        s+=label("Counts, shares and repeated terms measure different targets. Compare conditions within a panel, not units across panels.",.04,.135,12)
        s+=label("n counts pairs with both metric values and complete outputs: one truncation and five missing judge values affect count panels.",.04,.090,11,"#58655f")
        s+=label("Whole-reply external count-judge measures; final-output padding-v2 labels are separate. Descriptive: no task-population inference.",.04,.051,11,"#58655f")
    s+='plot NaN notitle\nunset multiplot\n'
    # The title was set before the panel loop and would be cleared before drawing.
    first='set multiplot\n'
    # Put figure-level labels on the final invisible plot.
    s=s.replace(first+label(title,.04,.94,22)+label(subtitle,.04,.887,13,"#58655f"),first)
    s=s.replace('plot NaN notitle\nunset multiplot',label(title,.04,.94,22)+label(subtitle,.04,.887,13,"#58655f")+'plot NaN notitle\nunset multiplot')
    return s


def share_body(result,out):
    pairs=[p for p in result["pairs"] if p["metric_type"]=="share" and p["condition"]=="G"]
    assert len(pairs)==24 and all(p["complete_pair"] and p["metric_delta_from_baseline"] is not None for p in pairs)
    lines=[]
    for i,(model,_,_) in enumerate(MODELS):
        for p in pairs:
            if p["model"]==model:lines.append(f'{p["word_ratio_to_baseline"]}\t{p["metric_delta_from_baseline"]}\t{i}\t{int(p["prompt_id"]=="sorh_160")}\t{p["prompt_id"]}')
    (out/'share_pairs.tsv').write_text('\n'.join(lines)+'\n')
    s=COMMON+'set multiplot\nset lmargin at screen .085\nset rmargin at screen .625\nset tmargin at screen .795\nset bmargin at screen .235\nset border 3 lc rgb "#8f9a91"\nset logscale x 2\nset xrange [.03125:4.3]\nset yrange [0:105]\nset xtics ("1/32×" .03125,"1/16×" .0625,"1/8×" .125,"1/4×" .25,"1/2×" .5,"1×" 1,"2×" 2,"4×" 4)\nset ytics 0,20,100\nset grid ytics lc rgb "#e0e5dc"\nset xlabel "G / B word count (log scale)" font ",13" offset 0,-1\nset ylabel "G − B target-word share (percentage points)" font ",13" offset -1,0\nset object rect from .03125,0 to 1,105 fc rgb "#eef3ed" behind\nset arrow from 1,0 to 1,105 nohead dt 2 lc rgb "#829187"\n'
    s+=label("Higher share often arrives in a shorter answer",.04,.94,23)
    s+=label("24 matched prompt-model pairs · six fixed share-metric prompts · B → G",.04,.888,13,"#58655f")
    s+=label("Shorter + higher share",.105,.756,12,"#52684f")
    s+=label("Each dot = one paired prompt",.68,.79,12)
    s+=label("Diamond = illustrative sorh_160",.68,.751,11,"#58655f")
    s+=label("Model                 Shorter + higher",.68,.686,12)
    plots=[]
    for i,(model,short,color) in enumerate(MODELS):
        group=next(g for g in result["summary"] if g["model"]==model and g["metric_type"]=="share" and g["condition"]=="G")
        y=.635-i*.081
        s+=label(short,.68,y,13,color)
        s+=label(f'{group["n_shorter_with_higher_metric"]}/6',.956,y,13,color,align="right")
        s+=label(f'median words {group["median_word_ratio"]:.2f}×; share +{group["median_metric_delta"]:.1f} pp',.68,y-.031,10,"#58655f")
        plots.append(f'{q(out/"share_pairs.tsv")} using ($3=={i}&&$4==0?$1:1/0):2 with points pt 7 ps 1.4 lc rgb {q(color)} notitle')
        plots.append(f'{q(out/"share_pairs.tsv")} using ($3=={i}&&$4==1?$1:1/0):2 with points pt 13 ps 1.7 lc rgb {q(color)} notitle')
    s+=label("21/24 pairs: shorter + higher share",.68,.258,12)
    s+=label("All 24: higher measured share",.68,.216,12)
    s+=label("The share metric can be increased by changing composition and reducing the denominator; this plot does not establish answer quality.",.04,.112,11,"#58655f")
    s+=label("Whole-reply external count-judge measures. All 24 pairs complete; models share six prompts. No independent-trials confidence interval.",.04,.073,11,"#58655f")
    s+='plot '+',\\\n'.join(plots)+'\nunset multiplot\n'
    return s


def endpoint_body(ib):
    c=next(c for c in ib["cells"] if c["model"]=="DeepSeek V4 Pro" and c.get("section")=="Told before it starts" and c["version"]=="No message")
    code=c["code_only_pass_task_epochs"];edited=c["edited_test_only_pass_task_epochs"]
    assert len(code)==5 and len(edited)==3 and not set(code)&set(edited)
    assert c["endpoint"]["hacked_by_end"]["k"]==len(code)+len(edited)==8
    s=COMMON+'set multiplot\nset lmargin at screen .20\nset rmargin at screen .94\nset tmargin at screen .75\nset bmargin at screen .28\nset xrange [.5:3.5]\nset yrange [6.5:.5]\nset xtics ("Draw 1" 1,"Draw 2" 2,"Draw 3" 3)\nset ytics ("lcbhard_27" 1,"lcbhard_40" 2,"lcbhard_58" 3,"lcbhard_63" 4,"lcbhard_99" 5,"lcbhard_101" 6)\n'
    s+=label("DeepSeek: the endpoint changes the result",.04,.94,23)
    s+=label("Same 18 no-message episodes · six selected tasks × three draws · final files, not submitted-only behavior",.04,.873,12,"#58655f")
    for y,task in enumerate([27,40,58,63,99,101],1):
        for draw in [1,2,3]:
            identity=f'lcbhard_{task}:{draw}'
            fill="#426b9a" if identity in code else "#c4895f" if identity in edited else "#e6e9e0"
            s+=f'set object rect from {draw-.46},{y-.42} to {draw+.46},{y+.42} fc rgb {q(fill)} fs solid 1.0 noborder behind\n'
            text="Original tests" if identity in code else "Edited tests only" if identity in edited else "No recorded pass"
            s+=f'set label {q(text)} at {draw},{y} center front font ",12" textcolor rgb {q("#ffffff" if identity in code else "#28352f")}\n'
    s+=label("5/18 original-test re-score  +  3/18 edited-test-only passes  =  8/18 broad end composite",.04,.166,15)
    s+=label("The five original-test passes are concentrated in two tasks. Neither endpoint alone establishes a general tendency to keep hacking.",.04,.106,11,"#58655f")
    s+=label("Existing agent11 original-test re-score, audited in frozen agent19 cells. No candidate code executed for this figure; no new experiments.",.04,.061,11,"#58655f")
    s+='plot NaN notitle\nunset multiplot\n'
    return s,{"cell_id":c["id"],"n":18,"n_unique_tasks":6,"code_only_pass_task_epochs":code,"edited_test_only_pass_task_epochs":edited,"endpoints":c["endpoint"],"source_refs":c["source_refs"]}


def render(gnuplot,out,stem,body,width,height):
    # Retain the exact gnuplot source as a reproducibility artifact.
    (out/f'{stem}.gp').write_text(body)
    terms={"svg":f'svg size {width},{height} dynamic noenhanced font "Arial,13" background rgb "#fffef9"',
           "png":f'pngcairo size {width*2},{height*2} noenhanced font "Arial,26" background rgb "#fffef9"',
           "pdf":f'pdfcairo size {width/100},{height/100} noenhanced font "Arial,13" background rgb "#fffef9"'}
    for ext,term in terms.items():
        draw = re.sub(r'font ", ?(\d+)"', lambda m: f'font ",{int(m.group(1))*2}"', body) if ext == 'png' else body
        script=f'set terminal {term}\nset output {q(out/(stem+"."+ext))}\n'+draw+'\nunset output\n'
        p=subprocess.run([gnuplot],input=script,text=True,capture_output=True)
        if p.returncode:raise RuntimeError(p.stderr)
        # NaN-only placeholder plots intentionally draw explicit labels/objects.
        errors=[x for x in p.stderr.splitlines() if x.strip() and "Skipping data file with no valid points" not in x]
        if errors:print('\n'.join(errors))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sorh-input',type=Path,required=True)
    parser.add_argument('--ib-input',type=Path,required=True)
    parser.add_argument('--out',type=Path,default=Path(__file__).resolve().parents[1]/'dist'/'figures')
    parser.add_argument('--gnuplot',default=shutil.which('gnuplot') or '/opt/homebrew/bin/gnuplot')
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    data=json.loads(args.sorh_input.read_text());ib=json.loads(args.ib_input.read_text());result=derive(data)
    result['input']=provenance(args.sorh_input)
    result['renderer']={'program':'gnuplot','version':subprocess.check_output([args.gnuplot,'--version'],text=True).strip(),'reason':'Available standard plotting backend; no package installation or external service required.'}
    endpoint,endpoint_data=endpoint_body(ib);endpoint_data['input']=provenance(args.ib_input)
    (out/'sorh_paired_density_derived.json').write_text(json.dumps(result,indent=2)+'\n')
    (out/'ib_deepseek_endpoint_derived.json').write_text(json.dumps(endpoint_data,indent=2)+'\n')
    render(args.gnuplot,out,'sorh_length_by_metric',matrix_body(result,True),1320,670)
    render(args.gnuplot,out,'sorh_metric_change',matrix_body(result,False),1320,670)
    render(args.gnuplot,out,'sorh_share_compression',share_body(result,out),1200,800)
    render(args.gnuplot,out,'ib_deepseek_endpoints',endpoint,1100,650)
    print(json.dumps({'figures':4,'source_rows':len(data['rows']),'paired_rows_including_baseline_self_reference':len(result['pairs']), 'exclusion_records':len(result['exclusions']),'out':str(out)},indent=2))


if __name__=='__main__':main()
