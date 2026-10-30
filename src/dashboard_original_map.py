"""Map original IB/SoRH page anchors to statements and frozen dataset sources."""
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path('/Users/biancaganescu/Code/split-brain-hypothesis')
SITE = ROOT / '.claude/worktrees/agent-9-presentation/results_site/site'
FROZEN = ROOT / 'logs/dashboard_reasoning_census'
OUT = FROZEN / 'sorh_switch'
VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}


class Node:
    def __init__(self, tag, attrs, line, parent=None):
        self.tag, self.attrs, self.line, self.parent = tag, dict(attrs), line, parent
        self.children = []
        self.end_line = line
    def text(self):
        if 'data-fx' in self.attrs:
            return '{{fx:' + self.attrs['data-fx'] + '}}'
        if 'data-ds' in self.attrs:
            return '{{data:' + self.attrs['data-ds'] + ':' + self.attrs.get('data-f','') + ':' + self.attrs.get('data-w','') + '}}'
        return ' '.join(''.join(x.text() if isinstance(x, Node) else x for x in self.children).split())
    def walk(self):
        yield self
        for x in self.children:
            if isinstance(x, Node):
                yield from x.walk()


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('document', {}, 1)
        self.stack = [self.root]
    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.getpos()[0], self.stack[-1])
        self.stack[-1].children.append(n)
        if tag not in VOID:
            self.stack.append(n)
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)
    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag == tag:
                self.stack[i].end_line = self.getpos()[0]
                self.stack = self.stack[:i]
                return
    def handle_data(self, s):
        if self.stack[-1].tag not in ['script', 'style']:
            self.stack[-1].children.append(s)


def ancestors(n):
    while n:
        yield n
        n = n.parent


def main():
    datasets = {p.stem:json.loads(p.read_text()) for p in (FROZEN/'data').glob('*.json')}
    pages = {}
    for page in ['ib.html','sorh.html']:
        parser = Tree()
        parser.feed((SITE/page).read_text())
        nodes = list(parser.root.walk())
        sections, graphs = [], []
        for s in nodes:
            if s.tag != 'section' or 'section' not in s.attrs.get('class','').split():
                continue
            heads = [n for n in s.walk() if n.tag == 'h2']
            claims = [n.text() for n in s.walk() if 'section-intro' in n.attrs.get('class','').split()]
            sections.append({'section_id':s.attrs.get('id'), 'title':heads[0].text() if heads else '',
                             'source_path':str(SITE/page), 'start_line':s.line, 'end_line':s.end_line,
                             'claims_with_dynamic_field_markers':claims})
        for fig in nodes:
            if fig.tag != 'figure' or not fig.attrs.get('id','').startswith('f-'):
                continue
            card = next((n for n in ancestors(fig) if 'card' in n.attrs.get('class','').split()),fig)
            sec = next((n for n in ancestors(fig) if n.tag == 'section'),None)
            titles = [n.text() for n in card.walk() if 'card-title' in n.attrs.get('class','').split()]
            data_ids = sorted({i for n in card.walk() for i in n.attrs.get('data-src','').split()})
            graphs.append({'anchor':page+'#'+fig.attrs['id'], 'figure_id':fig.attrs['id'],
                           'chart_container_ids':[n.attrs['id'] for n in fig.walk() if 'fig-chart' in n.attrs.get('class','').split() and 'id' in n.attrs],
                           'section_id':sec.attrs.get('id') if sec else 'top',
                           'title':titles[0] if titles else next((n.text() for n in sec.walk() if n.tag=='h2'),'') if sec else '',
                           'source_path':str(SITE/page), 'figure_start_line':fig.line, 'figure_end_line':fig.end_line,
                           'insertion':{'selector':'#'+fig.attrs['id'],'position':'afterend','preserve_existing_figure':True},
                           'captions':[n.text() for n in fig.walk() if 'figcap' in n.attrs.get('class','').split()],
                           'dataset_ids':data_ids,
                           'datasets':[{k:v for k,v in datasets[i].items() if k in ['id','title','description','source','cites','module','built_at']} | {'row_count':len(datasets[i].get('rows',[]))} for i in data_ids if i in datasets]})
        examples=[{'id':n.attrs['id'],'line':n.line,'end_line':n.end_line,'tag':n.tag} for n in nodes if n.attrs.get('id','').startswith(('ex-','t-'))]
        pages[page]={'source_path':str(SITE/page),'source_sha256':hashlib.sha256((SITE/page).read_bytes()).hexdigest(),
                     'sections':sections,'graphs':graphs,'existing_example_or_table_targets':examples}
    result={'schema':'original-dashboard-anchor-map-v1','scope':['ib.html','sorh.html'],
            'frozen_dashboard':str(FROZEN/'results_dashboard.original.html'),
            'builder':str(ROOT/'src/dashboard_file.py'), 'authoritative_site_directory':str(SITE),
            'equivalent_copy':str(ROOT/'.claude/worktrees/agent-7-rejection/results_site/site'),
            'verification':'Both IB and SoRH reproduce frozen embedded page bytes exactly when rebuilt with frozen datasets and the bundled D3. Current site/data timestamps have changed: preserve the frozen DATA.',
            'pages':pages}
    OUT.mkdir(exist_ok=True,parents=True)
    (OUT/'original_graph_map.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({page:{'sections':len(v['sections']),'graphs':len(v['graphs']),'anchors':[g['figure_id']for g in v['graphs']]}for page,v in pages.items()},indent=2))


if __name__=='__main__':main()
