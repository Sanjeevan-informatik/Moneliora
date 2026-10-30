"use strict";
// Account UI is intentionally separate from the locally simulated trading engine.
(() => {
 const $=id=>document.getElementById(id);
 let identity=null;
 const feedback=msg=>{$("accountFeedback").textContent=msg;};
 const post=async(path,body,method="POST")=>{
   const headers={"Content-Type":"application/json"};
   if(identity?.csrf)headers["X-CSRF-Token"]=identity.csrf;
   const r=await fetch(path,{method,headers,credentials:"same-origin",body:JSON.stringify(body)});
   const value=await r.json();
   if(!r.ok)throw Error(typeof value.detail==="string"?value.detail:"Request failed. Please try again.");
   return value;
 };
 const get=async(path)=>{
   const r=await fetch(path,{credentials:"same-origin"}),value=await r.json();
   if(!r.ok)throw Error(typeof value.detail==="string"?value.detail:"Request failed.");
   return value;
 };
 function show(){
   $("accountLoggedOut").hidden=!!identity;$("accountLoggedIn").hidden=!identity;
   if(!identity)return;
   $("accountEmail").textContent=identity.email;
   $("accountPlan").textContent="Account type: "+identity.plan+" · MFA "+(identity.mfa_enabled?"enabled":"not enabled");
   $("adminPanel").hidden=identity.role!=="admin";
   $("enableMFA").disabled=identity.mfa_enabled;
   $("confirmMFA").disabled=identity.mfa_enabled;
 }
 async function submitAuth(form,path){
   const data=Object.fromEntries(new FormData(form).entries());
   if(!data.otp)delete data.otp;
   try{identity=await post(path,data);form.reset();show();feedback("Signed in successfully.");await loadBookings();await checkBilling();}
   catch(err){feedback(err.message);}
 }
 $("registerForm").addEventListener("submit",e=>{e.preventDefault();submitAuth(e.currentTarget,"/api/auth/register");});
 $("loginForm").addEventListener("submit",e=>{e.preventDefault();submitAuth(e.currentTarget,"/api/auth/login");});
 $("logoutButton").addEventListener("click",async()=>{
   try{await post("/api/auth/logout",{});identity=null;show();$("myBookings").replaceChildren();$("adminBookings").replaceChildren();$("mfaSecret").textContent='';feedback("Signed out.");}catch(e){feedback(e.message);}
 });
 $("saveState").addEventListener("click",async()=>{
  try{
   const paper=JSON.parse(localStorage.getItem("moneliora-paper-v3")||"null");
   const saved=MonelioraMoney.snapshot(paper||{cash_cents:500000,positions:{},trades:[]});
   const watch=JSON.parse(localStorage.getItem("moneliora-watch-v1")||"[]");
   await post("/api/account/state",{...saved,watched:Array.isArray(watch)?watch:[]},"PUT");
   feedback("Your demo portfolio snapshot was saved to your account.");
  }catch(e){feedback("Could not save: "+e.message);}
 });
 $("loadState").addEventListener("click",async()=>{
   try{
    const result=await get("/api/account/state");
    if(!result.state){feedback("No saved portfolio yet.");return;}
    const confirmed=confirm("Replace your current local practice portfolio with the saved version? This will reload the page.");
    if(!confirmed)return;
    const s=result.state;
    localStorage.setItem("moneliora-paper-v3",JSON.stringify(MonelioraMoney.snapshot(s)));
    localStorage.setItem("moneliora-watch-v1",JSON.stringify(s.watched));
    location.reload();
   }catch(e){feedback(e.message);}
 });
 $("enableMFA").addEventListener("click",async()=>{
  try{
   const r=await post("/api/auth/mfa/setup",{});
   $("mfaSecret").textContent="Add this secret to your authenticator app, then enter its six-digit code: "+r.secret;
   feedback("MFA setup started. Do not share the secret.");
  }catch(e){feedback(e.message);}
 });
 $("confirmMFA").addEventListener("click",async()=>{
  try{const r=await post("/api/auth/mfa/confirm",{code:$("mfaCode").value.trim()});identity.csrf=r.csrf;identity.mfa_enabled=true;show();$("mfaCode").value='';$("mfaSecret").textContent="MFA is enabled.";feedback("Authenticator enabled.");}
  catch(e){feedback(e.message);}
 });
 function dates(){const today=new Date(),after=new Date(today);after.setDate(after.getDate()+90);const local=d=>d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0")+"-"+String(d.getDate()).padStart(2,"0");$("bookingDate").min=local(today);$("bookingDate").max=local(after);}
 dates();
 $("bookingForm").addEventListener("submit",async e=>{
  e.preventDefault();
  try{const data=Object.fromEntries(new FormData(e.currentTarget).entries());await post("/api/bookings",data);
   e.currentTarget.reset();feedback("Booking request received. It is not confirmed.");await loadBookings();}
  catch(err){feedback(err.message);}
 });
 function olderButton(node,cursor,load){
   node.querySelector('[data-older]')?.remove();
   if(cursor===null||cursor===undefined)return;
   const button=document.createElement('button');button.type='button';button.className='button button-outline';button.dataset.older='true';button.textContent='Load older requests';
   button.addEventListener('click',async()=>{button.disabled=true;try{await load(cursor);}catch(e){feedback(e.message);}finally{button.disabled=false;}});node.append(button);
 }
 async function loadBookings(cursor=null){
  if(!identity)return;
  try{
   const result=await get('/api/bookings'+(cursor?'?cursor='+encodeURIComponent(cursor):'')),node=$("myBookings");
   if(!cursor){node.replaceChildren();const heading=document.createElement('h4');heading.textContent='My requests';node.append(heading);}
   node.querySelector('[data-older]')?.remove();
   for(const b of result.bookings){
    const line=document.createElement("div");line.className="holding";
    const span=document.createElement("span");span.textContent=b.topic+" · "+b.preferred_date+" "+b.preferred_time+" ("+b.status+")";
    line.append(span);
    if(b.status==="pending"){
     const button=document.createElement("button");button.className="button button-outline";button.textContent="Cancel";
     button.addEventListener("click",async()=>{try{await post("/api/bookings/"+b.id,{},"DELETE");await loadBookings();}catch(e){feedback(e.message);}});
     line.append(button);
    }
    node.append(line);
   }
   olderButton(node,result.next_cursor,loadBookings);
   if(identity.role==="admin"&&!cursor)await loadAdmin();
  }catch(e){feedback(e.message);}
 }
 async function loadAdmin(cursor=null){
   const result=await get('/api/admin/bookings'+(cursor?'?cursor='+encodeURIComponent(cursor):'')),node=$("adminBookings");if(!cursor)node.replaceChildren();
   node.querySelector('[data-older]')?.remove();
   for(const b of result.bookings){
    const line=document.createElement("div");line.className="holding";const info=document.createElement("span");
    info.textContent=b.email+" · "+b.topic+" · "+b.preferred_date+" "+b.preferred_time+" · "+b.status;
    const selector=document.createElement("select");selector.setAttribute("aria-label","Status for request "+b.id);
    for(const status of ["pending","confirmed","cancelled"]){const opt=document.createElement("option");opt.value=status;opt.textContent=status;selector.append(opt);}selector.value=b.status;
    selector.addEventListener("change",async()=>{try{await post("/api/admin/bookings/"+b.id,{status:selector.value},"PUT");feedback("Booking status updated.");await loadAdmin();}catch(e){feedback(e.message);}});
    line.append(info,selector);node.append(line);
   }
   olderButton(node,result.next_cursor,loadAdmin);
 }
 async function checkBilling(){
  try{const s=await get("/api/billing/status");$("billingState").textContent=s.checkout_configured?"Subscription checkout available (test with Stripe configured).":"Subscriptions are not configured."; $("premiumCheckout").disabled=!s.checkout_configured;}
  catch(e){$("billingState").textContent="Billing status unavailable.";}
 }
 $("premiumCheckout").addEventListener("click",async()=>{
   try{const result=await post("/api/billing/checkout",{});if(!result.checkout_url.startsWith("https://checkout.stripe.com/"))throw Error("Unexpected checkout URL");location.href=result.checkout_url;}
   catch(e){feedback(e.message);}
 });
 async function init(){try{identity=await get("/api/auth/me");show();await loadBookings();await checkBilling();}
 catch(_){identity=null;show();}}
 init();
})();
