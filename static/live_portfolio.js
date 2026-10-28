"use strict";
(() => {
const $=id=>document.getElementById(id), KEY="moneliora-linked-v1", symbols=["AAPL","MSFT","NVDA","TSLA"];
const eur=x=>new Intl.NumberFormat("en-IE",{style:"currency",currency:"EUR"}).format(x);
let cash=5000, holdings={}, cost=0, quote=null, configured=false, busy=false;
try{
  const state=JSON.parse(localStorage.getItem(KEY)||"null");
  if(state&&Number.isFinite(state.cash)&&state.cash>=0&&state.cash<=10000000&&
     Number.isFinite(state.cost)&&Math.abs(state.cost)<10000000&&
     state.holdings&&Object.keys(state.holdings).every(s=>symbols.includes(s)&&Number.isSafeInteger(state.holdings[s])&&state.holdings[s]>=0&&state.holdings[s]<=10000)){
      cash=state.cash;cost=state.cost;holdings=state.holdings;
  }
}catch(_){}
function save(){try{localStorage.setItem(KEY,JSON.stringify({cash,cost,holdings}))}catch(_){}}
function status(message){$("linkedStatus").textContent=message;}
function total(){return quote.quotes.reduce((sum,q)=>sum+(holdings[q.symbol]||0)*q.eur,0);}
function render(){
 $("linkedCash").textContent=eur(cash);
 if(!quote){$("linkedValue").textContent="—";$("linkedPL").textContent="—";$("linkedBuy").disabled=true;$("linkedSell").disabled=true;return;}
 const invested=total(),value=cash+invested;$("linkedValue").textContent=eur(value);
 $("linkedPL").textContent=eur(value-5000);
 const quotes=$("linkedQuotes");quotes.replaceChildren();
 for(const q of quote.quotes){
  const row=document.createElement("div");row.className="watch-item";
  const name=document.createElement("div"),label=document.createElement("b"),info=document.createElement("small");
  label.textContent=q.name+" ("+q.symbol+")";info.textContent=eur(q.eur)+" · USD "+q.usd.toFixed(2)+" · "+(q.as_of||"Provider time unavailable")+" · may be delayed";
  name.append(label,info);row.append(name);quotes.append(row);
 }
 const root=$("linkedHoldings");root.replaceChildren();
 for(const q of quote.quotes){
  const qty=holdings[q.symbol]||0;if(!qty)continue;
  const line=document.createElement("div");line.className="holding";const info=document.createElement("span");info.textContent=q.name+": "+qty+" virtual shares";
  const val=document.createElement("strong");val.textContent=eur(qty*q.eur);line.append(info,val);root.append(line);
 }
 if(!root.children.length){const p=document.createElement("p");p.className="hint";p.textContent="No market-linked virtual shares yet.";root.append(p);}
 $("linkedAsOf").textContent="Market snapshot fetched: "+new Date(quote.fetched_at).toLocaleString()+
  " · USD/EUR "+quote.fx.rate+" · FX provider timestamp: "+(quote.fx.as_of||"not supplied")+
  ". Quote timestamps may differ from FX.";
 $("linkedBuy").disabled=false;$("linkedSell").disabled=false;
}
async function refresh(){
 if(busy||document.hidden)return;busy=true;
 try{
  const r=await fetch("/api/quotes/snapshot",{cache:"no-store"}),data=await r.json();
  if(!r.ok)throw Error(data.detail||"Market provider unavailable");
  if(data.currency!=="EUR"||!Array.isArray(data.quotes)||data.quotes.length!==4||!Number.isFinite(data.fx?.rate)||data.fx.rate<=0)
   throw Error("Invalid market snapshot");
  if(!data.quotes.every(q=>symbols.includes(q.symbol)&&Number.isFinite(q.eur)&&q.eur>0))throw Error("Invalid market quotes");
  quote=data;render();status("Provider-backed market snapshot loaded. Prices may be delayed.");
 }catch(err){quote=null;render();status("Market-linked trading paused: "+err.message+" No fictional fallback is used.");}
 finally{busy=false;}
}
function trade(side){
 if(!quote){$("linkedOrder").textContent="Market prices unavailable.";return;}
 const symbol=$("linkedSymbol").value,q=quote.quotes.find(q=>q.symbol===symbol),qty=Number($("linkedQty").value);
 if(!q||!Number.isSafeInteger(qty)||qty<1||qty>10000){$("linkedOrder").textContent="Enter 1–10,000 whole virtual shares.";return;}
 const value=Math.round(q.eur*qty*100)/100;
 if(side==="buy"&&value>cash){$("linkedOrder").textContent="Insufficient virtual EUR cash.";return;}
 if(side==="sell"&&qty>(holdings[symbol]||0)){$("linkedOrder").textContent="Not enough virtual shares.";return;}
 cash=Math.round((cash+(side==="buy"?-value:value))*100)/100;
 holdings[symbol]=(holdings[symbol]||0)+(side==="buy"?qty:-qty);
 cost=Math.round((cost+(side==="buy"?value:-value))*100)/100;
 save();render();
 $("linkedOrder").textContent=(side==="buy"?"Bought ":"Sold ")+qty+" "+symbol+" virtually at "+eur(q.eur)+" per share; no real order placed.";
}
$("linkedBuy").addEventListener("click",()=>trade("buy"));
$("linkedSell").addEventListener("click",()=>trade("sell"));
$("linkedRefresh").addEventListener("click",refresh);
render();refresh();
setInterval(()=>{if(!document.hidden)refresh()},75000);
document.addEventListener("visibilitychange",()=>{if(!document.hidden)refresh()});
})();