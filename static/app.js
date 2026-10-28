"use strict";
// Fictional educational prices; never market feeds or predictions.
const companies=[
 {symbol:"NVDA",name:"NVIDIA",price:125},{symbol:"MSFT",name:"Microsoft",price:360},
 {symbol:"AAPL",name:"Apple",price:180},{symbol:"TSLA",name:"Tesla",price:220},
 {symbol:"XIA",name:"Xiaomi",price:4.5},{symbol:"BYD",name:"BYD",price:14},
 {symbol:"IFX",name:"Infineon",price:30},{symbol:"VW",name:"Volkswagen",price:95},
 {symbol:"AIR",name:"Airbus",price:145}
];
const eur=n=>new Intl.NumberFormat("de-DE",{style:"currency",currency:"EUR"}).format(n);
let cash=5000;const positions={};
const STORAGE_KEY="moneliora-paper-v2";const WATCH_KEY="moneliora-watch-v1";
let watched=[];
try{
 const s=JSON.parse(localStorage.getItem(STORAGE_KEY)||"null");
 if(s&&Number.isFinite(s.cash)&&s.cash>=0&&s.cash<=5000&&s.positions&&typeof s.positions==="object"){
  let total=s.cash;let valid=true;
  for(const company of companies){const q=s.positions[company.symbol]??0;if(!Number.isSafeInteger(q)||q<0||q>100000){valid=false;break}total+=q*company.price;}
  if(valid&&total<=10000000){cash=s.cash;for(const company of companies){const q=s.positions[company.symbol]||0;if(q)positions[company.symbol]=q;}}
 }
 const w=JSON.parse(localStorage.getItem(WATCH_KEY)||"[]");if(Array.isArray(w))watched=[...new Set(w.filter(symbol=>companies.some(x=>x.symbol===symbol)))].slice(0,9);
}catch(_){}
function persist(){try{localStorage.setItem(STORAGE_KEY,JSON.stringify({cash,positions}));}catch(_){}}
function renderWatch(){const root=$("watchItems");root.replaceChildren();for(const symbol of watched){
const c=companies.find(x=>x.symbol===symbol),line=document.createElement("div");line.className="holding";
const name=document.createElement("span");name.textContent=c.name+" ("+c.symbol+") · fictional "+eur(c.price);
const btn=document.createElement("button");btn.className="ghost";btn.textContent="Remove";btn.addEventListener("click",()=>{watched=watched.filter(x=>x!==symbol);try{localStorage.setItem(WATCH_KEY,JSON.stringify(watched))}catch(_){}renderWatch()});line.append(name,btn);root.append(line)}
if(!watched.length){const p=document.createElement("p");p.className="muted";p.textContent="Your watchlist is empty.";root.append(p)}}
function risk(){const amount=number("riskAmount",0,10000000),drop=number("riskDrop",0,100);if(amount===null||drop===null){$("riskValue").textContent="Invalid values";$("riskLoss").textContent="";return}const loss=amount*drop/100;$("riskValue").textContent=eur(amount-loss);$("riskLoss").textContent="Hypothetical loss: "+eur(loss)+" · Not a forecast.";}

const $=id=>document.getElementById(id);
function number(id,min,max){const n=Number($(id).value);return Number.isFinite(n)&&n>=min&&n<=max?n:null}
function update(){
 let held=0;const root=$("holdings");root.replaceChildren();
 for(const company of companies){const qty=positions[company.symbol]||0;if(!qty)continue;
  held+=qty*company.price;const line=document.createElement("div");line.className="holding";
  const left=document.createElement("div"),right=document.createElement("strong");
  const name=document.createElement("b"),details=document.createElement("span");
  name.textContent=company.symbol;details.textContent=" · "+qty+" virtual shares";
  left.append(name,details);right.textContent=eur(qty*company.price);
  line.append(left,right);root.append(line);}
 if(!root.children.length){const p=document.createElement("p");p.className="muted";p.textContent="No holdings yet. Try a simulated trade.";root.append(p)}
 $("cashValue").textContent=eur(cash);$("portfolioValue").textContent=eur(cash+held);
 $("plValue").textContent=eur(cash+held-5000);persist();
}
function trade(side){
 const qty=number("tradeQty",1,100000);const c=companies.find(x=>x.symbol===$("tradeSymbol").value);
 if(!qty||!Number.isInteger(qty)||!c){$("tradeNotice").textContent="Enter a valid whole-share quantity.";return}
 const amount=qty*c.price;
 if(side==="buy"&&amount>cash+1e-8){$("tradeNotice").textContent="Not enough virtual cash.";return}
 if(side==="sell"&&qty>(positions[c.symbol]||0)){$("tradeNotice").textContent="You do not own enough virtual shares.";return}
 cash+=side==="buy"?-amount:amount;
 cash=Math.round(cash*100)/100;positions[c.symbol]=(positions[c.symbol]||0)+(side==="buy"?qty:-qty);
 $("tradeNotice").textContent=side==="buy"?"Virtual purchase recorded.":"Virtual sale recorded.";update();
}
function calculate(){
 const initial=number("initial",0,10000000),month=number("monthly",0,100000),rate=number("returnRate",-99,50),years=number("years",1,60);
 if([initial,month,rate,years].some(x=>x===null)){$("growthResult").textContent="Invalid values";return}
 const r=rate/1200;let balance=initial;const months=Math.round(years*12);
 for(let i=0;i<months;i++)balance=balance*(1+r)+month;
 const paid=initial+month*months;
 $("growthResult").textContent=eur(balance);$("growthDetail").textContent="Contributions: "+eur(paid)+" · hypothetical gain/loss: "+eur(balance-paid);
}
function fees(){
 const order=number("orderValue",1,100000000),fee=number("orderFee",0,1000000),spread=number("spread",0,100);
 if([order,fee,spread].some(x=>x===null)){$("feeResult").textContent="Invalid values";return}
 const cost=fee+order*spread/100;$("feeResult").textContent=eur(cost);$("feeDetail").textContent=(100*cost/order).toFixed(2)+"% of order value";
}
for(const c of companies){
 const card=document.createElement("article");card.className="market-card";
 const ticker=document.createElement("div");ticker.className="ticker";ticker.textContent=c.symbol+" · SAMPLE";
 const title=document.createElement("h3");title.textContent=c.name;
 const price=document.createElement("strong");price.textContent=eur(c.price);
 const note=document.createElement("p");note.textContent="Fictional teaching price · EUR";
 card.append(ticker,title,price,note);$("markets").append(card);
 const opt=document.createElement("option");opt.value=c.symbol;opt.textContent=c.name+" ("+c.symbol+")";$("tradeSymbol").append(opt);$("watchSymbol").append(opt.cloneNode(true));
}
function estimate(){const c=companies.find(x=>x.symbol===$("tradeSymbol").value),qty=number("tradeQty",1,100000);
 $("tradeEstimate").textContent=c&&qty?("Illustrative total: "+eur(c.price*qty)):"Enter valid quantity";}
["tradeSymbol","tradeQty"].forEach(id=>$(id).addEventListener("input",estimate));
$("buy").addEventListener("click",()=>trade("buy"));$("sell").addEventListener("click",()=>trade("sell"));
$("resetPortfolio").addEventListener("click",()=>{cash=5000;for(const key of Object.keys(positions))delete positions[key];$("tradeNotice").textContent="Virtual sandbox reset.";update()});
["initial","monthly","returnRate","years"].forEach(id=>$(id).addEventListener("input",calculate));
["orderValue","orderFee","spread"].forEach(id=>$(id).addEventListener("input",fees));
const tomorrow=new Date();tomorrow.setDate(tomorrow.getDate()+1);
$("preferredDate").min=new Date().toLocaleDateString("en-CA");
$("consultForm").addEventListener("submit",async event=>{
 event.preventDefault();const form=event.currentTarget,submit=form.querySelector("button");
 const fd=new FormData(form),data=Object.fromEntries(fd.entries());data.privacy_accepted=fd.has("privacy_accepted");
 $("consultStatus").textContent="Sending…";submit.disabled=true;
 try{const response=await fetch("/api/consultations",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});
 const result=await response.json();if(!response.ok)throw Error(typeof result.detail==="string"?result.detail:"Request could not be submitted.");
 $("consultStatus").textContent="Request recorded. Appointment not yet confirmed.";form.reset();
 }catch(err){$("consultStatus").textContent=err.message||"Network error"}finally{submit.disabled=false}
});
$("watchAdd").addEventListener("click",()=>{const symbol=$("watchSymbol").value;if(!watched.includes(symbol)){watched.push(symbol);try{localStorage.setItem(WATCH_KEY,JSON.stringify(watched))}catch(_){}renderWatch()}});
["riskAmount","riskDrop"].forEach(id=>$(id).addEventListener("input",risk));
update();calculate();fees();estimate();renderWatch();risk();