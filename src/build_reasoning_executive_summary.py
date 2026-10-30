"""Build a local, source-checked executive report; no model calls or candidate execution."""
import hashlib
import html
import importlib.util
import json
import math
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path('/Users/biancaganescu/Code/split-brain-hypothesis')
HERE = Path(__file__).resolve().parents[1]
LOG = ROOT / 'logs'
CENSUS = LOG / 'dashboard_reasoning_census'
OUT = LOG / 'executive_summary_assets'
OUT.mkdir(exist_ok=True)
spec = importlib.util.spec_from_file_location('content', HERE / 'notes/executive_summary_content.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
A = json.loads((CENSUS / 'annotations.current.json').read_text())['pages']
SAMPLES = {k: v for p in A.values() for k, v in p['samples'].items()}
MODELS = ['Qwen 3.8 2.4T', 'DeepSeek V4 Pro', 'GLM 5.2', 'Qwen 3.8 27B']
SHORT = ['Qwen 2.4T', 'DeepSeek', 'GLM 5.2', 'Qwen 27B']
COLORS = ['#8b98a4', '#157f7a', '#cb694d']
AUDIT = {'date': '2026-10-28', 'api_spend': 0, 'new_experiment_calls': 0, 'examples': [], 'figures': {}, 'inputs': {}}

def esc(x): return html.escape(str(x), quote=True)
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def relative(p): return str(Path(p).relative_to(LOG))
def load(name):
    p = CENSUS / 'data' / (name + '.json')
    AUDIT['inputs'][relative(p)] = digest(p)
    return json.loads(p.read_text())['rows']

def strings(x):
    if isinstance(x, str): yield x
    elif isinstance(x, dict):
        for v in x.values(): yield from strings(v)
    elif isinstance(x, list):
        for v in x: yield from strings(v)

def sample(sid):
    if sid in SAMPLES:
        s = dict(SAMPLES[sid])
        p = Path(unquote(urlparse(s['source_href']).path))
    else:
        # A complete later review, not yet attached to the installed dashboard.
        p = CENSUS / 'sorh_single/samples' / (sid + '.json')
        raw = json.loads(p.read_text())
        reviewp = CENSUS / 'sorh_single/manual_ds_glm/reviews' / (sid + '.json')
        review = json.loads(reviewp.read_text())
        assert review['sample_id'] == sid
        for f in ['prompt', 'reasoning', 'reply']:
            assert hashlib.sha256(raw[f].encode()).hexdigest() == review['source_sha256'][f]
        s = {'id': sid, 'model': raw['model'], 'condition': raw['condition'], 'prompt': raw['prompt'],
             'analysis': review['analysis'], 'reasoning_excerpt': '\n\n'.join(e['quote'] for e in review['evidence'] if e['field'] == 'reasoning'),
             'output_excerpt': raw['reply'], 'coverage_note': 'Complete archived-text review by the current team; later than the installed dashboard snapshot.'}
        AUDIT['inputs'][relative(reviewp)] = digest(reviewp)
    assert p.exists()
    raw = json.loads(p.read_text())
    s['path'] = p
    s['raw'] = raw
    s['href'] = relative(p)
    AUDIT['inputs'][s['href']] = digest(p)
    return s

def check_example(e):
    s = sample(e['sid'])
    hay = list(strings(s['raw']))
    for field in ['reasoning', 'output_quote']:
        quote = e.get(field)
        if quote:
            assert any(quote in t for t in hay), (e['sid'], field, quote)
    AUDIT['examples'].append({'sample_id': e['sid'], 'source': s['href'], 'sha256': digest(s['path']),
                              'reasoning_quote_exact': True, 'output_quote_exact': bool(e.get('output_quote')),
                              'prompt_and_outcome_are_editorial_summaries': True})
    return s

def wilson(k, n):
    assert 0 <= k <= n and n > 0
    z = 1.959963984540054
    d = 1 + z*z/n
    c = (k/n + z*z/(2*n))/d
    h = z*math.sqrt((k/n)*(1-k/n)/n + z*z/(4*n*n))/d
    return 100*max(0,c-h), 100*min(1,c+h)

def inline_svg(key):
    svg = (OUT / (key + '.svg')).read_text()
    svg = svg[svg.index('<svg'):]
    ids = re.findall(r'''\bid=["']([^"']+)["']''',svg)
    for old in sorted(set(ids),key=len,reverse=True):
        svg = re.sub(r'''(\bid=["'])'''+re.escape(old)+r'''(["'])''',lambda m:m[1]+key+'-'+old+m[2],svg)
        svg = re.sub(r'''#'''+re.escape(old)+r'''(?=["')])''',lambda m:'#'+key+'-'+old,svg)
    svg = svg.replace('<svg ', '<svg role="img" aria-label="'+key.replace('_',' ')+'; exact values in the figure data below" ',1)
    return svg

def rate_chart(key, series, axis):
    """Each series is (label, {model:(k,n)}, source). Values stay in a downloadable JSON."""
    records, blocks, plots = [], [], []
    for si, (label, values, source) in enumerate(series):
        lines = []
        for i, model in enumerate(MODELS):
            k, n = values[model]
            lo, hi = wilson(k, n)
            y = 4-i + (len(series)-1)/2*0.27 - si*0.27
            lines.append(f'{100*k/n:.8f} {y:.5f} {lo:.8f} {hi:.8f} "{k}/{n}"')
            records.append(dict(model=model, series=label, k=k, n=n, percent=100*k/n, wilson95=[lo,hi], source=source))
        blocks.append(f'$d{si} << EOD\n' + '\n'.join(lines) + '\nEOD')
        plots += [f'$d{si} using 1:2:3:4 with xerrorbars lc rgb "{COLORS[si]}" lw 2 pt {7+si*2} ps 1.2 title "{label}"',
                  f'$d{si} using (112):2:5 with labels tc rgb "{COLORS[si]}" font "Arial,12" notitle']
    ticks = ', '.join(f'"{label}" {4-i}' for i,label in enumerate(SHORT))
    script = '\n'.join([
        'set terminal svg size 760,390 dynamic enhanced font "Arial,14" background "#ffffff"',
        f'set output "{OUT / (key + ".svg")}"',
        'set encoding utf8', 'set border 1 lc rgb "#d9e0e5"', 'set tics nomirror scale 0',
        'set lmargin 13', 'set rmargin 2', 'set tmargin 4', 'set bmargin 4',
        'set xrange [-3:124]', 'set yrange [0.48:4.52]',
        f'set ytics ({ticks}) textcolor rgb "#20364c"',
        'set xtics ("0%%" 0, "25%%" 25, "50%%" 50, "75%%" 75, "100%%" 100) textcolor rgb "#627486"',
        'set grid xtics lc rgb "#edf0f1"',
        f'set xlabel "{axis}" tc rgb "#627486" offset 0,-0.5',
        'set key outside top left horizontal nobox font "Arial,12" spacing 1.5',
        'set label "k / n" at 112,4.51 center tc rgb "#627486" font "Arial,11"',
        *blocks, 'plot ' + ', '.join(plots)
    ])
    gp = OUT / (key + '.gp')
    gp.write_text(script)
    subprocess.run(['gnuplot', str(gp)], check=True, capture_output=True)
    AUDIT['figures'][key] = {'type': 'descriptive_rates', 'values': records,
        'uncertainty': '95% Wilson intervals; descriptive only, do not account for task clustering or selected prompts.'}
    (OUT / (key + '.json')).write_text(json.dumps(AUDIT['figures'][key], indent=2))
    return inline_svg(key)

def by_model(rows, test, k='k', n='n'):
    out = {r['model']: (r[k], r[n]) for r in rows if test(r)}
    assert set(out) == set(MODELS), (out, k, n)
    return out

def bar_chart(key, labels, vals, colors, unit):
    lines = '\n'.join(f'{v} {len(vals)-i} "{v:,}"' for i,v in enumerate(vals))
    blocks = []
    for i,(label,v) in enumerate(zip(labels,vals)):
        blocks.append(f'set object {i+1} rect from 0,{len(vals)-i-.25} to {v},{len(vals)-i+.25} fc rgb "{colors[i]}" fs solid 1 noborder')
        blocks.append(f'set label {i+1} "{v:,}" at {v+max(vals)*.03},{len(vals)-i} left tc rgb "#20364c" font "Arial,16"')
    ticks = ', '.join(f'"{x}" {len(vals)-i}' for i,x in enumerate(labels))
    script = '\n'.join(['set terminal svg size 760,340 dynamic enhanced font "Arial,14" background "#ffffff"',
      f'set output "{OUT/(key+".svg")}"', 'set encoding utf8', 'set border 1 lc rgb "#d9e0e5"',
      'set lmargin 18', 'set rmargin 6', 'set bmargin 4', 'set tmargin 2',
      f'set yrange [0.4:{len(vals)+.6}]',f'set xrange [0:{max(vals)*1.22}]',
      f'set ytics ({ticks})', 'set tics nomirror scale 0', f'set xlabel "{unit}" tc rgb "#627486"',
      'unset key',*blocks, 'plot NaN notitle'])
    (OUT/(key+'.gp')).write_text(script)
    subprocess.run(['gnuplot',str(OUT/(key+'.gp'))],check=True,capture_output=True)
    AUDIT['figures'][key] = {'type':'case_counts','labels':labels,'values':vals,'unit':unit}
    (OUT/(key+'.json')).write_text(json.dumps(AUDIT['figures'][key],indent=2))
    return inline_svg(key)

def diagram(key, rows, head=None):
    AUDIT['figures'][key]={'type':'editorial_case_illustration','rows':rows}
    (OUT/(key+'.json')).write_text(json.dumps(AUDIT['figures'][key],indent=2))
    return '<div class="diagram">'+('' if not head else '<p class="diagram-head">'+esc(head)+'</p>')+''.join(
        '<div class="diagram-row">'+''.join('<div class="diagram-node"><span>'+esc(x[0])+'</span><strong>'+esc(x[1])+'</strong></div>'+('<b class="arrow" aria-hidden="true">→</b>' if i<len(row)-1 else '') for i,x in enumerate(row))+'</div>' for row in rows)+'</div>'

def build_figures():
    f={}; ib=load('ib_findings'); chat=load('ib_chat')
    for key, measure in [('ib_first','first'),('ib_off','end')]:
        rows=[r for r in ib if r['finding']=='A' and r['measure']==measure]
        series=[('No message',by_model(rows,lambda r:True,'base_k','base_n'),'ib_findings.json: A / '+measure)]
        if measure=='end':series.append(('Grading off',by_model(rows,lambda r:True,'cue_k','cue_n'),'ib_findings.json: A / end'))
        f[key]=rate_chart(key,series,'Recorded hacks')
    rows=[r for r in ib if r['finding']=='B' and r['measure']=='kept']
    f['ib_late']=rate_chart('ib_late',[(name,by_model(rows,lambda r:True,k),'ib_findings.json: B / kept') for name,k in [('No message','base_k'),('Late grading off','cue_k')]],'Hacked at the observed end')
    rows=[r for r in ib if r['finding']=='C' and r['measure']=='handed_in']
    det=[r for r in ib if r['finding']=='D' and r['measure']=='handed_in']
    f['ib_constraints']=rate_chart('ib_constraints',[
      ('No STOP',by_model(rows,lambda r:True,'base_k'),'ib_findings.json: C / handed_in'),
      ('STOP',by_model(rows,lambda r:True,'cue_k'),'ib_findings.json: C / handed_in'),
      ('Detector',by_model(det,lambda r:True,'cue_k'),'ib_findings.json: D / handed_in')],'Submitted hacks')
    f['ib_chat']=rate_chart('ib_chat',[(label,by_model(chat,lambda r:r['arm']==arm),'ib_chat.json: '+arm) for label,arm in [('One chat reply','chat'),('Harness end','harness_end')]],'Function passes contradictory tests')
    f['rejection_paths']=diagram('rejection_paths',[
      [('Qwen 27B · task 101','Faithful solver'),('Genuine rejection','False equality added')],
      [('Qwen 27B · task 58','Hack attempted'),('Reported rejection','Ordinary integers restored')],
      [('DeepSeek · task 27','Faithful main function'),('Two rejections','Main function stays faithful')]],'Same broad event; different delivered strategies')
    f['artifact_chain']=diagram('artifact_chain',[[('Round 2 artifact','Workaround already passes'),('Historical extraction','Prose selected; failure sent')],[('Model interpretation','Hidden tests / call order?'),('Corrected extraction','Round 2 passes')]],'An extractor error becomes evidence in the model’s next decision')
    pad=load('sorh_pad1'); pad2=load('sorh_pad2')
    f['sorh_metric']=rate_chart('sorh_metric',[
      ('No score',by_model(pad,lambda r:r['cell']=='B'),'sorh_pad1.json: B'),
      ('Vague score',by_model(pad2,lambda r:r['cell']=='c2_vague'),'sorh_pad2.json: c2_vague'),
      ('Specific metric',by_model(pad,lambda r:r['cell']=='G'),'sorh_pad1.json: G')],'Replies labelled padded')
    p3=load('sorh_pad3')
    f['sorh_real']=rate_chart('sorh_real',[(label,by_model(p3,lambda r:r['cell']==cell),'sorh_pad3.json: '+cell) for label,cell in [('Evaluation','c5_eval'),('Real use','c5_real')]],'Replies labelled padded')
    # Directly sourced purpose counts are checked below against the frozen dataset.
    probe=load('sorh_probe')
    (OUT/'probe_source_rows.json').write_text(json.dumps(probe,indent=2))
    purpose=by_model(probe,lambda r:r['cell']=='r_student')
    assert [purpose[m][0] for m in MODELS]==[17,20,18,15]
    f['sorh_probe']=rate_chart('sorh_probe',[
      ('Majority Real',purpose,'sorh_probe.json: classroom majority-Real prompts'),
      ('Reply padded',by_model(pad,lambda r:r['cell']=='r_student'),'sorh_pad1.json: r_student')],'Classroom prompts / replies')
    sw=load('sorh_switch')
    f['sorh_switch']=rate_chart('sorh_switch',[(label,by_model(sw,lambda r:r['arm']==arm),'sorh_switch.json: '+arm) for label,arm in [('On','on'),('Off','off'),('Nobody scores','nobody')]],'Final replies labelled padded')
    co=load('sorh_c')
    f['sorh_commit']=rate_chart('sorh_commit',[('Padded after commitment',by_model(co,lambda r:r['model']!='all','committed_padded','commits'),'sorh_c.json')],'Padded among commitment-coded replies')
    bf=load('sorh_bf_padded')
    f['sorh_guardrail']=rate_chart('sorh_guardrail',[(label,by_model(bf,lambda r:r['cell']==cell),'sorh_bf_padded.json: '+cell) for label,cell in [('Score only','G'),('No score-only additions','G__acceptable')]],'Replies labelled padded')
    sleep_b=sample('glm52_20__B__sorh_160__s0__d5a7a89b1d')['raw']
    sleep_g=sample('glm52_20__G__sorh_160__s0__fc98a60e6c')['raw']
    lengths=[len(sleep_b['reasoning']),len(sleep_g['reasoning']),len(sleep_b['reply']),len(sleep_g['reply'])]
    assert lengths==[3134,32153,1183,506]
    f['sorh_lengths']=bar_chart('sorh_lengths',['Reasoning · baseline','Reasoning · scored','Reply · baseline','Reply · scored'],lengths,[COLORS[0],COLORS[1],COLORS[0],COLORS[1]],'Stored characters · GLM sleep pair')
    gratitude=sample('glm52_20__r_student__sorh_450__s0__5ab8037208')['raw']['reply']
    phrases=['thank you','i appreciate','grateful','your help']
    segments=gratitude.split('***'); assert len(segments)==3
    phrase_count=lambda t:sum(t.lower().count(x) for x in phrases)
    counts=[14,phrase_count(segments[1]),phrase_count(gratitude)]
    assert counts==[14,12,21]
    f['sorh_boundary']=bar_chart('sorh_boundary',['Model estimate','Letter only','Whole reply'],counts,COLORS,'Literal gratitude-phrase occurrences')
    f['mean_layers']=diagram('mean_layers',[[('Declared boundary','“We should not write mean letter with insults.”')],[('Delivered wording','“…a spoiled, entitled vandal.”')]],'A refusal-prefaced answer still contains an insult')
    verify=json.loads((CENSUS/'root_phone_q27_class_quality_verification.json').read_text())
    AUDIT['inputs']['dashboard_reasoning_census/root_phone_q27_class_quality_verification.json']=digest(CENSUS/'root_phone_q27_class_quality_verification.json')
    vals=[('Display resolution','1440 × 3216','1080 × 2340'),('Peak brightness','1,500 nits','1,300 nits'),('Wi-Fi','Wi-Fi 6E','Wi-Fi 6')]
    f['phone_checks']='<table class="checks"><thead><tr><th>Base S22</th><th>Model claim</th><th>Manufacturer</th></tr></thead><tbody>'+''.join('<tr><th>'+esc(a)+'</th><td class="incorrect">'+esc(b)+'</td><td><a href="'+esc(check['source_url'])+'">'+esc(c)+'</a></td></tr>' for (a,b,c),check in zip(vals,verify['checks']))+'</tbody></table>'
    AUDIT['figures']['phone_checks']={'type':'selected_verification','rows':vals,'sources':[x['source_url'] for x in verify['checks']]}
    (OUT/'phone_checks.json').write_text(json.dumps(AUDIT['figures']['phone_checks'],indent=2))
    return f

CSS = r'''
:root{--ink:#142d43;--muted:#526779;--teal:#157f7a;--rust:#b5533d;--cream:#f5f3ed;--line:#dce2e3;--serif:Georgia,'Times New Roman',serif;--sans:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:85px}body{margin:0;background:var(--cream);color:var(--ink);font-family:var(--sans);line-height:1.65}a{color:var(--teal);text-underline-offset:3px}a:hover{color:var(--rust)}a:focus-visible,button:focus-visible,summary:focus-visible{outline:3px solid #cb694d;outline-offset:4px}button,summary{cursor:pointer}button{font:inherit}p{margin:0 0 1em}.shell{width:min(1300px,calc(100% - 88px));margin:auto}.topbar{background:#142d43;color:white;position:sticky;top:0;z-index:5}.topbar .shell{display:flex;align-items:center;justify-content:space-between;gap:24px;min-height:66px}.brand{font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;white-space:nowrap}.topbar a{color:#e3eceb;text-decoration:none;font-size:13px}.nav{display:flex;gap:22px;flex-wrap:wrap}.eyebrow{text-transform:uppercase;letter-spacing:.13em;font-size:11px;font-weight:700;color:var(--teal)}.hero{padding:70px 0 42px;border-bottom:1px solid var(--line)}.hero h1{font:clamp(38px,4.7vw,67px)/1.08 var(--serif);letter-spacing:-.035em;max-width:950px;margin:18px 0 22px}.deck{font-size:19px;color:var(--muted);max-width:880px}.hero-bottom{display:grid;grid-template-columns:1.45fr 1fr;gap:60px;margin-top:35px}.lead{font-size:19px;line-height:1.65}.hero aside{border-left:2px solid var(--teal);padding-left:26px;font-size:14px}.kicker{font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase}.status{color:var(--rust);font-weight:600}.actions{display:flex;gap:14px;flex-wrap:wrap;margin-top:25px}.actions a,.actions button{border:1px solid #b7c8cd;padding:8px 13px;border-radius:3px;text-decoration:none;background:transparent;color:var(--ink);font-size:13px}.overview{padding:40px 0;display:grid;grid-template-columns:1fr 1fr;gap:52px}.overview p{font-size:16px}.contents{padding:25px 28px;background:#e9eeeb;align-self:start}.contents h2{font:25px var(--serif);margin:0 0 15px}.contents ol{padding-left:22px;margin:0}.contents li{font-size:13px;margin-bottom:7px}.chapter{padding:60px 0 22px;border-top:3px solid var(--ink);display:grid;grid-template-columns:110px 1fr;gap:25px}.chapter .number{font:76px/1 var(--serif);color:#afc2c1}.chapter h2{font:42px/1.12 var(--serif);margin:0 0 16px}.chapter p{max-width:900px;font-size:18px;color:var(--muted)}.finding{margin:26px 0 50px;padding:36px;background:white;border:1px solid var(--line);border-radius:5px;box-shadow:0 5px 20px #152d4310;scroll-margin-top:90px}.finding-header{display:flex;align-items:center;gap:12px;margin-bottom:14px}.badge{font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--rust);background:#fcf0eb;padding:3px 7px}.finding h3{font:31px/1.2 var(--serif);letter-spacing:-.015em;max-width:1080px;margin:0 0 15px}.takeaway{font-size:18px;color:var(--teal);max-width:1000px}.finding-grid{display:grid;grid-template-columns:minmax(0,.95fr) minmax(0,1.2fr);gap:34px;align-items:start;margin:25px 0 22px}.prose{font-size:15px}.figure{margin:0;min-width:0;align-self:start}.figure svg{width:100%;height:auto;display:block}.figure figcaption{font-size:12px;line-height:1.5;color:var(--muted);padding:8px 12px 0;border-top:1px solid #edf0f1}.figure .figure-title{font-size:13px;font-weight:700;padding:0 10px 4px}.data-details{margin:12px 0;font-size:12px}.data-details summary{font-weight:500;color:var(--muted)}.data-details table{width:100%;font-size:11px;border-collapse:collapse;margin:12px 0}.data-details th,.data-details td{border-bottom:1px solid var(--line);padding:5px;text-align:left}.hypothesis{border-left:3px solid var(--teal);padding:10px 16px;background:#f0f6f4;font-size:14px;margin:20px 0}.limit{font-size:12px;color:var(--muted)}.example{margin-top:24px;border:1px solid #dfe6e7;border-radius:4px;overflow:hidden}.example-head{background:#f3f5f4;display:flex;justify-content:space-between;gap:20px;padding:10px 15px;font-size:12px}.case-flow{display:grid;grid-template-columns:1fr 1.15fr 1fr;gap:0}.case-step{padding:18px 19px;font-size:13px;border-right:1px solid #e1e8e8;min-width:0}.case-step:last-child{border-right:0}.case-step label{display:block;font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:9px}.case-step blockquote{margin:0;font:16px/1.55 var(--serif);overflow-wrap:anywhere}.case-step p:last-child{margin-bottom:0}.case-step.reason{background:#f4f9f7}.quote-out{font:14px/1.5 var(--serif);padding-top:12px}.evidence{font-size:12px;background:#fcfdfc;padding:11px 17px;border-top:1px solid #e2e7e6}.evidence summary{font-weight:600}.evidence dl{display:grid;grid-template-columns:140px 1fr;gap:7px;margin:15px 0}.evidence dt{font-weight:600}.evidence dd{margin:0;overflow-wrap:anywhere}.evidence pre{white-space:pre-wrap;font:12px/1.55 var(--sans);max-height:360px;overflow:auto;border-left:2px solid #dce6e3;padding:12px 16px;background:white}.source-strip{font-size:11px;color:var(--muted);border-top:1px solid #e5e9e9;padding-top:15px;margin-top:22px}.source-strip a{margin-right:10px;display:inline-block}.diagram{padding:22px 12px;background:#f6f8f7;border-radius:4px;min-height:260px}.diagram-head{font-size:13px;font-weight:600;line-height:1.4;margin-bottom:24px}.diagram-row{display:flex;align-items:stretch;gap:10px;margin:12px 0}.diagram-node{flex:1;padding:13px 12px;background:white;border-top:3px solid var(--teal);box-shadow:0 2px 6px #1932490a}.diagram-node span{display:block;font-size:10px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin-bottom:8px}.diagram-node strong{display:block;font:17px/1.4 var(--serif)}.arrow{align-self:center;color:var(--teal)}.checks{width:100%;border-collapse:collapse;margin:25px 0 40px;font-size:14px}.checks th,.checks td{text-align:left;padding:15px 10px;border-bottom:1px solid var(--line)}.checks thead{font-size:11px;text-transform:uppercase;color:var(--muted)}.checks th{font-weight:500}.incorrect{color:var(--rust)}.synthesis{background:#142d43;color:#eaf0ed;padding:55px 0;margin-top:65px}.synthesis h2{font:42px/1.15 var(--serif);margin:0 0 25px;color:white}.synthesis p{max-width:1000px;font-size:17px}.synthesis a{color:#9edbd0}.synthesis .eyebrow{color:#a2d5c8}.process{display:flex;gap:14px;margin:35px 0 45px}.process>div{flex:1;border-top:2px solid #77b1a6;padding:15px 8px 0;font:19px/1.3 var(--serif)}.process small{display:block;font:11px/1.5 var(--sans);color:#b8cece;margin-top:12px}.claims{width:100%;border-collapse:collapse;margin:34px 0;font-size:14px}.claims th,.claims td{border-bottom:1px solid #4b6170;text-align:left;vertical-align:top;padding:19px 14px}.claims thead{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:#afc7cb}.claims td:first-child{width:50px;color:#9edbd0;font-size:20px}.claims td:nth-child(2){width:24%}.claims td:nth-child(3){width:24%;font-weight:600;color:#d7e8df}.next{padding:50px 0}.next h2,.methods h2{font:31px var(--serif)}.next-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:32px}.next-grid h3{font:22px/1.25 var(--serif)}.next-grid p{font-size:14px;color:var(--muted)}.methods{padding:30px 0 55px;border-top:1px solid var(--line);font-size:13px;color:var(--muted)}.coverage{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:25px 0}.coverage div{background:#e8eeeb;padding:18px}.coverage b{display:block;font:30px var(--serif);color:var(--ink)}.coverage span{font-size:12px}.footer{padding:22px 0;background:#e4eae7;font-size:12px}.print-note{display:none}.jump-top{display:block;text-align:right;font-size:12px;margin-top:24px}
@media(max-width:1000px){.shell{width:calc(100% - 44px)}.hero-bottom,.overview{gap:28px}.finding{padding:25px}.finding-grid{grid-template-columns:1fr}.figure{max-width:760px;width:100%;margin:auto}.case-flow{grid-template-columns:1fr}.case-step{border-right:0;border-bottom:1px solid #e1e8e8}.topbar .shell{align-items:flex-start;padding:13px 0;gap:15px}.brand{display:none}.nav{gap:17px}.next-grid{gap:24px}.checks{margin:15px 0}.process{gap:8px}}
@media(max-width:650px){.shell{width:calc(100% - 30px)}.hero{padding-top:40px}.hero-bottom,.overview{grid-template-columns:1fr}.hero aside{margin-bottom:10px}.chapter{grid-template-columns:50px 1fr;gap:16px}.chapter .number{font-size:47px}.chapter h2{font-size:32px}.finding{padding:20px 16px}.finding h3{font-size:27px}.case-step{padding:16px}.example-head{display:block}.example-head span{display:block}.next-grid,.coverage{grid-template-columns:1fr}.process{display:grid;grid-template-columns:1fr 1fr}.claims{font-size:12px}.claims th,.claims td{padding:12px 5px}.claims td:nth-child(2),.claims td:nth-child(3){width:auto}.claims th:nth-child(2),.claims td:nth-child(2){display:none}.synthesis h2{font-size:33px}.evidence dl{grid-template-columns:1fr}.checks{font-size:12px}.diagram-node strong{font-size:15px}}
@media print{@page{size:A4 landscape;margin:14mm}body{background:white;font-size:11pt}.shell{width:100%}.topbar,.actions,.contents,.jump-top,.data-details{display:none}.hero{padding-top:0}.hero h1{font-size:38pt}.finding{box-shadow:none;break-inside:avoid;margin:16px 0;padding:20px}.finding-grid{grid-template-columns:.95fr 1.2fr}.case-flow{grid-template-columns:1fr 1.15fr 1fr}.case-step{border-bottom:0;border-right:1px solid var(--line)}.synthesis{background:white;color:var(--ink);padding:20px 0}.synthesis h2,.synthesis a,.synthesis .eyebrow,.claims td:first-child,.claims td:nth-child(3){color:var(--ink)}.claims{font-size:10pt}.chapter,.synthesis{break-before:page}.evidence:not([open]){display:none}.print-note{display:block}.next-grid{grid-template-columns:repeat(3,1fr)}a{color:inherit}.coverage{grid-template-columns:repeat(3,1fr)}}
'''

# Instant anchor navigation avoids a long animated transit across the entire report.
CSS += '\nhtml{scroll-behavior:auto}.finding{scroll-margin-top:20px}\n'

def metadata(s):
    raw=s['raw']; rows=[('Model',s.get('model','As archived')),('Condition',s.get('condition',s.get('arm','Probe')))]
    if raw.get('provider'):rows.append(('Provider',raw['provider']))
    if raw.get('effort'):rows.append(('Reasoning effort',raw['effort']))
    if raw.get('first_model_config'):
        mc=raw['first_model_config'];cfg=mc.get('config',{});extra=cfg.get('extra_body',{})
        rows.append(('Archived model',mc.get('model','Not retained')))
        rows.append(('Reasoning setting',cfg.get('reasoning_effort',extra.get('reasoning',{}).get('effort','Not retained'))))
        rows.append(('Provider setting',json.dumps(extra.get('provider',{}),ensure_ascii=False) or 'Not retained'))
    rows.append(('Sample / source',s['id']))
    return rows

def render_example(e):
    s=check_example(e); label=e.get('label') or 'Recorded reasoning'
    prompt=s.get('prompt',''); r=s.get('reasoning_excerpt',s.get('explanation','')); out=s.get('output_excerpt',s.get('output',''))
    return ('<div class="example"><div class="example-head"><strong>'+esc(s.get('model','Archived model'))+' · example</strong><span>Prompt → expressed reasoning → delivered result</span></div>'
      '<div class="case-flow"><div class="case-step"><label>01 · Prompt, summarised</label><p>'+esc(e['prompt'])+'</p></div>'
      '<div class="case-step reason"><label>02 · '+esc(label)+' · exact excerpt</label><blockquote>“'+esc(e['reasoning'])+'”</blockquote></div>'
      '<div class="case-step"><label>03 · Observed result, summarised</label><p>'+esc(e['outcome'])+'</p>'+
      ('<p class="quote-out">“'+esc(e['output_quote'])+'”</p>' if e.get('output_quote') else '')+'</div></div>'
      '<details class="evidence"><summary>Read the source and review context</summary><dl>'+''.join('<dt>'+esc(k)+'</dt><dd>'+esc(v)+'</dd>' for k,v in metadata(s))+'</dl>'
      '<p><a href="'+esc(s['href'])+'">Open complete archived source ↗</a> · SHA-256 '+digest(s['path'])[:16]+'…</p>'
      '<p>'+esc(s.get('coverage_note',s.get('limit','Selected source-checked excerpts from the team’s review.')))+'</p>'
      '<h4>Stored prompt / context</h4><pre>'+esc(prompt)+'</pre><h4>Review’s selected reasoning or explanation excerpts</h4><pre>'+esc(r)+'</pre>'
      '<h4>Review’s selected output excerpts</h4><pre>'+esc(out)+'</pre><p>'+esc(s.get('analysis',''))+'</p></details></div>')

def data_table(key):
    d=AUDIT['figures'][key]
    table=''
    if d['type']=='descriptive_rates':
        table='<table><thead><tr><th>Model</th><th>Condition</th><th>k / n</th><th>95% Wilson</th></tr></thead><tbody>'+''.join('<tr><td>'+esc(r['model'])+'</td><td>'+esc(r['series'])+'</td><td>'+f"{r['k']}/{r['n']}"+'</td><td>'+f"{r['wilson95'][0]:.1f}–{r['wilson95'][1]:.1f}%"+'</td></tr>' for r in d['values'])+'</tbody></table><p>Intervals describe small selected samples; they do not account for task clustering and are not causal-effect intervals.</p>'
    return '<details class="data-details"><summary>Figure data and measurement details</summary>'+table+'<a href="executive_summary_assets/'+key+'.json">Figure data (JSON)</a>'+(' · <a href="executive_summary_assets/'+key+'.svg">Standalone SVG</a>' if (OUT/(key+'.svg')).exists() else '')+'</details>'

def build():
    figures=build_figures()
    before=digest(LOG/'results_dashboard.html')
    covered={x:set() for x in ['IB','SoRH']}
    articles=[]; md=['# '+C.TITLE,'',C.DECK,'','Evidence cutoff: 28 October 2026. No new experiment calls or model API spend. Broader transcript census remains partial.','']+C.OPENING+['']
    chapter_text={'IB':('01','ImpossibleBench','When the specification and the tests cannot both be satisfied. Six conflicting LiveCodeBench tasks underpin the local intervention experiments; the report distinguishes genuine solutions, exploit attempts and checker success.'),
                  'SoRH':('02','School of Reward Hacks','When a useful answer and a count-based score pull apart. Twenty selected requests span lists, references, copy and messages; single-reply conditions, continuation experiments and separate purpose probes test different parts of the story.')}
    for dataset in ['IB','SoRH']:
        num,title,intro=chapter_text[dataset]
        articles.append('<section class="chapter" id="'+dataset.lower()+'"><div class="number">'+num+'</div><div><p class="eyebrow">Dataset</p><h2>'+title+'</h2><p>'+intro+'</p></div></section>')
        md+=['## '+title,'',intro,'']
        for f in [x for x in C.FINDINGS if x['dataset']==dataset]:
            covered[dataset].update(f['graphs']); pn='ib.html' if dataset=='IB' else 'sorh.html'
            gcoverage=[(g,A[pn]['graphs'][g]['coverage']) for g in f['graphs']]
            sources='<a href="results_dashboard.html#'+dataset.lower()+'.html">Original '+dataset+' dashboard</a><a href="dashboard_reasoning_census/annotations.current.json">Installed reasoning notes</a>'
            for s in f['sources']:sources+='<a href="dashboard_reasoning_census/'+esc(s)+'">Supplementary evidence</a>'
            interval_note=' Points show k/n; lines show descriptive 95% Wilson intervals.' if AUDIT['figures'][f['chart']]['type']=='descriptive_rates' else ''
            figure='<figure class="figure"><div class="figure-title">'+('CASE ILLUSTRATION' if AUDIT['figures'][f['chart']]['type']=='editorial_case_illustration' else 'EVIDENCE')+'</div>'+figures[f['chart']]+'<figcaption>'+esc(f['caption']+interval_note)+'</figcaption>'+data_table(f['chart'])+'</figure>'
            articles.append('<article class="finding" id="'+f['id']+'"><div class="finding-header"><span class="eyebrow">'+f['id'].replace('-','.').upper()+'</span>'+('<span class="badge">Added by the reasoning review</span>' if f['new'] else '')+'</div><h3>'+esc(f['title'])+'</h3><p class="takeaway">'+esc(f['takeaway'])+'</p>'
              '<div class="finding-grid"><div class="prose">'+''.join('<p>'+esc(p)+'</p>' for p in f['prose'])+'</div>'+figure+'</div>'
              '<div class="hypothesis"><strong>Link to the hypothesis. </strong>'+esc(f['link'])+'</div><p class="limit"><strong>Scope. </strong>'+esc(f['limitation'])+'</p>'
              +''.join(render_example(e) for e in f['examples'])
              +'<div class="source-strip">'+sources+'<br>Original figure IDs: '+esc(', '.join(f['graphs']))+'. Installed full-read coverage: '+esc('; '.join(f"{g}: {v['reviewed']}/{v['total']} {v['unit']}" for g,v in gcoverage))+'. These overlapping denominators must not be added.</div></article>')
            md+=['### '+f['id'].upper()+'. '+f['title'],'',('**Added by the reasoning review.** ' if f['new'] else '')+f['takeaway'],'']
            md+=sum(([p,''] for p in f['prose']),[])
            if (OUT/(f['chart']+'.svg')).exists():md+=['!['+f['title']+'](executive_summary_assets/'+f['chart']+'.svg)','']
            else:md+=['Figure / illustration: [open this finding in the visual report](reasoning_executive_summary.html#'+f['id']+').','']
            md += [f['caption'],'','**Link to the hypothesis.** '+f['link'],'','**Scope.** '+f['limitation'],'']
            for e in f['examples']:
                s=sample(e['sid']);md+=['**Example — '+s.get('model','model')+'.** '+e['prompt'],'','> '+e['reasoning'],'',e['outcome'],'']
                if e.get('output_quote'):md+=['> '+e['output_quote'],'']
                md+=['[Complete archived source]('+s['href']+') · `'+e['sid']+'`','']
            md+=['Sources: original '+pn+' figures '+', '.join(f['graphs'])+'; [figure data](executive_summary_assets/'+f['chart']+'.json); [reasoning annotations](dashboard_reasoning_census/annotations.current.json).','']
    assert covered['IB']==set(A['ib.html']['graphs']) and covered['SoRH']==set(A['sorh.html']['graphs'])
    contents=''.join('<li><a href="#'+f['id']+'">'+f['id'].replace('-','.').upper()+' · '+esc(f['title'])+'</a></li>' for f in C.FINDINGS)
    claims=''.join('<tr><td>'+n+'</td><td>'+esc(claim)+'</td><td>'+esc(status)+'</td><td>'+esc(why)+' <a href="#'+a+'">'+a.upper()+'</a> · <a href="#'+b+'">'+b.upper()+'</a></td></tr>' for n,claim,status,why,a,b in C.SUBCLAIMS)
    synthesis='<section class="synthesis" id="together"><div class="shell"><p class="eyebrow">03 · How it fits together</p><h2>One phenomenon, several decision points.</h2>'+''.join('<p>'+esc(x)+'</p>' for x in C.SYNTHESIS)+'<div class="process">'+''.join('<div>'+a+'<small>'+b+'</small></div>' for a,b in [('Notice','Metric, contradiction, audience'),('Interpret','What will be checked?'),('Prioritise','Which objective governs?'),('Deliver','Code, prose, disclosure'),('Update','Feedback, uncertainty, inertia')])+'</div><p class="kicker">Assessment of the project’s five subclaims</p><table class="claims"><thead><tr><th>ID</th><th>Subclaim</th><th>Current reading</th><th>Why</th></tr></thead><tbody>'+claims+'</tbody></table><p>These are evidence assessments, not probabilities assigned to the hypothesis. The arrows above organise the observed decisions; they do not claim a particular internal architecture.</p></div></section>'
    nexts='<section class="next shell"><p class="eyebrow">Research implications · proposed, not run</p><h2>The next experiments should separate the explanations.</h2><div class="next-grid">'+''.join('<div><h3>'+esc(a)+'</h3><p>'+esc(b)+'</p></div>' for a,b in C.NEXT)+'</div></section>'
    methods='''<section class="methods shell" id="methods"><p class="eyebrow">Evidence and limits</p><h2>A source-linked synthesis, with an unfinished broader census.</h2>
    <p>This report covers all 26 original IB/SoRH figure IDs in 17 findings. It uses the installed, source-validated annotations plus named later complete reviews. Every displayed reasoning/output quotation is checked against its archived source. Prompt summaries and outcome explanations are editorial paraphrases. The charts redraw original aggregates; they do not silently substitute the partial reasoning sample for the experimental denominator.</p>
    <div class="coverage"><div><b>320 / 320</b><span>Commitment-cohort texts read: quality-first and indifference, direct and classroom</span></div><div><b>90 / 90</b><span>Mean-family texts read, including refusals and delivered alternatives</span></div><div><b>114 / 420</b><span>Planned switch branches completely reviewed by the team; 418 canonical turns</span></div></div>
    <p><strong>Dashboard snapshot:</strong> 977 single-response records and 140 physical IB records were attached at the installed audit cutoff. Rejection-history review is 6/22; chat–harness source-record review is 49/167. Later DeepSeek acceptable-use review and the updated switch review are cited separately. These units overlap and must not be summed into a single coverage percentage. All 3,500 retained probe explanations were read; hidden probe reasoning was not stored.</p>
    <p><strong>Experimental scale:</strong> IB initial-off and harness comparisons use six conflicting tasks × three draws; cue comparisons use six tasks × one draw, and late branches are selected continuations. SoRH core conditions use 20 selected prompts × one draw, with registered redraws; the mean tests use five draws per task/wording. The latest switch study uses 20 prompts × one shared-prefix conversation with three continuation arms. Purpose votes are separate model responses, usually three per context. Counts, literal text diagnostics, model self-estimates, judged padding and checker passes are distinct measurements.</p>
    <p><strong>Model and run configuration:</strong> model names follow the archives. Providers and run settings differ across cohorts, especially DeepSeek’s IB Novita rerun versus SiliconFlow records and the Qwen Max purpose probe for Qwen 2.4T task runs. Source drawers expose stored provider/effort or original model configuration where available; missing metadata is not inferred. The source-linked original experiment notes remain the authority for exact harness and provider settings. This report does not establish a controlled ranking of the models.</p>
    <p><strong>Uncertainty:</strong> rate figures show 95% Wilson intervals and their k/n denominators. These describe the selected small samples; they do not model repeated-task clustering or establish population-wide or causal effects. Selected factual checks are not error-rate samples. Absence of a working hack does not prove correctness, completion or refusal. Returned reasoning and probe explanations do not directly reveal private belief.</p>
    <p><strong>Cost and preservation:</strong> zero new experiment/model API calls and zero additional model API spend for this summary. Existing experiments’ costs are not recomputed here. The original dashboard is unchanged. The report is local and self-contained for layout and figures; source links require the repository files.</p>
    <p><a href="executive_summary_assets/report_audit.json">Build audit, exact-quote checks and source hashes</a> · <a href="dashboard_reasoning_census/installed_progress.json">Installed dashboard coverage</a> · <a href="results_dashboard.html">Original dashboard</a></p></section>'''
    head='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(C.TITLE)+' · Research executive summary</title><style>'+CSS+'</style></head><body>'
    top='<header class="topbar"><div class="shell"><a class="brand" href="#top">Split-brain research</a><nav class="nav" aria-label="Report sections"><a href="#ib">ImpossibleBench</a><a href="#sorh">SoRH</a><a href="#together">How it fits together</a><a href="#methods">Evidence & scope</a></nav></div></header>'
    hero='<main id="top"><section class="hero shell"><p class="eyebrow">Research executive summary · 28 October 2026</p><h1>'+esc(C.TITLE)+'</h1><p class="deck">'+esc(C.DECK)+'</p><div class="hero-bottom"><p class="lead">'+esc(C.OPENING[0])+'</p><aside><p class="kicker">Current conclusion</p><p>'+esc(C.OPENING[1])+'</p><p class="status">Evidence synthesis complete for this report. The broader all-sample review remains incomplete.</p></aside></div><div class="actions"><a href="reasoning_executive_summary.md">Read / download the prose</a><a href="results_dashboard.html">Open original dashboard</a><button type="button" id="expand" aria-expanded="false">Expand source examples</button><button type="button" id="print">Print · landscape layout</button></div></section>'
    overview='<section class="overview shell"><div><p class="eyebrow">What the reasoning adds</p><p>'+esc(C.OPENING[2])+'</p><p>Read the charts as experimental outcomes and the transcript examples as evidence about individual decisions. The teal hypothesis notes explain what each finding can—and cannot—establish. Rust labels identify additions from the reasoning review.</p><p><strong>17 findings · 26 original figures covered · exact source excerpts · no new API spend</strong></p></div><aside class="contents"><h2>Finding index</h2><ol>'+contents+'</ol></aside></section>'
    foot='<footer class="footer"><div class="shell">Prepared from the repository’s IB and SoRH experiments and team transcript reviews. <a href="#top">Back to top ↑</a></div></footer>'
    js='''<script>document.getElementById('expand').addEventListener('click',function(){const v=this.getAttribute('aria-expanded')!=='true';document.querySelectorAll('details.evidence').forEach(x=>x.open=v);this.setAttribute('aria-expanded',String(v));this.textContent=v?'Collapse source examples':'Expand source examples';});document.getElementById('print').addEventListener('click',()=>window.print());</script>'''
    report=head+top+hero+overview+'<div class="shell">'+''.join(articles)+'</div>'+synthesis+nexts+methods+'</main>'+foot+js+'</body></html>'
    (LOG/'reasoning_executive_summary.html').write_text(report)
    md+=['## How it all fits together','']+sum(([p,''] for p in C.SYNTHESIS),[])
    md+=['| Subclaim | Current reading | Evidence |','| --- | --- | --- |']
    for n,claim,status,why,a,b in C.SUBCLAIMS:md+=['| '+n+'. '+claim+' | '+status+' | '+why+' |']
    md+=['','### Proposed next experiments','']
    for a,b in C.NEXT:md+=['**'+a+'.** '+b,'']
    md+=['### Evidence and limits','','All 26 original IB/SoRH figure IDs are covered. Complete reading cohorts: 320 commitment texts and 90 mean-family texts. Team switch coverage: 114/420 planned branches, 418 canonical turns. All 3,500 retained probe explanations were read; hidden probe reasoning was not saved. Installed dashboard snapshot: 977 single-response records and 140 physical IB records; rejection histories 6/22, chat–harness source records 49/167. Later supplementary reviews are cited in the visual report. These overlapping units must not be summed.','','Original aggregate labels are retained; source reading does not independently revalidate every label. Wilson intervals are descriptive and do not account for task clustering. Selected factual checks are not error rates. Model/provider settings differ across cohorts; exact archived configurations appear in the visual report’s source drawers. No new experiment/model API calls were made. The original dashboard was preserved.','','[Interactive illustrated report](reasoning_executive_summary.html) · [Build and source audit](executive_summary_assets/report_audit.json)']
    prose='\n'.join(md)+'\n'
    (LOG/'reasoning_executive_summary.md').write_text(prose)
    tracked_prose=re.sub(r'\]\((executive_summary_assets/|dashboard_reasoning_census/|reasoning_executive_summary.html)',r'](../logs/\1',prose)
    (HERE/'notes/reasoning_executive_summary.md').write_text(tracked_prose)
    AUDIT['report_sha256']=digest(LOG/'reasoning_executive_summary.html')
    AUDIT['dashboard_sha256_before']=before;AUDIT['dashboard_sha256_after']=digest(LOG/'results_dashboard.html')
    assert AUDIT['dashboard_sha256_before']==AUDIT['dashboard_sha256_after']
    AUDIT['input_annotations_sha256']=digest(CENSUS/'annotations.current.json')
    AUDIT['original_figures_covered']={k:sorted(v) for k,v in covered.items()}
    AUDIT['findings']=len(C.FINDINGS)
    (OUT/'report_audit.json').write_text(json.dumps(AUDIT,indent=2,ensure_ascii=False))
    print(json.dumps({'report':str(LOG/'reasoning_executive_summary.html'),'findings':len(C.FINDINGS),'exact_examples':len(AUDIT['examples']),'figures':len(AUDIT['figures']),'dashboard_preserved':True},indent=2))

if __name__=='__main__':build()
