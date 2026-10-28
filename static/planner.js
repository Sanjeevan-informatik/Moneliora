"use strict";
(() => {
  const F = window.MonelioraFinance, el = id => document.getElementById(id);
  const money = n => new Intl.NumberFormat("en-IE", {style:"currency", currency:"EUR", maximumFractionDigits:0}).format(n);
  const key = "moneliora-plan-v1", forms = ["budgetForm", "goalForm", "debtForm", "businessForm"];
  const inputs = forms.flatMap(id => [...el(id).querySelectorAll("input")]);
  let scenarioData = null, currentBudget = null;
  function read(id) {
    const input = el(id), valid = input.value.trim() !== "" && input.checkValidity();
    input.setAttribute("aria-invalid", String(!valid));
    if (!valid) throw Error(`Check ${input.closest("label").firstChild.textContent.trim()}: enter a value within the displayed limits.`);
    return Number(input.value);
  }
  function show(id, headline, lines = [], error = false) {
    const root = el(id); root.replaceChildren(); root.classList.toggle("is-error", error);
    const title = document.createElement(error ? "p" : "strong"); title.textContent = headline; root.append(title);
    for (const text of lines) {const p = document.createElement("p"); p.textContent = text; root.append(p);}
  }
  function safely(id, fn) {try {fn();} catch (err) {show(id, err.message, [], true);}}
  function updateBudget() {
    currentBudget = null;
    safely("budgetResult", () => {
      const b = F.budget({income:read("planIncome"), essential:read("planEssential"), flexible:read("planFlexible"), debt:read("planDebt"), reserve:read("planReserve"), months:read("planMonths")});
      currentBudget = b;
      show("budgetResult", `${money(b.surplus)} / month ${b.surplus >= 0 ? "left over" : "shortfall"}`, [
        b.surplus < 0 ? "Spending exceeds income in this scenario. Review the shortfall before allocating new savings." : "This is the amount left before goal contributions and other unlisted costs.",
        `Cash reserve target: ${money(b.target)} · Remaining gap: ${money(b.gap)}.`,
        b.coverage === null ? "Reserve coverage needs positive essential costs or debt payments." : `Current reserve covers ${b.coverage.toFixed(1)} months of essentials and debt payments.`,
        b.savingRate === null ? "Savings rate is undefined with zero income." : `Unallocated surplus / income: ${b.savingRate.toFixed(1)}%.`
      ]);
    });
  }
  function svg(tag, attrs, text) {const n=document.createElementNS("http://www.w3.org/2000/svg",tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;return n;}
  function drawChart(scenarios) {
    const root=el("goalChartContent");root.replaceChildren();
    const max=Math.max(1,...scenarios.flatMap(s=>s.result.rows.map(r=>r.real))), years=scenarios[0].result.year;
    const x=y=>85+y/years*645,y=v=>205-v/max*175;
    for(let i=0;i<=4;i++){const v=max*i/4;root.append(svg("line",{x1:85,x2:730,y1:y(v),y2:y(v),stroke:"#e2ebec"}),svg("text",{x:77,y:y(v)+4,"text-anchor":"end",class:"chart-axis"},new Intl.NumberFormat("en",{notation:"compact",maximumFractionDigits:1}).format(v)+" €"));}
    scenarios.forEach((s,i)=>{root.append(svg("path",{d:s.result.rows.map((r,j)=>`${j?"L":"M"}${x(r.year).toFixed(2)},${y(r.real).toFixed(2)}`).join(" "),class:`scenario-line scenario-${["low","base","high"][i]}`}));root.append(svg("text",{x:85+i*215,y:242,class:"chart-axis"},`${s.name}: ${s.rate.toFixed(1)}%`));});
    root.append(svg("text",{x:85,y:222,class:"chart-axis"},"Now"),svg("text",{x:730,y:222,"text-anchor":"end",class:"chart-axis"},`Year ${years}`));
    el("goalChartDesc").textContent=`Three hypothetical paths in today's euros over ${years} years. `+scenarios.map(s=>`${s.name} ends at ${money(s.result.real)}.`).join(" ");
  }
  function updateGoal() {
    scenarioData=null;el("scenarioRows").replaceChildren();el("goalChartContent").replaceChildren();el("goalBudgetNote").textContent="";
    safely("goalResult",()=>{
      const p={initial:read("goalInitial"),monthly:read("goalMonthly"),years:read("goalYears"),rate:read("goalRate"),fee:read("goalFee"),inflation:read("goalInflation")};
      const target=read("goalTarget"),variation=read("goalVariation");
      if(p.rate-variation < -99 || p.rate+variation > 50) throw Error("Keep all three scenario returns between −99% and 50%; reduce the scenario difference.");
      const scenarios=[{name:"Lower",rate:p.rate-variation},{name:"Base",rate:p.rate},{name:"Higher",rate:p.rate+variation}].map(s=>({...s,result:F.project({...p,rate:s.rate})}));
      const base=scenarios[1].result;
      show("goalResult",`${money(base.real)} in today’s euros`,[`Base scenario: ${money(base.nominal)} in future euros.`, `Total paid in: ${money(base.contributed)}. Fee impact versus no fee: ${money(base.feeDrag)} in future euros.`,base.real>=target?"The base assumption reaches the goal; this is not a guarantee.":`Base scenario shortfall: ${money(target-base.real)} in today’s euros.`]);
      el("goalBudgetNote").textContent=!currentBudget?"Complete valid cash-flow inputs to compare affordability.":p.monthly>currentBudget.surplus?`This contribution exceeds your monthly surplus by ${money(p.monthly-currentBudget.surplus)}. The projection does not check borrowing or affordability automatically.`:`After this contribution, ${money(currentBudget.surplus-p.monthly)} remains each month for reserves and other goals.`;
      for(const s of scenarios){const tr=document.createElement("tr");for(const value of [s.name,`${s.rate.toFixed(1)}%`,money(s.result.nominal),money(s.result.real),money(Math.max(0,target-s.result.real))]){const td=document.createElement("td");td.textContent=value;tr.append(td);}el("scenarioRows").append(tr);}
      scenarioData={scenarios,target,params:p};drawChart(scenarios);
    });
    el("exportPlan").disabled=!scenarioData;
  }
  function updateDebt() {
    safely("debtResult",()=>{
      const p={balance:read("debtBalance"),apr:read("debtApr"),payment:read("debtPayment")},extra=read("debtExtra");
      if(p.payment+extra>1e6)throw Error("Combined monthly payment must not exceed €1,000,000.");
      const base=F.payoff(p),faster=F.payoff({...p,payment:p.payment+extra});
      const describe=(r,label)=>r.months===null?`${label}: ${r.reason}`:`${label}: ${r.months} months; ${money(r.interest)} interest; ${money(r.total)} total repaid.`;
      show("debtResult",base.months===0?"No outstanding debt":base.months===null?"Review the payment":`${base.months} months to repay`,[describe(base,"Current payment"),describe(faster,"With extra payment"),...(base.months!==null&&faster.months!==null?[`Extra payments save ${base.months-faster.months} months and ${money(Math.max(0,base.interest-faster.interest))} interest in this model.`]:[])]);
    });
  }
  function updateBusiness() {
    el("businessStress").replaceChildren();
    safely("businessResult",()=>{
      const p={fixed:read("bizFixed"),price:read("bizPrice"),variable:read("bizVariable"),units:read("bizUnits"),cash:read("bizCash")},b=F.business(p);
      show("businessResult",`${money(b.profit)} monthly operating ${b.profit<0?"loss":"surplus"}`,[`Revenue: ${money(b.revenue)} · Contribution per unit: ${money(b.margin)}.`,b.breakEven===null?"No profitable break-even: selling price must exceed variable cost per unit.":`Break-even: ${b.breakEven.toLocaleString()} units per month.`,b.runway===null?"No operating cash burn in this simplified scenario.":`Cash runway at this loss: ${b.runway.toFixed(1)} months.`]);
      const units=Math.floor(p.units*.8),stress=F.business({...p,units});
      show("businessStress","What if sales fall 20%?",[`${units.toLocaleString()} units → ${money(stress.profit)} monthly operating result.`,"Stress test assumes unchanged prices and costs, with units rounded down."]);
    });
  }
  function update(){updateBudget();updateGoal();updateDebt();updateBusiness();}
  try {const saved=JSON.parse(localStorage.getItem(key)||"null");if(saved&&saved.version===1&&saved.values&&typeof saved.values==="object"){
    const valid=inputs.every(i=>typeof saved.values[i.id]==="number"&&Number.isFinite(saved.values[i.id])&&saved.values[i.id]>=Number(i.min)&&saved.values[i.id]<=Number(i.max));
    if(valid){for(const i of inputs)i.value=saved.values[i.id];el("planStorage").textContent="Loaded your saved device plan.";}
  }}catch(_){el("planStorage").textContent="Saved plan unavailable. Example inputs are shown.";}
  for(const id of forms){el(id).addEventListener("submit",e=>e.preventDefault());el(id).addEventListener("input",()=>{update();el("planStorage").textContent="Changes are not saved until you choose Save.";});}
  el("savePlan").addEventListener("click",()=>{try{const values=Object.fromEntries(inputs.map(i=>[i.id,read(i.id)]));if(!scenarioData)throw Error("Fix the goal scenario before saving.");localStorage.setItem(key,JSON.stringify({version:1,values}));el("planStorage").textContent="Plan saved on this device. Other people using this browser may access it.";}catch(err){el("planStorage").textContent="Could not save. "+err.message;}});
  el("forgetPlan").addEventListener("click",()=>{try{localStorage.removeItem(key);for(const i of inputs)i.value=i.defaultValue;update();el("planStorage").textContent="Saved plan deleted. Example inputs restored.";}catch(_){el("planStorage").textContent="Could not delete saved data. Use your browser’s site-data settings.";}});
  el("exportPlan").addEventListener("click",()=>{
    if(!scenarioData)return;
    const {scenarios,target,params}=scenarioData;
    const rows=[["Moneliora hypothetical scenarios - not forecasts"],["Currency","EUR"],["Initial",params.initial],["Monthly contribution",params.monthly],["Annual fee percent",params.fee],["Inflation percent",params.inflation],["Goal in today's EUR",target],["Scenario","Annual return percent","Year","Nominal EUR","Today's EUR","Contributed EUR"]];
    for(const s of scenarios)for(const r of s.result.rows)rows.push([s.name,s.rate,r.year,r.nominal.toFixed(2),r.real.toFixed(2),r.contributed.toFixed(2)]);
    const csv=rows.map(row=>row.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(",")).join("\r\n");
    const url=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"})),a=document.createElement("a");a.href=url;a.download="moneliora-scenarios.csv";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    el("planStorage").textContent="Scenario CSV exported with assumptions and annual values.";
  });
  update();
})();
