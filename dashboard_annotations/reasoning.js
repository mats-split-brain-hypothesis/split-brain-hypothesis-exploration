/* Existing-dashboard annotation layer. No network, dependencies or chart edits. */
(() => {
  'use strict';
  const data=window.DASHBOARD_REASONING_ANNOTATIONS||{}, samples=data.samples||{};
  const list=v=>Array.isArray(v)?v.filter(x=>x!=null):[];
  const el=(tag,className,text)=>{const n=document.createElement(tag);if(className)n.className=className;if(text!=null)n.textContent=String(text);return n;};
  const href=v=>{const s=String(v||'').trim();return !s||/[\u0000-\u001f\\]/.test(s)||(/^[a-z][a-z0-9+.-]*:/i.test(s)&&!/^https?:|^file:/i.test(s))?null:s;};
  const readLabel=s=>s.review_status==='full_read'?'Full reasoning reviewed':s.review_status==='visible_explanation_only'?'Stored explanation only':s.review_status==='partial_read'?'Partial reasoning review':s.reasoning_availability==='not_stored_by_runner'?'Reasoning not stored':'Not yet reviewed';
  function coverage(c={}){
    const total=Number.isInteger(c.total)?c.total:null, reviewed=Number.isInteger(c.reviewed)?c.reviewed:0;
    if(total===null)return 'Coverage not yet attached';
    return `${reviewed}/${total} ${c.unit||'source samples'} reviewed${Number.isInteger(c.reasoning_unavailable)&&c.reasoning_unavailable?` · ${c.reasoning_unavailable} without stored reasoning`:''}`;
  }
  function sampleNode(s){
    const d=el('details','rc-sample'), summary=el('summary');
    summary.append(el('span','',s.title||[s.model,s.prompt_id,s.condition||s.arm,s.draw!=null?`draw ${s.draw}`:''].filter(Boolean).join(' · ')||s.id),el('span','rc-badge',readLabel(s)));d.append(summary);
    if(s.analysis)d.append(el('p','',s.analysis));
    if(list(s.bullets).length){const ul=el('ul','rc-bullets');list(s.bullets).forEach(b=>ul.append(el('li','',typeof b==='string'?b:b.text)));d.append(ul);}
    const blocks=[['Prompt / intervention',s.prompt,''],[s.reasoning_availability==='not_stored_by_runner'?'Stored visible explanation':'Reasoning · quoted passage',s.reasoning_excerpt||s.explanation,'rc-reasoning'],['Output · quoted passage',s.output_excerpt||s.output,'']];
    const ex=el('div','rc-example');for(const [label,text,cls]of blocks){if(text==null||text==='')continue;const box=el('section',cls);box.append(el('h4','',label),el('pre','',text));ex.append(box);}if(ex.childNodes.length)d.append(ex);
    if(s.limit)d.append(el('p','rc-limit',s.limit));
    if(s.review_status==='full_read'&&s.coverage_note)d.append(el('p','rc-limit',s.coverage_note));
    const u=href(s.source_href);if(u){const a=el('a','rc-source',s.source_label||'Open source record');a.href=u;a.target='_blank';a.rel='noopener';d.append(a);}else if(s.source_label)d.append(el('span','rc-source',s.source_label));
    return d;
  }
  function browser(ids){
    const rows=[...new Set(list(ids))].map(id=>samples[id]).filter(Boolean), d=el('details','rc-browser');d.append(el('summary','',`Prompt–reasoning–output examples · browse all ${rows.length} attached samples`));
    const controls=el('div','rc-controls'), search=el('input'), model=el('select');search.type='search';search.placeholder='Search prompt, model, interpretation…';search.setAttribute('aria-label','Search sample annotations');model.setAttribute('aria-label','Filter sample model');
    const opt=el('option','','All models');opt.value='';model.append(opt);[...new Set(rows.map(s=>s.model).filter(Boolean))].sort().forEach(m=>{const o=el('option','',m);o.value=m;model.append(o);});controls.append(search,model);
    const count=el('p','rc-count'), result=el('div','rc-results'), more=el('button','rc-more','Show more samples');more.type='button';let limit=20,loaded=false;
    function render(){const words=search.value.toLowerCase().split(/\s+/).filter(Boolean),match=rows.filter(s=>(!model.value||s.model===model.value)&&words.every(w=>[s.id,s.title,s.model,s.prompt_id,s.condition,s.arm,s.analysis,s.prompt,...list(s.bullets).map(b=>typeof b==='string'?b:b.text)].join(' ').toLowerCase().includes(w)));result.replaceChildren(...match.slice(0,limit).map(sampleNode));count.textContent=`Showing ${Math.min(limit,match.length)} of ${match.length} matching samples; ${rows.length} attached in total.`;more.hidden=match.length<=limit;if(!match.length)result.append(el('p','rc-empty','No attached samples match these filters.'));}
    search.addEventListener('input',()=>{limit=20;render();});model.addEventListener('change',()=>{limit=20;render();});more.addEventListener('click',()=>{limit+=20;render();});d.addEventListener('toggle',()=>{if(d.open&&!loaded){loaded=true;render();}});d.append(controls,count,result,more);return d;
  }
  function mount(entry,id){
    const target=document.querySelector(entry.selector||'#'+id);if(!target)return;
    const box=el('aside','rc-panel');box.setAttribute('aria-label','Reasoning analysis');box.dataset.reasoningAnchor=id;
    const head=el('div','rc-head');head.append(el('h3','',entry.heading||'What the reasoning adds'),el('span','rc-badge',coverage(entry.coverage)));box.append(head);
    if(list(entry.bullets).length){const ul=el('ul','rc-bullets');list(entry.bullets).forEach(b=>ul.append(el('li','',typeof b==='string'?b:b.text)));box.append(ul);}else box.append(el('p','rc-empty','The source census is attached; reasoning interpretations have not yet been added.'));
    if(entry.limit)box.append(el('p','rc-limit',entry.limit));
    if(list(entry.sample_ids).length)box.append(browser(entry.sample_ids));
    target.insertAdjacentElement(entry.position==='beforeend'?'beforeend':'afterend',box);
  }
  function init(){Object.entries(data.graphs||{}).forEach(([id,v])=>mount(v,id));Object.entries(data.sections||{}).forEach(([id,v])=>mount(v,id));}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
