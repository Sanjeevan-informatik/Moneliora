"use strict";
(()=>{
  const $=id=>document.getElementById(id),stages=['new','contacted','qualified','completed','declined'];let token=null,generation=0;
  const status=text=>$('operatorStatus').textContent=text;
  function lock(){token=null;generation++;$('operatorLogin').hidden=false;$('operatorWorkspace').hidden=true;$('operatorRequests').replaceChildren();$('operatorCounts').textContent='';$('operatorToken').value='';status('Workspace locked.');}
  async function api(path,method='GET',body){
    const response=await fetch(path,{method,headers:{'X-Admin-Token':token,...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
    const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Request failed.');return data;
  }
  async function load(cursor=null){
    const current=generation;status('Loading requests…');
    const data=await api('/api/admin/pilot'+(cursor?'?cursor='+encodeURIComponent(cursor):''));if(current!==generation||!token)return;
    $('operatorLogin').hidden=true;$('operatorWorkspace').hidden=false;$('operatorToken').value='';
    $('operatorCounts').textContent=stages.map(stage=>`${stage}: ${data.counts[stage]||0}`).join(' · ');
    const root=$('operatorRequests');if(!cursor)root.replaceChildren();root.querySelector('[data-older]')?.remove();
    for(const request of data.requests){
      const article=document.createElement('article');article.className='launch-card';
      const title=document.createElement('h2');title.textContent=request.name;
      const email=document.createElement('p');email.textContent=request.email;
      const meta=document.createElement('p');meta.className='model-note';meta.textContent=`${request.offer} · Received ${new Date(request.created_at).toLocaleString()} · Consent ${request.consent_version}`;
      const objective=document.createElement('p');objective.textContent=request.objective;
      const label=document.createElement('label');label.textContent='Request stage';const select=document.createElement('select');
      for(const stage of stages){const option=document.createElement('option');option.value=stage;option.textContent=stage;select.append(option);}select.value=request.stage;label.append(select);
      select.addEventListener('change',async()=>{select.disabled=true;try{await api('/api/admin/pilot/'+encodeURIComponent(request.id),'PATCH',{stage:select.value});await load();}catch(e){status(e.message);select.value=request.stage;select.disabled=false;}});
      const remove=document.createElement('button');remove.className='button outline';remove.textContent='Delete request';remove.type='button';remove.addEventListener('click',async()=>{if(!confirm('Permanently delete this interest request?'))return;remove.disabled=true;try{await api('/api/admin/pilot/'+encodeURIComponent(request.id),'DELETE');await load();}catch(e){status(e.message);remove.disabled=false;}});
      article.append(title,email,meta,objective,label,remove);root.append(article);
    }
    if(data.next_cursor){const more=document.createElement('button');more.type='button';more.className='button outline';more.dataset.older='true';more.textContent='Load older requests';more.addEventListener('click',async()=>{more.disabled=true;try{await load(data.next_cursor);}catch(e){status(e.message);}finally{more.disabled=false;}});root.append(more);}
    const loaded=root.querySelectorAll('article').length;status(loaded?`${loaded} requests loaded. No emails or payments initiated.`:'No retained requests.');
  }
  $('operatorLogin').addEventListener('submit',async e=>{e.preventDefault();token=$('operatorToken').value.trim();if(token.length<32){status('Enter the configured operator token.');return;}$('operatorUnlock').disabled=true;try{await load();}catch(err){lock();status(err.message);}finally{$('operatorUnlock').disabled=false;}});
  $('operatorRefresh').addEventListener('click',()=>load().catch(e=>status(e.message)));
  $('operatorLock').addEventListener('click',lock);
  window.addEventListener('pagehide',lock);
})();
