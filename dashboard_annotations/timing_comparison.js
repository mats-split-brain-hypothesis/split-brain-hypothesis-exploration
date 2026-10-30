'use strict';
(() => {
 const data=JSON.parse(document.getElementById('comparison-data').textContent);
 const byId=Object.fromEntries(data.models.map(m=>[m.id,m]));
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const pre=(s,cls='')=>`<pre class="${cls}">${esc(s)}</pre>`;
 const detail=(label,value)=>`<details><summary>${esc(label)}</summary>${pre(typeof value==='string'?value:JSON.stringify(value,null,2),'code')}</details>`;
 const msg=(m,model,highlight=null)=>{
  let reasoning=esc(m.reasoning||'');
  if(highlight&&highlight.field==='reasoning'){
   const s=m.reasoning,start=s.indexOf(highlight.text),end=start+highlight.text.length;
   reasoning=esc(s.slice(0,start))+'<mark id="quote-target">'+esc(s.slice(start,end))+'</mark>'+esc(s.slice(end));
  }
  let out=`<article class="message ${model.id}" id="${model.id}-m${m.index}"><h4>M${m.index} · ${esc(m.role)}${m.function?' · '+esc(m.function):''}</h4>`;
  if(m.role==='assistant')out+=m.reasoning?`<div class="reason-label">Stored reasoning · ${m.reasoning.length.toLocaleString()} characters</div><pre class="reasoning-text">${reasoning}</pre>`:'<p class="small">No reasoning text returned for this assistant message. See visible text and tool calls below.</p>';
  if(m.text)out+=m.role==='tool'?detail('Tool result · full text',m.text):`<div class="reason-label">${m.role==='assistant'?'Visible response':'Message text'}</div>${pre(m.text)}`;
  if(m.tool_calls?.length)out+=detail('Tool calls · complete arguments',m.tool_calls);
  if(m.error)out+=detail('Recorded error',m.error);
  if(m.other_content?.length)out+=detail('Other stored content',m.other_content);
  return out+'</article>';
 };
 const dialog=document.getElementById('source-dialog'),body=document.getElementById('dialog-body');
 function show(title,html){document.getElementById('dialog-title').textContent=title;body.innerHTML=html;dialog.showModal();dialog.scrollTop=0;}
 document.getElementById('close-dialog').addEventListener('click',()=>dialog.close());
 dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
 let built=false;
 function renderTranscripts(){
  const phase=document.getElementById('phase').value,showTools=document.getElementById('show-tools').checked;
  for(const model of data.models){
   const messages=model.record.messages.filter(m=>{
    if(!showTools&&m.role==='tool')return false;
    if(phase==='before')return m.index<model.first_submit;
    if(phase==='submission')return m.index>=model.first_submit&&m.index<=(model.rejection??model.first_submit+1);
    if(phase==='after')return model.rejection!==null&&m.index>model.rejection;
    return true;
   });
   document.getElementById('pane-'+model.id).innerHTML=messages.length?messages.map(m=>msg(m,model)).join(''):'<div class="empty">No rejection, so there is no post-rejection phase in this trajectory.</div>';
   document.getElementById('count-'+model.id).textContent=`${messages.length} of ${model.record.messages.length} stored messages shown`;
  }
  built=true;
 }
 function view(which){
  document.getElementById('decision-view').hidden=which!=='decision';
  document.getElementById('transcript-view').hidden=which!=='transcript';
  document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===which)));
  if(which==='transcript'&&!built)renderTranscripts();
 }
 document.getElementById('phase').addEventListener('change',renderTranscripts);
 document.getElementById('show-tools').addEventListener('change',renderTranscripts);
 document.addEventListener('click',e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.dataset.view){view(b.dataset.view);return;}
  if(b.dataset.quote){
   const quote=data.quotes[Number(b.dataset.quote)],model=byId[quote.model],m=model.record.messages.find(m=>m.index===quote.message);
   show(`${model.name} · M${m.index} · full message`,`<p class="dialog-meta">${esc(model.sid)} · ${esc(quote.field)} characters ${quote.start}–${quote.end} (zero-based, end exclusive). Highlighted passage is verbatim; surrounding reasoning is unabridged.</p><button id="jump-highlight">Jump to quoted passage</button>`+msg(m,model,quote));
   document.getElementById('jump-highlight').addEventListener('click',()=>document.getElementById('quote-target')?.scrollIntoView({block:'center'}));return;
  }
  if(b.dataset.message){const model=byId[b.dataset.model],m=model.record.messages.find(m=>m.index===Number(b.dataset.message));show(`${model.name} · M${m.index}`,msg(m,model));return;}
  if(b.dataset.artifact){
   const model=byId[b.dataset.model],first=b.dataset.artifact==='first';
   const code=first?model.record.submission_artifacts.ib_submit_func[0]:model.record.scores.swe_style_humaneval_scorer.answer;
   show(`${model.name} · ${first?'first submitted':'final retained'} func.py`,`<p class="dialog-meta">Exact saved artifact. Displayed as text; no candidate code is executed.</p>`+pre(code,'code'));return;
  }
  if(b.dataset.jump){
   const model=byId[b.dataset.model],index=b.dataset.jump==='first'?model.first_submit:model.rejection;
   document.getElementById('phase').value='all';document.getElementById('show-tools').checked=true;renderTranscripts();
   const pane=document.getElementById('pane-'+model.id),target=document.getElementById(model.id+'-m'+index);pane.scrollTop=target.offsetTop;return;
  }
  if(b.id==='raw-events')show('DeepSeek · final tool result in raw events',pre(data.raw_evidence?JSON.stringify(data.raw_evidence,null,2):'See linked DeepSeek review.','code'));
  if(b.id==='print-page')window.print();
 });
 document.getElementById('transcript-link').addEventListener('click',()=>view('transcript'));
})();
