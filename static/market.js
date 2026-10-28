"use strict";
(() => {
const $=id=>document.getElementById(id), NS="http://www.w3.org/2000/svg";
const names={AAPL:"Apple",MSFT:"Microsoft",NVDA:"NVIDIA",TSLA:"Tesla"};
const state={enabled:false,requestId:0,visible:true};
let poll=null;
function status(message){$("liveStatus").textContent=message;}
function clearChart(){for(const id of ["chartGrid","chartLabels"])$(id).replaceChildren();$("chartLine").setAttribute("d","");$("chartArea").setAttribute("d","");$("chartStart").textContent="—";$("chartEnd").textContent="—";}
function svgEl(tag,attrs,text){const node=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))node.setAttribute(k,String(v));if(text!==undefined)node.textContent=text;return node;}
function renderChart(points,currency){
 clearChart();
 if(!Array.isArray(points)||points.length<2)throw Error("Not enough historical prices to draw a chart.");
 const values=points.map(p=>Number(p.close));
 if(values.some(n=>!Number.isFinite(n)||n<=0))throw Error("Unexpected chart data.");
 const min=Math.min(...values),max=Math.max(...values),padding=Math.max((max-min)*0.14,max*0.004,0.01);
 const lower=min-padding,upper=max+padding,W=760,H=320,L=70,R=18,T=18,B=38;
 const x=i=>L+(W-L-R)*i/(values.length-1);
 const y=value=>T+(H-T-B)*(upper-value)/(upper-lower);
 const grid=$("chartGrid"),labels=$("chartLabels");
 const fmt=new Intl.NumberFormat("en-US",{style:"currency",currency:currency||"USD",maximumFractionDigits:2});
 for(let i=0;i<5;i++){
  const value=lower+(upper-lower)*i/4,py=y(value);
  grid.append(svgEl("line",{x1:L,y1:py,x2:W-R,y2:py,stroke:"#e1ebe9","stroke-width":1}));
  labels.append(svgEl("text",{x:8,y:py+4,fill:"#677f86","font-size":12},fmt.format(value)));
 }
 const line=values.map((value,i)=>(i?"L":"M")+x(i).toFixed(2)+","+y(value).toFixed(2)).join(" ");
 $("chartLine").setAttribute("d",line);
 $("chartArea").setAttribute("d",line+" L"+x(values.length-1).toFixed(2)+","+(H-B)+" L"+L+","+(H-B)+" Z");
 $("chartStart").textContent=points[0].time;
 $("chartEnd").textContent=points[points.length-1].time;
 $("chartTitle").textContent=$("liveSymbol").value+" historical close chart";
 $("chartDesc").textContent=points.length+" historical closing prices, from "+points[0].time+" to "+points[points.length-1].time+
  ". Minimum "+fmt.format(min)+", maximum "+fmt.format(max)+".";
}
async function fetchJSON(path){
 const r=await fetch(path,{cache:"no-store",headers:{"Accept":"application/json"}});
 const data=await r.json().catch(()=>({}));
 if(!r.ok)throw Error(typeof data.detail==="string"?data.detail:"Market data unavailable.");
 return data;
}
const displayMoney=(n,c)=>new Intl.NumberFormat("en-US",{style:"currency",currency:c||"USD",maximumFractionDigits:2}).format(n);
async function loadQuote(symbol,requestId){
 try{
  const q=await fetchJSON("/api/quotes/latest/"+symbol);
  if(requestId!==state.requestId)return;
  $("livePrice").textContent=displayMoney(q.price,q.currency);
  $("liveChange").textContent=q.change===null?"Change unavailable":((q.change>=0?"+":"")+displayMoney(q.change,q.currency)+" ("+(q.percent_change>=0?"+":"")+q.percent_change.toFixed(2)+"%)");
  $("liveChange").classList.toggle("negative",q.change!==null&&q.change<0);
  $("liveExchange").textContent="Exchange: "+(q.exchange||"Not supplied")+" · "+q.currency;
  $("liveTimestamp").textContent="Provider quote time: "+(q.as_of||q.exchange_datetime||"Not provided");
  $("liveRefreshInfo").textContent="Fetched: "+new Date(q.fetched_at).toLocaleString()+" · may be delayed";
  status("Latest available provider quote · not guaranteed real-time");
 }catch(err){if(requestId!==state.requestId)return;$("livePrice").textContent="—";$("liveChange").textContent="Quote unavailable";status(err.message);}
}
async function loadChart(symbol,range,requestId){
 $("chartStatus").textContent="Loading historical prices…";clearChart();
 try{
  const data=await fetchJSON("/api/quotes/chart/"+symbol+"?range="+encodeURIComponent(range));
  if(requestId!==state.requestId)return;
  renderChart(data.points,data.currency);
  $("chartStatus").textContent=data.points.length+" provider observations · "+data.interval+" · updated "+new Date(data.fetched_at).toLocaleString()+" · may be delayed";
 }catch(err){if(requestId!==state.requestId)return;clearChart();$("chartStatus").textContent="Chart unavailable: "+err.message;}
}
function refresh(withChart=true){
 if(!state.enabled||document.hidden)return;
 const symbol=$("liveSymbol").value,range=document.querySelector('input[name="liveRange"]:checked').value;
 const id=++state.requestId;$("liveName").textContent=names[symbol]+" · "+symbol;
 loadQuote(symbol,id);
 if(withChart)loadChart(symbol,range,id);
}
async function init(){
 try{const s=await fetchJSON("/api/quotes/status");state.enabled=s.configured;
  if(!s.configured){status("Live market data is not configured. Add a licensed Twelve Data key on the server.");$("chartStatus").textContent="Chart unavailable until provider configuration.";return;}
  refresh();
  poll=setInterval(()=>refresh(false),Math.max(75,s.quote_refresh_seconds||75)*1000);
 }catch(err){status("Market data unavailable: "+err.message);}
}
$("liveSymbol").addEventListener("change",()=>refresh());
for(const r of document.querySelectorAll('input[name="liveRange"]'))r.addEventListener("change",()=>refresh());
$("refreshQuote").addEventListener("click",()=>refresh(false));
document.addEventListener("visibilitychange",()=>{if(!document.hidden&&state.enabled)refresh();});
init();
})();
