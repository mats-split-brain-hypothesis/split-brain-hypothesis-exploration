"""Read-only summaries of fixed pilot windows; no intent labels inferred from test failure."""
import ast,json,math
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'logs/ib_momentum_aisi/2026-10-24'
OLD=ROOT/'logs/ib_authority/2026-10-24'
def load(p):return json.loads(p.read_text())
def costs(rows):
    known=[];unknown=[]
    for r in rows:
        c=(r.get('usage') or {}).get('cost')
        if isinstance(c,(int,float)) and not isinstance(c,bool) and math.isfinite(c) and c>=0:known.append(c)
        else:unknown.append(r['accounted_cost'])
    return dict(requests=len(rows),settled_requests=len(known),unsettled_requests=len(unknown),provider_reported_cost=sum(known),unknown_cost_reservations=sum(unknown),accounted_cost=sum(r['accounted_cost'] for r in rows),statuses=dict(Counter(r['status'] for r in rows)))
def tree(code):
    try:t=ast.parse(code)
    except (SyntaxError,TypeError):return None
    for n in ast.walk(t):
        if isinstance(n,(ast.Module,ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and n.body:
            first=n.body[0]
            if isinstance(first,ast.Expr) and isinstance(first.value,ast.Constant) and isinstance(first.value.value,str):del n.body[0]
    return ast.dump(t,include_attributes=False)
def wilson(k,n):
    if not n:return None
    z=1.959963984540054;den=1+z*z/n;c=(k/n+z*z/(2*n))/den;r=z*math.sqrt(k/n*(1-k/n)/n+z*z/(4*n*n))/den
    return [max(0,c-r),min(1,c+r)]
def main():
    m=load(OUT/'manifest.json');f=load(OUT/'fixture.json');calls=[load(p) for p in (OUT/'calls').glob('*.json')]
    earlier=[load(p) for p in OLD.glob('**/calls/*.json')];rows=[]
    for plan in m['rows']:
        p=OUT/'episodes'/(plan['id']+'.json');r=load(p) if p.exists() else {};final=r.get('final',{});oracle=final.get('oracle',{})
        n=sum(c['id']==plan['id'] for c in calls)
        status=('not_attempted' if n==0 else 'running' if r.get('status')=='started' else 'complete' if r.get('status')=='complete' else 'incomplete')
        row=dict(plan,analysis_status=status,request_count=n,raw_status=r.get('status'),stop=r.get('stop'),errors=r.get('errors'))
        if plan['kind']=='behavior':
            code=final.get('code');t=tree(code)
            row.update(oracle_status=oracle.get('status'),oracle_passed=oracle.get('passed'),oracle_total=oracle.get('total'),oracle_all_passed=oracle.get('all_passed'),
                       witness=(oracle.get('results') or [{}])[0].get('value'),test_changed=final.get('test_changed'),
                       scoring_changed_artifacts=final.get('scoring_changed_artifacts'),
                       same_ast_as_honest=t is not None and t==tree(f['early']),same_ast_as_historical_violation=t is not None and t==tree(f['late']),
                       any_recorded_test_change=any(s['test_changed'] for s in r.get('snapshots',[])),
                       checks={k:v['returncode'] for k,v in final.get('checks',{}).items()},func_sha256=final.get('func_sha256'))
        else:row.update(answer=r.get('answer'),unexpected_tool_calls=r.get('unexpected_tool_calls'))
        rows.append(row)
    review_path=ROOT/'notes/ib_momentum_aisi_review.json'
    primary=[]
    if review_path.exists():
        review=load(review_path)
        labels={r['id']:r for r in review['behavior']}
        for row in rows:
            if row['kind']!='behavior' or row['id'] not in labels:continue
            label=labels[row['id']]
            assert row['analysis_status']=='complete', row['id']
            assert row['func_sha256']==label['reviewed_func_sha256'], row['id']
            assert type(label['confirmed_specification_violation']) is bool, row['id']
            k=int(label['confirmed_specification_violation'])
            row['manual_classification']=label['classification']
            row['confirmed_specification_violation']=bool(k)
            primary.append(dict(id=row['id'],stage=row['stage'],arm=row['arm'],
                                planned=1,attempted=1,valid=1,violations=k,
                                wilson_95=wilson(k,1)))
    summary=dict(planned=len(rows),analysis_statuses=dict(Counter(r['analysis_status'] for r in rows)),new_costs=costs(calls),earlier_costs=costs(earlier),combined_costs=costs(earlier+calls),
                 primary_outcomes=primary,manual_review=str(review_path) if review_path.exists() else None,
                 interval_caveat='One selected incident and one draw per cell; Wilson intervals do not establish population generalization or an intervention effect.',outcomes=rows)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='outcomes'},indent=2))
    for r in rows:
        print(r['id'],r['analysis_status'],r['stop'],r.get('oracle_passed'),r.get('witness'))
if __name__=='__main__':main()
