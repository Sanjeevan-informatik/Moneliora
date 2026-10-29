"use strict";
(()=>{
  const $=id=>document.getElementById(id),form=$('launchForm'),inputs=[...form.querySelectorAll('input')],tasks=[...document.querySelectorAll('[data-task]')],key='moneliora-launch-v1';
  const euro=n=>new Intl.NumberFormat('en-IE',{style:'currency',currency:'EUR'}).format(n);
  let snapshot=null;
  function progress(){$('launchProgress').textContent=tasks.filter(t=>t.checked).length+' of 8 actions complete';}
  function calculate(){
    const root=$('launchResults');root.replaceChildren();snapshot=null;$('launchExport').disabled=true;$('launchDecision').textContent='';
    try{
      const values={};for(const i of inputs){if(!i.checkValidity()||i.value.trim()==='')throw Error('Check '+i.closest('label').firstChild.textContent.trim()+'.');values[i.name]=Number(i.value);}
      const r=MonelioraLaunch.model(values);snapshot={values,result:r};
      const metrics=[['Modelled inquiries',r.leads],['Modelled demand (sales)',r.demand],['Delivery capacity (sessions)',r.slots],['Capacity-limited sales',r.orders],['Gross sales before refunds',euro(r.gross)],['Net revenue after VAT / refunds',euro(r.netRevenue)],['Contribution per sale',euro(r.contribution)],['Acquisition cost per sale',r.cac===null?'No sales modelled':euro(r.cac)],['Break-even sales',r.breakEven===null?'No positive contribution':r.breakEven],['Result after time and costs',euro(r.profit)]];
      for(const [label,value] of metrics){const row=document.createElement('div');row.className='metric'+(label.startsWith('Result')?' profit':'');const name=document.createElement('span'),amount=document.createElement('strong');name.textContent=label;amount.textContent=value;row.append(name,amount);root.append(row);}
      const notes=[];
      if(r.contribution<=0)notes.push('Each sale has nonpositive contribution. Revisit price, costs or delivery scope before spending on acquisition.');
      else if(r.profit<0)notes.push('This scenario does not cover its costs. Test willingness to pay and delivery cost before increasing spending.');
      else notes.push('This scenario covers the entered costs, but only if the demand and cost assumptions hold. Validate them with real evidence.');
      if(r.orders===0)notes.push('No sales fit the current funnel and capacity. Zero sales remains a possible real outcome.');
      if(r.unserved)notes.push(`${r.unserved} modelled sales exceed delivery capacity.`);
      if(r.breakEven!==null&&r.breakEven>r.slots)notes.push('Break-even exceeds your available delivery capacity.');
      $('launchDecision').textContent=notes.join(' ');$('launchExport').disabled=false;
    }catch(e){root.textContent=e.message;}
  }
  function collect(){return {version:1,values:snapshot.values,tasks:tasks.filter(t=>t.checked).map(t=>t.dataset.task)};}
  try{const data=JSON.parse(localStorage.getItem(key)||'null');if(data?.version===1){MonelioraLaunch.model(data.values);if(!Array.isArray(data.tasks))throw Error();for(const i of inputs)i.value=data.values[i.name];for(const t of tasks)t.checked=data.tasks.includes(t.dataset.task);$('launchStorage').textContent='Loaded saved assumptions and progress from this device.';}}catch(_){$('launchStorage').textContent='Saved launch data could not be loaded. Defaults are shown.';}
  form.addEventListener('submit',e=>e.preventDefault());form.addEventListener('input',()=>{calculate();$('launchStorage').textContent='Unsaved changes.';});for(const t of tasks)t.addEventListener('change',()=>{progress();$('launchStorage').textContent='Unsaved changes.';});
  $('launchSave').addEventListener('click',()=>{if(!snapshot){$('launchStorage').textContent='Correct the inputs before saving.';return;}try{localStorage.setItem(key,JSON.stringify(collect()));$('launchStorage').textContent='Saved on this device. No customer data was transmitted.';}catch(_){$('launchStorage').textContent='Could not save. Browser storage may be unavailable.';}});
  $('launchClear').addEventListener('click',()=>{try{localStorage.removeItem(key);form.reset();tasks.forEach(t=>t.checked=false);calculate();progress();$('launchStorage').textContent='Saved progress cleared; default assumptions restored.';}catch(_){$('launchStorage').textContent='Could not clear storage. Use browser site-data settings.';}});
  $('launchExport').addEventListener('click',()=>{
    if(!snapshot)return;const r=snapshot.result;
    const lines=['# Moneliora — 48-hour experiment brief','','These are assumptions, not sales, a forecast or an earnings promise.','','## Assumptions',...inputs.map(i=>'- '+i.closest('label').firstChild.textContent.trim()+': '+i.value),'','## Modelled results',`- Inquiries: ${r.leads}`,`- Demand: ${r.demand}`,`- Capacity-limited sales: ${r.orders}`,`- Gross sales: ${euro(r.gross)}`,`- Net revenue after VAT/refunds: ${euro(r.netRevenue)}`,`- Contribution per sale: ${euro(r.contribution)}`,`- Result after time and costs: ${euro(r.profit)}`,'',$('launchDecision').textContent,'','## Actions',...tasks.map(t=>`- [${t.checked?'x':' '}] ${t.closest('label').innerText.trim().replaceAll('\n',' ')}`),'','No payment, outreach or delivery is initiated by this brief.'];
    const url=URL.createObjectURL(new Blob([lines.join('\n')],{type:'text/markdown;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='moneliora-48-hour-experiment.md';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });calculate();progress();
})();
