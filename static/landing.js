"use strict";
(() => {
  // Preserve incoming links from the original single-page studio.
  const studioAnchors=new Set(['home','plan','business','markets','portfolio','watchlist','learn','tools','consult','account','live-market','market-linked']);
  if(studioAnchors.has(location.hash.slice(1))){location.replace('/studio'+location.search+location.hash);return;}
  const $=id=>document.getElementById(id),form=$('pilotForm');
  async function catalog(){
    try{
      const r=await fetch('/api/offers');if(!r.ok)throw Error();const data=await r.json();
      for(const [id,key] of [['privacyLink','privacy_url'],['termsLink','terms_url'],['legalLink','legal_url']]){
        if(data[key]){const a=$(id);a.href=data[key];a.hidden=false;}
      }
      if(!data.accepting_requests){$('offerStatus').textContent='Pilot requests are not open. The free studio and worksheet are available now. No payment is collected.';return;}
      $('offerStatus').textContent='Interest requests are open. Sessions, final prices and availability are confirmed separately; submitting does not create a booking.';
      $('requestPrivacy').href=data.privacy_url;$('sellerName').textContent='Operator: '+data.seller;
      for(const b of document.querySelectorAll('.pilot-select')){b.disabled=false;b.textContent='Express interest';b.addEventListener('click',()=>{form.hidden=false;$('pilotOffer').value=b.dataset.offer;form.scrollIntoView({behavior:'smooth'});form.querySelector('input[name=name]').focus({preventScroll:true});});}
    }catch(_){$('offerStatus').textContent='Could not check pilot availability. Please try again later, or open the free studio.';}
  }
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(!form.reportValidity())return;
    const button=$('pilotSubmit');button.disabled=true;$('pilotStatus').textContent='Submitting…';
    const data=Object.fromEntries(new FormData(form));data.consent=data.consent==='on';
    try{const r=await fetch('/api/pilot/requests',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const body=await r.json();if(!r.ok)throw Error(typeof body.detail==='string'?body.detail:'Please check your inputs and try again.');form.reset();$('pilotStatus').textContent=body.message;}
    catch(err){$('pilotStatus').textContent=err.message||'Could not submit. Your request may not have been recorded.';}
    finally{button.disabled=false;}
  });
  catalog();
})();
