"use strict";
// Cash balances and executed virtual orders use safe integer EUR cents.
// Decimal parsing uses BigInt; quote totals round half away from zero once.
(function(root){
  function scaled(value, quantity=1, round=false){
    if(!['number','string'].includes(typeof value)||!Number.isSafeInteger(quantity)||quantity<0)throw Error('Invalid money input.');
    const text=String(value);if(text.length>128)throw Error('Money input is too long.');
    const match=/^([+-]?)(\d+)(?:\.(\d+))?(?:e([+-]?\d+))?$/i.exec(text);
    if(!match)throw Error('Use a finite decimal amount.');
    const exponent=Number(match[4]||0);if(!Number.isInteger(exponent)||Math.abs(exponent)>1000)throw Error('Amount outside supported range.');
    const fraction=match[3]||'',shift=2+exponent-fraction.length;
    let digits=BigInt(match[2]+fraction)*BigInt(quantity);
    if(shift>=0)digits*=10n**BigInt(shift);
    else{const divisor=10n**BigInt(-shift);if(!round&&digits%divisor!==0n)throw Error('Use at most two decimal places.');digits=(digits+(round?divisor/2n:0n))/divisor;}
    if(match[1]==='-')digits=-digits;
    if(digits>BigInt(Number.MAX_SAFE_INTEGER)||digits<BigInt(Number.MIN_SAFE_INTEGER))throw Error('Amount outside supported range.');
    return Number(digits);
  }
  function cents(value){if(!Number.isSafeInteger(value))throw Error('Integer cents required.');return value;}
  function snapshot(state){
    if(!state||typeof state!=='object')throw Error('Invalid portfolio snapshot.');
    if(state.cash!==undefined&&state.cash_cents!==undefined)throw Error('Ambiguous virtual cash fields.');
    const cash=state.cash_cents===undefined?scaled(state.cash):cents(state.cash_cents);
    if(cash<0||cash>500000)throw Error('Invalid virtual cash balance.');
    if(state.schema_version!==undefined&&state.schema_version!==2)throw Error('Unsupported portfolio version.');
    if(state.trades!==undefined&&!Array.isArray(state.trades))throw Error('Invalid trade history.');
    return {schema_version:2,cash_cents:cash,positions:state.positions||{},trades:(state.trades||[]).map(t=>{
      if(!t||typeof t!=='object'||t.amount!==undefined&&t.amount_cents!==undefined)throw Error('Invalid virtual order fields.');
      const amount=t.amount_cents===undefined?scaled(t.amount):cents(t.amount_cents);
      if(amount<0||amount>500000000)throw Error('Invalid virtual order amount.');
      return {symbol:t.symbol,qty:t.qty,amount_cents:amount,side:t.side,date:t.date};
    })};
  }
  const api={toCents:value=>scaled(value),multiplyToCents:(value,quantity)=>scaled(value,quantity,true),cents,snapshot};
  if(typeof module==='object'&&module.exports)module.exports=api;
  root.MonelioraMoney=api;
})(typeof globalThis==='undefined'?this:globalThis);
