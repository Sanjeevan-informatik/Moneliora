"use strict";
(() => {
const $=id=>document.getElementById(id), KEY="moneliora-linked-v1", symbols=["AAPL","MSFT","NVDA","TSLA"];
const eur=x=>new Intl.NumberFormat("en-IE",{style:"currency",currency:"EUR"}).format(x);
let cashCents=500000, holdings={}, costCents=0, quote=null, configured=false, busy=false;
try{
  let state=JSON.parse(localStorage.getItem(KEY)||"null");
  if(state)state={...state,cash_cents:state.cash_cents===undefined?MonelioraMoney.toCents(state.cash):state.cash_cents,cost_cents:state.cost_cents===undefined?MonelioraMoney.toCents(state.cost):state.cost_cents};
  if(state&&Number.isSafeInteger(state.cash_cents)&&state.cash_cents>=0&&state.cash_cents<=1000000000&&
     Number.isSafeInteger(state.cost_cents)&&Math.abs(state.cost_cents)<1000000000&&
     state.holdings&&Object.keys(state.holdings).every(s=>symbols.includes(s)&&Number.isSafeInteger(state.holdings[s])&&state.holdings[s]>=0&&state.holdings[s]<=10000)){
      cashCents=state.cash_cents;costCents=state.cost_cents;holdings=state.holdings;
  }
}catch(_){}
function save(){try{localStorage.setItem(KEY,JSON.stringify({schema_version:2,cash_cents:cashCents,cost_cents:costCents,holdings}))}catch(_){}}
function status(message){$("linkedStatus").textContent=message;}
function total(){return quote.quotes.reduce((sum,q)=>sum+MonelioraMoney.multiplyToCents(q.eur,holdings[q.symbol]||0),0);}
function render(){
 $("linkedCash").textContent=eur(cashCents/100);
 if(!quote){$("linkedValue").textContent="—";$("linkedPL").textContent="—";$("linkedBuy").disabled=true;$("linkedSell").disabled=true;return;}
 const invested=total(),value=cashCents+invested;$("linkedValue").textContent=eur(value/100);
 $("linkedPL").textContent=eur((value-500000)/100);
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
  const val=document.createElement("strong");val.textContent=eur(MonelioraMoney.multiplyToCents(q.eur,qty)/100);line.append(info,val);root.append(line);
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
  if(new Set(data.quotes.map(q=>q.symbol)).size!==4||!data.quotes.every(q=>symbols.includes(q.symbol)&&Number.isFinite(q.eur)&&q.eur>0&&q.eur<=1000000&&Number.isFinite(q.usd)&&q.usd>0))throw Error("Invalid market quotes");
  quote=data;render();status("Provider-backed market snapshot loaded. Prices may be delayed.");
 }catch(err){quote=null;render();status("Market-linked trading paused: "+err.message+" No fictional fallback is used.");}
 finally{busy=false;}
}
function trade(side){
 if(!quote){$("linkedOrder").textContent="Market prices unavailable.";return;}
 const symbol=$("linkedSymbol").value,q=quote.quotes.find(q=>q.symbol===symbol),qty=Number($("linkedQty").value);
 if(!q||!Number.isSafeInteger(qty)||qty<1||qty>10000){$("linkedOrder").textContent="Enter 1–10,000 whole virtual shares.";return;}
 const value=MonelioraMoney.multiplyToCents(q.eur,qty);
 if(side==="buy"&&value>cashCents){$("linkedOrder").textContent="Insufficient virtual EUR cash.";return;}
 if(side==="sell"&&qty>(holdings[symbol]||0)){$("linkedOrder").textContent="Not enough virtual shares.";return;}
 const nextCash=cashCents+(side==="buy"?-value:value);
 const nextCost=costCents+(side==="buy"?value:-value);
 if(!Number.isSafeInteger(nextCash)||nextCash>1000000000||!Number.isSafeInteger(nextCost)||Math.abs(nextCost)>=1000000000){$("linkedOrder").textContent="Virtual amount outside supported range.";return;}
 cashCents=nextCash;
 holdings[symbol]=(holdings[symbol]||0)+(side==="buy"?qty:-qty);
 costCents=nextCost;
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
