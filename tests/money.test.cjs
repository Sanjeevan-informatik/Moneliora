const {test}=require('node:test');
const assert=require('node:assert/strict');
const M=require('../static/money.js');
test('decimal amounts become exact integer cents',()=>{
  assert.equal(M.toCents('0.29'),29);assert.equal(M.toCents(0.1)+M.toCents(0.2),30);
  assert.equal(M.toCents('1.2300'),123);assert.equal(M.toCents('1e-2'),1);
  for(const value of [NaN,Infinity,true,null,'0.001','1e-99999',0.1+0.2])assert.throws(()=>M.toCents(value));
});
test('quote totals round once at order boundary, including exact half cents',()=>{
  assert.equal(M.multiplyToCents('1.005',1),101);
  assert.equal(M.multiplyToCents('1.005',2),201);
  assert.equal(M.multiplyToCents('-1.005',1),-101);
  assert.throws(()=>M.multiplyToCents('999999999999999',100));
});
test('repeated virtual cash operations retain every cent',()=>{
  let balance=500000;for(let n=0;n<10000;n++){balance-=M.toCents('0.29');balance+=M.toCents('0.29');}
  assert.equal(balance,500000);
});
test('legacy portfolio migration is exact and idempotent',()=>{
  const old={cash:4999.71,positions:{XIA:1},trades:[{symbol:'XIA',qty:1,amount:0.29,side:'buy',date:'Example'}]};
  const migrated=M.snapshot(old);assert.equal(migrated.cash_cents,499971);assert.equal(migrated.trades[0].amount_cents,29);
  assert.equal('cash' in migrated,false);assert.deepEqual(M.snapshot(migrated),migrated);
  assert.throws(()=>M.snapshot({...old,cash:'NaN'}));assert.throws(()=>M.snapshot({cash_cents:1.5}));
});
