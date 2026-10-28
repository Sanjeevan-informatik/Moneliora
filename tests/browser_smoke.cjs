// Optional browser regression: install Playwright and Chromium, start the app,
// then run node tests/browser_smoke.cjs. Preview and normal mode are supported.
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
(async()=>{
  const bundled=process.env.MONELIORA_CHROMIUM_MODULE?require(process.env.MONELIORA_CHROMIUM_MODULE).default:null;
  const browser=await chromium.launch(bundled?{executablePath:await bundled.executablePath(),args:bundled.args,headless:true}:{headless:true});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(process.env.MONELIORA_TEST_URL||'http://127.0.0.1:8000');
    await page.locator('#marketCards .market-card').first().waitFor();
    assert.equal(await page.locator('#marketCards .market-card').count(),9);
    await page.locator('#stockSearch').fill('Apple');
    assert.equal(await page.locator('#marketCards .market-card').count(),1);
    await page.locator('#marketCards .star').click();
    assert.match(await page.locator('#watchItems').innerText(),/Apple/);
    await page.locator('#marketCards .button').click();
    await page.locator('#buy').click();
    assert.match(await page.locator('#holdings').innerText(),/Apple/);
    assert.match(await page.locator('#concentration').innerText(),/100.0%/);
    assert.equal(await page.locator('#scenarioRows tr').count(),3);
    await page.locator('#planIncome').fill('0');
    assert.match(await page.locator('#budgetResult').innerText(),/shortfall/);
    await page.locator('#goalRate').fill('50');
    assert.match(await page.locator('#goalResult').innerText(),/Keep all three/);
    assert.equal(await page.locator('#exportPlan').isDisabled(),true);
    assert.equal(await page.locator('#scenarioRows tr').count(),0);
    await page.locator('#goalRate').fill('5');
    await page.locator('#savePlan').click();
    await page.reload();
    assert.equal(await page.locator('#planIncome').inputValue(),'0');
    await page.locator('#debtPayment').fill('0');
    assert.match(await page.locator('#debtResult').innerText(),/does not cover/);
    await page.locator('#bizPrice').fill('10');
    assert.match(await page.locator('#businessResult').innerText(),/No profitable break-even/);
    const downloadEvent=page.waitForEvent('download');await page.locator('#exportPlan').click();
    const download=await downloadEvent;assert.equal(download.suggestedFilename(),'moneliora-scenarios.csv');
    await page.locator('#forgetPlan').click();
    assert.equal(await page.locator('#planIncome').inputValue(),'2800');
    assert.equal(await page.evaluate(()=>localStorage.getItem('moneliora-plan-v1')),null);
    await page.evaluate(()=>localStorage.setItem('moneliora-plan-v1','not-json'));
    await page.reload();
    assert.match(await page.locator('#planStorage').innerText(),/Example inputs/);
    for(const width of [1440,390]){
      await page.setViewportSize({width,height:1000});
      await page.locator('#plan').scrollIntoViewIfNeeded();
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true,`Overflow at ${width}px`);
      if(process.env.MONELIORA_SCREENSHOT_DIR)await page.screenshot({path:`${process.env.MONELIORA_SCREENSHOT_DIR}/plan-${width}.png`});
    }
    assert.deepEqual(errors,[]);
    console.log('Browser smoke passed: explorer, trade, watchlist, calculations, validation, persistence, deletion, export, desktop/mobile overflow, no uncaught JS errors.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
