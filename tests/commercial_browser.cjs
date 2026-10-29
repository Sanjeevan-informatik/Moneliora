const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
  const bundle=process.env.MONELIORA_CHROMIUM_MODULE?require(process.env.MONELIORA_CHROMIUM_MODULE).default:null;
  const browser=await chromium.launch(bundle?{executablePath:await bundle.executablePath(),args:bundle.args,headless:true}:{headless:true});
  const base=process.env.MONELIORA_TEST_ORIGIN||'http://127.0.0.1:8000';
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(base);await page.waitForFunction(()=>document.getElementById('offerStatus').textContent.includes('not open'));
    assert.equal(await page.locator('.pilot-select:disabled').count(),2);
    for(const width of [1440,390]){
      await page.setViewportSize({width,height:1000});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
      if(process.env.MONELIORA_SCREENSHOT_DIR)await page.screenshot({path:`${process.env.MONELIORA_SCREENSHOT_DIR}/landing-${width}.png`});
    }
    // UI integration under a synthetic available catalog; real request policy is tested in Python.
    await page.route('**/api/offers',route=>route.fulfill({json:{accepting_requests:true,seller:'Synthetic test operator',privacy_url:'https://example.org/privacy',terms_url:'https://example.org/terms',legal_url:'https://example.org/legal'}}));
    await page.route('**/api/pilot/requests',async route=>{const data=route.request().postDataJSON();assert.equal(data.consent,true);assert.equal(data.offer,'business-basics');await route.fulfill({status:202,json:{message:'Interest recorded. This is not a booking or payment.'}});});
    await page.reload();await page.locator('[data-offer="business-basics"]').click();
    await page.locator('#pilotForm [name=name]').fill('Example Visitor');await page.locator('#pilotForm [name=email]').fill('example@example.org');await page.locator('#pilotForm [name=objective]').fill('Learn to understand contribution margin.');await page.locator('#pilotForm [name=consent]').check();await page.locator('#pilotSubmit').click();
    await page.waitForFunction(()=>document.getElementById('pilotStatus').textContent.includes('not a booking'));
    await page.goto(base+'/launch');assert.match(await page.locator('#launchResults').innerText(),/34.44/);
    await page.locator('#launch-capacity').fill('48');assert.match(await page.locator('#launchResults').innerText(),/fit within 48/);assert.equal(await page.locator('#launchExport').isDisabled(),true);
    await page.locator('#launch-capacity').fill('4');await page.locator('[data-task=scope]').check();await page.locator('#launchSave').click();await page.reload();assert.equal(await page.locator('[data-task=scope]').isChecked(),true);
    const download=page.waitForEvent('download');await page.locator('#launchExport').click();assert.equal((await download).suggestedFilename(),'moneliora-48-hour-experiment.md');
    await page.locator('#launchClear').click();assert.equal(await page.locator('[data-task=scope]').isChecked(),false);
    for(const width of [1440,390]){await page.setViewportSize({width,height:1000});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);if(process.env.MONELIORA_SCREENSHOT_DIR)await page.screenshot({path:`${process.env.MONELIORA_SCREENSHOT_DIR}/launch-${width}.png`});}
    await page.goto(base+'/static/workbook.html');await page.locator('textarea').first().fill('My example question');await page.evaluate(()=>window.dispatchEvent(new Event('beforeprint')));assert.match(await page.locator('.print-value').first().innerText(),/My example question/);await page.emulateMedia({media:'print'});assert.equal(await page.locator('#printWorksheet').isVisible(),false);await page.emulateMedia({media:'screen'});
    let records=[{id:'synthetic-id',name:'Example Person',email:'person@example.org',offer:'guided-planning',objective:'<b>Text stays literal</b>',stage:'new',created_at:'2026-10-28T12:00:00Z',consent_version:'pilot-v1'}];
    await page.route('**/api/admin/pilot**',async route=>{assert.equal(route.request().headers()['x-admin-token'],'x'.repeat(40));const method=route.request().method();if(method==='PATCH'){records[0].stage=route.request().postDataJSON().stage;await route.fulfill({json:{updated:true}});}else if(method==='DELETE'){records=[];await route.fulfill({json:{deleted:true}});}else await route.fulfill({json:{requests:records,counts:{new:records.filter(r=>r.stage==='new').length,qualified:records.filter(r=>r.stage==='qualified').length}}});});
    await page.goto(base+'/operator');await page.locator('#operatorToken').fill('x'.repeat(40));await page.locator('#operatorUnlock').click();await page.locator('#operatorRequests article').waitFor();assert.match(await page.locator('#operatorRequests').innerText(),/<b>Text stays literal<\/b>/);assert.equal(await page.locator('#operatorRequests b').count(),0);assert.equal(await page.locator('#operatorToken').inputValue(),'');
    await page.locator('#operatorRequests select').selectOption('qualified');await page.waitForFunction(()=>document.getElementById('operatorCounts').textContent.includes('qualified: 1'));
    page.once('dialog',dialog=>dialog.accept());await page.locator('#operatorRequests button').click();await page.waitForFunction(()=>document.getElementById('operatorStatus').textContent.includes('No retained requests'));
    await page.locator('#operatorLock').click();assert.equal(await page.locator('#operatorWorkspace').isVisible(),false);assert.equal(await page.evaluate(()=>Object.values(localStorage).some(v=>v.includes('x'.repeat(40)))),false);
    const redirected=page.waitForRequest(r=>r.isNavigationRequest()&&r.url()===base+'/studio?paypal=success');await page.goto(base+'/?paypal=success#account');await redirected;await page.waitForURL(u=>u.pathname==='/studio'&&u.hash==='#account');
    assert.deepEqual(errors,[]);console.log('Commercial browser checks passed: landing, pilot UI with mocked availability, launch calculator/save/export/reset, worksheet print styles, mocked operator workflow, old hash redirect, mobile overflow, JS errors.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
