"use strict";
// Fictional prices only; this app NEVER transmits real securities orders.
const companies=[
{symbol:"NVDA",name:"NVIDIA",sector:"Technology",price:125},
{symbol:"MSFT",name:"Microsoft",sector:"Technology",price:360},
{symbol:"AAPL",name:"Apple",sector:"Technology",price:180},
{symbol:"TSLA",name:"Tesla",sector:"Automotive",price:220},
{symbol:"XIA",name:"Xiaomi",sector:"Technology",price:4.5},
{symbol:"BYD",name:"BYD",sector:"Automotive",price:14},
{symbol:"IFX",name:"Infineon",sector:"Technology",price:30},
{symbol:"VW",name:"Volkswagen",sector:"Automotive",price:95},
{symbol:"AIR",name:"Airbus",sector:"Aerospace",price:145}
];
const $=id=>document.getElementById(id);
const eur=n=>new Intl.NumberFormat("en-IE",{style:"currency",currency:"EUR"}).format(n);
const PAPER_KEY="moneliora-paper-v3",OLD_PAPER_KEY="moneliora-paper-v2",WATCH_KEY="moneliora-watch-v1",STEP_KEY="moneliora-steps-v1";
let cash=5000,positions={},trades=[],watched=[],steps={explore:false,trade:false,risk:false};
function readLocal(key,fallback){try{let s=localStorage.getItem(key);return s?JSON.parse(s):fallback}catch(_){return fallback}}
function writeLocal(key,value){try{localStorage.setItem(key,JSON.stringify(value))}catch(_){}}
const snapshot=readLocal(PAPER_KEY,readLocal(OLD_PAPER_KEY,null));
if(snapshot&&typeof snapshot==="object"&&snapshot.positions&&typeof snapshot.positions==="object"){
  const nextCash=snapshot.cash,known=Object.keys(snapshot.positions).every(k=>companies.some(c=>c.symbol===k));
  const valid=known&&Number.isFinite(nextCash)&&nextCash>=0&&nextCash<=5000&&companies.every(c=>{
    const q=snapshot.positions[c.symbol]??0;return Number.isSafeInteger(q)&&q>=0&&q<=100000;
  });
  const value=valid?nextCash+companies.reduce((a,c)=>a+(snapshot.positions[c.symbol]||0)*c.price,0):Infinity;
  if(valid&&value<=10000000){
    cash=nextCash;positions=Object.fromEntries(companies.filter(c=>snapshot.positions[c.symbol]>0).map(c=>[c.symbol,snapshot.positions[c.symbol]]));
    if(Array.isArray(snapshot.trades))trades=snapshot.trades.filter(t=>t&&typeof t==="object"&&companies.some(c=>c.symbol===t.symbol)&&["buy","sell"].includes(t.side)&&Number.isSafeInteger(t.qty)&&t.qty>0&&t.qty<=100000&&Number.isFinite(t.amount)&&t.amount>=0).slice(0,30);
  }
}
const rawWatch=readLocal(WATCH_KEY,[]);
if(Array.isArray(rawWatch))watched=[...new Set(rawWatch.filter(x=>companies.some(c=>c.symbol===x)))].slice(0,9);
const rawSteps=readLocal(STEP_KEY,{});
if(rawSteps&&typeof rawSteps==="object")steps={explore:rawSteps.explore===true,trade:rawSteps.trade===true,risk:rawSteps.risk===true};
if(Object.values(positions).some(v=>v>0))steps.trade=true;
function persist(){writeLocal(PAPER_KEY,{cash,positions,trades});}
function markStep(step){steps[step]=true;writeLocal(STEP_KEY,steps);renderSteps();}
function toast(message){const node=$("toast");node.textContent=message;node.hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>node.hidden=true,3500);}
function inputNumber(id,min,max){const raw=$(id).value.trim();if(!raw)return null;const n=Number(raw);return Number.isFinite(n)&&n>=min&&n<=max?n:null;}
function renderSteps(){const done=Object.values(steps).filter(Boolean).length;$("stepsCounter").textContent=done+" of 3";$("stepsFill").style.width=done/3*100+"%";for(const [key,id] of [["explore","stepExplore"],["trade","stepTrade"],["risk","stepRisk"]]){$(id).classList.toggle("step-complete",steps[key]);$(id).querySelector(".step-mark").textContent=steps[key]?"✓":key==="explore"?"1":key==="trade"?"2":"3";}}
function selectStock(symbol){$("tradeSymbol").value=symbol;estimate();markStep("explore");document.getElementById("portfolio").scrollIntoView({behavior:"smooth"});$("tradeQty").focus({preventScroll:true});}
function toggleWatch(symbol){if(watched.includes(symbol))watched=watched.filter(x=>x!==symbol);else watched.push(symbol);writeLocal(WATCH_KEY,watched);renderMarkets();renderWatch();toast(watched.includes(symbol)?"Added to your watchlist":"Removed from your watchlist");}
function renderMarkets(){
const query=$("stockSearch").value.trim().toLowerCase(),sector=$("sectorFilter").value,only=$("watchOnly").checked;
const found=companies.filter(c=>(!query||(c.name+" "+c.symbol).toLowerCase().includes(query))&&(sector==="all"||sector===c.sector)&&(!only||watched.includes(c.symbol)));
const root=$("marketCards");root.replaceChildren();$("resultsCount").textContent=found.length+" of "+companies.length+" example companies";$("marketEmpty").hidden=found.length!==0;
for(const c of found){
const card=document.createElement("article");card.className="market-card";const top=document.createElement("div");top.className="market-top";
const ticker=document.createElement("span");ticker.className="symbol";ticker.textContent=c.symbol+" · DEMO";
const star=document.createElement("button");star.className="star";star.type="button";star.textContent=watched.includes(c.symbol)?"★":"☆";star.setAttribute("aria-pressed",String(watched.includes(c.symbol)));star.setAttribute("aria-label",(watched.includes(c.symbol)?"Remove ":"Add ")+c.name+(watched.includes(c.symbol)?" from":" to")+" watchlist");star.addEventListener("click",()=>toggleWatch(c.symbol));top.append(ticker,star);
const name=document.createElement("h3");name.textContent=c.name;
const price=document.createElement("strong");price.className="market-price";price.textContent=eur(c.price);
const info=document.createElement("small");info.className="fake-label";info.textContent="Fictional price, not a quote";
const bottom=document.createElement("div");bottom.className="market-bottom";const category=document.createElement("span");category.className="sector";category.textContent=c.sector;
const action=document.createElement("button");action.className="button button-outline";action.type="button";action.textContent="Practise →";action.addEventListener("click",()=>selectStock(c.symbol));bottom.append(category,action);card.append(top,name,price,info,bottom);root.append(card);
}}
function renderWatch(){const root=$("watchItems");root.replaceChildren();if(!watched.length){const p=document.createElement("p");p.className="hint";p.textContent="No saved companies yet. Explore stocks and tap ☆ to add one.";root.append(p);return}
for(const symbol of watched){const c=companies.find(x=>x.symbol===symbol);const div=document.createElement("div");div.className="watch-item";const info=document.createElement("div");const b=document.createElement("b");b.textContent=c.name;const small=document.createElement("small");small.textContent=c.symbol+" · Demo "+eur(c.price);info.append(b,small);const button=document.createElement("button");button.className="button button-outline";button.textContent="Remove";button.type="button";button.setAttribute("aria-label","Remove "+c.name+" from watchlist");button.addEventListener("click",()=>toggleWatch(symbol));div.append(info,button);root.append(div);}}
function renderPortfolio(){const invested=companies.reduce((n,c)=>n+(positions[c.symbol]||0)*c.price,0),total=cash+invested;
$("portfolioValue").textContent=eur(total);$("cashValue").textContent=eur(cash);$("investedValue").textContent=eur(invested);
const count=companies.filter(c=>(positions[c.symbol]||0)>0).length;$("holdingsCount").textContent=count+" "+(count===1?"company":"companies")+" held";
const pct=total>0?100*invested/total:0;$("allocationFilled").style.width=pct.toFixed(1)+"%";$("allocationInvested").textContent=pct.toFixed(1)+"%";$("allocationCash").textContent=(100-pct).toFixed(1)+"%";
$("allocationTrack").setAttribute("aria-label",pct.toFixed(1)+" percent virtual shares, "+(100-pct).toFixed(1)+" percent virtual cash");
const root=$("holdings");root.replaceChildren();for(const c of companies){const q=positions[c.symbol]||0;if(!q)continue;const line=document.createElement("div");line.className="holding";
const info=document.createElement("div"),name=document.createElement("b"),qty=document.createElement("small"),amount=document.createElement("strong");name.textContent=c.name;qty.textContent=q+" shares · "+c.symbol;amount.textContent=eur(q*c.price);info.append(name,qty);line.append(info,amount);root.append(line);}
if(!root.children.length){const p=document.createElement("p");p.className="hint";p.textContent="No virtual holdings yet. Choose a company and make your first practice trade.";root.append(p)}
const history=$("tradeHistory");history.replaceChildren();for(const t of trades.slice(0,10)){const line=document.createElement("div");line.className="activity-row";const info=document.createElement("div"),b=document.createElement("b"),date=document.createElement("small"),amount=document.createElement("strong");b.textContent=(t.side==="buy"?"Virtual buy":"Virtual sell")+" · "+t.symbol;date.textContent=t.qty+" shares · "+(typeof t.date==="string"?t.date:"Practice order");amount.textContent=eur(t.amount);info.append(b,date);line.append(info,amount);history.append(line);}
if(!history.children.length){const p=document.createElement("p");p.className="hint";p.textContent="Your simulated orders will appear here.";history.append(p)}
$("tradeAvailable").textContent="Virtual cash available: "+eur(cash);
const biggest=companies.reduce((best,c)=>Math.max(best,(positions[c.symbol]||0)*c.price),0);
const sectors=new Set(companies.filter(c=>positions[c.symbol]>0).map(c=>c.sector));
$("concentration").textContent=invested>0?"Largest company: "+(biggest/invested*100).toFixed(1)+"% of invested shares · "+sectors.size+" industries. These example stocks do not represent a diversified portfolio. Cash is excluded from this percentage.":"Your allocation insights will appear after a practice trade.";
}
function estimate(){const c=companies.find(x=>x.symbol===$("tradeSymbol").value),qty=inputNumber("tradeQty",1,100000);
$("tradeEstimate").textContent=c&&qty&&Number.isSafeInteger(qty)?eur(qty*c.price):"Enter a whole number of shares";}
function trade(side){const c=companies.find(x=>x.symbol===$("tradeSymbol").value),qty=inputNumber("tradeQty",1,100000);const message=$("tradeNotice");
if(!c||qty===null||!Number.isSafeInteger(qty)){message.textContent="Enter a valid whole number of shares.";return}
const amount=Math.round(qty*c.price*100)/100;if(side==="buy"&&amount>cash+0.0001){message.textContent="Not enough virtual cash. Try fewer shares.";return}
if(side==="sell"&&qty>(positions[c.symbol]||0)){message.textContent="You cannot sell more virtual shares than you own.";return}
cash=Math.round((cash+(side==="buy"?-amount:amount))*100)/100;const next=(positions[c.symbol]||0)+(side==="buy"?qty:-qty);if(next)positions[c.symbol]=next;else delete positions[c.symbol];
trades.unshift({symbol:c.symbol,qty,amount,side,date:new Date().toLocaleString()});trades=trades.slice(0,30);persist();markStep("trade");renderPortfolio();
message.textContent=(side==="buy"?"Virtual purchase":"Virtual sale")+" complete: "+qty+" "+c.symbol+" shares. No real money moved.";toast(message.textContent);}
function calculate(){const a=inputNumber("initial",0,10000000),m=inputNumber("monthly",0,100000),rate=inputNumber("returnRate",-99,50),years=inputNumber("years",1,60);if([a,m,rate,years].some(x=>x===null)){ $("growthResult").textContent="Check your inputs";$("growthDetail").textContent="";return}
let sum=a;const r=(1+rate/100)**(1/12)-1,n=Math.round(years*12);for(let i=0;i<n;i++)sum=sum*(1+r)+m;const contributed=a+m*n;$("growthResult").textContent=eur(sum);$("growthDetail").textContent="Contributions: "+eur(contributed)+" · Illustrative gain/loss: "+eur(sum-contributed);}
function fees(){const a=inputNumber("orderValue",1,100000000),f=inputNumber("orderFee",0,1000000),p=inputNumber("spread",0,100);if([a,f,p].some(x=>x===null)){$("feeResult").textContent="Check your inputs";$("feeDetail").textContent="";return}const cost=f+a*p/100;$("feeResult").textContent=eur(cost);$("feeDetail").textContent=(cost/a*100).toFixed(2)+"% of your example order";}
function risk(){const a=inputNumber("riskAmount",0,10000000),p=inputNumber("riskDrop",0,100);if(a===null||p===null){$("riskValue").textContent="Check your inputs";$("riskLoss").textContent="";return}const loss=a*p/100;$("riskValue").textContent=eur(a-loss);$("riskLoss").textContent="Hypothetical loss: "+eur(loss)+" · This is not a prediction.";}
for(const c of companies){const opt=document.createElement("option");opt.value=c.symbol;opt.textContent=c.name+" ("+c.symbol+")";$("tradeSymbol").append(opt);}
$("stockSearch").addEventListener("input",renderMarkets);$("sectorFilter").addEventListener("change",renderMarkets);$("watchOnly").addEventListener("change",renderMarkets);
$("clearFilters").addEventListener("click",()=>{$("stockSearch").value="";$("sectorFilter").value="all";$("watchOnly").checked=false;renderMarkets();$("stockSearch").focus();});
for(const id of ["tradeSymbol","tradeQty"])$(id).addEventListener("input",estimate);
$("buy").addEventListener("click",()=>trade("buy"));$("sell").addEventListener("click",()=>trade("sell"));
const dialog=$("resetDialog");$("resetPortfolio").addEventListener("click",()=>dialog.showModal());
dialog.addEventListener("close",()=>{if(dialog.returnValue!=="confirm")return;cash=5000;positions={};trades=[];steps.trade=false;writeLocal(STEP_KEY,steps);persist();renderPortfolio();renderSteps();$("tradeNotice").textContent="Account reset to €5,000 virtual cash.";toast("Virtual portfolio reset.");});
for(const id of ["initial","monthly","returnRate","years"])$(id).addEventListener("input",calculate);
for(const id of ["orderValue","orderFee","spread"])$(id).addEventListener("input",fees);
for(const id of ["riskAmount","riskDrop"])$(id).addEventListener("input",()=>{risk();markStep("risk");});
for(const btn of document.querySelectorAll("[data-drop]"))btn.addEventListener("click",()=>{$("riskDrop").value=btn.dataset.drop;risk();markStep("risk");});
$("quizYes").addEventListener("click",()=>{$("quizFeedback").textContent="Correct. Even a diversified portfolio may fall in value. Diversification is not a guarantee.";});
$("quizNo").addEventListener("click",()=>{$("quizFeedback").textContent="Not quite. Diversification can reduce individual-company risk, but market declines can still cause losses.";});
const dateInput=$("preferredDate");const today=new Date();function isoLocal(d){const y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,"0"),day=String(d.getDate()).padStart(2,"0");return y+"-"+m+"-"+day;}
dateInput.min=isoLocal(today);const latest=new Date(today);latest.setDate(latest.getDate()+180);dateInput.max=isoLocal(latest);
$("consultForm").addEventListener("submit",async e=>{e.preventDefault();const form=e.currentTarget,submit=$("consultSubmit"),fd=new FormData(form),data=Object.fromEntries(fd.entries());data.privacy_accepted=fd.has("privacy_accepted");
submit.disabled=true;$("consultStatus").textContent="Sending your request…";
try{const r=await fetch("/api/consultations",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});const body=await r.json();if(!r.ok)throw Error(typeof body.detail==="string"?body.detail:"Please check your information and try again.");
$("consultStatus").textContent="Request received. This is not a confirmed appointment.";form.reset();toast("Your learning request was received.");}
catch(err){$("consultStatus").textContent=err.message||"Could not submit the request.";}finally{submit.disabled=false;}});
const nav=[...document.querySelectorAll("[data-nav]")];function navActive(){const section=location.hash.slice(1)||"home";for(const link of nav){if(link.dataset.nav===section)link.setAttribute("aria-current","page");else link.removeAttribute("aria-current");}}
window.addEventListener("hashchange",navActive);navActive();
renderMarkets();renderWatch();renderPortfolio();renderSteps();calculate();fees();risk();estimate();
