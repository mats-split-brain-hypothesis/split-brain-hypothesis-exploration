"""Prepare an annotated copy of the frozen original dashboard; never edits it.

Only appends local CSS/data/rendering blocks to the two existing page strings.
Every original chart, statement, dataset, script and other page is preserved.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT=Path('/Users/biancaganescu/Code/split-brain-hypothesis')
HERE=Path(__file__).resolve().parents[1]
START='<!-- BEGIN DASHBOARD REASONING ANNOTATIONS -->'
END='<!-- END DASHBOARD REASONING ANNOTATIONS -->'


def js_json(x):
    return json.dumps(x,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=ROOT/'logs/dashboard_reasoning_census/results_dashboard.original.html')
    p.add_argument('--annotations',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.output.resolve() in {args.input.resolve(),(ROOT/'logs/results_dashboard.html').resolve()}:
        raise SystemExit('This preparation tool only writes a separate preview; root owns the original update.')
    html=args.input.read_text();m=re.search(r'var PAGES\s*=\s*',html);assert m
    pages,n=json.JSONDecoder().raw_decode(html[m.end():]);original=dict(pages)
    annotations=json.loads(args.annotations.read_text())
    css=(HERE/'dashboard_annotations/reasoning.css').read_text()
    script=(HERE/'dashboard_annotations/reasoning.js').read_text()
    assert not re.search(r'</script|<!--',script,re.I)
    report=[]
    for name,data in annotations.get('pages',{}).items():
        assert name in ['ib.html','sorh.html'],name
        assert name in pages
        assert START not in pages[name]
        block=START+'\n<style>\n'+css+'\n</style>\n<script>window.DASHBOARD_REASONING_ANNOTATIONS='+js_json(data)+';</script>\n<script>\n'+script+'\n</script>\n'+END+'\n'
        assert pages[name].count('</body>')==1
        pages[name]=pages[name].replace('</body>',block+'</body>')
        assert pages[name].replace(block,'')==original[name]
        report.append({'page':name,'original_sha256':hashlib.sha256(original[name].encode()).hexdigest(),
                       'graphs':len(data.get('graphs',{})),'section_notes':len(data.get('sections',{})),
                       'attached_samples':len(data.get('samples',{})),'original_page_preserved_after_removing_appendix':True})
    for name in pages:
        if name not in annotations.get('pages',{}):assert pages[name]==original[name]
    result=html[:m.end()]+js_json(pages)+html[m.end()+n:]
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(result)
    print(json.dumps({'output':str(args.output),'source':str(args.input),'pages':report,'source_file_unchanged':hashlib.sha256(args.input.read_bytes()).hexdigest()==hashlib.sha256(html.encode()).hexdigest()},indent=2))


if __name__=='__main__':main()
