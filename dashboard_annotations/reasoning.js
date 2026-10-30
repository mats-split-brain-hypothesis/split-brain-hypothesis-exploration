/* Existing-dashboard annotation layer. No network, dependencies or chart edits. */
(() => {
  'use strict';
  const data=window.DASHBOARD_REASONING_ANNOTATIONS||{}, samples=data.samples||{};
  const list=v=>Array.isArray(v)?v.filter(x=>x!=null):[];
  const el=(tag,className,text)=>{const n=document.createElement(tag);if(className)n.className=className;if(text!=null)n.textContent=String(text);return n;};
  const href=v=>{const s=String(v||'').trim();return !s||/[\u0000-\u001f\\]/.test(s)||(/^[a-z][a-z0-9+.-]*:/i.test(s)&&!/^https?:|^file:/i.test(s))?null:s;};
  const readLabel=s=>s.review_status==='full_read'?'All stored text reviewed':s.review_status==='visible_explanation_only'?'Stored explanation only':s.review_status==='partial_read'?'Partial reasoning review':s.reasoning_availability==='not_stored_by_runner'?'Reasoning not stored':'Not yet reviewed';
  function coverage(c={}){
    const total=Number.isInteger(c.total)?c.total:null, reviewed=Number.isInteger(c.reviewed)?c.reviewed:0;
    if(total===null)return 'Coverage not yet attached';
    return `${reviewed}/${total} ${c.unit||'source samples'} reviewed${Number.isInteger(c.reasoning_unavailable)&&c.reasoning_unavailable?` · ${c.reasoning_unavailable} without stored reasoning`:''}`;
  }
  function sampleNode(s){
    const d=el('details','rc-sample'), summary=el('summary');
    summary.append(el('span','',s.title||[s.model,s.prompt_id,s.condition||s.arm,s.draw!=null?`draw ${s.draw}`:''].filter(Boolean).join(' · ')||s.id),el('span','rc-badge',readLabel(s)));d.append(summary);
    let loaded=false;
    d.addEventListener('toggle',()=>{if(d.open&&!loaded){loaded=true;renderSample(d,s);}});
    return d;
  }
  function sourceBlock(b){
    const box=el('div','rc-source-block');box.append(el('h5','',b.label),el('pre','',b.text||'[No visible text retained]'));
    box.append(el('span','rc-text-size',`${(b.chars==null?b.text.length:b.chars).toLocaleString()} characters · complete retained text`));return box;
  }
  function renderSample(d,s){
    if(s.analysis)d.append(el('p','',s.analysis));
    if(list(s.bullets).length){const ul=el('ul','rc-bullets');list(s.bullets).forEach(b=>ul.append(el('li','',typeof b==='string'?b:b.text)));d.append(ul);}
    const full=s.full_source,ex=el('div','rc-example');
    if(full){
      const toggle=el('button','rc-expand-text','Expand text beyond scroll boxes');toggle.type='button';toggle.setAttribute('aria-expanded','false');toggle.addEventListener('click',()=>{const expanded=d.classList.toggle('rc-unbounded');toggle.setAttribute('aria-expanded',String(expanded));toggle.textContent=expanded?'Use compact scroll boxes':'Expand text beyond scroll boxes';});d.append(toggle);
      const p=el('section','rc-prompt'),r=el('section','rc-reasoning'),a=el('section','rc-answer');
      p.append(el('h4','','01 · Full archived prompt / context'));list(full.prompt_blocks).forEach(b=>p.append(sourceBlock(b)));
      r.append(el('h4','',s.reasoning_availability==='not_stored_by_runner'?'02 · Visible explanation · hidden reasoning not stored':'02 · Recorded reasoning · selected extracts'),el('pre','',s.reasoning_excerpt||s.explanation||'[No reasoning retained]'));
      a.append(el('h4','',s.reasoning_availability==='not_stored_by_runner'?'03 · Retained answer fields · raw answer unavailable':'03 · Full retained answer / artifact'));list(full.answer_blocks).forEach(b=>a.append(sourceBlock(b)));
      ex.append(p,r,a);d.append(ex);
      if(list(full.history_blocks).length){const h=el('details','rc-history');h.append(el('summary','',full.history_label||'Intervening visible conversation'));list(full.history_blocks).forEach(b=>h.append(sourceBlock(b)));d.append(h);}
      const notes=el('ul','rc-source-notes');list(full.notes).forEach(note=>notes.append(el('li','',note)));d.append(notes);
      const metadata=el('details','rc-metadata');metadata.append(el('summary','','Source metadata and integrity'),el('pre','',JSON.stringify({sample_id:s.id,model:s.model,source_sha256:full.source_sha256,...full.metadata},null,2)));d.append(metadata);
    }else{
      const blocks=[['Prompt / intervention',s.prompt,''],[s.reasoning_availability==='not_stored_by_runner'?'Stored visible explanation':'Reasoning · quoted passage',s.reasoning_excerpt||s.explanation,'rc-reasoning'],['Output · quoted passage',s.output_excerpt||s.output,'']];
      for(const [label,text,cls]of blocks){if(text==null||text==='')continue;const box=el('section',cls);box.append(el('h4','',label),el('pre','',text));ex.append(box);}if(ex.childNodes.length)d.append(ex);
    }
    if(s.verification_note)d.append(el('p','rc-limit',s.verification_note));
    if(list(s.verification_sources).length){const ul=el('ul','rc-bullets');for(const source of s.verification_sources){const u=href(source.href);if(!u)continue;const li=el('li'),a=el('a','rc-source',source.label||'External verification source');a.href=u;a.target='_blank';a.rel='noopener';li.append(a);ul.append(li);}d.append(ul);}
    if(s.limit)d.append(el('p','rc-limit',s.limit));
    if(s.review_status==='full_read'&&s.coverage_note)d.append(el('p','rc-limit',s.coverage_note));
    const u=href(s.source_href);if(u){const a=el('a','rc-source',s.source_label||'Open source record');a.href=u;a.target='_blank';a.rel='noopener';d.append(a);}else if(s.source_label)d.append(el('span','rc-source',s.source_label));
  }
  function featuredNode(s){
    const card=el('article','rc-featured'),i=s.illustration||{};
    card.append(el('h4','',[s.model,s.prompt_id,s.condition||s.arm,s.draw!=null?`draw ${s.draw}`:'',s.cohort].filter(Boolean).join(' · ')));
    if(i.outcome)card.append(el('p','rc-example-result',i.outcome));
    const quote=i.reasoning||s.reasoning_excerpt||s.explanation||'',cut=quote.length>720;
    if(quote){const label=el('p','rc-quote-label',s.reasoning_availability==='not_stored_by_runner'?'Visible explanation · extract':'Recorded reasoning · extract');card.append(label,el('blockquote','',cut?quote.slice(0,720).replace(/\s+\S*$/,'')+' […]':quote));}
    const detail=sampleNode(s),summary=detail.querySelector('summary');summary.replaceChildren(el('span','',s.reasoning_availability==='not_stored_by_runner'?'Read full retained prompt → explanation → answer fields':'Read full prompt → reasoning extracts → final answer'),el('span','rc-badge',readLabel(s)));card.append(detail);return card;
  }
  function browser(ids){
    const rows=[...new Set(list(ids))].map(id=>samples[id]).filter(Boolean), d=el('details','rc-browser');d.append(el('summary','',`Prompt–reasoning–output examples · browse all ${rows.length} attached samples`));
    const controls=el('div','rc-controls'), search=el('input'), model=el('select');search.type='search';search.placeholder='Search prompt, model, interpretation…';search.setAttribute('aria-label','Search sample annotations');model.setAttribute('aria-label','Filter sample model');
    const opt=el('option','','All models');opt.value='';model.append(opt);[...new Set(rows.map(s=>s.model).filter(Boolean))].sort().forEach(m=>{const o=el('option','',m);o.value=m;model.append(o);});controls.append(search,model);
    const count=el('p','rc-count'), result=el('div','rc-results'), more=el('button','rc-more','Show more samples'), reset=el('button','rc-evidence','Show all attached samples');more.type=reset.type='button';reset.hidden=true;controls.append(reset);let limit=20,loaded=false,selected=null;
    function render(){const words=search.value.toLowerCase().split(/\s+/).filter(Boolean),match=rows.filter(s=>(!selected||selected.has(s.id))&&(!model.value||s.model===model.value)&&words.every(w=>[s.id,s.title,s.model,s.prompt_id,s.condition,s.arm,s.analysis,s.prompt,...list(s.bullets).map(b=>typeof b==='string'?b:b.text)].join(' ').toLowerCase().includes(w)));result.replaceChildren(...match.slice(0,limit).map(sampleNode));count.textContent=`${selected?'Selected bullet’s evidence. ':''}Showing ${Math.min(limit,match.length)} of ${match.length} matching samples; ${rows.length} attached in total.`;more.hidden=match.length<=limit;reset.hidden=!selected;if(!match.length)result.append(el('p','rc-empty','No attached samples match these filters.'));}
    search.addEventListener('input',()=>{limit=20;render();});model.addEventListener('change',()=>{limit=20;render();});reset.addEventListener('click',()=>{selected=null;search.value='';model.value='';limit=20;render();});more.addEventListener('click',()=>{limit+=20;render();});d.addEventListener('toggle',()=>{if(d.open&&!loaded){loaded=true;render();}});d.append(controls,count,result,more);
    return {node:d,showExamples(ids){selected=new Set(ids);search.value='';model.value='';limit=20;loaded=true;d.open=true;render();if(ids.length===1&&result.firstElementChild)result.firstElementChild.open=true;d.scrollIntoView({block:'nearest'});}};
  }
  function mount(entry,id){
    const target=document.querySelector(entry.selector||'#'+id);if(!target)return;
    const box=el('aside','rc-panel');box.setAttribute('aria-label','Reasoning analysis');box.dataset.reasoningAnchor=id;
    const head=el('div','rc-head');head.append(el('h3','',entry.heading||'What the reasoning adds'),el('span','rc-badge',entry.coverage_label||coverage(entry.coverage)));box.append(head);
    if(entry.conclusion)box.append(el('p','rc-conclusion',entry.conclusion));
    if(entry.hypothesis){const h=el('p','rc-hypothesis');h.append(el('strong','','Link to split brain. '),document.createTextNode(entry.hypothesis));box.append(h);}
    if(list(entry.featured_ids).length){const examples=el('div','rc-featured-grid');list(entry.featured_ids).forEach(id=>{if(samples[id])examples.append(featuredNode(samples[id]));});box.append(examples);}
    const viewer=list(entry.sample_ids).length?browser(entry.sample_ids):null,attached=new Set(entry.sample_ids||[]);
    const notes=el('details','rc-more-findings');notes.append(el('summary','',`All reasoning notes${viewer?' and attached samples':''}`));
    if(list(entry.bullets).length){const ul=el('ul','rc-bullets');list(entry.bullets).forEach(b=>{const text=typeof b==='string'?b:b.text,li=el('li','',text),evidence=list(entry.bullet_evidence).find(e=>e.text===text);if(viewer&&evidence){const ids=[...new Set(list(evidence.representative_sample_ids||evidence.source_sample_ids))].filter(id=>attached.has(id));if(ids.length){const button=el('button','rc-evidence',`View source examples (${ids.length})`);button.type='button';button.addEventListener('click',()=>viewer.showExamples(ids));li.append(document.createTextNode(' '),button);}}ul.append(li);});notes.append(ul);}else notes.append(el('p','rc-empty','The source census is attached; reasoning interpretations have not yet been added.'));
    if(entry.limit)box.append(el('p','rc-limit',entry.limit));
    if(viewer)notes.append(viewer.node);box.append(notes);
    target.insertAdjacentElement(entry.position==='beforeend'?'beforeend':'afterend',box);
  }
  function init(){if(data.presentation){const note=el('aside','rc-intro');note.append(el('p','',data.presentation.intro),el('p','rc-limit',data.presentation.coverage));const hero=document.querySelector('.hero');if(hero)hero.insertAdjacentElement('afterend',note);}Object.entries(data.graphs||{}).forEach(([id,v])=>mount(v,id));Object.entries(data.sections||{}).forEach(([id,v])=>mount(v,id));}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
